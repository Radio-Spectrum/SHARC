from __future__ import annotations
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

import os
import math
import json
import time
import tempfile
import webbrowser
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

import matplotlib
matplotlib.use("TkAgg")

# Optional plotly
HAS_PLOTLY = True
try:
    import plotly.graph_objects as go
except Exception:
    HAS_PLOTLY = False

# Optional HTML embed for plotly
HAS_TKHTMLVIEW = True
try:
    from tkhtmlview import HTMLLabel  # pip install tkhtmlview
except Exception:
    HAS_TKHTMLVIEW = False

# Optional shapefile borders (.shp)
HAS_PYSHP = True
try:
    import shapefile as pyshp  # pyshp
except Exception:
    HAS_PYSHP = False

# Optional geopandas Natural Earth fallback
HAS_GEOPANDAS = True
try:
    import geopandas as gpd
except Exception:
    HAS_GEOPANDAS = False

try:
    from utils import lla_to_ecef, build_yaml_text
except Exception:  # fallback minimal if user runs standalone
    def lla_to_ecef(lat, lon, alt):
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)
        alt = np.asarray(alt, dtype=float)
        a = 6378137.0
        latr = np.radians(lat)
        lonr = np.radians(lon)
        r = a + alt
        x = r*np.cos(latr)*np.cos(lonr)
        y = r*np.cos(latr)*np.sin(lonr)
        z = r*np.sin(latr)
        return x, y, z

    def build_yaml_text(d):
        import yaml
        return yaml.safe_dump(d, sort_keys=False, allow_unicode=True)

try:
    from config import WGS84_A
except Exception:
    WGS84_A = 6378137.0

HAS_SHARC_CORE = True
try:
    from sharc.topology.topology_macrocell import TopologyMacrocell
    from sharc.topology.topology_hotspot import TopologyHotspot
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation
    from sharc.topology.topology_ntn import TopologyNTN
    from sharc.topology.topology_indoor import TopologyIndoor
    # UE-only / countries topologies are optional depending on your SHARC
    try:
        from sharc.topology.topology_ue_only import TopologyUEOnly  # type: ignore
    except Exception:
        TopologyUEOnly = None  # type: ignore

    # Station factory — in your repo it is in project root, and imports sharc.*
    # You provided station_factory.py in the conversation.
    try:
        from sharc.station_factory import StationFactory
    except Exception:
        StationFactory = None  # type: ignore

    from sharc.parameters.parameters_single_space_station import ParametersSingleSpaceStation
    from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation

    # Minimal param objects needed for TopologyHotspot/Indoor in some SHARC variants
    try:
        from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
    except Exception:
        ParametersHotspot = None  # type: ignore
    try:
        from sharc.parameters.imt.parameters_indoor import ParametersIndoor
    except Exception:
        ParametersIndoor = None  # type: ignore

except Exception as e:
    HAS_SHARC_CORE = False
    TopologyMacrocell = TopologyHotspot = TopologySingleBaseStation = TopologyNTN = TopologyIndoor = None  # type: ignore
    ParametersSingleSpaceStation = ParametersSingleEarthStation = None  # type: ignore
    ParametersHotspot = ParametersIndoor = None  # type: ignore
    StationFactory = None  # type: ignore
    print(f"[PreviewTab] SHARC imports not available: {e}")


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if hasattr(x, "get"):
            v = x.get()
        else:
            v = x
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        if hasattr(x, "get"):
            v = x.get()
        else:
            v = x
        if v in ("", None):
            return default
        return int(float(v))
    except Exception:
        return default


def _wrap180(deg: np.ndarray) -> np.ndarray:
    """Wrap degrees to [-180,180]."""
    return (deg + 180.0) % 360.0 - 180.0


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n <= 0:
        return v
    return v / n


def _angle_between(u: np.ndarray, v: np.ndarray) -> float:
    u = _unit(u)
    v = _unit(v)
    c = float(np.clip(np.dot(u, v), -1.0, 1.0))
    return float(np.degrees(np.arccos(c)))


def _guess_antenna_beamwidth_deg(antenna: Any, fallback: float = 5.0) -> float:
    """
    Try to read beamwidth from antenna object.
    Works with many antenna implementations by checking common attribute names.
    """
    if antenna is None:
        return fallback
    for attr in ("beamwidth", "beamwidth_deg", "hp_bw_deg", "half_power_beamwidth_deg",
                 "theta_3db", "theta_3dB", "bw_3db", "bw_3dB"):
        try:
            v = getattr(antenna, attr)
            if callable(v):
                v = v()
            v = float(v)
            if 0.1 <= v <= 180:
                return v
        except Exception:
            pass
    return fallback


def _antenna_gain_db(antenna: Any, off_axis_deg: float, phi_deg: float = 0.0) -> float:
    """
    Compute antenna gain from the antenna object using duck-typing.
    Supports patterns that accept:
      - get_gain(theta, phi)
      - get_gain(theta)
      - gain(theta, phi)
      - gain(theta)
    If nothing works, returns NaN.
    """
    if antenna is None:
        return float("nan")

    # try get_gain(theta, phi)
    for name in ("get_gain", "gain", "G"):
        fn = getattr(antenna, name, None)
        if fn is None or not callable(fn):
            continue
        # 2-arg
        try:
            return float(fn(off_axis_deg, phi_deg))
        except Exception:
            pass
        # 1-arg
        try:
            return float(fn(off_axis_deg))
        except Exception:
            pass

    # some antennas store pattern object
    for inner in ("pattern", "pat", "antenna_pattern"):
        try:
            pat = getattr(antenna, inner)
            if pat is None:
                continue
            return _antenna_gain_db(pat, off_axis_deg, phi_deg)
        except Exception:
            pass

    return float("nan")


class PlotlyEmbed(ttk.Frame):
    """
    Embeds Plotly figure HTML in Tk via tkhtmlview if available.
    If unavailable, provides a note + button to open in browser.
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self._html_label = None
        self._last_html_path = None

        if HAS_TKHTMLVIEW:
            self._html_label = HTMLLabel(self, html="<b>Plotly preview</b>")
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

        # write to temp file so user can open it externally
        fd, path = tempfile.mkstemp(prefix="sharc_preview_", suffix=".html")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self._last_html_path = path

        if HAS_TKHTMLVIEW and self._html_label is not None:
            try:
                self._html_label.set_html(html)
            except Exception:
                # fallback: load from file link
                self._html_label.set_html(
                    f"<b>Plot generated.</b><br>Saved to: {path}")

        if open_external:
            webbrowser.open(path)

    def open_in_browser(self):
        if self._last_html_path:
            webbrowser.open(self._last_html_path)


class PreviewTab:
    """
    Tkinter/ttkbootstrap PreviewTab.

    Requirements met:
    - Matplotlib engine embedded
    - Plotly engine embedded (HTML, optional) + open in browser
    - Show borders (shp or geopandas fallback)
    - Show gain map (global)
    - Beamwidth auto (toggle)
    - YAML preview + Update YAML button
    - Zoom + mouse wheel zoom
    """

    def __init__(self, app: Any, parent_frame: tk.Widget):
        self.app = app
        self.frame = parent_frame

        # Defaults for new features while preserving existing behavior
        if not hasattr(self.app, "show_borders"):
            self.app.show_borders = tk.BooleanVar(value=True)
        if not hasattr(self.app, "plot_engine"):
            self.app.plot_engine = tk.StringVar(
                value="matplotlib")  # "matplotlib" | "plotly"
        if not hasattr(self.app, "show_beamwidth"):
            self.app.show_beamwidth = tk.BooleanVar(value=True)
        if not hasattr(self.app, "var_auto_beamwidth"):
            self.app.var_auto_beamwidth = tk.BooleanVar(value=True)
        if not hasattr(self.app, "var_beamwidth_deg"):
            self.app.var_beamwidth_deg = tk.StringVar(value="2.0")
        if not hasattr(self.app, "open_plotly_external"):
            self.app.open_plotly_external = tk.BooleanVar(value=False)

        self._plotly_embed: Optional[PlotlyEmbed] = None
        self._plotly_last_fig: Optional["go.Figure"] = None

        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self.frame)
        right = ttk.Frame(self.frame)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y")

        # Matplotlib canvas (always created; plotly can switch view)
        self.fig3d = plt.figure(figsize=(6.6, 6.6))
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

        # Plotly embed frame (hidden by default)
        self._plotly_embed = PlotlyEmbed(left)
        self._plotly_embed.pack_forget()

        # ---------------- Controls ----------------
        ttk.Label(right, text="Engine:", font=(
            "Segoe UI", 9, "bold")).pack(anchor="w")
        frm_engine = ttk.Frame(right)
        frm_engine.pack(fill="x", pady=(2, 10))
        ttk.Radiobutton(frm_engine, text="Matplotlib", variable=self.app.plot_engine,
                        value="matplotlib", command=self._draw_preview).pack(anchor="w")
        ttk.Radiobutton(frm_engine, text="Plotly", variable=self.app.plot_engine,
                        value="plotly", command=self._draw_preview).pack(anchor="w")
        ttk.Checkbutton(frm_engine, text="Open Plotly in browser",
                        variable=self.app.open_plotly_external).pack(anchor="w", pady=(4, 0))

        # Gain map controls (keep your previous widgets)
        if not hasattr(self.app, "var_show_gainmap"):
            self.app.var_show_gainmap = tk.BooleanVar(value=False)
        if not hasattr(self.app, "var_gain_vmin"):
            self.app.var_gain_vmin = tk.StringVar(value="-10")
        if not hasattr(self.app, "var_gain_vmax"):
            self.app.var_gain_vmax = tk.StringVar(value="50")

        ttk.Checkbutton(right, text="Show Gain Map (Global Only)",
                        variable=self.app.var_show_gainmap,
                        command=self._draw_preview).pack(fill="x", pady=(0, 8))

        frm_gain = ttk.Frame(right)
        frm_gain.pack(fill="x", pady=(0, 8))
        ttk.Label(frm_gain, text="vmin:").pack(side="left")
        ttk.Entry(frm_gain, textvariable=self.app.var_gain_vmin,
                  width=7).pack(side="left", padx=(4, 8))
        ttk.Label(frm_gain, text="vmax:").pack(side="left")
        ttk.Entry(frm_gain, textvariable=self.app.var_gain_vmax,
                  width=7).pack(side="left", padx=(4, 0))

        ttk.Checkbutton(right, text="Show Borders", variable=self.app.show_borders,
                        command=self._draw_preview).pack(anchor="w", pady=(4, 2))
        frm_beam = ttk.Labelframe(right, text="Beam / Footprint", padding=6)
        frm_beam.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(frm_beam, text="Show footprint", variable=self.app.show_beamwidth,
                        command=self._draw_preview).pack(anchor="w")
        ttk.Checkbutton(frm_beam, text="Auto beamwidth", variable=self.app.var_auto_beamwidth,
                        command=self._draw_preview).pack(anchor="w", pady=(2, 0))
        frm_bw = ttk.Frame(frm_beam)
        frm_bw.pack(fill="x", pady=(2, 0))
        ttk.Label(frm_bw, text="Beamwidth (deg):").pack(side="left")
        ttk.Entry(frm_bw, textvariable=self.app.var_beamwidth_deg,
                  width=7).pack(side="left", padx=(6, 0))

        ttk.Button(right, text="Generate Preview",
                   command=self._draw_preview).pack(fill="x", pady=(4, 4))

        frm_zoom = ttk.Frame(right)
        frm_zoom.pack(fill="x", pady=(0, 4))
        ttk.Button(frm_zoom, text="Zoom +", width=10,
                   command=lambda: self._zoom_preview_3d(1/1.15)).pack(side="left", padx=(0, 2))
        ttk.Button(frm_zoom, text="Zoom -", width=10,
                   command=lambda: self._zoom_preview_3d(1.15)).pack(side="left", padx=(2, 0))

        ttk.Button(right, text="Save Image...",
                   command=self._save_image).pack(fill="x", pady=(4, 4))
        ttk.Button(right, text="Open Plotly in Browser",
                   command=self._open_plotly).pack(fill="x", pady=(0, 4))

        ttk.Button(right, text="Update YAML", command=self._update_yaml_preview).pack(
            fill="x", pady=(4, 4))

        ttk.Label(right, text="YAML Preview:", font=(
            "Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        self.txt_yaml = tk.Text(
            right, width=44, height=28, wrap="none", font=("Consolas", 9))
        self.txt_yaml.pack(fill="both", expand=True)

        w3d = self.canvas3d.get_tk_widget()
        w3d.bind("<MouseWheel>", self._on_scroll_3d)
        w3d.bind("<Button-4>", self._on_scroll_3d)
        w3d.bind("<Button-5>", self._on_scroll_3d)

        self._update_yaml_preview()
        self._draw_preview()

    def _current_yaml(self) -> Dict[str, Any]:
        if hasattr(self.app, "current_yaml_dict") and callable(self.app.current_yaml_dict):
            try:
                data = self.app.current_yaml_dict()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _detect_topology_type(self, data: Dict[str, Any]) -> str:
        topo_type = ""
        try:
            if 'topology' in data and isinstance(data['topology'], dict) and 'type' in data['topology']:
                topo_type = str(data['topology']['type']).strip()
            elif 'imt' in data and isinstance(data['imt'], dict) and 'topology' in data['imt'] and 'type' in data['imt']['topology']:
                topo_type = str(data['imt']['topology']['type']).strip()
            elif 'general' in data and isinstance(data['general'], dict) and 'system' in data['general']:
                topo_type = str(data['general']['system']).strip()
            elif 'single_earth_station' in data:
                topo_type = "SINGLE_EARTH_STATION"
        except Exception:
            pass

        if not topo_type and hasattr(self.app, "topo_type"):
            topo_type = (getattr(self.app.topo_type, "get",
                         lambda: "")() or "").strip()

        if topo_type != "Macro_countries":
            topo_type = topo_type.upper()

        return topo_type or "MACROCELL"

    def _draw_preview(self):
        data = self._current_yaml()
        topo_type = self._detect_topology_type(data)

        engine = getattr(self.app.plot_engine, "get", lambda: "matplotlib")()
        print(f"[PreviewTab] draw: topo='{topo_type}', engine='{engine}'")

        # Show appropriate view
        if engine == "plotly" and HAS_PLOTLY:
            self.canvas3d.get_tk_widget().pack_forget()
            self._plotly_embed.pack(fill="both", expand=True)
            self._draw_preview_plotly(topo_type, data)
        else:
            self._plotly_embed.pack_forget()
            self.canvas3d.get_tk_widget().pack(fill="both", expand=True)
            self._draw_preview_matplotlib(topo_type, data)

    def _draw_preview_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        self.ax3d.cla()

        is_global = topo_type in ["MACRO_COUNTRIES", "MACRO_COUNTRIES".upper(
        ), "Macro_countries", "SINGLE_SPACE_STATION", "MSS_DC", "EESS_SS", "METSAT_SS"]
        # Also treat single space station from general.system or station presence
        if topo_type in ["Macro_countries", "MACRO_COUNTRIES"]:
            is_global = True

        try:
            if is_global:
                self._draw_global_matplotlib(topo_type, data)
            else:
                self._draw_local_matplotlib(topo_type, data)
        except Exception as e:
            traceback.print_exc()
            self.ax3d.text2D(
                0.02, 0.98, f"Preview error: {e}", transform=self.ax3d.transAxes, color="red")
            # draw fallback marker
            self.ax3d.scatter([0], [0], [0], c="red", s=50)

        self.ax3d.set_xlabel("x")
        self.ax3d.set_ylabel("y")
        self.ax3d.set_zlabel("z")
        self.canvas3d.draw_idle()

    # ---- Local scenarios (IMT + SES) ----

    def _draw_local_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        bs_height = _safe_float(getattr(self.app, "bs_height", None), 30.0)

        xs: List[float] = []
        ys: List[float] = []
        azs: List[float] = []

        hex_radius = 0.0
        draw_hex = False
        hex_centers: List[Tuple[float, float]] = []
        marker_color = "blue"
        marker_style = "^"

        # If SES, we ALSO draw IMT grid (from IMT settings) if available
        is_ses = (topo_type == "SINGLE_EARTH_STATION")

        if HAS_SHARC_CORE:
            try:
                if topo_type == "SINGLE_EARTH_STATION":
                    # SES: station at origin (local), az from UI; IMT deployment around it (macro/hotspot) if configured
                    xs = [0.0]
                    ys = [0.0]
                    az_val = _safe_float(
                        getattr(self.app, "sbs_azimuth", None), 0.0)
                    azs = [az_val]
                    marker_style = "D"
                    marker_color = "tab:red"

                    # Draw IMT deployment around SES if IMT tab exists
                    imt_topo = ""
                    try:
                        imt_topo = str(data.get("imt", {}).get(
                            "topology", {}).get("type", "")).upper()
                    except Exception:
                        imt_topo = ""
                    if not imt_topo and hasattr(self.app, "imt_topo_type"):
                        imt_topo = (getattr(self.app.imt_topo_type,
                                    "get", lambda: "")() or "").upper()

                    if imt_topo in ("MACROCELL", "HOTSPOT", "SINGLE_BS"):
                        # Use same logic as those topologies, but centered at origin
                        imt_xs, imt_ys, imt_azs, imt_hex_centers, imt_hex_radius, imt_draw_hex = self._compute_imt_local_geometry(
                            imt_topo)
                        # Merge as "interferers"
                        # We'll draw IMT separately (mastros, hexes, wedges)
                        self._render_imt_local(
                            imt_topo, imt_xs, imt_ys, imt_azs, imt_hex_centers, imt_hex_radius, imt_draw_hex, bs_height)
                elif topo_type == "MACROCELL":
                    d = _safe_float(
                        getattr(self.app, "macro_intersite", None), 1500.0)
                    nc = _safe_int(
                        getattr(self.app, "macro_clusters", None), 1)
                    topo = TopologyMacrocell(
                        intersite_distance=d, num_clusters=nc)
                    topo.calculate_coordinates()
                    xs = list(map(float, topo.x))
                    ys = list(map(float, topo.y))
                    azs = list(map(float, topo.azimuth))
                    hex_radius = d / math.sqrt(3)
                    draw_hex = True
                    hex_centers = list(set(zip(xs, ys)))
                    marker_color = "black"
                elif topo_type == "HOTSPOT":
                    d = _safe_float(
                        getattr(self.app, "hotspot_intersite", None), 1500.0)
                    nc = _safe_int(
                        getattr(self.app, "hotspot_clusters", None), 1)

                    if ParametersHotspot is not None:
                        p_hot = ParametersHotspot()
                        p_hot.num_hotspots_per_cell = _safe_int(
                            getattr(self.app, "hotspot_num_per_cell", None), 3)
                        p_hot.max_dist_hotspot_ue = _safe_float(
                            getattr(self.app, "hotspot_max_dist_ue", None), 50.0)
                        p_hot.min_dist_bs_hotspot = _safe_float(
                            getattr(self.app, "hotspot_min_dist_bs", None), 10.0)
                    else:
                        p_hot = None

                    topo = TopologyHotspot(
                        param=p_hot, intersite_distance=d, num_clusters=nc)
                    topo.calculate_coordinates()
                    xs = list(map(float, topo.x))
                    ys = list(map(float, topo.y))
                    azs = list(map(float, topo.azimuth))

                    if hasattr(topo, "macrocell"):
                        hex_radius = d / math.sqrt(3)
                        mx, my = topo.macrocell.x, topo.macrocell.y
                        hex_centers = list(
                            set(zip(map(float, mx), map(float, my))))
                        draw_hex = True

                    marker_color = "green"
                    marker_style = "o"
                elif topo_type in ("SINGLE_BS", "SINGLE_BASE_STATION"):
                    cr = _safe_float(
                        getattr(self.app, "sbs_cell_radius", None), 100.0)
                    nc = _safe_int(getattr(self.app, "sbs_clusters", None), 1)
                    topo = TopologySingleBaseStation(
                        cell_radius=cr, num_clusters=nc, azimuth=None)
                    topo.calculate_coordinates()
                    xs = list(map(float, topo.x))
                    ys = list(map(float, topo.y))
                    azs = list(map(float, topo.azimuth))
                    marker_color = "green"
                elif topo_type == "NTN":
                    d = 50000.0
                    cr = 20000.0
                    topo = TopologyNTN(d, cr, 500000, 0, 90, 7)
                    topo.calculate_coordinates()
                    xs = list(map(float, topo.x))
                    ys = list(map(float, topo.y))
                    azs = list(map(float, topo.azimuth))
                    hex_radius = cr
                    hex_centers = list(zip(xs, ys))
                    draw_hex = True
                    marker_color = "purple"
                elif topo_type == "INDOOR":
                    if ParametersIndoor is not None:
                        p_in = ParametersIndoor()
                        p_in.n_rows = 3
                        p_in.n_colums = 3
                    else:
                        p_in = None
                    topo = TopologyIndoor(p_in)
                    topo.calculate_coordinates()
                    xs = list(map(float, topo.x))
                    ys = list(map(float, topo.y))
                    azs = [0.0] * len(xs)
                    marker_color = "orange"
                    marker_style = "s"
                elif topo_type == "UE_ONLY" and TopologyUEOnly is not None:
                    topo = TopologyUEOnly()
                    topo.calculate_coordinates()
                    xs = list(map(float, topo.x))
                    ys = list(map(float, topo.y))
                    azs = [0.0] * len(xs)
                    marker_color = "tab:blue"
                    marker_style = "."
            except Exception as e:
                print(f"[PreviewTab] Local topology compute error: {e}")
                traceback.print_exc()
                if len(xs) == 0:
                    xs, ys, azs = [0.0], [0.0], [0.0]

        # RENDER local core
        if len(xs) > 0:
            if draw_hex and len(hex_centers) > 0:
                for cx, cy in hex_centers:
                    self._draw_hexagon_shape(
                        cx, cy, hex_radius, color="gray", lw=1.0, alpha=0.15)
                    self.ax3d.plot([cx, cx], [cy, cy], [
                                   0, bs_height], color="gray", lw=1.0)

            self.ax3d.scatter(xs, ys, [
                              bs_height]*len(xs), c=marker_color, marker=marker_style, s=40, label=topo_type)

            # posts
            if (not draw_hex) or topo_type == "HOTSPOT" or topo_type == "SINGLE_EARTH_STATION":
                for x, y in zip(xs, ys):
                    self._draw_bs_post(
                        self.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

            # wedges (sectors)
            radius_sector = 0.0
            if topo_type in ["MACROCELL", "SINGLE_BS", "SINGLE_BASE_STATION"]:
                radius_sector = hex_radius * \
                    0.9 if hex_radius > 0 else _safe_float(
                        getattr(self.app, "sbs_cell_radius", None), 100.0)
            elif topo_type == "HOTSPOT":
                radius_sector = _safe_float(
                    getattr(self.app, "hotspot_max_dist_ue", None), 50.0)
            elif topo_type == "SINGLE_EARTH_STATION":
                # show a sector for pointing (optional)
                radius_sector = _safe_float(
                    getattr(self.app, "ses_sector_radius", None), 200.0)

            if radius_sector > 0 and topo_type != "SINGLE_EARTH_STATION":
                for x, y, az in zip(xs, ys, azs):
                    self._add_wedge_outline3d(
                        self.ax3d, x, y, radius_sector, az, color=marker_color, z_plane=bs_height)

            # SES pointing vector + optional wedge + optional footprint ring
            if topo_type == "SINGLE_EARTH_STATION":
                az_val = _safe_float(
                    getattr(self.app, "sbs_azimuth", None), 0.0)
                el_val = _safe_float(
                    getattr(self.app, "sbs_elevation", None), 45.0)
                length = _safe_float(
                    getattr(self.app, "ses_vector_len", None), 200.0)

                az_rad = np.radians(az_val)
                el_rad = np.radians(el_val)
                vx = length*np.cos(el_rad)*np.cos(az_rad)
                vy = length*np.cos(el_rad)*np.sin(az_rad)
                vz = length*np.sin(el_rad)
                self.ax3d.quiver(0, 0, bs_height, vx, vy, vz,
                                 color="red", length=1.0, label="Pointing")

                # draw a wedge outline around az direction (IMT-style)
                self._add_wedge_outline3d(
                    self.ax3d, 0, 0, length*0.9, az_val, half_bw_deg=60, color="red", lw=1.5, z_plane=bs_height)

            self._set_equal_3d(self.ax3d, xs, ys,
                               z_top=bs_height*2, margin=0.2)

        # ensure something visible
        if len(xs) == 0:
            self.ax3d.scatter([0], [0], [0], c="red", s=50)
            self.ax3d.text(0, 0, 0, "No geometry", color="red")

    def _compute_imt_local_geometry(self, topo_type: str):
        """Return (xs,ys,azs, hex_centers, hex_radius, draw_hex) for IMT local layouts."""
        bs_height = _safe_float(getattr(self.app, "bs_height", None), 30.0)
        xs = []
        ys = []
        azs = []
        hex_radius = 0.0
        draw_hex = False
        hex_centers = []
        if topo_type == "MACROCELL":
            d = _safe_float(getattr(self.app, "macro_intersite", None), 1500.0)
            nc = _safe_int(getattr(self.app, "macro_clusters", None), 1)
            topo = TopologyMacrocell(intersite_distance=d, num_clusters=nc)
            topo.calculate_coordinates()
            xs = list(map(float, topo.x))
            ys = list(map(float, topo.y))
            azs = list(map(float, topo.azimuth))
            hex_radius = d/math.sqrt(3)
            draw_hex = True
            hex_centers = list(set(zip(xs, ys)))
        elif topo_type == "HOTSPOT":
            d = _safe_float(
                getattr(self.app, "hotspot_intersite", None), 1500.0)
            nc = _safe_int(getattr(self.app, "hotspot_clusters", None), 1)
            if ParametersHotspot is not None:
                p_hot = ParametersHotspot()
                p_hot.num_hotspots_per_cell = _safe_int(
                    getattr(self.app, "hotspot_num_per_cell", None), 3)
                p_hot.max_dist_hotspot_ue = _safe_float(
                    getattr(self.app, "hotspot_max_dist_ue", None), 50.0)
                p_hot.min_dist_bs_hotspot = _safe_float(
                    getattr(self.app, "hotspot_min_dist_bs", None), 10.0)
            else:
                p_hot = None
            topo = TopologyHotspot(
                param=p_hot, intersite_distance=d, num_clusters=nc)
            topo.calculate_coordinates()
            xs = list(map(float, topo.x))
            ys = list(map(float, topo.y))
            azs = list(map(float, topo.azimuth))
            if hasattr(topo, "macrocell"):
                hex_radius = d/math.sqrt(3)
                draw_hex = True
                mx, my = topo.macrocell.x, topo.macrocell.y
                hex_centers = list(set(zip(map(float, mx), map(float, my))))
        elif topo_type == "SINGLE_BS":
            cr = _safe_float(getattr(self.app, "sbs_cell_radius", None), 100.0)
            nc = _safe_int(getattr(self.app, "sbs_clusters", None), 1)
            topo = TopologySingleBaseStation(
                cell_radius=cr, num_clusters=nc, azimuth=None)
            topo.calculate_coordinates()
            xs = list(map(float, topo.x))
            ys = list(map(float, topo.y))
            azs = list(map(float, topo.azimuth))
        return xs, ys, azs, hex_centers, hex_radius, draw_hex

    def _render_imt_local(self, topo_type: str, xs, ys, azs, hex_centers, hex_radius, draw_hex, bs_height):
        """Render IMT deployment around SES (interferers)."""
        # hexes
        if draw_hex and len(hex_centers) > 0:
            for cx, cy in hex_centers:
                self._draw_hexagon_shape(
                    cx, cy, hex_radius, color="gray", lw=1.0, alpha=0.15)
                self.ax3d.plot([cx, cx], [cy, cy], [
                               0, bs_height], color="gray", lw=1.0)

        # markers
        self.ax3d.scatter(xs, ys, [bs_height]*len(xs), c="black",
                          marker="^", s=22, label=f"IMT {topo_type}")

        # mastros
        for x, y in zip(xs, ys):
            self._draw_bs_post(self.ax3d, x, y, bs_height,
                               color="gray", lw=1.5)

        # sectors
        radius_sector = hex_radius * \
            0.9 if hex_radius > 0 else _safe_float(
                getattr(self.app, "sbs_cell_radius", None), 100.0)
        if radius_sector > 0 and len(azs) == len(xs):
            for x, y, az in zip(xs, ys, azs):
                self._add_wedge_outline3d(
                    self.ax3d, x, y, radius_sector, az, color="black", lw=0.8, z_plane=bs_height)

    # ---- Global scenarios ----

    def _draw_global_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        # Positions (lat/lon/alt) from UI
        ss_lat = _safe_float(getattr(self.app, "v_fix_lat", None), 0.0)
        ss_lon = _safe_float(getattr(self.app, "v_fix_lon", None), 0.0)
        ss_alt = _safe_float(
            getattr(self.app, "v_alt", None), 35786e3)  # default GEO

        es_lat = _safe_float(getattr(self.app, "v_es_lat", None), 0.0)
        es_lon = _safe_float(getattr(self.app, "v_es_lon", None), 0.0)
        es_alt = _safe_float(getattr(self.app, "v_es_alt", None), 0.0)

        # Try StationFactory for real position if available, else use lla_to_ecef
        sx = sy = sz = None
        sat_obj = None
        try:
            if HAS_SHARC_CORE and StationFactory is not None and ParametersSingleSpaceStation is not None:
                p_ss = ParametersSingleSpaceStation()
                # geometry fields vary across versions; use guarded sets
                try:
                    p_ss.geometry.altitude = ss_alt
                except Exception:
                    pass
                try:
                    p_ss.geometry.location.fixed.lat_deg = ss_lat
                    p_ss.geometry.location.fixed.long_deg = ss_lon
                except Exception:
                    try:
                        p_ss.geometry.location.lat_deg = ss_lat
                        p_ss.geometry.location.long_deg = ss_lon
                    except Exception:
                        pass
                try:
                    p_ss.is_global_coordinate_system = True
                except Exception:
                    pass

                # Dummy RF fields to avoid crashes in some SHARC versions
                try:
                    p_ss.antenna.pattern = getattr(
                        getattr(self.app, "sat_pattern", None), "get", lambda: "ITU-R S.672")()
                except Exception:
                    pass
                for fld, val in (("bandwidth", 10.0), ("tx_power_density", -50.0)):
                    try:
                        setattr(p_ss, fld, getattr(
                            getattr(self.app, f"sat_{fld}", None), "get", lambda: val)())
                    except Exception:
                        pass

                ss_man = StationFactory.generate_single_space_station(
                    p_ss)  # type: ignore
                sat_obj = ss_man
                sx, sy, sz = float(ss_man.x[0]), float(
                    ss_man.y[0]), float(ss_man.z[0])
        except Exception:
            sx = sy = sz = None

        if sx is None:
            sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)

        ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)

        # Draw Earth sphere
        a = WGS84_A * 0.98
        u = np.linspace(0, 2*np.pi, 50)
        v = np.linspace(0, np.pi, 25)
        X = a*np.outer(np.cos(u), np.sin(v))
        Y = a*np.outer(np.sin(u), np.sin(v))
        Z = a*np.outer(np.ones_like(u), np.cos(v))
        self.ax3d.plot_surface(X, Y, Z, color="#dbe7ff",
                               alpha=0.25, edgecolor="#b0c4de", lw=0.1)

        # Borders
        self._draw_country_borders_matplotlib()

        # Satellite / Earth station / link
        self.ax3d.scatter([sx], [sy], [sz], c="purple", s=70,
                          marker="^", label="Space station")
        self.ax3d.scatter([ex], [ey], [ez], c="blue", s=45,
                          marker="o", label="Earth station")
        self.ax3d.plot([sx, ex], [sy, ey], [sz, ez],
                       color="purple", lw=1.5, alpha=0.8, linestyle="--")

        # Optional beam footprint (beamwidth auto/manual)
        show_bw = getattr(getattr(self.app, "show_beamwidth",
                          None), "get", lambda: True)()
        if show_bw:
            auto_bw = getattr(
                getattr(self.app, "var_auto_beamwidth", None), "get", lambda: True)()
            manual_bw = _safe_float(
                getattr(self.app, "var_beamwidth_deg", None), 5.0)
            bw_deg = manual_bw
            if auto_bw and sat_obj is not None:
                try:
                    antenna = getattr(sat_obj, "antenna", None)
                    if isinstance(antenna, (list, np.ndarray)) and len(antenna) > 0:
                        antenna = antenna[0]
                    bw_deg = _guess_antenna_beamwidth_deg(
                        antenna, fallback=manual_bw)
                except Exception:
                    bw_deg = manual_bw
            self._draw_footprint_circle_ecef(sx, sy, sz, bw_deg)

        R_lim = WGS84_A + 20e6
        self.ax3d.set_xlim([-R_lim, R_lim])
        self.ax3d.set_ylim([-R_lim, R_lim])
        self.ax3d.set_zlim([-R_lim, R_lim])
        self.ax3d.set_box_aspect([1, 1, 1])

    def _draw_country_borders_matplotlib(self):
        if not getattr(self.app.show_borders, "get", lambda: True)():
            return

        # Prefer user-provided shapefile (pyshp)
        shp_path = None
        if hasattr(self.app, "path_shp"):
            try:
                shp_path = self.app.path_shp.get()
            except Exception:
                shp_path = None

        if shp_path and HAS_PYSHP:
            try:
                r = pyshp.Reader(shp_path)
                for sr in r.shapeRecords():
                    pts = sr.shape.points
                    if not pts:
                        continue
                    lons, lats = zip(*pts)
                    x, y, z = lla_to_ecef(np.array(lats), np.array(lons), 0.0)
                    self.ax3d.plot(x, y, z, lw=0.4, color="k",
                                   alpha=0.5, zorder=5)
                return
            except Exception:
                pass

        # Fallback: geopandas Natural Earth
        if HAS_GEOPANDAS:
            try:
                world = gpd.read_file(
                    gpd.datasets.get_path("naturalearth_lowres"))
                for _, row in world.iterrows():
                    geom = row.geometry
                    if geom is None:
                        continue
                    # handle Polygon & MultiPolygon
                    geoms = [geom] if geom.geom_type == "Polygon" else list(
                        getattr(geom, "geoms", []))
                    for g in geoms:
                        coords = np.array(g.exterior.coords)
                        lon = coords[:, 0]
                        lat = coords[:, 1]
                        x, y, z = lla_to_ecef(lat, lon, 0.0)
                        self.ax3d.plot(x, y, z, lw=0.35,
                                       color="k", alpha=0.45, zorder=5)
            except Exception:
                pass

    def _draw_footprint_circle_ecef(self, sx, sy, sz, beamwidth_deg: float):
        """
        Approximate beam footprint on Earth's surface for a nadir-pointing beam.
        We compute half-angle alpha = beamwidth/2 and then ground central angle gamma
        from geometry of a cone intersecting a sphere.

        Assumes satellite points to Earth's center (nadir).
        """
        # Earth radius
        Re = WGS84_A
        rs = float(np.linalg.norm([sx, sy, sz]))
        if rs <= Re:
            return
        alpha = math.radians(max(0.1, min(179.0, beamwidth_deg)) / 2.0)

        # central angle gamma between sub-satellite point and edge of footprint
        # cone half-angle alpha from satellite; sphere radius Re.
        # Derivation: consider triangle OS (center->sat) length rs, OP=Re, angle at S equals alpha.
        # Solve for angle at O (gamma) using law of sines:
        # sin(alpha)/Re = sin(pi - (alpha+beta))/rs ... but simplest numeric:
        # Use ray-sphere intersection in plane; compute edge point direction at cone boundary.
        # We'll compute in satellite-centered frame:
        # boresight points to center: u = -S/|S|
        u = _unit(-np.array([sx, sy, sz], dtype=float))
        # choose an arbitrary perpendicular basis
        tmp = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(tmp, u)) > 0.9:
            tmp = np.array([0.0, 1.0, 0.0])
        e1 = _unit(np.cross(u, tmp))
        e2 = _unit(np.cross(u, e1))

        # generate boundary rays
        phis = np.linspace(0, 2*np.pi, 128)
        pts = []
        S = np.array([sx, sy, sz], dtype=float)
        for phi in phis:
            dir_vec = math.cos(alpha)*u + math.sin(alpha) * \
                (math.cos(phi)*e1 + math.sin(phi)*e2)
            # ray: S + t*dir, find intersection with sphere |P|=Re
            # solve |S + t d|^2 = Re^2
            d = dir_vec
            A = float(np.dot(d, d))
            B = 2.0*float(np.dot(S, d))
            C = float(np.dot(S, S) - Re*Re)
            disc = B*B - 4*A*C
            if disc <= 0:
                continue
            t = (-B - math.sqrt(disc)) / (2*A)  # nearest intersection
            P = S + t*d
            pts.append(P)

        if len(pts) < 3:
            return
        pts = np.array(pts)
        self.ax3d.plot(pts[:, 0], pts[:, 1], pts[:, 2], color="magenta",
                       lw=1.0, alpha=0.7, label="Footprint (approx)")

    def _draw_preview_plotly(self, topo_type: str, data: Dict[str, Any]):
        if not HAS_PLOTLY:
            messagebox.showerror("Plotly not available",
                                 "Install plotly to use this engine.")
            return

        fig = go.Figure()

        is_global = topo_type in ["Macro_countries", "MACRO_COUNTRIES",
                                  "SINGLE_SPACE_STATION", "MSS_DC", "EESS_SS", "METSAT_SS"]
        if topo_type == "SINGLE_EARTH_STATION":
            # for SES, plotly can still be 3D local; we render local in a simple 3D scatter
            is_global = False

        try:
            if is_global:
                self._draw_global_plotly(fig, topo_type, data)
            else:
                self._draw_local_plotly(fig, topo_type, data)
        except Exception as e:
            traceback.print_exc()
            fig.add_annotation(
                text=f"Preview error: {e}", x=0.01, y=0.99, xref="paper", yref="paper", showarrow=False)

        self._plotly_last_fig = fig
        self._plotly_embed.set_figure(fig, open_external=getattr(
            self.app.open_plotly_external, "get", lambda: False)())

    def _draw_global_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        # Earth sphere
        Re = WGS84_A
        u = np.linspace(0, 2*np.pi, 80)
        v = np.linspace(0, np.pi, 40)
        X = Re*np.outer(np.cos(u), np.sin(v))
        Y = Re*np.outer(np.sin(u), np.sin(v))
        Z = Re*np.outer(np.ones_like(u), np.cos(v))

        fig.add_surface(x=X, y=Y, z=Z, opacity=0.25, showscale=False)

        # Borders
        if getattr(self.app.show_borders, "get", lambda: True)():
            self._draw_country_borders_plotly(fig)

        # Positions from UI
        ss_lat = _safe_float(getattr(self.app, "v_fix_lat", None), 0.0)
        ss_lon = _safe_float(getattr(self.app, "v_fix_lon", None), 0.0)
        ss_alt = _safe_float(getattr(self.app, "v_alt", None), 35786e3)

        es_lat = _safe_float(getattr(self.app, "v_es_lat", None), 0.0)
        es_lon = _safe_float(getattr(self.app, "v_es_lon", None), 0.0)
        es_alt = _safe_float(getattr(self.app, "v_es_alt", None), 0.0)

        sx = sy = sz = None
        sat_ant = None

        # Try StationFactory -> real antenna object
        try:
            if HAS_SHARC_CORE and StationFactory is not None and ParametersSingleSpaceStation is not None:
                p_ss = ParametersSingleSpaceStation()
                try:
                    p_ss.geometry.altitude = ss_alt
                    p_ss.geometry.location.fixed.lat_deg = ss_lat
                    p_ss.geometry.location.fixed.long_deg = ss_lon
                except Exception:
                    pass
                try:
                    p_ss.is_global_coordinate_system = True
                except Exception:
                    pass
                # dummy RF
                try:
                    p_ss.antenna.pattern = "ITU-R S.672"
                except Exception:
                    pass
                try:
                    p_ss.bandwidth = 10.0
                    p_ss.tx_power_density = -50.0
                except Exception:
                    pass

                ss_man = StationFactory.generate_single_space_station(
                    p_ss)  # type: ignore
                sx, sy, sz = float(ss_man.x[0]), float(
                    ss_man.y[0]), float(ss_man.z[0])
                try:
                    ant = getattr(ss_man, "antenna", None)
                    if isinstance(ant, (list, np.ndarray)) and len(ant) > 0:
                        sat_ant = ant[0]
                    else:
                        sat_ant = ant
                except Exception:
                    sat_ant = None
        except Exception:
            sx = sy = sz = None

        if sx is None:
            sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)

        ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)

        fig.add_scatter3d(x=[sx], y=[sy], z=[sz], mode="markers",
                          marker=dict(size=5), name="Space station")
        fig.add_scatter3d(x=[ex], y=[ey], z=[ez], mode="markers",
                          marker=dict(size=4), name="Earth station")

        fig.add_scatter3d(x=[sx, ex], y=[sy, ey], z=[sz, ez], mode="lines", line=dict(width=3, dash="dash"),
                          name="Link")

        # Beam footprint + gain map
        use_beam = getattr(self.app.show_beamwidth, "get", lambda: True)()
        show_gain = getattr(self.app.var_show_gainmap, "get", lambda: False)()
        vmin = _safe_float(getattr(self.app, "var_gain_vmin", None), -10.0)
        vmax = _safe_float(getattr(self.app, "var_gain_vmax", None), 50.0)

        if use_beam:
            auto_bw = getattr(
                getattr(self.app, "var_auto_beamwidth", None), "get", lambda: True)()
            manual_bw = _safe_float(
                getattr(self.app, "var_beamwidth_deg", None), 5.0)
            bw_deg = manual_bw
            if auto_bw and sat_ant is not None:
                try:
                    bw_deg = _guess_antenna_beamwidth_deg(
                        sat_ant, fallback=manual_bw)
                except Exception:
                    bw_deg = manual_bw
            fp = self._compute_footprint_boundary(sx, sy, sz, bw_deg, n=256)
            if fp is not None:
                fig.add_scatter3d(x=fp[:, 0], y=fp[:, 1], z=fp[:, 2], mode="lines",
                                  line=dict(width=3), name="Footprint")
        if show_gain and sat_ant is not None:
            # Real gain map computed as a surfacecolor on Earth sphere for directions from satellite to surface points.
            # Compute gain at each sphere mesh vertex using off-axis w.r.t. boresight (nadir).
            surface_gain = self._compute_gain_surfacecolor(
                sx, sy, sz, sat_ant, X, Y, Z, vmin=vmin, vmax=vmax)
            if surface_gain is not None:
                fig.add_surface(x=X, y=Y, z=Z, surfacecolor=surface_gain, colorscale="Turbo",
                                cmin=vmin, cmax=vmax, opacity=0.65, colorbar=dict(title="Gain (dBi)"))

        fig.update_layout(scene=dict(aspectmode="data"))

    def _draw_country_borders_plotly(self, fig: "go.Figure"):
        # Prefer user shp path
        shp_path = None
        if hasattr(self.app, "path_shp"):
            try:
                shp_path = self.app.path_shp.get()
            except Exception:
                shp_path = None

        if shp_path and HAS_PYSHP:
            try:
                r = pyshp.Reader(shp_path)
                for sr in r.shapeRecords():
                    pts = sr.shape.points
                    if not pts:
                        continue
                    lons, lats = zip(*pts)
                    x, y, z = lla_to_ecef(np.array(lats), np.array(lons), 0.0)
                    fig.add_scatter3d(x=x, y=y, z=z, mode="lines", line=dict(width=1, color="black"),
                                      showlegend=False)
                return
            except Exception:
                pass

        if HAS_GEOPANDAS:
            try:
                world = gpd.read_file(
                    gpd.datasets.get_path("naturalearth_lowres"))
                for _, row in world.iterrows():
                    geom = row.geometry
                    if geom is None:
                        continue
                    geoms = [geom] if geom.geom_type == "Polygon" else list(
                        getattr(geom, "geoms", []))
                    for g in geoms:
                        coords = np.array(g.exterior.coords)
                        lon = coords[:, 0]
                        lat = coords[:, 1]
                        x, y, z = lla_to_ecef(lat, lon, 0.0)
                        fig.add_scatter3d(x=x, y=y, z=z, mode="lines", line=dict(width=1, color="black"),
                                          showlegend=False)
            except Exception:
                pass

    def _compute_footprint_boundary(self, sx, sy, sz, beamwidth_deg: float, n: int = 256) -> Optional[np.ndarray]:
        Re = WGS84_A
        S = np.array([sx, sy, sz], dtype=float)
        rs = float(np.linalg.norm(S))
        if rs <= Re:
            return None

        alpha = math.radians(max(0.1, min(179.0, beamwidth_deg)) / 2.0)
        u = _unit(-S)  # nadir boresight
        tmp = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(tmp, u)) > 0.9:
            tmp = np.array([0.0, 1.0, 0.0])
        e1 = _unit(np.cross(u, tmp))
        e2 = _unit(np.cross(u, e1))

        phis = np.linspace(0, 2*np.pi, n)
        pts = []
        for phi in phis:
            d = math.cos(alpha)*u + math.sin(alpha) * \
                (math.cos(phi)*e1 + math.sin(phi)*e2)
            A = float(np.dot(d, d))
            B = 2.0*float(np.dot(S, d))
            C = float(np.dot(S, S) - Re*Re)
            disc = B*B - 4*A*C
            if disc <= 0:
                continue
            t = (-B - math.sqrt(disc)) / (2*A)
            P = S + t*d
            pts.append(P)
        if len(pts) < 3:
            return None
        return np.array(pts)

    def _compute_gain_surfacecolor(self, sx, sy, sz, antenna, X, Y, Z, vmin: float, vmax: float):
        # boresight is nadir
        S = np.array([sx, sy, sz], dtype=float)
        u_bore = _unit(-S)

        # mesh arrays
        gains = np.empty_like(X, dtype=float)
        # Compute off-axis angle for each surface point: angle between boresight and direction from satellite to point
        # To keep performance reasonable, subsample if mesh is huge
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                P = np.array([X[i, j], Y[i, j], Z[i, j]], dtype=float)
                d = _unit(P - S)
                off = _angle_between(u_bore, d)
                g = _antenna_gain_db(antenna, off, phi_deg=0.0)
                gains[i, j] = g

        # Replace NaNs with vmin so the color map stays stable
        gains = np.where(np.isfinite(gains), gains, vmin)
        return np.clip(gains, vmin, vmax)

    def _draw_local_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        # Simple 3D local layout in Plotly (useful for SES or local IMT)
        bs_height = _safe_float(getattr(self.app, "bs_height", None), 30.0)

        # Use same geometry as MPL
        xs, ys, azs, hex_centers, hex_radius, draw_hex = [], [], [], [], 0.0, False
        if topo_type == "SINGLE_EARTH_STATION":
            xs, ys, azs = [0.0], [0.0], [_safe_float(
                getattr(self.app, "sbs_azimuth", None), 0.0)]
        else:
            if topo_type in ("MACROCELL", "HOTSPOT", "SINGLE_BS"):
                xs, ys, azs, hex_centers, hex_radius, draw_hex = self._compute_imt_local_geometry(
                    topo_type)

        # points
        fig.add_scatter3d(x=xs, y=ys, z=[bs_height]*len(xs), mode="markers",
                          marker=dict(size=4), name=topo_type)

        # hexes
        if draw_hex and hex_centers and hex_radius > 0:
            for cx, cy in hex_centers:
                ring = self._hexagon_points(cx, cy, hex_radius)
                fig.add_scatter3d(x=ring[:, 0], y=ring[:, 1], z=np.zeros(len(ring)), mode="lines",
                                  line=dict(width=2), showlegend=False)

        fig.update_layout(scene=dict(aspectmode="data"))

    # ----------------------------
    # YAML preview, save, zoom
    # ----------------------------

    def _update_yaml_preview(self):
        data = self._current_yaml()
        self.txt_yaml.delete("1.0", tk.END)
        self.txt_yaml.insert(tk.END, build_yaml_text(data))

    def _save_image(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.fig3d.savefig(path, dpi=180, bbox_inches="tight")
            messagebox.showinfo("OK", f"Image saved: {path}")

    def _open_plotly(self):
        if self._plotly_last_fig is not None:
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
        except Exception:
            pass
        self.canvas3d.draw_idle()

    def _hexagon_points(self, x: float, y: float, r: float) -> np.ndarray:
        pts = []
        angle_deg = 30.0
        for _ in range(7):
            rad = math.radians(angle_deg)
            pts.append([x + r*math.cos(rad), y + r*math.sin(rad)])
            angle_deg += 60.0
        return np.array(pts, dtype=float)

    def _draw_hexagon_shape(self, x, y, r, color="k", lw=1.0, alpha=1.0):
        points = self._hexagon_points(x, y, r)
        self._add_polyline3d(self.ax3d, points.tolist(),
                             color=color, lw=lw, alpha=alpha)

    def _draw_bs_post(self, ax, x, y, h, color="tab:blue", lw=2.0):
        ax.plot([x, x], [y, y], [0, h], color=color, lw=lw)

    def _add_polyline3d(self, ax, xy_points, z=0.0, color="k", lw=1.0, alpha=1.0):
        segs = [((p1[0], p1[1], z), (p2[0], p2[1], z))
                for p1, p2 in zip(xy_points[:-1], xy_points[1:])]
        ax.add_collection3d(Line3DCollection(
            segs, colors=[color], linewidths=lw, alpha=alpha))

    def _add_wedge_outline3d(self, ax, x, y, r, az_deg, half_bw_deg=60, color="green", lw=1.0, z_plane=0.0):
        """Desenha o contorno do setor (fatia de pizza) no plano z=z_plane."""
        th0, th1 = np.radians(
            az_deg - half_bw_deg), np.radians(az_deg + half_bw_deg)
        ths = np.linspace(th0, th1, 24)
        pts = [(x, y)] + [(x + r*np.cos(t), y + r*np.sin(t))
                          for t in ths] + [(x, y)]
        self._add_polyline3d(ax, pts, z=float(z_plane), color=color, lw=lw)

    def _set_equal_3d(self, ax, xs, ys, z_top, margin=0.15):
        """Enquadra XY e mantém Z legível (evita Z enorme que 'some' com mastros)."""
        xs = np.atleast_1d(xs).astype(float)
        ys = np.atleast_1d(ys).astype(float)
        xmin, xmax = float(np.min(xs)), float(np.max(xs))
        ymin, ymax = float(np.min(ys)), float(np.max(ys))
        if xmin == xmax:
            xmin -= 50
            xmax += 50
        if ymin == ymax:
            ymin -= 50
            ymax += 50
        xspan = (xmax - xmin)
        yspan = (ymax - ymin)
        span_xy = max(xspan, yspan)
        if span_xy <= 0:
            span_xy = 100.0
        span_xy *= (1.0 + float(margin))
        cx, cy = (xmin + xmax)/2.0, (ymin + ymax)/2.0
        ax.set_xlim(cx - span_xy/2.0, cx + span_xy/2.0)
        ax.set_ylim(cy - span_xy/2.0, cy + span_xy/2.0)
        # Z: proporcional ao cenário vertical (mastros / alturas)
        zmax = max(float(z_top)*3.0, float(z_top), 10.0)
        ax.set_zlim(0.0, zmax)
        try:
            ax.set_box_aspect((1.0, 1.0, 0.35))
        except Exception:
            pass
