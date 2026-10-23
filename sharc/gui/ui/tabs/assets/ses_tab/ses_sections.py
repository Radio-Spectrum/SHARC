from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QStackedWidget, QComboBox, QCheckBox, QLineEdit, QPushButton, QFileDialog
)
import os

from PySide6.QtCore import Qt

from ui.tabs.assets.imt_tab.imt_tools import IMTUIHelper as H
from ui.tabs.assets.ses_tab.ses_pattern_controller import (
    LOC_TYPES, AZ_EL_TYPES, SUPPORTED_ANTENNA_PATTERNS, DIAMETER_PATTERNS, CHANNEL_MODELS
)


def _hint(widget, placeholder, tip=""):
    """Placeholder (and tooltip) for an optional free-text field."""
    widget.setPlaceholderText(placeholder)
    if tip:
        widget.setToolTip(tip)
    return widget


class SESBasicSection:
    @staticmethod
    def build(parent_layout, app):
        frm = QGroupBox("Basic Parameters")
        layout = QGridLayout(frm)

        H.add_grid_row(layout, 0, [
            ("frequency [MHz]", H.create_field(app.se_frequency)),
            ("bandwidth [MHz]", H.create_field(app.se_bandwidth)),
            ("noise_temperature [K]", H.create_field(app.se_noise_temperature)),
        ])
        H.add_grid_row(layout, 1, [
            ("adjacent_ch_reception", H.create_field(app.se_adjacent_ch_reception, QComboBox, ["ACS", "OFF"])),
            ("adjacent_ch_selectivity [dB]", H.create_field(app.se_adjacent_ch_selectivity)),
            ("adjacent_ch_emissions", H.create_field(app.se_adjacent_ch_emissions, QComboBox, ["ACLR", "SPECTRAL_MASK", "OFF"])),
        ])
        H.add_grid_row(layout, 2, [
            ("adjacent_ch_leak_ratio [dB]", H.create_field(app.se_adjacent_ch_leak_ratio)),
            ("spectral_mask", _hint(H.create_field(app.se_spectral_mask), "optional",
                                    "Used only when adjacent_ch_emissions = SPECTRAL_MASK")),
            ("spurious_emissions [dBm/MHz]", H.create_field(app.se_spurious_emissions)),
        ])
        H.add_grid_row(layout, 3, [
            ("tx_power_density [dBW/Hz]", H.create_field(app.se_tx_power_density)),
            ("height [m]", H.create_field(app.se_height)),
            ("polarization_loss [dB] (opt.)", H.create_field(app.se_polarization_loss)),
        ])
        parent_layout.addWidget(frm)


class SESGeometrySection:
    def __init__(self, parent_layout, app):
        self.app = app
        self.frame = QGroupBox("Geometry")
        self.main_layout = QVBoxLayout(self.frame)

        self._build_location_ui()
        self._build_pointing_ui()
        
        parent_layout.addWidget(self.frame)

    def _build_location_ui(self):
        box = QGroupBox("Location")
        l = QVBoxLayout(box)

        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("location.type"))
        row_type.addWidget(H.create_field(self.app.se_loc_type, QComboBox, LOC_TYPES))
        row_type.addStretch()
        l.addLayout(row_type)

        self.loc_stack = QStackedWidget()
        l.addWidget(self.loc_stack)
        self.loc_frames = {}

        # FIXED
        f_fix = QWidget()
        l_fix = QGridLayout(f_fix)
        H.add_grid_row(l_fix, 0, [("x [m]", H.create_field(self.app.se_loc_fixed_x)), ("y [m]", H.create_field(self.app.se_loc_fixed_y)), ("", None)])
        self.loc_frames["FIXED"] = f_fix
        self.loc_stack.addWidget(f_fix)

        # FIXED_GEO (needed by the database real terrain: the profiles start here)
        f_geo = QWidget()
        l_geo = QGridLayout(f_geo)
        H.add_grid_row(l_geo, 0, [
            ("latitude [deg]", H.create_field(self.app.se_loc_geo_lat)),
            ("longitude [deg]", H.create_field(self.app.se_loc_geo_lon)),
            ("ground altitude [m]", H.create_field(self.app.se_loc_geo_alt)),
        ])
        self.loc_frames["FIXED_GEO"] = f_geo
        self.loc_stack.addWidget(f_geo)

        # CELL
        f_cell = QWidget()
        l_cell = QGridLayout(f_cell)
        H.add_grid_row(l_cell, 0, [("cell.min_dist_to_bs [m]", H.create_field(self.app.se_loc_cell_min_dist_to_bs)), ("", None), ("", None)])
        self.loc_frames["CELL"] = f_cell
        self.loc_stack.addWidget(f_cell)

        # NETWORK
        f_net = QWidget()
        l_net = QGridLayout(f_net)
        H.add_grid_row(l_net, 0, [("network.min_dist_to_bs [m]", H.create_field(self.app.se_loc_network_min_dist_to_bs)), ("", None), ("", None)])
        self.loc_frames["NETWORK"] = f_net
        self.loc_stack.addWidget(f_net)

        # UNIFORM_DIST
        f_ud = QWidget()
        l_ud = QGridLayout(f_ud)
        H.add_grid_row(l_ud, 0, [("min_dist_to_center [m]", H.create_field(self.app.se_loc_ud_min_dist_to_center)), ("max_dist_to_center [m]", H.create_field(self.app.se_loc_ud_max_dist_to_center)), ("", None)])
        self.loc_frames["UNIFORM_DIST"] = f_ud
        self.loc_stack.addWidget(f_ud)
        
        self.empty_loc = QWidget()
        self.loc_stack.addWidget(self.empty_loc)

        self.app.se_loc_type.value_changed.connect(self.refresh_location)
        self.main_layout.addWidget(box)

    def _build_pointing_ui(self):
        box = QGroupBox("Antenna Pointing (Azimuth / Elevation)")
        l = QHBoxLayout(box)

        c_az = QGroupBox("Azimuth")
        c_el = QGroupBox("Elevation")
        l.addWidget(c_az)
        l.addWidget(c_el)

        self.az_frames, self.az_hint, self.az_stack = self._build_angle_col(
            c_az, self.app.se_az_type, self.app.se_az_fixed, self.app.se_az_ud_min, self.app.se_az_ud_max)
        self.app.se_az_type.value_changed.connect(self.refresh_az)

        self.el_frames, self.el_hint, self.el_stack = self._build_angle_col(
            c_el, self.app.se_el_type, self.app.se_el_fixed, self.app.se_el_ud_min, self.app.se_el_ud_max)
        self.app.se_el_type.value_changed.connect(self.refresh_el)

        self.main_layout.addWidget(box)

    def _build_angle_col(self, parent, var_type, var_fixed, var_min, var_max):
        l = QVBoxLayout(parent)
        
        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("type"))
        row_type.addWidget(H.create_field(var_type, QComboBox, AZ_EL_TYPES))
        l.addLayout(row_type)

        stack = QStackedWidget()
        l.addWidget(stack)
        frames = {}

        # Fixed
        f_fix = QWidget()
        l_fix = QHBoxLayout(f_fix)
        l_fix.setContentsMargins(0,0,0,0)
        l_fix.addWidget(QLabel("fixed [deg]"))
        l_fix.addWidget(H.create_field(var_fixed))
        l_fix.addStretch()
        frames["FIXED"] = f_fix
        stack.addWidget(f_fix)

        # Uniform
        f_ud = QWidget()
        l_ud = QHBoxLayout(f_ud)
        l_ud.setContentsMargins(0,0,0,0)
        l_ud.addWidget(QLabel("min"))
        l_ud.addWidget(H.create_field(var_min))
        l_ud.addWidget(QLabel("max"))
        l_ud.addWidget(H.create_field(var_max))
        frames["UNIFORM_DIST"] = f_ud
        stack.addWidget(f_ud)

        # Hint
        hint = QLabel("(Automatic)")
        hint.setStyleSheet("color: #555;")
        stack.addWidget(hint)
        
        empty = QWidget()
        stack.addWidget(empty)
        stack.setCurrentWidget(empty)

        return frames, hint, stack

    def refresh_location(self, *args):
        t = str(self.app.se_loc_type.get() or "").strip()
        if t in self.loc_frames:
            self.loc_stack.setCurrentWidget(self.loc_frames[t])
        else:
            self.loc_stack.setCurrentWidget(self.empty_loc)

    def refresh_az(self, *args):
        t = str(self.app.se_az_type.get() or "").strip()
        if t in self.az_frames:
            self.az_stack.setCurrentWidget(self.az_frames[t])
        elif t == "POINTING_AT_IMT_CENTER":
            self.az_stack.setCurrentWidget(self.az_hint)

    def refresh_el(self, *args):
        t = str(self.app.se_el_type.get() or "").strip()
        if t in self.el_frames:
            self.el_stack.setCurrentWidget(self.el_frames[t])
        elif t == "POINTING_AT_IMT_CENTER":
            self.el_stack.setCurrentWidget(self.el_hint)

    def refresh_all(self):
        self.refresh_location()
        self.refresh_az()
        self.refresh_el()


class SESAntennaSection:
    """Antena da estação terrena: todos os padrões do motor, com parâmetros e ganho ao vivo."""

    def __init__(self, parent_layout, app):
        self.app = app
        self.frame = QGroupBox("Antenna")
        self.main_layout = QVBoxLayout(self.frame)
        from core.state import SharcVar
        from ui.components.antenna_editor import AntennaEditor

        def get_var(name):
            v = getattr(app, name, None)
            if v is None:
                v = SharcVar("")
                setattr(app, name, v)
            return v

        self.editor = AntennaEditor(get_var, pattern_key="se_ant_pattern",
                                    gain_key="se_ant_gain", prefix="se_ant")
        self.main_layout.addWidget(self.editor)
        parent_layout.addWidget(self.frame)

    def refresh(self, *args):  # compatibilidade com o código antigo
        pass


class SESChannelSection:
    def __init__(self, parent_layout, app):
        self.app = app
        self.frame = QGroupBox("Channel Model")
        self.main_layout = QVBoxLayout(self.frame)

        grid = QGridLayout()
        H.add_grid_row(grid, 0, [
            ("channel_model", H.create_field(app.se_channel_model, QComboBox, CHANNEL_MODELS)),
            ("", None), ("", None)
        ])
        self.main_layout.addLayout(grid)

        # P.452 Frame
        self.p452_box = QGroupBox("P452 Parameters")
        l_p452 = QGridLayout(self.p452_box)

        H.add_grid_row(l_p452, 0, [("atmospheric_pressure [hPa]", H.create_field(app.p452_atmospheric_pressure)), ("air_temperature [K]", H.create_field(app.p452_air_temperature)), ("p_452 [%]", H.create_field(app.p452_percentage_p))])
        H.add_grid_row(l_p452, 1, [("N0", H.create_field(app.p452_N0)), ("delta_N", H.create_field(app.p452_delta_N)), ("polarization", H.create_field(app.p452_polarization, QComboBox, ["horizontal", "vertical"]))])
        H.add_grid_row(l_p452, 2, [("Dct [km]", H.create_field(app.p452_Dct)), ("Dcr [km]", H.create_field(app.p452_Dcr)), ("", None)])
        
        # Read-only heights
        hte = H.create_field(app.p452_Hte)
        hte.setReadOnly(True)
        hre = H.create_field(app.p452_Hre)
        hre.setReadOnly(True)
        H.add_grid_row(l_p452, 3, [("Hte [m] (auto)", hte), ("Hre [m] (auto)", hre), ("clutter_loss", H.create_field(app.p452_clutter_loss, QCheckBox))])

        self.clutter_row = QWidget()
        l_clut = QHBoxLayout(self.clutter_row)
        l_clut.setContentsMargins(0,0,0,0)
        l_clut.addWidget(QLabel("clutter_type"))
        l_clut.addWidget(H.create_field(app.p452_clutter_type, QComboBox, ["one_end", "both_ends"]))
        l_clut.addStretch()
        l_p452.addWidget(self.clutter_row, 4, 0, 1, 6)

        H.add_grid_row(l_p452, 5, [("tx_lat [deg]", H.create_field(app.p452_tx_lat)), ("rx_lat [deg]", H.create_field(app.p452_rx_lat)), ("", None)])

        self._build_p452_database_group(l_p452, 6)

        self.main_layout.addWidget(self.p452_box)

        self.app.se_channel_model.value_changed.connect(self.refresh)
        self.app.p452_clutter_loss.value_changed.connect(self.refresh_clutter)
        for var in (self.app.p452_override_from_db, self.app.p452_hte_from_db,
                    self.app.p452_profile_source, self.app.se_loc_type, self.app.se_channel_model):
            var.value_changed.connect(self.refresh_database_group)
        self.refresh_database_group()
        
        parent_layout.addWidget(self.frame)

    def refresh(self, *args):
        is_p452 = str(self.app.se_channel_model.get() or "").strip() == "P452"
        self.p452_box.setVisible(is_p452)
        self.refresh_clutter()

    def refresh_clutter(self, *args):
        is_p452 = str(self.app.se_channel_model.get() or "").strip() == "P452"
        has_clutter = str(self.app.p452_clutter_loss.get()).lower() in ("true", "1")
        self.clutter_row.setVisible(is_p452 and has_clutter)

    # ------------------------------------------------- P.452 over the database
    def _file_row(self, var, title, filters):
        """Line edit bound to `var` plus a Browse button; returns the row widget."""
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        edit = H.create_field(var, QLineEdit)
        btn = QPushButton("Browse")

        def pick():
            path, _ = QFileDialog.getOpenFileName(row, title, "", filters)
            if path:
                var.set(path)
        btn.clicked.connect(pick)
        lay.addWidget(edit)
        lay.addWidget(btn)
        return row

    def _build_p452_database_group(self, grid, row):
        app = self.app
        box = QGroupBox("Real terrain over the base-station database")
        self.db_group = box
        g = QGridLayout(box)
        tif = "GeoTIFF (*.tif *.tiff);;All files (*)"

        self.lbl_db_status = QLabel("")
        self.lbl_db_status.setWordWrap(True)
        g.addWidget(self.lbl_db_status, 0, 0, 1, 4)

        H.add_grid_row(g, 1, [
            ("override_from_db (precompute P.452 per BS)", H.create_field(app.p452_override_from_db, QCheckBox)),
            ("hte_from_db (BS height from 'altura')", H.create_field(app.p452_hte_from_db, QCheckBox)),
        ])
        H.add_grid_row(g, 2, [
            ("profile_source", H.create_field(app.p452_profile_source, QComboBox, ["mesh", "grid"])),
            ("profile_step_m (0 = 301 points)", H.create_field(app.p452_profile_step_m)),
        ])
        self.row_profile_raster = QWidget()
        lay = QHBoxLayout(self.row_profile_raster)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("profile_raster (terrain, needed for 'grid')"))
        lay.addWidget(self._file_row(app.p452_profile_raster, "Select terrain GeoTIFF", tif), 1)
        g.addWidget(self.row_profile_raster, 3, 0, 1, 4)

        self.row_clutter = QWidget()
        lay = QHBoxLayout(self.row_clutter)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("clutter_raster (land cover)"))
        lay.addWidget(self._file_row(app.p452_clutter_raster, "Select land-cover GeoTIFF", tif), 1)
        lay.addWidget(QLabel("clutter_heights"))
        lay.addWidget(H.create_field(app.p452_clutter_heights, QComboBox, ["celplan", "p452_tab3", "worldcover"]))
        g.addWidget(self.row_clutter, 4, 0, 1, 4)

        row_zone = QWidget()
        lay = QHBoxLayout(row_zone)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("zone_raster (1 = A1 coastal, 2 = A2 inland, 3 = B sea)"))
        lay.addWidget(self._file_row(app.p452_zone_raster, "Select radio-climatic zone GeoTIFF", tif), 1)
        g.addWidget(row_zone, 5, 0, 1, 4)

        btn = QPushButton("Apply required settings")
        btn.setToolTip("Turns on the database, its sites and real terrain, and uses FIXED_GEO for the station.")
        btn.clicked.connect(self.apply_required_settings)
        g.addWidget(btn, 6, 0, 1, 2)

        btn_terrain = QPushButton("Use the terrain loaded in the Terrain tab")
        btn_terrain.setToolTip("Sets profile_source grid with the downloaded terrain, its land cover and the "
                               "worldcover height table (the downloaded land cover uses ESA WorldCover classes).")
        btn_terrain.clicked.connect(self.use_loaded_terrain)
        g.addWidget(btn_terrain, 6, 2, 1, 2)

        grid.addWidget(box, row, 0, 1, 6)
        self._db_vars_connected = False

    def _database_state(self):
        tab = getattr(self.app, "tab_database", None)
        return getattr(tab, "state", None)

    def _connect_database_vars(self):
        """The Database tab is created after this one: hook its variables on first use."""
        st = self._database_state()
        if st is None or self._db_vars_connected:
            return
        for key in ("db_enabled", "db_file", "db_from_sites", "db_use_terrain"):
            st.get(key).value_changed.connect(self.refresh_database_group)
        self._db_vars_connected = True

    def database_requirements(self):
        """What is still missing for P.452 over the database; [] when everything is set."""
        app, st = self.app, self._database_state()
        missing = []

        def on(v):
            return str(v.get()).strip().lower() in ("true", "1")
        if str(app.se_channel_model.get() or "").strip() != "P452":
            missing.append("Channel model must be P452")
        if st is None or not on(st.get("db_enabled")) or not str(st.get("db_file").get() or "").strip():
            missing.append("Database tab: enable the database and choose its file")
        if st is not None and not on(st.get("db_from_sites")):
            missing.append("Database tab: take the sites from the database")
        if st is not None and not on(st.get("db_use_terrain")):
            missing.append("Database tab: use real terrain")
        if str(app.se_loc_type.get() or "").strip() != "FIXED_GEO":
            missing.append("Station location type must be FIXED_GEO (the profiles start there)")
        if str(app.p452_profile_source.get() or "") == "grid" and not str(app.p452_profile_raster.get() or "").strip():
            missing.append("profile_source 'grid' needs profile_raster")
        loaded = self._loaded_terrain()
        clutter = str(app.p452_clutter_raster.get() or "").strip()
        if loaded is not None and clutter and os.path.normcase(os.path.abspath(clutter)) == \
                os.path.normcase(str(loaded.clutter)) and str(app.p452_clutter_heights.get()) != "worldcover":
            missing.append("the downloaded land cover uses ESA WorldCover classes: set clutter_heights to worldcover")
        if loaded is not None and os.path.normcase(os.path.abspath(str(app.p452_profile_raster.get() or "x"))) == \
                os.path.normcase(str(loaded.terrain)):
            problem = self.coverage_problem()
            if problem:
                missing.append(problem)
        return missing

    def _loaded_terrain(self):
        """The terrain set loaded in the Terrain tab, or None."""
        tset = getattr(getattr(self.app, "tab_terrain", None), "active", None)
        return tset if tset is not None and tset.ready else None

    def use_loaded_terrain(self):
        """Point the P.452 profiles at the terrain and land cover downloaded in the Terrain tab."""
        tset = self._loaded_terrain()
        if tset is None:
            self.lbl_db_status.setText("No terrain loaded: download or load one in Terrain & Clutter first.")
            return False
        app = self.app
        app.p452_profile_source.set("grid")
        app.p452_profile_raster.set(str(tset.terrain))
        app.p452_clutter_raster.set(str(tset.clutter))
        app.p452_clutter_heights.set("worldcover")
        zones = tset.folder / "zones.tif"
        try:                    # P.452 zones (coast / sea) from the land cover and the DEM; without them every path is inland
            if not zones.is_file():
                from sharc.propagation.real_terrain.zones import build_zone_raster
                build_zone_raster(str(tset.clutter), str(zones), str(tset.terrain))
            app.p452_zone_raster.set(str(zones))
        except Exception as exc:  # noqa: BLE001 - the other options are still valid
            self.lbl_db_status.setText(f"Zone raster not built ({exc}); paths are treated as inland.")
            return True
        self.refresh_database_group()
        return True

    def coverage_problem(self):
        """Why the loaded terrain does not cover the station and the database sites, or '' when it does."""
        tset = self._loaded_terrain()
        if tset is None:
            return ""
        west, south, east, north = tset.bbox
        points = []
        try:
            points.append((float(self.app.se_loc_geo_lat.get()), float(self.app.se_loc_geo_lon.get())))
        except (TypeError, ValueError):
            pass
        st = self._database_state()
        db_file = str(st.get("db_file").get() or "").strip() if st is not None else ""
        if db_file and os.path.isfile(db_file):
            try:
                import pandas as pd
                df = pd.read_csv(db_file, usecols=["latitude", "longitude"])
                points += [(df["latitude"].min(), df["longitude"].min()), (df["latitude"].max(), df["longitude"].max())]
            except (ValueError, OSError):
                pass
        outside = [(la, lo) for la, lo in points if not (south <= la <= north and west <= lo <= east)]
        if not outside:
            return ""
        la, lo = outside[0]
        return (f"the loaded terrain (lon {west:.3f} to {east:.3f}, lat {south:.3f} to {north:.3f}) does not cover "
                f"({la:.3f}, {lo:.3f}): download a larger region")

    def refresh_database_group(self, *args):
        self._connect_database_vars()
        is_p452 = str(self.app.se_channel_model.get() or "").strip() == "P452"
        self.db_group.setVisible(is_p452)
        grid_src = str(self.app.p452_profile_source.get() or "") == "grid"
        self.row_profile_raster.setVisible(grid_src)
        if not is_p452:
            return
        override = str(self.app.p452_override_from_db.get()).strip().lower() in ("true", "1")
        missing = self.database_requirements() if override else []
        if not override:
            text = ("Off: P.452 is computed on every snapshot with the parameters above. "
                    "Turn override_from_db on to precompute it per base station over the real terrain.")
        elif missing:
            text = "Missing for override_from_db: " + "; ".join(missing) + "."
        else:
            text = "Ready: P.452 is precomputed per base station when the simulation starts (IMT downlink)."
        self.lbl_db_status.setText(text)

    def apply_required_settings(self):
        """Set what override_from_db needs; the database file itself is still the user's choice."""
        st = self._database_state()
        self.app.se_channel_model.set("P452")
        self.app.se_loc_type.set("FIXED_GEO")
        if st is not None:
            st.get("db_enabled").set(True)
            st.get("db_from_sites").set(True)
            st.get("db_use_terrain").set(True)
        self.refresh_database_group()
