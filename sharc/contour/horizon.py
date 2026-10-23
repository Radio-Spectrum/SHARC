"""Direction of the antenna gains from the P.452 horizon angles.

ITU-R P.452-18, Table 1: "Gt, Gr: antenna gain in the direction of the horizon along the great-circle interference
path". Horizon angles (P.452-18, Annex 1 Appendix 2, eqs. 143-151), in the form of the SHARC copy:

    theta_i  = 1000 arctan[ (h_i - h_ts) / (1000 d_i) - d_i / (2 a_e) ]      mrad; h in m, d in km; interior points
    theta_td = 1000 arctan[ (h_rs - h_ts) / (1000 d)  - d  / (2 a_e) ]       direction of the other antenna
    theta_t  = max(theta_i) when larger than theta_td (trans-horizon), else theta_td (line of sight)

and the same at the receiver side, with the distances counted from it. a_e = 6371 k50 km, k50 = 157 / (157 - dN); bare
terrain (the profile elevation, without the land cover), as in the engine.
"""
from __future__ import annotations

import numpy as np

MRAD_TO_DEG = 180.0 / np.pi / 1000.0
EARTH_RADIUS_KM = 6371.0


def effective_earth_radius_km(delta_n) -> float:
    """a_e [km] of P.452-18 eq. 5 with k50 = 157 / (157 - dN)."""
    return float(EARTH_RADIUS_KM * 157.0 / (157.0 - np.asarray(delta_n, float)))


def _angle_mrad(dh_m, d_km, ae_km):
    return 1000.0 * np.arctan(dh_m / (1000.0 * d_km) - d_km / (2.0 * ae_km))


def path_angles_deg(dist_km, elev_m, h_station_m, h_bs_m, ae_km):
    """(el_station, el_bs) [deg] of one profile from the station (index 0) to the base station (last point): the
    elevation of the arrival direction at the station (theta_r of P.452) and of the departure direction at the base
    station (theta_t). Heights are above ground, added to the elevation of the two ends of the profile."""
    d, h, ae = np.asarray(dist_km, float), np.asarray(elev_m, float), float(ae_km)
    total = float(d[-1])
    hr, hb = float(h[0]) + float(h_station_m), float(h[-1]) + float(h_bs_m)
    t_r = float(_angle_mrad(hb - hr, total, ae))
    t_b = float(_angle_mrad(hr - hb, total, ae))
    if d.size > 2:
        di, hi = d[1:-1], h[1:-1]
        t_r = max(t_r, float(np.max(_angle_mrad(hi - hr, di, ae))))
        t_b = max(t_b, float(np.max(_angle_mrad(hi - hb, total - di, ae))))
    return t_r * MRAD_TO_DEG, t_b * MRAD_TO_DEG
