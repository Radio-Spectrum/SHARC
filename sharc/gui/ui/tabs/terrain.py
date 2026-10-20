"""Terrain & Clutter tab: download real terrain and land cover and show them in the 3D scene.

Data: SRTM elevation and ESA WorldCover land cover, both through the engine's own
downloaders (see `core/terrain_service.py`). Downloads run in the background and are cached
per region, so asking for the same region again is instant.
"""
from __future__ import annotations

import os
import time
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core import buildings_service, hydro_service, terrain_service as ts_mod
from core.state import SharcVar

SOURCES = ["Scenario area", "Database extent", "Custom"]

# name -> value, in display order. The first entry of each list is the lowest detail.
QUALITY = {"Low": 4.0, "Medium": 2.0, "High": 1.5, "Ultra": 1.0}                  # globe screen-space error
RELIEF_RES = {"Low (33 x 33)": 33, "Medium (65 x 65)": 65, "High (129 x 129)": 129, "Very high (257 x 257)": 257}
MAX_LEVELS = ["10", "11", "12", "13", "14", "15"]
LOOKS = ["Analysis (land cover)", "Clean city model (white buildings, roads, trees)", "Realistic (satellite imagery)",
         "City buildings (Cesium OSM Buildings, needs ion token)",
         "Photorealistic 3D (Google tiles, needs ion token or Google key)"]
SUN_HOURS = {"Sunrise (06:30)": 6.5, "Morning (09:00)": 9.0, "Midday (12:30)": 12.5,
             "Afternoon (15:30)": 15.5, "Golden hour (17:30)": 17.5, "Night (22:00)": 22.0}
RELIEF_SOURCES = ["Local SRTM (offline)", "Cesium World Terrain (needs ion token)"]
BUILDING_LIMITS = ["500", "1000", "3000", "6000", "10000"]
BUILDING_DISTANCES = {"Close (1.5 km)": 1500, "Normal (3.5 km)": 3500, "Far (6 km)": 6000}
BUILDING_MIN_HEIGHT = ["0", "3", "6", "10", "20"]
RENDER_SCALES = {"50 %": 0.5, "75 %": 0.75, "100 %": 1.0, "150 %": 1.5, "200 %": 2.0}
BASEMAPS = {"Natural Earth II (offline)": "neii", "Dark political (offline)": "dark", "Esri World Imagery (online)": "esri"}

DEFAULTS: Dict[str, object] = {
    "terr_stream": True,
    "terr_source": "Scenario area",
    "terr_radius_km": "10",
    "terr_margin_km": "5",
    "terr_west": "-38.62", "terr_south": "-3.86", "terr_east": "-38.50", "terr_north": "-3.74",
    "terr_resolution_m": "100",
    "terr_show_relief": True,
    "terr_show_clutter": True,
    "terr_show_hillshade": False,
    "terr_show_hydro": True,
    "terr_check_water": True,
    "terr_quality": "High",
    "terr_relief_res": "Medium (65 x 65)",
    "terr_max_level": "14",
    "terr_bld_limit": "3000",
    "terr_bld_distance": "Normal (3.5 km)",
    "terr_bld_min_height": "0",
    "terr_render_scale": "100 %",
    "terr_basemap": "Natural Earth II (offline)",
    "terr_show_buildings": True,
    "terr_show_trees": True,
    "terr_look": "Analysis (land cover)",
    "terr_relief_source": "Local SRTM (offline)",
    "terr_effects": True,
    "terr_sun_hour": "Midday (12:30)",
    "terr_photoreal_key": "",
    "terr_ion_token": "",
    "terr_trees_limit": "2500",
    "terr_exaggeration": "1.0",
    "terr_clutter_opacity": "0.45",
}


class TerrainStateManager:
    """Terrain/map settings. They are remembered between sessions (QSettings, group "terrain")."""

    def __init__(self):
        from PySide6.QtCore import QSettings
        persist = not os.environ.get("SHARC_GUI_NO_RESTORE")
        self._settings = QSettings("SHARC", "GUI") if persist else None
        self.vars: Dict[str, SharcVar] = {}
        for k, v in DEFAULTS.items():
            kind = bool if isinstance(v, bool) else str
            if self._settings is not None:
                saved = self._settings.value(f"terrain/{k}")
                if saved is not None:
                    v = saved
            var = SharcVar(v, kind)
            self.vars[k] = var
            if self._settings is not None:
                var.value_changed.connect(lambda val, key=k: self._settings.setValue(f"terrain/{key}", val))

    def get(self, key: str) -> SharcVar:
        if key not in self.vars:
            self.vars[key] = SharcVar("")
        return self.vars[key]


class TerrainTab(QWidget):
    """Terrain & land-cover page."""

    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app
        self.state = TerrainStateManager()
        self.active: Optional[ts_mod.TerrainSet] = None
        self.meta: Optional[dict] = None
        self.summary: Optional[dict] = None
        self._job = None
        self._stamp = 0
        from core import tile_service
        tile_service.set_cache_dir(ts_mod.cache_root() / "tiles")
        hydro_service.set_cache_dir(ts_mod.cache_root() / "hydro")
        buildings_service.set_cache_dir(ts_mod.cache_root() / "buildings")
        self._build_ui()
        for key in ("terr_stream", "terr_show_relief", "terr_show_clutter", "terr_show_hillshade", "terr_show_hydro", "terr_show_buildings", "terr_show_trees", "terr_trees_limit", "terr_look", "terr_relief_source", "terr_effects", "terr_sun_hour", "terr_photoreal_key", "terr_ion_token", "terr_quality", "terr_relief_res",
                    "terr_max_level", "terr_bld_limit", "terr_bld_distance", "terr_bld_min_height", "terr_render_scale",
                    "terr_basemap",
                    "terr_exaggeration", "terr_clutter_opacity"):
            self.state.get(key).value_changed.connect(lambda *_: self._redraw_preview())
        for key in ("terr_source", "terr_radius_km", "terr_margin_km", "terr_west", "terr_south",
                    "terr_east", "terr_north"):
            self.state.get(key).value_changed.connect(lambda *_: self._refresh_region_label())
        self._refresh_region_label()

    # ------------------------------------------------------------------ UI
    def _field(self, key, choices=None):
        var = self.state.get(key)
        if isinstance(DEFAULTS[key], bool):
            w = QCheckBox()
            w.setChecked(bool(var.get()))
            w.toggled.connect(var.set)
            return w
        if choices:
            w = QComboBox()
            w.addItems(choices)
            w.setCurrentText(str(var.get()))
            w.currentTextChanged.connect(var.set)
            return w
        w = QLineEdit(str(var.get()))
        w.textChanged.connect(var.set)
        return w

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        g0 = QGroupBox("Map Layers (streamed on demand)")
        p = QGridLayout(g0)
        prow = [("Stream terrain and land cover", self._field("terr_stream")),
                ("Show 3D relief", self._field("terr_show_relief")),
                ("Show land cover", self._field("terr_show_clutter")),
                ("Show hillshade", self._field("terr_show_hillshade")),
                ("Show lakes and rivers", self._field("terr_show_hydro")),
                ("Show buildings when close (OpenStreetMap)", self._field("terr_show_buildings")),
                ("Show trees when close (OpenStreetMap + vegetation)", self._field("terr_show_trees")),
                ("Warn if a base station is on water", self._field("terr_check_water")),
                ("Vertical exaggeration (1 = true scale)", self._field("terr_exaggeration")),
                ("Land-cover opacity", self._field("terr_clutter_opacity"))]
        for i, (label, w) in enumerate(prow):
            p.addWidget(QLabel(label), i, 0)
            p.addWidget(w, i, 1)
        from core import tile_service
        note = QLabel("Tiles are requested only for the area in view and cached on disk, so nothing "
                      "is downloaded up front. " + tile_service.ATTRIBUTION + " " + hydro_service.ATTRIBUTION + " " + buildings_service.ATTRIBUTION)
        note.setWordWrap(True)
        note.setObjectName("StatusMsg")
        p.addWidget(note, len(prow), 0, 1, 2)
        lay.addWidget(g0)

        gd = QGroupBox("Detail and Performance")
        dl = QGridLayout(gd)
        drows = [
            ("Base map", self._field("terr_basemap", list(BASEMAPS))),
            ("Map quality", self._field("terr_quality", list(QUALITY))),
            ("Relief resolution (samples per tile)", self._field("terr_relief_res", list(RELIEF_RES))),
            ("Maximum tile detail level", self._field("terr_max_level", MAX_LEVELS)),
            ("Render resolution", self._field("terr_render_scale", list(RENDER_SCALES))),
            ("Building limit", self._field("terr_bld_limit", BUILDING_LIMITS)),
            ("Scene look", self._field("terr_look", LOOKS)),
            ("Relief source", self._field("terr_relief_source", RELIEF_SOURCES)),
            ("Cinematic tone mapping", self._field("terr_effects")),
            ("Time of day", self._field("terr_sun_hour", list(SUN_HOURS))),
            ("Cesium ion access token (free, ion.cesium.com)", self._field("terr_ion_token")),
            ("Google Map Tiles API key (alternative to ion)", self._field("terr_photoreal_key")),
            ("Tree limit", self._field("terr_trees_limit", ["500", "1000", "2500", "5000"])),
            ("Show buildings when closer than", self._field("terr_bld_distance", list(BUILDING_DISTANCES))),
            ("Hide buildings lower than [m]", self._field("terr_bld_min_height", BUILDING_MIN_HEIGHT)),
        ]
        for i, (label, w) in enumerate(drows):
            dl.addWidget(QLabel(label), i, 0)
            dl.addWidget(w, i, 1)
        hint = QLabel("Higher detail loads more tiles and needs a faster computer and network. "
                      "Lower it if the map feels slow.")
        hint.setWordWrap(True)
        hint.setObjectName("StatusMsg")
        btn_test = QPushButton("Test Google / ion access")
        btn_test.clicked.connect(self._test_photoreal_access)
        self.lbl_photoreal = QLabel("")
        self.lbl_photoreal.setWordWrap(True)
        self.lbl_photoreal.setObjectName("StatusMsg")
        # One container so the property-table converter keeps these as a single full-width block.
        footer = QWidget()
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(0, 4, 0, 0)
        fl.addWidget(hint)
        fl.addWidget(btn_test)
        fl.addWidget(self.lbl_photoreal)
        dl.addWidget(footer, len(drows), 0, 1, 2)
        lay.addWidget(gd)

        g1 = QGroupBox("Offline Region (for the simulation)")
        g = QGridLayout(g1)
        rows = [("Region from", self._field("terr_source", SOURCES)),
                ("Scenario radius [km]", self._field("terr_radius_km")),
                ("Database margin [km]", self._field("terr_margin_km")),
                ("West [deg]", self._field("terr_west")), ("South [deg]", self._field("terr_south")),
                ("East [deg]", self._field("terr_east")), ("North [deg]", self._field("terr_north"))]
        for i, (label, w) in enumerate(rows):
            g.addWidget(QLabel(label), i, 0)
            g.addWidget(w, i, 1)
        self.lbl_region = QLabel("")
        self.lbl_region.setObjectName("StatusMsg")
        self.lbl_region.setWordWrap(True)
        g.addWidget(self.lbl_region, len(rows), 0, 1, 2)
        lay.addWidget(g1)

        g2 = QGroupBox("Data")
        d = QGridLayout(g2)
        d.addWidget(QLabel("Grid resolution [m]"), 0, 0)
        d.addWidget(self._field("terr_resolution_m"), 0, 1)
        d.addWidget(QLabel("Elevation source"), 1, 0)
        d.addWidget(QLabel("SRTM (AWS Terrain Tiles)"), 1, 1)
        d.addWidget(QLabel("Land-cover source"), 2, 0)
        d.addWidget(QLabel("ESA WorldCover 10 m (2021)"), 2, 1)
        lay.addWidget(g2)

        g3 = QGroupBox("Download")
        v = QVBoxLayout(g3)
        row = QHBoxLayout()
        self.btn_download = QPushButton("Download terrain and land cover")
        self.btn_download.clicked.connect(self.download)
        btn_open = QPushButton("Open cache folder")
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ts_mod.cache_root()))))
        btn_clear = QPushButton("Remove from scene")
        btn_clear.clicked.connect(self.clear_active)
        for b in (self.btn_download, btn_open, btn_clear):
            row.addWidget(b)
        v.addLayout(row)
        self.lbl_status = QLabel("No terrain loaded.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.lbl_status)
        lay.addWidget(g3)

        lay.addStretch(1)

    # --------------------------------------------------------------- region
    def region_bbox(self) -> Optional[ts_mod.BBox]:
        def num(key, default=0.0):
            try:
                return float(str(self.state.get(key).get()).replace(",", "."))
            except ValueError:
                return default

        source = str(self.state.get("terr_source").get())
        if source == "Custom":
            return (num("terr_west"), num("terr_south"), num("terr_east"), num("terr_north"))
        if source == "Database extent":
            tab = getattr(self.app, "tab_database", None)
            info = getattr(tab, "_info", {}) if tab is not None else {}
            bbox = info.get("bbox") if info.get("ok") else None
            if not bbox:
                return None
            return ts_mod.expand_bbox(tuple(bbox), num("terr_margin_km", 5.0))
        st = self.app.tab_imt.state
        lat = float(str(st.get("topo_c_lat").get()) or 0.0)
        lon = float(str(st.get("topo_c_lon").get()) or 0.0)
        return ts_mod.bbox_around(lat, lon, num("terr_radius_km", 10.0))

    def _refresh_region_label(self):
        bbox = self.region_bbox()
        if bbox is None:
            self.lbl_region.setText("No database extent yet: choose a database in the Database page.")
            return
        w, s, e, n = bbox
        km_x = (e - w) * 111.32 * max(0.05, abs(__import__("math").cos(__import__("math").radians((s + n) / 2))))
        km_y = (n - s) * 111.32
        res = float(str(self.state.get("terr_resolution_m").get()) or 100)
        px = int(km_x * 1000 / max(1.0, res)) * int(km_y * 1000 / max(1.0, res))
        self.lbl_region.setText(
            f"Region: lon {w:.3f} to {e:.3f}, lat {s:.3f} to {n:.3f}  ({km_x:.0f} x {km_y:.0f} km, "
            f"about {px / 1e6:.1f} million grid cells)")

    # ------------------------------------------------------------- download
    def download(self):
        bbox = self.region_bbox()
        if bbox is None:
            self.lbl_status.setText("Choose a region first.")
            return
        try:
            res = float(str(self.state.get("terr_resolution_m").get()))
        except ValueError:
            self.lbl_status.setText("The grid resolution must be a number.")
            return
        if self._job is not None and self._job.isRunning():
            return
        self.btn_download.setEnabled(False)
        self.lbl_status.setText("Downloading... this can take a minute for large regions.")
        self._job = ts_mod.TerrainDownloadJob(bbox, res, self)
        self._job.log.connect(self.app._safe_log)
        self._job.finished_ok.connect(self._on_ready)
        self._job.failed.connect(self._on_failed)
        self._job.start()

    def _on_failed(self, message: str):
        self.btn_download.setEnabled(True)
        self.lbl_status.setText(f"Download failed: {message}")
        self.app._safe_log(f"[TERRAIN] Download failed: {message}")

    def _on_ready(self, tset):
        self.btn_download.setEnabled(True)
        self.set_active(tset)

    def set_active(self, tset: ts_mod.TerrainSet):
        """Make `tset` the terrain shown in the scene (builds overlays if needed)."""
        meta = ts_mod.load_overlay_meta(tset) or ts_mod.build_overlays(tset)
        self.active, self.meta = tset, meta
        self.summary = ts_mod.summarize(tset)
        self._stamp = int(time.time())
        from web.cesium_preview.local_server import set_overlay_dir
        set_overlay_dir(tset.folder)
        s = self.summary
        classes = ", ".join(f"{n} {p:.0f}%" for n, p in list(s["classes"].items())[:4])
        self.lbl_status.setText(
            f"Loaded {s['size']} cells. Elevation {s['elev_min']:.0f} to {s['elev_max']:.0f} m "
            f"(mean {s['elev_mean']:.0f} m). Land cover: {classes}.")
        self.app._safe_log(f"[TERRAIN] Terrain ready: {s['size']} cells, elevation "
                           f"{s['elev_min']:.0f}..{s['elev_max']:.0f} m")
        self._redraw_preview()

    def clear_active(self):
        self.active, self.meta, self.summary = None, None, None
        self.lbl_status.setText("No terrain loaded.")
        self._redraw_preview()

    def _redraw_preview(self):
        try:
            self.app.tab_preview._draw_preview()
        except AttributeError:
            pass

    # -------------------------------------------------------- preview data
    def overlay_info(self) -> Optional[dict]:
        """What the 3D scene needs to stream terrain and land cover (None when switched off)."""
        def flag(k):
            v = self.state.get(k).get()
            return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")

        def num(k, d):
            try:
                return float(str(self.state.get(k).get()))
            except ValueError:
                return d
        if not flag("terr_stream"):
            return None
        look = str(self.state.get("terr_look").get())
        clean = look.startswith("Clean")
        realistic = look.startswith(("Realistic", "City", "Photorealistic"))
        city_mode = "osm" if look.startswith("City") else ("photo" if look.startswith("Photorealistic") else "")
        return {
            "mode": "stream",
            "relief": flag("terr_show_relief"), "clutter": flag("terr_show_clutter") and not realistic,
            "hillshade": flag("terr_show_hillshade"), "hydro": flag("terr_show_hydro"), "buildings": flag("terr_show_buildings"), "trees": flag("terr_show_trees"),
            "trees_max": int(num("terr_trees_limit", 2500)),
            "exaggeration": num("terr_exaggeration", 1.0), "opacity": 0.85 if clean else num("terr_clutter_opacity", 0.45),
            "legend": [{"label": n, "color": c} for n, c in ts_mod.legend()],
            "sse": QUALITY.get(str(self.state.get("terr_quality").get()), 1.5),
            "relief_samples": RELIEF_RES.get(str(self.state.get("terr_relief_res").get()), 65),
            "max_level": int(num("terr_max_level", 14)),
            "buildings_max": int(num("terr_bld_limit", 3000)),
            "buildings_distance_m": BUILDING_DISTANCES.get(str(self.state.get("terr_bld_distance").get()), 3500),
            "buildings_min_height": num("terr_bld_min_height", 0),
            "render_scale": RENDER_SCALES.get(str(self.state.get("terr_render_scale").get()), 1.0),
            "basemap": "esri" if realistic else BASEMAPS.get(str(self.state.get("terr_basemap").get()), "neii"),
            "realistic": realistic,
            "effects": flag("terr_effects"),
            "world_terrain": str(self.state.get("terr_relief_source").get()).startswith("Cesium"),
            "sun_hour": SUN_HOURS.get(str(self.state.get("terr_sun_hour").get()), 12.5),
            "photoreal_key": str(self.state.get("terr_photoreal_key").get()).strip(),
            "ion_token": str(self.state.get("terr_ion_token").get()).strip(),
            "city_mode": city_mode,
            "clean": clean,
        }

    def _test_photoreal_access(self):
        """Check the Google key and/or ion token on a worker thread; the result lands in the label and Messages."""
        import threading
        from PySide6.QtCore import QTimer
        from core import photoreal_check
        key = str(self.state.get("terr_photoreal_key").get()).strip()
        token = str(self.state.get("terr_ion_token").get()).strip()
        if not key and not token:
            self.lbl_photoreal.setText("Enter a Google Map Tiles API key or a Cesium ion token first.")
            return
        self.lbl_photoreal.setText("Checking...")
        holder: list = []

        def work():
            res = []
            if key:
                res.append(photoreal_check.check_google_key(key))
            if token:
                res.append(photoreal_check.check_ion_token(token))
            holder.append(res)

        threading.Thread(target=work, daemon=True).start()
        timer = QTimer(self)
        timer.setInterval(150)

        def poll():
            if not holder:
                return
            timer.stop()
            self.lbl_photoreal.setText("\n".join(("OK: " if ok else "FAILED: ") + msg for ok, msg in holder[0]))

        timer.timeout.connect(poll)
        timer.start()

    def ground_heights(self, lat, lon):
        """Ground height [m] at the points (streamed DEM), or None when streaming is off."""
        import numpy as np
        from core import tile_service
        if self.overlay_info() is None:
            return None
        lat = np.atleast_1d(np.asarray(lat, float))
        lon = np.atleast_1d(np.asarray(lon, float))
        out = []
        for la, lo in zip(lat, lon):
            h = tile_service.ground_height(float(la), float(lo))
            out.append(0.0 if h is None else h)
        return np.asarray(out)
