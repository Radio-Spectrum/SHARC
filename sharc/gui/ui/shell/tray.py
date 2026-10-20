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
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QLabel, QMenu, QMessageBox, QSystemTrayIcon,
                               QVBoxLayout)

from core import job_scheduler as js

SETTING_KEY = "tray/keep_running"
CLOSE_KEY = "tray/close_action"


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


def render_tray_icon(color: str, pct: Optional[float] = None, active: int = 0, paused: bool = False,
                     failed: bool = False, size: int = 64) -> QIcon:
    """Tray icon with the queue progress drawn as a ring and the number of active jobs as a badge.

    pct=None draws the idle icon (orbit glyph only). Paused turns the ring amber, failures red.
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#161B24"))
    p.drawEllipse(QRectF(2, 2, s - 4, s - 4))
    ring = QRectF(7, 7, s - 14, s - 14)
    p.setPen(QPen(QColor("#2A3446"), s * 0.11))
    p.drawEllipse(ring)
    accent = QColor("#E0605A" if failed else "#D9A23B" if paused else color)
    if pct is not None:
        pen = QPen(accent, s * 0.11)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(ring, 90 * 16, int(-360 * 16 * max(0.0, min(100.0, pct)) / 100))
        p.setPen(QColor("#EAF1FA"))
        f = QFont("Segoe UI", int(s * 0.26), QFont.DemiBold)
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), Qt.AlignCenter, f"{int(pct)}")
    else:
        p.setPen(QPen(accent, s * 0.07))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(s * 0.3, s * 0.38, s * 0.4, s * 0.24))
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QRectF(s * 0.56, s * 0.3, s * 0.12, s * 0.12))
    if active > 1:
        r = s * 0.17
        p.setPen(Qt.NoPen)
        p.setBrush(accent)
        p.drawEllipse(QRectF(s - 2 * r - 1, 1, 2 * r, 2 * r))
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Segoe UI", int(s * 0.16), QFont.Bold))
        p.drawText(QRectF(s - 2 * r - 1, 1, 2 * r, 2 * r), Qt.AlignCenter, str(min(active, 9)))
    p.end()
    return QIcon(pm)


class TrayController:
    """Owns the tray icon and decides what closing the window means."""

    def __init__(self, window, scheduler: js.JobScheduler, color: str = "#4F9DDE",
                 tray_factory: Callable[..., QSystemTrayIcon] = QSystemTrayIcon):
        self.window, self.scheduler = window, scheduler
        self._color = color
        self._job_actions: list = []
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self._was_active = False
        self._quitting = False
        self.last_message = ""                     # last notification text (also used by tests)
        self.tray: Optional[QSystemTrayIcon] = None
        if self.available:
            self.tray = tray_factory(render_tray_icon(color), window)
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

    @staticmethod
    def close_action() -> str:
        """What the window's close button does: "ask" (default), "minimize" (to tray) or "quit"."""
        v = str(QSettings("SHARC", "GUI").value(CLOSE_KEY, "ask")).lower()
        return v if v in ("ask", "minimize", "quit") else "ask"

    @staticmethod
    def set_close_action(value: str) -> None:
        QSettings("SHARC", "GUI").setValue(CLOSE_KEY, value if value in ("ask", "minimize", "quit") else "ask")

    def close_choice(self) -> str:
        """Decide what the close button means now: "minimize", "quit" or "cancel" (asks unless remembered)."""
        action = self.close_action()
        if action in ("minimize", "quit"):
            return action
        n = self.active_jobs()
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Close SHARC")
        box.setText("Do you want to keep SHARC in the system tray or quit it?")
        box.setInformativeText(
            (f"{n} simulation job(s) are running or waiting; they keep going if you minimize to the tray."
             if n else "Minimized, SHARC stays available from the tray icon."))
        b_min = box.addButton("Minimize to tray", QMessageBox.AcceptRole)
        b_quit = box.addButton("Quit SHARC", QMessageBox.DestructiveRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(b_min)
        remember = QCheckBox("Remember my choice (change it in Settings > Preferences)")
        box.setCheckBox(remember)
        box.exec()
        clicked = box.clickedButton()
        choice = "minimize" if clicked is b_min else "quit" if clicked is b_quit else "cancel"
        if remember.isChecked() and choice != "cancel":
            self.set_close_action(choice)
        return choice

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

    def _refresh_job_actions(self, running) -> None:
        """One disabled menu line per running job (name, progress, ETA), above the pause/stop actions."""
        for a in self._job_actions:
            self._menu.removeAction(a)
        self._job_actions = []
        for j in running[:6]:
            eta = f"  ETA {j.eta}" if j.eta not in ("", "--") else ""
            a = QAction(f"{j.name[:34]}  {j.pct:.0f}%{eta}", self._menu)
            a.setEnabled(False)
            self._menu.insertAction(self.act_pause, a)
            self._job_actions.append(a)

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
            running = [j for j in self.scheduler.jobs if j.status == js.RUNNING]
            pcts = [j.pct for j in running]
            avg = sum(pcts) / len(pcts) if pcts else None
            text = (f"{n_run} running, {waiting} waiting" + (f", {avg:.0f}%" if avg is not None else "")) \
                if active else "No simulations running"
            lines = [f"SHARC: {text}"] + [f"{j.name[:26]}: {j.pct:.0f}%" + (f" (ETA {j.eta})" if j.eta not in ("", "--") else "")
                                         for j in running[:3]]
            self.tray.setToolTip("\n".join(lines))
            failed = any(j.status == js.FAILED for j in self.scheduler.jobs) and not active
            self.tray.setIcon(render_tray_icon(self._color, avg if active else None, active,
                                               self.scheduler.paused and active > 0, failed))
            self._refresh_job_actions(running)
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
        if n:
            self.notify("SHARC is still running",
                        f"The window was closed, but {n} simulation job(s) continue in the background. "
                        "Use the tray icon to reopen SHARC or to quit.")
        else:
            self.notify("SHARC is in the system tray",
                        "Click the tray icon to reopen SHARC, or right-click it to quit.")

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
