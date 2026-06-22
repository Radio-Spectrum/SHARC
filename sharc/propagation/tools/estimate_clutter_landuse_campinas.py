# -*- coding: utf-8 -*-
"""Estimate a distance-dependent statistical clutter model from REAL land use.

Samples ESA WorldCover (10 m, real land cover) along 20 radials of 50 km from
the centre of Campinas-SP, maps each point to a representative clutter height,
and fits a distance-dependent lognormal:

    clutter_height(d) = exp( N( mu_ln(d), sigma_ln ) ),  mu_ln(d) = a + b * d

so the resulting statistical model reproduces the real urban -> suburban ->
rural decay of clutter while remaining Monte-Carlo friendly (no land-cover data
needed at simulation runtime).

Run: python -m sharc.propagation.tools.estimate_clutter_landuse_campinas
"""
import os
import io
import json
import base64

import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Geod

from sharc.propagation.land_use_clutter import (
    WorldCoverClutter, WORLDCOVER_CLASS_NAMES,
)

START_LAT = -22.9048878490284
START_LON = -47.06032221390534
N_RADIALS = 20
RADIAL_LENGTH_KM = 50.0
STEP_KM = 0.1
BIN_KM = 5.0
MIN_H = 0.5     # floor (m) so lognormal is defined


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def main():
    out = _out()
    provider = WorldCoverClutter(os.path.join(out, "worldcover"), auto_download=True)
    geod = Geod(ellps="WGS84")
    n = int(round(RADIAL_LENGTH_KM / STEP_KM)) + 1

    all_d, all_h, all_c = [], [], []
    for k in range(N_RADIALS):
        az = 360.0 * k / N_RADIALS
        pts = geod.fwd(
            np.full(n, START_LON), np.full(n, START_LAT),
            np.full(n, az), np.linspace(0, RADIAL_LENGTH_KM * 1000.0, n),
        )
        lons, lats = pts[0], pts[1]
        h, c = provider.sample_heights(lats, lons)
        d = np.linspace(0, RADIAL_LENGTH_KM, n)
        all_d.append(d); all_h.append(h); all_c.append(c)

    d = np.concatenate(all_d)
    h = np.concatenate(all_h)
    c = np.concatenate(all_c)
    print(f"Sampled {d.size} WorldCover points along {N_RADIALS} radials.")

    # Class composition by distance band
    edges = np.arange(0, RADIAL_LENGTH_KM + BIN_KM, BIN_KM)
    print(f"\n{'dist (km)':>10} | {'mean h':>6} | {'median':>6} | dominant land cover")
    print("-" * 70)
    centers, mean_h, med_h = [], [], []
    for i in range(len(edges) - 1):
        m = (d >= edges[i]) & (d < edges[i + 1])
        if m.sum() < 20:
            continue
        cc = c[m]
        vals, counts = np.unique(cc, return_counts=True)
        order = np.argsort(-counts)[:3]
        dom = ", ".join(f"{WORLDCOVER_CLASS_NAMES.get(int(vals[j]),'?')} "
                        f"{100*counts[j]/cc.size:.0f}%" for j in order)
        centers.append(0.5 * (edges[i] + edges[i + 1]))
        mean_h.append(float(h[m].mean()))
        med_h.append(float(np.median(h[m])))
        print(f"{edges[i]:4.0f}-{edges[i+1]:<4.0f} | {h[m].mean():6.2f} | "
              f"{np.median(h[m]):6.2f} | {dom}")

    # Deterministic trend f(d) = C + (A - C)*exp(-d/d0) fitted to the per-bin
    # MEAN clutter height; multiplicative lognormal spread sigma from the
    # log-residuals around the trend (Section: trend-then-spread approach).
    from scipy.optimize import curve_fit

    def trend(dist, A, C, d0):
        return C + (A - C) * np.exp(-dist / d0)

    (A, C, d0), _ = curve_fit(trend, np.array(centers), np.array(mean_h),
                              p0=[18.0, 7.0, 8.0], maxfev=10000)
    yhat = trend(np.array(centers), A, C, d0)
    r2 = float(1 - np.sum((np.array(mean_h) - yhat) ** 2) /
               np.sum((np.array(mean_h) - np.mean(mean_h)) ** 2))
    ft = trend(d, A, C, d0)
    sigma_ln = float(np.std(np.log(np.maximum(h, MIN_H)) - np.log(np.maximum(ft, MIN_H))))
    A, C, d0 = float(A), float(C), float(d0)

    print("\nDistance-dependent clutter model (trend fitted to the MEAN, real land use):")
    print(f"  f(d) = {C:.2f} + ({A - C:.2f}) * exp(-d / {d0:.2f})   [R^2 = {r2:.3f}]")
    print(f"  sigma_ln = {sigma_ln:.4f}  (multiplicative lognormal spread)")
    print(f"  -> mean clutter @0 km : {trend(0, A, C, d0):5.2f} m")
    print(f"  -> mean clutter @5 km : {trend(5, A, C, d0):5.2f} m")
    print(f"  -> mean clutter @25km : {trend(25, A, C, d0):5.2f} m")
    print(f"  -> mean clutter @50km : {trend(50, A, C, d0):5.2f} m")

    result = {
        "source": "ESA WorldCover v200 2021 (real land use), Campinas-SP, 20x50 km radials",
        "model": "exponential_floor_trend_times_lognormal (target=mean)",
        "stat_clutter_trend_A": A,
        "stat_clutter_trend_C": C,
        "stat_clutter_trend_d0_km": d0,
        "stat_clutter_sigma": sigma_ln,
        "stat_clutter_target": "mean",
        "trend_r2": r2,
        "mean_height_m": {"d0": trend(0, A, C, d0), "d5": trend(5, A, C, d0),
                          "d25": trend(25, A, C, d0), "d50": trend(50, A, C, d0)},
    }
    with open(os.path.join(out, "clutter_landuse_params.json"), "w") as fh:
        json.dump(result, fh, indent=2)

    # Plot
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.scatter(d, h, s=2, alpha=0.05, color="#9b8cc4", label="clutter height (per point)")
    ax.plot(centers, mean_h, "o-", color="#6c3fa0", lw=2, label="mean per 5-km bin")
    dd = np.linspace(0, RADIAL_LENGTH_KM, 200)
    ax.plot(dd, trend(dd, A, C, d0), "r--", lw=2,
            label=f"fit mean = {C:.1f}+{A-C:.1f}·exp(-d/{d0:.1f})")
    ax.set_xlabel("Distância ao centro de Campinas (km)")
    ax.set_ylabel("Altura de clutter (uso do solo, m)")
    ax.set_title("Clutter por uso do solo real (ESA WorldCover) vs. distância")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "clutter_landuse_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)
    print(f"\nSaved -> {os.path.join(out, 'clutter_landuse_params.json')}")


if __name__ == "__main__":
    main()
