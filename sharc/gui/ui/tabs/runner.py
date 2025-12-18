import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
from pathlib import Path


class RunnerTab:
    def __init__(self, app, parent_frame):
        """
        :param app: Instância da classe App (main.py)
        :param parent_frame: O widget onde esta aba será desenhada
        """
        self.app = app
        self.frame = parent_frame

        # Referência atalho para o manager (backend)
        # Assume que o App instanciou: self.runner_manager = RunnerManager(...)
        self.manager = getattr(app, 'runner_manager', None)

        self._build_ui()

        # Inicializa estado da UI
        self._scan_yaml_files()
        self._toggle_ssh_frame()
        self._toggle_tunnel()

    def _build_ui(self):
        # =========================================================
        # TÚNEL SSH (BASTION)
        # =========================================================
        frm_tunnel = ttk.LabelFrame(self.frame, text="Túnel SSH (Bastion)")
        frm_tunnel.pack(fill="x", pady=6)

        # Linha 1: Bastion
        ttk.Label(frm_tunnel, text="Host Bastion").grid(row=0, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_host).grid(
            row=0, column=1)
        ttk.Label(frm_tunnel, text="Usuário").grid(row=0, column=2)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_user).grid(
            row=0, column=3)
        ttk.Label(frm_tunnel, text="Porta").grid(row=0, column=4)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_port,
                  width=6).grid(row=0, column=5)

        # Linha 2: Interno
        ttk.Label(frm_tunnel, text="IP Interno").grid(row=1, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_internal_ip).grid(
            row=1, column=1)
        ttk.Label(frm_tunnel, text="Porta Int").grid(row=1, column=2)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_internal_port,
                  width=6).grid(row=1, column=3)
        ttk.Label(frm_tunnel, text="Porta Local").grid(row=1, column=4)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_local_port,
                  width=6).grid(row=1, column=5)

        # Linha 3: Chave e Botões
        ttk.Label(frm_tunnel, text="Chave").grid(row=2, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_key_path,
                  width=50).grid(row=2, column=1, columnspan=4)
        ttk.Button(frm_tunnel, text="Escolher", command=lambda: self._pick_file(
            self.app.tunnel_key_path)).grid(row=2, column=5)

        ttk.Button(frm_tunnel, text="Criar Túnel",
                   command=self._create_tunnel_ui).grid(row=3, column=0, pady=4)
        ttk.Button(frm_tunnel, text="Fechar Túnel",
                   command=self._close_tunnel_ui).grid(row=3, column=1, pady=4)
        ttk.Label(frm_tunnel, textvariable=self.app.tunnel_status).grid(
            row=3, column=2, columnspan=3)

        # =========================================================
        # MODO DE EXECUÇÃO
        # =========================================================
        frm_mode = ttk.LabelFrame(self.frame, text="Modo de Execução")
        frm_mode.pack(fill="x", pady=6)

        ttk.Radiobutton(frm_mode, text="Local", value="LOCAL",
                        variable=self.app.var_run_mode).pack(side="left", padx=6)
        ttk.Radiobutton(frm_mode, text="Remoto (SSH)", value="SSH",
                        variable=self.app.var_run_mode).pack(side="left", padx=6)

        # Hook para mostrar/esconder painel SSH
        self.app.var_run_mode.trace_add("write", self._toggle_ssh_frame)

        # =========================================================
        # CONEXÃO SSH
        # =========================================================
        self.frm_ssh = ttk.LabelFrame(self.frame, text="Conexão SSH")
        # (Não damos pack agora, o _toggle_ssh_frame fará isso)

        ttk.Label(self.frm_ssh, text="Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_host,
                  width=24).grid(row=0, column=1, sticky="we")
        ttk.Label(self.frm_ssh, text="Usuário").grid(
            row=0, column=2, sticky="w")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_user,
                  width=18).grid(row=0, column=3, sticky="we")
        ttk.Label(self.frm_ssh, text="Porta").grid(row=0, column=4, sticky="w")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_port,
                  width=6).grid(row=0, column=5, sticky="w")

        ttk.Label(self.frm_ssh, text="Diretório remoto").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_remote_dir,
                  width=60).grid(row=1, column=1, columnspan=5, sticky="we")

        # Opções de Autenticação
        ttk.Checkbutton(self.frm_ssh, text="Usar chave SSH / túnel",
                        variable=self.app.ssh_use_tunnel).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(self.frm_ssh, text="Usar senha",
                        variable=self.app.ssh_use_password).grid(row=0, column=4, padx=6)

        self.app.ssh_use_tunnel.trace_add("write", self._toggle_tunnel)

        # Subframe da chave (aparece condicionalmente)
        self.frm_tunnel_opts = ttk.Frame(self.frm_ssh)
        ent_key = ttk.Entry(self.frm_tunnel_opts,
                            textvariable=self.app.ssh_key_path, width=50)
        ent_key.pack(side="left", fill="x", expand=True)
        ttk.Button(self.frm_tunnel_opts, text="Escolher", command=lambda: self._pick_file(
            self.app.ssh_key_path)).pack(side="left", padx=(4, 0))

        # Botões de conexão e Git
        ttk.Button(self.frm_ssh, text="Conectar", command=self._ssh_connect_ui).grid(
            row=3, column=0, pady=6, sticky="w")
        ttk.Button(self.frm_ssh, text="Desconectar", command=self._ssh_disconnect_ui).grid(
            row=3, column=1, pady=6, sticky="w")
        ttk.Label(self.frm_ssh, textvariable=self.app.ssh_status).grid(
            row=3, column=2, columnspan=3, sticky="w")

        ttk.Button(self.frm_ssh, text="HTOP", command=self._open_htop_window).grid(
            row=3, column=3, padx=4)

        # Git Branch Control
        self.lbl_remote_branch = ttk.Label(self.frm_ssh, text="Branch: --")
        self.lbl_remote_branch.grid(row=2, column=1, padx=6, sticky="w")

        self.cmb_git_branch = ttk.Combobox(
            self.frm_ssh, textvariable=self.app.var_git_branch, state="readonly", width=28)
        self.cmb_git_branch.grid(row=2, column=4, padx=6)

        ttk.Button(self.frm_ssh, text="Trocar Branch (FORCE)",
                   command=self._on_force_checkout_clicked).grid(row=2, column=5, padx=4)

        for c in range(6):
            self.frm_ssh.grid_columnconfigure(c, weight=1)

        # =========================================================
        # LISTA DE ARQUIVOS E EXECUÇÃO
        # =========================================================
        top = ttk.Frame(self.frame)
        top.pack(fill="x")

        ttk.Label(top, text="Pasta com arquivos .yaml").pack(side="left")
        e = ttk.Entry(top, textvariable=self.app.run_folder)
        e.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Escolher...",
                   command=self._pick_folder).pack(side="left")
        ttk.Button(top, text="Atualizar lista", command=self._scan_yaml_files).pack(
            side="left", padx=(6, 0))

        ttk.Label(top, text="Paralelo (máx):").pack(side="left", padx=(14, 4))
        tk.Spinbox(top, from_=1, to=32, width=4,
                   textvariable=self.app.var_max_workers).pack(side="left")

        # Treeview (Exposta publicamente como self.tree)
        mid = ttk.Frame(self.frame)
        mid.pack(fill="both", expand=True, pady=(8, 0))

        self.tree = ttk.Treeview(mid, columns=(
            "yaml", "status", "snap", "pct", "eta"), show="headings", height=12)
        self.tree.heading("yaml", text="YAML")
        self.tree.heading("status", text="Status")
        self.tree.heading("snap", text="Snapshots")
        self.tree.heading("pct", text="%")
        self.tree.heading("eta", text="ETA")

        self.tree.column("yaml", width=380)
        self.tree.column("status", width=220)
        self.tree.column("snap", width=120)
        self.tree.column("pct", width=60, anchor="e")
        self.tree.column("eta", width=100)

        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.configure(yscroll=sb.set)

        # Controles Inferiores
        right = ttk.Frame(self.frame)
        right.pack(fill="x", pady=(8, 0))

        ttk.Label(right, text="main_cli.py:").pack(side="left")
        ttk.Entry(right, textvariable=self.app.main_cli_path, width=44).pack(
            side="left", padx=6, fill="x", expand=True)

        ttk.Button(right, text="Parar selecionados",
                   command=self._stop_selected_ui).pack(side="right", padx=(6, 0))
        ttk.Button(right, text="Executar selecionados",
                   command=self._run_selected_ui).pack(side="right")

        # Log (Exposto publicamente como self.txt_log)
        logf = ttk.LabelFrame(self.frame, text="Log")
        logf.pack(fill="both", expand=True, pady=(8, 0))
        self.txt_log = tk.Text(logf, height=10, wrap="none")
        self.txt_log.pack(fill="both", expand=True)

    # ---------------- UI Logic & Callbacks ----------------

    def _toggle_ssh_frame(self, *_):
        if self.app.var_run_mode.get() == "SSH":
            self.frm_ssh.pack(fill="x", pady=6, after=self.frame.children.get(
                "!labelframe2"))  # tenta manter ordem
        else:
            self.frm_ssh.pack_forget()

    def _toggle_tunnel(self, *_):
        if self.app.ssh_use_tunnel.get():
            self.frm_tunnel_opts.grid(
                row=2, column=1, columnspan=5, sticky="we", padx=(4, 0), pady=(4, 0))
        else:
            self.frm_tunnel_opts.grid_remove()

    def _pick_file(self, tk_var):
        init = os.path.dirname(tk_var.get()) if tk_var.get() else os.getcwd()
        path = filedialog.askopenfilename(initialdir=init, filetypes=[(
            "Chaves", "*.pem *.ppk *.key *.rsa"), ("Todos", "*.*")])
        if path:
            tk_var.set(path)

    def _pick_folder(self):
        path = filedialog.askdirectory(
            initialdir=self.app.run_folder.get() or os.getcwd())
        if path:
            self.app.run_folder.set(path)
            self._scan_yaml_files()

    # ---------------- Interação com Manager (Backend) ----------------

    def _scan_yaml_files(self):
        # Limpa Treeview
        self.tree.delete(*self.tree.get_children())

        mode = self.app.var_run_mode.get()

        if mode == "LOCAL":
            folder = self.app.run_folder.get()
            if os.path.isdir(folder):
                files = [f for f in os.listdir(
                    folder) if f.lower().endswith((".yaml", ".yml"))]
                files.sort()
                for f in files:
                    full = os.path.join(folder, f)
                    self.tree.insert("", "end", iid=full, values=(
                        f, "Pronto", "0/--", "0", "--"))

        elif mode == "SSH":
            # Aqui chamamos o manager para listar arquivos remotos
            if self.manager and self.manager.ssh_connected:
                files = self.manager.list_remote_files(
                    self.app.ssh_remote_dir.get())
                for f in files:
                    # Se vier path completo ou só nome, ajuste conforme retorno do manager
                    self.tree.insert("", "end", iid=f, values=(
                        os.path.basename(f), "Pronto", "0/--", "0", "--"))
            else:
                self.app._safe_log(
                    "SSH desconectado. Não é possível listar arquivos remotos.")

    def _ssh_connect_ui(self):
        """Coleta dados da UI e chama o manager."""
        if self.app.ssh_use_password.get():
            pwd = simpledialog.askstring(
                "Senha SSH", f"Senha para {self.app.ssh_user.get()}:", show="*")
            if not pwd:
                return
            self.manager.connect_ssh_password(
                self.app.ssh_host.get(), self.app.ssh_user.get(), int(self.app.ssh_port.get()), pwd
            )
        else:
            self.manager.connect_ssh_key(
                self.app.ssh_host.get(), self.app.ssh_user.get(), int(
                    self.app.ssh_port.get()), self.app.ssh_key_path.get()
            )

        # Atualiza UI após tentativa
        if self.manager.ssh_connected:
            self.app.ssh_status.set("🟢 Conectado")
            # Opcional: Atualizar lista de branches
            branches = self.manager.get_git_branches()
            self.cmb_git_branch['values'] = branches
        else:
            self.app.ssh_status.set("🔴 Falha")

    def _ssh_disconnect_ui(self):
        if self.manager:
            self.manager.disconnect_ssh()
        self.app.ssh_status.set("Desconectado")

    def _create_tunnel_ui(self):
        # Coleta dados e chama manager
        self.manager.create_tunnel(
            self.app.tunnel_bastion_host.get(),
            self.app.tunnel_bastion_user.get(),
            self.app.tunnel_bastion_port.get(),
            self.app.tunnel_internal_ip.get(),
            self.app.tunnel_internal_port.get(),
            self.app.tunnel_local_port.get(),
            self.app.tunnel_key_path.get()
        )
        # Atualiza UI (status pode ser atualizado via callback do manager no main app)

    def _close_tunnel_ui(self):
        self.manager.close_tunnel()

    def _run_selected_ui(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Runner", "Selecione arquivos.")
            return

        mode = self.app.var_run_mode.get()
        if mode == "SSH":
            self.manager.run_remote_parallel(
                list(sel), int(self.app.var_max_workers.get()))
        else:
            self.manager.run_local_parallel(
                list(sel), int(self.app.var_max_workers.get()))

    def _stop_selected_ui(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.manager.stop_simulations(list(sel))

    def _on_force_checkout_clicked(self):
        branch = self.app.var_git_branch.get()
        if not branch:
            return
        if messagebox.askyesno("Git Force", f"Resetar e checkout para {branch}?"):
            self.manager.git_force_checkout(branch)

    # ---------------- HTOP Window ----------------

    def _open_htop_window(self):
        if not self.manager or not self.manager.ssh_connected:
            messagebox.showerror("SSH", "Não conectado.")
            return

        win = tk.Toplevel(self.frame)
        win.title("HTOP Remoto")
        win.geometry("800x600")

        txt = tk.Text(win, bg="black", fg="lime", font=("Consolas", 9))
        txt.pack(fill="both", expand=True)

        def _update():
            if not win.winfo_exists():
                return
            out = self.manager.exec_command_output(
                "htop -b -n 1 || top -b -n 1")
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", out)
            txt.configure(state="disabled")
            win.after(2000, _update)

        _update()
