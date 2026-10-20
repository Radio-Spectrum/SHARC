"""Ground heat maps for the preview: IMT downlink PSD, strongest-BS power and I/N, computed from the engine scene.

Each cell of an ENU grid around the network is a receiver at UE height. For every base station the nominal
full-power downlink level is

    PSD  = conducted_power - ohmic_loss - 10 log10(bandwidth) + G_sector(azimuth offset, elevation) - FSPL(d, f)

with G_sector the engine's own array gain toward that direction (`core.gain_lobe`) and free-space loss at the IMT
frequency. Aggregating all base stations in linear power gives the PSD map; the strongest one gives the received
power map; subtracting the victim's noise PSD (kT at its noise temperature) gives I/N. These are coverage /
interference *footprints* for planning, not a Monte Carlo result (no power control, no clutter).
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np

QUANTITIES = {
    "psd": ("Aggregate IMT PSD", "dBm/MHz"),
    "power": ("Strongest BS received power", "dBm"),
    "inr": ("Aggregate I/N", "dB"),
}
GRID_N = 80
M_PER_DEG = 111_320.0


def _noise_temperature_k(es) -> float:
    try:
        system = str(es.params.general.system).lower()
        t = getattr(getattr(es.params, system), "noise_temperature", None)
        return float(t) if t else 290.0
    except Exception:                                        # noqa: BLE001
        return 290.0


def _interp(data: Dict[str, Any]):
    from scipy.interpolate import RegularGridInterpolator
    return RegularGridInterpolator((data["elev"], data["dphi"]), data["gain"], bounds_error=False,
                                   fill_value=float(np.nanmin(data["gain"])))


def levels(es, data: Dict[str, Any], px: np.ndarray, py: np.ndarray, rx_z: float):
    """Nominal downlink at receivers (px, py, rx_z): per-base-station arrays of shape (n_points, n_bs).

    Returns (psd_dbm_mhz, power_dbm, gain_dbi, fspl_db, dist_m)."""
    geom = es.bs.geom
    bx, by, bz = np.asarray(geom.x_global, float), np.asarray(geom.y_global, float), np.asarray(geom.z_global, float)
    az = np.asarray(geom.pointn_azim_global, float)
    p = es.params.imt
    f_mhz, bw_mhz = float(p.frequency), float(p.bandwidth)
    eirp_total = float(p.bs.conducted_power) - float(p.bs.ohmic_loss)
    eirp_psd = eirp_total - 10.0 * math.log10(bw_mhz)
    interp = _interp(data)
    dx, dy = px[:, None] - bx[None, :], py[:, None] - by[None, :]
    hd = np.hypot(dx, dy)
    dz = rx_z - bz[None, :]
    dist = np.maximum(np.hypot(hd, dz), 1.0)
    dphi = (np.degrees(np.arctan2(dy, dx)) - az[None, :] + 180.0) % 360.0 - 180.0
    elev = np.degrees(np.arctan2(dz, np.maximum(hd, 1e-3)))
    gain = interp(np.stack([elev.ravel(), dphi.ravel()], axis=-1)).reshape(dist.shape)
    fspl = 32.44 + 20.0 * np.log10(dist / 1000.0) + 20.0 * math.log10(f_mhz)
    return eirp_psd + gain - fspl, eirp_total + gain - fspl, gain, fspl, dist


def compute(es, n: int = GRID_N) -> Optional[Dict[str, Any]]:
    """Grids for every quantity: {"bounds", "n", "maps": {name: {"values", "vmin", "vmax", "unit", "title"}}}."""
    from core import gain_lobe

    cached = getattr(es, "_heatmaps", "unset")
    if cached != "unset":
        return cached
    result = None
    try:
        data = gain_lobe.sample_bs_gain(es)
        p = es.params.imt
        f_mhz, bw_mhz = float(p.frequency), float(p.bandwidth)
        rx_z = float(np.mean(es.ue.geom.z_global)) if es.ue.geom.num_geometries else 1.5

        gx, gy = np.asarray(es.bs.geom.x_global, float), np.asarray(es.bs.geom.y_global, float)
        reach = float(max(np.abs(gx).max(), np.abs(gy).max())) + 600.0
        xs = np.linspace(-reach, reach, n)
        ys = np.linspace(-reach, reach, n)
        X, Y = np.meshgrid(xs, ys)                                          # row 0 = south
        psd_m, power_m, *_ = levels(es, data, X.ravel(), Y.ravel(), rx_z)
        agg_lin = (10.0 ** (psd_m / 10.0)).sum(axis=1).reshape(X.shape)
        best = power_m.max(axis=1).reshape(X.shape)
        agg_psd = 10.0 * np.log10(np.maximum(agg_lin, 1e-30))
        noise_psd = -114.0 + 10.0 * math.log10(_noise_temperature_k(es) / 290.0)
        grids = {"psd": agg_psd, "power": best, "inr": agg_psd - noise_psd}

        ref = es.reference
        lat0, lon0 = float(ref["lat_deg"]), float(ref["lon_deg"])
        dlat = reach / M_PER_DEG
        dlon = reach / (M_PER_DEG * max(math.cos(math.radians(lat0)), 0.05))
        maps = {}
        for name, g in grids.items():
            lo, hi = np.percentile(g, [2, 99.5])
            title, unit = QUANTITIES[name]
            maps[name] = {"values": np.round(g, 1).ravel().tolist(), "vmin": round(float(lo), 1),
                          "vmax": round(float(max(hi, lo + 1.0)), 1), "unit": unit, "title": title}
        result = {"n": n, "west": lon0 - dlon, "east": lon0 + dlon, "south": lat0 - dlat, "north": lat0 + dlat,
                  "freq_mhz": f_mhz, "bandwidth_mhz": bw_mhz, "maps": maps}
    except Exception:                                        # noqa: BLE001 - a map must never break the preview
        result = None
    try:
        es._heatmaps = result
    except Exception:                                        # noqa: BLE001
        pass
    return result
