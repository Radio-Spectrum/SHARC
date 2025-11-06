import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from utils.results_plot import _draw_results_plots, _export_results_fig, _ref_add, _ref_remove
from utils.res_schedule import _schedule_auto_update

# Note: The original code assumes 'plt', 'FigureCanvasTkAgg', 
# and 'Path' have been imported. I've added them for completeness.

def build_results_tab(self, root):
    """Builds the 'Results' tab UI elements."""
    
    def draw_results_plots():
        return _draw_results_plots(root)
    
    def schedule_auto_update():
        return _schedule_auto_update(root)
    
    def export_results_fig():
        return _export_results_fig(root)
    
    def ref_add():
        return _ref_add(root)
    
    def ref_remove():
        return _ref_remove(root)

    # Left side: controls / Right side: figure
    left = ttk.Frame(root)
    right = ttk.Frame(root)
    left.pack(side="left", fill="y")
    right.pack(side="right", fill="both", expand=True)

    # ---- Folder selection ----
    ttk.Label(left, text="Result folders (comparison):").pack(anchor="w", pady=(6, 2))
    frm_dirs = ttk.Frame(left)
    frm_dirs.pack(fill="x")
    root.lb_dirs = tk.Listbox(frm_dirs, height=6, selectmode="extended")
    root.lb_dirs.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(frm_dirs, orient="vertical", command=root.lb_dirs.yview)
    sb.pack(side="right", fill="y")
    root.lb_dirs.config(yscrollcommand=sb.set)

    def _add_dir():
        init = str(Path(root.var_outdir.get() or Path.cwd()))
        path = filedialog.askdirectory(initialdir=init, title="Select results folder")
        if path and path not in root.res_dirs:
            root.res_dirs.append(path)
            root.lb_dirs.insert("end", path)
            draw_results_plots()

    def _add_current_outdir():
        path = str(Path(root.var_outdir.get()))
        if path and path not in root.res_dirs:
            root.res_dirs.append(path)
            root.lb_dirs.insert("end", path)
            draw_results_plots()

    def _remove_dir():
        sel = list(root.lb_dirs.curselection())[::-1]
        for idx in sel:
            path = root.lb_dirs.get(idx)
            root.res_dirs.remove(path)
            root.lb_dirs.delete(idx)
        draw_results_plots()

    frm_btn = ttk.Frame(left)
    frm_btn.pack(fill="x", pady=(4, 8))
    ttk.Button(frm_btn, text="Add folder…", command=_add_dir).pack(side="left", padx=(0, 4))
    ttk.Button(frm_btn, text="Use current output_dir", command=_add_current_outdir).pack(side="left", padx=(0, 4))
    ttk.Button(frm_btn, text="Remove selected", command=_remove_dir).pack(side="left")

    # ---- Subplot grid ----
    frm_grid = ttk.LabelFrame(left, text="Subplot Layout")
    frm_grid.pack(fill="x", pady=(6, 6))
    ttk.Label(frm_grid, text="Rows").grid(row=0, column=0, padx=4, pady=4, sticky="w")
    ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=root.var_rows, width=5, command=draw_results_plots).grid(row=0, column=1, padx=4, pady=4)
    ttk.Label(frm_grid, text="Columns").grid(row=0, column=2, padx=4, pady=4, sticky="w")
    ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=root.var_cols, width=5, command=draw_results_plots).grid(row=0, column=3, padx=4, pady=4)

    # ---- Configuration per subplot (up to _max_axes)
    frm_cfg = ttk.LabelFrame(left, text="Subplot Configuration")
    frm_cfg.pack(fill="x", pady=(6, 8))
    root._subplot_cfg_rows = []
    for i in range(root._max_axes):
        r = ttk.Frame(frm_cfg)
        r.pack(fill="x", pady=2)
        ttk.Label(r, text=f"{i+1:02d}").pack(side="left", padx=(2, 6))

        # METRIC
        cb_field = ttk.Combobox(r, values=root.result_fields, width=34)
        cb_field.set(root._axes_cfg[i]["field"])
        cb_field.pack(side="left", padx=(0, 6))

        # CDF/CCDF
        cb_mode = ttk.Combobox(r, values=["CDF", "CCDF"], width=6)
        cb_mode.set(root._axes_cfg[i]["mode"])
        cb_mode.pack(side="left", padx=(0, 6))

        # Y-SCALE (Linear/Log)
        cb_ys = ttk.Combobox(r, values=["Linear", "Log"], width=7)
        cb_ys.set(root._axes_cfg[i]["yscale"])
        cb_ys.pack(side="left", padx=(0, 6))

        # REFERENCES (%, e.g.: 5,10,50)
        ttk.Label(r, text="Refs(%)").pack(side="left")
        ent_refs = ttk.Entry(r, width=10)
        ent_refs.insert(0, root._axes_cfg[i]["refs"])
        ent_refs.pack(side="left", padx=(4, 6))

        def _mk_upd(idx, combof, combom, comboys, entryrefs):
            def _upd(*_):
                root._axes_cfg[idx]["field"] = combof.get()
                root._axes_cfg[idx]["mode"] = combom.get()
                root._axes_cfg[idx]["yscale"] = comboys.get()
                root._axes_cfg[idx]["refs"] = entryrefs.get()
                root._draw_results_plots()
            return _upd

        upd = _mk_upd(i, cb_field, cb_mode, cb_ys, ent_refs)
        cb_field.bind("<<ComboboxSelected>>", upd)
        cb_mode.bind("<<ComboboxSelected>>", upd)
        cb_ys.bind("<<ComboboxSelected>>", upd)
        ent_refs.bind("<FocusOut>", upd)
        ent_refs.bind("<Return>", upd)

        root._subplot_cfg_rows.append((cb_field, cb_mode, cb_ys, ent_refs))

    # ---- Automatic update ----
    frm_auto = ttk.LabelFrame(left, text="Update")
    frm_auto.pack(fill="x", pady=(6, 8))
    ttk.Checkbutton(frm_auto, text="Automatic update", variable=root.var_auto_update,
                    command=schedule_auto_update).pack(side="left", padx=(4, 8))
    ttk.Label(frm_auto, text="Period (ms):").pack(side="left")
    ttk.Spinbox(frm_auto, from_=500, to=10000, increment=500, textvariable=root.var_update_period_ms, width=8,
                command=schedule_auto_update).pack(side="left", padx=(4, 8))
    ttk.Button(frm_auto, text="Update now", command=draw_results_plots).pack(side="left")

    # ---- Export figure ----
    frm_export = ttk.LabelFrame(left, text="Export")
    frm_export.pack(fill="x", pady=(6, 8))
    ttk.Label(frm_export, text="DPI:").pack(side="left", padx=(6, 4))
    root.var_export_dpi = tk.IntVar(value=200)
    ttk.Spinbox(frm_export, from_=100, to=600, increment=50, textvariable=root.var_export_dpi, width=6).pack(side="left", padx=(0, 8))
    ttk.Button(frm_export, text="Export figure…", command=export_results_fig).pack(side="left")
    
    # ---- Scale / Export ----
    frm_extras = ttk.LabelFrame(left, text="Scale and Export")
    frm_extras.pack(fill="x", pady=(6, 8))

    # Log scale on X
    ttk.Checkbutton(
        frm_extras, text="Log scale on X-axis",
        variable=root.var_xlog,
        command=draw_results_plots
    ).pack(fill="x", padx=4, pady=(2, 6))

    # Export figure
    fexp = ttk.Frame(frm_extras)
    fexp.pack(fill="x", pady=(2, 4))
    ttk.Label(fexp, text="Format:").pack(side="left")
    ttk.Combobox(
        fexp, textvariable=root.var_export_fmt,
        values=["PNG", "SVG", "PDF"], width=6, state="readonly"
    ).pack(side="left", padx=(4, 8))
    ttk.Label(fexp, text="DPI:").pack(side="left")
    ttk.Spinbox(
        fexp, from_=72, to=600, increment=10, width=6,
        textvariable=root.var_export_dpi
    ).pack(side="left", padx=(4, 8))
    # ttk.Button(fexp, text="Export figure…", command=root._export_results_figure).pack(side="left")

    # ---- Reference lines (global) ----
    frm_refs = ttk.LabelFrame(left, text="Reference Lines (all subplots)")
    frm_refs.pack(fill="x", pady=(6, 8))

    ref_row = ttk.Frame(frm_refs)
    ref_row.pack(fill="x", pady=(2, 4))
    ttk.Label(ref_row, text="x=").pack(side="left")
    root._ref_x_entry = ttk.Entry(ref_row, width=10)
    root._ref_x_entry.pack(side="left", padx=(4, 8))
    ttk.Label(ref_row, text="label:").pack(side="left")
    root._ref_label_entry = ttk.Entry(ref_row, width=18)
    root._ref_label_entry.pack(side="left", padx=(4, 8))
    ttk.Button(ref_row, text="Add", command=ref_add).pack(side="left")

    # list of lines
    list_frame = ttk.Frame(frm_refs)
    list_frame.pack(fill="x", pady=(2, 4))
    root.lb_refs = tk.Listbox(list_frame, height=5, selectmode="extended")
    root.lb_refs.pack(side="left", fill="both", expand=True)
    sb2 = ttk.Scrollbar(list_frame, orient="vertical", command=root.lb_refs.yview)
    sb2.pack(side="right", fill="y")
    root.lb_refs.config(yscrollcommand=sb2.set)

    btns = ttk.Frame(frm_refs)
    btns.pack(fill="x")
    ttk.Button(btns, text="Remove selected", command=ref_remove).pack(side="left")
    ttk.Button(btns, text="Apply (redraw)", command=draw_results_plots).pack(side="left", padx=(6, 0))

    # ---- Results figure (matplotlib)
    root.fig_res = plt.figure(figsize=(7.8, 6.2))
    root.canvas_res = FigureCanvasTkAgg(root.fig_res, master=right)
    root.canvas_res.get_tk_widget().pack(fill="both", expand=True)

    draw_results_plots()
    schedule_auto_update()