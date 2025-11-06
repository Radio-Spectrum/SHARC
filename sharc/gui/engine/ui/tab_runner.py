import tkinter as tk
from tkinter import ttk
import os
from pathlib import Path

from core.yaml_tools import _scan_yaml_files
from core.files_control import _pick_folder
from core.run_data.run_handler import _stop_selected, _run_selected_yaml_parallel, _drain_log_queue

# Note: The original code assumes 'os' and 'Path' 
# have been imported. I've added them for completeness.

def build_runner_tab(self, root):
    """Builds the 'Runner' tab UI elements."""

    def pick_folder():
        return _pick_folder(root)
    
    def scan_yaml_files():
        return _scan_yaml_files(root)
    
    def stop_selected():
        return _stop_selected(root)
    
    def run_selected_yaml_parallel():
        return _run_selected_yaml_parallel(root)
    
    def drain_log_queue():
        return _drain_log_queue(root)
    
    def runner_scheduler_tick():
        return _drain_log_queue(root)
    
    top = ttk.Frame(root)
    top.pack(fill="x")
    root.run_folder = tk.StringVar(value=os.path.join(Path.cwd(), "/sharc/campaigns"))
    ttk.Label(top, text="Folder with .yaml files").pack(side="left")
    e = ttk.Entry(top, textvariable=root.run_folder)
    e.pack(side="left", fill="x", expand=True, padx=6)
    ttk.Button(top, text="Browse...", command=lambda: _pick_folder(root, root.run_folder)).pack(side="left")
    ttk.Button(top, text="Refresh list", command=scan_yaml_files).pack(side="left", padx=(6, 0))
    ttk.Label(top, text="Parallel (max runs):").pack(side="left", padx=(14, 4))
    tk.Spinbox(top, from_=1, to=32, width=4, textvariable=root.var_max_workers).pack(side="left")

    # Tree for files + progress
    mid = ttk.Frame(root)
    mid.pack(fill="both", expand=True, pady=(8, 0))
    root.tree = ttk.Treeview(mid, columns=("yaml", "status", "snap", "pct", "eta"), show="headings", height=12)
    root.tree.heading("yaml", text="YAML")
    root.tree.heading("status", text="Status")
    root.tree.heading("snap", text="Snapshots (done/total)")
    root.tree.heading("pct", text="%")
    root.tree.heading("eta", text="ETA")
    root.tree.column("yaml", width=380)
    root.tree.column("status", width=220)
    root.tree.column("snap", width=180)
    root.tree.column("pct", width=60, anchor="e")
    root.tree.column("eta", width=120)
    root.tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(mid, orient="vertical", command=root.tree.yview)
    sb.pack(side="left", fill="y")
    root.tree.configure(yscroll=sb.set)

    right = ttk.Frame(root)
    right.pack(fill="x", pady=(8, 0))
    root.main_cli_path = tk.StringVar(value=os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_cli.py"))
    ttk.Label(right, text="main_cli.py:").pack(side="left")
    ttk.Entry(right, textvariable=root.main_cli_path, width=44).pack(side="left", padx=6, fill="x", expand=True)
    ttk.Button(right, text="Stop selected", command=stop_selected).pack(side="right", padx=(6, 0))
    ttk.Button(right, text="Run selected", command=run_selected_yaml_parallel).pack(side="right")

    logf = ttk.LabelFrame(root, text="Log")
    logf.pack(fill="both", expand=True, pady=(8, 0))
    root.txt_log = tk.Text(logf, height=10, wrap="none")
    root.txt_log.pack(fill="both", expand=True)

    # Initial setup
    _scan_yaml_files(root)
    root.after(150, drain_log_queue)
    root.after(250, runner_scheduler_tick)