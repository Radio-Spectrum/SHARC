from __future__ import annotations

import os
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QRadioButton,
    QCheckBox, QLineEdit, QLabel, QGroupBox, QScrollArea, QTextEdit,
    QDialog
)
from PySide6.QtCore import Qt

import matplotlib
matplotlib.use("QtAgg") # MUDANÇA CRÍTICA: Backend Qt nativo
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

# --- Import do Motor Chromium (PySide6-WebEngine) ---
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

# --- CesiumJS engine (motor primário — ver CESIUMJS_MIGRATION_PLAN.md) ---
# Requires QtWebEngine *and* the vendored Cesium static build, which is not
# committed to git (see .gitignore) — fetched locally per
# web/cesium_preview/local_server.py's module docstring. Matplotlib remains
# available as a secondary/fallback engine when either is missing.
HAS_CESIUM = False
if HAS_WEBENGINE:
    try:
        from web.cesium_preview.spike_widget import CesiumSpikeWidget
        from web.cesium_preview.local_server import _WEB_ROOT as _CESIUM_WEB_ROOT
        HAS_CESIUM = os.path.isdir(os.path.join(_CESIUM_WEB_ROOT, "vendor", "cesium"))
    except ImportError:
        HAS_CESIUM = False

# --- Core SHARC Imports (Preservados) ---
from utils import build_yaml_text
from core.state import SharcVar
from core.geometry_3d import Geometry3DMixin
from core.scene_builder import SceneBuilderMixin
from core.cesium_bridge import CesiumBridgeMixin
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

# ---------------------------------------------------------------------------
# Preview Tab Principal
# ---------------------------------------------------------------------------
class PreviewTab(QWidget, Geometry3DMixin, SceneBuilderMixin, CesiumBridgeMixin, PlotEnginesMixin):
    """
    Main Preview Tab Logic for PySide6.
    CesiumJS (3D Globe) is the primary rendering engine; Matplotlib (Canvas3D)
    is the secondary/fallback engine (no WebEngine, no vendored Cesium build,
    or explicitly selected by the user).
    """

    def __init__(self, app: Any, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app

        # Substituição da injeção de vars do Tkinter pelo SharcVar nativo
        if not hasattr(self.app, "show_borders"):
            self.app.show_borders = SharcVar(True, bool)
        if not hasattr(self.app, "plot_engine"):
            self.app.plot_engine = SharcVar("cesium" if HAS_CESIUM else "matplotlib", str)
        if not hasattr(self.app, "show_beamwidth"):
            self.app.show_beamwidth = SharcVar(True, bool)
        if not hasattr(self.app, "var_auto_beamwidth"):
            self.app.var_auto_beamwidth = SharcVar(True, bool)
        if not hasattr(self.app, "var_beamwidth_deg"):
            self.app.var_beamwidth_deg = SharcVar("2.0", str)
        if not hasattr(self.app, "var_show_gainmap"):
            self.app.var_show_gainmap = SharcVar(False, bool)
        if not hasattr(self.app, "var_gain_vmin"):
            self.app.var_gain_vmin = SharcVar("-10", str)
        if not hasattr(self.app, "var_gain_vmax"):
            self.app.var_gain_vmax = SharcVar("50", str)

        self._cesium_embed: Optional["CesiumSpikeWidget"] = None

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

        # CesiumJS Embed (motor primário — ver CESIUMJS_MIGRATION_PLAN.md) —
        # dados reais do cenário via self._cesium_scene_provider
        # (core/cesium_bridge.py), não topologias de demonstração.
        if HAS_CESIUM:
            self._cesium_embed = CesiumSpikeWidget(
                scene_provider=self._cesium_scene_provider, embedded=True)
            left_layout.addWidget(self._cesium_embed)

        # Matplotlib 3D Canvas (motor secundário/fallback)
        from matplotlib.figure import Figure
        self.fig3d = Figure(figsize=(6, 6), facecolor="#1a1a2e")
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.canvas3d = FigureCanvasQTAgg(self.fig3d)

        # Conecta o zoom ao scroll do mouse pelo backend do matplotlib
        self.fig3d.canvas.mpl_connect('scroll_event', self._on_scroll_3d)
        left_layout.addWidget(self.canvas3d)

        # _draw_preview() (called via self.refresh() below) sets the
        # correct initial visibility based on self.app.plot_engine.
        if self._cesium_embed is not None:
            self._cesium_embed.hide()
        self.canvas3d.hide()

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
        
        rb_cesium = QRadioButton("CesiumJS (3D Globe)")
        rb_mpl = QRadioButton("Matplotlib (3D) — secondary")

        # Binding do radio button ao SharcVar
        def _set_cesium(): self.app.plot_engine.set("cesium"); self._draw_preview()
        def _set_mpl(): self.app.plot_engine.set("matplotlib"); self._draw_preview()

        rb_cesium.clicked.connect(_set_cesium)
        rb_mpl.clicked.connect(_set_mpl)

        if not HAS_CESIUM:
            rb_cesium.setEnabled(False)
            rb_cesium.setToolTip(
                "Requires PySide6-WebEngine and the vendored CesiumJS build "
                "(see sharc/gui/web/cesium_preview/local_server.py's docstring)."
            )

        engine = self.app.plot_engine.get()
        if engine == "cesium" and HAS_CESIUM:
            rb_cesium.setChecked(True)
        else:
            rb_mpl.setChecked(True)

        l_engine.addWidget(rb_cesium)
        l_engine.addWidget(rb_mpl)
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