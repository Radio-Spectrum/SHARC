"""Extra data for the 3D preview, all derived from the engine scene: UE links with a link budget, the PSD/CDF
plots shown over the scene, and a short sequence of snapshots (UE redraws) to animate.

Link budget of a nominal downlink (free space, sector array gain from the engine, no power control):

    P_rx = P_cond - ohmic_loss + G_bs(toward UE) - FSPL + G_ue - body_loss          [dBm]
    N    = -174 + 10 log10(B_hz) + NF_ue                                            [dBm]
    SNR  = P_rx - N                                                                  [dB]
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

MAX_LINKS = 60
N_SNAPSHOTS = 12


def _budget(es, data, ux, uy, uz):
    """Serving BS (strongest nominal power) and the downlink budget for UEs at (ux, uy, uz)."""
    from core import heatmap
    p = es.params.imt
    rx_z = float(np.mean(uz))
    _psd, power, gain, fspl, dist = heatmap.levels(es, data, ux, uy, rx_z)
    serving = power.argmax(axis=1)
    idx = np.arange(len(ux))
    g_ue = float(getattr(p.ue.antenna.array, "element_max_g", 0.0) or 0.0)
    body = float(getattr(p.ue, "body_loss", 0.0) or 0.0)
    nf = float(getattr(p.ue, "noise_figure", 0.0) or 0.0)
    noise = -174.0 + 10.0 * math.log10(float(p.bandwidth) * 1e6) + nf
    p_rx = power[idx, serving] + g_ue - body
    return {"serving": serving, "dist": dist[idx, serving], "g_tx": gain[idx, serving], "fspl": fspl[idx, serving],
            "p_rx": p_rx, "snr": p_rx - noise, "g_ue": g_ue, "body": body, "noise": noise,
            "tx_dbm": float(p.bs.conducted_power) - float(p.bs.ohmic_loss)}


def links(es, max_links: int = MAX_LINKS) -> Optional[List[Dict[str, Any]]]:
    """Serving-BS link (strongest nominal power) for a sample of the UEs, with its link budget."""
    cached = getattr(es, "_links", "unset")
    if cached != "unset":
        return cached
    result = None
    try:
        from core import gain_lobe
        data = gain_lobe.sample_bs_gain(es)
        ue, bs, p = es.ue.geom, es.bs.geom, es.params.imt
        n = int(ue.num_geometries)
        pick = np.arange(0, n, max(1, math.ceil(n / max_links)))
        ux, uy, uz = (np.asarray(ue.x_global, float)[pick], np.asarray(ue.y_global, float)[pick],
                      np.asarray(ue.z_global, float)[pick])
        b = _budget(es, data, ux, uy, uz)
        bx, by, bz = (np.asarray(bs.x_global, float), np.asarray(bs.y_global, float), np.asarray(bs.z_global, float))
        result = []
        for i, k in enumerate(pick):
            j = int(b["serving"][i])
            result.append({
                "ue": int(k), "bs": j,
                "ue_xyz": [float(ux[i]), float(uy[i]), float(uz[i])],
                "bs_xyz": [float(bx[j]), float(by[j]), float(bz[j])],
                "dist_m": round(float(b["dist"][i]), 1), "tx_power_dbm": round(b["tx_dbm"], 1),
                "g_tx_dbi": round(float(b["g_tx"][i]), 1), "fspl_db": round(float(b["fspl"][i]), 1),
                "g_rx_dbi": round(b["g_ue"], 1), "body_loss_db": round(b["body"], 1),
                "rx_power_dbm": round(float(b["p_rx"][i]), 1), "noise_dbm": round(b["noise"], 1),
                "snr_db": round(float(b["snr"][i]), 1),
                "freq_mhz": float(p.frequency), "bandwidth_mhz": float(p.bandwidth),
            })
    except Exception:                                        # noqa: BLE001 - decoration only
        result = None
    try:
        es._links = result
    except Exception:                                        # noqa: BLE001
        pass
    return result


def plots(es) -> Optional[Dict[str, Any]]:
    """Data for the HUD plots: the IMT PSD against the victim band, and the CDF of I/N over the ground map."""
    cached = getattr(es, "_plots", "unset")
    if cached != "unset":
        return cached
    result = None
    try:
        from core import heatmap
        p = es.params.imt
        f, bw = float(p.frequency), float(p.bandwidth)
        psd_level = float(p.bs.conducted_power) - float(p.bs.ohmic_loss) - 10.0 * math.log10(bw)
        victim = None
        try:
            system = str(es.params.general.system).lower()
            sp = getattr(es.params, system)
            vf, vb = float(sp.frequency), float(sp.bandwidth)
            victim = {"freq_mhz": vf, "bandwidth_mhz": vb, "name": str(es.params.general.system)}
        except Exception:                                    # noqa: BLE001 - not every system exposes both
            victim = None
        heat = heatmap.compute(es)
        cdf = None
        if heat:
            vals = np.sort(np.asarray(heat["maps"]["inr"]["values"], dtype=float))
            q = np.linspace(0.0, 1.0, 60)
            cdf = {"x": [round(float(v), 1) for v in np.quantile(vals, q)], "p": [round(float(v), 3) for v in q],
                   "unit": "dB", "label": "I/N at ground receivers (isotropic, UE height)"}
        result = {"imt": {"freq_mhz": f, "bandwidth_mhz": bw, "psd_dbm_mhz": round(psd_level, 1)},
                  "victim": victim, "cdf": cdf}
    except Exception:                                        # noqa: BLE001
        result = None
    try:
        es._plots = result
    except Exception:                                        # noqa: BLE001
        pass
    return result


def snapshots(es, k: int = N_SNAPSHOTS) -> Optional[List[Dict[str, List[float]]]]:
    """UE positions of `k` consecutive snapshots (the engine redraws the UEs every snapshot, same topology)."""
    cached = getattr(es, "_snapshots", "unset")
    if cached != "unset":
        return cached
    result = None
    try:
        from sharc.station_factory import StationFactory
        seed = int(es.params.general.seed) if str(es.params.general.seed).isdigit() else 42
        from core import gain_lobe
        data = gain_lobe.sample_bs_gain(es)
        result = []
        for i in range(k):
            rng = np.random.RandomState(seed + 1000 + i)
            ue = StationFactory.generate_imt_ue(es.params.imt, es.params.imt.ue.antenna.array, es.topology, rng)
            x, y, z = (np.asarray(ue.geom.x_global, float), np.asarray(ue.geom.y_global, float),
                       np.asarray(ue.geom.z_global, float))
            b = _budget(es, data, x, y, z)
            result.append({"x": [round(float(v), 1) for v in x], "y": [round(float(v), 1) for v in y],
                           "bs": [int(v) for v in b["serving"]], "snr": [round(float(v), 1) for v in b["snr"]]})
    except Exception:                                        # noqa: BLE001
        result = None
    try:
        es._snapshots = result
    except Exception:                                        # noqa: BLE001
        pass
    return result
