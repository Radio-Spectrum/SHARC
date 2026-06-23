# -*- coding: utf-8 -*-
"""Sweep the FS earth-station distance and find the I/N protection distance.

For each ES distance-to-centre it runs the SHARC campaign (reduced snapshots),
reads system_inr and computes P(I/N > -10 dB); the protection distance is where
that exceedance drops to the 20% criterion.
"""
import os
import io
import re
import sys
import json
import glob
import base64
import subprocess

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CAMPAIGN_YAML = ("sharc/campaigns/FS_8000_MHz_stat_terrain_clutter/input/"
                 "parameters_FS_8000_MHz_stat_terrain_clutter.yaml")
DISTANCES_KM = [5, 10, 20, 40, 80, 160, 320, 640]
N_SNAP = 300
CRIT_IN_DB = -10.0
CRIT_PCT = 20.0


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _run_one(dist_km, base_yaml):
    """Write a temp config at the given ES distance, run SHARC, return P(I/N>-10)."""
    out = _out()
    work = os.path.join(out, "sweep", f"d{dist_km}")
    os.makedirs(work, exist_ok=True)
    t = base_yaml
    t = re.sub(r"num_snapshots:\s*\d+", f"num_snapshots: {N_SNAP}", t)
    t = re.sub(r"output_dir:.*", lambda m: "output_dir: " + work, t, count=1)
    t = re.sub(r"min_dist_to_center:\s*[\d.]+", f"min_dist_to_center: {dist_km*1000}", t)
    t = re.sub(r"max_dist_to_center:\s*[\d.]+", f"max_dist_to_center: {dist_km*1000}", t)
    cfg = os.path.join(work, "params.yaml")
    open(cfg, "w", encoding="utf-8").write(t)

    subprocess.run([sys.executable, "sharc/main_cli.py", "-p", cfg],
                   check=True, capture_output=True)
    hits = glob.glob(os.path.join(work, "**", "system_inr.csv"), recursive=True)
    inr = pd.read_csv(hits[-1])["samples"].values.astype(float)
    return 100.0 * np.mean(inr > CRIT_IN_DB), float(np.median(inr))


def main():
    out = _out()
    base_yaml = open(CAMPAIGN_YAML, encoding="utf-8").read()

    d, pct, med = [], [], []
    for dk in DISTANCES_KM:
        p, m = _run_one(dk, base_yaml)
        d.append(dk); pct.append(p); med.append(m)
        print(f"  d={dk:4d} km -> P(I/N>{CRIT_IN_DB:.0f}dB)={p:5.1f}%   median I/N={m:6.1f} dB")
    d = np.array(d, float); pct = np.array(pct)

    # Protection distance: interpolate (log-distance) where exceedance == 20%
    prot = np.nan
    for i in range(len(d) - 1):
        if (pct[i] - CRIT_PCT) * (pct[i + 1] - CRIT_PCT) <= 0:
            lx0, lx1 = np.log10(d[i]), np.log10(d[i + 1])
            prot = 10 ** (lx0 + (lx1 - lx0) * (pct[i] - CRIT_PCT) / (pct[i] - pct[i + 1]))
            break

    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.semilogx(d, pct, "o-", color="#2980b9", lw=2, label=f"P(I/N > {CRIT_IN_DB:.0f} dB)")
    ax.axhline(CRIT_PCT, color="#7f8c8d", ls="--", lw=1, label=f"critério {CRIT_PCT:.0f}%")
    if np.isfinite(prot):
        ax.axvline(prot, color="#c0392b", ls=":", lw=1.5)
        ax.plot(prot, CRIT_PCT, "o", color="#c0392b", ms=9, zorder=5,
                label=f"distância de proteção ≈ {prot:.0f} km")
    ax.set_xlabel("Distância da ES ao centro do cluster IMT (km)")
    ax.set_ylabel("P(I/N > -10 dB)  (%)")
    ax.set_title("Distância de proteção — FS ES (Campinas, P.1812 terreno+clutter estat.)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "protection_distance.png"), dpi=120)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(out, "protection_distance_b64.json"), "w") as fh:
        json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")}, fh)

    json.dump({"distances_km": d.tolist(), "exceed_pct": pct.tolist(),
               "median_in_db": med, "protection_distance_km": prot,
               "criterion": {"in_db": CRIT_IN_DB, "pct": CRIT_PCT}},
              open(os.path.join(out, "protection_distance.json"), "w"), indent=2)
    print(f"\nDistância de proteção (I/N>-10dB <= 20%): "
          f"{prot:.1f} km" if np.isfinite(prot) else "fora da faixa varrida")


if __name__ == "__main__":
    main()
