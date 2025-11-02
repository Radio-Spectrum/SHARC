"""
Runner tab builder: UI to select YAML files and control simulation runs.
Heavy runner logic (process management, threading) should be implemented in core/runner.py later.
"""

from tkinter import ttk, filedialog
import tkinter as tk
import os


def build_runner_tab(app: tk.Tk, root: tk.Widget) -> None:
    top = ttk.Frame(root)
    top.pack(fill="x")
    ttk.Label(top, text="Folder with .yaml files").pack(side="left")
    e = ttk.Entry(top, textvariable=app.run_folder)
    e.pack(side="left", fill="x", expand=True, padx=6)
    ttk.Button(top, text="Choose...", command=lambda: _pick_folder(app)).pack(side="left")
    ttk.Button(top, text="Refresh list", command=lambda: _scan_yaml_files(app)).pack(side="left", padx=(6, 0))
    ttk.Label(top, text="Parallel (max runs):").pack(side="left", padx=(14, 4))
    ttk.Spinbox(top, from_=1, to=32, width=4, textvariable=app.var_max_workers).pack(side="left")

    # Tree for files + progress
    mid = ttk.Frame(root)
    mid.pack(fill="both", expand=True, pady=(8, 0))
    app.tree = ttk.Treeview(mid, columns=("yaml", "status", "snap", "pct", "eta"), show="headings", height=12)
    app.tree.heading("yaml", text="YAML")
    app.tree.heading("status", text="Status")
    app.tree.heading("snap", text="Snapshots (done/total)")
    app.tree.heading("pct", text="%")
    app.tree.heading("eta", text="ETA")
    app.tree.column("yaml", width=380)
    app.tree.column("status", width=220)
    app.tree.column("snap", width=180)
    app.tree.column("pct", width=60, anchor="e")
    app.tree.column("eta", width=120)
    app.tree.pack(side="left", fill="both", expand=True)

    sb = ttk.Scrollbar(mid, orient="vertical", command=app.tree.yview)
    sb.pack(side="left", fill="y")
    app.tree.configure(yscroll=sb.set)

    right = ttk.Frame(root)
    right.pack(fill="x", pady=(8, 0))
    app.main_cli_path = ttk.Entry(right, width=44)
    app.main_cli_path.pack(side="left", padx=6, fill="x", expand=True)
    ttk.Button(right, text="Stop selected", command=lambda: None).pack(side="right", padx=(6, 0))
    ttk.Button(right, text="Run selected", command=lambda: None).pack(side="right")

    # Log frame
    logf = ttk.LabelFrame(root, text="Log")
    logf.pack(fill="both", expand=True, pady=(8, 0))
    app.txt_log = tk.Text(logf, height=10, wrap="none")
    app.txt_log.pack(fill="both", expand=True)

    # Initial scan
    _scan_yaml_files(app)


def _pick_folder(app: tk.Tk) -> None:
    path = filedialog.askdirectory(initialdir=app.run_folder.get() or ".")
    if path:
        app.run_folder.set(path)
        _scan_yaml_files(app)


def _scan_yaml_files(app: tk.Tk) -> None:
    """Populate the tree with .yaml/.yml files found in the selected folder."""
    folder = app.run_folder.get()
    app.tree.delete(*app.tree.get_children())
    if not os.path.isdir(folder):
        return
    for filename in sorted(os.listdir(folder)):
        if filename.lower().endswith((".yaml", ".yml")):
            app.tree.insert("", "end", values=(filename, "idle", "0/0", "0", ""))
