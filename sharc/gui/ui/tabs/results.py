import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import glob
import time
import stat
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pathlib import Path
import posixpath

# Attempt to import paramiko for SSH. If failed, SSH features will be disabled.
try:
    import paramiko
except ImportError:
    paramiko = None

# Import global configurations (assuming config.py exists)
from config import RESULT_FIELDNAME_TO_PLOT_INFO


class ResultsTab:
    """
    Manages the 'Results' tab, responsible for aggregating, filtering, and plotting
    simulation data (CDFs/CCDFs) from local or remote directories.
    """

    def __init__(self, app, parent_frame):
        """
        Initializes the ResultsTab.

        Args:
            app: Instance of the main App class.
            parent_frame: The widget where this tab will be drawn.
        """
        self.app = app
        self.frame = parent_frame

        # --- Local Tab State ---
        if not hasattr(self.app, "res_dirs"):
            # List of full tags (local path or ssh://...)
            self.app.res_dirs = []

        # Mapping for Listbox (Display Name <-> Full Tag)
        self._lb_display_to_tag = {}
        self._lb_tag_to_display = {}

        # Style by directory: tag -> {label, color, ls, lw}
        self._dir_style = {}

        # Performance Cache
        self._series_cache = {}   # (folder, field) -> (key, data)
        self._local_ls_cache = {}  # (folder, mtime) -> [csvs]

        self._plot_auto_job = None
        self._max_axes = 9

        # Subplot Configuration
        self.result_fields = sorted(list(RESULT_FIELDNAME_TO_PLOT_INFO.keys()))
        default_field = self.result_fields[0] if self.result_fields else ""

        self._axes_cfg = []
        for _ in range(self._max_axes):
            self._axes_cfg.append({
                "field": default_field,
                "mode": "CDF",
                "yscale": "Linear",
                "criteria": [],       # List of dicts {x, p, label...}
                "x_shift": 0.0,
                "x_label_override": "",
                "legend_suffix": ""
            })

        # UI Control Variables (create if they don't exist in app)
        if not hasattr(self.app, "var_results_src"):
            self.app.var_results_src = tk.StringVar(value="LOCAL")
        if not hasattr(self.app, "var_remote_results_dir"):
            self.app.var_remote_results_dir = tk.StringVar(value="/home")
        if not hasattr(self.app, "var_plot_selected_only"):
            self.app.var_plot_selected_only = tk.BooleanVar(value=False)

        # Style Editing Variables
        self.var_style_label = tk.StringVar()
        self.var_style_color = tk.StringVar(value="Auto")
        self.var_style_ls = tk.StringVar(value="Auto")
        self.var_style_lw = tk.DoubleVar(value=1.6)

        self._build_ui()
        self._schedule_auto_update()

    def _build_ui(self):
        """Constructs the UI layout for controls and plotting."""
        left = ttk.Frame(self.frame)
        right = ttk.Frame(self.frame)
        left.pack(side="left", fill="y", padx=5, pady=5)
        right.pack(side="right", fill="both", expand=True)

        # ==================== CONTROLS (LEFT) ====================

        # 1. Results Source (Local vs Remote)
        frm_src = ttk.LabelFrame(left, text="Results Source")
        frm_src.pack(fill="x", pady=(0, 5))

        #
        # This section toggles between local file access and remote access via SSH.
        # The image illustrates how the client connects to the remote server to retrieve data.

        ttk.Radiobutton(frm_src, text="Local", value="LOCAL", variable=self.app.var_results_src,
                        command=self._refresh_src_ui).pack(side="left", padx=5)
        ttk.Radiobutton(frm_src, text="Remote (SSH)", value="REMOTE", variable=self.app.var_results_src,
                        command=self._refresh_src_ui).pack(side="left", padx=5)

        self.frm_src_remote = ttk.Frame(left)
        ttk.Label(self.frm_src_remote,
                  text="Remote Folder (Base):").pack(anchor="w")
        ttk.Entry(self.frm_src_remote,
                  textvariable=self.app.var_remote_results_dir).pack(fill="x")

        # 2. Folder List
        ttk.Label(left, text="Result Folders (Comparison):").pack(anchor="w")
        frm_dirs = ttk.Frame(left)
        frm_dirs.pack(fill="x")

        self.lb_dirs = tk.Listbox(frm_dirs, height=5, selectmode="extended")
        self.lb_dirs.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frm_dirs, orient="vertical",
                           command=self.lb_dirs.yview)
        sb.pack(side="right", fill="y")
        self.lb_dirs.config(yscrollcommand=sb.set)

        # List Buttons
        frm_btn = ttk.Frame(left)
        frm_btn.pack(fill="x", pady=2)
        ttk.Button(frm_btn, text="+ Folder", command=self._add_dir,
                   width=8).pack(side="left", padx=(0, 2))
        ttk.Button(frm_btn, text="+ Current", command=self._add_current_outdir,
                   width=8).pack(side="left", padx=(0, 2))
        ttk.Button(frm_btn, text="- Sel", command=self._remove_dir,
                   width=6).pack(side="left")
        ttk.Button(frm_btn, text="↓", width=3,
                   command=lambda: self._move_selected_dirs(1)).pack(side="right")
        ttk.Button(frm_btn, text="↑", width=3,
                   command=lambda: self._move_selected_dirs(-1)).pack(side="right", padx=(2, 0))

        ttk.Checkbutton(left, text="Plot Selected Only",
                        variable=self.app.var_plot_selected_only,
                        command=self._draw_results_plots).pack(anchor="w", pady=(2, 5))

        # 3. Style Editor
        frm_style = ttk.LabelFrame(left, text="Style (Applies to Selection)")
        frm_style.pack(fill="x", pady=(0, 5))

        sf1 = ttk.Frame(frm_style)
        sf1.pack(fill="x", padx=2, pady=2)
        ttk.Label(sf1, text="Legend:").pack(side="left")
        ttk.Entry(sf1, textvariable=self.var_style_label).pack(
            side="left", fill="x", expand=True, padx=2)

        sf2 = ttk.Frame(frm_style)
        sf2.pack(fill="x", padx=2, pady=2)

        # Color
        cb_color = ttk.Combobox(sf2, textvariable=self.var_style_color, width=8, state="readonly",
                                values=["Auto", "tab:blue", "tab:orange", "tab:green", "tab:red", "black"])
        cb_color.pack(side="left", padx=2)

        # Line Style
        cb_ls = ttk.Combobox(sf2, textvariable=self.var_style_ls, width=5, state="readonly",
                             values=["Auto", "-", "--", "-.", ":"])
        cb_ls.pack(side="left", padx=2)

        # Line Width
        ttk.Spinbox(sf2, from_=0.5, to=5.0, increment=0.1,
                    textvariable=self.var_style_lw, width=4).pack(side="left", padx=2)

        ttk.Button(sf2, text="Apply", command=self._apply_style).pack(
            side="right", padx=2)

        # Bind to load style on selection
        self.lb_dirs.bind("<<ListboxSelect>>", self._load_style_from_selection)

        # 4. Grid Layout
        frm_grid = ttk.LabelFrame(left, text="Subplot Layout")
        frm_grid.pack(fill="x", pady=(0, 5))
        ttk.Label(frm_grid, text="R:").pack(side="left", padx=2)
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.app.var_rows, width=3,
                    command=self._rebuild_cfg_rows_and_draw).pack(side="left")
        ttk.Label(frm_grid, text="C:").pack(side="left", padx=2)
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.app.var_cols, width=3,
                    command=self._rebuild_cfg_rows_and_draw).pack(side="left")

        # 5. Configuration per Subplot
        self.frm_cfg_container = ttk.LabelFrame(
            left, text="Config per Subplot")
        self.frm_cfg_container.pack(fill="x", pady=(0, 5))

        self._subplot_widgets = []
        self._build_subplot_cfg_rows()

        # 6. Global Options & Export
        frm_glob = ttk.LabelFrame(left, text="Global Options")
        frm_glob.pack(fill="x", pady=(0, 5))

        #
        # This checkbox toggles the X-axis between linear and logarithmic scales,
        # useful for visualizing data that spans multiple orders of magnitude.
        ttk.Checkbutton(frm_glob, text="Log X Axis", variable=self.app.var_xlog,
                        command=self._draw_results_plots).pack(anchor="w", padx=2)

        frm_auto = ttk.Frame(frm_glob)
        frm_auto.pack(fill="x", padx=2, pady=2)
        ttk.Checkbutton(frm_auto, text="Auto Update", variable=self.app.var_auto_update,
                        command=self._schedule_auto_update).pack(side="left")
        ttk.Entry(frm_auto, textvariable=self.app.var_update_period_ms,
                  width=5).pack(side="left", padx=2)
        ttk.Label(frm_auto, text="ms").pack(side="left")

        ttk.Button(frm_glob, text="Export Figure",
                   command=self._export_results_fig).pack(fill="x", padx=2, pady=2)

        # ==================== PLOT (RIGHT) ====================
        self.fig_res = plt.figure(figsize=(7.8, 6.2))
        self.canvas_res = FigureCanvasTkAgg(self.fig_res, master=right)
        self.canvas_res.get_tk_widget().pack(fill="both", expand=True)

        # Initialization
        self._refresh_src_ui()
        self._rebuild_lb_from_state()
        self._rebuild_cfg_rows_and_draw()

    # ---------------- UI Helpers ----------------

    def _refresh_src_ui(self):
        """Shows or hides the Remote Folder input based on selection."""
        if self.app.var_results_src.get() == "REMOTE":
            self.frm_src_remote.pack(fill="x", pady=(
                2, 4), after=self.frm_src_remote.master.winfo_children()[0])
        else:
            self.frm_src_remote.pack_forget()

    def _build_subplot_cfg_rows(self):
        """Creates configuration rows for all possible subplots."""
        for i in range(self._max_axes):
            r = ttk.Frame(self.frm_cfg_container)

            ttk.Label(r, text=f"{i+1:02d}").pack(side="left")

            cb_field = ttk.Combobox(r, values=self.result_fields, width=15)
            cb_field.set(self._axes_cfg[i]["field"])
            cb_field.pack(side="left", padx=2)

            cb_mode = ttk.Combobox(
                r, values=["CDF", "CCDF"], width=5, state="readonly")
            cb_mode.set(self._axes_cfg[i]["mode"])
            cb_mode.pack(side="left", padx=2)

            cb_scale = ttk.Combobox(
                r, values=["Linear", "Log"], width=6, state="readonly")
            cb_scale.set(self._axes_cfg[i]["yscale"])
            cb_scale.pack(side="left", padx=2)

            btn_crit = ttk.Button(
                r, text="Crit.", width=4, command=lambda idx=i: self._open_criteria_popup(idx))
            btn_crit.pack(side="left", padx=1)

            btn_axis = ttk.Button(
                r, text="Axis", width=4, command=lambda idx=i: self._open_axis_popup(idx))
            btn_axis.pack(side="left", padx=1)

            # Closure for bindings
            def _mk_cb(idx, w_f, w_m, w_s):
                def _upd(*_):
                    self._axes_cfg[idx]["field"] = w_f.get()
                    self._axes_cfg[idx]["mode"] = w_m.get()
                    self._axes_cfg[idx]["yscale"] = w_s.get()
                    self._draw_results_plots()
                return _upd

            cb_func = _mk_cb(i, cb_field, cb_mode, cb_scale)
            cb_field.bind("<<ComboboxSelected>>", cb_func)
            cb_mode.bind("<<ComboboxSelected>>", cb_func)
            cb_scale.bind("<<ComboboxSelected>>", cb_func)

            self._subplot_widgets.append(r)

    def _rebuild_cfg_rows_and_draw(self):
        """Updates the visibility of configuration rows based on grid size."""
        rows = max(1, int(self.app.var_rows.get()))
        cols = max(1, int(self.app.var_cols.get()))
        n_needed = min(rows * cols, self._max_axes)

        for i, widget_frame in enumerate(self._subplot_widgets):
            if i < n_needed:
                widget_frame.pack(fill="x", pady=1)
            else:
                widget_frame.pack_forget()

        self._draw_results_plots()

    # ---------------- Listbox & Folder Helpers ----------------

    def _get_display_name(self, tag):
        """Generates a short name for display in the Listbox."""
        raw = tag
        if raw.startswith("ssh://"):
            raw = raw[6:]
        base = os.path.basename(raw.rstrip("/\\")) or raw.rstrip("/\\")

        # Simple Disambiguation
        count = 0
        disp = base
        while disp in self._lb_display_to_tag and self._lb_display_to_tag[disp] != tag:
            count += 1
            disp = f"{base} ({count})"
        return disp

    def _insert_tag_lb(self, tag):
        """Inserts a tag into the Listbox and internal mappings."""
        disp = self._get_display_name(tag)
        self._lb_display_to_tag[disp] = tag
        self._lb_tag_to_display[tag] = disp
        self.lb_dirs.insert("end", disp)

    def _rebuild_lb_from_state(self):
        """Rebuilds the Listbox from the app state."""
        self.lb_dirs.delete(0, "end")
        self._lb_display_to_tag.clear()
        self._lb_tag_to_display.clear()

        for tag in self.app.res_dirs:
            self._insert_tag_lb(tag)

    def _get_selected_tags(self):
        """Returns the tags associated with the currently selected items."""
        tags = []
        for idx in self.lb_dirs.curselection():
            disp = self.lb_dirs.get(idx)
            tag = self._lb_display_to_tag.get(disp)
            if tag:
                tags.append(tag)
        return tags

    def _add_dir(self):
        """Opens dialog (Local or Remote) to add a directory."""
        if self.app.var_results_src.get() == "REMOTE":
            chosen = self._remote_dir_picker(
                initial=self.app.var_remote_results_dir.get())
            if chosen:
                tag = f"ssh://{chosen}"
                if tag not in self.app.res_dirs:
                    self.app.res_dirs.append(tag)
                    self._insert_tag_lb(tag)
                    self._draw_results_plots()
        else:
            # Local
            init = str(Path(self.app.var_outdir.get() or Path.cwd()))
            path = filedialog.askdirectory(
                initialdir=init, title="Select Folder")
            if path:
                path = str(Path(path))  # Normalize
                if path not in self.app.res_dirs:
                    self.app.res_dirs.append(path)
                    self._insert_tag_lb(path)
                    self._draw_results_plots()

    def _add_current_outdir(self):
        """Adds the current output directory to the comparison list."""
        path = str(Path(self.app.var_outdir.get()))
        if path and path not in self.app.res_dirs:
            self.app.res_dirs.append(path)
            self._insert_tag_lb(path)
            self._draw_results_plots()

    def _remove_dir(self):
        """Removes the selected directories from the list."""
        sel_idx = list(self.lb_dirs.curselection())[::-1]
        for idx in sel_idx:
            disp = self.lb_dirs.get(idx)
            tag = self._lb_display_to_tag.get(disp)
            if tag:
                if tag in self.app.res_dirs:
                    self.app.res_dirs.remove(tag)
                del self._lb_display_to_tag[disp]
                del self._lb_tag_to_display[tag]
                self._dir_style.pop(tag, None)
            self.lb_dirs.delete(idx)
        self._draw_results_plots()

    def _move_selected_dirs(self, delta):
        """Reorders the selected directories up or down."""
        sel_idx = list(self.lb_dirs.curselection())
        if not sel_idx:
            return

        arr = self.app.res_dirs
        n = len(arr)

        current_selection_tags = [
            self._lb_display_to_tag[self.lb_dirs.get(i)] for i in sel_idx]

        idxs_to_move = sorted(sel_idx, reverse=(delta > 0))

        for i in idxs_to_move:
            if delta < 0 and i > 0:  # Up
                arr[i], arr[i-1] = arr[i-1], arr[i]
            elif delta > 0 and i < n - 1:  # Down
                arr[i], arr[i+1] = arr[i+1], arr[i]

        self._rebuild_lb_from_state()

        # Restore selection
        for i, tag in enumerate(self.app.res_dirs):
            if tag in current_selection_tags:
                self.lb_dirs.selection_set(i)

        self._draw_results_plots()

    # ---------------- Style Logic ----------------

    def _load_style_from_selection(self, event=None):
        """Loads style parameters into the editor for the selected directory."""
        tags = self._get_selected_tags()
        if not tags:
            return
        st = self._dir_style.get(tags[0], {})
        self.var_style_label.set(st.get("label", ""))
        self.var_style_color.set(st.get("color", "Auto"))
        self.var_style_ls.set(st.get("ls", "Auto"))
        self.var_style_lw.set(st.get("lw", 1.6))

    def _apply_style(self):
        """Applies style changes to all selected directories."""
        tags = self._get_selected_tags()
        if not tags:
            return
        for tag in tags:
            st = self._dir_style.get(tag, {})
            st["label"] = self.var_style_label.get()
            st["color"] = self.var_style_color.get()
            st["ls"] = self.var_style_ls.get()
            st["lw"] = self.var_style_lw.get()
            self._dir_style[tag] = st
        self._draw_results_plots()

    # ---------------- Popups (Criteria & Axis) ----------------

    def _open_criteria_popup(self, idx):
        """Opens the popup to manage statistical criteria (percentiles)."""
        cfg = self._axes_cfg[idx]
        criteria_list = cfg.get("criteria", [])

        win = tk.Toplevel(self.frame)
        win.title(f"Criteria - Subplot {idx+1}")
        win.geometry("600x350")

        # Treeview
        cols = ("x", "p", "label", "color")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=8)
        tv.heading("x", text="X")
        tv.column("x", width=60)
        tv.heading("p", text="Crit %")
        tv.column("p", width=60)
        tv.heading("label", text="Label")
        tv.column("label", width=150)
        tv.heading("color", text="Color")
        tv.column("color", width=80)
        tv.pack(fill="both", expand=True, padx=5, pady=5)

        def _refresh():
            tv.delete(*tv.get_children())
            for i, c in enumerate(criteria_list):
                tv.insert("", "end", iid=str(i), values=(
                    c.get('x'), c.get('p'), c.get('label'), c.get('color')))

        _refresh()

        #
        # This section defines criteria lines. For example, setting 'p' to 95
        # draws a line indicating the value below which 95% of observations fall (95th percentile).

        # Inputs
        frm = ttk.Frame(win)
        frm.pack(fill="x", padx=5, pady=5)
        v_x = tk.DoubleVar()
        v_p = tk.DoubleVar()
        v_l = tk.StringVar()
        v_c = tk.StringVar(value="black")

        ttk.Label(frm, text="X:").pack(side="left")
        ttk.Entry(frm, textvariable=v_x, width=8).pack(side="left", padx=2)
        ttk.Label(frm, text="Prob(%):").pack(side="left")
        ttk.Entry(frm, textvariable=v_p, width=8).pack(side="left", padx=2)
        ttk.Label(frm, text="Label:").pack(side="left")
        ttk.Entry(frm, textvariable=v_l, width=15).pack(side="left", padx=2)
        ttk.Combobox(frm, textvariable=v_c, values=[
                     "black", "red", "blue", "green"], width=8).pack(side="left")

        def _add():
            criteria_list.append({
                "x": v_x.get(), "p": v_p.get(), "label": v_l.get(), "color": v_c.get(), "ls": ":", "lw": 1.0
            })
            _refresh()
            self._draw_results_plots()

        def _del():
            sel = tv.selection()
            if sel:
                idx_del = int(sel[0])
                if 0 <= idx_del < len(criteria_list):
                    criteria_list.pop(idx_del)
                    _refresh()
                    self._draw_results_plots()

        ttk.Button(frm, text="Add", command=_add).pack(side="left", padx=5)
        ttk.Button(frm, text="Remove", command=_del).pack(side="left")

    def _open_axis_popup(self, idx):
        """Opens popup for configuring axis properties (shifts, labels)."""
        cfg = self._axes_cfg[idx]
        win = tk.Toplevel(self.frame)
        win.title(f"Axis - Subplot {idx+1}")
        win.geometry("400x200")

        v_shift = tk.DoubleVar(value=cfg.get("x_shift", 0.0))
        v_xlab = tk.StringVar(value=cfg.get("x_label_override", ""))
        v_leg_suf = tk.StringVar(value=cfg.get("legend_suffix", ""))

        frm = ttk.Frame(win)
        frm.pack(padx=10, pady=10, fill="both")

        ttk.Label(frm, text="Shift X (offset):").grid(
            row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_shift).grid(row=0, column=1, sticky="ew")

        ttk.Label(frm, text="Label X Override:").grid(
            row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_xlab).grid(row=1, column=1, sticky="ew")

        ttk.Label(frm, text="Legend Suffix:").grid(
            row=2, column=0, sticky="w")
        ttk.Entry(frm, textvariable=v_leg_suf).grid(
            row=2, column=1, sticky="ew")

        def _save():
            cfg["x_shift"] = v_shift.get()
            cfg["x_label_override"] = v_xlab.get()
            cfg["legend_suffix"] = v_leg_suf.get()
            self._draw_results_plots()
            win.destroy()

        ttk.Button(win, text="Save", command=_save).pack(pady=10)

    # ---------------- SSH / Remote Logic ----------------

    def _get_ssh_client(self):
        """Retrieves an existing SSH client or creates a new one using Paramiko."""
        cli = getattr(self.app, "ssh_client", None)
        if cli and getattr(cli, "get_transport", None) and cli.get_transport().is_active():
            return cli

        if paramiko is None:
            return None

        try:
            host = getattr(self.app, "ssh_host",
                           tk.StringVar(value="localhost")).get()
            user = getattr(self.app, "ssh_user", tk.StringVar(value="")).get()
            pwd = getattr(self.app, "ssh_password",
                          tk.StringVar(value="")).get()
            port = int(getattr(self.app, "ssh_port",
                       tk.IntVar(value=2222)).get())

            if not user:
                return None

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, port=port, username=user,
                           password=pwd or None, timeout=5)
            self.app.ssh_client = client
            return client
        except:
            return None

    def _remote_dir_picker(self, initial=""):
        """Opens a remote browser via SFTP to select a directory."""
        cli = self._get_ssh_client()
        if not cli:
            messagebox.showerror(
                "Error", "Could not connect via SSH or Paramiko is not installed.")
            return None

        try:
            sftp = cli.open_sftp()
        except:
            return None

        # Mini Browser Modal
        win = tk.Toplevel(self.frame)
        win.title("Remote Browser")
        win.geometry("600x400")

        cur_path = tk.StringVar(value=initial or ".")

        top = ttk.Frame(win)
        top.pack(fill="x")
        ttk.Entry(top, textvariable=cur_path).pack(
            side="left", fill="x", expand=True)

        tv = ttk.Treeview(win, show="tree")
        tv.pack(fill="both", expand=True)

        chosen = []

        def _ls(p):
            tv.delete(*tv.get_children())
            try:
                # Resolve path
                if p == ".":
                    p = sftp.normalize(".")
                cur_path.set(p)

                for item in sorted(sftp.listdir_attr(p), key=lambda x: x.filename):
                    if stat.S_ISDIR(item.st_mode):
                        tv.insert("", "end", text=item.filename,
                                  values=("DIR",))
            except Exception as e:
                print(e)

        def _dbl_click(_):
            sel = tv.selection()
            if not sel:
                return
            item = tv.item(sel[0])
            name = item["text"]
            new_p = posixpath.join(cur_path.get(), name)
            _ls(new_p)

        def _up():
            p = cur_path.get()
            _ls(posixpath.dirname(p))

        def _ok():
            chosen.append(cur_path.get())
            win.destroy()

        tv.bind("<Double-1>", _dbl_click)

        btn = ttk.Frame(win)
        btn.pack(fill="x")
        ttk.Button(btn, text="Up", command=_up).pack(side="left")
        ttk.Button(btn, text="Select Current Folder",
                   command=_ok).pack(side="right")

        _ls(initial or ".")
        win.wait_window()
        sftp.close()
        return chosen[0] if chosen else None

    # ---------------- Data & Caching Logic ----------------

    def _remote_cache_base(self):
        """Returns the path for caching remote files locally."""
        out = str(Path(self.app.var_outdir.get()))
        base = os.path.join(out, "_remote_cache")
        os.makedirs(base, exist_ok=True)
        return base

    def _ensure_local_folder(self, tag):
        """Returns the local folder path. Downloads if remote."""
        if tag.startswith("ssh://"):
            remote_path = tag[6:]
            # Safe name for local cache
            safe_name = remote_path.strip(
                "/").replace("/", "__").replace(":", "_")
            local_cache = os.path.join(self._remote_cache_base(), safe_name)
            os.makedirs(local_cache, exist_ok=True)
            return local_cache
        else:
            return tag  # Already local

    def _sync_remote_file(self, tag, field):
        """Downloads specific CSV for the field if remote."""
        if not tag.startswith("ssh://"):
            return

        remote_path = tag[6:]
        local_dir = self._ensure_local_folder(tag)
        fname = f"{field}.csv"
        local_file = os.path.join(local_dir, fname)
        remote_file = posixpath.join(remote_path, fname)

        # Simple check: assume valid if exists and > 0 size
        if os.path.exists(local_file) and os.path.getsize(local_file) > 0:
            return

        # Download
        cli = self._get_ssh_client()
        if cli:
            try:
                sftp = cli.open_sftp()
                sftp.get(remote_file, local_file)
                sftp.close()
            except:
                pass  # File might not exist

    def _get_series_data(self, tag, field):
        """Retrieves data for a specific field, handling caching."""
        # 1. Ensure local file
        self._sync_remote_file(tag, field)
        folder = self._ensure_local_folder(tag)

        # 2. Check Memory Cache
        cand = os.path.join(folder, f"{field}.csv")
        target_file = None

        if os.path.exists(cand):
            target_file = cand
        else:
            # Glob cache optimization
            mtime_dir = os.stat(folder).st_mtime
            if (folder, mtime_dir) in self._local_ls_cache:
                files = self._local_ls_cache[(folder, mtime_dir)]
            else:
                files = glob.glob(os.path.join(folder, "*.csv"))
                self._local_ls_cache[(folder, mtime_dir)] = files
            pass

        if not target_file:
            return None

        # 3. Check file modification time
        try:
            stats = os.stat(target_file)
            key = f"{stats.st_mtime}:{stats.st_size}"

            cache_key = (tag, field)
            if cache_key in self._series_cache:
                stored_key, data = self._series_cache[cache_key]
                if stored_key == key:
                    return data

            # Read CSV
            df = pd.read_csv(target_file)
            col_data = None
            if field in df.columns:
                col_data = df[field].values
            elif "value" in df.columns:
                col_data = df["value"].values
            elif df.shape[1] == 1:
                col_data = df.iloc[:, 0].values

            if col_data is not None:
                col_data = col_data.astype(float)
                col_data = col_data[np.isfinite(col_data)]
                self._series_cache[cache_key] = (key, col_data)
                return col_data

        except Exception as e:
            print(f"Error reading {target_file}: {e}")

        return None

    # ---------------- Plot Logic ----------------

    def _compute_ecdf(self, x, ccdf=False):
        """Computes the Empirical Cumulative Distribution Function."""
        #
        # ECDF sorts the data points and assigns a probability (y-axis) to each value (x-axis),
        # creating a step function. CCDF is simply 1 - ECDF.
        x = np.sort(x)
        n = x.size
        y = np.arange(1, n + 1) / n
        if ccdf:
            y = 1.0 - y
        return x, y

    def _draw_results_plots(self):
        """Main plotting routine. Clears canvas and draws requested subplots."""
        if self._plot_auto_job:
            self.app.after_cancel(self._plot_auto_job)
            self._plot_auto_job = None

        rows = max(1, int(self.app.var_rows.get()))
        cols = max(1, int(self.app.var_cols.get()))
        n_axes = min(rows * cols, self._max_axes)

        self.fig_res.clf()
        axes = self.fig_res.subplots(rows, cols)
        if isinstance(axes, np.ndarray):
            axes_flat = axes.ravel()
        else:
            axes_flat = [axes]

        # Filter folders
        all_tags = self.app.res_dirs
        if self.app.var_plot_selected_only.get():
            tags_to_plot = self._get_selected_tags()
            # Keep original order
            tags_to_plot = [t for t in all_tags if t in tags_to_plot]
        else:
            tags_to_plot = list(all_tags)
            if not tags_to_plot:
                cur = str(Path(self.app.var_outdir.get()))
                if os.path.exists(cur):
                    tags_to_plot = [cur]

        for i in range(n_axes):
            ax = axes_flat[i]
            cfg = self._axes_cfg[i]
            field = cfg.get("field", "")
            mode = cfg.get("mode", "CDF")
            ccdf = (mode == "CCDF")
            ysc = cfg.get("yscale", "Linear")
            x_shift = float(cfg.get("x_shift", 0.0))

            ax.cla()
            has_data = False

            # Plot Lines
            for tag in tags_to_plot:
                data = self._get_series_data(tag, field)
                if data is None or data.size == 0:
                    continue

                xs, ys = self._compute_ecdf(data, ccdf)
                xs = xs + x_shift

                # Apply Style
                st = self._dir_style.get(tag, {})
                lbl = st.get("label") or self._lb_tag_to_display.get(
                    tag) or Path(tag).name
                lbl += cfg.get("legend_suffix", "")

                clr = st.get("color", "Auto")
                ls = st.get("ls", "Auto")
                lw = st.get("lw", 1.6)

                kwargs = {"label": lbl, "linewidth": lw}
                if clr != "Auto":
                    kwargs["color"] = clr
                if ls != "Auto":
                    kwargs["linestyle"] = ls

                # Clip for Log scale
                if ysc == "Log":
                    ys = np.clip(ys, 1e-5, 1.0)

                ax.plot(xs, ys, **kwargs)
                has_data = True

            # Plot Criteria Lines
            for crit in cfg.get("criteria", []):
                try:
                    cx = float(crit["x"]) + x_shift
                    cp = float(crit["p"])
                    if cp > 1.0:
                        cp /= 100.0

                    ccolor = crit.get("color", "black")
                    clabel = crit.get("label", "")

                    y_target = cp
                    y_bottom = 1e-5 if ysc == "Log" else 0

                    ax.vlines(cx, y_bottom, y_target, colors=ccolor,
                              linestyles=":", label=clabel if clabel else "_nolegend_")
                    ax.hlines(y_target, -1e9, cx,
                              colors=ccolor, linestyles=":")
                except:
                    pass

            # Axis Config
            info = RESULT_FIELDNAME_TO_PLOT_INFO.get(field, {})
            ax.set_title(info.get("title", field))

            x_label = cfg.get("x_label_override") or info.get("x_label", field)
            ax.set_xlabel(x_label)
            ax.set_ylabel(mode)

            if ysc == "Log":
                ax.set_yscale("log")
                ax.set_ylim(bottom=1e-4)

            if self.app.var_xlog.get():
                try:
                    ax.set_xscale("log")
                except:
                    pass

            ax.grid(True, which="both", alpha=0.3)
            if has_data:
                ax.legend(fontsize=8)

        # Remove empty axes
        for i in range(n_axes, len(axes_flat)):
            self.fig_res.delaxes(axes_flat[i])

        self.fig_res.tight_layout()
        self.canvas_res.draw_idle()

        if self.app.var_auto_update.get():
            ms = int(self.app.var_update_period_ms.get())
            self._plot_auto_job = self.app.after(
                max(500, ms), self._draw_results_plots)

    def _export_results_fig(self):
        """Exports the current figure to a file."""
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[
                                            ("PNG", "*.png"), ("PDF", "*.pdf")])
        if path:
            dpi = getattr(self.app, "var_export_dpi",
                          tk.IntVar(value=300)).get()
            self.fig_res.savefig(path, dpi=dpi)
            messagebox.showinfo("Export", f"Saved: {path}")

    def _schedule_auto_update(self):
        """Toggles the automatic update timer."""
        if self.app.var_auto_update.get():
            self._draw_results_plots()
        elif self._plot_auto_job:
            self.app.after_cancel(self._plot_auto_job)
            self._plot_auto_job = None
