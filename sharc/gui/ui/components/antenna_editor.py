"""Editor de antena guiado pelo motor: escolhe o padrão, mostra os parâmetros certos
para ele e traça o ganho ao vivo (a curva vem da antena real do simulador).

Uso (qualquer aba que tenha variáveis SharcVar):

    editor = AntennaEditor(get_var, pattern_key="v_ant_pattern", gain_key="v_ant_gain",
                           prefix="v_ant")
    layout.addWidget(editor)
    yaml_block = editor.to_yaml()      # {"pattern":..., "gain":..., "<sub-bloco>": {...}}

`get_var(nome)` devolve o `SharcVar` do estado (criando-o se preciso); assim o
valor entra nos presets e no YAML sem código extra.
"""
from __future__ import annotations

import re
from typing import Callable, Dict, List

import numpy as np
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from core.antenna_service import PATTERN_SPECS, build_antenna, gain_at, pattern_names
from ui.components.properties import SectionBody  # reutiliza a linha de propriedade


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class GainPlot(QChartView):
    """Gráfico de ganho (dBi x ângulo) com linha fina, no estilo dos simuladores."""

    def __init__(self, parent=None):
        self._chart = QChart()
        super().__init__(self._chart, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(190)
        self._chart.legend().hide()
        self._chart.setMargins(QMargins(2, 2, 2, 2))
        self._chart.setBackgroundRoundness(0)
        self._chart.setBackgroundBrush(QColor("#1A1C1F"))
        self._chart.setBackgroundPen(QPen(QColor("#383C42"), 1))
        self._chart.setTitleBrush(QColor("#A0A6AD"))
        self.ax = QValueAxis()
        self.ay = QValueAxis()
        for ax, name in ((self.ax, "Off-axis angle [deg]"), (self.ay, "Gain [dBi]")):
            ax.setTitleText(name)
            ax.setLabelsColor(QColor("#A0A6AD"))
            ax.setTitleBrush(QColor("#A0A6AD"))
            ax.setGridLineColor(QColor("#30343A"))
            ax.setLinePenColor(QColor("#4A4F57"))
            ax.setLabelFormat("%.0f")
            ax.setTickCount(7)
        self._chart.addAxis(self.ax, Qt.AlignBottom)
        self._chart.addAxis(self.ay, Qt.AlignLeft)
        self.series = QLineSeries()
        pen = QPen(QColor("#4F9DDE"), 1.2)
        pen.setCosmetic(True)
        self.series.setPen(pen)
        self._chart.addSeries(self.series)
        self.series.attachAxis(self.ax)
        self.series.attachAxis(self.ay)

    def set_curve(self, angles: np.ndarray, gains: np.ndarray, title: str = "") -> None:
        self.series.replace([__import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(float(a), float(g))
                             for a, g in zip(angles, gains)])
        self.ax.setRange(float(angles.min()), float(angles.max()))
        lo, hi = float(np.nanmin(gains)), float(np.nanmax(gains))
        pad = max(2.0, (hi - lo) * 0.05)
        self.ay.setRange(np.floor(lo - pad), np.ceil(hi + pad))
        self._chart.setTitle(title)


class AntennaEditor(QWidget):
    """Padrão de antena + parâmetros + curva de ganho."""

    def __init__(self, get_var: Callable[[str], object], pattern_key: str, gain_key: str,
                 prefix: str, allowed: List[str] | None = None, parent=None):
        super().__init__(parent)
        self._get = get_var
        self._pattern_var = get_var(pattern_key)
        self._gain_var = get_var(gain_key)
        self._prefix = prefix
        self._allowed = allowed or pattern_names()
        self._field_vars: Dict[str, object] = {}
        self._edits: Dict[str, QLineEdit] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Padrão
        self._head = _Rows()
        self.combo = QComboBox()
        self.combo.addItems(self._allowed)
        self._head.add_row("Pattern", self.combo)
        lay.addWidget(self._head)
        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        self.desc.setObjectName("StatusMsg")
        lay.addWidget(self.desc)

        # Parâmetros do padrão (reconstruídos ao trocar)
        self._params_host = QFrame()
        self._params_lay = QVBoxLayout(self._params_host)
        self._params_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._params_host)

        # Curva
        self.plot = GainPlot()
        lay.addWidget(self.plot)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._redraw)

        cur = str(self._pattern_var.get() or "")
        if cur not in self._allowed:
            cur = self._allowed[0]
            self._pattern_var.set(cur)
        self.combo.setCurrentText(cur)
        self.combo.currentTextChanged.connect(self._on_combo)
        self._pattern_var.value_changed.connect(self._on_var_pattern)
        self._build_params()

    # --- estado ---------------------------------------------------------
    def _var_for(self, pattern: str, key: str):
        if key == "antenna_gain":
            return self._gain_var
        name = f"{self._prefix}_{_slug(pattern)}_{key}"
        v = self._get(name)
        spec = {f.key: f for f in PATTERN_SPECS[pattern].fields}[key]
        if str(v.get() or "") == "" and spec.default is not None:
            v.set(spec.default)
        return v

    def _on_combo(self, text):
        if text and text != str(self._pattern_var.get()):
            self._pattern_var.set(text)
        self._build_params()

    def _on_var_pattern(self, value):
        value = str(value)
        if value in self._allowed and value != self.combo.currentText():
            self.combo.blockSignals(True)
            self.combo.setCurrentText(value)
            self.combo.blockSignals(False)
            self._build_params()

    # --- interface ------------------------------------------------------
    def _build_params(self):
        while self._params_lay.count():
            it = self._params_lay.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        pattern = self.combo.currentText()
        spec = PATTERN_SPECS[pattern]
        self.desc.setText(spec.description)
        rows = _Rows()
        self._edits = {}
        for f in spec.fields:
            var = self._var_for(pattern, f.key)
            ed = QLineEdit()
            ed.setText(str(var.get()))
            ed.setToolTip(f.help or f.key)
            ed.textChanged.connect(lambda t, v=var: v.set(t))
            ed.textChanged.connect(lambda *_: self._timer.start())
            var.value_changed.connect(lambda val, e=ed: e.setText(str(val)) if e.text() != str(val) else None)
            rows.add_row(f.label, ed, f.unit)
            self._edits[f.key] = ed
        self._params_lay.addWidget(rows)
        self._timer.start()

    def _values(self) -> Dict[str, float]:
        pattern = self.combo.currentText()
        out = {}
        for f in PATTERN_SPECS[pattern].fields:
            raw = self._var_for(pattern, f.key).get()
            try:
                out[f.key] = float(raw)
            except (TypeError, ValueError):
                out[f.key] = None
        return out

    def _redraw(self):
        pattern = self.combo.currentText()
        try:
            vals = self._values()
            if any(v is None for v in vals.values()):
                raise ValueError("fill in every parameter with a number")
            ant = build_antenna(pattern, vals)
            peak_est = float(gain_at(ant, np.array([0.0]))[0])
            width = 30.0
            angles = np.linspace(0.0, width, 601)
            gains = gain_at(ant, angles, np.zeros_like(angles))
            # amplia a janela até o ganho cair bem abaixo do pico (feixes largos)
            for w in (30.0, 90.0, 180.0):
                angles = np.linspace(0.0, w, 721)
                gains = gain_at(ant, angles, np.zeros_like(angles))
                if gains[-1] < peak_est - 40 or w == 180.0:
                    break
            self.plot.set_curve(angles, gains, f"{pattern}  ·  peak {peak_est:.1f} dBi")
            self.msg.setText("")
        except Exception as exc:  # noqa: BLE001 - parâmetros do usuário
            self.msg.setStyleSheet("color: #e0605a;")
            self.msg.setText(f"Invalid parameters: {exc}")

    # --- YAML -----------------------------------------------------------
    def to_yaml(self) -> dict:
        pattern = self.combo.currentText()
        spec = PATTERN_SPECS[pattern]
        out: dict = {"pattern": pattern}
        vals = self._values()
        if "antenna_gain" in vals:
            out["gain"] = vals["antenna_gain"]
        if spec.attr is None:
            out["gain"] = vals.get("gain")
        else:
            out[spec.attr] = {k: v for k, v in vals.items() if k != "antenna_gain" and v is not None}
        return out


class _Rows(QWidget):
    """Bloco de linhas de propriedade (mesmo visual das seções)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QGridLayout
        self.setObjectName("SectionBody")
        self.grid = QGridLayout(self)
        self.grid.setObjectName("PropGrid")
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(0)
        self.grid.setVerticalSpacing(0)
        self.grid.setColumnStretch(0, 5)
        self.grid.setColumnStretch(1, 6)
        self.grid.setColumnMinimumWidth(2, 40)
        self.rows = 0
        self.content = self

    add_row = SectionBody.add_row
