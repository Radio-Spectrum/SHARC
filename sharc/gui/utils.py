"""
utils.py – Shared helpers for the SHARC GUI.

Provides:
  - Type-safe coercion helpers (_safe_float, _safe_int, _coerce_*, _as_value)
  - YAML helpers (_yaml_get, _yaml_first, dump_yaml_block, build_yaml_text)
  - Geodetic math (lla_to_ecef)
  - Geometry / hex / antenna helpers (_unit, _approx_hex_cluster_centers, etc.)
  - Optional-library feature flags (HAS_PLOTLY, HAS_PYSHP, HAS_GEOPANDAS, HAS_TKHTMLVIEW)
  - SHARC-core topology imports + HAS_SHARC_CORE flag
  - Preview constants (GLOBAL_PREVIEW_TYPES, SUPPORTED_TOPOLOGY_TYPES, SUPPORTED_SYSTEM_TYPES)
  - GUI-state query helpers (_get_imt_value, _get_countries_text, _parse_country_names, etc.)
  - UI layout helpers (add_row_three, CollapsibleFrame)
"""

from __future__ import annotations

import math
import traceback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QGridLayout
)
from PySide6.QtCore import Qt

# ============================================================================
# CONFIG CONSTANTS
# ============================================================================

try:
    from config import WGS84_A, WGS84_F
except ImportError:
    WGS84_A = 6378137.0
    WGS84_F = 1.0 / 298.257223563

# ============================================================================
# OPTIONAL LIBRARY FLAGS
# ============================================================================

HAS_PLOTLY = True
try:
    import plotly.graph_objects as go  # noqa: F401
except Exception:
    HAS_PLOTLY = False

HAS_TKHTMLVIEW = True
try:
    from tkhtmlview import HTMLLabel  # noqa: F401
except Exception:
    HAS_TKHTMLVIEW = False

HAS_PYSHP = True
try:
    import shapefile as pyshp  # noqa: F401
except Exception:
    HAS_PYSHP = False
    pyshp = None

HAS_GEOPANDAS = True
try:
    import geopandas as gpd  # noqa: F401
except Exception:
    HAS_GEOPANDAS = False
    gpd = None

# ============================================================================
# SHARC CORE TOPOLOGY IMPORTS
# ============================================================================

HAS_SHARC_CORE = True
TopologyMacrocell = None
TopologyHotspot = None
TopologySingleBaseStation = None
TopologyIndoor = None
TopologyNTN = None
TopologyCountries = None
TopologyUEOnly = None
ParametersCountries = None
ParametersHotspot = None
ParametersIndoor = None
ParametersSingleSpaceStation = None
ParametersSingleEarthStation = None
StationFactory = None
AntennaS672 = None
ParametersAntennaS672 = None

try:
    from sharc.topology.topology_macrocell import TopologyMacrocell
    from sharc.topology.topology_hotspot import TopologyHotspot
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation
    from sharc.topology.topology_indoor import TopologyIndoor

    try:
        from sharc.topology.topology_ntn import TopologyNTN
    except Exception:
        TopologyNTN = None

    try:
        from sharc.topology.topology_countries import TopologyCountries
        from sharc.parameters.imt.parameters_Countries_imt import ParametersCountries
    except Exception:
        TopologyCountries = None
        ParametersCountries = None

    try:
        from sharc.topology.topology_ue_only import TopologyUEOnly
    except Exception:
        TopologyUEOnly = None

    try:
        from sharc.station_factory import StationFactory
    except Exception:
        try:
            from station_factory import StationFactory
        except Exception:
            StationFactory = None

    try:
        from sharc.parameters.parameters_single_space_station import ParametersSingleSpaceStation
    except Exception:
        ParametersSingleSpaceStation = None

    try:
        from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation
    except Exception:
        ParametersSingleEarthStation = None

    try:
        from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
    except Exception:
        ParametersHotspot = None

    try:
        from sharc.parameters.imt.parameters_indoor import ParametersIndoor
    except Exception:
        ParametersIndoor = None

    try:
        from sharc.antenna.antenna_s672 import AntennaS672
        from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
    except Exception:
        AntennaS672 = None
        ParametersAntennaS672 = None

except Exception:
    HAS_SHARC_CORE = False

# ============================================================================
# PREVIEW CONSTANTS
# ============================================================================

SUPPORTED_TOPOLOGY_TYPES = (
    "MACROCELL",
    "HOTSPOT",
    "SINGLE_BS",
    "Macro_countries",
    "INDOOR",
    "NTN",
    "MSS_DC",
)

SUPPORTED_SYSTEM_TYPES = (
    "SINGLE_EARTH_STATION",
    "SINGLE_SPACE_STATION",
    "HAPS",
    "MSS_SS",
    "MSS_D2D",
    "MSS_DC",
)

GLOBAL_PREVIEW_TYPES = {
    "Macro_countries",
    "SINGLE_SPACE_STATION",
    "EESS_SS",
    "METSAT_SS",
    "FSS_SS",
}

# ============================================================================
# YAML HELPERS
# ============================================================================


def _yaml_bool(v: bool) -> str:
    """Converte booleano Python para string minúscula (padrão YAML)."""
    return "true" if v else "false"


def dump_yaml_block(d, indent=0):
    """
    Função recursiva para gerar texto YAML manualmente,
    preservando ordem e formatação específica desejada.
    """
    lines = []
    sp = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.extend(dump_yaml_block(v, indent + 1))
            elif isinstance(v, (list, tuple)):
                lines.append(f"{sp}{k}:")
                for it in v:
                    if isinstance(it, (dict, list, tuple)):
                        lines.append(f"{sp}-")
                        lines.extend(dump_yaml_block(it, indent + 1))
                    elif isinstance(it, bool):
                        lines.append(f"{sp}- {_yaml_bool(it)}")
                    elif it is None:
                        lines.append(f"{sp}- null")
                    else:
                        lines.append(f"{sp}- {it}")
            elif isinstance(v, bool):
                lines.append(f"{sp}{k}: {_yaml_bool(v)}")
            elif v is None:
                lines.append(f"{sp}{k}: null")
            else:
                lines.append(f"{sp}{k}: {v}")
    else:
        lines.append(f"{sp}{d}")
    return lines


def build_yaml_text(root_dict: dict) -> str:
    """Constrói a string final do arquivo YAML a partir de um dicionário."""
    return "\n".join(dump_yaml_block(root_dict)) + "\n"


def _yaml_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Safely get nested value from dict using dotted path (e.g. 'imt.topology.type')."""
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

# ============================================================================
# TYPE-SAFE COERCION HELPERS
# ============================================================================


def _as_value(x: Any) -> Any:
    """If x is a Tk variable, return x.get(); else return x."""
    try:
        if hasattr(x, "get") and callable(x.get):
            return x.get()
    except Exception:
        pass
    return x


def _safe_float(x: Any, default: float = 0.0) -> float:
    """Safely convert x (possibly a Tk var) to float, returning default on failure."""
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
    """Safely convert x (possibly a Tk var) to int, returning default on failure."""
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

# ============================================================================
# GEODESY / MATH HELPERS
# ============================================================================


def lla_to_ecef(lat_deg, lon_deg, h_m, a=WGS84_A, f=WGS84_F):
    """
    Converte Latitude, Longitude, Altitude para coordenadas ECEF (X, Y, Z).
    Suporta arrays numpy ou escalares.
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    s, c = np.sin(lat), np.cos(lat)
    sl, cl = np.sin(lon), np.cos(lon)
    e2 = f * (2.0 - f)
    N = a / np.sqrt(1.0 - e2 * s * s)
    X = (N + h_m) * c * cl
    Y = (N + h_m) * c * sl
    Z = (N * (1.0 - e2) + h_m) * s
    return X, Y, Z

# ============================================================================
# GEOMETRY / ANTENNA HELPERS
# ============================================================================


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


def _approx_hex_cluster_centers(count: int, spacing: float) -> List[Tuple[float, float]]:
    """Create an approximate 1/7/19-beam hex cluster for preview purposes."""
    if count <= 0:
        return []

    centers: List[Tuple[float, float]] = [(0.0, 0.0)]
    if count == 1:
        return centers

    for k in range(6):
        angle = math.radians(k * 60.0)
        centers.append((spacing * math.cos(angle), spacing * math.sin(angle)))
    if count <= 7:
        return centers[:count]

    for k in range(6):
        angle = math.radians(k * 60.0)
        next_angle = math.radians((k + 1) * 60.0)
        centers.append((2.0 * spacing * math.cos(angle), 2.0 * spacing * math.sin(angle)))
        centers.append((
            spacing * math.cos(angle) + spacing * math.cos(next_angle),
            spacing * math.sin(angle) + spacing * math.sin(next_angle),
        ))

    return centers[:count]


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

    calc_fn = getattr(antenna, "calculate_gain", None)
    if calc_fn and callable(calc_fn):
        try:
            result = calc_fn(off_axis_angle_vec=np.array([off_axis_deg]))
            if hasattr(result, '__len__'):
                return float(result[0])
            return float(result)
        except Exception:
            pass

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

    calc_fn = getattr(antenna, "calculate_gain", None)
    if calc_fn and callable(calc_fn):
        try:
            result = calc_fn(off_axis_angle_vec=off_axis_deg_array)
            return np.asarray(result, dtype=float)
        except Exception:
            pass

    gains = np.zeros_like(off_axis_deg_array)
    for i, ang in enumerate(off_axis_deg_array):
        gains[i] = _antenna_gain_db(antenna, ang)
    return gains

# ============================================================================
# GUI-STATE QUERY HELPERS
# ============================================================================


def _get_imt_value(app: Any, key: str, default: Any = None) -> Any:
    try:
        tab = getattr(app, "tab_imt")
        state = getattr(tab, "state")
        var = state.get(key)
        return var.get()
    except Exception:
        pass

    try:
        value = getattr(app, key)
        return _as_value(value)
    except Exception:
        return default


def _get_countries_text(app: Any, default: str = "Brazil") -> str:
    try:
        return app.tab_imt.topo_section.get_countries_text()
    except Exception:
        return _coerce_str(getattr(app, "topo_countries", ""), default)


def _parse_country_names(text: str) -> List[str]:
    return [c.strip() for c in str(text or "").replace(",", "\n").splitlines() if c.strip()]


def _normalize_raster_encoding(value: Any) -> str:
    raw = str(value or "").strip()
    legacy = {"Uniforme": "uniform", "Denspop": "indexed", "": "uniform"}
    enc = legacy.get(raw, raw.lower())
    return enc if enc in {"uniform", "density", "indexed"} else "uniform"

# ============================================================================
# UI LAYOUT HELPERS
# ============================================================================




# ============================================================================
# EXTENDED UI WIDGETS
# ============================================================================


class CollapsibleFrame(QFrame):
    """
    Um frame expansível/retrátil (estilo accordion) para agrupar opções.
    Para adicionar widgets, coloque-os dentro de `self.sub_frame`.
    """
    def __init__(self, parent=None, text="", expanded=False):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        
        self.is_expanded = expanded
        self._text = text

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        self.title_frame = QWidget()
        self.title_layout = QHBoxLayout(self.title_frame)
        self.title_layout.setContentsMargins(0, 0, 0, 0)

        self.toggle_button = QPushButton("-" if expanded else "+")
        self.toggle_button.setFixedWidth(30)
        self.toggle_button.clicked.connect(self.toggle)
        self.title_layout.addWidget(self.toggle_button)

        self.title_label = QLabel(self._text)
        self.title_label.setStyleSheet("font-family: 'Segoe UI'; font-size: 9pt; font-weight: bold;")
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()

        self.main_layout.addWidget(self.title_frame)

        self.sub_frame = QWidget()
        self.sub_layout = QVBoxLayout(self.sub_frame)
        self.sub_layout.setContentsMargins(5, 5, 5, 5)

        self.main_layout.addWidget(self.sub_frame)

        self.sub_frame.setVisible(self.is_expanded)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.sub_frame.setVisible(self.is_expanded)
        self.toggle_button.setText("-" if self.is_expanded else "+")
