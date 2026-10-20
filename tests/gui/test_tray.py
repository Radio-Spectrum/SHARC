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


# ---------------------------------------------------------------- close-button dialog
@pytest.fixture()
def close_pref():
    """Restore the user's real close-button preference after a test changes it."""
    from ui.shell.tray import TrayController
    old = TrayController.close_action()
    yield TrayController
    TrayController.set_close_action(old)


@pytest.mark.parametrize("value", ["minimize", "quit"])
def test_remembered_close_action_skips_the_dialog(tray, close_pref, value, monkeypatch):
    close_pref.set_close_action(value)
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("dialog must not open"))
    assert tray.close_choice() == value


def test_invalid_stored_close_action_falls_back_to_ask(close_pref):
    from PySide6.QtCore import QSettings
    QSettings("SHARC", "GUI").setValue("tray/close_action", "bogus")
    assert close_pref.close_action() == "ask"


@pytest.mark.parametrize("label,expected", [("Minimize to tray", "minimize"), ("Quit SHARC", "quit"), ("Cancel", "cancel")])
def test_dialog_buttons_map_to_choices(tray, close_pref, label, expected, monkeypatch):
    close_pref.set_close_action("ask")
    from PySide6.QtWidgets import QMessageBox

    def fake_exec(self):
        for b in self.buttons():
            if b.text() == label:
                self._clicked = b
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: getattr(self, "_clicked", None))
    assert tray.close_choice() == expected
    assert close_pref.close_action() == "ask"          # not remembered unless the box is ticked


def test_interactive_close_minimizes_to_tray(win, tray, close_pref, monkeypatch):
    monkeypatch.delenv("SHARC_GUI_NO_RESTORE", raising=False)
    monkeypatch.setattr(tray, "close_choice", lambda: "minimize")
    monkeypatch.setattr(win, "saveGeometry", lambda: b"")           # keep the test from touching saved layout
    monkeypatch.setattr(win, "saveState", lambda *_a: b"")
    from PySide6.QtCore import QSettings
    monkeypatch.setattr(QSettings, "setValue", lambda *a, **k: None)
    win.show()
    win.close()
    assert not win.isVisible()
    assert "system tray" in tray.last_message


def test_interactive_close_cancel_keeps_window(win, tray, monkeypatch):
    monkeypatch.delenv("SHARC_GUI_NO_RESTORE", raising=False)
    monkeypatch.setattr(tray, "close_choice", lambda: "cancel")
    from PySide6.QtCore import QSettings
    monkeypatch.setattr(QSettings, "setValue", lambda *a, **k: None)
    win.show()
    win.close()
    assert win.isVisible()
