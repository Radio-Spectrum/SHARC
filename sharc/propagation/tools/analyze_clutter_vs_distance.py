# -*- coding: utf-8 -*-
"""Analyze how the Campinas-SP clutter proxy varies with distance from the centre.

Re-extracts the sub-kilometre roughness (clutter proxy) from the 20 radial
profiles, keeping the distance from the centre, and characterizes the
urban -> suburban -> rural decay so a distance-dependent clutter model can be
fitted.
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

CLUTTER_SMOOTH_KM = 1.6
BIN_KM = 5.0
MAX_KM = 50.0


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def extract_clutter_with_distance(samples):
    """Return (distance_km, clutter_m) pairs from all radials (positive residuals)."""
    n_rad = sum(1 for k in samples.files if k.endswith("_d") and k.startswith("radial_"))
    ds, cs = [], []
    for i in range(n_rad):
        d = samples[f"radial_{i}_d"]
        h = samples[f"radial_{i}_h"]
        step = np.median(np.diff(d))
        win = max(int(round(CLUTTER_SMOOTH_KM / step)) | 1, 3)
        smooth = np.array([
            np.median(h[max(0, j - win // 2):min(len(h), j + win // 2 + 1)])
            for j in range(len(h))
        ])
        resid = h - smooth
        pos = resid > 0
        ds.extend(d[pos].tolist())
        cs.extend(resid[pos].tolist())
    return np.asarray(ds), np.asarray(cs)


def main():
    out = _out()
    samples = np.load(os.path.join(out, "campinas_samples.npz"))
    d, c = extract_clutter_with_distance(samples)
    c = np.maximum(c, 0.1)

    edges = np.arange(0, MAX_KM + BIN_KM, BIN_KM)
    centers, med, mean, mu_ln, sig_ln, ns = [], [], [], [], [], []
    print(f"{'dist bin (km)':>14} | {'n':>5} | {'median':>7} | {'mean':>7} | {'mu_ln':>7} | {'sig_ln':>7}")
    print("-" * 64)
    for k in range(len(edges) - 1):
        m = (d >= edges[k]) & (d < edges[k + 1])
        if m.sum() < 20:
            continue
        cc = c[m]
        s, _, scale = stats.lognorm.fit(cc, floc=0.0)
        centers.append(0.5 * (edges[k] + edges[k + 1]))
        med.append(float(np.median(cc)))
        mean.append(float(cc.mean()))
        mu_ln.append(float(np.log(scale)))
        sig_ln.append(float(s))
        ns.append(int(m.sum()))
        print(f"{edges[k]:5.0f}-{edges[k+1]:<5.0f}     | {m.sum():5d} | "
              f"{np.median(cc):7.2f} | {cc.mean():7.2f} | {np.log(scale):7.3f} | {s:7.3f}")

    centers = np.array(centers); mu_ln = np.array(mu_ln); sig_ln = np.array(sig_ln)

    # Fit mu_ln(d) = a + b*d  (linear decay of lognormal location with distance)
    A = np.vstack([np.ones_like(centers), centers]).T
    coef, *_ = np.linalg.lstsq(A, mu_ln, rcond=None)
    a, b = float(coef[0]), float(coef[1])
    sigma_const = float(np.mean(sig_ln))

    print("\nDistance-dependent lognormal fit:")
    print(f"  mu_ln(d) = {a:.4f} + ({b:.5f}) * d_km   [d in km]")
    print(f"  sigma_ln = {sigma_const:.4f} (approx constant)")
    print(f"  -> median clutter at center (d=0):   {np.exp(a):5.2f} m")
    print(f"  -> median clutter at 25 km:          {np.exp(a + b*25):5.2f} m")
    print(f"  -> median clutter at 50 km:          {np.exp(a + b*50):5.2f} m")

    result = {
        "model": "lognormal_distance_dependent",
        "mu_ln_intercept_a": a,
        "mu_ln_slope_b_per_km": b,
        "sigma_ln": sigma_const,
        "bins": [{"d_km": float(x), "median_m": float(mm), "mu_ln": float(u),
                  "sigma_ln": float(sg), "n": int(nn)}
                 for x, mm, u, sg, nn in zip(centers, med, mu_ln, sig_ln, ns)],
    }
    with open(os.path.join(out, "clutter_vs_distance.json"), "w") as fh:
        json.dump(result, fh, indent=2)

    # Plot
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.scatter(d, c, s=2, alpha=0.08, color="#82c596", label="clutter proxy (per point)")
    ax.plot(centers, med, "o-", color="#16a085", lw=2, label="median per 5-km bin")
    dd = np.linspace(0, MAX_KM, 200)
    ax.plot(dd, np.exp(a + b * dd), "r--", lw=2,
            label=f"fit median = exp({a:.2f} {b:+.4f}·d)")
    ax.set_xlabel("Distância ao centro de Campinas (km)")
    ax.set_ylabel("Altura de clutter (proxy, m)")
    ax.set_ylim(0, np.percentile(c, 99))
    ax.set_title("Clutter vs. distância — Campinas-SP (20 radiais)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "clutter_vs_distance_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)
    print(f"\nSaved -> {os.path.join(out, 'clutter_vs_distance.json')}")


if __name__ == "__main__":
    main()
