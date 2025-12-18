import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, Any, Optional

# Assumindo que estas importações existem no seu projeto
from utils import add_row_three
from ui.tabs.assets.imt_state import IMTStateManager

# Constantes de Estilo para padronização
PAD_X = (6, 4)
PAD_Y = 2
SECTION_PAD_Y = (2, 8)


class IMTTab:
    def __init__(self, app, parent_frame: tk.Widget):
        self.app = app
        self.frame = parent_frame

        # Inicializa o gerenciador de estado
        self.state = IMTStateManager()

        # Variáveis de UI que precisam ser acessadas em outros métodos
        self.inner_frame: Optional[ttk.Frame] = None
        self.txt_countries: Optional[tk.Text] = None

        # Referências aos frames de topologia para o toggle
        self.frm_t_countries: Optional[ttk.LabelFrame] = None
        self.frm_t_macro: Optional[ttk.LabelFrame] = None
        self.frm_t_hotspot: Optional[ttk.LabelFrame] = None
        self.frm_t_sbs: Optional[ttk.LabelFrame] = None
        self.col_dist_ue: Optional[ttk.LabelFrame] = None

        # Widgets de inputs específicos que precisam de referência
        self.ent_raster: Optional[ttk.Entry] = None
        self.btn_raster: Optional[ttk.Button] = None

        # Constrói a interface
        self._init_ui()

    def _init_ui(self):
        """Método mestre que orquestra a construção da interface."""
        self._setup_scroll_container()

        # Construção dos blocos
        self._build_topbar()
        self._build_general_section()
        self._build_topology_section()
        self._build_bs_section()
        self._build_ue_section()
        self._build_channel_section()

        # Configuração final (binds e estado inicial)
        self._setup_initial_state()

    # ================== 1. ESTRUTURA BÁSICA (SCROLL) ==================
    def _setup_scroll_container(self):
        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.inner_frame = ttk.Frame(canvas)
        # Anchor nw é importante para que o frame comece no topo
        canvas_window = canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw")

        def _on_frame_config(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Garante que o inner_frame ocupe a largura do canvas
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        self.inner_frame.bind("<Configure>", _on_frame_config)

        # Bind no canvas também para redimensionamento da janela
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            canvas_window, width=e.width))

        # Mousewheel
        def _on_mousewheel(event):
            # Proteção para plataformas diferentes
            if self.inner_frame.winfo_exists():
                delta = int(-1 * (event.delta / 120))
                canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all(
            "<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all(
            "<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    # ================== 2. SEÇÕES DA UI ==================
    def _build_topbar(self):
        topbar = ttk.Frame(self.inner_frame)
        topbar.pack(fill="x", pady=(0, 6))

        ttk.Button(topbar, text="Salvar configuração IMT (.json)",
                   command=self._save_proxy).pack(side="left")

        ttk.Button(topbar, text="Carregar configuração IMT (.json)",
                   command=self._load_proxy).pack(side="left", padx=(6, 0))

    def _build_general_section(self):
        frm_g = ttk.LabelFrame(
            self.inner_frame, text="IMT – Parâmetros gerais")
        frm_g.pack(fill="x", pady=SECTION_PAD_Y)

        add_row_three(frm_g, 0, [
            ("minimum_separation_distance_bs_ue [m]",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_min_sep"), width=10)),
            ("interfered_with",
             ttk.Combobox(frm_g, textvariable=self.state.get("imt_interfered"), values=[False, True], state="readonly", width=8)),
            ("frequency [MHz]",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_freq"), width=12)),
        ])
        add_row_three(frm_g, 1, [
            ("bandwidth [MHz]",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_bw"), width=10)),
            ("rb_bandwidth [MHz]",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_rb_bw"), width=10)),
            ("spectral_mask",
             ttk.Combobox(frm_g, textvariable=self.state.get("imt_spec_mask"), values=["IMT-2020", "3GPP"], state="readonly", width=12)),
        ])
        add_row_three(frm_g, 2, [
            ("spurious_emissions [dBc]",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_spurious"), width=10)),
            ("adjacent_antenna_model",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_adj_ant_model"), width=16)),
            ("guard_band_ratio",
             ttk.Entry(frm_g, textvariable=self.state.get("imt_guard_ratio"), width=10)),
        ])

    def _build_topology_section(self):
        frm_t = ttk.LabelFrame(self.inner_frame, text="Topologia – IMT")
        frm_t.pack(fill="x", pady=SECTION_PAD_Y)

        # Seletor de Tipo
        row_type = ttk.Frame(frm_t)
        row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 4))

        ttk.Label(row_type, text="type").pack(side="left")
        cb_topo_type = ttk.Combobox(row_type, textvariable=self.state.get("topo_type"),
                                    values=["MACROCELL", "HOTSPOT",
                                            "SINGLE_BS", "Macro_countries"],
                                    state="readonly", width=18)
        cb_topo_type.pack(side="left", padx=(6, 0))
        # Bind para atualizar visualização
        cb_topo_type.bind("<<ComboboxSelected>>", self._toggle_topology_frames)

        # Parâmetros comuns de topologia
        add_row_three(frm_t, 1, [
            ("central_latitude", ttk.Entry(
                frm_t, textvariable=self.state.get("topo_c_lat"), width=12)),
            ("central_longitude", ttk.Entry(
                frm_t, textvariable=self.state.get("topo_c_lon"), width=12)),
            ("central_altitude [m]", ttk.Entry(
                frm_t, textvariable=self.state.get("topo_c_alt"), width=12)),
        ])

        # Sub-seções (Frames)
        self._build_topology_countries(frm_t)
        self._build_topology_macro(frm_t)
        self._build_topology_hotspot(frm_t)
        self._build_topology_sbs(frm_t)

    def _build_topology_countries(self, parent):
        self.frm_t_countries = ttk.LabelFrame(
            parent, text="Topologia – COUNTRIES (Macro_countries)")
        self.frm_t_countries.grid(
            row=2, column=0, columnspan=6, sticky="we", pady=(4, 8))

        # Opções de Raster/Dist
        row_opts = ttk.Frame(self.frm_t_countries)
        row_opts.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2, 4))

        self._add_inline_combo(row_opts, "raster_encoding", self.state.get("topo_raster_enc"), [
                               "Uniforme", "Denspop"], width=12, command=self._toggle_raster_by_encoding)
        self._add_inline_combo(row_opts, "dist_type", self.state.get("topo_dist_type"), [
                               "Urban", "Suburban", "Rural"], width=12, pack_padx=(6, 0))

        # Text Area
        row_c = ttk.Frame(self.frm_t_countries)
        row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row_c, text="country_names (1/linha)").pack(side="left")

        self.txt_countries = tk.Text(row_c, width=48, height=7)
        self.txt_countries.insert("1.0", self.state.get("countries").get())
        self.txt_countries.pack(side="left", fill="x",
                                expand=True, padx=(6, 6))

        add_row_three(self.frm_t_countries, 2, [
            ("num_bs_total", ttk.Entry(self.frm_t_countries,
             textvariable=self.state.get("topo_num_bs"), width=10)),
            ("cell_radius [m]", ttk.Entry(self.frm_t_countries,
             textvariable=self.state.get("topo_cell_radius"), width=10)),
            ("rng_seed", ttk.Entry(self.frm_t_countries,
             textvariable=self.state.get("topo_rng"), width=10)),
        ])

        # File Pickers
        self._add_file_picker_row(self.frm_t_countries, 3, "countries_shapefile",
                                  self.state.get("path_shp"), self._browse_shapefile)

        self.ent_raster, self.btn_raster = self._add_file_picker_row(
            self.frm_t_countries, 4, "population_raster",
            self.state.get("path_raster"), self._browse_raster, return_widgets=True)

    def _build_topology_macro(self, parent):
        self.frm_t_macro = ttk.LabelFrame(parent, text="Topologia – MACROCELL")
        self.frm_t_macro.grid(row=3, column=0, columnspan=6,
                              sticky="we", pady=(4, 8))

        add_row_three(self.frm_t_macro, 0, [
            ("intersite_distance [m]", ttk.Entry(
                self.frm_t_macro, textvariable=self.state.get("macro_intersite"), width=10)),
            ("wrap_around", ttk.Combobox(self.frm_t_macro, textvariable=self.state.get(
                "macro_wrap"), values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(self.frm_t_macro,
             textvariable=self.state.get("macro_clusters"), width=8)),
        ])

    def _build_topology_hotspot(self, parent):
        self.frm_t_hotspot = ttk.LabelFrame(parent, text="Topologia – HOTSPOT")
        self.frm_t_hotspot.grid(
            row=4, column=0, columnspan=6, sticky="we", pady=(4, 8))

        add_row_three(self.frm_t_hotspot, 0, [
            ("intersite_distance [m]", ttk.Entry(
                self.frm_t_hotspot, textvariable=self.state.get("hotspot_intersite"), width=10)),
            ("wrap_around", ttk.Combobox(self.frm_t_hotspot, textvariable=self.state.get(
                "hotspot_wrap"), values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(self.frm_t_hotspot,
             textvariable=self.state.get("hotspot_clusters"), width=8)),
        ])
        add_row_three(self.frm_t_hotspot, 1, [
            ("num_hotspots_per_cell", ttk.Entry(self.frm_t_hotspot,
             textvariable=self.state.get("hotspot_num_per_cell"), width=10)),
            ("max_dist_hotspot_ue [m]", ttk.Entry(
                self.frm_t_hotspot, textvariable=self.state.get("hotspot_max_dist_ue"), width=12)),
            ("min_dist_bs_hotspot [m]", ttk.Entry(
                self.frm_t_hotspot, textvariable=self.state.get("hotspot_min_dist_bs"), width=12)),
        ])

    def _build_topology_sbs(self, parent):
        self.frm_t_sbs = ttk.LabelFrame(parent, text="Topologia – SINGLE_BS")
        self.frm_t_sbs.grid(row=5, column=0, columnspan=6,
                            sticky="we", pady=(4, 8))

        add_row_three(self.frm_t_sbs, 0, [
            ("intersite_distance [m]", ttk.Entry(
                self.frm_t_sbs, textvariable=self.state.get("sbs_intersite"), width=10)),
            ("cell_radius [m]", ttk.Entry(
                self.frm_t_sbs, textvariable=self.state.get("sbs_cell_radius"), width=10)),
            ("num_clusters", ttk.Entry(self.frm_t_sbs,
             textvariable=self.state.get("sbs_clusters"), width=8)),
        ])
        add_row_three(self.frm_t_sbs, 1, [
            ("azimuth (lista ou str)", ttk.Entry(self.frm_t_sbs,
             textvariable=self.state.get("sbs_azimuth"), width=28)),
            ("", ttk.Label(self.frm_t_sbs, text="")),
            ("", ttk.Label(self.frm_t_sbs, text="")),
        ])

    def _build_bs_section(self):
        frm_bs = ttk.LabelFrame(self.inner_frame, text="BS – Parâmetros")
        frm_bs.pack(fill="x", padx=6, pady=8)
        for c in range(3):
            frm_bs.columnconfigure(c, weight=1, uniform="bscols")

        # BS Basic
        col_basic = self._create_sub_column(frm_bs, 0, "BS – Básico")
        self._add_field(col_basic, 0, "load_probability", ttk.Entry(
            col_basic, textvariable=self.state.get("bs_load_prob"), width=10))
        self._add_field(col_basic, 1, "conducted_power [dBm]", ttk.Entry(
            col_basic, textvariable=self.state.get("bs_power"), width=10))
        self._add_field(col_basic, 2, "height [m]", ttk.Entry(
            col_basic, textvariable=self.state.get("bs_height"), width=10))
        self._add_field(col_basic, 3, "noise_figure [dB]", ttk.Entry(
            col_basic, textvariable=self.state.get("bs_nf"), width=10))
        self._add_field(col_basic, 4, "ohmic_loss [dB]", ttk.Entry(
            col_basic, textvariable=self.state.get("bs_ohmic"), width=10))

        # BS Array
        col_array = self._create_sub_column(frm_bs, 1, "BS – Array da Antena")
        self._add_field(col_array, 0, "normalization", ttk.Checkbutton(
            col_array, variable=self.state.get("bs_norm"), text=""))
        self._add_field(col_array, 1, "element_pattern", ttk.Combobox(col_array, textvariable=self.state.get(
            "bs_elem_pat"), values=["M2101", "ITU-R S.672", "Custom"], state="readonly", width=14))
        self._add_field(col_array, 2, "minimum_array_gain [dB]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_min_arr_gain"), width=10))

        self._add_range(col_array, 3, "h_beamsteer [deg]",
                        ttk.Entry(col_array, textvariable=self.state.get(
                            "bs_h_steer_min"), width=7),
                        ttk.Entry(col_array, textvariable=self.state.get("bs_h_steer_max"), width=7))
        self._add_range(col_array, 4, "v_beamsteer [deg]",
                        ttk.Entry(col_array, textvariable=self.state.get(
                            "bs_v_steer_min"), width=7),
                        ttk.Entry(col_array, textvariable=self.state.get("bs_v_steer_max"), width=7))

        self._add_field(col_array, 5, "downtilt [deg]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_downtilt"), width=10))
        self._add_field(col_array, 6, "element_max_g [dBi]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_elem_max_g"), width=10))
        self._add_field(col_array, 7, "element_phi_3db [deg]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_phi3"), width=10))
        self._add_field(col_array, 8, "element_theta_3db [deg]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_theta3"), width=10))
        self._add_field(col_array, 9, "n_rows", ttk.Entry(
            col_array, textvariable=self.state.get("bs_rows"), width=10))
        self._add_field(col_array, 10, "n_columns", ttk.Entry(
            col_array, textvariable=self.state.get("bs_cols"), width=10))
        self._add_field(col_array, 11, "element_horiz_spacing [λ]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_elem_hs"), width=10))
        self._add_field(col_array, 12, "element_vert_spacing [λ]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_elem_vs"), width=10))
        self._add_field(col_array, 13, "element_am [dB]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_elem_am"), width=10))
        self._add_field(col_array, 14, "element_sla_v [dB]", ttk.Entry(
            col_array, textvariable=self.state.get("bs_elem_sla_v"), width=10))
        self._add_field(col_array, 15, "multiplication_factor", ttk.Entry(
            col_array, textvariable=self.state.get("bs_mult"), width=10))

        # BS Sub-array
        col_sub = self._create_sub_column(frm_bs, 2, "BS – Sub-array")
        self._add_field(col_sub, 0, "is_enabled", ttk.Checkbutton(
            col_sub, variable=self.state.get("bs_sub_enabled"), text=""))
        self._add_field(col_sub, 1, "n_rows", ttk.Entry(
            col_sub, textvariable=self.state.get("bs_sub_rows"), width=10))
        self._add_field(col_sub, 2, "element_vert_spacing [λ]", ttk.Entry(
            col_sub, textvariable=self.state.get("bs_sub_evspace"), width=10))
        self._add_field(col_sub, 3, "eletrical_downtilt [deg]", ttk.Entry(
            col_sub, textvariable=self.state.get("bs_sub_e_downtilt"), width=10))

    def _build_ue_section(self):
        frm_ue = ttk.LabelFrame(self.inner_frame, text="UE – Parâmetros")
        frm_ue.pack(fill="x", padx=6, pady=8)
        for c in range(3):
            frm_ue.columnconfigure(c, weight=1, uniform="uecols")

        # UE Basic
        col_basic = self._create_sub_column(frm_ue, 0, "UE – Básico")
        self._add_field(col_basic, 0, "k", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_k"), width=8))
        self._add_field(col_basic, 1, "k_m", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_km"), width=8))
        self._add_field(col_basic, 2, "indoor_percent [%]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_indoor"), width=8))

        cb_ue_dist = ttk.Combobox(col_basic, textvariable=self.state.get("ue_dist_type"),
                                  values=["Macro_countries", "UNIFORM", "CELL", "UNIFORM_IN_CELL", "ANGLE_AND_DISTANCE"], state="readonly", width=18)
        self._add_field(col_basic, 3, "distribution_type", cb_ue_dist)
        cb_ue_dist.bind("<<ComboboxSelected>>",
                        lambda e: self._toggle_ue_distribution())

        self._add_field(col_basic, 4, "tx_power_control", ttk.Checkbutton(
            col_basic, variable=self.state.get("ue_tx_power_ctrl"), text=""))
        self._add_field(col_basic, 5, "p_o_pusch [dBm]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_p_o_pusch"), width=10))
        self._add_field(col_basic, 6, "alpha", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_alpha"), width=10))
        self._add_field(col_basic, 7, "p_cmax [dBm]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_p_cmax"), width=10))
        self._add_field(col_basic, 8, "power_dynamic_range [dB]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_p_dyn"), width=10))
        self._add_field(col_basic, 9, "height [m]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_height"), width=10))
        self._add_field(col_basic, 10, "noise_figure [dB]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_nf"), width=10))
        self._add_field(col_basic, 11, "ohmic_loss [dB]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_ohmic"), width=10))
        self._add_field(col_basic, 12, "body_loss [dB]", ttk.Entry(
            col_basic, textvariable=self.state.get("ue_body_loss"), width=10))

        # UE Array
        col_array = self._create_sub_column(frm_ue, 1, "UE – Array da Antena")
        self._add_field(col_array, 0, "normalization", ttk.Checkbutton(
            col_array, variable=self.state.get("ue_norm"), text=""))
        self._add_field(col_array, 1, "element_pattern", ttk.Combobox(col_array, textvariable=self.state.get(
            "ue_elem_pat"), values=["FIXED", "M2101", "Custom"], state="readonly", width=14))
        self._add_field(col_array, 2, "minimum_array_gain [dB]", ttk.Entry(
            col_array, textvariable=self.state.get("ue_min_arr_gain"), width=10))
        self._add_field(col_array, 3, "element_max_g [dBi]", ttk.Entry(
            col_array, textvariable=self.state.get("ue_elem_max_g"), width=10))
        self._add_field(col_array, 4, "element_phi_3db [deg]", ttk.Entry(
            col_array, textvariable=self.state.get("ue_phi3"), width=10))
        self._add_field(col_array, 5, "element_theta_3db [deg]", ttk.Entry(
            col_array, textvariable=self.state.get("ue_theta3"), width=10))
        self._add_field(col_array, 6, "n_rows", ttk.Entry(
            col_array, textvariable=self.state.get("ue_rows"), width=10))
        self._add_field(col_array, 7, "n_columns", ttk.Entry(
            col_array, textvariable=self.state.get("ue_cols"), width=10))
        self._add_field(col_array, 8, "element_am [dB]", ttk.Entry(
            col_array, textvariable=self.state.get("ue_elem_am"), width=10))
        self._add_field(col_array, 9, "element_sla_v [dB]", ttk.Entry(
            col_array, textvariable=self.state.get("ue_elem_sla_v"), width=10))
        self._add_field(col_array, 10, "multiplication_factor", ttk.Entry(
            col_array, textvariable=self.state.get("ue_mult"), width=10))

        # UE Sub-array
        col_sub = self._create_sub_column(frm_ue, 2, "UE – Sub-array")
        self._add_field(col_sub, 0, "is_enabled", ttk.Checkbutton(
            col_sub, variable=self.state.get("ue_sub_enabled"), text=""))
        self._add_field(col_sub, 1, "n_rows", ttk.Entry(
            col_sub, textvariable=self.state.get("ue_sub_rows"), width=10))
        self._add_field(col_sub, 2, "element_vert_spacing [λ]", ttk.Entry(
            col_sub, textvariable=self.state.get("ue_sub_evspace"), width=10))
        self._add_field(col_sub, 3, "eletrical_downtilt [deg]", ttk.Entry(
            col_sub, textvariable=self.state.get("ue_sub_e_downtilt"), width=10))

        # UE Dist (Linha extra)
        self.col_dist_ue = ttk.LabelFrame(
            frm_ue, text="UE – Distribuição (Angle&Distance)")
        self.col_dist_ue.grid(
            row=1, column=0, sticky="nsew", padx=(3, 6), pady=(0, 6))
        for c in range(4):
            self.col_dist_ue.columnconfigure(
                c, weight=(1 if c in (1, 3) else 0))

        self._add_field(self.col_dist_ue, 0, "distribution_distance",
                        ttk.Combobox(self.col_dist_ue, textvariable=self.state.get("ue_dist_distance"), values=["RAYLEIGH", "UNIFORM", "SQRT(UNIFORM)"], state="readonly", width=16))
        self._add_field(self.col_dist_ue, 1, "distribution_azimuth",
                        ttk.Combobox(self.col_dist_ue, textvariable=self.state.get("ue_dist_azimuth"), values=["NORMAL", "UNIFORM"], state="readonly", width=16))
        self._add_range(self.col_dist_ue, 2, "azimuth_range [deg]",
                        ttk.Entry(self.col_dist_ue, textvariable=self.state.get(
                            "ue_az_min"), width=8),
                        ttk.Entry(self.col_dist_ue, textvariable=self.state.get("ue_az_max"), width=8))

    def _build_channel_section(self):
        frm_l = ttk.LabelFrame(
            self.inner_frame, text="UL / DL / Channel / Shadowing")
        frm_l.pack(fill="x", pady=SECTION_PAD_Y)

        add_row_three(frm_l, 0, [
            ("uplink.attenuation_factor", ttk.Entry(
                frm_l, textvariable=self.state.get("ul_att"), width=8)),
            ("uplink.sinr_min / sinr_max [dB]", self._pair_entries(
                frm_l, self.state.get("ul_sinr_min"), self.state.get("ul_sinr_max"), w=8)),
            ("downlink.attenuation_factor", ttk.Entry(
                frm_l, textvariable=self.state.get("dl_att"), width=8)),
        ])
        add_row_three(frm_l, 1, [
            ("downlink.sinr_min / sinr_max [dB]", self._pair_entries(
                frm_l, self.state.get("dl_sinr_min"), self.state.get("dl_sinr_max"), w=8)),
            ("channel_model", ttk.Entry(
                frm_l, textvariable=self.state.get("ch_model"), width=12)),
            ("shadowing", ttk.Combobox(frm_l, textvariable=self.state.get(
                "shadowing"), values=[True, False], state="readonly", width=8)),
        ])

    def _setup_initial_state(self):
        """Aplica a visibilidade inicial baseada nos valores carregados ou default."""
        self._toggle_topology_frames()
        self._toggle_raster_by_encoding()
        self._toggle_ue_distribution()

    # ================== 3. UI HELPER METHODS ==================
    def _create_sub_column(self, parent, col_idx, title):
        frame = ttk.LabelFrame(parent, text=title)
        frame.grid(row=0, column=col_idx, sticky="nsew", padx=3, pady=6)
        for c in range(4):
            frame.columnconfigure(c, weight=(1 if c in (1, 3) else 0))
        return frame

    def _add_inline_combo(self, parent, text, variable, values, width=12, command=None, pack_padx=(0, 0)):
        ttk.Label(parent, text=text).pack(side="left")
        cb = ttk.Combobox(parent, textvariable=variable,
                          values=values, state="readonly", width=width)
        cb.pack(side="left", padx=pack_padx)
        if command:
            cb.bind("<<ComboboxSelected>>", command)
        return cb

    def _add_file_picker_row(self, parent, row, label, variable, command, return_widgets=False):
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=row, column=0, columnspan=6,
                       sticky="we", pady=(2, 2))
        ttk.Label(row_frame, text=label).pack(side="left")

        entry = ttk.Entry(row_frame, textvariable=variable, width=64)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))

        btn = ttk.Button(row_frame, text="…", width=3, command=command)
        btn.pack(side="left")

        if return_widgets:
            return entry, btn

    def _add_field(self, parent, row, label, widget, col=0, col_span=2):
        ttk.Label(parent, text=label).grid(
            row=row, column=col, sticky="w", padx=PAD_X, pady=PAD_Y)
        widget.grid(row=row, column=col + 1, columnspan=col_span -
                    1, sticky="we", padx=(0, 6), pady=PAD_Y)

    def _add_range(self, parent, row, label, wmin, wmax, sep_text="a"):
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", padx=PAD_X, pady=PAD_Y)
        wmin.grid(row=row, column=1, sticky="we", padx=(0, 4), pady=PAD_Y)
        ttk.Label(parent, text=f" {sep_text} ").grid(
            row=row, column=2, padx=(0, 4))
        wmax.grid(row=row, column=3, sticky="we", padx=(0, 6), pady=PAD_Y)

    def _pair_entries(self, parent, var1, var2, w=6):
        f = ttk.Frame(parent)
        e1 = ttk.Entry(f, textvariable=var1, width=w)
        e1.pack(side="left")
        ttk.Label(f, text=" / ").pack(side="left")
        e2 = ttk.Entry(f, textvariable=var2, width=w)
        e2.pack(side="left")
        return f

    # ================== 4. LÓGICA DE EVENTOS (TOGGLES) ==================
    def _toggle_topology_frames(self, *_):
        # Esconde todos primeiro
        for f in (self.frm_t_countries, self.frm_t_macro, self.frm_t_hotspot, self.frm_t_sbs):
            if f:
                f.grid_remove()

        t = self.state.get("topo_type").get()
        mapping = {
            "Macro_countries": self.frm_t_countries,
            "MACROCELL": self.frm_t_macro,
            "HOTSPOT": self.frm_t_hotspot,
            "SINGLE_BS": self.frm_t_sbs
        }

        target = mapping.get(t)
        if target:
            target.grid()

    def _toggle_raster_by_encoding(self, *_):
        if not self.ent_raster:
            return

        enc = (self.state.get("topo_raster_enc").get() or "").strip()
        state = "disabled" if enc == "Uniforme" else "normal"

        if enc == "Uniforme":
            self.state.get("path_raster").set("")

        self.ent_raster.configure(state=state)
        self.btn_raster.configure(state=state)

    def _toggle_ue_distribution(self):
        if not self.col_dist_ue:
            return
        is_ang_dist = (self.state.get(
            "ue_dist_type").get().upper() == "ANGLE_AND_DISTANCE")
        if is_ang_dist:
            self.col_dist_ue.grid()
        else:
            self.col_dist_ue.grid_remove()

    # ================== 5. PERSISTÊNCIA & ARQUIVOS ==================
    def _save_proxy(self):
        # Coleta dados extras que não estão nas variáveis (o Text Widget)
        extra = {}
        if self.txt_countries:
            extra["countries"] = self.txt_countries.get("1.0", "end").strip()
        self.state.save_to_file(extra)

    def _load_proxy(self):
        data = self.state.load_from_file(
            callback_after_load=lambda d: [
                self._setup_initial_state()
            ]
        )
        if data and "countries" in data and self.txt_countries:
            self.txt_countries.delete("1.0", "end")
            self.txt_countries.insert("1.0", data["countries"])

    def _browse_shapefile(self):
        fn = filedialog.askopenfilename(title="Escolher shapefile",
                                        filetypes=[("Shapefile", "*.shp"), ("All", "*.*")])
        if fn:
            self.state.get("path_shp").set(fn)

    def _browse_raster(self):
        fn = filedialog.askopenfilename(title="Escolher raster",
                                        filetypes=[("GeoTIFF", "*.tif;*.tiff"), ("All", "*.*")])
        if fn:
            self.state.get("path_raster").set(fn)
