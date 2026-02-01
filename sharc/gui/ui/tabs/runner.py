import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
from pathlib import Path


class RunnerTab:
    """
    Manages the simulation execution tab.

    This class handles the configuration of execution modes (Local vs. Remote/SSH),
    manages SSH tunneling (Bastion host) for secure access, allows file selection
    for batch processing, and monitors execution status via logs and process viewers.
    """

    def __init__(self, app, parent_frame):
        """
        Initializes the RunnerTab.

        Args:
            app: Instance of the main App class (main.py).
            parent_frame: The widget where this tab will be drawn.
        """
        self.app = app
        self.frame = parent_frame

        # Shortcut reference to the backend manager
        # Assumes App instantiated: self.runner_manager = RunnerManager(...)
        self.manager = getattr(app, 'runner_manager', None)

        self._build_ui()

        # Initialize UI state
        self._scan_yaml_files()
        self._toggle_ssh_frame()
        self._toggle_tunnel()

    def _build_ui(self):
        """Constructs the user interface elements."""

        # =========================================================
        # SSH TUNNEL (BASTION)
        # =========================================================
        #
        # This section configures a jump host (bastion). A bastion host is a special purpose computer
        # on a network specifically designed and configured to withstand attacks, used as a portal
        # to access a private network from an external network.

        frm_tunnel = ttk.LabelFrame(self.frame, text="SSH Tunnel (Bastion)")
        frm_tunnel.pack(fill="x", pady=6)

        # Row 1: Bastion
        ttk.Label(frm_tunnel, text="Bastion Host").grid(row=0, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_host).grid(
            row=0, column=1)
        ttk.Label(frm_tunnel, text="User").grid(row=0, column=2)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_user).grid(
            row=0, column=3)
        ttk.Label(frm_tunnel, text="Port").grid(row=0, column=4)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_port,
                  width=6).grid(row=0, column=5)

        # Row 2: Internal Target
        ttk.Label(frm_tunnel, text="Internal IP").grid(row=1, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_internal_ip).grid(
            row=1, column=1)
        ttk.Label(frm_tunnel, text="Int Port").grid(row=1, column=2)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_internal_port,
                  width=6).grid(row=1, column=3)
        ttk.Label(frm_tunnel, text="Local Port").grid(row=1, column=4)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_local_port,
                  width=6).grid(row=1, column=5)

        # Row 3: Key and Actions
        ttk.Label(frm_tunnel, text="Key").grid(row=2, column=0)
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_key_path,
                  width=50).grid(row=2, column=1, columnspan=4)
        ttk.Button(frm_tunnel, text="Browse", command=lambda: self._pick_file(
            self.app.tunnel_key_path)).grid(row=2, column=5)

        ttk.Button(frm_tunnel, text="Create Tunnel",
                   command=self._create_tunnel_ui).grid(row=3, column=0, pady=4)
        ttk.Button(frm_tunnel, text="Close Tunnel",
                   command=self._close_tunnel_ui).grid(row=3, column=1, pady=4)
        ttk.Label(frm_tunnel, textvariable=self.app.tunnel_status).grid(
            row=3, column=2, columnspan=3)

        # =========================================================
        # EXECUTION MODE
        # =========================================================
        frm_mode = ttk.LabelFrame(self.frame, text="Execution Mode")
        frm_mode.pack(fill="x", pady=6)

        ttk.Radiobutton(frm_mode, text="Local", value="LOCAL",
                        variable=self.app.var_run_mode).pack(side="left", padx=6)
        ttk.Radiobutton(frm_mode, text="Remote (SSH)", value="SSH",
                        variable=self.app.var_run_mode).pack(side="left", padx=6)

        # Hook to show/hide SSH panel based on selection
        self.app.var_run_mode.trace_add("write", self._toggle_ssh_frame)

        # =========================================================
        # SSH CONNECTION
        # =========================================================
        #
        # This section handles the credentials for the compute server. SSH keys are generally
        # preferred over passwords for automated or script-based connections due to better security.

        self.frm_ssh = ttk.LabelFrame(self.frame, text="SSH Connection")

        ttk.Label(self.frm_ssh, text="Host").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_host,
                  width=24).grid(row=0, column=1, sticky="we")
        ttk.Label(self.frm_ssh, text="User").grid(
            row=0, column=2, sticky="w")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_user,
                  width=18).grid(row=0, column=3, sticky="we")
        ttk.Label(self.frm_ssh, text="Port").grid(row=0, column=4, sticky="w")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_port,
                  width=6).grid(row=0, column=5, sticky="w")

        ttk.Label(self.frm_ssh, text="Remote Directory").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_remote_dir,
                  width=60).grid(row=1, column=1, columnspan=5, sticky="we")

        # Auth Options
        ttk.Checkbutton(self.frm_ssh, text="Use SSH Key / Tunnel",
                        variable=self.app.ssh_use_tunnel).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(self.frm_ssh, text="Use Password",
                        variable=self.app.ssh_use_password).grid(row=0, column=4, padx=6)

        self.app.ssh_use_tunnel.trace_add("write", self._toggle_tunnel)

        # Key subframe (conditionally visible)
        self.frm_tunnel_opts = ttk.Frame(self.frm_ssh)
        ent_key = ttk.Entry(self.frm_tunnel_opts,
                            textvariable=self.app.ssh_key_path, width=50)
        ent_key.pack(side="left", fill="x", expand=True)
        ttk.Button(self.frm_tunnel_opts, text="Browse", command=lambda: self._pick_file(
            self.app.ssh_key_path)).pack(side="left", padx=(4, 0))

        # Connection and Git Buttons
        ttk.Button(self.frm_ssh, text="Connect", command=self._ssh_connect_ui).grid(
            row=3, column=0, pady=6, sticky="w")
        ttk.Button(self.frm_ssh, text="Disconnect", command=self._ssh_disconnect_ui).grid(
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

        ttk.Button(self.frm_ssh, text="Switch Branch (FORCE)",
                   command=self._on_force_checkout_clicked).grid(row=2, column=5, padx=4)

        for c in range(6):
            self.frm_ssh.grid_columnconfigure(c, weight=1)

        # =========================================================
        # FILE LIST AND EXECUTION
        # =========================================================
        top = ttk.Frame(self.frame)
        top.pack(fill="x")

        ttk.Label(top, text="YAML Files Folder").pack(side="left")
        e = ttk.Entry(top, textvariable=self.app.run_folder)
        e.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Browse...",
                   command=self._pick_folder).pack(side="left")
        ttk.Button(top, text="Refresh List", command=self._scan_yaml_files).pack(
            side="left", padx=(6, 0))

        ttk.Label(top, text="Parallel (max):").pack(side="left", padx=(14, 4))
        tk.Spinbox(top, from_=1, to=32, width=4,
                   textvariable=self.app.var_max_workers).pack(side="left")

        # Treeview (Publicly exposed as self.tree)
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

        # Bottom Controls
        right = ttk.Frame(self.frame)
        right.pack(fill="x", pady=(8, 0))

        ttk.Label(right, text="main_cli.py:").pack(side="left")
        ttk.Entry(right, textvariable=self.app.main_cli_path, width=44).pack(
            side="left", padx=6, fill="x", expand=True)

        ttk.Button(right, text="Stop Selected",
                   command=self._stop_selected_ui).pack(side="right", padx=(6, 0))
        ttk.Button(right, text="Run Selected",
                   command=self._run_selected_ui).pack(side="right")

        # Log (Publicly exposed as self.txt_log)
        logf = ttk.LabelFrame(self.frame, text="Log")
        logf.pack(fill="both", expand=True, pady=(8, 0))
        self.txt_log = tk.Text(logf, height=10, wrap="none")
        self.txt_log.pack(fill="both", expand=True)

    # ---------------- UI Logic & Callbacks ----------------

    def _toggle_ssh_frame(self, *_):
        """Shows or hides the SSH configuration frame based on execution mode."""
        if self.app.var_run_mode.get() == "SSH":
            self.frm_ssh.pack(fill="x", pady=6, after=self.frame.children.get(
                "!labelframe2"))
        else:
            self.frm_ssh.pack_forget()

    def _toggle_tunnel(self, *_):
        """Shows or hides tunnel key options."""
        if self.app.ssh_use_tunnel.get():
            self.frm_tunnel_opts.grid(
                row=2, column=1, columnspan=5, sticky="we", padx=(4, 0), pady=(4, 0))
        else:
            self.frm_tunnel_opts.grid_remove()

    def _pick_file(self, tk_var):
        """Opens a file dialog to select SSH keys."""
        init = os.path.dirname(tk_var.get()) if tk_var.get() else os.getcwd()
        path = filedialog.askopenfilename(initialdir=init, filetypes=[(
            "Keys", "*.pem *.ppk *.key *.rsa"), ("All Files", "*.*")])
        if path:
            tk_var.set(path)

    def _pick_folder(self):
        """Opens a directory dialog to select the YAML folder."""
        path = filedialog.askdirectory(
            initialdir=self.app.run_folder.get() or os.getcwd())
        if path:
            self.app.run_folder.set(path)
            self._scan_yaml_files()

    # ---------------- Manager (Backend) Interaction ----------------

    def _scan_yaml_files(self):
        """Refreshes the Treeview with YAML files from the local or remote source."""
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
                        f, "Ready", "0/--", "0", "--"))

        elif mode == "SSH":
            if self.manager and self.manager.ssh_connected:
                files = self.manager.list_remote_files(
                    self.app.ssh_remote_dir.get())
                for f in files:
                    self.tree.insert("", "end", iid=f, values=(
                        os.path.basename(f), "Ready", "0/--", "0", "--"))
            else:
                self.app._safe_log(
                    "SSH disconnected. Cannot list remote files.")

    def _ssh_connect_ui(self):
        """Collects credentials and initiates SSH connection via the manager."""
        if self.app.ssh_use_password.get():
            pwd = simpledialog.askstring(
                "SSH Password", f"Password for {self.app.ssh_user.get()}:", show="*")
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

        if self.manager.ssh_connected:
            self.app.ssh_status.set("🟢 Connected")
            # Update git branches if connected
            branches = self.manager.get_git_branches()
            self.cmb_git_branch['values'] = branches
        else:
            self.app.ssh_status.set("🔴 Failed")

    def _ssh_disconnect_ui(self):
        """Disconnects the SSH session."""
        if self.manager:
            self.manager.disconnect_ssh()
        self.app.ssh_status.set("Disconnected")

    def _create_tunnel_ui(self):
        """Creates the SSH Bastion tunnel."""
        #
        # This setup typically creates a Local Port Forward. Traffic sent to a local port (e.g., 8080)
        # is tunneled through the Bastion host to a specific port on the Internal IP (Target).

        self.manager.create_tunnel(
            self.app.tunnel_bastion_host.get(),
            self.app.tunnel_bastion_user.get(),
            self.app.tunnel_bastion_port.get(),
            self.app.tunnel_internal_ip.get(),
            self.app.tunnel_internal_port.get(),
            self.app.tunnel_local_port.get(),
            self.app.tunnel_key_path.get()
        )

    def _close_tunnel_ui(self):
        """Closes the active SSH tunnel."""
        self.manager.close_tunnel()

    def _run_selected_ui(self):
        """Starts simulations for the selected YAML files."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Runner", "Select files.")
            return

        mode = self.app.var_run_mode.get()
        if mode == "SSH":
            self.manager.run_remote_parallel(
                list(sel), int(self.app.var_max_workers.get()))
        else:
            self.manager.run_local_parallel(
                list(sel), int(self.app.var_max_workers.get()))

    def _stop_selected_ui(self):
        """Stops the selected running simulations."""
        sel = self.tree.selection()
        if not sel:
            return
        self.manager.stop_simulations(list(sel))

    def _on_force_checkout_clicked(self):
        """Forces a git checkout on the remote server."""
        branch = self.app.var_git_branch.get()
        if not branch:
            return
        if messagebox.askyesno("Git Force", f"Reset and checkout to {branch}?"):
            self.manager.git_force_checkout(branch)

    # ---------------- HTOP Window ----------------

    def _open_htop_window(self):
        """Opens a window displaying the 'htop' process monitor from the remote server."""
        #
        # htop is an interactive process viewer for Unix systems. It provides a real-time,
        # color-coded view of CPU usage, memory consumption, and running processes.

        if not self.manager or not self.manager.ssh_connected:
            messagebox.showerror("SSH", "Not connected.")
            return

        win = tk.Toplevel(self.frame)
        win.title("Remote HTOP")
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
