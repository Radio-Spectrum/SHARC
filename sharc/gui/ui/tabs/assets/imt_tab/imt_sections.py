import tkinter as tk
from tkinter import ttk
from utils import add_row_three
from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper as H


class IMTSections:
    """Static builders for the standardized sections (General, BS, UE, Channel)."""

    @staticmethod
    def build_general(parent, state):
        frm = ttk.LabelFrame(parent, text="IMT – General Parameters")
        frm.pack(fill="x", pady=(2, 8))

        add_row_three(frm, 0, [
            ("minimum_separation_distance_bs_ue [m]", ttk.Entry(
                frm, textvariable=state.get("imt_min_sep"), width=10)),
            ("interfered_with", ttk.Combobox(frm, textvariable=state.get(
                "imt_interfered"), values=[False, True], state="readonly", width=8)),
            ("frequency [MHz]", ttk.Entry(
                frm, textvariable=state.get("imt_freq"), width=12)),
        ])
        add_row_three(frm, 1, [
            ("bandwidth [MHz]", ttk.Entry(
                frm, textvariable=state.get("imt_bw"), width=10)),
            ("rb_bandwidth [MHz]", ttk.Entry(
                frm, textvariable=state.get("imt_rb_bw"), width=10)),
            ("spectral_mask", ttk.Combobox(frm, textvariable=state.get(
                "imt_spec_mask"), values=["IMT-2020", "3GPP"], state="readonly", width=12)),
        ])
        add_row_three(frm, 2, [
            ("spurious_emissions [dBc]", ttk.Entry(
                frm, textvariable=state.get("imt_spurious"), width=10)),
            ("adjacent_antenna_model", ttk.Entry(
                frm, textvariable=state.get("imt_adj_ant_model"), width=16)),
            ("guard_band_ratio", ttk.Entry(
                frm, textvariable=state.get("imt_guard_ratio"), width=10)),
        ])

    @staticmethod
    def build_bs(parent, state):
        frm = ttk.LabelFrame(parent, text="BS – Parameters")
        frm.pack(fill="x", padx=6, pady=8)

        # Configure grid weights
        for c in range(3):
            frm.columnconfigure(c, weight=1, uniform="bscols")

        # --- Column 1: BS Basic ---
        # DEFINITION OF c1 MUST HAPPEN HERE
        c1 = H.create_sub_column(frm, 0, "BS – Basic")

        H.add_field(c1, 0, "load_probability", ttk.Entry(
            c1, textvariable=state.get("bs_load_prob"), width=10))
        H.add_field(c1, 1, "conducted_power [dBm]", ttk.Entry(
            c1, textvariable=state.get("bs_power"), width=10))
        H.add_field(c1, 2, "height [m]", ttk.Entry(
            c1, textvariable=state.get("bs_height"), width=10))
        H.add_field(c1, 3, "noise_figure [dB]", ttk.Entry(
            c1, textvariable=state.get("bs_nf"), width=10))
        H.add_field(c1, 4, "ohmic_loss [dB]", ttk.Entry(
            c1, textvariable=state.get("bs_ohmic"), width=10))

        # --- Column 2: BS Antenna Array  ---
        # DEFINITION OF c2
        c2 = H.create_sub_column(frm, 1, "BS – Antenna Array")

        H.add_field(c2, 0, "normalization", ttk.Checkbutton(
            c2, variable=state.get("bs_norm"), text=""))
        H.add_field(c2, 1, "element_pattern", ttk.Combobox(c2, textvariable=state.get(
            "bs_elem_pat"), values=["M2101", "ITU-R S.672", "Custom"], state="readonly", width=14))
        H.add_field(c2, 2, "minimum_array_gain [dB]", ttk.Entry(
            c2, textvariable=state.get("bs_min_arr_gain"), width=10))

        H.add_range(c2, 3, "h_beamsteer [deg]",
                    ttk.Entry(c2, textvariable=state.get(
                        "bs_h_steer_min"), width=7),
                    ttk.Entry(c2, textvariable=state.get("bs_h_steer_max"), width=7))
        H.add_range(c2, 4, "v_beamsteer [deg]",
                    ttk.Entry(c2, textvariable=state.get(
                        "bs_v_steer_min"), width=7),
                    ttk.Entry(c2, textvariable=state.get("bs_v_steer_max"), width=7))

        H.add_field(c2, 5, "downtilt [deg]", ttk.Entry(
            c2, textvariable=state.get("bs_downtilt"), width=10))
        H.add_field(c2, 6, "element_max_g [dBi]", ttk.Entry(
            c2, textvariable=state.get("bs_elem_max_g"), width=10))
        H.add_field(c2, 7, "element_phi_3db [deg]", ttk.Entry(
            c2, textvariable=state.get("bs_phi3"), width=10))
        H.add_field(c2, 8, "element_theta_3db [deg]", ttk.Entry(
            c2, textvariable=state.get("bs_theta3"), width=10))
        H.add_field(c2, 9, "n_rows", ttk.Entry(
            c2, textvariable=state.get("bs_rows"), width=10))
        H.add_field(c2, 10, "n_columns", ttk.Entry(
            c2, textvariable=state.get("bs_cols"), width=10))
        H.add_field(c2, 11, "element_horiz_spacing [λ]", ttk.Entry(
            c2, textvariable=state.get("bs_elem_hs"), width=10))
        H.add_field(c2, 12, "element_vert_spacing [λ]", ttk.Entry(
            c2, textvariable=state.get("bs_elem_vs"), width=10))
        H.add_field(c2, 13, "element_am [dB]", ttk.Entry(
            c2, textvariable=state.get("bs_elem_am"), width=10))
        H.add_field(c2, 14, "element_sla_v [dB]", ttk.Entry(
            c2, textvariable=state.get("bs_elem_sla_v"), width=10))
        H.add_field(c2, 15, "multiplication_factor", ttk.Entry(
            c2, textvariable=state.get("bs_mult"), width=10))

        # --- Column 3: BS Sub-array ---
        # DEFINITION OF c3
        c3 = H.create_sub_column(frm, 2, "BS – Sub-array")

        H.add_field(c3, 0, "is_enabled", ttk.Checkbutton(
            c3, variable=state.get("bs_sub_enabled"), text=""))
        H.add_field(c3, 1, "n_rows", ttk.Entry(
            c3, textvariable=state.get("bs_sub_rows"), width=10))
        H.add_field(c3, 2, "element_vert_spacing [λ]", ttk.Entry(
            c3, textvariable=state.get("bs_sub_evspace"), width=10))
        H.add_field(c3, 3, "eletrical_downtilt [deg]", ttk.Entry(
            c3, textvariable=state.get("bs_sub_e_downtilt"), width=10))

    @staticmethod
    def build_ue(parent, state):
        frm = ttk.LabelFrame(parent, text="UE – Parameters")
        frm.pack(fill="x", padx=6, pady=8)
        for c in range(3):
            frm.columnconfigure(c, weight=1, uniform="uecols")

        # Column 1
        c1 = H.create_sub_column(frm, 0, "UE – Basic")
        H.add_field(c1, 0, "k", ttk.Entry(
            c1, textvariable=state.get("ue_k"), width=8))
        H.add_field(c1, 1, "k_m", ttk.Entry(
            c1, textvariable=state.get("ue_km"), width=8))
        H.add_field(c1, 2, "indoor_percent [%]", ttk.Entry(
            c1, textvariable=state.get("ue_indoor"), width=8))

        # Distribution Logic
        col_dist = ttk.LabelFrame(
            frm, text="UE – Distribution (Angle&Distance)")

        def _toggle_dist(*_):
            if state.get("ue_dist_type").get().upper() == "ANGLE_AND_DISTANCE":
                col_dist.grid()
            else:
                col_dist.grid_remove()

        cb_dist = ttk.Combobox(c1, textvariable=state.get("ue_dist_type"), values=[
                               "Macro_countries", "UNIFORM", "CELL", "UNIFORM_IN_CELL", "ANGLE_AND_DISTANCE"], state="readonly", width=18)
        cb_dist.bind("<<ComboboxSelected>>", _toggle_dist)
        H.add_field(c1, 3, "distribution_type", cb_dist)

        H.add_field(c1, 4, "tx_power_control", ttk.Checkbutton(
            c1, variable=state.get("ue_tx_power_ctrl"), text=""))
        H.add_field(c1, 5, "p_o_pusch [dBm]", ttk.Entry(
            c1, textvariable=state.get("ue_p_o_pusch"), width=10))
        H.add_field(c1, 6, "alpha", ttk.Entry(
            c1, textvariable=state.get("ue_alpha"), width=10))
        H.add_field(c1, 7, "p_cmax [dBm]", ttk.Entry(
            c1, textvariable=state.get("ue_p_cmax"), width=10))
        H.add_field(c1, 8, "power_dynamic_range [dB]", ttk.Entry(
            c1, textvariable=state.get("ue_p_dyn"), width=10))
        H.add_field(c1, 9, "height [m]", ttk.Entry(
            c1, textvariable=state.get("ue_height"), width=10))
        H.add_field(c1, 10, "noise_figure [dB]", ttk.Entry(
            c1, textvariable=state.get("ue_nf"), width=10))
        H.add_field(c1, 11, "ohmic_loss [dB]", ttk.Entry(
            c1, textvariable=state.get("ue_ohmic"), width=10))
        H.add_field(c1, 12, "body_loss [dB]", ttk.Entry(
            c1, textvariable=state.get("ue_body_loss"), width=10))

        # Column 1 Extra (Distribution Panel)
        col_dist.grid(row=1, column=0, sticky="nsew", padx=(3, 6), pady=(0, 6))
        for c in range(4):
            col_dist.columnconfigure(c, weight=(1 if c in (1, 3) else 0))
        H.add_field(col_dist, 0, "distribution_distance", ttk.Combobox(col_dist, textvariable=state.get(
            "ue_dist_distance"), values=["RAYLEIGH", "UNIFORM", "SQRT(UNIFORM)"], state="readonly", width=16))
        H.add_field(col_dist, 1, "distribution_azimuth", ttk.Combobox(col_dist, textvariable=state.get(
            "ue_dist_azimuth"), values=["NORMAL", "UNIFORM"], state="readonly", width=16))
        H.add_range(col_dist, 2, "azimuth_range [deg]", ttk.Entry(col_dist, textvariable=state.get(
            "ue_az_min"), width=8), ttk.Entry(col_dist, textvariable=state.get("ue_az_max"), width=8))
        _toggle_dist()  # Init state

        # Column 2
        c2 = H.create_sub_column(frm, 1, "UE – Antenna Array")
        H.add_field(c2, 0, "normalization", ttk.Checkbutton(
            c2, variable=state.get("ue_norm"), text=""))
        H.add_field(c2, 1, "element_pattern", ttk.Combobox(c2, textvariable=state.get(
            "ue_elem_pat"), values=["FIXED", "M2101", "Custom"], state="readonly", width=14))
        H.add_field(c2, 2, "minimum_array_gain [dB]", ttk.Entry(
            c2, textvariable=state.get("ue_min_arr_gain"), width=10))
        H.add_field(c2, 3, "element_max_g [dBi]", ttk.Entry(
            c2, textvariable=state.get("ue_elem_max_g"), width=10))
        H.add_field(c2, 4, "element_phi_3db [deg]", ttk.Entry(
            c2, textvariable=state.get("ue_phi3"), width=10))
        H.add_field(c2, 5, "element_theta_3db [deg]", ttk.Entry(
            c2, textvariable=state.get("ue_theta3"), width=10))
        H.add_field(c2, 6, "n_rows", ttk.Entry(
            c2, textvariable=state.get("ue_rows"), width=10))
        H.add_field(c2, 7, "n_columns", ttk.Entry(
            c2, textvariable=state.get("ue_cols"), width=10))
        H.add_field(c2, 8, "element_am [dB]", ttk.Entry(
            c2, textvariable=state.get("ue_elem_am"), width=10))
        H.add_field(c2, 9, "element_sla_v [dB]", ttk.Entry(
            c2, textvariable=state.get("ue_elem_sla_v"), width=10))
        H.add_field(c2, 10, "multiplication_factor", ttk.Entry(
            c2, textvariable=state.get("ue_mult"), width=10))

        # Column 3
        c3 = H.create_sub_column(frm, 2, "UE – Sub-array")
        H.add_field(c3, 0, "is_enabled", ttk.Checkbutton(
            c3, variable=state.get("ue_sub_enabled"), text=""))
        H.add_field(c3, 1, "n_rows", ttk.Entry(
            c3, textvariable=state.get("ue_sub_rows"), width=10))
        H.add_field(c3, 2, "element_vert_spacing [λ]", ttk.Entry(
            c3, textvariable=state.get("ue_sub_evspace"), width=10))
        H.add_field(c3, 3, "eletrical_downtilt [deg]", ttk.Entry(
            c3, textvariable=state.get("ue_sub_e_downtilt"), width=10))

    @staticmethod
    def build_channel(parent, state):
        frm = ttk.LabelFrame(parent, text="UL / DL / Channel / Shadowing")
        frm.pack(fill="x", pady=(2, 8))

        add_row_three(frm, 0, [
            ("uplink.attenuation_factor", ttk.Entry(
                frm, textvariable=state.get("ul_att"), width=8)),
            ("uplink.sinr_min / sinr_max [dB]", H.pair_entries(
                frm, state.get("ul_sinr_min"), state.get("ul_sinr_max"), width=8)),
            ("downlink.attenuation_factor", ttk.Entry(
                frm, textvariable=state.get("dl_att"), width=8)),
        ])
        add_row_three(frm, 1, [
            ("downlink.sinr_min / sinr_max [dB]", H.pair_entries(
                frm, state.get("dl_sinr_min"), state.get("dl_sinr_max"), width=8)),
            ("channel_model", ttk.Entry(
                frm, textvariable=state.get("ch_model"), width=12)),
            ("shadowing", ttk.Combobox(frm, textvariable=state.get(
                "shadowing"), values=[True, False], state="readonly", width=8)),
        ])
