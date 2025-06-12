#!/usr/bin/env python3
# plot_results_matplot.py
import glob
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# === PARAMETERS ===
BASE_DIR = Path(__file__).parent.parent  # two levels up: campaigns/mss_d2d_to_gnss
OUTPUT_DIR = BASE_DIR / "output"
FOLDER_PATTERN = "output_mss_d2d_to_gnss_elev_*_20*_*"

# CCDF settings
PERC_TIME = 0.01  # 1%

# Protection criteria
INR_CRIT = -6.0           # dB
PSD_CRIT = -147.4         # dBW/MHz

# Colors & linestyles
COLORS = ["C0","C1","C2","C3","C4"]
LS = ["-","--","-.",":","-"]

def load_csv(path, column="samples"):
    """Load a single-column CSV into a flat numpy array."""
    df = pd.read_csv(path, header=0)
    return df[column].to_numpy()

def ccdf_from(data, n_bins=200):
    """Compute CCDF: returns (x, P(X>x))."""
    data = np.sort(data)
    y = 1.0 - np.arange(1, len(data)+1)/len(data)
    return data, y

# 1) Find all result folders
folders = sorted(glob.glob(str(OUTPUT_DIR / FOLDER_PATTERN)))

# 2) Bucket by elevation
by_elev = {}
regex = re.compile(r"elev_(\d+)_deg")
for d in folders:
    m = regex.search(d)
    if not m:
        continue
    elev = int(m.group(1))
    by_elev.setdefault(elev, []).append(d)

# 3) Load metrics per elevation
inr_data = {}
psd_data = {}

for elev, dirs in sorted(by_elev.items()):
    folder = dirs[-1]  # only latest
    inr_csv = os.path.join(folder, "system_inr.csv")
    if os.path.exists(inr_csv):
        inr_data[elev] = load_csv(inr_csv)
    psd_csv = os.path.join(folder, "system_dl_interf_power_per_mhz.csv")
    if os.path.exists(psd_csv):
        psd_data[elev] = load_csv(psd_csv)

# 4) Plot CCDF of INR
plt.figure(figsize=(10, 6))

for i, (elev, data) in enumerate(sorted(inr_data.items())):
    x, y = ccdf_from(data)
    plt.plot(x, y, label=f"{elev}°", color=COLORS[i % len(COLORS)],
             linestyle=LS[i % len(LS)], linewidth=2)

plt.axvline(INR_CRIT, color="red", linestyle="--", linewidth=2, label=f"INR crit = {INR_CRIT} dB")
plt.axhline(PERC_TIME, color="black", linestyle=":", linewidth=1.5, label="1%")

plt.title("CCDF of INR by Elevation", fontsize=14)
plt.xlabel("INR [dB]", fontsize=12)
plt.ylabel(r"P(INR $>$ x)", fontsize=12)
plt.xlim([-50, 10])
plt.ylim([1e-3, 1])
plt.yscale("log")
plt.grid(True, which="major", linestyle="--", linewidth=0.6, color="gray")
plt.minorticks_off()
plt.legend(title="Elevation", fontsize=10, title_fontsize=11, loc="lower left")
plt.tight_layout()
plt.show()

# 5) Plot CCDF of Interference Power per MHz
plt.figure(figsize=(10, 6))

for i, (elev, data) in enumerate(sorted(psd_data.items())):
    x, y = ccdf_from(data)
    plt.plot(x, y, label=f"{elev}°", color=COLORS[i % len(COLORS)],
             linestyle=LS[i % len(LS)], linewidth=2)

plt.axvline(PSD_CRIT, color="red", linestyle="--", linewidth=2, label=f"PSD crit = {PSD_CRIT} dBW/MHz")
plt.axhline(PERC_TIME, color="black", linestyle=":", linewidth=1.5, label="1%")

plt.title("CCDF of Interference Power per MHz by Elevation", fontsize=14)
plt.xlabel("Interference Power per MHz [dBW/MHz]", fontsize=12)
plt.ylabel(r"P(P > x)", fontsize=12)
plt.xlim([-200, -100])
plt.ylim([1e-3, 1])
plt.yscale("log")
plt.grid(True, which="major", linestyle="--", linewidth=0.6, color="gray")
plt.minorticks_off()
plt.legend(title="Elevation", fontsize=10, title_fontsize=11, loc="lower left")
plt.tight_layout()
plt.show()
