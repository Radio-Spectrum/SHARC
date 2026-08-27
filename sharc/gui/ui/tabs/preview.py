from __future__ import annotations

import os
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QLineEdit, QLabel, QGroupBox, QScrollArea, QTextEdit,
    QDialog
)
from PySide6.QtCore import Qt

try:
    from PySide6 import QtWebEngineWidgets  # noqa: F401
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

HAS_CESIUM = False
if HAS_WEBENGINE:
    try:
        from web.cesium_preview.spike_widget import CesiumSpikeWidget
        from web.cesium_preview.local_server import _WEB_ROOT as _CESIUM_WEB_ROOT
        HAS_CESIUM = os.path.isdir(os.path.join(_CESIUM_WEB_ROOT, "vendor", "cesium"))
    except ImportError:
        HAS_CESIUM = False

from utils import build_yaml_text
from core.state import SharcVar
from core.geometry_3d import Geometry3DMixin
from core.scene_builder import SceneBuilderMixin
from core.cesium_bridge import CesiumBridgeMixin

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
class PreviewTab(QWidget, Geometry3DMixin, SceneBuilderMixin, CesiumBridgeMixin):
    """
    Preview Tab — CesiumJS 3D Globe rendering engine.
    """

    def __init__(self, app: Any, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app

        if not hasattr(self.app, "show_borders"):
            self.app.show_borders = SharcVar(True, bool)
        if not hasattr(self.app, "plot_engine"):
            self.app.plot_engine = SharcVar("cesium", str)
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
        # LEFT PANEL (CesiumJS Globe)
        # ═══════════════════════════════════════════════
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_scenario = QLabel("Scenario Preview")
        self._lbl_scenario.setAlignment(Qt.AlignCenter)
        self._lbl_scenario.setObjectName("PageTitle")
        left_layout.addWidget(self._lbl_scenario)

        if HAS_CESIUM:
            self._cesium_embed = CesiumSpikeWidget(
                scene_provider=self._cesium_scene_provider, embedded=True)
            left_layout.addWidget(self._cesium_embed)
        else:
            lbl_no_cesium = QLabel(
                "CesiumJS not available.\n\n"
                "Install PySide6-WebEngine and fetch the vendored Cesium build\n"
                "(see sharc/gui/web/cesium_preview/local_server.py)."
            )
            lbl_no_cesium.setAlignment(Qt.AlignCenter)
            lbl_no_cesium.setObjectName("StatusMsg")
            left_layout.addWidget(lbl_no_cesium)

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
        btn_refresh = QPushButton("Refresh Preview")
        btn_refresh.setObjectName("ActionBtn")
        btn_refresh.clicked.connect(self._draw_preview)
        right_layout.addWidget(btn_refresh)

        # --- 2. Display Options ---
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

        # --- 3. Supported Types ---
        frm_catalog = QGroupBox("Visible Before Run")
        l_cat = QVBoxLayout(frm_catalog)
        self.txt_catalog = QTextEdit()
        self.txt_catalog.setObjectName("ConsoleLog")
        self.txt_catalog.setReadOnly(True)
        self.txt_catalog.setFixedHeight(120)
        l_cat.addWidget(self.txt_catalog)
        right_layout.addWidget(frm_catalog)

        # --- 6. Simulation Summary ---
        frm_summary = QGroupBox("Simulation Summary")
        l_sum = QVBoxLayout(frm_summary)
        self.txt_summary = QTextEdit()
        self.txt_summary.setObjectName("ConsoleLog")
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setFixedHeight(150)
        l_sum.addWidget(self.txt_summary)

        f_sum_btns = QHBoxLayout()
        btn_ref_sum = QPushButton("Refresh")
        btn_pop_sum = QPushButton("Pop Out")
        btn_ref_sum.clicked.connect(self._update_sim_summary)
        btn_pop_sum.clicked.connect(self._pop_out_summary)
        f_sum_btns.addWidget(btn_ref_sum)
        f_sum_btns.addWidget(btn_pop_sum)
        l_sum.addLayout(f_sum_btns)
        right_layout.addWidget(frm_summary)

        # --- 7. YAML Preview ---
        frm_yaml = QGroupBox("YAML Preview")
        l_yaml = QVBoxLayout(frm_yaml)
        self.txt_yaml = QTextEdit()
        self.txt_yaml.setObjectName("ConsoleLog")
        self.txt_yaml.setReadOnly(True)
        self.txt_yaml.setFixedHeight(150)
        l_yaml.addWidget(self.txt_yaml)

        f_yml_btns = QHBoxLayout()
        btn_ref_yaml = QPushButton("Update YAML")
        btn_pop_yaml = QPushButton("Pop Out")
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
        txt.setObjectName("ConsoleLog")
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
        self._draw_preview()

    def _pop_out_yaml(self):
        self._update_yaml_preview()
        self.pop_yaml = QDialog(self)
        self.pop_yaml.setWindowTitle("YAML Configuration")
        self.pop_yaml.resize(600, 600)
        l = QVBoxLayout(self.pop_yaml)
        txt = QTextEdit()
        txt.setObjectName("ConsoleLog")
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

    def _resolve_preview_type(self, topo_type: str, sys_type: str) -> str:
        """Pick the scene type to render.

        System types that correspond to a dedicated global renderer
        (satellite/earth-station/HAPS) take priority over the IMT
        topology whenever they differ — otherwise a user who switches
        ``general.system`` to SINGLE_SPACE_STATION still sees MACROCELL.
        """
        SYSTEM_OVERRIDES = {
            "SINGLE_SPACE_STATION", "SINGLE_EARTH_STATION",
            "HAPS", "MSS_SS", "MSS_D2D", "MSS_DC",
            "EESS_SS", "METSAT_SS", "FSS_SS",
        }
        if sys_type in SYSTEM_OVERRIDES and topo_type not in (
            "Macro_countries", "NTN", "INDOOR",
            sys_type,
        ):
            return sys_type
        return topo_type

    def _draw_preview(self):
        data = self._current_yaml()
        topo_type = self._detect_topology_type(data)
        sys_type = self._detect_system_type(data)
        scene_type = self._resolve_preview_type(topo_type, sys_type)

        self._update_sim_summary()
        self._update_supported_catalog(topo_type, sys_type)

        if self._cesium_embed is not None:
            self._cesium_embed.show()
            try:
                self._cesium_embed.request_scene(scene_type)
            except Exception as e:
                print(f"[PreviewTab] CesiumJS render failed: {e}")