"""SHARC app icon and the subtle Cerrado / UnB background art.

The art is cartographic, not figurative: it is a quiet watermark meant to be found, not noticed. All colours
are flat (no gradients); each layer is rendered opaque and composed once with a single opacity.

  * Contour lines of a chapada (flat-topped plateau, dissected valleys) generated with marching squares.
  * The Plano Piloto of Brasilia (Lucio Costa's "airplane": Eixo Monumental + Eixo Rodoviario) and the
    Paranoa lake, drawn as fine lines.
  * A small naturalist's plate in the lower-left corner: ipe-amarelo, buriti, pequi and lobo-guara as tiny
    geometric glyphs with their scientific names, plus "UnB - Campus Darcy Ribeiro - 1962" and the default
    scenario coordinates.

    python -m ui.shell.app_art <out_dir>      # writes sharc.png / sharc.ico (run from sharc/gui)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

ACCENT = "#4F9DDE"
IPE = "#E8B931"          # ipe amarelo
PEQUI = "#C9A227"
BURITI = "#7FB069"


# --------------------------------------------------------------------------- icon
def _icon_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#121A28"))
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)
    cx, cy, r = s * 0.5, s * 0.52, s * 0.30
    hexa = QPolygonF([QPointF(cx + r * math.cos(math.pi / 3 * k + math.pi / 6),
                              cy + r * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)])
    p.setPen(QPen(QColor(ACCENT), max(1.0, s * 0.045), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor("#17314D"))
    p.drawPolygon(hexa)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#EAF1FA"))
    p.drawEllipse(QPointF(cx, cy), s * 0.05, s * 0.05)
    p.setBrush(Qt.NoBrush)
    for a in (0.13, 0.20):
        p.setPen(QPen(QColor(ACCENT), max(1.0, s * 0.035), Qt.SolidLine, Qt.RoundCap))
        rect = QRectF(cx - s * a, cy - s * a, 2 * s * a, 2 * s * a)
        p.drawArc(rect, 30 * 16, 60 * 16)
        p.drawArc(rect, 210 * 16, 60 * 16)
    p.setPen(QPen(QColor(111, 178, 234, 150), max(1.0, s * 0.022)))
    p.save()
    p.translate(cx, cy)
    p.rotate(-24)
    p.drawEllipse(QPointF(0, 0), s * 0.43, s * 0.15)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(QPointF(s * 0.43 * math.cos(0.9), s * 0.15 * math.sin(0.9)), s * 0.045, s * 0.045)
    p.restore()
    p.setBrush(QColor(IPE))                              # ipe-yellow dot: Cerrado easter egg
    p.drawEllipse(QPointF(s * 0.80, s * 0.84), s * 0.045, s * 0.045)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_icon_pixmap(sz))
    return icon


def export_icon(out_dir: str | Path) -> list[Path]:
    """Write sharc.png (256) and sharc.ico for packaging."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    png, ico = out / "sharc.png", out / "sharc.ico"
    _icon_pixmap(256).save(str(png), "PNG")
    _icon_pixmap(256).save(str(ico), "ICO")
    return [png, ico]


# --------------------------------------------------------------------------- contour lines (marching squares)
NX, NY, LEVELS = 150, 46, 15
_SEGMENTS: list[tuple[float, float, float, float]] | None = None


def _terrain() -> np.ndarray:
    """Synthetic chapada: a flat-topped plateau (tanh-saturated bump), side hills and a dissected relief."""
    xs, ys = np.linspace(0, 1, NX), np.linspace(0, 1, NY)
    X, Y = np.meshgrid(xs, ys)

    def bump(cx, cy, sx, sy, a):
        return a * np.exp(-(((X - cx) / sx) ** 2 + ((Y - cy) / sy) ** 2))

    plateau = np.tanh(2.6 * bump(0.70, 0.62, 0.17, 0.42, 1.0))           # steep escarpment, flat top
    f = plateau + bump(0.38, 0.78, 0.10, 0.30, 0.42) + bump(0.93, 0.35, 0.09, 0.30, 0.36) + bump(0.15, 0.85, 0.13, 0.25, 0.22)
    f += 0.035 * np.sin(X * 19 + Y * 6) + 0.025 * np.sin(X * 9 - Y * 15 + 1.3) + 0.02 * np.sin(X * 31 + 2.1)
    return f


def _contours() -> list[tuple[float, float, float, float]]:
    """Iso-line segments in unit coordinates (computed once and cached)."""
    global _SEGMENTS
    if _SEGMENTS is not None:
        return _SEGMENTS
    f = _terrain()
    a, b, c, d = f[:-1, :-1], f[:-1, 1:], f[1:, 1:], f[1:, :-1]            # tl, tr, br, bl
    segs: list[tuple[float, float, float, float]] = []

    def lerp(t, v0, v1):
        return 0.5 if v1 == v0 else (t - v0) / (v1 - v0)

    for t in np.linspace(f.min() + 0.06, f.max() - 0.03, LEVELS):
        idx = (a > t) * 8 + (b > t) * 4 + (c > t) * 2 + (d > t) * 1
        for j, i in zip(*np.nonzero((idx > 0) & (idx < 15))):
            va, vb, vc, vd = a[j, i], b[j, i], c[j, i], d[j, i]
            top = (i + lerp(t, va, vb), j)
            right = (i + 1, j + lerp(t, vb, vc))
            bottom = (i + lerp(t, vd, vc), j + 1)
            left = (i, j + lerp(t, va, vd))
            k = int(idx[j, i])
            pairs = {1: [(left, bottom)], 2: [(bottom, right)], 3: [(left, right)], 4: [(top, right)],
                     5: [(top, left), (bottom, right)], 6: [(top, bottom)], 7: [(top, left)], 8: [(top, left)],
                     9: [(top, bottom)], 10: [(top, right), (left, bottom)], 11: [(top, right)], 12: [(left, right)],
                     13: [(bottom, right)], 14: [(left, bottom)]}[k]
            for (x0, y0), (x1, y1) in pairs:
                segs.append((x0 / (NX - 1), y0 / (NY - 1), x1 / (NX - 1), y1 / (NY - 1)))
    _SEGMENTS = segs
    return segs


# --------------------------------------------------------------------------- the layers
def _plano_piloto(p: QPainter, cx: float, cy: float, s: float) -> None:
    """Lucio Costa's Plano Piloto: Eixo Monumental (fuselage) crossed by the curved Eixo Rodoviario (wings)."""
    p.save()
    p.translate(cx, cy)
    p.rotate(-8)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(Qt.white, 1.3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(-s * 1.05, 0), QPointF(s * 0.95, 0))                          # Eixo Monumental
    wings = QPainterPath(QPointF(-s * 0.12, -s * 0.92))
    wings.cubicTo(QPointF(s * 0.34, -s * 0.5), QPointF(s * 0.34, s * 0.5), QPointF(-s * 0.12, s * 0.92))
    p.drawPath(wings)                                                                  # Eixo Rodoviario
    p.setBrush(Qt.white)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(0.06 * s, 0), s * 0.022, s * 0.022)                         # Rodoviaria
    p.drawPolygon(QPolygonF([QPointF(s * 0.95, 0), QPointF(s * 0.88, -s * 0.045), QPointF(s * 0.88, s * 0.045)]))  # 3 Poderes
    p.restore()


def _lake(p: QPainter, cx: float, cy: float, s: float) -> None:
    """Lago Paranoa: a wide sinuous band around the east of the Plano Piloto."""
    path = QPainterPath(QPointF(cx + s * 0.45, cy - s * 1.05))
    path.cubicTo(QPointF(cx + s * 1.25, cy - s * 0.85), QPointF(cx + s * 1.55, cy - s * 0.1), QPointF(cx + s * 1.05, cy + s * 0.35))
    path.cubicTo(QPointF(cx + s * 0.85, cy + s * 0.55), QPointF(cx + s * 0.95, cy + s * 0.85), QPointF(cx + s * 0.6, cy + s * 1.1))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(Qt.white, max(2.0, s * 0.04), Qt.SolidLine, Qt.RoundCap))
    p.drawPath(path)


def _glyph_ipe(p: QPainter, x: float, y: float, r: float) -> None:
    """Ipe flower: five rounded petals around a centre."""
    p.save()
    p.translate(x, y)
    for k in range(5):
        p.save()
        p.rotate(k * 72)
        p.drawEllipse(QPointF(0, -r * 0.55), r * 0.36, r * 0.52)
        p.restore()
    p.restore()


def _glyph_buriti(p: QPainter, x: float, y: float, r: float) -> None:
    """Buriti: fan of fronds on a slender trunk."""
    p.save()
    p.setPen(QPen(p.brush().color(), max(1.0, r * 0.11), Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(x, y + r), QPointF(x, y - r * 0.2))
    for ang in range(-75, 76, 25):
        a = math.radians(ang)
        path = QPainterPath(QPointF(x, y - r * 0.2))
        path.quadTo(QPointF(x + math.sin(a) * r * 0.5, y - r * 0.2 - math.cos(a) * r * 0.75),
                    QPointF(x + math.sin(a) * r * 0.95, y - r * 0.05 - math.cos(a) * r * 0.35 + abs(math.sin(a)) * r * 0.3))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    p.restore()


def _glyph_pequi(p: QPainter, x: float, y: float, r: float) -> None:
    """Pequi: round fruit with its lobed segments and a leaf."""
    p.save()
    p.drawEllipse(QPointF(x, y + r * 0.1), r * 0.78, r * 0.72)
    p.restore()
    leaf = QPainterPath(QPointF(x + r * 0.05, y - r * 0.6))
    leaf.quadTo(QPointF(x + r * 0.2, y - r * 1.05), QPointF(x + r * 0.7, y - r * 1.0))
    leaf.quadTo(QPointF(x + r * 0.5, y - r * 0.6), QPointF(x + r * 0.05, y - r * 0.6))
    p.drawPath(leaf)


def _glyph_wolf(p: QPainter, x: float, y: float, r: float) -> None:
    """Lobo-guara head, frontal: two very tall ears and a narrow muzzle."""
    ears = [QPolygonF([QPointF(x - r * 0.62, y - r * 0.1), QPointF(x - r * 0.46, y - r * 1.12), QPointF(x - r * 0.08, y - r * 0.32)]),
            QPolygonF([QPointF(x + r * 0.62, y - r * 0.1), QPointF(x + r * 0.46, y - r * 1.12), QPointF(x + r * 0.08, y - r * 0.32)])]
    for e in ears:
        p.drawPolygon(e)
    face = QPolygonF([QPointF(x - r * 0.62, y - r * 0.12), QPointF(x + r * 0.62, y - r * 0.12),
                      QPointF(x + r * 0.2, y + r * 0.62), QPointF(x, y + r * 0.95), QPointF(x - r * 0.2, y + r * 0.62)])
    p.drawPolygon(face)


def _glyph_unb(p: QPainter, x: float, y: float, r: float) -> None:
    """The Minhocao: a row of piers under a slab."""
    p.drawRect(QRectF(x - r, y - r * 0.55, 2 * r, r * 0.16))
    for k in range(9):
        p.drawRect(QRectF(x - r + k * (2 * r / 9) + r * 0.04, y - r * 0.35, r * 0.1, r * 0.85))


PLATE = (("Handroanthus albus", "ipê-amarelo", _glyph_ipe, IPE),
         ("Mauritia flexuosa", "buriti", _glyph_buriti, BURITI),
         ("Caryocar brasiliense", "pequi", _glyph_pequi, PEQUI),
         ("Chrysocyon brachyurus", "lobo-guará", _glyph_wolf, None))


VW, VH = 1000.0, 300.0      # virtual canvas the contour field and the Plano Piloto are laid out on


def _cover(w: float, h: float) -> tuple[float, float, float]:
    """Uniform scale that covers (w, h) with the virtual canvas, anchored bottom-right: (scale, x0, y0)."""
    k = max(w / VW, h / VH)
    return k, w - VW * k, h - VH * k


def _plan_frame(w: float, h: float) -> tuple[float, float, float]:
    """Centre and size of the Plano Piloto, kept fully inside the frame even on short, wide docks."""
    k, ox, oy = _cover(w, h)
    sp = min(100 * k, h * 0.40)
    cy = min(max(oy + 0.40 * VH * k, sp * 1.05 + 4), h - sp * 1.05 - 4)
    return ox + 0.31 * VW * k, cy, sp


def _draw(p: QPainter, tier: str, w: float, h: float) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(Qt.white)
    if tier == "contours":
        pen = QPen(Qt.white, 1.0)
        pen.setCosmetic(True)
        p.setPen(pen)
        k, ox, oy = _cover(w, h)                      # uniform scale: crop, never stretch
        p.drawLines([QLineF(ox + x0 * VW * k, oy + y0 * VH * k, ox + x1 * VW * k, oy + y1 * VH * k)
                     for x0, y0, x1, y1 in _contours()])
    elif tier == "plan":
        cx, cy, sp = _plan_frame(w, h)
        _plano_piloto(p, cx, cy, sp)
    elif tier == "lake":
        cx, cy, sp = _plan_frame(w, h)
        _lake(p, cx, cy, sp)
    elif tier == "text":
        f = QFont("Segoe UI", 7)
        f.setItalic(True)
        p.setFont(f)
        p.setPen(Qt.white)
        gx, gy = 22.0, h - 22.0
        for i, (latin, common, _glyph, _col) in enumerate(PLATE):
            p.drawText(QPointF(gx + 30, gy - 78 + i * 16 + 4), f"{latin}  ·  {common}")
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QPointF(gx + 30, gy + 6), "UnB  ·  Campus Darcy Ribeiro  ·  1962")
        p.drawText(QPointF(w - 150, h - 14), "-15.79, -47.88  ·  Cerrado")
    elif tier == "glyphs":                                         # monochrome glyphs (the wolf, the Minhocao)
        gx, gy = 22.0, h - 22.0
        p.setBrush(Qt.white)
        _glyph_wolf(p, gx + 12, gy - 78 + 3 * 16, 6.0)
        _glyph_unb(p, gx + 12, gy + 2, 6.0)
    else:                                                          # accent: coloured glyphs
        gx, gy = 22.0, h - 22.0
        for i, (_latin, _common, glyph, col) in enumerate(PLATE):
            if col is None:
                continue
            p.setBrush(QColor(col))
            p.setPen(Qt.NoPen)
            glyph(p, gx + 12, gy - 78 + i * 16, 6.0)


_TIERS = (("contours", 2.3), ("lake", 1.1), ("plan", 2.4), ("text", 3.0), ("glyphs", 3.2), ("accent", 4.5))


def _layer(w: int, h: int, tier: str, tint: QColor) -> QImage:
    """Opaque flat-colour layer: overlaps stay one solid colour; opacity is applied once on compose."""
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    lp = QPainter(img)
    lp.setRenderHint(QPainter.Antialiasing)
    _draw(lp, tier, float(w), float(h))
    if tier != "accent":
        lp.setCompositionMode(QPainter.CompositionMode_SourceIn)
        lp.fillRect(img.rect(), QColor(tint.red(), tint.green(), tint.blue(), 255))
    lp.end()
    return img


def render_art(w: int, h: int, shade: QColor) -> QImage:
    """The finished watermark as a transparent image (flat colours, subtle)."""
    out = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p = QPainter(out)
    for tier, boost in _TIERS:
        p.setOpacity(min(1.0, shade.alpha() / 255.0 * boost))
        p.drawImage(0, 0, _layer(w, h, tier, shade))
    p.end()
    return out


def paint_cerrado_art(p: QPainter, rect: QRectF, shade: QColor) -> None:
    w, h = int(rect.width()), int(rect.height())
    if w < 220 or h < 90:
        return
    p.drawImage(rect.topLeft(), render_art(w, h, shade))


class _Backdrop(QWidget):
    """Transparent overlay that paints the art over its parent; clicks go through. The image is cached per size."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._cache: tuple[tuple, QImage] | None = None
        parent.installEventFilter(self)
        self._fit()

    def _fit(self):
        self.setGeometry(self.parentWidget().rect())
        self.raise_()

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802
        if ev.type() in (QEvent.Resize, QEvent.Show):
            self._fit()
        return False

    def paintEvent(self, _ev):  # noqa: N802
        base = self.parentWidget().palette().base().color()
        shade = QColor(190, 205, 225, 14) if base.lightness() < 128 else QColor(40, 55, 80, 16)
        w, h = self.width(), self.height()
        if w < 220 or h < 90:
            return
        key = (w, h, shade.rgba())
        if self._cache is None or self._cache[0] != key:
            self._cache = (key, render_art(w, h, shade))
        p = QPainter(self)
        p.drawImage(0, 0, self._cache[1])
        p.end()


def attach_backdrop(widget: QWidget) -> QWidget:
    """Attach the art to a scrollable widget's viewport (or to the widget itself)."""
    host = widget.viewport() if hasattr(widget, "viewport") else widget
    backdrop = _Backdrop(host)
    backdrop.show()
    return backdrop


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    for path in export_icon(sys.argv[1] if len(sys.argv) > 1 else "."):
        print("wrote", path)
