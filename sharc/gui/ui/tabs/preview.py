from __future__ import annotations

import os
import math
import json
import time
import tempfile
import webbrowser
import traceback
from typing import Any, Dict, Optional, Tuple, List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import matplotlib.pyplot as plt

# --- All shared helpers and SHARC imports come from utils ---
from utils import (
    # Optional lib flags
    HAS_PLOTLY, HAS_TKHTMLVIEW, HAS_PYSHP, HAS_GEOPANDAS,
    # YAML / type helpers
    lla_to_ecef, build_yaml_text, WGS84_A,
    _yaml_get, _yaml_first, _as_value,
    _safe_float, _safe_int,
    _coerce_float, _coerce_int, _coerce_str,
    # GUI state helpers
    _get_imt_value, _get_countries_text, _parse_country_names, _normalize_raster_encoding,
    # Geometry helpers
    _unit, _guess_antenna_beamwidth_deg, _approx_hex_cluster_centers,
    _antenna_gain_db, _antenna_gain_db_batch,
    # Preview constants
    SUPPORTED_TOPOLOGY_TYPES, SUPPORTED_SYSTEM_TYPES, GLOBAL_PREVIEW_TYPES,
    # SHARC core flags and classes
    HAS_SHARC_CORE,
    TopologyMacrocell, TopologyHotspot, TopologySingleBaseStation,
    TopologyIndoor, TopologyNTN, TopologyCountries, TopologyUEOnly,
    ParametersCountries, ParametersHotspot, ParametersIndoor,
    ParametersSingleSpaceStation, ParametersSingleEarthStation,
    StationFactory, AntennaS672, ParametersAntennaS672,
)

# Conditional imports that need local variable bindings
try:
    import plotly.graph_objects as go
except Exception:
    go = None

try:
    from tkhtmlview import HTMLLabel
except Exception:
    HTMLLabel = None

try:
    import shapefile as pyshp
except Exception:
    pyshp = None

try:
    import geopandas as gpd
except Exception:
    gpd = None

# ---------------------------------------------------------------------------
# Modular sub-modules (extracted for maintainability)
# ---------------------------------------------------------------------------
from ui.tabs.assets.preview_tab.preview_detection import (
    get_current_yaml as _get_current_yaml,
    detect_system_type as _detect_system_type_fn,
    detect_topology_type as _detect_topology_type_fn,
)
from ui.tabs.assets.preview_tab.preview_catalog import (
    update_sim_summary as _update_sim_summary_fn,
    update_supported_catalog as _update_supported_catalog_fn,
)


class PlotlyEmbed(ttk.Frame):
    """
    Embeds Plotly figure HTML in Tk via tkhtmlview if available.
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self._html_label = None
        self._last_html_path = None

        if HAS_TKHTMLVIEW:
            self._html_label = HTMLLabel(
                self, html="<b>Plotly preview area</b>")
            self._html_label.pack(fill="both", expand=True)
        else:
            ttk.Label(self, text="Plotly embed requires 'tkhtmlview'.\n"
                                 "Install: pip install tkhtmlview\n"
                                 "Using external browser instead.",
                      justify="left").pack(anchor="w", pady=8)

    def set_figure(self, fig: "go.Figure", open_external: bool = False):
        if not HAS_PLOTLY:
            return

        html = fig.to_html(include_plotlyjs="cdn", full_html=True)

        fd, path = tempfile.mkstemp(prefix="sharc_preview_", suffix=".html")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self._last_html_path = path

        if HAS_TKHTMLVIEW and self._html_label is not None:
            try:
                self._html_label.set_html(html)
            except Exception:
                self._html_label.set_html(
                    f"<b>Plot generated.</b><br>Saved to: {path}")

        if open_external:
            webbrowser.open(path)

    def open_in_browser(self):
        if self._last_html_path:
            webbrowser.open(self._last_html_path)


from ui.components.scroll_containers import ScrollableContainer

from core.geometry_3d import Geometry3DMixin
from ui.components.plot_engines import PlotEnginesMixin
class PreviewTab(Geometry3DMixin, PlotEnginesMixin):
    """
    Main Preview Tab Logic.
    Supports Matplotlib (Canvas3D) and Plotly (HTML/Browser).
    """

    def __init__(self, app: Any, parent_frame: tk.Widget):
        self.app = app
        self.frame = parent_frame

        if not hasattr(self.app, "show_borders"):
            self.app.show_borders = tk.BooleanVar(value=True)
        if not hasattr(self.app, "plot_engine"):
            self.app.plot_engine = tk.StringVar(value="matplotlib")
        if not hasattr(self.app, "show_beamwidth"):
            self.app.show_beamwidth = tk.BooleanVar(value=True)
        if not hasattr(self.app, "var_auto_beamwidth"):
            self.app.var_auto_beamwidth = tk.BooleanVar(value=True)
        if not hasattr(self.app, "var_beamwidth_deg"):
            self.app.var_beamwidth_deg = tk.StringVar(value="2.0")
        if not hasattr(self.app, "open_plotly_external"):
            self.app.open_plotly_external = tk.BooleanVar(value=False)

        if not hasattr(self.app, "var_show_gainmap"):
            self.app.var_show_gainmap = tk.BooleanVar(value=False)
        if not hasattr(self.app, "var_gain_vmin"):
            self.app.var_gain_vmin = tk.StringVar(value="-10")
        if not hasattr(self.app, "var_gain_vmax"):
            self.app.var_gain_vmax = tk.StringVar(value="50")

        self._plotly_embed: Optional[PlotlyEmbed] = None
        self._plotly_last_fig: Optional["go.Figure"] = None

        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self.frame)
        self.right_scroll = ScrollableContainer(self.frame, width=280)
        
        left.pack(side="left", fill="both", expand=True)
        self.right_scroll.pack(side="right", fill="y", padx=5, pady=5)
        self.right_scroll.pack_propagate(False)
        self.right_scroll.canvas.config(width=280) # Force minimum width
        
        right = self.right_scroll.container

        # --- Scenario Header Label ---
        self._lbl_scenario = ttk.Label(
            left, text="", font=("Segoe UI", 10, "bold"),
            foreground="#2196F3", anchor="center")
        self._lbl_scenario.pack(fill="x", pady=(4, 0))

        # --- Plot area ---
        self.fig3d = plt.figure(figsize=(6, 6), facecolor="#1a1a2e")
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

        self._plotly_embed = PlotlyEmbed(left)
        self._plotly_embed.pack_forget()

        # ═══════════════════════════════════════════════
        # RIGHT SIDEBAR
        # ═══════════════════════════════════════════════

        # --- 1. Main Action ---
        ttk.Button(right, text="🔄  Refresh Preview",
                   command=self._draw_preview,
                   bootstyle="primary").pack(fill="x", pady=(0, 8))

        # --- 2. Engine Selection ---
        frm_engine = ttk.Labelframe(right, text="Plot Engine", padding=4)
        frm_engine.pack(fill="x", pady=(0, 6))
        ttk.Radiobutton(frm_engine, text="Matplotlib (3D)",
                        variable=self.app.plot_engine, value="matplotlib",
                        command=self._draw_preview).pack(anchor="w")
        ttk.Radiobutton(frm_engine, text="Plotly (Interactive)",
                        variable=self.app.plot_engine, value="plotly",
                        command=self._draw_preview).pack(anchor="w")
        ttk.Checkbutton(frm_engine, text="Auto-open browser",
                        variable=self.app.open_plotly_external).pack(anchor="w", padx=15)

        # --- 3. Display Options ---
        frm_vis = ttk.Labelframe(right, text="Display Options", padding=4)
        frm_vis.pack(fill="x", pady=(0, 6))

        ttk.Checkbutton(frm_vis, text="Show country borders",
                        variable=self.app.show_borders,
                        command=self._draw_preview).pack(anchor="w")
        ttk.Checkbutton(frm_vis, text="Show satellite footprint",
                        variable=self.app.show_beamwidth,
                        command=self._draw_preview).pack(anchor="w")

        f_bw = ttk.Frame(frm_vis)
        f_bw.pack(fill="x", padx=(15, 0))
        ttk.Checkbutton(f_bw, text="Auto BW",
                        variable=self.app.var_auto_beamwidth,
                        command=self._draw_preview).pack(side="left")
        ttk.Label(f_bw, text=" / ").pack(side="left")
        ttk.Entry(f_bw, textvariable=self.app.var_beamwidth_deg,
                  width=5).pack(side="left")
        ttk.Label(f_bw, text="°").pack(side="left")

        ttk.Checkbutton(frm_vis, text="Show gain map",
                        variable=self.app.var_show_gainmap,
                        command=self._draw_preview).pack(anchor="w", pady=(3, 0))

        f_clim = ttk.Frame(frm_vis)
        f_clim.pack(fill="x", padx=(15, 0))
        ttk.Label(f_clim, text="vMin:").pack(side="left")
        ttk.Entry(f_clim, textvariable=self.app.var_gain_vmin,
                  width=4).pack(side="left", padx=2)
        ttk.Label(f_clim, text="vMax:").pack(side="left")
        ttk.Entry(f_clim, textvariable=self.app.var_gain_vmax,
                  width=4).pack(side="left", padx=2)

        # --- 4. Tools ---
        frm_tools = ttk.Labelframe(right, text="Tools", padding=4)
        frm_tools.pack(fill="x", pady=(0, 6))

        frm_zoom = ttk.Frame(frm_tools)
        frm_zoom.pack(fill="x", pady=2)
        ttk.Button(frm_zoom, text="🔍+", width=5,
                   command=lambda: self._zoom_preview_3d(1/1.15)).pack(side="left", padx=(0, 2))
        ttk.Button(frm_zoom, text="🔍−", width=5,
                   command=lambda: self._zoom_preview_3d(1.15)).pack(side="left", padx=(0, 4))
        ttk.Button(frm_zoom, text="💾 Save Image",
                   command=self._save_image).pack(side="left", fill="x", expand=True)

        ttk.Button(frm_tools, text="🌐 Open in Browser",
                   command=self._open_plotly).pack(fill="x", pady=2)

        # --- 5. Supported Types ---
        frm_catalog = ttk.Labelframe(right, text="✅ Visible Before Run", padding=4)
        frm_catalog.pack(fill="both", expand=False, pady=(0, 6))

        self.txt_catalog = tk.Text(
            frm_catalog, width=32, height=9, wrap="word",
            font=("Consolas", 8), bg="#101726", fg="#d8e6ff",
            insertbackground="#d8e6ff", relief="flat",
            state="disabled")
        self.txt_catalog.pack(fill="both", expand=True)

        # --- 6. Simulation Summary (detachable) ---
        frm_summary = ttk.Labelframe(right, text="📋 Simulation Summary", padding=4)
        frm_summary.pack(fill="both", expand=True, pady=(0, 3))

        self.txt_summary = tk.Text(
            frm_summary, width=32, height=10, wrap="word",
            font=("Consolas", 8), bg="#1a1a2e", fg="#e0e0e0",
            insertbackground="#e0e0e0", relief="flat",
            state="disabled")
        self.txt_summary.pack(fill="both", expand=True)

        frm_sum_btns = ttk.Frame(frm_summary)
        frm_sum_btns.pack(fill="x", pady=(3, 0))
        ttk.Button(frm_sum_btns, text="🔄 Refresh",
                   command=self._update_sim_summary).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(frm_sum_btns, text="📌 Pop Out",
                   command=self._pop_out_summary).pack(side="left")

        # --- 7. YAML Preview (detachable) ---
        frm_yaml = ttk.Labelframe(right, text="📝 YAML Preview", padding=4)
        frm_yaml.pack(fill="both", expand=True, pady=(0, 6))

        self.txt_yaml = tk.Text(
            frm_yaml, width=32, height=10, wrap="none",
            font=("Consolas", 8), bg="#0d1117", fg="#c9d1d9",
            insertbackground="#c9d1d9", relief="flat")
        scroll_y = ttk.Scrollbar(frm_yaml, orient="vertical", command=self.txt_yaml.yview)
        self.txt_yaml.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        self.txt_yaml.pack(fill="both", expand=True)

        frm_yaml_btns = ttk.Frame(frm_yaml)
        frm_yaml_btns.pack(fill="x", pady=(3, 0))
        ttk.Button(frm_yaml_btns, text="🔄 Update YAML",
                   command=self._update_yaml_preview).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(frm_yaml_btns, text="📌 Pop Out",
                   command=self._pop_out_yaml).pack(side="left")

        # Scroll bindings
        w3d = self.canvas3d.get_tk_widget()
        w3d.bind("<MouseWheel>", self._on_scroll_3d)
        w3d.bind("<Button-4>", self._on_scroll_3d)
        w3d.bind("<Button-5>", self._on_scroll_3d)

        self._update_supported_catalog("", "")
        self.refresh()

    def _pop_out_summary(self):
        top = tk.Toplevel(self.frame)
        top.title("Simulation Summary")
        top.geometry("400x500")
        txt = tk.Text(top, wrap="word", font=("Consolas", 10), bg="#1a1a2e", fg="#e0e0e0")
        txt.pack(fill="both", expand=True, padx=5, pady=5)
        txt.insert("1.0", self.txt_summary.get("1.0", "end"))
        txt.configure(state="disabled")
        ttk.Button(top, text="Close", command=top.destroy).pack(pady=5)

    def _update_yaml_preview(self):
        """Update the YAML text preview based on current configuration."""
        data = self._current_yaml()
        text = build_yaml_text(data) if data else "No configuration generated."
        if hasattr(self, "txt_yaml"):
            self.txt_yaml.delete("1.0", "end")
            self.txt_yaml.insert("1.0", text)

    def refresh(self):
        self._update_yaml_preview()
        self._update_sim_summary()
        self._draw_preview()

    def _pop_out_yaml(self):
        self._update_yaml_preview()
        top = tk.Toplevel(self.frame)
        top.title("YAML Configuration")
        top.geometry("600x600")
        txt = tk.Text(top, wrap="none", font=("Consolas", 10), bg="#0d1117", fg="#c9d1d9")
        scroll_y = ttk.Scrollbar(top, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(top, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        txt.pack(fill="both", expand=True, padx=2, pady=2)
        if hasattr(self, "txt_yaml"):
            txt.insert("1.0", self.txt_yaml.get("1.0", "end"))
        txt.configure(state="disabled")
        ttk.Button(top, text="Close", command=top.destroy).pack(pady=5)

    def _update_sim_summary(self):
        """Build a human-readable summary of the current simulation configuration."""
        data = self._current_yaml()

        def v(paths: Tuple[str, ...], attr: Optional[str] = None, default: str = "—") -> str:
            value = _yaml_first(data, paths, None)
            if (value is None or value == "") and attr and hasattr(self.app, attr):
                value = getattr(self.app, attr)
            return _coerce_str(value, default)

        def list_v(paths: Tuple[str, ...]) -> str:
            value = _yaml_first(data, paths, None)
            if isinstance(value, list):
                return ", ".join(str(item) for item in value if str(item).strip()) or "—"
            return _coerce_str(value, "—")

        lines = []
        topo = self._detect_topology_type(data)
        sys_type = self._detect_system_type(data)
        link = _coerce_str(getattr(self.app, "var_imt_link", ""), "—")
        freq = v(("imt.frequency",), "imt_freq")
        bw = v(("imt.bandwidth",), "imt_bw")
        bs_h = v(("imt.bs.height", "imt.base_station.height_m"), "bs_height")
        ue_h = v(("imt.ue.height",), "ue_height")
        ue_k = v(("imt.ue.k",), "ue_k")
        snaps = _coerce_str(getattr(self.app, "var_snaps", ""), "—")
        seed = _coerce_str(getattr(self.app, "var_seed", ""), "—")
        bs_pwr = v(("imt.bs.conducted_power",), "bs_power")
        bs_dt = v(("imt.bs.antenna.array.downtilt",), "bs_downtilt")
        ch = v(("imt.channel_model",), "ch_model")

        lines.append(f"━━━ SCENARIO ━━━")
        lines.append(f"Topology : {topo}")
        lines.append(f"System   : {sys_type}")
        lines.append(f"Link     : {link}")
        lines.append(f"")
        lines.append(f"━━━ IMT ━━━")
        lines.append(f"Freq     : {freq} MHz")
        lines.append(f"BW       : {bw} MHz")
        lines.append(f"Channel  : {ch}")
        lines.append(f"")
        lines.append(f"━━━ BS ━━━")
        lines.append(f"Height   : {bs_h} m")
        lines.append(f"Power    : {bs_pwr} dBm")
        lines.append(f"Downtilt : {bs_dt}°")
        lines.append(f"")
        lines.append(f"━━━ UE ━━━")
        lines.append(f"Height   : {ue_h} m")
        lines.append(f"K (UEs)  : {ue_k}")
        lines.append(f"")
        lines.append(f"━━━ SIMULATION ━━━")
        lines.append(f"Snapshots: {snaps}")
        lines.append(f"Seed     : {seed}")

        # Topology-specific info
        if topo == "INDOOR":
            lines.append(f"")
            lines.append(f"━━━ INDOOR ━━━")
            lines.append(f"Rows     : {_coerce_str(getattr(self.app, 'indoor_n_rows', ''), '—')}")
            lines.append(f"Cols     : {_coerce_str(getattr(self.app, 'indoor_n_cols', ''), '—')}")
            lines.append(f"Floors   : {_coerce_str(getattr(self.app, 'indoor_num_floors', ''), '—')}")
            lines.append(f"Cells    : {_coerce_str(getattr(self.app, 'indoor_num_cells', ''), '—')}")
        elif topo == "NTN":
            lines.append(f"")
            lines.append(f"━━━ NTN ━━━")
            lines.append(f"Sat H    : {v(('imt.topology.ntn.bs_height',), 'ntn_bs_height')} m")
            lines.append(f"Elevation: {v(('imt.topology.ntn.bs_elevation',), 'ntn_bs_elevation')}°")
            lines.append(f"Azimuth  : {v(('imt.topology.ntn.bs_azimuth',), 'ntn_bs_azimuth')}°")
            lines.append(f"Sectors  : {v(('imt.topology.ntn.num_sectors',), 'ntn_num_sectors')}")
        elif topo == "MSS_DC":
            lines.append(f"")
            lines.append(f"━━━ MSS-DC TOPOLOGY ━━━")
            lines.append(f"Beam R   : {v(('imt.topology.mss_dc.beam_radius',), None)} m")
            lines.append(f"Beams    : {v(('imt.topology.mss_dc.num_beams',), None)}")
            lines.append(
                f"Countries: {list_v(('imt.topology.mss_dc.sat_is_active_if.lat_long_inside_country.country_names', 'imt.topology.mss_dc.beam_positioning.service_grid.country_names'))}"
            )
        elif topo == "Macro_countries":
            lines.append(f"")
            lines.append(f"━━━ COUNTRIES ━━━")
            lines.append(f"Num BS   : {v(('imt.topology.macro_countries.num_bs',), 'topo_num_bs')}")
            lines.append(f"Cell R   : {v(('imt.topology.macro_countries.cell_radius',), 'topo_cell_radius')} m")
            countries = v(("imt.topology.macro_countries.countries",), "topo_countries")
            lines.append(f"Countries: {countries}")

        if sys_type == "SINGLE_EARTH_STATION":
            lines.append(f"")
            lines.append(f"━━━ EARTH STATION ━━━")
            loc = v(("single_earth_station.geometry.location.type",), "se_loc_type")
            lines.append(f"Location : {loc}")
            lines.append(f"ES Height: {v(('single_earth_station.geometry.height',), 'se_height')} m")
            lines.append(f"Freq     : {v(('single_earth_station.frequency',), 'se_frequency')} MHz")
        elif sys_type == "SINGLE_SPACE_STATION":
            lines.append(f"")
            lines.append(f"━━━ SPACE STATION ━━━")
            lines.append(f"Altitude : {v(('single_space_station.geometry.altitude',), 'v_alt')} m")
            lines.append(f"Lat/Lon  : {v(('single_space_station.geometry.location.fixed.lat_deg',), 'v_fix_lat')} / {v(('single_space_station.geometry.location.fixed.long_deg',), 'v_fix_lon')}")
            lines.append(f"Freq     : {v(('single_space_station.frequency',), 'v_freq')} MHz")
        elif sys_type == "HAPS":
            lines.append(f"")
            lines.append(f"━━━ HAPS ━━━")
            lines.append(f"Altitude : {v(('haps.altitude',), 'v_alt')} m")
            lines.append(f"Latitude : {v(('haps.lat_deg',), 'v_fix_lat')}°")
            lines.append(f"Freq     : {v(('haps.frequency',), 'v_freq')} MHz")
        elif sys_type == "MSS_SS":
            lines.append(f"")
            lines.append(f"━━━ MSS-SS ━━━")
            lines.append(f"Altitude : {v(('mss_ss.altitude',), 'v_alt')} m")
            lines.append(f"Cell R   : {v(('mss_ss.cell_radius',), 'ntn_cell_radius')} m")
            lines.append(f"Sectors  : {v(('mss_ss.num_sectors',), 'ntn_num_sectors')}")
        elif sys_type == "MSS_D2D":
            lines.append(f"")
            lines.append(f"━━━ MSS-D2D ━━━")
            lines.append(f"Freq     : {v(('mss_d2d.frequency',), 'v_freq')} MHz")
            lines.append(f"BW       : {v(('mss_d2d.bandwidth',), 'v_bw')} MHz")
            lines.append(f"Beams    : {v(('mss_d2d.num_sectors', 'imt.topology.mss_dc.num_beams'), None)}")
            lines.append(f"Channel  : {v(('mss_d2d.channel_model',), 'v_ch_model')}")
        elif sys_type == "MSS_DC":
            lines.append(f"")
            lines.append(f"━━━ MSS-DC ━━━")
            lines.append(f"Freq     : {v(('mss_dc.frequency',), 'v_freq')} MHz")
            lines.append(f"BW       : {v(('mss_dc.bandwidth',), 'v_bw')} MHz")
            lines.append(f"Beams    : {v(('mss_dc.num_sectors', 'imt.topology.mss_dc.num_beams'), None)}")
            lines.append(f"Channel  : {v(('mss_dc.channel_model',), 'v_ch_model')}")

        text = "\n".join(lines)
        self.txt_summary.configure(state="normal")
        self.txt_summary.delete("1.0", "end")
        self.txt_summary.insert("1.0", text)
        self.txt_summary.configure(state="disabled")

    def _current_yaml(self) -> Dict[str, Any]:
        if hasattr(self.app, "current_yaml_dict") and callable(self.app.current_yaml_dict):
            try:
                data = self.app.current_yaml_dict()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _detect_system_type(self, data: Dict[str, Any]) -> str:
        sys_type = _coerce_str(_yaml_first(data, ("general.system",), None), "")
        if not sys_type:
            for key, name in (
                ("mss_dc", "MSS_DC"),
                ("mss_d2d", "MSS_D2D"),
                ("mss_ss", "MSS_SS"),
                ("haps", "HAPS"),
                ("single_space_station", "SINGLE_SPACE_STATION"),
                ("single_earth_station", "SINGLE_EARTH_STATION"),
            ):
                if isinstance(data.get(key), dict):
                    sys_type = name
                    break

        if not sys_type and hasattr(self.app, "var_system"):
            sys_type = _coerce_str(getattr(self.app, "var_system", ""), "")

        t = (sys_type or "").strip().upper().replace("-", "_")
        return t or "SINGLE_EARTH_STATION"

    def _update_supported_catalog(self, topo_type: str, sys_type: str):
        lines = ["Topologies"]
        for name in SUPPORTED_TOPOLOGY_TYPES:
            prefix = ">" if name == topo_type else " "
            lines.append(f"{prefix} {name}")

        lines.append("")
        lines.append("Systems")
        for name in SUPPORTED_SYSTEM_TYPES:
            prefix = ">" if name == sys_type else " "
            lines.append(f"{prefix} {name}")

        text = "\n".join(lines)
        if hasattr(self, "txt_catalog"):
            self.txt_catalog.configure(state="normal")
            self.txt_catalog.delete("1.0", "end")
            self.txt_catalog.insert("1.0", text)
            self.txt_catalog.configure(state="disabled")

    def _detect_topology_type(self, data: Dict[str, Any]) -> str:
        """Detect topology/system type from YAML and/or app vars, with a few aliases.

        IMPORTANT: The SHARC simulator uses the literal string 'Macro_countries'
        (mixed case) in topology_factory.py and station_factory.py, so we must
        preserve that exact spelling rather than upper-casing it.
        """
        topo_type = _coerce_str(
            _yaml_first(
                data,
                (
                    "topology.type",
                    "imt.topology.type",
                    "imt.topology",          # sometimes stored as string
                    "general.system",
                ),
                default=""
            ),
            ""
        )

        if not topo_type and isinstance(_yaml_get(data, "imt.topology.mss_dc", None), dict):
            topo_type = "MSS_DC"

        if not topo_type and "single_earth_station" in data:
            topo_type = "SINGLE_EARTH_STATION"

        if not topo_type and hasattr(self.app, "topo_type"):
            topo_type = _coerce_str(getattr(self.app, "topo_type", ""), "")

        t = (topo_type or "").strip()

        # Normalize Macro_countries variants to SHARC's canonical form
        if t.lower().replace("_", "") in ("macrocountries", "macrocountry"):
            return "Macro_countries"
        if t in ("Macro_countries", "Macro_Countries", "macro_countries"):
            return "Macro_countries"
        if t.lower().replace("-", "_") in ("mss_dc", "mssdc"):
            return "MSS_DC"
        if t.upper() in {"SINGLE_BASE_STATION", "SINGLE_BS"}:
            return "SINGLE_BS"

        # Known SHARC topology/system types that should be uppercased
        t_up = t.upper()
        return t_up if t_up else "MACROCELL"

    def _open_plotly(self):
        """Opens the current plotly figure in the browser."""
        if not HAS_PLOTLY:
            messagebox.showerror("Error", "Plotly is not installed.")
            return

        if self._plotly_last_fig:
            self._plotly_embed.set_figure(
                self._plotly_last_fig, open_external=True)
        else:
            self._plotly_embed.open_in_browser()

    def _on_scroll_3d(self, event):
        base = 1.15
        direction = -1 if getattr(event, "delta",
                                  0) > 0 or getattr(event, "num", 0) == 4 else 1
        self._zoom_preview_3d(1.0/base if direction < 0 else base)

    def _zoom_preview_3d(self, factor: float):
        try:
            self.ax3d.dist = max(1, float(self.ax3d.dist) * float(factor))
            self.canvas3d.draw_idle()
        except Exception:
            pass
    
