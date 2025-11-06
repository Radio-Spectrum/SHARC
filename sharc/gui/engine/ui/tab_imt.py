import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.utils import add_row_three, _add_field, _add_range
from core.imt_data.imt_handler import _save_imt_config, _load_imt_config
from core.shp_control import _browse_raster, _browse_shapefile, _toggle_raster_by_encoding

# Note: The helper functions add_row_three, self._add_field, 
# and self._add_range were not provided,
# but the main function logic is translated below.

def build_imt_tab(self, root):
    """Builds the 'IMT' tab UI elements."""
    
    imt_min_sep = root.imt_min_sep
    imt_interfered = root.imt_interfered
    imt_freq = root.imt_freq

    imt_bw = root.imt_bw
    imt_rb_bw = root.imt_rb_bw
    imt_spec_mask = root.imt_spec_mask

    imt_spurious = root.imt_spurious
    imt_adj_ant_model = root.imt_adj_ant_model
    imt_guard_ratio = root.imt_guard_ratio

    topo_type = root.topo_type
    topo_c_lat = root.topo_c_lat
    topo_c_lon = root.topo_c_lon
    topo_c_alt = root.topo_c_alt

    topo_raster_enc = root.topo_raster_enc
    topo_dist_type = root.topo_dist_type
    topo_countries = root.topo_countries

    topo_num_bs = root.topo_num_bs
    topo_cell_radius = root.topo_cell_radius
    topo_rng = root.topo_rng

    path_shp = root.path_shp
    path_raster = root.path_raster

    macro_intersite = root.macro_intersite
    macro_wrap = root.macro_wrap
    macro_clusters = root.macro_clusters

    hotspot_intersite = root.hotspot_intersite
    hotspot_wrap = root.hotspot_wrap
    hotspot_clusters = root.hotspot_clusters

    hotspot_num_per_cell = root.hotspot_num_per_cell
    hotspot_max_dist_ue = root.hotspot_max_dist_ue
    hotspot_min_dist_bs = root.hotspot_min_dist_bs

    sbs_intersite = root.sbs_intersite
    sbs_cell_radius = root.sbs_cell_radius
    sbs_clusters = root.sbs_clusters
    sbs_azimuth = root.sbs_azimuth

    bs_load_prob = root.bs_load_prob
    bs_power = root.bs_power
    bs_height = root.bs_height
    bs_nf = root.bs_nf
    bs_ohmic = root.bs_ohmic
    bs_norm = root.bs_norm
    bs_elem_pat = root.bs_elem_pat
    bs_min_arr_gain = root.bs_min_arr_gain
    bs_h_steer = root.bs_h_steer
    bs_v_steer = root.bs_v_steer
    bs_downtilt = root.bs_downtilt
    bs_elem_max_g = root.bs_elem_max_g
    bs_phi3 = root.bs_phi3
    bs_theta3 = root.bs_theta3
    bs_rows = root.bs_rows
    bs_cols = root.bs_cols
    bs_elem_hs = root.bs_elem_hs
    bs_elem_vs = root.bs_elem_vs
    bs_elem_am = root.bs_elem_am
    bs_elem_sla_v = root.bs_elem_sla_v
    bs_mult = root.bs_mult
    bs_sub_enabled = root.bs_sub_enabled
    bs_sub_rows = root.bs_sub_rows
    bs_sub_evspace = root.bs_sub_evspace 
    bs_sub_e_downtilt = root.bs_sub_e_downtilt
    ue_k = root.ue_k
    ue_km = root.ue_km
    ue_indoor = root.ue_indoor



    # ===== Scrollable container for the IMT tab =====
    container = ttk.Frame(root)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0)
    vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)

    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # The actual frame where you add the widgets
    imt_body = ttk.Frame(canvas)
    # create a window inside the canvas
    canvas_window = canvas.create_window((0, 0), window=imt_body, anchor="nw")

    def _on_frame_config(event):
        # adjust scroll region to fit content
        canvas.configure(scrollregion=canvas.bbox("all"))
        # keep the frame width equal to the visible canvas width
        canvas.itemconfig(canvas_window, width=canvas.winfo_width())

    imt_body.bind("<Configure>", _on_frame_config)

    # mouse wheel support
    def _on_mousewheel(event):
        # Windows / Linux
        delta = int(-1*(event.delta/120))
        canvas.yview_scroll(delta, "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)      # Windows
    canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
    canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll( 1, "units"))  # Linux

    # >>> From here on, use 'imt_body' instead of 'root' to build the IMT tab UI
    root = imt_body

    topbar = ttk.Frame(root)
    topbar.pack(fill="x", pady=(0, 6))
    ttk.Button(topbar, text="Save IMT config (.json)", command=_save_imt_config).pack(side="left")
    ttk.Button(topbar, text="Load IMT config (.json)", command=_load_imt_config).pack(side="left", padx=(6, 0))

    frm_g = ttk.LabelFrame(root, text="IMT – General Parameters")
    frm_g.pack(fill="x", pady=(2, 8))

    add_row_three(frm_g, 0, [
        ("minimum_separation_distance_bs_ue [m]", ttk.Entry(frm_g, textvariable=imt_min_sep, width=10)),
        ("interfered_with", ttk.Combobox(frm_g, textvariable=imt_interfered, values=[False, True], state="readonly", width=8)),
        ("frequency [MHz]", ttk.Entry(frm_g, textvariable=imt_freq, width=12)),
    ])
    add_row_three(frm_g, 1, [
        ("bandwidth [MHz]", ttk.Entry(frm_g, textvariable=imt_bw, width=10)),
        ("rb_bandwidth [MHz]", ttk.Entry(frm_g, textvariable=imt_rb_bw, width=10)),
        ("spectral_mask", ttk.Combobox(frm_g, textvariable=imt_spec_mask, values=["IMT-2020", "3GPP"], state="readonly", width=12)),
    ])
    add_row_three(frm_g, 2, [
        ("spurious_emissions [dBc]", ttk.Entry(frm_g, textvariable=imt_spurious, width=10)),
        ("adjacent_antenna_model", ttk.Entry(frm_g, textvariable=imt_adj_ant_model, width=16)),
        ("guard_band_ratio", ttk.Entry(frm_g, textvariable=imt_guard_ratio, width=10)),
    ])

    # ---------- Topology (type selector + subframes) ----------
    frm_t = ttk.LabelFrame(root, text="Topology – IMT")
    frm_t.pack(fill="x", pady=(2, 8))

    # Row 0: TYPE selector comes first
    row_type = ttk.Frame(frm_t)
    row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 4))
    ttk.Label(row_type, text="type").pack(side="left")
    cb_topo_type = ttk.Combobox(
        row_type, textvariable=topo_type,
        values=["MACROCELL", "HOTSPOT", "SINGLE_BS", "Macro_countries"], state="readonly", width=18
    )
    cb_topo_type.pack(side="left", padx=(6, 0))

    # Row 1: central (common) parameters
    add_row_three(frm_t, 1, [
        ("central_latitude", ttk.Entry(frm_t, textvariable=topo_c_lat, width=12)),
        ("central_longitude", ttk.Entry(frm_t, textvariable=topo_c_lon, width=12)),
        ("central_altitude [m]", ttk.Entry(frm_t, textvariable=topo_c_alt, width=12)),
    ])

    # ---- Subframe: Countries ----
    self.frm_t_countries = ttk.LabelFrame(frm_t, text="Topology – COUNTRIES (Macro_countries)")
    self.frm_t_countries.grid(row=2, column=0, columnspan=6, sticky="we", pady=(4, 8))

    # Row 0: raster_encoding + dist_type (ABOVE the countries list)
    row_opts = ttk.Frame(self.frm_t_countries)
    row_opts.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2, 4))

    ttk.Label(row_opts, text="raster_encoding").pack(side="left")
    cb_renc = ttk.Combobox(
        row_opts, textvariable=topo_raster_enc,
        values=["Uniforme", "Denspop"], state="readonly", width=12
    )
    cb_renc.pack(side="left", padx=(6, 16))

    ttk.Label(row_opts, text="dist_type").pack(side="left")
    cb_dist = ttk.Combobox(
        row_opts, textvariable=topo_dist_type,
        values=["Urban", "Suburban", "Rural"], state="readonly", width=12
    )
    cb_dist.pack(side="left", padx=(6, 0))
    # Visual tip: "" = None (no filter)

    # Row 1: List of countries (Text)
    row_c = ttk.Frame(self.frm_t_countries)
    row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row_c, text="country_names (1/line)").pack(side="left")
    self.txt_countries = tk.Text(row_c, width=48, height=7)
    self.txt_countries.insert("1.0", topo_countries.get())
    self.txt_countries.pack(side="left", fill="x", expand=True, padx=(6, 6))

    # Row 2: num_bs_total, cell_radius, rng_seed (if it existed, keep it)
    add_row_three(self.frm_t_countries, 2, [
        ("num_bs_total", ttk.Entry(self.frm_t_countries, textvariable=topo_num_bs, width=10)),
        ("cell_radius [m]", ttk.Entry(self.frm_t_countries, textvariable=topo_cell_radius, width=10)),
        ("rng_seed", ttk.Entry(self.frm_t_countries, textvariable=topo_rng, width=10)),
    ])

    # ---- Shapefile (row spanning 3 columns, with "..." button) ----
    row_shp = ttk.Frame(self.frm_t_countries)
    row_shp.grid(row=3, column=0, columnspan=6, sticky="we", pady=(2, 2))
    ttk.Label(row_shp, text="countries_shapefile").pack(side="left")
    self.ent_shp = ttk.Entry(row_shp, textvariable=path_shp, width=64)
    self.ent_shp.pack(side="left", fill="x", expand=True, padx=(6, 6))
    self.btn_shp = ttk.Button(row_shp, text="…", width=3, command=_browse_shapefile)
    self.btn_shp.pack(side="left")
    
    # ---- Population raster (row spanning 3 columns, with "..." button) ----
    row_ras = ttk.Frame(self.frm_t_countries)
    row_ras.grid(row=4, column=0, columnspan=6, sticky="we", pady=(2, 2))
    ttk.Label(row_ras, text="population_raster").pack(side="left")
    self.ent_raster = ttk.Entry(row_ras, textvariable=path_raster, width=64)
    self.ent_raster.pack(side="left", fill="x", expand=True, padx=(6, 6))
    self.btn_raster = ttk.Button(row_ras, text="…", width=3, command=_browse_raster)
    self.btn_raster.pack(side="left")
    #cb_renc.bind("<<ComboboxSelected>>", _toggle_raster_by_encoding(root))
    #_toggle_raster_by_encoding(root)

    # ---- Subframe: MACROCELL ----
    self.frm_t_macro = ttk.LabelFrame(frm_t, text="Topology – MACROCELL")
    self.frm_t_macro.grid(row=3, column=0, columnspan=6, sticky="we", pady=(4, 8))
    add_row_three(self.frm_t_macro, 0, [
        ("intersite_distance [m]", ttk.Entry(self.frm_t_macro, textvariable=macro_intersite, width=10)),
        ("wrap_around", ttk.Combobox(self.frm_t_macro, textvariable=macro_wrap, values=[False, True], state="readonly", width=8)),
        ("num_clusters", ttk.Entry(self.frm_t_macro, textvariable=macro_clusters, width=8)),
    ])

    # ---- Subframe: HOTSPOT ----
    self.frm_t_hotspot = ttk.LabelFrame(frm_t, text="Topology – HOTSPOT")
    self.frm_t_hotspot.grid(row=4, column=0, columnspan=6, sticky="we", pady=(4, 8))
    add_row_three(self.frm_t_hotspot, 0, [
        ("intersite_distance [m]", ttk.Entry(self.frm_t_hotspot, textvariable=hotspot_intersite, width=10)),
        ("wrap_around", ttk.Combobox(self.frm_t_hotspot, textvariable=hotspot_wrap, values=[False, True], state="readonly", width=8)),
        ("num_clusters", ttk.Entry(self.frm_t_hotspot, textvariable=hotspot_clusters, width=8)),
    ])
    add_row_three(self.frm_t_hotspot, 1, [
        ("num_hotspots_per_cell", ttk.Entry(self.frm_t_hotspot, textvariable=hotspot_num_per_cell, width=10)),
        ("max_dist_hotspot_ue [m]", ttk.Entry(self.frm_t_hotspot, textvariable=hotspot_max_dist_ue, width=12)),
        ("min_dist_bs_hotspot [m]", ttk.Entry(self.frm_t_hotspot, textvariable=hotspot_min_dist_bs, width=12)),
    ])

    # ---- Subframe: SINGLE_BS ----
    self.frm_t_sbs = ttk.LabelFrame(frm_t, text="Topology – SINGLE_BS")
    self.frm_t_sbs.grid(row=5, column=0, columnspan=6, sticky="we", pady=(4, 8))
    add_row_three(self.frm_t_sbs, 0, [
        ("intersite_distance [m]", ttk.Entry(self.frm_t_sbs, textvariable=sbs_intersite, width=10)),
        ("cell_radius [m]", ttk.Entry(self.frm_t_sbs, textvariable=sbs_cell_radius, width=10)),
        ("num_clusters", ttk.Entry(self.frm_t_sbs, textvariable=sbs_clusters, width=8)),
    ])
    add_row_three(self.frm_t_sbs, 1, [
        ("azimuth (list or str)", ttk.Entry(self.frm_t_sbs, textvariable=sbs_azimuth, width=28)),
        ("", ttk.Label(self.frm_t_sbs, text="")),
        ("", ttk.Label(self.frm_t_sbs, text="")),
    ])

    def _toggle_topology_frames(*_):
        t = topo_type.get()
        # hide all
        for f in (self.frm_t_countries, self.frm_t_macro, self.frm_t_hotspot, self.frm_t_sbs):
            f.grid_remove()
        # show the corresponding one
        if t == "Macro_countries":
            self.frm_t_countries.grid()
        elif t == "MACROCELL":
            self.frm_t_macro.grid()
        elif t == "HOTSPOT":
            self.frm_t_hotspot.grid()
        elif t == "SINGLE_BS":
            self.frm_t_sbs.grid()

    cb_topo_type.bind("<<ComboboxSelected>>", _toggle_topology_frames)
    _toggle_topology_frames()

    # ======= BS Section (3 columns) =======
    # Note: This frame seems to be defined twice in your original code.
    # I am keeping the second definition as it includes column configurations.
    frm_bs = ttk.LabelFrame(root, text="BS – Parameters")
    frm_bs.pack(fill="x", padx=6, pady=8)

    # 3 fluid columns
    for c in range(3):
        frm_bs.columnconfigure(c, weight=1, uniform="bscols")

    # ----- Column 1: BS – Basic -----
    col_basic = ttk.LabelFrame(frm_bs, text="BS – Basic")
    col_basic.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
    # two internal columns
    col_basic.columnconfigure(0, weight=0)
    col_basic.columnconfigure(1, weight=1)

    _add_field(col_basic, 0, "load_probability",
                    ttk.Entry(col_basic, textvariable=bs_load_prob, width=10))
    _add_field(col_basic, 1, "conducted_power [dBm]",
                    ttk.Entry(col_basic, textvariable=bs_power, width=10))
    _add_field(col_basic, 2, "height [m]",
                    ttk.Entry(col_basic, textvariable=bs_height, width=10))
    _add_field(col_basic, 3, "noise_figure [dB]",
                    ttk.Entry(col_basic, textvariable=bs_nf, width=10))
    _add_field(col_basic, 4, "ohmic_loss [dB]",
                    ttk.Entry(col_basic, textvariable=bs_ohmic, width=10))

    # ----- Column 2: BS – Antenna Array -----
    col_array = ttk.LabelFrame(frm_bs, text="BS – Antenna Array")
    col_array.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
    # four internal columns (to make ranges look good)
    for c in range(4):
        col_array.columnconfigure(c, weight=(1 if c in (1, 3) else 0))

    # normalization (use Checkbutton to avoid "0/1" in UI)
    norm_chk = ttk.Checkbutton(col_array, variable=bs_norm, text="")
    _add_field(col_array, 0, "normalization", norm_chk)

    # element_pattern
    cb_pat = ttk.Combobox(col_array, textvariable=bs_elem_pat,
                          values=["M2101", "ITU-R S.672", "Custom"], state="readonly", width=14)
    _add_field(col_array, 1, "element_pattern", cb_pat)

    # minimum_array_gain
    _add_field(col_array, 2, "minimum_array_gain [dB]",
                    ttk.Entry(col_array, textvariable=bs_min_arr_gain, width=10))

    # horizontal_beamsteering_range
    w_hmin = ttk.Entry(col_array, textvariable=bs_h_steer[0], width=7)
    w_hmax = ttk.Entry(col_array, textvariable=bs_h_steer[1], width=7)
    _add_range(col_array, 3, "h_beamsteer [deg]", w_hmin=0, w_hmax=0)

    # vertical_beamsteering_range
    w_vmin = ttk.Entry(col_array, textvariable=bs_v_steer[0], width=7)
    w_vmax = ttk.Entry(col_array, textvariable=bs_v_steer[1], width=7)
    _add_range(col_array, 4, "v_beamsteer [deg]", w_vmin=0, w_vmax=0)

    # other fields (single line)
    _add_field(col_array, 5, "downtilt [deg]",
                    ttk.Entry(col_array, textvariable=bs_downtilt, width=10))
    _add_field(col_array, 6, "element_max_g [dBi]",
                    ttk.Entry(col_array, textvariable=bs_elem_max_g, width=10))
    _add_field(col_array, 7, "element_phi_3db [deg]",
                    ttk.Entry(col_array, textvariable=bs_phi3, width=10))
    _add_field(col_array, 8, "element_theta_3db [deg]",
                    ttk.Entry(col_array, textvariable=bs_theta3, width=10))
    _add_field(col_array, 9, "n_rows",
                    ttk.Entry(col_array, textvariable=bs_rows, width=10))
    _add_field(col_array, 10, "n_columns",
                    ttk.Entry(col_array, textvariable=bs_cols, width=10))
    _add_field(col_array, 11, "element_horiz_spacing [λ]",
                    ttk.Entry(col_array, textvariable=bs_elem_hs, width=10))
    _add_field(col_array, 12, "element_vert_spacing [λ]",
                    ttk.Entry(col_array, textvariable=bs_elem_vs, width=10))
    _add_field(col_array, 13, "element_am [dB]",
                    ttk.Entry(col_array, textvariable=bs_elem_am, width=10))
    _add_field(col_array, 14, "element_sla_v [dB]",
                    ttk.Entry(col_array, textvariable=bs_elem_sla_v, width=10))
    _add_field(col_array, 15, "multiplication_factor",
                    ttk.Entry(col_array, textvariable=bs_mult, width=10))

    # ----- Column 3: BS – Sub-array -----
    col_sub = ttk.LabelFrame(frm_bs, text="BS – Sub-array")
    col_sub.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=6)
    col_sub.columnconfigure(0, weight=0)
    col_sub.columnconfigure(1, weight=1)

    # is_enabled
    sub_en_chk = ttk.Checkbutton(col_sub, variable=bs_sub_enabled, text="")
    _add_field(col_sub, 0, "is_enabled", sub_en_chk)

    _add_field(col_sub, 1, "n_rows",
                    ttk.Entry(col_sub, textvariable=bs_sub_rows, width=10))
    _add_field(col_sub, 2, "element_vert_spacing [λ]",
                    ttk.Entry(col_sub, textvariable=bs_sub_evspace, width=10))
    _add_field(col_sub, 3, "eletrical_downtilt [deg]",
                    ttk.Entry(col_sub, textvariable=bs_sub_e_downtilt, width=10))

    # ======= UE Section (3 columns, grid only) =======
    frm_ue = ttk.LabelFrame(root, text="UE – Parameters")
    frm_ue.pack(fill="x", padx=6, pady=8)

    # 3 fluid columns
    for c in range(3):
        frm_ue.columnconfigure(c, weight=1, uniform="uecols")

    # ----- Column 1: UE – Basic -----
    col_basic_ue = ttk.LabelFrame(frm_ue, text="UE – Basic")
    col_basic_ue.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
    col_basic_ue.columnconfigure(0, weight=0)
    col_basic_ue.columnconfigure(1, weight=1)

    _add_field(col_basic_ue, 0, "k", ttk.Entry(col_basic_ue, textvariable=ue_k, width=8))
    _add_field(col_basic_ue, 1, "k_m", ttk.Entry(col_basic_ue, textvariable=ue_km, width=8))
    _add_field(col_basic_ue, 2, "indoor_percent [%]", ttk.Entry(col_basic_ue, textvariable=ue_indoor, width=8))

    # distribution_type (Combobox)
    cb_ue_dist = ttk.Combobox(col_basic_ue, textvariable=self.ue_dist_type,
                              values=["Macro_countries", "UNIFORM", "CELL", "UNIFORM_IN_CELL", "ANGLE_AND_DISTANCE"],
                              state="readonly", width=18)
    self._add_field(col_basic_ue, 3, "distribution_type", cb_ue_dist)
    cb_ue_dist.bind("<<ComboboxSelected>>", lambda e: self._toggle_ue_distribution())
    self._add_field(col_basic_ue, 3, "distribution_type", cb_ue_dist)

    # tx_power_control (Checkbutton)
    chk_tx = ttk.Checkbutton(col_basic_ue, variable=self.ue_tx_power_ctrl, text="")
    self._add_field(col_basic_ue, 4, "tx_power_control", chk_tx)

    self._add_field(col_basic_ue, 5, "p_o_pusch [dBm]", ttk.Entry(col_basic_ue, textvariable=self.ue_p_o_pusch, width=10))
    self._add_field(col_basic_ue, 6, "alpha", ttk.Entry(col_basic_ue, textvariable=self.ue_alpha, width=10))
    self._add_field(col_basic_ue, 7, "p_cmax [dBm]", ttk.Entry(col_basic_ue, textvariable=self.ue_p_cmax, width=10))
    self._add_field(col_basic_ue, 8, "power_dynamic_range [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_p_dyn, width=10))
    self._add_field(col_basic_ue, 9, "height [m]", ttk.Entry(col_basic_ue, textvariable=self.ue_height, width=10))
    self._add_field(col_basic_ue, 10, "noise_figure [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_nf, width=10))
    self._add_field(col_basic_ue, 11, "ohmic_loss [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_ohmic, width=10))
    self._add_field(col_basic_ue, 12, "body_loss [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_body_loss, width=10))

    # ----- Column 2: UE – Antenna Array -----
    col_array_ue = ttk.LabelFrame(frm_ue, text="UE – Antenna Array")
    col_array_ue.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
    for c in range(4):
        col_array_ue.columnconfigure(c, weight=(1 if c in (1, 3) else 0))

    chk_norm_ue = ttk.Checkbutton(col_array_ue, variable=self.ue_norm, text="")
    self._add_field(col_array_ue, 0, "normalization", chk_norm_ue)

    cb_pat_ue = ttk.Combobox(col_array_ue, textvariable=self.ue_elem_pat,
                             values=["FIXED", "M2101", "Custom"], state="readonly", width=14)
    self._add_field(col_array_ue, 1, "element_pattern", cb_pat_ue)

    self._add_field(col_array_ue, 2, "minimum_array_gain [dB]", ttk.Entry(col_array_ue, textvariable=self.ue_min_arr_gain, width=10))
    self._add_field(col_array_ue, 3, "element_max_g [dBi]", ttk.Entry(col_array_ue, textvariable=self.ue_elem_max_g, width=10))
    self._add_field(col_array_ue, 4, "element_phi_3db [deg]", ttk.Entry(col_array_ue, textvariable=self.ue_phi3, width=10))
    self._add_field(col_array_ue, 5, "element_theta_3db [deg]", ttk.Entry(col_array_ue, textvariable=self.ue_theta3, width=10))
    self._add_field(col_array_ue, 6, "n_rows", ttk.Entry(col_array_ue, textvariable=self.ue_rows, width=10))
    self._add_field(col_array_ue, 7, "n_columns", ttk.Entry(col_array_ue, textvariable=self.ue_cols, width=10))
    self._add_field(col_array_ue, 8, "element_am [dB]", ttk.Entry(col_array_ue, textvariable=self.ue_elem_am, width=10))
    self._add_field(col_array_ue, 9, "element_sla_v [dB]", ttk.Entry(col_array_ue, textvariable=self.ue_elem_sla_v, width=10))
    self._add_field(col_array_ue, 10, "multiplication_factor", ttk.Entry(col_array_ue, textvariable=self.ue_mult, width=10))

    # ----- Column 3: UE – Sub-array -----
    col_sub_ue = ttk.LabelFrame(frm_ue, text="UE – Sub-array")
    col_sub_ue.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=6)
    col_sub_ue.columnconfigure(0, weight=0)
    col_sub_ue.columnconfigure(1, weight=1)

    chk_sub_en_ue = ttk.Checkbutton(col_sub_ue, variable=self.ue_sub_enabled, text="")
    self._add_field(col_sub_ue, 0, "is_enabled", chk_sub_en_ue)
    self._add_field(col_sub_ue, 1, "n_rows", ttk.Entry(col_sub_ue, textvariable=self.ue_sub_rows, width=10))
    self._add_field(col_sub_ue, 2, "element_vert_spacing [λ]", ttk.Entry(col_sub_ue, textvariable=self.ue_sub_evspace, width=10))
    self._add_field(col_sub_ue, 3, "eletrical_downtilt [deg]", ttk.Entry(col_sub_ue, textvariable=self.ue_sub_e_downtilt, width=10))

    col_dist_ue = ttk.LabelFrame(frm_ue, text="UE – Distribution (Angle&Distance)")
    col_dist_ue.grid(row=1, column=0, sticky="nsew", padx=(3, 6), pady=(0, 6))  # same column, row below
    for c in range(4):
        col_dist_ue.columnconfigure(c, weight=(1 if c in (1, 3) else 0))

    # distribution_distance
    cb_dist_d = ttk.Combobox(col_dist_ue, textvariable=self.ue_dist_distance,
                             values=["RAYLEIGH", "UNIFORM", "SQRT(UNIFORM)"],
                             state="readonly", width=16)
    self._add_field(col_dist_ue, 0, "distribution_distance", cb_dist_d)

    # distribution_azimuth
    cb_dist_a = ttk.Combobox(col_dist_ue, textvariable=self.ue_dist_azimuth,
                             values=["NORMAL", "UNIFORM"], state="readonly", width=16)
    self._add_field(col_dist_ue, 1, "distribution_azimuth", cb_dist_a)

    # azimuth_range (min to max)
    w_azmin = ttk.Entry(col_dist_ue, textvariable=self.ue_az_min, width=8)
    w_azmax = ttk.Entry(col_dist_ue, textvariable=self.ue_az_max, width=8)
    _add_range(col_dist_ue, 2, "azimuth_range [deg]", w_azmin=0, w_azmax=0)

    # save the reference for the toggle
    self._ue_col_dist_frame = col_dist_ue

    frm_l = ttk.LabelFrame(root, text="UL / DL / Channel / Shadowing")
    frm_l.pack(fill="x", pady=(2, 8))
    add_row_three(frm_l, 0, [
        ("uplink.attenuation_factor", ttk.Entry(frm_l, textvariable=self.ul_att, width=8)),
        ("uplink.sinr_min / sinr_max [dB]", self._pair_entries(frm_l, self.ul_sinr_min, self.ul_sinr_max, w=8)),
        ("downlink.attenuation_factor", ttk.Entry(frm_l, textvariable=self.dl_att, width=8)),
    ])
    add_row_three(frm_l, 1, [
        ("downlink.sinr_min / sinr_max [dB]", self._pair_entries(frm_l, self.dl_sinr_min, self.dl_sinr_max, w=8)),
        ("channel_model", ttk.Entry(frm_l, textvariable=self.ch_model, width=12)),
        ("shadowing", ttk.Combobox(frm_l, textvariable=self.shadowing, values=[True, False], state="readonly", width=8)),
    ])
    
    # Initialize the UI state
    self._toggle_ue_distribution()