from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QStackedWidget, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt

from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper as H
from ui.tabs.assets.ses_tab.ses_pattern_controller import (
    LOC_TYPES, AZ_EL_TYPES, SUPPORTED_ANTENNA_PATTERNS, DIAMETER_PATTERNS, CHANNEL_MODELS
)

class SESBasicSection:
    @staticmethod
    def build(parent_layout, app):
        frm = QGroupBox("Basic Parameters")
        layout = QGridLayout(frm)

        H.add_grid_row(layout, 0, [
            ("frequency [MHz]", H.create_field(app.se_frequency)),
            ("bandwidth [MHz]", H.create_field(app.se_bandwidth)),
            ("noise_temperature [K]", H.create_field(app.se_noise_temperature)),
        ])
        H.add_grid_row(layout, 1, [
            ("adjacent_ch_reception", H.create_field(app.se_adjacent_ch_reception, QComboBox, ["ACS", "OFF"])),
            ("adjacent_ch_selectivity [dB]", H.create_field(app.se_adjacent_ch_selectivity)),
            ("adjacent_ch_emissions", H.create_field(app.se_adjacent_ch_emissions, QComboBox, ["ACLR", "SPECTRAL_MASK", "OFF"])),
        ])
        H.add_grid_row(layout, 2, [
            ("adjacent_ch_leak_ratio [dB]", H.create_field(app.se_adjacent_ch_leak_ratio)),
            ("spectral_mask", H.create_field(app.se_spectral_mask)),
            ("spurious_emissions [dBm/MHz]", H.create_field(app.se_spurious_emissions)),
        ])
        H.add_grid_row(layout, 3, [
            ("tx_power_density [dBW/Hz]", H.create_field(app.se_tx_power_density)),
            ("height [m]", H.create_field(app.se_height)),
            ("polarization_loss [dB] (opt.)", H.create_field(app.se_polarization_loss)),
        ])
        parent_layout.addWidget(frm)


class SESGeometrySection:
    def __init__(self, parent_layout, app):
        self.app = app
        self.frame = QGroupBox("Geometry")
        self.main_layout = QVBoxLayout(self.frame)

        self._build_location_ui()
        self._build_pointing_ui()
        
        parent_layout.addWidget(self.frame)

    def _build_location_ui(self):
        box = QGroupBox("Location")
        l = QVBoxLayout(box)

        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("location.type"))
        row_type.addWidget(H.create_field(self.app.se_loc_type, QComboBox, LOC_TYPES))
        row_type.addStretch()
        l.addLayout(row_type)

        self.loc_stack = QStackedWidget()
        l.addWidget(self.loc_stack)
        self.loc_frames = {}

        # FIXED
        f_fix = QWidget()
        l_fix = QGridLayout(f_fix)
        H.add_grid_row(l_fix, 0, [("x [m]", H.create_field(self.app.se_loc_fixed_x)), ("y [m]", H.create_field(self.app.se_loc_fixed_y)), ("", None)])
        self.loc_frames["FIXED"] = f_fix
        self.loc_stack.addWidget(f_fix)

        # CELL
        f_cell = QWidget()
        l_cell = QGridLayout(f_cell)
        H.add_grid_row(l_cell, 0, [("cell.min_dist_to_bs [m]", H.create_field(self.app.se_loc_cell_min_dist_to_bs)), ("", None), ("", None)])
        self.loc_frames["CELL"] = f_cell
        self.loc_stack.addWidget(f_cell)

        # NETWORK
        f_net = QWidget()
        l_net = QGridLayout(f_net)
        H.add_grid_row(l_net, 0, [("network.min_dist_to_bs [m]", H.create_field(self.app.se_loc_network_min_dist_to_bs)), ("", None), ("", None)])
        self.loc_frames["NETWORK"] = f_net
        self.loc_stack.addWidget(f_net)

        # UNIFORM_DIST
        f_ud = QWidget()
        l_ud = QGridLayout(f_ud)
        H.add_grid_row(l_ud, 0, [("min_dist_to_center [m]", H.create_field(self.app.se_loc_ud_min_dist_to_center)), ("max_dist_to_center [m]", H.create_field(self.app.se_loc_ud_max_dist_to_center)), ("", None)])
        self.loc_frames["UNIFORM_DIST"] = f_ud
        self.loc_stack.addWidget(f_ud)
        
        self.empty_loc = QWidget()
        self.loc_stack.addWidget(self.empty_loc)

        self.app.se_loc_type.value_changed.connect(self.refresh_location)
        self.main_layout.addWidget(box)

    def _build_pointing_ui(self):
        box = QGroupBox("Antenna Pointing (Azimuth / Elevation)")
        l = QHBoxLayout(box)

        c_az = QGroupBox("Azimuth")
        c_el = QGroupBox("Elevation")
        l.addWidget(c_az)
        l.addWidget(c_el)

        self.az_frames, self.az_hint, self.az_stack = self._build_angle_col(
            c_az, self.app.se_az_type, self.app.se_az_fixed, self.app.se_az_ud_min, self.app.se_az_ud_max)
        self.app.se_az_type.value_changed.connect(self.refresh_az)

        self.el_frames, self.el_hint, self.el_stack = self._build_angle_col(
            c_el, self.app.se_el_type, self.app.se_el_fixed, self.app.se_el_ud_min, self.app.se_el_ud_max)
        self.app.se_el_type.value_changed.connect(self.refresh_el)

        self.main_layout.addWidget(box)

    def _build_angle_col(self, parent, var_type, var_fixed, var_min, var_max):
        l = QVBoxLayout(parent)
        
        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("type"))
        row_type.addWidget(H.create_field(var_type, QComboBox, AZ_EL_TYPES))
        l.addLayout(row_type)

        stack = QStackedWidget()
        l.addWidget(stack)
        frames = {}

        # Fixed
        f_fix = QWidget()
        l_fix = QHBoxLayout(f_fix)
        l_fix.setContentsMargins(0,0,0,0)
        l_fix.addWidget(QLabel("fixed [deg]"))
        l_fix.addWidget(H.create_field(var_fixed))
        l_fix.addStretch()
        frames["FIXED"] = f_fix
        stack.addWidget(f_fix)

        # Uniform
        f_ud = QWidget()
        l_ud = QHBoxLayout(f_ud)
        l_ud.setContentsMargins(0,0,0,0)
        l_ud.addWidget(QLabel("min"))
        l_ud.addWidget(H.create_field(var_min))
        l_ud.addWidget(QLabel("max"))
        l_ud.addWidget(H.create_field(var_max))
        frames["UNIFORM_DIST"] = f_ud
        stack.addWidget(f_ud)

        # Hint
        hint = QLabel("(Automatic)")
        hint.setStyleSheet("color: #555;")
        stack.addWidget(hint)
        
        empty = QWidget()
        stack.addWidget(empty)
        stack.setCurrentWidget(empty)

        return frames, hint, stack

    def refresh_location(self, *args):
        t = str(self.app.se_loc_type.get() or "").strip()
        if t in self.loc_frames:
            self.loc_stack.setCurrentWidget(self.loc_frames[t])
        else:
            self.loc_stack.setCurrentWidget(self.empty_loc)

    def refresh_az(self, *args):
        t = str(self.app.se_az_type.get() or "").strip()
        if t in self.az_frames:
            self.az_stack.setCurrentWidget(self.az_frames[t])
        elif t == "POINTING_AT_IMT_CENTER":
            self.az_stack.setCurrentWidget(self.az_hint)

    def refresh_el(self, *args):
        t = str(self.app.se_el_type.get() or "").strip()
        if t in self.el_frames:
            self.el_stack.setCurrentWidget(self.el_frames[t])
        elif t == "POINTING_AT_IMT_CENTER":
            self.el_stack.setCurrentWidget(self.el_hint)

    def refresh_all(self):
        self.refresh_location()
        self.refresh_az()
        self.refresh_el()


class SESAntennaSection:
    """Antena da estação terrena: todos os padrões do motor, com parâmetros e ganho ao vivo."""

    def __init__(self, parent_layout, app):
        self.app = app
        self.frame = QGroupBox("Antenna")
        self.main_layout = QVBoxLayout(self.frame)
        from core.state import SharcVar
        from ui.components.antenna_editor import AntennaEditor

        def get_var(name):
            v = getattr(app, name, None)
            if v is None:
                v = SharcVar("")
                setattr(app, name, v)
            return v

        self.editor = AntennaEditor(get_var, pattern_key="se_ant_pattern",
                                    gain_key="se_ant_gain", prefix="se_ant")
        self.main_layout.addWidget(self.editor)
        parent_layout.addWidget(self.frame)

    def refresh(self, *args):  # compatibilidade com o código antigo
        pass


class SESChannelSection:
    def __init__(self, parent_layout, app):
        self.app = app
        self.frame = QGroupBox("Channel Model")
        self.main_layout = QVBoxLayout(self.frame)

        grid = QGridLayout()
        H.add_grid_row(grid, 0, [
            ("channel_model", H.create_field(app.se_channel_model, QComboBox, CHANNEL_MODELS)),
            ("", None), ("", None)
        ])
        self.main_layout.addLayout(grid)

        # P.452 Frame
        self.p452_box = QGroupBox("P452 Parameters")
        l_p452 = QGridLayout(self.p452_box)

        H.add_grid_row(l_p452, 0, [("atmospheric_pressure [hPa]", H.create_field(app.p452_atmospheric_pressure)), ("air_temperature [K]", H.create_field(app.p452_air_temperature)), ("p_452 [%]", H.create_field(app.p452_percentage_p))])
        H.add_grid_row(l_p452, 1, [("N0", H.create_field(app.p452_N0)), ("delta_N", H.create_field(app.p452_delta_N)), ("polarization", H.create_field(app.p452_polarization))])
        H.add_grid_row(l_p452, 2, [("Dct [km]", H.create_field(app.p452_Dct)), ("Dcr [km]", H.create_field(app.p452_Dcr)), ("", None)])
        
        # Read-only heights
        hte = H.create_field(app.p452_Hte)
        hte.setReadOnly(True)
        hre = H.create_field(app.p452_Hre)
        hre.setReadOnly(True)
        H.add_grid_row(l_p452, 3, [("Hte [m] (auto)", hte), ("Hre [m] (auto)", hre), ("clutter_loss", H.create_field(app.p452_clutter_loss, QCheckBox))])

        self.clutter_row = QWidget()
        l_clut = QHBoxLayout(self.clutter_row)
        l_clut.setContentsMargins(0,0,0,0)
        l_clut.addWidget(QLabel("clutter_type"))
        l_clut.addWidget(H.create_field(app.p452_clutter_type, QComboBox, ["one_end", "both_ends"]))
        l_clut.addStretch()
        l_p452.addWidget(self.clutter_row, 4, 0, 1, 6)

        H.add_grid_row(l_p452, 5, [("tx_lat [deg]", H.create_field(app.p452_tx_lat)), ("rx_lat [deg]", H.create_field(app.p452_rx_lat)), ("is_terrain", H.create_field(app.p452_is_terrain, QCheckBox))])

        self.main_layout.addWidget(self.p452_box)

        self.app.se_channel_model.value_changed.connect(self.refresh)
        self.app.p452_clutter_loss.value_changed.connect(self.refresh_clutter)
        
        parent_layout.addWidget(self.frame)

    def refresh(self, *args):
        is_p452 = str(self.app.se_channel_model.get() or "").strip() == "P452"
        self.p452_box.setVisible(is_p452)
        self.refresh_clutter()

    def refresh_clutter(self, *args):
        is_p452 = str(self.app.se_channel_model.get() or "").strip() == "P452"
        has_clutter = str(self.app.p452_clutter_loss.get()).lower() in ("true", "1")
        self.clutter_row.setVisible(is_p452 and has_clutter)