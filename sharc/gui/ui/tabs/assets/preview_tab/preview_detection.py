"""
preview_detection.py – Standalone detection helpers for the Preview Tab.

Extracted from PreviewTab so they can be tested and reused independently.

Public API:
    get_current_yaml(app)          -> Dict[str, Any]
    detect_system_type(data, app)  -> str
    detect_topology_type(data, app)-> str
"""

from __future__ import annotations

from typing import Any, Dict

from utils import _coerce_str, _yaml_first, _yaml_get


def get_current_yaml(app: Any) -> Dict[str, Any]:
    """Return the current YAML configuration dict from *app*, or ``{}``."""
    if hasattr(app, "current_yaml_dict") and callable(app.current_yaml_dict):
        try:
            data = app.current_yaml_dict()
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def detect_system_type(data: Dict[str, Any], app: Any = None) -> str:
    """Detect the system type from *data* (YAML dict) and/or *app* variables.

    Returns a normalised upper-case system-type string such as
    ``"SINGLE_EARTH_STATION"``, ``"SINGLE_SPACE_STATION"``, ``"HAPS"``, etc.
    Falls back to ``"SINGLE_EARTH_STATION"`` when nothing can be determined.
    """
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

    if not sys_type and app is not None and hasattr(app, "var_system"):
        sys_type = _coerce_str(getattr(app, "var_system", ""), "")

    t = (sys_type or "").strip().upper().replace("-", "_")
    return t or "SINGLE_EARTH_STATION"


def detect_topology_type(data: Dict[str, Any], app: Any = None) -> str:
    """Detect topology type from *data* (YAML dict) and/or *app* variables.

    IMPORTANT: The SHARC simulator uses the literal string ``'Macro_countries'``
    (mixed case) in ``topology_factory.py`` and ``station_factory.py``, so we
    preserve that exact spelling rather than upper-casing it.

    Returns a normalised topology-type string such as ``"MACROCELL"``,
    ``"Macro_countries"``, ``"NTN"``, ``"MSS_DC"``, etc.
    Falls back to ``"MACROCELL"`` when nothing can be determined.
    """
    topo_type = _coerce_str(
        _yaml_first(
            data,
            (
                "topology.type",
                "imt.topology.type",
                "imt.topology",          # sometimes stored as a bare string
                "general.system",
            ),
            default="",
        ),
        "",
    )

    if not topo_type and isinstance(_yaml_get(data, "imt.topology.mss_dc", None), dict):
        topo_type = "MSS_DC"

    if not topo_type and "single_earth_station" in data:
        topo_type = "SINGLE_EARTH_STATION"

    if not topo_type and app is not None and hasattr(app, "topo_type"):
        topo_type = _coerce_str(getattr(app, "topo_type", ""), "")

    t = (topo_type or "").strip()

    # Normalise Macro_countries variants to SHARC's canonical form
    if t.lower().replace("_", "") in ("macrocountries", "macrocountry"):
        return "Macro_countries"
    if t in ("Macro_countries", "Macro_Countries", "macro_countries"):
        return "Macro_countries"
    if t.lower().replace("-", "_") in ("mss_dc", "mssdc"):
        return "MSS_DC"
    if t.upper() in {"SINGLE_BASE_STATION", "SINGLE_BS"}:
        return "SINGLE_BS"

    # Known SHARC topology/system types – upper-case them
    t_up = t.upper()
    return t_up if t_up else "MACROCELL"
