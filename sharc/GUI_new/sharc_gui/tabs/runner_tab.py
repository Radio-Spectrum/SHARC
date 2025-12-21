# Auto-split from original sharc_gui.py
from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import RESULT_FIELDNAME_TO_PLOT_INFO  # noqa
import yaml
import sharc
from pathlib import Path
import tkinter as tk
import tempfile
import os
import stat

class RunnerTabTabMixin:
    def _tab_runner(self, root):

        # =========================================================
        # ESTADOS (garanta que existam)
        # =========================================================
        if not hasattr(self, "var_run_mode"):
            self.var_run_mode = tk.StringVar(value="LOCAL")   # "LOCAL" | "SSH"
        if not hasattr(self, "var_use_tunnel"):
            self.var_use_tunnel = tk.BooleanVar(value=False)  # mostra/oculta túnel
        if not hasattr(self, "var_ssh_auth"):
            self.var_ssh_auth = tk.StringVar(value="KEY")     # "KEY" | "PASSWORD"
        if not hasattr(self, "ssh_password"):
            self.ssh_password = tk.StringVar(value="")

        # =========================================================
        # 1ª LINHA: MODO (LOCAL / REMOTO)
        # =========================================================
        frm_mode = ttk.LabelFrame(root, text="Modo de Execução")
        frm_mode.pack(fill="x", pady=6)

        ttk.Radiobutton(frm_mode, text="Local", value="LOCAL", variable=self.var_run_mode)\
            .pack(side="left", padx=6)
        ttk.Radiobutton(frm_mode, text="Remoto (SSH)", value="SSH", variable=self.var_run_mode)\
            .pack(side="left", padx=6)

        # =========================================================
        # TÚNEL SSH  - CRIA, MAS NÃO MOSTRA (pack só quando marcado)
        # =========================================================
        frm_tunnel = ttk.LabelFrame(root, text="Túnel SSH ")
        # NÃO DAR pack aqui

        ttk.Label(frm_tunnel, text="Host Bastion").grid(row=0, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_bastion_host).grid(row=0, column=1)

        ttk.Label(frm_tunnel, text="Usuário Bastion").grid(row=0, column=2)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_bastion_user).grid(row=0, column=3)

        ttk.Label(frm_tunnel, text="Porta Bastion").grid(row=0, column=4)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_bastion_port, width=6).grid(row=0, column=5)

        ttk.Label(frm_tunnel, text="IP Interno").grid(row=1, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_internal_ip).grid(row=1, column=1)

        ttk.Label(frm_tunnel, text="Porta Interna").grid(row=1, column=2)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_internal_port, width=6).grid(row=1, column=3)

        ttk.Label(frm_tunnel, text="Porta Local").grid(row=1, column=4)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_local_port, width=6).grid(row=1, column=5)

        ttk.Label(frm_tunnel, text="Chave").grid(row=2, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.tunnel_key_path, width=50).grid(row=2, column=1, columnspan=4)

        ttk.Button(
            frm_tunnel,
            text="Escolher",
            command=lambda: self._pick_file(
                self.tunnel_key_path,
                [("Chaves SSH", "*.pem *.ppk *.key *.rsa"), ("Todos os arquivos", "*.*")]
            )
        ).grid(row=2, column=5)

        ttk.Button(frm_tunnel, text="Criar Túnel", command=self._create_tunnel).grid(row=3, column=0, pady=4)
        ttk.Button(frm_tunnel, text="Fechar Túnel", command=self._close_tunnel).grid(row=3, column=1, pady=4)
        ttk.Label(frm_tunnel, textvariable=self.tunnel_status).grid(row=3, column=2, columnspan=3)

        for c in range(6):
            frm_tunnel.grid_columnconfigure(c, weight=1)

        # =========================================================
        # CONEXÃO SSH - CRIA, MAS NÃO MOSTRA (pack só quando modo=SSH)
        # =========================================================
        frm_ssh = ttk.LabelFrame(root, text="Conexão SSH")
        # NÃO DAR pack aqui

        ttk.Label(frm_ssh, text="Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm_ssh, textvariable=self.ssh_host, width=24).grid(row=0, column=1, sticky="we", padx=(0, 4))

        ttk.Label(frm_ssh, text="Usuário").grid(row=0, column=2, sticky="w")
        ttk.Entry(frm_ssh, textvariable=self.ssh_user, width=18).grid(row=0, column=3, sticky="we", padx=(0, 4))

        ttk.Label(frm_ssh, text="Porta").grid(row=0, column=4, sticky="w")
        ttk.Entry(frm_ssh, textvariable=self.ssh_port, width=6).grid(row=0, column=5, sticky="w")

        # ---- Autenticação: KEY / PASSWORD
        ttk.Label(frm_ssh, text="Autenticação").grid(row=0, column=6, sticky="w", padx=(10, 0))

        ttk.Radiobutton(frm_ssh, text="Chave", value="KEY", variable=self.var_ssh_auth)\
            .grid(row=0, column=7, sticky="w")
        ttk.Radiobutton(frm_ssh, text="Senha", value="PASSWORD", variable=self.var_ssh_auth)\
            .grid(row=0, column=8, sticky="w")

        # ---- Checkbox para túnel (se marcado, mostra frm_tunnel acima do SSH)
        ttk.Checkbutton(frm_ssh, text="Usar túnel", variable=self.var_use_tunnel)\
            .grid(row=2, column=0, sticky="e", pady=(4, 0))

        # =========================================================
        # SLOT FIXO: AUTH (KEY/PASSWORD) - MESMA POSIÇÃO SEM BUG
        # =========================================================
        # Este slot fica SEMPRE no mesmo lugar e só alterna o conteúdo interno.
        auth_slot = ttk.Frame(frm_ssh)
        auth_slot.grid(row=1, column=6, columnspan=3, sticky="e", pady=(4, 0), padx=(10, 0))
        auth_slot.grid_columnconfigure(0, weight=1)

        # Frame KEY
        auth_key = ttk.Frame(auth_slot)
        auth_key.grid_columnconfigure(0, weight=1)

        ent_key = ttk.Entry(auth_key, textvariable=self.ssh_key_path)
        ent_key.grid(row=0, column=0, sticky="we")

        btn_pick_key = ttk.Button(
            auth_key,
            text="Escolher",
            command=lambda: self._pick_file(
                self.ssh_key_path,
                [("Chave SSH", "*.pem *.ppk *.key *.rsa"), ("Todos", "*.*")]
            )
        )
        # colado à direita
        btn_pick_key.grid(row=0, column=1, sticky="e", padx=(6, 0))

        # Frame PASSWORD
        auth_pwd = ttk.Frame(auth_slot)
        auth_pwd.grid_columnconfigure(0, weight=1)

        ent_pwd = ttk.Entry(auth_pwd, textvariable=self.ssh_password, show="*")
        ent_pwd.grid(row=0, column=0, sticky="we")

        # ---- Botões + status
        ttk.Button(frm_ssh, text="Conectar", command=self._ssh_connect).grid(row=3, column=0, pady=6, sticky="w")
        ttk.Button(frm_ssh, text="Desconectar", command=self._ssh_disconnect).grid(row=3, column=1, pady=6, sticky="w")
        ttk.Label(frm_ssh, textvariable=self.ssh_status).grid(row=3, column=2, columnspan=3, sticky="we", padx=(6, 6))

        ttk.Button(frm_ssh, text="HTOP", command=self._open_htop_window).grid(row=3, column=5, padx=4, sticky="e")

        self.lbl_remote_branch = ttk.Label(frm_ssh, text="Branch: --")
        self.lbl_remote_branch.grid(row=2, column=1, padx=6, sticky="w")

        self.var_git_branch = tk.StringVar()
        self.cmb_git_branch = ttk.Combobox(frm_ssh, textvariable=self.var_git_branch, state="readonly", width=28)
        self.cmb_git_branch.grid(row=2, column=4, padx=6)

        ttk.Button(frm_ssh, text="Trocar Branch (FORCE)", command=self._on_force_checkout_clicked)\
            .grid(row=2, column=5, padx=4)

        # ======= CONFIG GRID: NÃO deixar tudo weight=1 (isso estoura tudo) =======
        # Colunas principais: 1 e 3 podem expandir; 8 “empurra” a área de auth pro canto.
        for c in range(9):
            frm_ssh.grid_columnconfigure(c, weight=0)
        frm_ssh.grid_columnconfigure(1, weight=1)  # host entry expand
        frm_ssh.grid_columnconfigure(3, weight=1)  # user entry expand
        frm_ssh.grid_columnconfigure(8, weight=1)  # empurra área da direita

        # =========================================================
        # TOGGLES DE VISIBILIDADE
        # =========================================================
        def _toggle_remote_blocks(*_):
            if self.var_run_mode.get() == "SSH":
                if not frm_ssh.winfo_manager():
                    frm_ssh.pack(fill="x", pady=6)
                _toggle_tunnel()
            else:
                if frm_tunnel.winfo_manager():
                    frm_tunnel.pack_forget()
                if frm_ssh.winfo_manager():
                    frm_ssh.pack_forget()

        def _toggle_tunnel(*_):
            if self.var_run_mode.get() == "SSH" and self.var_use_tunnel.get():
                if not frm_tunnel.winfo_manager():
                    frm_tunnel.pack(fill="x", pady=6, before=frm_ssh)
            else:
                if frm_tunnel.winfo_manager():
                    frm_tunnel.pack_forget()

        def _toggle_auth(*_):
            # some os dois
            if auth_key.winfo_ismapped():
                auth_key.grid_remove()
            if auth_pwd.winfo_ismapped():
                auth_pwd.grid_remove()

            # mostra só o selecionado (sempre na MESMA célula)
            if self.var_ssh_auth.get() == "PASSWORD":
                auth_pwd.grid(row=0, column=0, sticky="e")
            else:
                auth_key.grid(row=0, column=0, sticky="e")

        self.var_run_mode.trace_add("write", _toggle_remote_blocks)
        self.var_use_tunnel.trace_add("write", _toggle_tunnel)
        self.var_ssh_auth.trace_add("write", _toggle_auth)

        _toggle_remote_blocks()
        _toggle_auth()

        # =========================================================
        # LISTA DE ARQUIVOS + EXECUÇÃO
        # =========================================================
        top = ttk.Frame(root)
        top.pack(fill="x")
        self.run_folder = tk.StringVar(value=os.path.join(Path.cwd(), "/sharc/sharc/campaigns"))
        ttk.Label(top, text="Pasta com arquivos .yaml").pack(side="left")
        e = ttk.Entry(top, textvariable=self.run_folder)
        e.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Escolher...", command=lambda: self._pick_folder(self.run_folder)).pack(side="left")
        ttk.Button(top, text="Atualizar lista", command=self._scan_yaml_files).pack(side="left", padx=(6,0))
        ttk.Label(top, text="Paralelo (máx execuções):").pack(side="left", padx=(14,4))
        ttk.Spinbox(top, from_=1, to=32, width=4, textvariable=self.var_max_workers).pack(side="left")

        # Tree for files + progress
        mid = ttk.Frame(root)
        mid.pack(fill="both", expand=True, pady=(8,0))
        self.tree = ttk.Treeview(mid, columns=("yaml","status","snap","pct","eta"), show="headings", height=12)
        self.tree.heading("yaml", text="YAML")
        self.tree.heading("status", text="Status")
        self.tree.heading("snap", text="Snapshots (done/total)")
        self.tree.heading("pct", text="%")
        self.tree.heading("eta", text="ETA")
        self.tree.column("yaml", width=380)
        self.tree.column("status", width=220)
        self.tree.column("snap", width=180)
        self.tree.column("pct", width=60, anchor="e")
        self.tree.column("eta", width=120)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.configure(yscroll=sb.set)

        right = ttk.Frame(root)
        right.pack(fill="x", pady=(8,0))
        self.main_cli_path = tk.StringVar(
            value=str(Path(sharc.__file__).resolve().parent / "main_cli.py")
        )
        ttk.Label(right, text="main_cli.py:").pack(side="left")
        ttk.Entry(right, textvariable=self.main_cli_path, width=44).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(right, text="Parar selecionados", command=self._stop_selected).pack(side="right", padx=(6,0))
        ttk.Button(right, text="Executar selecionados", command=self._run_selected_yaml_parallel).pack(side="right")

        logf = ttk.LabelFrame(root, text="Log")
        logf.pack(fill="both", expand=True, pady=(8,0))
        self.txt_log = tk.Text(logf, height=10, wrap="none")
        self.txt_log.pack(fill="both", expand=True)

        self._scan_yaml_files()
        self.after(150, self._drain_log_queue)
        self.after(250, self._runner_scheduler_tick)

    def _append_log(self, msg: str):
            import time
            timestamp = time.strftime("%H:%M:%S")
            line = f"[{timestamp}] {msg}\n"

            try:
                self.txt_log.configure(state="normal")
                self.txt_log.insert("end", line)
                self.txt_log.see("end")
                self.txt_log.configure(state="disabled")
            except Exception as e:
                print("LOG ERROR:", e, line)

            # Sempre manda também para o console (debug)
            try:
                print(line, end="")
            except Exception:
                pass

    def _cleanup_remote_tmp_dir(self):
            if not hasattr(self, "_remote_tmp_dir"):
                return

            if not self._remote_tmp_dir:
                return

            try:
                cmd = f"rm -rf {self._remote_tmp_dir}"
                self._exec_remote_paramiko(cmd)

                self._append_log(
                    f"[REMOTE] Pasta temporária removida: {self._remote_tmp_dir}"
                )

                self._remote_tmp_dir = None

            except Exception as e:
                self._append_log(
                    f"[REMOTE][ERRO] Falha ao remover pasta temporária: {e}"
                )

    def _close_tunnel(self):
            if self.tunnel_process:
                self.tunnel_process.terminate()
                self.tunnel_process = None

            self.tunnel_status.set("🔴 Túnel Inativo")
            messagebox.showinfo("Túnel", "Túnel fechado.")

    def _create_remote_tmp_dir(self):
            """
            Cria uma pasta temporária no servidor dentro de:
            /home/{self.ssh_user.get().strip()}/SHARC/sharc/campaigns/

            Retorna o caminho completo da pasta criada.
            """
            if not self.ssh_client:
                raise RuntimeError("SSH não conectado.")

            base_dir = f"/home/{self.ssh_user.get().strip()}/SHARC/sharc/campaigns"

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            remote_tmp = f"{base_dir}/remote_run_{timestamp}"

            cmd = f"mkdir -p {remote_tmp}"
            out, err = self._exec_remote_paramiko(cmd)

            if err.strip():
                raise RuntimeError(f"Erro ao criar diretório remoto:\n{err}")

            return remote_tmp

    def _create_tunnel(self):
            host = self.tunnel_bastion_host.get()
            user = self.tunnel_bastion_user.get()
            port = self.tunnel_bastion_port.get()
            internal_ip = self.tunnel_internal_ip.get()
            internal_port = self.tunnel_internal_port.get()
            local_port = self.tunnel_local_port.get()
            key = self.tunnel_key_path.get()

            if not all([host, user, key, internal_ip]):
                messagebox.showerror("Túnel", "Preencha todos os dados do túnel.")
                return

            try:
                cmd = [
                    "ssh",
                    "-i", key,
                    "-N",
                    "-L", f"{local_port}:{internal_ip}:{internal_port}",
                    f"{user}@{host}",
                    "-p", str(port)
                ]

                self.tunnel_process = subprocess.Popen(cmd)
                self.tunnel_status.set("🟢 Túnel Ativo")

                # Auto-preencher dados de SSH
                self.ssh_host.set("localhost")
                self.ssh_port.set(local_port)

                messagebox.showinfo("Túnel", "Túnel criado com sucesso.")

            except Exception as e:
                self.tunnel_status.set("🔴 Falha no túnel")
                messagebox.showerror("Túnel", str(e))

    def _drain_log_queue(self):
            try:
                while True:
                    line = self.line_q.get_nowait()
                    self.txt_log.insert("end", line)
                    if not line.endswith("\n"):
                        self.txt_log.insert("end", "\n")
                    self.txt_log.see("end")
            except queue.Empty:
                pass
            self.after(150, self._drain_log_queue)

    def _eta_string(self, t0, now, done, total):
                if done <= 0 or total <= 0:
                    return "--"
                elapsed = now - t0
                rate = elapsed / max(done, 1)  # seg/snapshot
                remain = max(total - done, 0) * rate
                return str(datetime.timedelta(seconds=int(remain)))

    def _exec_remote_paramiko(self, command: str):
            if not self.ssh_client:
                raise RuntimeError("SSH Paramiko não está conectado.")
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            out = stdout.read().decode(errors="ignore")
            err = stderr.read().decode(errors="ignore")
            return out, err

    def _force_checkout_remote_branch(self, branch):
        try:
            base = f"/home/{self.ssh_user.get().strip()}/SHARC"
            campaigns_dir = f"{base}/sharc/campaigns"

            # 0) LIMPEZA DAS CAMPANHAS (ANTES DO GIT)
            self._append_log("[CLEAN] Removendo pasta sharc/campaigns/")
            cmd_clean = f"rm -rf {campaigns_dir}"
            out, err = self._exec_remote_paramiko(cmd_clean)
            if err.strip():
                self._append_log(f"[CLEAN][WARN]\n{err}")
            else:
                self._append_log("[CLEAN] Pasta campaigns removida com sucesso") 

            # 1) GIT: fetch + reset + clean + checkout
            self._append_log(f"[GIT] FORCE checkout para branch: {branch}")
            cmd_git = (
                f"cd {base} && "
                f"git fetch --all --prune && "
                f"git reset --hard && "
                f"git clean -fd -e .sharc_env -e .venv_sharc -e venv_sharc && "
                f"git checkout {branch}"
            )
            out, err = self._exec_remote_paramiko(cmd_git)
            if out.strip():
                self._append_log(f"[GIT][OUT]\n{out}")
            if err.strip():
                self._append_log(f"[GIT][ERR]\n{err}")

            # 2) VENV: criar (versão simples e robusta)
            self._append_log("[ENV] Verificando / criando .sharc_env/")

            cmd_venv = (
                f"cd {base} && "
                "if [ ! -d .sharc_env/ ]; then "
                "echo '[ENV] Criando ambiente virtual .sharc_env/'; "
                "(python3 -m venv .sharc_env/ || python -m venv .sharc_env/); "
                "fi"
            )

            out2, err2 = self._exec_remote_paramiko(cmd_venv)
            if out2.strip():
                self._append_log(f"[ENV][OUT]\n{out2}")
            if err2.strip():
                self._append_log(f"[ENV][ERR]\n{err2}")


            """# 2b) Checar se o activate realmente existe
            cmd_check = (
                f"cd {base} && "
                "if [ -f ..venv_sharc/bin/activate ]; then "
                "echo 'OK_VENV'; "
                "else "
                "echo 'MISSING_VENV'; "
                "fi"
            )
            out3, err3 = self._exec_remote_paramiko(cmd_check)
            if out3.strip():
                self._append_log(f"[ENV][CHECK]\n{out3}")
            if "MISSING_VENV" in out3:
                raise RuntimeError(
                    "Ambiente virtual ..venv_sharc/ não foi criado corretamente no servidor. "
                    "Verifique se o pacote python3-venv está instalado no sistema."
                )"""

            # 3) ATIVAR VENV + ATUALIZAR PIP + REQUIREMENTS + SHARC (-e)
            self._append_log("[ENV] Ativando venv e instalando dependências/SHARC")
            cmd_req = (
                f"cd {base} && "
                "python3 -m venv .sharc_env &&"
                f"source /home/{self.ssh_user.get().strip()}/SHARC/.sharc_env/bin/activate && "
                "python -m pip install --upgrade pip && "
                "if [ -f requirements.txt ]; then "
                "pip install -r requirements.txt; "
                "else "
                "echo '[ENV] Nenhum requirements.txt encontrado'; "
                "fi && "
                "pip install -e ."
            )
            out4, err4 = self._exec_remote_paramiko(cmd_req)
            if out4.strip():
                self._append_log(f"[ENV][OUT]\n{out4}")
            if err4.strip():
                self._append_log(f"[ENV][ERR]\n{err4}")

            # Atualiza label da branch na interface
            new_branch = self._get_remote_git_branch()
            if hasattr(self, "lbl_remote_branch"):
                self.lbl_remote_branch.config(text=f"Branch: {new_branch}")

            messagebox.showinfo(
                "Git / Ambiente remoto",
                f"Branch alterada para: {new_branch}\n\n"
                "Ambiente virtual .sharcarc_env verificado/criado, "
                "requirements instalados e SHARC instalado em modo editável."
            )

        except Exception as e:
            self._append_log(f"[GIT/ENV][EXCEPTION] {e}")
            messagebox.showerror(
                    "Git / Ambiente remoto", f"Erro no FORCE checkout / ambiente:\n{e}"
                )

    def _get_remote_git_branch(self):
        """Return current git branch name on remote SHARC repo (or empty on failure)."""
        if not self.ssh_client:
            return ""
        try:
            base = self._remote_base_dir()
            cmd = (
                f'cd "{base}" && '
                '(git symbolic-ref --quiet --short HEAD '
                '|| echo "DETACHED-HEAD ($(git rev-parse --short HEAD))")'
            )
            out, err = self._exec_remote_paramiko(cmd)
            return out.strip()
        except Exception:
            return ""

    def _get_remote_git_branches(self):
            try:
                # Atualiza referências remotas
                self._exec_remote_paramiko(
                    f"cd /home/{self.ssh_user.get().strip()}/SHARC && git fetch --all --prune"
                )

                # Lista TODAS as branches (local + remotas)
                out, err = self._exec_remote_paramiko(
                    f"cd /home/{self.ssh_user.get().strip()}/SHARC && git branch -a"
                )

                branches = set()

                for line in out.splitlines():
                    line = line.strip()

                    # Remove marcador da branch atual
                    if line.startswith("*"):
                        line = line[1:].strip()

                    # Ignora ponteiros simbólicos tipo origin/HEAD -> origin/main
                    if "->" in line:
                        continue

                    # Normaliza origin/nome
                    if line.startswith("remotes/origin/"):
                        line = line.replace("remotes/origin/", "")

                    if line:
                        branches.add(line)

                return sorted(branches)

            except Exception as e:
                messagebox.showerror("Git", f"Erro ao listar branches:\n{e}")
                return []

    def _on_force_checkout_clicked(self):
            branch = self.var_git_branch.get().strip()
            if not branch:
                messagebox.showwarning("Git", "Selecione uma branch.")
                return

            resp = messagebox.askyesno(
                "Git - FORCE CHECKOUT",
                f"Isso vai APAGAR TODAS as modificações locais no servidor.\n\n"
                f"Deseja realmente trocar para a branch:\n\n{branch} ?"
            )

            if not resp:
                return

            self._force_checkout_remote_branch(branch)

    def _open_htop_window(self):
            if not self.ssh_client:
                messagebox.showerror("SSH", "Você não está conectado ao servidor.")
                return

            win = tk.Toplevel(self)
            win.title("HTOP - Servidor Remoto")
            win.geometry("1000x600")

            txt = tk.Text(win, wrap="none", bg="black", fg="lime")
            txt.pack(fill="both", expand=True)

            # barras de rolagem
            yscroll = ttk.Scrollbar(win, orient="vertical", command=txt.yview)
            yscroll.pack(side="right", fill="y")
            txt.configure(yscrollcommand=yscroll.set)

            # botão fechar
            ttk.Button(win, text="Fechar", command=win.destroy).pack(pady=4)

            self._htop_window = win
            self._htop_text = txt

            self._update_htop_loop()

    def _pick_file(self, tk_strvar, patterns):
            init = os.path.dirname(tk_strvar.get()) if tk_strvar.get() else os.getcwd()
            path = filedialog.askopenfilename(initialdir=init, title="Selecionar arquivo", filetypes=patterns)
            if path:
                tk_strvar.set(path)

    def _pick_folder(self, var):
            cur = var.get() or os.getcwd()
            if not os.path.isdir(cur):
                cur = os.getcwd()
            path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta")
            if path:
                var.set(path)
                self._scan_yaml_files()

    def _run_one_yaml(self, ypath):
            declared_total = self._yaml_num_snapshots(ypath) or int(self.var_snaps.get())
            self.runtime[ypath] = {
                "status": "Rodando",
                "done": 0,
                "total": declared_total,
                "t0": time.time(),
                "last_snap_time": None,
            }
            self._update_row(ypath, status="Rodando", snap=f"0/{declared_total}", pct="0", eta="--")

            try:
                # Escolhe comando LOCAL ou SSH
                if getattr(self, "var_run_mode", None) is not None and self.var_run_mode.get() == "SSH":
                    if not getattr(self, "ssh_connected", False):
                        raise RuntimeError("SSH não conectado.")

                    host = self.ssh_host.get().strip()
                    user = self.ssh_user.get().strip()
                    port = self.ssh_port.get()
                    remote_main = self.main_cli_path.get().strip()
                    remote_yaml = ypath

                    if not remote_main:
                        raise RuntimeError("Caminho remoto do main_cli.py não definido.")

                    # Usa python3 no servidor e repassa o caminho do YAML
                    remote_cmd = f'python3 "{remote_main}" -p "{remote_yaml}"'
                    cmd = ["ssh", "-p", str(port), f"{user}@{host}", remote_cmd]
                else:
                    cmd = [sys.executable, self.main_cli_path.get(), "-p", ypath]

                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, text=True)
                self.procs[ypath] = proc

                # (SSH) tenta armazenar o PID remoto associado a este YAML (para cancelar sempre o certo)
                if self.var_run_mode.get() == "SSH":
                    if not hasattr(self, "remote_pid_by_yaml"):
                        self.remote_pid_by_yaml = {}
                        if not hasattr(self, "remote_output_by_yaml"):
                            self.remote_output_by_yaml = {}
                    try:
                        if getattr(self, "ssh_client", None) and hasattr(self, "_remote_yaml_by_local"):
                            _ry = self._remote_yaml_by_local.get(ypath, "")
                            if _ry:
                                find_pid_cmd = (
                                    f"ps -eo pid,cmd | grep -F '{_ry}' "
                                    f"| grep -v grep | grep -E 'python(3|[0-9\\.])' "
                                    f"| awk '{{print $1}}' | tail -n 1"
                                )
                                stdin, stdout, stderr = self.ssh_client.exec_command(find_pid_cmd)
                                pid = stdout.read().decode().strip()
                                if pid:
                                    self.remote_pid_by_yaml[ypath] = pid
                    except Exception:
                        pass


                # (SSH) tenta armazenar o PID remoto associado a este YAML
                if self.var_run_mode.get() == "SSH":
                    if not hasattr(self, "remote_pid_by_yaml"):
                        self.remote_pid_by_yaml = {}
                    try:
                        if hasattr(self, "ssh_client") and self.ssh_client and hasattr(self, "_remote_yaml_by_local"):
                            _ry = self._remote_yaml_by_local.get(ypath, "")
                            if _ry:
                                find_pid_cmd = (
                                    f"ps -eo pid,cmd | grep -F '{_ry}' | grep -v grep "
                                    f"| grep -E 'python(3|[0-9\\.])' | awk '{{print $1}}' | tail -n 1"
                                )
                                stdin, stdout, stderr = self.ssh_client.exec_command(find_pid_cmd)
                                _pid = stdout.read().decode().strip()
                                if _pid:
                                    self.remote_pid_by_yaml[ypath] = _pid
                    except Exception:
                        pass


                pat_xy = re.compile(r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
                pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

                total = declared_total
                for line in proc.stdout:
                    text = line.rstrip()
                    self._append_log(f"[LOCAL] {text}")
                    m1 = pat_xy.search(line)
                    m2 = pat_hash.search(line)
                    if m1:
                        done = int(m1.group(1))
                        total_in_line = int(m1.group(2))
                        if total_in_line:
                            total = max(total, total_in_line)
                        self.runtime[ypath]["done"] = done
                        self.runtime[ypath]["total"] = total
                    elif m2:
                        done = int(m2.group(1))
                        self.runtime[ypath]["done"] = done
                        total = max(total, self.runtime[ypath]["total"])
                    else:
                        continue

                    now = time.time()
                    self.runtime[ypath]["last_snap_time"] = now
                    pct = f"{(100.0 * self.runtime[ypath]['done'] / max(total, 1)):.1f}"
                    eta = self._eta_string(self.runtime[ypath]["t0"], now, self.runtime[ypath]["done"], total)
                    self._update_row(ypath, status="Rodando", snap=f"{self.runtime[ypath]['done']}/{total}", pct=pct, eta=eta)

                proc.wait()
                rc = proc.returncode
                done = self.runtime[ypath]["done"]
                pct = "100" if rc == 0 else f"{(100.0 * done / max(total, 1)):.1f}"
                self._update_row(ypath, status=("OK" if rc == 0 else f"Erro {rc}"), snap=f"{done}/{total}", pct=pct, eta="00:00")
            except Exception as e:
                self._update_row(ypath, status=f"Falha: {e}", snap="--/--", pct="--", eta="--")
            finally:
                if ypath in self.running:
                    self.running.remove(ypath)
                if ypath in self.procs:
                    p = self.procs[ypath]
                    try:
                        if p.poll() is None:
                            p.terminate()
                    except Exception:
                        pass

    def _run_remote_yaml_worker(self, remote_yaml, local_yaml, tree_iid, declared_total):

            with self._remote_semaphore:

                try:
                    cmd = (
                        f"cd /home/{self.ssh_user.get().strip()}/SHARC && "
                        f"source /home/{self.ssh_user.get().strip()}/SHARC/.sharc_env/bin/activate && "
                        f"python3 /home/{self.ssh_user.get().strip()}/SHARC/sharc/main_cli.py -p {remote_yaml} 2>&1"
                    )

                    self._append_log(f"[REMOTE][CMD] {cmd}")

                    pat_xy = re.compile(r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
                    pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

                    done = 0
                    total = declared_total
                    t0 = time.time()

                    self._update_row(tree_iid, status="Rodando (remoto)", snap=f"0/{total}", pct="0", eta="--")

                    stdin, stdout, stderr = self.ssh_client.exec_command(cmd)

                    # ============ LEITURA EM TEMPO REAL ============
                    while True:
                        line = stdout.readline()

                        if not line:
                            break

                        line = line.rstrip()
                        self._append_log(f"[REMOTE] {line}")

                        m1 = pat_xy.search(line)
                        m2 = pat_hash.search(line)

                        if m1:
                            done = int(m1.group(1))
                            total = int(m1.group(2))
                        elif m2:
                            done = int(m2.group(1))

                        if done and total:
                            pct = f"{(100.0 * done / total):.1f}"
                            eta = self._eta_string(t0, time.time(), done, total)

                            self._update_row(
                                tree_iid,
                                status="Rodando (remoto)",
                                snap=f"{done}/{total}",
                                pct=pct,
                                eta=eta,
                            )

                    # ============ STATUS DE SAÍDA ============
                    rc = stdout.channel.recv_exit_status()

                    if rc == 0:
                        final_status = "OK"
                    else:
                        final_status = f"Erro {rc}"

                        err_out = stderr.read().decode()
                        self._append_log(f"[REMOTE][ERRO STD] {err_out}")

                    self._update_row(
                        tree_iid,
                        status=final_status,
                        snap=f"{done}/{total}",
                        pct="100" if rc == 0 else f"{(100.0 * done / total):.1f}",
                        eta="00:00",
                    )


                    # Baixa outputs do YAML (se configurado) ao terminar
                    try:
                        self._download_outputs_for_yaml(local_yaml, when="finish")
                        self._append_log(f"[REMOTE][DL][ERR] finished: {local_yaml}")
                    except Exception as e:
                        pass
                except Exception as e:
                    self._update_row(tree_iid, status=f"Erro: {e}")
                    self._append_log(f"[REMOTE][EXCEPTION] {e}")

                finally:
                    self._remote_pending.discard(tree_iid)

                    # ✅ SÓ LIMPA QUANDO A ÚLTIMA TERMINAR
                    if not self._remote_pending:
                        self._append_log("[REMOTE] Todas as simulações concluídas.")
                        self._maybe_cleanup_remote_tmp_dir()

    def _run_selected_yaml_parallel(self):

            # ===== MODO REMOTO (SSH) =====
            if self.var_run_mode.get() == "SSH":

                yaml_ids = self.tree.selection()
                if not yaml_ids:
                    messagebox.showwarning("Runner", "Nenhum YAML selecionado.")
                    return

                if not self.ssh_client:
                    messagebox.showerror("SSH", "Você não está conectado ao servidor.")
                    return

                # Aqui os iids já devem ser caminhos REMOTOS
                remote_yaml_paths = list(yaml_ids)

                #self._append_log("[REMOTE] Iniciando execução remota...")
                self._run_selected_yaml_remote_option_c(remote_yaml_paths)
                return   # <<< ESSENCIAL: impede cair no modo local


            # ===== MODO LOCAL (RUNNER ORIGINAL) =====
            sel = self.tree.selection()
            if not sel:
                messagebox.showwarning("Runner", "Selecione pelo menos um arquivo YAML.")
                return

            for iid in sel:
                # se já tem thread viva para esse YAML, pula
                if iid in self.proc_threads and self.proc_threads[iid].is_alive():
                    continue

                self.jobs_q.put(iid)
                self._update_row(iid, status="Na fila", snap=None, pct=None, eta="--")

    def _run_selected_yaml_remote_option_c(self, yaml_files):

            if not self.ssh_client:
                messagebox.showerror("SSH", "Conecte-se ao servidor primeiro.")
                return

            try:
                ts_dir = self._create_remote_tmp_dir()
                self._remote_tmp_dir = ts_dir
                self._remote_pending = set()   # controla processos ativos

                self._append_log(f"[REMOTE] Pasta temporária criada: {ts_dir}")

                self._upload_yaml_files_remote(yaml_files, ts_dir)

                max_parallel = int(self.var_max_workers.get())
                self._remote_semaphore = threading.Semaphore(max_parallel)

                for local_yaml in yaml_files:
                    fname = os.path.basename(local_yaml)
                    remote_yaml = f"{ts_dir}/{fname}"

                    # Mapa local_yaml -> remote_yaml (para cancelamento por PID)
                    if not hasattr(self, "_remote_yaml_by_local"):
                        self._remote_yaml_by_local = {}
                    self._remote_yaml_by_local[local_yaml] = remote_yaml

                    tree_iid = local_yaml
                    declared_total = self._yaml_num_snapshots(local_yaml) or int(self.var_snaps.get())

                    self._append_log(f"[REMOTE] Executando: {remote_yaml}")

                    self._remote_pending.add(tree_iid)

                    threading.Thread(
                        target=self._run_remote_yaml_worker,
                        args=(remote_yaml, local_yaml, tree_iid, declared_total),
                        daemon=True
                    ).start()

            except Exception as e:
                messagebox.showerror("Runner (SSH)", f"Erro na execução remota:\n{e}")
                self._append_log(f"[REMOTE][ERRO] {e}")

    def _runner_scheduler_tick(self):
            # inicia até max_workers simultâneos
            maxw = max(1, int(self.var_max_workers.get()))
            while len(self.running) < maxw and not self.jobs_q.empty():
                iid = self.jobs_q.get()
                if iid in self.running:
                    continue
                if iid in self.proc_threads and self.proc_threads[iid].is_alive():
                    continue
                t = threading.Thread(target=self._run_one_yaml, args=(iid,), daemon=True)
                self.proc_threads[iid] = t
                self.running.add(iid)
                t.start()
            # reaplicar em loop
            self.after(300, self._runner_scheduler_tick)

    def _scan_yaml_files(self):
            if not hasattr(self, "tree"):
                return

            from tkinter import messagebox  # local import to evitar ciclos

            self.tree.delete(*self.tree.get_children())

            # Se modo SSH, lista arquivos no servidor remoto
            """"if getattr(self, "var_run_mode", None) is not None and self.var_run_mode.get() == "SSH":
                if not getattr(self, "ssh_connected", False):
                    messagebox.showwarning("Runner (SSH)", "Conecte ao servidor SSH antes de listar os YAML.")
                    return

                host = self.ssh_host.get().strip()
                user = self.ssh_user.get().strip()
                port = self.ssh_port.get()
                rdir = self.ssh_remote_dir.get().strip() or "."

                remote_cmd = f'cd "{rdir}" && ls *.yaml *.yml 2>/dev/null'

                try:
                    out = subprocess.check_output(
                        ["ssh", "-p", str(port), f"{user}@{host}", remote_cmd],
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    messagebox.showerror("Runner (SSH)", f"Erro ao listar YAML no servidor:\n{e.output}")
                    return
                except Exception as e:
                    messagebox.showerror("Runner (SSH)", f"Falha ao executar SSH: {e}")
                    return

                files = [ln.strip() for ln in out.splitlines() if ln.strip()]
                files.sort()
                if not files:
                    return

                for fname in files:
                    # caminho remoto completo (assumindo rdir como base)
                    if fname.startswith("/"):
                        ypath = fname
                        label = os.path.basename(fname)
                    else:
                        ypath = rdir.rstrip("/") + "/" + fname
                        label = fname
                    total = int(self.var_snaps.get())
                    self.tree.insert("", "end", iid=ypath,
                                     values=(label, "Pronto", f"0/{total}", "0", "--"))
                return
                """
            # Modo LOCAL (comportamento anterior)
            folder = getattr(self, "run_folder", tk.StringVar(value=os.getcwd())).get()
            if not os.path.isdir(folder):
                return
            files = [f for f in os.listdir(folder) if f.lower().endswith((".yaml", ".yml"))]
            files.sort()
            for f in files:
                path = os.path.join(folder, f)
                total = self._yaml_num_snapshots(path) or int(self.var_snaps.get())
                self.tree.insert("", "end", iid=path,
                                 values=(os.path.basename(path), "Pronto", f"0/{total}", "0", "--"))

    def _ssh_connect(self):
            host = self.ssh_host.get().strip()
            user = self.ssh_user.get().strip()
            port = int(self.ssh_port.get())
            pwd = self.ssh_password.get().strip()

            if not host or not user:
                messagebox.showerror("SSH", "Host e usuário são obrigatórios.")
                return

            # ===========================================
            # 1) MODO SENHA (PARAMIKO)
            # ===========================================
            if self.ssh_use_password.get():
                import paramiko
                from tkinter import simpledialog

                try:
                    cli = paramiko.SSHClient()
                    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    cli.connect(
                        hostname=host,
                        port=port,
                        username=user,
                        password=pwd,
                        timeout=10,
                        allow_agent=False,
                        look_for_keys=False
                    )
                    self.ssh_client = cli
                    self.ssh_connected = True
                    self.ssh_status.set("🟢 Conectado (Senha)")
                    try:
                        branch = self._get_remote_git_branch()
                    except Exception:
                        branch = "(indefinida)"

                    if hasattr(self, "lbl_remote_branch"):
                        self.lbl_remote_branch.config(text=f"Branch: {branch}")

                    # ===== Atualiza lista de branches disponíveis =====
                    try:
                        branches = self._get_remote_git_branches()
                    except Exception:
                        branches = []

                    if hasattr(self, "cmb_git_branch"):
                        self.cmb_git_branch["values"] = branches

                    # ===== Se a branch atual existir na lista, seleciona =====
                    if branch in branches and hasattr(self, "var_git_branch"):
                        self.var_git_branch.set(branch)
                    else:
                        if hasattr(self, "var_git_branch"):
                            self.var_git_branch.set("")


                    messagebox.showinfo("SSH", "Conectado via senha com Paramiko.")
                    return

                except Exception as e:
                    self.ssh_client = None
                    self.ssh_connected = False
                    self.ssh_status.set("🔴 Falha SSH")
                    messagebox.showerror("SSH", f"Erro ao conectar via senha:\n{e}")
                    return

            # ===========================================
            # 2) MODO CHAVE / SSH LOCAL
            # ===========================================
            cmd = ["ssh", "-p", str(port), f"{user}@{host}", "echo SSH_OK"]

            try:
                out = subprocess.check_output(cmd, timeout=6).decode().strip()
                if "SSH_OK" in out:
                    self.ssh_connected = True
                    self.ssh_status.set("🟢 Conectado (Chave)")
                    # Atualiza branch atual
                    branch = self._get_remote_git_branch()
                    self.lbl_remote_branch.config(text=f"Branch: {branch}")

                    # Atualiza lista de branches disponíveis
                    branches = self._get_remote_git_branches()
                    self.cmb_git_branch["values"] = branches
                    messagebox.showinfo("SSH", "Conexão estabelecida com sucesso.")
            except Exception as e:
                self.ssh_connected = False
                self.ssh_status.set("🔴 Falha na conexão")
                messagebox.showerror("SSH", f"Falha na conexão:\n{e}")

    def _ssh_disconnect(self):
            self.ssh_connected = False
            self.ssh_status.set("Desconectado")

    def _stop_selected(self):
            sel = self.tree.selection()
            if not sel:
                messagebox.showwarning("Runner", "Selecione pelo menos um YAML.")
                return


            # ============================================================
            # ===================== MODO REMOTO (SSH) ====================
            # ============================================================
            if self.var_run_mode.get() == "SSH":

                if not self.ssh_client:
                    messagebox.showerror("SSH", "Você não está conectado ao servidor.")
                    return

                if not hasattr(self, "_remote_tmp_dir") or not self._remote_tmp_dir:
                    messagebox.showwarning("SSH", "Nenhuma pasta remota ativa para cancelamento.")
                    return

                for iid in sel:
                    try:
                        local_yaml = iid
                        fname = os.path.basename(local_yaml)
                        remote_yaml = f"{self._remote_tmp_dir}/{fname}"

                        #try:
                        #    self.remote_output_by_yaml[local_yaml] = self._yaml_output_dir(local_yaml)
                        #except Exception:
                        #    pass
                        def _kill(_iid=iid, _local_yaml=local_yaml, _fname=fname, _remote_yaml=remote_yaml):
                            try:
                                # localizar PID (preferir PID armazenado; fallback por busca)
                                if not hasattr(self, "remote_pid_by_yaml"):
                                    self.remote_pid_by_yaml = {}

                                pid = self.remote_pid_by_yaml.get(_iid) or self.remote_pid_by_yaml.get(_local_yaml)

                                # Confirma se o PID ainda está vivo
                                if pid:
                                    check_cmd = f"ps -p {pid} -o pid= 2>/dev/null"
                                    stdin, stdout, stderr = self.ssh_client.exec_command(check_cmd)
                                    alive = stdout.read().decode().strip()
                                    if not alive:
                                        pid = ""

                                if not pid:
                                    # Filtra python e pega o ÚLTIMO PID para evitar pegar bash/ssh wrapper
                                    find_pid_cmd = (
                                        f"ps -eo pid,cmd | grep -F '{_remote_yaml}' "
                                        f"| grep -v grep | grep -E 'python(3|[0-9\\.])' "
                                        f"| awk '{{print $1}}' | tail -n 1"
                                    )
                                    stdin, stdout, stderr = self.ssh_client.exec_command(find_pid_cmd)
                                    pid = stdout.read().decode().strip()

                                if not pid:
                                    self._append_log(f"[REMOTE] Nenhum processo encontrado para {_fname}")
                                    self._update_row(_iid, status="Não está rodando", eta="--")
                                    return

                                self._append_log(f"[REMOTE] Matando PID {pid} ({_fname})")
                                kill_cmd = f"kill -9 {pid}"
                                self.ssh_client.exec_command(kill_cmd)

                                # remove PID armazenado
                                self.remote_pid_by_yaml.pop(_iid, None)
                                self.remote_pid_by_yaml.pop(_local_yaml, None)

                                self._update_row(_iid, status="Parado pelo usuário", eta="--")

                                # Baixa resultados (uma vez só; a função já tem dedupe)
                                try:
                                    self._download_outputs_for_yaml(_local_yaml, when="stop")
                                except Exception:
                                    pass

                            except Exception as e:
                                self._update_row(_iid, status=f"Erro ao parar: {e}")

                        threading.Thread(target=_kill, daemon=True).start()

                    except Exception as e:
                        self._update_row(iid, status=f"Erro ao parar: {e}")
                        self._cleanup_remote_tmp_dir()

                return  # <<< impede cair na lógica local
            else:
                # ============================================================
                # ======================== MODO LOCAL ========================
                # ============================================================
                for iid in sel:
                    p = self.procs.get(iid)
                    if p and (p.poll() is None):
                        try:
                            p.terminate()
                            try:
                                p.wait(timeout=2.0)
                            except Exception:
                                p.kill()
                            self._update_row(iid, status="Parado pelo usuário", eta="--")
                        except Exception as e:
                            self._update_row(iid, status=f"Erro ao parar: {e}")
                    else:
                        self._update_row(iid, status="Não está rodando")

    def _update_htop_loop(self):
            if not hasattr(self, "_htop_window"):
                return

            if not self._htop_window.winfo_exists():
                return

            try:
                # Se htop existir, usa ele; senão cai para top
                cmd = "htop -b -n 1 || top -b -n 1"

                out, err = self._exec_remote_paramiko(cmd)

                self._htop_text.configure(state="normal")
                self._htop_text.delete("1.0", "end")
                self._htop_text.insert("end", out)
                self._htop_text.configure(state="disabled")

            except Exception as e:
                self._htop_text.configure(state="normal")
                self._htop_text.insert("end", f"\nERRO AO ATUALIZAR HTOP:\n{e}\n")
                self._htop_text.configure(state="disabled")

            # atualiza a cada 2 segundos
            self.after(2000, self._update_htop_loop)

    def _update_row(self, iid, status=None, snap=None, pct=None, eta=None):
            try:
                cur = list(self.tree.item(iid, "values"))
                if not cur:
                    return
                if status is not None: cur[1] = status
                if snap   is not None: cur[2] = snap
                if pct    is not None: cur[3] = pct
                if eta    is not None: cur[4] = eta
                self.tree.item(iid, values=cur)
            except Exception:
                pass

    def _upload_yaml_files_remote(self, yaml_files, remote_dir):
        """
        Envia os arquivos YAML locais para a pasta remota criada no servidor.
        Reescreve dentro do YAML o general.output_dir para um caminho remoto,
        mantendo o general.output_dir_prefix (quando existir).

        Observações importantes:
        - O YAML enviado ao servidor é um arquivo TEMPORÁRIO (com output_dir remoto).
        - O download de resultados considera output_dir/output_dir_prefix.
        """
        if not self.ssh_client:
            raise RuntimeError("SSH não conectado.")

        try:
            sftp = self.ssh_client.open_sftp()

            # cache dicts
            if not hasattr(self, "remote_output_by_yaml"):
                self.remote_output_by_yaml = {}
            if not hasattr(self, "local_output_by_yaml"):
                self.local_output_by_yaml = {}

            for local_yaml in yaml_files:
                fname = os.path.basename(local_yaml)
                remote_path = f"{remote_dir}/{fname}"

                # parse local yaml
                with open(local_yaml, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                remote_output_dir = f"{remote_dir}/output"  # pasta remota base
                out_pref = data.get("general", {}).get("output_dir_prefix", "").strip()

                # sobrescreve output_dir no YAML para ser remoto
                data.setdefault("general", {})
                data["general"]["output_dir"] = remote_output_dir

                # salva em cache o caminho remoto FINAL (output_dir/output_dir_prefix)
                if out_pref:
                    remote_final = f"{remote_output_dir}/{out_pref}"
                else:
                    remote_final = remote_output_dir

                self.remote_output_by_yaml[local_yaml] = remote_final    

                gen = data.setdefault("general", {})

                local_output_dir = gen.get("output_dir")
                out_prefix = gen.get("output_dir_prefix")
                out_basename = os.path.basename(os.path.normpath(str(local_output_dir))) if local_output_dir else "output"

                # remote output base (same final folder name as local output_dir)
                remote_output_dir = f"{remote_dir}/{out_basename}"
                gen["output_dir"] = remote_output_dir

                # ensure output base exists on remote (best effort)
                try:
                    self.ssh_client.exec_command(f"mkdir -p '{remote_output_dir}'")
                except Exception:
                    pass

                # Cache: remote path that we will download (output_dir/output_dir_prefix when present)
                remote_full = remote_output_dir
                if out_prefix:
                    remote_full = f"{remote_output_dir}/{out_prefix}"
                self.remote_output_by_yaml[local_yaml] = remote_full
                self.local_output_by_yaml[local_yaml] = local_output_dir

                # Write a temp YAML and upload it
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
                try:
                    yaml.safe_dump(data, tmp, sort_keys=False, allow_unicode=True)
                    tmp_path = tmp.name
                finally:
                    tmp.close()

                self._append_log(f"[REMOTE] Enviando {fname} -> {remote_path} (output_dir -> {remote_output_dir})")
                try:
                    sftp.put(tmp_path, remote_path)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

            sftp.close()
            self._append_log("[REMOTE] Upload dos YAMLs concluído.")

        except Exception as e:
            raise RuntimeError(f"Erro no upload dos YAMLs via SFTP:\n{e}")

    def _yaml_num_snapshots(self, ypath):
            try:
                with open(ypath, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict):
                    if "general" in data and isinstance(data["general"], dict) and "num_snapshots" in data["general"]:
                        return int(data["general"]["num_snapshots"])
                    if "num_snapshots" in data:
                        return int(data["num_snapshots"])
            except Exception:
                pass
            return None

    def _yaml_output_dir(self, ypath):
        """Best-effort: read YAML and return the configured output directory/path (string) if present."""
        try:
            import yaml
            with open(ypath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            return None

        def _walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str):
                        kk = k.lower()
                        if kk in {"output_dir", "output_directory", "output_path", "results_dir", "results_path"}:
                            if isinstance(v, str) and v.strip():
                                return v.strip()
                    found = _walk(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for it in obj:
                    found = _walk(it)
                    if found:
                        return found
            return None

        return _walk(data)

    def _yaml_output_prefix(self, local_yaml):
        """Return output_dir_prefix from YAML (or None)."""
        try:
            with open(local_yaml, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            gen = data.get("general", {}) or {}
            pref = gen.get("output_dir_prefix")
            return str(pref).strip() if pref else None
        except Exception:
            return None

    def _find_local_sharc_root(self, hint_path=None):
        """Find local SHARC repo root by walking up from a hint path (YAML path) or cwd."""
        cache = getattr(self, "_local_sharc_root_cache", None)
        if cache and os.path.isdir(cache):
            return cache

        start = Path(hint_path).resolve() if hint_path else Path.cwd().resolve()
        for p in [start] + list(start.parents):
            try:
                if (p / "setup.py").is_file() and (p / "sharc").is_dir():
                    setattr(self, "_local_sharc_root_cache", str(p))
                    return str(p)
            except Exception:
                pass

        # fallback: just use cwd
        setattr(self, "_local_sharc_root_cache", str(Path.cwd().resolve()))
        return cache

    def _map_remote_to_local_path(self, remote_path, local_yaml_hint=None):
        """Map a remote SHARC path (/home/.../SHARC/...) into the local SHARC root (best effort)."""
        remote_base = f"/home/{self.ssh_user.get().strip()}/SHARC"
        local_base = self._find_local_sharc_root(local_yaml_hint)

        try:
            rp = str(remote_path)
            if rp.startswith(remote_base + "/"):
                rel = rp[len(remote_base) + 1 :]
                return str(Path(local_base) / rel)
        except Exception:
            pass

        # If it's already relative, just place it under local base.
        try:
            if not os.path.isabs(str(remote_path)):
                return str(Path(local_base) / str(remote_path))
        except Exception:
            pass

        # Otherwise: dump into local_base/output_downloads/<basename>
        return str(Path(local_base) / "output_downloads" / Path(str(remote_path)).name)

    # =========================
    # SFTP download (recursive)
    # =========================
    def _sftp_download_dir(self, sftp, remote_dir: str, local_dir: str):
        os.makedirs(local_dir, exist_ok=True)

        for entry in sftp.listdir_attr(remote_dir):
            rpath = f"{remote_dir.rstrip('/')}/{entry.filename}"
            lpath = os.path.join(local_dir, entry.filename)

            # S_ISDIR bit
            if stat.S_ISDIR(entry.st_mode):
                self._sftp_download_dir(sftp, rpath, lpath)
            else:
                os.makedirs(os.path.dirname(lpath), exist_ok=True)
                sftp.get(rpath, lpath)

    def _download_outputs_for_yaml(self, local_yaml: str, when: str = "finish"):
        """Download remote output folder into the local output_dir/output_dir_prefix."""
        if not self.ssh_client:
            return
    # 🔒 evita download duplicado
        if local_yaml in self._downloaded_yamls:
            self._append_log(
                f"[REMOTE][DL] Download já realizado anteriormente para {os.path.basename(local_yaml)} — pulando"
            )
            return
        local_out_dir = self._yaml_output_dir(local_yaml)
        local_out_pref = self._yaml_output_prefix(local_yaml)

        if not local_out_dir:
            self._append_log(f"[REMOTE][DL][WARN] Não encontrei output_dir no YAML: {os.path.basename(local_yaml)}")
            return

        local_dest = local_out_dir
        if local_out_pref:
            local_dest = os.path.join(local_out_dir, local_out_pref)

        # Prefer cached remote output (already includes prefix)
        remote_out = self.remote_output_by_yaml.get(local_yaml)

        if not remote_out:
            out_pref = self._yaml_output_prefix(local_yaml)  # lê só o prefix local
            remote_base = f"{self._remote_tmp_dir}/output"
            remote_out = f"{remote_base}/{out_pref}" if out_pref else remote_base

        if not remote_out:
            self._append_log(f"[REMOTE][DL][WARN] Não consegui inferir caminho remoto de output para: {os.path.basename(local_yaml)}")
            return
        
        self._remote_downloading.add(local_yaml)
        try:
            self._append_log(f"[REMOTE][DL] ({when}) Baixando: {remote_out} -> {local_dest}")
            sftp = self.ssh_client.open_sftp()
            try:
                # ---- helper: exists? ----
                def _remote_exists(path: str) -> bool:
                    try:
                        sftp.stat(path)
                        return True
                    except IOError:
                        return False
                # 1) Resolver pasta remota real (prefix + sufixo dinâmico)
                if not _remote_exists(remote_out) and local_out_pref:
                    # remote_out esperado: .../output/output_mss_-40
                    # mas o real pode ser: .../output/output_mss_-40_YYYY-MM-DD_XX
                    remote_out_norm = remote_out.rstrip("/")
                    remote_base = os.path.dirname(remote_out_norm)   # <-- FIX: LISTAR A PASTA PAI (.../output)
                    
                    try:
                        entries = sftp.listdir_attr(remote_base)
                        dirs = [e for e in entries if stat.S_ISDIR(e.st_mode)]

                        # match exato (raro)
                        exact = [d for d in dirs if d.filename == local_out_pref]
                        if exact:
                            remote_out = f"{remote_base}/{exact[0].filename}"
                        else:
                            # match por prefixo (o caso comum)
                            prefixed = [d for d in dirs if d.filename.startswith(local_out_pref + "_")]
                            if prefixed:
                                best = max(prefixed, key=lambda d: d.st_mtime)
                                remote_out = f"{remote_base}/{best.filename}"

                    except Exception as e:
                        self._append_log(
                            f"[REMOTE][DL][WARN] Falha ao resolver pasta dinâmica em {remote_base}: {e}"
                        )

                # 2) Garante que o diretório LOCAL existe
                os.makedirs(local_dest, exist_ok=True)

                # 3) Se ainda não existe, loga e aborta (não dá Errno 2)
                if not _remote_exists(remote_out):
                    self._append_log(
                        f"[REMOTE][DL][WARN] Pasta remota não encontrada para download: {remote_out}"
                    )
                    return

                # 4) Agora sim, baixa recursivamente
                self._append_log(
                    f"[REMOTE][DL] ({when}) Baixando: {remote_out} -> {local_dest}"
                )

                self._sftp_download_dir(sftp, remote_out, local_dest)

            finally:
                sftp.close()

            self._append_log(f"[REMOTE][DL] OK: {os.path.basename(local_yaml)}")
            self._downloaded_yamls.add(local_yaml)
        except Exception as e:
            self._append_log(f"[REMOTE][DL][ERR] Falha ao baixar resultados ({os.path.basename(local_yaml)}): {e}")
        finally:
            self._remote_downloading.discard(local_yaml)
            downloading = any(t.is_alive() for t in self._remote_downloading.values())
            if not self._remote_pending and not downloading:
                self._maybe_cleanup_remote_tmp_dir()

    def _remote_base_dir(self) -> str:
        """Base directory of SHARC repo on the remote host for the current SSH user."""
        return f"/home/{self.ssh_user.get().strip()}/SHARC"


    def _maybe_cleanup_remote_tmp_dir(self):
        # Só limpa se:
        # - existe tmp dir
        # - não tem processo remoto pendente
        # - não tem downloads pendentes
        if not getattr(self, "_remote_tmp_dir", None):
            return

        pending = getattr(self, "_remote_pending", set())
        downloading = getattr(self, "_remote_downloading", set())

        if len(pending) == 0 and len(downloading) == 0:
            self._cleanup_remote_tmp_dir()

