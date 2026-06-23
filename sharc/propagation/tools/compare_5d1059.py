# -*- coding: utf-8 -*-
"""Decompose the protection-distance gap vs ITU-R WP5D 5D/1059 (Study D).

Runs the P.1812 campaign under three configurations to isolate the effect of the
clutter model and the FS boresight pointing, and finds the protection distance
(P(I/N>-10 dB) <= 20%) for each:

  1. terrain_pointing : clutter-over-terrain (statistical) + boresight at centre
  2. p2108_pointing   : ITU-R P.2108 (both ends)         + boresight at centre
  3. p2108_random     : ITU-R P.2108 (both ends)         + random azimuth  (~doc)
"""
import os
import re
import sys
import json
import glob
import subprocess

import numpy as np
import pandas as pd

CAMP_YAML = ("sharc/campaigns/FS_8000_MHz_stat_terrain_clutter/input/"
             "parameters_FS_8000_MHz_stat_terrain_clutter.yaml")
DISTS = [5, 10, 20, 40, 80]
NSNAP = 250
CRIT = -10.0
PCT = 20.0

AZ_POINT = "    azimuth:\n      type: POINTING_AT_IMT_CENTER\n"
AZ_RAND = ("    azimuth:\n      type: UNIFORM_DIST\n"
           "      uniform_dist:\n        min: -180\n        max: 180\n")

CONFIGS = {
    "terrain_pointing": dict(clutter_mode="terrain", clutter_stat="true", az=AZ_POINT),
    "p2108_pointing":   dict(clutter_mode="p2108",   clutter_stat="false", az=AZ_POINT),
    "p2108_random":     dict(clutter_mode="p2108",   clutter_stat="false", az=AZ_RAND),
}


def _out():
    return os.environ.get("CLAUDE_SCRATCH",
                          os.path.join(os.path.dirname(__file__), "_campinas_out"))


def _build_yaml(base, cfg, dist_km, work):
    t = base
    t = re.sub(r"num_snapshots:\s*\d+", f"num_snapshots: {NSNAP}", t)
    t = re.sub(r"output_dir:.*", lambda m: "output_dir: " + work, t, count=1)
    t = re.sub(r"min_dist_to_center:\s*[\d.]+", f"min_dist_to_center: {dist_km*1000}", t)
    t = re.sub(r"max_dist_to_center:\s*[\d.]+", f"max_dist_to_center: {dist_km*1000}", t)
    t = re.sub(r"clutter_mode:.*",
               lambda m: "clutter_mode: " + cfg["clutter_mode"]
               + "\n    clutter_type: both_ends", t, count=1)
    t = re.sub(r"clutter_statistical:.*",
               lambda m: "clutter_statistical: " + cfg["clutter_stat"], t, count=1)
    # Replace the azimuth block (from 'azimuth:' up to the 'elevation:' line)
    t = re.sub(r"[ ]{4}azimuth:.*?(?=[ ]{4}elevation:)", lambda m: cfg["az"], t,
               count=1, flags=re.DOTALL)
    return t


def _exceed(cfg, dist_km, base):
    out = _out()
    work = os.path.join(out, "cmp5d1059", f"{cfg['clutter_mode']}_{cfg['clutter_stat']}_{dist_km}")
    os.makedirs(work, exist_ok=True)
    yml = os.path.join(work, "p.yaml")
    open(yml, "w", encoding="utf-8").write(_build_yaml(base, cfg, dist_km, work))
    subprocess.run([sys.executable, "sharc/main_cli.py", "-p", yml],
                   check=True, capture_output=True)
    inr = pd.read_csv(glob.glob(os.path.join(work, "**", "system_inr.csv"),
                                recursive=True)[-1])["samples"].values.astype(float)
    return 100.0 * np.mean(inr > CRIT), float(np.median(inr))


def _protection(d, pct):
    for i in range(len(d) - 1):
        if (pct[i] - PCT) * (pct[i + 1] - PCT) <= 0:
            lx0, lx1 = np.log10(d[i]), np.log10(d[i + 1])
            return 10 ** (lx0 + (lx1 - lx0) * (pct[i] - PCT) / (pct[i] - pct[i + 1]))
    return np.nan


def main():
    base = open(CAMP_YAML, encoding="utf-8").read()
    res = {}
    for name, cfg in CONFIGS.items():
        pcts, meds = [], []
        for dk in DISTS:
            p, m = _exceed(cfg, dk, base)
            pcts.append(p); meds.append(m)
            print(f"  [{name}] d={dk:3d} km -> P(I/N>-10)={p:5.1f}%  median I/N={m:6.1f} dB")
        prot = _protection(np.array(DISTS, float), np.array(pcts))
        res[name] = dict(dist_km=DISTS, exceed_pct=pcts, median=meds, protection_km=prot)
        print(f"  => {name}: protection distance ~ {prot:.0f} km\n")
    json.dump(res, open(os.path.join(_out(), "cmp5d1059.json"), "w"), indent=2)
    print("Saved cmp5d1059.json")


if __name__ == "__main__":
    main()
