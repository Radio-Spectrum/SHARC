import threading
import subprocess
import paramiko
import time
import os
import re
import sys
import uuid
import shutil
import json
import shlex
from datetime import timedelta
from core.state import get_sharc_root

PROJECT_ROOT = get_sharc_root()
# This dictionary is now actively populated by RunnerManager
SIMULATION_STATUS = dict()


class RunnerManager:
    def __init__(self, log_callback, update_row_callback):
        self.log_callback = log_callback
        self.update_row_callback = update_row_callback

        # SSH State
        self.ssh_client = None
        self.ssh_connected = False

        # Tunnel State (local port-forward via system ssh)
        self.tunnel_process = None
        self._tunnel_loc_port = None

        # Execution Control
        self.running_procs_local = {}
        # legacy: tree_id -> run_uuid (str)
        # tmux: tree_id -> dict(run_uuid=..., session=..., log_file=..., mode="tmux")
        self.running_procs_remote = {}
        self.active_threads = []

        # Remote base path (dynamically set on connect)
        self.remote_base_dir = "~/SHARC"
        # Remote entrypoint (relative to remote_base_dir, or absolute)
        self.remote_main_cli_rel = "sharc/main_cli.py"

        # Persistent remote runs directory (set after connect with real $HOME)
        self.remote_runs_dir = "~/.sharc_gui_runs"

        # Prefer tmux protection when available
        self.prefer_tmux = True

        # Remote virtualenv detection state
        self.remote_venv_path = None

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    def _emit_status(self, data):
        """
        Updates the global SIMULATION_STATUS dictionary and triggers the UI callback.
        """
        iid = data.get("iid")
        if iid:
            # Initialize dict for this IID if it doesn't exist
            if iid not in SIMULATION_STATUS:
                SIMULATION_STATUS[iid] = {}

            SIMULATION_STATUS[iid].update(data)

        # Pass data to main.py via the callback for UI row updates
        if self.update_row_callback:
            self.update_row_callback(data)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_yaml_total_snapshots(self, path, is_remote=False):
        """
        Extracts 'num_snapshots: N' from the YAML file to provide accurate
        progress bars even if the log output doesn't specify the total.
        """
        regex = re.compile(r"num_snapshots\s*:\s*(\d+)", re.IGNORECASE)
        try:
            content = ""
            if is_remote:
                # Use grep to fetch only the relevant line to save bandwidth
                if not self.ssh_connected:
                    return 0
                cmd = f"grep -i 'num_snapshots' {shlex.quote(path)}"
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                content = stdout.read().decode().strip()
            else:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()

            match = regex.search(content)
            if match:
                return int(match.group(1))
        except Exception as e:
            # Don't fail the run if we can't parse the config; just log warning
            self.log_callback(
                f"[CONFIG] Could not parse num_snapshots from {path}: {e}")

        return 0

    def _set_paramiko_keepalive(self, seconds: int = 30):
        """
        Avoid SSH idle disconnects in Paramiko transport.
        """
        try:
            if self.ssh_client:
                tr = self.ssh_client.get_transport()
                if tr is not None:
                    tr.set_keepalive(int(seconds))
        except Exception:
            pass

    def _ensure_remote_runs_dir(self):
        """
        Ensure persistent runs directory exists on remote.
        """
        if not self.ssh_connected:
            return
        try:
            self.exec_command_output(f"mkdir -p {self.remote_runs_dir}")
        except Exception:
            pass

    def _remote_has_tmux(self) -> bool:
        """
        Check if tmux exists on remote.
        """
        if not self.ssh_connected:
            return False
        try:
            out = self.exec_command_output(
                "command -v tmux >/dev/null 2>&1; echo $?")
            return out.strip().endswith("0")
        except Exception:
            return False

    def _quote_remote_single(self, value: str) -> str:
        return "'" + str(value).replace("'", "'\''") + "'"

    def _detect_remote_venv(self, log_result: bool = True):
        """
        Detect a usable virtualenv inside the configured remote_base_dir.
        Returns the activate script path or None.
        """
        self.remote_venv_path = None
        if not self.ssh_connected:
            return None

        base_dir = (self.remote_base_dir or "").strip()
        if not base_dir:
            return None

        candidates = [".venv", "venv", ".sharc_env", "env"]
        py = r'''
import json, os
base = os.path.expanduser({base_dir!r})
candidates = {candidates!r}
found = None
for name in candidates:
    act = os.path.join(base, name, "bin", "activate")
    if os.path.isfile(act):
        found = act
        break
print(json.dumps({{"found": found, "base": base}}))
'''.format(base_dir=base_dir, candidates=candidates)
        cmd = "python3 - <<'PY'\n" + py + "\nPY"

        try:
            out = self.exec_command_output(cmd).strip()
            info = json.loads(out) if out else {}
            found = info.get("found")
            resolved_base = info.get("base") or base_dir
            if resolved_base:
                self.remote_base_dir = resolved_base
            self.remote_venv_path = found or None
            if log_result:
                if self.remote_venv_path:
                    self.log_callback(
                        f"[VENV] Found remote virtualenv: {self.remote_venv_path}")
                else:
                    self.log_callback(
                        f"[VENV] No virtualenv found in {self.remote_base_dir} (checked: {', '.join(candidates)}).")
            return self.remote_venv_path
        except Exception as e:
            if log_result:
                self.log_callback(f"[VENV] Detection error: {e}")
            return None

    def _build_remote_activation_prefix(self) -> str:
        """
        Build a shell-safe prefix that activates the detected remote virtualenv.
        Detection is refreshed on demand if needed.
        """
        venv_path = self.remote_venv_path or self._detect_remote_venv(log_result=False)
        if venv_path:
            quoted = self._quote_remote_single(venv_path)
            return (
                f"if [ -f {quoted} ]; then "
                f"echo '[VENV] Activating {venv_path}'; "
                f"source {quoted}; "
                f"else echo '[VENV] Activation script not found: {venv_path}'; fi"
            )
        return "echo '[VENV] No virtualenv detected. Running with system Python.'"


    def _build_remote_python_entrypoint(self, remote_path: str) -> str:
        """
        Build the remote Python command preserving configured main_cli path when possible.
        Falls back to module execution for backwards compatibility.
        """
        main_cli = (self.remote_main_cli_rel or "").strip()
        if main_cli and main_cli.endswith('.py'):
            return f"python3 {shlex.quote(main_cli)} -p {shlex.quote(remote_path)}"
        if main_cli:
            return f"python3 -m {main_cli} -p {shlex.quote(remote_path)}"
        # Fallback to avoid infinite recursion
        return f"python3 sharc/main_cli.py -p {shlex.quote(remote_path)}"

    # =========================================================================
    # SSH CONNECTION & TUNNELING
    # =========================================================================

    def _cleanup_connection(self):
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
        self.ssh_connected = False

    def connect_ssh_password(self, host, user, port, password):
        self._cleanup_connection()
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )
            self.ssh_client = cli
            self.ssh_connected = True
            self._detect_remote_home()
            self._set_paramiko_keepalive(30)
            self._ensure_remote_runs_dir()
            self._detect_remote_venv(log_result=True)
            self.log_callback(f"[SSH] Connected to {user}@{host} (Password)")
        except Exception as e:
            self._cleanup_connection()
            self.log_callback(f"[SSH] Connection Error: {e}")
            raise e

    def connect_ssh_key(self, host, user, port, key_path):
        self._cleanup_connection()
        try:
            k = paramiko.RSAKey.from_private_key_file(key_path)
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(
                hostname=host,
                port=port,
                username=user,
                pkey=k,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )
            self.ssh_client = cli
            self.ssh_connected = True
            self._detect_remote_home()
            self._set_paramiko_keepalive(30)
            self._ensure_remote_runs_dir()
            self._detect_remote_venv(log_result=True)
            self.log_callback(f"[SSH] Connected to {user}@{host} (Key)")
        except Exception as e:
            self._cleanup_connection()
            self.log_callback(f"[SSH] Key Connection Error: {e}")
            raise e

    def _detect_remote_home(self):
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command("echo $HOME")
            home = stdout.read().decode().strip()
            self.remote_base_dir = f"{home}/SHARC"
            self.remote_runs_dir = f"{home}/.sharc_gui_runs"
            self.remote_venv_path = None
            self.log_callback(
                f"[SSH] Remote base set to: {self.remote_base_dir}")
        except Exception:
            self.remote_base_dir = "~/SHARC"
            self.remote_runs_dir = "~/.sharc_gui_runs"
            self.remote_venv_path = None

    def disconnect_ssh(self):
        self._cleanup_connection()
        self.log_callback("[SSH] Disconnected.")

    def create_tunnel(self, bastion_host, bastion_user, bastion_port, int_ip, int_port, loc_port, key_path):
        """
        Create local port-forward tunnel using system 'ssh'.

        Fixes / improvements (non-breaking):
        - Bind explicitly on 127.0.0.1 (avoid localhost/IPv6 mismatch)
        - ExitOnForwardFailure=yes (fail-fast)
        - Keepalive options to avoid idle drop
        - Capture stderr and log real cause if ssh exits early
        """
        try:
            if not shutil.which("ssh"):
                self.log_callback(
                    "[TUNNEL] Error: 'ssh' executable not found in PATH.")
                return

            # Close existing
            try:
                if self.tunnel_process and self.tunnel_process.poll() is None:
                    self.close_tunnel()
            except Exception:
                pass

            self._tunnel_loc_port = int(loc_port)

            cmd = [
                "ssh",
                "-i", key_path,
                "-N",
                "-L", f"127.0.0.1:{loc_port}:{int_ip}:{int_port}",
                f"{bastion_user}@{bastion_host}",
                "-p", str(bastion_port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "TCPKeepAlive=yes",
                "-o", "IdentitiesOnly=yes",
            ]

            flags = 0
            if os.name == 'nt':
                flags = subprocess.CREATE_NO_WINDOW

            self.tunnel_process = subprocess.Popen(
                cmd,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True
            )

            time.sleep(0.8)

            if self.tunnel_process.poll() is not None:
                err = ""
                try:
                    err = (self.tunnel_process.stderr.read() or "").strip()
                except Exception:
                    pass
                self.tunnel_process = None
                self.log_callback(
                    f"[TUNNEL] Failed to start. ssh exited early. {err}")
                return

            self.log_callback(
                f"[TUNNEL] Started (keepalive) on 127.0.0.1:{loc_port}")
        except Exception as e:
            self.log_callback(f"[TUNNEL] Error: {e}")

    def close_tunnel(self):
        if self.tunnel_process:
            try:
                self.tunnel_process.terminate()
                try:
                    self.tunnel_process.wait(timeout=2)
                except Exception:
                    try:
                        self.tunnel_process.kill()
                    except Exception:
                        pass
            except Exception:
                pass
            self.tunnel_process = None
            self.log_callback("[TUNNEL] Closed.")

    # =========================================================================
    # REMOTE UTILITIES
    # =========================================================================

    def exec_command_output(self, command):
        if not self.ssh_connected:
            return "Not connected."
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        return stdout.read().decode(errors="ignore")

    def list_remote_files(self, remote_dir):
        if not self.ssh_connected:
            return []
        try:
            py = f"import os, glob; d=os.path.expanduser({repr(remote_dir)}); print('\\n'.join(glob.glob(d+'/*.yaml')+glob.glob(d+'/*.yml')))"
            cmd = f"python3 -c {shlex.quote(py)}"
            out = self.exec_command_output(cmd)
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception as e:
            self.log_callback(f"[SSH] Error listing files: {e}")
            return []

    def upload_yaml_files(self, local_paths, remote_dir, overwrite=True):
        """
        Upload one or more local YAML files (.yaml/.yml) to a directory on the remote server.
        Keeps existing RunnerManager behavior intact; adds only a convenience API for RunnerTab.

        Args:
            local_paths (list[str]): local file paths
            remote_dir (str): remote directory to place files (created if missing)
            overwrite (bool): if True, overwrite remote files with same name
        Returns:
            list[str]: list of remote file paths successfully uploaded
        """
        if not self.ssh_connected:
            raise RuntimeError("Not connected")

        if not local_paths:
            return []

        # Expand ~ on remote side and ensure directory exists
        remote_dir_q = remote_dir.strip() if remote_dir else ""
        if not remote_dir_q:
            raise ValueError("remote_dir is empty")

        # Open SFTP
        sftp = None
        uploaded = []
        try:
            # Normalize remote_dir absolute path (resolve ~)
            try:
                # paramiko doesn't expand ~; ask remote shell for it
                resolved = self.exec_command_output(
                    f"python3 -c 'import os; print(os.path.expanduser({json.dumps(remote_dir_q)}))'"
                ).strip()
                remote_dir_resolved = resolved if resolved else remote_dir_q
            except Exception:
                remote_dir_resolved = remote_dir_q

            # Ensure remote dir exists safely after expanding `~`
            self.exec_command_output(f"mkdir -p {shlex.quote(remote_dir_resolved)}")

            sftp = self.ssh_client.open_sftp()

            for lp in local_paths:
                if not lp:
                    continue
                lp = os.path.abspath(lp)
                if not os.path.isfile(lp):
                    continue
                base = os.path.basename(lp)
                if not (base.lower().endswith(".yaml") or base.lower().endswith(".yml")):
                    continue
                rp = remote_dir_resolved.rstrip("/") + "/" + base

                if not overwrite:
                    try:
                        sftp.stat(rp)
                        # exists
                        continue
                    except Exception:
                        pass

                self.log_callback(f"[SFTP] Upload: {lp} -> {rp}")
                sftp.put(lp, rp)
                uploaded.append(rp)

            if uploaded:
                self.log_callback(f"[SFTP] Uploaded {len(uploaded)} file(s) to {remote_dir_resolved}")
            else:
                self.log_callback("[SFTP] Nothing uploaded (no valid .yaml/.yml files selected).")
            return uploaded
        finally:
            try:
                if sftp is not None:
                    sftp.close()
            except Exception:
                pass




    def set_remote_paths(self, base_dir=None, main_cli=None, runs_dir=None):
        # Update remote paths without breaking existing behavior.
        changed_base = False
        if base_dir:
            self.remote_base_dir = base_dir
            changed_base = True
        if main_cli:
            self.remote_main_cli_rel = main_cli
        if runs_dir:
            self.remote_runs_dir = runs_dir

        if changed_base:
            self.remote_venv_path = None
            self.log_callback(f"[SSH] Remote base set to: {self.remote_base_dir}")

        if self.ssh_connected and (changed_base or runs_dir):
            self._ensure_remote_runs_dir()
            self._detect_remote_venv(log_result=True)

    def detect_remote_sharc_paths(self):
        # Best-effort detection of repo base and main_cli on the remote.
        if not self.ssh_connected:
            raise RuntimeError("Not connected")

        candidates = [
            self.remote_base_dir,
            "~/SHARC",
            "~/sharc",
            "~",
        ]
        
        # Safely resolve tilde (~) expansion globally on the remote machine
        try:
            py_resolve = "python3 -c 'import os, json, sys; print(json.dumps([os.path.expanduser(p) for p in sys.argv[1:]]))' " + " ".join(shlex.quote(c) for c in candidates if c)
            out = self.exec_command_output(py_resolve).strip()
            if out:
                candidates = json.loads(out)
        except Exception:
            pass

        main_candidates = [
            "sharc/main_cli.py",
            "main_cli.py",
            "sharc/cli/main_cli.py",
        ]

        for base in candidates:
            ok_git = self.exec_command_output(f"test -d {shlex.quote(base)}/.git && echo OK || true").strip() == "OK"
            if not ok_git:
                continue
            for mc in main_candidates:
                ok = self.exec_command_output(f"test -f {shlex.quote(base)}/{shlex.quote(mc)} && echo OK || true").strip() == "OK"
                if ok:
                    self.remote_base_dir = base
                    self.remote_main_cli_rel = mc
                    self.remote_venv_path = None
                    self._detect_remote_venv(log_result=True)
                    return {"remote_base_dir": base, "remote_main_cli_rel": mc}

        # fallback: find main_cli.py near home (limited depth)
        out = self.exec_command_output("find ~ -maxdepth 5 -type f -name main_cli.py 2>/dev/null | head -n 5 || true")
        first = (out.splitlines() or [""])[0].strip()
        if first:
            p = first.replace("\\", "/")
            if "/sharc/" in p:
                base = p.split("/sharc/")[0]
                rel = "sharc/" + p.split("/sharc/")[1]
            else:
                base = os.path.dirname(p)
                rel = os.path.basename(p)
            if base:
                self.remote_base_dir = base
            if rel:
                self.remote_main_cli_rel = rel
            self.remote_venv_path = None
            self._detect_remote_venv(log_result=True)
            return {"remote_base_dir": self.remote_base_dir, "remote_main_cli_rel": self.remote_main_cli_rel}

        return {"remote_base_dir": self.remote_base_dir, "remote_main_cli_rel": self.remote_main_cli_rel}

    def list_remote_dir(self, path: str):
        # Structured listing for remote browser (python3 on remote; falls back to ls).
        if not self.ssh_connected:
            return []
        p = (path or "~").strip() or "~"
        py = r'''
import os, json, time
p = os.path.expanduser(%(p)s)
items = []
try:
    for name in os.listdir(p):
        fp = os.path.join(p, name)
        try:
            st = os.stat(fp)
            items.append({
                "name": name,
                "full_path": fp,
                "is_dir": os.path.isdir(fp),
                "size": st.st_size,
                "mtime": time.strftime("%%Y-%%m-%%d %%H:%%M:%%S", time.localtime(st.st_mtime)),
            })
        except Exception:
            items.append({"name": name, "full_path": fp, "is_dir": os.path.isdir(fp), "size": "", "mtime": ""})
except Exception:
    pass
print(json.dumps(items))
'''
        cmd = "python3 - <<'PY'\n" + (py % {"p": repr(p)}) + "\nPY"
        out = self.exec_command_output(cmd)
        try:
            return json.loads(out or "[]")
        except Exception:
            out2 = self.exec_command_output(f"ls -A1p {shlex.quote(p)} 2>/dev/null || true")
            items = []
            for line in (out2 or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                is_dir = line.endswith("/")
                name = line[:-1] if is_dir else line
                fp = p.rstrip("/") + "/" + name if p not in ("~", "") else name
                items.append({"name": name, "full_path": fp, "is_dir": is_dir, "size": "", "mtime": ""})
            return items
    def get_git_branches(self):
        if not self.ssh_connected:
            return []
        try:
            self.log_callback("[GIT] Fetching remote branches...")
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f"cd {self.remote_base_dir} && git fetch --all --prune"
            )
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                self.log_callback(
                    f"[GIT] Fetch failed: {stderr.read().decode()}")
                return []

            out = self.exec_command_output(
                f"cd {self.remote_base_dir} && git branch -a")
            branches = set()
            for line in out.splitlines():
                line = line.strip().replace("*", "").strip()
                if "->" in line:
                    continue
                if line.startswith("remotes/origin/"):
                    line = line.replace("remotes/origin/", "")
                if line:
                    branches.add(line)
            return sorted(list(branches))
        except Exception as e:
            self.log_callback(f"[GIT] Error: {e}")
            return []

    def git_force_checkout(self, branch):
        if not self.ssh_connected:
            return
            
        venv_path = self.remote_venv_path or self._detect_remote_venv(log_result=False)
        if venv_path:
            # Re-use existing virtual environment
            venv_rel = os.path.dirname(os.path.dirname(venv_path))
            setup_venv = "true"
        else:
            # Fallback to creating a new one if not found
            venv_rel = ".venv"
            venv_path = f"{venv_rel}/bin/activate"
            setup_venv = f"if [ ! -d {shlex.quote(venv_rel)} ]; then python3 -m venv {shlex.quote(venv_rel)}; fi"
            
        cmds = [
            f"cd {shlex.quote(self.remote_base_dir)}",
            "git fetch --all --prune",
            "git reset --hard",
            "git clean -fd",
            f"git checkout {shlex.quote(branch)}",
            setup_venv,
            f"source {shlex.quote(venv_path)} && pip install -e ."
        ]
        full_cmd = " && ".join(cmds)

        def _thread_git():
            self.log_callback(f"[GIT] Starting Checkout: {branch}...")
            stdin, stdout, stderr = self.ssh_client.exec_command(
                full_cmd, get_pty=True)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                self.remote_venv_path = None
                self._detect_remote_venv(log_result=True)
                self.log_callback("[GIT] Checkout completed successfully.")
            else:
                out_log = stdout.read().decode()
                self.log_callback(f"[GIT] Error ({exit_status}):\n{out_log}")

        threading.Thread(target=_thread_git, daemon=True).start()

    # =========================================================================
    # LOCAL EXECUTION (unchanged)
    # =========================================================================

    def run_local_parallel(self, file_paths, max_workers):
        self.active_threads = [t for t in self.active_threads if t.is_alive()]
        semaphore = threading.Semaphore(max_workers)
        for fpath in file_paths:
            t = threading.Thread(target=self._worker_local,
                                 args=(fpath, semaphore), daemon=True)
            self.active_threads.append(t)
            t.start()

    def _worker_local(self, ypath, semaphore):
        with semaphore:
            self._emit_status(
                {"iid": ypath, "status": "Starting...", "snap": None})

            known_total = self._get_yaml_total_snapshots(
                ypath, is_remote=False)
            if known_total:
                self.log_callback(
                    f"[LOCAL] Config '{os.path.basename(ypath)}' has {known_total} snapshots.")

            main_script = os.path.join(PROJECT_ROOT / "main_cli.py")
            if not os.path.exists(main_script):
                self.log_callback(
                    f"[LOCAL] Error: main_cli.py missing at {main_script}")
                self._emit_status({"iid": ypath, "status": "Missing Script"})
                return

            cmd = [sys.executable, main_script, "-p", ypath]

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                )
                self.running_procs_local[ypath] = proc

                self._parse_progress(proc.stdout, ypath,
                                     known_total=known_total, is_local=True)

                proc.wait()
                rc = proc.returncode
                final = "Completed" if rc == 0 else f"Error {rc}"
                self._emit_status(
                    {"iid": ypath, "status": final, "pct": "100" if rc == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[LOCAL] Exception: {e}")
                self._emit_status({"iid": ypath, "status": "Failed"})
            finally:
                if ypath in self.running_procs_local:
                    del self.running_procs_local[ypath]

    # =========================================================================
    # REMOTE EXECUTION (legacy + tmux protection)
    # =========================================================================


    def run_remote_parallel(self, file_paths, max_workers):
        """Run remote YAMLs in parallel, preserving legacy mode and tmux packs."""
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Error: Not connected.")
            return

        file_paths = [p for p in (file_paths or []) if p]
        if not file_paths:
            self.log_callback("[REMOTE] No files selected.")
            return

        self._set_paramiko_keepalive(30)
        self._ensure_remote_runs_dir()
        self._detect_remote_venv(log_result=True)

        use_tmux = bool(self.prefer_tmux and self._remote_has_tmux())
        pack_uuid = None
        session_name = None
        if use_tmux:
            pack_uuid, session_name = self._new_pack_identity(file_paths)
            self.log_callback(f"[REMOTE] tmux detected: starting pack session '{session_name}' with {len(file_paths)} file(s).")
        else:
            self.log_callback("[REMOTE] tmux not available: using legacy SSH exec mode.")

        self.active_threads = [t for t in self.active_threads if t.is_alive()]
        semaphore = threading.Semaphore(max(1, int(max_workers or 1)))
        for index, fpath in enumerate(file_paths, start=1):
            t = threading.Thread(
                target=self._worker_remote,
                args=(fpath, fpath, semaphore, use_tmux, pack_uuid, session_name, index),
                daemon=True,
            )
            self.active_threads.append(t)
            t.start()


    def _worker_remote(self, remote_path, tree_id, semaphore, use_tmux=False, pack_uuid=None, session_name=None, window_index=1):
        with semaphore:
            self._emit_status({"iid": tree_id, "status": "Starting Remote...", "snap": "0/--", "pct": "0.0%"})
            known_total = self._get_yaml_total_snapshots(remote_path, is_remote=True)
            if known_total:
                self.log_callback(f"[REMOTE] Config '{os.path.basename(remote_path)}' has {known_total} snapshots.")
            run_uuid = str(uuid.uuid4())
            try:
                if use_tmux:
                    meta = self._start_remote_tmux_run(
                        tree_id=tree_id,
                        remote_path=remote_path,
                        run_uuid=run_uuid,
                        pack_uuid=pack_uuid,
                        session_name=session_name,
                        window_index=window_index,
                    )
                    self.running_procs_remote[tree_id] = meta
                    self._poll_remote_log_and_parse(
                        tree_id=tree_id,
                        log_file=meta["log_file"],
                        known_total=known_total,
                        run_uuid=run_uuid,
                        session_name=meta.get("session"),
                    )
                    final = self._infer_tmux_final_status(run_uuid)
                    self._emit_status({
                        "iid": tree_id,
                        "status": final,
                        "pct": "100.0%" if final == "Completed" else "--",
                        "pct_value": 100.0 if final == "Completed" else 0.0,
                    })
                    return

                self.running_procs_remote[tree_id] = run_uuid
                activation_prefix = self._build_remote_activation_prefix()
                cmd = (
                    f"export SHARC_RUN_ID={run_uuid} && "
                    f"cd {shlex.quote(self.remote_base_dir)} && "
                    f"{activation_prefix} && "
                    'export PYTHONPATH="$PWD":$PYTHONPATH && ' +
                    self._build_remote_python_entrypoint(remote_path)
                )
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd, get_pty=True)
                self._parse_progress(stdout, tree_id, known_total=known_total, is_local=False)
                exit_status = stdout.channel.recv_exit_status()
                final = "Completed" if exit_status == 0 else f"Remote Error {exit_status}"
                self._emit_status({
                    "iid": tree_id,
                    "status": final,
                    "pct": "100.0%" if exit_status == 0 else "--",
                    "pct_value": 100.0 if exit_status == 0 else 0.0,
                })
            except Exception as e:
                self.log_callback(f"[REMOTE] Worker error: {e}")
                self._emit_status({"iid": tree_id, "status": "SSH Error", "pct": "--"})
            finally:
                meta = self.running_procs_remote.get(tree_id)
                if isinstance(meta, str):
                    del self.running_procs_remote[tree_id]


    def _new_pack_identity(self, file_paths):
        """Create one tmux pack identity for a batch of YAML files."""
        stamp = int(time.time())
        joined = "|".join(os.path.basename(p or "") for p in (file_paths or []))
        digest = uuid.uuid5(uuid.NAMESPACE_DNS, joined + str(stamp)).hex[:8]
        pack_uuid = f"pack_{digest}"
        session_name = f"sharc_pack_{digest}"
        return pack_uuid, session_name


    def _tmux_session_exists(self, session_name: str) -> bool:
        if not self.ssh_connected or not session_name:
            return False
        try:
            out = self.exec_command_output(f"tmux has-session -t {shlex.quote(session_name)} >/dev/null 2>&1; echo $?")
            return out.strip().endswith("0")
        except Exception:
            return False



    def _tmux_window_exists(self, session_name: str, window_name: str) -> bool:
        if not self.ssh_connected or not session_name or not window_name:
            return False
        try:
            out = self.exec_command_output(f"tmux list-windows -t {shlex.quote(session_name)} -F '#{{window_name}}' 2>/dev/null || true")
            names = {line.strip() for line in (out or "").splitlines() if line.strip()}
            return window_name in names
        except Exception:
            return False

    def _start_remote_tmux_run(self, tree_id: str, remote_path: str, run_uuid: str,
                               pack_uuid: str = None, session_name: str = None,
                               window_index: int = 1) -> dict:
        """Start a protected run in tmux using one session per pack and one window per YAML."""
        self._ensure_remote_runs_dir()
        session = session_name or f"sharc_pack_{run_uuid[:8]}"
        pack_uuid = pack_uuid or run_uuid
        safe_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', os.path.basename(remote_path) or f'job_{window_index}')
        window_name = f"{window_index:02d}_{safe_name[:40]}"
        log_file = f"{self.remote_runs_dir}/run_{run_uuid}.log"
        meta_file = f"{self.remote_runs_dir}/run_{run_uuid}.json"
        activation = self._build_remote_activation_prefix()

        sim_cmd = (
            f"echo '[PACK] {session} | file: {os.path.basename(remote_path)}'; "
            f"echo '[VENV] Preparing remote environment...'; "
            f"export SHARC_RUN_ID={shlex.quote(run_uuid)}; "
            f"export SHARC_PACK_ID={shlex.quote(pack_uuid)}; "
            f"cd {shlex.quote(self.remote_base_dir)}; "
            f"{activation}; "
            'export PYTHONPATH="$PWD":$PYTHONPATH; ' +
            self._build_remote_python_entrypoint(remote_path) +
            f" 2>&1 | tee -a {shlex.quote(log_file)}; "
            f"rc=$?; echo '__SHARC_DONE__:'$rc | tee -a {shlex.quote(log_file)}; exit $rc"
        )

        meta = {
            "run_uuid": run_uuid,
            "pack_uuid": pack_uuid,
            "session": session,
            "window": window_name,
            "window_name": window_name,
            "log_file": log_file,
            "remote_path": remote_path,
            "tree_id": tree_id,
            "remote_base_dir": self.remote_base_dir,
            "created_at": int(time.time()),
            "mode": "tmux",
        }
        self.exec_command_output(f"mkdir -p {self.remote_runs_dir} && : > {shlex.quote(log_file)}")
        self.exec_command_output(f"printf %s {shlex.quote(json.dumps(meta))} > {shlex.quote(meta_file)}")
        session_exists = self._tmux_session_exists(session)
        base_cmd = 'bash -lc ' + shlex.quote(sim_cmd)
        if not session_exists:
            tmux_cmd = f"tmux new-session -d -s {shlex.quote(session)} -n {shlex.quote(window_name)} {shlex.quote(base_cmd)}"
            self.log_callback(f"[TMUX] Starting protected pack session: {session}")
        else:
            tmux_cmd = f"tmux new-window -t {shlex.quote(session)} -n {shlex.quote(window_name)} {shlex.quote(base_cmd)}"
            self.log_callback(f"[TMUX] Adding window '{window_name}' to pack session: {session}")
        out = self.exec_command_output(tmux_cmd + " 2>&1 || true")
        if out.strip():
            self.log_callback(f"[TMUX] tmux output: {out.strip()}")
        if not self._tmux_session_exists(session):
            tail = self.exec_command_output(f"tail -n 80 {shlex.quote(log_file)} 2>/dev/null || true")
            raise RuntimeError(f"tmux session did not start. Log tail:\n{tail}")
        self.log_callback(f"[TMUX] Session/window running: {session}:{window_name} | Log: {log_file}")
        return {"run_uuid": run_uuid, "pack_uuid": pack_uuid, "session": session, "window": window_name, "window_name": window_name, "log_file": log_file, "mode": "tmux"}


    def _tail_remote_log_and_parse(self, tree_id: str, log_file: str, known_total: int = 0):
        self._poll_remote_log_and_parse(tree_id=tree_id, log_file=log_file, known_total=known_total)

    def _poll_remote_log_and_parse(self, tree_id: str, log_file: str, known_total: int = 0,
                                   run_uuid: str = None, session_name: str = None,
                                   poll_interval: float = 1.2, max_idle_cycles: int = 10):
        if not self.ssh_connected:
            return
        start_time = time.time()
        total_snaps = known_total or 0
        current_snap = 0
        sent_count = 0
        idle_cycles = 0
        pat_prog = re.compile(r"(?:snapshot|step|snap).*?(\d+)\s*(?:/|of)\s*(\d+)", re.IGNORECASE)
        pat_step = re.compile(r"(?:snapshot|step|snap).*?#?(\d+)", re.IGNORECASE)
        while self.ssh_connected:
            cmd = f"python3 - <<'PY'\nimport os\np=os.path.expanduser({log_file!r})\nif os.path.exists(p):\n os.system(f'tail -n +{{1 + {sent_count}}} \"{{p}}\"')\nPY"
            raw = self.exec_command_output(cmd)
            lines = raw.splitlines()
            if lines:
                for line in lines:
                    clean_text = line.strip()
                    if not clean_text:
                        continue
                    self.log_callback(f"[SSH] {clean_text}")
                    if "__SHARC_DONE__:" in clean_text:
                        idle_cycles = max_idle_cycles
                        break
                    m_prog = pat_prog.search(clean_text)
                    m_step = pat_step.search(clean_text)
                    if m_prog:
                        current_snap = int(m_prog.group(1))
                        total_snaps = int(m_prog.group(2))
                    elif m_step:
                        current_snap = int(m_step.group(1))
                    if current_snap > 0:
                        status = {"iid": tree_id, "status": "Running (SSH/tmux)"}
                        if total_snaps > 0:
                            pct = (current_snap / total_snaps) * 100.0
                            status["snap"] = f"{current_snap}/{total_snaps}"
                            status["pct"] = f"{pct:.1f}%"
                            status["pct_value"] = max(0.0, min(100.0, pct))
                            elapsed = max(0.0, time.time() - start_time)
                            if elapsed > 0 and current_snap > 0:
                                rate = elapsed / current_snap
                                remaining = max(0, total_snaps - current_snap)
                                status["eta"] = str(timedelta(seconds=int(remaining * rate)))
                            else:
                                status["eta"] = "Calc..."
                        else:
                            status["snap"] = f"{current_snap}/?"
                            status["pct"] = "--"
                            status["pct_value"] = 0.0
                            status["eta"] = "--"
                        self._emit_status(status)
                sent_count += len(lines)
                idle_cycles = 0
            else:
                idle_cycles += 1
            if raw and "__SHARC_DONE__:" in raw:
                break
            alive = True
            if session_name:
                alive = self._tmux_session_exists(session_name)
            if not alive and idle_cycles >= 2:
                break
            if idle_cycles >= max_idle_cycles:
                if run_uuid:
                    tail = self.exec_command_output(f"tail -n 20 {shlex.quote(log_file)} 2>/dev/null || true")
                    if "__SHARC_DONE__:" in tail:
                        break
                if not alive:
                    break
            time.sleep(max(0.3, float(poll_interval)))

    def _infer_tmux_final_status(self, run_uuid: str) -> str:
        try:
            log_file = f"{self.remote_runs_dir}/run_{run_uuid}.log"
            tail = self.exec_command_output(
                f"tail -n 120 {shlex.quote(log_file)} 2>/dev/null || true")
            m = re.search(r"__SHARC_DONE__:(\d+)", tail)
            if m:
                rc = int(m.group(1))
                return "Completed" if rc == 0 else f"Remote Error {rc}"
            if tail.strip():
                return "Stopped/Unknown"
        except Exception:
            pass
        return "Unknown"

    # ---- resume API (used by RunnerTab) -------------------------------------


    def list_remote_runs(self):
        if not self.ssh_connected:
            return []
        self._ensure_remote_runs_dir()
        try:
            out = self.exec_command_output(f"ls -1 {self.remote_runs_dir}/run_*.json 2>/dev/null || true")
            files = [x.strip() for x in out.splitlines() if x.strip()]
            runs = []
            for f in files:
                js = self.exec_command_output(f"cat {shlex.quote(f)} 2>/dev/null || true")
                try:
                    meta = json.loads(js)
                except Exception:
                    continue
                session = meta.get("session")
                window = meta.get("window") or meta.get("window_name")
                run_uuid = meta.get("run_uuid")
                log_file = meta.get("log_file")
                session_alive = bool(session and self._tmux_session_exists(session))
                window_alive = bool(session_alive and window and self._tmux_window_exists(session, window))
                final_status = self._infer_tmux_final_status(run_uuid) if run_uuid else "Completed"
                if session_alive and window_alive:
                    state = "running"
                elif session_alive:
                    state = "pack-alive"
                else:
                    state = "done" if final_status == "Completed" else "orphaned"
                meta["window"] = window
                meta["window_name"] = window
                meta["session_alive"] = session_alive
                meta["window_alive"] = window_alive
                meta["state"] = state
                meta["final_status"] = final_status
                meta["log_file"] = log_file
                runs.append(meta)
            runs.sort(key=lambda r: int(r.get("created_at", 0)), reverse=True)
            return runs
        except Exception as e:
            self.log_callback(f"[REMOTE] list_remote_runs error: {e}")
            return []


    def reconcile_persisted_runs(self, remove_orphans: bool = False):
        if not self.ssh_connected:
            return 0
        self._ensure_remote_runs_dir()
        out = self.exec_command_output(f"ls -1 {self.remote_runs_dir}/run_*.json 2>/dev/null || true")
        files = [x.strip() for x in out.splitlines() if x.strip()]
        orphan_count = 0
        for f in files:
            js = self.exec_command_output(f"cat {shlex.quote(f)} 2>/dev/null || true")
            try:
                meta = json.loads(js)
            except Exception:
                continue
            sess = meta.get("session")
            if sess and not self._tmux_session_exists(sess):
                orphan_count += 1
                if remove_orphans:
                    log_file = meta.get("log_file")
                    rm_cmd = f"rm -f {shlex.quote(f)}"
                    if log_file:
                        rm_cmd += f" {shlex.quote(log_file)}"
                    self.exec_command_output(rm_cmd + " 2>/dev/null || true")
        if remove_orphans:
            self.log_callback(f"[REMOTE] Removed {orphan_count} orphaned persisted run(s).")
        else:
            self.log_callback(f"[REMOTE] Found {orphan_count} orphaned persisted run(s).")
        return orphan_count

    def clear_sharc_tmux_sessions(self, remove_persisted_orphans: bool = True):
        if not self.ssh_connected:
            self.log_callback("[TMUX] Not connected.")
            return {"cleared": 0, "removed_orphans": 0}
        cmd = "tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -E '^(sharc_pack_|sharc_)' || true"
        out = self.exec_command_output(cmd)
        sessions = [x.strip() for x in (out or "").splitlines() if x.strip()]
        cleared = 0
        for sess in sessions:
            self.log_callback(f"[TMUX] Killing session: {sess}")
            self.exec_command_output(f"tmux kill-session -t {shlex.quote(sess)} 2>/dev/null || true")
            cleared += 1
        if not sessions:
            self.log_callback("[TMUX] No SHARC tmux sessions to clear.")
        else:
            self.log_callback(f"[TMUX] Cleared {cleared} SHARC tmux session(s).")
        removed = self.reconcile_persisted_runs(remove_orphans=True) if remove_persisted_orphans else 0
        return {"cleared": cleared, "removed_orphans": removed}

    def clear_all_tmux_sessions(self, remove_metadata: bool = False):
        return self.clear_sharc_tmux_sessions(remove_persisted_orphans=remove_metadata)

    def resume_remote_run(self, run_uuid: str, tree_id: str = None):
        """
        Resume (reattach) by tailing the persistent log and parsing progress again.
        Does not require the original GUI session to be alive.
        """
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Not connected.")
            return

        self._ensure_remote_runs_dir()
        meta_file = f"{self.remote_runs_dir}/run_{run_uuid}.json"
        js = self.exec_command_output(
            f"cat {shlex.quote(meta_file)} 2>/dev/null || true")
        if not js.strip():
            self.log_callback(f"[REMOTE] No metadata for run_uuid={run_uuid}")
            return

        try:
            meta = json.loads(js)
        except Exception:
            self.log_callback(
                f"[REMOTE] Invalid metadata JSON for run_uuid={run_uuid}")
            return

        iid = tree_id or meta.get("tree_id") or run_uuid
        log_file = meta.get("log_file")
        sess = meta.get("session")

        if not log_file:
            self.log_callback("[REMOTE] Missing log_file in metadata.")
            return

        alive = bool(sess and self._tmux_session_exists(sess))
        self.log_callback(
            f"[REMOTE] Resuming run {run_uuid} (tmux alive={alive}). Tailing log...")

        self._emit_status(
            {"iid": iid, "status": "Resuming (SSH/tmux)...", "pct": "--", "snap": "0/--"})
        self._tail_remote_log_and_parse(iid, log_file, known_total=0)

        if sess and not self._tmux_session_exists(sess):
            final = self._infer_tmux_final_status(run_uuid)
            self._emit_status({"iid": iid, "status": final,
                              "pct": "100" if final == "Completed" else "--"})

    # =========================================================================
    # PARSE PROGRESS (original)
    # =========================================================================

    def _parse_progress(self, stream, iid, known_total=0, is_local=True):
        """
        Parses output stream.
        known_total: If > 0, used as the total count if the log only says 'Step X'.
        """
        total_snaps = known_total
        current_snap = 0
        start_time = time.time()

        pat_prog = re.compile(
            r"(?:snapshot|step|snap).*?(\d+)\s*(?:/|of)\s*(\d+)", re.IGNORECASE)
        pat_step = re.compile(
            r"(?:snapshot|step|snap).*?#?(\d+)", re.IGNORECASE)

        iterator = iter(stream.readline, "") if not is_local else stream

        for line in iterator:
            if not line:
                break
            clean_text = line.strip()

            if clean_text:
                prefix = "[LOCAL]" if is_local else "[SSH]"
                self.log_callback(f"{prefix} {clean_text}")

            m_prog = pat_prog.search(clean_text)
            m_step = pat_step.search(clean_text)

            if m_prog:
                current_snap = int(m_prog.group(1))
                total_snaps = int(m_prog.group(2))
            elif m_step:
                if not m_prog:
                    current_snap = int(m_step.group(1))

            if current_snap > 0:
                status_data = {
                    "iid": iid,
                    "status": "Running" if is_local else "Running (SSH)",
                }

                if total_snaps > 0:
                    pct = (current_snap / total_snaps) * 100
                    status_data["snap"] = f"{current_snap}/{total_snaps}"
                    status_data["pct"] = f"{pct:.1f}%"

                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        rate = elapsed / current_snap
                        remaining = total_snaps - current_snap
                        eta_seconds = remaining * rate
                        status_data["eta"] = str(
                            timedelta(seconds=int(eta_seconds)))
                    else:
                        status_data["eta"] = "Calc..."
                else:
                    status_data["snap"] = f"{current_snap}/?"
                    status_data["pct"] = "--"
                    status_data["eta"] = "--"

                self._emit_status(status_data)

    # =========================================================================
    # STOP SIMULATIONS (keeps original + tmux support)
    # =========================================================================


    def stop_simulations(self, iid_list):
        for iid in iid_list:
            if iid in self.running_procs_local:
                try:
                    self.running_procs_local[iid].terminate()
                    self.log_callback(f"[STOP] Local process terminated: {iid}")
                except Exception:
                    pass
            if iid in self.running_procs_remote and self.ssh_connected:
                meta = self.running_procs_remote[iid]
                if isinstance(meta, dict) and meta.get("mode") == "tmux":
                    sess = meta.get("session")
                    win = meta.get("window") or meta.get("window_name")
                    run_uuid = meta.get("run_uuid")
                    try:
                        if sess and win and self._tmux_window_exists(sess, win):
                            self.log_callback(f"[STOP] Killing tmux window {sess}:{win}...")
                            target = f"{sess}:{win}"
                            self.ssh_client.exec_command(f"tmux kill-window -t {shlex.quote(target)} 2>/dev/null || true")
                        elif sess:
                            self.log_callback(f"[STOP] Killing tmux session {sess}...")
                            self.ssh_client.exec_command(f"tmux kill-session -t {shlex.quote(sess)} 2>/dev/null || true")
                    except Exception as e:
                        self.log_callback(f"[STOP] Failed to kill tmux target: {e}")
                    if run_uuid:
                        kill_cmd = f"pkill -f 'SHARC_RUN_ID={run_uuid}'"
                        try:
                            self.ssh_client.exec_command(kill_cmd)
                        except Exception as e:
                            self.log_callback(f"[STOP] Failed to kill remote: {e}")
                    self._emit_status({"iid": iid, "status": "Cancelled", "pct": "--"})
                    continue
                run_uuid = meta if isinstance(meta, str) else None
                if run_uuid:
                    self.log_callback(f"[STOP] Sending kill signal to remote run {run_uuid}...")
                    kill_cmd = f"pkill -f 'SHARC_RUN_ID={run_uuid}'"
                    try:
                        self.ssh_client.exec_command(kill_cmd)
                        self._emit_status({"iid": iid, "status": "Cancelled", "pct": "--"})
                    except Exception as e:
                        self.log_callback(f"[STOP] Failed to kill remote: {e}")

