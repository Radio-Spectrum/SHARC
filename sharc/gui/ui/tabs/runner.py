import os
import threading
from datetime import datetime
import shlex

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QMessageBox, QFileDialog, QScrollArea, QFrame, QLabel, QGroupBox, QGridLayout, QProgressBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard, QGuiApplication

# ---------------------------------------------------------------------------
# Modular sub-modules (extracted for maintainability)
# ---------------------------------------------------------------------------
from ui.tabs.assets.runner_tab.runner_ui_builder import build_runner_ui
from ui.tabs.assets.runner_tab.runner_actions import (
    scan_yaml_files as _scan_yaml_files_impl,
    insert_job_row as _insert_job_row_impl,
    run_selected as _run_selected_impl,
    stop_selected as _stop_selected_impl,
)

from ui.components.remote_browser import RemoteBrowserMixin


class RunnerTab(QWidget, RemoteBrowserMixin):

    # =========================================================
    # Lifecycle
    # =========================================================
    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app
        self.host_frame = self
        
        # O runner_ui_builder.py espera tab.frame, vamos criar um QVBoxLayout no host_frame
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.manager = getattr(app, "runner_manager", None)

        # job registry (para "schedule view")
        # key = iid (path remoto ou local completo)
        self._jobs = {}

        # tee holders
        self._orig_log_callback = None
        self._orig_update_row_callback = None

        # schedule window state
        self._schedule_win = None
        self._schedule_layout = None

        self._build_ui()
        
        # Adicionar o frame construído pelo runner_ui_builder ao layout desta aba
        self.main_layout.addWidget(self.frame)
        
        self._install_manager_callbacks()

        # inicial
        self._toggle_mode_ui()
        QTimer.singleShot(500, self._scan_yaml_files)

    def _build_ui(self):
        build_runner_ui(self)

    def _toggle_mode_ui(self, *_):
        mode = "LOCAL" if self.rb_local.isChecked() else "SSH"

        # remote scheduler header and components
        if mode == "SSH":
            self.frm_remote.setVisible(True)
            if hasattr(self, "frm_remote_paths"): self.frm_remote_paths.setVisible(True)
            if hasattr(self, "frm_browser"): self.frm_browser.setVisible(True)
            if hasattr(self, "frm_runs"): self.frm_runs.setVisible(True)
            
            self._refresh_remote_summary()
            self._refresh_branches(auto=True)
            try:
                self._remote_browse_refresh()
            except Exception:
                pass
        else:
            self.frm_remote.setVisible(False)
            if hasattr(self, "frm_remote_paths"): self.frm_remote_paths.setVisible(False)
            if hasattr(self, "frm_browser"): self.frm_browser.setVisible(False)
            if hasattr(self, "frm_runs"): self.frm_runs.setVisible(False)

        self._apply_tree_layout_for_mode(mode)
        self._append_log(f"[UI] Mode set to: {mode}")

    def _apply_tree_layout_for_mode(self, mode: str):
        if mode == "LOCAL":
            self.tree.setColumnWidth(5, 90) # branch
            self.tree.setColumnWidth(6, 180) # location
            self.tree.setColumnHidden(7, True) # host
        else:
            self.tree.setColumnWidth(5, 140)
            self.tree.setColumnWidth(6, 260)
            self.tree.setColumnHidden(7, False)
            self.tree.setColumnWidth(7, 180)

    # =========================================================
    # Manager callback wiring (TEE)
    # =========================================================
    def _install_manager_callbacks(self):
        # In PySide6, callbacks from background threads must be routed through 
        # a thread-safe mechanism like queue/Signals. main.py already does this 
        # by initializing RunnerManager with `_safe_log` and `_safe_update_row`
        # which enqueue to `line_q`, and then calls the below UI methods safely.
        pass

    # =========================================================
    # Thread-safe UI writers
    # =========================================================
    def _append_log(self, message):
        if not hasattr(self, "txt_log"): return

        try:
            msg = str(message) if message is not None else ""
            if msg and not msg.endswith("\n"):
                msg += "\n"
            self.txt_log.appendPlainText(msg.strip())
        except Exception:
            pass

    def _update_tree_row(self, data):
        if not hasattr(self, "tree"): return

        try:
            iid = data.get("iid")
            if not iid: return
            
            existing_item = None
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                if item.data(0, Qt.UserRole) == iid:
                    existing_item = item
                    break
                    
            if not existing_item: return

            if "status" in data: existing_item.setText(1, data["status"])
            if "snap" in data: existing_item.setText(2, data["snap"])
            if "pct" in data: existing_item.setText(3, data["pct"])
            if "eta" in data: existing_item.setText(4, data["eta"])
            if "branch" in data: existing_item.setText(5, data["branch"])
            if "location" in data: existing_item.setText(6, data["location"])
            if "host" in data: existing_item.setText(7, data["host"])

            job = self._jobs.get(iid, {})
            job.update({k: v for k, v in data.items() if k != "iid"})
            self._jobs[iid] = job
            
            if getattr(self, '_schedule_win', None) and self._schedule_win.isVisible():
                self._render_schedule_cards()
        except Exception:
            pass

    # =========================================================
    # Helpers: Remote summary / branches
    # =========================================================
    def _refresh_remote_summary(self):
        host = getattr(self.app, "ssh_host", None)
        user = getattr(self.app, "ssh_user", None)

        h = host.text().strip() if hasattr(host, "text") else getattr(host, "get", lambda: "")().strip()
        u = user.text().strip() if hasattr(user, "text") else getattr(user, "get", lambda: "")().strip()
        if u and h:
            self._lbl_host_summary.setText(f"{u}@{h}")
        elif h:
            self._lbl_host_summary.setText(h)
        else:
            self._lbl_host_summary.setText("")

    def _refresh_branches(self, auto: bool = False):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            if not auto:
                QMessageBox.information(self, "SSH", "Not connected. Connect via SSH tab first.")
            return

        def _thread():
            try:
                if hasattr(self.manager, "get_git_branches"):
                    branches = self.manager.get_git_branches()
                else:
                    base = getattr(self.manager, "remote_base_dir", "").strip()
                    if hasattr(self.manager, "exec_command_output") and base:
                        out = self.manager.exec_command_output(f"cd {shlex.quote(base)} && git branch -a")
                        bset = set()
                        for line in out.splitlines():
                            line = line.strip().replace("*", "").strip()
                            if not line or "->" in line: continue
                            if line.startswith("remotes/origin/"):
                                line = line.replace("remotes/origin/", "")
                            bset.add(line)
                        branches = sorted(bset)
                    else:
                        branches = []
            except Exception as e:
                self._append_log(f"[SSH] Error getting branches: {e}")
                branches = []

            def _apply():
                try:
                    self.cmb_git_branch.clear()
                    self.cmb_git_branch.addItems(branches)
                    if branches:
                        self.cmb_git_branch.setCurrentIndex(0)
                except Exception:
                    pass

            QTimer.singleShot(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    # =========================================================
    # File picking / scan
    # =========================================================
    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select YAML Folder", self.e_run_folder.text())
        if path:
            self.e_run_folder.setText(path)
            self._scan_yaml_files()

    def _scan_yaml_files(self):
        _scan_yaml_files_impl(self)

    def _insert_job_row(self, iid: str, yaml_name: str, status: str, snap: str, pct: str, eta: str, branch: str, location: str, host: str):
        _insert_job_row_impl(self, iid, yaml_name, status, snap, pct, eta, branch, location, host)

    def _current_host_label(self) -> str:
        host = getattr(self.app, "ssh_host", None)
        user = getattr(self.app, "ssh_user", None)
        h = host.text().strip() if hasattr(host, "text") else getattr(host, "get", lambda: "")().strip()
        u = user.text().strip() if hasattr(user, "text") else getattr(user, "get", lambda: "")().strip()
        if u and h: return f"{u}@{h}"
        return h or "remote"

    # =========================================================
    # Run/Stop
    # =========================================================
    def _run_selected_ui(self):
        _run_selected_impl(self)

    def _stop_selected_ui(self):
        _stop_selected_impl(self)

    # =========================================================
    # Remote-only actions
    # =========================================================
    def _list_remote_runs(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.information(self, "SSH", "Not connected. Connect via SSH tab first.")
            return

        def _thread():
            try:
                runs = self.manager.list_remote_runs()
            except Exception as e:
                runs = []
                self._append_log(f"[REMOTE] list_remote_runs error: {e}")

            items = []
            self._runs_map = {}
            for r in runs:
                ru = r.get("run_uuid", "")
                rp = r.get("remote_path", "")
                alive = r.get("session_alive", False)
                state = r.get("state") or ('alive' if alive else 'done')
                short = ru[:8] if ru else "--------"
                name = os.path.basename(rp) if rp else "(unknown)"
                disp = f"{short} | {state:<8} | {name}"
                items.append(disp)
                self._runs_map[disp] = r

            def _apply():
                try:
                    self.cmb_runs.clear()
                    self.cmb_runs.addItems(items)
                    if items:
                        self.cmb_runs.setCurrentIndex(0)
                    self._append_log(f"[REMOTE] Found {len(items)} persisted run(s).")
                    if getattr(self, "_schedule_win", None) and self._schedule_win.isVisible():
                        self._render_schedule_cards()
                except Exception:
                    pass

            QTimer.singleShot(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    def _resume_selected_run(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.information(self, "SSH", "Not connected. Connect via SSH tab first.")
            return

        disp = self.cmb_runs.currentText().strip()
        meta = getattr(self, "_runs_map", {}).get(disp) if disp else None
        if not meta:
            QMessageBox.warning(self, "Resume", "Select a run first (List Runs).")
            return

        run_uuid = meta.get("run_uuid")
        remote_path = meta.get("remote_path", "")
        if not run_uuid:
            QMessageBox.critical(self, "Resume", "Invalid run metadata (missing run_uuid).")
            return

        iid = f"run:{run_uuid}"
        existing_item = None
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == iid:
                existing_item = item
                break
                
        if not existing_item:
            yaml_name = os.path.basename(remote_path) if remote_path else f"run_{run_uuid[:8]}.yaml"
            self._insert_job_row(
                iid=iid, yaml_name=yaml_name, status="Resuming...", snap="0/--", pct="--", eta="--",
                branch=self.cmb_git_branch.currentText() or "", location="(remote persisted)", host=self._current_host_label(),
            )
        else:
            existing_item.setText(1, "Resuming...")

        self._append_log(f"[REMOTE] Resuming run_uuid={run_uuid} (iid={iid})...")

        def _thread():
            try:
                self.manager.resume_remote_run(run_uuid, tree_id=iid)
            except Exception as e:
                self._append_log(f"[REMOTE] resume error: {e}")

        threading.Thread(target=_thread, daemon=True).start()

    def _tmux_attach_hint(self):
        disp = self.cmb_runs.currentText().strip()
        meta = getattr(self, "_runs_map", {}).get(disp) if disp else None
        if not meta: return
        run_uuid = meta.get("run_uuid")
        if not run_uuid: return
        sess = meta.get("session") or f"sharc_{run_uuid[:8]}"
        self._append_log(f"[TMUX] Manual attach on remote: tmux attach -t {sess}")

    def _on_force_checkout_clicked(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.critical(self, "Git Checkout", "SSH Not Connected (connect via SSH tab).")
            return

        branch = self.cmb_git_branch.currentText()
        if not branch: return

        if QMessageBox.question(self, "Git Checkout", f"Force checkout remote to '{branch}'?\nThis will discard changes.") == QMessageBox.Yes:
            try:
                self.manager.git_force_checkout(branch)
                self._append_log(f"[GIT] Force checkout -> {branch}")
            except Exception as e:
                self._append_log(f"[GIT] Error: {e}")

    # =========================================================
    # Monitor (top/htop snapshots)
    # =========================================================
    def _open_top_window(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.critical(self, "Error", "SSH Not Connected (connect via SSH tab).")
            return
        self._open_monitor_snapshot(cmd="top -b -n 1", title="Remote TOP Snapshot")

    def _open_htop_window(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.critical(self, "Error", "SSH Not Connected (connect via SSH tab).")
            return
        self._open_monitor_snapshot(cmd="(htop -b -n 1 2>/dev/null || top -b -n 1)", title="Remote HTOP Snapshot")

    def _open_monitor_snapshot(self, cmd: str, title: str):
        win = QDialog(self)
        win.setWindowTitle(title)
        win.resize(900, 600)
        
        layout = QVBoxLayout(win)
        txt = QTextEdit()
        txt.setStyleSheet("background-color: black; color: #00FF00; font-family: Consolas; font-size: 9pt;")
        txt.setReadOnly(True)
        layout.addWidget(txt)
        
        def _refresh():
            if not win.isVisible(): return
            try:
                out = self.manager.exec_command_output(cmd)
            except Exception as e:
                out = f"Error: {e}"
            txt.setPlainText(out or "")
            QTimer.singleShot(3000, _refresh)
            
        win.show()
        _refresh()

    # =========================================================
    # Remote Paths apply / autodetect
    # =========================================================
    def _apply_remote_paths(self):
        if not self.manager: return
        base_dir = self.e_remote_project_dir.text().strip()
        main_cli = self.e_remote_main_cli.text().strip()
        runs_dir = getattr(self.manager, "remote_runs_dir", None)
        try:
            if hasattr(self.manager, "set_remote_paths"):
                self.manager.set_remote_paths(
                    base_dir=base_dir or None, main_cli=main_cli or None, runs_dir=runs_dir
                )
            else:
                if base_dir: self.manager.remote_base_dir = base_dir
                if main_cli: self.manager.remote_main_cli_rel = main_cli

            self._append_log(f"[REMOTE] Paths updated: base='{getattr(self.manager, 'remote_base_dir', '')}', main_cli='{getattr(self.manager, 'remote_main_cli_rel', '')}'")
        except Exception as e:
            self._append_log(f"[REMOTE] Failed to apply paths: {e}")

    def _auto_detect_remote_paths(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.critical(self, "Error", "SSH Not Connected (connect via SSH tab).")
            return

        def _thread():
            try:
                info = self.manager.detect_remote_sharc_paths() if hasattr(self.manager, "detect_remote_sharc_paths") else {}
            except Exception as e:
                info = {"error": str(e)}

            def _apply():
                if "error" in info:
                    self._append_log(f"[REMOTE] Auto-detect error: {info['error']}")
                    return
                bd = info.get("remote_base_dir")
                mc = info.get("remote_main_cli_rel")
                if bd: self.e_remote_project_dir.setText(bd)
                if mc: self.e_remote_main_cli.setText(mc)
                self._apply_remote_paths()

            QTimer.singleShot(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    # =========================================================
    # Tree context menu
    # =========================================================
    def _on_tree_right_click(self, pos):
        item = self.tree.itemAt(pos)
        if item:
            self._menu.exec_(self.tree.mapToGlobal(pos))

    def _copy_selected_path(self):
        sel = self.tree.selectedItems()
        if not sel: return
        path = sel[0].data(0, Qt.UserRole)
        try:
            QGuiApplication.clipboard().setText(path)
            self._append_log(f"[CLIP] Copied: {path}")
        except Exception:
            pass

    def _open_local_containing_folder(self):
        sel = self.tree.selectedItems()
        if not sel: return
        path = sel[0].data(0, Qt.UserRole)
        if not self.rb_local.isChecked():
            QMessageBox.information(self, "Open folder", "Local-only action.")
            return
        try:
            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                os.startfile(folder)
        except Exception as e:
            QMessageBox.critical(self, "Open folder", str(e))

    def _upload_local_yaml_files(self):
        if not self.rb_ssh.isChecked():
            QMessageBox.information(self, "Upload YAMLs", "Switch to Remote (SSH) mode first.")
            return
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.information(self, "Upload YAMLs", "SSH not connected. Connect via SSH tab first.")
            return

        remote_dir = self.e_remote_dir.text().strip()
        if not remote_dir:
            QMessageBox.critical(self, "Upload YAMLs", "Remote YAML Dir is empty.")
            return

        paths, _ = QFileDialog.getOpenFileNames(self, "Select YAML files to upload", "", "YAML files (*.yaml *.yml);;All files (*.*)")
        if not paths: return

        def _thread():
            try:
                uploaded = self.manager.upload_yaml_files(list(paths), remote_dir, overwrite=True)
                self._append_log(f"[SFTP] Uploaded {len(uploaded)} file(s) to {remote_dir}")
                self._scan_yaml_files()
            except Exception as e:
                self._append_log(f"[SFTP] Upload failed: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Upload YAMLs", str(e)))

        threading.Thread(target=_thread, daemon=True).start()

    def _upload_yaml_folder(self):
        if not self.rb_ssh.isChecked():
            QMessageBox.information(self, "Upload YAML Folder", "Switch to Remote (SSH) mode first.")
            return
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.information(self, "Upload YAML Folder", "SSH not connected. Connect via SSH tab first.")
            return

        local_dir = self.e_run_folder.text().strip()
        if not local_dir or not os.path.isdir(local_dir):
            QMessageBox.critical(self, "Upload YAML Folder", "Local YAML Folder is invalid.")
            return

        remote_dir = self.e_remote_dir.text().strip()
        if not remote_dir:
            QMessageBox.critical(self, "Upload YAML Folder", "Remote YAML Dir is empty.")
            return

        local_paths = []
        try:
            for name in os.listdir(local_dir):
                low = name.lower()
                if low.endswith(".yaml") or low.endswith(".yml"):
                    local_paths.append(os.path.join(local_dir, name))
        except Exception as e:
            QMessageBox.critical(self, "Upload YAML Folder", str(e))
            return

        if not local_paths:
            QMessageBox.information(self, "Upload YAML Folder", "No .yaml/.yml files found in the selected folder.")
            return

        def _thread():
            try:
                uploaded = self.manager.upload_yaml_files(local_paths, remote_dir, overwrite=True)
                self._append_log(f"[SFTP] Uploaded {len(uploaded)} file(s) to {remote_dir}")
                self._scan_yaml_files()
            except Exception as e:
                self._append_log(f"[SFTP] Upload failed: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Upload YAML Folder", str(e)))

        threading.Thread(target=_thread, daemon=True).start()

    def _clear_tmux_sessions(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            QMessageBox.information(self, "SSH", "Not connected. Connect via SSH tab first.")
            return

        def _thread():
            try:
                if hasattr(self.manager, "clear_sharc_tmux_sessions"):
                    self.manager.clear_sharc_tmux_sessions(remove_persisted_orphans=True)
                else:
                    self._append_log("[TMUX] clear_sharc_tmux_sessions() not available in RunnerManager.")
                try:
                    self._list_remote_runs()
                except Exception:
                    pass
            except Exception as e:
                self._append_log(f"[TMUX] Clear error: {e}")

        threading.Thread(target=_thread, daemon=True).start()

    def _open_schedule_window(self):
        if getattr(self, "_schedule_win", None) and self._schedule_win.isVisible():
            self._schedule_win.activateWindow()
            self._schedule_win.raise_()
            self._render_schedule_cards()
            return

        self._schedule_win = QDialog(self)
        self._schedule_win.setWindowTitle("Simulation Schedule")
        self._schedule_win.resize(980, 680)

        main_layout = QVBoxLayout(self._schedule_win)
        
        top = QHBoxLayout()
        lbl = QLabel("Simulation Schedule")
        lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 12pt; font-weight: bold;")
        top.addWidget(lbl)
        top.addStretch()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_schedule_window)
        top.addWidget(btn_refresh)
        
        main_layout.addLayout(top)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        self._schedule_layout = QGridLayout(content)
        scroll_area.setWidget(content)
        
        main_layout.addWidget(scroll_area)
        
        self._render_schedule_cards()
        self._schedule_win.show()

    def _refresh_schedule_window(self):
        try:
            self._list_remote_runs()
        except Exception:
            pass
        self._render_schedule_cards()

    def _render_schedule_cards(self):
        layout = getattr(self, "_schedule_layout", None)
        if not layout: return

        # Clear layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        jobs = []
        for iid, meta in (self._jobs or {}).items():
            item = dict(meta)
            item["iid"] = iid
            jobs.append(item)

        runs_map = getattr(self, "_runs_map", {}) or {}
        for disp, r in runs_map.items():
            iid = f"run:{r.get('run_uuid','')}"
            if any(j.get("iid") == iid for j in jobs):
                continue
            final_status = r.get("final_status") or ("Running" if r.get("session_alive") else "Done")
            state = r.get("state") or "unknown"
            jobs.append({
                "iid": iid,
                "yaml": os.path.basename(r.get("remote_path", "")) or disp,
                "status": final_status if state != "running" else "Running",
                "snap": r.get("snap") or "0/--",
                "pct": r.get("pct") or ("100.0%" if final_status == "Completed" else ("0.0%" if r.get("session_alive") else "--")),
                "eta": r.get("eta") or ("--" if state != "running" else "Calc..."),
                "branch": self.cmb_git_branch.currentText() or "",
                "location": r.get("remote_path", ""),
                "host": self._current_host_label(),
            })

        if not jobs:
            layout.addWidget(QLabel("No simulations found."), 0, 0)
            return

        def pct_value(v):
            try:
                if isinstance(v, str): v = v.strip().replace('%','')
                return max(0.0, min(100.0, float(v)))
            except Exception:
                return 0.0

        cols = 3
        for index, job in enumerate(jobs):
            card = QGroupBox(job.get("yaml") or "Simulation")
            card_layout = QHBoxLayout(card)
            
            p = pct_value(job.get("pct", 0))
            prog = QProgressBar()
            prog.setValue(int(p))
            prog.setFormat(f"{p:.1f}%")
            prog.setFixedSize(120, 20)
            card_layout.addWidget(prog)
            
            info_layout = QVBoxLayout()
            info_layout.addWidget(QLabel(f"<b>Status:</b> {job.get('status','--')}"))
            info_layout.addWidget(QLabel(f"Snapshots: {job.get('snap','--')}"))
            info_layout.addWidget(QLabel(f"ETA: {job.get('eta','--')}"))
            info_layout.addWidget(QLabel(f"Host: {job.get('host','--')}"))
            
            lbl_loc = QLabel(f"Location: {job.get('location','--')}")
            lbl_loc.setWordWrap(True)
            info_layout.addWidget(lbl_loc)
            
            card_layout.addLayout(info_layout)
            
            r = index // cols
            c = index % cols
            layout.addWidget(card, r, c)
