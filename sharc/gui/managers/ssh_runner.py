import threading
import subprocess
import paramiko
import time
import os
import re
import sys
import queue
from datetime import timedelta
from core.state import get_sharc_root

PROJECT_ROOT = get_sharc_root()


class RunnerManager:
    """
    Backend manager for handling simulation execution.

    This class abstracts the logic for:
    1. Managing SSH connections and Bastion tunnels.
    2. Spawning and monitoring local subprocesses.
    3. orchestrating remote execution via SSH commands.
    4. Parsing stdout streams to update UI progress bars.
    """

    def __init__(self, log_callback, update_row_callback):
        """
        Initializes the RunnerManager.

        Args:
            log_callback (callable): Thread-safe function to append messages to the UI log.
            update_row_callback (callable): Thread-safe function to update the Treeview.
                                            Expects a dict: {iid, status, snap, pct, eta}.
        """
        self.log_callback = log_callback
        self.update_row_callback = update_row_callback

        # SSH State
        self.ssh_client = None
        self.ssh_connected = False

        # Tunnel State
        self.tunnel_process = None

        # Execution Control
        self.running_procs_local = {}  # {iid: subprocess.Popen}
        self.active_threads = []
        self.stop_flags = set()        # Set of iids that should stop

        # Remote base path (could be made configurable)
        self.remote_base_dir = "/home/achiles.mota/SHARC"

    # =========================================================================
    # SSH CONNECTION & TUNNELING
    # =========================================================================

    def connect_ssh_password(self, host, user, port, password):
        """Establishes an SSH connection using a password."""
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=host, port=port, username=user,
                        password=password, timeout=10)
            self.ssh_client = cli
            self.ssh_connected = True
            self.log_callback(f"[SSH] Connected to {user}@{host} (Password)")
        except Exception as e:
            self.ssh_connected = False
            self.ssh_client = None
            self.log_callback(f"[SSH] Connection Error: {e}")
            raise e

    def connect_ssh_key(self, host, user, port, key_path):
        """Establishes an SSH connection using a private key file."""
        #
        # SSH key authentication uses asymmetric cryptography. The private key remains
        # on the client, and the public key is stored on the server.
        try:
            k = paramiko.RSAKey.from_private_key_file(key_path)
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=host, port=port,
                        username=user, pkey=k, timeout=10)

            self.ssh_client = cli
            self.ssh_connected = True
            self.log_callback(f"[SSH] Connected to {user}@{host} (Key)")
        except Exception as e:
            self.ssh_connected = False
            self.log_callback(f"[SSH] Key Connection Error: {e}")
            raise e

    def disconnect_ssh(self):
        """Closes the active SSH connection."""
        if self.ssh_client:
            self.ssh_client.close()
        self.ssh_connected = False
        self.log_callback("[SSH] Disconnected.")

    def create_tunnel(self, bastion_host, bastion_user, bastion_port, int_ip, int_port, loc_port, key_path):
        """
        Creates a local port forwarding tunnel via a Bastion/Jump host using a subprocess.

        Args:
            bastion_host (str): Public IP of the jump host.
            int_ip (str): Private IP of the target machine behind the bastion.
            int_port (int): Port on the target machine.
            loc_port (int): Local port to map to.
            key_path (str): Path to the SSH private key.
        """
        #
        # A bastion host acts as a gateway. We tunnel traffic from 'localhost:loc_port'
        # through the bastion to 'int_ip:int_port'.
        try:
            cmd = [
                "ssh", "-i", key_path, "-N",
                "-L", f"{loc_port}:{int_ip}:{int_port}",
                f"{bastion_user}@{bastion_host}",
                "-p", str(bastion_port)
            ]

            # On Windows, creationflags=subprocess.CREATE_NO_WINDOW hides the cmd window
            flags = 0
            if os.name == 'nt':
                flags = subprocess.CREATE_NO_WINDOW

            self.tunnel_process = subprocess.Popen(cmd, creationflags=flags)
            self.log_callback(f"[TUNNEL] Started on local port {loc_port}")
        except Exception as e:
            self.log_callback(f"[TUNNEL] Error: {e}")

    def close_tunnel(self):
        """Terminates the SSH tunnel process."""
        if self.tunnel_process:
            self.tunnel_process.terminate()
            self.tunnel_process = None
            self.log_callback("[TUNNEL] Closed.")

    # =========================================================================
    # REMOTE UTILITIES (GIT, HTOP, LS)
    # =========================================================================

    def exec_command_output(self, command):
        """Executes a simple remote command and returns stdout as a string."""
        if not self.ssh_connected:
            return "Not connected."
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        return stdout.read().decode(errors="ignore")

    def list_remote_files(self, remote_dir):
        """Lists .yaml/.yml files in a remote directory."""
        if not self.ssh_connected:
            return []
        try:
            cmd = f'find "{remote_dir}" -maxdepth 1 -name "*.yaml" -o -name "*.yml"'
            out = self.exec_command_output(cmd)
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception as e:
            self.log_callback(f"[SSH] Error listing files: {e}")
            return []

    def get_git_branches(self):
        """Fetches and lists available git branches from the remote repository."""
        if not self.ssh_connected:
            return []
        try:
            self.ssh_client.exec_command(
                f"cd {self.remote_base_dir} && git fetch --all --prune")
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
        except:
            return []

    def git_force_checkout(self, branch):
        """Forces a git checkout to a specific branch on the remote server."""
        if not self.ssh_connected:
            return
        cmds = [
            f"cd {self.remote_base_dir}",
            "git fetch --all --prune",
            "git reset --hard",
            "git clean -fd",
            f"git checkout {branch}",
            # Re-configure environment if necessary
            "if [ ! -d .sharc_env/ ]; then python3 -m venv .sharc_env; fi",
            "source .sharc_env/bin/activate && pip install -e ."
        ]
        full_cmd = " && ".join(cmds)

        def _thread_git():
            self.log_callback(f"[GIT] Starting Checkout: {branch}...")
            stdin, stdout, stderr = self.ssh_client.exec_command(full_cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                self.log_callback("[GIT] Checkout completed successfully.")
            else:
                err = stderr.read().decode()
                self.log_callback(f"[GIT] Error ({exit_status}):\n{err}")

        threading.Thread(target=_thread_git, daemon=True).start()

    # =========================================================================
    # LOCAL EXECUTION
    # =========================================================================

    def run_local_parallel(self, file_paths, max_workers):
        """
        Starts local simulations in parallel using a thread pool.

        Args:
            file_paths (list): List of YAML file paths to execute.
            max_workers (int): Maximum number of concurrent simulations.
        """
        semaphore = threading.Semaphore(max_workers)

        for fpath in file_paths:
            t = threading.Thread(target=self._worker_local,
                                 args=(fpath, semaphore), daemon=True)
            self.active_threads.append(t)
            t.start()

    def _worker_local(self, ypath, semaphore):
        """
        Worker thread for a single local simulation.
        Executes the CLI script and parses stdout for progress.
        """
        with semaphore:
            self.update_row_callback(
                {"iid": ypath, "status": "Starting...", "snap": None, "pct": None, "eta": None})

            # Attempt to locate main_cli.py
            main_script = os.path.join(PROJECT_ROOT / "main_cli.py")

            if not os.path.exists(main_script):
                self.log_callback(
                    f"[LOCAL] main_cli.py not found at {main_script}")
                return

            cmd = [sys.executable, main_script, "-p", ypath]

            try:
                #
                # We use subprocess.PIPE to capture the standard output of the simulation script
                # in real-time, allowing us to parse progress logs line by line.
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                self.running_procs_local[ypath] = proc

                total_snaps = 1  # Default value
                current_snap = 0
                t0 = time.time()

                # Regex patterns for progress parsing
                pat_xy = re.compile(
                    r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
                pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

                for line in proc.stdout:
                    line = line.strip()

                    # Parsing Logic
                    m1 = pat_xy.search(line)
                    m2 = pat_hash.search(line)

                    if m1:
                        current_snap = int(m1.group(1))
                        total_snaps = int(m1.group(2))
                    elif m2:
                        current_snap = int(m2.group(1))
                        # If we find Snapshot #X without a total, we assume total might update later

                    if current_snap > 0:
                        pct = (current_snap / max(total_snaps, 1)) * 100
                        elapsed = time.time() - t0
                        rate = elapsed / current_snap
                        remain = (total_snaps - current_snap) * rate
                        eta_str = str(timedelta(seconds=int(remain)))

                        self.update_row_callback({
                            "iid": ypath,
                            "status": "Running",
                            "snap": f"{current_snap}/{total_snaps}",
                            "pct": f"{pct:.1f}",
                            "eta": eta_str
                        })

                proc.wait()
                rc = proc.returncode
                final_status = "Completed" if rc == 0 else f"Error {rc}"
                self.update_row_callback(
                    {"iid": ypath, "status": final_status, "pct": "100" if rc == 0 else "--", "eta": "--"})

            except Exception as e:
                self.log_callback(f"[LOCAL] Error executing {ypath}: {e}")
                self.update_row_callback({"iid": ypath, "status": "Failed"})
            finally:
                if ypath in self.running_procs_local:
                    del self.running_procs_local[ypath]

    # =========================================================================
    # REMOTE EXECUTION
    # =========================================================================

    def run_remote_parallel(self, remote_files, max_workers):
        """
        Starts remote simulations. Assumes files are already accessible on the remote server
        or copies them to a temporary directory before execution.
        """
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Error: Not connected.")
            return

        # 1. Create temporary remote folder
        ts = time.strftime("%Y%m%d_%H%M%S")
        remote_tmp = f"{self.remote_base_dir}/sharc/campaigns/remote_run_{ts}"
        try:
            self.ssh_client.exec_command(f"mkdir -p {remote_tmp}")
            self.log_callback(f"[REMOTE] Temp folder: {remote_tmp}")
        except Exception as e:
            self.log_callback(f"[REMOTE] Failed to create folder: {e}")
            return

        # 2. Stage files (Assumption: copying from remote source to remote temp)
        target_files = []
        for f in remote_files:
            fname = os.path.basename(f)
            new_path = f"{remote_tmp}/{fname}"
            # Copy original remote file to temp remote folder
            self.ssh_client.exec_command(f"cp '{f}' '{new_path}'")
            target_files.append(new_path)

        semaphore = threading.Semaphore(max_workers)
        for rf in target_files:
            # Map temp path back to the original ID in the treeview
            original_id = [k for k in remote_files if os.path.basename(
                k) == os.path.basename(rf)][0]

            t = threading.Thread(
                target=self._worker_remote,
                args=(rf, original_id, semaphore),
                daemon=True
            )
            t.start()

    def _worker_remote(self, remote_path, tree_id, semaphore):
        """Worker thread for a single remote simulation via SSH."""
        with semaphore:
            self.update_row_callback(
                {"iid": tree_id, "status": "Starting Remote...", "snap": "0/--"})

            cmd = (
                f"cd {self.remote_base_dir} && "
                f"source .sharc_env/bin/activate && "
                f"python3 sharc/main_cli.py -p '{remote_path}'"
            )

            try:
                # exec_command returns streams
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    cmd, get_pty=True)

                total_snaps = 1
                current_snap = 0
                t0 = time.time()

                pat_xy = re.compile(
                    r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)

                for line in iter(stdout.readline, ""):
                    line = line.strip()

                    m = pat_xy.search(line)
                    if m:
                        current_snap = int(m.group(1))
                        total_snaps = int(m.group(2))

                        pct = (current_snap / max(total_snaps, 1)) * 100
                        elapsed = time.time() - t0
                        rate = elapsed / max(current_snap, 1)
                        remain = (total_snaps - current_snap) * rate

                        self.update_row_callback({
                            "iid": tree_id,
                            "status": "Running (SSH)",
                            "snap": f"{current_snap}/{total_snaps}",
                            "pct": f"{pct:.1f}",
                            "eta": str(timedelta(seconds=int(remain)))
                        })

                exit_status = stdout.channel.recv_exit_status()
                final = "Completed" if exit_status == 0 else f"Remote Error {exit_status}"
                self.update_row_callback(
                    {"iid": tree_id, "status": final, "pct": "100" if exit_status == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[REMOTE] Worker error: {e}")
                self.update_row_callback(
                    {"iid": tree_id, "status": "SSH Error"})

    def stop_simulations(self, iid_list):
        """Stops running simulations (local or remote)."""
        for iid in iid_list:
            # Local
            if iid in self.running_procs_local:
                p = self.running_procs_local[iid]
                p.terminate()
                self.log_callback(f"Stopping local process: {iid}")

            # Remote (Complex: requires finding PID by filename)
            if self.ssh_connected:
                fname = os.path.basename(iid)
                # Pattern match pkill on the yaml filename
                cmd = f"pkill -f 'python3.*{fname}'"
                self.ssh_client.exec_command(cmd)
                self.update_row_callback({"iid": iid, "status": "Cancelled"})
