from typing import Any
import tkinter as tk
from tkinter import messagebox
import os
import shlex
import threading

class RemoteBrowserMixin:
    # =========================================================
    # Remote File Browser helpers
    # =========================================================
    def _remote_browse_refresh(self):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            return

        path = (self.var_remote_browse_dir.get() or "~").strip() or "~"

        def _thread():
            try:
                if hasattr(self.manager, "list_remote_dir"):
                    items = self.manager.list_remote_dir(path)
                else:
                    out = self.manager.exec_command_output(
                        f"ls -A1p {self._sh_quote(path)}"
                    )
                    items = []
                    for line in (out or "").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        is_dir = line.endswith("/")
                        name = line[:-1] if is_dir else line
                        fullp = (
                            path.rstrip("/") + "/" + name
                            if path not in ("~", "")
                            else name
                        )
                        items.append(
                            {
                                "name": name,
                                "is_dir": is_dir,
                                "full_path": fullp,
                                "size": "",
                                "mtime": "",
                            }
                        )
            except Exception as e:
                items = []
                self._append_log(f"[BROWSE] Error: {e}")

            def _apply():
                try:
                    self.tree_remote.delete(*self.tree_remote.get_children())
                except Exception:
                    return

                items_sorted = sorted(
                    items,
                    key=lambda x: (
                        not bool(x.get("is_dir")),
                        (x.get("name") or "").lower(),
                    ),
                )
                for it in items_sorted:
                    name = it.get("name", "")
                    is_dir = bool(it.get("is_dir"))
                    typ = "dir" if is_dir else "file"
                    size = it.get("size", "")
                    mtime = it.get("mtime", "")
                    full_path = it.get("full_path") or (
                        path.rstrip("/") + "/" + name
                    )
                    iid = f"rb:{full_path}"
                    try:
                        self.tree_remote.insert(
                            "", "end", iid=iid, values=(name, typ, size, mtime)
                        )
                    except Exception:
                        self.tree_remote.insert(
                            "", "end", values=(name, typ, size, mtime)
                        )

            self.frame.after(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    def _remote_browse_up(self):
        p = (self.var_remote_browse_dir.get() or "~").strip().rstrip("/")
        if p in ("", "~", "/"):
            self.var_remote_browse_dir.set("~")
        else:
            parent = os.path.dirname(p)
            self.var_remote_browse_dir.set(parent if parent else "~")
        self._remote_browse_refresh()

    def _remote_browse_on_double_click(self, _event=None):
        sel = self.tree_remote.selection()
        if not sel:
            return
        iid = sel[0]
        full_path = iid[3:] if iid.startswith("rb:") else ""
        if not full_path:
            return
        try:
            typ = self.tree_remote.set(iid, "type")
        except Exception:
            typ = ""

        if typ == "dir":
            self.var_remote_browse_dir.set(full_path)
            self._remote_browse_refresh()
        else:
            self._remote_browse_preview(mode="head")

    def _remote_browse_right_click(self, event):
        try:
            iid = self.tree_remote.identify_row(event.y)
            if iid:
                self.tree_remote.selection_set(iid)
                self._remote_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._remote_menu.grab_release()
            except Exception:
                pass

    def _remote_browse_copy_path(self):
        sel = self.tree_remote.selection()
        if not sel:
            return
        iid = sel[0]
        full_path = iid[3:] if iid.startswith("rb:") else ""
        if not full_path:
            return
        try:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(full_path)
            self._append_log(f"[CLIP] Copied remote: {full_path}")
        except Exception:
            pass

    def _remote_browse_set_as_yaml_dir(self):
        p = (self.var_remote_browse_dir.get() or "~").strip() or "~"
        self.app.ssh_remote_dir.set(p)
        self._append_log(f"[BROWSE] Remote YAML Dir set to: {p}")

    def _remote_browse_set_as_project_dir(self):
        sel = self.tree_remote.selection()
        if not sel:
            return
        iid = sel[0]
        full_path = iid[3:] if iid.startswith("rb:") else ""
        if not full_path:
            return
        try:
            typ = self.tree_remote.set(iid, "type")
        except Exception:
            typ = ""
        base_dir = full_path if typ == "dir" else os.path.dirname(full_path)
        self.var_remote_project_dir.set(base_dir)
        self._apply_remote_paths()

    def _remote_browse_set_as_main_cli(self):
        sel = self.tree_remote.selection()
        if not sel:
            return
        iid = sel[0]
        full_path = iid[3:] if iid.startswith("rb:") else ""
        if not full_path:
            return
        try:
            typ = self.tree_remote.set(iid, "type")
        except Exception:
            typ = ""
        if typ == "dir":
            return

        base_dir = (self.var_remote_project_dir.get() or "").strip()
        rel = full_path
        if base_dir and full_path.startswith(base_dir.rstrip("/") + "/"):
            rel = full_path[len(base_dir.rstrip("/")) + 1:]
        self.var_remote_main_cli.set(rel)
        self._apply_remote_paths()

    def _remote_browse_preview(self, mode="head"):
        if not self.manager or not getattr(self.manager, "ssh_connected", False):
            return
        sel = self.tree_remote.selection()
        if not sel:
            return
        iid = sel[0]
        full_path = iid[3:] if iid.startswith("rb:") else ""
        if not full_path:
            return
        try:
            typ = self.tree_remote.set(iid, "type")
            if typ == "dir":
                return
        except Exception:
            pass

        cmd = (
            f"head -n 80 {self._sh_quote(full_path)}"
            if mode == "head"
            else f"tail -n 120 {self._sh_quote(full_path)}"
        )

        def _thread():
            try:
                out = self.manager.exec_command_output(cmd)
            except Exception as e:
                out = f"[PREVIEW] Error: {e}"

            def _apply():
                win = tk.Toplevel(self.frame)
                win.title(
                    f"Remote Preview ({mode}) - {os.path.basename(full_path)}")
                win.geometry("980x650")
                txt = tk.Text(win, font=("Consolas", 9))
                txt.pack(fill="both", expand=True)
                txt.insert("end", out or "")
                txt.configure(state="disabled")

            self.frame.after(0, _apply)

        threading.Thread(target=_thread, daemon=True).start()

    def _sh_quote(self, s: str) -> str:
        return shlex.quote(s or "")

