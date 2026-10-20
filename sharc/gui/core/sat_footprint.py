"""Satellite footprint maps and the interference the IMT network puts into the satellite.

For the SINGLE_SPACE_STATION system the engine antenna is evaluated on the ground around the sub-satellite point:

  * ``sat_gain``: antenna gain toward each ground point [dBi] (boresight at nadir), with the 3 dB beamwidth.
  * ``sat_psd``: PSD the satellite puts on the ground [dBm/MHz] = tx PSD + G_sat - FSPL(slant) - polarization loss
    (isotropic receiver), when the system defines a transmit PSD.

and, for interference assessment, the *aggregate IMT interference at the satellite receiver*:

    I = sum over base stations of  EIRP_psd + G_bs(toward satellite) - FSPL(slant to satellite) + G_sat(toward the BS)

reported as PSD [dBm/MHz] and I/N against the satellite's noise temperature. Co-channel, free space, nominal full
power: a planning bound, not a Monte Carlo result.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np

EARTH_RADIUS = 6_371_000.0
GRID_N = 80


def _unit_ll(lat_deg, lon_deg):
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def _fspl(dist_m, f_mhz):
    return 32.44 + 20.0 * np.log10(np.maximum(dist_m, 1.0) / 1000.0) + 20.0 * math.log10(f_mhz)


def _beamwidth_deg(antenna, peak: float) -> float:
    """Full 3 dB beamwidth from the engine pattern (first off-axis angle that is 3 dB down, times two)."""
    from core import antenna_service
    ang = np.linspace(0.0, 10.0, 2001)
    g = np.asarray(antenna_service.gain_at(antenna, ang), dtype=float)
    below = np.nonzero(g <= peak - 3.0)[0]
    return float(2.0 * ang[below[0]]) if len(below) else 20.0


def compute(es, n: int = GRID_N) -> Optional[Dict[str, Any]]:
    cached = getattr(es, "_sat_footprint", "unset")
    if cached != "unset":
        return cached
    result = None
    try:
        if str(es.params.general.system).upper() != "SINGLE_SPACE_STATION" or es.system is None:
            raise ValueError("no space station")
        from core import antenna_service, gain_lobe, heatmap

        ss = es.params.single_space_station
        lat_s = float(ss.geometry.location.fixed.lat_deg)
        lon_s = float(ss.geometry.location.fixed.long_deg)
        alt = float(ss.geometry.altitude)
        f_sat = float(ss.frequency)
        antenna = es.system.antenna[0]
        sat_u = _unit_ll(lat_s, lon_s)
        sat_pos = sat_u * (EARTH_RADIUS + alt)

        def off_axis(points):
            v = points - sat_pos
            nadir = -sat_u
            cosang = (v @ nadir) / np.linalg.norm(v, axis=-1)
            return np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0))), np.linalg.norm(v, axis=-1)

        peak = float(np.nanmax(antenna_service.gain_at(antenna, np.linspace(0.0, 1.0, 21))))
        bw = _beamwidth_deg(antenna, peak)
        theta_ext = float(np.clip(1.4 * bw, 0.3, math.degrees(math.asin(EARTH_RADIUS / (EARTH_RADIUS + alt))) * 0.98))
        t = math.radians(theta_ext)
        gamma = math.degrees(math.asin(min(1.0, (EARTH_RADIUS + alt) * math.sin(t) / EARTH_RADIUS)) - t)  # central angle
        dlat = gamma
        dlon = gamma / max(math.cos(math.radians(lat_s)), 0.05)
        lats = np.linspace(lat_s - dlat, lat_s + dlat, n)
        lons = np.linspace(lon_s - dlon, lon_s + dlon, n)
        LON, LAT = np.meshgrid(lons, lats)                                   # row 0 = south
        ground = _unit_ll(LAT.ravel(), LON.ravel()) * EARTH_RADIUS
        theta, dist = off_axis(ground)
        gain = np.asarray(antenna_service.gain_at(antenna, theta), dtype=float)

        maps = {}
        lo = max(float(peak - 30.0), float(np.nanmin(gain)))
        maps["sat_gain"] = {"values": np.round(gain, 1).tolist(), "vmin": round(lo, 1), "vmax": round(peak, 1),
                            "unit": "dBi", "title": "Satellite antenna gain (footprint)"}
        tx = getattr(ss, "tx_power_density", None)
        if tx is not None:
            pol = float(getattr(ss, "polarization_loss", 0.0) or 0.0)
            psd = float(tx) + 90.0 + gain - _fspl(dist, f_sat) - pol                     # dBW/Hz -> dBm/MHz
            hi = float(np.nanmax(psd))
            maps["sat_psd"] = {"values": np.round(psd, 1).tolist(), "vmin": round(hi - 30.0, 1), "vmax": round(hi, 1),
                               "unit": "dBm/MHz", "title": "Satellite PSD on the ground"}

        # aggregate IMT interference at the satellite receiver
        data = gain_lobe.sample_bs_gain(es)
        cs, geom, p = es.coordinate_system, es.bs.geom, es.params.imt
        bx, by, bz = (np.asarray(geom.x_global, float), np.asarray(geom.y_global, float), np.asarray(geom.z_global, float))
        az = np.asarray(geom.pointn_azim_global, float)
        ex, ey, ez = cs.enu2ecef(bx, by, bz)
        bs_ecef = np.stack([np.asarray(ex, float), np.asarray(ey, float), np.asarray(ez, float)], axis=-1)
        sat_enu = np.asarray(cs.ecef2enu(*sat_pos.reshape(3, 1))).reshape(3)
        dx, dy, dz = sat_enu[0] - bx, sat_enu[1] - by, sat_enu[2] - bz
        hd = np.hypot(dx, dy)
        dphi = (np.degrees(np.arctan2(dy, dx)) - az + 180.0) % 360.0 - 180.0
        elev = np.degrees(np.arctan2(dz, np.maximum(hd, 1e-3)))
        g_bs = heatmap._interp(data)(np.stack([elev, dphi], axis=-1))
        th_bs, slant = off_axis(bs_ecef)
        g_sat = np.asarray(antenna_service.gain_at(antenna, th_bs), dtype=float)
        eirp_psd = float(p.bs.conducted_power) - float(p.bs.ohmic_loss) - 10.0 * math.log10(float(p.bandwidth))
        pol = float(getattr(ss, "polarization_loss", 0.0) or 0.0)
        per_bs = eirp_psd + g_bs - _fspl(slant, float(p.frequency)) + g_sat - pol
        i_psd = float(10.0 * np.log10(np.sum(10.0 ** (per_bs / 10.0))))
        t_noise = float(getattr(ss, "noise_temperature", None) or 290.0)
        noise_psd = -114.0 + 10.0 * math.log10(t_noise / 290.0)
        summary = {"altitude_km": round(alt / 1000.0, 1), "peak_gain_dbi": round(peak, 1), "beamwidth_deg": round(bw, 2),
                   "freq_mhz": f_sat, "imt_freq_mhz": float(p.frequency), "n_bs": int(len(bx)),
                   "imt_psd_at_sat_dbm_mhz": round(i_psd, 1), "noise_psd_dbm_mhz": round(noise_psd, 1),
                   "inr_db": round(i_psd - noise_psd, 1), "gain_toward_network_dbi": round(float(g_sat.mean()), 1)}
        result = {"n": n, "west": float(lons[0]), "east": float(lons[-1]), "south": float(lats[0]),
                  "north": float(lats[-1]), "maps": maps, "summary": summary,
                  "contrib": [round(float(v), 1) for v in per_bs],
                  "victim_lla": {"lat_deg": lat_s, "lon_deg": lon_s, "alt_m": alt}}
    except Exception:                                        # noqa: BLE001 - decoration only
        result = None
    try:
        es._sat_footprint = result
    except Exception:                                        # noqa: BLE001
        pass
    return result
