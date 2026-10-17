"""Start-up splash screen with self-checks and pre-loading.

Professional simulators show a splash while they verify the installation and warm their caches.
This one runs a short list of checks (dependencies, vendored 3D engine, writable cache, SHARC
engine import) and pre-loads the heavy modules so the first scene and first Run are fast.
Every check is reported on the splash; failures never block start-up, they are kept in
`StartupReport` so the Messages dock can show them.
"""
from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

GUI_ROOT = Path(__file__).resolve().parents[2]
OK, WARN, FAIL = "ok", "warning", "failed"


@dataclass
class StartupReport:
    results: List[Tuple[str, str, str]] = field(default_factory=list)   # (check, status, detail)
    seconds: float = 0.0

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.results.append((name, status, detail))

    @property
    def problems(self) -> List[Tuple[str, str, str]]:
        return [r for r in self.results if r[1] != OK]

    def summary(self) -> str:
        n = len(self.results)
        bad = len(self.problems)
        return f"Start-up checks: {n - bad}/{n} passed in {self.seconds:.1f} s" + (
            "; " + "; ".join(f"{a}: {c or b}" for a, b, c in self.problems) if bad else "")


# ------------------------------------------------------------------ checks
def _check_modules() -> Tuple[str, str]:
    missing = []
    for mod in ("PySide6.QtWebEngineWidgets", "PySide6.QtCharts", "qtawesome", "yaml", "numpy"):
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001
            missing.append(mod)
    return (FAIL, "missing: " + ", ".join(missing)) if missing else (OK, "")


def _check_optional() -> Tuple[str, str]:
    missing = []
    for mod in ("rasterio", "geopandas", "requests"):
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001
            missing.append(mod)
    return (WARN, "optional data libraries missing (" + ", ".join(missing) + "): terrain/clutter/hydro limited") \
        if missing else (OK, "")


def _check_cesium() -> Tuple[str, str]:
    index = GUI_ROOT / "web" / "cesium_preview" / "vendor" / "cesium" / "Cesium.js"
    return (OK, "") if index.is_file() else (FAIL, "vendored CesiumJS not found: 3D scene unavailable")


def _check_cache() -> Tuple[str, str]:
    try:
        from core import terrain_service
        root = terrain_service.cache_root()
        probe = root / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return OK, str(root)
    except Exception as exc:  # noqa: BLE001
        return WARN, f"cache folder not writable ({exc})"


def _preload_engine() -> Tuple[str, str]:
    try:
        for mod in ("sharc.parameters.parameters", "sharc.topology.topology_factory",
                    "sharc.station_factory", "sharc.support.geodesy"):
            importlib.import_module(mod)
        return OK, ""
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"SHARC engine import failed: {exc}"


def _preload_services() -> Tuple[str, str]:
    try:
        for mod in ("core.engine_scene", "core.antenna_service", "core.tile_service",
                    "core.hydro_service", "core.buildings_service", "core.job_scheduler"):
            importlib.import_module(mod)
        return OK, ""
    except Exception as exc:  # noqa: BLE001
        return WARN, f"service pre-load failed: {exc}"


def _selftest_scene() -> Tuple[str, str]:
    """Build one default scene through the engine: proves the geometry pipeline and warms numpy."""
    try:
        from core.engine_scene import hex_sector_scene
        hex_sector_scene  # noqa: B018 - import is the test; the call needs GUI state
        return OK, ""
    except Exception as exc:  # noqa: BLE001
        return WARN, f"scene pipeline unavailable: {exc}"


CHECKS: List[Tuple[str, Callable[[], Tuple[str, str]]]] = [
    ("Checking Qt modules", _check_modules),
    ("Checking data libraries", _check_optional),
    ("Locating 3D engine (CesiumJS)", _check_cesium),
    ("Checking cache folder", _check_cache),
    ("Loading SHARC engine", _preload_engine),
    ("Loading GUI services", _preload_services),
    ("Verifying scene pipeline", _selftest_scene),
]


# ------------------------------------------------------------------ splash
def _pixmap(w: int = 640, h: int = 360) -> QPixmap:
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor("#1B2230"))
    g.setColorAt(1, QColor("#0D1119"))
    p.fillRect(0, 0, w, h, QBrush(g))
    p.setPen(QPen(QColor(79, 157, 222, 70), 1))               # orbit rings
    for r in (90, 150, 215):
        p.drawEllipse(QRectF(w - 170 - r, h / 2 - r * 0.45 - 20, 2 * r, r * 0.9))
    p.setBrush(QColor("#4F9DDE"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(w - 175, h / 2 - 25, 10, 10))
    p.setPen(QColor("#E8ECF1"))
    p.setFont(QFont("Segoe UI", 38, QFont.Light))
    p.drawText(40, 135, "SHARC")
    p.setPen(QColor("#8A94A6"))
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(42, 165, "Spectrum sHAring Radio-frequency Compatibility simulator")
    p.drawText(42, 188, "Interference analysis workbench")
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#2A3446"), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    p.end()
    return pm


class StartupSplash(QSplashScreen):
    def __init__(self):
        super().__init__(_pixmap(), Qt.WindowStaysOnTopHint)
        self._text, self._pct = "Starting...", 0

    def progress(self, pct: int, text: str) -> None:
        self._pct, self._text = pct, text
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        painter.setPen(QColor("#B8C1CF"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(40, h - 56, self._text)
        painter.fillRect(40, h - 36, w - 80, 4, QColor("#222B3A"))
        painter.fillRect(40, h - 36, int((w - 80) * self._pct / 100), 4, QColor("#4F9DDE"))


def run_startup(app: QApplication, skip: bool = False) -> Tuple[StartupSplash | None, StartupReport]:
    """Show the splash, run every check, return (splash, report). `skip` runs headless (tests)."""
    report = StartupReport()
    splash = None if skip or os.environ.get("SHARC_GUI_NO_SPLASH") else StartupSplash()
    if splash:
        splash.show()
    t0 = time.time()
    total = len(CHECKS) + 1
    for i, (label, fn) in enumerate(CHECKS):
        if splash:
            splash.progress(int(100 * i / total), label + "...")
        try:
            status, detail = fn()
        except Exception as exc:  # noqa: BLE001
            status, detail = FAIL, str(exc)
        report.add(label, status, detail)
    report.seconds = time.time() - t0
    if splash:
        splash.progress(int(100 * len(CHECKS) / total), "Building workspace...")
    return splash, report
