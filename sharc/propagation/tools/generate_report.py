# -*- coding: utf-8 -*-
"""Generate diagnostic figures (PNG) for the statistical terrain/clutter report."""
import os
import io
import json
import base64

import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sharc.propagation.terrain_statistical import StatisticalTerrainModel


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    out = _out()
    params = json.load(open(os.path.join(out, "campinas_terrain_clutter_params.json")))
    s = np.load(os.path.join(out, "campinas_samples.npz"))
    val = json.load(open(os.path.join(out, "validation_results.json")))

    heights = s["heights"]; distances = s["distances"]; clutter = s["clutter"]
    tm = params["terrain_model"]; cm = params["clutter_model"]

    figs = {}

    # Fig 1: height & distance distributions with fits
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    hclip = heights[np.abs(heights) < 300]
    ax[0].hist(hclip, bins=80, density=True, color="#7fb3d5", edgecolor="white", linewidth=0.3)
    xx = np.linspace(-300, 300, 600)
    t = tm["height_student_t"]
    ax[0].plot(xx, stats.t.pdf(xx, df=t["nu"], loc=0, scale=t["sigma_m"]), "r", lw=2,
               label=f"Student-t (σ={t['sigma_m']:.1f} m, ν={t['nu']:.2f})")
    ax[0].set_xlabel("Peak/valley height deviation (m)"); ax[0].set_ylabel("PDF")
    ax[0].set_title("Terrain height deviations"); ax[0].legend(fontsize=8)

    dclip = distances[distances < 5]
    ax[1].hist(dclip, bins=60, density=True, color="#7fb3d5", edgecolor="white", linewidth=0.3)
    xd = np.linspace(0.01, 5, 600)
    dd = tm["distance_lognormal"]
    ax[1].plot(xd, stats.lognorm.pdf(xd, s=dd["sigma"], scale=np.exp(dd["mu"])), "r", lw=2,
               label=f"Lognormal (mean={dd['mean_km']:.2f} km)")
    ax[1].set_xlabel("Distance between extrema (km)"); ax[1].set_ylabel("PDF")
    ax[1].set_title("Distance between terrain extrema"); ax[1].legend(fontsize=8)
    figs["dist"] = _png(fig)

    # Fig 2: clutter proxy distribution
    fig, ax = plt.subplots(figsize=(6, 4))
    cclip = clutter[clutter < 80]
    ax.hist(cclip, bins=70, density=True, color="#82c596", edgecolor="white", linewidth=0.3)
    xc = np.linspace(0.1, 80, 600)
    cl = cm["clutter_lognormal"]
    ax.plot(xc, stats.lognorm.pdf(xc, s=cl["sigma"], scale=np.exp(cl["mu"])), "r", lw=2,
            label=f"Lognormal (median={cl['median_m']:.1f} m, mean={cl['mean_m']:.1f} m)")
    ax.set_xlabel("Representative clutter height (m)"); ax.set_ylabel("PDF")
    ax.set_title("Statistical clutter-over-terrain (proxy)"); ax.legend(fontsize=8)
    figs["clutter"] = _png(fig)

    # Fig 3: example real vs synthetic profile
    fig, ax = plt.subplots(figsize=(10, 3.6))
    d0 = s["radial_0_d"]; h0 = s["radial_0_h"]
    ax.plot(d0, h0 - h0.mean(), color="#34495e", lw=1.2, label="Real radial #0 (SRTM, detrended)")
    rng = np.random.RandomState(7)
    sd, sh = StatisticalTerrainModel().synthesize(50.0, 100, rng)
    ax.plot(sd, sh, color="#e67e22", lw=1.4, label="Synthetic statistical profile")
    ax.set_xlabel("Distance (km)"); ax.set_ylabel("Height vs mean (m)")
    ax.set_title("Real vs synthetic terrain profile (50 km)"); ax.legend(fontsize=8)
    figs["profile"] = _png(fig)

    # Fig 4: validation - loss vs distance
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    dk = [r["dist_km"] for r in val]
    ax.plot(dk, [r["flat"] for r in val], "k--o", label="Flat (smooth Earth)", lw=1.5)
    ax.plot(dk, [r["real"]["p50"] for r in val], "-s", color="#2e86c1", label="Real profiles p50")
    ax.fill_between(dk, [r["real"]["p5"] for r in val], [r["real"]["p95"] for r in val],
                    color="#2e86c1", alpha=0.18, label="Real p5–p95")
    ax.plot(dk, [r["stat"]["p50"] for r in val], "-^", color="#e67e22", label="Statistical p50")
    ax.fill_between(dk, [r["stat"]["p5"] for r in val], [r["stat"]["p95"] for r in val],
                    color="#e67e22", alpha=0.18, label="Statistical p5–p95")
    ax.set_xlabel("Distance (km)"); ax.set_ylabel("P.1812 basic transmission loss (dB)")
    ax.set_title("Validation: statistical model vs real Campinas profiles (3.5 GHz)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    figs["validation"] = _png(fig)

    with open(os.path.join(out, "report_figures.json"), "w") as fh:
        json.dump(figs, fh)
    print("figures generated:", list(figs.keys()))


if __name__ == "__main__":
    main()
