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
    def __init__(self, log_callback, update_row_callback):
        """
        :param log_callback: Função (thread-safe) para enviar strings ao log da UI.
        :param update_row_callback: Função (thread-safe) para atualizar a Treeview.
                                    Espera um dict: {iid, status, snap, pct, eta}
        """
        self.log_callback = log_callback
        self.update_row_callback = update_row_callback

        # Estado SSH
        self.ssh_client = None
        self.ssh_connected = False

        # Estado Túnel
        self.tunnel_process = None

        # Controle de Execução
        self.running_procs_local = {}  # {iid: subprocess.Popen}
        self.active_threads = []
        self.stop_flags = set()        # Conjunto de iids que devem parar

        # Caminho base no servidor (pode ser tornado configurável)
        self.remote_base_dir = "/home/achiles.mota/SHARC"

    # =========================================================================
    # CONEXÃO SSH & TÚNEL
    # =========================================================================

    def connect_ssh_password(self, host, user, port, password):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=host, port=port, username=user,
                        password=password, timeout=10)
            self.ssh_client = cli
            self.ssh_connected = True
            self.log_callback(f"[SSH] Conectado a {user}@{host} (Senha)")
        except Exception as e:
            self.ssh_connected = False
            self.ssh_client = None
            self.log_callback(f"[SSH] Erro na conexão: {e}")
            raise e

    def connect_ssh_key(self, host, user, port, key_path):
        try:
            # Tenta usar o comando ssh do sistema (mais robusto para configs de ~/.ssh/config)
            # ou Paramiko se preferir. O código original usava subprocess para "chave/túnel" local.
            # Aqui vamos tentar Paramiko com chave para manter consistência,
            # mas se a chave tiver passphrase, precisaria de tratamento extra.

            k = paramiko.RSAKey.from_private_key_file(key_path)
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=host, port=port,
                        username=user, pkey=k, timeout=10)

            self.ssh_client = cli
            self.ssh_connected = True
            self.log_callback(f"[SSH] Conectado a {user}@{host} (Chave)")
        except Exception as e:
            self.ssh_connected = False
            self.log_callback(f"[SSH] Erro na conexão por chave: {e}")
            raise e

    def disconnect_ssh(self):
        if self.ssh_client:
            self.ssh_client.close()
        self.ssh_connected = False
        self.log_callback("[SSH] Desconectado.")

    def create_tunnel(self, bastion_host, bastion_user, bastion_port, int_ip, int_port, loc_port, key_path):
        try:
            cmd = [
                "ssh", "-i", key_path, "-N",
                "-L", f"{loc_port}:{int_ip}:{int_port}",
                f"{bastion_user}@{bastion_host}",
                "-p", str(bastion_port)
            ]
            # No Windows, creationflags=subprocess.CREATE_NO_WINDOW esconde o cmd
            flags = 0
            if os.name == 'nt':
                flags = subprocess.CREATE_NO_WINDOW

            self.tunnel_process = subprocess.Popen(cmd, creationflags=flags)
            self.log_callback(f"[TUNNEL] Iniciado na porta local {loc_port}")
        except Exception as e:
            self.log_callback(f"[TUNNEL] Erro: {e}")

    def close_tunnel(self):
        if self.tunnel_process:
            self.tunnel_process.terminate()
            self.tunnel_process = None
            self.log_callback("[TUNNEL] Fechado.")

    # =========================================================================
    # UTILITÁRIOS REMOTOS (GIT, HTOP, LS)
    # =========================================================================

    def exec_command_output(self, command):
        """Executa comando simples e retorna stdout como string."""
        if not self.ssh_connected:
            return "Não conectado."
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        return stdout.read().decode(errors="ignore")

    def list_remote_files(self, remote_dir):
        if not self.ssh_connected:
            return []
        try:
            # Lista apenas arquivos .yaml/.yml
            cmd = f'find "{remote_dir}" -maxdepth 1 -name "*.yaml" -o -name "*.yml"'
            out = self.exec_command_output(cmd)
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception as e:
            self.log_callback(f"[SSH] Erro ao listar arquivos: {e}")
            return []

    def get_git_branches(self):
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
        if not self.ssh_connected:
            return
        cmds = [
            f"cd {self.remote_base_dir}",
            "git fetch --all --prune",
            "git reset --hard",
            "git clean -fd",
            f"git checkout {branch}",
            # Re-configurar ambiente se necessário
            "if [ ! -d .sharc_env/ ]; then python3 -m venv .sharc_env; fi",
            "source .sharc_env/bin/activate && pip install -e ."
        ]
        full_cmd = " && ".join(cmds)

        def _thread_git():
            self.log_callback(f"[GIT] Iniciando Checkout: {branch}...")
            stdin, stdout, stderr = self.ssh_client.exec_command(full_cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                self.log_callback("[GIT] Checkout concluído com sucesso.")
            else:
                err = stderr.read().decode()
                self.log_callback(f"[GIT] Erro ({exit_status}):\n{err}")

        threading.Thread(target=_thread_git, daemon=True).start()

    # =========================================================================
    # EXECUÇÃO LOCAL
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
            self.update_row_callback(
                {"iid": ypath, "status": "Iniciando...", "snap": None, "pct": None, "eta": None})

            # Tenta descobrir o main_cli.py
            main_script = os.path.join(PROJECT_ROOT / "main_cli.py")
            # Se não existir lá, tenta usar o sys.executable se estiver rodando como script
            if not os.path.exists(main_script):
                self.log_callback(
                    f"[LOCAL] main_cli.py não encontrado em {main_script}")
                return

            cmd = [sys.executable, main_script, "-p", ypath]

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                self.running_procs_local[ypath] = proc

                total_snaps = 1  # Valor padrão
                current_snap = 0
                t0 = time.time()

                # Regex patterns
                pat_xy = re.compile(
                    r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
                pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

                for line in proc.stdout:
                    line = line.strip()
                    # self.log_callback(f"[LOCAL] {line}") # Verboso demais se habilitado

                    # Parsing
                    m1 = pat_xy.search(line)
                    m2 = pat_hash.search(line)

                    if m1:
                        current_snap = int(m1.group(1))
                        total_snaps = int(m1.group(2))
                    elif m2:
                        current_snap = int(m2.group(1))
                        # Se achou snapshot X e não temos total, assumimos que total atualiza se soubermos ler o YAML

                    if current_snap > 0:
                        pct = (current_snap / max(total_snaps, 1)) * 100
                        elapsed = time.time() - t0
                        rate = elapsed / current_snap
                        remain = (total_snaps - current_snap) * rate
                        eta_str = str(timedelta(seconds=int(remain)))

                        self.update_row_callback({
                            "iid": ypath,
                            "status": "Rodando",
                            "snap": f"{current_snap}/{total_snaps}",
                            "pct": f"{pct:.1f}",
                            "eta": eta_str
                        })

                proc.wait()
                rc = proc.returncode
                final_status = "Concluído" if rc == 0 else f"Erro {rc}"
                self.update_row_callback(
                    {"iid": ypath, "status": final_status, "pct": "100" if rc == 0 else "--", "eta": "--"})

            except Exception as e:
                self.log_callback(f"[LOCAL] Erro ao executar {ypath}: {e}")
                self.update_row_callback({"iid": ypath, "status": "Falha"})
            finally:
                if ypath in self.running_procs_local:
                    del self.running_procs_local[ypath]

    # =========================================================================
    # EXECUÇÃO REMOTA
    # =========================================================================

    def run_remote_parallel(self, remote_files, max_workers):
        if not self.ssh_connected:
            self.log_callback("[REMOTE] Erro: Não conectado.")
            return

        # 1. Cria pasta temporária
        ts = time.strftime("%Y%m%d_%H%M%S")
        remote_tmp = f"{self.remote_base_dir}/sharc/campaigns/remote_run_{ts}"
        try:
            self.ssh_client.exec_command(f"mkdir -p {remote_tmp}")
            self.log_callback(f"[REMOTE] Pasta temporária: {remote_tmp}")
        except Exception as e:
            self.log_callback(f"[REMOTE] Falha ao criar pasta: {e}")
            return

        # 2. Upload (Para simplificar, vamos assumir que os arquivos passados JÁ SÃO remotos
        # Se fossem locais, usaríamos sftp.put. O código original tinha essa ambiguidade.
        # Aqui, assumo que se o modo é SSH, os arquivos selecionados na Treeview são caminhos remotos.)

        # Se quisermos upload de locais:
        # sftp = self.ssh_client.open_sftp()
        # for f in local_files: sftp.put(f, remote_tmp/basename(f))

        # Vamos assumir lógica de "Copiar para temp e rodar"
        target_files = []
        for f in remote_files:
            fname = os.path.basename(f)
            new_path = f"{remote_tmp}/{fname}"
            # Copia arquivo original remoto para pasta temp remota
            self.ssh_client.exec_command(f"cp '{f}' '{new_path}'")
            target_files.append(new_path)

        semaphore = threading.Semaphore(max_workers)
        for rf in target_files:
            # O ID na treeview é o caminho original, mas rodamos o da pasta temp
            original_id = [k for k in remote_files if os.path.basename(
                k) == os.path.basename(rf)][0]

            t = threading.Thread(
                target=self._worker_remote,
                args=(rf, original_id, semaphore),
                daemon=True
            )
            t.start()

    def _worker_remote(self, remote_path, tree_id, semaphore):
        with semaphore:
            self.update_row_callback(
                {"iid": tree_id, "status": "Iniciando Remoto...", "snap": "0/--"})

            cmd = (
                f"cd {self.remote_base_dir} && "
                f"source .sharc_env/bin/activate && "
                f"python3 sharc/main_cli.py -p '{remote_path}'"
            )

            try:
                # exec_command retorna streams (não bloqueante imediato, mas readline bloqueia)
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    cmd, get_pty=True)

                total_snaps = 1
                current_snap = 0
                t0 = time.time()

                pat_xy = re.compile(
                    r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)

                for line in iter(stdout.readline, ""):
                    line = line.strip()
                    # self.log_callback(f"[REMOTE] {line}")

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
                            "status": "Rodando (SSH)",
                            "snap": f"{current_snap}/{total_snaps}",
                            "pct": f"{pct:.1f}",
                            "eta": str(timedelta(seconds=int(remain)))
                        })

                exit_status = stdout.channel.recv_exit_status()
                final = "Concluído" if exit_status == 0 else f"Erro Remoto {exit_status}"
                self.update_row_callback(
                    {"iid": tree_id, "status": final, "pct": "100" if exit_status == 0 else "--"})

            except Exception as e:
                self.log_callback(f"[REMOTE] Erro worker: {e}")
                self.update_row_callback(
                    {"iid": tree_id, "status": "Erro SSH"})

    def stop_simulations(self, iid_list):
        """Para simulações locais ou remotas."""
        for iid in iid_list:
            # Local
            if iid in self.running_procs_local:
                p = self.running_procs_local[iid]
                p.terminate()
                self.log_callback(f"Parando processo local: {iid}")

            # Remoto (Complexo: precisa achar PID pelo nome do arquivo)
            if self.ssh_connected:
                fname = os.path.basename(iid)
                # Pkill pattern match no nome do arquivo yaml
                cmd = f"pkill -f 'python3.*{fname}'"
                self.ssh_client.exec_command(cmd)
                self.update_row_callback({"iid": iid, "status": "Cancelado"})
