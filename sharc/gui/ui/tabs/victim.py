import tkinter as tk
from tkinter import ttk
from utils import add_row_three

# Importa o gerenciador (assumindo que a pasta assets está no path ou relativa)
from ui.tabs.assets.victim_state import VictimStateManager


class VictimTab:
    def __init__(self, app, parent_frame):
        """
        :param app: Instância da classe App (main.py)
        :param parent_frame: O widget onde esta aba será desenhada
        """
        self.app = app
        self.frame = parent_frame

        # Inicializa o Estado (Dados)
        self.state = VictimStateManager()

        # Constrói a interface
        self._build_ui()

    def _build_ui(self):
        # Topbar: Botões Salvar/Carregar (Delegados ao State)
        topbar = ttk.Frame(self.frame)
        topbar.pack(fill="x", pady=(0, 6))

        ttk.Button(topbar, text="Salvar config (.json)",
                   command=self.state.save_to_file).pack(side="left")

        ttk.Button(topbar, text="Carregar config (.json)",
                   command=lambda: self.state.load_from_file(callback_after_load=self._toggle_antenna)).pack(side="left", padx=(6, 0))

        # ==== Parâmetros Básicos ====
        frm0 = ttk.LabelFrame(self.frame, text="Parâmetros básicos")
        frm0.pack(fill="x", padx=2, pady=4)

        add_row_three(frm0, 0, [
            ("frequency [MHz]", ttk.Entry(
                frm0, textvariable=self.state.get("v_freq"), width=10)),
            ("bandwidth [MHz]", ttk.Entry(
                frm0, textvariable=self.state.get("v_bw"), width=10)),
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm0,
             textvariable=self.state.get("v_txpsd"), width=12)),
        ])
        add_row_three(frm0, 1, [
            ("polarization_loss [dB]", ttk.Entry(
                frm0, textvariable=self.state.get("v_pol_loss"), width=10)),
            ("noise_temperature [K]", ttk.Entry(
                frm0, textvariable=self.state.get("v_tnoise"), width=10)),
            ("channel_model", ttk.Combobox(frm0, textvariable=self.state.get(
                "v_ch_model"), values=["P619", "FSPL"], state="readonly", width=12)),
        ])

        # Checkbox solto para "Terra Esférica"
        chk_sphere = ttk.Checkbutton(
            frm0, variable=self.state.get("ss_is_global_cs"), text="")

        add_row_three(frm0, 2, [
            ("season", ttk.Combobox(frm0, textvariable=self.state.get(
                "v_season"), values=["SUMMER", "WINTER"], state="readonly", width=10)),
            ("Terra Esférica?", chk_sphere),
            ("", ttk.Label(frm0, text="")),
        ])

        # ==== P619 ====
        frm1 = ttk.LabelFrame(self.frame, text="P619 parameters")
        frm1.pack(fill="x", padx=2, pady=4)
        add_row_three(frm1, 0, [
            ("mean_clutter_height", ttk.Combobox(frm1, textvariable=self.state.get(
                "v_p619_clutter"), values=["Low", "Mid", "High"], state="readonly", width=10)),
            ("below_rooftop [%]", ttk.Entry(
                frm1, textvariable=self.state.get("v_p619_below_rooftop"), width=10)),
            ("", ttk.Label(frm1, text="")),
        ])

        # ==== Geometria (subdividida) ====
        wrap = ttk.LabelFrame(self.frame, text="Geometria – Classes")
        wrap.pack(fill="x", padx=2, pady=4)

        # Spacecraft (FIXED)
        frm_sc = ttk.LabelFrame(wrap, text="Spacecraft – Location (FIXED/GEO)")
        frm_sc.pack(fill="x", padx=2, pady=(6, 6))
        add_row_three(frm_sc, 0, [
            ("altitude [m] (sat)", ttk.Entry(
                frm_sc, textvariable=self.state.get("v_alt"), width=12)),
            ("location.fixed.lat_deg", ttk.Entry(
                frm_sc, textvariable=self.state.get("v_fix_lat"), width=12)),
            ("location.fixed.long_deg", ttk.Entry(
                frm_sc, textvariable=self.state.get("v_fix_lon"), width=12)),
        ])

        # Earth Station
        frm_es = ttk.LabelFrame(
            wrap, text="Earth Station – Reference point on Earth")
        frm_es.pack(fill="x", padx=2, pady=(0, 6))
        add_row_three(frm_es, 0, [
            ("es_altitude [m]", ttk.Entry(
                frm_es, textvariable=self.state.get("v_es_alt"), width=12)),
            ("es_lat_deg", ttk.Entry(
                frm_es, textvariable=self.state.get("v_es_lat"), width=12)),
            ("es_long_deg", ttk.Entry(
                frm_es, textvariable=self.state.get("v_es_lon"), width=12)),
        ])

        # Pointing (export only)
        frm_pt = ttk.LabelFrame(wrap, text="Pointing (export only)")
        frm_pt.pack(fill="x", padx=2, pady=(0, 6))
        add_row_three(frm_pt, 0, [
            ("azimuth.type", ttk.Combobox(frm_pt, textvariable=self.state.get(
                "v_az_type"), values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
            ("elevation.type", ttk.Combobox(frm_pt, textvariable=self.state.get(
                "v_el_type"), values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
            ("", ttk.Label(frm_pt, text="")),
        ])

        # ==== Antenna ====
        frm3 = ttk.LabelFrame(self.frame, text="Antenna")
        frm3.pack(fill="x", padx=2, pady=4)

        # Seletor de Padrão
        add_row_three(frm3, 0, [
            ("pattern", ttk.Combobox(frm3, textvariable=self.state.get("v_ant_pattern"),
                                     values=["ITU-R S.672", "ITU-R M.2101", "3GPP TR 38.901", "Custom"], state="readonly", width=18)),
            ("gain [dBi]", ttk.Entry(
                frm3, textvariable=self.state.get("v_ant_gain"), width=10)),
            ("", ttk.Label(frm3, text="")),
        ])

        # Frame S.672 (visível condicionalmente)
        self.frm_s672 = ttk.Frame(frm3)
        self.frm_s672.grid(row=1, column=0, columnspan=6,
                           sticky="we", pady=(4, 0))
        add_row_three(self.frm_s672, 0, [
            ("itu_r_s_672.antenna_3_dB", ttk.Entry(self.frm_s672,
             textvariable=self.state.get("v_s672_3db"), width=8)),
            ("itu_r_s_672.antenna_l_s [dB]", ttk.Entry(
                self.frm_s672, textvariable=self.state.get("v_s672_ls"), width=8)),
            ("", ttk.Label(self.frm_s672, text="")),
        ])

        # Frame "Outros" (aviso)
        self.frm_other_ant = ttk.Frame(frm3)
        ttk.Label(self.frm_other_ant, text="Parâmetros para este padrão ainda não implementados na GUI.").grid(
            row=0, column=0, sticky="w")

        # Configura o toggle de visibilidade
        # Nota: trace_add deve ser feito na variável do State
        self.state.get("v_ant_pattern").trace_add(
            "write", self._toggle_antenna)
        self._toggle_antenna()

    # ---------------- Lógica de Interface ----------------

    def _toggle_antenna(self, *args):
        """Alterna entre os parâmetros do S.672 e o frame genérico."""
        pattern = self.state.get("v_ant_pattern").get()

        if pattern == "ITU-R S.672":
            self.frm_other_ant.grid_remove()
            self.frm_s672.grid()
        else:
            self.frm_s672.grid_remove()
            self.frm_other_ant.grid(
                row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))
