import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import stat
import pandas as pd
import numpy as np
import threading
import io
import webbrowser
import posixpath
import shutil
import math  # Added for log calculation
from pathlib import Path

# Image handling for Tkinter
from PIL import Image, ImageTk

# Plotly Imports
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# SSH Import (Paramiko)
try:
    import paramiko
except ImportError:
    paramiko = None

# Config Import
try:
    from config import RESULT_FIELDNAME_TO_PLOT_INFO
except ImportError:
    RESULT_FIELDNAME_TO_PLOT_INFO = {}


class ResultsTab:
    """
    Results Tab with SSH Plotting & Caching.

    Features:
    - Plotly-based interactive plotting with static preview.
    - SSH Support: Browses remote folders, caches CSVs locally for speed.
    - Comparison: Plots multiple folders (Local vs Remote).
    - Multi-select for remote folders.
    - Default Protection Criteria: -12.2dB and -6dB (Toggleable).
    - Style Editor: Customize legend, color, linestyle per folder.
    - Filter: Option to plot only selected folders.
    - Axis Control: Adjust Limits and Ticks (Step) with Smart Formatting.
    """

    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        # --- State Management ---
        if not hasattr(self.app, "res_dirs"):
            self.app.res_dirs = []

        if not hasattr(self.app, "res_styles"):
            self.app.res_styles = {}

        self._init_ssh_vars()

        self._data_cache = {}
        self._plot_preview_job = None
        self._photo_image = None
        self._max_axes = 9
        self._disable_traces = False

        # --- Default Configuration ---
        self.result_fields = sorted(list(RESULT_FIELDNAME_TO_PLOT_INFO.keys()))
        if not self.result_fields:
            self.result_fields = ["ExampleField"]

        default_field = self.result_fields[0]

        default_criteria = [
            {"val": -12.2, "type": "Vertical (X)",
                "label": "Prot -12.2dB", "color": "red", "enabled": True},
            {"val": -6.0,  "type": "Vertical (X)",
                "label": "Prot -6dB",    "color": "orange", "enabled": True}
        ]

        self._axes_cfg = []
        for i in range(self._max_axes):
            self._axes_cfg.append({
                "field": default_field,
                "mode": "CDF",
                "title": "",
                "x_label": "",
                "y_label": "",
                "x_log": False,
                "y_log": False,
                "x_shift": 0.0,
                "legend_suffix": "",
                "x_min": "", "x_max": "", "x_step": "",
                "y_min": "", "y_max": "", "y_step": "",
                "criteria": [c.copy() for c in default_criteria]
            })

        self._init_ui_vars()
        self._build_ui()
        self._schedule_update()

    def _init_ssh_vars(self):
        if hasattr(self.app, "ssh_host"):
            self.var_ssh_host = self.app.ssh_host
        else:
            self.var_ssh_host = tk.StringVar(value="localhost")
            self.app.ssh_host = self.var_ssh_host

        if hasattr(self.app, "ssh_user"):
            self.var_ssh_user = self.app.ssh_user
        else:
            self.var_ssh_user = tk.StringVar(value="")
            self.app.ssh_user = self.var_ssh_user

        if hasattr(self.app, "ssh_password"):
            self.var_ssh_pass = self.app.ssh_password
        else:
            self.var_ssh_pass = tk.StringVar(value="")
            self.app.ssh_password = self.var_ssh_pass

        if hasattr(self.app, "ssh_port"):
            self.var_ssh_port = self.app.ssh_port
        else:
            self.var_ssh_port = tk.StringVar(value="22")
            self.app.ssh_port = self.var_ssh_port

    def _init_ui_vars(self):
        self.var_rows = tk.IntVar(value=1)
        self.var_cols = tk.IntVar(value=1)
        self.var_source_mode = tk.StringVar(value="LOCAL")
        self.var_remote_base = tk.StringVar(value="/home")
        self.var_current_subplot_idx = tk.IntVar(value=0)

        # Plot Config Vars
        self.var_edit_field = tk.StringVar()
        self.var_edit_mode = tk.StringVar()
        self.var_edit_title = tk.StringVar()
        self.var_edit_xlabel = tk.StringVar()
        self.var_edit_ylabel = tk.StringVar()
        self.var_edit_xlog = tk.BooleanVar()
        self.var_edit_ylog = tk.BooleanVar()
        self.var_edit_leg_suffix = tk.StringVar()
        self.var_edit_xshift = tk.DoubleVar(value=0.0)

        # Limits and Steps
        self.var_edit_xmin = tk.StringVar()
        self.var_edit_xmax = tk.StringVar()
        self.var_edit_xstep = tk.StringVar()
        self.var_edit_ymin = tk.StringVar()
        self.var_edit_ymax = tk.StringVar()
        self.var_edit_ystep = tk.StringVar()

        if hasattr(self.app, "var_plot_selected_only"):
            self.var_plot_selected_only = self.app.var_plot_selected_only
        else:
            self.var_plot_selected_only = tk.BooleanVar(value=False)
            self.app.var_plot_selected_only = self.var_plot_selected_only

        self.var_style_label = tk.StringVar()
        self.var_style_color = tk.StringVar(value="Auto")
        self.var_style_ls = tk.StringVar(value="Auto")
        self.var_style_lw = tk.DoubleVar(value=1.5)

        self._trace_vars = [
            self.var_edit_field, self.var_edit_mode, self.var_edit_title,
            self.var_edit_xlabel, self.var_edit_ylabel, self.var_edit_xlog,
            self.var_edit_ylog, self.var_edit_leg_suffix, self.var_rows, self.var_cols,
            self.var_plot_selected_only,
            self.var_edit_xmin, self.var_edit_xmax, self.var_edit_xstep,
            self.var_edit_ymin, self.var_edit_ymax, self.var_edit_ystep
        ]
        for v in self._trace_vars:
            v.trace_add("write", self._on_config_change)

        self.var_edit_xshift.trace_add("write", self._on_config_change)

    # ---------------- UI Construction ----------------

    def _build_ui(self):
        paned = ttk.PanedWindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left_frame = ttk.Frame(paned, width=450)
        right_frame = ttk.Frame(paned)

        paned.add(left_frame, weight=0)
        paned.add(right_frame, weight=1)

        self._build_file_manager(left_frame)
        self._build_layout_controls(left_frame)
        self._build_subplot_config(left_frame)
        self._build_plot_preview(right_frame)
        self._load_subplot_config_to_ui()

    def _build_file_manager(self, parent):
        frm = ttk.LabelFrame(parent, text="Result Folders")
        frm.pack(fill="x", padx=5, pady=5)

        src_frame = ttk.Frame(frm)
        src_frame.pack(fill="x", padx=5, pady=2)

        ttk.Label(src_frame, text="Source:").pack(side="left")
        ttk.Radiobutton(src_frame, text="Local", variable=self.var_source_mode,
                        value="LOCAL").pack(side="left", padx=5)
        ttk.Radiobutton(src_frame, text="Remote", variable=self.var_source_mode,
                        value="REMOTE").pack(side="left", padx=5)

        ttk.Button(src_frame, text="Connection...",
                   command=self._open_ssh_config, width=10).pack(side="right", padx=2)

        list_frame = ttk.Frame(frm)
        list_frame.pack(fill="x", padx=5, pady=5)

        self.lb_dirs = tk.Listbox(list_frame, height=5, selectmode="extended")
        self.lb_dirs.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, command=self.lb_dirs.yview)
        sb.pack(side="right", fill="y")
        self.lb_dirs.config(yscrollcommand=sb.set)

        self.lb_dirs.bind("<<ListboxSelect>>", self._load_style_from_selection)
        self._refresh_dir_listbox()

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill="x", padx=5, pady=2)

        ttk.Button(btn_frame, text="Add Folder...",
                   command=self._add_dir_handler).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Remove", command=self._remove_dir).pack(
            side="left", padx=2)
        ttk.Button(btn_frame, text="Clear", command=self._clear_all_dirs).pack(
            side="right", padx=2)

        ttk.Checkbutton(frm, text="Plot Selected Only",
                        variable=self.var_plot_selected_only).pack(anchor="w", padx=5, pady=(2, 5))

        self._build_style_editor(parent)

    def _build_style_editor(self, parent):
        frm_style = ttk.LabelFrame(parent, text="Style (Applies to Selection)")
        frm_style.pack(fill="x", padx=5, pady=(0, 5))

        sf1 = ttk.Frame(frm_style)
        sf1.pack(fill="x", padx=5, pady=2)
        ttk.Label(sf1, text="Legend:").pack(side="left")
        ttk.Entry(sf1, textvariable=self.var_style_label).pack(
            side="left", fill="x", expand=True, padx=5)

        sf2 = ttk.Frame(frm_style)
        sf2.pack(fill="x", padx=5, pady=2)

        ttk.Label(sf2, text="Color:").pack(side="left")
        cb_color = ttk.Combobox(sf2, textvariable=self.var_style_color, width=8,
                                values=["Auto", "tab:blue", "tab:orange", "tab:green", "tab:red", "black", "grey"])
        cb_color.pack(side="left", padx=2)

        ttk.Label(sf2, text="Line:").pack(side="left", padx=(5, 0))
        cb_ls = ttk.Combobox(sf2, textvariable=self.var_style_ls, width=5, state="readonly",
                             values=["Auto", "-", "--", "-.", ":"])
        cb_ls.pack(side="left", padx=2)

        ttk.Label(sf2, text="Wid:").pack(side="left", padx=(5, 0))
        ttk.Spinbox(sf2, from_=0.5, to=5.0, increment=0.5,
                    textvariable=self.var_style_lw, width=4).pack(side="left", padx=2)

        ttk.Button(sf2, text="Apply", command=self._apply_style).pack(
            side="right", padx=2)

    def _build_layout_controls(self, parent):
        frm = ttk.LabelFrame(parent, text="Grid Layout")
        frm.pack(fill="x", padx=5, pady=5)
        ttk.Label(frm, text="Rows:").pack(side="left", padx=5)
        ttk.Spinbox(frm, from_=1, to=3, textvariable=self.var_rows,
                    width=3).pack(side="left")
        ttk.Label(frm, text="Cols:").pack(side="left", padx=5)
        ttk.Spinbox(frm, from_=1, to=3, textvariable=self.var_cols,
                    width=3).pack(side="left")

    def _build_subplot_config(self, parent):
        frm = ttk.LabelFrame(parent, text="Active Subplot Settings")
        frm.pack(fill="both", expand=True, padx=5, pady=5)

        sel_frame = ttk.Frame(frm)
        sel_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(sel_frame, text="Editing Subplot:").pack(side="left")
        self.cb_subplot_sel = ttk.Combobox(
            sel_frame, state="readonly", width=5)
        self.cb_subplot_sel['values'] = [
            str(i+1) for i in range(self._max_axes)]
        self.cb_subplot_sel.current(0)
        self.cb_subplot_sel.pack(side="left", padx=5)
        self.cb_subplot_sel.bind(
            "<<ComboboxSelected>>", self._on_subplot_selection_change)

        nb = ttk.Notebook(frm)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Data & Axis Tab ---
        tab_axis = ttk.Frame(nb)
        nb.add(tab_axis, text="Data & Axis")

        # Grid Configuration Helper
        r_idx = 0

        def grid_next(pady=2):
            nonlocal r_idx
            r_idx += 1
            return dict(row=r_idx, padx=5, pady=pady, sticky='w')

        # CSV & Mode
        ttk.Label(tab_axis, text="CSV Field:").grid(
            row=0, column=0, sticky='w', padx=5, pady=2)
        ttk.Combobox(tab_axis, textvariable=self.var_edit_field,
                     values=self.result_fields).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(tab_axis, text="Mode:").grid(
            row=1, column=0, sticky='w', padx=5, pady=2)
        ttk.Combobox(tab_axis, textvariable=self.var_edit_mode, values=[
                     "CDF", "CCDF"], state="readonly").grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Separator(tab_axis, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=5)

        # Titles & Labels
        ttk.Label(tab_axis, text="Chart Title:").grid(
            row=3, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(tab_axis, textvariable=self.var_edit_title).grid(
            row=3, column=1, sticky="ew", padx=5)

        ttk.Label(tab_axis, text="X Label:").grid(
            row=4, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(tab_axis, textvariable=self.var_edit_xlabel).grid(
            row=4, column=1, sticky="ew", padx=5)

        ttk.Label(tab_axis, text="Y Label:").grid(
            row=5, column=0, sticky='w', padx=5, pady=2)
        ttk.Entry(tab_axis, textvariable=self.var_edit_ylabel).grid(
            row=5, column=1, sticky="ew", padx=5)

        # Log Scales
        chk_frame = ttk.Frame(tab_axis)
        chk_frame.grid(row=6, column=0, columnspan=2,
                       sticky="w", padx=5, pady=2)
        ttk.Checkbutton(chk_frame, text="Log X", variable=self.var_edit_xlog).pack(
            side="left", padx=(0, 10))
        ttk.Checkbutton(chk_frame, text="Log Y",
                        variable=self.var_edit_ylog).pack(side="left")

        # Shifts & Suffix
        shift_frame = ttk.Frame(tab_axis)
        shift_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Label(shift_frame, text="X Shift:").pack(side="left", padx=5)
        ttk.Entry(shift_frame, textvariable=self.var_edit_xshift,
                  width=6).pack(side="left")
        ttk.Label(shift_frame, text="Legend Suffix:").pack(side="left", padx=5)
        ttk.Entry(shift_frame, textvariable=self.var_edit_leg_suffix).pack(
            side="left", fill="x", expand=True, padx=5)

        ttk.Separator(tab_axis, orient="horizontal").grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=5)

        # --- Axis Limits & Steps ---
        lim_frame = ttk.LabelFrame(
            tab_axis, text="Limits & Steps (Empty = Auto)")
        lim_frame.grid(row=9, column=0, columnspan=2,
                       sticky="ew", padx=5, pady=5)

        # Header
        ttk.Label(lim_frame, text="Min").grid(row=0, column=1, padx=2)
        ttk.Label(lim_frame, text="Max").grid(row=0, column=2, padx=2)
        ttk.Label(lim_frame, text="Step").grid(row=0, column=3, padx=2)

        # X Controls
        ttk.Label(lim_frame, text="X Axis:").grid(
            row=1, column=0, sticky="e", padx=2)
        ttk.Entry(lim_frame, textvariable=self.var_edit_xmin,
                  width=7).grid(row=1, column=1, padx=2)
        ttk.Entry(lim_frame, textvariable=self.var_edit_xmax,
                  width=7).grid(row=1, column=2, padx=2)
        ttk.Entry(lim_frame, textvariable=self.var_edit_xstep,
                  width=7).grid(row=1, column=3, padx=2)

        # Y Controls
        ttk.Label(lim_frame, text="Y Axis:").grid(
            row=2, column=0, sticky="e", padx=2)
        ttk.Entry(lim_frame, textvariable=self.var_edit_ymin,
                  width=7).grid(row=2, column=1, padx=2, pady=2)
        ttk.Entry(lim_frame, textvariable=self.var_edit_ymax,
                  width=7).grid(row=2, column=2, padx=2, pady=2)
        ttk.Entry(lim_frame, textvariable=self.var_edit_ystep,
                  width=7).grid(row=2, column=3, padx=2, pady=2)

        tab_axis.columnconfigure(1, weight=1)

        # --- Criteria Tab ---
        tab_crit = ttk.Frame(nb)
        nb.add(tab_crit, text="Protection Criteria")

        cols = ("enabled", "val", "type", "label")
        self.tv_crit = ttk.Treeview(
            tab_crit, columns=cols, show="headings", height=6)

        self.tv_crit.heading("enabled", text="Status")
        self.tv_crit.column("enabled", width=50, anchor="center")
        self.tv_crit.heading("val", text="Val")
        self.tv_crit.column("val", width=50, anchor="center")
        self.tv_crit.heading("type", text="Type")
        self.tv_crit.column("type", width=80)
        self.tv_crit.heading("label", text="Label")
        self.tv_crit.column("label", width=100)
        self.tv_crit.pack(fill="both", expand=True, padx=5, pady=5)

        self.tv_crit.bind("<Double-1>", self._toggle_criteria)

        btn_crit = ttk.Frame(tab_crit)
        btn_crit.pack(fill="x", padx=5, pady=5)

        ttk.Button(btn_crit, text="Remove",
                   command=self._remove_criteria).pack(side="right")
        ttk.Button(btn_crit, text="Toggle", command=self._toggle_criteria).pack(
            side="right", padx=5)
        ttk.Button(btn_crit, text="Add...", command=self._add_criteria_dialog).pack(
            side="right", padx=5)

    def _build_plot_preview(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(side="top", fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text="Refresh",
                   command=self._update_plot_preview).pack(side="left")
        ttk.Button(toolbar, text="Open Interactive (Browser)",
                   command=self._open_browser).pack(side="right", padx=5)

        self.preview_frame = ttk.Frame(parent, relief="sunken", borderwidth=1)
        self.preview_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.lbl_preview = ttk.Label(
            self.preview_frame, text="Initializing...", anchor="center")
        self.lbl_preview.pack(fill="both", expand=True)

        # --- Loading Bar (Determinate for %) ---
        self.pb_loading = ttk.Progressbar(
            self.preview_frame, mode='determinate', length=200)

        self.preview_frame.bind("<Configure>", self._on_resize)

    # ---------------- SSH Logic ----------------

    def _open_ssh_config(self):
        win = tk.Toplevel(self.frame)
        win.title("SSH Connection Settings")
        win.geometry("300x200")

        ttk.Label(win, text="Host:").pack(pady=2)
        ttk.Entry(win, textvariable=self.var_ssh_host).pack(fill="x", padx=10)

        ttk.Label(win, text="User:").pack(pady=2)
        ttk.Entry(win, textvariable=self.var_ssh_user).pack(fill="x", padx=10)

        ttk.Label(win, text="Password:").pack(pady=2)
        ttk.Entry(win, textvariable=self.var_ssh_pass,
                  show="*").pack(fill="x", padx=10)

        ttk.Label(win, text="Port:").pack(pady=2)
        ttk.Entry(win, textvariable=self.var_ssh_port).pack(fill="x", padx=10)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

    def _get_ssh_client(self):
        cli = getattr(self.app, "ssh_client", None)
        if cli and getattr(cli, "get_transport", None) and cli.get_transport().is_active():
            return cli

        if paramiko is None:
            return None

        try:
            host = self.var_ssh_host.get()
            user = self.var_ssh_user.get()
            pwd = self.var_ssh_pass.get()
            port = int(self.var_ssh_port.get())

            if not host or not user:
                return None

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, port=port, username=user,
                           password=pwd or None, timeout=5)
            self.app.ssh_client = client
            return client
        except Exception as e:
            print(f"SSH Error: {e}")
            return None

    def _remote_dir_picker(self):
        cli = self._get_ssh_client()
        if not cli:
            messagebox.showerror(
                "SSH Error", "Could not connect.\nCheck 'Connection' settings.")
            return None

        try:
            sftp = cli.open_sftp()
        except:
            return None

        win = tk.Toplevel(self.frame)
        win.title("Select Remote Folder(s)")
        win.geometry("600x400")

        cur_path = tk.StringVar(value=self.var_remote_base.get() or ".")

        top = ttk.Frame(win)
        top.pack(fill="x")
        ttk.Entry(top, textvariable=cur_path).pack(
            side="left", fill="x", expand=True)

        tv = ttk.Treeview(win, show="tree", selectmode="extended")
        tv.pack(fill="both", expand=True)

        chosen_paths = []

        def _ls(p):
            tv.delete(*tv.get_children())
            try:
                if p == ".":
                    p = sftp.normalize(".")
                cur_path.set(p)
                for item in sorted(sftp.listdir_attr(p), key=lambda x: x.filename):
                    if stat.S_ISDIR(item.st_mode):
                        tv.insert("", "end", text=item.filename,
                                  values=("DIR",))
            except Exception as e:
                print(e)

        def _enter(_):
            sel = tv.selection()
            if not sel:
                return
            name = tv.item(sel[0])["text"]
            _ls(posixpath.join(cur_path.get(), name))

        def _up():
            _ls(posixpath.dirname(cur_path.get()))

        def _select():
            selection = tv.selection()
            base_p = cur_path.get()

            if not selection:
                chosen_paths.append(base_p)
            else:
                for item_id in selection:
                    name = tv.item(item_id)["text"]
                    chosen_paths.append(posixpath.join(base_p, name))

            self.var_remote_base.set(base_p)
            win.destroy()

        tv.bind("<Double-1>", _enter)
        btn = ttk.Frame(win)
        btn.pack(fill="x")
        ttk.Button(btn, text="Up Level", command=_up).pack(side="left")
        ttk.Button(btn, text="Select Selected Folder(s)",
                   command=_select).pack(side="right")

        _ls(cur_path.get())
        win.wait_window()
        sftp.close()
        return chosen_paths if chosen_paths else None

    # ---------------- Data Handling ----------------

    def _sync_remote_file(self, tag, field):
        if not tag.startswith("ssh://"):
            return tag

        remote_path = tag[6:]
        fname = f"{field}.csv"

        base = getattr(self.app, "var_outdir", None)
        base = base.get() if (base and hasattr(base, "get")) else os.getcwd()

        safe_name = remote_path.strip("/").replace("/", "__").replace(":", "_")
        local_dir = os.path.join(base, "_remote_cache", safe_name)
        os.makedirs(local_dir, exist_ok=True)

        local_file = os.path.join(local_dir, fname)

        if not (os.path.exists(local_file) and os.path.getsize(local_file) > 0):
            cli = self._get_ssh_client()
            if cli:
                try:
                    sftp = cli.open_sftp()
                    rem_file = posixpath.join(remote_path, fname)
                    sftp.get(rem_file, local_file)
                    sftp.close()
                except Exception as e:
                    print(f"Sync failed for {fname}: {e}")

        return local_dir

    def _get_data(self, folder_tag, field):
        local_folder = self._sync_remote_file(folder_tag, field)
        fpath = os.path.join(local_folder, f"{field}.csv")

        if not os.path.exists(fpath):
            return None

        try:
            mtime = os.path.getmtime(fpath)
            key = (local_folder, field)
            if key in self._data_cache:
                cm, data = self._data_cache[key]
                if cm == mtime:
                    return data

            df = pd.read_csv(fpath)
            if df.empty:
                return None

            target = [c for c in df.columns if field.lower() in c.lower()
                      or "value" in c.lower()]
            data = None
            if target:
                data = df[target[0]].dropna().values
            elif df.shape[1] > 0:
                data = df.iloc[:, 0].dropna().values

            if data is not None:
                self._data_cache[key] = (mtime, data)
                return data

        except Exception as e:
            print(f"Read error: {e}")
        return None

    def _compute_ecdf(self, x, ccdf=False):
        x = np.sort(x)
        n = x.size
        if n == 0:
            return [], []
        y = np.arange(1, n+1)/n
        if ccdf:
            y = 1.0 - y
        return x, y

    # ---------------- UI Events ----------------

    def _load_style_from_selection(self, event=None):
        sel = self.lb_dirs.curselection()
        if not sel:
            return

        idx = sel[0]
        if idx < len(self.app.res_dirs):
            path = self.app.res_dirs[idx]
            style = self.app.res_styles.get(path, {})

            self.var_style_label.set(style.get("label", ""))
            self.var_style_color.set(style.get("color", "Auto"))
            self.var_style_ls.set(style.get("linestyle", "Auto"))
            self.var_style_lw.set(style.get("linewidth", 1.5))

    def _apply_style(self):
        sel = self.lb_dirs.curselection()
        if not sel:
            return

        label = self.var_style_label.get().strip()
        color = self.var_style_color.get()
        ls = self.var_style_ls.get()
        lw = self.var_style_lw.get()

        for idx in sel:
            if idx < len(self.app.res_dirs):
                path = self.app.res_dirs[idx]
                if path not in self.app.res_styles:
                    self.app.res_styles[path] = {}

                if label:
                    self.app.res_styles[path]["label"] = label
                self.app.res_styles[path]["color"] = color
                self.app.res_styles[path]["linestyle"] = ls
                self.app.res_styles[path]["linewidth"] = float(lw)

        self._schedule_update()

    def _on_subplot_selection_change(self, event=None):
        try:
            idx = int(self.cb_subplot_sel.get()) - 1
        except:
            idx = 0
        self.var_current_subplot_idx.set(idx)
        self._load_subplot_config_to_ui()

    def _load_subplot_config_to_ui(self):
        idx = self.var_current_subplot_idx.get()
        cfg = self._axes_cfg[idx]
        self._disable_traces = True

        self.var_edit_field.set(cfg["field"])
        self.var_edit_mode.set(cfg["mode"])
        self.var_edit_title.set(cfg.get("title", ""))
        self.var_edit_xlabel.set(cfg.get("x_label", ""))
        self.var_edit_ylabel.set(cfg.get("y_label", ""))
        self.var_edit_xlog.set(cfg.get("x_log", False))
        self.var_edit_ylog.set(cfg.get("y_log", False))
        self.var_edit_leg_suffix.set(cfg.get("legend_suffix", ""))
        self.var_edit_xshift.set(cfg.get("x_shift", 0.0))

        # Limits
        self.var_edit_xmin.set(cfg.get("x_min", ""))
        self.var_edit_xmax.set(cfg.get("x_max", ""))
        self.var_edit_xstep.set(cfg.get("x_step", ""))
        self.var_edit_ymin.set(cfg.get("y_min", ""))
        self.var_edit_ymax.set(cfg.get("y_max", ""))
        self.var_edit_ystep.set(cfg.get("y_step", ""))

        self._refresh_criteria_list(cfg.get("criteria", []))
        self._disable_traces = False

    def _on_config_change(self, *args):
        if self._disable_traces:
            return
        idx = self.var_current_subplot_idx.get()
        cfg = self._axes_cfg[idx]

        cfg["field"] = self.var_edit_field.get()
        cfg["mode"] = self.var_edit_mode.get()
        cfg["title"] = self.var_edit_title.get()
        cfg["x_label"] = self.var_edit_xlabel.get()
        cfg["y_label"] = self.var_edit_ylabel.get()
        cfg["x_log"] = self.var_edit_xlog.get()
        cfg["y_log"] = self.var_edit_ylog.get()
        cfg["legend_suffix"] = self.var_edit_leg_suffix.get()

        cfg["x_min"] = self.var_edit_xmin.get()
        cfg["x_max"] = self.var_edit_xmax.get()
        cfg["x_step"] = self.var_edit_xstep.get()
        cfg["y_min"] = self.var_edit_ymin.get()
        cfg["y_max"] = self.var_edit_ymax.get()
        cfg["y_step"] = self.var_edit_ystep.get()

        try:
            cfg["x_shift"] = self.var_edit_xshift.get()
        except:
            pass
        self._schedule_update()

    # ---------------- File List ----------------

    def _refresh_dir_listbox(self):
        self.lb_dirs.delete(0, "end")
        for p in self.app.res_dirs:
            display = p
            if p.startswith("ssh://"):
                display = f"[SSH] {os.path.basename(p)}"
            else:
                display = os.path.basename(os.path.normpath(p))
            if not display:
                display = p
            self.lb_dirs.insert("end", display)

    def _add_dir_handler(self):
        if self.var_source_mode.get() == "REMOTE":
            if paramiko is None:
                messagebox.showerror("Error", "Paramiko library missing.")
                return

            chosen_paths = self._remote_dir_picker()
            if chosen_paths:
                for p in chosen_paths:
                    full_p = f"ssh://{p}"
                    if full_p not in self.app.res_dirs:
                        self.app.res_dirs.append(full_p)
        else:
            start = getattr(self, "_last_dir", os.getcwd())
            path = filedialog.askdirectory(initialdir=start)
            if path:
                self._last_dir = path
                if path not in self.app.res_dirs:
                    self.app.res_dirs.append(path)

        self._refresh_dir_listbox()
        self._schedule_update()

    def _remove_dir(self):
        sel = list(self.lb_dirs.curselection())
        for i in reversed(sel):
            del self.app.res_dirs[i]
        self._refresh_dir_listbox()
        self._schedule_update()

    def _clear_all_dirs(self):
        self.app.res_dirs.clear()
        self.app.res_styles.clear()
        self._refresh_dir_listbox()
        self._schedule_update()

    # ---------------- Criteria ----------------

    def _refresh_criteria_list(self, criteria_list):
        self.tv_crit.delete(*self.tv_crit.get_children())
        for i, c in enumerate(criteria_list):
            status = "On" if c.get("enabled", True) else "Off"
            self.tv_crit.insert("", "end", iid=str(i), values=(
                status, c.get("val"), c.get("type"), c.get("label")))

    def _add_criteria_dialog(self):
        idx = self.var_current_subplot_idx.get()
        cfg = self._axes_cfg[idx]

        win = tk.Toplevel(self.frame)
        win.title("Add Protection Criteria")
        win.geometry("320x300")

        v_val = tk.DoubleVar()
        v_type = tk.StringVar(value="Vertical (X)")
        v_label = tk.StringVar()
        v_color = tk.StringVar(value="red")

        ttk.Label(win, text="Value:").pack(pady=(5, 0))
        ttk.Entry(win, textvariable=v_val).pack()
        ttk.Label(win, text="Type:").pack(pady=(5, 0))
        ttk.Combobox(win, textvariable=v_type, values=[
                     "Vertical (X)", "Horizontal (Prob)"], state="readonly").pack()
        ttk.Label(win, text="Label:").pack(pady=(5, 0))
        ttk.Entry(win, textvariable=v_label).pack()
        ttk.Label(win, text="Color:").pack(pady=(5, 0))
        ttk.Combobox(win, textvariable=v_color, values=[
                     "red", "green", "blue", "black", "orange"]).pack()

        def _apply():
            try:
                cfg["criteria"].append({
                    "val": v_val.get(), "type": v_type.get(),
                    "label": v_label.get(), "color": v_color.get(), "enabled": True
                })
                self._refresh_criteria_list(cfg["criteria"])
                self._schedule_update()
            except:
                messagebox.showerror("Error", "Invalid Number")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=15)

        ttk.Button(btn_frame, text="Apply", command=_apply).pack(side="left")
        ttk.Button(btn_frame, text="Close",
                   command=win.destroy).pack(side="right")

    def _toggle_criteria(self, event=None):
        sel = self.tv_crit.selection()
        if not sel:
            return

        idx_crit = int(sel[0])
        idx_subplot = self.var_current_subplot_idx.get()
        cfg = self._axes_cfg[idx_subplot]

        current_state = cfg["criteria"][idx_crit].get("enabled", True)
        cfg["criteria"][idx_crit]["enabled"] = not current_state

        self._refresh_criteria_list(cfg["criteria"])
        self._schedule_update()

    def _remove_criteria(self):
        sel = self.tv_crit.selection()
        if not sel:
            return
        idx = self.var_current_subplot_idx.get()
        cfg = self._axes_cfg[idx]
        cfg["criteria"].pop(int(sel[0]))
        self._refresh_criteria_list(cfg["criteria"])
        self._schedule_update()

    # ---------------- Plotting ----------------

    def _schedule_update(self):
        if hasattr(self, "_update_timer") and self._update_timer:
            self.app.after_cancel(self._update_timer)
        self._update_timer = self.app.after(300, self._update_plot_preview)

    def _on_resize(self, event):
        if hasattr(self, "_resize_timer") and self._resize_timer:
            self.app.after_cancel(self._resize_timer)
        self._resize_timer = self.app.after(800, self._update_plot_preview)

    def _create_plotly_fig(self, progress_callback=None):
        rows = max(1, self.var_rows.get())
        cols = max(1, self.var_cols.get())
        n_plots = min(rows*cols, self._max_axes)

        # Calculate Total Steps for Progress
        total_steps = n_plots * max(1, len(self.app.res_dirs))
        current_step = 0

        titles = []
        for i in range(n_plots):
            cfg = self._axes_cfg[i]
            t = cfg.get("title")
            if not t:
                t = RESULT_FIELDNAME_TO_PLOT_INFO.get(
                    cfg["field"], {}).get("title", cfg["field"])
            titles.append(t)

        fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles,
                            vertical_spacing=0.12, horizontal_spacing=0.08)

        dash_map = {
            "-": "solid",
            "--": "dash",
            "-.": "dashdot",
            ":": "dot",
            "Auto": None
        }

        color_map = {
            "tab:blue": "#1f77b4", "tab:orange": "#ff7f0e", "tab:green": "#2ca02c",
            "tab:red": "#d62728", "tab:purple": "#9467bd", "tab:brown": "#8c564b",
            "tab:pink": "#e377c2", "tab:gray": "#7f7f7f", "tab:olive": "#bcbd22", "tab:cyan": "#17becf"
        }

        selected_indices = self.lb_dirs.curselection()
        plot_selected_only = self.var_plot_selected_only.get()

        for i in range(n_plots):
            cfg = self._axes_cfg[i]
            r, c = (i // cols) + 1, (i % cols) + 1
            field = cfg["field"]

            for dir_idx, folder in enumerate(self.app.res_dirs):
                # -- Progress Update --
                current_step += 1
                if progress_callback and total_steps > 0:
                    pct = (current_step / total_steps) * 90.0
                    progress_callback(pct)

                if plot_selected_only and (dir_idx not in selected_indices):
                    continue

                data = self._get_data(folder, field)
                if data is None or len(data) == 0:
                    continue

                x, y = self._compute_ecdf(data, ccdf=(cfg["mode"] == "CCDF"))
                x = x + cfg.get("x_shift", 0.0)

                if cfg["x_log"]:
                    x, y = x[x > 0], y[x > 0]
                if cfg["y_log"]:
                    x, y = x[y > 0], y[y > 0]

                if len(x) == 0:
                    continue

                style = self.app.res_styles.get(folder, {})

                custom_label = style.get("label", "")
                if custom_label:
                    name = custom_label
                else:
                    name = os.path.basename(
                        folder) if "ssh://" not in folder else f"[SSH] {os.path.basename(folder)}"
                name += cfg.get('legend_suffix', '')

                line_props = dict(width=style.get("linewidth", 1.5))

                ls_val = style.get("linestyle", "Auto")
                if ls_val in dash_map and dash_map[ls_val]:
                    line_props["dash"] = dash_map[ls_val]

                c_val = style.get("color", "Auto")
                if c_val != "Auto":
                    line_props["color"] = color_map.get(c_val, c_val)

                trace_type = go.Scattergl if len(x) > 10000 else go.Scatter
                fig.add_trace(trace_type(
                    x=x, y=y,
                    mode='lines',
                    name=name,
                    line=line_props,
                    legendgroup=folder,
                    showlegend=(i == 0)
                ), row=r, col=c)

            for crit in cfg.get("criteria", []):
                if not crit.get("enabled", True):
                    continue

                try:
                    val = float(crit["val"])
                    color = crit.get("color", "red")
                    if "Vertical" in crit["type"]:
                        fig.add_vline(x=val, line_dash="dash", line_color=color,
                                      annotation_text=crit.get("label"), row=r, col=c)
                    else:
                        fig.add_hline(y=val, line_dash="dash", line_color=color,
                                      annotation_text=crit.get("label"), row=r, col=c)
                except:
                    pass

            xlab = cfg.get("x_label") or field
            ylab = cfg.get("y_label") or f"Prob ({cfg['mode']})"

            # Prepare Axis Params
            xaxis_params = dict(
                title_text=xlab,
                type="log" if cfg["x_log"] else "linear",
                showgrid=True
            )
            yaxis_params = dict(
                title_text=ylab,
                type="log" if cfg["y_log"] else "linear",
                showgrid=True
            )

            # Apply limits if valid floats
            try:
                xmin = float(cfg.get("x_min", ""))
                xmax = float(cfg.get("x_max", ""))
                xaxis_params["range"] = [xmin, xmax]
            except ValueError:
                pass  # Auto

            try:
                ymin = float(cfg.get("y_min", ""))
                ymax = float(cfg.get("y_max", ""))
                yaxis_params["range"] = [ymin, ymax]
            except ValueError:
                pass  # Auto

            # Apply Steps (dtick) with Smart Scaling
            try:
                xstep = float(cfg.get("x_step", ""))
                if xstep > 0:
                    xaxis_params["dtick"] = xstep
                    # If step is small and axis is linear, try percentage formatting
                    if not cfg["x_log"] and xstep < 1.0:
                        # Auto-detect precision: 0.01 -> 0 dec, 0.001 -> 1 dec
                        decimals = max(
                            0, int(math.ceil(-math.log10(xstep)) - 2))
                        xaxis_params["tickformat"] = f".{decimals}%"
            except ValueError:
                pass

            try:
                ystep = float(cfg.get("y_step", ""))
                if ystep > 0:
                    yaxis_params["dtick"] = ystep
                    # If step is small and axis is linear, try percentage formatting
                    if not cfg["y_log"] and ystep < 1.0:
                        decimals = max(
                            0, int(math.ceil(-math.log10(ystep)) - 2))
                        yaxis_params["tickformat"] = f".{decimals}%"
            except ValueError:
                pass

            fig.update_xaxes(xaxis_params, row=r, col=c)
            fig.update_yaxes(yaxis_params, row=r, col=c)

        fig.update_layout(template="plotly_white", margin=dict(l=50, r=20, t=50, b=50),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        return fig

    def _update_plot_preview(self):
        if self._plot_preview_job and self._plot_preview_job.is_alive():
            return
        w = max(400, min(self.lbl_preview.winfo_width(), 1920))
        h = max(300, min(self.lbl_preview.winfo_height(), 1080))

        # Start Loading UI
        self.lbl_preview.configure(text="Initializing...")
        self.pb_loading['value'] = 0  # Reset
        self.pb_loading.place(relx=0.5, rely=0.5, anchor="center")

        self._plot_preview_job = threading.Thread(
            target=self._render_worker, args=(w, h))
        self._plot_preview_job.daemon = True
        self._plot_preview_job.start()

    def _stop_loading_ui(self):
        """Helper to stop the progress bar."""
        self.pb_loading.stop()
        self.pb_loading.place_forget()

    def _on_render_error(self, msg):
        """Helper to handle render errors on main thread."""
        self._stop_loading_ui()
        self.lbl_preview.configure(text=msg)

    def _update_progress_ui(self, percent):
        """Updates progress bar from thread."""
        self.pb_loading['value'] = percent
        self.lbl_preview.configure(
            text=f"Generating Traces... {int(percent)}%")

    def _render_worker(self, w, h):
        def _progress(p):
            # Update progress bar on main thread
            self.app.after(0, self._update_progress_ui, p)

        try:
            fig = self._create_plotly_fig(progress_callback=_progress)

            # Indicate final phase
            self.app.after(0, lambda: self.lbl_preview.configure(
                text="Rasterizing... (may take a moment)"))
            self.app.after(0, lambda: self.pb_loading.configure(value=95))

            img_bytes = fig.to_image(format="png", width=w, height=h, scale=1)
            self.app.after(0, self._display_image, img_bytes)
        except ImportError:
            self.app.after(0, self._on_render_error,
                           "Install 'kaleido' for static preview.\nUse 'Open Interactive' for now.")
        except Exception as e:
            self.app.after(0, self._on_render_error,
                           f"Render Error:\n{e}")

    def _display_image(self, img_bytes):
        self._stop_loading_ui()
        try:
            pil = Image.open(io.BytesIO(img_bytes))
            self._photo_image = ImageTk.PhotoImage(pil)
            self.lbl_preview.configure(image=self._photo_image, text="")
        except:
            pass

    def _open_browser(self):
        try:
            fig = self._create_plotly_fig()
            import tempfile
            fd, path = tempfile.mkstemp(suffix=".html")
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(fig.to_html(include_plotlyjs='cdn'))
            webbrowser.open(f"file://{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
