import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

# Importa função auxiliar de layout do utils
from utils import add_row_three


class IMTTab:
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
        # ===== Scrollable container =====
        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Frame interno onde os widgets realmente ficam
        self.inner_frame = ttk.Frame(canvas)

        # Cria uma window dentro do canvas
        canvas_window = canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw")

        def _on_frame_config(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        self.inner_frame.bind("<Configure>", _on_frame_config)

        # Suporte a rodinha do mouse
        def _on_mousewheel(event):
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        # Bindings de scroll
        canvas.bind_all("<MouseWheel>", _on_mousewheel)      # Windows
        canvas.bind_all(
            "<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind_all(
            "<Button-5>", lambda e: canvas.yview_scroll(1, "units"))  # Linux

        # ================== CONTEÚDO DA ABA ==================

        # Topbar: Load/Save Config
        topbar = ttk.Frame(self.inner_frame)
        topbar.pack(fill="x", pady=(0, 6))
        ttk.Button(topbar, text="Salvar configuração IMT (.json)",
                   command=self._save_imt_config).pack(side="left")
        ttk.Button(topbar, text="Carregar configuração IMT (.json)",
                   command=self._load_imt_config).pack(side="left", padx=(6, 0))

        # ---- IMT: Parâmetros Gerais ----
        frm_g = ttk.LabelFrame(
            self.inner_frame, text="IMT – Parâmetros gerais")
        frm_g.pack(fill="x", pady=(2, 8))

        add_row_three(frm_g, 0, [
            ("minimum_separation_distance_bs_ue [m]", ttk.Entry(
                frm_g, textvariable=self.app.imt_min_sep, width=10)),
            ("interfered_with", ttk.Combobox(frm_g, textvariable=self.app.imt_interfered,
             values=[False, True], state="readonly", width=8)),
            ("frequency [MHz]", ttk.Entry(
                frm_g, textvariable=self.app.imt_freq, width=12)),
        ])
        add_row_three(frm_g, 1, [
            ("bandwidth [MHz]", ttk.Entry(
                frm_g, textvariable=self.app.imt_bw, width=10)),
            ("rb_bandwidth [MHz]", ttk.Entry(
                frm_g, textvariable=self.app.imt_rb_bw, width=10)),
            ("spectral_mask", ttk.Combobox(frm_g, textvariable=self.app.imt_spec_mask,
             values=["IMT-2020", "3GPP"], state="readonly", width=12)),
        ])
        add_row_three(frm_g, 2, [
            ("spurious_emissions [dBc]", ttk.Entry(
                frm_g, textvariable=self.app.imt_spurious, width=10)),
            ("adjacent_antenna_model", ttk.Entry(
                frm_g, textvariable=self.app.imt_adj_ant_model, width=16)),
            ("guard_band_ratio", ttk.Entry(
                frm_g, textvariable=self.app.imt_guard_ratio, width=10)),
        ])

        # ---- Topologia ----
        self._build_topology_section()

        # ---- BS Parameters ----
        self._build_bs_section()

        # ---- UE Parameters ----
        self._build_ue_section()

        # ---- UL / DL / Channel ----
        frm_l = ttk.LabelFrame(
            self.inner_frame, text="UL / DL / Channel / Shadowing")
        frm_l.pack(fill="x", pady=(2, 8))

        add_row_three(frm_l, 0, [
            ("uplink.attenuation_factor", ttk.Entry(
                frm_l, textvariable=self.app.ul_att, width=8)),
            ("uplink.sinr_min / sinr_max [dB]", self._pair_entries(
                frm_l, self.app.ul_sinr_min, self.app.ul_sinr_max, w=8)),
            ("downlink.attenuation_factor", ttk.Entry(
                frm_l, textvariable=self.app.dl_att, width=8)),
        ])
        add_row_three(frm_l, 1, [
            ("downlink.sinr_min / sinr_max [dB]", self._pair_entries(
                frm_l, self.app.dl_sinr_min, self.app.dl_sinr_max, w=8)),
            ("channel_model", ttk.Entry(
                frm_l, textvariable=self.app.ch_model, width=12)),
            ("shadowing", ttk.Combobox(frm_l, textvariable=self.app.shadowing,
             values=[True, False], state="readonly", width=8)),
        ])

        # Inicializa estado dos toggles
        self._toggle_ue_distribution()

    def _build_topology_section(self):
        frm_t = ttk.LabelFrame(self.inner_frame, text="Topologia – IMT")
        frm_t.pack(fill="x", pady=(2, 8))

        # Seletor de TYPE
        row_type = ttk.Frame(frm_t)
        row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 4))
        ttk.Label(row_type, text="type").pack(side="left")

        cb_topo_type = ttk.Combobox(
            row_type, textvariable=self.app.topo_type,
            values=["MACROCELL", "HOTSPOT", "SINGLE_BS", "Macro_countries"], state="readonly", width=18
        )
        cb_topo_type.pack(side="left", padx=(6, 0))

        # Parâmetros centrais (comuns)
        add_row_three(frm_t, 1, [
            ("central_latitude", ttk.Entry(
                frm_t, textvariable=self.app.topo_c_lat, width=12)),
            ("central_longitude", ttk.Entry(
                frm_t, textvariable=self.app.topo_c_lon, width=12)),
            ("central_altitude [m]", ttk.Entry(
                frm_t, textvariable=self.app.topo_c_alt, width=12)),
        ])

        # ---- Subframe: Countries ----
        self.frm_t_countries = ttk.LabelFrame(
            frm_t, text="Topologia – COUNTRIES (Macro_countries)")
        self.frm_t_countries.grid(
            row=2, column=0, columnspan=6, sticky="we", pady=(4, 8))

        row_opts = ttk.Frame(self.frm_t_countries)
        row_opts.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2, 4))

        ttk.Label(row_opts, text="raster_encoding").pack(side="left")
        cb_renc = ttk.Combobox(
            row_opts, textvariable=self.app.topo_raster_enc,
            values=["Uniforme", "Denspop"], state="readonly", width=12
        )
        cb_renc.pack(side="left", padx=(6, 16))

        ttk.Label(row_opts, text="dist_type").pack(side="left")
        cb_dist = ttk.Combobox(
            row_opts, textvariable=self.app.topo_dist_type,
            values=["Urban", "Suburban", "Rural"], state="readonly", width=12
        )
        cb_dist.pack(side="left", padx=(6, 0))

        # Lista de countries (Text)
        row_c = ttk.Frame(self.frm_t_countries)
        row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row_c, text="country_names (1/linha)").pack(side="left")

        self.txt_countries = tk.Text(row_c, width=48, height=7)
        self.txt_countries.insert("1.0", self.app.topo_countries.get())
        self.txt_countries.pack(side="left", fill="x",
                                expand=True, padx=(6, 6))

        add_row_three(self.frm_t_countries, 2, [
            ("num_bs_total", ttk.Entry(self.frm_t_countries,
             textvariable=self.app.topo_num_bs, width=10)),
            ("cell_radius [m]", ttk.Entry(self.frm_t_countries,
             textvariable=self.app.topo_cell_radius, width=10)),
            ("rng_seed", ttk.Entry(self.frm_t_countries,
             textvariable=self.app.topo_rng, width=10)),
        ])

        # Shapefile e Raster
        row_shp = ttk.Frame(self.frm_t_countries)
        row_shp.grid(row=3, column=0, columnspan=6, sticky="we", pady=(2, 2))
        ttk.Label(row_shp, text="countries_shapefile").pack(side="left")
        self.ent_shp = ttk.Entry(
            row_shp, textvariable=self.app.path_shp, width=64)
        self.ent_shp.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row_shp, text="…", width=3,
                   command=self._browse_shapefile).pack(side="left")

        row_ras = ttk.Frame(self.frm_t_countries)
        row_ras.grid(row=4, column=0, columnspan=6, sticky="we", pady=(2, 2))
        ttk.Label(row_ras, text="population_raster").pack(side="left")
        self.ent_raster = ttk.Entry(
            row_ras, textvariable=self.app.path_raster, width=64)
        self.ent_raster.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.btn_raster = ttk.Button(
            row_ras, text="…", width=3, command=self._browse_raster)
        self.btn_raster.pack(side="left")

        # Bindings específicos
        cb_renc.bind("<<ComboboxSelected>>", self._toggle_raster_by_encoding)
        self._toggle_raster_by_encoding()

        # ---- Subframe: MACROCELL ----
        self.frm_t_macro = ttk.LabelFrame(frm_t, text="Topologia – MACROCELL")
        self.frm_t_macro.grid(row=3, column=0, columnspan=6,
                              sticky="we", pady=(4, 8))
        add_row_three(self.frm_t_macro, 0, [
            ("intersite_distance [m]", ttk.Entry(
                self.frm_t_macro, textvariable=self.app.macro_intersite, width=10)),
            ("wrap_around", ttk.Combobox(self.frm_t_macro, textvariable=self.app.macro_wrap,
             values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(self.frm_t_macro,
             textvariable=self.app.macro_clusters, width=8)),
        ])

        # ---- Subframe: HOTSPOT ----
        self.frm_t_hotspot = ttk.LabelFrame(frm_t, text="Topologia – HOTSPOT")
        self.frm_t_hotspot.grid(
            row=4, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(self.frm_t_hotspot, 0, [
            ("intersite_distance [m]", ttk.Entry(
                self.frm_t_hotspot, textvariable=self.app.hotspot_intersite, width=10)),
            ("wrap_around", ttk.Combobox(self.frm_t_hotspot, textvariable=self.app.hotspot_wrap,
             values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(self.frm_t_hotspot,
             textvariable=self.app.hotspot_clusters, width=8)),
        ])
        add_row_three(self.frm_t_hotspot, 1, [
            ("num_hotspots_per_cell", ttk.Entry(self.frm_t_hotspot,
             textvariable=self.app.hotspot_num_per_cell, width=10)),
            ("max_dist_hotspot_ue [m]", ttk.Entry(
                self.frm_t_hotspot, textvariable=self.app.hotspot_max_dist_ue, width=12)),
            ("min_dist_bs_hotspot [m]", ttk.Entry(
                self.frm_t_hotspot, textvariable=self.app.hotspot_min_dist_bs, width=12)),
        ])

        # ---- Subframe: SINGLE_BS ----
        self.frm_t_sbs = ttk.LabelFrame(frm_t, text="Topologia – SINGLE_BS")
        self.frm_t_sbs.grid(row=5, column=0, columnspan=6,
                            sticky="we", pady=(4, 8))
        add_row_three(self.frm_t_sbs, 0, [
            ("intersite_distance [m]", ttk.Entry(
                self.frm_t_sbs, textvariable=self.app.sbs_intersite, width=10)),
            ("cell_radius [m]", ttk.Entry(self.frm_t_sbs,
             textvariable=self.app.sbs_cell_radius, width=10)),
            ("num_clusters", ttk.Entry(self.frm_t_sbs,
             textvariable=self.app.sbs_clusters, width=8)),
        ])
        add_row_three(self.frm_t_sbs, 1, [
            ("azimuth (lista ou str)", ttk.Entry(self.frm_t_sbs,
             textvariable=self.app.sbs_azimuth, width=28)),
            ("", ttk.Label(self.frm_t_sbs, text="")),
            ("", ttk.Label(self.frm_t_sbs, text="")),
        ])

        cb_topo_type.bind("<<ComboboxSelected>>", self._toggle_topology_frames)
        self._toggle_topology_frames()

    def _build_bs_section(self):
        frm_bs = ttk.LabelFrame(self.inner_frame, text="BS – Parâmetros")
        frm_bs.pack(fill="x", padx=6, pady=8)

        for c in range(3):
            frm_bs.columnconfigure(c, weight=1, uniform="bscols")

        # Coluna 1: Básico
        col_basic = ttk.LabelFrame(frm_bs, text="BS – Básico")
        col_basic.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
        col_basic.columnconfigure(1, weight=1)

        self._add_field(col_basic, 0, "load_probability", ttk.Entry(
            col_basic, textvariable=self.app.bs_load_prob, width=10))
        self._add_field(col_basic, 1, "conducted_power [dBm]", ttk.Entry(
            col_basic, textvariable=self.app.bs_power, width=10))
        self._add_field(col_basic, 2, "height [m]", ttk.Entry(
            col_basic, textvariable=self.app.bs_height, width=10))
        self._add_field(col_basic, 3, "noise_figure [dB]", ttk.Entry(
            col_basic, textvariable=self.app.bs_nf, width=10))
        self._add_field(col_basic, 4, "ohmic_loss [dB]", ttk.Entry(
            col_basic, textvariable=self.app.bs_ohmic, width=10))

        # Coluna 2: Array
        col_array = ttk.LabelFrame(frm_bs, text="BS – Array da Antena")
        col_array.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
        for c in range(4):
            col_array.columnconfigure(c, weight=(1 if c in (1, 3) else 0))

        self._add_field(col_array, 0, "normalization", ttk.Checkbutton(
            col_array, variable=self.app.bs_norm, text=""))

        cb_pat = ttk.Combobox(col_array, textvariable=self.app.bs_elem_pat,
                              values=["M2101", "ITU-R S.672", "Custom"], state="readonly", width=14)
        self._add_field(col_array, 1, "element_pattern", cb_pat)

        self._add_field(col_array, 2, "minimum_array_gain [dB]", ttk.Entry(
            col_array, textvariable=self.app.bs_min_arr_gain, width=10))

        w_hmin = ttk.Entry(
            col_array, textvariable=self.app.bs_h_steer[0], width=7)
        w_hmax = ttk.Entry(
            col_array, textvariable=self.app.bs_h_steer[1], width=7)
        self._add_range(col_array, 3, "h_beamsteer [deg]", w_hmin, w_hmax)

        w_vmin = ttk.Entry(
            col_array, textvariable=self.app.bs_v_steer[0], width=7)
        w_vmax = ttk.Entry(
            col_array, textvariable=self.app.bs_v_steer[1], width=7)
        self._add_range(col_array, 4, "v_beamsteer [deg]", w_vmin, w_vmax)

        self._add_field(col_array, 5, "downtilt [deg]", ttk.Entry(
            col_array, textvariable=self.app.bs_downtilt, width=10))
        self._add_field(col_array, 6, "element_max_g [dBi]", ttk.Entry(
            col_array, textvariable=self.app.bs_elem_max_g, width=10))
        self._add_field(col_array, 7, "element_phi_3db [deg]", ttk.Entry(
            col_array, textvariable=self.app.bs_phi3, width=10))
        self._add_field(col_array, 8, "element_theta_3db [deg]", ttk.Entry(
            col_array, textvariable=self.app.bs_theta3, width=10))
        self._add_field(col_array, 9, "n_rows", ttk.Entry(
            col_array, textvariable=self.app.bs_rows, width=10))
        self._add_field(col_array, 10, "n_columns", ttk.Entry(
            col_array, textvariable=self.app.bs_cols, width=10))
        self._add_field(col_array, 11, "element_horiz_spacing [λ]", ttk.Entry(
            col_array, textvariable=self.app.bs_elem_hs, width=10))
        self._add_field(col_array, 12, "element_vert_spacing [λ]", ttk.Entry(
            col_array, textvariable=self.app.bs_elem_vs, width=10))
        self._add_field(col_array, 13, "element_am [dB]", ttk.Entry(
            col_array, textvariable=self.app.bs_elem_am, width=10))
        self._add_field(col_array, 14, "element_sla_v [dB]", ttk.Entry(
            col_array, textvariable=self.app.bs_elem_sla_v, width=10))
        self._add_field(col_array, 15, "multiplication_factor", ttk.Entry(
            col_array, textvariable=self.app.bs_mult, width=10))

        # Coluna 3: Sub-array
        col_sub = ttk.LabelFrame(frm_bs, text="BS – Sub-array")
        col_sub.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=6)
        col_sub.columnconfigure(1, weight=1)

        self._add_field(col_sub, 0, "is_enabled", ttk.Checkbutton(
            col_sub, variable=self.app.bs_sub_enabled, text=""))
        self._add_field(col_sub, 1, "n_rows", ttk.Entry(
            col_sub, textvariable=self.app.bs_sub_rows, width=10))
        self._add_field(col_sub, 2, "element_vert_spacing [λ]", ttk.Entry(
            col_sub, textvariable=self.app.bs_sub_evspace, width=10))
        self._add_field(col_sub, 3, "eletrical_downtilt [deg]", ttk.Entry(
            col_sub, textvariable=self.app.bs_sub_e_downtilt, width=10))

    def _build_ue_section(self):
        frm_ue = ttk.LabelFrame(self.inner_frame, text="UE – Parâmetros")
        frm_ue.pack(fill="x", padx=6, pady=8)
        for c in range(3):
            frm_ue.columnconfigure(c, weight=1, uniform="uecols")

        # Coluna 1: Básico
        col_basic_ue = ttk.LabelFrame(frm_ue, text="UE – Básico")
        col_basic_ue.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
        col_basic_ue.columnconfigure(1, weight=1)

        self._add_field(col_basic_ue, 0, "k", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_k, width=8))
        self._add_field(col_basic_ue, 1, "k_m", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_km, width=8))
        self._add_field(col_basic_ue, 2, "indoor_percent [%]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_indoor, width=8))

        cb_ue_dist = ttk.Combobox(col_basic_ue, textvariable=self.app.ue_dist_type,
                                  values=["Macro_countries", "UNIFORM", "CELL",
                                          "UNIFORM_IN_CELL", "ANGLE_AND_DISTANCE"],
                                  state="readonly", width=18)
        self._add_field(col_basic_ue, 3, "distribution_type", cb_ue_dist)
        cb_ue_dist.bind("<<ComboboxSelected>>",
                        lambda e: self._toggle_ue_distribution())

        self._add_field(col_basic_ue, 4, "tx_power_control", ttk.Checkbutton(
            col_basic_ue, variable=self.app.ue_tx_power_ctrl, text=""))
        self._add_field(col_basic_ue, 5, "p_o_pusch [dBm]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_p_o_pusch, width=10))
        self._add_field(col_basic_ue, 6, "alpha", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_alpha, width=10))
        self._add_field(col_basic_ue, 7, "p_cmax [dBm]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_p_cmax, width=10))
        self._add_field(col_basic_ue, 8, "power_dynamic_range [dB]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_p_dyn, width=10))
        self._add_field(col_basic_ue, 9, "height [m]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_height, width=10))
        self._add_field(col_basic_ue, 10, "noise_figure [dB]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_nf, width=10))
        self._add_field(col_basic_ue, 11, "ohmic_loss [dB]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_ohmic, width=10))
        self._add_field(col_basic_ue, 12, "body_loss [dB]", ttk.Entry(
            col_basic_ue, textvariable=self.app.ue_body_loss, width=10))

        # Coluna 2: Array
        col_array_ue = ttk.LabelFrame(frm_ue, text="UE – Array da Antena")
        col_array_ue.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
        for c in range(4):
            col_array_ue.columnconfigure(c, weight=(1 if c in (1, 3) else 0))

        self._add_field(col_array_ue, 0, "normalization", ttk.Checkbutton(
            col_array_ue, variable=self.app.ue_norm, text=""))

        cb_pat_ue = ttk.Combobox(col_array_ue, textvariable=self.app.ue_elem_pat,
                                 values=["FIXED", "M2101", "Custom"], state="readonly", width=14)
        self._add_field(col_array_ue, 1, "element_pattern", cb_pat_ue)

        self._add_field(col_array_ue, 2, "minimum_array_gain [dB]", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_min_arr_gain, width=10))
        self._add_field(col_array_ue, 3, "element_max_g [dBi]", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_elem_max_g, width=10))
        self._add_field(col_array_ue, 4, "element_phi_3db [deg]", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_phi3, width=10))
        self._add_field(col_array_ue, 5, "element_theta_3db [deg]", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_theta3, width=10))
        self._add_field(col_array_ue, 6, "n_rows", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_rows, width=10))
        self._add_field(col_array_ue, 7, "n_columns", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_cols, width=10))
        self._add_field(col_array_ue, 8, "element_am [dB]", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_elem_am, width=10))
        self._add_field(col_array_ue, 9, "element_sla_v [dB]", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_elem_sla_v, width=10))
        self._add_field(col_array_ue, 10, "multiplication_factor", ttk.Entry(
            col_array_ue, textvariable=self.app.ue_mult, width=10))

        # Coluna 3: Sub-array
        col_sub_ue = ttk.LabelFrame(frm_ue, text="UE – Sub-array")
        col_sub_ue.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=6)
        col_sub_ue.columnconfigure(1, weight=1)

        self._add_field(col_sub_ue, 0, "is_enabled", ttk.Checkbutton(
            col_sub_ue, variable=self.app.ue_sub_enabled, text=""))
        self._add_field(col_sub_ue, 1, "n_rows", ttk.Entry(
            col_sub_ue, textvariable=self.app.ue_sub_rows, width=10))
        self._add_field(col_sub_ue, 2, "element_vert_spacing [λ]", ttk.Entry(
            col_sub_ue, textvariable=self.app.ue_sub_evspace, width=10))
        self._add_field(col_sub_ue, 3, "eletrical_downtilt [deg]", ttk.Entry(
            col_sub_ue, textvariable=self.app.ue_sub_e_downtilt, width=10))

        # Distribuição UE (Dinâmico)
        self.col_dist_ue = ttk.LabelFrame(
            frm_ue, text="UE – Distribuição (Angle&Distance)")
        self.col_dist_ue.grid(
            row=1, column=0, sticky="nsew", padx=(3, 6), pady=(0, 6))
        for c in range(4):
            self.col_dist_ue.columnconfigure(
                c, weight=(1 if c in (1, 3) else 0))

        cb_dist_d = ttk.Combobox(self.col_dist_ue, textvariable=self.app.ue_dist_distance,
                                 values=["RAYLEIGH", "UNIFORM",
                                         "SQRT(UNIFORM)"],
                                 state="readonly", width=16)
        self._add_field(self.col_dist_ue, 0,
                        "distribution_distance", cb_dist_d)

        cb_dist_a = ttk.Combobox(self.col_dist_ue, textvariable=self.app.ue_dist_azimuth,
                                 values=["NORMAL", "UNIFORM"], state="readonly", width=16)
        self._add_field(self.col_dist_ue, 1, "distribution_azimuth", cb_dist_a)

        w_azmin = ttk.Entry(
            self.col_dist_ue, textvariable=self.app.ue_az_min, width=8)
        w_azmax = ttk.Entry(
            self.col_dist_ue, textvariable=self.app.ue_az_max, width=8)
        self._add_range(self.col_dist_ue, 2,
                        "azimuth_range [deg]", w_azmin, w_azmax)

    # ---------------- UI Helper Methods (Internal) ----------------

    def _add_field(self, parent, row, label, widget, col=0, col_span=2):
        ttk.Label(parent, text=label).grid(
            row=row, column=col, sticky="w", padx=(6, 4), pady=2)
        widget.grid(row=row, column=col + 1, columnspan=col_span -
                    1, sticky="we", padx=(0, 6), pady=2)

    def _add_range(self, parent, row, label, wmin, wmax, sep_text="a"):
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", padx=(6, 4), pady=2)
        wmin.grid(row=row, column=1, sticky="we", padx=(0, 4), pady=2)
        ttk.Label(parent, text=f" {sep_text} ").grid(
            row=row, column=2, padx=(0, 4))
        wmax.grid(row=row, column=3, sticky="we", padx=(0, 6), pady=2)

    def _pair_entries(self, parent, var1, var2, w=6):
        f = ttk.Frame(parent)
        e1 = ttk.Entry(f, textvariable=var1, width=w)
        e1.pack(side="left")
        ttk.Label(f, text=" / ").pack(side="left")
        e2 = ttk.Entry(f, textvariable=var2, width=w)
        e2.pack(side="left")
        return f

    # ---------------- Toggle Logic ----------------

    def _toggle_topology_frames(self, *_):
        t = self.app.topo_type.get()
        for f in (self.frm_t_countries, self.frm_t_macro, self.frm_t_hotspot, self.frm_t_sbs):
            f.grid_remove()

        if t == "Macro_countries":
            self.frm_t_countries.grid()
        elif t == "MACROCELL":
            self.frm_t_macro.grid()
        elif t == "HOTSPOT":
            self.frm_t_hotspot.grid()
        elif t == "SINGLE_BS":
            self.frm_t_sbs.grid()

    def _toggle_raster_by_encoding(self, *_):
        enc = (self.app.topo_raster_enc.get() or "").strip()
        if enc == "Uniforme":
            self.app.path_raster.set("")
            self.ent_raster.configure(state="disabled")
            self.btn_raster.configure(state="disabled")
        else:
            self.ent_raster.configure(state="normal")
            self.btn_raster.configure(state="normal")

    def _toggle_ue_distribution(self):
        is_ang_dist = (self.app.ue_dist_type.get().upper()
                       == "ANGLE_AND_DISTANCE")
        if is_ang_dist:
            self.col_dist_ue.grid()
        else:
            self.col_dist_ue.grid_remove()

    # ---------------- File Pickers ----------------

    def _browse_shapefile(self):
        fn = filedialog.askopenfilename(
            title="Escolher shapefile de países",
            filetypes=[("Shapefile", "*.shp"), ("Todos os arquivos", "*.*")]
        )
        if fn:
            self.app.path_shp.set(fn)

    def _browse_raster(self):
        fn = filedialog.askopenfilename(
            title="Escolher raster de população (SEDAC/GeoTIFF)",
            filetypes=[("GeoTIFF", "*.tif;*.tiff"),
                       ("Todos os arquivos", "*.*")]
        )
        if fn:
            self.app.path_raster.set(fn)

    # ---------------- Load/Save Config ----------------

    def _save_imt_config(self):
        # Mapeamento massivo de variáveis para dicionário
        data = {
            "imt_min_sep": self.app.imt_min_sep.get(),
            "imt_interfered": self.app.imt_interfered.get(),
            "imt_freq": self.app.imt_freq.get(),
            "imt_bw": self.app.imt_bw.get(),
            "imt_rb_bw": self.app.imt_rb_bw.get(),
            "imt_spec_mask": self.app.imt_spec_mask.get(),
            "imt_spurious": self.app.imt_spurious.get(),
            "imt_adj_ant_model": self.app.imt_adj_ant_model.get(),
            "imt_guard_ratio": self.app.imt_guard_ratio.get(),
            "topo_c_lat": self.app.topo_c_lat.get(),
            "topo_c_lon": self.app.topo_c_lon.get(),
            "topo_c_alt": self.app.topo_c_alt.get(),
            "topo_type": self.app.topo_type.get(),
            "topo_dist_type": self.app.topo_dist_type.get(),
            "topo_num_bs": self.app.topo_num_bs.get(),
            "topo_cell_radius": self.app.topo_cell_radius.get(),
            "topo_rng": self.app.topo_rng.get(),
            "countries": self.txt_countries.get("1.0", "end"),
            "path_shp": self.app.path_shp.get(),
            "path_raster": self.app.path_raster.get(),
            "raster_encoding": self.app.topo_raster_enc.get(),
            "sedac_mode": self.app.sedac_mode.get(),
            "sedac_min": self.app.sedac_min.get(),
            "sedac_max": self.app.sedac_max.get(),
            "pixel_area_method": self.app.pixel_area_method.get(),
            # BS
            "bs_load_prob": self.app.bs_load_prob.get(),
            "bs_power": self.app.bs_power.get(),
            "bs_height": self.app.bs_height.get(),
            "bs_nf": self.app.bs_nf.get(),
            "bs_ohmic": self.app.bs_ohmic.get(),
            "bs_norm": self.app.bs_norm.get(),
            "bs_elem_pat": self.app.bs_elem_pat.get(),
            "bs_min_arr_gain": self.app.bs_min_arr_gain.get(),
            "bs_downtilt": self.app.bs_downtilt.get(),
            "bs_elem_max_g": self.app.bs_elem_max_g.get(),
            "bs_phi3": self.app.bs_phi3.get(),
            "bs_theta3": self.app.bs_theta3.get(),
            "bs_rows": self.app.bs_rows.get(),
            "bs_cols": self.app.bs_cols.get(),
            "bs_elem_hs": self.app.bs_elem_hs.get(),
            "bs_elem_vs": self.app.bs_elem_vs.get(),
            "bs_elem_am": self.app.bs_elem_am.get(),
            "bs_elem_sla_v": self.app.bs_elem_sla_v.get(),
            "bs_mult": self.app.bs_mult.get(),
            "bs_sub_enabled": self.app.bs_sub_enabled.get(),
            "bs_sub_rows": self.app.bs_sub_rows.get(),
            "bs_sub_evspace": self.app.bs_sub_evspace.get(),
            "bs_sub_e_downtilt": self.app.bs_sub_e_downtilt.get(),
            # UE
            "ue_k": self.app.ue_k.get(),
            "ue_km": self.app.ue_km.get(),
            "ue_indoor": self.app.ue_indoor.get(),
            "ue_dist_type": self.app.ue_dist_type.get(),
            "ue_tx_power_ctrl": self.app.ue_tx_power_ctrl.get(),
            "ue_p_o_pusch": self.app.ue_p_o_pusch.get(),
            "ue_alpha": self.app.ue_alpha.get(),
            "ue_p_cmax": self.app.ue_p_cmax.get(),
            "ue_p_dyn": self.app.ue_p_dyn.get(),
            "ue_height": self.app.ue_height.get(),
            "ue_nf": self.app.ue_nf.get(),
            "ue_ohmic": self.app.ue_ohmic.get(),
            "ue_body_loss": self.app.ue_body_loss.get(),
            "ue_norm": self.app.ue_norm.get(),
            "ue_elem_pat": self.app.ue_elem_pat.get(),
            "ue_min_arr_gain": self.app.ue_min_arr_gain.get(),
            "ue_elem_max_g": self.app.ue_elem_max_g.get(),
            "ue_phi3": self.app.ue_phi3.get(),
            "ue_theta3": self.app.ue_theta3.get(),
            "ue_rows": self.app.ue_rows.get(),
            "ue_cols": self.app.ue_cols.get(),
            "ue_elem_am": self.app.ue_elem_am.get(),
            "ue_elem_sla_v": self.app.ue_elem_sla_v.get(),
            "ue_mult": self.app.ue_mult.get(),
            # UL/DL
            "ul_att": self.app.ul_att.get(),
            "ul_sinr_min": self.app.ul_sinr_min.get(),
            "ul_sinr_max": self.app.ul_sinr_max.get(),
            "dl_att": self.app.dl_att.get(),
            "dl_sinr_min": self.app.dl_sinr_min.get(),
            "dl_sinr_max": self.app.dl_sinr_max.get(),
            "ch_model": self.app.ch_model.get(),
            "shadowing": self.app.shadowing.get(),
        }
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[
                                            ("JSON", "*.json")], initialfile="imt_config.json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("IMT", f"Configuração salva em:\n{path}")

    def _load_imt_config(self):
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

        S("imt_min_sep", self.app.imt_min_sep)
        S("imt_interfered", self.app.imt_interfered)
        S("imt_freq", self.app.imt_freq)
        S("imt_bw", self.app.imt_bw)
        S("imt_rb_bw", self.app.imt_rb_bw)
        S("imt_spec_mask", self.app.imt_spec_mask)
        S("imt_spurious", self.app.imt_spurious)
        S("imt_adj_ant_model", self.app.imt_adj_ant_model)
        S("imt_guard_ratio", self.app.imt_guard_ratio)
        S("topo_c_lat", self.app.topo_c_lat)
        S("topo_c_lon", self.app.topo_c_lon)
        S("topo_c_alt", self.app.topo_c_alt)
        S("topo_type", self.app.topo_type)
        S("topo_dist_type", self.app.topo_dist_type)
        S("topo_num_bs", self.app.topo_num_bs)
        S("topo_cell_radius", self.app.topo_cell_radius)
        S("topo_rng", self.app.topo_rng)

        if "countries" in vals:
            self.txt_countries.delete("1.0", "end")
            self.txt_countries.insert("1.0", vals["countries"])

        S("path_shp", self.app.path_shp)
        S("path_raster", self.app.path_raster)
        S("raster_encoding", self.app.topo_raster_enc)
        S("sedac_mode", self.app.sedac_mode)
        S("sedac_min", self.app.sedac_min)
        S("sedac_max", self.app.sedac_max)
        S("pixel_area_method", self.app.pixel_area_method)

        # BS
        S("bs_load_prob", self.app.bs_load_prob)
        S("bs_power", self.app.bs_power)
        S("bs_height", self.app.bs_height)
        S("bs_nf", self.app.bs_nf)
        S("bs_ohmic", self.app.bs_ohmic)
        S("bs_norm", self.app.bs_norm)
        S("bs_elem_pat", self.app.bs_elem_pat)
        S("bs_min_arr_gain", self.app.bs_min_arr_gain)
        S("bs_downtilt", self.app.bs_downtilt)
        S("bs_elem_max_g", self.app.bs_elem_max_g)
        S("bs_phi3", self.app.bs_phi3)
        S("bs_theta3", self.app.bs_theta3)
        S("bs_rows", self.app.bs_rows)
        S("bs_cols", self.app.bs_cols)
        S("bs_elem_hs", self.app.bs_elem_hs)
        S("bs_elem_vs", self.app.bs_elem_vs)
        S("bs_elem_am", self.app.bs_elem_am)
        S("bs_elem_sla_v", self.app.bs_elem_sla_v)
        S("bs_mult", self.app.bs_mult)
        S("bs_sub_enabled", self.app.bs_sub_enabled)
        S("bs_sub_rows", self.app.bs_sub_rows)
        S("bs_sub_evspace", self.app.bs_sub_evspace)
        S("bs_sub_e_downtilt", self.app.bs_sub_e_downtilt)

        # UE
        S("ue_k", self.app.ue_k)
        S("ue_km", self.app.ue_km)
        S("ue_indoor", self.app.ue_indoor)
        S("ue_dist_type", self.app.ue_dist_type)
        S("ue_tx_power_ctrl", self.app.ue_tx_power_ctrl)
        S("ue_p_o_pusch", self.app.ue_p_o_pusch)
        S("ue_alpha", self.app.ue_alpha)
        S("ue_p_cmax", self.app.ue_p_cmax)
        S("ue_p_dyn", self.app.ue_p_dyn)
        S("ue_height", self.app.ue_height)
        S("ue_nf", self.app.ue_nf)
        S("ue_ohmic", self.app.ue_ohmic)
        S("ue_body_loss", self.app.ue_body_loss)
        S("ue_norm", self.app.ue_norm)
        S("ue_elem_pat", self.app.ue_elem_pat)
        S("ue_min_arr_gain", self.app.ue_min_arr_gain)
        S("ue_elem_max_g", self.app.ue_elem_max_g)
        S("ue_phi3", self.app.ue_phi3)
        S("ue_theta3", self.app.ue_theta3)
        S("ue_rows", self.app.ue_rows)
        S("ue_cols", self.app.ue_cols)
        S("ue_elem_am", self.app.ue_elem_am)
        S("ue_elem_sla_v", self.app.ue_elem_sla_v)
        S("ue_mult", self.app.ue_mult)

        # UL/DL
        S("ul_att", self.app.ul_att)
        S("ul_sinr_min", self.app.ul_sinr_min)
        S("ul_sinr_max", self.app.ul_sinr_max)
        S("dl_att", self.app.dl_att)
        S("dl_sinr_min", self.app.dl_sinr_min)
        S("dl_sinr_max", self.app.dl_sinr_max)
        S("ch_model", self.app.ch_model)
        S("shadowing", self.app.shadowing)

        # Atualiza a visibilidade dos frames após carregar
        self._toggle_topology_frames()
        self._toggle_raster_by_encoding()
        self._toggle_ue_distribution()

        messagebox.showinfo("IMT", "Configuração IMT carregada.")
