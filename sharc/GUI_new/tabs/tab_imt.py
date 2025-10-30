from tkinter import ttk, filedialog
from utils.ui_helpers import add_row_three
import tkinter as tk

def build_tab_imt(root, S):
    # ----- IMT gerais -----
    frm_g = ttk.LabelFrame(root, text="IMT – Parâmetros gerais")
    frm_g.pack(fill="x", pady=(2,8))

    add_row_three(frm_g, 0, [
        ("minimum_separation_distance_bs_ue [m]", ttk.Entry(frm_g, textvariable=S.imt_min_sep, width=10)),
        ("interfered_with", ttk.Combobox(frm_g, textvariable=S.imt_interfered, values=[False, True], state="readonly", width=8)),
        ("frequency [MHz]", ttk.Entry(frm_g, textvariable=S.imt_freq, width=12)),
    ])
    add_row_three(frm_g, 1, [
        ("bandwidth [MHz]", ttk.Entry(frm_g, textvariable=S.imt_bw, width=10)),
        ("rb_bandwidth [MHz]", ttk.Entry(frm_g, textvariable=S.imt_rb_bw, width=10)),
        ("spectral_mask", ttk.Combobox(frm_g, textvariable=S.imt_spec_mask, values=["IMT-2020","3GPP"], state="readonly", width=12)),
    ])
    add_row_three(frm_g, 2, [
        ("spurious_emissions [dBc]", ttk.Entry(frm_g, textvariable=S.imt_spurious, width=10)),
        ("adjacent_antenna_model", ttk.Entry(frm_g, textvariable=S.imt_adj_ant_model, width=16)),
        ("guard_band_ratio", ttk.Entry(frm_g, textvariable=S.imt_guard_ratio, width=10)),
    ])

    # ----- Topologia COUNTRIES -----
    frm_t = ttk.LabelFrame(root, text="Topologia – COUNTRIES (Macro_countries)")
    frm_t.pack(fill="x", pady=(2,8))

    add_row_three(frm_t, 0, [
        ("central_latitude", ttk.Entry(frm_t, textvariable=S.topo_c_lat, width=12)),
        ("central_longitude", ttk.Entry(frm_t, textvariable=S.topo_c_lon, width=12)),
        ("central_altitude [m]", ttk.Entry(frm_t, textvariable=S.topo_c_alt, width=12)),
    ])

    row_c = ttk.Frame(frm_t); row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row_c, text="country_names (1/linha)").pack(side="left")
    S.txt_countries_widget = tk.Text(row_c, width=48, height=7)
    S.txt_countries_widget.insert("1.0", S.topo_countries_text_default)
    S.txt_countries_widget.pack(side="left", fill="x", expand=True, padx=(6,6))

    add_row_three(frm_t, 2, [
        ("num_bs_total", ttk.Entry(frm_t, textvariable=S.topo_num_bs, width=10)),
        ("cell_radius [m]", ttk.Entry(frm_t, textvariable=S.topo_cell_radius, width=10)),
        ("rng_seed", ttk.Entry(frm_t, textvariable=S.topo_rng, width=10)),
    ])

    add_row_three(frm_t, 3, [
        ('dist_type', ttk.Combobox(frm_t, textvariable=S.topo_dist_type, values=["Urban","Suburban","Rural"], state="readonly", width=12)),
        ("type", ttk.Entry(frm_t, textvariable=S.topo_type, width=18)),
        ("", ttk.Label(frm_t, text="")),
    ])

    # optional shapefile/raster for preview
    row_paths = ttk.Frame(frm_t); row_paths.grid(row=4, column=0, columnspan=6, sticky="we", pady=(6,0))
    ttk.Label(row_paths, text="shapefile (preview)").grid(row=0, column=0, sticky="e")
    e_shp = ttk.Entry(row_paths, textvariable=S.path_shp, width=54); e_shp.grid(row=0, column=1, sticky="we", padx=(6,6))
    ttk.Button(row_paths, text="...", command=lambda: _pick_file(S.path_shp)).grid(row=0, column=2, sticky="w", padx=(0,8))

    ttk.Label(row_paths, text="raster (preview)").grid(row=1, column=0, sticky="e")
    e_ras = ttk.Entry(row_paths, textvariable=S.path_raster, width=54); e_ras.grid(row=1, column=1, sticky="we", padx=(6,6))
    ttk.Button(row_paths, text="...", command=lambda: _pick_file(S.path_raster)).grid(row=1, column=2, sticky="w")
    row_paths.grid_columnconfigure(1, weight=1)

def _pick_file(tk_strvar):
    path = filedialog.askopenfilename(title="Selecionar arquivo", filetypes=[("Todos", "*.*")])
    if path:
        tk_strvar.set(path)
