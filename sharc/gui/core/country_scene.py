"""Scene data for wide-area IMT networks (Macro_countries): sites, sectors, UEs, links and ground maps.

The flat-ENU helpers (`core.heatmap`, `core.preview_extras`) assume a network a few kilometres across. A country
spans thousands of kilometres, where the Earth is not flat, so everything here is computed on the sphere the
engine uses (ECEF, radius `EARTH_RADIUS_M`) and every direction is measured in the *local* ENU frame of the site:

    d     = r_receiver - r_site                     (ECEF vector, m)
    e,n,u = d . east, d . north, d . up             (site frame)
    dphi  = atan2(n, e) - azimuth_local             (engine azimuth: from east, counter-clockwise)
    elev  = atan2(u, hypot(e, n))
    PSD   = P_cond - ohmic - 10 log10(B) + G_sector(elev, dphi) - FSPL(|d|, f)

Same nominal model as the local maps (free space, no power control, no clutter): a planning footprint, not a
Monte Carlo result. The preview says so in its status line.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from sharc.satellite.ngso.constants import EARTH_RADIUS_M      # the engine's own sphere (6378.145 km), not 6371 km

GRID_N = 300
MAX_LINKS = 60
MAX_UES = 400
CHUNK = 1500                                   # receivers per block: keeps (chunk, n_bs, 3) small


def _basis(lat_deg, lon_deg):
    """Unit east, north, up vectors (ECEF) at spherical lat/lon, each of shape (N, 3)."""
    la, lo = np.radians(np.asarray(lat_deg, float)), np.radians(np.asarray(lon_deg, float))
    east = np.stack([-np.sin(lo), np.cos(lo), np.zeros_like(lo)], axis=-1)
    north = np.stack([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)], axis=-1)
    up = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    return east, north, up


def _ecef(lat_deg, lon_deg, radius):
    la, lo = np.radians(np.asarray(lat_deg, float)), np.radians(np.asarray(lon_deg, float))
    r = np.asarray(radius, float)
    return np.stack([r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)], axis=-1)


class Sites:
    """Base stations of the engine scene on the sphere, with their local ENU frames."""

    def __init__(self, es, geom=None):
        from core.engine_scene import station_lat_lon
        g = geom if geom is not None else es.bs.geom
        self.lat, self.lon = station_lat_lon(es, g)
        x, y, z = es.coordinate_system.enu2ecef(
            np.asarray(g.x_global, float), np.asarray(g.y_global, float), np.asarray(g.z_global, float))
        self.xyz = np.stack([np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)], axis=-1)
        self.height = np.linalg.norm(self.xyz, axis=-1) - EARTH_RADIUS_M     # above the sphere
        self.east, self.north, self.up = _basis(self.lat, self.lon)
        self.az = np.asarray(g.pointn_azim_local, float)                     # site frame, not the global one
        self.el = np.asarray(g.pointn_elev_local, float)


def _interp(data):
    from scipy.interpolate import RegularGridInterpolator
    return RegularGridInterpolator((data["elev"], data["dphi"]), data["gain"], bounds_error=False,
                                   fill_value=float(np.nanmin(data["gain"])))


def levels(es, sites: Sites, data, rx_lat, rx_lon, rx_h):
    """Nominal downlink at receivers on the sphere.

    `rx_h` is the height above the sphere [m] (scalar or one per receiver). Returns arrays of shape (n_rx, n_bs):
    psd [dBm/MHz], power [dBm], gain [dBi], fspl [dB], dist [m]."""
    p = es.params.imt
    f_mhz, bw_mhz = float(p.frequency), float(p.bandwidth)
    eirp_total = float(p.bs.conducted_power) - float(p.bs.ohmic_loss)
    eirp_psd = eirp_total - 10.0 * math.log10(bw_mhz)
    interp = _interp(data)
    rx = _ecef(rx_lat, rx_lon, EARTH_RADIUS_M + np.asarray(rx_h, float))
    outs: List[list] = [[] for _ in range(5)]
    for s in range(0, len(rx), CHUNK):
        d = rx[s:s + CHUNK, None, :] - sites.xyz[None, :, :]                  # (m, B, 3)
        e = np.einsum("mbk,bk->mb", d, sites.east)
        n = np.einsum("mbk,bk->mb", d, sites.north)
        u = np.einsum("mbk,bk->mb", d, sites.up)
        dist = np.maximum(np.linalg.norm(d, axis=-1), 1.0)
        elev = np.degrees(np.arctan2(u, np.hypot(e, n)))
        dphi = (np.degrees(np.arctan2(n, e)) - sites.az[None, :] + 180.0) % 360.0 - 180.0
        gain = interp(np.stack([elev.ravel(), dphi.ravel()], axis=-1)).reshape(dist.shape)
        fspl = 32.44 + 20.0 * np.log10(dist / 1000.0) + 20.0 * math.log10(f_mhz)
        for lst, arr in zip(outs, (eirp_psd + gain - fspl, eirp_total + gain - fspl, gain, fspl, dist)):
            lst.append(arr)
    return tuple(np.concatenate(o, axis=0) for o in outs)


def cell_radius_m(es, sites: Sites) -> float:
    """Radius drawn around each site: the engine's cell radius, or from the spacing when the sites come from a
    database (the radius parameter is inert there)."""
    topo = es.topology
    r = float(getattr(topo, "cell_radius", 0.0) or 0.0)
    if getattr(topo, "database", None) is not None or r <= 0.0:
        if len(sites.lat) > 1:
            xyz = _ecef(sites.lat, sites.lon, EARTH_RADIUS_M)
            dd = np.linalg.norm(xyz[:, None, :] - xyz[None, :, :], axis=-1)
            np.fill_diagonal(dd, np.inf)
            r = float(np.median(dd.min(axis=1))) / 2.0
        r = max(r, 500.0)
    return r


def _noise_psd(es) -> float:
    from core.heatmap import _noise_temperature_k
    return -114.0 + 10.0 * math.log10(_noise_temperature_k(es) / 290.0)


def _bounds(sites: Sites, radius_m: float):
    """lat/lon box around the sites with a margin of a few cell radii (at least 0.25 deg)."""
    m_lat = max(0.25, 0.08 * float(np.ptp(sites.lat)), 4.0 * radius_m / 111_320.0)
    m_lon = max(0.25, 0.08 * float(np.ptp(sites.lon)), 4.0 * radius_m / 111_320.0)
    return (float(sites.lat.min()) - m_lat, float(sites.lat.max()) + m_lat,
            float(sites.lon.min()) - m_lon, float(sites.lon.max()) + m_lon)


def heat(es, sites: Sites, data, radius_m: float, n: int = GRID_N) -> Optional[Dict[str, Any]]:
    """Ground maps in the format the preview already draws: {"west","east","south","north","n","maps":{...}}."""
    from core.heatmap import QUANTITIES
    south, north, west, east = _bounds(sites, radius_m)
    LON, LAT = np.meshgrid(np.linspace(west, east, n), np.linspace(south, north, n))   # row 0 = south
    psd, power, *_ = levels(es, sites, data, LAT.ravel(), LON.ravel(), 1.5)
    agg = 10.0 * np.log10(np.maximum((10.0 ** (psd / 10.0)).sum(axis=1), 1e-30)).reshape(LAT.shape)
    grids = {"psd": agg, "power": power.max(axis=1).reshape(LAT.shape), "inr": agg - _noise_psd(es)}
    maps = {}
    for name, g in grids.items():
        lo, hi = np.percentile(g, [2, 99.5])
        title, unit = QUANTITIES[name]
        maps[name] = {"values": np.round(g, 1).ravel().tolist(), "vmin": round(float(lo), 1),
                      "vmax": round(float(max(hi, lo + 1.0)), 1), "unit": unit, "title": title}
    p = es.params.imt
    return {"n": n, "west": west, "east": east, "south": south, "north": north,
            "freq_mhz": float(p.frequency), "bandwidth_mhz": float(p.bandwidth), "maps": maps}


def links(es, sites: Sites, data, max_links: int = MAX_LINKS) -> List[Dict[str, Any]]:
    """Serving-BS link (strongest nominal power) for a sample of the UEs, with the downlink budget."""
    from core.engine_scene import station_lat_lon
    p = es.params.imt
    ue = es.ue.geom
    pick = np.arange(0, int(ue.num_geometries), max(1, math.ceil(int(ue.num_geometries) / max_links)))
    ulat, ulon = station_lat_lon(es, ue)
    ulat, ulon = ulat[pick], ulon[pick]
    x, y, z = es.coordinate_system.enu2ecef(
        np.asarray(ue.x_global, float)[pick], np.asarray(ue.y_global, float)[pick],
        np.asarray(ue.z_global, float)[pick])
    u_h = np.linalg.norm(np.stack([np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)], axis=-1),
                         axis=-1) - EARTH_RADIUS_M
    g_ue = float(getattr(p.ue.antenna.array, "element_max_g", 0.0) or 0.0)
    body = float(getattr(p.ue, "body_loss", 0.0) or 0.0)
    noise = -174.0 + 10.0 * math.log10(float(p.bandwidth) * 1e6) + float(getattr(p.ue, "noise_figure", 0.0) or 0.0)
    tx = float(p.bs.conducted_power) - float(p.bs.ohmic_loss)
    _psd, power, gain, fspl, dist = levels(es, sites, data, ulat, ulon, u_h)
    # The engine places UE i around BS i // k, so that is its serving station (it is also the nearest one). The
    # strongest-power rule of the local preview would pick a distant site whenever the own sector is in a null.
    k = int(getattr(p.ue, "k", 0) or 0)
    serving = np.minimum(pick // k, power.shape[1] - 1) if k > 0 else power.argmax(axis=1)
    out = []
    for i, j in enumerate(serving):
        j = int(j)
        rx = float(power[i, j]) + g_ue - body
        out.append({
            "ue": int(pick[i]), "bs": j,
            "ue_lla": [float(ulat[i]), float(ulon[i]), float(u_h[i])],
            "bs_lla": [float(sites.lat[j]), float(sites.lon[j]), float(sites.height[j])],
            "dist_m": round(float(dist[i, j]), 1), "tx_power_dbm": round(tx, 1),
            "g_tx_dbi": round(float(gain[i, j]), 1), "fspl_db": round(float(fspl[i, j]), 1),
            "g_rx_dbi": round(g_ue, 1), "body_loss_db": round(body, 1),
            "rx_power_dbm": round(rx, 1), "noise_dbm": round(noise, 1), "snr_db": round(rx - noise, 1),
            "freq_mhz": float(p.frequency), "bandwidth_mhz": float(p.bandwidth),
        })
    return out


def build(es) -> Dict[str, Any]:
    """Everything the global preview needs for a Macro_countries network, from the engine scene.

    Each decoration is independent: one failing never removes the others, and the reason is returned in
    `problems` so the preview can tell the user instead of silently drawing less."""
    from core import gain_lobe
    from core.engine_scene import station_lat_lon
    sites = Sites(es)
    radius = cell_radius_m(es, sites)
    result: Dict[str, Any] = {"problems": [], "cell_radius_m": radius}
    result["sites"] = [
        {"lat_deg": float(la), "lon_deg": float(lo), "height_m": float(h),
         "azimuth_deg": float(a), "downtilt_deg": float(-e)}
        for la, lo, h, a, e in zip(sites.lat, sites.lon, sites.height, sites.az, sites.el)
    ]
    ue = es.ue.geom
    if ue.num_geometries:
        ulat, ulon = station_lat_lon(es, ue)
        step = max(1, math.ceil(len(ulat) / MAX_UES))
        result["ues"] = [{"lat_deg": float(a), "lon_deg": float(b)} for a, b in zip(ulat[::step], ulon[::step])]
        result["ue_total"] = int(len(ulat))
    try:
        data = gain_lobe.sample_bs_gain(es, local_frame=True)
    except Exception as exc:  # noqa: BLE001
        data = None
        result["problems"].append(f"antenna gain: {type(exc).__name__}: {exc}")
    if data is None:
        result["problems"].append("antenna gain: the engine antenna could not be sampled")
        return result
    try:
        result["lobe"] = gain_lobe._register(data, "lobe")
    except Exception as exc:  # noqa: BLE001
        result["problems"].append(f"antenna lobe: {type(exc).__name__}: {exc}")
    for key, fn in (("heat", lambda: heat(es, sites, data, radius)), ("links", lambda: links(es, sites, data))):
        try:
            result[key] = fn()
        except Exception as exc:  # noqa: BLE001
            result["problems"].append(f"{key}: {type(exc).__name__}: {exc}")
    return result


MAX_CONSTELLATION_UES = 600
MAX_CONSTELLATION_LINKS = 80


def constellation(es, geom=None, beam_radius_m: Optional[float] = None, with_ues: bool = True) -> Dict[str, Any]:
    """Satellites, beam footprints, UEs and serving links of a space-borne IMT network (MSS_DC).

    The engine's "base stations" are the beams: each sits at its satellite and points along (azimuth, elevation) in
    the global ENU frame of the scenario reference. The footprint centre is where that boresight ray meets the sphere:

        d = cos(el) (cos(az) E + sin(az) N) + sin(el) U          (engine azimuth: from east, counter-clockwise)
        t = -(p . d) - sqrt((p . d)^2 - (|p|^2 - R^2)),   ground = p + t d

    A beam that misses the Earth has no footprint and is left out (counted in `beams_missing`)."""
    from core.engine_scene import station_lat_lon
    sites = Sites(es, geom)
    n = len(sites.lat)
    radius = beam_radius_m
    if radius is None:
        r = np.asarray(getattr(es.topology, "cell_radius", 0.0), float).ravel()
        radius = float(r[0]) if r.size and r[0] > 0 else 25_000.0
    # Pointing is taken in the GLOBAL frame (ENU at the scenario reference): it is a physical direction for every
    # geometry, while the "local" angles of a satellite geometry are relative to its own nadir frame, not to ENU.
    g = geom if geom is not None else es.bs.geom
    ref_e, ref_n, ref_u = (v[0] for v in _basis([es.reference["lat_deg"]], [es.reference["lon_deg"]]))
    az, el = np.radians(np.asarray(g.pointn_azim_global, float)), np.radians(np.asarray(g.pointn_elev_global, float))
    d = (np.cos(el)[:, None] * (np.cos(az)[:, None] * ref_e + np.sin(az)[:, None] * ref_n)
         + np.sin(el)[:, None] * ref_u)
    b = np.einsum("ik,ik->i", sites.xyz, d)
    disc = b * b - (np.einsum("ik,ik->i", sites.xyz, sites.xyz) - EARTH_RADIUS_M ** 2)
    hit = disc >= 0.0
    t = -b - np.sqrt(np.where(hit, disc, 0.0))
    ground = sites.xyz + t[:, None] * d
    g_lat = np.degrees(np.arcsin(ground[:, 2] / np.linalg.norm(ground, axis=1)))
    g_lon = np.degrees(np.arctan2(ground[:, 1], ground[:, 0]))

    key = np.round(sites.xyz / 1000.0).astype(np.int64)                  # beams of one satellite share its position
    _u, first, sat_of = np.unique(key, axis=0, return_index=True, return_inverse=True)
    sat_of = np.asarray(sat_of).ravel()
    satellites = [{"lat_deg": float(sites.lat[i]), "lon_deg": float(sites.lon[i]),
                   "alt_m": float(sites.height[i]), "beams": int((sat_of == k).sum())}
                  for k, i in enumerate(first)]
    beams = [{"lat_deg": float(g_lat[i]), "lon_deg": float(g_lon[i]), "sat": int(sat_of[i])}
             for i in range(n) if hit[i]]

    ue = es.ue.geom
    ues, links = [], []
    if with_ues and ue.num_geometries:
        ulat, ulon = station_lat_lon(es, ue)
        step = max(1, math.ceil(len(ulat) / MAX_CONSTELLATION_UES))
        ues = [{"lat_deg": float(a), "lon_deg": float(c)} for a, c in zip(ulat[::step], ulon[::step])]
        ub = _basis(ulat, ulon)
        uxyz = _ecef(ulat, ulon, EARTH_RADIUS_M)
        lstep = max(1, math.ceil(len(ulat) / MAX_CONSTELLATION_LINKS))
        centres = _ecef(g_lat, g_lon, EARTH_RADIUS_M)
        beam_ids = np.flatnonzero(hit)
        for i in range(0, len(ulat), lstep):
            # The engine's UE order does not follow its beam order (checked: the UE sits in the footprint of the
            # nearest beam centre, not of beam i), so a UE is linked to the satellite of the nearest footprint.
            j = int(beam_ids[np.linalg.norm(centres[beam_ids] - uxyz[i], axis=1).argmin()])
            v = sites.xyz[j] - uxyz[i]
            e, nn, u = float(v @ ub[0][i]), float(v @ ub[1][i]), float(v @ ub[2][i])
            links.append({"ue_lat_deg": float(ulat[i]), "ue_lon_deg": float(ulon[i]), "sat": int(sat_of[j]),
                          "dist_km": round(float(np.linalg.norm(v)) / 1000.0, 1),
                          "elev_deg": round(math.degrees(math.atan2(u, math.hypot(e, nn))), 1)})
    return {"satellites": satellites, "beams": beams, "beams_missing": int(n - hit.sum()), "beam_radius_m": radius,
            "ues": ues, "ue_total": int(ue.num_geometries) if with_ues else 0, "links": links}
