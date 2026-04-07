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
        from sharc.topology.topology_countries import TopologyCountries
    except Exception:
        TopologyCountries = None

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

    # Antenna gain calculation imports
    try:
        from sharc.antenna.antenna_s672 import AntennaS672
        from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
    except Exception:
        AntennaS672 = None
        ParametersAntennaS672 = None

except Exception as e:
    HAS_SHARC_CORE = False
    TopologyMacrocell = TopologyHotspot = TopologySingleBaseStation = TopologyNTN = TopologyIndoor = None
    TopologyCountries = None
    ParametersSingleSpaceStation = ParametersSingleEarthStation = None
    ParametersHotspot = ParametersIndoor = None
    StationFactory = None
    AntennaS672 = None
    ParametersAntennaS672 = None
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
    Compute antenna gain using SHARC's native calculate_gain API.

    SHARC antennas implement calculate_gain(**kwargs) where the off-axis
    angle is passed as keyword 'off_axis_angle_vec' as a numpy array.
    """
    if antenna is None:
        return float("nan")

    if isinstance(antenna, (list, tuple, np.ndarray)) and len(antenna) > 0:
        return _antenna_gain_db(antenna[0], off_axis_deg, phi_deg)

    # Try SHARC's standard calculate_gain(off_axis_angle_vec=...)
    calc_fn = getattr(antenna, "calculate_gain", None)
    if calc_fn and callable(calc_fn):
        try:
            result = calc_fn(off_axis_angle_vec=np.array([off_axis_deg]))
            if hasattr(result, '__len__'):
                return float(result[0])
            return float(result)
        except Exception:
            pass

    # Fallback: try duck-typing for non-standard antenna objects
    for method_name in ["get_gain", "gain", "G"]:
        func = getattr(antenna, method_name, None)
        if func and callable(func):
            try:
                return float(func(off_axis_deg, phi_deg))
            except Exception:
                try:
                    return float(func(off_axis_deg))
                except Exception:
                    pass

    for pat_attr in ["pattern", "pat", "antenna_pattern"]:
        sub_pat = getattr(antenna, pat_attr, None)
        if sub_pat:
            return _antenna_gain_db(sub_pat, off_axis_deg, phi_deg)

    return float("nan")


def _antenna_gain_db_batch(antenna: Any, off_axis_deg_array: np.ndarray) -> np.ndarray:
    """
    Compute antenna gain for a batch of off-axis angles using SHARC's native API.
    Returns an array of gains in dB. Much faster than calling _antenna_gain_db per element.
    """
    if antenna is None:
        return np.full_like(off_axis_deg_array, float("nan"))

    if isinstance(antenna, (list, tuple, np.ndarray)) and len(antenna) > 0:
        return _antenna_gain_db_batch(antenna[0], off_axis_deg_array)

    # Try SHARC's standard calculate_gain(off_axis_angle_vec=...)
    calc_fn = getattr(antenna, "calculate_gain", None)
    if calc_fn and callable(calc_fn):
        try:
            result = calc_fn(off_axis_angle_vec=off_axis_deg_array)
            return np.asarray(result, dtype=float)
        except Exception:
            pass

    # Fallback: element-wise
    gains = np.zeros_like(off_axis_deg_array)
    for i, ang in enumerate(off_axis_deg_array):
        gains[i] = _antenna_gain_db(antenna, ang)
    return gains


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


class ScrollableContainer(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")
        
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)
        self.v_scroll.configure(command=self.canvas.yview)
        
        self.container = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.container, anchor="nw")
        
        self.container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        try:
            widget = self.winfo_containing(*self.winfo_pointerxy())
            cur = widget
            while cur:
                if cur == self:
                    if event.delta > 0: self.canvas.yview_scroll(-1, "units")
                    elif event.delta < 0: self.canvas.yview_scroll(1, "units")
                    break
                cur = cur.master
        except: pass

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

        # --- 5. Simulation Summary (detachable) ---
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

        # --- 6. YAML Preview (detachable) ---
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

        self._update_sim_summary()
        self._update_yaml_preview()
        self._draw_preview()

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
        lines = []
        # Topology
        topo = _coerce_str(getattr(self.app, "topo_type", ""), "—")
        sys_type = _coerce_str(getattr(self.app, "var_system", ""), "—")
        link = _coerce_str(getattr(self.app, "var_imt_link", ""), "—")
        freq = _coerce_str(getattr(self.app, "imt_freq", ""), "—")
        bw = _coerce_str(getattr(self.app, "imt_bw", ""), "—")
        bs_h = _coerce_str(getattr(self.app, "bs_height", ""), "—")
        ue_h = _coerce_str(getattr(self.app, "ue_height", ""), "—")
        ue_k = _coerce_str(getattr(self.app, "ue_k", ""), "—")
        snaps = _coerce_str(getattr(self.app, "var_snaps", ""), "—")
        seed = _coerce_str(getattr(self.app, "var_seed", ""), "—")
        bs_pwr = _coerce_str(getattr(self.app, "bs_power", ""), "—")
        bs_dt = _coerce_str(getattr(self.app, "bs_downtilt", ""), "—")
        ch = _coerce_str(getattr(self.app, "ch_model", ""), "—")

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
            lines.append(f"Sat H    : {_coerce_str(getattr(self.app, 'ntn_bs_height', ''), '—')} m")
            lines.append(f"Elevation: {_coerce_str(getattr(self.app, 'ntn_bs_elevation', ''), '—')}°")
            lines.append(f"Azimuth  : {_coerce_str(getattr(self.app, 'ntn_bs_azimuth', ''), '—')}°")
            lines.append(f"Sectors  : {_coerce_str(getattr(self.app, 'ntn_num_sectors', ''), '—')}")
        elif topo == "Macro_countries":
            lines.append(f"")
            lines.append(f"━━━ COUNTRIES ━━━")
            lines.append(f"Num BS   : {_coerce_str(getattr(self.app, 'topo_num_bs', ''), '—')}")
            lines.append(f"Cell R   : {_coerce_str(getattr(self.app, 'topo_cell_radius', ''), '—')} m")
            countries = _coerce_str(getattr(self.app, 'topo_countries', ''), '—')
            lines.append(f"Countries: {countries}")

        # Earth Station info
        if sys_type == "SINGLE_EARTH_STATION":
            lines.append(f"")
            lines.append(f"━━━ EARTH STATION ━━━")
            loc = _coerce_str(getattr(self.app, "se_loc_type", ""), "—")
            lines.append(f"Location : {loc}")
            lines.append(f"ES Height: {_coerce_str(getattr(self.app, 'se_height', ''), '—')} m")
            lines.append(f"Freq     : {_coerce_str(getattr(self.app, 'se_frequency', ''), '—')} MHz")

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

        # Known SHARC topology/system types that should be uppercased
        t_up = t.upper()
        return t_up if t_up else "MACROCELL"

    def _draw_preview(self):
        data = self._current_yaml()
        topo_type = self._detect_topology_type(data)
        engine = self.app.plot_engine.get()

        # Update simulation summary and scenario header
        self._update_sim_summary()
        sys_type = _coerce_str(getattr(self.app, "var_system", ""), "")
        scenario_label = f"🎯 {topo_type}"
        if sys_type:
            scenario_label += f"  |  System: {sys_type}"
        link = _coerce_str(getattr(self.app, "var_imt_link", ""), "")
        if link:
            scenario_label += f"  |  {link}"
        if hasattr(self, "_lbl_scenario"):
            self._lbl_scenario.configure(text=scenario_label)

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

        # --- Dark theme styling ---
        self.fig3d.set_facecolor("#1a1a2e")
        self.ax3d.set_facecolor("#16213e")
        for axis_pane in [self.ax3d.xaxis, self.ax3d.yaxis, self.ax3d.zaxis]:
            axis_pane.set_pane_color((0.08, 0.13, 0.24, 0.9))
            axis_pane.label.set_color("#b0c4de")
            axis_pane._axinfo["tick"]["color"] = "#b0c4de"
            axis_pane._axinfo["grid"]["color"] = "#2a3a5e"
        self.ax3d.tick_params(colors="#8899aa", labelsize=7)

        global_types = ["Macro_countries", "SINGLE_SPACE_STATION",
                        "MSS_DC", "EESS_SS", "METSAT_SS", "SINGLE_EARTH_STATION",
                        "MSS_SS", "HAPS"]
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

        # --- Clean axis labels ---
        self.ax3d.set_xlabel("x", fontsize=8, color="#b0c4de")
        self.ax3d.set_ylabel("y", fontsize=8, color="#b0c4de")
        self.ax3d.set_zlabel("z", fontsize=8, color="#b0c4de")

        # --- Title ---
        sys_type = _coerce_str(getattr(self.app, "var_system", ""), "")
        title = f"{topo_type}"
        if sys_type:
            title += f" — {sys_type}"
        self.ax3d.set_title(title, fontsize=10, color="#e0e0e0", pad=2)

        # --- Legend ---
        leg = self.ax3d.legend(loc='upper right', fontsize=6,
                               facecolor="#1a1a2e", edgecolor="#3a4a6e",
                               labelcolor="#d0d0e0", framealpha=0.8)

        self.fig3d.tight_layout(pad=1.0)
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

        ue_height = _coerce_float(_yaml_first(data, ("imt.ue.height", "ue_height"), None), 1.5)
        if hasattr(self.app, "ue_height"):
            ue_height = _safe_float(getattr(self.app, "ue_height", None), ue_height)

        # ============================================================
        # INDOOR topology: draw building outlines and floors
        # ============================================================
        if topo_type == "INDOOR" and self._indoor_topo is not None:
            topo = self._indoor_topo
            b_w, b_d, b_h = topo.b_w, topo.b_d, topo.b_h
            num_cells = topo.num_cells
            cell_radius = topo.cell_radius
            num_floors = topo.num_floors
            n_total_bs = len(topo.x)
            bs_per_floor = max(1, n_total_bs // max(1, num_floors))

            drawn_first = False
            for b_idx in range(bs_per_floor // max(1, num_cells)):
                floor_i = b_idx * num_cells
                if floor_i >= len(topo.x):
                    break
                x_b = topo.x[floor_i] - cell_radius
                y_b = topo.y[floor_i] - b_d / 2
                for f in range(num_floors):
                    z0, z1 = f * b_h, (f + 1) * b_h
                    cx = [x_b, x_b + b_w, x_b + b_w, x_b, x_b]
                    cy = [y_b, y_b, y_b + b_d, y_b + b_d, y_b]
                    lbl = "Building" if not drawn_first else None
                    self.ax3d.plot(cx, cy, [z0]*5, color="#d4a574", lw=0.8, alpha=0.7, label=lbl)
                    self.ax3d.plot(cx, cy, [z1]*5, color="#d4a574", lw=0.8, alpha=0.7)
                    for vx, vy in [(x_b, y_b), (x_b+b_w, y_b), (x_b+b_w, y_b+b_d), (x_b, y_b+b_d)]:
                        self.ax3d.plot([vx, vx], [vy, vy], [z0, z1], color="#d4a574", lw=0.5, alpha=0.5)
                    drawn_first = True

            heights = list(topo.height) if hasattr(topo, "height") and len(topo.height) > 0 else [bs_height]*len(xs)
            self.ax3d.scatter(xs, ys, heights, c="#4fc3f7", marker="s", s=25,
                              depthshade=False, label="Indoor BS", zorder=5)
            n_ue = min(len(xs) * 3, 60)
            if n_ue > 0:
                ue_xs = [xs[i % len(xs)] + np.random.uniform(-cell_radius, cell_radius) for i in range(n_ue)]
                ue_ys = [ys[i % len(ys)] + np.random.uniform(-b_d/2, b_d/2) for i in range(n_ue)]
                ue_zs = [heights[i % len(heights)] - np.random.uniform(0, b_h*0.8) for i in range(n_ue)]
                self.ax3d.scatter(ue_xs, ue_ys, ue_zs, c="#ff6b6b", marker=".", s=12,
                                  alpha=0.7, label="UE (sample)", zorder=4)
            if xs:
                span = max(max(xs)-min(xs), max(ys)-min(ys), 50) * 1.3
                cx_m, cy_m = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2
                self.ax3d.set_xlim(cx_m - span/2, cx_m + span/2)
                self.ax3d.set_ylim(cy_m - span/2, cy_m + span/2)
                self.ax3d.set_zlim(0, max(heights)*1.5 if heights else b_h*num_floors*1.5)
            return

        # ============================================================
        # NTN topology: draw ground hexagons + satellite
        # ============================================================
        if topo_type == "NTN" and self._ntn_topo is not None:
            topo = self._ntn_topo
            sc = 1000.0
            cr_km = topo.cell_radius / sc
            first_hex = True
            for x, y in zip(topo.x / sc, topo.y / sc):
                lbl = "Sector Cells" if first_hex else None
                angs = np.linspace(0, 2*np.pi, 7)
                self.ax3d.plot(x + cr_km*np.cos(angs), y + cr_km*np.sin(angs),
                               np.zeros(7), color="#7986cb", lw=1, label=lbl)
                first_hex = False
            self.ax3d.scatter(topo.x/sc, topo.y/sc, np.zeros(len(topo.x)),
                              c="#e0e0e0", marker="v", s=50, depthshade=False, label="Anchor Points", zorder=5)
            sx, sy, sz = topo.space_station_x/sc, topo.space_station_y/sc, topo.space_station_z/sc
            self.ax3d.scatter([sx], [sy], [sz], c="#ff5252", marker="^", s=100, depthshade=False,
                              label=f"Satellite (el={np.degrees(topo.bs_elevation):.0f}°)", zorder=10)
            self.ax3d.plot([sx, sx], [sy, sy], [0, sz], color="#4fc3f7", lw=1.5,
                           label=f"Height = {sz:.0f} km")
            self.ax3d.plot([0, sx], [0, sy], [0, sz], color="#66bb6a", linestyle="--", lw=1.5,
                           label=f"Slant = {topo.bs_radius/sc:.0f} km")
            n_ue = min(len(topo.x)*5, 80)
            if n_ue > 0:
                ue_x = [topo.x[i%len(topo.x)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                ue_y = [topo.y[i%len(topo.y)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                self.ax3d.scatter(ue_x, ue_y, [0]*n_ue, c="#ff6b6b", marker=".", s=10,
                                  alpha=0.6, label="UE (sample)", zorder=3)
            self.ax3d.set_xlabel("x [km]")
            self.ax3d.set_ylabel("y [km]")
            self.ax3d.set_zlabel("z [km]")
            return


        # Hexagon Grid (Honeycomb)
        if draw_hex and hex_centers:
            # Draw one hex with label for legend, rest without
            first = True
            for cx, cy in hex_centers:
                label = "Cell Grid" if first else None
                self._draw_hexagon_shape_mpl(cx, cy, hex_radius, rotation_deg=30,
                                             color="#4a5a8a", lw=1.0, alpha=0.3, label=label)
                self.ax3d.plot([cx, cx], [cy, cy], [0, bs_height],
                               color="#4a5a8a", lw=0.5, alpha=0.5)
                first = False

        marker = "o" if topo_type == "HOTSPOT" else "^"
        color = "#4fc3f7"
        label_bs = f"{topo_type.replace('_', ' ').title()} BS"

        self.ax3d.scatter(xs, ys, [bs_height]*len(xs), c=color, marker=marker, s=40,
                          depthshade=False, label=label_bs)

        for x, y in zip(xs, ys):
            self.ax3d.plot([x, x], [y, y], [0, bs_height], color=color, lw=1.5)

        radius = hex_radius * 0.85 if hex_radius > 0 else 50.0
        if topo_type == "HOTSPOT":
            radius = 20.0

        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            first_sector = True
            for x, y, az in zip(xs, ys, azs):
                lbl = "Sector" if first_sector else None
                self._add_wedge_outline3d_mpl(
                    self.ax3d, x, y, radius, az, z_plane=bs_height, color=color, label=lbl)
                first_sector = False

        # ============================================================
        # BS Antenna direction arrows (azimuth + downtilt)
        # ============================================================
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            downtilt = 6.0
            if hasattr(self.app, "bs_downtilt"):
                downtilt = _safe_float(getattr(self.app, "bs_downtilt", None), 6.0)
            arrow_len = radius * 0.5 if radius > 0 else 30.0
            first_arrow = True
            for x, y, az in zip(xs, ys, azs):
                az_rad = np.radians(az)
                dt_rad = np.radians(downtilt)
                avx = arrow_len * np.cos(-dt_rad) * np.cos(az_rad)
                avy = arrow_len * np.cos(-dt_rad) * np.sin(az_rad)
                avz = -arrow_len * np.sin(dt_rad)
                lbl_a = f"Antenna (dt={downtilt:.0f}°)" if first_arrow else None
                self.ax3d.quiver(x, y, bs_height, avx, avy, avz,
                                 color="#ffab40", arrow_length_ratio=0.15,
                                 linewidth=1.2, label=lbl_a)
                first_arrow = False

        # ============================================================
        # UE positions (sample generation around BS cells)
        # ============================================================
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            ue_k = 3
            if hasattr(self.app, "ue_k"):
                ue_k = _safe_int(getattr(self.app, "ue_k", None), 3)
            n_ue_per_bs = max(ue_k, 1)
            ue_radius = hex_radius * 0.9 if hex_radius > 0 else radius * 0.9
            if topo_type == "HOTSPOT":
                hotspot_max_dist = 50.0
                if hasattr(self.app, "hotspot_max_dist_ue"):
                    hotspot_max_dist = _safe_float(getattr(self.app, "hotspot_max_dist_ue", None), 50.0)
                ue_radius = hotspot_max_dist

            ue_xs, ue_ys = [], []
            unique_bs = list(set(zip(xs, ys)))
            n_ue_total = min(len(unique_bs) * n_ue_per_bs, 120)
            for i in range(n_ue_total):
                bi = i % len(unique_bs)
                bx, by = unique_bs[bi]
                ang = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(0, ue_radius)
                ue_xs.append(bx + r * np.cos(ang))
                ue_ys.append(by + r * np.sin(ang))
            if ue_xs:
                self.ax3d.scatter(ue_xs, ue_ys, [ue_height]*len(ue_xs),
                                  c="#ff6b6b", marker=".", s=15, alpha=0.7,
                                  depthshade=False, label=f"UE (K={ue_k})", zorder=4)

        # ============================================================
        # MSS_D2D: draw two devices with link
        # ============================================================
        if topo_type == "MSS_D2D":
            self.ax3d.scatter(xs[:1], ys[:1], [ue_height], c="#66bb6a", marker="D",
                              s=60, depthshade=False, label="Device 1", zorder=5)
            if len(xs) > 1:
                self.ax3d.scatter(xs[1:2], ys[1:2], [ue_height], c="#ab47bc", marker="D",
                                  s=60, depthshade=False, label="Device 2", zorder=5)
                self.ax3d.plot([xs[0], xs[1]], [ys[0], ys[1]], [ue_height, ue_height],
                               color="#ffab40", linestyle="--", lw=2, label="D2D Link")

        if self.app.var_system.get() == "SINGLE_EARTH_STATION":
            def set_equal_3d(ax):
                xlim = ax.get_xlim3d()
                ylim = ax.get_ylim3d()
                zlim = ax.get_zlim3d()

                xmid = 0.5 * (xlim[0] + xlim[1])
                ymid = 0.5 * (ylim[0] + ylim[1])
                zmid = 0.5 * (zlim[0] + zlim[1])

                radius = 0.5 * max(
                    xlim[1] - xlim[0],
                    ylim[1] - ylim[0],
                    zlim[1] - zlim[0]
                )

                ax.set_xlim3d([xmid - radius, xmid + radius])
                ax.set_ylim3d([ymid - radius, ymid + radius])
                ax.set_zlim3d([zmid - radius, zmid + radius])   
           
            mode = getattr(self.app, "se_loc_type", None)
            mode = mode.get() if hasattr(mode, "get") else "FIXED"

            # ---------------- FIXED ----------------
            if mode == "FIXED":
                x0 = _safe_float(getattr(self.app, "se_loc_fixed_x", 0.0))
                y0 = _safe_float(getattr(self.app, "se_loc_fixed_y", 0.0))

                self.ax3d.scatter(
                    [x0], [y0], [bs_height],
                    c="red", s=40,
                    depthshade=False,
                    label="Single Earth Station"
                )

            # ---------------- UNIFORM ----------------
            elif mode == "UNIFORM_DIST":

                rmin = _safe_float(self.app.se_loc_ud_min_dist_to_center)
                rmax = _safe_float(self.app.se_loc_ud_max_dist_to_center)

                # posição exemplo
                ang = np.random.uniform(0, 2*np.pi)
                r = np.random.uniform(rmin, rmax)

                x0 = r*np.cos(ang)
                y0 = r*np.sin(ang)

                # ponto
                self.ax3d.scatter(
                    [x0], [y0], [bs_height],
                    c="red", s=40,
                    depthshade=False,
                    label="Single Earth Station"
                )

                # anel
                th = np.linspace(0, 2*np.pi, 120)

                self.ax3d.plot(
                    rmin*np.cos(th),
                    rmin*np.sin(th),
                    [bs_height]*len(th),
                    color="red",
                    linestyle="dotted",
                    label="min radius"
                )

                self.ax3d.plot(
                    rmax*np.cos(th),
                    rmax*np.sin(th),
                    [bs_height]*len(th),
                    color="red",
                    linestyle="dotted",
                    label="max radius"
                )

            # ---------------- POINTING VECTOR ----------------
            se_az_type = getattr(self.app, "se_az_type", None)
            se_el_type = getattr(self.app, "se_el_type", None)
            az_type_val = se_az_type.get() if hasattr(se_az_type, "get") else "FIXED"
            el_type_val = se_el_type.get() if hasattr(se_el_type, "get") else "FIXED"

            if az_type_val == "UNIFORM_DIST" or el_type_val == "UNIFORM_DIST":
                # --------- AZ VALS ----------
                if az_type_val == "UNIFORM_DIST":
                    az_min = _safe_float(self.app.se_az_ud_min)
                    az_max = _safe_float(self.app.se_az_ud_max)
                else:
                    az0 = _safe_float(self.app.se_az_fixed)
                    az_min, az_max = az0-1, az0+1   # pequena largura para visual

                # --------- EL VALS ----------
                if el_type_val == "UNIFORM_DIST":
                    el_min = _safe_float(self.app.se_el_ud_min)
                    el_max = _safe_float(self.app.se_el_ud_max)
                else:
                    el0 = _safe_float(self.app.se_el_fixed)
                    el_min, el_max = el0-1, el0+1

                # --------- GRID ----------
                az_vals = np.linspace(az_min, az_max, 30)
                el_vals = np.linspace(el_min, el_max, 30)
                AZ, EL = np.meshgrid(az_vals, el_vals)

                # --------- RADIUS ----------
                R = max(np.sqrt(x0**2 + y0**2)/4, 100)

                # --------- SPHERICAL PATCH ----------
                X = x0 + R*np.cos(np.radians(EL))*np.cos(np.radians(AZ))
                Y = y0 + R*np.cos(np.radians(EL))*np.sin(np.radians(AZ))
                Z = bs_height + R*np.sin(np.radians(EL))

                surf = self.ax3d.plot_surface(
                    X, Y, Z,
                    color="blue",
                    alpha=0.35,
                    linewidth=0,
                    antialiased=True
                )
                # --------- CENTRO ANGULAR ----------
                az_c = 0.5*(az_min + az_max)
                el_c = 0.5*(el_min + el_max)

                # --------- VETOR DIREÇÃO ----------
                vx = R*np.cos(np.radians(el_c))*np.cos(np.radians(az_c))
                vy = R*np.cos(np.radians(el_c))*np.sin(np.radians(az_c))
                vz = R*np.sin(np.radians(el_c))

                # --------- SETA ----------
                self.ax3d.quiver(
                    x0, y0, bs_height,
                    vx, vy, vz,
                    color="red",
                    arrow_length_ratio=0.2,
                    linewidth=2,
                    label="Pointing center"
                )
                # --------- LEGEND ----------
                from matplotlib.patches import Patch
                self.ax3d.legend(handles=[
                    Patch(facecolor="blue", alpha=0.35, label="Pointing angular range")
                ])
            else:
                length = np.sqrt(x0**2 + y0**2)/3
                target = np.array([0, 0, 0])
                origin = np.array([x0, y0, bs_height])
                v = target - origin
                v = v/np.linalg.norm(v)
                vx, vy, vz = v*length
                el = _safe_float(getattr(self.app, "se_el_fixed", 0.0))
                az = _safe_float(getattr(self.app, "se_az_fixed", 0.0))
                vx2 = length * np.cos(np.radians(el)) * np.cos(np.radians(az))
                vy2 = length * np.cos(np.radians(el)) * np.sin(np.radians(az))
                vz2 = length * np.sin(np.radians(el))
                if az_type_val == "FIXED" and el_type_val == "FIXED":
                    vx = vx2
                    vy = vy2
                    vz = vz2
                if az_type_val == "FIXED" and el_type_val == "POINTING_AT_IMT_CENTER":
                    vx = vx2
                    vy = vy2
                if el_type_val == "FIXED" and az_type_val == "POINTING_AT_IMT_CENTER":
                    vz = vz2

                self.ax3d.quiver(x0, y0, bs_height, vx, vy, vz, color="red")
            set_equal_3d(self.ax3d)

    def _draw_global_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        a = WGS84_A
        # More segments for smoother sphere
        u = np.linspace(0, 2 * np.pi, 60)
        v = np.linspace(0, np.pi, 30)
        X = a * np.outer(np.cos(u), np.sin(v))
        Y = a * np.outer(np.sin(u), np.sin(v))
        Z = a * np.outer(np.ones_like(u), np.cos(v))

        self.ax3d.plot_surface(X, Y, Z, color="#1e3a5f",
                               alpha=0.85, edgecolor="#2a4a7f", lw=0.3)

        if self.app.show_borders.get():
            self._draw_borders_mpl()

        # ============================================================
        # Macro_countries: show BS positions distributed across countries
        # ============================================================
        if topo_type == "Macro_countries":
            # Get BS positions with cache invalidation
            countries_str = _coerce_str(getattr(self.app, "topo_countries", ""), "Brazil")
            num_bs_val = _safe_int(getattr(self.app, "topo_num_bs", None), 50)
            cache_key = f"{countries_str}_{num_bs_val}"
            
            bs_lats = getattr(self.app, "_mc_bs_lats", None)
            bs_lons = getattr(self.app, "_mc_bs_lons", None)
            last_key = getattr(self.app, "_mc_cache_key", None)

            # If no cached positions or UI params changed, generate using real TopologyCountries or fallback
            if bs_lats is None or bs_lons is None or last_key != cache_key:
                try:
                    if TopologyCountries is None or ParametersCountries is None:
                        raise ImportError("TopologyCountries/ParametersCountries not available")
                    
                    param_c = ParametersCountries()
                    # Parse country block from app
                    names = [c.strip() for c in countries_str.split(",") if c.strip()]
                    param_c.country_names = names if names else ["Brazil"]
                    param_c.num_bs_total = _safe_int(getattr(self.app, "topo_num_bs", None), 50)
                    
                    # Auto-resolve paths
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    shp_path = os.path.join(base_dir, "topology", "map", "ne_110m_admin_0_countries.shp")
                    ras_path = os.path.join(base_dir, "topology", "map", "SEDAC_map2.tiff")
                    act_path = os.path.join(base_dir, "topology", "map", "sedac_pop.act")
                    if os.path.exists(shp_path): param_c.shapefile_path = shp_path
                    if os.path.exists(ras_path): param_c.population_raster = ras_path
                    if os.path.exists(act_path): param_c.act_colormap_path = act_path
                    
                    topo = TopologyCountries(param_c, None)
                    topo.calculate_coordinates()
                    bs_lats, bs_lons = topo.lats, topo.lons
                    
                    self.app._mc_bs_lats = bs_lats
                    self.app._mc_bs_lons = bs_lons
                    self.app._mc_cache_key = cache_key
                except Exception as e:
                    print(f"[PreviewTab] TopologyCountries failed: {e}")
                    # Fallback to dummy points
                    n_bs = _safe_int(getattr(self.app, "topo_num_bs", None), 50)
                    center_lat = _safe_float(getattr(self.app, "topo_center_lat", None), -15.0)
                    center_lon = _safe_float(getattr(self.app, "topo_center_lon", None), -47.0)
                    np.random.seed(42)
                    bs_lats = center_lat + np.random.uniform(-15, 15, n_bs)
                    bs_lons = center_lon + np.random.uniform(-20, 20, n_bs)

            # Convert lat/lon to ECEF for 3D globe plot
            bs_x, bs_y, bs_z = lla_to_ecef(bs_lats, bs_lons, 0)
            # Offset outward slightly so dots sit on top of the sphere
            offset = 1.005
            self.ax3d.scatter(
                np.asarray(bs_x) * offset,
                np.asarray(bs_y) * offset,
                np.asarray(bs_z) * offset,
                c="#4fc3f7", marker="^", s=12, alpha=0.9,
                depthshade=False, label=f"BS ({len(bs_lats)})", zorder=10
            )

            # Removed early return here so spatial/satellite link elements and gain map render 
            # as part of the standard global scenarios pipeline below.

        # ============================================================
        # Standard satellite/earth-station global scenarios
        # ============================================================
        sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)

        self.ax3d.scatter([sx], [sy], [sz], c="#ff5252", s=80,
                          marker="^", label="Satellite", zorder=10)
        self.ax3d.scatter([ex], [ey], [ez], c="#4fc3f7", s=50,
                          marker="o", label="Earth Station", zorder=10)
        self.ax3d.plot([sx, ex], [sy, ey], [sz, ez], color="#ffab40",
                       linestyle="--", lw=1.5, alpha=0.9, label="Link")

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

        global_types = ["Macro_countries", "SINGLE_SPACE_STATION",
                        "MSS_DC", "EESS_SS", "METSAT_SS", "SINGLE_EARTH_STATION",
                        "MSS_SS", "HAPS"]
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

        ue_height = _coerce_float(_yaml_first(data, ("imt.ue.height", "ue_height"), None), 1.5)
        if hasattr(self.app, "ue_height"):
            ue_height = _safe_float(getattr(self.app, "ue_height", None), ue_height)

        # ============================================================
        # INDOOR topology (Plotly)
        # ============================================================
        if topo_type == "INDOOR" and self._indoor_topo is not None:
            topo = self._indoor_topo
            b_w, b_d, b_h = topo.b_w, topo.b_d, topo.b_h
            num_cells = topo.num_cells
            cell_radius = topo.cell_radius
            num_floors = topo.num_floors
            n_total_bs = len(topo.x)
            bs_per_floor = max(1, n_total_bs // max(1, num_floors))

            # Draw building wireframes
            bld_x, bld_y, bld_z = [], [], []
            for b_idx in range(bs_per_floor // max(1, num_cells)):
                floor_i = b_idx * num_cells
                if floor_i >= len(topo.x):
                    break
                x_b = topo.x[floor_i] - cell_radius
                y_b = topo.y[floor_i] - b_d / 2
                for f in range(num_floors):
                    z0, z1 = f * b_h, (f + 1) * b_h
                    corners = [(x_b, y_b), (x_b+b_w, y_b), (x_b+b_w, y_b+b_d), (x_b, y_b+b_d), (x_b, y_b)]
                    for cx, cy in corners:
                        bld_x.append(cx); bld_y.append(cy); bld_z.append(z0)
                    bld_x.append(None); bld_y.append(None); bld_z.append(None)
                    for cx, cy in corners:
                        bld_x.append(cx); bld_y.append(cy); bld_z.append(z1)
                    bld_x.append(None); bld_y.append(None); bld_z.append(None)
                    # Verticals
                    for cx, cy in corners[:4]:
                        bld_x.extend([cx, cx, None]); bld_y.extend([cy, cy, None]); bld_z.extend([z0, z1, None])

            fig.add_trace(go.Scatter3d(x=bld_x, y=bld_y, z=bld_z, mode="lines",
                                       line=dict(color="sienna", width=2), name="Buildings"))

            heights = list(topo.height) if hasattr(topo, "height") and len(topo.height) > 0 else [bs_height]*len(xs)
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=heights, mode="markers",
                                       marker=dict(size=4, color="blue", symbol="square"),
                                       name="Indoor BS"))
            # UEs
            n_ue = min(len(xs) * 3, 60)
            if n_ue > 0:
                ue_xs = [xs[i % len(xs)] + np.random.uniform(-cell_radius, cell_radius) for i in range(n_ue)]
                ue_ys = [ys[i % len(ys)] + np.random.uniform(-b_d/2, b_d/2) for i in range(n_ue)]
                ue_zs = [heights[i % len(heights)] - np.random.uniform(0, b_h*0.8) for i in range(n_ue)]
                fig.add_trace(go.Scatter3d(x=ue_xs, y=ue_ys, z=ue_zs, mode="markers",
                                           marker=dict(size=2, color="red"), name="UE (sample)", opacity=0.6))
            return

        # ============================================================
        # NTN topology (Plotly)
        # ============================================================
        if topo_type == "NTN" and self._ntn_topo is not None:
            topo = self._ntn_topo
            sc = 1000.0
            cr_km = topo.cell_radius / sc

            # Hexagonal sectors
            hex_x, hex_y, hex_z = [], [], []
            for x, y in zip(topo.x / sc, topo.y / sc):
                angs = np.linspace(0, 2*np.pi, 7)
                hx = list(x + cr_km * np.cos(angs))
                hy = list(y + cr_km * np.sin(angs))
                hex_x.extend(hx + [None]); hex_y.extend(hy + [None]); hex_z.extend([0]*7 + [None])

            fig.add_trace(go.Scatter3d(x=hex_x, y=hex_y, z=hex_z, mode="lines",
                                       line=dict(color="gray", width=2), name="Sector Cells"))
            # Anchor points
            fig.add_trace(go.Scatter3d(x=list(topo.x/sc), y=list(topo.y/sc), z=[0]*len(topo.x),
                                       mode="markers", marker=dict(size=5, color="black", symbol="diamond"),
                                       name="Anchor Points"))
            # Satellite
            sx, sy, sz = topo.space_station_x/sc, topo.space_station_y/sc, topo.space_station_z/sc
            fig.add_trace(go.Scatter3d(x=[sx], y=[sy], z=[sz], mode="markers",
                                       marker=dict(size=8, color="red", symbol="diamond"),
                                       name=f"Satellite (el={np.degrees(topo.bs_elevation):.0f}°)"))
            # Height + slant lines
            fig.add_trace(go.Scatter3d(x=[sx, sx], y=[sy, sy], z=[0, sz], mode="lines",
                                       line=dict(color="blue", width=3), name=f"Height = {sz:.0f} km"))
            fig.add_trace(go.Scatter3d(x=[0, sx], y=[0, sy], z=[0, sz], mode="lines",
                                       line=dict(color="green", width=3, dash="dash"),
                                       name=f"Slant = {topo.bs_radius/sc:.0f} km"))
            # UEs
            n_ue = min(len(topo.x)*5, 80)
            if n_ue > 0:
                ue_x = [topo.x[i%len(topo.x)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                ue_y = [topo.y[i%len(topo.y)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                fig.add_trace(go.Scatter3d(x=ue_x, y=ue_y, z=[0]*n_ue, mode="markers",
                                           marker=dict(size=2, color="red"), name="UE (sample)", opacity=0.5))
            fig.update_layout(scene=dict(xaxis_title="x [km]", yaxis_title="y [km]", zaxis_title="z [km]"))
            return

        # ============================================================
        # Standard terrestrial topologies (Plotly)
        # ============================================================
        if draw_hex and hex_centers:
            hex_x, hex_y, hex_z = [], [], []
            for cx, cy in hex_centers:
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
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            for x, y, az in zip(xs, ys, azs):
                self._add_wedge_plotly(
                    fig, x, y, sec_radius, az, bs_height, color)

        # UE positions (Plotly)
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            ue_k = _safe_int(getattr(self.app, "ue_k", None), 3)
            ue_radius = hex_radius * 0.9 if hex_radius > 0 else sec_radius * 0.9
            if topo_type == "HOTSPOT":
                ue_radius = _safe_float(getattr(self.app, "hotspot_max_dist_ue", None), 50.0)
            unique_bs = list(set(zip(xs, ys)))
            n_ue = min(len(unique_bs) * max(ue_k, 1), 120)
            ue_xs, ue_ys = [], []
            for i in range(n_ue):
                bx, by = unique_bs[i % len(unique_bs)]
                ang = np.random.uniform(0, 2*np.pi)
                r = np.random.uniform(0, ue_radius)
                ue_xs.append(bx + r*np.cos(ang))
                ue_ys.append(by + r*np.sin(ang))
            if ue_xs:
                fig.add_trace(go.Scatter3d(x=ue_xs, y=ue_ys, z=[ue_height]*len(ue_xs),
                                           mode="markers", marker=dict(size=2, color="red"),
                                           name=f"UE (K={ue_k})", opacity=0.6))

        # MSS_D2D (Plotly)
        if topo_type == "MSS_D2D":
            fig.add_trace(go.Scatter3d(x=xs[:1], y=ys[:1], z=[ue_height], mode="markers",
                                       marker=dict(size=6, color="green", symbol="diamond"), name="Device 1"))
            if len(xs) > 1:
                fig.add_trace(go.Scatter3d(x=xs[1:2], y=ys[1:2], z=[ue_height], mode="markers",
                                           marker=dict(size=6, color="purple", symbol="diamond"), name="Device 2"))
                fig.add_trace(go.Scatter3d(x=[xs[0], xs[1]], y=[ys[0], ys[1]], z=[ue_height]*2,
                                           mode="lines", line=dict(color="orange", width=4, dash="dash"), name="D2D Link"))

        if self.app.var_system.get() == "SINGLE_EARTH_STATION":
            mode = getattr(self.app, "se_loc_type", None)
            mode = mode.get() if hasattr(mode, "get") else "FIXED"

            # ---------------- FIXED ----------------
            if mode == "FIXED":
                x0 = _safe_float(getattr(self.app, "se_loc_fixed_x", 0.0))
                y0 = _safe_float(getattr(self.app, "se_loc_fixed_y", 0.0))

                fig.add_trace(go.Scatter3d(
                    x=[x0], y=[y0], z=[bs_height],
                    mode="markers",
                    marker=dict(size=6, color="red"),
                    name="Single Earth Station"
                ))
# ---------------- UNIFORM ----------------
            elif mode == "UNIFORM_DIST":

                rmin = _safe_float(getattr(self.app, "se_loc_ud_min_dist_to_center", 10))
                rmax = _safe_float(getattr(self.app, "se_loc_ud_max_dist_to_center", 100))

                # posição exemplo (uma realização)
                ang = np.random.uniform(0, 2*np.pi)
                r = np.random.uniform(rmin, rmax)

                x0 = r*np.cos(ang)
                y0 = r*np.sin(ang)

                # ponto
                fig.add_trace(go.Scatter3d(
                    x=[x0], y=[y0], z=[bs_height],
                    mode="markers",
                    marker=dict(size=6, color="red"),
                    name="Single Earth Station"
                ))

                # anel
                th = np.linspace(0, 2*np.pi, 100)

                fig.add_trace(go.Scatter3d(
                    x=rmin*np.cos(th),
                    y=rmin*np.sin(th),
                    z=[bs_height]*len(th),
                    mode="lines",
                    line=dict(color="red", dash="dot"),
                    name="min radius"
                ))

                fig.add_trace(go.Scatter3d(
                    x=rmax*np.cos(th),
                    y=rmax*np.sin(th),
                    z=[bs_height]*len(th),
                    mode="lines",
                    line=dict(color="red", dash="dot"),
                    name="max radius"
                ))
        fig.update_layout(scene=dict(aspectmode="data"))

    def _draw_global_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        Re = WGS84_A
        # Higher resolution for better sphere
        N_phi, N_theta = 80, 40
        u = np.linspace(0, 2*np.pi, N_phi)
        v = np.linspace(0, np.pi, N_theta)
        X = Re * np.outer(np.cos(u), np.sin(v))
        Y = Re * np.outer(np.sin(u), np.sin(v))
        Z = Re * np.outer(np.ones_like(u), np.cos(v))

        # ============================================================
        # Macro_countries: show BS positions distributed across countries
        # ============================================================
        if topo_type == "Macro_countries":
            fig.add_trace(go.Surface(
                x=X, y=Y, z=Z,
                surfacecolor=np.zeros_like(Z),
                colorscale=[[0, "lightblue"], [1, "lightblue"]],
                opacity=0.3, showscale=False, name="Earth Surface"
            ))

            if self.app.show_borders.get():
                self._draw_borders_plotly(fig)

            # Get BS positions with cache invalidation
            countries_str = _coerce_str(getattr(self.app, "topo_countries", ""), "Brazil")
            num_bs_val = _safe_int(getattr(self.app, "topo_num_bs", None), 50)
            cache_key = f"{countries_str}_{num_bs_val}"
            
            bs_lats = getattr(self.app, "_mc_bs_lats", None)
            bs_lons = getattr(self.app, "_mc_bs_lons", None)
            last_key = getattr(self.app, "_mc_cache_key", None)
            
            if bs_lats is None or bs_lons is None or last_key != cache_key:
                try:
                    if TopologyCountries is None or ParametersCountries is None:
                        raise ImportError("TopologyCountries/ParametersCountries not available")
                    
                    param_c = ParametersCountries()
                    names = [c.strip() for c in countries_str.split(",") if c.strip()]
                    param_c.country_names = names if names else ["Brazil"]
                    param_c.num_bs_total = _safe_int(getattr(self.app, "topo_num_bs", None), 50)
                    
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    shp_path = os.path.join(base_dir, "topology", "map", "ne_110m_admin_0_countries.shp")
                    ras_path = os.path.join(base_dir, "topology", "map", "SEDAC_map2.tiff")
                    act_path = os.path.join(base_dir, "topology", "map", "sedac_pop.act")
                    if os.path.exists(shp_path): param_c.shapefile_path = shp_path
                    if os.path.exists(ras_path): param_c.population_raster = ras_path
                    if os.path.exists(act_path): param_c.act_colormap_path = act_path
                    
                    topo = TopologyCountries(param_c, None)
                    topo.calculate_coordinates()
                    bs_lats, bs_lons = topo.lats, topo.lons
                    
                    self.app._mc_bs_lats = bs_lats
                    self.app._mc_bs_lons = bs_lons
                except Exception as e:
                    print(f"[PreviewTab] TopologyCountries failed: {e}")
                    n_bs = _safe_int(getattr(self.app, "topo_num_bs", None), 50)
                    center_lat = _safe_float(getattr(self.app, "topo_center_lat", None), -15.0)
                    center_lon = _safe_float(getattr(self.app, "topo_center_lon", None), -47.0)
                    np.random.seed(42)
                    bs_lats = center_lat + np.random.uniform(-15, 15, n_bs)
                    bs_lons = center_lon + np.random.uniform(-20, 20, n_bs)

            bs_x, bs_y, bs_z = lla_to_ecef(bs_lats, bs_lons, 0)
            offset = 1.005
            fig.add_trace(go.Scatter3d(
                x=np.asarray(bs_x) * offset,
                y=np.asarray(bs_y) * offset,
                z=np.asarray(bs_z) * offset,
                mode="markers",
                marker=dict(size=3, color="cyan", symbol="diamond"),
                name=f"BS ({len(bs_lats)})"
            ))

            # Removed early return and scene data override so spatial elements render below

        # ============================================================
        # Standard satellite/earth-station global scenarios
        # ============================================================
        sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)

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

        # Reset topology-specific caches
        self._indoor_topo = None
        self._ntn_topo = None

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

            elif topo_type == "INDOOR":
                if ParametersIndoor is not None and TopologyIndoor is not None:
                    p_ind = ParametersIndoor()
                    p_ind.intersite_distance = _safe_float(getattr(self.app, "indoor_intersite", None), 20.0)
                    p_ind.n_rows = _safe_int(getattr(self.app, "indoor_n_rows", None), 3)
                    p_ind.n_colums = _safe_int(getattr(self.app, "indoor_n_cols", None), 3)
                    p_ind.street_width = _safe_float(getattr(self.app, "indoor_street_width", None), 30.0)
                    p_ind.num_cells = _safe_int(getattr(self.app, "indoor_num_cells", None), 6)
                    p_ind.num_floors = _safe_int(getattr(self.app, "indoor_num_floors", None), 3)
                    nb = _coerce_str(getattr(self.app, "indoor_num_buildings", "ALL"), "ALL")
                    p_ind.num_imt_buildings = nb
                    p_ind.ue_indoor_percent = _safe_float(getattr(self.app, "indoor_ue_indoor_percent", None), 0.95)
                    p_ind.building_class = _coerce_str(getattr(self.app, "indoor_building_class", "TRADITIONAL"), "TRADITIONAL")
                    topo = TopologyIndoor(p_ind)
                    topo.calculate_coordinates()
                    xs = list(topo.x)
                    ys = list(topo.y)
                    azs = list(topo.azimuth) if len(topo.azimuth) > 0 else [0.0] * len(xs)
                    self._indoor_topo = topo
                else:
                    xs, ys, azs = [0], [0], [0]

            elif topo_type == "NTN":
                if TopologyNTN is not None:
                    isd = _safe_float(getattr(self.app, "ntn_intersite", None), 100000.0)
                    cr = _safe_float(getattr(self.app, "ntn_cell_radius", None), 50000.0)
                    bsh = _safe_float(getattr(self.app, "ntn_bs_height", None), 600000.0)
                    bsa = _safe_float(getattr(self.app, "ntn_bs_azimuth", None), 45.0)
                    bse = _safe_float(getattr(self.app, "ntn_bs_elevation", None), 45.0)
                    ns = _safe_int(getattr(self.app, "ntn_num_sectors", None), 7)
                    if ns not in (1, 7, 19):
                        ns = 7
                    topo = TopologyNTN(
                        intersite_distance=isd,
                        cell_radius=cr,
                        bs_height=bsh,
                        bs_azimuth=bsa,
                        bs_elevation=bse,
                        num_sectors=ns,
                    )
                    xs = list(topo.x)
                    ys = list(topo.y)
                    azs = list(topo.azimuth) if hasattr(topo, "azimuth") and len(topo.azimuth) > 0 else [0.0] * len(xs)
                    hex_radius = cr
                    draw_hex = True
                    hex_centers = list(set(zip(xs, ys)))
                    self._ntn_topo = topo
                else:
                    xs, ys, azs = [0], [0], [0]

            elif topo_type == "MSS_D2D":
                # Simple fallback: two UE positions
                xs, ys, azs = [0.0, 200.0], [0.0, 100.0], [0.0, 180.0]

            else:
                # Generic fallback for unknown topology
                xs, ys, azs = [0.0], [0.0], [0.0]

        except Exception as e:
            print(f"Topology calc error: {e}")
            traceback.print_exc()
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
        """Compute gain map on the sphere surface using SHARC's antenna API."""
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

        # Use vectorized batch call for performance
        gains = _antenna_gain_db_batch(antenna, angles_deg)

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

    def _get_border_coords(self) -> List[Tuple[np.ndarray, np.ndarray, bool]]:
        """Reliably extract border coordinates, trying local SHARC files first, then Geopandas.
        Returns tuples of (lat_array, lon_array, is_selected).
        """
        coords = []
        
        # Get selected countries for highlighting
        selected_names = [c.strip().lower() for c in getattr(self.app, "topo_countries", tk.StringVar()).get().split(",") if c.strip()]
        
        # 1. Try user-provided path
        paths_to_try = []
        if hasattr(self.app, "path_shp") and self.app.path_shp.get():
            paths_to_try.append(self.app.path_shp.get().strip())
            
        # 2. Try SHARC local shapefiles
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            paths_to_try.extend([
                os.path.join(base_dir, "topology", "map", "ne_110m_admin_0_countries.shp"),
                os.path.join(base_dir, "data", "countries", "ne_110m_admin_0_countries.shp")
            ])
        except Exception:
            pass

        # Helper to check if a shapefile record matches selected countries
        def _is_selected(record_vals):
            for val in record_vals:
                if str(val).lower() in selected_names:
                    return True
            return False

        # Try to read with pyshp
        if HAS_PYSHP:
            for p in paths_to_try:
                if os.path.exists(p):
                    try:
                        r = pyshp.Reader(p)
                        for sr in r.shapeRecords():
                            is_seq = _is_selected(sr.record)
                            if sr.shape.points:
                                lons, lats = zip(*sr.shape.points)
                                coords.append((np.array(lats), np.array(lons), is_seq))
                        if coords:
                            return coords
                    except Exception:
                        pass

        # Try Geopandas with local files
        if HAS_GEOPANDAS:
            for p in paths_to_try:
                if os.path.exists(p):
                    try:
                        gdf = gpd.read_file(p)
                        # Identify name columns
                        name_cols = [c for c in gdf.columns if c in ["ADMIN", "name", "NAME", "admin", "Country", "SOVEREIGNT"]]
                        
                        for idx, row in gdf.iterrows():
                            is_seq = any(str(row[c]).lower() in selected_names for c in name_cols) if name_cols else False
                            geom = row.geometry
                            if geom is None:
                                continue
                            if geom.geom_type == 'Polygon':
                                lons, lats = geom.exterior.coords.xy
                                coords.append((np.array(lats), np.array(lons), is_seq))
                            elif geom.geom_type == 'MultiPolygon':
                                for poly in geom.geoms:
                                    lons, lats = poly.exterior.coords.xy
                                    coords.append((np.array(lats), np.array(lons), is_seq))
                        if coords:
                            return coords
                    except Exception:
                        pass
                        
            # Finally, try Geopandas built-in (might fail on >=1.0)
            try:
                if hasattr(gpd.datasets, "get_path"):
                    gdf = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
                    name_cols = [c for c in gdf.columns if c in ["ADMIN", "name", "NAME", "admin", "Country", "SOVEREIGNT"]]
                    for idx, row in gdf.iterrows():
                        is_seq = any(str(row[c]).lower() in selected_names for c in name_cols) if name_cols else False
                        geom = row.geometry
                        if geom is None:
                            continue
                        if geom.geom_type == 'Polygon':
                            lons, lats = geom.exterior.coords.xy
                            coords.append((np.array(lats), np.array(lons), is_seq))
                        elif geom.geom_type == 'MultiPolygon':
                            for poly in geom.geoms:
                                lons, lats = poly.exterior.coords.xy
                                coords.append((np.array(lats), np.array(lons), is_seq))
                    if coords:
                        return coords
            except Exception:
                pass
                
        return coords

    def _draw_borders_mpl(self):
        coords = self._get_border_coords()

        for lat, lon, is_selected in coords:
            x, y, z = lla_to_ecef(lat, lon, 0)
            # Offset outwards slightly to prevent z-fighting with the sphere surface
            offset = 1.002
            x = np.asarray(x) * offset
            y = np.asarray(y) * offset
            z = np.asarray(z) * offset
            
            if is_selected:
                self.ax3d.plot(x, y, z, color="#00ff00", lw=2.0, alpha=1.0)  # Bright lime green
            else:
                self.ax3d.plot(x, y, z, color="#ffffff", lw=0.6, alpha=0.9)

    def _draw_footprint_mpl(self, sx, sy, sz, bw):
        fp = self._compute_footprint_boundary(sx, sy, sz, bw)
        if fp is not None:
            self.ax3d.plot(fp[:, 0], fp[:, 1], fp[:, 2],
                           color="magenta", lw=1.5, label="Footprint")

    def _draw_borders_plotly(self, fig):
        coords = self._get_border_coords()

        for lat, lon, is_selected in coords:
            # Offset borders slightly (1.001*R) to avoid z-fighting with sphere surface
            x, y, z = lla_to_ecef(lat, lon, 0.0)
            # Basic scaling to push them out a tiny bit
            norm = np.sqrt(x*x + y*y + z*z)
            scale = (WGS84_A * 1.001) / norm
            
            color = "lime" if is_selected else "white"
            width = 3 if is_selected else 1
            
            fig.add_trace(go.Scatter3d(
                x=x*scale, y=y*scale, z=z*scale,
                mode="lines", line=dict(color=color, width=width), showlegend=False
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

    # NOTE: _update_yaml_preview is defined earlier (line ~504).
    # The duplicate definition that was here has been removed.

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
    
