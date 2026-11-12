"""Workflow strip of the compact toolbar: Setup > Validate > Run > Results, each stage coloured by its state.

The strip only renders `core.workflow_status.StageState` values and emits which stage was clicked; the window decides
what a click does and when to refresh. The page -> stage map lives here because it is presentation knowledge.
"""
from __future__ import annotations

from typing import Dict, Mapping

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from core.workflow_status import (ACTIVE, ERROR, IDLE, OK, RESULTS, RUN, SETUP, STAGES, VALIDATE, WARN, Stage,
                                  StageState, Visual)

_GLYPHS: Dict[Stage, str] = {
    SETUP: "mdi.tune-variant",
    VALIDATE: "mdi.check-decagram-outline",
    RUN: "mdi.play-circle-outline",
    RESULTS: "mdi.chart-box-outline",
}
_STATE_COLOR: Dict[Visual, str] = {OK: "success", WARN: "warn", ERROR: "danger", ACTIVE: "accent", IDLE: "icon"}

# which workbench page belongs to which stage (pages not listed are Setup)
_PAGE_STAGE: Dict[str, Stage] = {"runner": RUN, "ssh": RUN, "results": RESULTS, "contour": RESULTS}


def stage_for_page(page_key: str) -> Stage:
    return _PAGE_STAGE.get(page_key, SETUP)


class WorkflowStrip(QFrame):
    stage_clicked = Signal(str)          # a Stage value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkflowStrip")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(0)
        self._buttons: Dict[Stage, QToolButton] = {}
        self._states: Dict[Stage, StageState] = {}
        self._current: str = ""
        for i, (key, label) in enumerate(STAGES):
            if i:
                chevron = QLabel("›")
                chevron.setObjectName("WorkflowChevron")
                lay.addWidget(chevron)
            b = QToolButton()
            b.setObjectName("WorkflowStage")
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setIconSize(QSize(16, 16))
            b.setCursor(Qt.PointingHandCursor)
            b.setText(label)
            b.setProperty("state", IDLE)
            b.setProperty("current", False)
            b.clicked.connect(lambda _=False, k=key: self.stage_clicked.emit(k))
            lay.addWidget(b)
            self._buttons[key] = b
            self._states[key] = StageState()
        self._tokens: Dict[str, str] = {}

    # ---------------------------------------------------------------- state
    def set_states(self, states: Mapping[Stage, StageState]) -> None:
        for key, st in states.items():
            b = self._buttons.get(key)
            if b is None:
                continue
            self._states[key] = st
            label = dict(STAGES)[key]
            b.setText(f"{label}  {st.badge}" if st.badge else label)
            b.setToolTip(st.tip)
            if b.property("state") != st.state:
                b.setProperty("state", st.state)
                self._repolish(b)
        self._paint_icons()

    def set_current(self, stage: Stage) -> None:
        if stage == self._current:
            return
        self._current = stage
        for key, b in self._buttons.items():
            b.setProperty("current", key == stage)
            self._repolish(b)

    def state_of(self, stage: Stage) -> StageState:
        return self._states.get(stage, StageState())

    def refresh_icons(self, tokens: Mapping[str, str]) -> None:
        self._tokens = dict(tokens)
        self._paint_icons()

    # ------------------------------------------------------------- helpers
    def _paint_icons(self) -> None:
        if not self._tokens:
            return
        for key, b in self._buttons.items():
            role = _STATE_COLOR[self._states[key].state]
            b.setIcon(qta.icon(_GLYPHS[key], color=self._tokens[role]))

    @staticmethod
    def _repolish(widget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
