"""Simulation job queue: order, parallel limit and scheduled start.

Jobs are SHARC configuration files run locally through the runner manager
(`managers/ssh_runner.py::RunnerManager`). The scheduler decides *when* each job starts:

* jobs start in list order, at most `max_parallel` at a time;
* a job can have a start time (it waits in "Scheduled" until then);
* the queue can be paused, jobs can be reordered, stopped, rescheduled or started right away.

The runner reports progress through `on_status()` (same payloads the Execution Engine
table receives), so the queue stays in sync without polling the processes.
"""
from __future__ import annotations

import itertools
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

QUEUED, SCHEDULED, RUNNING, COMPLETED, FAILED, STOPPED = (
    "Queued", "Scheduled", "Running", "Completed", "Failed", "Stopped")
ACTIVE = (RUNNING,)
WAITING = (QUEUED, SCHEDULED)
FINISHED = (COMPLETED, FAILED, STOPPED)
_ids = itertools.count(1)


@dataclass
class Job:
    path: str
    name: str
    id: int = 0
    status: str = QUEUED
    start_at: Optional[datetime] = None
    created: float = 0.0
    started: Optional[float] = None
    finished: Optional[float] = None
    pct: float = 0.0
    snap: str = "--"
    eta: str = "--"
    message: str = ""

    @property
    def elapsed(self) -> Optional[float]:
        if self.started is None:
            return None
        return (self.finished or time.time()) - self.started


def _parse_pct(text) -> Optional[float]:
    if text is None:
        return None
    m = re.search(r"[\d.]+", str(text))
    return float(m.group()) if m else None


class JobScheduler(QObject):
    """Queue of simulation jobs."""

    changed = Signal()

    def __init__(self, start_fn: Callable[[str], None], stop_fn: Callable[[str], None],
                 log: Callable[[str], None] = lambda _m: None, max_parallel: int = 2, parent=None):
        super().__init__(parent)
        self._start_fn, self._stop_fn, self._log = start_fn, stop_fn, log
        self.jobs: List[Job] = []
        self.max_parallel = max(1, int(max_parallel))
        self.paused = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.tick)
        self._timer.start()

    # ------------------------------------------------------------ queries
    def job(self, job_id: int) -> Optional[Job]:
        return next((j for j in self.jobs if j.id == job_id), None)

    def by_path(self, path: str) -> Optional[Job]:
        # the newest job for a path wins (the same file can be queued again)
        return next((j for j in reversed(self.jobs) if j.path == path), None)

    def running(self) -> List[Job]:
        return [j for j in self.jobs if j.status in ACTIVE]

    def summary(self) -> str:
        n = lambda s: sum(1 for j in self.jobs if j.status == s)  # noqa: E731
        return (f"{n(RUNNING)} running, {n(QUEUED) + n(SCHEDULED)} waiting, "
                f"{n(COMPLETED)} completed, {n(FAILED)} failed")

    # ---------------------------------------------------------- commands
    def submit(self, paths: List[str], start_at: Optional[datetime] = None) -> List[Job]:
        created = []
        for p in paths:
            parts = os.path.normpath(p).split(os.sep)
            job = Job(path=p, name="/".join(parts[-2:]), id=next(_ids), created=time.time(),
                      start_at=start_at, status=SCHEDULED if start_at else QUEUED)
            self.jobs.append(job)
            created.append(job)
        self._log(f"[QUEUE] {len(created)} job(s) added" + (f", scheduled for {start_at:%Y-%m-%d %H:%M}" if start_at else ""))
        self.tick()
        return created

    def move(self, job_id: int, delta: int) -> None:
        j = self.job(job_id)
        if j is None or j.status not in WAITING:
            return
        i = self.jobs.index(j)
        k = max(0, min(len(self.jobs) - 1, i + delta))
        self.jobs.insert(k, self.jobs.pop(i))
        self.changed.emit()

    def remove(self, job_id: int) -> None:
        j = self.job(job_id)
        if j is None:
            return
        if j.status in ACTIVE:
            self.stop(job_id)
        self.jobs.remove(j)
        self.changed.emit()

    def clear_finished(self) -> None:
        self.jobs = [j for j in self.jobs if j.status not in FINISHED]
        self.changed.emit()

    def stop(self, job_id: int) -> None:
        j = self.job(job_id)
        if j is None:
            return
        if j.status in ACTIVE:
            self._stop_fn(j.path)
        if j.status not in FINISHED:
            j.status, j.finished = STOPPED, time.time()
            self._log(f"[QUEUE] {j.name} stopped")
        self.changed.emit()

    def reschedule(self, job_id: int, start_at: Optional[datetime]) -> None:
        j = self.job(job_id)
        if j is None or j.status not in WAITING:
            return
        j.start_at = start_at
        j.status = SCHEDULED if start_at else QUEUED
        self.tick()

    def run_now(self, job_id: int) -> None:
        j = self.job(job_id)
        if j is not None and j.status in WAITING:
            j.start_at = None
            self._start(j)

    def pause(self, on: bool = True) -> None:
        self.paused = bool(on)
        self._log("[QUEUE] queue paused" if self.paused else "[QUEUE] queue resumed")
        self.changed.emit()
        if not self.paused:
            self.tick()

    def set_max_parallel(self, n: int) -> None:
        self.max_parallel = max(1, int(n))
        self.tick()

    # ----------------------------------------------------------- engine
    def _start(self, job: Job) -> None:
        job.status, job.started, job.finished = RUNNING, time.time(), None
        job.pct, job.snap, job.eta = 0.0, "--", "--"
        self._log(f"[QUEUE] starting {job.name}")
        try:
            self._start_fn(job.path)
        except Exception as exc:  # noqa: BLE001
            job.status, job.finished, job.message = FAILED, time.time(), str(exc)
            self._log(f"[QUEUE] could not start {job.name}: {exc}")
        self.changed.emit()

    def tick(self) -> None:
        """Start every job that is due, in list order, while there are free slots."""
        now = datetime.now()
        if not self.paused:
            for j in self.jobs:
                if len(self.running()) >= self.max_parallel:
                    break
                if j.status in WAITING and (j.start_at is None or j.start_at <= now):
                    self._start(j)
        self.changed.emit()      # also refreshes elapsed times

    def on_status(self, data: Dict[str, object]) -> None:
        """Runner progress payload: {iid, status, snap, pct, eta, ...}."""
        j = self.by_path(str(data.get("iid", "")))
        if j is None or j.status in (STOPPED,):
            return
        status = str(data.get("status") or "")
        low = status.lower()
        if "pct" in data and data["pct"] is not None:
            p = _parse_pct(data["pct"])
            if p is not None:
                j.pct = p
        if data.get("snap"):
            j.snap = str(data["snap"])
        if data.get("eta"):
            j.eta = str(data["eta"])
        if low.startswith("completed"):
            j.status, j.pct, j.finished = COMPLETED, 100.0, time.time()
            self._log(f"[QUEUE] {j.name} completed")
        elif low.startswith(("error", "failed", "missing", "ssh error")):
            j.status, j.finished, j.message = FAILED, time.time(), status
            self._log(f"[QUEUE] {j.name} failed: {status}")
        elif low.startswith("stopped"):
            j.status, j.finished = STOPPED, time.time()
        elif j.status in WAITING:
            pass
        else:
            j.status = RUNNING
        self.changed.emit()
        if j.status in FINISHED:
            self.tick()            # a slot is free: start the next job
