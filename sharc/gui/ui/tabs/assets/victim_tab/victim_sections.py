import tkinter as tk
from tkinter import ttk
from utils import add_row_three


class VictimBasicSection:
    @staticmethod
    def build(parent, state):
        frm = ttk.LabelFrame(parent, text="Basic Parameters")
        frm.pack(fill="x", padx=2, pady=4)

        add_row_three(frm, 0, [
            ("frequency [MHz]", ttk.Entry(
                frm, textvariable=state.get("v_freq"), width=10)),
            ("bandwidth [MHz]", ttk.Entry(
                frm, textvariable=state.get("v_bw"), width=10)),
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm,
             textvariable=state.get("v_txpsd"), width=12)),
        ])
        add_row_three(frm, 1, [
            ("polarization_loss [dB]", ttk.Entry(
                frm, textvariable=state.get("v_pol_loss"), width=10)),
            ("noise_temperature [K]", ttk.Entry(
                frm, textvariable=state.get("v_tnoise"), width=10)),
            ("channel_model", ttk.Combobox(frm, textvariable=state.get(
                "v_ch_model"), values=["P619", "FSPL"], state="readonly", width=12)),
        ])

        chk_sphere = ttk.Checkbutton(
            frm, variable=state.get("ss_is_global_cs"), text="")
        add_row_three(frm, 2, [
            ("season", ttk.Combobox(frm, textvariable=state.get("v_season"),
             values=["SUMMER", "WINTER"], state="readonly", width=10)),
            ("Spherical Earth?", chk_sphere),
            ("", ttk.Label(frm, text="")),
        ])


class VictimP619Section:
    @staticmethod
    def build(parent, state):
        # ITU-R P.619 models propagation loss accounting for atmospheric gases and clutter.
        frm = ttk.LabelFrame(parent, text="P619 Parameters")
        frm.pack(fill="x", padx=2, pady=4)

        add_row_three(frm, 0, [
            ("mean_clutter_height", ttk.Combobox(frm, textvariable=state.get(
                "v_p619_clutter"), values=["Low", "Mid", "High"], state="readonly", width=10)),
            ("below_rooftop [%]", ttk.Entry(
                frm, textvariable=state.get("v_p619_below_rooftop"), width=10)),
            ("", ttk.Label(frm, text="")),
        ])


class VictimGeometrySection:
    @staticmethod
    def build(parent, state):
        wrap = ttk.LabelFrame(parent, text="Geometry – Classes")
        wrap.pack(fill="x", padx=2, pady=4)

        # Spacecraft
        frm_sc = ttk.LabelFrame(wrap, text="Spacecraft – Location (FIXED/GEO)")
        frm_sc.pack(fill="x", padx=2, pady=(6, 6))
        add_row_three(frm_sc, 0, [
            ("altitude [m] (sat)", ttk.Entry(
                frm_sc, textvariable=state.get("v_alt"), width=12)),
            ("location.fixed.lat_deg", ttk.Entry(
                frm_sc, textvariable=state.get("v_fix_lat"), width=12)),
            ("location.fixed.long_deg", ttk.Entry(
                frm_sc, textvariable=state.get("v_fix_lon"), width=12)),
        ])

        # Earth Station
        frm_es = ttk.LabelFrame(
            wrap, text="Earth Station – Reference Point on Earth")
        frm_es.pack(fill="x", padx=2, pady=(0, 6))
        add_row_three(frm_es, 0, [
            ("es_altitude [m]", ttk.Entry(
                frm_es, textvariable=state.get("v_es_alt"), width=12)),
            ("es_lat_deg", ttk.Entry(
                frm_es, textvariable=state.get("v_es_lat"), width=12)),
            ("es_long_deg", ttk.Entry(
                frm_es, textvariable=state.get("v_es_lon"), width=12)),
        ])

        # Pointing
        frm_pt = ttk.LabelFrame(wrap, text="Pointing (Export Only)")
        frm_pt.pack(fill="x", padx=2, pady=(0, 6))
        add_row_three(frm_pt, 0, [
            ("azimuth.type", ttk.Combobox(frm_pt, textvariable=state.get(
                "v_az_type"), values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
            ("elevation.type", ttk.Combobox(frm_pt, textvariable=state.get(
                "v_el_type"), values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
            ("", ttk.Label(frm_pt, text="")),
        ])


class VictimAntennaSection:
    def __init__(self, parent, state):
        self.state = state
        self.frame = ttk.LabelFrame(parent, text="Antenna")
        self.frame.pack(fill="x", padx=2, pady=4)

        self.frm_s672 = None
        self.frm_other = None

        self._build_ui()

    def _build_ui(self):
        # The S.672 standard defines a reference radiation pattern for satellite system antennas.
        #
        # Pattern Selector
        add_row_three(self.frame, 0, [
            ("pattern", ttk.Combobox(self.frame, textvariable=self.state.get("v_ant_pattern"),
                                     values=["ITU-R S.672", "ITU-R M.2101", "3GPP TR 38.901", "Custom"], state="readonly", width=18)),
            ("gain [dBi]", ttk.Entry(self.frame,
             textvariable=self.state.get("v_ant_gain"), width=10)),
            ("", ttk.Label(self.frame, text="")),
        ])

        # S.672 Frame
        self.frm_s672 = ttk.Frame(self.frame)
        self.frm_s672.grid(row=1, column=0, columnspan=6,
                           sticky="we", pady=(4, 0))
        add_row_three(self.frm_s672, 0, [
            ("itu_r_s_672.antenna_3_dB", ttk.Entry(self.frm_s672,
             textvariable=self.state.get("v_s672_3db"), width=8)),
            ("itu_r_s_672.antenna_l_s [dB]", ttk.Entry(
                self.frm_s672, textvariable=self.state.get("v_s672_ls"), width=8)),
            ("", ttk.Label(self.frm_s672, text="")),
        ])

        # Other Frame
        self.frm_other = ttk.Frame(self.frame)
        ttk.Label(self.frm_other, text="Parameters for this pattern not yet implemented in GUI.").grid(
            row=0, column=0, sticky="w")

        # Setup Traces
        self.state.get("v_ant_pattern").trace_add("write", self.refresh)
        self.refresh()

    def refresh(self, *args):
        """Toggles S.672 parameters visibility."""
        pattern = self.state.get("v_ant_pattern").get()
        if pattern == "ITU-R S.672":
            self.frm_other.grid_remove()
            self.frm_s672.grid()
        else:
            self.frm_s672.grid_remove()
            self.frm_other.grid(row=1, column=0, columnspan=6,
                                sticky="w", pady=(4, 0))
