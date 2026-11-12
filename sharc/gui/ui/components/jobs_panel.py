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
from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDateTimeEdit, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QMenu, QProgressBar, QSpinBox, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
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


def _exec_menu(menu: QMenu, global_pos) -> None:
    """Single place that opens the jobs menu modally (tests replace it)."""
    menu.exec(global_pos)


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
    plot_requested = Signal(int)         # job id whose results the user wants to plot

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
        self.btn_resume = self._tool("mdi.restore", "Resume selected job from its last checkpoint",
                                     self._resume_selected)
        self.btn_up = self._tool("mdi.arrow-up", "Move up", lambda: self._act("move", -1))
        self.btn_down = self._tool("mdi.arrow-down", "Move down", lambda: self._act("move", +1))
        self.btn_when = self._tool("mdi.calendar-clock", "Schedule start time", self._schedule_selected)
        self.btn_remove = self._tool("mdi.delete-outline", "Remove selected job", lambda: self._act("remove"))
        self.btn_clear = self._tool("mdi.broom", "Clear finished jobs", lambda: self.sched and self.sched.clear_finished())
        for b in (self.btn_pause, self.btn_now, self.btn_stop, self.btn_resume, self.btn_up, self.btn_down,
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
        self.chk_auto = QCheckBox("Auto-resume")
        self.chk_auto.setToolTip("When a simulation crashes, continue it automatically from its last "
                                 "checkpoint (up to 3 times, only while it keeps making progress)")
        self.chk_auto.setChecked(True)
        self.chk_auto.toggled.connect(self._on_auto_resume)
        bar.addWidget(self.chk_auto)
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
        self.tree.itemDoubleClicked.connect(lambda *_: self._open_selected())
        for col, w in enumerate((34, 230, 110, 120, 150, 80, 80)):
            self.tree.setColumnWidth(col, w)
        lay.addWidget(self.tree, 1)
        from ui.components.empty_state import EmptyState, EmptyStateOverlay
        self.empty_state = EmptyStateOverlay(self.tree, EmptyState(
            "mdi.tray-full", "No simulations in the queue",
            "Run (Ctrl+R) queues the current scenario; right-click a job for options."))
        self.empty_state.set_empty(True)

        # keyboard: Enter opens (plot results of a completed job, run a waiting one), Delete removes, Ctrl+D duplicates
        for keys, slot in (("Return", self._open_selected), ("Enter", self._open_selected),
                           ("Delete", lambda: self._act("remove")), ("Ctrl+D", self._duplicate_selected),
                           ("Ctrl+P", self._plot_selected)):
            sc = QShortcut(QKeySequence(keys), self.tree)
            sc.setContext(Qt.WidgetShortcut)
            sc.activated.connect(slot)

    def refresh_icons(self, tokens: dict) -> None:
        self.empty_state.refresh_icons(tokens)

    def _on_parallel(self, n: int) -> None:
        if self.sched is not None:
            self.sched.set_max_parallel(n)
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            from PySide6.QtCore import QSettings
            QSettings("SHARC", "GUI").setValue("sim/parallel", n)

    def _on_auto_resume(self, on: bool) -> None:
        if self.sched is not None:
            self.sched.auto_resume = bool(on)
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            from PySide6.QtCore import QSettings
            QSettings("SHARC", "GUI").setValue("sim/auto_resume", bool(on))

    def _resumable_ids(self):
        return [i for i in self._selected_ids() if self.sched.can_resume(i)]

    def _resume_selected(self):
        if self.sched is None:
            return
        for jid in self._resumable_ids():
            self.sched.resume(jid)

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
        auto = True
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            from PySide6.QtCore import QSettings
            auto = str(QSettings("SHARC", "GUI").value("sim/auto_resume", True)).lower() in ("true", "1", "yes")
        self.chk_auto.setChecked(auto)
        scheduler.auto_resume = auto
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

    def _completed_ids(self):
        return [i for i in self._selected_ids() if self.sched.job(i) and self.sched.job(i).status == js.COMPLETED]

    def _plot_selected(self):
        if self.sched is None:
            return
        for jid in self._completed_ids():
            self.plot_requested.emit(jid)

    def _open_selected(self):
        """Enter / double-click: plot a completed job, otherwise run a waiting one now."""
        if self.sched is None:
            return
        if self._completed_ids():
            self._plot_selected()
        else:
            self._act("run_now")

    def _duplicate_selected(self):
        if self.sched is not None:
            for jid in self._selected_ids():
                self.sched.duplicate(jid)

    def _menu(self, pos):
        if self.sched is None:
            return
        ids = self._selected_ids()
        menu = self._build_menu(ids)
        _exec_menu(menu, self.tree.viewport().mapToGlobal(pos))

    def _build_menu(self, ids):
        menu = QMenu(self)
        if ids:
            plot = menu.addAction(qta.icon("mdi.chart-line", color="#4F9DDE"), "Plot results (Enter)", self._plot_selected)
            plot.setObjectName("act_plot_results")
            plot.setEnabled(bool(self._completed_ids()))
            folder = menu.addAction(qta.icon("mdi.folder-open-outline"), "Open results folder", self._open_results_folder)
            folder.setObjectName("act_open_results")
            folder.setEnabled(bool(self._completed_ids()))
            menu.addSeparator()
            menu.addAction(qta.icon("mdi.play", color="#5DB36A"), "Run now", lambda: self._act("run_now"))
            menu.addAction(qta.icon("mdi.stop", color="#E0605A"), "Stop", lambda: self._act("stop"))
            resume = menu.addAction(qta.icon("mdi.restore", color="#4F9DDE"), "Resume from last checkpoint",
                                    self._resume_selected)
            resume.setObjectName("act_resume")
            resume.setEnabled(bool(self._resumable_ids()))
            menu.addSeparator()
            menu.addAction(qta.icon("mdi.calendar-clock"), "Reschedule...", self._schedule_selected)
            menu.addAction("Start as soon as possible", lambda: [self.sched.reschedule(i, None) for i in ids])
            menu.addAction(qta.icon("mdi.arrow-up"), "Move up", lambda: self._act("move", -1))
            menu.addAction(qta.icon("mdi.arrow-down"), "Move down", lambda: self._act("move", +1))
            menu.addSeparator()
            menu.addAction(qta.icon("mdi.content-copy"), "Duplicate (Ctrl+D)", self._duplicate_selected).setObjectName(
                "act_duplicate")
            menu.addAction("Copy file path", lambda: QApplication.clipboard().setText(
                "\n".join(self.sched.job(i).path for i in ids if self.sched.job(i))))
            menu.addAction("Open containing folder", self._open_folder)
            menu.addAction(qta.icon("mdi.delete-outline"), "Remove (Delete)", lambda: self._act("remove"))
            menu.addSeparator()
        menu.addAction("Pause queue" if not self.sched.paused else "Resume queue",
                       lambda: (self.btn_pause.setChecked(not self.sched.paused), self._toggle_pause()))
        menu.addAction("Clear finished", self.sched.clear_finished)
        return menu

    def _open_results_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from core.results_locator import find_job_results
        for jid in self._completed_ids()[:1]:
            folder = find_job_results(self.sched.job(jid).path)
            if folder is not None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

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
        self.empty_state.set_empty(not jobs)
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
            status = j.status
            if j.resume and j.status in (js.QUEUED, js.SCHEDULED, js.RUNNING):
                status = {js.RUNNING: "Resumed", js.SCHEDULED: "Resume pending"}.get(j.status, "Resume queued")
            it.setText(2, status)
            tip = j.message or ""
            if j.auto_resumes:
                tip += f"\nAutomatic resumes: {j.auto_resumes}"
            it.setToolTip(2, tip.strip())
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
