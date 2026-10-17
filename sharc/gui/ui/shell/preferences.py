"""Preferences window (Settings > Preferences, Ctrl+,): categories on the left, options on the right.

Pages: Appearance, Map & Terrain, Simulation, Notifications & Tray, Data & Cache, Advanced.
Map options are bound to the same variables as the Terrain & Clutter page, so both always agree.
Everything is remembered between sessions.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSettings, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from ui.tabs import terrain as terrain_mod

THEMES = {"Graphite (dark)": "graphite", "Light": "light"}


def settings() -> QSettings:
    return QSettings("SHARC", "GUI")


def _flag(value, default=True) -> bool:
    return default if value is None else str(value).lower() in ("true", "1", "yes")


def folder_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return ""


class PreferencesDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Preferences")
        self.resize(820, 560)
        outer = QHBoxLayout(self)
        self.nav = QListWidget()
        self.nav.setFixedWidth(190)
        self.stack = QStackedWidget()
        outer.addWidget(self.nav)
        outer.addWidget(self.stack, 1)
        for title, builder in (
            ("Appearance", self._page_appearance), ("Map & Terrain", self._page_map),
            ("Simulation", self._page_simulation), ("Notifications & Tray", self._page_tray),
            ("Data & Cache", self._page_data), ("Advanced", self._page_advanced),
        ):
            self.nav.addItem(title)
            self.stack.addWidget(builder())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

    # --------------------------------------------------------------- helpers
    def _page(self, title: str):
        w = QWidget()
        lay = QVBoxLayout(w)
        head = QLabel(title)
        head.setObjectName("DocTitle")
        lay.addWidget(head)
        return w, lay

    def _bind_combo(self, key: str, choices) -> QComboBox:
        var = self.win.tab_terrain.state.get(key)
        cb = QComboBox()
        cb.addItems([str(c) for c in choices])
        cb.setCurrentText(str(var.get()))
        cb.currentTextChanged.connect(var.set)
        var.value_changed.connect(lambda v, cb=cb: cb.setCurrentText(str(v)) if cb.currentText() != str(v) else None)
        return cb

    def _bind_check(self, key: str, text: str) -> QCheckBox:
        var = self.win.tab_terrain.state.get(key)
        c = QCheckBox(text)
        c.setChecked(_flag(var.get()))
        c.toggled.connect(var.set)
        var.value_changed.connect(lambda v, c=c: c.setChecked(_flag(v)) if c.isChecked() != _flag(v) else None)
        return c

    # ----------------------------------------------------------------- pages
    def _page_appearance(self):
        w, lay = self._page("Appearance")
        form = QFormLayout()
        theme = QComboBox()
        theme.addItems(list(THEMES))
        cur = getattr(self.win, "_current_theme", "graphite")
        theme.setCurrentText(next((k for k, v in THEMES.items() if v == cur), "Graphite (dark)"))
        theme.currentTextChanged.connect(lambda t: self.win._apply_theme(THEMES[t]))
        form.addRow("Theme", theme)
        size = QSpinBox()
        size.setRange(8, 14)
        size.setSuffix(" pt")
        size.setValue(int(settings().value("appearance/font_pt", 10)))
        size.valueChanged.connect(self._set_font_size)
        form.addRow("Interface font size", size)
        lay.addLayout(form)
        lay.addStretch(1)
        return w

    def _set_font_size(self, pt: int) -> None:
        settings().setValue("appearance/font_pt", pt)
        QApplication.instance().setFont(QFont("Segoe UI", pt))

    def _page_map(self):
        w, lay = self._page("Map & Terrain")
        g = QGroupBox("Layers")
        gl = QVBoxLayout(g)
        for key, text in (("terr_stream", "Stream terrain and land cover on demand"),
                          ("terr_show_relief", "3D relief"), ("terr_show_clutter", "Land cover (ESA WorldCover)"),
                          ("terr_show_hillshade", "Hillshade"), ("terr_show_hydro", "Lakes and rivers"),
                          ("terr_show_buildings", "Buildings (OpenStreetMap)"),
                          ("terr_check_water", "Warn if a base station is on water")):
            gl.addWidget(self._bind_check(key, text))
        lay.addWidget(g)
        d = QGroupBox("Detail and performance")
        form = QFormLayout(d)
        T = terrain_mod
        form.addRow("Base map", self._bind_combo("terr_basemap", list(T.BASEMAPS)))
        form.addRow("Map quality", self._bind_combo("terr_quality", list(T.QUALITY)))
        form.addRow("Relief resolution", self._bind_combo("terr_relief_res", list(T.RELIEF_RES)))
        form.addRow("Maximum tile detail level", self._bind_combo("terr_max_level", T.MAX_LEVELS))
        form.addRow("Render resolution", self._bind_combo("terr_render_scale", list(T.RENDER_SCALES)))
        form.addRow("Building limit", self._bind_combo("terr_bld_limit", T.BUILDING_LIMITS))
        form.addRow("Show buildings when closer than", self._bind_combo("terr_bld_distance", list(T.BUILDING_DISTANCES)))
        form.addRow("Hide buildings lower than [m]", self._bind_combo("terr_bld_min_height", T.BUILDING_MIN_HEIGHT))
        lay.addWidget(d)
        lay.addStretch(1)
        return w

    def _page_simulation(self):
        w, lay = self._page("Simulation")
        form = QFormLayout()
        par = QSpinBox()
        par.setRange(1, 64)
        par.setValue(self.win.scheduler.max_parallel if getattr(self.win, "scheduler", None) else 2)
        par.valueChanged.connect(self._set_parallel)
        form.addRow("Simulations running in parallel", par)
        open_jobs = QCheckBox("Show the Jobs panel when a run starts")
        open_jobs.setChecked(_flag(settings().value("sim/show_jobs", True)))
        open_jobs.toggled.connect(lambda on: settings().setValue("sim/show_jobs", on))
        form.addRow(open_jobs)
        lay.addLayout(form)
        from core.run_service import run_root
        row = QHBoxLayout()
        row.addWidget(QLabel(f"Run folder: {run_root()}"))
        b = QPushButton("Open")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(run_root()))))
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _set_parallel(self, n: int) -> None:
        settings().setValue("sim/parallel", n)
        sched = getattr(self.win, "scheduler", None)
        if sched is not None:
            sched.set_max_parallel(n)
            self.win.jobs_panel.spin.setValue(n)

    def _page_tray(self):
        from ui.shell.tray import TrayController
        w, lay = self._page("Notifications & Tray")
        keep = QCheckBox("Keep running in the system tray when the window is closed during a simulation")
        keep.setChecked(TrayController.keep_running_enabled())
        keep.toggled.connect(TrayController.set_keep_running)
        lay.addWidget(keep)
        fin = QCheckBox("Notify when background simulations finish")
        fin.setChecked(_flag(settings().value("tray/notify_finish", True)))
        fin.toggled.connect(lambda on: settings().setValue("tray/notify_finish", on))
        lay.addWidget(fin)
        lay.addWidget(QLabel("The tray icon shows the queue progress and lets you reopen, pause, stop or quit."))
        lay.addStretch(1)
        return w

    def _page_data(self):
        from core import terrain_service
        w, lay = self._page("Data & Cache")
        root = terrain_service.cache_root()
        lay.addWidget(QLabel(f"Cache folder: {root}"))
        self.lbl_size = QLabel("")
        lay.addWidget(self.lbl_size)
        for text, sub in (("Clear map tiles (elevation, hillshade, land cover)", "tiles"),
                          ("Clear buildings", "buildings"), ("Clear rivers and lakes", "hydro")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=sub: self._clear(root / s))
            lay.addWidget(b)
        o = QPushButton("Open cache folder")
        o.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(root))))
        lay.addWidget(o)
        self._root = root
        self._refresh_size()
        lay.addStretch(1)
        return w

    def _refresh_size(self) -> None:
        self.lbl_size.setText(f"Size on disk: {human(folder_size(self._root))}")

    def _clear(self, folder: Path) -> None:
        if QMessageBox.question(self, "Clear cache", f"Delete the cached data in\n{folder} ?\nIt is downloaded again when needed.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            shutil.rmtree(folder, ignore_errors=True)
            self._refresh_size()

    def _page_advanced(self):
        w, lay = self._page("Advanced")
        b1 = QPushButton("Reset window layout")
        b1.clicked.connect(self.win._reset_workbench_layout)
        lay.addWidget(b1)
        b2 = QPushButton("Reset all preferences to defaults")
        b2.clicked.connect(self._reset_all)
        lay.addWidget(b2)
        lay.addWidget(QLabel("Preferences are stored per user and apply to every project."))
        lay.addStretch(1)
        return w

    def _reset_all(self) -> None:
        if QMessageBox.question(self, "Reset preferences", "Restore every preference to its default?\nRestart SHARC to apply all of them.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            s = settings()
            for group in ("terrain", "tray", "appearance", "sim", "workbench"):
                s.remove(group)
            for k, v in terrain_mod.DEFAULTS.items():
                self.win.tab_terrain.state.get(k).set(v)


def open_preferences(win) -> None:
    PreferencesDialog(win).exec()


def apply_saved_appearance(win) -> None:
    """At start-up: restore font size and theme (called once the window exists)."""
    if os.environ.get("SHARC_GUI_NO_RESTORE"):
        return
    s = settings()
    pt = s.value("appearance/font_pt")
    if pt:
        QApplication.instance().setFont(QFont("Segoe UI", int(pt)))
    theme = s.value("appearance/theme")
    if theme in THEMES.values() and theme != getattr(win, "_current_theme", None):
        win._apply_theme(theme)
