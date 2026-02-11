import threading
import subprocess
import paramiko
import time
import os
import re
import sys
import uuid
import queue
from datetime import timedelta
from core.state import get_sharc_root

PROJECT_ROOT = get_sharc_root()


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
        self.running_procs_local = {}  # {iid: subprocess.Popen}
        self.running_procs_remote = {}  # {iid: unique_run_uuid} for safe killing
        self.active_threads = []

        # Remote base path (dynamically set on connect)
        self.remote_base_dir = "~/SHARC"

    # =========================================================================
    # SSH CONNECTION & TUNNELING
    # =========================================================================

    def _cleanup_connection(self):
        """Ensures previous connections are closed before new ones."""
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
        """Finds the actual home directory to avoid hardcoded users."""
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
            # Check if ssh is available in path, otherwise warn user
            if not shutil.which("ssh"):
                self.log_callback(
                    "[TUNNEL] Error: 'ssh' executable not found in PATH.")
                return

            cmd = [
                "ssh", "-i", key_path, "-N",
                "-L", f"{loc_port}:{int_ip}:{int_port}",
                f"{bastion_user}@{bastion_host}",
                "-p", str(bastion_port),
                "-o", "StrictHostKeyChecking=no"  # Prevent interactive yes/no prompts
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
            # Use 'find' carefully or ls
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
            # FIX: Wait for fetch to complete before listing branches
            self.log_callback("[GIT] Fetching remote branches...")
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f"cd {self.remote_base_dir} && git fetch --all --prune"
            )
            exit_status = stdout.channel.recv_exit_status()  # BLOCKING WAIT

            if exit_status != 0:
                self.log_callback(
                    f"[GIT] Fetch failed: {stderr.read().decode()}")
                return []

            out = self.exec_command_output(
                f"cd {self.remote_base_dir} && git branch -a"
            )

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

        # Improved command chain
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
            # Use get_pty=True to combine stdout/stderr often helps with git output
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
    # (Kept mostly same, added safe regex checks)

    def run_local_parallel(self, file_paths, max_workers):
        semaphore = threading.Semaphore(max_workers)
        for fpath in file_paths:
            t = threading.Thread(target=self._worker_local,
                                 args=(fpath, semaphore), daemon=True)
            self.active_threads.append(t)
            t.start()

    def _worker_local(self, ypath, semaphore):
        with semaphore:
            self.update_row_callback(
                {"iid": ypath, "status": "Starting...", "snap": None})

            main_script = os.path.join(PROJECT_ROOT / "main_cli.py")
            if not os.path.exists(main_script):
                self.log_callback(
                    f"[LOCAL] Error: main_cli.py missing at {main_script}")
                self.update_row_callback(
                    {"iid": ypath, "status": "Missing Script"})
                return

            cmd = [sys.executable, main_script, "-p", ypath]

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                )
                self.running_procs_local[ypath] = proc

                self._parse_progress(proc.stdout, ypath, is_local=True)

                proc.wait()
                rc = proc.returncode
                final = "Completed" if rc == 0 else f"Error {rc}"
                self.update_row_callback(
                    {"iid": ypath, "status": final, "pct": "100" if rc == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[LOCAL] Exception: {e}")
                self.update_row_callback({"iid": ypath, "status": "Failed"})
            finally:
                if ypath in self.running_procs_local:
                    del self.running_procs_local[ypath]

    # =========================================================================
    # REMOTE EXECUTION
    # =========================================================================

    def run_remote_parallel(self, local_file_paths, max_workers):
        """
        Args:
            local_file_paths (list): List of LOCAL paths to yaml files. 
                                     These must be uploaded first.
        """
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Error: Not connected.")
            return

        ts = time.strftime("%Y%m%d_%H%M%S")
        remote_tmp_dir = f"{self.remote_base_dir}/sharc/campaigns/remote_run_{ts}"

        # 1. Create Remote Dir
        try:
            self.ssh_client.exec_command(f"mkdir -p {remote_tmp_dir}")
            self.log_callback(f"[REMOTE] Created temp dir: {remote_tmp_dir}")
        except Exception as e:
            self.log_callback(f"[REMOTE] Failed to create dir: {e}")
            return

        # 2. Upload Files via SFTP (FIXED from 'cp')
        sftp = None
        try:
            sftp = self.ssh_client.open_sftp()
        except Exception as e:
            self.log_callback(f"[REMOTE] SFTP Failure: {e}")
            return

        tasks = []
        for local_path in local_file_paths:
            fname = os.path.basename(local_path)
            remote_path = f"{remote_tmp_dir}/{fname}"

            try:
                # Upload local file to remote path
                sftp.put(local_path, remote_path)
                # Store tuple: (Remote Path, Original Tree ID/Local Path)
                tasks.append((remote_path, local_path))
            except Exception as e:
                self.log_callback(f"[REMOTE] Upload failed for {fname}: {e}")

        sftp.close()

        # 3. Start Workers
        semaphore = threading.Semaphore(max_workers)
        for r_path, original_id in tasks:
            t = threading.Thread(
                target=self._worker_remote,
                args=(r_path, original_id, semaphore),
                daemon=True
            )
            t.start()

    def _worker_remote(self, remote_path, tree_id, semaphore):
        with semaphore:
            self.update_row_callback(
                {"iid": tree_id, "status": "Starting Remote...", "snap": "0/--"})

            # Generate a unique ID for this specific run to safely kill it later if needed
            run_uuid = str(uuid.uuid4())
            self.running_procs_remote[tree_id] = run_uuid

            # Pass UUID as env var SHARC_RUN_ID so we can pkill -f "SHARC_RUN_ID=<uuid>"
            # checking pgrep availability might be good, but assuming standard linux here.
            cmd = (
                f"export SHARC_RUN_ID={run_uuid} && "
                f"cd {self.remote_base_dir} && "
                f"source .sharc_env/bin/activate && "
                f"python3 sharc/main_cli.py -p '{remote_path}'"
            )

            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    cmd, get_pty=True)

                # Parse output
                self._parse_progress(stdout, tree_id, is_local=False)

                exit_status = stdout.channel.recv_exit_status()
                final = "Completed" if exit_status == 0 else f"Remote Error {exit_status}"
                self.update_row_callback(
                    {"iid": tree_id, "status": final, "pct": "100" if exit_status == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[REMOTE] Worker error: {e}")
                self.update_row_callback(
                    {"iid": tree_id, "status": "SSH Error"})
            finally:
                if tree_id in self.running_procs_remote:
                    del self.running_procs_remote[tree_id]

    def _parse_progress(self, stream, iid, is_local=True):
        """Shared logic for parsing stdout from local or remote streams."""
        total_snaps = 1
        current_snap = 0
        t0 = time.time()

        pat_xy = re.compile(
            r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
        pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

        # iter(readline, "") handles both local file-like and paramiko channels well
        iterator = iter(stream.readline, "") if not is_local else stream

        for line in iterator:
            if not line:
                break
            line = line.strip()

            m1 = pat_xy.search(line)
            m2 = pat_hash.search(line)

            if m1:
                current_snap = int(m1.group(1))
                total_snaps = int(m1.group(2))
            elif m2:
                current_snap = int(m2.group(1))

            if current_snap > 0 and total_snaps > 0:
                pct = (current_snap / total_snaps) * 100
                elapsed = time.time() - t0
                # Avoid ZeroDivision
                rate = elapsed / current_snap
                remain = (total_snaps - current_snap) * rate

                status_str = "Running" if is_local else "Running (SSH)"

                self.update_row_callback({
                    "iid": iid,
                    "status": status_str,
                    "snap": f"{current_snap}/{total_snaps}",
                    "pct": f"{pct:.1f}",
                    "eta": str(timedelta(seconds=int(remain)))
                })

    def stop_simulations(self, iid_list):
        for iid in iid_list:
            # Local Stop
            if iid in self.running_procs_local:
                try:
                    self.running_procs_local[iid].terminate()
                    self.log_callback(
                        f"[STOP] Local process terminated: {iid}")
                except:
                    pass

            # Remote Stop (Safe UUID kill)
            if iid in self.running_procs_remote and self.ssh_connected:
                run_uuid = self.running_procs_remote[iid]
                self.log_callback(
                    f"[STOP] Sending kill signal to remote run {run_uuid}...")

                # We grep for the UUID in the environment variable to find the PID
                # This prevents killing other users' processes or identically named files.
                kill_cmd = f"pkill -f 'SHARC_RUN_ID={run_uuid}'"
                try:
                    self.ssh_client.exec_command(kill_cmd)
                    self.update_row_callback(
                        {"iid": iid, "status": "Cancelled"})
                except Exception as e:
                    self.log_callback(f"[STOP] Failed to kill remote: {e}")
