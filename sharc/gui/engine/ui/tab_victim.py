import tkinter as tk
from tkinter import ttk
from core.utils import add_row_three
from core.victim_data.victim_handler import _save_victim_config, _load_victim_config

# Note: The helper function add_row_three was not provided,
# but the main function logic is translated below.

def build_victim_tab(self, root):
    """Builds the 'Single Space Station' (Victim) tab UI elements."""

    def save_victim_config():
        _save_victim_config(root)

    def load_victim_config():
        _load_victim_config(root)

    
    topbar = ttk.Frame(root)
    topbar.pack(fill="x", pady=(0, 6))
    ttk.Button(topbar, text="Save Single Space Station config (.json)", command=save_victim_config).pack(side="left")
    ttk.Button(topbar, text="Load Single Space Station config (.json)", command=load_victim_config).pack(side="left", padx=(6, 0))

    # ==== Basic ====
    frm0 = ttk.LabelFrame(root, text="Basic Parameters")
    frm0.pack(fill="x", padx=2, pady=4)
    add_row_three(frm0, 0, [
        ("frequency [MHz]", ttk.Entry(frm0, textvariable=root.v_freq, width=10)),
        ("bandwidth [MHz]", ttk.Entry(frm0, textvariable=root.v_bw, width=10)),
        ("tx_power_density [dBW/Hz]", ttk.Entry(frm0, textvariable=root.v_txpsd, width=12)),
    ])
    add_row_three(frm0, 1, [
        ("polarization_loss [dB]", ttk.Entry(frm0, textvariable=root.v_pol_loss, width=10)),
        ("noise_temperature [K]", ttk.Entry(frm0, textvariable=root.v_tnoise, width=10)),
        ("channel_model", ttk.Combobox(frm0, textvariable=root.v_ch_model, values=["P619", "FSPL"], state="readonly", width=12)),
    ])
    add_row_three(frm0, 2, [
        ("season", ttk.Combobox(
            frm0, textvariable=root.v_season,
            values=["SUMMER", "WINTER"], state="readonly", width=10
        )),
        ("Spherical Earth?", ttk.Checkbutton(
            frm0, variable=root.ss_is_global_cs  # <- just pass the widget, no .grid()
        )),
        ("", ttk.Label(frm0, text="")),
    ])

    # ==== P619 ====
    frm1 = ttk.LabelFrame(root, text="P619 parameters")
    frm1.pack(fill="x", padx=2, pady=4)
    add_row_three(frm1, 0, [
        ("mean_clutter_height", ttk.Combobox(frm1, textvariable=root.v_p619_clutter,
                                             values=["Low", "Mid", "High"], state="readonly", width=10)),
        ("below_rooftop [%]", ttk.Entry(frm1, textvariable=root.v_p619_below_rooftop, width=10)),
        ("", ttk.Label(frm1, text="")),
    ])

    # ==== Geometry (subdivided) ====
    wrap = ttk.LabelFrame(root, text="Geometry – Classes")
    wrap.pack(fill="x", padx=2, pady=4)

    # Spacecraft (FIXED)
    frm_sc = ttk.LabelFrame(wrap, text="Spacecraft – Location (FIXED/GEO)")
    frm_sc.pack(fill="x", padx=2, pady=(6, 6))
    add_row_three(frm_sc, 0, [
        ("altitude [m] (sat)", ttk.Entry(frm_sc, textvariable=root.v_alt, width=12)),
        ("location.fixed.lat_deg", ttk.Entry(frm_sc, textvariable=root.v_fix_lat, width=12)),
        ("location.fixed.long_deg", ttk.Entry(frm_sc, textvariable=root.v_fix_lon, width=12)),
    ])

    # Earth Station
    frm_es = ttk.LabelFrame(wrap, text="Earth Station – Reference point on Earth")
    frm_es.pack(fill="x", padx=2, pady=(0, 6))
    add_row_three(frm_es, 0, [
        ("es_altitude [m]", ttk.Entry(frm_es, textvariable=root.v_es_alt, width=12)),
        ("es_lat_deg", ttk.Entry(frm_es, textvariable=root.v_es_lat, width=12)),
        ("es_long_deg", ttk.Entry(frm_es, textvariable=root.v_es_lon, width=12)),
    ])

    # Pointing (export only)
    frm_pt = ttk.LabelFrame(wrap, text="Pointing (export only)")
    frm_pt.pack(fill="x", padx=2, pady=(0, 6))
    add_row_three(frm_pt, 0, [
        ("azimuth.type", ttk.Combobox(frm_pt, textvariable=root.v_az_type, values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
        ("elevation.type", ttk.Combobox(frm_pt, textvariable=root.v_el_type, values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
        ("", ttk.Label(frm_pt, text="")),
    ])

    # Antenna
    frm3 = ttk.LabelFrame(root, text="Antenna")
    frm3.pack(fill="x", padx=2, pady=4)
    add_row_three(frm3, 0, [
        ("pattern", ttk.Combobox(frm3, textvariable=root.v_ant_pattern,
                                 values=["ITU-R S.672", "ITU-R M.2101", "3GPP TR 38.901", "Custom"], state="readonly", width=18)),
        ("gain [dBi]", ttk.Entry(frm3, textvariable=root.v_ant_gain, width=10)),
        ("", ttk.Label(frm3, text="")),
    ])
    root.frm_s672 = ttk.Frame(frm3)
    root.frm_s672.grid(row=1, column=0, columnspan=6, sticky="we", pady=(4, 0))
    add_row_three(root.frm_s672, 0, [
        ("itu_r_s_672.antenna_3_dB", ttk.Entry(root.frm_s672, textvariable=root.v_s672_3db, width=8)),
        ("itu_r_s_672.antenna_l_s [dB]", ttk.Entry(root.frm_s672, textvariable=root.v_s672_ls, width=8)),
        ("", ttk.Label(root.frm_s672, text="")),
    ])
    root.frm_other_ant = ttk.Frame(frm3)
    ttk.Label(root.frm_other_ant, text="Parameters for this pattern are not yet implemented.").grid(row=0, column=0, sticky="w")

    def _toggle_antenna(*_):
        if root.v_ant_pattern.get() == "ITU-R S.672":
            root.frm_other_ant.grid_remove()
            root.frm_s672.grid()
        else:
            root.frm_s672.grid_remove()
            root.frm_other_ant.grid(row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
            
    root.v_ant_pattern.trace_add("write", _toggle_antenna)
    _toggle_antenna()