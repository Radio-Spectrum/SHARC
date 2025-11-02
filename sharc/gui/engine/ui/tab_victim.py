"""
Single Space Station (victim) tab.
Contains parameters for the victim satellite/earth-station configuration.
"""

from tkinter import ttk
import tkinter as tk
from core.utils import add_row_three


def build_victim_tab(app: tk.Tk, root: tk.Widget) -> None:
    topbar = ttk.Frame(root)
    topbar.pack(fill="x", pady=(0, 6))
    ttk.Button(topbar, text="Save Single Space Station config (.json)", command=lambda: None).pack(side="left")
    ttk.Button(topbar, text="Load Single Space Station config (.json)", command=lambda: None).pack(side="left", padx=(6, 0))

    # Basic parameters
    frm0 = ttk.LabelFrame(root, text="Basic parameters")
    frm0.pack(fill="x", padx=2, pady=4)
    add_row_three(
        frm0,
        0,
        [
            ("frequency [MHz]", ttk.Entry(frm0, textvariable=app.v_freq, width=10)),
            ("bandwidth [MHz]", ttk.Entry(frm0, textvariable=app.v_bw, width=10)),
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm0, textvariable=app.v_txpsd, width=12)),
        ],
    )

    add_row_three(
        frm0,
        1,
        [
            ("polarization_loss [dB]", ttk.Entry(frm0, textvariable=tk.StringVar(value="0"), width=10)),
            ("noise_temperature [K]", ttk.Entry(frm0, textvariable=tk.StringVar(value="500"), width=10)),
            ("channel_model", ttk.Combobox(frm0, values=["P619", "FSPL"], state="readonly", width=12)),
        ],
    )

    # Spacecraft geometry
    frm_sc = ttk.LabelFrame(root, text="Spacecraft – Location (FIXED/GEO)")
    frm_sc.pack(fill="x", padx=2, pady=(6, 6))
    add_row_three(
        frm_sc,
        0,
        [
            ("altitude [m] (satellite)", ttk.Entry(frm_sc, textvariable=app.v_alt, width=12)),
            ("location.fixed.lat_deg", ttk.Entry(frm_sc, textvariable=app.v_fix_lat, width=12)),
            ("location.fixed.long_deg", ttk.Entry(frm_sc, textvariable=app.v_fix_lon, width=12)),
        ],
    )

    # Antenna parameters
    frm_ant = ttk.LabelFrame(root, text="Antenna")
    frm_ant.pack(fill="x", padx=2, pady=4)
    add_row_three(
        frm_ant,
        0,
        [
            (
                "pattern",
                ttk.Combobox(
                    frm_ant,
                    textvariable=app.v_ant_pattern,
                    values=["ITU-R S.672", "ITU-R M.2101", "3GPP TR 38.901", "Custom"],
                    state="readonly",
                    width=18,
                ),
            ),
            ("gain [dBi]", ttk.Entry(frm_ant, textvariable=app.v_ant_gain, width=10)),
            ("", ttk.Label(frm_ant, text="")),
        ],
    )
