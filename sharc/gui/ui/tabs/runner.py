import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
from pathlib import Path
import threading


class RunnerTab:
    """
    Manages the simulation execution tab.
    """

    def __init__(self, app, parent_frame):
        """
        Initializes the RunnerTab.
        """
        self.app = app
        self.frame = parent_frame

        self._build_ui()

        # --- CRITICAL ADAPTATION: Wire the Backend to this UI ---
        # We grab the manager instance from the main app and tell it:
        # "When you have a log message, call MY _append_log function."
        # "When you have a progress update, call MY _update_tree_row function."
        self.manager = getattr(app, 'runner_manager', None)
        if self.manager:
            self.manager.log_callback = self._append_log
            self.manager.update_row_callback = self._update_tree_row

        # Initialize UI state
        self._toggle_ssh_frame()
        self._toggle_tunnel()

        # Delay scan slightly to let UI settle
        self.frame.after(500, self._scan_yaml_files)

    def _build_ui(self):
        """Constructs the user interface elements."""

        # =========================================================
        # SSH TUNNEL (BASTION)
        # =========================================================
        frm_tunnel = ttk.LabelFrame(self.frame, text="SSH Tunnel (Bastion)")
        frm_tunnel.pack(fill="x", pady=5, padx=5)

        # Row 1: Bastion
        ttk.Label(frm_tunnel, text="Bastion Host").grid(
            row=0, column=0, sticky="e")
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_host).grid(
            row=0, column=1, sticky="ew")
        ttk.Label(frm_tunnel, text="User").grid(row=0, column=2, sticky="e")
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_user).grid(
            row=0, column=3, sticky="ew")
        ttk.Label(frm_tunnel, text="Port").grid(row=0, column=4, sticky="e")
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_bastion_port,
                  width=6).grid(row=0, column=5, sticky="w")

        # Row 2: Internal Target
        ttk.Label(frm_tunnel, text="Internal IP").grid(
            row=1, column=0, sticky="e")
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_internal_ip).grid(
            row=1, column=1, sticky="ew")
        ttk.Label(frm_tunnel, text="Int Port").grid(
            row=1, column=2, sticky="e")
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_internal_port,
                  width=6).grid(row=1, column=3, sticky="ew")
        ttk.Label(frm_tunnel, text="Local Port").grid(
            row=1, column=4, sticky="e")
        ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_local_port,
                  width=6).grid(row=1, column=5, sticky="w")

        # Row 3: Key and Actions
        ttk.Label(frm_tunnel, text="Key").grid(row=2, column=0, sticky="e")
        ent_key = ttk.Entry(frm_tunnel, textvariable=self.app.tunnel_key_path)
        ent_key.grid(row=2, column=1, columnspan=4, sticky="ew")
        ttk.Button(frm_tunnel, text="Browse", command=lambda: self._pick_file(
            self.app.tunnel_key_path)).grid(row=2, column=5)

        btn_frm = ttk.Frame(frm_tunnel)
        btn_frm.grid(row=3, column=0, columnspan=6, pady=5)
        ttk.Button(btn_frm, text="Create Tunnel",
                   command=self._create_tunnel_ui).pack(side="left", padx=5)
        ttk.Button(btn_frm, text="Close Tunnel",
                   command=self._close_tunnel_ui).pack(side="left", padx=5)
        ttk.Label(btn_frm, textvariable=self.app.tunnel_status).pack(
            side="left", padx=10)

        for i in range(6):
            frm_tunnel.columnconfigure(i, weight=1)

        # =========================================================
        # EXECUTION MODE
        # =========================================================
        frm_mode = ttk.LabelFrame(self.frame, text="Execution Mode")
        frm_mode.pack(fill="x", pady=5, padx=5)

        ttk.Radiobutton(frm_mode, text="Local", value="LOCAL",
                        variable=self.app.var_run_mode, command=self._toggle_ssh_frame).pack(side="left", padx=10)
        ttk.Radiobutton(frm_mode, text="Remote (SSH)", value="SSH",
                        variable=self.app.var_run_mode, command=self._toggle_ssh_frame).pack(side="left", padx=10)

        # =========================================================
        # SSH CONNECTION
        # =========================================================
        self.frm_ssh = ttk.LabelFrame(self.frame, text="SSH Connection")
        # (Packed conditionally by _toggle_ssh_frame)

        ttk.Label(self.frm_ssh, text="Host").grid(row=0, column=0, sticky="e")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_host).grid(
            row=0, column=1, sticky="ew")

        ttk.Label(self.frm_ssh, text="User").grid(row=0, column=2, sticky="e")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_user).grid(
            row=0, column=3, sticky="ew")

        ttk.Label(self.frm_ssh, text="Port").grid(row=0, column=4, sticky="e")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_port,
                  width=6).grid(row=0, column=5, sticky="w")

        ttk.Label(self.frm_ssh, text="Remote Dir").grid(
            row=1, column=0, sticky="e")
        ttk.Entry(self.frm_ssh, textvariable=self.app.ssh_remote_dir).grid(
            row=1, column=1, columnspan=5, sticky="ew")

        # Auth
        # Note: logic inverted in UI? Checkbox "Use Key" -> if True, use key.
        # Ensure state.py variable ssh_use_password logic matches.
        # Here I assume ssh_use_password=True means "Password", False means "Key".
        ttk.Checkbutton(self.frm_ssh, text="Use Key",
                        variable=self.app.ssh_use_password, onvalue=False, offvalue=True).grid(row=2, column=0, sticky="w")

        self.ent_ssh_key = ttk.Entry(
            self.frm_ssh, textvariable=self.app.ssh_key_path)
        self.ent_ssh_key.grid(row=2, column=1, columnspan=4, sticky="ew")
        ttk.Button(self.frm_ssh, text="Browse", command=lambda: self._pick_file(
            self.app.ssh_key_path)).grid(row=2, column=5)

        # Actions
        btn_box = ttk.Frame(self.frm_ssh)
        btn_box.grid(row=3, column=0, columnspan=6, pady=5)

        ttk.Button(btn_box, text="Connect", command=self._ssh_connect_ui).pack(
            side="left", padx=5)
        ttk.Button(btn_box, text="Disconnect",
                   command=self._ssh_disconnect_ui).pack(side="left", padx=5)
        ttk.Label(btn_box, textvariable=self.app.ssh_status).pack(
            side="left", padx=10)

        ttk.Label(btn_box, text="Branch:").pack(side="left", padx=(10, 2))
        self.cmb_git_branch = ttk.Combobox(btn_box, textvariable=self.app.var_git_branch,
                                           state="readonly", width=15)
        self.cmb_git_branch.pack(side="left")
        ttk.Button(btn_box, text="Checkout", command=self._on_force_checkout_clicked).pack(
            side="left", padx=2)
        ttk.Button(btn_box, text="HTOP", command=self._open_htop_window).pack(
            side="left", padx=10)

        for i in range(6):
            self.frm_ssh.columnconfigure(i, weight=1)

        # =========================================================
        # EXECUTION CONTROLS
        # =========================================================
        frm_exec = ttk.Frame(self.frame)
        frm_exec.pack(fill="x", pady=5, padx=5)

        ttk.Label(frm_exec, text="YAML Folder").pack(side="left")
        ttk.Entry(frm_exec, textvariable=self.app.run_folder).pack(
            side="left", fill="x", expand=True, padx=5)
        ttk.Button(frm_exec, text="Browse",
                   command=self._pick_folder).pack(side="left")
        ttk.Button(frm_exec, text="Refresh", command=self._scan_yaml_files).pack(
            side="left", padx=5)

        ttk.Label(frm_exec, text="Workers:").pack(side="left", padx=(15, 5))
        tk.Spinbox(frm_exec, from_=1, to=32, width=3,
                   textvariable=self.app.var_max_workers).pack(side="left")

        ttk.Button(frm_exec, text="Run Selected",
                   command=self._run_selected_ui).pack(side="right", padx=5)
        ttk.Button(frm_exec, text="Stop",
                   command=self._stop_selected_ui).pack(side="right")

        # =========================================================
        # TREEVIEW (JOBS)
        # =========================================================
        frm_tree = ttk.Frame(self.frame)
        frm_tree.pack(fill="both", expand=True, padx=5, pady=2)

        cols = ("yaml", "status", "snap", "pct", "eta")
        self.tree = ttk.Treeview(
            frm_tree, columns=cols, show="headings", height=8)

        self.tree.heading("yaml", text="YAML File")
        self.tree.heading("status", text="Status")
        self.tree.heading("snap", text="Snapshot")
        self.tree.heading("pct", text="%")
        self.tree.heading("eta", text="ETA")

        self.tree.column("yaml", width=300)
        self.tree.column("status", width=150)
        self.tree.column("snap", width=80, anchor="center")
        self.tree.column("pct", width=60, anchor="e")
        self.tree.column("eta", width=80, anchor="center")

        sb = ttk.Scrollbar(frm_tree, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # =========================================================
        # LOG WINDOW
        # =========================================================
        frm_log = ttk.LabelFrame(self.frame, text="Execution Log")
        frm_log.pack(fill="both", expand=True, padx=5, pady=5)

        self.txt_log = tk.Text(
            frm_log, height=12, state="disabled", font=("Consolas", 9))
        sb_log = ttk.Scrollbar(frm_log, orient="vertical",
                               command=self.txt_log.yview)
        self.txt_log.configure(yscroll=sb_log.set)

        self.txt_log.pack(side="left", fill="both", expand=True)
        sb_log.pack(side="right", fill="y")

    # ---------------- UI Logic (Thread-Safe Wrappers) ----------------

    def _append_log(self, message):
        """
        Thread-safe method to append text to the log widget.
        """
        if not self.txt_log.winfo_exists():
            return

        def _thread_safe_write():
            self.txt_log.configure(state="normal")
            # Ensure message ends with newline if not present
            msg = message if message.endswith('\n') else message + '\n'
            self.txt_log.insert("end", msg)
            self.txt_log.see("end")  # Auto-scroll to latest
            self.txt_log.configure(state="disabled")

        self.frame.after(0, _thread_safe_write)

    def _update_tree_row(self, data):
        """
        Thread-safe method to update a specific row in the TreeView.
        data: dict with keys {iid, status, snap, pct, eta}
        """
        if not self.tree.winfo_exists():
            return

        def _thread_safe_update():
            iid = data.get("iid")
            if not iid:
                return

            # If item doesn't exist (maybe refreshing), ignore
            if not self.tree.exists(iid):
                return

            # Update columns individually if present in data
            if "status" in data:
                self.tree.set(iid, "status", data["status"])
            if "snap" in data:
                self.tree.set(iid, "snap", data["snap"])
            if "pct" in data:
                self.tree.set(iid, "pct", data["pct"])
            if "eta" in data:
                self.tree.set(iid, "eta", data["eta"])

        self.frame.after(0, _thread_safe_update)

    def _toggle_ssh_frame(self, *_):
        if self.app.var_run_mode.get() == "SSH":
            self.frm_ssh.pack(fill="x", pady=5, padx=5,
                              after=self.frame.children.get("!labelframe"))
        else:
            self.frm_ssh.pack_forget()

    def _toggle_tunnel(self, *_):
        # Tunnel options visibility is often tied to SSH connection logic,
        # but here we just keep them available if needed.
        pass

    def _pick_file(self, tk_var):
        path = filedialog.askopenfilename(
            filetypes=[("Keys", "*.pem *.ppk *.key *.rsa"), ("All", "*.*")])
        if path:
            tk_var.set(path)

    def _pick_folder(self):
        path = filedialog.askdirectory(initialdir=self.app.run_folder.get())
        if path:
            self.app.run_folder.set(path)
            self._scan_yaml_files()

    # ---------------- Manager Interaction ----------------

    def _scan_yaml_files(self):
        self.tree.delete(*self.tree.get_children())
        mode = self.app.var_run_mode.get()

        self._append_log(f"Scanning files in mode: {mode}...")

        if mode == "LOCAL":
            folder = self.app.run_folder.get()
            if os.path.isdir(folder):
                files = [f for f in os.listdir(
                    folder) if f.lower().endswith((".yaml", ".yml"))]
                files.sort()
                for f in files:
                    full_path = os.path.join(folder, f)
                    self.tree.insert("", "end", iid=full_path,
                                     values=(f, "Ready", "0/--", "0", "--"))
            else:
                self._append_log(f"Error: Local folder not found: {folder}")

        elif mode == "SSH":
            if self.manager and self.manager.ssh_connected:
                try:
                    files = self.manager.list_remote_files(
                        self.app.ssh_remote_dir.get())
                    for f in files:
                        fname = os.path.basename(f)
                        self.tree.insert("", "end", iid=f, values=(
                            fname, "Ready", "0/--", "0", "--"))
                except Exception as e:
                    self._append_log(f"Error listing remote files: {e}")
            else:
                self._append_log("SSH Not connected. Cannot list files.")

    def _ssh_connect_ui(self):
        if not self.manager:
            return

        host = self.app.ssh_host.get()
        user = self.app.ssh_user.get()
        port = int(self.app.ssh_port.get())

        self._append_log(f"Connecting to {user}@{host}:{port}...")

        # Determine auth method
        # ssh_use_password: True=Password, False=Key (based on Checkbutton above)
        use_key = not self.app.ssh_use_password.get()
        pwd = None

        if not use_key:
            pwd = simpledialog.askstring(
                "SSH Password", f"Password for {user}:", show="*")
            if not pwd:
                self._append_log("Connection cancelled (no password).")
                return

        def _connect_thread():
            try:
                if use_key:
                    self.manager.connect_ssh_key(
                        host, user, port, self.app.ssh_key_path.get())
                else:
                    self.manager.connect_ssh_password(host, user, port, pwd)

                if self.manager.ssh_connected:
                    self.app.ssh_status.set("🟢 Connected")
                    self._append_log("SSH Connected Successfully.")

                    # Fetch git branches
                    branches = self.manager.get_git_branches()

                    def _update_combo():
                        self.cmb_git_branch['values'] = branches
                        if branches:
                            self.cmb_git_branch.current(0)
                    self.frame.after(0, _update_combo)

                    # Auto scan
                    self.frame.after(0, self._scan_yaml_files)
                else:
                    self.app.ssh_status.set("🔴 Failed")
            except Exception as e:
                self.app.ssh_status.set("🔴 Error")
                self._append_log(f"SSH Error: {e}")

        threading.Thread(target=_connect_thread, daemon=True).start()

    def _ssh_disconnect_ui(self):
        if self.manager:
            self.manager.disconnect_ssh()
        self.app.ssh_status.set("Disconnected")
        self._append_log("SSH Disconnected.")

    def _create_tunnel_ui(self):
        self._append_log("Starting SSH Tunnel...")
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
        self.manager.close_tunnel()
        self._append_log("SSH Tunnel Closed.")

    def _run_selected_ui(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Runner", "Select files to run.")
            return

        mode = self.app.var_run_mode.get()
        self._append_log(
            f"Starting {len(sel)} simulation(s) in {mode} mode...")

        # Convert tuple to list of strings
        files = list(sel)
        workers = int(self.app.var_max_workers.get())

        if mode == "SSH":
            # Files must be remote paths
            self.manager.run_remote_parallel(files, workers)
        else:
            self.manager.run_local_parallel(files, workers)

    def _stop_selected_ui(self):
        sel = self.tree.selection()
        if not sel:
            return
        self._append_log(f"Stopping {len(sel)} process(es)...")
        self.manager.stop_simulations(list(sel))

    def _on_force_checkout_clicked(self):
        branch = self.app.var_git_branch.get()
        if not branch:
            return
        if messagebox.askyesno("Git Checkout", f"Force checkout remote to '{branch}'?\nThis will discard changes."):
            self.manager.git_force_checkout(branch)

    def _open_htop_window(self):
        if not self.manager or not self.manager.ssh_connected:
            messagebox.showerror("Error", "SSH Not Connected")
            return

        win = tk.Toplevel(self.frame)
        win.title("Remote HTOP Snapshot")
        win.geometry("800x600")

        txt = tk.Text(win, bg="black", fg="#00FF00", font=("Consolas", 9))
        txt.pack(fill="both", expand=True)

        def _refresh():
            if not win.winfo_exists():
                return
            out = self.manager.exec_command_output("top -b -n 1")

            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", out)
            txt.configure(state="disabled")

            # Refresh every 3 seconds
            win.after(3000, _refresh)

        _refresh()
