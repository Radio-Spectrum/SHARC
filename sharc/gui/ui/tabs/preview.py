from __future__ import annotations

import os
import tempfile
import webbrowser
from typing import Any, Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QRadioButton, 
    QCheckBox, QLineEdit, QLabel, QGroupBox, QScrollArea, QTextEdit, 
    QDialog, QMessageBox
)
from PySide6.QtCore import Qt, QUrl

import matplotlib
matplotlib.use("QtAgg") # MUDANÇA CRÍTICA: Backend Qt nativo
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.pyplot as plt

# --- Import do Motor Chromium (PySide6-WebEngine) ---
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

# --- Core SHARC Imports (Preservados) ---
from utils import build_yaml_text, HAS_PLOTLY
from core.state import SharcVar
from core.geometry_3d import Geometry3DMixin
from ui.components.plot_engines import PlotEnginesMixin

from ui.tabs.assets.preview_tab.preview_detection import (
    get_current_yaml as _get_current_yaml,
    detect_system_type as _detect_system_type_fn,
    detect_topology_type as _detect_topology_type_fn,
)
from ui.tabs.assets.preview_tab.preview_catalog import (
    update_sim_summary as _update_sim_summary_fn,
    update_supported_catalog as _update_supported_catalog_fn,
)

try:
    import plotly.graph_objects as go
except ImportError:
    go = None

# ---------------------------------------------------------------------------
# Plotly Embed (PySide6 WebEngine)
# ---------------------------------------------------------------------------
class PlotlyEmbed(QWidget):
    """
    Embeds Plotly figure natively in PySide6 using QWebEngineView.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self._last_html_path = None

        if HAS_WEBENGINE:
            self.webview = QWebEngineView()
            self.main_layout.addWidget(self.webview)
        else:
            lbl = QLabel("Plotly embed requires 'PySide6-WebEngine'.\n"
                         "Install: pip install PySide6-WebEngine\n"
                         "Using external browser instead.")
            lbl.setStyleSheet("color: #ffcccc;")
            self.main_layout.addWidget(lbl)

    def set_figure(self, fig: "go.Figure", open_external: bool = False):
        if not HAS_PLOTLY:
            return

        html = fig.to_html(include_plotlyjs="cdn", full_html=True)
        fd, path = tempfile.mkstemp(prefix="sharc_preview_", suffix=".html")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self._last_html_path = path

        if HAS_WEBENGINE:
            self.webview.setUrl(QUrl.fromLocalFile(path))

        if open_external:
            self.open_in_browser()

    def open_in_browser(self):
        if self._last_html_path:
            webbrowser.open(self._last_html_path)

# ---------------------------------------------------------------------------
# Preview Tab Principal
# ---------------------------------------------------------------------------
class PreviewTab(QWidget, Geometry3DMixin, PlotEnginesMixin):
    """
    Main Preview Tab Logic for PySide6.
    Supports Matplotlib (Canvas3D) and Plotly (Native WebEngine Chromium).
    """

    def __init__(self, app: Any, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app

        # Substituição da injeção de vars do Tkinter pelo SharcVar nativo
        if not hasattr(self.app, "show_borders"):
            self.app.show_borders = SharcVar(True, bool)
        if not hasattr(self.app, "plot_engine"):
            self.app.plot_engine = SharcVar("matplotlib", str)
        if not hasattr(self.app, "show_beamwidth"):
            self.app.show_beamwidth = SharcVar(True, bool)
        if not hasattr(self.app, "var_auto_beamwidth"):
            self.app.var_auto_beamwidth = SharcVar(True, bool)
        if not hasattr(self.app, "var_beamwidth_deg"):
            self.app.var_beamwidth_deg = SharcVar("2.0", str)
        if not hasattr(self.app, "open_plotly_external"):
            self.app.open_plotly_external = SharcVar(False, bool)
        if not hasattr(self.app, "var_show_gainmap"):
            self.app.var_show_gainmap = SharcVar(False, bool)
        if not hasattr(self.app, "var_gain_vmin"):
            self.app.var_gain_vmin = SharcVar("-10", str)
        if not hasattr(self.app, "var_gain_vmax"):
            self.app.var_gain_vmax = SharcVar("50", str)

        self._plotly_embed: Optional[PlotlyEmbed] = None
        self._plotly_last_fig: Optional["go.Figure"] = None

        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # ═══════════════════════════════════════════════
        # LEFT PANEL (Plot Display)
        # ═══════════════════════════════════════════════
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_scenario = QLabel("Scenario Preview")
        self._lbl_scenario.setAlignment(Qt.AlignCenter)
        self._lbl_scenario.setStyleSheet("color: #2196F3; font-weight: bold; font-size: 14px;")
        left_layout.addWidget(self._lbl_scenario)

        # Matplotlib 3D Canvas
        from matplotlib.figure import Figure
        self.fig3d = Figure(figsize=(6, 6), facecolor="#1a1a2e")
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.canvas3d = FigureCanvasQTAgg(self.fig3d)
        
        # Conecta o zoom ao scroll do mouse pelo backend do matplotlib
        self.fig3d.canvas.mpl_connect('scroll_event', self._on_scroll_3d)
        left_layout.addWidget(self.canvas3d)

        # Plotly HTML Embed
        self._plotly_embed = PlotlyEmbed()
        self._plotly_embed.hide()
        left_layout.addWidget(self._plotly_embed)

        main_layout.addWidget(left_panel, stretch=7)

        # ═══════════════════════════════════════════════
        # RIGHT SIDEBAR (Controls & Summaries)
        # ═══════════════════════════════════════════════
        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFixedWidth(300)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # --- 1. Main Action ---
        btn_refresh = QPushButton("🔄  Refresh Preview")
        btn_refresh.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 8px;")
        btn_refresh.clicked.connect(self._draw_preview)
        right_layout.addWidget(btn_refresh)

        # --- 2. Engine Selection ---
        frm_engine = QGroupBox("Plot Engine")
        l_engine = QVBoxLayout(frm_engine)
        
        rb_mpl = QRadioButton("Matplotlib (3D)")
        rb_plt = QRadioButton("Plotly (Interactive)")
        cb_ext = QCheckBox("Auto-open browser")
        
        # Binding do radio button ao SharcVar (Mpl)
        def _set_mpl(): self.app.plot_engine.set("matplotlib"); self._draw_preview()
        def _set_plt(): self.app.plot_engine.set("plotly"); self._draw_preview()
        
        rb_mpl.clicked.connect(_set_mpl)
        rb_plt.clicked.connect(_set_plt)
        
        if self.app.plot_engine.get() == "plotly":
            rb_plt.setChecked(True)
        else:
            rb_mpl.setChecked(True)

        self.app.open_plotly_external.value_changed.connect(cb_ext.setChecked)
        cb_ext.toggled.connect(self.app.open_plotly_external.set)

        l_engine.addWidget(rb_mpl)
        l_engine.addWidget(rb_plt)
        l_engine.addWidget(cb_ext)
        right_layout.addWidget(frm_engine)

        # --- 3. Display Options ---
        frm_vis = QGroupBox("Display Options")
        l_vis = QVBoxLayout(frm_vis)

        cb_borders = QCheckBox("Show country borders")
        self.app.show_borders.value_changed.connect(cb_borders.setChecked)
        cb_borders.toggled.connect(lambda v: (self.app.show_borders.set(v), self._draw_preview()))
        cb_borders.setChecked(self.app.show_borders.get())
        l_vis.addWidget(cb_borders)

        cb_footprint = QCheckBox("Show satellite footprint")
        self.app.show_beamwidth.value_changed.connect(cb_footprint.setChecked)
        cb_footprint.toggled.connect(lambda v: (self.app.show_beamwidth.set(v), self._draw_preview()))
        cb_footprint.setChecked(self.app.show_beamwidth.get())
        l_vis.addWidget(cb_footprint)

        # Auto BW
        f_bw = QHBoxLayout()
        cb_auto_bw = QCheckBox("Auto BW")
        self.app.var_auto_beamwidth.value_changed.connect(cb_auto_bw.setChecked)
        cb_auto_bw.toggled.connect(lambda v: (self.app.var_auto_beamwidth.set(v), self._draw_preview()))
        cb_auto_bw.setChecked(self.app.var_auto_beamwidth.get())
        
        e_bw = QLineEdit()
        e_bw.setFixedWidth(50)
        self.app.var_beamwidth_deg.value_changed.connect(e_bw.setText)
        e_bw.textChanged.connect(self.app.var_beamwidth_deg.set)
        e_bw.setText(self.app.var_beamwidth_deg.get())

        f_bw.addWidget(cb_auto_bw)
        f_bw.addWidget(QLabel(" / "))
        f_bw.addWidget(e_bw)
        f_bw.addWidget(QLabel("°"))
        f_bw.addStretch()
        l_vis.addLayout(f_bw)

        # Gain Map
        cb_gainmap = QCheckBox("Show gain map")
        self.app.var_show_gainmap.value_changed.connect(cb_gainmap.setChecked)
        cb_gainmap.toggled.connect(lambda v: (self.app.var_show_gainmap.set(v), self._draw_preview()))
        cb_gainmap.setChecked(self.app.var_show_gainmap.get())
        l_vis.addWidget(cb_gainmap)

        f_clim = QHBoxLayout()
        e_vmin = QLineEdit()
        e_vmax = QLineEdit()
        e_vmin.setFixedWidth(40)
        e_vmax.setFixedWidth(40)

        self.app.var_gain_vmin.value_changed.connect(e_vmin.setText)
        e_vmin.textChanged.connect(self.app.var_gain_vmin.set)
        e_vmin.setText(self.app.var_gain_vmin.get())

        self.app.var_gain_vmax.value_changed.connect(e_vmax.setText)
        e_vmax.textChanged.connect(self.app.var_gain_vmax.set)
        e_vmax.setText(self.app.var_gain_vmax.get())

        f_clim.addWidget(QLabel("vMin:"))
        f_clim.addWidget(e_vmin)
        f_clim.addWidget(QLabel("vMax:"))
        f_clim.addWidget(e_vmax)
        f_clim.addStretch()
        l_vis.addLayout(f_clim)

        right_layout.addWidget(frm_vis)

        # --- 4. Tools ---
        frm_tools = QGroupBox("Tools")
        l_tools = QVBoxLayout(frm_tools)
        
        f_zoom = QHBoxLayout()
        btn_z_in = QPushButton("🔍+")
        btn_z_out = QPushButton("🔍−")
        btn_save = QPushButton("💾 Save Image")
        
        btn_z_in.clicked.connect(lambda: self._zoom_preview_3d(1/1.15))
        btn_z_out.clicked.connect(lambda: self._zoom_preview_3d(1.15))
        btn_save.clicked.connect(self._save_image)

        f_zoom.addWidget(btn_z_in)
        f_zoom.addWidget(btn_z_out)
        f_zoom.addWidget(btn_save)
        l_tools.addLayout(f_zoom)

        btn_open_br = QPushButton("🌐 Open Plotly in Browser")
        btn_open_br.clicked.connect(self._open_plotly)
        l_tools.addWidget(btn_open_br)

        right_layout.addWidget(frm_tools)

        # --- 5. Supported Types ---
        frm_catalog = QGroupBox("✅ Visible Before Run")
        l_cat = QVBoxLayout(frm_catalog)
        self.txt_catalog = QTextEdit()
        self.txt_catalog.setStyleSheet("background-color: #101726; color: #d8e6ff; font-family: Consolas; font-size: 11px;")
        self.txt_catalog.setReadOnly(True)
        self.txt_catalog.setFixedHeight(120)
        l_cat.addWidget(self.txt_catalog)
        right_layout.addWidget(frm_catalog)

        # --- 6. Simulation Summary ---
        frm_summary = QGroupBox("📋 Simulation Summary")
        l_sum = QVBoxLayout(frm_summary)
        self.txt_summary = QTextEdit()
        self.txt_summary.setStyleSheet("background-color: #1a1a2e; color: #e0e0e0; font-family: Consolas; font-size: 11px;")
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setFixedHeight(150)
        l_sum.addWidget(self.txt_summary)

        f_sum_btns = QHBoxLayout()
        btn_ref_sum = QPushButton("🔄 Refresh")
        btn_pop_sum = QPushButton("📌 Pop Out")
        btn_ref_sum.clicked.connect(self._update_sim_summary)
        btn_pop_sum.clicked.connect(self._pop_out_summary)
        f_sum_btns.addWidget(btn_ref_sum)
        f_sum_btns.addWidget(btn_pop_sum)
        l_sum.addLayout(f_sum_btns)
        right_layout.addWidget(frm_summary)

        # --- 7. YAML Preview ---
        frm_yaml = QGroupBox("📝 YAML Preview")
        l_yaml = QVBoxLayout(frm_yaml)
        self.txt_yaml = QTextEdit()
        self.txt_yaml.setStyleSheet("background-color: #0d1117; color: #c9d1d9; font-family: Consolas; font-size: 11px;")
        self.txt_yaml.setReadOnly(True)
        self.txt_yaml.setFixedHeight(150)
        l_yaml.addWidget(self.txt_yaml)

        f_yml_btns = QHBoxLayout()
        btn_ref_yaml = QPushButton("🔄 Update YAML")
        btn_pop_yaml = QPushButton("📌 Pop Out")
        btn_ref_yaml.clicked.connect(self._update_yaml_preview)
        btn_pop_yaml.clicked.connect(self._pop_out_yaml)
        f_yml_btns.addWidget(btn_ref_yaml)
        f_yml_btns.addWidget(btn_pop_yaml)
        l_yaml.addLayout(f_yml_btns)
        right_layout.addWidget(frm_yaml)

        right_layout.addStretch()
        self.right_scroll.setWidget(right_panel)
        main_layout.addWidget(self.right_scroll, stretch=3)

        self._update_supported_catalog("", "")
        self.refresh()

    # =========================================================================
    # Helpers & Callbacks
    # =========================================================================

    def _pop_out_summary(self):
        self.pop_sum = QDialog(self)
        self.pop_sum.setWindowTitle("Simulation Summary")
        self.pop_sum.resize(400, 500)
        l = QVBoxLayout(self.pop_sum)
        txt = QTextEdit()
        txt.setStyleSheet("background-color: #1a1a2e; color: #e0e0e0; font-family: Consolas;")
        txt.setPlainText(self.txt_summary.toPlainText())
        txt.setReadOnly(True)
        l.addWidget(txt)
        btn = QPushButton("Close")
        btn.clicked.connect(self.pop_sum.accept)
        l.addWidget(btn)
        self.pop_sum.show()

    def _update_yaml_preview(self):
        data = self._current_yaml()
        text = build_yaml_text(data) if data else "No configuration generated."
        if hasattr(self, "txt_yaml"):
            self.txt_yaml.setPlainText(text)

    def refresh(self):
        self._update_yaml_preview()
        self._update_sim_summary()
        # O _draw_preview deve estar definido nos Mixins (PlotEnginesMixin) da sua classe base
        if hasattr(self, '_draw_preview'):
            self._draw_preview()

    def _pop_out_yaml(self):
        self._update_yaml_preview()
        self.pop_yaml = QDialog(self)
        self.pop_yaml.setWindowTitle("YAML Configuration")
        self.pop_yaml.resize(600, 600)
        l = QVBoxLayout(self.pop_yaml)
        txt = QTextEdit()
        txt.setStyleSheet("background-color: #0d1117; color: #c9d1d9; font-family: Consolas;")
        txt.setPlainText(self.txt_yaml.toPlainText())
        txt.setReadOnly(True)
        l.addWidget(txt)
        btn = QPushButton("Close")
        btn.clicked.connect(self.pop_yaml.accept)
        l.addWidget(btn)
        self.pop_yaml.show()

    def _update_sim_summary(self):
        _update_sim_summary_fn(self, self._current_yaml())

    def _current_yaml(self) -> Dict[str, Any]:
        return _get_current_yaml(self.app)

    def _detect_system_type(self, data: Dict[str, Any]) -> str:
        return _detect_system_type_fn(data, self.app)

    def _update_supported_catalog(self, topo_type: str, sys_type: str):
        _update_supported_catalog_fn(self, topo_type, sys_type)

    def _detect_topology_type(self, data: Dict[str, Any]) -> str:
        return _detect_topology_type_fn(data, self.app)

    def _open_plotly(self):
        if not HAS_PLOTLY:
            QMessageBox.critical(self, "Error", "Plotly is not installed.")
            return

        if self._plotly_last_fig:
            self._plotly_embed.set_figure(self._plotly_last_fig, open_external=True)
        else:
            self._plotly_embed.open_in_browser()

    def _on_scroll_3d(self, event):
        """Captura scroll do mouse no Matplotlib nativamente."""
        base = 1.15
        # event.step contains scroll direction in matplotlib backend
        direction = -1 if event.step > 0 else 1
        self._zoom_preview_3d(1.0/base if direction < 0 else base)

    def _zoom_preview_3d(self, factor: float):
        try:
            self.ax3d.dist = max(1, float(self.ax3d.dist) * float(factor))
            self.canvas3d.draw_idle()
        except Exception:
            pass
            
    # O método _save_image() deve estar implementado no PlotEnginesMixin. 
    # Caso precise, ele chamará o FileDialog do Qt para salvar.