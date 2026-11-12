"""Regression: the Plotly preview stayed on "Preparing Plot... 0%" because the render thread used
QTimer.singleShot, which never fires from a thread without an event loop."""
import os
import sys
import threading
import time

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("plotly")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _pump(app, cond, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.02)
    return cond()


def test_render_thread_reaches_the_gui_and_shows_the_image(win, monkeypatch):
    import plotly.graph_objects as go
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    tab = win.tab_results
    steps = []
    monkeypatch.setattr(
        tab, "_create_plotly_fig",
        lambda progress_callback=None, **k: (progress_callback and progress_callback(40.0),
                                             go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 4, 9])))[1])
    tab._ui_progress.connect(steps.append)
    tab.lbl_preview.setText("Preparing Plot...")
    t = threading.Thread(target=tab._render_worker, args=(400, 300, False), daemon=True)
    t.start()
    assert _pump(app, lambda: tab.lbl_preview.pixmap() is not None and not tab.lbl_preview.pixmap().isNull()), \
        f"the image never arrived; label says {tab.lbl_preview.text()!r}"
    t.join(10)
    assert 40 in steps                                   # progress crossed the thread boundary too
    assert tab.pb_loading.isHidden()


def test_render_error_is_shown_instead_of_hanging(win, monkeypatch):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    tab = win.tab_results

    def boom(**k):
        raise RuntimeError("no data")
    monkeypatch.setattr(tab, "_create_plotly_fig", boom)
    tab.lbl_preview.clear()
    tab.lbl_preview.setText("Preparing Plot...")
    threading.Thread(target=tab._render_worker, args=(400, 300, False), daemon=True).start()
    assert _pump(app, lambda: "Plot Error" in tab.lbl_preview.text())
    assert "RuntimeError: no data" in tab.lbl_preview.text()


def test_dropped_render_does_not_leave_preparing_message(win):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    tab = win.tab_results
    tab.lbl_preview.setText("Preparing Plot...")
    assert tab._render_lock.acquire(blocking=False)
    try:
        threading.Thread(target=tab._render_worker, args=(400, 300, False), daemon=True).start()
        assert _pump(app, lambda: "already being prepared" in tab.lbl_preview.text(), 10)
    finally:
        tab._render_lock.release()
