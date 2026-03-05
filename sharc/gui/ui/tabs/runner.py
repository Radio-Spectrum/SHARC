import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from datetime import datetime


class RunnerTab:

    # =========================================================
    # Lifecycle
    # =========================================================
    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        self.manager = getattr(app, "runner_manager", None)

        # job registry (para "schedule view")
        # key = iid (path remoto ou local completo)
        self._jobs = {}

        # tee holders
        self._orig_log_callback = None
        self._orig_update_row_callback = None

        self._build_ui()
        self._install_manager_callbacks()

        # inicial
        self._toggle_mode_ui()
        self.frame.after(500, self._scan_yaml_files)

    # =========================================================
    # UI
    # =========================================================
    def _build_ui(self):
        # =========================================================
        # EXECUTION MODE
        # =========================================================
        self.frm_mode = ttk.LabelFrame(self.frame, text="Execution Mode")
        self.frm_mode.pack(fill="x", pady=5, padx=5)

        ttk.Radiobutton(
            self.frm_mode,
            text="Local",
            value="LOCAL",
            variable=self.app.var_run_mode,
            command=self._toggle_mode_ui,
        ).pack(side="left", padx=10)

        ttk.Radiobutton(
            self.frm_mode,
            text="Remote (SSH)",
            value="SSH",
            variable=self.app.var_run_mode,
            command=self._toggle_mode_ui,
        ).pack(side="left", padx=10)

        # =========================================================
        # REMOTE SCHEDULER HEADER (somente SSH)
        # =========================================================
        self.frm_remote = ttk.LabelFrame(
            self.frame, text="Remote Scheduler (SSH)")
        # pack controlado em _toggle_mode_ui

        row = ttk.Frame(self.frm_remote)
        row.pack(fill="x", padx=8, pady=(6, 6))

        # Status vindo do app (atualizado pelo ssh_config tab)
        ttk.Label(row, text="SSH:", font=(
            "Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(row, textvariable=self.app.ssh_status).pack(
            side="left", padx=(4, 14))

        if hasattr(self.app, "tunnel_status"):
            ttk.Label(row, text="Tunnel:", font=(
                "Segoe UI", 9, "bold")).pack(side="left")
            ttk.Label(row, textvariable=self.app.tunnel_status).pack(
                side="left", padx=(4, 14))

        # Host summary (se existir variáveis no app)
        self._lbl_host_summary = ttk.Label(row, text="")
        self._lbl_host_summary.pack(side="left", padx=(0, 14))

        # Branch controls (mantém, pois é parte do workflow remoto)
        ttk.Label(row, text="Branch:", font=(
            "Segoe UI", 9, "bold")).pack(side="left")
        self.cmb_git_branch = ttk.Combobox(
            row,
            textvariable=self.app.var_git_branch,
            state="readonly",
            width=18,
        )
        self.cmb_git_branch.pack(side="left", padx=(6, 6))

        ttk.Button(row, text="Checkout", command=self._on_force_checkout_clicked).pack(
            side="left", padx=(0, 8))
        ttk.Button(row, text="HTOP", command=self._open_htop_window).pack(
            side="left", padx=(0, 8))
        ttk.Button(row, text="Refresh branches",
                   command=self._refresh_branches).pack(side="left")

        # Remote directory (continua no Runner, pois é parte do scheduler/listagem)
        row2 = ttk.Frame(self.frm_remote)
        row2.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(row2, text="Remote YAML Dir:", font=(
            "Segoe UI", 9, "bold")).pack(side="left")
        ttk.Entry(row2, textvariable=self.app.ssh_remote_dir).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="List Remote YAMLs", command=self._scan_yaml_files).pack(
            side="left", padx=(0, 6))

        

        # =========================================================
        # PROTECTED REMOTE RUNS (tmux resume)
        # =========================================================
        self.frm_runs = ttk.LabelFrame(self.frm_remote, text="Protected Runs (tmux)")
        self.frm_runs.pack(fill="x", padx=8, pady=(0, 8))

        rr = ttk.Frame(self.frm_runs)
        rr.pack(fill="x", padx=6, pady=6)

        ttk.Button(rr, text="List Runs", command=self._list_remote_runs).pack(side="left", padx=(0, 8))

        ttk.Label(rr, text="Run:", font=("Segoe UI", 9, "bold")).pack(side="left")
        self._run_pick = tk.StringVar(value="")
        self.cmb_runs = ttk.Combobox(rr, textvariable=self._run_pick, state="readonly", width=38)
        self.cmb_runs.pack(side="left", padx=(6, 8), fill="x", expand=True)

        ttk.Button(rr, text="Resume", command=self._resume_selected_run).pack(side="left", padx=(0, 8))
        ttk.Button(rr, text="Open tmux attach hint", command=self._tmux_attach_hint).pack(side="left")

# =========================================================
        # EXECUTION CONTROLS (vale para os dois modos)
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
        # TREEVIEW (JOBS/SCHEDULE)
        # =========================================================
        frm_tree = ttk.Frame(self.frame)
        frm_tree.pack(fill="both", expand=True, padx=5, pady=2)

        # schedule columns (superset do local)
        cols = ("yaml", "status", "snap", "pct",
                "eta", "branch", "location", "host")
        self.tree = ttk.Treeview(
            frm_tree, columns=cols, show="headings", height=10)

        self.tree.heading("yaml", text="YAML File")
        self.tree.heading("status", text="Status")
        self.tree.heading("snap", text="Snapshot")
        self.tree.heading("pct", text="%")
        self.tree.heading("eta", text="ETA")
        self.tree.heading("branch", text="Branch")
        self.tree.heading("location", text="Location")
        self.tree.heading("host", text="Host")

        self.tree.column("yaml", width=320)
        self.tree.column("status", width=160)
        self.tree.column("snap", width=90, anchor="center")
        self.tree.column("pct", width=70, anchor="e")
        self.tree.column("eta", width=90, anchor="center")
        self.tree.column("branch", width=140)
        self.tree.column("location", width=260)
        self.tree.column("host", width=180)

        sb = ttk.Scrollbar(frm_tree, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Context menu básico
        self._menu = tk.Menu(self.frame, tearoff=False)
        self._menu.add_command(label="Open containing folder (local only)",
                               command=self._open_local_containing_folder)
        self._menu.add_command(
            label="Copy path", command=self._copy_selected_path)
        self.tree.bind("<Button-3>", self._on_tree_right_click, add="+")

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

    def _toggle_mode_ui(self, *_):
        mode = self.app.var_run_mode.get()

        # remote scheduler header
        if mode == "SSH":
            self.frm_remote.pack(fill="x", pady=5, padx=5, after=self.frm_mode)
            self._refresh_remote_summary()
            self._refresh_branches(auto=True)
        else:
            try:
                self.frm_remote.pack_forget()
            except Exception:
                pass

        # tree columns visibility hint (não dá pra esconder colunas fácil no ttk.Treeview)
        # mas podemos ajustar headers/widths para "simular"
        self._apply_tree_layout_for_mode(mode)

        self._append_log(f"[UI] Mode set to: {mode}")

    def _apply_tree_layout_for_mode(self, mode: str):
        # Local: deixa branch/location/host mais estreito para não poluir
        if mode == "LOCAL":
            self.tree.column("branch", width=90)
            self.tree.column("location", width=180)
            self.tree.column("host", width=0, stretch=False)
            self.tree.heading("host", text="")
        else:
            self.tree.column("branch", width=140)
            self.tree.column("location", width=260)
            self.tree.column("host", width=180, stretch=True)
            self.tree.heading("host", text="Host")

    # =========================================================
    # Manager callback wiring (TEE)
    # =========================================================
    def _install_manager_callbacks(self):
        if not self.manager:
            self._append_log("[WARN] runner_manager not found on app.")
            return

        # --- LOG TEE ---
        orig_log = getattr(self.manager, "log_callback", None)
        self._orig_log_callback = orig_log if callable(orig_log) else None

        def _log_tee(msg: str):
            # keep original
            try:
                if callable(self._orig_log_callback):
                    self._orig_log_callback(msg)
            except Exception:
                pass
            # mirror here
            self._append_log(msg)

        self.manager.log_callback = _log_tee

        # --- UPDATE ROW TEE ---
        orig_upd = getattr(self.manager, "update_row_callback", None)
        self._orig_update_row_callback = orig_upd if callable(
            orig_upd) else None

        def _upd_tee(data: dict):
            # keep original
            try:
                if callable(self._orig_update_row_callback):
                    self._orig_update_row_callback(data)
            except Exception:
                pass
            # update local UI
            self._update_tree_row(data)

        self.manager.update_row_callback = _upd_tee

        self._append_log(
            "[OK] Runner tab attached (tee) to runner_manager callbacks.")

    # =========================================================
    # Thread-safe UI writers
    # =========================================================
    def _append_log(self, message):
        if not hasattr(self, "txt_log") or not self.txt_log.winfo_exists():
            return

        def _write():
            try:
                self.txt_log.configure(state="normal")
                msg = str(message) if message is not None else ""
                if msg and not msg.endswith("\n"):
                    msg += "\n"
                self.txt_log.insert("end", msg)
                self.txt_log.see("end")
                self.txt_log.configure(state="disabled")
            except Exception:
                pass

        self.frame.after(0, _write)

    def _update_tree_row(self, data):
        """
        data: dict with keys {iid, status, snap, pct, eta, branch, location, host}
        manager pode mandar só parte disso.
        """
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return

        def _upd():
            try:
                iid = data.get("iid")
                if not iid:
                    return
                if not self.tree.exists(iid):
                    return

                # compat (colunas antigas)
                if "status" in data:
                    self.tree.set(iid, "status", data["status"])
                if "snap" in data:
                    self.tree.set(iid, "snap", data["snap"])
                if "pct" in data:
                    self.tree.set(iid, "pct", data["pct"])
                if "eta" in data:
                    self.tree.set(iid, "eta", data["eta"])

                # novas colunas do schedule
                if "branch" in data:
                    self.tree.set(iid, "branch", data["branch"])
                if "location" in data:
                    self.tree.set(iid, "location", data["location"])
                if "host" in data:
                    self.tree.set(iid, "host", data["host"])

                # registrar no schedule interno
                job = self._jobs.get(iid, {})
                job.update({k: v for k, v in data.items() if k != "iid"})
                self._jobs[iid] = job
            except Exception:
                pass

        self.frame.after(0, _upd)

    # =========================================================
    # Helpers: Remote summary / branches
    # =========================================================
    def _refresh_remote_summary(self):
        # tenta puxar host/user do app se existirem
        host = getattr(self.app, "ssh_host", None)
        user = getattr(self.app, "ssh_user", None)

        h = host.get().strip() if hasattr(host, "get") else ""
        u = user.get().strip() if hasattr(user, "get") else ""
        if u and h:
            self._lbl_host_summary.configure(text=f"{u}@{h}")
        elif h:
            self._lbl_host_summary.configure(text=h)
        else:
            self._lbl_host_summary.configure(text="")

    def _refresh_branches(self, auto: bool = False):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            if not auto:
                messagebox.showinfo(
                    "SSH", "Not connected. Connect via SSH tab first.")
            return

        def _thread():
            try:
                branches = self.manager.get_git_branches()
            except Exception as e:
                self._append_log(f"[SSH] Error getting branches: {e}")
                branches = []

            def _apply():
                try:
                    self.cmb_git_branch["values"] = branches
                    if branches and (not self.app.var_git_branch.get()):
                        self.cmb_git_branch.current(0)
                except Exception:
                    pass

            self.frame.after(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    # =========================================================
    # File picking / scan
    # =========================================================
    def _pick_folder(self):
        path = filedialog.askdirectory(initialdir=self.app.run_folder.get())
        if path:
            self.app.run_folder.set(path)
            self._scan_yaml_files()

    def _scan_yaml_files(self):
        # limpa tree mas mantém _jobs (schedule) — assim “histórico” pode ser reusado se quiser.
        try:
            self.tree.delete(*self.tree.get_children())
        except Exception:
            pass

        mode = self.app.var_run_mode.get()
        self._append_log(f"[SCAN] Scanning files in mode: {mode}...")

        if mode == "LOCAL":
            folder = self.app.run_folder.get()
            if os.path.isdir(folder):
                files = [f for f in os.listdir(
                    folder) if f.lower().endswith((".yaml", ".yml"))]
                files.sort()
                for f in files:
                    full_path = os.path.join(folder, f)
                    self._insert_job_row(
                        iid=full_path,
                        yaml_name=f,
                        status="Ready",
                        snap="0/--",
                        pct="0",
                        eta="--",
                        branch="(local)",
                        location=folder,
                        host="local",
                    )
            else:
                self._append_log(f"[ERR] Local folder not found: {folder}")

        elif mode == "SSH":
            if self.manager and getattr(self.manager, "ssh_connected", False):
                remote_dir = self.app.ssh_remote_dir.get().strip()
                try:
                    files = self.manager.list_remote_files(remote_dir)
                    for f in files:
                        fname = os.path.basename(f)
                        self._insert_job_row(
                            iid=f,
                            yaml_name=fname,
                            status="Ready",
                            snap="0/--",
                            pct="0",
                            eta="--",
                            branch=self.app.var_git_branch.get() or "",
                            location=remote_dir,
                            host=self._current_host_label(),
                        )
                except Exception as e:
                    self._append_log(f"[ERR] Error listing remote files: {e}")
            else:
                self._append_log(
                    "[SSH] Not connected. Connect via SSH tab first.")

    def _insert_job_row(
        self,
        iid: str,
        yaml_name: str,
        status: str,
        snap: str,
        pct: str,
        eta: str,
        branch: str,
        location: str,
        host: str,
    ):
        # registra no schedule interno
        self._jobs[iid] = {
            "yaml": yaml_name,
            "status": status,
            "snap": snap,
            "pct": pct,
            "eta": eta,
            "branch": branch,
            "location": location,
            "host": host,
            "seen_at": datetime.now().isoformat(timespec="seconds"),
        }

        try:
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(yaml_name, status, snap, pct,
                        eta, branch, location, host),
            )
        except Exception:
            # iid duplicado, tenta update
            try:
                if self.tree.exists(iid):
                    self.tree.item(iid, values=(
                        yaml_name, status, snap, pct, eta, branch, location, host))
            except Exception:
                pass

    def _current_host_label(self) -> str:
        host = getattr(self.app, "ssh_host", None)
        user = getattr(self.app, "ssh_user", None)
        h = host.get().strip() if hasattr(host, "get") else ""
        u = user.get().strip() if hasattr(user, "get") else ""
        if u and h:
            return f"{u}@{h}"
        return h or "remote"

    # =========================================================
    # Run/Stop
    # =========================================================
    def _run_selected_ui(self):
        if not self.manager:
            messagebox.showerror("Runner", "runner_manager not found.")
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Runner", "Select files to run.")
            return

        mode = self.app.var_run_mode.get()
        workers = int(self.app.var_max_workers.get())
        files = list(sel)

        self._append_log(
            f"[RUN] Starting {len(files)} simulation(s) in {mode} mode (workers={workers})...")

        # marca como queued no schedule
        for iid in files:
            try:
                self.tree.set(iid, "status", "Queued")
                self.tree.set(iid, "branch", self.app.var_git_branch.get(
                ) or self.tree.set(iid, "branch"))
                self.tree.set(iid, "host", self._current_host_label())
            except Exception:
                pass

        if mode == "SSH":
            # Files must be remote paths
            self.manager.run_remote_parallel(files, workers)
        else:
            self.manager.run_local_parallel(files, workers)

    def _stop_selected_ui(self):
        if not self.manager:
            return
        sel = self.tree.selection()
        if not sel:
            return
        self._append_log(f"[STOP] Stopping {len(sel)} process(es)...")
        self.manager.stop_simulations(list(sel))

        for iid in sel:
            try:
                self.tree.set(iid, "status", "Stopped")
            except Exception:
                pass

    # =========================================================
    # Remote-only actions

    def _list_remote_runs(self):
        """
        List persisted tmux-backed runs on remote and populate the combobox.
        """
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            messagebox.showinfo("SSH", "Not connected. Connect via SSH tab first.")
            return

        def _thread():
            try:
                runs = self.manager.list_remote_runs()
            except Exception as e:
                runs = []
                self._append_log(f"[REMOTE] list_remote_runs error: {e}")

            # Build display list and mapping
            items = []
            self._runs_map = {}  # display -> meta
            for r in runs:
                ru = r.get("run_uuid", "")
                rp = r.get("remote_path", "")
                alive = r.get("session_alive", False)
                short = ru[:8] if ru else "--------"
                name = os.path.basename(rp) if rp else "(unknown)"
                disp = f"{short} | {'alive' if alive else 'done '} | {name}"
                items.append(disp)
                self._runs_map[disp] = r

            def _apply():
                try:
                    self.cmb_runs["values"] = items
                    if items:
                        self.cmb_runs.current(0)
                    self._append_log(f"[REMOTE] Found {len(items)} persisted run(s).")
                except Exception:
                    pass

            self.frame.after(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    def _resume_selected_run(self):
        """
        Resume a selected tmux run by tailing its remote log and updating the job row.
        """
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            messagebox.showinfo("SSH", "Not connected. Connect via SSH tab first.")
            return

        disp = self._run_pick.get().strip()
        meta = getattr(self, "_runs_map", {}).get(disp) if disp else None
        if not meta:
            messagebox.showwarning("Resume", "Select a run first (List Runs).")
            return

        run_uuid = meta.get("run_uuid")
        remote_path = meta.get("remote_path", "")
        if not run_uuid:
            messagebox.showerror("Resume", "Invalid run metadata (missing run_uuid).")
            return

        # Ensure a row exists for this resumed run (use run_uuid as iid)
        iid = f"run:{run_uuid}"
        if not self.tree.exists(iid):
            yaml_name = os.path.basename(remote_path) if remote_path else f"run_{run_uuid[:8]}.yaml"
            self._insert_job_row(
                iid=iid,
                yaml_name=yaml_name,
                status="Resuming...",
                snap="0/--",
                pct="--",
                eta="--",
                branch=self.app.var_git_branch.get() or "",
                location="(remote persisted)",
                host=self._current_host_label(),
            )
        else:
            try:
                self.tree.set(iid, "status", "Resuming...")
            except Exception:
                pass

        self._append_log(f"[REMOTE] Resuming run_uuid={run_uuid} (iid={iid})...")

        def _thread():
            try:
                # tail + parse happens inside manager; it will call update_row_callback
                self.manager.resume_remote_run(run_uuid, tree_id=iid)
            except Exception as e:
                self._append_log(f"[REMOTE] resume error: {e}")

        threading.Thread(target=_thread, daemon=True).start()

    def _tmux_attach_hint(self):
        """
        Shows a manual tmux attach hint in log for the selected run.
        """
        disp = self._run_pick.get().strip()
        meta = getattr(self, "_runs_map", {}).get(disp) if disp else None
        if not meta:
            return
        run_uuid = meta.get("run_uuid")
        if not run_uuid:
            return
        # Session is sharc_<8> in ssh_runner
        sess = meta.get("session") or f"sharc_{run_uuid[:8]}"
        self._append_log(f"[TMUX] Manual attach on remote: tmux attach -t {sess}")

    # =========================================================
    def _on_force_checkout_clicked(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            messagebox.showerror(
                "Git Checkout", "SSH Not Connected (connect via SSH tab).")
            return

        branch = self.app.var_git_branch.get()
        if not branch:
            return

        if messagebox.askyesno(
            "Git Checkout",
            f"Force checkout remote to '{branch}'?\nThis will discard changes.",
        ):
            try:
                self.manager.git_force_checkout(branch)
                self._append_log(f"[GIT] Force checkout -> {branch}")
            except Exception as e:
                self._append_log(f"[GIT] Error: {e}")

    def _open_htop_window(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            messagebox.showerror(
                "Error", "SSH Not Connected (connect via SSH tab).")
            return

        win = tk.Toplevel(self.frame)
        win.title("Remote TOP Snapshot")
        win.geometry("900x600")

        txt = tk.Text(win, bg="black", fg="#00FF00", font=("Consolas", 9))
        txt.pack(fill="both", expand=True)

        def _refresh():
            if not win.winfo_exists():
                return
            try:
                out = self.manager.exec_command_output("top -b -n 1")
            except Exception as e:
                out = f"Error: {e}"

            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", out)
            txt.configure(state="disabled")

            win.after(3000, _refresh)

        _refresh()

    # =========================================================
    # Tree context menu
    # =========================================================
    def _on_tree_right_click(self, event):
        try:
            iid = self.tree.identify_row(event.y)
            if iid:
                self.tree.selection_set(iid)
                self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._menu.grab_release()
            except Exception:
                pass

    def _copy_selected_path(self):
        sel = self.tree.selection()
        if not sel:
            return
        path = sel[0]
        try:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(path)
            self._append_log(f"[CLIP] Copied: {path}")
        except Exception:
            pass

    def _open_local_containing_folder(self):
        sel = self.tree.selection()
        if not sel:
            return
        path = sel[0]
        if self.app.var_run_mode.get() != "LOCAL":
            messagebox.showinfo("Open folder", "Local-only action.")
            return
        try:
            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                os.startfile(folder)  # Windows
        except Exception as e:
            messagebox.showerror("Open folder", str(e))
