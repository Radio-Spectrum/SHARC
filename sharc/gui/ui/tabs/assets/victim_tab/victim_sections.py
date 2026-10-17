from PySide6.QtWidgets import (
    QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QCheckBox, QStackedWidget, QWidget
)

from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper as H

class VictimBasicSection:
    @staticmethod
    def build(parent_layout, state):
        frm = QGroupBox("Basic Parameters")
        layout = QGridLayout(frm)

        H.add_grid_row(layout, 0, [
            ("frequency [MHz]", H.create_field(state.get("v_freq"))),
            ("bandwidth [MHz]", H.create_field(state.get("v_bw"))),
            ("tx_power_density [dBW/Hz]", H.create_field(state.get("v_txpsd"))),
        ])
        H.add_grid_row(layout, 1, [
            ("polarization_loss [dB]", H.create_field(state.get("v_pol_loss"))),
            ("noise_temperature [K]", H.create_field(state.get("v_tnoise"))),
            ("channel_model", H.create_field(state.get("v_ch_model"), QComboBox, ["P619", "FSPL"])),
        ])
        H.add_grid_row(layout, 2, [
            ("season", H.create_field(state.get("v_season"), QComboBox, ["SUMMER", "WINTER"])),
            ("Spherical Earth?", H.create_field(state.get("ss_is_global_cs"), QCheckBox)),
            ("", None),
        ])
        parent_layout.addWidget(frm)


class VictimP619Section:
    @staticmethod
    def build(parent_layout, state):
        # ITU-R P.619 models propagation loss accounting for atmospheric gases and clutter.
        frm = QGroupBox("P619 Parameters")
        layout = QGridLayout(frm)

        H.add_grid_row(layout, 0, [
            ("mean_clutter_height", H.create_field(state.get("v_p619_clutter"), QComboBox, ["Low", "Mid", "High"])),
            ("below_rooftop [%]", H.create_field(state.get("v_p619_below_rooftop"))),
            ("", None),
        ])
        parent_layout.addWidget(frm)


class VictimGeometrySection:
    @staticmethod
    def build(parent_layout, state):
        wrap = QGroupBox("Geometry – Classes")
        wrap_layout = QVBoxLayout(wrap)

        # Spacecraft
        frm_sc = QGroupBox("Spacecraft – Location (FIXED/GEO)")
        l_sc = QGridLayout(frm_sc)
        H.add_grid_row(l_sc, 0, [
            ("altitude [m] (sat)", H.create_field(state.get("v_alt"))),
            ("location.fixed.lat_deg", H.create_field(state.get("v_fix_lat"))),
            ("location.fixed.long_deg", H.create_field(state.get("v_fix_lon"))),
        ])
        wrap_layout.addWidget(frm_sc)

        # Earth Station
        frm_es = QGroupBox("Earth Station – Reference Point on Earth")
        l_es = QGridLayout(frm_es)
        H.add_grid_row(l_es, 0, [
            ("es_altitude [m]", H.create_field(state.get("v_es_alt"))),
            ("es_lat_deg", H.create_field(state.get("v_es_lat"))),
            ("es_long_deg", H.create_field(state.get("v_es_lon"))),
        ])
        wrap_layout.addWidget(frm_es)

        # Pointing
        frm_pt = QGroupBox("Pointing (Export Only)")
        l_pt = QGridLayout(frm_pt)
        H.add_grid_row(l_pt, 0, [
            ("azimuth.type", H.create_field(state.get("v_az_type"), QComboBox, ["POINTING_AT_IMT", "FIXED"])),
            ("elevation.type", H.create_field(state.get("v_el_type"), QComboBox, ["POINTING_AT_IMT", "FIXED"])),
            ("", None),
        ])
        wrap_layout.addWidget(frm_pt)

        parent_layout.addWidget(wrap)


class VictimAntennaSection:
    """Antena do sistema vítima: todos os padrões do motor, com parâmetros e ganho ao vivo."""

    def __init__(self, parent_layout, state):
        self.state = state
        self.frame = QGroupBox("Antenna")
        self.main_layout = QVBoxLayout(self.frame)
        from ui.components.antenna_editor import AntennaEditor
        self.editor = AntennaEditor(
            state.get, pattern_key="v_ant_pattern", gain_key="v_ant_gain", prefix="v_ant")
        self.main_layout.addWidget(self.editor)
        parent_layout.addWidget(self.frame)
