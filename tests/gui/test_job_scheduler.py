"""Job queue: order, parallel limit, scheduled start, pause, stop and status mapping."""
from datetime import datetime, timedelta

import pytest

from core import job_scheduler as js


@pytest.fixture()
def sched():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    started, stopped = [], []
    s = js.JobScheduler(started.append, stopped.append, max_parallel=2)
    s._timer.stop()                       # tests drive tick() by hand
    s.started, s.stopped = started, stopped
    return s


def _status(s, job, status, **extra):
    s.on_status({"iid": job.path, "status": status, **extra})


def test_runs_at_most_max_parallel_in_order(sched):
    jobs = sched.submit(["a.yaml", "b.yaml", "c.yaml", "d.yaml"])
    assert sched.started == ["a.yaml", "b.yaml"]
    assert [j.status for j in jobs] == [js.RUNNING, js.RUNNING, js.QUEUED, js.QUEUED]
    _status(sched, jobs[0], "Completed")
    assert sched.started == ["a.yaml", "b.yaml", "c.yaml"]      # the freed slot goes to the next job
    assert jobs[0].status == js.COMPLETED and jobs[0].pct == 100.0


def test_scheduled_job_waits_for_its_time(sched):
    later = datetime.now() + timedelta(hours=1)
    (job,) = sched.submit(["x.yaml"], start_at=later)
    assert job.status == js.SCHEDULED and sched.started == []
    sched.reschedule(job.id, datetime.now() - timedelta(seconds=1))   # now due
    assert job.status == js.RUNNING and sched.started == ["x.yaml"]


def test_pause_blocks_new_jobs_and_resume_releases_them(sched):
    sched.pause(True)
    sched.submit(["a.yaml", "b.yaml"])
    assert sched.started == []
    sched.pause(False)
    assert sched.started == ["a.yaml", "b.yaml"]


def test_reorder_waiting_jobs(sched):
    sched.set_max_parallel(1)
    a, b, c = sched.submit(["a.yaml", "b.yaml", "c.yaml"])
    sched.move(c.id, -1)                                   # c before b
    assert [j.path for j in sched.jobs] == ["a.yaml", "c.yaml", "b.yaml"]
    sched.move(a.id, +1)                                   # a is running: cannot be moved
    assert sched.jobs[0] is a
    _status(sched, a, "Completed")
    assert sched.started[-1] == "c.yaml"


def test_stop_running_job_frees_slot_and_calls_runner(sched):
    sched.set_max_parallel(1)
    a, b = sched.submit(["a.yaml", "b.yaml"])
    sched.stop(a.id)
    assert sched.stopped == ["a.yaml"] and a.status == js.STOPPED
    sched.tick()
    assert b.status == js.RUNNING


def test_status_mapping_and_progress(sched):
    (job,) = sched.submit(["a.yaml"])
    _status(sched, job, "Running", pct="42.5%", snap="425/1000", eta="0:01:10")
    assert job.status == js.RUNNING and job.pct == 42.5 and job.snap == "425/1000" and job.eta == "0:01:10"
    _status(sched, job, "Error 1")
    assert job.status == js.FAILED and "Error" in job.message
    assert "1 failed" in sched.summary()


def test_run_now_skips_the_wait(sched):
    sched.set_max_parallel(1)
    a, b = sched.submit(["a.yaml", "b.yaml"])
    sched.run_now(b.id)                                    # explicit override of the order/limit
    assert b.status == js.RUNNING and "b.yaml" in sched.started


def test_remove_and_clear_finished(sched):
    a, b = sched.submit(["a.yaml", "b.yaml"])
    _status(sched, a, "Completed")
    sched.clear_finished()
    assert [j.path for j in sched.jobs] == ["b.yaml"]
    sched.remove(b.id)
    assert sched.jobs == [] and sched.stopped == ["b.yaml"]
