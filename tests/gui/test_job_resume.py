"""Job queue: resuming stopped/failed jobs from their checkpoint, manually and automatically."""
from types import SimpleNamespace

import pytest

from core import job_scheduler as js


@pytest.fixture()
def sched(monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    started, resumed, stopped = [], [], []
    s = js.JobScheduler(started.append, stopped.append, max_parallel=2, resume_fn=resumed.append)
    s._timer.stop()
    s.auto_resume_delay_s = 0
    s.started, s.resumed, s.stopped = started, resumed, stopped
    s.ckpt = {}                            # path -> checkpoint snapshot (None: no checkpoint)

    def fake(path):
        snap = s.ckpt.get(path)
        return None if snap is None else SimpleNamespace(snapshot=snap, pct=snap, resumable=True)
    monkeypatch.setattr(js, "checkpoint_of", fake)
    return s


def _status(s, job, status):
    s.on_status({"iid": job.path, "status": status})


def test_manual_resume_of_a_stopped_job(sched):
    (job,) = sched.submit(["a.yaml"])
    sched.stop(job.id)
    assert not sched.can_resume(job.id)             # no checkpoint yet
    sched.ckpt["a.yaml"] = 40
    assert sched.can_resume(job.id)
    assert sched.resume(job.id)
    assert sched.resumed == ["a.yaml"] and job.status == js.RUNNING and job.pct == 40


def test_crash_is_resumed_automatically_while_progressing(sched):
    sched.auto_resume = True
    (job,) = sched.submit(["a.yaml"])
    sched.ckpt["a.yaml"] = 30
    _status(sched, job, "Error 1")
    sched.tick()
    assert sched.resumed == ["a.yaml"] and job.auto_resumes == 1 and job.status == js.RUNNING
    _status(sched, job, "Error 1")                   # crashed again with no new checkpoint
    assert job.status == js.FAILED and sched.resumed == ["a.yaml"]


def test_no_auto_resume_without_checkpoint_or_when_disabled(sched):
    a, b = sched.submit(["a.yaml", "b.yaml"])
    _status(sched, a, "Error 1")                     # crashed before any checkpoint
    assert a.status == js.FAILED
    sched.auto_resume = False
    sched.ckpt["b.yaml"] = 50
    _status(sched, b, "Error 1")
    assert b.status == js.FAILED and sched.resumed == []


def test_auto_resume_gives_up_after_max_attempts(sched):
    sched.max_auto_resumes = 2
    (job,) = sched.submit(["a.yaml"])
    for snap in (10, 20, 30):
        sched.ckpt["a.yaml"] = snap
        _status(sched, job, "Error 1")
        sched.tick()
    assert job.status == js.FAILED and len(sched.resumed) == 2


def test_jobs_panel_resume_button_and_context_menu(sched):
    from ui.components.jobs_panel import JobsPanel
    panel = JobsPanel()
    panel.bind(sched)
    (job,) = sched.submit(["a.yaml"])
    sched.stop(job.id)
    sched.ckpt["a.yaml"] = 50
    panel.refresh()
    panel.tree.selectAll()
    menu = panel._build_menu([job.id])
    act = next(a for a in menu.actions() if a.objectName() == "act_resume")
    assert act.isEnabled()
    panel.btn_resume.click()
    assert sched.resumed == ["a.yaml"] and job.status == js.RUNNING


def test_resume_dialog_queues_or_discards_interrupted_runs(tmp_path, monkeypatch, sched):
    from sharc.support import checkpoint
    from ui.shell import resume_dialog as rd
    y = tmp_path / "sim.yaml"
    y.write_text("general: {}\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    checkpoint.save(checkpoint.Checkpoint(
        param_file=str(y), param_hash=checkpoint.file_hash(str(y)),
        output_dir=str(out), snapshot=20, num_snapshots=100, pid=99999999))
    monkeypatch.setenv("SHARC_GUI_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(checkpoint, "pid_alive", lambda _pid: False)
    app = SimpleNamespace(scheduler=sched)

    runs = rd.interrupted_runs(app)
    assert len(runs) == 1 and runs[0].snapshot == 20
    dlg = rd.ResumeDialog(runs)
    assert len(dlg.checked()) == 1
    monkeypatch.setattr(rd.ResumeDialog, "exec", lambda self: rd.QDialog.Accepted)
    assert rd.offer_resume_interrupted(app) == 1
    assert sched.resumed == [str(y)]
