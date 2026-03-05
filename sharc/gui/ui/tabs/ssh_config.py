import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional ttkbootstrap support (keeps consistent with main.py)
try:
    import ttkbootstrap as tb
    HAS_BOOTSTRAP = True
except Exception:
    tb = None
    HAS_BOOTSTRAP = False


def _safe_read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _safe_write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class SSHTunnelTab(ttk.Frame):
    """
    SSH / Tunnel configuration tab.

    - Uses app.runner_manager as backend component (RunnerManager from ssh_runner.py).
    - Save/Load config via JSON chosen by the user.
    - Does NOT store password.
    - Shows a live log box by tee-ing RunnerManager.log_callback (thread-safe via after()).
    """

    def __init__(self, app, parent):
        super().__init__(parent)

        self.pack(fill="both", expand=True)

        self.app = app
        self.runner = getattr(app, "runner_manager", None)
        if self.runner is None:
            raise RuntimeError("SSHTunnelTab: app.runner_manager not found.")

        # Keep last opened/saved config file path
        self._config_file_path = tk.StringVar(value="")

        # --- log box state ---
        self._orig_log_callback = None
        self._log_autoscroll = tk.BooleanVar(value=True)

        # UI vars
        self.ssh_host = tk.StringVar(value="")
        self.ssh_port = tk.IntVar(value=22)
        self.ssh_user = tk.StringVar(value="")
        self.ssh_password = tk.StringVar(value="")  # not persisted
        self.ssh_key_path = tk.StringVar(value="")

        self.bastion_host = tk.StringVar(value="")
        self.bastion_user = tk.StringVar(value="")
        self.bastion_port = tk.IntVar(value=22)

        self.internal_ip = tk.StringVar(value="")
        self.internal_port = tk.IntVar(value=22)
        self.local_port = tk.IntVar(value=2222)

        self.tunnel_key_path = tk.StringVar(value="")

        self._build_ui()
        self._install_logger_tee()
        self._refresh_status_labels()

        # Restore callback if this widget is destroyed/reloaded
        self.bind("<Destroy>", self._on_destroy, add="+")

    # ==========================================================
    # UI
    # ==========================================================
    def _build_ui(self):
        Frame = tb.Frame if (HAS_BOOTSTRAP and tb is not None) else ttk.Frame
        LabelFrame = tb.Labelframe if (
            HAS_BOOTSTRAP and tb is not None) else ttk.LabelFrame
        Button = tb.Button if (
            HAS_BOOTSTRAP and tb is not None) else ttk.Button
        Label = tb.Label if (HAS_BOOTSTRAP and tb is not None) else ttk.Label
        Entry = tb.Entry if (HAS_BOOTSTRAP and tb is not None) else ttk.Entry
        Sep = tb.Separator if (
            HAS_BOOTSTRAP and tb is not None) else ttk.Separator
        Checkbutton = tb.Checkbutton if (
            HAS_BOOTSTRAP and tb is not None) else ttk.Checkbutton

        root = Frame(self)
        root.pack(fill="both", expand=True, padx=18, pady=18)

        # Header row
        top = Frame(root)
        top.pack(fill="x", pady=(0, 10))

        Label(top, text="SSH / Tunnel",
              font=("Segoe UI", 14, "bold")).pack(side="left")

        btns_top = Frame(top)
        btns_top.pack(side="right")

        Button(btns_top, text="Load Config (.json)",
               command=self._on_load_clicked).pack(side="left", padx=6)
        Button(btns_top, text="Save Config (.json)",
               command=self._on_save_clicked).pack(side="left", padx=6)

        Sep(root, orient="horizontal").pack(fill="x", pady=(0, 12))

        # Config path display
        path_row = Frame(root)
        path_row.pack(fill="x", pady=(0, 10))
        Label(path_row, text="Config file:", font=(
            "Segoe UI", 9, "bold")).pack(side="left")
        self.lbl_cfg_path = Label(
            path_row, textvariable=self._config_file_path, font=("Consolas", 9))
        self.lbl_cfg_path.pack(side="left", padx=(8, 0))

        # Status row
        status_row = Frame(root)
        status_row.pack(fill="x", pady=(0, 12))

        self.lbl_ssh = Label(status_row, text="SSH: --", font=("Consolas", 10))
        self.lbl_ssh.pack(side="left", padx=(0, 15))

        self.lbl_tun = Label(status_row, text="Tunnel: --",
                             font=("Consolas", 10))
        self.lbl_tun.pack(side="left")

        # SSH frame
        ssh_box = LabelFrame(
            root, text="SSH Connection (direct or via tunnel)")
        ssh_box.pack(fill="x", pady=10)

        r = 0
        Label(ssh_box, text="Host").grid(
            row=r, column=0, sticky="w", padx=(10, 4), pady=6)
        Entry(ssh_box, textvariable=self.ssh_host, width=28).grid(
            row=r, column=1, sticky="we", pady=6)

        Label(ssh_box, text="Port").grid(
            row=r, column=2, sticky="w", padx=(10, 4), pady=6)
        Entry(ssh_box, textvariable=self.ssh_port, width=8).grid(
            row=r, column=3, sticky="w", pady=6)

        r += 1
        Label(ssh_box, text="User").grid(
            row=r, column=0, sticky="w", padx=(10, 4), pady=6)
        Entry(ssh_box, textvariable=self.ssh_user, width=28).grid(
            row=r, column=1, sticky="we", pady=6)

        Label(ssh_box, text="Password").grid(
            row=r, column=2, sticky="w", padx=(10, 4), pady=6)
        Entry(ssh_box, textvariable=self.ssh_password, show="*",
              width=16).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        Label(ssh_box, text="SSH Key").grid(
            row=r, column=0, sticky="w", padx=(10, 4), pady=6)
        Entry(ssh_box, textvariable=self.ssh_key_path).grid(
            row=r, column=1, columnspan=2, sticky="we", pady=6)
        Button(ssh_box, text="Browse", command=self._pick_ssh_key).grid(
            row=r, column=3, sticky="w", pady=6)

        r += 1
        actions = Frame(ssh_box)
        actions.grid(row=r, column=0, columnspan=4,
                     sticky="w", padx=10, pady=(8, 10))

        Button(actions, text="Connect (Password)",
               command=self._connect_password).pack(side="left", padx=(0, 6))
        Button(actions, text="Connect (Key)", command=self._connect_key).pack(
            side="left", padx=(0, 6))
        Button(actions, text="Disconnect",
               command=self._disconnect).pack(side="left")

        ssh_box.grid_columnconfigure(1, weight=1)

        # Tunnel frame
        tun_box = LabelFrame(root, text="SSH Tunnel (Local Port Forward)")
        tun_box.pack(fill="x", pady=10)

        r = 0
        Label(tun_box, text="Bastion Host").grid(
            row=r, column=0, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.bastion_host, width=28).grid(
            row=r, column=1, sticky="we", pady=6)

        Label(tun_box, text="User").grid(
            row=r, column=2, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.bastion_user, width=20).grid(
            row=r, column=3, sticky="w", pady=6)

        Label(tun_box, text="Port").grid(
            row=r, column=4, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.bastion_port, width=8).grid(
            row=r, column=5, sticky="w", pady=6)

        r += 1
        Label(tun_box, text="Internal IP").grid(
            row=r, column=0, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.internal_ip, width=28).grid(
            row=r, column=1, sticky="we", pady=6)

        Label(tun_box, text="Internal Port").grid(
            row=r, column=2, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.internal_port, width=8).grid(
            row=r, column=3, sticky="w", pady=6)

        Label(tun_box, text="Local Port").grid(
            row=r, column=4, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.local_port, width=8).grid(
            row=r, column=5, sticky="w", pady=6)

        r += 1
        Label(tun_box, text="Tunnel SSH Key").grid(
            row=r, column=0, sticky="w", padx=(10, 4), pady=6)
        Entry(tun_box, textvariable=self.tunnel_key_path).grid(
            row=r, column=1, columnspan=4, sticky="we", pady=6)
        Button(tun_box, text="Browse", command=self._pick_tunnel_key).grid(
            row=r, column=5, sticky="w", pady=6)

        r += 1
        actions2 = Frame(tun_box)
        actions2.grid(row=r, column=0, columnspan=6,
                      sticky="w", padx=10, pady=(8, 10))

        Button(actions2, text="Open Tunnel", command=self._open_tunnel).pack(
            side="left", padx=(0, 6))
        Button(actions2, text="Close Tunnel",
               command=self._close_tunnel).pack(side="left")

        tun_box.grid_columnconfigure(1, weight=1)

        # ======================================================
        # LOG BOX
        # ======================================================
        log_box = LabelFrame(root, text="System Logs (ssh_runner)")
        log_box.pack(fill="both", expand=True, pady=(12, 0))

        log_controls = Frame(log_box)
        log_controls.pack(fill="x", padx=10, pady=(8, 6))

        Button(log_controls, text="Clear",
               command=self._clear_log_box).pack(side="left")
        Checkbutton(log_controls, text="Auto-scroll",
                    variable=self._log_autoscroll).pack(side="left", padx=10)

        text_frame = Frame(log_box)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._log_text = tk.Text(
            text_frame,
            height=12,
            wrap="word",
            state="disabled",
            font=("Consolas", 9)
        )
        self._log_text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(text_frame, orient="vertical",
                           command=self._log_text.yview)
        sb.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=sb.set)

    # ==========================================================
    # Logger tee (RunnerManager.log_callback)
    # ==========================================================
    def _install_logger_tee(self):
        if self._orig_log_callback is not None:
            return

        orig = getattr(self.runner, "log_callback", None)
        if not callable(orig):
            orig = getattr(self.app, "_safe_log", None)

        self._orig_log_callback = orig

        def _tee(msg: str):
            # 1) keep original behavior
            try:
                if callable(self._orig_log_callback):
                    self._orig_log_callback(msg)
            except Exception:
                pass

            # 2) mirror into this tab
            self._append_log_box(msg)

        self.runner.log_callback = _tee
        self._append_log_box("[LOG] SSH tab logger attached.\n")

    def _restore_logger(self):
        if self._orig_log_callback is not None:
            try:
                self.runner.log_callback = self._orig_log_callback
            except Exception:
                pass
            self._orig_log_callback = None

    def _on_destroy(self, event=None):
        try:
            if event is not None and event.widget is not self:
                return
        except Exception:
            pass
        self._restore_logger()

    def _append_log_box(self, msg: str):
        if not hasattr(self, "_log_text") or self._log_text is None:
            return
        if msg is None:
            return
        s = str(msg)
        if not s.endswith("\n"):
            s += "\n"

        def _ui_write():
            try:
                self._log_text.configure(state="normal")
                self._log_text.insert("end", s)
                if self._log_autoscroll.get():
                    self._log_text.see("end")
                self._log_text.configure(state="disabled")
            except Exception:
                pass

        try:
            self.after(0, _ui_write)
        except Exception:
            pass

    def _clear_log_box(self):
        if not hasattr(self, "_log_text") or self._log_text is None:
            return
        try:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.configure(state="disabled")
        except Exception:
            pass

    # ==========================================================
    # JSON Config (ask user where to save / which file to open)
    # ==========================================================
    def _collect_config_dict(self) -> dict:
        # NOTE: password intentionally excluded
        return {
            "ssh": {
                "host": self.ssh_host.get().strip(),
                "port": int(self.ssh_port.get()),
                "user": self.ssh_user.get().strip(),
                "key_path": self.ssh_key_path.get().strip(),
            },
            "tunnel": {
                "bastion_host": self.bastion_host.get().strip(),
                "bastion_user": self.bastion_user.get().strip(),
                "bastion_port": int(self.bastion_port.get()),
                "internal_ip": self.internal_ip.get().strip(),
                "internal_port": int(self.internal_port.get()),
                "local_port": int(self.local_port.get()),
                "key_path": self.tunnel_key_path.get().strip(),
            }
        }

    def _apply_config_dict(self, cfg: dict):
        ssh = cfg.get("ssh", {}) if isinstance(cfg, dict) else {}
        tun = cfg.get("tunnel", {}) if isinstance(cfg, dict) else {}

        self.ssh_host.set(ssh.get("host", ""))
        self.ssh_port.set(int(ssh.get("port", 22)))
        self.ssh_user.set(ssh.get("user", ""))
        self.ssh_key_path.set(ssh.get("key_path", ""))

        self.bastion_host.set(tun.get("bastion_host", ""))
        self.bastion_user.set(tun.get("bastion_user", ""))
        self.bastion_port.set(int(tun.get("bastion_port", 22)))
        self.internal_ip.set(tun.get("internal_ip", ""))
        self.internal_port.set(int(tun.get("internal_port", 22)))
        self.local_port.set(int(tun.get("local_port", 2222)))
        self.tunnel_key_path.set(tun.get("key_path", ""))

    def _on_save_clicked(self):
        initdir = None
        try:
            if self._config_file_path.get():
                initdir = str(self._config_file_path.get())
        except Exception:
            initdir = None

        path = filedialog.asksaveasfilename(
            title="Save SSH/Tunnel config",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="ssh_config.json"
        )
        if not path:
            return

        try:
            data = self._collect_config_dict()
            _safe_write_json(path, data)
            self._config_file_path.set(path)
            self._append_log_box(f"[CFG] Saved JSON config: {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _on_load_clicked(self):
        path = filedialog.askopenfilename(
            title="Load SSH/Tunnel config",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            cfg = _safe_read_json(path)
            self._apply_config_dict(cfg)
            self._config_file_path.set(path)
            self._append_log_box(f"[CFG] Loaded JSON config: {path}")
            self._refresh_status_labels()
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    # ==========================================================
    # Pickers
    # ==========================================================
    def _pick_ssh_key(self):
        p = filedialog.askopenfilename(title="Select SSH Private Key")
        if p:
            self.ssh_key_path.set(p)

    def _pick_tunnel_key(self):
        p = filedialog.askopenfilename(title="Select Tunnel SSH Private Key")
        if p:
            self.tunnel_key_path.set(p)

    # ==========================================================
    # Actions (use RunnerManager from ssh_runner.py)
    # ==========================================================
    def _connect_password(self):
        try:
            self.runner.connect_ssh_password(
                host=self.ssh_host.get().strip(),
                user=self.ssh_user.get().strip(),
                port=int(self.ssh_port.get()),
                password=self.ssh_password.get(),
            )
            self._refresh_status_labels()
        except Exception as e:
            messagebox.showerror("SSH Error", str(e))
            self._refresh_status_labels()

    def _connect_key(self):
        try:
            key_path = self.ssh_key_path.get().strip()
            if not key_path:
                messagebox.showwarning(
                    "Missing key", "Select an SSH key file first.")
                return

            self.runner.connect_ssh_key(
                host=self.ssh_host.get().strip(),
                user=self.ssh_user.get().strip(),
                port=int(self.ssh_port.get()),
                key_path=key_path,
            )
            self._refresh_status_labels()
        except Exception as e:
            messagebox.showerror("SSH Error", str(e))
            self._refresh_status_labels()

    def _disconnect(self):
        try:
            self.runner.disconnect_ssh()
        except Exception:
            pass
        self._refresh_status_labels()

    def _open_tunnel(self):
        try:
            key_path = self.tunnel_key_path.get().strip()
            if not key_path:
                messagebox.showwarning(
                    "Missing key", "Select a tunnel SSH key file first.")
                return

            self.runner.create_tunnel(
                bastion_host=self.bastion_host.get().strip(),
                bastion_user=self.bastion_user.get().strip(),
                bastion_port=int(self.bastion_port.get()),
                int_ip=self.internal_ip.get().strip(),
                int_port=int(self.internal_port.get()),
                loc_port=int(self.local_port.get()),
                key_path=key_path,
            )
            self._refresh_status_labels()
        except Exception as e:
            messagebox.showerror("Tunnel Error", str(e))
            self._refresh_status_labels()

    def _close_tunnel(self):
        try:
            self.runner.close_tunnel()
        except Exception:
            pass
        self._refresh_status_labels()

    # ==========================================================
    # Status integration
    # ==========================================================
    def _refresh_status_labels(self):
        ssh_ok = bool(getattr(self.runner, "ssh_connected", False))
        tun_ok = bool(getattr(self.runner, "tunnel_process", None))

        ssh_txt = "SSH: Connected" if ssh_ok else "SSH: Disconnected"
        tun_txt = "Tunnel: Active" if tun_ok else "Tunnel: Closed"

        try:
            self.lbl_ssh.configure(text=ssh_txt)
            self.lbl_tun.configure(text=tun_txt)
        except Exception:
            pass

        if hasattr(self.app, "ssh_status"):
            try:
                self.app.ssh_status.set(ssh_txt)
            except Exception:
                pass
        if hasattr(self.app, "tunnel_status"):
            try:
                self.app.tunnel_status.set(tun_txt)
            except Exception:
                pass
