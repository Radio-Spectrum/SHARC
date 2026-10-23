"""Protection Contour page: how far from a protected station (radio-astronomy dish, or any fixed receiver) IMT base
stations must be, in every direction, to meet its protection criterion. Runs `sharc.contour` for any site and region.

Left: site, terrain, base station, criterion and propagation. Right: the contour on a map, a summary per off-axis angle
and exports (CSV, PNG / PDF / SVG). The campaign runs in a background thread (rays in worker processes).
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from sharc.contour import campaign
from sharc.contour.budget import ReferenceBs
from sharc.contour.calculator import Sweep
from sharc.contour.criterion import Criterion
from sharc.contour.region import Region
from sharc.contour.site import PRESETS, RasSite

CUSTOM = "Custom"
TABLE_COLUMNS = ["Off-axis [deg]", "Rays", "Median [km]", "Min [km]", "Max [km]", "Violated at ray end"]


class ContourJob(QThread):
    """Runs a campaign off the GUI thread."""
    progressed = Signal(int, int)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, config: campaign.ContourConfig, processes: int, parent=None):
        super().__init__(parent)
        self.config, self.processes, self._cancel = config, processes, False

    def cancel(self):
        self._cancel = True

    def run(self):  # noqa: D401 (Qt override)
        try:
            rows = campaign.run_campaign(self.config, self.processes, self.progressed.emit, lambda: self._cancel)
            self.finished_ok.emit(rows)
        except Exception as exc:  # noqa: BLE001 - shown to the user, never crashes the GUI
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def _spin(value, lo, hi, decimals=2, step=1.0, suffix="") -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    if suffix:
        box.setSuffix(suffix)
    return box


class ContourTab(QWidget):
    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app
        self.rows: List[dict] = []
        self._job: Optional[ContourJob] = None
        self._started = 0.0
        self.w: Dict[str, QWidget] = {}
        self._build_ui()
        self._apply_preset(next(iter(PRESETS)))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QHBoxLayout(self)
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split)

        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setMinimumWidth(300)
        left.setMaximumWidth(380)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.addWidget(self._site_group())
        lay.addWidget(self._terrain_group())
        lay.addWidget(self._bs_group())
        lay.addWidget(self._criterion_group())
        lay.addWidget(self._propagation_group())
        lay.addWidget(self._rays_group())
        lay.addStretch(1)
        left.setWidget(panel)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        bar = QHBoxLayout()
        self.btn_run = QPushButton("Run contour")
        self.btn_run.setObjectName("ActionBtn")
        self.btn_run.clicked.connect(self.run)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_csv = QPushButton("Export CSV")
        self.btn_csv.clicked.connect(self.export_csv)
        self.btn_fig = QPushButton("Export figure")
        self.btn_fig.clicked.connect(self.export_figure)
        self.btn_3d = QPushButton("Show in 3D Scene")
        self.btn_3d.setToolTip("Draw the contour on the terrain of the 3D preview and fly the camera to the station")
        self.btn_3d.clicked.connect(lambda: self.show_in_3d())
        self.btn_3d_clear = QPushButton("Clear from 3D")
        self.btn_3d_clear.clicked.connect(self.clear_3d)
        for b in (self.btn_run, self.btn_cancel, self.btn_csv, self.btn_fig, self.btn_3d, self.btn_3d_clear):
            bar.addWidget(b)
        bar.addStretch(1)
        rl.addLayout(bar)
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        rl.addWidget(self.progress)
        self.lbl_status = QLabel("Choose the site and the terrain, then Run contour.")
        self.lbl_status.setWordWrap(True)
        rl.addWidget(self.lbl_status)

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from sharc.contour.plot import contour_figure
        self._contour_figure = contour_figure
        self.canvas = FigureCanvasQTAgg(contour_figure([], dpi=100))
        self.canvas.setMinimumHeight(320)
        rl.addWidget(self.canvas, 1)

        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.table.setMaximumHeight(130)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        rl.addWidget(self.table)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 700])
        self._set_buttons(False)

    def _site_group(self) -> QGroupBox:
        box, form = QGroupBox("Protected station"), QFormLayout()
        box.setLayout(form)
        w = self.w
        w["preset"] = QComboBox()
        w["preset"].addItems([CUSTOM, *PRESETS])
        w["preset"].currentTextChanged.connect(lambda name: self._apply_preset(name) if name != CUSTOM else None)
        form.addRow("Preset", w["preset"])
        w["name"] = QLineEdit("Station")
        w["lat"], w["lon"] = _spin(0.0, -90, 90, 5, 0.01, " deg"), _spin(0.0, -180, 180, 5, 0.01, " deg")
        w["height"] = _spin(15.0, 0, 500, 1, 1, " m")
        w["dish"] = _spin(12.0, 0.1, 500, 1, 1, " m")
        w["eff"] = _spin(0.7, 0.05, 1.0, 2, 0.01)
        w["freq"] = _spin(4895.0, 100, 100000, 1, 10, " MHz")
        w["bw"] = _spin(190.0, 0.001, 20000, 2, 10, " MHz")
        w["elev"] = _spin(8.1, 0, 90, 1, 1, " deg")
        w["temp"] = _spin(50.0, 1, 5000, 1, 5, " K")
        for label, key in (("Name", "name"), ("Latitude", "lat"), ("Longitude", "lon"), ("Antenna height", "height"),
                           ("Dish diameter", "dish"), ("Efficiency", "eff"), ("Observation frequency", "freq"),
                           ("Observation bandwidth", "bw"), ("Dish elevation", "elev"), ("System temperature", "temp")):
            form.addRow(label, w[key])
        for key in ("name", "lat", "lon", "height", "dish", "eff", "freq", "bw", "elev", "temp"):
            sig = w[key].textChanged if key == "name" else w[key].valueChanged
            sig.connect(lambda *_: self.w["preset"].setCurrentText(CUSTOM) if not self._loading_preset else None)
        return box

    _loading_preset = False

    def _terrain_group(self) -> QGroupBox:
        box, form = QGroupBox("Terrain"), QFormLayout()
        box.setLayout(form)
        w = self.w
        self.lbl_terrain = QLabel("No terrain loaded in the Terrain & Clutter page.")
        self.lbl_terrain.setWordWrap(True)
        form.addRow(self.lbl_terrain)
        btn = QPushButton("Use the terrain loaded in Terrain && Clutter")
        btn.clicked.connect(self.use_loaded_terrain)
        form.addRow(btn)
        w["dem"], w["cover"], w["zones"] = QLineEdit(), QLineEdit(), QLineEdit()
        for label, key, tip in (("Elevation (GeoTIFF)", "dem", "Required"),
                                ("Land cover (GeoTIFF)", "cover", "Optional: adds clutter heights to the profiles"),
                                ("P.452 zones (GeoTIFF)", "zones", "Optional: 1 coastal, 2 inland, 3 sea; none = all inland")):
            w[key].setToolTip(tip)
            row = QHBoxLayout()
            row.addWidget(w[key], 1)
            pick = QPushButton("...")
            pick.setFixedWidth(30)
            pick.clicked.connect(lambda _=False, k=key: self._pick_file(k))
            row.addWidget(pick)
            form.addRow(label, row)
        w["heights"] = QComboBox()
        w["heights"].addItems(["worldcover", "celplan", "p452_tab3"])
        w["heights"].setToolTip("Height table of the land-cover classes (the downloaded land cover is ESA WorldCover)")
        form.addRow("Clutter heights", w["heights"])
        w["polygon"] = QLineEdit()
        w["polygon"].setToolTip("Optional GeoJSON of the study area: rays end where they leave it")
        row = QHBoxLayout()
        row.addWidget(w["polygon"], 1)
        pick = QPushButton("...")
        pick.setFixedWidth(30)
        pick.clicked.connect(lambda: self._pick_file("polygon", "GeoJSON (*.geojson *.json);;All files (*)"))
        row.addWidget(pick)
        form.addRow("Boundary (GeoJSON)", row)
        return box

    def _bs_group(self) -> QGroupBox:
        box, form = QGroupBox("Reference base station (IMT)"), QFormLayout()
        box.setLayout(form)
        w, d = self.w, ReferenceBs()
        w["bs_freq"], w["bs_bw"] = _spin(d.frequency_mhz, 100, 100000, 1, 10, " MHz"), _spin(d.bandwidth_mhz, 1, 2000, 1, 10, " MHz")
        w["spur"] = _spin(d.spurious_dbm_mhz, -200, 100, 1, 1, " dBm/MHz")
        w["n_op"] = QSpinBox()
        w["n_op"].setRange(1, 20)
        w["n_op"].setValue(d.n_operators)
        w["tilt"] = _spin(d.downtilt_deg, -30, 60, 1, 1, " deg")
        w["losses"] = _spin(d.losses_db, -50, 100, 1, 1, " dB")
        w["bs_height"] = _spin(30.0, 1, 500, 1, 1, " m")
        w["db"] = QLineEdit()
        w["db"].setToolTip("Optional CSV (latitude, longitude, altura): the height at each distance is the median of "
                           "the base stations of a ring around the station")
        row = QHBoxLayout()
        row.addWidget(w["db"], 1)
        pick = QPushButton("...")
        pick.setFixedWidth(30)
        pick.clicked.connect(lambda: self._pick_file("db", "CSV (*.csv);;All files (*)"))
        row.addWidget(pick)
        for label, key in (("IMT carrier frequency", "bs_freq"), ("IMT carrier bandwidth", "bs_bw"),
                           ("Spurious emission / operator", "spur"), ("Operators", "n_op"), ("Downtilt", "tilt"),
                           ("Other losses", "losses"), ("Constant height", "bs_height")):
            form.addRow(label, w[key])
        form.addRow("Height database (CSV)", row)
        return box

    def _criterion_group(self) -> QGroupBox:
        box, form = QGroupBox("Protection criterion (ITU-R RA.769)"), QFormLayout()
        box.setLayout(form)
        w = self.w
        w["case"] = QComboBox()
        w["case"].addItems(["VLBI", "CONTINUUM"])
        w["p_vlbi"], w["p_cont"] = _spin(1.0, 0.0001, 100, 4, 0.1, " %"), _spin(1.0, 0.0001, 100, 4, 0.1, " %")
        w["tau"] = _spin(2000.0, 0.001, 1e7, 1, 100, " s")
        w["margin"] = _spin(0.0, -50, 50, 1, 1, " dB")
        for label, key in (("Case", "case"), ("VLBI percentage", "p_vlbi"), ("Continuum percentage", "p_cont"),
                           ("Integration time", "tau"), ("Allocation margin", "margin")):
            form.addRow(label, w[key])
        return box

    def _propagation_group(self) -> QGroupBox:
        box, form = QGroupBox("Propagation (ITU-R P.452)"), QFormLayout()
        box.setLayout(form)
        w, p = self.w, campaign.DEFAULT_P452
        w["prop_freq"] = _spin(3500.0, 100, 50000, 1, 10, " MHz")
        w["prop_freq"].setToolTip("Frequency of the loss calculation: the IMT carrier, as in the SHARC campaigns")
        w["p"] = _spin(p["percentage_p"], 0.001, 50, 3, 0.5, " %")
        w["dn"] = _spin(p["delta_N"], 0, 200, 1, 1)
        w["n0"] = _spin(p["N0"], 200, 500, 1, 1)
        w["pol"] = QComboBox()
        w["pol"].addItems(["horizontal", "vertical"])
        w["clutter_loss"] = QCheckBox("Add P.2108 clutter loss at the ends")
        for label, key in (("Loss frequency", "prop_freq"), ("Time percentage p", "p"), ("Delta N", "dn"), ("N0", "n0"),
                           ("Polarization", "pol")):
            form.addRow(label, w[key])
        form.addRow(w["clutter_loss"])
        return box

    def _rays_group(self) -> QGroupBox:
        box, form = QGroupBox("Rays and search"), QFormLayout()
        box.setLayout(form)
        w, s = self.w, Sweep()
        w["ray_step"] = _spin(10.0, 0.1, 90, 2, 1, " deg")
        w["offs"] = QLineEdit("0, 90, 135")
        w["offs"].setToolTip("Base-station off-axis angles [deg], comma separated: 0 points the sector at the station, "
                             "180 away from it")
        w["step"] = _spin(s.step_m, 10, 5000, 0, 10, " m")
        w["step"].setToolTip("Spacing of the search grid AND of the terrain profile points. Keep it at 50 m: a coarse profile "
                             "misses hills and makes the contour too large")
        w["dmin"] = _spin(s.d_min_m, 10, 100000, 0, 50, " m")
        w["dmax"] = _spin(s.d_max_m / 1000.0, 1, 3000, 0, 10, " km")
        w["tol"] = _spin(s.tol_m, 0.1, 100, 1, 1, " m")
        w["procs"] = QSpinBox()
        w["procs"].setRange(1, max(1, (os.cpu_count() or 2)))
        w["procs"].setValue(max(1, min(4, (os.cpu_count() or 2) - 1)))
        for label, key in (("Azimuth step", "ray_step"), ("BS off-axis angles", "offs"), ("Search step", "step"),
                           ("Minimum distance", "dmin"), ("Maximum distance", "dmax"), ("Tolerance", "tol"),
                           ("Processes", "procs")):
            form.addRow(label, w[key])
        return box

    # ------------------------------------------------------------- helpers
    def _pick_file(self, key: str, filt: str = "GeoTIFF (*.tif *.tiff);;All files (*)"):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", self.w[key].text() or "", filt)
        if path:
            self.w[key].setText(path)

    def _apply_preset(self, name: str):
        site = PRESETS.get(name)
        if site is None:
            return
        self._loading_preset = True
        try:
            w = self.w
            w["preset"].setCurrentText(name)
            w["name"].setText(site.name)
            for key, value in (("lat", site.lat_deg), ("lon", site.lon_deg), ("height", site.height_m),
                               ("dish", site.diameter_m), ("eff", site.efficiency), ("freq", site.frequency_mhz),
                               ("bw", site.bandwidth_mhz), ("elev", site.elevation_deg), ("temp", site.temperature_k)):
                w[key].setValue(value)
        finally:
            self._loading_preset = False

    def use_loaded_terrain(self) -> bool:
        """Fill the terrain files from the terrain loaded in the Terrain & Clutter page (zones are derived)."""
        tset = getattr(getattr(self.app, "tab_terrain", None), "active", None)
        if tset is None or not tset.ready:
            self.lbl_terrain.setText("No terrain loaded: download or load one in Terrain & Clutter first.")
            return False
        try:
            region = Region.from_terrain_set(tset)
        except Exception as exc:  # noqa: BLE001
            self.lbl_terrain.setText(f"Could not prepare the terrain: {exc}")
            return False
        self.w["dem"].setText(region.terrain)
        self.w["cover"].setText(region.clutter)
        self.w["zones"].setText(region.zones)
        self.w["heights"].setCurrentText("worldcover")
        w, e, s, n = tset.bbox[0], tset.bbox[2], tset.bbox[1], tset.bbox[3]
        self.lbl_terrain.setText(f"Terrain loaded: lon {w:.3f} to {e:.3f}, lat {s:.3f} to {n:.3f}.")
        return True

    def _offs(self) -> List[float]:
        try:
            values = [float(v) for v in self.w["offs"].text().replace(";", ",").split(",") if v.strip()]
        except ValueError:
            raise ValueError("BS off-axis angles must be numbers separated by commas") from None
        if not values:
            raise ValueError("give at least one BS off-axis angle")
        return values

    def config(self) -> campaign.ContourConfig:
        """The campaign configured in the page; raises ValueError with a message the user can act on."""
        w = self.w
        if not w["dem"].text().strip():
            raise ValueError("choose the elevation raster, or use the terrain loaded in Terrain & Clutter")
        site = RasSite(w["name"].text().strip() or "Station", w["lat"].value(), w["lon"].value(), w["height"].value(),
                       w["dish"].value(), w["eff"].value(), w["freq"].value(), w["bw"].value(), w["elev"].value(),
                       w["temp"].value())
        region = Region(w["dem"].text().strip(), w["cover"].text().strip(), w["zones"].text().strip(),
                        w["heights"].currentText(), w["step"].value())
        p452 = dict(campaign.DEFAULT_P452, percentage_p=w["p"].value(), delta_N=w["dn"].value(), N0=w["n0"].value(),
                    polarization=w["pol"].currentText(), clutter_loss=w["clutter_loss"].isChecked())
        return campaign.ContourConfig(
            site=site, region=region,
            bs=ReferenceBs(w["bs_freq"].value(), w["bs_bw"].value(), w["spur"].value(), w["n_op"].value(),
                           w["tilt"].value(), w["losses"].value()),
            criterion=Criterion(w["case"].currentText(), w["p_vlbi"].value(), w["p_cont"].value(), w["tau"].value(),
                                w["margin"].value()),
            p452=p452, propagation_frequency_mhz=w["prop_freq"].value(),
            sweep=Sweep(w["step"].value(), w["dmin"].value(), w["dmax"].value() * 1000.0, w["tol"].value()),
            bs_height_m=w["bs_height"].value(), database_csv=w["db"].text().strip(),
            polygon_geojson=w["polygon"].text().strip(), ray_step_deg=w["ray_step"].value(), off_axis_deg=self._offs())

    def _set_buttons(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        has = bool(self.rows) and not running
        self.btn_csv.setEnabled(has)
        self.btn_fig.setEnabled(has)
        self.btn_3d.setEnabled(has)

    # --------------------------------------------------------------- run
    def run(self, processes: Optional[int] = None) -> bool:
        if self._job is not None and self._job.isRunning():
            return False
        try:
            cfg = self.config()
            cfg.region.check()
            cfg.build()                      # fail here, with a clear message, instead of inside the worker
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"Cannot run: {exc}")
            self.app._safe_log(f"[CONTOUR] Cannot run: {exc}")
            return False
        n = int(processes if isinstance(processes, int) and not isinstance(processes, bool) else self.w["procs"].value())
        self.rows = []
        self.progress.setValue(0)
        self._started = time.time()
        self.lbl_status.setText(f"Running {len(cfg.azimuths())} rays x {len(cfg.off_axis_deg)} off-axis angles...")
        self._set_buttons(True)
        self._job = ContourJob(cfg, n, self)
        self._job.progressed.connect(self._on_progress)
        self._job.finished_ok.connect(self._on_done)
        self._job.failed.connect(self._on_failed)
        self._job.start()
        return True

    def cancel(self):
        if self._job is not None:
            self._job.cancel()
            self.lbl_status.setText("Cancelling after the current rays...")

    def wait(self, ms: int = 600000) -> bool:
        """Block until the running campaign ends (tests and scripts)."""
        return True if self._job is None else self._job.wait(ms)

    def _on_progress(self, done: int, total: int):
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        elapsed = time.time() - self._started
        if done >= 2 and total > done:                      # an estimate only once there is something to extrapolate
            left = elapsed / done * (total - done)
            text = f"{int(left // 60)} min {int(left % 60):02d} s" if left >= 60 else f"{int(left)} s"
            self.lbl_status.setText(f"Running: {done} of {total} rays done, about {text} left.")

    def _on_failed(self, message: str):
        self._set_buttons(False)
        self.lbl_status.setText(f"Failed: {message}")
        self.app._safe_log(f"[CONTOUR] Failed: {message}")

    def _on_done(self, rows):
        self.rows = list(rows)
        self._set_buttons(False)
        took = time.time() - self._started
        self.lbl_status.setText(f"Done: {len(self.rows)} results in {took:.0f} s. Crosses mark rays on which the "
                                "criterion is still violated where the ray ends.")
        self.app._safe_log(f"[CONTOUR] {len(self.rows)} results in {took:.0f} s")
        self._show(self.rows)

    def _show(self, rows):
        site_name = self.w["name"].text().strip() or "Station"
        self._contour_figure(rows, site_name, fig=self.canvas.figure)       # keeps the size the canvas gave the figure
        self.canvas.draw_idle()
        info = campaign.summary(rows)
        self.table.setRowCount(len(info))
        for r, (off, s) in enumerate(info.items()):
            values = [f"{off:g}", f"{s['rays']}", f"{s['median_m'] / 1000:.2f}", f"{s['min_m'] / 1000:.2f}",
                      f"{s['max_m'] / 1000:.2f}", f"{int(s.get('not_met_at_end', 0))}"]
            for c, text in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------- 3D scene
    def _embed(self):
        return getattr(getattr(self.app, "tab_preview", None), "_cesium_embed", None)

    def _run_js(self, code: str) -> bool:
        embed = self._embed()
        if embed is None:
            return False
        embed.view.page().runJavaScript(code)
        return True

    def contour_payload(self) -> Optional[dict]:
        """The 3D-scene description of the current results (None without results)."""
        if not self.rows:
            return None
        from core import contour_scene
        w = self.w
        return contour_scene.payload(self.rows, w["name"].text().strip() or "Station", w["lat"].value(), w["lon"].value())

    def show_in_3d(self, fly: bool = True, switch: bool = True) -> bool:
        """Draw the contour in the 3D preview (and go there). False with a message when it cannot."""
        data = self.contour_payload()
        if data is None:
            self.lbl_status.setText("Run the contour first: there is nothing to show yet.")
            return False
        import json
        if not self._run_js(f"setContour({json.dumps(data)}, {'true' if fly else 'false'});"):
            self.lbl_status.setText("The 3D preview is not available in this installation.")
            return False
        self._connect_ready()
        if switch and hasattr(self.app, "_switch_page"):
            self.app._switch_page("preview", "Topology Preview")
        self.lbl_status.setText("Contour drawn in the 3D Scene (camera on the station). Use Clear from 3D to remove it.")
        return True

    def clear_3d(self) -> None:
        self._run_js("clearContour();")

    def _connect_ready(self):
        """The page restarts when the 3D view reloads: draw the contour again then."""
        embed = self._embed()
        if embed is not None and not getattr(self, "_ready_connected", False):
            embed.ready.connect(lambda *_: self.show_in_3d(fly=False, switch=False) if self.rows else None)
            self._ready_connected = True

    # ------------------------------------------------------------ exports
    def _default_dir(self) -> str:
        return os.environ.get("SHARC_SCREENSHOT_DIR") or os.path.join(os.path.expanduser("~"), "Pictures", "SHARC")

    def export_csv(self, path: Optional[str] = None) -> str:
        if not self.rows:
            return ""
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Export contour (CSV)", os.path.join(self._default_dir(), "contour.csv"),
                                                  "CSV (*.csv)")
        if not path:
            return ""
        campaign.write_csv(self.rows, path)
        self.lbl_status.setText(f"Saved {path}")
        return path

    def export_figure(self, folder: Optional[str] = None) -> List[str]:
        """PNG (300 dpi), PDF and SVG of the contour map, for papers."""
        if not self.rows:
            return []
        if not isinstance(folder, str) or not folder:
            folder = QFileDialog.getExistingDirectory(self, "Folder for the contour figure", self._default_dir())
        if not folder:
            return []
        os.makedirs(folder, exist_ok=True)
        fig = self._contour_figure(self.rows, self.w["name"].text().strip() or "Station", width_in=7.0, dpi=300)
        paths = []
        for ext in ("png", "pdf", "svg"):
            path = os.path.join(folder, f"sharc_contour.{ext}")
            fig.savefig(path, dpi=300, facecolor="white", bbox_inches="tight", pad_inches=0.05)
            paths.append(path)
        self.lbl_status.setText(f"Saved {len(paths)} figure files in {folder}")
        return paths
