"""Colour-scale legend window for the 3D preview (antenna gain lobes, ground heat maps).

The 3D view reports which scales are on screen (`PyBridge.legend_changed`); this widget draws one vertical colour
bar per scale with its title, unit and values. It lives in a detached dock, so it never crowds the scene.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

# Same rainbow stops as core/gain_lobe.jet (antenna lobes; cold to hot)
STOPS = [(0.0, "#00007f"), (0.12, "#0000ff"), (0.37, "#00ffff"), (0.5, "#00ff00"), (0.63, "#ffff00"),
         (0.88, "#ff0000"), (1.0, "#7f0000")]
# Items from the 3D view may carry their own `stops` ([[position 0..1, '#rrggbb'], ...]), e.g. the heat map in the
# palette the user chose (View panel > Heat map); the others use the rainbow above.
COL_W, BAR_W, BAR_H, PAD = 168, 18, 190, 14


class LegendPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LegendPanel")
        self._items: List[Dict[str, Any]] = []
        self.setMinimumSize(COL_W, BAR_H + 96)

    # ------------------------------------------------------------------ data
    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self._items = [i for i in items if i.get("vmax") is not None and i.get("vmin") is not None]
        self.setMinimumSize(max(1, len(self._items)) * COL_W, BAR_H + 96)
        self.updateGeometry()
        self.update()

    def set_payload(self, payload: str) -> None:
        """Accepts the JSON the 3D view sends; malformed input just clears the legend."""
        try:
            items = json.loads(payload)
        except (TypeError, ValueError):
            items = []
        self.set_items(items if isinstance(items, list) else [])

    @property
    def items(self) -> List[Dict[str, Any]]:
        return list(self._items)

    def sizeHint(self):  # noqa: N802
        from PySide6.QtCore import QSize
        return QSize(max(1, len(self._items)) * COL_W, BAR_H + 96)

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _ev):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1B1D20"))                  # dark like the 3D HUD, independent of the theme
        text = QColor("#D6D9DD")
        muted = QColor(text)
        muted.setAlpha(170)
        for k, item in enumerate(self._items):
            x0 = k * COL_W + PAD
            p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            p.setPen(text)
            p.drawText(QRectF(x0, 8, COL_W - 2 * PAD + 8, 32), Qt.AlignLeft | Qt.TextWordWrap, item.get("title", ""))
            p.setFont(QFont("Segoe UI", 8))
            p.setPen(muted)
            p.drawText(QPointF(x0, 54), f"[{item.get('unit', '')}]")
            top = 64.0
            bar = QRectF(x0, top, BAR_W, BAR_H)
            grad = QLinearGradient(0, bar.bottom(), 0, bar.top())
            stops = [(float(p), c) for p, c in item["stops"]] if item.get("stops") else STOPS
            for pos, col in stops:
                grad.setColorAt(pos, QColor(col))
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.drawRoundedRect(bar, 3, 3)
            vmin, vmax = float(item["vmin"]), float(item["vmax"])
            p.setPen(QPen(text, 1))
            p.setFont(QFont("Segoe UI", 9))
            for frac in (1.0, 0.75, 0.5, 0.25, 0.0):
                y = bar.bottom() - frac * BAR_H
                p.setPen(QPen(muted, 1))
                p.drawLine(QPointF(bar.right(), y), QPointF(bar.right() + 5, y))
                p.setPen(text)
                label = f"{vmin + frac * (vmax - vmin):.0f}"
                p.drawText(QRectF(bar.right() + 8, y - 8, 60, 16), Qt.AlignLeft | Qt.AlignVCenter, label)
        if not self._items:
            p.setPen(QColor("#6E747B"))
            p.drawText(self.rect(), Qt.AlignCenter, "No colour scale on screen")
        p.end()
