import os
import copy
import math
import time
import posixpath
import threading
from collections import OrderedDict
from pathlib import Path
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QGroupBox, QLabel, 
    QRadioButton, QPushButton, QListWidget, QCheckBox, QComboBox, 
    QLineEdit, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, 
    QDialog, QProgressBar, QMessageBox, QHeaderView, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QMenu

try:
    from ui.tabs.assets.results_tab.alt_plot_engine import MatplotlibPlotter
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import paramiko
except ImportError:
    paramiko = None

try:
    from config import RESULT_FIELDNAME_TO_PLOT_INFO
except ImportError:
    RESULT_FIELDNAME_TO_PLOT_INFO = {}

from ui.components.scroll_containers import ScrollableContainer
from core.yaml_builder import _as_bool  # noqa: E402
from core.state import SharcVar


def _exec_menu(menu, global_pos):
    """Single place that opens a menu modally (tests replace it)."""
    menu.exec(global_pos)


# Kaleido (the Plotly rasteriser) drives one helper process and must not be used by two threads at once.
_KALEIDO_LOCK = threading.Lock()


class ResultsTab(QWidget):
    results_changed = Signal()          # the list of result folders changed (added, removed, cleared)
    _ui_progress = Signal(int)          # render thread -> GUI thread
    _ui_status = Signal(str, int)
    _ui_image = Signal(bytes)
    _ui_error = Signal(str)

    """
    Results Tab - PySide6 Edition
    Features: Smart Column Scan, float32 Optimization, Auto-Cache Clearing, 
    and Dual Plotting Engine (Plotly/Matplotlib QtAgg).
    """
    # Sorted sample arrays kept in memory (one per folder and field), so that changing a title, a limit
    # or the CDF/CCDF mode does not sort every dataset again.
    _SORTED_CACHE_MAX = 64

    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app

        if not hasattr(self.app, "res_dirs"):
            self.app.res_dirs = []
        if not hasattr(self.app, "res_styles"):
            self.app.res_styles = {}

        self._init_ssh_vars()

        from core.remote_data_client import RemoteDataClient
        self.data_client = RemoteDataClient(cache_limit=50)

        # Rendering Control
        self._render_lock = threading.Lock()
        self._data_lock = threading.Lock()
        self._sorted_cache = OrderedDict()
        self._render_busy = False         # a Plotly render is running (only touched in the GUI thread)
        self._pending_refresh = None      # force_refresh of a refresh asked while another was rendering
        # The render thread must not touch widgets or call QTimer.singleShot: a QTimer started from a thread
        # without an event loop never fires, which left the page stuck on "Preparing Plot... 0%".
        self._ui_progress.connect(self._update_progress_ui)
        self._ui_status.connect(self._show_render_status)
        self._ui_image.connect(self._on_render_done)
        self._ui_error.connect(self._on_render_failed)
        self._update_timer = None
        self._max_axes = 9
        self._disable_traces = False
        
        self._mpl_canvas = None
        self._mpl_toolbar = None

        self.result_fields = sorted(list(RESULT_FIELDNAME_TO_PLOT_INFO.keys()))
        if not self.result_fields:
            self.result_fields = ["ExampleField"]

        default_field = self.result_fields[0]
        default_criteria = [
            {"val": -12.2, "type": "Vertical (X)", "label": "Prot -12.2dB", "color": "red", "enabled": True},
            {"val": -6.0,  "type": "Vertical (X)", "label": "Prot -6dB",    "color": "orange", "enabled": True}
        ]

        self._axes_cfg = []
        for i in range(self._max_axes):
            self._axes_cfg.append({
                "field": default_field, "mode": "CDF", "title": "",
                "x_label": "", "y_label": "", "x_log": False, "y_log": False,
                "x_shift": 0.0, "legend_suffix": "", "x_min": "", "x_max": "", "x_step": "",
                "y_min": "", "y_max": "", "y_step": "",
                "criteria": [c.copy() for c in default_criteria]
            })

        self.var_plot_selected_only = getattr(self.app, "var_plot_selected_only", SharcVar(False, bool))
        self.app.var_plot_selected_only = self.var_plot_selected_only

        self._build_ui()
        QTimer.singleShot(500, self._schedule_update)

    def _init_ssh_vars(self):
        if not hasattr(self.app, "ssh_host"): self.app.ssh_host = SharcVar("localhost")
        if not hasattr(self.app, "ssh_user"): self.app.ssh_user = SharcVar("")
        if not hasattr(self.app, "ssh_password"): self.app.ssh_password = SharcVar("")
        if not hasattr(self.app, "ssh_port"): self.app.ssh_port = SharcVar("22")

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        paned = QSplitter(Qt.Horizontal)
        self.left_scroll = ScrollableContainer()
        left_frame = self.left_scroll.container
        
        right_frame = QWidget()
        self.right_layout = QVBoxLayout(right_frame)

        self._build_file_manager(left_frame)
        self._build_layout_controls(left_frame)
        self._build_subplot_config(left_frame)
        self._build_plot_preview(right_frame)

        paned.addWidget(self.left_scroll)
        paned.addWidget(right_frame)
        paned.setChildrenCollapsible(False)
        paned.setStretchFactor(0, 0)
        paned.setStretchFactor(1, 1)
        paned.setSizes([470, 330])
        main_layout.addWidget(paned)
        self._paned = paned

        self._load_subplot_config_to_ui()

    # The controls need ~480 px. When the tab is narrower, stack controls above the plot
    # instead of clipping them.
    _NARROW_PX = 900

    def resizeEvent(self, ev):  # noqa: N802
        super().resizeEvent(ev)
        paned = getattr(self, "_paned", None)
        if paned is None:
            return
        want = Qt.Vertical if self.width() < self._NARROW_PX else Qt.Horizontal
        if paned.orientation() != want:
            paned.setOrientation(want)
            paned.setSizes([300, 300] if want == Qt.Vertical else [470, 330])

    def _build_file_manager(self, parent):
        frm = QGroupBox("Result Folders")
        l = QVBoxLayout(frm)

        # Source Selection
        src_frame = QHBoxLayout()
        src_frame.addWidget(QLabel("Source:"))
        self.rb_local = QRadioButton("Local")
        self.rb_remote = QRadioButton("Remote")
        self.rb_local.setChecked(True)
        btn_conn = QPushButton("Connection...")
        btn_conn.clicked.connect(self._open_ssh_config)
        
        src_frame.addWidget(self.rb_local)
        src_frame.addWidget(self.rb_remote)
        src_frame.addStretch()
        src_frame.addWidget(btn_conn)
        l.addLayout(src_frame)

        # Listbox
        self.lb_dirs = QListWidget()
        self.lb_dirs.setSelectionMode(QListWidget.ExtendedSelection)
        self.lb_dirs.itemSelectionChanged.connect(self._load_style_from_selection)
        l.addWidget(self.lb_dirs)
        self._refresh_dir_listbox()

        # Buttons
        btn_frame = QHBoxLayout()
        btn_add = QPushButton("Add Folder...")
        btn_detect = QPushButton("Detect results")
        btn_detect.setToolTip("Find simulation results automatically (output folders written by the simulator)")
        btn_rm = QPushButton("Remove")
        btn_clr = QPushButton("Clear")
        btn_add.clicked.connect(self._add_dir_handler)
        btn_detect.clicked.connect(lambda: self.detect_results())
        btn_rm.clicked.connect(self._remove_dir)
        btn_clr.clicked.connect(self._clear_all_dirs)
        self.lb_dirs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lb_dirs.customContextMenuRequested.connect(self._dirs_menu)
        for keys, slot in (("Delete", self._remove_dir), ("F5", self._manual_refresh),
                           ("Ctrl+A", self.lb_dirs.selectAll), ("Ctrl+O", self._add_dir_handler)):
            sc = QShortcut(QKeySequence(keys), self.lb_dirs)
            sc.setContext(Qt.WidgetShortcut)
            sc.activated.connect(slot)

        btn_frame.addWidget(btn_add)
        btn_frame.addWidget(btn_detect)
        btn_frame.addWidget(btn_rm)
        btn_frame.addStretch()
        btn_frame.addWidget(btn_clr)
        l.addLayout(btn_frame)

        # Bulk Selection Tools
        sel_frame = QHBoxLayout()
        cb_plot_sel = QCheckBox("Plot Selected Only")
        self.var_plot_selected_only.value_changed.connect(cb_plot_sel.setChecked)
        cb_plot_sel.toggled.connect(self.var_plot_selected_only.set)
        cb_plot_sel.setChecked(_as_bool(self.var_plot_selected_only.get()))
        
        btn_all = QPushButton("Select All")
        btn_none = QPushButton("None")
        btn_all.clicked.connect(self.lb_dirs.selectAll)
        btn_none.clicked.connect(self.lb_dirs.clearSelection)
        
        sel_frame.addWidget(cb_plot_sel)
        sel_frame.addStretch()
        sel_frame.addWidget(btn_all)
        sel_frame.addWidget(btn_none)
        l.addLayout(sel_frame)

        parent.layout().addWidget(frm)
        self._build_style_editor(parent)

    def _build_style_editor(self, parent):
        frm_style = QGroupBox("Style (Applies to Selection)")
        l = QVBoxLayout(frm_style)
        
        sf1 = QHBoxLayout()
        sf1.addWidget(QLabel("Legend:"))
        self.e_style_lbl = QLineEdit()
        sf1.addWidget(self.e_style_lbl)
        l.addLayout(sf1)
        
        sf2 = QHBoxLayout()
        sf2.addWidget(QLabel("Color:"))
        self.cb_style_col = QComboBox()
        self.cb_style_col.addItems(["Auto", "tab:blue", "tab:orange", "tab:green", "tab:red", "black", "grey"])
        sf2.addWidget(self.cb_style_col)
        
        sf2.addWidget(QLabel("Line:"))
        self.cb_style_ls = QComboBox()
        self.cb_style_ls.addItems(["Auto", "-", "--", "-.", ":"])
        sf2.addWidget(self.cb_style_ls)
        
        sf2.addWidget(QLabel("Wid:"))
        self.sp_style_lw = QSpinBox()
        self.sp_style_lw.setRange(1, 5)
        self.sp_style_lw.setValue(2)
        sf2.addWidget(self.sp_style_lw)
        
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._apply_style)
        sf2.addWidget(btn_apply)
        l.addLayout(sf2)
        
        parent.layout().addWidget(frm_style)

    def _build_layout_controls(self, parent):
        frm = QGroupBox("Grid Layout")
        l = QHBoxLayout(frm)
        l.addWidget(QLabel("Rows:"))
        self.sp_rows = QSpinBox()
        self.sp_rows.setRange(1, 3)
        self.sp_rows.valueChanged.connect(self._schedule_update)
        l.addWidget(self.sp_rows)
        
        l.addWidget(QLabel("Cols:"))
        self.sp_cols = QSpinBox()
        self.sp_cols.setRange(1, 3)
        self.sp_cols.valueChanged.connect(self._schedule_update)
        l.addWidget(self.sp_cols)
        
        parent.layout().addWidget(frm)

    def _build_subplot_config(self, parent):
        frm = QGroupBox("Active Subplot Settings")
        l = QVBoxLayout(frm)
        
        sel_frame = QHBoxLayout()
        sel_frame.addWidget(QLabel("Editing Subplot:"))
        self.cb_subplot_sel = QComboBox()
        self.cb_subplot_sel.addItems([str(i+1) for i in range(self._max_axes)])
        self.cb_subplot_sel.currentTextChanged.connect(self._on_subplot_selection_change)
        sel_frame.addWidget(self.cb_subplot_sel)
        sel_frame.addStretch()
        l.addLayout(sel_frame)

        nb = QTabWidget()
        tab_axis = QWidget()
        l_axis = QVBoxLayout(tab_axis)
        
        f_frame = QHBoxLayout()
        f_frame.addWidget(QLabel("CSV Field:"))
        self.cb_field = QComboBox()
        self.cb_field.addItems(self.result_fields)
        self.cb_field.currentTextChanged.connect(self._on_config_change)
        f_frame.addWidget(self.cb_field, 1)
        l_axis.addLayout(f_frame)

        g1 = QHBoxLayout()
        g1.addWidget(QLabel("Mode:"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["CDF", "CCDF"])
        self.cb_mode.currentTextChanged.connect(self._on_config_change)
        g1.addWidget(self.cb_mode)
        l_axis.addLayout(g1)
        
        def _add_line(lbl, default=""):
            h = QHBoxLayout()
            h.addWidget(QLabel(lbl))
            e = QLineEdit(default)
            e.textChanged.connect(self._on_config_change)
            h.addWidget(e)
            l_axis.addLayout(h)
            return e
            
        self.e_title = _add_line("Chart Title:")
        self.e_xlabel = _add_line("X Label:")
        self.e_ylabel = _add_line("Y Label:")

        chk_frame = QHBoxLayout()
        self.cb_xlog = QCheckBox("Log X")
        self.cb_ylog = QCheckBox("Log Y")
        self.cb_xlog.stateChanged.connect(self._on_config_change)
        self.cb_ylog.stateChanged.connect(self._on_config_change)
        chk_frame.addWidget(self.cb_xlog)
        chk_frame.addWidget(self.cb_ylog)
        chk_frame.addStretch()
        l_axis.addLayout(chk_frame)

        sh_frame = QHBoxLayout()
        sh_frame.addWidget(QLabel("X Shift:"))
        self.e_xshift = QLineEdit("0.0")
        self.e_xshift.textChanged.connect(self._on_config_change)
        sh_frame.addWidget(self.e_xshift)
        sh_frame.addWidget(QLabel("Legend Suffix:"))
        self.e_leg_suffix = QLineEdit()
        self.e_leg_suffix.textChanged.connect(self._on_config_change)
        sh_frame.addWidget(self.e_leg_suffix)
        l_axis.addLayout(sh_frame)

        lim_box = QGroupBox("Limits && Steps (Empty = Auto)")
        lim_l = QGridLayout(lim_box)
        lim_l.addWidget(QLabel("Min"), 0, 1)
        lim_l.addWidget(QLabel("Max"), 0, 2)
        lim_l.addWidget(QLabel("Step"), 0, 3)
        
        lim_l.addWidget(QLabel("X Axis:"), 1, 0)
        self.e_xmin = QLineEdit()
        self.e_xmax = QLineEdit()
        self.e_xstep = QLineEdit()
        for i, w in enumerate([self.e_xmin, self.e_xmax, self.e_xstep]):
            w.textChanged.connect(self._on_config_change)
            lim_l.addWidget(w, 1, i+1)

        lim_l.addWidget(QLabel("Y Axis:"), 2, 0)
        self.e_ymin = QLineEdit()
        self.e_ymax = QLineEdit()
        self.e_ystep = QLineEdit()
        for i, w in enumerate([self.e_ymin, self.e_ymax, self.e_ystep]):
            w.textChanged.connect(self._on_config_change)
            lim_l.addWidget(w, 2, i+1)
        
        l_axis.addWidget(lim_box)
        
        # Tab 2: Criteria
        tab_crit = QWidget()
        l_crit = QVBoxLayout(tab_crit)
        
        self.tv_crit = QTableWidget(0, 4)
        self.tv_crit.setHorizontalHeaderLabels(["Status", "Val", "Type", "Label"])
        self.tv_crit.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tv_crit.setSelectionBehavior(QTableWidget.SelectRows)
        self.tv_crit.cellDoubleClicked.connect(self._toggle_criteria)
        l_crit.addWidget(self.tv_crit)
        
        btns = QHBoxLayout()
        btn_add_c = QPushButton("Add...")
        btn_tog_c = QPushButton("Toggle")
        btn_rm_c = QPushButton("Remove")
        btn_add_c.clicked.connect(self._add_criteria_dialog)
        btn_tog_c.clicked.connect(self._toggle_criteria)
        btn_rm_c.clicked.connect(self._remove_criteria)
        btns.addStretch()
        btns.addWidget(btn_add_c)
        btns.addWidget(btn_tog_c)
        btns.addWidget(btn_rm_c)
        l_crit.addLayout(btns)

        nb.addTab(tab_axis, "Data && Axis")
        nb.addTab(tab_crit, "Protection Criteria")
        l.addWidget(nb)
        
        parent.layout().addWidget(frm)

    def _build_plot_preview(self, parent):
        toolbar = QHBoxLayout()

        if HAS_MATPLOTLIB:
            toolbar.addWidget(QLabel("Engine:"))
            self.rb_plt = QRadioButton("Plotly")
            self.rb_mpl = QRadioButton("Matplotlib")
            self.rb_plt.setChecked(True)
            self.rb_plt.toggled.connect(self._manual_refresh)
            toolbar.addWidget(self.rb_plt)
            toolbar.addWidget(self.rb_mpl)

        btn_ref = QPushButton("Refresh")
        btn_ref.clicked.connect(self._manual_refresh)
        toolbar.addWidget(btn_ref)
        toolbar.addStretch()

        btn_open = QPushButton("Open Interactive (Browser)")
        btn_open.clicked.connect(self._open_browser)
        toolbar.addWidget(btn_open)

        self.right_layout.addLayout(toolbar)

        self.preview_frame = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        
        from ui.components.empty_state import EmptyState
        self.empty_state = EmptyState(
            "mdi.chart-box-plus-outline", "No results loaded",
            "Add a result folder, or let SHARC detect the output of the latest simulation.", "Detect results")
        self.empty_state.action_clicked.connect(lambda: self.detect_results())
        self.preview_layout.addWidget(self.empty_state, 0, Qt.AlignCenter)
        self.lbl_preview = QLabel("")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.preview_layout.addWidget(self.lbl_preview)
        model = self.lb_dirs.model()
        model.rowsInserted.connect(self._sync_empty_state)
        model.rowsRemoved.connect(self._sync_empty_state)
        model.modelReset.connect(self._sync_empty_state)
        
        self.pb_loading = QProgressBar()
        self.pb_loading.hide()
        self.preview_layout.addWidget(self.pb_loading)

        self.right_layout.addWidget(self.preview_frame, stretch=1)

    # ---------------- SSH Logic ----------------
    def _open_ssh_config(self):
        win = QDialog(self)
        win.setWindowTitle("SSH Connection Settings")
        win.resize(300, 200)
        l = QVBoxLayout(win)
        
        l.addWidget(QLabel("Host:"))
        e_host = QLineEdit(str(self.app.ssh_host.get()))
        e_host.textChanged.connect(self.app.ssh_host.set)
        l.addWidget(e_host)
        
        l.addWidget(QLabel("User:"))
        e_user = QLineEdit(str(self.app.ssh_user.get()))
        e_user.textChanged.connect(self.app.ssh_user.set)
        l.addWidget(e_user)
        
        l.addWidget(QLabel("Password:"))
        e_pass = QLineEdit(str(self.app.ssh_password.get()))
        e_pass.setEchoMode(QLineEdit.Password)
        e_pass.textChanged.connect(self.app.ssh_password.set)
        l.addWidget(e_pass)
        
        l.addWidget(QLabel("Port:"))
        e_port = QLineEdit(str(self.app.ssh_port.get()))
        e_port.textChanged.connect(self.app.ssh_port.set)
        l.addWidget(e_port)
        
        btn = QPushButton("Close")
        btn.clicked.connect(win.accept)
        l.addWidget(btn)
        win.exec()

    def _get_ssh_client(self):
        cli = getattr(self.app, "ssh_client", None)
        if cli and getattr(cli, "get_transport", None) and cli.get_transport().is_active():
            return cli
        if paramiko is None:
            return None
        try:
            host = self.app.ssh_host.get()
            port = int(self.app.ssh_port.get() or 22)
            user = self.app.ssh_user.get()
            pwd = self.app.ssh_password.get()
            cli = self.data_client.get_ssh_client(host, port, user, pwd)
            if cli:
                self.app.ssh_client = cli
            return cli
        except Exception as e:
            print(f"Error getting SSH client: {e}")
            return None

    def _remote_dir_picker(self):
        cli = self._get_ssh_client()
        if not cli:
            QMessageBox.critical(self, "SSH Error", "Could not connect.\nCheck 'Connection' settings.")
            return None
        
        win = QDialog(self)
        win.setWindowTitle("Select Remote Folder(s)")
        win.resize(600, 400)
        l = QVBoxLayout(win)
        
        top = QHBoxLayout()
        e_path = QLineEdit("/home")
        top.addWidget(e_path)
        l.addLayout(top)
        
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        tv = QTreeWidget()
        tv.setHeaderLabels(["Directory"])
        tv.setSelectionMode(QTreeWidget.ExtendedSelection)
        l.addWidget(tv)
        
        chosen_paths = []
        
        def _ls(p):
            tv.clear()
            e_path.setText(p)
            try:
                for item, ftype in self.data_client.list_dir(cli, p):
                    if ftype == "DIR":
                        QTreeWidgetItem(tv, [item])
            except Exception:
                pass
                
        def _enter(item, column):
            _ls(posixpath.join(e_path.text(), item.text(0)))
            
        tv.itemDoubleClicked.connect(_enter)
        
        btn_box = QHBoxLayout()
        btn_up = QPushButton("Up Level")
        btn_up.clicked.connect(lambda: _ls(posixpath.dirname(e_path.text())))
        btn_sel = QPushButton("Select Selected Folder(s)")
        
        def _select():
            base_p = e_path.text()
            items = tv.selectedItems()
            if not items:
                chosen_paths.append(base_p)
            else:
                for item in items:
                    chosen_paths.append(posixpath.join(base_p, item.text(0)))
            win.accept()
            
        btn_sel.clicked.connect(_select)
        btn_box.addWidget(btn_up)
        btn_box.addStretch()
        btn_box.addWidget(btn_sel)
        l.addLayout(btn_box)
        
        _ls(e_path.text())
        win.exec()
        return chosen_paths if chosen_paths else None

    # ---------------- Data Handling ----------------
    def _get_data(self, folder_tag, field, force_refresh=False):
        base = getattr(self.app, "var_outdir", None)
        base = base.get() if (base and hasattr(base, "get")) else os.getcwd()
        cli = None
        if folder_tag.startswith("ssh://"):
            cli = self._get_ssh_client()
        return self.data_client.get_data(cli, folder_tag, field, base, force_refresh)

    def _compute_ecdf(self, x, ccdf=False, downsample_to=0):
        return self._ecdf_from_sorted(np.sort(x), ccdf=ccdf, downsample_to=downsample_to)

    @staticmethod
    def _ecdf_from_sorted(x, ccdf=False, downsample_to=0):
        """Empirical CDF (or CCDF) of already sorted samples: same values as sorting and dividing the ranks,
        but when a downsampled curve is asked for only its points are computed."""
        n = x.size
        if n == 0: return [], []
        if downsample_to > 0 and n > downsample_to:
            idx = np.linspace(0, n - 1, downsample_to).astype(int)
            x, y = x[idx], (idx + 1) / n
        else:
            y = np.arange(1, n+1)/n
        if ccdf: y = 1.0 - y
        return x, y

    def _get_sorted_data(self, folder_tag, field, force_refresh=False):
        """Samples of a field sorted in ascending order (None when there is no data). The sorted array is
        kept while the file is unchanged; safe to call from the render thread."""
        with self._data_lock:
            data = self._get_data(folder_tag, field, force_refresh=force_refresh)
            if data is None or len(data) == 0:
                return None
            key = (folder_tag, field)
            cached = self._sorted_cache.get(key)
            if cached is not None and cached[0] is data:      # same array object = same file contents
                self._sorted_cache.move_to_end(key)
                return cached[1]
            ordered = np.sort(data)
            ordered.flags.writeable = False
            self._sorted_cache[key] = (data, ordered)
            while len(self._sorted_cache) > self._SORTED_CACHE_MAX:
                self._sorted_cache.popitem(last=False)
            return ordered

    def _plot_state(self):
        """Everything a plot needs from the widgets, read in the GUI thread, so that a render running in the
        worker thread neither touches Qt objects nor sees half of a later edit."""
        return {
            "rows": max(1, self.sp_rows.value()),
            "cols": max(1, self.sp_cols.value()),
            "axes_cfg": copy.deepcopy(self._axes_cfg),
            "res_dirs": list(self.app.res_dirs),
            "res_styles": copy.deepcopy(self.app.res_styles),
            "sel_indices": [i.row() for i in self.lb_dirs.selectedIndexes()],
            "plot_selected_only": self.var_plot_selected_only.get(),
        }

    def _scan_columns_handler(self):
        if not self.app.res_dirs:
            QMessageBox.information(self, "Info", "No folders added.")
            return

        folder = self.app.res_dirs[0]
        if folder.startswith("ssh://"):
            cli = self._get_ssh_client()
            if not cli: return
            remote_path = folder[6:]
            cols, f = self.data_client.scan_columns(cli, remote_path)
            if cols:
                self.cb_field.clear()
                self.cb_field.addItems(cols)
                self.result_fields = cols
                QMessageBox.information(self, "Success", f"Found columns in {f}: {cols}")
                return
            QMessageBox.critical(self, "Error", "Remote scan failed or no CSV found.")
            return
        else:
            try:
                import pandas as pd
                for f in os.listdir(folder):
                    if f.endswith(".csv"):
                        full_p = os.path.join(folder, f)
                        df = pd.read_csv(full_p, nrows=0)
                        cols = list(df.columns)
                        self.cb_field.clear()
                        self.cb_field.addItems(cols)
                        self.result_fields = cols
                        QMessageBox.information(self, "Success", f"Found columns in {f}: {cols}")
                        return
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Local scan failed: {e}")

        QMessageBox.warning(self, "Scan", "No CSV files found in the first folder.")

    # ---------------- UI Events ----------------
    def _load_style_from_selection(self, *args):
        items = self.lb_dirs.selectedIndexes()
        if not items: return
        idx = items[0].row()
        if idx < len(self.app.res_dirs):
            path = self.app.res_dirs[idx]
            style = self.app.res_styles.get(path, {})
            self.e_style_lbl.setText(style.get("label", ""))
            self.cb_style_col.setCurrentText(style.get("color", "Auto"))
            self.cb_style_ls.setCurrentText(style.get("linestyle", "Auto"))
            self.sp_style_lw.setValue(int(style.get("linewidth", 2)))

    def _apply_style(self):
        items = self.lb_dirs.selectedIndexes()
        if not items: return
        label = self.e_style_lbl.text().strip()
        color = self.cb_style_col.currentText()
        ls = self.cb_style_ls.currentText()
        lw = self.sp_style_lw.value()
        
        for item in items:
            idx = item.row()
            if idx < len(self.app.res_dirs):
                path = self.app.res_dirs[idx]
                if path not in self.app.res_styles:
                    self.app.res_styles[path] = {}
                self.app.res_styles[path]["label"] = label
                self.app.res_styles[path]["color"] = color
                self.app.res_styles[path]["linestyle"] = ls
                self.app.res_styles[path]["linewidth"] = float(lw)
        self._schedule_update()

    def _on_subplot_selection_change(self, text):
        self._load_subplot_config_to_ui()

    def _load_subplot_config_to_ui(self):
        idx = int(self.cb_subplot_sel.currentText()) - 1
        cfg = self._axes_cfg[idx]
        self._disable_traces = True
        
        self.cb_field.setCurrentText(cfg.get("field", ""))
        self.cb_mode.setCurrentText(cfg.get("mode", "CDF"))
        self.e_title.setText(cfg.get("title", ""))
        self.e_xlabel.setText(cfg.get("x_label", ""))
        self.e_ylabel.setText(cfg.get("y_label", ""))
        self.cb_xlog.setChecked(cfg.get("x_log", False))
        self.cb_ylog.setChecked(cfg.get("y_log", False))
        self.e_leg_suffix.setText(cfg.get("legend_suffix", ""))
        self.e_xshift.setText(str(cfg.get("x_shift", 0.0)))
        
        self.e_xmin.setText(cfg.get("x_min", ""))
        self.e_xmax.setText(cfg.get("x_max", ""))
        self.e_xstep.setText(cfg.get("x_step", ""))
        self.e_ymin.setText(cfg.get("y_min", ""))
        self.e_ymax.setText(cfg.get("y_max", ""))
        self.e_ystep.setText(cfg.get("y_step", ""))
        
        self._refresh_criteria_list(cfg.get("criteria", []))
        self._disable_traces = False

    def _on_config_change(self, *args):
        if self._disable_traces: return
        idx = int(self.cb_subplot_sel.currentText()) - 1
        cfg = self._axes_cfg[idx]
        
        cfg["field"] = self.cb_field.currentText()
        cfg["mode"] = self.cb_mode.currentText()
        cfg["title"] = self.e_title.text()
        cfg["x_label"] = self.e_xlabel.text()
        cfg["y_label"] = self.e_ylabel.text()
        cfg["x_log"] = self.cb_xlog.isChecked()
        cfg["y_log"] = self.cb_ylog.isChecked()
        cfg["legend_suffix"] = self.e_leg_suffix.text()
        cfg["x_min"] = self.e_xmin.text()
        cfg["x_max"] = self.e_xmax.text()
        cfg["x_step"] = self.e_xstep.text()
        cfg["y_min"] = self.e_ymin.text()
        cfg["y_max"] = self.e_ymax.text()
        cfg["y_step"] = self.e_ystep.text()
        try: cfg["x_shift"] = float(self.e_xshift.text())
        except ValueError: pass
            
        self._schedule_update()

    def _refresh_dir_listbox(self):
        self.lb_dirs.clear()
        for p in self.app.res_dirs:
            display = f"[SSH] {os.path.basename(p)}" if p.startswith("ssh://") else os.path.basename(os.path.normpath(p))
            if not display: display = p
            self.lb_dirs.addItem(display)

    def loaded_count(self) -> int:
        """Result folders currently listed."""
        return self.lb_dirs.count()

    def _sync_empty_state(self, *_):
        empty = self.loaded_count() == 0
        self.results_changed.emit()
        self.empty_state.setVisible(empty)
        if empty:
            self.lbl_preview.clear()

    def refresh_icons(self, tokens: dict) -> None:
        self.empty_state.refresh_icons(tokens)

    def _add_dir_handler(self):
        if self.rb_remote.isChecked():
            if paramiko is None:
                QMessageBox.critical(self, "Error", "Paramiko library missing.")
                return
            chosen_paths = self._remote_dir_picker()
            if chosen_paths:
                for p in chosen_paths:
                    full_p = f"ssh://{p}"
                    if full_p not in self.app.res_dirs:
                        self.app.res_dirs.append(full_p)
        else:
            path = QFileDialog.getExistingDirectory(self, "Select Result Folder")
            if path:
                if path not in self.app.res_dirs:
                    self.app.res_dirs.append(path)
        self._refresh_dir_listbox()
        self._schedule_update()

    def add_result_dir(self, path, refresh: bool = True) -> bool:
        """Add a local result folder (no-op when already listed). Returns True when it was added."""
        path = str(path)
        if path in self.app.res_dirs:
            return False
        self.app.res_dirs.append(path)
        self._refresh_dir_listbox()
        if refresh:
            self._schedule_update()
        return True

    def detect_results(self, roots=None) -> int:
        """Find result folders written by the simulator and add the ones not listed yet.

        Looks under `sharc/<output dir>` of the General tab and the default `sharc/output`, two levels deep.
        Returns how many folders were added; "Add Folder..." still accepts any folder."""
        from core.results_locator import SHARC_DIR, discover
        if roots is None:
            roots = [SHARC_DIR / "output"]
            out = str(self.app.var_outdir.get() or "").strip() if hasattr(self.app, "var_outdir") else ""
            if out:
                roots.append(SHARC_DIR / out)
        added = sum(1 for d in discover(roots) if self.add_result_dir(d, refresh=False))
        if added:
            self._refresh_dir_listbox()
            self._schedule_update()
        if hasattr(self.app, "_safe_log"):
            self.app._safe_log(f"[RESULTS] {added} new result folder(s) detected.")
        return added

    def _dirs_menu(self, pos):
        rows = sorted({i.row() for i in self.lb_dirs.selectedIndexes()})
        menu = QMenu(self)
        for text, slot in (("Detect results", lambda: self.detect_results()), ("Add folder... (Ctrl+O)", self._add_dir_handler)):
            menu.addAction(text, slot)
        menu.addSeparator()
        sel = menu.addAction("Open folder", lambda: self._open_dir(rows))
        sel.setEnabled(bool(rows))
        cp = menu.addAction("Copy path", lambda: self._copy_dir(rows))
        cp.setEnabled(bool(rows))
        rm = menu.addAction("Remove (Delete)", self._remove_dir)
        rm.setEnabled(bool(rows))
        menu.addSeparator()
        menu.addAction("Refresh plot (F5)", self._manual_refresh)
        menu.addAction("Select all (Ctrl+A)", self.lb_dirs.selectAll)
        menu.addAction("Clear list", self._clear_all_dirs)
        _exec_menu(menu, self.lb_dirs.viewport().mapToGlobal(pos))

    def _open_dir(self, rows):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        for i in rows[:1]:
            if i < len(self.app.res_dirs) and not self.app.res_dirs[i].startswith("ssh://"):
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.app.res_dirs[i]))

    def _copy_dir(self, rows):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText("\n".join(self.app.res_dirs[i] for i in rows if i < len(self.app.res_dirs)))

    def _remove_dir(self):
        rows = sorted({i.row() for i in self.lb_dirs.selectedIndexes() if 0 <= i.row() < len(self.app.res_dirs)},
                      reverse=True)
        for i in rows:
            del self.app.res_dirs[i]
        self._refresh_dir_listbox()
        self._schedule_update()

    def _clear_all_dirs(self):
        self.app.res_dirs.clear()
        self.app.res_styles.clear()
        self._refresh_dir_listbox()
        self._schedule_update()

    def _refresh_criteria_list(self, criteria_list):
        self.tv_crit.setRowCount(0)
        for i, c in enumerate(criteria_list):
            self.tv_crit.insertRow(i)
            status = "On" if c.get("enabled", True) else "Off"
            self.tv_crit.setItem(i, 0, QTableWidgetItem(status))
            self.tv_crit.setItem(i, 1, QTableWidgetItem(str(c.get("val", ""))))
            self.tv_crit.setItem(i, 2, QTableWidgetItem(c.get("type", "")))
            self.tv_crit.setItem(i, 3, QTableWidgetItem(c.get("label", "")))

    def _add_criteria_dialog(self):
        idx = int(self.cb_subplot_sel.currentText()) - 1
        cfg = self._axes_cfg[idx]
        
        win = QDialog(self)
        win.setWindowTitle("Add Protection Criteria")
        win.resize(320, 300)
        l = QVBoxLayout(win)
        
        l.addWidget(QLabel("Value:"))
        e_val = QLineEdit("0.0")
        l.addWidget(e_val)
        
        l.addWidget(QLabel("Type:"))
        cb_type = QComboBox()
        cb_type.addItems(["Vertical (X)", "Horizontal (Prob)"])
        l.addWidget(cb_type)
        
        l.addWidget(QLabel("Label:"))
        e_label = QLineEdit()
        l.addWidget(e_label)
        
        l.addWidget(QLabel("Color:"))
        cb_color = QComboBox()
        cb_color.addItems(["red", "green", "blue", "black", "orange"])
        l.addWidget(cb_color)
        
        def _apply():
            try:
                val = float(e_val.text())
                cfg["criteria"].append({"val": val, "type": cb_type.currentText(), "label": e_label.text(), "color": cb_color.currentText(), "enabled": True})
                self._refresh_criteria_list(cfg["criteria"])
                self._schedule_update()
                win.accept()
            except ValueError:
                QMessageBox.critical(win, "Error", "Invalid Number")
                
        btns = QHBoxLayout()
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(_apply)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(win.reject)
        btns.addWidget(btn_apply)
        btns.addWidget(btn_close)
        l.addLayout(btns)
        win.exec()

    def _selected_criteria_rows(self, criteria) -> list:
        """Distinct selected rows, valid for `criteria`. selectedItems() returns one item per CELL (4 per row),
        so rows must be de-duplicated; stale rows beyond the list are dropped instead of raising."""
        return sorted({i.row() for i in self.tv_crit.selectedItems() if 0 <= i.row() < len(criteria)})

    def _toggle_criteria(self, *args):
        idx = int(self.cb_subplot_sel.currentText()) - 1
        cfg = self._axes_cfg[idx]
        rows = self._selected_criteria_rows(cfg["criteria"])
        for r in rows:
            cfg["criteria"][r]["enabled"] = not cfg["criteria"][r].get("enabled", True)
        self._refresh_criteria_list(cfg["criteria"])      # also re-syncs a table that had gone stale
        if rows:
            self._schedule_update()

    def _remove_criteria(self):
        idx = int(self.cb_subplot_sel.currentText()) - 1
        cfg = self._axes_cfg[idx]
        for r in reversed(self._selected_criteria_rows(cfg["criteria"])):
            cfg["criteria"].pop(r)
        self._refresh_criteria_list(cfg["criteria"])
        self._schedule_update()

    def _manual_refresh(self):
        self._schedule_update(force_refresh=True)

    def _schedule_update(self, force_refresh=False):
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer.deleteLater()
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(lambda: self._update_plot_preview(force_refresh))
        self._update_timer.start(500)

    # ---------------- Plotly Core Logic ----------------
    def _create_plotly_fig(self, progress_callback=None, is_preview=False, force_refresh=False, state=None):
        if state is None:
            state = self._plot_state()
        rows, cols = state["rows"], state["cols"]
        axes_cfg, res_dirs, res_styles = state["axes_cfg"], state["res_dirs"], state["res_styles"]
        n_plots = min(rows*cols, self._max_axes)
        total_steps = n_plots * max(1, len(res_dirs))
        current_step = 0
        last_progress_time = 0

        titles = []
        for i in range(n_plots):
            cfg = axes_cfg[i]
            t = cfg.get("title")
            if not t: t = RESULT_FIELDNAME_TO_PLOT_INFO.get(cfg["field"], {}).get("title", cfg["field"])
            titles.append(t)

        fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles, vertical_spacing=0.12, horizontal_spacing=0.08)

        dash_map = {"-": "solid", "--": "dash", "-.": "dashdot", ":": "dot", "Auto": None}
        color_map = {"tab:blue": "#1f77b4", "tab:orange": "#ff7f0e", "tab:green": "#2ca02c", "tab:red": "#d62728"}
        
        sel_indices = state["sel_indices"]
        plot_selected_only = state["plot_selected_only"]
        refreshed = set()      # a forced refresh reads each file once, even when several subplots show it

        for i in range(n_plots):
            cfg = axes_cfg[i]
            r, c = (i // cols) + 1, (i % cols) + 1
            field = cfg["field"]

            for dir_idx, folder in enumerate(res_dirs):
                current_step += 1
                now = time.time()
                if progress_callback and total_steps > 0 and (now - last_progress_time > 0.1):
                    progress_callback((current_step / total_steps) * 80.0)
                    last_progress_time = now

                if plot_selected_only and (dir_idx not in sel_indices): continue

                ordered = self._get_sorted_data(folder, field,
                                                force_refresh=force_refresh and (folder, field) not in refreshed)
                refreshed.add((folder, field))
                if ordered is None: continue

                x, y = self._ecdf_from_sorted(ordered, ccdf=(cfg["mode"] == "CCDF"), downsample_to=2000 if is_preview else 0)
                x = x + cfg.get("x_shift", 0.0)
                if cfg["x_log"]: x, y = x[x > 0], y[x > 0]
                if cfg["y_log"]: x, y = x[y > 0], y[y > 0]

                if len(x) == 0: continue

                style = res_styles.get(folder, {})
                custom_label = style.get("label", "")
                name = custom_label if custom_label else (os.path.basename(folder) if "ssh://" not in folder else f"[SSH] {os.path.basename(folder)}")
                name += cfg.get('legend_suffix', '')

                line_props = dict(width=style.get("linewidth", 1.5))
                ls_val = style.get("linestyle", "Auto")
                if ls_val in dash_map and dash_map[ls_val]: line_props["dash"] = dash_map[ls_val]
                c_val = style.get("color", "Auto")
                if c_val != "Auto": line_props["color"] = color_map.get(c_val, c_val)

                trace_type = go.Scatter if is_preview else (go.Scattergl if len(x) > 10000 else go.Scatter)
                fig.add_trace(trace_type(x=x, y=y, mode='lines', name=name, line=line_props, legendgroup=folder, showlegend=(i == 0)), row=r, col=c)

            for crit in cfg.get("criteria", []):
                if not crit.get("enabled", True): continue
                try:
                    val = float(crit["val"])
                    if "Vertical" in crit["type"]: fig.add_vline(x=val, line_dash="dash", line_color=crit.get("color", "red"), annotation_text=crit.get("label"), row=r, col=c)
                    else: fig.add_hline(y=val, line_dash="dash", line_color=crit.get("color", "red"), annotation_text=crit.get("label"), row=r, col=c)
                except (ValueError, TypeError): pass

            xaxis_params = dict(title_text=cfg.get("x_label") or field, type="log" if cfg["x_log"] else "linear", showgrid=True)
            yaxis_params = dict(title_text=cfg.get("y_label") or f"Prob ({cfg['mode']})", type="log" if cfg["y_log"] else "linear", showgrid=True)
            
            try:
                xmin, xmax = float(cfg.get("x_min", "")), float(cfg.get("x_max", ""))
                if cfg["x_log"]: xaxis_params["range"] = [math.log10(xmin) if xmin > 0 else 0, math.log10(xmax) if xmax > 0 else 1]
                else: xaxis_params["range"] = [xmin, xmax]
            except ValueError: pass
            
            try:
                ymin, ymax = float(cfg.get("y_min", "")), float(cfg.get("y_max", ""))
                if cfg["y_log"]: yaxis_params["range"] = [math.log10(ymin) if ymin > 0 else 0, math.log10(ymax) if ymax > 0 else 1]
                else: yaxis_params["range"] = [ymin, ymax]
            except ValueError: pass

            fig.update_xaxes(xaxis_params, row=r, col=c)
            fig.update_yaxes(yaxis_params, row=r, col=c)

        fig.update_layout(template="plotly_white", margin=dict(l=50, r=20, t=50, b=50), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        return fig

    def _update_plot_preview(self, force_refresh=False):
        if self.loaded_count() == 0:          # nothing to plot: the empty state is showing, skip the render worker
            self._sync_empty_state()
            return
        engine = "MATPLOTLIB" if hasattr(self, 'rb_mpl') and self.rb_mpl.isChecked() else "PLOTLY"

        if engine == "PLOTLY" and self._render_busy:
            # A render is still running: draw again as soon as it ends instead of dropping this request
            # (the plot would otherwise keep showing the settings of the previous request).
            self._pending_refresh = bool(force_refresh) or bool(self._pending_refresh)
            return
        self._pending_refresh = None

        if self._mpl_canvas:
            self.preview_layout.removeWidget(self._mpl_canvas)
            self._mpl_canvas.setParent(None)
            self._mpl_canvas.close()
            self._mpl_canvas.deleteLater()
            self._mpl_canvas = None
        if self._mpl_toolbar:
            self.preview_layout.removeWidget(self._mpl_toolbar)
            self._mpl_toolbar.setParent(None)
            self._mpl_toolbar.close()
            self._mpl_toolbar.deleteLater()
            self._mpl_toolbar = None

        if engine == "MATPLOTLIB" and HAS_MATPLOTLIB:
            self.lbl_preview.hide()
            self.pb_loading.hide()
            try:
                plotter = MatplotlibPlotter(
                    self._axes_cfg, self.app.res_dirs, self.app.res_styles, 
                    self.sp_rows.value(), self.sp_cols.value(), self._max_axes
                )
                refreshed = set()

                def sorted_provider(folder, field):
                    force = force_refresh and (folder, field) not in refreshed
                    refreshed.add((folder, field))
                    return self._get_sorted_data(folder, field, force_refresh=force)

                sel_indices = [i.row() for i in self.lb_dirs.selectedIndexes()]
                fig = plotter.create_figure(sorted_provider, plot_selected_only=self.var_plot_selected_only.get(),
                                            selected_indices=sel_indices, data_is_sorted=True)
                
                self._mpl_canvas = FigureCanvasQTAgg(fig)
                self._mpl_toolbar = NavigationToolbar2QT(self._mpl_canvas, self.preview_frame)
                self.preview_layout.addWidget(self._mpl_canvas)
                self.preview_layout.addWidget(self._mpl_toolbar)
            except Exception as e:
                self.lbl_preview.show()
                self.lbl_preview.setText(f"Matplotlib Error: {e}")
        else:
            self.lbl_preview.show()
            w = max(400, min(self.lbl_preview.width(), 1920))
            h = max(300, min(self.lbl_preview.height(), 1080))
            
            self.lbl_preview.setText("Preparing Plot...")
            self.pb_loading.setValue(0)
            self.pb_loading.show()

            state = self._plot_state()     # widgets are read here, in the GUI thread
            self._render_busy = True
            threading.Thread(target=self._render_worker, args=(w, h, force_refresh, state),
                             daemon=True).start()

    def _stop_loading_ui(self):
        self.pb_loading.hide()

    def _on_render_error(self, msg):
        self._stop_loading_ui()
        self.lbl_preview.setText(msg)

    def _update_progress_ui(self, percent):
        self.pb_loading.setValue(int(percent))
        self.lbl_preview.setText(f"Plotting... {int(percent)}%")

    def _show_render_status(self, text: str, percent: int):
        self.lbl_preview.setText(text)
        self.pb_loading.setValue(percent)

    # ---- end of a render, delivered in the GUI thread by _ui_image / _ui_error ----
    def _on_render_done(self, img_bytes):
        self._render_busy = False
        if self._pending_refresh is None:      # else the settings changed meanwhile: draw again instead
            self._display_image(img_bytes)
        self._run_pending_refresh()

    def _on_render_failed(self, msg):
        self._render_busy = False
        if self._pending_refresh is None:
            self._on_render_error(msg)
        self._run_pending_refresh()

    def _run_pending_refresh(self):
        if self._pending_refresh is not None:
            force, self._pending_refresh = self._pending_refresh, None
            self._update_plot_preview(force)

    def _render_worker(self, w, h, force_refresh=False, state=None):
        if not self._render_lock.acquire(blocking=False):
            # another render is running; never leave "Preparing Plot..." on screen for a render that was dropped
            self._ui_error.emit("A plot is already being prepared. Press Refresh when it finishes.")
            return
        failure, img_bytes = None, None
        try:
            fig = self._create_plotly_fig(progress_callback=lambda p: self._ui_progress.emit(int(p)),
                                          is_preview=True, force_refresh=force_refresh, state=state)
            self._ui_status.emit("Rasterizing (the first plot starts the image engine and takes a few seconds)...", 90)
            with _KALEIDO_LOCK:
                img_bytes = fig.to_image(format="png", width=w, height=h, scale=1)
        except Exception as e:  # noqa: BLE001 - any plotting failure must reach the user
            failure = f"Plot Error:\n{type(e).__name__}: {e}"
        finally:
            self._render_lock.release()
        # emitted after the lock is released, so that a refresh asked meanwhile can start right away
        if failure is None:
            self._ui_image.emit(img_bytes)
        else:
            self._ui_error.emit(failure)

    def _display_image(self, img_bytes):
        self._stop_loading_ui()
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            self.lbl_preview.setPixmap(pixmap)
        except Exception as e:
            self.lbl_preview.setText(f"Image Error: {e}")

    def _open_browser(self):
        try:
            self.lbl_preview.setText("Generating Interactive HTML...")
            fig = self._create_plotly_fig(is_preview=False)
            import tempfile, webbrowser
            fd, path = tempfile.mkstemp(suffix=".html")
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(fig.to_html(include_plotlyjs='cdn'))
            webbrowser.open(f"file://{path}")
            self.lbl_preview.setText("")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))