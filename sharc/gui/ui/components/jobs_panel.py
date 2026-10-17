"""Jobs panel: the simulation queue as a professional job manager.

Columns: order, job, status, scheduled start, progress, ETA, elapsed. Toolbar and right-click menu
offer Run now, Stop, Move up/down, Reschedule, Remove, Pause queue and the parallel limit.
The logic lives in `core/job_scheduler.py`; this widget only shows it and sends commands.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import qtawesome as qta
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDateTimeEdit, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMenu,
    QProgressBar, QSpinBox, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core import job_scheduler as js

STATUS_STYLE = {
    js.QUEUED: ("mdi.clock-outline", "#A0A6AD"),
    js.SCHEDULED: ("mdi.calendar-clock", "#D9A23B"),
    js.RUNNING: ("mdi.play-circle", "#4F9DDE"),
    js.COMPLETED: ("mdi.check-circle", "#5DB36A"),
    js.FAILED: ("mdi.alert-circle", "#E0605A"),
    js.STOPPED: ("mdi.stop-circle", "#8A9099"),
}


def _fmt_elapsed(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--"
    s = int(seconds)
    return f"{s // 3600:d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class ScheduleDialog(QDialog):
    """Pick the date and time a job should start."""

    def __init__(self, parent=None, when: Optional[datetime] = None):
        super().__init__(parent)
        self.setWindowTitle("Schedule start")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Start the job at:"))
        self.edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(300) if when is None
                                  else QDateTime(when))
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.edit.setMinimumDateTime(QDateTime.currentDateTime())
        lay.addWidget(self.edit)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def value(self) -> datetime:
        return self.edit.dateTime().toPython()


class JobsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sched: Optional[js.JobScheduler] = None
        self._bars = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)
        bar.setSpacing(2)
        self.btn_pause = self._tool("mdi.pause-circle-outline", "Pause / resume the queue", self._toggle_pause, True)
        self.btn_now = self._tool("mdi.play", "Run selected job now", lambda: self._act("run_now"))
        self.btn_stop = self._tool("mdi.stop", "Stop selected job", lambda: self._act("stop"))
        self.btn_up = self._tool("mdi.arrow-up", "Move up", lambda: self._act("move", -1))
        self.btn_down = self._tool("mdi.arrow-down", "Move down", lambda: self._act("move", +1))
        self.btn_when = self._tool("mdi.calendar-clock", "Schedule start time", self._schedule_selected)
        self.btn_remove = self._tool("mdi.delete-outline", "Remove selected job", lambda: self._act("remove"))
        self.btn_clear = self._tool("mdi.broom", "Clear finished jobs", lambda: self.sched and self.sched.clear_finished())
        for b in (self.btn_pause, self.btn_now, self.btn_stop, self.btn_up, self.btn_down,
                  self.btn_when, self.btn_remove, self.btn_clear):
            bar.addWidget(b)
        bar.addSpacing(10)
        bar.addWidget(QLabel("Parallel"))
        self.spin = QSpinBox()
        self.spin.setRange(1, 64)
        self.spin.setValue(2)
        self.spin.setToolTip("Maximum simulations running at the same time")
        self.spin.valueChanged.connect(self._on_parallel)
        bar.addWidget(self.spin)
        bar.addStretch(1)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setObjectName("StatusMsg")
        bar.addWidget(self.lbl_summary)
        lay.addLayout(bar)

        self.tree = QTreeWidget()
        self.tree.setObjectName("JobsTree")
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["#", "Job", "Status", "Start", "Progress", "ETA", "Elapsed"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemDoubleClicked.connect(lambda *_: self._act("run_now"))
        for col, w in enumerate((34, 230, 110, 120, 150, 80, 80)):
            self.tree.setColumnWidth(col, w)
        lay.addWidget(self.tree, 1)

    def _on_parallel(self, n: int) -> None:
        if self.sched is not None:
            self.sched.set_max_parallel(n)
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            from PySide6.QtCore import QSettings
            QSettings("SHARC", "GUI").setValue("sim/parallel", n)

    # ------------------------------------------------------------- setup
    def _tool(self, icon, tip, slot, checkable=False):
        b = QToolButton()
        b.setIcon(qta.icon(icon, color="#9AA0A7"))
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setAutoRaise(True)
        b.clicked.connect(lambda *_: slot())
        return b

    def bind(self, scheduler: js.JobScheduler) -> None:
        self.sched = scheduler
        self.spin.setValue(scheduler.max_parallel)
        scheduler.changed.connect(self.refresh)
        self.refresh()

    # ---------------------------------------------------------- selection
    def _selected_ids(self):
        return [it.data(0, Qt.UserRole) for it in self.tree.selectedItems()]

    def _act(self, name: str, *args):
        if self.sched is None:
            return
        ids = self._selected_ids()
        if name == "move" and args and args[0] > 0:
            ids = ids[::-1]                          # moving down: last item first keeps the order
        for jid in ids:
            getattr(self.sched, name)(jid, *args)

    def _toggle_pause(self):
        if self.sched is not None:
            self.sched.pause(self.btn_pause.isChecked())

    def _schedule_selected(self):
        if self.sched is None or not self._selected_ids():
            return
        dlg = ScheduleDialog(self)
        if dlg.exec() == QDialog.Accepted:
            for jid in self._selected_ids():
                self.sched.reschedule(jid, dlg.value())

    def _menu(self, pos):
        if self.sched is None:
            return
        ids = self._selected_ids()
        menu = QMenu(self)
        if ids:
            menu.addAction(qta.icon("mdi.play", color="#5DB36A"), "Run now", lambda: self._act("run_now"))
            menu.addAction(qta.icon("mdi.stop", color="#E0605A"), "Stop", lambda: self._act("stop"))
            menu.addSeparator()
            menu.addAction(qta.icon("mdi.calendar-clock"), "Reschedule...", self._schedule_selected)
            menu.addAction("Start as soon as possible", lambda: [self.sched.reschedule(i, None) for i in ids])
            menu.addAction(qta.icon("mdi.arrow-up"), "Move up", lambda: self._act("move", -1))
            menu.addAction(qta.icon("mdi.arrow-down"), "Move down", lambda: self._act("move", +1))
            menu.addSeparator()
            menu.addAction("Copy file path", lambda: QApplication.clipboard().setText(
                "\n".join(self.sched.job(i).path for i in ids if self.sched.job(i))))
            menu.addAction("Open containing folder", self._open_folder)
            menu.addAction(qta.icon("mdi.delete-outline"), "Remove", lambda: self._act("remove"))
            menu.addSeparator()
        menu.addAction("Pause queue" if not self.sched.paused else "Resume queue",
                       lambda: (self.btn_pause.setChecked(not self.sched.paused), self._toggle_pause()))
        menu.addAction("Clear finished", self.sched.clear_finished)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _open_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        for jid in self._selected_ids()[:1]:
            job = self.sched.job(jid)
            if job:
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(job.path)))

    # ------------------------------------------------------------ refresh
    def refresh(self):
        if self.sched is None:
            return
        selected = set(self._selected_ids())
        jobs = self.sched.jobs
        ids = [j.id for j in jobs]
        current = [self.tree.topLevelItem(i).data(0, Qt.UserRole) for i in range(self.tree.topLevelItemCount())]
        if ids != current:                                   # structure changed: rebuild rows
            self.tree.clear()
            self._bars.clear()
            for j in jobs:
                it = QTreeWidgetItem(self.tree)
                it.setData(0, Qt.UserRole, j.id)
                bar = QProgressBar()
                bar.setRange(0, 1000)
                bar.setTextVisible(True)
                bar.setFixedHeight(15)
                self.tree.setItemWidget(it, 4, bar)
                self._bars[j.id] = bar
        for i, j in enumerate(jobs):
            it = self.tree.topLevelItem(i)
            icon, color = STATUS_STYLE.get(j.status, STATUS_STYLE[js.QUEUED])
            it.setText(0, str(i + 1))
            it.setText(1, j.name)
            it.setToolTip(1, j.path)
            it.setText(2, j.status)
            it.setIcon(2, qta.icon(icon, color=color))
            it.setForeground(2, QColor(color))
            it.setText(3, f"{j.start_at:%m-%d %H:%M}" if j.start_at and j.status == js.SCHEDULED else "--")
            it.setText(5, j.eta if j.status == js.RUNNING else "--")
            it.setText(6, _fmt_elapsed(j.elapsed))
            bar = self._bars[j.id]
            bar.setValue(int(j.pct * 10))
            bar.setFormat(f"{j.pct:.0f}%  {j.snap if j.snap != '--' else ''}".strip())
            it.setSelected(j.id in selected)
        self.btn_pause.setChecked(self.sched.paused)
        self.lbl_summary.setText(self.sched.summary())
