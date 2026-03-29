import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
import itertools

BASE = Path(__file__).resolve().parents[1] / "output"

# line style by mask
MASK_STYLE = {
    "MSS": "-",     
    "STEP": ":",    
    "Spu": "--"     
}

LOAD_FACTORS = [0.2, 0.5]
MASK = ["Spu"] # "STEP",  "Spu"
EESS_systems = ["EESS_B"] # "EESS_D" "EESS_B"
EESS_pos = ['P','C'] # 'P','C'
MARGIN = [0]
DCMSS_systems = ["system_525km", "system_340km"] # "system_525km", "system_340km"

COVERAGES = {"SA": {}}

# matplotlib color cycle
COLOR_LIST = plt.rcParams['axes.prop_cycle'].by_key()['color']


# map color based on (LF, Margin)
COLOR_MAP = {}
comb = list(itertools.product(LOAD_FACTORS, MARGIN))

for i,(lf,m) in enumerate(comb):
    COLOR_MAP[(lf,m)] = COLOR_LIST[i % len(COLOR_LIST)]


def find_run(system, eess, cov, pos, mask, margin, lf):

    pattern = f"{system}_{eess}_{cov}_{pos}_{mask}_OM_{margin}_lf_{lf}"
    
    for d in BASE.iterdir():
        if d.is_dir() and pattern in d.name:
            return d
    
    return None


def load_curve(run_dir):

    f = run_dir / "system_dl_interf_power_per_mhz.csv"
    
    df = pd.read_csv(f)

    power_dbm = df.iloc[:,0].values

    # convert to dBW
    power_dbw = power_dbm - 30

    power_dbw = np.sort(power_dbw)

    n = len(power_dbw)

    ccdf = (n - np.arange(n)) / n

    return power_dbw, ccdf


def plot_for_position(ax, pos):

    for system in DCMSS_systems:
        for eess in EESS_systems:
            for cov in COVERAGES:
                for mask in MASK:
                    for margin in MARGIN:
                        for lf in LOAD_FACTORS:

                            run = find_run(system, eess, cov, pos, mask, margin, lf)

                            if run is None:
                                continue

                            x,y = load_curve(run)

                            label = f"{system.replace('_','')} - {eess.replace('_','')} - M = {margin}km - LF = {int(lf*100)}% / Mask: {mask}"

                            linestyle = MASK_STYLE.get(mask, "-")

                            color = COLOR_MAP[(lf,margin)]

                            ax.plot(
                                x,
                                y,
                                label=label,
                                linestyle=linestyle,
                                color=color,
                                linewidth=1.8
                            )


def add_protection_line(ax):

    ax.vlines(
        x=-154,
        ymin=0.01,
        ymax=1,
        colors="black",
        linewidth=2,
        label="-154 dBW/MHz 1% of the time"
    )




def make_plot():

    fig,ax = plt.subplots(1,2,figsize=(16,7))

    plot_for_position(ax[0],'P')
    ax[0].set_title("Station in Paraguay")

    plot_for_position(ax[1],'C')
    ax[1].set_title("Station in Colombia")

    for a in ax:

        add_protection_line(a)

        a.set_xlabel("Interference Power [dBW/MHz]")
        a.set_ylabel("CCDF")
        a.set_yscale("log")
        a.set_ylim(0.001, 1) # show from 1% to 100% of the time

        # soft dotted grid
        a.grid(
            True,
            linestyle=":",
            linewidth=0.5,
            alpha=0.4
        )

        a.legend(fontsize=8)

    plt.tight_layout()
    plt.show()


make_plot()