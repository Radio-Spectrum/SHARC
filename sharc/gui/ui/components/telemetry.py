"""System and simulator telemetry shown in the free right corner of the menu bar."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from core import preflight as pf
from core import job_scheduler as js


class TelemetryWidget(QWidget):
    """CPU, RAM and free disk of the machine, plus what the simulator is doing (jobs, engine RAM, elapsed)."""

    def __init__(self, get_scheduler: Callable[[], Optional[js.JobScheduler]], disk_path: Callable[[], str],
                 parent=None, interval_ms: int = 1000):
        super().__init__(parent)
        self._get_scheduler, self._disk_path = get_scheduler, disk_path
        try:
            import psutil
            self._ps = psutil
            self._me = psutil.Process()
            psutil.cpu_percent(None)             # first call primes the counter
        except Exception:  # noqa: BLE001 - psutil missing: the widget stays empty
            self._ps = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 10, 0)
        lay.setSpacing(14)
        self.lbl_sys = QLabel("")
        self.lbl_sim = QLabel("")
        for lbl in (self.lbl_sys, self.lbl_sim):
            lbl.setObjectName("HUDStat")
            lay.addWidget(lbl)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        if self._ps is not None:
            self._timer.start(interval_ms)
            self.refresh()

    def refresh(self):
        ps = self._ps
        if ps is None:
            return
        try:
            cpu = ps.cpu_percent(None)
            vm = ps.virtual_memory()
            disk = ps.disk_usage(self._disk_path() or ".")
        except Exception:  # noqa: BLE001 - never let a monitor raise inside a timer
            return
        self.lbl_sys.setText(f"CPU {cpu:.0f}%   RAM {vm.percent:.0f}%   DISK {pf.fmt_bytes(disk.free)} free")
        self.lbl_sys.setToolTip(
            f"CPU: {ps.cpu_count(logical=True)} logical cores, {cpu:.1f}% busy\n"
            f"RAM: {pf.fmt_bytes(vm.total - vm.available)} used of {pf.fmt_bytes(vm.total)} "
            f"({pf.fmt_bytes(vm.available)} available)\n"
            f"Disk ({self._disk_path()}): {pf.fmt_bytes(disk.free)} free of {pf.fmt_bytes(disk.total)}")

        sched = self._get_scheduler()
        jobs = list(sched.jobs) if sched is not None else []
        running = [j for j in jobs if j.status == js.RUNNING]
        waiting = sum(1 for j in jobs if j.status in js.WAITING)
        engine_rss, nproc = 0, 0
        try:
            for c in self._me.children(recursive=True):
                try:
                    engine_rss += c.memory_info().rss
                    nproc += 1
                except ps.Error:
                    pass
        except ps.Error:
            pass
        if running or waiting:
            longest = max((j.elapsed or 0.0 for j in running), default=0.0)
            self.lbl_sim.setText(f"SIM {len(running)} running · {waiting} queued · "
                                 f"{pf.fmt_bytes(engine_rss)} · {pf.fmt_duration(longest)}")
        else:
            self.lbl_sim.setText("SIM idle")
        self.lbl_sim.setToolTip(
            f"Running jobs: {len(running)}\nWaiting: {waiting}\n"
            f"Child processes: {nproc} using {pf.fmt_bytes(engine_rss)} of RAM\n"
            f"GUI process: {pf.fmt_bytes(self._me.memory_info().rss)}")
