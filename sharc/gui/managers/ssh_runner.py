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

        # Persistent remote runs directory (set after connect with real $HOME)
        self.remote_runs_dir = "~/.sharc_gui_runs"

        # Prefer tmux protection when available
        self.prefer_tmux = True

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
            self.log_callback(
                f"[SSH] Remote base set to: {self.remote_base_dir}")
        except Exception:
            self.remote_base_dir = "~/SHARC"
            self.remote_runs_dir = "~/.sharc_gui_runs"

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
            cmd = f'ls "{remote_dir}"/*.yaml "{remote_dir}"/*.yml 2>/dev/null'
            out = self.exec_command_output(cmd)
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception as e:
            self.log_callback(f"[SSH] Error listing files: {e}")
            return []

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
        cmds = [
            f"cd {self.remote_base_dir}",
            "git fetch --all --prune",
            "git reset --hard",
            "git clean -fd",
            f"git checkout {branch}",
            "if [ ! -d .sharc_env/ ]; then python3 -m venv .sharc_env; fi",
            "source .sharc_env/bin/activate && pip install -e ."
        ]
        full_cmd = " && ".join(cmds)

        def _thread_git():
            self.log_callback(f"[GIT] Starting Checkout: {branch}...")
            stdin, stdout, stderr = self.ssh_client.exec_command(
                full_cmd, get_pty=True)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                self.log_callback("[GIT] Checkout completed successfully.")
            else:
                out_log = stdout.read().decode()
                self.log_callback(f"[GIT] Error ({exit_status}):\n{out_log}")

        threading.Thread(target=_thread_git, daemon=True).start()

    # =========================================================================
    # LOCAL EXECUTION (unchanged)
    # =========================================================================

    def run_local_parallel(self, file_paths, max_workers):
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
        """
        file_paths: list of remote yaml paths
        Preserves original behavior, but uses tmux for protection if available and prefer_tmux=True.
        """
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Error: Not connected.")
            return

        self._set_paramiko_keepalive(30)
        self._ensure_remote_runs_dir()

        use_tmux = bool(self.prefer_tmux and self._remote_has_tmux())
        if use_tmux:
            self.log_callback(
                "[REMOTE] tmux detected: runs will be protected (detached sessions).")
        else:
            self.log_callback(
                "[REMOTE] tmux not available: using legacy SSH exec mode.")

        semaphore = threading.Semaphore(max_workers)

        for fpath in file_paths:
            t = threading.Thread(
                target=self._worker_remote,
                args=(fpath, fpath, semaphore, use_tmux),
                daemon=True
            )
            t.start()

    def _worker_remote(self, remote_path, tree_id, semaphore, use_tmux=False):
        with semaphore:
            self._emit_status(
                {"iid": tree_id, "status": "Starting Remote...", "snap": "0/--"})

            known_total = self._get_yaml_total_snapshots(
                remote_path, is_remote=True)
            if known_total:
                self.log_callback(
                    f"[REMOTE] Config '{os.path.basename(remote_path)}' has {known_total} snapshots.")

            run_uuid = str(uuid.uuid4())

            try:
                if use_tmux:
                    meta = self._start_remote_tmux_run(
                        tree_id, remote_path, run_uuid)
                    self.running_procs_remote[tree_id] = meta

                    # Tail log and parse; if UI closes, tmux continues
                    self._tail_remote_log_and_parse(
                        tree_id, meta["log_file"], known_total=known_total)

                    # If tail ends, mark completed if tmux ended (best-effort)
                    if not self._tmux_session_exists(meta["session"]):
                        final = self._infer_tmux_final_status(run_uuid)
                        self._emit_status(
                            {"iid": tree_id, "status": final, "pct": "100" if final == "Completed" else "--"})
                    else:
                        # keep running status; do not overwrite with failure
                        self._emit_status(
                            {"iid": tree_id, "status": "Running (SSH/tmux)", "pct": "--"})
                    return

                # --- legacy mode (original) ---
                self.running_procs_remote[tree_id] = run_uuid

                cmd = (
                    f"export SHARC_RUN_ID={run_uuid} && "
                    f"cd {self.remote_base_dir} && "
                    f"source .sharc_env/bin/activate && "
                    f"python3 sharc/main_cli.py -p {shlex.quote(remote_path)}"
                )

                stdin, stdout, stderr = self.ssh_client.exec_command(
                    cmd, get_pty=True)

                self._parse_progress(
                    stdout, tree_id, known_total=known_total, is_local=False)

                exit_status = stdout.channel.recv_exit_status()
                final = "Completed" if exit_status == 0 else f"Remote Error {exit_status}"
                self._emit_status(
                    {"iid": tree_id, "status": final, "pct": "100" if exit_status == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[REMOTE] Worker error: {e}")
                self._emit_status({"iid": tree_id, "status": "SSH Error"})
            finally:
                # keep tmux metadata so user can resume later
                meta = self.running_procs_remote.get(tree_id)
                if isinstance(meta, str):
                    del self.running_procs_remote[tree_id]

    # ---- tmux helpers --------------------------------------------------------

    def _tmux_session_exists(self, session_name: str) -> bool:
        if not self.ssh_connected:
            return False
        try:
            out = self.exec_command_output(
                f"tmux has-session -t {shlex.quote(session_name)} >/dev/null 2>&1; echo $?")
            return out.strip().endswith("0")
        except Exception:
            return False

    def _start_remote_tmux_run(self, tree_id: str, remote_path: str, run_uuid: str) -> dict:
        """
        Start protected run in tmux, tee output to a persistent log file.
        Also writes a metadata JSON file to enable resume.
        """
        self._ensure_remote_runs_dir()

        session = f"sharc_{run_uuid[:8]}"
        log_file = f"{self.remote_runs_dir}/run_{run_uuid}.log"
        meta_file = f"{self.remote_runs_dir}/run_{run_uuid}.json"

        sim_cmd = (
            f"export SHARC_RUN_ID={shlex.quote(run_uuid)}; "
            f"cd {shlex.quote(self.remote_base_dir)}; "
            f"source .sharc_env/bin/activate; "
            f"python3 sharc/main_cli.py -p {shlex.quote(remote_path)} "
            f"2>&1 | tee -a {shlex.quote(log_file)}; "
            f"echo '__SHARC_DONE__:$?' | tee -a {shlex.quote(log_file)}"
        )

        # create/clear log, write metadata first
        meta = {
            "run_uuid": run_uuid,
            "session": session,
            "log_file": log_file,
            "remote_path": remote_path,
            "tree_id": tree_id,
            "remote_base_dir": self.remote_base_dir,
            "created_at": int(time.time()),
            "mode": "tmux",
        }

        self.exec_command_output(
            f"mkdir -p {self.remote_runs_dir} && : > {shlex.quote(log_file)}")
        self.exec_command_output(
            f"printf %s {shlex.quote(json.dumps(meta))} > {shlex.quote(meta_file)}")

        # run inside tmux detached
        tmux_cmd = f"tmux new-session -d -s {shlex.quote(session)} {shlex.quote('bash -lc ' + shlex.quote(sim_cmd))}"
        self.log_callback(f"[TMUX] Starting protected session: {session}")
        out = self.exec_command_output(tmux_cmd + " 2>&1 || true")
        if out.strip():
            self.log_callback(f"[TMUX] tmux output: {out.strip()}")

        if not self._tmux_session_exists(session):
            tail = self.exec_command_output(
                f"tail -n 80 {shlex.quote(log_file)} 2>/dev/null || true")
            raise RuntimeError(
                f"tmux session did not start. Log tail:\n{tail}")

        self.log_callback(f"[TMUX] Session running. Log: {log_file}")
        return {"run_uuid": run_uuid, "session": session, "log_file": log_file, "mode": "tmux"}

    def _tail_remote_log_and_parse(self, tree_id: str, log_file: str, known_total: int = 0):
        cmd = f"tail -n +1 -F {shlex.quote(log_file)}"
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd, get_pty=True)
        self._parse_progress(
            stdout, tree_id, known_total=known_total, is_local=False)
        try:
            stdout.channel.close()
        except Exception:
            pass

    def _infer_tmux_final_status(self, run_uuid: str) -> str:
        try:
            log_file = f"{self.remote_runs_dir}/run_{run_uuid}.log"
            tail = self.exec_command_output(
                f"tail -n 120 {shlex.quote(log_file)} 2>/dev/null || true")
            m = re.search(r"__SHARC_DONE__:(\d+)", tail)
            if m:
                rc = int(m.group(1))
                return "Completed" if rc == 0 else f"Remote Error {rc}"
        except Exception:
            pass
        return "Completed"

    # ---- resume API (used by RunnerTab) -------------------------------------

    def list_remote_runs(self):
        """
        List persisted tmux runs (metadata) in remote_runs_dir.
        Returns list[dict] with keys:
          run_uuid, session, log_file, remote_path, created_at, session_alive
        """
        if not self.ssh_connected:
            return []
        self._ensure_remote_runs_dir()
        try:
            out = self.exec_command_output(
                f"ls -1 {self.remote_runs_dir}/run_*.json 2>/dev/null || true")
            files = [x.strip() for x in out.splitlines() if x.strip()]
            runs = []
            for f in files:
                js = self.exec_command_output(
                    f"cat {shlex.quote(f)} 2>/dev/null || true")
                try:
                    meta = json.loads(js)
                except Exception:
                    continue
                sess = meta.get("session")
                meta["session_alive"] = bool(
                    sess and self._tmux_session_exists(sess))
                runs.append(meta)

            # sort newest first
            runs.sort(key=lambda r: int(r.get("created_at", 0)), reverse=True)
            return runs
        except Exception as e:
            self.log_callback(f"[REMOTE] list_remote_runs error: {e}")
            return []

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
                    self.log_callback(
                        f"[STOP] Local process terminated: {iid}")
                except Exception:
                    pass

            if iid in self.running_procs_remote and self.ssh_connected:
                meta = self.running_procs_remote[iid]

                # tmux mode
                if isinstance(meta, dict) and meta.get("mode") == "tmux":
                    sess = meta.get("session")
                    run_uuid = meta.get("run_uuid")
                    if sess:
                        self.log_callback(
                            f"[STOP] Killing tmux session {sess}...")
                        try:
                            self.ssh_client.exec_command(
                                f"tmux kill-session -t {shlex.quote(sess)} 2>/dev/null || true")
                        except Exception as e:
                            self.log_callback(
                                f"[STOP] Failed to kill tmux: {e}")

                    if run_uuid:
                        # fallback kill by SHARC_RUN_ID as well
                        kill_cmd = f"pkill -f 'SHARC_RUN_ID={run_uuid}'"
                        try:
                            self.ssh_client.exec_command(kill_cmd)
                        except Exception as e:
                            self.log_callback(
                                f"[STOP] Failed to kill remote: {e}")

                    self._emit_status({"iid": iid, "status": "Cancelled"})
                    continue

                # legacy mode: meta is run_uuid string (original behavior)
                run_uuid = meta if isinstance(meta, str) else None
                if run_uuid:
                    self.log_callback(
                        f"[STOP] Sending kill signal to remote run {run_uuid}...")
                    kill_cmd = f"pkill -f 'SHARC_RUN_ID={run_uuid}'"
                    try:
                        self.ssh_client.exec_command(kill_cmd)
                        self._emit_status({"iid": iid, "status": "Cancelled"})
                    except Exception as e:
                        self.log_callback(f"[STOP] Failed to kill remote: {e}")
