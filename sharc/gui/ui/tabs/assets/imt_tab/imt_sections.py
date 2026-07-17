from PySide6.QtWidgets import QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout, QFormLayout
from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper as H
from PySide6.QtWidgets import QLineEdit, QComboBox

class IMTSections:
    """Static builders for the standardized sections (General, BS, UE, Channel)."""

    @staticmethod
    def build_general(parent_layout, state):
        frm = QGroupBox("IMT – General Parameters")
        layout = QGridLayout(frm)
        
        H.add_grid_row(layout, 0, [
            ("min_separation_distance_bs_ue [m]", H.create_field(state.get("imt_min_sep"))),
            ("interfered_with", H.create_field(state.get("imt_interfered"), QComboBox, ["False", "True"])),
            ("frequency [MHz]", H.create_field(state.get("imt_freq"))),
        ])
        H.add_grid_row(layout, 1, [
            ("bandwidth [MHz]", H.create_field(state.get("imt_bw"))),
            ("rb_bandwidth [MHz]", H.create_field(state.get("imt_rb_bw"))),
            ("spectral_mask", H.create_field(state.get("imt_spec_mask"), QComboBox, ["IMT-2020", "3GPP E-UTRA", "MSS"])),
        ])
        H.add_grid_row(layout, 2, [
            ("spurious_emissions [dBc]", H.create_field(state.get("imt_spurious"))),
            ("adjacent_antenna_model", H.create_field(state.get("imt_adj_ant_model"), QComboBox, ["SINGLE_ELEMENT", "BEAMFORMING"])),
            ("guard_band_ratio", H.create_field(state.get("imt_guard_ratio"))),
        ])
        parent_layout.addWidget(frm)

    @staticmethod
    def build_bs(parent_layout, state):
        frm = QGroupBox("BS – Parameters")
        layout = QHBoxLayout(frm)

        c1 = H.create_sub_column(layout, "BS – Basic")
        c1.addRow("load_probability", H.create_field(state.get("bs_load_prob")))
        c1.addRow("conducted_power [dBm]", H.create_field(state.get("bs_power")))
        c1.addRow("height [m]", H.create_field(state.get("bs_height")))
        c1.addRow("noise_figure [dB]", H.create_field(state.get("bs_nf")))
        c1.addRow("ohmic_loss [dB]", H.create_field(state.get("bs_ohmic")))

        c2 = H.create_sub_column(layout, "BS – Antenna Array")
        c2.addRow("normalization", H.create_field(state.get("bs_norm"), QComboBox, ["False", "True"]))
        c2.addRow("element_pattern", H.create_field(state.get("bs_elem_pat"), QComboBox, ["M2101", "ITU-R S.672", "Custom"]))
        c2.addRow("min_array_gain [dB]", H.create_field(state.get("bs_min_arr_gain")))
        H.add_range(c2, "h_beamsteer [deg]", state.get("bs_h_steer_min"), state.get("bs_h_steer_max"))
        H.add_range(c2, "v_beamsteer [deg]", state.get("bs_v_steer_min"), state.get("bs_v_steer_max"))
        c2.addRow("downtilt [deg]", H.create_field(state.get("bs_downtilt")))
        c2.addRow("element_max_g [dBi]", H.create_field(state.get("bs_elem_max_g")))
        c2.addRow("element_phi_3db [deg]", H.create_field(state.get("bs_phi3")))
        c2.addRow("element_theta_3db [deg]", H.create_field(state.get("bs_theta3")))
        c2.addRow("n_rows", H.create_field(state.get("bs_rows")))
        c2.addRow("n_columns", H.create_field(state.get("bs_cols")))
        c2.addRow("element_horiz_spacing [λ]", H.create_field(state.get("bs_elem_hs")))
        c2.addRow("element_vert_spacing [λ]", H.create_field(state.get("bs_elem_vs")))
        c2.addRow("element_am [dB]", H.create_field(state.get("bs_elem_am")))
        c2.addRow("element_sla_v [dB]", H.create_field(state.get("bs_elem_sla_v")))
        c2.addRow("multiplication_factor", H.create_field(state.get("bs_mult")))

        c3 = H.create_sub_column(layout, "BS – Sub-array")
        c3.addRow("is_enabled", H.create_field(state.get("bs_sub_enabled"), QComboBox, ["False", "True"]))
        c3.addRow("n_rows", H.create_field(state.get("bs_sub_rows")))
        c3.addRow("element_vert_spacing [λ]", H.create_field(state.get("bs_sub_evspace")))
        c3.addRow("eletrical_downtilt [deg]", H.create_field(state.get("bs_sub_e_downtilt")))
        
        parent_layout.addWidget(frm)

    @staticmethod
    def build_ue(parent_layout, state):
        frm = QGroupBox("UE – Parameters")
        layout = QHBoxLayout(frm)

        col1_layout = QVBoxLayout()
        layout.addLayout(col1_layout)

        c1 = H.create_sub_column(col1_layout, "UE – Basic")
        c1.addRow("k", H.create_field(state.get("ue_k")))
        c1.addRow("k_m", H.create_field(state.get("ue_km")))
        c1.addRow("indoor_percent [%]", H.create_field(state.get("ue_indoor")))
        
        cb_dist = H.create_field(state.get("ue_dist_type"), QComboBox, ["Macro_countries", "UNIFORM", "CELL", "UNIFORM_IN_CELL", "ANGLE_AND_DISTANCE"])
        c1.addRow("distribution_type", cb_dist)
        
        c1.addRow("tx_power_control", H.create_field(state.get("ue_tx_power_ctrl"), QComboBox, ["False", "True"]))
        c1.addRow("p_o_pusch [dBm]", H.create_field(state.get("ue_p_o_pusch")))
        c1.addRow("alpha", H.create_field(state.get("ue_alpha")))
        c1.addRow("p_cmax [dBm]", H.create_field(state.get("ue_p_cmax")))
        c1.addRow("power_dynamic_range [dB]", H.create_field(state.get("ue_p_dyn")))
        c1.addRow("height [m]", H.create_field(state.get("ue_height")))
        c1.addRow("noise_figure [dB]", H.create_field(state.get("ue_nf")))
        c1.addRow("ohmic_loss [dB]", H.create_field(state.get("ue_ohmic")))
        c1.addRow("body_loss [dB]", H.create_field(state.get("ue_body_loss")))

        col_dist = QGroupBox("UE – Distribution (Angle&Distance)")
        col1_layout.addWidget(col_dist)
        col_dist_layout = QFormLayout(col_dist)
        
        col_dist_layout.addRow("distribution_distance", H.create_field(state.get("ue_dist_distance"), QComboBox, ["RAYLEIGH", "UNIFORM", "SQRT(UNIFORM)"]))
        col_dist_layout.addRow("distribution_azimuth", H.create_field(state.get("ue_dist_azimuth"), QComboBox, ["NORMAL", "UNIFORM"]))
        H.add_range(col_dist_layout, "azimuth_range [deg]", state.get("ue_az_min"), state.get("ue_az_max"))

        def _toggle_dist(text=None):
            is_angle = state.get("ue_dist_type").get().upper() == "ANGLE_AND_DISTANCE"
            col_dist.setVisible(is_angle)
            
        cb_dist.currentTextChanged.connect(_toggle_dist)
        _toggle_dist()

        c2 = H.create_sub_column(layout, "UE – Antenna Array")
        c2.addRow("normalization", H.create_field(state.get("ue_norm"), QComboBox, ["False", "True"]))
        c2.addRow("element_pattern", H.create_field(state.get("ue_elem_pat"), QComboBox, ["FIXED", "M2101", "Custom"]))
        c2.addRow("min_array_gain [dB]", H.create_field(state.get("ue_min_arr_gain")))
        c2.addRow("element_max_g [dBi]", H.create_field(state.get("ue_elem_max_g")))
        c2.addRow("element_phi_3db [deg]", H.create_field(state.get("ue_phi3")))
        c2.addRow("element_theta_3db [deg]", H.create_field(state.get("ue_theta3")))
        c2.addRow("n_rows", H.create_field(state.get("ue_rows")))
        c2.addRow("n_columns", H.create_field(state.get("ue_cols")))
        c2.addRow("element_am [dB]", H.create_field(state.get("ue_elem_am")))
        c2.addRow("element_sla_v [dB]", H.create_field(state.get("ue_elem_sla_v")))
        c2.addRow("multiplication_factor", H.create_field(state.get("ue_mult")))

        c3 = H.create_sub_column(layout, "UE – Sub-array")
        c3.addRow("is_enabled", H.create_field(state.get("ue_sub_enabled"), QComboBox, ["False", "True"]))
        c3.addRow("n_rows", H.create_field(state.get("ue_sub_rows")))
        c3.addRow("element_vert_spacing [λ]", H.create_field(state.get("ue_sub_evspace")))
        c3.addRow("eletrical_downtilt [deg]", H.create_field(state.get("ue_sub_e_downtilt")))

        parent_layout.addWidget(frm)

    @staticmethod
    def build_channel(parent_layout, state):
        frm = QGroupBox("UL / DL / Channel / Shadowing")
        layout = QGridLayout(frm)

        H.add_grid_row(layout, 0, [
            ("uplink.attenuation_factor", H.create_field(state.get("ul_att"))),
            ("uplink.sinr_min / max [dB]", H.pair_entries(state.get("ul_sinr_min"), state.get("ul_sinr_max"))),
            ("downlink.attenuation_factor", H.create_field(state.get("dl_att"))),
        ])
        H.add_grid_row(layout, 1, [
            ("downlink.sinr_min / max [dB]", H.pair_entries(state.get("dl_sinr_min"), state.get("dl_sinr_max"))),
            ("channel_model", H.create_field(state.get("ch_model"))),
            ("shadowing", H.create_field(state.get("shadowing"), QComboBox, ["False", "True"])),
        ])
        parent_layout.addWidget(frm)