"""Who interferes with whom, and how much each base station contributes (for the 3D preview).

Roles come from the engine: with `imt.interfered_with = False` (default) the IMT network is the *interferer* and the
system is the *victim*; with True it is the other way around. When the system is the victim, every base station gets
its contribution to the interference at the victim receiver [dBm/MHz]:

    contribution = EIRP_psd + G_bs(toward the victim) - FSPL + G_victim(toward the BS) - polarization loss

(co-channel, free space, nominal power). Satellites reuse `core.sat_footprint`; earth stations are computed here.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np


def roles(es) -> Dict[str, str]:
    imt_interfered = bool(getattr(es.params.imt, "interfered_with", False))
    return {"imt": "victim" if imt_interfered else "interferer", "system": "interferer" if imt_interfered else "victim"}


def _earth_station(es) -> Optional[Dict[str, Any]]:
    from core import antenna_service, gain_lobe, heatmap
    sys_geom = es.system.geom
    ex, ey, ez = float(sys_geom.x_global[0]), float(sys_geom.y_global[0]), float(sys_geom.z_global[0])
    az, el = math.radians(float(sys_geom.pointn_azim_global[0])), math.radians(float(sys_geom.pointn_elev_global[0]))
    point = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    geom, p = es.bs.geom, es.params.imt
    bx, by, bz = (np.asarray(geom.x_global, float), np.asarray(geom.y_global, float), np.asarray(geom.z_global, float))
    v = np.stack([ex - bx, ey - by, ez - bz], axis=-1)                         # BS -> ES
    dist = np.maximum(np.linalg.norm(v, axis=-1), 1.0)
    # ES antenna gain toward the BS: angle between the ES pointing and the direction ES -> BS
    cosang = (-v / dist[:, None]) @ point
    g_es = np.asarray(antenna_service.gain_at(es.system.antenna[0], np.degrees(np.arccos(np.clip(cosang, -1, 1)))), float)
    data = gain_lobe.sample_bs_gain(es)
    hd = np.hypot(v[:, 0], v[:, 1])
    az_bs = np.asarray(geom.pointn_azim_global, float)
    dphi = (np.degrees(np.arctan2(v[:, 1], v[:, 0])) - az_bs + 180.0) % 360.0 - 180.0
    elev = np.degrees(np.arctan2(v[:, 2], np.maximum(hd, 1e-3)))
    g_bs = heatmap._interp(data)(np.stack([elev, dphi], axis=-1))
    eirp_psd = float(p.bs.conducted_power) - float(p.bs.ohmic_loss) - 10.0 * math.log10(float(p.bandwidth))
    sp = es.params.single_earth_station
    pol = float(getattr(sp, "polarization_loss", 0.0) or 0.0)
    fspl = 32.44 + 20.0 * np.log10(dist / 1000.0) + 20.0 * math.log10(float(p.frequency))
    contrib = eirp_psd + g_bs - fspl + g_es - pol
    total = float(10.0 * np.log10(np.sum(10.0 ** (contrib / 10.0))))
    noise = -114.0 + 10.0 * math.log10(float(getattr(sp, "noise_temperature", None) or 290.0) / 290.0)
    return {"contrib": [round(float(c), 1) for c in contrib], "psd_dbm_mhz": round(total, 1),
            "noise_psd_dbm_mhz": round(noise, 1), "inr_db": round(total - noise, 1), "victim_name": "earth station"}


def compute(es) -> Optional[Dict[str, Any]]:
    """Roles and per-base-station contributions, or None when the scenario has no victim system to evaluate."""
    cached = getattr(es, "_interference", "unset")
    if cached != "unset":
        return cached
    result = None
    try:
        r = roles(es)
        result = {"roles": r}
        system = str(es.params.general.system).upper()
        if r["system"] == "victim" and es.system is not None:
            if system == "SINGLE_SPACE_STATION":
                from core import sat_footprint
                fp = sat_footprint.compute(es)
                if fp:
                    s = fp["summary"]
                    result.update({"contrib": fp["contrib"], "psd_dbm_mhz": s["imt_psd_at_sat_dbm_mhz"],
                                   "noise_psd_dbm_mhz": s["noise_psd_dbm_mhz"], "inr_db": s["inr_db"],
                                   "victim_name": "satellite"})
            elif system == "SINGLE_EARTH_STATION":
                result.update(_earth_station(es) or {})
        c = result.get("contrib")
        if c:
            result["cmin"], result["cmax"] = round(min(c), 1), round(max(c), 1)
    except Exception:                                        # noqa: BLE001 - decoration only
        result = None
    try:
        es._interference = result
    except Exception:                                        # noqa: BLE001
        pass
    return result
