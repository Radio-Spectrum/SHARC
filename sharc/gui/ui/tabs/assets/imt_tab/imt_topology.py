import copy
import yaml

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, 
    QFileDialog, QTabWidget, QStackedWidget, QCheckBox
)
from PySide6.QtCore import Qt, Slot

from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper as H

# =============================================================================
# Constantes e Helpers Puros (Sem dependência de Interface)
# =============================================================================

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


# =============================================================================
# Classe da Interface Gráfica (PySide6)
# =============================================================================

class IMTTopologySection:
    def __init__(self, parent_layout, state_manager):
        self.state = state_manager
        
        self.txt_countries = None
        self.txt_mss_dc_sat_countries = None
        self.txt_mss_dc_grid_countries = None
        self.txt_mss_dc_orbits = None
        
        self.raster_widgets = []
        self.indexed_widgets = []

        self._build_ui(parent_layout)

    def _build_ui(self, parent_layout):
        self.frm_t = QGroupBox("Topology – IMT")
        main_layout = QVBoxLayout(self.frm_t)

        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("type:"))
        self.cb_topo_type = H.create_field(self.state.get("topo_type"), QComboBox, 
            ["MACROCELL", "HOTSPOT", "SINGLE_BS", "Macro_countries", "INDOOR", "NTN", "MSS_DC"])
        row_type.addWidget(self.cb_topo_type)
        row_type.addStretch()
        main_layout.addLayout(row_type)

        grid_common = QGridLayout()
        H.add_grid_row(grid_common, 0, [
            ("central_latitude", H.create_field(self.state.get("topo_c_lat"))),
            ("central_longitude", H.create_field(self.state.get("topo_c_lon"))),
            ("central_altitude [m]", H.create_field(self.state.get("topo_c_alt"))),
        ])
        main_layout.addLayout(grid_common)

        # Usando StackedWidget para trocar as topologias conforme seleção
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self.frames = {
            "Macro_countries": self._build_countries(),
            "MACROCELL": self._build_macro(),
            "HOTSPOT": self._build_hotspot(),
            "SINGLE_BS": self._build_sbs(),
            "INDOOR": self._build_indoor(),
            "NTN": self._build_ntn(),
            "MSS_DC": self._build_mss_dc()
        }
        
        for name, widget in self.frames.items():
            self.stack.addWidget(widget)

        self.cb_topo_type.currentTextChanged.connect(self.toggle_visibility)
        parent_layout.addWidget(self.frm_t)
        self.toggle_visibility()

    def _build_countries(self):
        frm = QGroupBox("Topology – COUNTRIES")
        layout = QVBoxLayout(frm)
        
        row_opts = QHBoxLayout()
        row_opts.addWidget(QLabel("raster_encoding"))
        self.cb_enc = H.create_field(self.state.get("topo_raster_enc"), QComboBox, ["uniform", "density", "indexed"])
        self.cb_enc.currentTextChanged.connect(self._toggle_raster_state)
        row_opts.addWidget(self.cb_enc)
        
        row_opts.addWidget(QLabel("dist_type"))
        row_opts.addWidget(H.create_field(self.state.get("topo_dist_type"), QComboBox, ["Urban", "Suburban", "Rural"]))
        row_opts.addStretch()
        layout.addLayout(row_opts)

        grid = QGridLayout()
        cb_mode = H.create_field(self.state.get("topo_sedac_palette_mode"), QComboBox, ["log", "linear"])
        ent_sedac_min = H.create_field(self.state.get("topo_sedac_min"))
        ent_sedac_max = H.create_field(self.state.get("topo_sedac_max"))
        ent_density_thr = H.create_field(self.state.get("topo_min_density_threshold"))
        ent_density_exp = H.create_field(self.state.get("topo_density_exponent"))

        H.add_grid_row(grid, 0, [
            ("sedac_palette_mode", cb_mode),
            ("sedac_min", ent_sedac_min),
            ("sedac_max", ent_sedac_max)
        ])
        H.add_grid_row(grid, 1, [
            ("min_density_threshold", ent_density_thr),
            ("density_exponent", ent_density_exp),
            ("", None)
        ])
        layout.addLayout(grid)

        self.raster_widgets.extend([ent_density_thr, ent_density_exp])
        self.indexed_widgets.extend([cb_mode, ent_sedac_min, ent_sedac_max])

        layout.addWidget(QLabel("country_names (1/line)"))
        self.txt_countries = QTextEdit()
        self.txt_countries.setFixedHeight(100)
        self.txt_countries.setPlainText(str(self.state.get("countries").get()))
        layout.addWidget(self.txt_countries)

        grid2 = QGridLayout()
        H.add_grid_row(grid2, 0, [
            ("num_bs_total", H.create_field(self.state.get("topo_num_bs"))),
            ("cell_radius [m]", H.create_field(self.state.get("topo_cell_radius"))),
            ("rng_seed", H.create_field(self.state.get("topo_rng")))
        ])
        layout.addLayout(grid2)

        self._add_file_row(layout, "countries_shapefile", self.state.get("path_shp"), "Shapefile (*.shp)")
        self.ent_raster, self.btn_raster = self._add_file_row(layout, "population_raster", self.state.get("path_raster"), "GeoTIFF (*.tif *.tiff)", return_widgets=True)

        self._toggle_raster_state()
        return frm

    def _build_macro(self):
        frm = QGroupBox("Topology – MACROCELL")
        l = QGridLayout(frm)
        H.add_grid_row(l, 0, [
            ("intersite_distance [m]", H.create_field(self.state.get("macro_intersite"))),
            ("wrap_around", H.create_field(self.state.get("macro_wrap"), QComboBox, ["False", "True"])),
            ("num_clusters", H.create_field(self.state.get("macro_clusters"))),
        ])
        return frm

    def _build_hotspot(self):
        frm = QGroupBox("Topology – HOTSPOT")
        l = QGridLayout(frm)
        H.add_grid_row(l, 0, [
            ("intersite_distance [m]", H.create_field(self.state.get("hotspot_intersite"))),
            ("wrap_around", H.create_field(self.state.get("hotspot_wrap"), QComboBox, ["False", "True"])),
            ("num_clusters", H.create_field(self.state.get("hotspot_clusters"))),
        ])
        H.add_grid_row(l, 1, [
            ("num_hotspots_per_cell", H.create_field(self.state.get("hotspot_num_per_cell"))),
            ("max_dist_hotspot_ue [m]", H.create_field(self.state.get("hotspot_max_dist_ue"))),
            ("min_dist_bs_hotspot [m]", H.create_field(self.state.get("hotspot_min_dist_bs"))),
        ])
        return frm

    def _build_sbs(self):
        frm = QGroupBox("Topology – SINGLE_BS")
        l = QGridLayout(frm)
        H.add_grid_row(l, 0, [
            ("intersite_distance [m]", H.create_field(self.state.get("sbs_intersite"))),
            ("cell_radius [m]", H.create_field(self.state.get("sbs_cell_radius"))),
            ("num_clusters", H.create_field(self.state.get("sbs_clusters"))),
        ])
        H.add_grid_row(l, 1, [
            ("azimuth (list/str)", H.create_field(self.state.get("sbs_azimuth"))),
            ("", None), ("", None)
        ])
        return frm

    def _build_indoor(self):
        frm = QGroupBox("Topology – INDOOR")
        l = QGridLayout(frm)
        H.add_grid_row(l, 0, [
            ("basic_path_loss", H.create_field(self.state.get("indoor_basic_path_loss"), QComboBox, ["INH_OFFICE", "FSPL"])),
            ("intersite_distance [m]", H.create_field(self.state.get("indoor_intersite"))),
            ("street_width [m]", H.create_field(self.state.get("indoor_street_width"))),
        ])
        H.add_grid_row(l, 1, [
            ("n_rows", H.create_field(self.state.get("indoor_n_rows"))),
            ("n_columns", H.create_field(self.state.get("indoor_n_cols"))),
            ("num_cells", H.create_field(self.state.get("indoor_num_cells"))),
        ])
        H.add_grid_row(l, 2, [
            ("num_floors", H.create_field(self.state.get("indoor_num_floors"))),
            ("num_imt_buildings", H.create_field(self.state.get("indoor_num_buildings"))),
            ("building_class", H.create_field(self.state.get("indoor_building_class"), QComboBox, ["TRADITIONAL", "THERMALLY_EFFICIENT"])),
        ])
        H.add_grid_row(l, 3, [
            ("ue_indoor_percent [0-1]", H.create_field(self.state.get("indoor_ue_indoor_percent"))),
            ("", None), ("", None)
        ])
        return frm

    def _build_ntn(self):
        frm = QGroupBox("Topology – NTN")
        l = QGridLayout(frm)
        H.add_grid_row(l, 0, [
            ("intersite_distance [m]", H.create_field(self.state.get("ntn_intersite"))),
            ("cell_radius [m]", H.create_field(self.state.get("ntn_cell_radius"))),
            ("bs_height [m]", H.create_field(self.state.get("ntn_bs_height"))),
        ])
        H.add_grid_row(l, 1, [
            ("bs_azimuth [deg]", H.create_field(self.state.get("ntn_bs_azimuth"))),
            ("bs_elevation [deg]", H.create_field(self.state.get("ntn_bs_elevation"))),
            ("num_sectors", H.create_field(self.state.get("ntn_num_sectors"), QComboBox, ["1", "7", "19"])),
        ])
        H.add_grid_row(l, 2, [
            ("bs_backoff_power [dB]", H.create_field(self.state.get("ntn_bs_backoff_power"))),
            ("bs_n_rows_layer1", H.create_field(self.state.get("ntn_bs_n_rows_layer1"))),
            ("bs_n_columns_layer1", H.create_field(self.state.get("ntn_bs_n_columns_layer1"))),
        ])
        H.add_grid_row(l, 3, [
            ("bs_n_rows_layer2", H.create_field(self.state.get("ntn_bs_n_rows_layer2"))),
            ("bs_n_columns_layer2", H.create_field(self.state.get("ntn_bs_n_columns_layer2"))),
            ("", None),
        ])
        return frm

    def _build_mss_dc(self):
        frm = QGroupBox("Topology – MSS_DC")
        l = QVBoxLayout(frm)
        
        grid = QGridLayout()
        H.add_grid_row(grid, 0, [
            ("name", H.create_field(self.state.get("mss_dc_name"))),
            ("num_beams", H.create_field(self.state.get("mss_dc_num_beams"), QComboBox, ["1", "7", "19"])),
            ("beam_radius [m]", H.create_field(self.state.get("mss_dc_beam_radius"))),
        ])
        l.addLayout(grid)

        tabs = QTabWidget()
        tab_sat = QWidget()
        tab_beam = QWidget()
        tab_orbits = QWidget()
        
        self._build_mss_dc_satellite_tab(tab_sat)
        self._build_mss_dc_beam_tab(tab_beam)
        self._build_mss_dc_orbits_tab(tab_orbits)

        tabs.addTab(tab_sat, "Sat Selection")
        tabs.addTab(tab_beam, "Beam Positioning")
        tabs.addTab(tab_orbits, "Orbits")
        l.addWidget(tabs)
        
        initial_text = self.state.get("mss_dc_config").get().strip() or _yaml_dump_text(DEFAULT_MSS_DC_DATA)
        self.set_mss_dc_text(initial_text)
        return frm

    def _build_mss_dc_satellite_tab(self, parent):
        l = QVBoxLayout(parent)
        grid = QGridLayout()
        H.add_grid_row(grid, 0, [
            ("LAT_LONG_INSIDE_COUNTRY", H.create_field(self.state.get("mss_dc_sat_cond_inside_country"), QCheckBox)),
            ("MIN_ELEVATION", H.create_field(self.state.get("mss_dc_sat_cond_min_elev"), QCheckBox)),
            ("MAX_ELEVATION", H.create_field(self.state.get("mss_dc_sat_cond_max_elev"), QCheckBox)),
        ])
        H.add_grid_row(grid, 1, [
            ("min_elevation_from_es [deg]", H.create_field(self.state.get("mss_dc_sat_min_elevation_from_es"))),
            ("max_elevation_from_es [deg]", H.create_field(self.state.get("mss_dc_sat_max_elevation_from_es"))),
            ("margin_from_border [km]", H.create_field(self.state.get("mss_dc_sat_margin_from_border"))),
        ])
        l.addLayout(grid)
        self._add_file_row(l, "country_shapes_filename", self.state.get("mss_dc_sat_country_shapes_filename"), "Shapefile (*.shp)")
        
        l.addWidget(QLabel("country_names (1/line)"))
        self.txt_mss_dc_sat_countries = QTextEdit()
        l.addWidget(self.txt_mss_dc_sat_countries)

    def _build_mss_dc_beam_tab(self, parent):
        l = QVBoxLayout(parent)
        grid = QGridLayout()
        
        H.add_grid_row(grid, 0, [
            ("type", H.create_field(self.state.get("mss_dc_bp_type"), QComboBox, 
                ["ANGLE_FROM_SUBSATELLITE", "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE", "SERVICE_GRID"])),
            ("", None), ("", None)
        ])
        l.addLayout(grid)
        
        frame_theta = QGroupBox("angle_from_subsatellite_theta")
        l.addWidget(frame_theta)
        self._build_mss_dc_value_editor(frame_theta, "mss_dc_theta")

        frame_phi = QGroupBox("angle_from_subsatellite_phi")
        l.addWidget(frame_phi)
        self._build_mss_dc_value_editor(frame_phi, "mss_dc_phi")

        frame_distance = QGroupBox("distance_from_subsatellite")
        l.addWidget(frame_distance)
        self._build_mss_dc_value_editor(frame_distance, "mss_dc_distance")
        
        frame_grid = QGroupBox("service_grid")
        l.addWidget(frame_grid)
        l_grid = QVBoxLayout(frame_grid)
        
        flags_grid = QGridLayout()
        H.add_grid_row(flags_grid, 0, [
            ("transform_grid_randomly", H.create_field(self.state.get("mss_dc_sg_transform_grid_randomly"), QCheckBox)),
            ("enable_fixed_lat_lons_for_grid", H.create_field(self.state.get("mss_dc_sg_enable_fixed_lat_lons_for_grid"), QCheckBox)),
            ("", None)
        ])
        H.add_grid_row(flags_grid, 1, [
            ("grid_margin_from_border [km]", H.create_field(self.state.get("mss_dc_sg_grid_margin_from_border"))),
            ("eligible_sats_margin_from_border [km]", H.create_field(self.state.get("mss_dc_sg_eligible_sats_margin_from_border"))),
            ("grid_exclusion_zone.type", H.create_field(self.state.get("mss_dc_sg_exclusion_type"), QComboBox, ["", "CIRCLE"]))
        ])
        H.add_grid_row(flags_grid, 2, [
            ("fixed_lats (list)", H.create_field(self.state.get("mss_dc_sg_fixed_lats"))),
            ("fixed_lons (list)", H.create_field(self.state.get("mss_dc_sg_fixed_lons"))),
            ("", None)
        ])
        H.add_grid_row(flags_grid, 3, [
            ("circle.center_lat", H.create_field(self.state.get("mss_dc_sg_excl_center_lat"))),
            ("circle.center_lon", H.create_field(self.state.get("mss_dc_sg_excl_center_lon"))),
            ("circle.radius_km", H.create_field(self.state.get("mss_dc_sg_excl_radius_km")))
        ])
        l_grid.addLayout(flags_grid)
        
        self._add_file_row(l_grid, "country_shapes_filename", self.state.get("mss_dc_sg_country_shapes_filename"), "Shapefile (*.shp)")
        l_grid.addWidget(QLabel("country_names (1/line)"))
        self.txt_mss_dc_grid_countries = QTextEdit()
        l_grid.addWidget(self.txt_mss_dc_grid_countries)

    def _build_mss_dc_value_editor(self, parent, prefix, min_label="distribution.min", max_label="distribution.max"):
        l = QGridLayout(parent)
        H.add_grid_row(l, 0, [
            ("type", H.create_field(self.state.get(f"{prefix}_type"), QComboBox, ["FIXED", "~U(MIN,MAX)", "~SQRT(U(0,1))*MAX"])),
            ("fixed", H.create_field(self.state.get(f"{prefix}_fixed"))),
            (min_label, H.create_field(self.state.get(f"{prefix}_dist_min")))
        ])
        H.add_grid_row(l, 1, [
            (max_label, H.create_field(self.state.get(f"{prefix}_dist_max"))),
            ("", None), ("", None)
        ])
        
    def _build_mss_dc_orbits_tab(self, parent):
        l = QVBoxLayout(parent)
        l.addWidget(QLabel("Informe a lista de órbitas em YAML. Cada item segue ParametersOrbit."))
        self.txt_mss_dc_orbits = QTextEdit()
        l.addWidget(self.txt_mss_dc_orbits)

    @Slot()
    def toggle_visibility(self, *args):
        current = self.cb_topo_type.currentText()
        if current in self.frames:
            self.stack.setCurrentWidget(self.frames[current])

    @Slot()
    def _toggle_raster_state(self, *args):
        if not self.ent_raster:
            return
        enc = self.cb_enc.currentText().lower()
        is_uniform = (enc == "uniform")
        is_indexed = (enc == "indexed")
        
        self.ent_raster.setEnabled(not is_uniform)
        self.btn_raster.setEnabled(not is_uniform)
        
        for widget in self.raster_widgets:
            widget.setEnabled(not is_uniform)
        for widget in self.indexed_widgets:
            widget.setEnabled(is_indexed)

    def _add_file_row(self, layout, label, var, ext_filter, return_widgets=False):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        entry = QLineEdit(str(var.get()))
        
        def pick():
            f, _ = QFileDialog.getOpenFileName(None, "Choose File", "", ext_filter)
            if f:
                var.set(f)
                entry.setText(f)
                
        var.value_changed.connect(lambda v: entry.setText(str(v)))
        entry.textChanged.connect(lambda t: var.set(t))
        
        btn = QPushButton("...")
        btn.clicked.connect(pick)
        btn.setFixedWidth(40)
        
        row.addWidget(entry)
        row.addWidget(btn)
        layout.addLayout(row)
        
        if return_widgets:
            return entry, btn
        return None

    def get_countries_text(self):
        if self.txt_countries:
            return self.txt_countries.toPlainText().strip()
        return ""

    def set_countries_text(self, text):
        if self.txt_countries:
            self.txt_countries.setPlainText(text)
            
    def _set_text_widget(self, widget, text):
        if widget is None:
            return
        widget.setPlainText(text or "")

    def _get_text_widget(self, widget):
        if widget is None:
            return ""
        return widget.toPlainText().strip()

    def _fallback_mss_dc_countries(self):
        countries = _parse_line_list(self.get_countries_text())
        if countries:
            return countries
        default_countries = DEFAULT_MSS_DC_DATA["sat_is_active_if"]["lat_long_inside_country"]["country_names"]
        return list(default_countries)

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
        data = _parse_yaml_dict(text)
        self.set_mss_dc_data(data)