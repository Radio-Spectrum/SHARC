"""
Results tab builder: folder selection and subplot configuration UI.
Actual plotting code should be implemented in plotting/results_plot.py.
"""

import tkinter as tk
from tkinter import ttk, filedialog


def build_results_tab(app: tk.Tk, root: tk.Widget) -> None:
    left = ttk.Frame(root)
    right = ttk.Frame(root)
    left.pack(side="left", fill="y")
    right.pack(side="right", fill="both", expand=True)

    ttk.Label(left, text="Result folders (comparison):").pack(anchor="w", pady=(6, 2))
    frm_dirs = ttk.Frame(left)
    frm_dirs.pack(fill="x")
    app.lb_dirs = tk.Listbox(frm_dirs, height=6, selectmode="extended")
    app.lb_dirs.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(frm_dirs, orient="vertical", command=app.lb_dirs.yview)
    sb.pack(side="right", fill="y")
    app.lb_dirs.config(yscrollcommand=sb.set)

    def _add_dir() -> None:
        path = filedialog.askdirectory(initialdir=".")
        if path and path not in app.res_dirs:
            app.res_dirs.append(path)
            app.lb_dirs.insert("end", path)

    def _remove_dir() -> None:
        selected = list(app.lb_dirs.curselection())[::-1]
        for idx in selected:
            path = app.lb_dirs.get(idx)
            app.res_dirs.remove(path)
            app.lb_dirs.delete(idx)

    frm_btn = ttk.Frame(left)
    frm_btn.pack(fill="x", pady=(4, 8))
    ttk.Button(frm_btn, text="Add folder...", command=_add_dir).pack(side="left", padx=(0, 4))
    ttk.Button(frm_btn, text="Remove selected", command=_remove_dir).pack(side="left")

    # Layout controls for subplots
    frm_grid = ttk.LabelFrame(left, text="Subplot layout")
    frm_grid.pack(fill="x", pady=(6, 6))
    ttk.Label(frm_grid, text="Rows").grid(row=0, column=0, padx=4, pady=4, sticky="w")
    ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=app.var_rows, width=5, command=lambda: None).grid(
        row=0, column=1, padx=4, pady=4
    )
    ttk.Label(frm_grid, text="Columns").grid(row=0, column=2, padx=4, pady=4, sticky="w")
    ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=app.var_cols, width=5, command=lambda: None).grid(
        row=0, column=3, padx=4, pady=4
    )

    # Placeholder area for figure: implement plotting in plotting/results_plot.py
    fig_frame = ttk.LabelFrame(right, text="Figure (to be implemented)")
    fig_frame.pack(fill="both", expand=True, padx=6, pady=6)
    ttk.Label(fig_frame, text="Results plotting will appear here. Move plot code to plotting/results_plot.py.").pack(
        padx=8, pady=8
    )
