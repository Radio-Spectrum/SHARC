# Auto-split from original sharc_gui.py
from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import RESULT_FIELDNAME_TO_PLOT_INFO  # noqa

import os
import glob
import time
import threading
from pathlib import Path
import numpy as np
import pandas as pd


class ResultsTabTabMixin:
    """
    Results tab with:
      - Local or Remote (SSH/SFTP) folders
      - Multi-folder comparison with per-folder styling (label/color/linestyle/linewidth)
      - Per-subplot config (field, CDF/CCDF, Y linear/log, X log, protection criteria, X-axis shift presets)
      - Remote folder picker via SFTP
      - Aggressive caching to keep plotting fast
    """

    # --------------------------
    # UI
    # --------------------------
    def _tab_results(self, root):
        app = self  # freeze correct self for callbacks

        # ============ state ============
        if not hasattr(app, "res_dirs"):
            app.res_dirs = []  # list[str] full tags (local path or ssh://path)
        if not hasattr(app, "_dir_style"):
            # full_dir_tag -> dict(label,color,linestyle,linewidth)
            app._dir_style = {}
        if not hasattr(app, "_axes_cfg"):
            app._max_axes = getattr(app, "_max_axes", 9)
            app._axes_cfg = []
            for _ in range(app._max_axes):
                app._axes_cfg.append({
                    "field": (getattr(app, "result_fields", ["INR"])[0] if hasattr(app, "result_fields") else "INR"),
                    "mode": "CDF",
                    "yscale": "Linear",
                    "criteria": [],  # list of dicts: {x,p,label,color,ls,lw}
                    "x_shift": 0.0,  # numeric shift applied to x
                    "x_label_override": "",  # optional x label
                    "legend_suffix": "",  # appended to legend entries
                })
        if not hasattr(app, "var_rows"):
            app.var_rows = tk.IntVar(value=1)
        if not hasattr(app, "var_cols"):
            app.var_cols = tk.IntVar(value=1)
        if not hasattr(app, "var_auto_update"):
            app.var_auto_update = tk.BooleanVar(value=False)
        if not hasattr(app, "var_update_period_ms"):
            app.var_update_period_ms = tk.IntVar(value=1500)
        if not hasattr(app, "var_xlog"):
            app.var_xlog = tk.BooleanVar(value=False)

        # source selection
        if not hasattr(app, "var_results_src"):
            app.var_results_src = tk.StringVar(value="LOCAL")  # LOCAL | REMOTE
        if not hasattr(app, "var_remote_results_dir"):
            app.var_remote_results_dir = tk.StringVar(value="")

        # caches (fast)
        if not hasattr(app, "_series_cache"):
            # (folder_tag, field) -> (mtime_key, np.ndarray)
            app._series_cache = {}
        if not hasattr(app, "_remote_cache_dir"):
            app._remote_cache_dir = ""
        if not hasattr(app, "_remote_ls_cache"):
            # remote_dir -> (t, [names])
            app._remote_ls_cache = {}
        if not hasattr(app, "_plot_auto_job"):
            app._plot_auto_job = None

        # ============ layout frames ============
        left = ttk.Frame(root)
        right = ttk.Frame(root)
        left.pack(side="left", fill="y")
        right.pack(side="right", fill="both", expand=True)

        # ============ Source frame ============
        frm_src = ttk.LabelFrame(left, text="Fonte dos resultados")
        frm_src.pack(fill="x", pady=(6, 4))
        ttk.Radiobutton(frm_src, text="Local", value="LOCAL", variable=app.var_results_src,
                        command=lambda: _refresh_src_ui()).pack(side="left", padx=(6, 8))
        ttk.Radiobutton(frm_src, text="Remota (SSH)", value="REMOTE", variable=app.var_results_src,
                        command=lambda: _refresh_src_ui()).pack(side="left")

        frm_src_local = ttk.Frame(left)
        frm_src_remote = ttk.Frame(left)

        # remote controls
        ttk.Label(frm_src_remote, text="Pasta remota (servidor):").pack(anchor="w")
        ent_remote_dir = ttk.Entry(frm_src_remote, textvariable=app.var_remote_results_dir)
        ent_remote_dir.pack(fill="x", pady=(0, 4))

        # ============ Folder list ============
        ttk.Label(left, text="Pastas de resultados (comparação):").pack(anchor="w", pady=(6, 2))
        frm_dirs = ttk.Frame(left)
        frm_dirs.pack(fill="x")

        # show short names, store full tags in listbox values (via mapping)
        app._lb_display_to_tag = {}
        app._lb_tag_to_display = {}

        app.lb_dirs = tk.Listbox(frm_dirs, height=7, selectmode="extended", exportselection=False)
        app.lb_dirs.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frm_dirs, orient="vertical", command=app.lb_dirs.yview)
        sb.pack(side="right", fill="y")
        app.lb_dirs.config(yscrollcommand=sb.set)

        def _display_name_for_tag(tag: str) -> str:
            # tag: local path or ssh://...
            raw = tag
            if raw.startswith("ssh://"):
                raw = raw[6:]
            base = os.path.basename(raw.rstrip("/")) or raw.rstrip("/")
            disp = base
            # disambiguate if needed
            if disp in app._lb_display_to_tag and app._lb_display_to_tag[disp] != tag:
                parent = os.path.basename(os.path.dirname(raw.rstrip("/")))
                disp = f"{base} [{parent}]"
            # final fallback: add counter
            if disp in app._lb_display_to_tag and app._lb_display_to_tag[disp] != tag:
                k = 2
                while f"{disp} ({k})" in app._lb_display_to_tag:
                    k += 1
                disp = f"{disp} ({k})"
            return disp

        def _lb_insert_tag(tag: str):
            disp = _display_name_for_tag(tag)
            app._lb_display_to_tag[disp] = tag
            app._lb_tag_to_display[tag] = disp
            app.lb_dirs.insert("end", disp)

        def _lb_remove_display(disp: str):
            tag = app._lb_display_to_tag.get(disp)
            if tag:
                app._lb_display_to_tag.pop(disp, None)
                app._lb_tag_to_display.pop(tag, None)

        def _lb_selected_tags() -> list[str]:
            tags = []
            for idx in app.lb_dirs.curselection():
                disp = app.lb_dirs.get(idx)
                tag = app._lb_display_to_tag.get(disp, disp)
                tags.append(tag)
            return tags


        def _lb_rebuild_from_res_dirs(select_tags: list[str] | None = None):
            """Rebuild listbox display from app.res_dirs, keeping tag<->display maps consistent."""
            if select_tags is None:
                select_tags = []
            # clear
            app.lb_dirs.delete(0, "end")
            app._lb_display_to_tag.clear()
            app._lb_tag_to_display.clear()
            for tag in app.res_dirs:
                _lb_insert_tag(tag)

            # restore selection by tags
            if select_tags:
                for i, tag in enumerate(app.res_dirs):
                    if tag in select_tags:
                        app.lb_dirs.selection_set(i)

        def _move_selected_dirs(delta: int):
            """Move selected folders up/down in app.res_dirs and listbox. delta=-1 up, +1 down."""
            sel_idx = list(app.lb_dirs.curselection())
            if not sel_idx:
                return
            n = len(app.res_dirs)
            if n <= 1:
                return

            sel_set = set(sel_idx)
            if delta < 0:
                # move up: iterate ascending
                for i in sel_idx:
                    if i <= 0:
                        continue
                    if (i - 1) in sel_set:
                        continue
                    app.res_dirs[i - 1], app.res_dirs[i] = app.res_dirs[i], app.res_dirs[i - 1]
                    sel_set.remove(i)
                    sel_set.add(i - 1)
                new_sel_idx = sorted(sel_set)
            else:
                # move down: iterate descending
                for i in sorted(sel_idx, reverse=True):
                    if i >= n - 1:
                        continue
                    if (i + 1) in sel_set:
                        continue
                    app.res_dirs[i + 1], app.res_dirs[i] = app.res_dirs[i], app.res_dirs[i + 1]
                    sel_set.remove(i)
                    sel_set.add(i + 1)
                new_sel_idx = sorted(sel_set)

            # rebuild listbox preserving selection tags order
            select_tags = [app.res_dirs[i] for i in new_sel_idx if 0 <= i < len(app.res_dirs)]
            _lb_rebuild_from_res_dirs(select_tags=select_tags)
            app._draw_results_plots()


        def _add_dir():
            # Remote: open remote picker
            if app.var_results_src.get() == "REMOTE":
                chosen = app._remote_dir_picker(initial=app.var_remote_results_dir.get().strip())
                if not chosen:
                    return
                app.var_remote_results_dir.set(chosen)
                tag = f"ssh://{chosen}"
                if tag not in app.res_dirs:
                    app.res_dirs.append(tag)
                    _lb_insert_tag(tag)
                app._draw_results_plots()
                return

            init = str(Path(app.var_outdir.get() or Path.cwd()))
            paths = app._local_dir_picker_multi(initial=init)
            if not paths:
                return
            for path in paths:
                if path and path not in app.res_dirs:
                    app.res_dirs.append(path)
                    _lb_insert_tag(path)
            app._draw_results_plots()

        def _add_current_outdir():
            od = str(Path(app.var_outdir.get()))
            if od and od not in app.res_dirs:
                app.res_dirs.append(od)
                _lb_insert_tag(od)
            app._draw_results_plots()

        def _remove_dir():
            sel = list(app.lb_dirs.curselection())[::-1]
            for idx in sel:
                disp = app.lb_dirs.get(idx)
                tag = app._lb_display_to_tag.get(disp, disp)
                if tag in app.res_dirs:
                    app.res_dirs.remove(tag)
                app.lb_dirs.delete(idx)
                _lb_remove_display(disp)
                app._dir_style.pop(tag, None)
            app._draw_results_plots()

        frm_btn = ttk.Frame(left)
        frm_btn.pack(fill="x", pady=(4, 6))
        ttk.Button(frm_btn, text="Adicionar pasta…", command=_add_dir).pack(side="left", padx=(0, 4))
        ttk.Button(frm_btn, text="Usar output_dir atual", command=_add_current_outdir).pack(side="left", padx=(0, 4))
        ttk.Button(frm_btn, text="Remover selecionadas", command=_remove_dir).pack(side="left")
        ttk.Button(frm_btn, text="↑", width=3, command=lambda: _move_selected_dirs(-1)).pack(side="right", padx=(4, 0))
        ttk.Button(frm_btn, text="↓", width=3, command=lambda: _move_selected_dirs(+1)).pack(side="right")

        # Plot filter: optionally plot only selected folders
        if not hasattr(app, "var_plot_selected_only"):
            app.var_plot_selected_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left,
            text="Plotar somente selecionadas",
            variable=app.var_plot_selected_only,
            command=app._draw_results_plots,
        ).pack(anchor="w", pady=(0, 6))


        # Populate listbox from res_dirs
        for tag in list(app.res_dirs):
            if tag not in app._lb_tag_to_display:
                _lb_insert_tag(tag)

        # ============ Per-folder style editor ============
        frm_style = ttk.LabelFrame(left, text="Estilo por pasta (aplica às selecionadas)")
        frm_style.pack(fill="x", pady=(6, 6))

        ttk.Label(frm_style, text="Legenda:").grid(row=0, column=0, padx=4, pady=3, sticky="w")
        app.var_style_label = getattr(app, "var_style_label", tk.StringVar(value=""))
        ent_style_label = ttk.Entry(frm_style, textvariable=app.var_style_label, width=22)
        ent_style_label.grid(row=0, column=1, padx=4, pady=3, sticky="we")

        ttk.Label(frm_style, text="Cor:").grid(row=1, column=0, padx=4, pady=3, sticky="w")
        app.var_style_color = getattr(app, "var_style_color", tk.StringVar(value="Auto"))
        cb_color = ttk.Combobox(frm_style, textvariable=app.var_style_color, values=[
            "Auto", "tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink",
            "tab:gray", "tab:olive", "tab:cyan", "black"
        ], width=18, state="readonly")
        cb_color.grid(row=1, column=1, padx=4, pady=3, sticky="w")

        ttk.Label(frm_style, text="Linha:").grid(row=2, column=0, padx=4, pady=3, sticky="w")
        app.var_style_ls = getattr(app, "var_style_ls", tk.StringVar(value="Auto"))
        cb_ls = ttk.Combobox(frm_style, textvariable=app.var_style_ls, values=["Auto", "-", "--", "-.", ":"],
                             width=8, state="readonly")
        cb_ls.grid(row=2, column=1, padx=4, pady=3, sticky="w")

        ttk.Label(frm_style, text="Espessura:").grid(row=3, column=0, padx=4, pady=3, sticky="w")
        app.var_style_lw = getattr(app, "var_style_lw", tk.DoubleVar(value=1.6))
        sp_lw = ttk.Spinbox(frm_style, from_=0.5, to=6.0, increment=0.1, textvariable=app.var_style_lw, width=8)
        sp_lw.grid(row=3, column=1, padx=4, pady=3, sticky="w")

        frm_style.grid_columnconfigure(1, weight=1)

        def _load_style_from_selection(*_):
            tags = _lb_selected_tags()
            if not tags:
                return
            # if one selected, load its style into fields
            if len(tags) == 1:
                st = app._dir_style.get(tags[0], {})
                app.var_style_label.set(st.get("label", ""))
                app.var_style_color.set(st.get("color", "Auto"))
                app.var_style_ls.set(st.get("ls", "Auto"))
                app.var_style_lw.set(float(st.get("lw", 1.6)))
            else:
                # multiple: keep current entries (do not overwrite)
                pass

        def _apply_style():
            tags = _lb_selected_tags()
            if not tags:
                messagebox.showwarning("Estilo", "Selecione uma ou mais pastas na lista.")
                return
            for tag in tags:
                st = app._dir_style.get(tag, {})
                st["label"] = app.var_style_label.get()
                st["color"] = app.var_style_color.get()
                st["ls"] = app.var_style_ls.get()
                try:
                    st["lw"] = float(app.var_style_lw.get())
                except Exception:
                    st["lw"] = 1.6
                app._dir_style[tag] = st
            app._draw_results_plots()

        ttk.Button(frm_style, text="Aplicar estilo", command=_apply_style).grid(row=4, column=0, columnspan=2,
                                                                               padx=4, pady=(4, 4), sticky="we")

        app.lb_dirs.bind("<<ListboxSelect>>", _load_style_from_selection)

        # ============ Layout ============
        frm_grid = ttk.LabelFrame(left, text="Layout de subfiguras")
        frm_grid.pack(fill="x", pady=(6, 6))
        ttk.Label(frm_grid, text="Linhas").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=6, textvariable=app.var_rows, width=5,
                    command=lambda: app._on_results_grid_change()).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frm_grid, text="Colunas").grid(row=0, column=2, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=6, textvariable=app.var_cols, width=5,
                    command=lambda: app._on_results_grid_change()).grid(row=0, column=3, padx=4, pady=4)

        # ============ Per subplot cfg ============
        frm_cfg = ttk.LabelFrame(left, text="Configuração de cada subfigura")
        frm_cfg.pack(fill="x", pady=(6, 8))

        app._subplot_cfg_rows = []

        def _visible_axes_count() -> int:
            rows = max(1, int(app.var_rows.get()))
            cols = max(1, int(app.var_cols.get()))
            return min(rows * cols, app._max_axes)

        def _rebuild_cfg_rows():
            # show only rows*cols
            n_axes = _visible_axes_count()
            # first create rows if not exist
            if not hasattr(app, "_subplot_cfg_widgets"):
                app._subplot_cfg_widgets = []  # list[(row_frame, cb_field, cb_mode, cb_ys, btn_crit, btn_axis)]
            # create missing
            while len(app._subplot_cfg_widgets) < app._max_axes:
                i = len(app._subplot_cfg_widgets)
                r = ttk.Frame(frm_cfg)
                ttk.Label(r, text=f"{i+1:02d}").pack(side="left", padx=(2, 6))

                cb_field = ttk.Combobox(r, values=getattr(app, "result_fields", []), width=28)
                cb_field.set(app._axes_cfg[i].get("field", ""))
                cb_field.pack(side="left", padx=(0, 6))

                cb_mode = ttk.Combobox(r, values=["CDF", "CCDF"], width=6, state="readonly")
                cb_mode.set(app._axes_cfg[i].get("mode", "CDF"))
                cb_mode.pack(side="left", padx=(0, 6))

                cb_ys = ttk.Combobox(r, values=["Linear", "Log"], width=7, state="readonly")
                cb_ys.set(app._axes_cfg[i].get("yscale", "Linear"))
                cb_ys.pack(side="left", padx=(0, 6))

                btn_crit = ttk.Button(r, text="Critérios", command=lambda idx=i: app._open_criteria_popup(idx))
                btn_crit.pack(side="left", padx=(0, 4))

                btn_axis = ttk.Button(r, text="Eixo X", command=lambda idx=i: app._open_axis_popup(idx))
                btn_axis.pack(side="left", padx=(0, 4))

                def _mk_upd(idx, combof, combom, comboys):
                    def _upd(*_):
                        app._axes_cfg[idx]["field"] = combof.get()
                        app._axes_cfg[idx]["mode"] = combom.get()
                        app._axes_cfg[idx]["yscale"] = comboys.get()
                        app._draw_results_plots()
                    return _upd

                upd = _mk_upd(i, cb_field, cb_mode, cb_ys)
                cb_field.bind("<<ComboboxSelected>>", upd)
                cb_mode.bind("<<ComboboxSelected>>", upd)
                cb_ys.bind("<<ComboboxSelected>>", upd)

                app._subplot_cfg_widgets.append((r, cb_field, cb_mode, cb_ys, btn_crit, btn_axis))

            # pack/unpack based on n_axes
            for i, (r, *_rest) in enumerate(app._subplot_cfg_widgets):
                if i < n_axes:
                    if not r.winfo_ismapped():
                        r.pack(fill="x", pady=2)
                else:
                    if r.winfo_ismapped():
                        r.pack_forget()

        # ============ Extras ============
        frm_extras = ttk.LabelFrame(left, text="Escala")
        frm_extras.pack(fill="x", pady=(6, 8))
        ttk.Checkbutton(frm_extras, text="Escala log no eixo X", variable=app.var_xlog,
                        command=lambda: app._draw_results_plots()).pack(fill="x", padx=4, pady=(2, 6))

        frm_auto = ttk.LabelFrame(left, text="Atualização")
        frm_auto.pack(fill="x", pady=(6, 8))
        ttk.Checkbutton(frm_auto, text="Atualização automática", variable=app.var_auto_update,
                        command=lambda: app._schedule_auto_update()).pack(side="left", padx=(4, 8))
        ttk.Label(frm_auto, text="Período (ms):").pack(side="left")
        ttk.Spinbox(frm_auto, from_=500, to=10000, increment=500, textvariable=app.var_update_period_ms, width=8,
                    command=lambda: app._schedule_auto_update()).pack(side="left", padx=(4, 8))
        ttk.Button(frm_auto, text="Atualizar agora", command=lambda: app._draw_results_plots()).pack(side="left")

        # ============ Figure ============
        app.fig_res = plt.figure(figsize=(7.8, 6.2))
        app.canvas_res = FigureCanvasTkAgg(app.fig_res, master=right)
        app.canvas_res.get_tk_widget().pack(fill="both", expand=True)

        def _refresh_src_ui():
            if app.var_results_src.get() == "REMOTE":
                frm_src_local.pack_forget()
                frm_src_remote.pack(fill="x", pady=(0, 6))
            else:
                frm_src_remote.pack_forget()
                frm_src_local.pack(fill="x", pady=(0, 6))

        _refresh_src_ui()
        _rebuild_cfg_rows()
        app._draw_results_plots()
        app._schedule_auto_update()

        # re-render cfg rows when grid changes
        app._results_rebuild_cfg_rows = _rebuild_cfg_rows

    # --------------------------
    # Helpers: SSH reuse and remote picker
    # --------------------------
    def _results_get_ssh_client(self):
        """
        Prefer reusing SSH client from Runner (self.ssh_client).
        If absent, try to create a new paramiko client using runner's settings if available.
        """
        cli = getattr(self, "ssh_client", None)
        try:
            if cli is not None and getattr(cli, "get_transport", None) and cli.get_transport() and cli.get_transport().is_active():
                return cli
        except Exception:
            pass

        # try to open new connection (no tunnel setup here; assume tunnel already running if using localhost:2222)
        try:
            import paramiko
        except Exception:
            return None

        # attempt to use existing vars from runner (if present)
        host = getattr(self, "ssh_host", tk.StringVar(value="localhost")).get().strip() if hasattr(self, "ssh_host") else "localhost"
        user = getattr(self, "ssh_user", tk.StringVar(value="")).get().strip() if hasattr(self, "ssh_user") else ""
        port = int(getattr(self, "ssh_port", tk.IntVar(value=2222)).get()) if hasattr(self, "ssh_port") else 2222
        pwd = getattr(self, "ssh_password", tk.StringVar(value="")).get() if hasattr(self, "ssh_password") else ""

        if not user:
            return None

        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # If runner uses key auth, this can still work with agent/keys.
            c.connect(hostname=host, port=port, username=user, password=(pwd or None),
                      timeout=8, allow_agent=True, look_for_keys=True)
            self.ssh_client = c
            return c
        except Exception:
            return None

    def _remote_dir_picker(self, initial=""):
        cli = self._results_get_ssh_client()
        if cli is None:
            messagebox.showerror("SSH", "Sem conexão SSH ativa (use a aba Runner para conectar).")
            return None
        try:
            sftp = cli.open_sftp()
        except Exception as e:
            messagebox.showerror("SFTP", f"Falha ao abrir SFTP:\n{e}")
            return None

        import posixpath
        import stat

        win = tk.Toplevel(self)
        win.title("Selecionar pasta remota (SSH)")
        win.transient(self)
        win.grab_set()
        win.geometry("760x480")

        # initial folder
        if not initial:
            if hasattr(self, "ssh_user"):
                initial = f"/home/{self.ssh_user.get().strip()}"
            else:
                initial = "/home"
        cur = tk.StringVar(value=initial)

        top = ttk.Frame(win)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Pasta:").pack(side="left")
        ent = ttk.Entry(top, textvariable=cur)
        ent.pack(side="left", fill="x", expand=True, padx=(6, 6))

        tree = ttk.Treeview(win, columns=("path",), show="tree")
        tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        chosen = {"path": None}

        def _is_dir(p):
            try:
                return stat.S_ISDIR(sftp.stat(p).st_mode)
            except Exception:
                return False

        def _list_dir(p):
            tree.delete(*tree.get_children())
            try:
                names = sorted(sftp.listdir(p))
                for name in names:
                    full = posixpath.join(p, name)
                    if _is_dir(full):
                        tree.insert("", "end", text=name, values=(full,))
            except Exception as e:
                messagebox.showerror("Remoto", f"Não consegui listar:\n{p}\n\n{e}")

        def _enter():
            sel = tree.selection()
            if not sel:
                return
            p = tree.item(sel[0], "values")[0]
            cur.set(p)
            _list_dir(p)

        def _go_up():
            p = cur.get().strip() or "/"
            up = posixpath.dirname(p.rstrip("/")) or "/"
            cur.set(up)
            _list_dir(up)

        def _select():
            p = cur.get().strip()
            if not p:
                return
            chosen["path"] = p
            win.destroy()

        def _goto_typed(_=None):
            p = cur.get().strip() or "/"
            if not _is_dir(p):
                messagebox.showwarning("Remoto", f"Diretório inválido:\n{p}")
                return
            _list_dir(p)

        ent.bind("<Return>", _goto_typed)
        tree.bind("<Double-1>", lambda e: _enter())

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Voltar", command=_go_up).pack(side="left")
        ttk.Button(btns, text="Entrar", command=_enter).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Selecionar esta pasta", command=_select).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=win.destroy).pack(side="right", padx=(0, 6))

        # initial list
        if not _is_dir(cur.get().strip()):
            cur.set("/")
        _list_dir(cur.get().strip())

        win.wait_window()
        try:
            sftp.close()
        except Exception:
            pass
        return chosen["path"]


    def _local_dir_picker_multi(self, initial: str = ""):
        """Popup browser (local) to select one or more directories. Returns list[str]."""
        import os
        import tkinter as tk
        from tkinter import ttk, messagebox

        start = initial if initial and os.path.isdir(initial) else os.path.expanduser("~")
        if not os.path.isdir(start):
            start = os.getcwd()

        win = tk.Toplevel(self)
        win.title("Selecionar pastas locais")
        win.transient(self)
        win.grab_set()
        win.geometry("760x480")

        cur = tk.StringVar(value=start)

        top = ttk.Frame(win); top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Pasta:").pack(side="left")
        ent = ttk.Entry(top, textvariable=cur)
        ent.pack(side="left", fill="x", expand=True, padx=(6,6))

        tree = ttk.Treeview(win, show="tree", selectmode="extended")
        tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

        chosen = {"paths": []}

        def _list_dir(p: str):
            tree.delete(*tree.get_children())
            try:
                names = sorted(os.listdir(p))
                for name in names:
                    full = os.path.join(p, name)
                    if os.path.isdir(full):
                        tree.insert("", "end", text=name)
            except Exception as e:
                messagebox.showerror("Local", f"Não consegui listar:\n{p}\n\n{e}")

        def _enter_selected():
            sel = tree.selection()
            if not sel:
                return
            name = tree.item(sel[0], "text")
            p = os.path.join(cur.get(), name)
            if os.path.isdir(p):
                cur.set(p)
                _list_dir(p)

        def _go_up():
            p = (cur.get() or "").strip()
            if not p:
                return
            up = os.path.dirname(p.rstrip("\\/"))
            if up and os.path.isdir(up):
                cur.set(up)
                _list_dir(up)

        def _add_selected():
            base = (cur.get() or "").strip()
            paths = []
            for iid in tree.selection():
                name = tree.item(iid, "text")
                full = os.path.join(base, name)
                if os.path.isdir(full):
                    paths.append(full)
            if not paths and os.path.isdir(base):
                paths = [base]
            chosen["paths"] = paths
            win.destroy()

        btns = ttk.Frame(win); btns.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(btns, text="Voltar", command=_go_up).pack(side="left")
        ttk.Button(btns, text="Entrar", command=_enter_selected).pack(side="left", padx=(6,0))
        ttk.Button(btns, text="Adicionar selecionadas", command=_add_selected).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=win.destroy).pack(side="right", padx=(0,6))

        tree.bind("<Double-1>", lambda e: _enter_selected())

        _list_dir(start)
        win.wait_window()
        return chosen["paths"]
    # --------------------------
    # Axis popup (per subplot)
    # --------------------------
    def _open_axis_popup(self, idx: int):
        cfg = self._axes_cfg[idx]
        field = cfg.get("field", "")

        info = RESULT_FIELDNAME_TO_PLOT_INFO.get(field, {})
        xlab_default = info.get("x_label", field)

        win = tk.Toplevel(self)
        win.title(f"Eixo X — Subfigura {idx+1:02d}")
        win.transient(self)
        win.grab_set()
        win.geometry("520x260")

        var_shift = tk.DoubleVar(value=float(cfg.get("x_shift", 0.0)))
        var_xlab = tk.StringVar(value=cfg.get("x_label_override", "") or xlab_default)
        var_leg_suffix = tk.StringVar(value=cfg.get("legend_suffix", ""))

        frm = ttk.Frame(win); frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text=f"Métrica: {field}").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(frm, text="Deslocamento em X (somar):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=var_shift, width=10).grid(row=1, column=1, sticky="w", padx=(6, 0))

        ttk.Label(frm, text="Rótulo X:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=var_xlab, width=44).grid(row=2, column=1, columnspan=2, sticky="we", padx=(6, 0), pady=(8, 0))

        ttk.Label(frm, text="Sufixo na legenda:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=var_leg_suffix, width=22).grid(row=3, column=1, sticky="w", padx=(6, 0), pady=(8, 0))

        # Presets based on common unit conversions
        presets = [
            ("(nenhum)", 0.0, xlab_default, ""),
            ("dBm → dBW  (-30)", -30.0, xlab_default.replace("dBm", "dBW"), " (dBW)"),
            ("dBW → dBm  (+30)", +30.0, xlab_default.replace("dBW", "dBm"), " (dBm)"),
            ("dBm/MHz → dBm/GHz (+30)", +30.0, xlab_default.replace("dBm/MHz", "dBm/GHz"), " (per GHz)"),
            ("dBm/GHz → dBm/MHz (-30)", -30.0, xlab_default.replace("dBm/GHz", "dBm/MHz"), " (per MHz)"),
        ]
        ttk.Label(frm, text="Preset:").grid(row=4, column=0, sticky="w", pady=(10, 0))
        var_preset = tk.StringVar(value=presets[0][0])
        cb = ttk.Combobox(frm, textvariable=var_preset, values=[p[0] for p in presets], state="readonly", width=28)
        cb.grid(row=4, column=1, sticky="w", padx=(6, 0), pady=(10, 0))

        def _apply_preset(*_):
            name = var_preset.get()
            for (nm, sh, xl, suf) in presets:
                if nm == name:
                    var_shift.set(sh)
                    var_xlab.set(xl)
                    var_leg_suffix.set(suf)
                    break

        cb.bind("<<ComboboxSelected>>", _apply_preset)

        frm.grid_columnconfigure(2, weight=1)

        def _save():
            try:
                cfg["x_shift"] = float(var_shift.get())
            except Exception:
                cfg["x_shift"] = 0.0
            cfg["x_label_override"] = var_xlab.get().strip()
            cfg["legend_suffix"] = var_leg_suffix.get()
            self._draw_results_plots()
            win.destroy()

        btns = ttk.Frame(win); btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="Salvar", command=_save).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=win.destroy).pack(side="right", padx=(0, 6))

        win.wait_window()

    # --------------------------
    # Criteria popup (per subplot)
    # --------------------------
    def _open_criteria_popup(self, idx: int):
        cfg = self._axes_cfg[idx]
        criteria = list(cfg.get("criteria", []))

        win = tk.Toplevel(self)
        win.title(f"Critérios de proteção — Subfigura {idx+1:02d}")
        win.transient(self)
        win.grab_set()
        win.geometry("780x420")

        # table
        cols = ("x", "p", "label", "color", "ls", "lw")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=110 if c in ("label",) else 90, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        def _refresh():
            tv.delete(*tv.get_children())
            for i, it in enumerate(criteria):
                tv.insert("", "end", iid=str(i), values=(
                    it.get("x", ""),
                    it.get("p", ""),
                    it.get("label", ""),
                    it.get("color", "Auto"),
                    it.get("ls", ":"),
                    it.get("lw", 1.6),
                ))

        _refresh()

        # edit form
        frm = ttk.Frame(win); frm.pack(fill="x", padx=10, pady=6)

        var_x = tk.StringVar(value="")
        var_p = tk.StringVar(value="")
        var_label = tk.StringVar(value="")
        var_color = tk.StringVar(value="Auto")
        var_ls = tk.StringVar(value=":")
        var_lw = tk.DoubleVar(value=1.6)

        ttk.Label(frm, text="x:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=var_x, width=10).grid(row=0, column=1, padx=(4, 10), sticky="w")
        ttk.Label(frm, text="critério (%):").grid(row=0, column=2, sticky="w")
        ttk.Entry(frm, textvariable=var_p, width=10).grid(row=0, column=3, padx=(4, 10), sticky="w")
        ttk.Label(frm, text="Legenda:").grid(row=0, column=4, sticky="w")
        ttk.Entry(frm, textvariable=var_label, width=20).grid(row=0, column=5, padx=(4, 10), sticky="we")

        ttk.Label(frm, text="Cor:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        cb_color = ttk.Combobox(frm, textvariable=var_color, values=[
            "Auto", "tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink",
            "tab:gray", "tab:olive", "tab:cyan", "black"
        ], width=12, state="readonly")
        cb_color.grid(row=1, column=1, padx=(4, 10), pady=(6, 0), sticky="w")

        ttk.Label(frm, text="Linha:").grid(row=1, column=2, sticky="w", pady=(6, 0))
        cb_ls = ttk.Combobox(frm, textvariable=var_ls, values=["-", "--", "-.", ":"], width=8, state="readonly")
        cb_ls.grid(row=1, column=3, padx=(4, 10), pady=(6, 0), sticky="w")

        ttk.Label(frm, text="Espessura:").grid(row=1, column=4, sticky="w", pady=(6, 0))
        ttk.Spinbox(frm, from_=0.5, to=6.0, increment=0.1, textvariable=var_lw, width=8).grid(
            row=1, column=5, padx=(4, 10), pady=(6, 0), sticky="w"
        )

        frm.grid_columnconfigure(5, weight=1)

        def _parse_p(txt):
            try:
                p = float(str(txt).strip())
                if p > 1.0:
                    p = p / 100.0
                return p
            except Exception:
                return None

        def _parse_x(txt):
            try:
                return float(str(txt).strip())
            except Exception:
                return None

        def _add_or_update(update=False):
            x = _parse_x(var_x.get())
            p = _parse_p(var_p.get())
            if x is None or p is None:
                messagebox.showwarning("Critério", "Preencha x e critério (%).")
                return
            it = {
                "x": x,
                "p": p,
                "label": var_label.get().strip(),
                "color": var_color.get(),
                "ls": var_ls.get(),
                "lw": float(var_lw.get()),
            }
            sel = tv.selection()
            if update and sel:
                i = int(sel[0])
                criteria[i] = it
            else:
                criteria.append(it)
            _refresh()

        def _remove():
            sel = tv.selection()
            if not sel:
                return
            i = int(sel[0])
            if 0 <= i < len(criteria):
                criteria.pop(i)
            _refresh()

        def _load_selected(*_):
            sel = tv.selection()
            if not sel:
                return
            i = int(sel[0])
            it = criteria[i]
            var_x.set(str(it.get("x", "")))
            var_p.set(str(it.get("p", "")))
            var_label.set(it.get("label", ""))
            var_color.set(it.get("color", "Auto"))
            var_ls.set(it.get("ls", ":"))
            try:
                var_lw.set(float(it.get("lw", 1.6)))
            except Exception:
                var_lw.set(1.6)

        tv.bind("<<TreeviewSelect>>", _load_selected)

        btns = ttk.Frame(win); btns.pack(fill="x", padx=10, pady=(6, 10))
        ttk.Button(btns, text="Adicionar", command=lambda: _add_or_update(update=False)).pack(side="left")
        ttk.Button(btns, text="Atualizar selecionado", command=lambda: _add_or_update(update=True)).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Remover selecionado", command=_remove).pack(side="left", padx=(6, 0))

        def _save():
            cfg["criteria"] = criteria
            self._draw_results_plots()
            win.destroy()

        ttk.Button(btns, text="Salvar", command=_save).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=win.destroy).pack(side="right", padx=(0, 6))

        win.wait_window()

    # --------------------------
    # Grid change handler
    # --------------------------
    def _on_results_grid_change(self):
        if hasattr(self, "_results_rebuild_cfg_rows"):
            try:
                self._results_rebuild_cfg_rows()
            except Exception:
                pass
        self._draw_results_plots()

    # --------------------------
    # Data access (local/remote) with caching
    # --------------------------
    def _remote_cache_base(self) -> str:
        # cache under local output_dir
        base = str(Path(getattr(self, "var_outdir", tk.StringVar(value=str(Path.cwd()))).get()) / "_remote_cache")
        os.makedirs(base, exist_ok=True)
        return base

    def _local_series_mtime_key(self, csv_path: str) -> str:
        try:
            st = os.stat(csv_path)
            return f"{st.st_mtime_ns}:{st.st_size}"
        except Exception:
            return "0:0"

    def _collect_series_from_folder(self, folder_tag: str, field: str):
        """
        folder_tag: local path OR 'ssh://<remote_dir>'
        Returns: np.ndarray or None
        Uses cache keyed by (folder_tag, field, mtime_key).
        """
        # Resolve local folder (download-on-demand if remote)
        folder_local = self._ensure_local_folder(folder_tag)
        if not folder_local:
            return None

        # Prefer exact <field>.csv
        cand = os.path.join(folder_local, f"{field}.csv")
        if os.path.exists(cand):
            key = self._local_series_mtime_key(cand)
            ckey = (folder_tag, field)
            if ckey in self._series_cache and self._series_cache[ckey][0] == key:
                return self._series_cache[ckey][1]
            arr = self._read_series_csv(cand, field)
            if arr is not None:
                self._series_cache[ckey] = (key, arr)
            return arr

        # fallback: scan other csvs (cached list)
        csvs = self._list_csvs_local(folder_local)
        for p in csvs:
            key = self._local_series_mtime_key(p)
            ckey = (folder_tag, field, p)
            if ckey in self._series_cache and self._series_cache[ckey][0] == key:
                arr = self._series_cache[ckey][1]
            else:
                arr = self._read_series_csv(p, field)
                if arr is not None:
                    self._series_cache[ckey] = (key, arr)
            if arr is not None and arr.size > 0:
                return arr
        return None

    def _read_series_csv(self, path: str, field: str):
        try:
            df = pd.read_csv(path)
        except Exception:
            return None
        try:
            if field in df.columns:
                s = df[field].dropna().values
            else:
                if df.shape[1] == 1:
                    s = df.iloc[:, 0].dropna().values
                elif "value" in df.columns:
                    s = df["value"].dropna().values
                else:
                    return None
            arr = np.asarray(s, dtype=float)
            arr = arr[np.isfinite(arr)]
            return arr if arr.size else None
        except Exception:
            return None

    def _list_csvs_local(self, folder_local: str) -> list[str]:
        # cache by folder + mtime of directory listing (best effort)
        try:
            m = os.stat(folder_local).st_mtime_ns
        except Exception:
            m = 0
        key = (folder_local, m)
        if not hasattr(self, "_local_ls_cache"):
            self._local_ls_cache = {}
        if key in self._local_ls_cache:
            return self._local_ls_cache[key]
        lst = sorted(glob.glob(os.path.join(folder_local, "*.csv")))
        self._local_ls_cache = {key: lst}  # keep only last
        return lst

    def _ensure_local_folder(self, folder_tag: str) -> str | None:
        """
        For local paths: returns itself.
        For ssh:// paths: returns a cache folder containing downloaded csvs (lazy).
        """
        if not folder_tag:
            return None
        if folder_tag.startswith("ssh://"):
            remote_dir = folder_tag[6:]
            cache_base = self._remote_cache_base()
            safe = remote_dir.strip("/").replace("/", "__")
            local_dir = os.path.join(cache_base, safe)
            os.makedirs(local_dir, exist_ok=True)
            return local_dir
        # local path
        if os.path.isdir(folder_tag):
            return folder_tag
        return None

    def _ensure_remote_field_csv(self, remote_dir: str, local_dir: str, field: str):
        """
        Downloads <field>.csv from remote_dir into local_dir if missing.
        """
        cli = self._results_get_ssh_client()
        if cli is None:
            return
        try:
            sftp = cli.open_sftp()
        except Exception:
            return
        try:
            rfile = f"{remote_dir.rstrip('/')}/{field}.csv"
            lfile = os.path.join(local_dir, f"{field}.csv")
            if os.path.exists(lfile):
                return
            # get
            sftp.get(rfile, lfile)
        except Exception:
            # ignore if not found
            pass
        finally:
            try:
                sftp.close()
            except Exception:
                pass

    # --------------------------
    # ECDF
    # --------------------------
    def _compute_ecdf(self, x: np.ndarray, ccdf: bool = False):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if x.size == 0:
            return None, None
        xs = np.sort(x)
        y = np.arange(1, xs.size + 1) / xs.size
        if ccdf:
            y = 1.0 - y
        return xs, y

    # --------------------------
    # Plot
    # --------------------------
    
    def _selected_dirs_for_plot(self) -> list[str]:
        """Return folders to plot.

        Default: plot *all* added folders.
        If the checkbox 'Plotar somente selecionadas' is enabled, plot only the
        currently selected folders in the listbox.
        """
        # If we have an explicit list of folders, use it
        if getattr(self, "res_dirs", None):
            all_dirs = list(self.res_dirs)

            only_sel = bool(getattr(self, "var_plot_selected_only", tk.BooleanVar(value=False)).get())
            if only_sel and hasattr(self, "lb_dirs") and hasattr(self, "_lb_display_to_tag"):
                sels = list(getattr(self.lb_dirs, "curselection", lambda: [])())
                if not sels:
                    return []  # user requested "only selected" but nothing selected
                out: list[str] = []
                for i in sels:
                    disp = self.lb_dirs.get(i)
                    tag = self._lb_display_to_tag.get(disp)
                    if tag:
                        out.append(tag)
                # keep order as in all_dirs
                ordered = [d for d in all_dirs if d in set(out)]
                return ordered

            return all_dirs

        # Fallback: current output_dir
        od = str(Path(getattr(self, "var_outdir", tk.StringVar(value="")).get()))
        return [od] if od else []

    def _draw_results_plots(self):
        # cancel pending auto job if disabled
        if self._plot_auto_job is not None and not self.var_auto_update.get():
            try:
                self.after_cancel(self._plot_auto_job)
            except Exception:
                pass
            self._plot_auto_job = None

        rows = max(1, int(self.var_rows.get()))
        cols = max(1, int(self.var_cols.get()))
        n_axes = min(rows * cols, self._max_axes)

        dirs = self._selected_dirs_for_plot()
        if not dirs:
            return

        self.fig_res.clf()
        axes = self.fig_res.subplots(rows, cols)
        if isinstance(axes, np.ndarray):
            axes_flat = axes.ravel()
        else:
            axes_flat = [axes]

        xlog = bool(self.var_xlog.get())

        for i in range(n_axes):
            ax = axes_flat[i]
            cfg = self._axes_cfg[i]
            field = cfg.get("field", "")
            mode = (cfg.get("mode") or "CDF").strip().upper()
            ytxt = (cfg.get("yscale") or "").strip().lower()
            ysc = "Log" if ytxt in {"log", "log10", "logarítmica", "logaritmica", "log-scale", "logscale"} else "Linear"
            ccdf = (mode == "CCDF")
            eps = 1e-4 if ysc == "Log" else 0.0

            x_shift = float(cfg.get("x_shift", 0.0) or 0.0)
            xlab_override = (cfg.get("x_label_override") or "").strip()
            legend_suffix = cfg.get("legend_suffix", "") or ""

            ax.cla()
            plotted_any = False

            for folder_tag in dirs:
                # remote: download needed field csv lazily (fast path)
                if folder_tag.startswith("ssh://"):
                    remote_dir = folder_tag[6:]
                    local_dir = self._ensure_local_folder(folder_tag)
                    self._ensure_remote_field_csv(remote_dir, local_dir, field)

                s = self._collect_series_from_folder(folder_tag, field)
                if s is None or s.size == 0:
                    continue

                xs, ys = self._compute_ecdf(s, ccdf=ccdf)
                if xs is None:
                    continue

                xs = xs + x_shift

                yplot = np.clip(ys, eps, 1.0) if ysc == "Log" else ys

                st = self._dir_style.get(folder_tag, {})
                label = st.get("label") or (Path(folder_tag[6:] if folder_tag.startswith("ssh://") else folder_tag).name)
                label = f"{label}{legend_suffix}"

                color = st.get("color", "Auto")
                ls = st.get("ls", "Auto")
                lw = float(st.get("lw", 1.6) or 1.6)

                plot_kwargs = {"label": label, "linewidth": lw}
                if color and color != "Auto":
                    plot_kwargs["color"] = color
                if ls and ls != "Auto":
                    plot_kwargs["linestyle"] = ls

                (line,) = ax.plot(xs, yplot, **plot_kwargs)
                plotted_any = True

            # protection criteria (vertical dotted lines)
            crits = cfg.get("criteria", []) or []
            for it in crits:
                try:
                    x0 = float(it.get("x"))
                    p = float(it.get("p"))
                    if p > 1.0:
                        p = p / 100.0
                    p = max(0.0, min(1.0, p))
                except Exception:
                    continue

                # As requested:
                # CDF: from 1 down to 1-p
                # CCDF: from 1 down to p
                if ccdf:
                    y1 = p
                else:
                    y1 = 1.0 - p
                y0 = 1.0

                if ysc == "Log":
                    y0 = max(eps, y0)
                    y1 = max(eps, y1)

                col = it.get("color", "Auto")
                ls = it.get("ls", ":") or ":"
                lw = float(it.get("lw", 1.6) or 1.6)
                if not col or col == "Auto":
                    col = "black"

                # draw as a Line2D so it can appear in the legend
                lab = (it.get("label") or "").strip()
                leg_label = lab if lab else "_nolegend_"
                ax.plot([x0 + x_shift, x0 + x_shift], [y0, y1],
                        linestyle=ls, linewidth=lw, color=col, alpha=0.9,
                        label=leg_label)

            # titles/labels
            info = RESULT_FIELDNAME_TO_PLOT_INFO.get(field, {})
            ax.set_title(info.get("title", field))
            ax.set_xlabel(xlab_override if xlab_override else info.get("x_label", field))
            ax.set_ylabel("CCDF" if ccdf else "CDF")

            # scales
            try:
                ax.set_yscale("log" if ysc == "Log" else "linear")
            except Exception:
                pass
            if xlog:
                try:
                    ax.set_xscale("log")
                except Exception:
                    pass

            ax.grid(True, which="both", alpha=0.3)
            if plotted_any:
                ax.legend()
            else:
                ax.text(0.5, 0.5, "sem dados", ha="center", va="center", transform=ax.transAxes, alpha=0.6)

            if ysc == "Log":
                ax.set_ylim(max(eps, 1e-6), 1.0)

        # remove unused axes
        if isinstance(axes, np.ndarray):
            for j in range(n_axes, len(axes_flat)):
                try:
                    self.fig_res.delaxes(axes_flat[j])
                except Exception:
                    pass

        self.fig_res.tight_layout()
        try:
            self.canvas_res.draw_idle()
        except Exception:
            pass

        # (re)schedule auto update
        if self.var_auto_update.get():
            period = max(200, int(self.var_update_period_ms.get()))
            def _tick():
                self._draw_results_plots()
            if self._plot_auto_job is not None:
                try:
                    self.after_cancel(self._plot_auto_job)
                except Exception:
                    pass
            self._plot_auto_job = self.after(period, _tick)

    def _schedule_auto_update(self):
        # cancel any previous job
        if self._plot_auto_job is not None:
            try:
                self.after_cancel(self._plot_auto_job)
            except Exception:
                pass
            self._plot_auto_job = None
        if self.var_auto_update.get():
            self._draw_results_plots()
