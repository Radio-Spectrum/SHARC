import threading
import subprocess
import paramiko
import time
import os
import re
import sys
import uuid
import shutil
from datetime import timedelta
from core.state import get_sharc_root

PROJECT_ROOT = get_sharc_root()
# This dictionary is now actively populated by RunnerManager
SIMULATION_STATUS = dict()


class RunnerManager:
    """
    Backend manager for handling simulation execution.
    """

    def __init__(self, log_callback, update_row_callback):
        self.log_callback = log_callback
        self.update_row_callback = update_row_callback

        # SSH State
        self.ssh_client = None
        self.ssh_connected = False

        # Tunnel State
        self.tunnel_process = None

        # Execution Control
        self.running_procs_local = {}
        self.running_procs_remote = {}
        self.active_threads = []

        # Remote base path (dynamically set on connect)
        self.remote_base_dir = "~/SHARC"

    # =========================================================================
    # STATE MANAGEMENT (FIXED)
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

            # Update the global state registry
            SIMULATION_STATUS[iid].update(data)
        print(SIMULATION_STATUS)
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
                cmd = f"grep -i 'num_snapshots' '{path}'"
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

    # =========================================================================
    # SSH CONNECTION & TUNNELING
    # =========================================================================

    def _cleanup_connection(self):
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
        self.ssh_connected = False

    def connect_ssh_password(self, host, user, port, password):
        self._cleanup_connection()
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=host, port=port, username=user,
                        password=password, timeout=10)
            self.ssh_client = cli
            self.ssh_connected = True
            self._detect_remote_home()
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
            cli.connect(hostname=host, port=port,
                        username=user, pkey=k, timeout=10)
            self.ssh_client = cli
            self.ssh_connected = True
            self._detect_remote_home()
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
            self.log_callback(
                f"[SSH] Remote base set to: {self.remote_base_dir}")
        except:
            self.remote_base_dir = "~/SHARC"

    def disconnect_ssh(self):
        self._cleanup_connection()
        self.log_callback("[SSH] Disconnected.")

    def create_tunnel(self, bastion_host, bastion_user, bastion_port, int_ip, int_port, loc_port, key_path):
        try:
            if not shutil.which("ssh"):
                self.log_callback(
                    "[TUNNEL] Error: 'ssh' executable not found in PATH.")
                return

            cmd = [
                "ssh", "-i", key_path, "-N",
                "-L", f"{loc_port}:{int_ip}:{int_port}",
                f"{bastion_user}@{bastion_host}",
                "-p", str(bastion_port),
                "-o", "StrictHostKeyChecking=no"
            ]

            flags = 0
            if os.name == 'nt':
                flags = subprocess.CREATE_NO_WINDOW

            self.tunnel_process = subprocess.Popen(cmd, creationflags=flags)
            self.log_callback(f"[TUNNEL] Started on local port {loc_port}")
        except Exception as e:
            self.log_callback(f"[TUNNEL] Error: {e}")

    def close_tunnel(self):
        if self.tunnel_process:
            self.tunnel_process.terminate()
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
    # LOCAL EXECUTION
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

            # 1. Pre-fetch total snapshots from YAML
            known_total = self._get_yaml_total_snapshots(
                ypath, is_remote=False)
            if known_total:
                self.log_callback(
                    f"[LOCAL] Config '{os.path.basename(ypath)}' has {known_total} snapshots.")

            main_script = os.path.join(PROJECT_ROOT / "main_cli.py")
            if not os.path.exists(main_script):
                self.log_callback(
                    f"[LOCAL] Error: main_cli.py missing at {main_script}")
                self._emit_status(
                    {"iid": ypath, "status": "Missing Script"})
                return

            cmd = [sys.executable, main_script, "-p", ypath]

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                )
                self.running_procs_local[ypath] = proc

                # Pass known_total to parser
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
    # REMOTE EXECUTION
    # =========================================================================

    def run_remote_parallel(self, file_paths, max_workers):
        """
        file_paths: List of file paths. 
        If user selected remote files (SSH mode), these are REMOTE paths.
        If user selected local files (Local mode), these are LOCAL paths.
        """
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Error: Not connected.")
            return

        semaphore = threading.Semaphore(max_workers)

        for fpath in file_paths:
            t = threading.Thread(
                target=self._worker_remote,
                args=(fpath, fpath, semaphore),  # iid is same as path here
                daemon=True
            )
            t.start()

    def _worker_remote(self, remote_path, tree_id, semaphore):
        with semaphore:
            self._emit_status(
                {"iid": tree_id, "status": "Starting Remote...", "snap": "0/--"})

            # 1. Pre-fetch total snapshots from YAML (Remote grep)
            known_total = self._get_yaml_total_snapshots(
                remote_path, is_remote=True)
            if known_total:
                self.log_callback(
                    f"[REMOTE] Config '{os.path.basename(remote_path)}' has {known_total} snapshots.")

            run_uuid = str(uuid.uuid4())
            self.running_procs_remote[tree_id] = run_uuid

            cmd = (
                f"export SHARC_RUN_ID={run_uuid} && "
                f"cd {self.remote_base_dir} && "
                f"source .sharc_env/bin/activate && "
                f"python3 sharc/main_cli.py -p '{remote_path}'"
            )

            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    cmd, get_pty=True)

                # Pass known_total to parser
                self._parse_progress(
                    stdout, tree_id, known_total=known_total, is_local=False)

                exit_status = stdout.channel.recv_exit_status()
                final = "Completed" if exit_status == 0 else f"Remote Error {exit_status}"
                self._emit_status(
                    {"iid": tree_id, "status": final, "pct": "100" if exit_status == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[REMOTE] Worker error: {e}")
                self._emit_status(
                    {"iid": tree_id, "status": "SSH Error"})
            finally:
                if tree_id in self.running_procs_remote:
                    del self.running_procs_remote[tree_id]

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
                # Log's explicit total overrides config file
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
                    # Fallback if config failed to read AND log is vague
                    status_data["snap"] = f"{current_snap}/?"
                    status_data["pct"] = "--"
                    status_data["eta"] = "--"

                self._emit_status(status_data)

    def stop_simulations(self, iid_list):
        for iid in iid_list:
            if iid in self.running_procs_local:
                try:
                    self.running_procs_local[iid].terminate()
                    self.log_callback(
                        f"[STOP] Local process terminated: {iid}")
                except:
                    pass

            if iid in self.running_procs_remote and self.ssh_connected:
                run_uuid = self.running_procs_remote[iid]
                self.log_callback(
                    f"[STOP] Sending kill signal to remote run {run_uuid}...")

                kill_cmd = f"pkill -f 'SHARC_RUN_ID={run_uuid}'"
                try:
                    self.ssh_client.exec_command(kill_cmd)
                    self._emit_status(
                        {"iid": iid, "status": "Cancelled"})
                except Exception as e:
                    self.log_callback(f"[STOP] Failed to kill remote: {e}")
