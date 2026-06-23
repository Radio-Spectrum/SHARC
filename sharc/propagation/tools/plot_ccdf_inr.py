# -*- coding: utf-8 -*-
"""Plot the CCDF (complementary CDF) of the I/N samples with a protection criterion.

Usage:
    python -m sharc.propagation.tools.plot_ccdf_inr [csv_path]
"""
import os
import io
import sys
import json
import base64

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_CSV = ("sharc/campaigns/FS_8000_MHz_stat_terrain_clutter/output/"
               "FS_5km_2026-06-23_01/system_inr.csv")
CRIT_IN_DB = -10.0      # protection criterion I/N (dB)
CRIT_PCT = 20.0         # ... not to be exceeded for this % of events


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def main(argv=None):
    csv = (argv[0] if argv else DEFAULT_CSV)
    samples = pd.read_csv(csv)["samples"].values.astype(float)
    n = samples.size

    # CCDF: percentage of events with I/N > abscissa
    xs = np.sort(samples)
    ccdf = 100.0 * (np.arange(n, 0, -1)) / n   # P(I/N >= xs)

    # Actual CCDF value at the criterion
    pct_at_crit = 100.0 * np.mean(samples > CRIT_IN_DB)
    met = pct_at_crit <= CRIT_PCT

    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.semilogy(xs, ccdf, color="#2980b9", lw=2, label="CCDF do I/N")

    # Protection criterion marker and guides
    ax.axvline(CRIT_IN_DB, color="#7f8c8d", ls="--", lw=1)
    ax.axhline(CRIT_PCT, color="#7f8c8d", ls="--", lw=1)
    ax.plot(CRIT_IN_DB, CRIT_PCT, "o", color="#c0392b", ms=9, zorder=5,
            label=f"Critério: I/N = {CRIT_IN_DB:.0f} dB @ {CRIT_PCT:.0f}%")
    ax.annotate(f"  critério\n  ({CRIT_IN_DB:.0f} dB, {CRIT_PCT:.0f}%)",
                xy=(CRIT_IN_DB, CRIT_PCT), color="#c0392b", fontsize=9,
                va="center", ha="left")

    # Mark the actual exceedance at -10 dB
    ax.plot(CRIT_IN_DB, pct_at_crit, "s", color="#16a085", ms=8, zorder=5,
            label=f"Real @ {CRIT_IN_DB:.0f} dB: {pct_at_crit:.1f}%")

    ax.set_xlabel("I/N (dB)")
    ax.set_ylabel("Porcentagem dos eventos com I/N > abscissa (%)")
    ax.set_ylim(max(0.05, 100.0 / n / 2), 100)
    ax.set_title("CCDF do I/N — FS ES (Campinas, P.1812 terreno+clutter estatístico)\n"
                 f"{'CRITÉRIO ATENDIDO' if met else 'CRITÉRIO VIOLADO'}: "
                 f"I/N > {CRIT_IN_DB:.0f} dB em {pct_at_crit:.1f}% (limite {CRIT_PCT:.0f}%)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=9, loc="upper right")
    fig.tight_layout()

    png = os.path.join(_out(), "ccdf_inr.png")
    fig.savefig(png, dpi=120)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(_out(), "ccdf_inr_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)

    print(f"N = {n} amostras")
    print(f"I/N: min={xs[0]:.1f}  p50={np.median(samples):.1f}  "
          f"p90={np.percentile(samples,90):.1f}  max={xs[-1]:.1f} dB")
    print(f"P(I/N > {CRIT_IN_DB:.0f} dB) = {pct_at_crit:.1f}%   "
          f"(criterio: <= {CRIT_PCT:.0f}%)  -> {'ATENDIDO' if met else 'VIOLADO'}")
    print(f"figure -> {png}")


if __name__ == "__main__":
    main(sys.argv[1:])
