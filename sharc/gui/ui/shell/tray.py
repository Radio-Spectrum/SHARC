"""System-tray behaviour: keep simulating in the background after the window is closed.

When the user closes the main window while simulations are running or waiting, the window is
hidden instead of closed, a notification says so, and a tray icon stays. The icon shows the queue
progress in its tooltip, reopens the window on click, and its menu can pause the queue, stop every
job or quit. A notification also tells when the background work finishes.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

import qtawesome as qta
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMenu, QMessageBox, QSystemTrayIcon, QVBoxLayout

from core import job_scheduler as js

SETTING_KEY = "tray/keep_running"


class CornerNotice(QFrame):
    """Always-visible notice in the screen corner. Windows can hide system toasts (Focus Assist,
    notification settings), so the "still running in the background" message must not depend on them."""

    def __init__(self, title: str, text: str, ms: int = 8000):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("CornerNotice{background:#1B2230;border:1px solid #4F9DDE;border-radius:6px;}"
                           "QLabel{color:#E8ECF1;} #t{font-weight:600;font-size:13px;} #b{color:#B8C1CF;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        t, b = QLabel(title), QLabel(text)
        t.setObjectName("t")
        b.setObjectName("b")
        b.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(b)
        self.setFixedWidth(360)
        self.adjustSize()
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 16, geo.bottom() - self.height() - 16)
        QTimer.singleShot(ms, self.close)

    def mousePressEvent(self, ev):  # noqa: N802
        self.close()


class TrayController:
    """Owns the tray icon and decides what closing the window means."""

    def __init__(self, window, scheduler: js.JobScheduler, color: str = "#4F9DDE",
                 tray_factory: Callable[..., QSystemTrayIcon] = QSystemTrayIcon):
        self.window, self.scheduler = window, scheduler
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self._was_active = False
        self._quitting = False
        self.last_message = ""                     # last notification text (also used by tests)
        self.tray: Optional[QSystemTrayIcon] = None
        if self.available:
            icon = qta.icon("mdi.orbit-variant", color=color)
            self.tray = tray_factory(icon, window)
            self.tray.setToolTip("SHARC")
            self.tray.activated.connect(self._on_activated)
            self.tray.setContextMenu(self._build_menu())
        scheduler.changed.connect(self._on_queue_changed)
        QApplication.instance().setQuitOnLastWindowClosed(False)

    # ------------------------------------------------------------- settings
    @staticmethod
    def keep_running_enabled() -> bool:
        v = QSettings("SHARC", "GUI").value(SETTING_KEY, True)
        return str(v).lower() in ("true", "1", "yes")

    @staticmethod
    def set_keep_running(on: bool) -> None:
        QSettings("SHARC", "GUI").setValue(SETTING_KEY, bool(on))

    # ----------------------------------------------------------- state
    def active_jobs(self) -> int:
        return sum(1 for j in self.scheduler.jobs if j.status in (js.RUNNING, js.QUEUED, js.SCHEDULED))

    def should_hide(self) -> bool:
        """Closing the window keeps SHARC alive only when there is background work to protect."""
        return self.available and self.keep_running_enabled() and not self._quitting and self.active_jobs() > 0

    # --------------------------------------------------------------- menu
    def _build_menu(self) -> QMenu:
        m = QMenu()
        self.act_show = QAction(qta.icon("mdi.window-restore"), "Show SHARC", m)
        self.act_show.triggered.connect(self.show_window)
        m.addAction(self.act_show)
        m.addSeparator()
        self.act_status = QAction("No simulations running", m)
        self.act_status.setEnabled(False)
        m.addAction(self.act_status)
        self.act_pause = QAction(qta.icon("mdi.pause-circle-outline"), "Pause queue", m)
        self.act_pause.triggered.connect(lambda: self.scheduler.pause(not self.scheduler.paused))
        m.addAction(self.act_pause)
        self.act_stop = QAction(qta.icon("mdi.stop"), "Stop all jobs", m)
        self.act_stop.triggered.connect(self._stop_all)
        m.addAction(self.act_stop)
        m.addSeparator()
        act_quit = QAction(qta.icon("mdi.power"), "Quit SHARC", m)
        act_quit.triggered.connect(self.quit)
        m.addAction(act_quit)
        self._menu = m
        return m

    def _stop_all(self) -> None:
        for job in list(self.scheduler.jobs):
            if job.status in (js.RUNNING, js.QUEUED, js.SCHEDULED):
                self.scheduler.stop(job.id)

    # ---------------------------------------------------------- reactions
    def _on_queue_changed(self) -> None:
        n_run = sum(1 for j in self.scheduler.jobs if j.status == js.RUNNING)
        waiting = sum(1 for j in self.scheduler.jobs if j.status in (js.QUEUED, js.SCHEDULED))
        active = n_run + waiting
        if self.tray is not None:
            pcts = [j.pct for j in self.scheduler.jobs if j.status == js.RUNNING]
            avg = f", {sum(pcts) / len(pcts):.0f}%" if pcts else ""
            text = f"{n_run} running, {waiting} waiting{avg}" if active else "No simulations running"
            self.tray.setToolTip(f"SHARC: {text}")
            self.act_status.setText(text)
            self.act_pause.setText("Resume queue" if self.scheduler.paused else "Pause queue")
            self.act_stop.setEnabled(active > 0)
        notify_finish = str(QSettings("SHARC", "GUI").value("tray/notify_finish", True)).lower() in ("true", "1", "yes")
        if self._was_active and active == 0 and not self.window.isVisible() and notify_finish:
            done = sum(1 for j in self.scheduler.jobs if j.status == js.COMPLETED)
            failed = sum(1 for j in self.scheduler.jobs if j.status == js.FAILED)
            self.notify("Simulations finished",
                        f"{done} completed" + (f", {failed} failed" if failed else "")
                        + ". Click the tray icon to open SHARC.",
                        QSystemTrayIcon.Warning if failed else QSystemTrayIcon.Information)
        self._was_active = active > 0

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    # -------------------------------------------------------------- actions
    def notify(self, title: str, text: str, icon=QSystemTrayIcon.Information, ms: int = 7000) -> None:
        self.last_message = f"{title}: {text}"
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):          # tests run without on-screen popups
            self._popup = CornerNotice(title, text, ms + 1000)
            self._popup.show()
        if self.tray is not None:
            self.tray.show()
            self.tray.showMessage(title, text, icon, ms)

    def hide_to_tray(self) -> None:
        """Called by the main window instead of closing."""
        self.window.hide()
        if self.tray is not None:
            self.tray.show()
        n = self.active_jobs()
        self.notify("SHARC is still running",
                    f"The window was closed, but {n} simulation job(s) continue in the background. "
                    "Use the tray icon to reopen SHARC or to quit.")

    def show_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        if self.tray is not None and self.active_jobs() == 0:
            self.tray.hide()

    def quit(self) -> None:
        """Quit for real; asks first when simulations would be interrupted."""
        n = self.active_jobs()
        if n:
            self.window.show()
            ans = QMessageBox.question(
                self.window, "Quit SHARC",
                f"{n} simulation job(s) are still running or waiting.\nQuit and stop them?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
            self._stop_all()
        self._quitting = True
        if self.tray is not None:
            self.tray.hide()
        QTimer.singleShot(0, self.window.close)
        QTimer.singleShot(50, QApplication.quit)
