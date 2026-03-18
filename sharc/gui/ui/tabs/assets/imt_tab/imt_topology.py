import tkinter as tk
from tkinter import ttk, filedialog
from utils import add_row_three  # Assuming this exists in your project
from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper


class IMTTopologySection:
    """
    Manages the Topology section of the IMT Tab, including 
    sub-frame toggling (Macro/Hotspot/etc.) and file pickers.
    """

    def __init__(self, parent, state_manager):
        self.parent = parent
        self.state = state_manager

        # Frame References
        self.frames = {}
        self.ent_raster = None
        self.btn_raster = None
        self.txt_countries = None

        self._build_ui()

    def _build_ui(self):
        frm_t = ttk.LabelFrame(self.parent, text="Topology – IMT")
        frm_t.pack(fill="x", pady=(2, 8))

        # --- Type Selection ---
        row_type = ttk.Frame(frm_t)
        row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 4))

        ttk.Label(row_type, text="type").pack(side="left")
        cb_topo_type = ttk.Combobox(
            row_type, textvariable=self.state.get("topo_type"),
            values=["MACROCELL", "HOTSPOT", "SINGLE_BS", "Macro_countries", "INDOOR", "NTN"],
            state="readonly", width=18
        )
        cb_topo_type.pack(side="left", padx=(6, 0))
        cb_topo_type.bind("<<ComboboxSelected>>", self.toggle_visibility)

        # --- Common Params ---
        add_row_three(frm_t, 1, [
            ("central_latitude", ttk.Entry(
                frm_t, textvariable=self.state.get("topo_c_lat"), width=12)),
            ("central_longitude", ttk.Entry(
                frm_t, textvariable=self.state.get("topo_c_lon"), width=12)),
            ("central_altitude [m]", ttk.Entry(
                frm_t, textvariable=self.state.get("topo_c_alt"), width=12)),
        ])

        # --- Sub-Sections ---
        self.frames["Macro_countries"] = self._build_countries(frm_t)
        self.frames["MACROCELL"] = self._build_macro(frm_t)
        self.frames["HOTSPOT"] = self._build_hotspot(frm_t)
        self.frames["SINGLE_BS"] = self._build_sbs(frm_t)
        self.frames["INDOOR"] = self._build_indoor(frm_t)
        self.frames["NTN"] = self._build_ntn(frm_t)

        self.toggle_visibility()

    def _build_countries(self, parent):
        frm = ttk.LabelFrame(
            parent, text="Topology – COUNTRIES (Macro_countries)")
        frm.grid(row=2, column=0, columnspan=6, sticky="we", pady=(4, 8))

        # Options Row
        row_opts = ttk.Frame(frm)
        row_opts.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2, 4))

        # Raster Encoding
        ttk.Label(row_opts, text="raster_encoding").pack(side="left")
        cb_enc = ttk.Combobox(
            row_opts, textvariable=self.state.get("topo_raster_enc"),
            values=["Uniforme", "Denspop"], state="readonly", width=12
        )
        cb_enc.pack(side="left")
        cb_enc.bind("<<ComboboxSelected>>", self._toggle_raster_state)

        # Dist Type
        ttk.Label(row_opts, text="dist_type").pack(side="left", padx=(10, 0))
        ttk.Combobox(
            row_opts, textvariable=self.state.get("topo_dist_type"),
            values=["Urban", "Suburban", "Rural"], state="readonly", width=12
        ).pack(side="left")

        # Text Area
        row_c = ttk.Frame(frm)
        row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row_c, text="country_names (1/line)").pack(side="left")
        self.txt_countries = tk.Text(row_c, width=48, height=7)
        self.txt_countries.insert("1.0", self.state.get("countries").get())
        self.txt_countries.pack(side="left", fill="x",
                                expand=True, padx=(6, 6))

        # Numeric Params
        add_row_three(frm, 2, [
            ("num_bs_total", ttk.Entry(
                frm, textvariable=self.state.get("topo_num_bs"), width=10)),
            ("cell_radius [m]", ttk.Entry(
                frm, textvariable=self.state.get("topo_cell_radius"), width=10)),
            ("rng_seed", ttk.Entry(frm, textvariable=self.state.get("topo_rng"), width=10)),
        ])

        # File Pickers
        self._add_file_row(frm, 3, "countries_shapefile",
                           self.state.get("path_shp"), "Shapefile", "*.shp")
        self.ent_raster, self.btn_raster = self._add_file_row(
            frm, 4, "population_raster", self.state.get("path_raster"), "GeoTIFF", "*.tif;*.tiff", return_widgets=True
        )

        # Init toggle state
        self._toggle_raster_state()
        return frm

    def _build_macro(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – MACROCELL")
        frm.grid(row=3, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(
                frm, textvariable=self.state.get("macro_intersite"), width=10)),
            ("wrap_around", ttk.Combobox(frm, textvariable=self.state.get(
                "macro_wrap"), values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(
                frm, textvariable=self.state.get("macro_clusters"), width=8)),
        ])
        return frm

    def _build_hotspot(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – HOTSPOT")
        frm.grid(row=4, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(
                frm, textvariable=self.state.get("hotspot_intersite"), width=10)),
            ("wrap_around", ttk.Combobox(frm, textvariable=self.state.get(
                "hotspot_wrap"), values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(
                frm, textvariable=self.state.get("hotspot_clusters"), width=8)),
        ])
        add_row_three(frm, 1, [
            ("num_hotspots_per_cell", ttk.Entry(
                frm, textvariable=self.state.get("hotspot_num_per_cell"), width=10)),
            ("max_dist_hotspot_ue [m]", ttk.Entry(
                frm, textvariable=self.state.get("hotspot_max_dist_ue"), width=12)),
            ("min_dist_bs_hotspot [m]", ttk.Entry(
                frm, textvariable=self.state.get("hotspot_min_dist_bs"), width=12)),
        ])
        return frm

    def _build_sbs(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – SINGLE_BS")
        frm.grid(row=5, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(
                frm, textvariable=self.state.get("sbs_intersite"), width=10)),
            ("cell_radius [m]", ttk.Entry(
                frm, textvariable=self.state.get("sbs_cell_radius"), width=10)),
            ("num_clusters", ttk.Entry(
                frm, textvariable=self.state.get("sbs_clusters"), width=8)),
        ])
        add_row_three(frm, 1, [
            ("azimuth (list or str)", ttk.Entry(
                frm, textvariable=self.state.get("sbs_azimuth"), width=28)),
            ("", ttk.Label(frm, text="")), ("", ttk.Label(frm, text="")),
        ])
        return frm

    def _build_indoor(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology \u2013 INDOOR")
        frm.grid(row=6, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(
                frm, textvariable=self.state.get("indoor_intersite"), width=10)),
            ("n_rows", ttk.Entry(
                frm, textvariable=self.state.get("indoor_n_rows"), width=8)),
            ("n_columns", ttk.Entry(
                frm, textvariable=self.state.get("indoor_n_cols"), width=8)),
        ])
        add_row_three(frm, 1, [
            ("street_width [m]", ttk.Entry(
                frm, textvariable=self.state.get("indoor_street_width"), width=10)),
            ("num_cells", ttk.Entry(
                frm, textvariable=self.state.get("indoor_num_cells"), width=8)),
            ("num_floors", ttk.Entry(
                frm, textvariable=self.state.get("indoor_num_floors"), width=8)),
        ])
        add_row_three(frm, 2, [
            ("num_imt_buildings", ttk.Entry(
                frm, textvariable=self.state.get("indoor_num_buildings"), width=10)),
            ("building_class", ttk.Combobox(frm, textvariable=self.state.get(
                "indoor_building_class"), values=["TRADITIONAL", "THERMALLY_EFFICIENT"], state="readonly", width=20)),
            ("ue_indoor_percent", ttk.Entry(
                frm, textvariable=self.state.get("indoor_ue_indoor_percent"), width=8)),
        ])
        return frm

    def _build_ntn(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology \u2013 NTN")
        frm.grid(row=7, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(
                frm, textvariable=self.state.get("ntn_intersite"), width=12)),
            ("cell_radius [m]", ttk.Entry(
                frm, textvariable=self.state.get("ntn_cell_radius"), width=12)),
            ("bs_height [m]", ttk.Entry(
                frm, textvariable=self.state.get("ntn_bs_height"), width=12)),
        ])
        add_row_three(frm, 1, [
            ("bs_azimuth [deg]", ttk.Entry(
                frm, textvariable=self.state.get("ntn_bs_azimuth"), width=10)),
            ("bs_elevation [deg]", ttk.Entry(
                frm, textvariable=self.state.get("ntn_bs_elevation"), width=10)),
            ("num_sectors", ttk.Combobox(frm, textvariable=self.state.get(
                "ntn_num_sectors"), values=["1", "7", "19"], state="readonly", width=8)),
        ])
        return frm

    # --- Logic ---

    def toggle_visibility(self, *args):
        for f in self.frames.values():
            f.grid_remove()

        current = self.state.get("topo_type").get()
        if current in self.frames:
            self.frames[current].grid()

    def _toggle_raster_state(self, *args):
        if not self.ent_raster:
            return
        enc = (self.state.get("topo_raster_enc").get() or "").strip()
        state = "disabled" if enc == "Uniforme" else "normal"
        if enc == "Uniforme":
            self.state.get("path_raster").set("")
        self.ent_raster.configure(state=state)
        self.btn_raster.configure(state=state)

    def _add_file_row(self, parent, row, label, var, type_name, ext, return_widgets=False):
        f = ttk.Frame(parent)
        f.grid(row=row, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(f, text=label).pack(side="left")
        e = ttk.Entry(f, textvariable=var, width=64)
        e.pack(side="left", fill="x", expand=True, padx=6)

        def pick():
            fn = filedialog.askopenfilename(title=f"Choose {type_name}", filetypes=[
                                            (type_name, ext), ("All", "*.*")])
            if fn:
                var.set(fn)

        b = ttk.Button(f, text="…", width=3, command=pick)
        b.pack(side="left")
        if return_widgets:
            return e, b
        return None

    def get_countries_text(self):
        if self.txt_countries:
            return self.txt_countries.get("1.0", "end").strip()
        return ""

    def set_countries_text(self, text):
        if self.txt_countries:
            self.txt_countries.delete("1.0", "end")
            self.txt_countries.insert("1.0", text)
