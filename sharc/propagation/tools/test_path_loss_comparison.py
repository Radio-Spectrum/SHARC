# -*- coding: utf-8 -*-
"""Compare median path loss (PL50) of several models along a Campinas-SP path.

Scenario
--------
Tx: 20 m height, 6 GHz, isotropic, EIRP 30 dBm, at (-22.931034, -47.096705)
Rx: isotropic, 10 m above ground, at (-22.971095, -47.143359)

The receiver is moved along the great-circle path Tx->Rx, sampled every 100 m,
and PL50 is computed for:
  * Free space (FSPL)
  * Okumura-Hata / COST-231 (extrapolated to 6 GHz)
  * ITU-R P.452 (smooth earth)
  * ITU-R P.1812 (smooth earth)
  * ITU-R P.1812 (specific terrain, SRTM, no clutter)
  * ITU-R P.1812 (statistical terrain, no clutter)   -> median over realizations
  * ITU-R P.1812 (statistical terrain, with clutter) -> median over realizations

Note: path loss is independent of EIRP/antenna gains; EIRP is scenario context.
P.452/P.1812 are evaluated at p = 50 % of time (median); clutter disabled unless
stated. 6 GHz is at/above the nominal upper bound of these models (used here for
comparison as requested).

Run:  python -m sharc.propagation.tools.test_path_loss_comparison
"""
import os
import io
import sys
import json
import base64
import argparse

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Geod

from sharc.parameters.parameters_p452 import ParametersP452
from sharc.parameters.parameters_p1812 import ParametersP1812
from sharc.propagation.propagation_clear_air_452 import PropagationClearAir
from sharc.propagation.propagation_p1812 import PropagationP1812
from sharc.propagation.terrain_srtm import SRTMReader

# --- Scenario (defaults; overridable via CLI) -------------------------------
TX_LAT, TX_LON = -22.931033961157787, -47.09670475303627
RX_LAT, RX_LON = -22.97109534026452, -47.143358503534564
FREQ_MHZ = 6000.0
FREQ_GHZ = FREQ_MHZ / 1000.0
HTX_M = 20.0
HRX_M = 10.0
EIRP_DBM = 30.0
STEP_M = 100.0
N_MC = 150               # Monte-Carlo realizations for the statistical terrain
PROFILE_LEN = 100        # points per P.1812 profile


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def fspl(d_km):
    """Free-space path loss (dB)."""
    d_km = np.maximum(d_km, 1e-4)
    return 32.45 + 20 * np.log10(d_km) + 20 * np.log10(FREQ_MHZ)


def hata_cost231(d_km, hb=HTX_M, hm=HRX_M, f=FREQ_MHZ, big_city=False):
    """COST-231 Hata (urban), extrapolated to 6 GHz. Valid range is 1500-2000 MHz."""
    d_km = np.maximum(d_km, 1e-3)
    logf = np.log10(f)
    a_hm = (1.1 * logf - 0.7) * hm - (1.56 * logf - 0.8)
    C = 3.0 if big_city else 0.0
    return (46.3 + 33.9 * logf - 13.82 * np.log10(hb) - a_hm
            + (44.9 - 6.55 * np.log10(hb)) * np.log10(d_km) + C)


def _p452_prop(clutter=False):
    par = ParametersP452()
    par.percentage_p = 50.0          # PL50
    par.clutter_loss = clutter       # add ITU-R P.2108 statistical clutter if True
    par.clutter_type = "one_end"
    par.Hte = HTX_M
    par.Hre = HRX_M
    return PropagationClearAir(np.random.RandomState(1), par)


def _p1812_prop(terrain_profile, clutter_mode, clutter_statistical=False, seed=1):
    par = ParametersP1812()
    par.percentage_p = 50.0
    par.terrain_profile = terrain_profile
    par.clutter_mode = clutter_mode
    par.clutter_statistical = clutter_statistical
    par.Hte = HTX_M
    par.Hre = HRX_M
    par.profile_resolution = PROFILE_LEN
    par.srtm_directory = os.path.join(_out(), "srtm")
    par.srtm_auto_download = True
    return PropagationP1812(np.random.RandomState(seed), par)


def _loss_low(prop, d_km, profile=None, center_dist=None):
    """Single-link low-level get_loss call (km, GHz).

    Optionally stash a terrain profile and the (Tx, Rx) distances from the
    cluster centre (km) used by the distance-dependent statistical clutter.
    """
    if profile is not None:
        prop._terrain_profiles = [profile]
    if center_dist is not None:
        prop._link_center_dist = [center_dist]
    try:
        d = np.array([[d_km]])
        f = FREQ_GHZ * np.ones((1, 1))
        ind = np.zeros((1, 1), dtype=bool)
        el = np.zeros((1, 1))
        return float(np.ravel(prop.get_loss(
            d, f, ind, el, np.array([0.0]), np.array([0.0])))[0])
    finally:
        if profile is not None:
            prop._terrain_profiles = None
        if center_dist is not None:
            prop._link_center_dist = None


def main(argv=None):
    ap = argparse.ArgumentParser(description="PL50 model comparison along a path.")
    ap.add_argument("--tx-lat", type=float, default=TX_LAT)
    ap.add_argument("--tx-lon", type=float, default=TX_LON)
    ap.add_argument("--rx-lat", type=float, default=RX_LAT)
    ap.add_argument("--rx-lon", type=float, default=RX_LON)
    ap.add_argument("--tag", default="", help="suffix for output files and title")
    args = ap.parse_args(argv)
    tx_lat, tx_lon = args.tx_lat, args.tx_lon
    rx_lat, rx_lon = args.rx_lat, args.rx_lon
    tag = ("_" + args.tag) if args.tag else ""
    title_tag = f" [{args.tag}]" if args.tag else ""

    out = _out()
    geod = Geod(ellps="WGS84")
    _, _, total_m = geod.inv(tx_lon, tx_lat, rx_lon, rx_lat)
    n = int(round(total_m / STEP_M)) + 1
    pts = geod.npts(tx_lon, tx_lat, rx_lon, rx_lat, n - 2)
    lons = np.array([tx_lon] + [p[0] for p in pts] + [rx_lon])
    lats = np.array([tx_lat] + [p[1] for p in pts] + [rx_lat])
    d_km = np.linspace(0.0, total_m / 1000.0, n)
    print(f"Path Tx->Rx: {total_m/1000:.2f} km, {n} samples @ {STEP_M:.0f} m, f={FREQ_MHZ:.0f} MHz")

    # SRTM master profile (Tx -> each sample point) using cached tiles
    reader = SRTMReader(os.path.join(out, "srtm"), auto_download=True)

    p452 = _p452_prop(clutter=False)
    p452_clut = _p452_prop(clutter=True)
    p1812_flat = _p1812_prop("flat", "none")
    p1812_srtm = _p1812_prop("srtm", "none")
    p1812_stat = _p1812_prop("statistical", "none")
    p1812_statc = _p1812_prop("statistical", "terrain", clutter_statistical=True)

    res = {k: np.full(n, np.nan) for k in
           ["fspl", "hata", "p452", "p452_clut", "p1812_flat", "p1812_srtm",
            "p1812_stat", "p1812_statc"]}

    res["fspl"] = fspl(d_km)
    res["hata"] = hata_cost231(d_km)

    for k in range(1, n):
        dk = d_km[k]
        res["p452"][k] = _loss_low(p452, dk)
        res["p452_clut"][k] = _loss_low(p452_clut, dk)
        res["p1812_flat"][k] = _loss_low(p1812_flat, dk)

        # Specific terrain: real SRTM profile Tx -> point k
        prof = reader.path_profile(tx_lat, tx_lon, lats[k], lons[k], PROFILE_LEN)
        res["p1812_srtm"][k] = _loss_low(p1812_srtm, dk, profile=prof)

        # Statistical terrain: PL50 = median over MC realizations. For the
        # distance-dependent clutter, the Tx sits at the cluster centre (d=0)
        # and the Rx is at the along-path distance dk (clutter decays with dk).
        mc, mcc = [], []
        for s in range(N_MC):
            p1812_stat.random_number_gen = np.random.RandomState(1000 * k + s)
            mc.append(_loss_low(p1812_stat, dk))
            p1812_statc.random_number_gen = np.random.RandomState(7000 * k + s)
            mcc.append(_loss_low(p1812_statc, dk, center_dist=(0.0, dk)))
        res["p1812_stat"][k] = np.median(mc)
        res["p1812_statc"][k] = np.median(mcc)

    # ---- Plot --------------------------------------------------------------
    styles = [
        ("fspl",        "Espaço livre (FSPL)",                         "#7f8c8d", "--"),
        ("hata",        "Okumura-Hata / COST-231 (extrap. 6 GHz)",     "#9b59b6", "--"),
        ("p452",        "ITU-R P.452 (smooth earth)",                  "#16a085", "-"),
        ("p452_clut",   "ITU-R P.452 + clutter P.2108",                "#16a085", ":"),
        ("p1812_flat",  "ITU-R P.1812 (smooth earth)",                 "#2980b9", "-"),
        ("p1812_srtm",  "ITU-R P.1812 (terreno específico SRTM)",      "#27ae60", "-"),
        ("p1812_stat",  "ITU-R P.1812 (terreno estatístico)",          "#e67e22", "-"),
        ("p1812_statc", "ITU-R P.1812 (terreno estat. + clutter)",     "#c0392b", "-"),
    ]
    fig, ax = plt.subplots(figsize=(10, 6))
    for key, lbl, col, ls in styles:
        ax.plot(d_km, res[key], ls, color=col, lw=1.8, label=lbl)
    ax.set_xlabel("Distância Tx-Rx ao longo do percurso (km)")
    ax.set_ylabel("Perda de propagação mediana PL50 (dB)")
    ax.set_title(f"PL50 — Campinas-SP{title_tag}, {FREQ_MHZ:.0f} MHz, "
                 f"hTx={HTX_M:.0f} m, hRx={HRX_M:.0f} m")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()

    png = os.path.join(out, f"path_loss_comparison{tag}.png")
    fig.savefig(png, dpi=120)
    print(f"figure -> {png}")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, f"path_loss_comparison{tag}_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)

    # Endpoint summary (Rx position)
    print(f"\nPL50 at Rx (d={d_km[-1]:.2f} km):")
    for key, lbl, _, _ in styles:
        print(f"  {lbl:<48} {res[key][-1]:7.1f} dB   (Prx = {EIRP_DBM-res[key][-1]:7.1f} dBm)")

    np.savez(os.path.join(out, f"path_loss_comparison{tag}.npz"), d_km=d_km, **res)


if __name__ == "__main__":
    main(sys.argv[1:])
