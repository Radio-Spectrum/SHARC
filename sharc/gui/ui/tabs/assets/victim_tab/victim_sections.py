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
    def __init__(self, parent_layout, state):
        self.state = state
        self.frame = QGroupBox("Antenna")
        self.main_layout = QVBoxLayout(self.frame)

        self._build_ui()
        parent_layout.addWidget(self.frame)

    def _build_ui(self):
        # Pattern Selector
        grid_top = QGridLayout()
        H.add_grid_row(grid_top, 0, [
            ("pattern", H.create_field(self.state.get("v_ant_pattern"), QComboBox, ["ITU-R S.672", "ITU-R M.2101", "3GPP TR 38.901", "Custom"])),
            ("gain [dBi]", H.create_field(self.state.get("v_ant_gain"))),
            ("", None),
        ])
        self.main_layout.addLayout(grid_top)

        # Stacked area for dynamically switching the parameters
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        # S.672 Frame
        self.frm_s672 = QWidget()
        l_s672 = QGridLayout(self.frm_s672)
        l_s672.setContentsMargins(0, 0, 0, 0)
        H.add_grid_row(l_s672, 0, [
            ("itu_r_s_672.antenna_3_dB", H.create_field(self.state.get("v_s672_3db"))),
            ("itu_r_s_672.antenna_l_s [dB]", H.create_field(self.state.get("v_s672_ls"))),
            ("", None),
        ])
        self.stack.addWidget(self.frm_s672)

        # Other Frame
        self.frm_other = QWidget()
        l_other = QVBoxLayout(self.frm_other)
        l_other.setContentsMargins(0, 0, 0, 0)
        lbl_other = QLabel("Parameters for this pattern not yet implemented in GUI.")
        lbl_other.setStyleSheet("color: gray; font-style: italic;")
        l_other.addWidget(lbl_other)
        self.stack.addWidget(self.frm_other)

        # Setup Traces
        self.state.get("v_ant_pattern").value_changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *args):
        """Toggles S.672 parameters visibility."""
        pattern = str(self.state.get("v_ant_pattern").get() or "").strip()
        if pattern == "ITU-R S.672":
            self.stack.setCurrentWidget(self.frm_s672)
        else:
            self.stack.setCurrentWidget(self.frm_other)