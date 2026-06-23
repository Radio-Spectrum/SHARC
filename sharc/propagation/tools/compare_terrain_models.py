# -*- coding: utf-8 -*-
"""Compare the statistical terrain model of 5D/1059 (Brazilian borders) with the
fit obtained from Campinas-SP data (same methodology)."""
import os
import io
import json
import base64

import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 5D/1059 published parameters (Brazilian borders)
BORDER = {"h_sigma": 24.25, "h_nu": 1.525, "d_mu": 1.06, "d_sigma": 0.84}
# Campinas-SP fit (this work), 1 km sampling (terrain-scale extrema)
CAMP = {"h_sigma": 39.04, "h_nu": 4.197, "d_mu": 0.4268, "d_sigma": 0.5237}


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def lognorm_stats(mu, s):
    return (np.exp(mu - s ** 2),               # mode
            np.exp(mu),                          # median
            np.exp(mu + 0.5 * s ** 2))           # mean


def main():
    out = _out()
    s = np.load(os.path.join(out, "campinas_samples.npz"))
    heights = s["heights"]; distances = s["distances"]

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))

    # --- Heights ---
    hx = np.linspace(-250, 250, 800)
    ax[0].hist(heights[np.abs(heights) < 250], bins=90, density=True,
               color="#cde0ec", edgecolor="white", lw=0.2,
               label="Histograma Campinas")
    ax[0].plot(hx, stats.t.pdf(hx, df=CAMP["h_nu"], loc=0, scale=CAMP["h_sigma"]),
               color="#16a085", lw=2.2,
               label=f"Campinas: t (σ={CAMP['h_sigma']:.1f}, ν={CAMP['h_nu']:.2f})")
    ax[0].plot(hx, stats.t.pdf(hx, df=BORDER["h_nu"], loc=0, scale=BORDER["h_sigma"]),
               color="#c0392b", lw=2.2, ls="--",
               label=f"5D/1059: t (σ={BORDER['h_sigma']:.2f}, ν={BORDER['h_nu']:.3f})")
    ax[0].set_xlabel("Desvio de altura pico/vale (m)"); ax[0].set_ylabel("PDF")
    ax[0].set_title("Altura dos extremos — Student-t"); ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)

    # --- Distances ---
    dx = np.linspace(0.01, 12, 800)
    ax[1].hist(distances[distances < 12], bins=70, density=True,
               color="#cde0ec", edgecolor="white", lw=0.2,
               label="Histograma Campinas")
    ax[1].plot(dx, stats.lognorm.pdf(dx, s=CAMP["d_sigma"], scale=np.exp(CAMP["d_mu"])),
               color="#16a085", lw=2.2,
               label=f"Campinas: LN (μ={CAMP['d_mu']:.2f}, σ={CAMP['d_sigma']:.2f})")
    ax[1].plot(dx, stats.lognorm.pdf(dx, s=BORDER["d_sigma"], scale=np.exp(BORDER["d_mu"])),
               color="#c0392b", lw=2.2, ls="--",
               label=f"5D/1059: LN (μ={BORDER['d_mu']:.2f}, σ={BORDER['d_sigma']:.2f})")
    ax[1].set_xlabel("Distância entre extremos (km)"); ax[1].set_ylabel("PDF")
    ax[1].set_title("Espaçamento dos extremos — Lognormal"); ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    fig.suptitle("Modelo estatístico de terreno: 5D/1059 (fronteiras) vs. Campinas-SP",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    fig.savefig(os.path.join(out, "compare_terrain.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "compare_terrain_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)

    # Derived distance statistics
    bm = lognorm_stats(BORDER["d_mu"], BORDER["d_sigma"])
    cm = lognorm_stats(CAMP["d_mu"], CAMP["d_sigma"])
    print("HEIGHTS (Student-t, mu=0):")
    print(f"  5D/1059 : sigma={BORDER['h_sigma']:.2f} m, nu={BORDER['h_nu']:.3f}  (cauda muito pesada)")
    print(f"  Campinas: sigma={CAMP['h_sigma']:.2f} m, nu={CAMP['h_nu']:.2f}   (escala maior, cauda mais leve)")
    print("\nDISTANCE between extrema (lognormal) [mode / median / mean] km:")
    print(f"  5D/1059 : {bm[0]:.2f} / {bm[1]:.2f} / {bm[2]:.2f}")
    print(f"  Campinas: {cm[0]:.2f} / {cm[1]:.2f} / {cm[2]:.2f}")
    print(f"\nfigure -> {os.path.join(out, 'compare_terrain.png')}")


if __name__ == "__main__":
    main()
