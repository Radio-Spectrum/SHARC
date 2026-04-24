import copy
import tkinter as tk
from tkinter import filedialog, ttk

import yaml

from utils import add_row_three
from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper


DEFAULT_MSS_DC_DATA = {
    "name": "SystemA",
    "num_beams": 19,
    "beam_radius": 36516.0,
    "sat_is_active_if": {
        "conditions": [
            "LAT_LONG_INSIDE_COUNTRY",
            "MINIMUM_ELEVATION_FROM_ES",
        ],
        "minimum_elevation_from_es": 5.0,
        "lat_long_inside_country": {
            "country_names": ["Brazil"],
            "margin_from_border": 0.0,
        },
    },
    "beam_positioning": {
        "type": "SERVICE_GRID",
        "angle_from_subsatellite_theta": {
            "type": "FIXED",
            "fixed": 0.0,
            "distribution": {"min": 0.0, "max": 10.0},
        },
        "angle_from_subsatellite_phi": {
            "type": "FIXED",
            "fixed": 0.0,
            "distribution": {"min": -180.0, "max": 180.0},
        },
        "distance_from_subsatellite": {
            "type": "FIXED",
            "fixed": 0.0,
            "distribution": {"min": 0.0, "max": 100000.0},
        },
        "service_grid": {
            "country_names": ["Brazil"],
            "transform_grid_randomly": True,
            "grid_margin_from_border": 0.0,
            "eligible_sats_margin_from_border": 0.0,
            "enable_fixed_lat_lons_for_grid": False,
            "fixed_lats": [0.0],
            "fixed_lons": [0.0],
            "grid_exclusion_zone": {
                "type": None,
                "circle": {
                    "center_lat": 0.0,
                    "center_lon": 0.0,
                    "radius_km": 10.0,
                },
            },
        },
    },
    "orbits": [
        {
            "n_planes": 28,
            "inclination_deg": 53.0,
            "perigee_alt_km": 525.0,
            "apogee_alt_km": 525.0,
            "sats_per_plane": 120,
            "long_asc_deg": 0.0,
            "phasing_deg": 1.5,
            "initial_mean_anomaly": 0.0,
        }
    ],
}


def _num_or_str(value):
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value

    text = str(value).strip()
    if not text:
        return None

    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False

    if "." not in text and "e" not in low:
        try:
            return int(text)
        except Exception:
            pass

    try:
        return float(text)
    except Exception:
        return text


def _deep_merge(base_dict, new_dict):
    for key, value in new_dict.items():
        if isinstance(value, dict) and isinstance(base_dict.get(key), dict):
            _deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


def _yaml_dump_text(data):
    return yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).strip()


def _parse_yaml_dict(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return {}
    try:
        data = yaml.safe_load(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_yaml_list(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return []
    try:
        data = yaml.safe_load(text)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _parse_line_list(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return []

    try:
        data = yaml.safe_load(text)
    except Exception:
        data = None

    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]

    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_scalar_list(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return []

    try:
        data = yaml.safe_load(text)
    except Exception:
        data = None

    if isinstance(data, list):
        return [_num_or_str(item) for item in data]

    values = []
    for chunk in text.replace("\n", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            values.append(_num_or_str(chunk))
    return values


class IMTTopologySection:
    """
    Manages the Topology section of the IMT Tab, including
    sub-frame toggling (Macro/Hotspot/etc.) and file pickers.
    """

    def __init__(self, parent, state_manager):
        self.parent = parent
        self.state = state_manager

        self.frames = {}
        self.ent_raster = None
        self.btn_raster = None
        self.txt_countries = None
        self.txt_mss_dc_sat_countries = None
        self.txt_mss_dc_grid_countries = None
        self.txt_mss_dc_orbits = None
        self.raster_widgets = []
        self.indexed_widgets = []

        self._build_ui()

    def _build_ui(self):
        frm_t = ttk.LabelFrame(self.parent, text="Topology – IMT")
        frm_t.pack(fill="x", pady=(2, 8))

        row_type = ttk.Frame(frm_t)
        row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 4))

        ttk.Label(row_type, text="type").pack(side="left")
        cb_topo_type = ttk.Combobox(
            row_type,
            textvariable=self.state.get("topo_type"),
            values=["MACROCELL", "HOTSPOT", "SINGLE_BS", "Macro_countries", "INDOOR", "NTN", "MSS_DC"],
            state="readonly",
            width=18,
        )
        cb_topo_type.pack(side="left", padx=(6, 0))
        cb_topo_type.bind("<<ComboboxSelected>>", self.toggle_visibility)

        add_row_three(frm_t, 1, [
            ("central_latitude", ttk.Entry(frm_t, textvariable=self.state.get("topo_c_lat"), width=12)),
            ("central_longitude", ttk.Entry(frm_t, textvariable=self.state.get("topo_c_lon"), width=12)),
            ("central_altitude [m]", ttk.Entry(frm_t, textvariable=self.state.get("topo_c_alt"), width=12)),
        ])

        self.frames["Macro_countries"] = self._build_countries(frm_t)
        self.frames["MACROCELL"] = self._build_macro(frm_t)
        self.frames["HOTSPOT"] = self._build_hotspot(frm_t)
        self.frames["SINGLE_BS"] = self._build_sbs(frm_t)
        self.frames["INDOOR"] = self._build_indoor(frm_t)
        self.frames["NTN"] = self._build_ntn(frm_t)
        self.frames["MSS_DC"] = self._build_mss_dc(frm_t)

        self.toggle_visibility()

    def _build_countries(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – COUNTRIES (Macro_countries)")
        frm.grid(row=2, column=0, columnspan=6, sticky="we", pady=(4, 8))

        row_opts = ttk.Frame(frm)
        row_opts.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2, 4))

        ttk.Label(row_opts, text="raster_encoding").pack(side="left")
        cb_enc = ttk.Combobox(
            row_opts,
            textvariable=self.state.get("topo_raster_enc"),
            values=["uniform", "density", "indexed"],
            state="readonly",
            width=12,
        )
        cb_enc.pack(side="left")
        cb_enc.bind("<<ComboboxSelected>>", self._toggle_raster_state)

        ttk.Label(row_opts, text="dist_type").pack(side="left", padx=(10, 0))
        ttk.Combobox(
            row_opts,
            textvariable=self.state.get("topo_dist_type"),
            values=["Urban", "Suburban", "Rural"],
            state="readonly",
            width=12,
        ).pack(side="left")

        row_scale = ttk.Frame(frm)
        row_scale.grid(row=1, column=0, columnspan=6, sticky="we", pady=(2, 4))
        for col in range(6):
            row_scale.columnconfigure(col, weight=1 if col in (1, 3, 5) else 0)

        cb_mode = ttk.Combobox(
            row_scale,
            textvariable=self.state.get("topo_sedac_palette_mode"),
            values=["log", "linear"],
            state="readonly",
            width=10,
        )
        ent_sedac_min = ttk.Entry(row_scale, textvariable=self.state.get("topo_sedac_min"), width=10)
        ent_sedac_max = ttk.Entry(row_scale, textvariable=self.state.get("topo_sedac_max"), width=10)
        ent_density_thr = ttk.Entry(row_scale, textvariable=self.state.get("topo_min_density_threshold"), width=10)
        ent_density_exp = ttk.Entry(row_scale, textvariable=self.state.get("topo_density_exponent"), width=10)

        IMTUIHelper.add_field(row_scale, 0, "sedac_palette_mode", cb_mode)
        IMTUIHelper.add_field(row_scale, 0, "sedac_min", ent_sedac_min, col=2)
        IMTUIHelper.add_field(row_scale, 0, "sedac_max", ent_sedac_max, col=4)
        IMTUIHelper.add_field(row_scale, 1, "min_density_threshold", ent_density_thr)
        IMTUIHelper.add_field(row_scale, 1, "density_exponent", ent_density_exp, col=2)
        IMTUIHelper.add_field(row_scale, 1, "", ttk.Label(row_scale, text=""), col=4)

        self.raster_widgets.extend([ent_density_thr, ent_density_exp])
        self.indexed_widgets.extend([cb_mode, ent_sedac_min, ent_sedac_max])

        row_c = ttk.Frame(frm)
        row_c.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row_c, text="country_names (1/line)").pack(side="left")
        self.txt_countries = tk.Text(row_c, width=48, height=7)
        self.txt_countries.insert("1.0", self.state.get("countries").get())
        self.txt_countries.pack(side="left", fill="x", expand=True, padx=(6, 6))

        add_row_three(frm, 3, [
            ("num_bs_total", ttk.Entry(frm, textvariable=self.state.get("topo_num_bs"), width=10)),
            ("cell_radius [m]", ttk.Entry(frm, textvariable=self.state.get("topo_cell_radius"), width=10)),
            ("rng_seed", ttk.Entry(frm, textvariable=self.state.get("topo_rng"), width=10)),
        ])

        self._add_file_row(frm, 4, "countries_shapefile", self.state.get("path_shp"), "Shapefile", "*.shp")
        self.ent_raster, self.btn_raster = self._add_file_row(
            frm,
            5,
            "population_raster",
            self.state.get("path_raster"),
            "GeoTIFF",
            "*.tif;*.tiff",
            return_widgets=True,
        )

        self._toggle_raster_state()
        return frm

    def _build_macro(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – MACROCELL")
        frm.grid(row=3, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(frm, textvariable=self.state.get("macro_intersite"), width=10)),
            ("wrap_around", ttk.Combobox(
                frm,
                textvariable=self.state.get("macro_wrap"),
                values=[False, True],
                state="readonly",
                width=8,
            )),
            ("num_clusters", ttk.Entry(frm, textvariable=self.state.get("macro_clusters"), width=8)),
        ])
        return frm

    def _build_hotspot(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – HOTSPOT")
        frm.grid(row=4, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(frm, textvariable=self.state.get("hotspot_intersite"), width=10)),
            ("wrap_around", ttk.Combobox(
                frm,
                textvariable=self.state.get("hotspot_wrap"),
                values=[False, True],
                state="readonly",
                width=8,
            )),
            ("num_clusters", ttk.Entry(frm, textvariable=self.state.get("hotspot_clusters"), width=8)),
        ])
        add_row_three(frm, 1, [
            ("num_hotspots_per_cell", ttk.Entry(frm, textvariable=self.state.get("hotspot_num_per_cell"), width=10)),
            ("max_dist_hotspot_ue [m]", ttk.Entry(frm, textvariable=self.state.get("hotspot_max_dist_ue"), width=12)),
            ("min_dist_bs_hotspot [m]", ttk.Entry(frm, textvariable=self.state.get("hotspot_min_dist_bs"), width=12)),
        ])
        return frm

    def _build_sbs(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – SINGLE_BS")
        frm.grid(row=5, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("intersite_distance [m]", ttk.Entry(frm, textvariable=self.state.get("sbs_intersite"), width=10)),
            ("cell_radius [m]", ttk.Entry(frm, textvariable=self.state.get("sbs_cell_radius"), width=10)),
            ("num_clusters", ttk.Entry(frm, textvariable=self.state.get("sbs_clusters"), width=8)),
        ])
        add_row_three(frm, 1, [
            ("azimuth (list or str)", ttk.Entry(frm, textvariable=self.state.get("sbs_azimuth"), width=28)),
            ("", ttk.Label(frm, text="")),
            ("", ttk.Label(frm, text="")),
        ])
        return frm

    def _build_indoor(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – INDOOR")
        frm.grid(row=6, column=0, columnspan=6, sticky="we", pady=(4, 8))
        add_row_three(frm, 0, [
            ("basic_path_loss", ttk.Combobox(
                frm,
                textvariable=self.state.get("indoor_basic_path_loss"),
                values=["INH_OFFICE", "FSPL"],
                state="readonly",
                width=14,
            )),
            ("intersite_distance [m]", ttk.Entry(frm, textvariable=self.state.get("indoor_intersite"), width=10)),
            ("street_width [m]", ttk.Entry(frm, textvariable=self.state.get("indoor_street_width"), width=10)),
        ])
        add_row_three(frm, 1, [
            ("n_rows", ttk.Entry(frm, textvariable=self.state.get("indoor_n_rows"), width=8)),
            ("n_columns", ttk.Entry(frm, textvariable=self.state.get("indoor_n_cols"), width=8)),
            ("num_cells", ttk.Entry(frm, textvariable=self.state.get("indoor_num_cells"), width=8)),
        ])
        add_row_three(frm, 2, [
            ("num_floors", ttk.Entry(frm, textvariable=self.state.get("indoor_num_floors"), width=8)),
            ("num_imt_buildings", ttk.Entry(frm, textvariable=self.state.get("indoor_num_buildings"), width=10)),
            ("building_class", ttk.Combobox(
                frm,
                textvariable=self.state.get("indoor_building_class"),
                values=["TRADITIONAL", "THERMALLY_EFFICIENT"],
                state="readonly",
                width=20,
            )),
        ])
        add_row_three(frm, 3, [
            ("ue_indoor_percent [0-1]", ttk.Entry(
                frm,
                textvariable=self.state.get("indoor_ue_indoor_percent"),
                width=8,
            )),
            ("", ttk.Label(frm, text="")),
            ("", ttk.Label(frm, text="")),
        ])
        return frm

    def _build_ntn(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – NTN")
        frm.grid(row=7, column=0, columnspan=6, sticky="we", pady=(4, 8))
        ttk.Label(
            frm,
            text="Preencha apenas um entre cell_radius e intersite_distance.",
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=4, pady=(2, 4))
        add_row_three(frm, 1, [
            ("intersite_distance [m]", ttk.Entry(frm, textvariable=self.state.get("ntn_intersite"), width=12)),
            ("cell_radius [m]", ttk.Entry(frm, textvariable=self.state.get("ntn_cell_radius"), width=12)),
            ("bs_height [m]", ttk.Entry(frm, textvariable=self.state.get("ntn_bs_height"), width=12)),
        ])
        add_row_three(frm, 2, [
            ("bs_azimuth [deg]", ttk.Entry(frm, textvariable=self.state.get("ntn_bs_azimuth"), width=10)),
            ("bs_elevation [deg]", ttk.Entry(frm, textvariable=self.state.get("ntn_bs_elevation"), width=10)),
            ("num_sectors", ttk.Combobox(
                frm,
                textvariable=self.state.get("ntn_num_sectors"),
                values=["1", "7", "19"],
                state="readonly",
                width=8,
            )),
        ])
        add_row_three(frm, 3, [
            ("bs_backoff_power [dB]", ttk.Entry(
                frm,
                textvariable=self.state.get("ntn_bs_backoff_power"),
                width=10,
            )),
            ("bs_n_rows_layer1", ttk.Entry(
                frm,
                textvariable=self.state.get("ntn_bs_n_rows_layer1"),
                width=10,
            )),
            ("bs_n_columns_layer1", ttk.Entry(
                frm,
                textvariable=self.state.get("ntn_bs_n_columns_layer1"),
                width=10,
            )),
        ])
        add_row_three(frm, 4, [
            ("bs_n_rows_layer2", ttk.Entry(
                frm,
                textvariable=self.state.get("ntn_bs_n_rows_layer2"),
                width=10,
            )),
            ("bs_n_columns_layer2", ttk.Entry(
                frm,
                textvariable=self.state.get("ntn_bs_n_columns_layer2"),
                width=10,
            )),
            ("", ttk.Label(frm, text="")),
        ])
        return frm

    def _build_mss_dc(self, parent):
        frm = ttk.LabelFrame(parent, text="Topology – MSS_DC")
        frm.grid(row=8, column=0, columnspan=6, sticky="we", pady=(4, 8))
        frm.grid_columnconfigure(0, weight=1)

        ttk.Label(
            frm,
            text="Configure os parâmetros do bloco imt.topology.mss_dc abaixo. O campo de órbitas aceita YAML.",
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(2, 4))

        add_row_three(frm, 1, [
            ("name", ttk.Entry(frm, textvariable=self.state.get("mss_dc_name"), width=18)),
            ("num_beams", ttk.Combobox(
                frm,
                textvariable=self.state.get("mss_dc_num_beams"),
                values=["1", "7", "19"],
                state="readonly",
                width=8,
            )),
            ("beam_radius [m]", ttk.Entry(frm, textvariable=self.state.get("mss_dc_beam_radius"), width=12)),
        ])

        notebook = ttk.Notebook(frm)
        notebook.grid(row=2, column=0, sticky="nsew", padx=4, pady=(4, 4))
        frm.grid_rowconfigure(2, weight=1)

        tab_sat = ttk.Frame(notebook)
        tab_beam = ttk.Frame(notebook)
        tab_orbits = ttk.Frame(notebook)
        notebook.add(tab_sat, text="Sat Selection")
        notebook.add(tab_beam, text="Beam Positioning")
        notebook.add(tab_orbits, text="Orbits")

        self._build_mss_dc_satellite_tab(tab_sat)
        self._build_mss_dc_beam_tab(tab_beam)
        self._build_mss_dc_orbits_tab(tab_orbits)

        initial_text = self.state.get("mss_dc_config").get().strip() or _yaml_dump_text(DEFAULT_MSS_DC_DATA)
        self.set_mss_dc_text(initial_text)
        return frm

    def _build_mss_dc_satellite_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)

        cond_box = ttk.LabelFrame(parent, text="Active Satellite Conditions")
        cond_box.grid(row=0, column=0, sticky="we", padx=4, pady=(4, 6))

        ttk.Checkbutton(
            cond_box,
            text="LAT_LONG_INSIDE_COUNTRY",
            variable=self.state.get("mss_dc_sat_cond_inside_country"),
        ).pack(side="left", padx=(6, 10), pady=4)
        ttk.Checkbutton(
            cond_box,
            text="MINIMUM_ELEVATION_FROM_ES",
            variable=self.state.get("mss_dc_sat_cond_min_elev"),
        ).pack(side="left", padx=(0, 10), pady=4)
        ttk.Checkbutton(
            cond_box,
            text="MAXIMUM_ELEVATION_FROM_ES",
            variable=self.state.get("mss_dc_sat_cond_max_elev"),
        ).pack(side="left", padx=(0, 6), pady=4)

        add_row_three(parent, 1, [
            ("minimum_elevation_from_es [deg]", ttk.Entry(
                parent,
                textvariable=self.state.get("mss_dc_sat_min_elevation_from_es"),
                width=10,
            )),
            ("maximum_elevation_from_es [deg]", ttk.Entry(
                parent,
                textvariable=self.state.get("mss_dc_sat_max_elevation_from_es"),
                width=10,
            )),
            ("margin_from_border [km]", ttk.Entry(
                parent,
                textvariable=self.state.get("mss_dc_sat_margin_from_border"),
                width=10,
            )),
        ])

        self._add_file_row(
            parent,
            2,
            "country_shapes_filename",
            self.state.get("mss_dc_sat_country_shapes_filename"),
            "Shapefile",
            "*.shp",
        )

        row_c = ttk.Frame(parent)
        row_c.grid(row=3, column=0, columnspan=6, sticky="we", pady=(4, 4))
        ttk.Label(row_c, text="country_names (1/line)").pack(side="left")
        self.txt_mss_dc_sat_countries = tk.Text(row_c, width=48, height=6)
        self.txt_mss_dc_sat_countries.pack(side="left", fill="x", expand=True, padx=(6, 6))

    def _build_mss_dc_beam_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)

        add_row_three(parent, 0, [
            ("type", ttk.Combobox(
                parent,
                textvariable=self.state.get("mss_dc_bp_type"),
                values=[
                    "ANGLE_FROM_SUBSATELLITE",
                    "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
                    "SERVICE_GRID",
                ],
                state="readonly",
                width=28,
            )),
            ("", ttk.Label(parent, text="")),
            ("", ttk.Label(parent, text="")),
        ])

        frame_theta = ttk.LabelFrame(parent, text="angle_from_subsatellite_theta")
        frame_theta.grid(row=1, column=0, columnspan=6, sticky="we", padx=4, pady=(4, 4))
        self._build_mss_dc_value_editor(frame_theta, "mss_dc_theta", min_label="distribution.min", max_label="distribution.max")

        frame_phi = ttk.LabelFrame(parent, text="angle_from_subsatellite_phi")
        frame_phi.grid(row=2, column=0, columnspan=6, sticky="we", padx=4, pady=(4, 4))
        self._build_mss_dc_value_editor(frame_phi, "mss_dc_phi", min_label="distribution.min", max_label="distribution.max")

        frame_distance = ttk.LabelFrame(parent, text="distance_from_subsatellite")
        frame_distance.grid(row=3, column=0, columnspan=6, sticky="we", padx=4, pady=(4, 4))
        self._build_mss_dc_value_editor(frame_distance, "mss_dc_distance", min_label="distribution.min", max_label="distribution.max")

        frame_grid = ttk.LabelFrame(parent, text="service_grid")
        frame_grid.grid(row=4, column=0, columnspan=6, sticky="we", padx=4, pady=(4, 4))
        frame_grid.grid_columnconfigure(0, weight=1)

        row_flags = ttk.Frame(frame_grid)
        row_flags.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2, 4))
        ttk.Checkbutton(
            row_flags,
            text="transform_grid_randomly",
            variable=self.state.get("mss_dc_sg_transform_grid_randomly"),
        ).pack(side="left", padx=(6, 10))
        ttk.Checkbutton(
            row_flags,
            text="enable_fixed_lat_lons_for_grid",
            variable=self.state.get("mss_dc_sg_enable_fixed_lat_lons_for_grid"),
        ).pack(side="left", padx=(0, 6))

        add_row_three(frame_grid, 1, [
            ("grid_margin_from_border [km]", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_grid_margin_from_border"),
                width=10,
            )),
            ("eligible_sats_margin_from_border [km]", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_eligible_sats_margin_from_border"),
                width=10,
            )),
            ("grid_exclusion_zone.type", ttk.Combobox(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_exclusion_type"),
                values=["", "CIRCLE"],
                state="readonly",
                width=10,
            )),
        ])

        add_row_three(frame_grid, 2, [
            ("fixed_lats (list)", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_fixed_lats"),
                width=18,
            )),
            ("fixed_lons (list)", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_fixed_lons"),
                width=18,
            )),
            ("", ttk.Label(frame_grid, text="")),
        ])

        add_row_three(frame_grid, 3, [
            ("circle.center_lat", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_excl_center_lat"),
                width=12,
            )),
            ("circle.center_lon", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_excl_center_lon"),
                width=12,
            )),
            ("circle.radius_km", ttk.Entry(
                frame_grid,
                textvariable=self.state.get("mss_dc_sg_excl_radius_km"),
                width=12,
            )),
        ])

        self._add_file_row(
            frame_grid,
            4,
            "country_shapes_filename",
            self.state.get("mss_dc_sg_country_shapes_filename"),
            "Shapefile",
            "*.shp",
        )

        row_c = ttk.Frame(frame_grid)
        row_c.grid(row=5, column=0, columnspan=6, sticky="we", pady=(4, 4))
        ttk.Label(row_c, text="country_names (1/line)").pack(side="left")
        self.txt_mss_dc_grid_countries = tk.Text(row_c, width=48, height=6)
        self.txt_mss_dc_grid_countries.pack(side="left", fill="x", expand=True, padx=(6, 6))

    def _build_mss_dc_value_editor(self, parent, prefix, min_label="distribution.min", max_label="distribution.max"):
        add_row_three(parent, 0, [
            ("type", ttk.Combobox(
                parent,
                textvariable=self.state.get(f"{prefix}_type"),
                values=["FIXED", "~U(MIN,MAX)", "~SQRT(U(0,1))*MAX"],
                state="readonly",
                width=18,
            )),
            ("fixed", ttk.Entry(parent, textvariable=self.state.get(f"{prefix}_fixed"), width=10)),
            (min_label, ttk.Entry(parent, textvariable=self.state.get(f"{prefix}_dist_min"), width=10)),
        ])
        add_row_three(parent, 1, [
            (max_label, ttk.Entry(parent, textvariable=self.state.get(f"{prefix}_dist_max"), width=10)),
            ("", ttk.Label(parent, text="")),
            ("", ttk.Label(parent, text="")),
        ])

    def _build_mss_dc_orbits_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ttk.Label(
            parent,
            text="Informe a lista de órbitas em YAML. Cada item segue ParametersOrbit.",
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 4))

        self.txt_mss_dc_orbits = tk.Text(parent, width=72, height=12)
        self.txt_mss_dc_orbits.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        parent.grid_rowconfigure(1, weight=1)

    def toggle_visibility(self, *args):
        for frame in self.frames.values():
            frame.grid_remove()

        current = self.state.get("topo_type").get()
        if current in self.frames:
            self.frames[current].grid()

    def _toggle_raster_state(self, *args):
        if not self.ent_raster:
            return
        enc = self._normalized_raster_encoding()
        state = "disabled" if enc == "uniform" else "normal"
        indexed_state = "readonly" if enc == "indexed" else "disabled"
        indexed_entry_state = "normal" if enc == "indexed" else "disabled"
        if enc == "uniform":
            self.state.get("path_raster").set("")
        self.ent_raster.configure(state=state)
        self.btn_raster.configure(state=state)
        for widget in self.raster_widgets:
            widget.configure(state=state)
        for widget in self.indexed_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state=indexed_state)
            else:
                widget.configure(state=indexed_entry_state)

    def _normalized_raster_encoding(self):
        raw = (self.state.get("topo_raster_enc").get() or "").strip()
        legacy = {"Uniforme": "uniform", "Denspop": "indexed", "": "uniform"}
        enc = legacy.get(raw, raw.lower())
        if enc not in {"uniform", "density", "indexed"}:
            enc = "uniform"
        if raw != enc:
            self.state.get("topo_raster_enc").set(enc)
        return enc

    def _add_file_row(self, parent, row, label, var, type_name, ext, return_widgets=False):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(frame, text=label).pack(side="left")
        entry = ttk.Entry(frame, textvariable=var, width=64)
        entry.pack(side="left", fill="x", expand=True, padx=6)

        def pick():
            filename = filedialog.askopenfilename(
                title=f"Choose {type_name}",
                filetypes=[(type_name, ext), ("All", "*.*")],
            )
            if filename:
                var.set(filename)

        button = ttk.Button(frame, text="…", width=3, command=pick)
        button.pack(side="left")
        if return_widgets:
            return entry, button
        return None

    def _set_text_widget(self, widget, text):
        if widget is None:
            return
        widget.delete("1.0", "end")
        if text:
            widget.insert("1.0", text)

    def _get_text_widget(self, widget):
        if widget is None:
            return ""
        return widget.get("1.0", "end").strip()

    def _fallback_mss_dc_countries(self):
        countries = _parse_line_list(self.get_countries_text())
        if countries:
            return countries
        default_countries = DEFAULT_MSS_DC_DATA["sat_is_active_if"]["lat_long_inside_country"]["country_names"]
        return list(default_countries)

    def get_countries_text(self):
        if self.txt_countries:
            return self.txt_countries.get("1.0", "end").strip()
        return ""

    def set_countries_text(self, text):
        if self.txt_countries:
            self.txt_countries.delete("1.0", "end")
            self.txt_countries.insert("1.0", text)

    def get_mss_dc_data(self):
        data = copy.deepcopy(DEFAULT_MSS_DC_DATA)
        fallback_countries = self._fallback_mss_dc_countries()

        name = str(self.state.get("mss_dc_name").get() or "").strip()
        if name:
            data["name"] = name

        num_beams = _num_or_str(self.state.get("mss_dc_num_beams").get())
        if num_beams is not None:
            data["num_beams"] = int(num_beams)

        beam_radius = _num_or_str(self.state.get("mss_dc_beam_radius").get())
        if beam_radius is not None:
            data["beam_radius"] = beam_radius

        sat = data["sat_is_active_if"]
        conditions = []
        if bool(self.state.get("mss_dc_sat_cond_inside_country").get()):
            conditions.append("LAT_LONG_INSIDE_COUNTRY")
        if bool(self.state.get("mss_dc_sat_cond_min_elev").get()):
            conditions.append("MINIMUM_ELEVATION_FROM_ES")
        if bool(self.state.get("mss_dc_sat_cond_max_elev").get()):
            conditions.append("MAXIMUM_ELEVATION_FROM_ES")
        sat["conditions"] = conditions

        min_elev = _num_or_str(self.state.get("mss_dc_sat_min_elevation_from_es").get())
        max_elev = _num_or_str(self.state.get("mss_dc_sat_max_elevation_from_es").get())
        if min_elev is not None:
            sat["minimum_elevation_from_es"] = min_elev
        if max_elev is not None:
            sat["maximum_elevation_from_es"] = max_elev

        lat_long = sat["lat_long_inside_country"]
        sat_country_names = _parse_line_list(self._get_text_widget(self.txt_mss_dc_sat_countries)) or list(fallback_countries)
        lat_long["country_names"] = sat_country_names

        sat_margin = _num_or_str(self.state.get("mss_dc_sat_margin_from_border").get())
        if sat_margin is not None:
            lat_long["margin_from_border"] = sat_margin

        sat_shapes = str(self.state.get("mss_dc_sat_country_shapes_filename").get() or "").strip()
        if sat_shapes:
            lat_long["country_shapes_filename"] = sat_shapes
        else:
            lat_long.pop("country_shapes_filename", None)

        beam_positioning = data["beam_positioning"]
        beam_positioning["type"] = str(self.state.get("mss_dc_bp_type").get() or "SERVICE_GRID").strip()

        for prefix, key in [
            ("mss_dc_theta", "angle_from_subsatellite_theta"),
            ("mss_dc_phi", "angle_from_subsatellite_phi"),
            ("mss_dc_distance", "distance_from_subsatellite"),
        ]:
            block = beam_positioning[key]
            block["type"] = str(self.state.get(f"{prefix}_type").get() or "FIXED").strip()
            fixed = _num_or_str(self.state.get(f"{prefix}_fixed").get())
            dist_min = _num_or_str(self.state.get(f"{prefix}_dist_min").get())
            dist_max = _num_or_str(self.state.get(f"{prefix}_dist_max").get())
            if fixed is not None:
                block["fixed"] = fixed
            if dist_min is not None:
                block["distribution"]["min"] = dist_min
            if dist_max is not None:
                block["distribution"]["max"] = dist_max

        service_grid = beam_positioning["service_grid"]
        grid_country_names = _parse_line_list(self._get_text_widget(self.txt_mss_dc_grid_countries)) or list(sat_country_names)
        service_grid["country_names"] = grid_country_names
        service_grid["transform_grid_randomly"] = bool(self.state.get("mss_dc_sg_transform_grid_randomly").get())

        grid_margin = _num_or_str(self.state.get("mss_dc_sg_grid_margin_from_border").get())
        if grid_margin is not None:
            service_grid["grid_margin_from_border"] = grid_margin

        eligible_margin = _num_or_str(self.state.get("mss_dc_sg_eligible_sats_margin_from_border").get())
        if eligible_margin is not None:
            service_grid["eligible_sats_margin_from_border"] = eligible_margin

        service_grid["enable_fixed_lat_lons_for_grid"] = bool(
            self.state.get("mss_dc_sg_enable_fixed_lat_lons_for_grid").get()
        )

        fixed_lats = _parse_scalar_list(self.state.get("mss_dc_sg_fixed_lats").get())
        fixed_lons = _parse_scalar_list(self.state.get("mss_dc_sg_fixed_lons").get())
        if fixed_lats:
            service_grid["fixed_lats"] = fixed_lats
        if fixed_lons:
            service_grid["fixed_lons"] = fixed_lons

        sg_shapes = str(self.state.get("mss_dc_sg_country_shapes_filename").get() or "").strip()
        if sg_shapes:
            service_grid["country_shapes_filename"] = sg_shapes
        else:
            service_grid.pop("country_shapes_filename", None)

        exclusion = service_grid["grid_exclusion_zone"]
        exclusion_type = str(self.state.get("mss_dc_sg_exclusion_type").get() or "").strip() or None
        exclusion["type"] = exclusion_type
        circle = exclusion["circle"]
        center_lat = _num_or_str(self.state.get("mss_dc_sg_excl_center_lat").get())
        center_lon = _num_or_str(self.state.get("mss_dc_sg_excl_center_lon").get())
        radius_km = _num_or_str(self.state.get("mss_dc_sg_excl_radius_km").get())
        if center_lat is not None:
            circle["center_lat"] = center_lat
        if center_lon is not None:
            circle["center_lon"] = center_lon
        if radius_km is not None:
            circle["radius_km"] = radius_km

        orbits = _parse_yaml_list(self._get_text_widget(self.txt_mss_dc_orbits))
        if orbits:
            data["orbits"] = orbits

        return data

    def set_mss_dc_data(self, data):
        merged = copy.deepcopy(DEFAULT_MSS_DC_DATA)
        if isinstance(data, dict):
            _deep_merge(merged, data)

        sat = merged.get("sat_is_active_if", {})
        lat_long = sat.get("lat_long_inside_country", {})
        beam_positioning = merged.get("beam_positioning", {})
        service_grid = beam_positioning.get("service_grid", {})
        legacy_from_countries = (
            service_grid.get("grid_in_zone", {}).get("from_countries", {})
            if isinstance(service_grid.get("grid_in_zone"), dict)
            else {}
        )

        self.state.get("mss_dc_name").set(merged.get("name", "SystemA"))
        self.state.get("mss_dc_num_beams").set(merged.get("num_beams", 19))
        self.state.get("mss_dc_beam_radius").set(merged.get("beam_radius", 36516.0))

        conditions = sat.get("conditions", [])
        self.state.get("mss_dc_sat_cond_inside_country").set("LAT_LONG_INSIDE_COUNTRY" in conditions)
        self.state.get("mss_dc_sat_cond_min_elev").set("MINIMUM_ELEVATION_FROM_ES" in conditions)
        self.state.get("mss_dc_sat_cond_max_elev").set("MAXIMUM_ELEVATION_FROM_ES" in conditions)
        self.state.get("mss_dc_sat_min_elevation_from_es").set(sat.get("minimum_elevation_from_es", 5.0))
        self.state.get("mss_dc_sat_max_elevation_from_es").set(sat.get("maximum_elevation_from_es", ""))
        self.state.get("mss_dc_sat_margin_from_border").set(lat_long.get("margin_from_border", 0.0))
        self.state.get("mss_dc_sat_country_shapes_filename").set(lat_long.get("country_shapes_filename", ""))

        sat_country_names = lat_long.get("country_names") or self._fallback_mss_dc_countries()
        self._set_text_widget(self.txt_mss_dc_sat_countries, "\n".join(sat_country_names))

        self.state.get("mss_dc_bp_type").set(beam_positioning.get("type", "SERVICE_GRID"))

        for prefix, key in [
            ("mss_dc_theta", "angle_from_subsatellite_theta"),
            ("mss_dc_phi", "angle_from_subsatellite_phi"),
            ("mss_dc_distance", "distance_from_subsatellite"),
        ]:
            block = beam_positioning.get(key, {})
            distribution = block.get("distribution", {})
            self.state.get(f"{prefix}_type").set(block.get("type", "FIXED"))
            self.state.get(f"{prefix}_fixed").set(block.get("fixed", 0.0))
            self.state.get(f"{prefix}_dist_min").set(distribution.get("min", ""))
            self.state.get(f"{prefix}_dist_max").set(distribution.get("max", ""))

        grid_country_names = (
            service_grid.get("country_names")
            or legacy_from_countries.get("country_names")
            or sat_country_names
        )
        self._set_text_widget(self.txt_mss_dc_grid_countries, "\n".join(grid_country_names))

        grid_margin = service_grid.get("grid_margin_from_border")
        if grid_margin is None:
            grid_margin = legacy_from_countries.get("margin_from_border", 0.0)

        self.state.get("mss_dc_sg_transform_grid_randomly").set(
            service_grid.get("transform_grid_randomly", True)
        )
        self.state.get("mss_dc_sg_grid_margin_from_border").set(grid_margin if grid_margin is not None else 0.0)
        self.state.get("mss_dc_sg_eligible_sats_margin_from_border").set(
            service_grid.get("eligible_sats_margin_from_border", 0.0)
        )
        self.state.get("mss_dc_sg_enable_fixed_lat_lons_for_grid").set(
            service_grid.get("enable_fixed_lat_lons_for_grid", False)
        )
        self.state.get("mss_dc_sg_fixed_lats").set(
            ", ".join(map(str, service_grid.get("fixed_lats", [])))
        )
        self.state.get("mss_dc_sg_fixed_lons").set(
            ", ".join(map(str, service_grid.get("fixed_lons", [])))
        )
        self.state.get("mss_dc_sg_country_shapes_filename").set(
            service_grid.get("country_shapes_filename", "")
        )

        exclusion = service_grid.get("grid_exclusion_zone", {})
        circle = exclusion.get("circle", {})
        exclusion_type = exclusion.get("type", None)
        self.state.get("mss_dc_sg_exclusion_type").set("" if exclusion_type is None else exclusion_type)
        self.state.get("mss_dc_sg_excl_center_lat").set(circle.get("center_lat", ""))
        self.state.get("mss_dc_sg_excl_center_lon").set(circle.get("center_lon", ""))
        self.state.get("mss_dc_sg_excl_radius_km").set(circle.get("radius_km", ""))

        self._set_text_widget(self.txt_mss_dc_orbits, _yaml_dump_text(merged.get("orbits", [])))
        self.state.get("mss_dc_config").set(_yaml_dump_text(self.get_mss_dc_data()))

    def get_mss_dc_text(self):
        text = _yaml_dump_text(self.get_mss_dc_data())
        self.state.get("mss_dc_config").set(text)
        return text

    def set_mss_dc_text(self, text):
        final_text = (text or "").strip() or _yaml_dump_text(DEFAULT_MSS_DC_DATA)
        parsed = _parse_yaml_dict(final_text)
        self.set_mss_dc_data(parsed)
        self.state.get("mss_dc_config").set(final_text)
