# -*- coding: utf-8 -*-
"""Reproduce ITU-R WP5D 5D/1059 Figure A1.1.4-9(a): FS Example 3 (20 m), CCDF of
INR (DL) at D = 60 km, P.2108 clutter on one end, random azimuth, with and
without the statistical terrain profile.
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

CAMP_YAML = ("sharc/campaigns/FS_8000_MHz_stat_terrain_clutter/input/"
             "parameters_FS_8000_MHz_stat_terrain_clutter.yaml")
DIST_KM = 60
NSNAP = 2000
CRIT, PCT = -10.0, 20.0
# Doc Fig A1.1.4-9 uses boresight at the cluster centre (beta=0) with random FS
# position (alpha). Set BORESIGHT=random to instead use a random azimuth.
AZ_POINT = "    azimuth:\n      type: POINTING_AT_IMT_CENTER\n"
AZ_RAND = ("    azimuth:\n      type: UNIFORM_DIST\n"
           "      uniform_dist:\n        min: -180\n        max: 180\n")
AZ = AZ_RAND if os.environ.get("BORESIGHT", "pointing") == "random" else AZ_POINT
TAG = os.environ.get("BORESIGHT", "pointing")


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _build(base, terrain, work):
    t = base
    t = re.sub(r"num_snapshots:\s*\d+", f"num_snapshots: {NSNAP}", t)
    t = re.sub(r"output_dir:.*", lambda m: "output_dir: " + work, t, count=1)
    t = re.sub(r"min_dist_to_center:\s*[\d.]+", f"min_dist_to_center: {DIST_KM*1000}", t)
    t = re.sub(r"max_dist_to_center:\s*[\d.]+", f"max_dist_to_center: {DIST_KM*1000}", t)
    t = re.sub(r"clutter_mode:.*",
               lambda m: "clutter_mode: p2108\n    clutter_type: one_end", t, count=1)
    t = re.sub(r"clutter_statistical:.*", lambda m: "clutter_statistical: false", t, count=1)
    t = re.sub(r"terrain_profile:.*", lambda m: "terrain_profile: " + terrain, t, count=1)
    t = re.sub(r"percentage_p:.*", lambda m: "percentage_p: RANDOM", t, count=1)
    t = re.sub(r"[ ]{4}azimuth:.*?(?=[ ]{4}elevation:)", lambda m: AZ, t,
               count=1, flags=re.DOTALL)
    return t


def _run(terrain, base):
    work = os.path.join(_out(), "fig9", TAG, terrain)
    os.makedirs(work, exist_ok=True)
    yml = os.path.join(work, "p.yaml")
    open(yml, "w", encoding="utf-8").write(_build(base, terrain, work))
    subprocess.run([sys.executable, "sharc/main_cli.py", "-p", yml], check=True, capture_output=True)
    inr = pd.read_csv(glob.glob(os.path.join(work, "**", "system_inr.csv"),
                                recursive=True)[-1])["samples"].values.astype(float)
    return inr


def main():
    base = open(CAMP_YAML, encoding="utf-8").read()
    data = {}
    for terrain in ["flat", "statistical"]:
        inr = _run(terrain, base)
        data[terrain] = inr
        pct = 100.0 * np.mean(inr > CRIT)
        print(f"[{terrain:>11}] N={inr.size}  I/N p50={np.median(inr):.1f}  "
              f"P(I/N>-10)={pct:.1f}%")

    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    styles = {"flat": ("#c0392b", "sem terreno (ter_OFF)"),
              "statistical": ("#2980b9", "com terreno estatístico (ter_ON)")}
    for terrain, inr in data.items():
        xs = np.sort(inr)
        ccdf = 100.0 * np.arange(inr.size, 0, -1) / inr.size
        col, lbl = styles[terrain]
        ax.semilogy(xs, ccdf, color=col, lw=2, label=lbl)
    ax.axvline(CRIT, color="#7f8c8d", ls="--", lw=1)
    ax.axhline(PCT, color="#7f8c8d", ls="--", lw=1)
    ax.plot(CRIT, PCT, "ko", ms=7, label="critério (−10 dB @ 20%)")
    ax.set_xlabel("INR = I/N (dB)")
    ax.set_ylabel("P(I/N > abscissa) (%)")
    ax.set_ylim(max(0.04, 100.0 / NSNAP / 2), 100)
    bmode = "boresight no centro (β=0)" if TAG != "random" else "azimute aleatório"
    ax.set_title(f"Reprodução 5D/1059 Fig. A1.1.4-9(a) — FS 20 m, D={DIST_KM} km\n"
                 f"P.2108 (1 ponta), {bmode}, P.1812 (DL), {NSNAP} snapshots")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=9, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(_out(), f"fig9_repro_{TAG}.png"), dpi=120)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    json.dump({"img": base64.b64encode(buf.getvalue()).decode("ascii")},
              open(os.path.join(_out(), f"fig9_repro_{TAG}_b64.json"), "w"))
    print("figure -> fig9_repro.png")


if __name__ == "__main__":
    main()
