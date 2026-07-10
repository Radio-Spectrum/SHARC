"""
preview_catalog.py – Simulation-summary and supported-catalog helpers for the Preview Tab.

Extracted from PreviewTab so they can be tested and reused independently.

Public API:
    update_sim_summary(self_obj, data)             -> str   (returns the text)
    update_supported_catalog(self_obj, topo_type, sys_type)  -> None
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from utils import (
    SUPPORTED_TOPOLOGY_TYPES,
    SUPPORTED_SYSTEM_TYPES,
    _coerce_str,
    _yaml_first,
)

from ui.tabs.assets.preview_tab.preview_detection import (
    detect_topology_type,
    detect_system_type,
)


def update_sim_summary(self_obj: Any, data: Dict[str, Any]) -> str:
    """Build a human-readable summary of the current simulation configuration.

    Args:
        self_obj: The PreviewTab instance (for access to ``app`` and ``txt_summary``).
        data:     The current YAML configuration dict (from :func:`get_current_yaml`).

    Returns:
        The summary text string (also written to ``self_obj.txt_summary`` when present).
    """
    app = self_obj.app

    def v(paths: Tuple[str, ...], attr: Optional[str] = None, default: str = "—") -> str:
        value = _yaml_first(data, paths, None)
        if (value is None or value == "") and attr and hasattr(app, attr):
            value = getattr(app, attr)
        return _coerce_str(value, default)

    def list_v(paths: Tuple[str, ...]) -> str:
        value = _yaml_first(data, paths, None)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if str(item).strip()) or "—"
        return _coerce_str(value, "—")

    lines = []
    topo     = detect_topology_type(data, app)
    sys_type = detect_system_type(data, app)
    link  = _coerce_str(getattr(app, "var_imt_link", ""), "—")
    freq  = v(("imt.frequency",), "imt_freq")
    bw    = v(("imt.bandwidth",), "imt_bw")
    bs_h  = v(("imt.bs.height", "imt.base_station.height_m"), "bs_height")
    ue_h  = v(("imt.ue.height",), "ue_height")
    ue_k  = v(("imt.ue.k",), "ue_k")
    snaps = _coerce_str(getattr(app, "var_snaps", ""), "—")
    seed  = _coerce_str(getattr(app, "var_seed", ""), "—")
    bs_pwr = v(("imt.bs.conducted_power",), "bs_power")
    bs_dt  = v(("imt.bs.antenna.array.downtilt",), "bs_downtilt")
    ch     = v(("imt.channel_model",), "ch_model")

    lines.append("━━━ SCENARIO ━━━")
    lines.append(f"Topology : {topo}")
    lines.append(f"System   : {sys_type}")
    lines.append(f"Link     : {link}")
    lines.append("")
    lines.append("━━━ IMT ━━━")
    lines.append(f"Freq     : {freq} MHz")
    lines.append(f"BW       : {bw} MHz")
    lines.append(f"Channel  : {ch}")
    lines.append("")
    lines.append("━━━ BS ━━━")
    lines.append(f"Height   : {bs_h} m")
    lines.append(f"Power    : {bs_pwr} dBm")
    lines.append(f"Downtilt : {bs_dt}°")
    lines.append("")
    lines.append("━━━ UE ━━━")
    lines.append(f"Height   : {ue_h} m")
    lines.append(f"K (UEs)  : {ue_k}")
    lines.append("")
    lines.append("━━━ SIMULATION ━━━")
    lines.append(f"Snapshots: {snaps}")
    lines.append(f"Seed     : {seed}")

    # Topology-specific info
    if topo == "INDOOR":
        lines.append("")
        lines.append("━━━ INDOOR ━━━")
        lines.append(f"Rows     : {_coerce_str(getattr(app, 'indoor_n_rows', ''), '—')}")
        lines.append(f"Cols     : {_coerce_str(getattr(app, 'indoor_n_cols', ''), '—')}")
        lines.append(f"Floors   : {_coerce_str(getattr(app, 'indoor_num_floors', ''), '—')}")
        lines.append(f"Cells    : {_coerce_str(getattr(app, 'indoor_num_cells', ''), '—')}")
    elif topo == "NTN":
        lines.append("")
        lines.append("━━━ NTN ━━━")
        lines.append(f"Sat H    : {v(('imt.topology.ntn.bs_height',), 'ntn_bs_height')} m")
        lines.append(f"Elevation: {v(('imt.topology.ntn.bs_elevation',), 'ntn_bs_elevation')}°")
        lines.append(f"Azimuth  : {v(('imt.topology.ntn.bs_azimuth',), 'ntn_bs_azimuth')}°")
        lines.append(f"Sectors  : {v(('imt.topology.ntn.num_sectors',), 'ntn_num_sectors')}")
    elif topo == "MSS_DC":
        lines.append("")
        lines.append("━━━ MSS-DC TOPOLOGY ━━━")
        lines.append(f"Beam R   : {v(('imt.topology.mss_dc.beam_radius',), None)} m")
        lines.append(f"Beams    : {v(('imt.topology.mss_dc.num_beams',), None)}")
        lines.append(
            f"Countries: {list_v(('imt.topology.mss_dc.sat_is_active_if.lat_long_inside_country.country_names', 'imt.topology.mss_dc.beam_positioning.service_grid.country_names'))}"
        )
    elif topo == "Macro_countries":
        lines.append("")
        lines.append("━━━ COUNTRIES ━━━")
        lines.append(f"Num BS   : {v(('imt.topology.macro_countries.num_bs',), 'topo_num_bs')}")
        lines.append(f"Cell R   : {v(('imt.topology.macro_countries.cell_radius',), 'topo_cell_radius')} m")
        countries = v(("imt.topology.macro_countries.countries",), "topo_countries")
        lines.append(f"Countries: {countries}")

    if sys_type == "SINGLE_EARTH_STATION":
        lines.append("")
        lines.append("━━━ EARTH STATION ━━━")
        loc = v(("single_earth_station.geometry.location.type",), "se_loc_type")
        lines.append(f"Location : {loc}")
        lines.append(f"ES Height: {v(('single_earth_station.geometry.height',), 'se_height')} m")
        lines.append(f"Freq     : {v(('single_earth_station.frequency',), 'se_frequency')} MHz")
    elif sys_type == "SINGLE_SPACE_STATION":
        lines.append("")
        lines.append("━━━ SPACE STATION ━━━")
        lines.append(f"Altitude : {v(('single_space_station.geometry.altitude',), 'v_alt')} m")
        lines.append(
            f"Lat/Lon  : {v(('single_space_station.geometry.location.fixed.lat_deg',), 'v_fix_lat')}"
            f" / {v(('single_space_station.geometry.location.fixed.long_deg',), 'v_fix_lon')}"
        )
        lines.append(f"Freq     : {v(('single_space_station.frequency',), 'v_freq')} MHz")
    elif sys_type == "HAPS":
        lines.append("")
        lines.append("━━━ HAPS ━━━")
        lines.append(f"Altitude : {v(('haps.altitude',), 'v_alt')} m")
        lines.append(f"Latitude : {v(('haps.lat_deg',), 'v_fix_lat')}°")
        lines.append(f"Freq     : {v(('haps.frequency',), 'v_freq')} MHz")
    elif sys_type == "MSS_SS":
        lines.append("")
        lines.append("━━━ MSS-SS ━━━")
        lines.append(f"Altitude : {v(('mss_ss.altitude',), 'v_alt')} m")
        lines.append(f"Cell R   : {v(('mss_ss.cell_radius',), 'ntn_cell_radius')} m")
        lines.append(f"Sectors  : {v(('mss_ss.num_sectors',), 'ntn_num_sectors')}")
    elif sys_type == "MSS_D2D":
        lines.append("")
        lines.append("━━━ MSS-D2D ━━━")
        lines.append(f"Freq     : {v(('mss_d2d.frequency',), 'v_freq')} MHz")
        lines.append(f"BW       : {v(('mss_d2d.bandwidth',), 'v_bw')} MHz")
        lines.append(f"Beams    : {v(('mss_d2d.num_sectors', 'imt.topology.mss_dc.num_beams'), None)}")
        lines.append(f"Channel  : {v(('mss_d2d.channel_model',), 'v_ch_model')}")
    elif sys_type == "MSS_DC":
        lines.append("")
        lines.append("━━━ MSS-DC ━━━")
        lines.append(f"Freq     : {v(('mss_dc.frequency',), 'v_freq')} MHz")
        lines.append(f"BW       : {v(('mss_dc.bandwidth',), 'v_bw')} MHz")
        lines.append(f"Beams    : {v(('mss_dc.num_sectors', 'imt.topology.mss_dc.num_beams'), None)}")
        lines.append(f"Channel  : {v(('mss_dc.channel_model',), 'v_ch_model')}")

    text = "\n".join(lines)

    if hasattr(self_obj, "txt_summary"):
        self_obj.txt_summary.configure(state="normal")
        self_obj.txt_summary.delete("1.0", "end")
        self_obj.txt_summary.insert("1.0", text)
        self_obj.txt_summary.configure(state="disabled")

    return text


def update_supported_catalog(self_obj: Any, topo_type: str, sys_type: str) -> None:
    """Populate ``self_obj.txt_catalog`` with the supported topology / system types.

    The currently-active *topo_type* and *sys_type* are highlighted with a
    ``>`` prefix so the user can quickly see where they are in the catalog.

    Args:
        self_obj:  The PreviewTab instance (needs ``txt_catalog`` attribute).
        topo_type: The currently-detected topology type string.
        sys_type:  The currently-detected system type string.
    """
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

    if hasattr(self_obj, "txt_catalog"):
        self_obj.txt_catalog.configure(state="normal")
        self_obj.txt_catalog.delete("1.0", "end")
        self_obj.txt_catalog.insert("1.0", text)
        self_obj.txt_catalog.configure(state="disabled")
