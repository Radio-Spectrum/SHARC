"""Start-up splash screen with self-checks and pre-loading.

Professional simulators show a splash while they verify the installation and warm their caches.
This one runs a short list of checks (dependencies, vendored 3D engine, writable cache, SHARC
engine import) and pre-loads the heavy modules so the first scene and first Run are fast.
Every check is reported on the splash; failures never block start-up, they are kept in
`StartupReport` so the Messages dock can show them.
"""
from __future__ import annotations

import importlib
import math
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QRadialGradient)
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
W, H = 900, 520
ACCENT = QColor("#4F9DDE")
_STATUS_COLOR = {OK: "#5DB36A", WARN: "#D9A23B", FAIL: "#E0605A"}          # drawn as small dots, no glyphs


def _stars(n: int = 140):
    """Deterministic starfield: (x, y, radius, base alpha, twinkle phase)."""
    rng = random.Random(7)
    return [(rng.uniform(0, W), rng.uniform(0, H), rng.choice((0.6, 0.8, 1.1, 1.5)),
             rng.uniform(60, 200), rng.uniform(0, 6.28)) for _ in range(n)]


def _hexagon(cx: float, cy: float, r: float) -> QPolygonF:
    return QPolygonF([QPointF(cx + r * math.cos(math.pi / 3 * k + math.pi / 6),
                              cy + r * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)])


class StartupSplash(QSplashScreen):
    """Animated, fully painted splash: night-side Earth, orbits, cell grid, live check list."""

    def __init__(self):
        pm = QPixmap(W, H)
        pm.fill(Qt.transparent)
        super().__init__(pm, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._text, self._pct, self._shown = "Starting...", 0, 0.0
        self._log: List[Tuple[str, str]] = []
        self._stars = _stars()
        self._t0 = time.time()

    # -- API used by run_startup
    def progress(self, pct: int, text: str) -> None:
        self._pct, self._text = pct, text
        self.animate(0.0)

    def mark(self, label: str, status: str) -> None:
        self._log.append((label, status))
        self.animate(0.12)

    def animate(self, seconds: float) -> None:
        """Repaint for `seconds` (keeps the animation alive while start-up work blocks the loop)."""
        end = time.time() + seconds
        while True:
            self._shown += (self._pct - self._shown) * 0.25          # eased progress bar
            self.repaint()
            QApplication.processEvents()
            if time.time() >= end:
                break
            time.sleep(0.016)

    # -- painting
    def drawContents(self, p: QPainter) -> None:
        t = time.time() - self._t0
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, W, H), 14, 14)
        p.setClipPath(clip)
        self._paint_space(p, t)
        self._paint_earth(p, t)
        self._paint_cells(p, t)
        self._paint_orbits(p, t)
        self._paint_title(p)
        self._paint_checks(p, t)
        p.setClipping(False)
        p.setPen(QPen(QColor(79, 157, 222, 90), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.6, 0.6, W - 1.2, H - 1.2), 14, 14)

    def _paint_space(self, p: QPainter, t: float) -> None:
        g = QLinearGradient(0, 0, W, H)
        g.setColorAt(0, QColor("#0A0F1A"))
        g.setColorAt(0.55, QColor("#0D1420"))
        g.setColorAt(1, QColor("#101A2C"))
        p.fillRect(0, 0, W, H, QBrush(g))
        p.setPen(Qt.NoPen)
        for x, y, r, a, ph in self._stars:
            alpha = int(a * (0.65 + 0.35 * math.sin(t * 1.6 + ph)))
            p.setBrush(QColor(210, 225, 255, max(20, min(255, alpha))))
            p.drawEllipse(QPointF(x, y), r, r)

    def _paint_earth(self, p: QPainter, t: float) -> None:
        cx, cy, r = W * 0.80, H * 1.18, 330
        glow = QRadialGradient(cx, cy, r * 1.25)
        glow.setColorAt(0.74, QColor(79, 157, 222, 0))
        glow.setColorAt(0.80, QColor(79, 157, 222, 120))
        glow.setColorAt(1.0, QColor(79, 157, 222, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, cy), r * 1.25, r * 1.25)
        body = QRadialGradient(cx - r * 0.25, cy - r * 0.45, r * 1.1)
        body.setColorAt(0, QColor("#16304F"))
        body.setColorAt(0.6, QColor("#0B1B30"))
        body.setColorAt(1, QColor("#060C16"))
        p.setBrush(QBrush(body))
        p.setPen(QPen(QColor(120, 190, 255, 170), 1.6))
        p.drawEllipse(QPointF(cx, cy), r, r)
        # city lights on the night side
        rng = random.Random(11)
        p.setPen(Qt.NoPen)
        for _ in range(70):
            a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
            d = r * math.sqrt(rng.uniform(0.15, 0.97))
            x, y = cx + d * math.cos(a), cy + d * math.sin(a)
            if 0 < y < H and 0 < x < W:
                tw = 0.6 + 0.4 * math.sin(t * 2 + x)
                p.setBrush(QColor(255, 200, 120, int(150 * tw)))
                p.drawEllipse(QPointF(x, y), 1.3, 1.3)

    def _paint_cells(self, p: QPainter, t: float) -> None:
        """Hexagonal cell grid fading in from the lower right, like an IMT macro layout."""
        r = 24.0
        dx, dy = r * math.sqrt(3), r * 1.5
        cx0, cy0 = W * 0.80, H * 0.86
        for row in range(-3, 4):
            for col in range(-5, 6):
                x = cx0 + col * dx + (row % 2) * dx / 2
                y = cy0 + row * dy
                dist = math.hypot(x - cx0, y - cy0)
                fade = max(0.0, 1 - dist / 260)
                pulse = 0.5 + 0.5 * math.sin(t * 1.4 - dist / 40)
                if fade <= 0:
                    continue
                p.setBrush(QColor(79, 157, 222, int(40 * fade * pulse)))
                p.setPen(QPen(QColor(79, 157, 222, int(120 * fade)), 0.9))
                p.drawPolygon(_hexagon(x, y, r - 1.5))

    def _paint_orbits(self, p: QPainter, t: float) -> None:
        cx, cy = W * 0.80, H * 0.80
        p.setBrush(Qt.NoBrush)
        for i, (rx, ry, tilt, speed) in enumerate(((150, 52, -24, 0.55), (225, 78, -24, -0.38), (310, 112, -24, 0.25))):
            p.save()
            p.translate(cx, cy)
            p.rotate(tilt)
            p.setPen(QPen(QColor(79, 157, 222, 70 - i * 12), 1))
            p.drawEllipse(QPointF(0, 0), rx, ry)
            a = t * speed + i * 2.1
            sx, sy = rx * math.cos(a), ry * math.sin(a)
            halo = QRadialGradient(sx, sy, 14)
            halo.setColorAt(0, QColor(255, 255, 255, 230))
            halo.setColorAt(0.25, QColor(111, 190, 255, 150))
            halo.setColorAt(1, QColor(79, 157, 222, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(sx, sy), 14, 14)
            p.restore()

    def _paint_title(self, p: QPainter) -> None:
        f = QFont("Segoe UI", 58, QFont.Light)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 14)
        p.setFont(f)
        p.setPen(QColor("#EAF1FA"))
        p.drawText(48, 150, "SHARC")
        bar = QLinearGradient(52, 0, 360, 0)
        bar.setColorAt(0, ACCENT)
        bar.setColorAt(1, QColor(79, 157, 222, 0))
        p.fillRect(QRectF(52, 168, 308, 3), QBrush(bar))
        p.setFont(QFont("Segoe UI", 12))
        p.setPen(QColor("#A9B6C9"))
        p.drawText(52, 202, "Spectrum sHAring Radio-frequency Compatibility")
        p.setPen(QColor("#7F8DA3"))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(52, 224, "Monte Carlo interference analysis workbench")

    def _paint_checks(self, p: QPainter, t: float) -> None:
        y0 = 268
        p.setFont(QFont("Segoe UI", 10))
        for i, (label, status) in enumerate(self._log[-7:]):
            color = _STATUS_COLOR.get(status, "#5DB36A")
            y = y0 + i * 21
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(56, y - 4), 3.2, 3.2)
            p.setPen(QColor("#9AA7BA" if status == OK else "#E3C27A" if status == WARN else "#F0908C"))
            p.drawText(74, y, label)
        by = H - 52
        p.setPen(QColor("#C5D0E0"))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(52, by - 14, self._text)
        track = QRectF(52, by, W - 104, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1B2638"))
        p.drawRoundedRect(track, 2.5, 2.5)
        fill = QRectF(track.x(), track.y(), track.width() * max(0.0, min(100.0, self._shown)) / 100, track.height())
        if fill.width() > 1:
            bar = QLinearGradient(fill.left(), 0, fill.right(), 0)
            bar.setColorAt(0, QColor("#2F6FA6"))
            bar.setColorAt(1, QColor("#6DB2EA"))
            p.setBrush(QBrush(bar))
            p.drawRoundedRect(fill, 2.5, 2.5)
            shimmer = (t * 0.9) % 1.0
            sx = fill.left() + fill.width() * shimmer
            sg = QRadialGradient(sx, fill.center().y(), 26)
            sg.setColorAt(0, QColor(255, 255, 255, 120))
            sg.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(sg))
            p.drawRoundedRect(fill, 2.5, 2.5)
        p.setPen(QColor("#6E7B90"))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(W - 152, by - 22, 100, 16), Qt.AlignRight, f"{int(self._shown)} %")


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
        if splash:
            splash.mark(label, status)
    report.seconds = time.time() - t0
    if splash:
        splash.progress(int(100 * len(CHECKS) / total), "Building workspace...")
    return splash, report
