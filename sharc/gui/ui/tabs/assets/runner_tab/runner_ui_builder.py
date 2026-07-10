"""
runner_ui_builder.py
--------------------
Standalone UI construction for RunnerTab.

Usage (inside RunnerTab._build_ui):
    from ui.tabs.assets.runner_tab.runner_ui_builder import build_runner_ui
    build_runner_ui(self)
"""

import tkinter as tk
from tkinter import ttk

from utils import CollapsibleFrame


def build_runner_ui(tab) -> None:
    """
    Build all widgets for the RunnerTab.

    Parameters
    ----------
    tab : RunnerTab
        The RunnerTab instance.  All widgets are attached to ``tab`` as
        attributes (``tab.frame``, ``tab.tree``, ``tab.txt_log``, …) exactly
        as they were when the code lived inside ``_build_ui``.
    """

    # A partir daqui, todos os widgets serão criados dentro do frame
    # "scrollável" provido pela Main.
    tab.frame = ttk.Frame(tab.host_frame)
    tab.frame.pack(fill="both", expand=True)

    # =========================================================
    # EXECUTION MODE
    # =========================================================
    tab.frm_mode = ttk.LabelFrame(tab.frame, text="Execution Mode")
    tab.frm_mode.pack(fill="x", pady=5, padx=5)

    ttk.Radiobutton(
        tab.frm_mode,
        text="Local",
        value="LOCAL",
        variable=tab.app.var_run_mode,
        command=tab._toggle_mode_ui,
    ).pack(side="left", padx=10)

    ttk.Radiobutton(
        tab.frm_mode,
        text="Remote (SSH)",
        value="SSH",
        variable=tab.app.var_run_mode,
        command=tab._toggle_mode_ui,
    ).pack(side="left", padx=10)

    # =========================================================
    # REMOTE SCHEDULER HEADER (somente SSH)
    # =========================================================
    tab.frm_remote = ttk.LabelFrame(tab.frame, text="Remote Scheduler (SSH)")
    # pack controlado em _toggle_mode_ui

    row = ttk.Frame(tab.frm_remote)
    row.pack(fill="x", padx=8, pady=(6, 6))

    # Status vindo do app (atualizado pelo ssh_config tab)
    ttk.Label(row, text="SSH:", font=("Segoe UI", 9, "bold")).pack(side="left")
    ttk.Label(row, textvariable=tab.app.ssh_status).pack(side="left", padx=(4, 14))

    if hasattr(tab.app, "tunnel_status"):
        ttk.Label(row, text="Tunnel:", font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(row, textvariable=tab.app.tunnel_status).pack(
            side="left", padx=(4, 14)
        )

    # Host summary (se existir variáveis no app)
    tab._lbl_host_summary = ttk.Label(row, text="")
    tab._lbl_host_summary.pack(side="left", padx=(0, 14))

    # Branch controls (mantém, pois é parte do workflow remoto)
    ttk.Label(row, text="Branch:", font=("Segoe UI", 9, "bold")).pack(side="left")
    tab.cmb_git_branch = ttk.Combobox(
        row,
        textvariable=tab.app.var_git_branch,
        state="readonly",
        width=18,
    )
    tab.cmb_git_branch.pack(side="left", padx=(6, 6))

    ttk.Button(row, text="Checkout", command=tab._on_force_checkout_clicked).pack(
        side="left", padx=(0, 8)
    )

    # Monitor menu (top/htop)
    tab.btn_monitor = ttk.Menubutton(row, text="Monitor")
    tab._monitor_menu = tk.Menu(tab.btn_monitor, tearoff=False)
    tab._monitor_menu.add_command(
        label="top (snapshot)", command=tab._open_top_window
    )
    tab.btn_monitor.configure(menu=tab._monitor_menu)
    tab.btn_monitor.pack(side="left", padx=(0, 8))
    ttk.Button(row, text="Refresh branches", command=tab._refresh_branches).pack(
        side="left"
    )

    # Remote directory (continua no Runner, pois é parte do scheduler/listagem)
    row2 = ttk.Frame(tab.frm_remote)
    row2.pack(fill="x", padx=8, pady=(0, 8))

    ttk.Label(row2, text="Remote YAML Dir:", font=("Segoe UI", 9, "bold")).pack(
        side="left"
    )
    ttk.Entry(row2, textvariable=tab.app.ssh_remote_dir).pack(
        side="left", fill="x", expand=True, padx=6
    )
    ttk.Button(
        row2, text="List Remote YAMLs", command=tab._scan_yaml_files
    ).pack(side="left", padx=(0, 6))

    ttk.Button(
        row2, text="Upload Local YAMLs", command=tab._upload_local_yaml_files
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        row2, text="Upload YAML Folder", command=tab._upload_yaml_folder
    ).pack(side="left", padx=(0, 6))

    # =========================================================
    # REMOTE PATHS (Project dir + main_cli) - somente SSH
    # =========================================================
    tab.frm_remote_paths = CollapsibleFrame(
        tab.frm_remote, text="Remote Paths", expanded=False
    )
    tab.frm_remote_paths.pack(fill="x", expand=False, padx=8, pady=(0, 8))

    rp = ttk.Frame(tab.frm_remote_paths.sub_frame)
    rp.pack(fill="x", padx=6, pady=(6, 6))

    tab.var_remote_project_dir = tk.StringVar(
        value=getattr(tab.manager, "remote_base_dir", "") if tab.manager else ""
    )
    tab.var_remote_main_cli = tk.StringVar(
        value=(
            getattr(tab.manager, "remote_main_cli_rel", "sharc/main_cli.py")
            if tab.manager
            else "sharc/main_cli.py"
        )
    )

    ttk.Label(rp, text="Project Dir:", font=("Segoe UI", 9, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Entry(rp, textvariable=tab.var_remote_project_dir).grid(
        row=0, column=1, sticky="ew", padx=(6, 6)
    )
    ttk.Button(rp, text="Apply", command=tab._apply_remote_paths).grid(
        row=0, column=2, padx=(0, 6)
    )

    ttk.Label(rp, text="main_cli:", font=("Segoe UI", 9, "bold")).grid(
        row=1, column=0, sticky="w", pady=(6, 0)
    )
    ttk.Entry(rp, textvariable=tab.var_remote_main_cli).grid(
        row=1, column=1, sticky="ew", padx=(6, 6), pady=(6, 0)
    )

    ttk.Button(
        rp,
        text="Apply",
        command=lambda: (tab._apply_remote_paths(), tab._auto_detect_remote_paths()),
    ).grid(row=1, column=2, columnspan=2, padx=(0, 6), pady=(6, 0))

    rp.columnconfigure(1, weight=1)

    # =========================================================
    # REMOTE FILE BROWSER (somente SSH)
    # =========================================================
    tab.frm_browser = CollapsibleFrame(
        tab.frm_remote, text="Remote File Browser", expanded=True
    )
    tab.frm_browser.pack(fill="both", expand=False, padx=8, pady=(0, 8))

    br_top = ttk.Frame(tab.frm_browser.sub_frame)
    br_top.pack(fill="x", padx=6, pady=(6, 4))

    tab.var_remote_browse_dir = tk.StringVar(
        value=tab.app.ssh_remote_dir.get().strip() or "~"
    )

    ttk.Label(br_top, text="Path:", font=("Segoe UI", 9, "bold")).pack(side="left")
    ttk.Entry(br_top, textvariable=tab.var_remote_browse_dir).pack(
        side="left", fill="x", expand=True, padx=(6, 6)
    )
    ttk.Button(br_top, text="Up", command=tab._remote_browse_up).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(br_top, text="Refresh", command=tab._remote_browse_refresh).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(
        br_top,
        text="Set YAML Dir",
        command=tab._remote_browse_set_as_yaml_dir,
    ).pack(side="left")

    br_mid = ttk.Frame(tab.frm_browser.sub_frame)
    br_mid.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    bcols = ("name", "type", "size", "mtime")
    tab.tree_remote = ttk.Treeview(br_mid, columns=bcols, show="headings", height=10)
    tab.tree_remote.heading("name", text="Name")
    tab.tree_remote.heading("type", text="Type")
    tab.tree_remote.heading("size", text="Size")
    tab.tree_remote.heading("mtime", text="Modified")
    tab.tree_remote.column("name", width=360)
    tab.tree_remote.column("type", width=90, anchor="center")
    tab.tree_remote.column("size", width=110, anchor="e")
    tab.tree_remote.column("mtime", width=160, anchor="center")

    sb_br = ttk.Scrollbar(br_mid, orient="vertical", command=tab.tree_remote.yview)
    tab.tree_remote.configure(yscroll=sb_br.set)
    tab.tree_remote.pack(side="left", fill="both", expand=True)
    sb_br.pack(side="right", fill="y")

    tab.tree_remote.bind("<Double-1>", tab._remote_browse_on_double_click, add="+")

    tab._remote_menu = tk.Menu(tab.frame, tearoff=False)
    tab._remote_menu.add_command(
        label="Copy remote path", command=tab._remote_browse_copy_path
    )
    tab._remote_menu.add_command(
        label="Set as Remote YAML Dir",
        command=tab._remote_browse_set_as_yaml_dir,
    )
    tab._remote_menu.add_command(
        label="Set as Remote Project Dir",
        command=tab._remote_browse_set_as_project_dir,
    )
    tab._remote_menu.add_command(
        label="Set as Remote main_cli (this file)",
        command=tab._remote_browse_set_as_main_cli,
    )
    tab._remote_menu.add_separator()
    tab._remote_menu.add_command(
        label="Preview (head)",
        command=lambda: tab._remote_browse_preview(mode="head"),
    )
    tab._remote_menu.add_command(
        label="Preview (tail)",
        command=lambda: tab._remote_browse_preview(mode="tail"),
    )
    tab.tree_remote.bind("<Button-3>", tab._remote_browse_right_click, add="+")

    # =========================================================
    # PROTECTED REMOTE RUNS (tmux resume)
    # =========================================================
    tab.frm_runs = CollapsibleFrame(
        tab.frm_remote, text="Protected Runs (tmux)", expanded=False
    )
    tab.frm_runs.pack(fill="x", padx=8, pady=(0, 8))

    rr = ttk.Frame(tab.frm_runs.sub_frame)
    rr.pack(fill="x", padx=6, pady=6)

    ttk.Button(rr, text="List Runs", command=tab._list_remote_runs).pack(
        side="left", padx=(0, 8)
    )

    ttk.Label(rr, text="Run:", font=("Segoe UI", 9, "bold")).pack(side="left")
    tab._run_pick = tk.StringVar(value="")
    tab.cmb_runs = ttk.Combobox(
        rr, textvariable=tab._run_pick, state="readonly", width=38
    )
    tab.cmb_runs.pack(side="left", padx=(6, 8), fill="x", expand=True)

    ttk.Button(rr, text="Resume", command=tab._resume_selected_run).pack(
        side="left", padx=(0, 8)
    )
    ttk.Button(
        rr, text="Open tmux attach hint", command=tab._tmux_attach_hint
    ).pack(side="left", padx=(0, 8))
    ttk.Button(rr, text="Schedule", command=tab._open_schedule_window).pack(
        side="left", padx=(0, 8)
    )
    ttk.Button(rr, text="Clear tmux", command=tab._clear_tmux_sessions).pack(
        side="left"
    )

    # =========================================================
    # EXECUTION CONTROLS (vale para os dois modos)
    # =========================================================
    frm_exec = ttk.Frame(tab.frame)
    frm_exec.pack(fill="x", pady=5, padx=5)

    ttk.Label(frm_exec, text="YAML Folder").pack(side="left")
    ttk.Entry(frm_exec, textvariable=tab.app.run_folder).pack(
        side="left", fill="x", expand=True, padx=5
    )
    ttk.Button(frm_exec, text="Browse", command=tab._pick_folder).pack(side="left")
    ttk.Button(frm_exec, text="Refresh", command=tab._scan_yaml_files).pack(
        side="left", padx=5
    )

    ttk.Label(frm_exec, text="Workers:").pack(side="left", padx=(15, 5))
    tk.Spinbox(
        frm_exec, from_=1, to=32, width=3, textvariable=tab.app.var_max_workers
    ).pack(side="left")

    ttk.Button(frm_exec, text="Run Selected", command=tab._run_selected_ui).pack(
        side="right", padx=5
    )
    ttk.Button(frm_exec, text="Stop", command=tab._stop_selected_ui).pack(
        side="right"
    )

    # =========================================================
    # TREEVIEW (JOBS/SCHEDULE)
    # =========================================================
    frm_tree = ttk.Frame(tab.frame)
    frm_tree.pack(fill="both", expand=True, padx=5, pady=2)

    cols = ("yaml", "status", "snap", "pct", "eta", "branch", "location", "host")
    tab.tree = ttk.Treeview(frm_tree, columns=cols, show="headings", height=10)

    tab.tree.heading("yaml", text="YAML File")
    tab.tree.heading("status", text="Status")
    tab.tree.heading("snap", text="Snapshot")
    tab.tree.heading("pct", text="%")
    tab.tree.heading("eta", text="ETA")
    tab.tree.heading("branch", text="Branch")
    tab.tree.heading("location", text="Location")
    tab.tree.heading("host", text="Host")

    tab.tree.column("yaml", width=320)
    tab.tree.column("status", width=160)
    tab.tree.column("snap", width=90, anchor="center")
    tab.tree.column("pct", width=70, anchor="e")
    tab.tree.column("eta", width=90, anchor="center")
    tab.tree.column("branch", width=140)
    tab.tree.column("location", width=260)
    tab.tree.column("host", width=180)

    sb = ttk.Scrollbar(frm_tree, orient="vertical", command=tab.tree.yview)
    tab.tree.configure(yscroll=sb.set)

    tab.tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    # Context menu básico
    tab._menu = tk.Menu(tab.frame, tearoff=False)
    tab._menu.add_command(
        label="Open containing folder (local only)",
        command=tab._open_local_containing_folder,
    )
    tab._menu.add_command(label="Copy path", command=tab._copy_selected_path)
    tab.tree.bind("<Button-3>", tab._on_tree_right_click, add="+")

    # =========================================================
    # LOG WINDOW
    # =========================================================
    frm_log = CollapsibleFrame(tab.frame, text="Execution Log", expanded=False)
    frm_log.pack(fill="both", expand=True, padx=5, pady=5)

    tab.txt_log = tk.Text(
        frm_log.sub_frame, height=12, state="disabled", font=("Consolas", 9)
    )
    sb_log = ttk.Scrollbar(
        frm_log.sub_frame, orient="vertical", command=tab.txt_log.yview
    )
    tab.txt_log.configure(yscroll=sb_log.set)

    tab.txt_log.pack(side="left", fill="both", expand=True)
    sb_log.pack(side="right", fill="y")
