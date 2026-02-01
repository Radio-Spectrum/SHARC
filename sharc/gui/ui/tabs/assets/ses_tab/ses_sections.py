import tkinter as tk
from tkinter import ttk
from utils import add_row_three
from ui.tabs.assets.ses_tab.ses_pattern_controller import *


class SESBasicSection:
    @staticmethod
    def build(parent, app):
        frm = ttk.LabelFrame(parent, text="Basic Parameters")
        frm.pack(fill="x", padx=2, pady=4)

        add_row_three(frm, 0, [
            ("frequency [MHz]", ttk.Entry(
                frm, textvariable=app.se_frequency, width=12)),
            ("bandwidth [MHz]", ttk.Entry(
                frm, textvariable=app.se_bandwidth, width=12)),
            ("noise_temperature [K]", ttk.Entry(
                frm, textvariable=app.se_noise_temperature, width=12)),
        ])
        add_row_three(frm, 1, [
            ("adjacent_ch_reception", ttk.Combobox(frm, textvariable=app.se_adjacent_ch_reception,
             values=["ACS", "OFF"], width=12, state="readonly")),
            ("adjacent_ch_selectivity [dB]", ttk.Entry(
                frm, textvariable=app.se_adjacent_ch_selectivity, width=12)),
            ("adjacent_ch_emissions", ttk.Combobox(frm, textvariable=app.se_adjacent_ch_emissions,
             values=["ACLR", "SPECTRAL_MASK", "OFF"], width=14, state="readonly")),
        ])
        add_row_three(frm, 2, [
            ("adjacent_ch_leak_ratio [dB]", ttk.Entry(
                frm, textvariable=app.se_adjacent_ch_leak_ratio, width=12)),
            ("spectral_mask", ttk.Entry(
                frm, textvariable=app.se_spectral_mask, width=18)),
            ("spurious_emissions [dBm/MHz]", ttk.Entry(frm,
             textvariable=app.se_spurious_emissions, width=14)),
        ])
        add_row_three(frm, 3, [
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm,
             textvariable=app.se_tx_power_density, width=14)),
            ("height [m]", ttk.Entry(
                frm, textvariable=app.se_height, width=12)),
            ("polarization_loss [dB] (opt.)", ttk.Entry(
                frm, textvariable=app.se_polarization_loss, width=12)),
        ])


class SESGeometrySection:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.LabelFrame(parent, text="Geometry")
        self.frame.pack(fill="x", padx=2, pady=4)

        self._build_location_ui()
        self._build_pointing_ui()

    def _build_location_ui(self):
        box = ttk.LabelFrame(self.frame, text="Location")
        box.pack(fill="x", padx=2, pady=(6, 6))

        add_row_three(box, 0, [
            ("location.type", ttk.Combobox(box, textvariable=self.app.se_loc_type,
             values=LOC_TYPES, width=14, state="readonly")),
            ("", ttk.Label(box, text="")), ("", ttk.Label(box, text="")),
        ])

        self.loc_frames = {}
        # Fixed
        f_fix = ttk.Frame(box)
        add_row_three(f_fix, 0, [("x [m]", ttk.Entry(f_fix, textvariable=self.app.se_loc_fixed_x, width=12)), ("y [m]", ttk.Entry(
            f_fix, textvariable=self.app.se_loc_fixed_y, width=12)), ("", ttk.Label(f_fix, text=""))])
        self.loc_frames["FIXED"] = f_fix

        # Cell
        f_cell = ttk.Frame(box)
        add_row_three(f_cell, 0, [("cell.min_dist_to_bs [m]", ttk.Entry(
            f_cell, textvariable=self.app.se_loc_cell_min_dist_to_bs, width=14)), ("", ttk.Label(f_cell, text="")), ("", ttk.Label(f_cell, text=""))])
        self.loc_frames["CELL"] = f_cell

        # Network
        f_net = ttk.Frame(box)
        add_row_three(f_net, 0, [("network.min_dist_to_bs [m]", ttk.Entry(
            f_net, textvariable=self.app.se_loc_network_min_dist_to_bs, width=14)), ("", ttk.Label(f_net, text="")), ("", ttk.Label(f_net, text=""))])
        self.loc_frames["NETWORK"] = f_net

        # Uniform
        f_ud = ttk.Frame(box)
        add_row_three(f_ud, 0, [("min_dist_to_center [m]", ttk.Entry(f_ud, textvariable=self.app.se_loc_ud_min_dist_to_center, width=18)), (
            "max_dist_to_center [m]", ttk.Entry(f_ud, textvariable=self.app.se_loc_ud_max_dist_to_center, width=18)), ("", ttk.Label(f_ud, text=""))])
        self.loc_frames["UNIFORM_DIST"] = f_ud

        # Pack all hidden initially
        for f in self.loc_frames.values():
            f.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
            f.grid_remove()

        self.app.se_loc_type.trace_add("write", self.refresh_location)

    def _build_pointing_ui(self):

        box = ttk.LabelFrame(
            self.frame, text="Antenna Pointing (Azimuth / Elevation)")
        box.pack(fill="x", padx=2, pady=(0, 6))

        c_az = ttk.LabelFrame(box, text="Azimuth")
        c_el = ttk.LabelFrame(box, text="Elevation")
        c_az.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        c_el.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)

        # Azimuth Logic
        self.az_frames = {}
        self.az_hint = None
        self._build_angle_col(c_az, self.app.se_az_type, self.app.se_az_fixed,
                              self.app.se_az_ud_min, self.app.se_az_ud_max,
                              self.az_frames, is_az=True)
        self.app.se_az_type.trace_add("write", self.refresh_az)

        # Elevation Logic
        self.el_frames = {}
        self.el_hint = None
        self._build_angle_col(c_el, self.app.se_el_type, self.app.se_el_fixed,
                              self.app.se_el_ud_min, self.app.se_el_ud_max,
                              self.el_frames, is_az=False)
        self.app.se_el_type.trace_add("write", self.refresh_el)

    def _build_angle_col(self, parent, var_type, var_fixed, var_min, var_max, frame_dict, is_az):
        ttk.Label(parent, text="type").grid(
            row=0, column=0, sticky="w", padx=4)
        ttk.Combobox(parent, textvariable=var_type, values=AZ_EL_TYPES, width=22,
                     state="readonly").grid(row=0, column=1, sticky="w", padx=4)

        # Fixed
        f_fix = ttk.Frame(parent)
        f_fix.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(f_fix, text="fixed [deg]").pack(side="left")
        ttk.Entry(f_fix, textvariable=var_fixed,
                  width=12).pack(side="left", padx=4)
        frame_dict["FIXED"] = f_fix

        # Uniform
        f_ud = ttk.Frame(parent)
        f_ud.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(f_ud, text="min").pack(side="left")
        ttk.Entry(f_ud, textvariable=var_min,
                  width=8).pack(side="left", padx=2)
        ttk.Label(f_ud, text="max").pack(side="left", padx=(4, 0))
        ttk.Entry(f_ud, textvariable=var_max,
                  width=8).pack(side="left", padx=2)
        frame_dict["UNIFORM_DIST"] = f_ud

        # Hint
        lbl = ttk.Label(parent, text="(Automatic)", foreground="#555")
        lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
        if is_az:
            self.az_hint = lbl
        else:
            self.el_hint = lbl

        # Initial Hide
        f_fix.grid_remove()
        f_ud.grid_remove()
        lbl.grid_remove()

    def refresh_location(self, *args):
        t = (self.app.se_loc_type.get() or "").strip()
        for f in self.loc_frames.values():
            f.grid_remove()
        if t in self.loc_frames:
            self.loc_frames[t].grid()

    def refresh_az(self, *args):
        t = (self.app.se_az_type.get() or "").strip()
        for f in self.az_frames.values():
            f.grid_remove()
        self.az_hint.grid_remove()
        if t in self.az_frames:
            self.az_frames[t].grid()
        elif t == "POINTING_AT_IMT_CENTER":
            self.az_hint.grid()

    def refresh_el(self, *args):
        t = (self.app.se_el_type.get() or "").strip()
        for f in self.el_frames.values():
            f.grid_remove()
        self.el_hint.grid_remove()
        if t in self.el_frames:
            self.el_frames[t].grid()
        elif t == "POINTING_AT_IMT_CENTER":
            self.el_hint.grid()

    def refresh_all(self):
        self.refresh_location()
        self.refresh_az()
        self.refresh_el()


class SESAntennaSection:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.LabelFrame(
            parent, text="Antenna (Pattern + Parameters)")
        self.frame.pack(fill="x", padx=2, pady=4)

        add_row_three(self.frame, 0, [
            ("antenna.pattern", ttk.Combobox(self.frame, textvariable=app.se_ant_pattern,
             values=SUPPORTED_ANTENNA_PATTERNS, width=28, state="readonly")),
            ("antenna.gain [dBi]", ttk.Entry(
                self.frame, textvariable=app.se_ant_gain, width=12)), ("", ttk.Label(self.frame, text="")),
        ])

        self.frames = {}

        # Diameter-based
        f_diam = ttk.Frame(self.frame)
        add_row_three(f_diam, 0, [("diameter [m]", ttk.Entry(f_diam, textvariable=app.se_ant_diameter, width=12)), (
            "", ttk.Label(f_diam, text="(freq & gain from system)")), ("", ttk.Label(f_diam, text=""))])
        self.frames["DIAM"] = f_diam

        # Envelope
        f_env = ttk.Frame(self.frame)
        add_row_three(f_env, 0, [("envelope_gain [dB]", ttk.Entry(
            f_env, textvariable=app.se_ant_envelope_gain, width=12)), ("", ttk.Label(f_env, text="")), ("", ttk.Label(f_env, text=""))])
        self.frames["MODIFIED ITU-R S.465"] = f_env

        # S.672
        f_s672 = ttk.Frame(self.frame)
        add_row_three(f_s672, 0, [("antenna_3_dB [deg]", ttk.Entry(f_s672, textvariable=app.se_ant_3db, width=12)), (
            "antenna_l_s [dB] (opt.)", ttk.Entry(f_s672, textvariable=app.se_ant_l_s, width=12)), ("", ttk.Label(f_s672, text=""))])
        self.frames["ITU-R S.672"] = f_s672

        # F1245
        f_f1245 = ttk.Frame(self.frame)
        add_row_three(f_f1245, 0, [("gain (F1245) [dB]", ttk.Entry(f_f1245, textvariable=app.se_ant_f1245_gain, width=12)), ("diameter [m]", ttk.Entry(
            f_f1245, textvariable=app.se_ant_f1245_diameter, width=12)), ("frequency [MHz]", ttk.Entry(f_f1245, textvariable=app.se_ant_f1245_frequency, width=12))])
        self.frames["ITU-R F.1245_fs"] = f_f1245

        # Hint
        self.hint = ttk.Label(
            self.frame, text="Select a pattern to view specific parameters.")

        for f in self.frames.values():
            f.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
            f.grid_remove()
        self.hint.grid(row=1, column=0, sticky="w", pady=6)
        self.hint.grid_remove()

        self.app.se_ant_pattern.trace_add("write", self.refresh)

    def refresh(self, *args):
        pat = (self.app.se_ant_pattern.get() or "").strip()
        for f in self.frames.values():
            f.grid_remove()
        self.hint.grid_remove()

        if not pat:
            self.hint.grid()
        elif pat in DIAMETER_PATTERNS:
            self.frames["DIAM"].grid()
        elif pat in self.frames:
            self.frames[pat].grid()
        else:
            self.hint.grid()


class SESChannelSection:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.LabelFrame(parent, text="Channel Model")
        self.frame.pack(fill="x", padx=2, pady=4)

        add_row_three(self.frame, 0, [
            ("channel_model", ttk.Combobox(self.frame, textvariable=app.se_channel_model,
             values=CHANNEL_MODELS, width=10, state="readonly")),
            ("", ttk.Label(self.frame, text="")
             ), ("", ttk.Label(self.frame, text=""))
        ])

        # P.452 Frame
        self.p452_box = ttk.LabelFrame(self.frame, text="P452 Parameters")
        self.p452_box.grid(row=1, column=0, columnspan=6,
                           sticky="ew", padx=2, pady=(6, 2))

        add_row_three(self.p452_box, 0, [("atmospheric_pressure [hPa]", ttk.Entry(self.p452_box, textvariable=app.p452_atmospheric_pressure, width=12)), ("air_temperature [K]", ttk.Entry(
            self.p452_box, textvariable=app.p452_air_temperature, width=12)), ("p_452 [%]", ttk.Entry(self.p452_box, textvariable=app.p452_percentage_p, width=12))])
        add_row_three(self.p452_box, 1, [("N0", ttk.Entry(self.p452_box, textvariable=app.p452_N0, width=12)), ("delta_N", ttk.Entry(
            self.p452_box, textvariable=app.p452_delta_N, width=12)), ("polarization", ttk.Entry(self.p452_box, textvariable=app.p452_polarization, width=12))])
        add_row_three(self.p452_box, 2, [("Dct [km]", ttk.Entry(self.p452_box, textvariable=app.p452_Dct, width=12)), (
            "Dcr [km]", ttk.Entry(self.p452_box, textvariable=app.p452_Dcr, width=12)), ("", ttk.Label(self.p452_box, text=""))])
        add_row_three(self.p452_box, 3, [("Hte [m]", ttk.Entry(self.p452_box, textvariable=app.p452_Hte, width=12, state="readonly")), ("Hre [m]", ttk.Entry(
            self.p452_box, textvariable=app.p452_Hre, width=12, state="readonly")), ("clutter_loss", ttk.Checkbutton(self.p452_box, variable=app.p452_clutter_loss))])

        self.clutter_row = ttk.Frame(self.p452_box)
        self.clutter_row.grid(row=4, column=0, columnspan=6,
                              sticky="ew", pady=(2, 0))
        self.clutter_row.columnconfigure(0, weight=1)
        ttk.Label(self.clutter_row, text="clutter_type").grid(
            row=0, column=1, sticky="e", padx=4)
        ttk.Combobox(self.clutter_row, textvariable=app.p452_clutter_type, values=[
                     "one_end", "both_ends"], width=12, state="readonly").grid(row=0, column=2, sticky="w", padx=4)

        add_row_three(self.p452_box, 5, [("tx_lat [deg]", ttk.Entry(self.p452_box, textvariable=app.p452_tx_lat, width=12)), ("rx_lat [deg]", ttk.Entry(
            self.p452_box, textvariable=app.p452_rx_lat, width=12)), ("is_terrain", ttk.Checkbutton(self.p452_box, variable=app.p452_is_terrain))])

        self.app.se_channel_model.trace_add("write", self.refresh)
        self.app.p452_clutter_loss.trace_add("write", self.refresh_clutter)

    def refresh(self, *args):
        if (self.app.se_channel_model.get() or "").strip() == "P452":
            self.p452_box.grid()
        else:
            self.p452_box.grid_remove()
        self.refresh_clutter()

    def refresh_clutter(self, *args):
        is_p452 = (self.app.se_channel_model.get() or "").strip() == "P452"
        if is_p452 and bool(self.app.p452_clutter_loss.get()):
            self.clutter_row.grid()
        else:
            self.clutter_row.grid_remove()
