# -*- coding: utf-8 -*-
"""Plot clutter-height PDFs of the distance-dependent statistical model.

Shows the lognormal PDF of representative clutter height at three distances from
the IMT cluster centre (300 m, 3 km, 30 km), with the analytical density, a
histogram of samples drawn by the implemented sampler, and the mean/median.
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

from sharc.propagation.terrain_statistical import StatisticalClutterModel

DISTANCES_KM = [0.3, 3.0, 30.0]
CONTEXT = {0.3: "centro urbano", 3.0: "suburbano", 30.0: "rural"}
N_SAMPLES = 200000


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def main():
    out = _out()
    model = StatisticalClutterModel()  # defaults = Campinas land-use fit
    rng = np.random.RandomState(2024)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    for ax, d in zip(axes, DISTANCES_KM):
        mu_d = float(model._mu(d))
        s = model.clutter_sigma
        median = model.median_m(d)
        mean = model.mean_m(d)

        # Analytical lognormal PDF
        xmax = float(stats.lognorm.ppf(0.99, s=s, scale=np.exp(mu_d)))
        x = np.linspace(0.01, xmax, 600)
        pdf = stats.lognorm.pdf(x, s=s, scale=np.exp(mu_d))

        # Samples from the implemented model
        samp = model.sample(rng, distance_km=d, size=N_SAMPLES)

        ax.hist(samp, bins=120, range=(0, xmax), density=True,
                color="#bcd6c4", edgecolor="white", linewidth=0.2,
                label="amostras (sampler)")
        ax.plot(x, pdf, color="#16a085", lw=2, label="PDF lognormal")
        ax.axvline(median, color="#2980b9", ls="--", lw=1.8,
                   label=f"mediana = {median:.1f} m")
        ax.axvline(mean, color="#c0392b", ls="-.", lw=1.8,
                   label=f"média = {mean:.1f} m")

        dlabel = f"{d*1000:.0f} m" if d < 1 else f"{d:.0f} km"
        ax.set_title(f"d = {dlabel}  ({CONTEXT[d]})")
        ax.set_xlabel("Altura de clutter (m)")
        ax.set_ylabel("Densidade de probabilidade")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        print(f"d={dlabel:>5}: mediana={median:5.2f} m, média={mean:6.2f} m "
              f"(mu_ln={mu_d:.3f}, sigma_ln={s:.3f})")

    fig.suptitle("PDF da altura de clutter — modelo estatístico dependente da "
                 "distância (uso do solo real, Campinas-SP)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    png = os.path.join(out, "clutter_pdfs.png")
    fig.savefig(png, dpi=120)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "clutter_pdfs_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)
    print(f"\nfigure -> {png}")


if __name__ == "__main__":
    main()
