from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMessageBox
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
import os, shlex, threading

class RemoteBrowserMixin:
    """
    Mixin para Browse Remoto do SSH adaptado para PySide6.
    """
    def _remote_browse_refresh(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            return
            
        path = (self.var_remote_browse_dir.get() or "~").strip() or "~"

        def _thread():
            try:
                if hasattr(self.manager, "list_remote_dir"):
                    items = self.manager.list_remote_dir(path)
                else:
                    out = self.manager.exec_command_output(f"ls -A1p {self._sh_quote(path)}")
                    items = []
                    for line in (out or "").splitlines():
                        line = line.strip()
                        if not line: continue
                        is_dir = line.endswith("/")
                        name = line[:-1] if is_dir else line
                        fullp = path.rstrip("/") + "/" + name if path not in ("~", "") else name
                        items.append({"name": name, "is_dir": is_dir, "full_path": fullp, "size": "", "mtime": ""})
            except Exception as e:
                items = []
                self._append_log(f"[BROWSE] Error: {e}")

            def _apply():
                try:
                    self.tree_remote.clear()
                except Exception:
                    return

                items_sorted = sorted(items, key=lambda x: (not bool(x.get("is_dir")), (x.get("name") or "").lower()))
                for it in items_sorted:
                    name = it.get("name", "")
                    typ = "dir" if bool(it.get("is_dir")) else "file"
                    size = str(it.get("size", ""))
                    mtime = str(it.get("mtime", ""))
                    full_path = it.get("full_path") or (path.rstrip("/") + "/" + name)
                    
                    tw_item = QTreeWidgetItem([name, typ, size, mtime])
                    tw_item.setData(0, Qt.UserRole, full_path)
                    self.tree_remote.addTopLevelItem(tw_item)

            QTimer.singleShot(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    def _remote_browse_up(self):
        p = (self.var_remote_browse_dir.get() or "~").strip().rstrip("/")
        if p in ("", "~", "/"):
            self.var_remote_browse_dir.set("~")
        else:
            parent = os.path.dirname(p)
            self.var_remote_browse_dir.set(parent if parent else "~")
        self._remote_browse_refresh()

    def _remote_browse_on_double_click(self, item, column):
        if not item: return
        full_path = item.data(0, Qt.UserRole)
        typ = item.text(1)
        if typ == "dir":
            self.var_remote_browse_dir.set(full_path)
            self._remote_browse_refresh()
        else:
            self._remote_browse_preview(mode="head")

    def _remote_browse_right_click(self, pos):
        item = self.tree_remote.itemAt(pos)
        if item:
            self.tree_remote.setCurrentItem(item)
            self._remote_menu.exec_(self.tree_remote.mapToGlobal(pos))

    def _remote_browse_copy_path(self):
        items = self.tree_remote.selectedItems()
        if not items: return
        full_path = items[0].data(0, Qt.UserRole)
        if not full_path: return
        QGuiApplication.clipboard().setText(full_path)
        self._append_log(f"[CLIP] Copied remote: {full_path}")

    def _remote_browse_set_as_yaml_dir(self):
        p = (self.var_remote_browse_dir.get() or "~").strip() or "~"
        if hasattr(self.app, "ssh_remote_dir"):
            self.app.ssh_remote_dir.set(p)
            self._append_log(f"[BROWSE] Remote YAML Dir set to: {p}")

    def _remote_browse_set_as_project_dir(self):
        items = self.tree_remote.selectedItems()
        if not items: return
        full_path = items[0].data(0, Qt.UserRole)
        typ = items[0].text(1)
        base_dir = full_path if typ == "dir" else os.path.dirname(full_path)
        if hasattr(self, "var_remote_project_dir"):
            self.var_remote_project_dir.set(base_dir)
            self._apply_remote_paths()

    def _remote_browse_set_as_main_cli(self):
        items = self.tree_remote.selectedItems()
        if not items: return
        full_path = items[0].data(0, Qt.UserRole)
        typ = items[0].text(1)
        if typ == "dir": return
        
        base_dir = (self.var_remote_project_dir.get() or "").strip() if hasattr(self, "var_remote_project_dir") else ""
        rel = full_path
        if base_dir and full_path.startswith(base_dir.rstrip("/") + "/"):
            rel = full_path[len(base_dir.rstrip("/")) + 1:]
        if hasattr(self, "var_remote_main_cli"):
            self.var_remote_main_cli.set(rel)
            self._apply_remote_paths()

    def _remote_browse_preview(self, mode="head"):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            return
        items = self.tree_remote.selectedItems()
        if not items: return
        full_path = items[0].data(0, Qt.UserRole)
        typ = items[0].text(1)
        if typ == "dir": return

        cmd = f"head -n 80 {self._sh_quote(full_path)}" if mode == "head" else f"tail -n 120 {self._sh_quote(full_path)}"

        def _thread():
            try:
                out = self.manager.exec_command_output(cmd)
            except Exception as e:
                out = f"[PREVIEW] Error: {e}"

            def _apply():
                win = QDialog(self.frame) if hasattr(self, 'frame') else QDialog()
                win.setWindowTitle(f"Remote Preview ({mode}) - {os.path.basename(full_path)}")
                win.resize(980, 650)
                l = QVBoxLayout(win)
                txt = QTextEdit()
                txt.setStyleSheet("font-family: Consolas; font-size: 11px;")
                txt.setPlainText(out or "")
                txt.setReadOnly(True)
                l.addWidget(txt)
                win.setAttribute(Qt.WA_DeleteOnClose)
                win.show()
                # Store reference to prevent garbage collection
                if not hasattr(self, '_preview_windows'):
                    self._preview_windows = []
                self._preview_windows.append(win)

            QTimer.singleShot(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    def _sh_quote(self, s: str) -> str:
        return shlex.quote(s or "")