"""Closing the window while simulations run hides SHARC in the tray instead of quitting."""
import pytest

from core import job_scheduler as js


@pytest.fixture()
def tray(win):
    t = win.tray
    old_avail, old_msg = t.available, t.last_message
    t.available = True                      # the offscreen platform has no real tray
    t.last_message = ""
    yield t
    t.available = old_avail
    t.last_message = old_msg
    for job in list(win.scheduler.jobs):
        win.scheduler.remove(job.id)
    win.show()


def test_close_with_running_jobs_hides_and_notifies(win, tray, monkeypatch):
    monkeypatch.setattr(tray, "keep_running_enabled", staticmethod(lambda: True))
    win.scheduler.set_max_parallel(1)
    monkeypatch.setattr(win.scheduler, "_start_fn", lambda path: None)   # do not launch processes
    (job,) = win.scheduler.submit(["x.yaml"])
    assert tray.should_hide()
    win.show()
    win.close()                                       # the user closes the window
    assert not win.isVisible()                        # hidden, not destroyed
    assert "still running" in tray.last_message and "background" in tray.last_message
    assert job.status == js.RUNNING


def test_close_without_jobs_does_not_hide(win, tray, monkeypatch):
    monkeypatch.setattr(tray, "keep_running_enabled", staticmethod(lambda: True))
    assert tray.active_jobs() == 0 and not tray.should_hide()


def test_setting_can_turn_the_behaviour_off(win, tray, monkeypatch):
    monkeypatch.setattr(win.scheduler, "_start_fn", lambda path: None)
    win.scheduler.submit(["y.yaml"])
    monkeypatch.setattr(tray, "keep_running_enabled", staticmethod(lambda: False))
    assert not tray.should_hide()


def test_finishing_in_background_notifies(win, tray, monkeypatch):
    monkeypatch.setattr(win.scheduler, "_start_fn", lambda path: None)
    (job,) = win.scheduler.submit(["z.yaml"])
    tray._on_queue_changed()                          # records that work is active
    win.hide()
    win.scheduler.on_status({"iid": job.path, "status": "Completed"})
    assert "finished" in tray.last_message and "1 completed" in tray.last_message


def test_tray_tooltip_reports_progress(win, tray, monkeypatch):
    monkeypatch.setattr(win.scheduler, "_start_fn", lambda path: None)
    (job,) = win.scheduler.submit(["p.yaml"])
    win.scheduler.on_status({"iid": job.path, "status": "Running", "pct": "40%"})
    if tray.tray is not None:
        assert "1 running" in tray.tray.toolTip()
