"""Panels that accompany the 3D preview: the link budget of the clicked UE link, and the PSD / CDF plots.

Both are fed with JSON by the 3D view (`PyBridge.link_selected`, `PyBridge.plots_changed`) and live in docks of the
workbench, so they stay readable next to the scene instead of crowding it.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

BG, FG, MUTED, GRID = QColor("#1B1D20"), QColor("#D6D9DD"), QColor("#8A9098"), QColor("#33373D")
ACCENT, WARN = QColor("#4F9DDE"), QColor("#E8B931")


def _loads(payload: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class LinkBudgetPanel(QWidget):
    """Link budget of one UE <- base-station link, as a table."""

    ROWS = [("Distance", "dist_m", "m", "{:.0f}"), ("Frequency", "freq_mhz", "MHz", "{:.0f}"),
            ("Bandwidth", "bandwidth_mhz", "MHz", "{:.0f}"),
            ("Tx power (after ohmic loss)", "tx_power_dbm", "dBm", "{:+.1f}"),
            ("Tx antenna gain toward the UE", "g_tx_dbi", "dBi", "{:+.1f}"),
            ("Free-space path loss", "fspl_db", "dB", "-{:.1f}"),
            ("UE antenna gain", "g_rx_dbi", "dBi", "{:+.1f}"), ("Body loss", "body_loss_db", "dB", "-{:.1f}"),
            ("Received power", "rx_power_dbm", "dBm", "{:+.1f}"),
            ("Noise (kTB + NF)", "noise_dbm", "dBm", "{:+.1f}"), ("SNR", "snr_db", "dB", "{:+.1f}")]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        self.title = QLabel("Click a UE link in the 3D scene")
        self.title.setStyleSheet("font-weight: 600;")
        self.body = QLabel("")
        self.body.setTextFormat(Qt.RichText)
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        lay.addStretch(1)
        self.link: Optional[Dict[str, Any]] = None
        self.setMinimumWidth(330)

    def set_payload(self, payload: str) -> None:
        link = _loads(payload)
        self.link = link
        if not link:
            self.title.setText("Click a UE link in the 3D scene")
            self.body.setText("")
            return
        self.title.setText(f"Link budget: UE {link.get('ue')} ← BS {link.get('bs')}")
        rows = []
        for label, key, unit, fmt in self.ROWS:
            if key in link:
                strong = key in ("rx_power_dbm", "snr_db")
                val = fmt.format(float(link[key]))
                rows.append(f"<tr><td style='padding-right:14px;color:#A0A6AD'>{label}</td>"
                            f"<td align='right'>{'<b>' if strong else ''}{val}{'</b>' if strong else ''}</td>"
                            f"<td style='padding-left:6px;color:#8A9098'>{unit}</td></tr>")
        self.body.setText("<table cellspacing='3'>" + "".join(rows) + "</table>")


class PlotsPanel(QWidget):
    """Left: IMT PSD against the victim band. Right: CDF of I/N over the ground map."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Optional[Dict[str, Any]] = None
        self.setMinimumHeight(150)

    def sizeHint(self):  # noqa: N802
        return QSize(640, 190)

    def set_payload(self, payload: str) -> None:
        self.data = _loads(payload)
        self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _ev):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), BG)
        if not self.data:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignCenter, "No plot data for this scene")
            p.end()
            return
        half = self.width() / 2
        self._psd(p, QRectF(62, 24, half - 84, self.height() - 62))
        self._cdf(p, QRectF(half + 62, 24, half - 84, self.height() - 62))
        p.end()

    def _frame(self, p: QPainter, r: QRectF, title: str, xlabel: str, ylabel: str) -> None:
        p.setPen(FG)
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        p.drawText(QPointF(r.left(), r.top() - 8), title)
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(MUTED)
        p.drawText(QRectF(r.left(), r.bottom() + 18, r.width(), 14), Qt.AlignCenter, xlabel)
        p.save()
        p.translate(r.left() - 52, r.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-r.height() / 2, 0, r.height(), 14), Qt.AlignCenter, ylabel)
        p.restore()
        p.setPen(QPen(GRID, 1))
        p.drawRect(r)

    def _ticks(self, p: QPainter, r: QRectF, xs: List[float], ys: List[float], x0, x1, y0, y1, fx="{:.0f}", fy="{:.0f}"):
        p.setFont(QFont("Segoe UI", 8))
        for v in xs:
            x = r.left() + (v - x0) / (x1 - x0) * r.width()
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(MUTED)
            p.drawText(QRectF(x - 30, r.bottom() + 3, 60, 14), Qt.AlignCenter, fx.format(v))
        for v in ys:
            y = r.bottom() - (v - y0) / (y1 - y0) * r.height()
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(MUTED)
            p.drawText(QRectF(r.left() - 40, y - 7, 36, 14), Qt.AlignRight | Qt.AlignVCenter, fy.format(v))

    def _psd(self, p: QPainter, r: QRectF) -> None:
        imt = self.data.get("imt") or {}
        vic = self.data.get("victim") or {}
        f, bw, level = imt.get("freq_mhz"), imt.get("bandwidth_mhz"), imt.get("psd_dbm_mhz")
        if f is None or bw is None or level is None:
            return
        span = max(bw, vic.get("bandwidth_mhz") or 0.0) * 1.6
        centre = f
        if vic.get("freq_mhz"):
            centre = (f + vic["freq_mhz"]) / 2 if abs(f - vic["freq_mhz"]) < span * 2 else f
        x0, x1 = centre - span, centre + span
        y0, y1 = level - 60.0, level + 12.0
        self._frame(p, r, "IMT PSD vs victim band", "Frequency [MHz]", "PSD [dBm/MHz]")
        self._ticks(p, r, [x0 + (x1 - x0) * k / 4 for k in range(5)], [y0 + 12 * k for k in range(1, 6)], x0, x1, y0, y1)
        X = lambda v: r.left() + (v - x0) / (x1 - x0) * r.width()          # noqa: E731
        Y = lambda v: r.bottom() - (v - y0) / (y1 - y0) * r.height()       # noqa: E731
        if vic.get("freq_mhz") and vic.get("bandwidth_mhz"):
            vx0, vx1 = vic["freq_mhz"] - vic["bandwidth_mhz"] / 2, vic["freq_mhz"] + vic["bandwidth_mhz"] / 2
            shade = QColor(WARN)
            shade.setAlpha(55)
            p.fillRect(QRectF(max(r.left(), X(vx0)), r.top(), min(r.right(), X(vx1)) - max(r.left(), X(vx0)), r.height()), shade)
            p.setPen(WARN)
            p.drawText(QPointF(min(r.right() - 120, max(r.left(), X(vx1)) - 124), r.top() + 14), str(vic.get("name", "victim")))
        path = QPainterPath(QPointF(X(f - bw / 2), r.bottom()))
        path.lineTo(X(f - bw / 2), Y(level))
        path.lineTo(X(f + bw / 2), Y(level))
        path.lineTo(X(f + bw / 2), r.bottom())
        fill = QColor(ACCENT)
        fill.setAlpha(90)
        p.setPen(QPen(ACCENT, 2))
        p.setBrush(fill)
        p.drawPath(path)
        p.setPen(FG)
        p.drawText(QPointF(X(f - bw / 2) + 6, Y(level) + 16), f"IMT {level:.1f} dBm/MHz")

    def _cdf(self, p: QPainter, r: QRectF) -> None:
        cdf = self.data.get("cdf")
        if not cdf or not cdf.get("x"):
            return
        xs, ps = [float(v) for v in cdf["x"]], [float(v) for v in cdf["p"]]
        x0, x1 = math.floor(xs[0] / 10) * 10, math.ceil(xs[-1] / 10) * 10
        if x1 <= x0:
            x1 = x0 + 10
        self._frame(p, r, "CDF of " + cdf.get("label", "I/N"), f"I/N [{cdf.get('unit', 'dB')}]", "Probability")
        self._ticks(p, r, [x0 + (x1 - x0) * k / 4 for k in range(5)], [0.0, 0.25, 0.5, 0.75, 1.0], x0, x1, 0.0, 1.0,
                    fy="{:.2f}")
        path = QPainterPath()
        for k, (x, y) in enumerate(zip(xs, ps)):
            pt = QPointF(r.left() + (x - x0) / (x1 - x0) * r.width(), r.bottom() - y * r.height())
            path.moveTo(pt) if k == 0 else path.lineTo(pt)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(ACCENT, 2))
        p.drawPath(path)
