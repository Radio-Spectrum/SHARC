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
    resume: bool = False             # next start continues from the last checkpoint
    auto_resumes: int = 0            # automatic resumes already attempted after failures
    last_ckpt_snap: int = -1         # checkpoint snapshot at the last automatic resume

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


def checkpoint_of(path: str):
    """Resumable checkpoint of the last run of `path` (None when it cannot be resumed)."""
    try:
        from sharc.support import checkpoint
    except Exception:  # noqa: BLE001  (engine not importable: no resume)
        return None
    ckpt = checkpoint.find(path)
    return ckpt if ckpt is not None and ckpt.resumable else None


class JobScheduler(QObject):
    """Queue of simulation jobs."""

    changed = Signal()
    job_completed = Signal(int)          # job id, emitted once when a job reaches Completed
    job_started = Signal(int)            # job id, emitted when a job starts running
    job_failed = Signal(int)             # job id, emitted once when a job reaches Failed
    job_retrying = Signal(int)           # job id, failed but will be resumed automatically

    def __init__(self, start_fn: Callable[[str], None], stop_fn: Callable[[str], None],
                 log: Callable[[str], None] = lambda _m: None, max_parallel: int = 2, parent=None,
                 resume_fn: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self._start_fn, self._stop_fn, self._log = start_fn, stop_fn, log
        self._resume_fn = resume_fn
        self.jobs: List[Job] = []
        self.max_parallel = max(1, int(max_parallel))
        self.paused = False
        # automatic resume of jobs that crash (needs resume_fn and a checkpoint)
        self.auto_resume = True
        self.max_auto_resumes = 3
        self.auto_resume_delay_s = 15
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
    def submit(self, paths: List[str], start_at: Optional[datetime] = None, resume: bool = False) -> List[Job]:
        created = []
        for p in paths:
            parts = os.path.normpath(p).split(os.sep)
            job = Job(path=p, name="/".join(parts[-2:]), id=next(_ids), created=time.time(),
                      start_at=start_at, status=SCHEDULED if start_at else QUEUED, resume=resume)
            self.jobs.append(job)
            created.append(job)
        self._log(f"[QUEUE] {len(created)} job(s) " + ("queued to resume" if resume else "added")
                  + (f", scheduled for {start_at:%Y-%m-%d %H:%M}" if start_at else ""))
        self.tick()
        return created

    # ------------------------------------------------------------- resume
    def can_resume(self, job_id: int) -> bool:
        """A stopped/failed job whose run left a checkpoint it can continue from."""
        j = self.job(job_id)
        return (j is not None and self._resume_fn is not None
                and j.status in (FAILED, STOPPED) and checkpoint_of(j.path) is not None)

    def resume(self, job_id: int) -> bool:
        """Queue a stopped/failed job again, continuing from its last checkpoint."""
        j = self.job(job_id)
        if j is None or not self.can_resume(job_id):
            return False
        ckpt = checkpoint_of(j.path)
        j.resume, j.start_at, j.status, j.message = True, None, QUEUED, ""
        j.pct = ckpt.pct if ckpt else j.pct
        self._log(f"[QUEUE] {j.name} queued to resume from snapshot {ckpt.snapshot if ckpt else '?'}")
        self.tick()
        return True

    def _maybe_auto_resume(self, j: Job) -> bool:
        """After a crash: queue an automatic resume while the run keeps making progress."""
        if not self.auto_resume or self._resume_fn is None or j.auto_resumes >= self.max_auto_resumes:
            return False
        ckpt = checkpoint_of(j.path)
        if ckpt is None or ckpt.snapshot <= j.last_ckpt_snap:
            return False                     # no checkpoint, or no progress since the last retry
        j.auto_resumes += 1
        j.last_ckpt_snap = ckpt.snapshot
        j.resume = True
        j.start_at = datetime.fromtimestamp(time.time() + self.auto_resume_delay_s)
        j.status = SCHEDULED
        self._log(f"[QUEUE] {j.name} failed ({j.message}); resuming automatically from snapshot "
                  f"{ckpt.snapshot} in {self.auto_resume_delay_s} s "
                  f"(attempt {j.auto_resumes}/{self.max_auto_resumes})")
        return True

    def duplicate(self, job_id: int) -> Optional[Job]:
        """Queue the same configuration file again (a new job that starts as soon as a slot is free)."""
        j = self.job(job_id)
        if j is None:
            return None
        return self.submit([j.path])[0]

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
        resuming = job.resume and self._resume_fn is not None
        job.status, job.started, job.finished = RUNNING, time.time(), None
        if not resuming:
            job.pct = 0.0
        job.snap, job.eta = "--", "--"
        self._log(f"[QUEUE] {'resuming' if resuming else 'starting'} {job.name}")
        started = True
        try:
            (self._resume_fn if resuming else self._start_fn)(job.path)
        except Exception as exc:  # noqa: BLE001
            started = False
            job.status, job.finished, job.message = FAILED, time.time(), str(exc)
            self._log(f"[QUEUE] could not start {job.name}: {exc}")
        self.changed.emit()
        (self.job_started if started else self.job_failed).emit(job.id)

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
        newly_completed = newly_failed = retrying = False
        if low.startswith("completed"):
            newly_completed = j.status != COMPLETED
            j.status, j.pct, j.finished = COMPLETED, 100.0, time.time()
            self._log(f"[QUEUE] {j.name} completed")
        elif low.startswith(("error", "failed", "missing", "ssh error")):
            if j.status == RUNNING:
                j.finished, j.message = time.time(), status
                retrying = self._maybe_auto_resume(j)
            if not retrying:
                newly_failed = j.status != FAILED
                j.status, j.finished, j.message = FAILED, time.time(), status
                self._log(f"[QUEUE] {j.name} failed: {status}"
                          + ("  (right-click > Resume to continue from the last checkpoint)"
                             if self.can_resume(j.id) else ""))
        elif low.startswith("stopped"):
            j.status, j.finished = STOPPED, time.time()
        elif j.status in WAITING:
            pass
        else:
            j.status = RUNNING
        self.changed.emit()
        if newly_completed:
            self.job_completed.emit(j.id)
        if newly_failed:
            self.job_failed.emit(j.id)
        if retrying:
            self.job_retrying.emit(j.id)
        if j.status in FINISHED or retrying:
            self.tick()            # a slot is free: start the next job
