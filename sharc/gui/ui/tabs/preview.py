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

# Try imports from local project structure
try:
    from utils import lla_to_ecef, build_yaml_text
except Exception:
    # Fallback if running standalone
    def lla_to_ecef(lat, lon, alt):
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)
        alt = np.asarray(alt, dtype=float)
        a = 6378137.0
        latr = np.radians(lat)
        lonr = np.radians(lon)
        r = a + alt
        x = r * np.cos(latr) * np.cos(lonr)
        y = r * np.cos(latr) * np.sin(lonr)
        z = r * np.sin(latr)
        return x, y, z

    def build_yaml_text(d):
        import yaml
        return yaml.safe_dump(d, sort_keys=False, allow_unicode=True)

try:
    from config import WGS84_A
except Exception:
    WGS84_A = 6378137.0

# SHARC Core Imports
HAS_SHARC_CORE = True
try:
    from sharc.topology.topology_macrocell import TopologyMacrocell
    from sharc.topology.topology_hotspot import TopologyHotspot
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation
    from sharc.topology.topology_ntn import TopologyNTN
    from sharc.topology.topology_indoor import TopologyIndoor

    try:
        from sharc.topology.topology_ue_only import TopologyUEOnly
    except Exception:
        TopologyUEOnly = None

    # StationFactory location varies across SHARC layouts
    try:
        from sharc.station_factory import StationFactory  # type: ignore
    except Exception:
        try:
            from station_factory import StationFactory  # type: ignore
        except Exception:
            StationFactory = None

    from sharc.parameters.parameters_single_space_station import ParametersSingleSpaceStation
    from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation

    try:
        from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
    except Exception:
        ParametersHotspot = None
    try:
        from sharc.parameters.imt.parameters_indoor import ParametersIndoor
    except Exception:
        ParametersIndoor = None

except Exception as e:
    HAS_SHARC_CORE = False
    TopologyMacrocell = TopologyHotspot = TopologySingleBaseStation = TopologyNTN = TopologyIndoor = None
    ParametersSingleSpaceStation = ParametersSingleEarthStation = None
    ParametersHotspot = ParametersIndoor = None
    StationFactory = None
    print(f"[PreviewTab] SHARC imports not available: {e}")


# ---------------- Helpers ----------------

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


def _yaml_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Safely get nested value from dict using dotted path (e.g., 'imt.topology.type')."""
    cur: Any = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _yaml_first(data: Dict[str, Any], paths: Tuple[str, ...], default: Any = None) -> Any:
    """Return first non-empty value found in any of the dotted paths."""
    for p in paths:
        v = _yaml_get(data, p, None)
        if v is not None and v != "":
            return v
    return default


def _as_value(x: Any) -> Any:
    """If x is a Tk variable, return x.get(); else return x."""
    try:
        if hasattr(x, "get") and callable(x.get):
            return x.get()
    except Exception:
        pass
    return x


def _coerce_float(x: Any, default: float) -> float:
    return _safe_float(_as_value(x), default)


def _coerce_int(x: Any, default: int) -> int:
    return _safe_int(_as_value(x), default)


def _coerce_str(x: Any, default: str) -> str:
    try:
        v = _as_value(x)
        if v is None:
            return default
        s = str(v).strip()
        return s if s else default
    except Exception:
        return default


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n <= 1e-9:
        return v
    return v / n


def _angle_between(u: np.ndarray, v: np.ndarray) -> float:
    u = _unit(u)
    v = _unit(v)
    c = float(np.clip(np.dot(u, v), -1.0, 1.0))
    return float(np.degrees(np.arccos(c)))


def _guess_antenna_beamwidth_deg(antenna: Any, fallback: float = 5.0) -> float:
    """Attempt to retrieve beamwidth from an antenna object via duck-typing."""
    if antenna is None:
        return fallback

    # Check common attributes
    candidates = ["beamwidth", "beamwidth_deg", "hp_bw_deg", "half_power_beamwidth_deg",
                  "theta_3db", "theta_3dB", "bw_3db", "bw_3dB"]

    for attr in candidates:
        try:
            val = getattr(antenna, attr, None)
            if val is None:
                continue
            if callable(val):
                val = val()
            f_val = float(val)
            if 0.1 <= f_val <= 360.0:
                return f_val
        except Exception:
            pass

    return fallback


def _antenna_gain_db(antenna: Any, off_axis_deg: float, phi_deg: float = 0.0) -> float:
    """
    Compute antenna gain using duck-typing for various SHARC antenna implementations.
    """
    if antenna is None:
        return float("nan")

    if isinstance(antenna, (list, tuple, np.ndarray)) and len(antenna) > 0:
        return _antenna_gain_db(antenna[0], off_axis_deg, phi_deg)

    for method_name in ["get_gain", "gain", "G"]:
        func = getattr(antenna, method_name, None)
        if func and callable(func):
            try:
                return float(func(off_axis_deg, phi_deg))
            except:
                try:
                    return float(func(off_axis_deg))
                except:
                    pass

    for pat_attr in ["pattern", "pat", "antenna_pattern"]:
        sub_pat = getattr(antenna, pat_attr, None)
        if sub_pat:
            return _antenna_gain_db(sub_pat, off_axis_deg, phi_deg)

    return float("nan")


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


class PreviewTab:
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
        right = ttk.Frame(self.frame)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y", padx=5, pady=5)

        self.fig3d = plt.figure(figsize=(6, 6))
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

        self._plotly_embed = PlotlyEmbed(left)
        self._plotly_embed.pack_forget()

        ttk.Label(right, text="Engine:", font=(
            "Segoe UI", 9, "bold")).pack(anchor="w")

        frm_engine = ttk.Frame(right)
        frm_engine.pack(fill="x", pady=(2, 10))
        ttk.Radiobutton(frm_engine, text="Matplotlib", variable=self.app.plot_engine,
                        value="matplotlib", command=self._draw_preview).pack(anchor="w")
        ttk.Radiobutton(frm_engine, text="Plotly", variable=self.app.plot_engine,
                        value="plotly", command=self._draw_preview).pack(anchor="w")
        ttk.Checkbutton(frm_engine, text="Auto-open Browser",
                        variable=self.app.open_plotly_external).pack(anchor="w", padx=15)

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(right, text="Visualization:", font=(
            "Segoe UI", 9, "bold")).pack(anchor="w")

        ttk.Checkbutton(right, text="Show Borders", variable=self.app.show_borders,
                        command=self._draw_preview).pack(anchor="w")

        frm_glob = ttk.Labelframe(right, text="Global / Satellite", padding=5)
        frm_glob.pack(fill="x", pady=5)

        ttk.Checkbutton(frm_glob, text="Show Footprint", variable=self.app.show_beamwidth,
                        command=self._draw_preview).pack(anchor="w")

        f_bw = ttk.Frame(frm_glob)
        f_bw.pack(fill="x")
        ttk.Checkbutton(f_bw, text="Auto BW", variable=self.app.var_auto_beamwidth,
                        command=self._draw_preview).pack(side="left")
        ttk.Label(f_bw, text=" or ").pack(side="left")
        ttk.Entry(f_bw, textvariable=self.app.var_beamwidth_deg,
                  width=5).pack(side="left")
        ttk.Label(f_bw, text="°").pack(side="left")

        ttk.Checkbutton(frm_glob, text="Show Gain Map", variable=self.app.var_show_gainmap,
                        command=self._draw_preview).pack(anchor="w", pady=(5, 0))

        f_clim = ttk.Frame(frm_glob)
        f_clim.pack(fill="x")
        ttk.Label(f_clim, text="vMin:").pack(side="left")
        ttk.Entry(f_clim, textvariable=self.app.var_gain_vmin,
                  width=4).pack(side="left", padx=2)
        ttk.Label(f_clim, text="vMax:").pack(side="left")
        ttk.Entry(f_clim, textvariable=self.app.var_gain_vmax,
                  width=4).pack(side="left", padx=2)

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(right, text="Refresh Preview",
                   command=self._draw_preview).pack(fill="x", pady=2)

        frm_zoom = ttk.Frame(right)
        frm_zoom.pack(fill="x", pady=2)
        ttk.Button(frm_zoom, text="Zoom +", width=8,
                   command=lambda: self._zoom_preview_3d(1/1.15)).pack(side="left", padx=(0, 2))
        ttk.Button(frm_zoom, text="Zoom -", width=8,
                   command=lambda: self._zoom_preview_3d(1.15)).pack(side="left")

        ttk.Button(right, text="Save Image...",
                   command=self._save_image).pack(fill="x", pady=2)
        ttk.Button(right, text="Open Plotly Browser",
                   command=self._open_plotly).pack(fill="x", pady=2)

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(right, text="Update YAML Text",
                   command=self._update_yaml_preview).pack(fill="x")
        self.txt_yaml = tk.Text(
            right, width=40, height=15, wrap="none", font=("Consolas", 8))
        self.txt_yaml.pack(fill="both", expand=True, pady=5)

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
        """Detect topology/system type from YAML and/or app vars, with a few aliases."""
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

        if not topo_type and "single_earth_station" in data:
            topo_type = "SINGLE_EARTH_STATION"

        if not topo_type and hasattr(self.app, "topo_type"):
            topo_type = _coerce_str(getattr(self.app, "topo_type", ""), "")

        t = (topo_type or "").strip()

        # normalize common legacy value
        if t in ("Macro_countries", "Macro_Countries", "macro_countries"):
            return "MACRO_COUNTRIES"

        t_up = t.upper()
        if t_up in ("MACRO_COUNTRY", "MACROCOUNTRIES"):
            return "MACRO_COUNTRIES"

        return t_up if t_up else "MACROCELL"

    def _draw_preview(self):
        data = self._current_yaml()
        topo_type = self._detect_topology_type(data)
        engine = self.app.plot_engine.get()

        print(f"[PreviewTab] Drawing {topo_type} using {engine}")

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

        global_types = ["MACRO_COUNTRIES", "SINGLE_SPACE_STATION",
                        "MSS_DC", "EESS_SS", "METSAT_SS"]
        is_global = topo_type in global_types

        try:
            if is_global:
                self._draw_global_matplotlib(topo_type, data)
            else:
                self._draw_local_matplotlib(topo_type, data)
        except Exception as e:
            traceback.print_exc()
            self.ax3d.text2D(
                0.05, 0.95, f"Error: {e}", transform=self.ax3d.transAxes, color="red")

        self.ax3d.set_xlabel("x")
        self.ax3d.set_ylabel("y")
        self.ax3d.set_zlabel("z")

        # Add legend
        self.ax3d.legend(loc='upper right', fontsize='small')

        self.canvas3d.draw_idle()

    def _draw_local_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        bs_height = _coerce_float(_yaml_first(data, ("imt.base_station.height_m",
                                  "imt.bs.height_m", "imt.bs_height", "bs_height", "general.bs_height"), None), 30.0)
        if hasattr(self.app, "bs_height"):
            bs_height = _safe_float(
                getattr(self.app, "bs_height", None), bs_height)

        xs, ys, azs, hex_centers, hex_radius, draw_hex = self._compute_local_geometry(
            topo_type, data)

        if not xs:
            xs, ys = [0.0], [0.0]

        # Hexagon Grid (Honeycomb)
        if draw_hex and hex_centers:
            # Draw one hex with label for legend, rest without
            first = True
            for cx, cy in hex_centers:
                label = "Cell Grid" if first else None
                self._draw_hexagon_shape_mpl(cx, cy, hex_radius, rotation_deg=30,
                                             color="gray", lw=1.0, alpha=0.15, label=label)
                self.ax3d.plot([cx, cx], [cy, cy], [0, bs_height],
                               color="gray", lw=0.5, alpha=0.5)
                first = False

        marker = "o" if topo_type == "HOTSPOT" else "^"
        color = "tab:blue"
        label_bs = f"{topo_type.replace('_', ' ').title()} BS"

        self.ax3d.scatter(xs, ys, [bs_height]*len(xs), c=color, marker=marker, s=40,
                          depthshade=False, label=label_bs)

        for x, y in zip(xs, ys):
            self.ax3d.plot([x, x], [y, y], [0, bs_height], color=color, lw=1.5)

        radius = hex_radius * 0.85 if hex_radius > 0 else 50.0
        if topo_type == "HOTSPOT":
            radius = 20.0

        if topo_type != "SINGLE_EARTH_STATION":
            first_sector = True
            for x, y, az in zip(xs, ys, azs):
                lbl = "Sector" if first_sector else None
                self._add_wedge_outline3d_mpl(
                    self.ax3d, x, y, radius, az, z_plane=bs_height, color=color, label=lbl)
                first_sector = False

        if topo_type == "SINGLE_EARTH_STATION":
            az = _coerce_float(_yaml_first(data, ("single_base_station.antenna.azimuth_deg",
                               "imt.single_base_station.antenna.azimuth_deg", "sbs_azimuth_deg", "sbs_azimuth"), None), 0.0)
            if hasattr(self.app, "sbs_azimuth"):
                az = _safe_float(getattr(self.app, "sbs_azimuth", None), az)
            el = _safe_float(getattr(self.app, "sbs_elevation", None), 45.0)
            vec_len = 200.0

            rad_az, rad_el = np.radians(az), np.radians(el)
            vx = vec_len * np.cos(rad_el) * np.cos(rad_az)
            vy = vec_len * np.cos(rad_el) * np.sin(rad_az)
            vz = vec_len * np.sin(rad_el)
            self.ax3d.quiver(0, 0, bs_height, vx, vy, vz,
                             color="red", length=1.0, label="Pointing Vector")

            self._add_wedge_outline3d_mpl(
                self.ax3d, 0, 0, vec_len*0.8, az, z_plane=bs_height, color="red", label="Antenna Sector")

        self._set_equal_3d_mpl(self.ax3d, xs, ys, bs_height*2)

    def _draw_global_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        a = WGS84_A
        # More segments for smoother sphere
        u = np.linspace(0, 2 * np.pi, 60)
        v = np.linspace(0, np.pi, 30)
        X = a * np.outer(np.cos(u), np.sin(v))
        Y = a * np.outer(np.sin(u), np.sin(v))
        Z = a * np.outer(np.ones_like(u), np.cos(v))

        self.ax3d.plot_surface(X, Y, Z, color="#e6f2ff",
                               alpha=0.3, edgecolor="#b0c4de", lw=0.1)

        if self.app.show_borders.get():
            self._draw_borders_mpl()

        sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)

        self.ax3d.scatter([sx], [sy], [sz], c="purple", s=80,
                          marker="^", label="Satellite", zorder=10)
        self.ax3d.scatter([ex], [ey], [ez], c="blue", s=50,
                          marker="o", label="Earth Station", zorder=10)
        self.ax3d.plot([sx, ex], [sy, ey], [sz, ez], color="purple",
                       linestyle="--", alpha=0.6, label="Link")

        if self.app.show_beamwidth.get():
            bw = self._determine_beamwidth(sat_obj)
            self._draw_footprint_mpl(sx, sy, sz, bw)

        limit = WGS84_A * 2.5
        self.ax3d.set_xlim(-limit, limit)
        self.ax3d.set_ylim(-limit, limit)
        self.ax3d.set_zlim(-limit, limit)
        # Ensure it looks spherical, not squashed
        self.ax3d.set_box_aspect([1, 1, 1])

    def _draw_preview_plotly(self, topo_type: str, data: Dict[str, Any]):
        if not HAS_PLOTLY:
            return

        fig = go.Figure()

        global_types = ["MACRO_COUNTRIES", "SINGLE_SPACE_STATION",
                        "MSS_DC", "EESS_SS", "METSAT_SS"]
        is_global = topo_type in global_types

        try:
            if is_global:
                self._draw_global_plotly(fig, topo_type, data)
            else:
                self._draw_local_plotly(fig, topo_type, data)
        except Exception as e:
            traceback.print_exc()
            fig.add_annotation(text=f"Error: {e}", showarrow=False)

        # Ensure legend is visible
        fig.update_layout(showlegend=True, legend=dict(x=0, y=1))

        self._plotly_last_fig = fig
        self._plotly_embed.set_figure(
            fig, open_external=self.app.open_plotly_external.get())

    def _draw_local_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        bs_height = _coerce_float(_yaml_first(data, ("imt.base_station.height_m",
                                  "imt.bs.height_m", "imt.bs_height", "bs_height", "general.bs_height"), None), 30.0)
        if hasattr(self.app, "bs_height"):
            bs_height = _safe_float(
                getattr(self.app, "bs_height", None), bs_height)
        xs, ys, azs, hex_centers, hex_radius, draw_hex = self._compute_local_geometry(
            topo_type, data)

        if draw_hex and hex_centers:
            hex_x, hex_y, hex_z = [], [], []
            for cx, cy in hex_centers:
                # 30 deg rotation makes it pointy-topped to match cluster layout
                pts = self._hexagon_points(cx, cy, hex_radius, rotation_deg=30)
                pts = np.vstack([pts, pts[0]])
                hex_x.extend(pts[:, 0])
                hex_x.append(None)
                hex_y.extend(pts[:, 1])
                hex_y.append(None)
                hex_z.extend([0]*len(pts))
                hex_z.append(None)

            fig.add_trace(go.Scatter3d(
                x=hex_x, y=hex_y, z=hex_z,
                mode="lines", line=dict(color="lightgray", width=2),
                name="Grid / Cells"
            ))

        color = "blue"
        if topo_type == "HOTSPOT":
            color = "green"
        elif topo_type == "SINGLE_EARTH_STATION":
            color = "red"

        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=[bs_height]*len(xs),
            mode="markers", marker=dict(size=5, color=color),
            name=f"{topo_type.replace('_', ' ').title()} BS"
        ))

        post_x, post_y, post_z = [], [], []
        for x, y in zip(xs, ys):
            post_x.extend([x, x, None])
            post_y.extend([y, y, None])
            post_z.extend([0, bs_height, None])

        fig.add_trace(go.Scatter3d(
            x=post_x, y=post_y, z=post_z,
            mode="lines", line=dict(color=color, width=3),
            showlegend=False
        ))

        sec_radius = hex_radius * 0.8 if hex_radius > 0 else 50.0
        if topo_type != "SINGLE_EARTH_STATION":
            for x, y, az in zip(xs, ys, azs):
                self._add_wedge_plotly(
                    fig, x, y, sec_radius, az, bs_height, color)

        if topo_type == "SINGLE_EARTH_STATION":
            az = _coerce_float(_yaml_first(data, ("single_base_station.antenna.azimuth_deg",
                               "imt.single_base_station.antenna.azimuth_deg", "sbs_azimuth_deg", "sbs_azimuth"), None), 0.0)
            if hasattr(self.app, "sbs_azimuth"):
                az = _safe_float(getattr(self.app, "sbs_azimuth", None), az)
            el = _safe_float(getattr(self.app, "sbs_elevation", None), 45.0)
            length = 200.0
            vx = length * np.cos(np.radians(el)) * np.cos(np.radians(az))
            vy = length * np.cos(np.radians(el)) * np.sin(np.radians(az))
            vz = length * np.sin(np.radians(el))

            fig.add_trace(go.Scatter3d(
                x=[0, vx], y=[0, vy], z=[bs_height, bs_height+vz],
                mode="lines", line=dict(color="red", width=5), name="Pointing Vector"
            ))

        fig.update_layout(scene=dict(aspectmode="data"))

    def _draw_global_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)

        Re = WGS84_A
        # Higher resolution for better sphere
        N_phi, N_theta = 80, 40
        u = np.linspace(0, 2*np.pi, N_phi)
        v = np.linspace(0, np.pi, N_theta)
        X = Re * np.outer(np.cos(u), np.sin(v))
        Y = Re * np.outer(np.sin(u), np.sin(v))
        Z = Re * np.outer(np.ones_like(u), np.cos(v))

        surface_color = None
        cmin, cmax = None, None

        show_gain = self.app.var_show_gainmap.get()
        if show_gain and sat_obj:
            ant = getattr(sat_obj, "antenna", None)
            if ant:
                vmin = float(self.app.var_gain_vmin.get())
                vmax = float(self.app.var_gain_vmax.get())
                surface_color = self._compute_gain_surface(
                    sx, sy, sz, ant, X, Y, Z, vmin, vmax)
                cmin, cmax = vmin, vmax

        fig.add_trace(go.Surface(
            x=X, y=Y, z=Z,
            surfacecolor=surface_color if surface_color is not None else np.zeros_like(
                Z),
            colorscale="Turbo" if surface_color is not None else [
                [0, "lightblue"], [1, "lightblue"]],
            cmin=cmin, cmax=cmax,
            opacity=0.7 if surface_color is not None else 0.3,
            showscale=bool(surface_color is not None),
            name="Earth Surface"
        ))

        if self.app.show_borders.get():
            self._draw_borders_plotly(fig)

        fig.add_trace(go.Scatter3d(
            x=[sx], y=[sy], z=[sz], mode="markers",
            marker=dict(size=6, color="purple"), name="Satellite"
        ))
        fig.add_trace(go.Scatter3d(
            x=[ex], y=[ey], z=[ez], mode="markers",
            marker=dict(size=5, color="blue"), name="Earth Station"
        ))
        fig.add_trace(go.Scatter3d(
            x=[sx, ex], y=[sy, ey], z=[sz, ez], mode="lines",
            line=dict(color="purple", dash="dash", width=2), name="Link Path"
        ))

        if self.app.show_beamwidth.get():
            bw = self._determine_beamwidth(sat_obj)
            fp_pts = self._compute_footprint_boundary(sx, sy, sz, bw)
            if fp_pts is not None:
                fig.add_trace(go.Scatter3d(
                    x=fp_pts[:, 0], y=fp_pts[:, 1], z=fp_pts[:, 2],
                    mode="lines", line=dict(color="magenta", width=4),
                    name=f"Footprint ({bw:.1f}°)"
                ))

        # IMPORTANT: Force aspectmode='data' so Earth is a sphere, not an ellipsoid
        fig.update_layout(scene=dict(aspectmode="data"))

    def _compute_local_geometry(self, topo_type: str, data: Dict[str, Any]):
        xs, ys, azs = [], [], []
        hex_centers, hex_radius, draw_hex = [], 0.0, False

        if not HAS_SHARC_CORE:
            return ([0], [0], [0], [], 0, False)

        try:
            if topo_type == "SINGLE_EARTH_STATION":
                xs, ys, azs = [0.0], [0.0], [0.0]

            elif topo_type == "MACROCELL":
                d = _coerce_float(_yaml_first(data, ("imt.topology.intersite_distance", "topology.intersite_distance",
                                  "macrocell.intersite_distance", "macro.intersite_distance", "macro_intersite"), None), 1500.0)
                if hasattr(self.app, "macro_intersite"):
                    d = _safe_float(
                        getattr(self.app, "macro_intersite", None), d)
                nc = _coerce_int(_yaml_first(data, ("imt.topology.num_clusters",
                                 "topology.num_clusters", "macrocell.num_clusters", "macro_clusters"), None), 1)
                if hasattr(self.app, "macro_clusters"):
                    nc = _safe_int(
                        getattr(self.app, "macro_clusters", None), nc)
                topo = TopologyMacrocell(intersite_distance=d, num_clusters=nc)
                topo.calculate_coordinates()
                xs, ys, azs = list(topo.x), list(topo.y), list(topo.azimuth)
                # Correct hexagon size for honeycomb packing:
                # If intersite distance is d, hex radius (center to corner) is d / sqrt(3)
                hex_radius = d / math.sqrt(3)
                draw_hex = True
                hex_centers = list(set(zip(xs, ys)))

            elif topo_type == "HOTSPOT":
                d = _coerce_float(_yaml_first(data, ("imt.hotspot.intersite_distance", "hotspot.intersite_distance",
                                  "imt.topology.intersite_distance", "hotspot_intersite"), None), 1500.0)
                if hasattr(self.app, "hotspot_intersite"):
                    d = _safe_float(
                        getattr(self.app, "hotspot_intersite", None), d)
                nc = _coerce_int(_yaml_first(
                    data, ("imt.hotspot.num_clusters", "hotspot.num_clusters", "hotspot_clusters"), None), 1)
                if hasattr(self.app, "hotspot_clusters"):
                    nc = _safe_int(
                        getattr(self.app, "hotspot_clusters", None), nc)
                p_hot = ParametersHotspot() if ParametersHotspot else None
                if p_hot:
                    p_hot.num_hotspots_per_cell = _coerce_int(_yaml_first(
                        data, ("imt.hotspot.num_hotspots_per_cell", "hotspot.num_hotspots_per_cell", "hotspot_num_per_cell"), None), 3)
                    if hasattr(self.app, "hotspot_num_per_cell"):
                        p_hot.num_hotspots_per_cell = _safe_int(
                            getattr(self.app, "hotspot_num_per_cell", None), p_hot.num_hotspots_per_cell)
                topo = TopologyHotspot(
                    param=p_hot, intersite_distance=d, num_clusters=nc)
                topo.calculate_coordinates()
                xs, ys, azs = list(topo.x), list(topo.y), list(topo.azimuth)
                if hasattr(topo, "macrocell"):
                    hex_radius = d / math.sqrt(3)
                    draw_hex = True
                    hex_centers = list(
                        set(zip(topo.macrocell.x, topo.macrocell.y)))

            elif topo_type in ("SINGLE_BS", "SINGLE_BASE_STATION"):
                cr = _safe_float(
                    getattr(self.app, "sbs_cell_radius", None), 100.0)
                topo = TopologySingleBaseStation(
                    cell_radius=cr, num_clusters=1)
                topo.calculate_coordinates()
                xs, ys, azs = list(topo.x), list(topo.y), list(topo.azimuth)

        except Exception as e:
            print(f"Topology calc error: {e}")
            xs, ys, azs = [0], [0], [0]

        return xs, ys, azs, hex_centers, hex_radius, draw_hex

    def _get_global_positions(self, data: Optional[Dict[str, Any]] = None):
        if data is None:
            data = {}
        ss_lat = _coerce_float(_yaml_first(data, ("single_space_station.geometry.location.fixed.lat_deg",
                               "space_station.geometry.location.fixed.lat_deg", "satellite.lat_deg", "general.satellite.lat_deg"), None), 0.0)
        ss_lon = _coerce_float(_yaml_first(data, ("single_space_station.geometry.location.fixed.long_deg",
                               "space_station.geometry.location.fixed.long_deg", "satellite.lon_deg", "general.satellite.lon_deg"), None), 0.0)
        ss_alt = _coerce_float(_yaml_first(data, ("single_space_station.geometry.altitude",
                               "space_station.geometry.altitude", "satellite.altitude_m", "general.satellite.altitude_m"), None), 35786e3)
        es_lat = _coerce_float(_yaml_first(data, ("single_earth_station.geometry.location.fixed.lat_deg",
                               "earth_station.geometry.location.fixed.lat_deg", "earth_station.lat_deg", "general.earth_station.lat_deg"), None), 0.0)
        es_lon = _coerce_float(_yaml_first(data, ("single_earth_station.geometry.location.fixed.long_deg",
                               "earth_station.geometry.location.fixed.long_deg", "earth_station.lon_deg", "general.earth_station.lon_deg"), None), 0.0)
        es_alt = _coerce_float(_yaml_first(data, ("single_earth_station.geometry.altitude", "earth_station.geometry.altitude",
                               "earth_station.altitude_m", "general.earth_station.altitude_m"), None), 0.0)

        # App fallbacks (older GUI vars)
        if hasattr(self.app, "v_fix_lat"):
            ss_lat = _safe_float(getattr(self.app, "v_fix_lat", None), ss_lat)
        if hasattr(self.app, "v_fix_lon"):
            ss_lon = _safe_float(getattr(self.app, "v_fix_lon", None), ss_lon)
        if hasattr(self.app, "v_alt"):
            ss_alt = _safe_float(getattr(self.app, "v_alt", None), ss_alt)
        if hasattr(self.app, "v_es_lat"):
            es_lat = _safe_float(getattr(self.app, "v_es_lat", None), es_lat)
        if hasattr(self.app, "v_es_lon"):
            es_lon = _safe_float(getattr(self.app, "v_es_lon", None), es_lon)
        if hasattr(self.app, "v_es_alt"):
            es_alt = _safe_float(getattr(self.app, "v_es_alt", None), es_alt)

        ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)

        sat_obj = None
        sx, sy, sz = None, None, None

        if HAS_SHARC_CORE and StationFactory and ParametersSingleSpaceStation:
            try:
                p_ss = ParametersSingleSpaceStation()
                try:
                    p_ss.geometry.altitude = ss_alt
                except:
                    pass
                try:
                    p_ss.geometry.location.fixed.lat_deg = ss_lat
                    p_ss.geometry.location.fixed.long_deg = ss_lon
                except:
                    pass

                pat_name = _coerce_str(_yaml_first(data, ("single_space_station.antenna.pattern",
                                       "space_station.antenna.pattern", "satellite.antenna.pattern"), None), "ITU-R S.672")
                if hasattr(self.app, "sat_pattern"):
                    pat_name = _coerce_str(
                        getattr(self.app, "sat_pattern", pat_name), pat_name)
                try:
                    p_ss.antenna.pattern = pat_name
                except:
                    pass

                sat_obj = StationFactory.generate_single_space_station(p_ss)
                sx, sy, sz = float(sat_obj.x[0]), float(
                    sat_obj.y[0]), float(sat_obj.z[0])
            except Exception:
                pass

        if sx is None:
            sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)

        return sx, sy, sz, ex, ey, ez, sat_obj

    def _determine_beamwidth(self, sat_obj):
        if self.app.var_auto_beamwidth.get():
            if sat_obj:
                ant = getattr(sat_obj, "antenna", None)
                if isinstance(ant, list) and ant:
                    ant = ant[0]
                return _guess_antenna_beamwidth_deg(ant, fallback=float(self.app.var_beamwidth_deg.get()))
        return float(self.app.var_beamwidth_deg.get())

    def _compute_footprint_boundary(self, sx, sy, sz, bw_deg, n=128):
        Re = WGS84_A
        S = np.array([sx, sy, sz], dtype=float)
        rs = float(np.linalg.norm(S))
        if rs <= Re:
            return None

        alpha = math.radians(max(0.1, min(179.0, bw_deg)) / 2.0)

        u = -S / rs

        tmp = np.array([0, 0, 1.0])
        if abs(np.dot(tmp, u)) > 0.9:
            tmp = np.array([0, 1.0, 0])
        e1 = _unit(np.cross(u, tmp))
        e2 = _unit(np.cross(u, e1))

        pts = []
        for phi in np.linspace(0, 2*np.pi, n):
            d = math.cos(alpha)*u + math.sin(alpha) * \
                (math.cos(phi)*e1 + math.sin(phi)*e2)

            B = 2.0 * np.dot(S, d)
            C = rs*rs - Re*Re

            disc = B*B - 4*C
            if disc >= 0:
                t = (-B - math.sqrt(disc)) / 2.0
                pts.append(S + t*d)

        if not pts:
            return None
        return np.array(pts)

    def _compute_gain_surface(self, sx, sy, sz, antenna, X, Y, Z, vmin, vmax):
        S = np.array([sx, sy, sz])
        u_bore = _unit(-S)  # Nadir

        orig_shape = X.shape
        Xf, Yf, Zf = X.ravel(), Y.ravel(), Z.ravel()

        P = np.column_stack((Xf, Yf, Zf))

        D = P - S

        d_norms = np.linalg.norm(D, axis=1)
        d_norms[d_norms == 0] = 1.0
        D_unit = D / d_norms[:, np.newaxis]

        dots = np.dot(D_unit, u_bore)
        dots = np.clip(dots, -1.0, 1.0)
        angles_deg = np.degrees(np.arccos(dots))

        gains = np.zeros_like(angles_deg)

        for i, ang in enumerate(angles_deg):
            gains[i] = _antenna_gain_db(antenna, ang)

        gains = np.nan_to_num(gains, nan=vmin)
        gains = np.clip(gains, vmin, vmax)

        return gains.reshape(orig_shape)

    def _draw_hexagon_shape_mpl(self, x, y, r, rotation_deg=0, label=None, **kwargs):
        pts = self._hexagon_points(x, y, r, rotation_deg=rotation_deg)
        pts = np.vstack([pts, pts[0]])
        line = self.ax3d.plot(pts[:, 0], pts[:, 1], [0]*len(pts), **kwargs)
        if label:
            line[0].set_label(label)

    def _add_wedge_outline3d_mpl(self, ax, x, y, r, az_deg, half_bw=30, z_plane=0, color="k", label=None):
        th0 = np.radians(az_deg - half_bw)
        th1 = np.radians(az_deg + half_bw)
        ths = np.linspace(th0, th1, 12)

        pts = [(x, y)] + [(x + r*math.cos(t), y + r*math.sin(t))
                          for t in ths] + [(x, y)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, [z_plane]*len(xs), color=color, lw=1, label=label)

    def _set_equal_3d_mpl(self, ax, xs, ys, z_top):
        xs = np.array(xs)
        ys = np.array(ys)
        span = max(xs.max()-xs.min(), ys.max()-ys.min(), 100)
        cx = (xs.max()+xs.min())/2
        cy = (ys.max()+ys.min())/2
        ax.set_xlim(cx - span/2, cx + span/2)
        ax.set_ylim(cy - span/2, cy + span/2)
        ax.set_zlim(0, max(z_top, span/4))

    def _draw_borders_mpl(self):
        if not (HAS_PYSHP or HAS_GEOPANDAS):
            return

        coords = []
        if HAS_PYSHP and hasattr(self.app, "path_shp"):
            try:
                r = pyshp.Reader(self.app.path_shp.get())
                for sr in r.shapeRecords():
                    if sr.shape.points:
                        lons, lats = zip(*sr.shape.points)
                        coords.append((lats, lons))
            except:
                pass
        elif HAS_GEOPANDAS:
            try:
                gdf = gpd.read_file(
                    gpd.datasets.get_path("naturalearth_lowres"))
                for geom in gdf.geometry:
                    if geom.geom_type == 'Polygon':
                        lons, lats = geom.exterior.coords.xy
                        coords.append((lats, lons))
                    elif geom.geom_type == 'MultiPolygon':
                        for poly in geom.geoms:
                            lons, lats = poly.exterior.coords.xy
                            coords.append((lats, lons))
            except:
                pass

        for lat, lon in coords:
            x, y, z = lla_to_ecef(lat, lon, 0)
            self.ax3d.plot(x, y, z, color="k", lw=0.3, alpha=0.5)

    def _draw_footprint_mpl(self, sx, sy, sz, bw):
        fp = self._compute_footprint_boundary(sx, sy, sz, bw)
        if fp is not None:
            self.ax3d.plot(fp[:, 0], fp[:, 1], fp[:, 2],
                           color="magenta", lw=1.5, label="Footprint")

    def _draw_borders_plotly(self, fig):
        coords = []
        if HAS_PYSHP and hasattr(self.app, "path_shp"):
            try:
                r = pyshp.Reader(self.app.path_shp.get())
                for sr in r.shapeRecords():
                    if sr.shape.points:
                        lons, lats = zip(*sr.shape.points)
                        coords.append((np.array(lats), np.array(lons)))
            except:
                pass
        elif HAS_GEOPANDAS:
            try:
                gdf = gpd.read_file(
                    gpd.datasets.get_path("naturalearth_lowres"))
                for geom in gdf.geometry:
                    if geom.geom_type == 'Polygon':
                        lons, lats = geom.exterior.coords.xy
                        coords.append((np.array(lats), np.array(lons)))
                    elif geom.geom_type == 'MultiPolygon':
                        for poly in geom.geoms:
                            lons, lats = poly.exterior.coords.xy
                            coords.append((np.array(lats), np.array(lons)))
            except:
                pass

        for lat, lon in coords:
            # Offset borders slightly (1.001*R) to avoid z-fighting with sphere surface
            x, y, z = lla_to_ecef(lat, lon, 0.0)
            # Basic scaling to push them out a tiny bit
            norm = np.sqrt(x*x + y*y + z*z)
            scale = (WGS84_A * 1.001) / norm
            fig.add_trace(go.Scatter3d(
                x=x*scale, y=y*scale, z=z*scale,
                mode="lines", line=dict(color="black", width=2), showlegend=False
            ))

    def _add_wedge_plotly(self, fig, x, y, r, az, z, color):
        th0 = np.radians(az - 30)
        th1 = np.radians(az + 30)
        ths = np.linspace(th0, th1, 10)

        px = [x] + [x + r*math.cos(t) for t in ths] + [x]
        py = [y] + [y + r*math.sin(t) for t in ths] + [y]
        pz = [z] * len(px)

        fig.add_trace(go.Scatter3d(
            x=px, y=py, z=pz, mode="lines",
            line=dict(color=color, width=2), showlegend=False
        ))

    def _hexagon_points(self, x, y, r, rotation_deg=0):
        # Generate 6 points
        angles = np.linspace(np.radians(rotation_deg),
                             np.radians(rotation_deg+360), 7)[:-1]
        return np.column_stack([
            x + r * np.cos(angles),
            y + r * np.sin(angles)
        ])

    def _update_yaml_preview(self):
        data = self._current_yaml()
        self.txt_yaml.delete("1.0", tk.END)
        self.txt_yaml.insert(tk.END, build_yaml_text(data))

    def _save_image(self):
        """Save the current Matplotlib preview to an image file."""
        if self.app.plot_engine.get() == "plotly":
            messagebox.showinfo("Save Image",
                                "For Plotly, please use the 'camera' icon in the plot toolbar \n"
                                "or open in browser and save from there.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
        if path:
            try:
                self.fig3d.savefig(path, dpi=200, bbox_inches='tight')
                messagebox.showinfo(
                    "Saved", f"Image saved successfully to:\n{path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image:\n{e}")

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
