import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

# Importa função auxiliar do utils
from utils import add_row_three


class VictimTab:
    def __init__(self, app, parent_frame):
        """
        :param app: Instância da classe App (main.py)
        :param parent_frame: O widget onde esta aba será desenhada
        """
        self.app = app
        self.frame = parent_frame

        # Constrói a interface
        self._build_ui()

    def _build_ui(self):
        # Topbar: Botões Salvar/Carregar
        topbar = ttk.Frame(self.frame)
        topbar.pack(fill="x", pady=(0, 6))
        ttk.Button(topbar, text="Salvar config Single Space Station (.json)",
                   command=self._save_victim_config).pack(side="left")
        ttk.Button(topbar, text="Carregar config Single Space Station (.json)",
                   command=self._load_victim_config).pack(side="left", padx=(6, 0))

        # ==== Parâmetros Básicos ====
        frm0 = ttk.LabelFrame(self.frame, text="Parâmetros básicos")
        frm0.pack(fill="x", padx=2, pady=4)

        add_row_three(frm0, 0, [
            ("frequency [MHz]", ttk.Entry(
                frm0, textvariable=self.app.v_freq, width=10)),
            ("bandwidth [MHz]", ttk.Entry(
                frm0, textvariable=self.app.v_bw, width=10)),
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm0,
             textvariable=self.app.v_txpsd, width=12)),
        ])
        add_row_three(frm0, 1, [
            ("polarization_loss [dB]", ttk.Entry(
                frm0, textvariable=self.app.v_pol_loss, width=10)),
            ("noise_temperature [K]", ttk.Entry(
                frm0, textvariable=self.app.v_tnoise, width=10)),
            ("channel_model", ttk.Combobox(frm0, textvariable=self.app.v_ch_model,
             values=["P619", "FSPL"], state="readonly", width=12)),
        ])

        # Checkbox solto para "Terra Esférica"
        chk_sphere = ttk.Checkbutton(
            frm0, variable=self.app.ss_is_global_cs, text="")

        add_row_three(frm0, 2, [
            ("season", ttk.Combobox(frm0, textvariable=self.app.v_season,
             values=["SUMMER", "WINTER"], state="readonly", width=10)),
            ("Terra Esférica?", chk_sphere),
            ("", ttk.Label(frm0, text="")),
        ])

        # ==== P619 ====
        frm1 = ttk.LabelFrame(self.frame, text="P619 parameters")
        frm1.pack(fill="x", padx=2, pady=4)
        add_row_three(frm1, 0, [
            ("mean_clutter_height", ttk.Combobox(frm1, textvariable=self.app.v_p619_clutter,
             values=["Low", "Mid", "High"], state="readonly", width=10)),
            ("below_rooftop [%]", ttk.Entry(
                frm1, textvariable=self.app.v_p619_below_rooftop, width=10)),
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
                frm_sc, textvariable=self.app.v_alt, width=12)),
            ("location.fixed.lat_deg", ttk.Entry(
                frm_sc, textvariable=self.app.v_fix_lat, width=12)),
            ("location.fixed.long_deg", ttk.Entry(
                frm_sc, textvariable=self.app.v_fix_lon, width=12)),
        ])

        # Earth Station
        frm_es = ttk.LabelFrame(
            wrap, text="Earth Station – Reference point on Earth")
        frm_es.pack(fill="x", padx=2, pady=(0, 6))
        add_row_three(frm_es, 0, [
            ("es_altitude [m]", ttk.Entry(
                frm_es, textvariable=self.app.v_es_alt, width=12)),
            ("es_lat_deg", ttk.Entry(frm_es, textvariable=self.app.v_es_lat, width=12)),
            ("es_long_deg", ttk.Entry(frm_es, textvariable=self.app.v_es_lon, width=12)),
        ])

        # Pointing (export only)
        frm_pt = ttk.LabelFrame(wrap, text="Pointing (export only)")
        frm_pt.pack(fill="x", padx=2, pady=(0, 6))
        add_row_three(frm_pt, 0, [
            ("azimuth.type", ttk.Combobox(frm_pt, textvariable=self.app.v_az_type,
             values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
            ("elevation.type", ttk.Combobox(frm_pt, textvariable=self.app.v_el_type,
             values=["POINTING_AT_IMT", "FIXED"], state="readonly", width=18)),
            ("", ttk.Label(frm_pt, text="")),
        ])

        # ==== Antenna ====
        frm3 = ttk.LabelFrame(self.frame, text="Antenna")
        frm3.pack(fill="x", padx=2, pady=4)

        # Seletor de Padrão
        add_row_three(frm3, 0, [
            ("pattern", ttk.Combobox(frm3, textvariable=self.app.v_ant_pattern,
                                     values=["ITU-R S.672", "ITU-R M.2101", "3GPP TR 38.901", "Custom"], state="readonly", width=18)),
            ("gain [dBi]", ttk.Entry(
                frm3, textvariable=self.app.v_ant_gain, width=10)),
            ("", ttk.Label(frm3, text="")),
        ])

        # Frame S.672 (visível condicionalmente)
        self.frm_s672 = ttk.Frame(frm3)
        self.frm_s672.grid(row=1, column=0, columnspan=6,
                           sticky="we", pady=(4, 0))
        add_row_three(self.frm_s672, 0, [
            ("itu_r_s_672.antenna_3_dB", ttk.Entry(
                self.frm_s672, textvariable=self.app.v_s672_3db, width=8)),
            ("itu_r_s_672.antenna_l_s [dB]", ttk.Entry(
                self.frm_s672, textvariable=self.app.v_s672_ls, width=8)),
            ("", ttk.Label(self.frm_s672, text="")),
        ])

        # Frame "Outros" (aviso)
        self.frm_other_ant = ttk.Frame(frm3)
        ttk.Label(self.frm_other_ant, text="Parâmetros para este padrão ainda não implementados na GUI.").grid(
            row=0, column=0, sticky="w")

        # Configura o toggle de visibilidade
        self.app.v_ant_pattern.trace_add("write", self._toggle_antenna)
        self._toggle_antenna()

    # ---------------- Lógica de Interface ----------------

    def _toggle_antenna(self, *args):
        """Alterna entre os parâmetros do S.672 e o frame genérico."""
        pattern = self.app.v_ant_pattern.get()

        if pattern == "ITU-R S.672":
            self.frm_other_ant.grid_remove()
            self.frm_s672.grid()
        else:
            self.frm_s672.grid_remove()
            self.frm_other_ant.grid(
                row=1, column=0, columnspan=6, sticky="w", pady=(4, 0))

    # ---------------- IO (Save/Load Config) ----------------

    def _save_victim_config(self):
        data = {
            "v_freq": self.app.v_freq.get(),
            "v_bw": self.app.v_bw.get(),
            "v_txpsd": self.app.v_txpsd.get(),
            "v_pol_loss": self.app.v_pol_loss.get(),
            "v_tnoise": self.app.v_tnoise.get(),
            "v_ch_model": self.app.v_ch_model.get(),
            "v_season": self.app.v_season.get(),
            "v_p619_clutter": self.app.v_p619_clutter.get(),
            "v_p619_below_rooftop": self.app.v_p619_below_rooftop.get(),
            "v_alt": self.app.v_alt.get(),
            "v_fix_lat": self.app.v_fix_lat.get(),
            "v_fix_lon": self.app.v_fix_lon.get(),
            "v_es_alt": self.app.v_es_alt.get(),
            "v_es_lat": self.app.v_es_lat.get(),
            "v_es_lon": self.app.v_es_lon.get(),
            "v_az_type": self.app.v_az_type.get(),
            "v_el_type": self.app.v_el_type.get(),
            "v_ant_pattern": self.app.v_ant_pattern.get(),
            "v_ant_gain": self.app.v_ant_gain.get(),
            "v_s672_3db": self.app.v_s672_3db.get(),
            "v_s672_ls": self.app.v_s672_ls.get(),
            "ss_is_global_cs": self.app.ss_is_global_cs.get()
        }
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="single_space_station_config.json"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("Single Space Station",
                            f"Configuração salva em:\n{path}")

    def _load_victim_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            vals = json.load(f)

        def S(name, var):
            if name in vals:
                try:
                    var.set(vals[name])
                except:
                    pass

        S("v_freq", self.app.v_freq)
        S("v_bw", self.app.v_bw)
        S("v_txpsd", self.app.v_txpsd)
        S("v_pol_loss", self.app.v_pol_loss)
        S("v_tnoise", self.app.v_tnoise)
        S("v_ch_model", self.app.v_ch_model)
        S("v_season", self.app.v_season)
        S("v_p619_clutter", self.app.v_p619_clutter)
        S("v_p619_below_rooftop", self.app.v_p619_below_rooftop)
        S("v_alt", self.app.v_alt)
        S("v_fix_lat", self.app.v_fix_lat)
        S("v_fix_lon", self.app.v_fix_lon)
        S("v_es_alt", self.app.v_es_alt)
        S("v_es_lat", self.app.v_es_lat)
        S("v_es_lon", self.app.v_es_lon)
        S("v_az_type", self.app.v_az_type)
        S("v_el_type", self.app.v_el_type)
        S("v_ant_pattern", self.app.v_ant_pattern)
        S("v_ant_gain", self.app.v_ant_gain)
        S("v_s672_3db", self.app.v_s672_3db)
        S("v_s672_ls", self.app.v_s672_ls)
        S("ss_is_global_cs", self.app.ss_is_global_cs)

        # Garante que a UI reflita o padrão de antena carregado
        self._toggle_antenna()

        messagebox.showinfo("Single Space Station", "Configuração carregada.")
