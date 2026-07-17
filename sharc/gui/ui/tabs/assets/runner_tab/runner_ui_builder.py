"""
runner_ui_builder.py
--------------------
Standalone UI construction for RunnerTab.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QLineEdit, QPushButton, QRadioButton, QComboBox,
    QTreeWidget, QTreeWidgetItem, QMenu, QSpinBox, QScrollArea,
    QPlainTextEdit, QFrame
)
from PySide6.QtCore import Qt

from utils import CollapsibleFrame

def build_runner_ui(tab) -> None:
    """
    Build all widgets for the RunnerTab using PySide6.
    """

    tab.frame = QWidget(tab.host_frame)
    main_layout = QVBoxLayout(tab.frame)
    main_layout.setContentsMargins(5, 5, 5, 5)
    
    # Scrollable container (if not provided by host)
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.NoFrame)
    
    content_widget = QWidget()
    content_layout = QVBoxLayout(content_widget)

    # =========================================================
    # EXECUTION MODE
    # =========================================================
    tab.frm_mode = QGroupBox("Execution Mode")
    mode_layout = QHBoxLayout(tab.frm_mode)
    
    tab.rb_local = QRadioButton("Local")
    tab.rb_ssh = QRadioButton("Remote (SSH)")
    tab.rb_local.setChecked(True)
    
    tab.rb_local.toggled.connect(lambda checked: tab._toggle_mode_ui() if checked else None)
    tab.rb_ssh.toggled.connect(lambda checked: tab._toggle_mode_ui() if checked else None)
    
    mode_layout.addWidget(tab.rb_local)
    mode_layout.addWidget(tab.rb_ssh)
    mode_layout.addStretch()
    
    content_layout.addWidget(tab.frm_mode)

    # =========================================================
    # REMOTE SCHEDULER HEADER (somente SSH)
    # =========================================================
    tab.frm_remote = QGroupBox("Remote Scheduler (SSH)")
    rem_layout = QVBoxLayout(tab.frm_remote)
    
    row1 = QHBoxLayout()
    row1.addWidget(QLabel("SSH:"), 0, Qt.AlignLeft)
    tab.lbl_ssh_status = QLabel("--")
    row1.addWidget(tab.lbl_ssh_status)
    
    row1.addWidget(QLabel("Tunnel:"), 0, Qt.AlignLeft)
    tab.lbl_tun_status = QLabel("--")
    row1.addWidget(tab.lbl_tun_status)
    
    tab._lbl_host_summary = QLabel("")
    row1.addWidget(tab._lbl_host_summary)
    
    row1.addWidget(QLabel("Branch:"), 0, Qt.AlignLeft)
    tab.cmb_git_branch = QComboBox()
    row1.addWidget(tab.cmb_git_branch)
    
    btn_checkout = QPushButton("Checkout")
    btn_checkout.clicked.connect(tab._on_force_checkout_clicked)
    row1.addWidget(btn_checkout)
    
    tab.btn_monitor = QPushButton("Monitor ▼")
    tab._monitor_menu = QMenu(tab.btn_monitor)
    tab._monitor_menu.addAction("top (snapshot)", tab._open_top_window)
    tab.btn_monitor.setMenu(tab._monitor_menu)
    row1.addWidget(tab.btn_monitor)
    
    btn_ref_branches = QPushButton("Refresh branches")
    btn_ref_branches.clicked.connect(tab._refresh_branches)
    row1.addWidget(btn_ref_branches)
    
    row1.addStretch()
    rem_layout.addLayout(row1)

    row2 = QHBoxLayout()
    row2.addWidget(QLabel("Remote YAML Dir:"))
    tab.e_remote_dir = QLineEdit()
    row2.addWidget(tab.e_remote_dir)
    
    btn_list_rem = QPushButton("List Remote YAMLs")
    btn_list_rem.clicked.connect(tab._scan_yaml_files)
    row2.addWidget(btn_list_rem)
    
    btn_up_loc = QPushButton("Upload Local YAMLs")
    btn_up_loc.clicked.connect(tab._upload_local_yaml_files)
    row2.addWidget(btn_up_loc)
    
    btn_up_fold = QPushButton("Upload YAML Folder")
    btn_up_fold.clicked.connect(tab._upload_yaml_folder)
    row2.addWidget(btn_up_fold)
    
    rem_layout.addLayout(row2)
    content_layout.addWidget(tab.frm_remote)

    # =========================================================
    # REMOTE PATHS
    # =========================================================
    tab.frm_remote_paths = CollapsibleFrame(text="Remote Paths", expanded=False)
    rp_layout = QGridLayout()
    tab.frm_remote_paths.sub_layout.addLayout(rp_layout)
    
    rp_layout.addWidget(QLabel("Project Dir:"), 0, 0)
    tab.e_remote_project_dir = QLineEdit()
    rp_layout.addWidget(tab.e_remote_project_dir, 0, 1)
    btn_apply_proj = QPushButton("Apply")
    btn_apply_proj.clicked.connect(tab._apply_remote_paths)
    rp_layout.addWidget(btn_apply_proj, 0, 2)
    
    rp_layout.addWidget(QLabel("main_cli:"), 1, 0)
    tab.e_remote_main_cli = QLineEdit("sharc/main_cli.py")
    rp_layout.addWidget(tab.e_remote_main_cli, 1, 1)
    btn_apply_cli = QPushButton("Apply")
    btn_apply_cli.clicked.connect(lambda: (tab._apply_remote_paths(), tab._auto_detect_remote_paths()))
    rp_layout.addWidget(btn_apply_cli, 1, 2)
    
    content_layout.addWidget(tab.frm_remote_paths)

    # =========================================================
    # REMOTE FILE BROWSER
    # =========================================================
    tab.frm_browser = CollapsibleFrame(text="Remote File Browser", expanded=True)
    br_layout = QVBoxLayout()
    tab.frm_browser.sub_layout.addLayout(br_layout)
    
    br_top = QHBoxLayout()
    br_top.addWidget(QLabel("Path:"))
    tab.e_remote_browse_dir = QLineEdit("~")
    br_top.addWidget(tab.e_remote_browse_dir)
    
    btn_up = QPushButton("Up")
    btn_up.clicked.connect(tab._remote_browse_up)
    br_top.addWidget(btn_up)
    
    btn_ref_br = QPushButton("Refresh")
    btn_ref_br.clicked.connect(tab._remote_browse_refresh)
    br_top.addWidget(btn_ref_br)
    
    btn_set_yaml = QPushButton("Set YAML Dir")
    btn_set_yaml.clicked.connect(tab._remote_browse_set_as_yaml_dir)
    br_top.addWidget(btn_set_yaml)
    
    br_layout.addLayout(br_top)
    
    tab.tree_remote = QTreeWidget()
    tab.tree_remote.setHeaderLabels(["Name", "Type", "Size", "Modified"])
    tab.tree_remote.setColumnWidth(0, 360)
    tab.tree_remote.setColumnWidth(1, 90)
    tab.tree_remote.setColumnWidth(2, 110)
    tab.tree_remote.setColumnWidth(3, 160)
    
    tab.tree_remote.itemDoubleClicked.connect(tab._remote_browse_on_double_click)
    tab.tree_remote.setContextMenuPolicy(Qt.CustomContextMenu)
    tab.tree_remote.customContextMenuRequested.connect(tab._remote_browse_right_click)
    
    tab._remote_menu = QMenu(tab.frame)
    tab._remote_menu.addAction("Copy remote path", tab._remote_browse_copy_path)
    tab._remote_menu.addAction("Set as Remote YAML Dir", tab._remote_browse_set_as_yaml_dir)
    tab._remote_menu.addAction("Set as Remote Project Dir", tab._remote_browse_set_as_project_dir)
    tab._remote_menu.addAction("Set as Remote main_cli (this file)", tab._remote_browse_set_as_main_cli)
    tab._remote_menu.addSeparator()
    tab._remote_menu.addAction("Preview (head)", lambda: tab._remote_browse_preview(mode="head"))
    tab._remote_menu.addAction("Preview (tail)", lambda: tab._remote_browse_preview(mode="tail"))
    
    br_layout.addWidget(tab.tree_remote)
    content_layout.addWidget(tab.frm_browser)

    # =========================================================
    # PROTECTED REMOTE RUNS (tmux)
    # =========================================================
    tab.frm_runs = CollapsibleFrame(text="Protected Runs (tmux)", expanded=False)
    rr_layout = QHBoxLayout()
    tab.frm_runs.sub_layout.addLayout(rr_layout)
    
    btn_list_runs = QPushButton("List Runs")
    btn_list_runs.clicked.connect(tab._list_remote_runs)
    rr_layout.addWidget(btn_list_runs)
    
    rr_layout.addWidget(QLabel("Run:"))
    tab.cmb_runs = QComboBox()
    rr_layout.addWidget(tab.cmb_runs, 1)
    
    btn_resume = QPushButton("Resume")
    btn_resume.clicked.connect(tab._resume_selected_run)
    rr_layout.addWidget(btn_resume)
    
    btn_hint = QPushButton("Open tmux attach hint")
    btn_hint.clicked.connect(tab._tmux_attach_hint)
    rr_layout.addWidget(btn_hint)
    
    btn_sched = QPushButton("Schedule")
    btn_sched.clicked.connect(tab._open_schedule_window)
    rr_layout.addWidget(btn_sched)
    
    btn_clear = QPushButton("Clear tmux")
    btn_clear.clicked.connect(tab._clear_tmux_sessions)
    rr_layout.addWidget(btn_clear)
    
    content_layout.addWidget(tab.frm_runs)

    # =========================================================
    # EXECUTION CONTROLS
    # =========================================================
    frm_exec = QWidget()
    exec_layout = QHBoxLayout(frm_exec)
    exec_layout.setContentsMargins(0, 0, 0, 0)
    
    exec_layout.addWidget(QLabel("YAML Folder:"))
    tab.e_run_folder = QLineEdit()
    exec_layout.addWidget(tab.e_run_folder, 1)
    
    btn_br_fold = QPushButton("Browse")
    btn_br_fold.clicked.connect(tab._pick_folder)
    exec_layout.addWidget(btn_br_fold)
    
    btn_ref_fold = QPushButton("Refresh")
    btn_ref_fold.clicked.connect(tab._scan_yaml_files)
    exec_layout.addWidget(btn_ref_fold)
    
    exec_layout.addWidget(QLabel("Workers:"))
    tab.spin_workers = QSpinBox()
    tab.spin_workers.setRange(1, 32)
    exec_layout.addWidget(tab.spin_workers)
    
    exec_layout.addStretch()
    
    btn_run = QPushButton("Run Selected")
    btn_run.clicked.connect(tab._run_selected_ui)
    exec_layout.addWidget(btn_run)
    
    btn_stop = QPushButton("Stop")
    btn_stop.clicked.connect(tab._stop_selected_ui)
    exec_layout.addWidget(btn_stop)
    
    content_layout.addWidget(frm_exec)

    # =========================================================
    # TREEVIEW (JOBS)
    # =========================================================
    tab.tree = QTreeWidget()
    tab.tree.setHeaderLabels(["YAML File", "Status", "Snapshot", "%", "ETA", "Branch", "Location", "Host"])
    tab.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
    
    tab.tree.setColumnWidth(0, 320)
    tab.tree.setColumnWidth(1, 160)
    tab.tree.setColumnWidth(2, 90)
    tab.tree.setColumnWidth(3, 70)
    tab.tree.setColumnWidth(4, 90)
    tab.tree.setColumnWidth(5, 140)
    tab.tree.setColumnWidth(6, 260)
    tab.tree.setColumnWidth(7, 180)
    
    tab.tree.setContextMenuPolicy(Qt.CustomContextMenu)
    tab.tree.customContextMenuRequested.connect(tab._on_tree_right_click)
    
    tab._menu = QMenu(tab.frame)
    tab._menu.addAction("Open containing folder (local only)", tab._open_local_containing_folder)
    tab._menu.addAction("Copy path", tab._copy_selected_path)
    
    content_layout.addWidget(tab.tree, 1) # strech

    # =========================================================
    # LOG WINDOW
    # =========================================================
    tab.frm_log = CollapsibleFrame(text="Execution Log", expanded=False)
    log_layout = QVBoxLayout()
    tab.frm_log.sub_layout.addLayout(log_layout)
    
    tab.txt_log = QPlainTextEdit()
    tab.txt_log.setReadOnly(True)
    tab.txt_log.setStyleSheet("font-family: Consolas; font-size: 9pt;")
    tab.txt_log.setMinimumHeight(150)
    log_layout.addWidget(tab.txt_log)
    
    content_layout.addWidget(tab.frm_log)

    scroll_area.setWidget(content_widget)
    main_layout.addWidget(scroll_area)

    # Bind status variables to UI
    if hasattr(tab.app, "ssh_status"):
        tab.app.ssh_status.value_changed.connect(lambda v: tab.lbl_ssh_status.setText(str(v)))
        tab.lbl_ssh_status.setText(str(tab.app.ssh_status.get()))
        
    if hasattr(tab.app, "tunnel_status"):
        tab.app.tunnel_status.value_changed.connect(lambda v: tab.lbl_tun_status.setText(str(v)))
        tab.lbl_tun_status.setText(str(tab.app.tunnel_status.get()))
