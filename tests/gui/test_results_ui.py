"""Results are recognised automatically and reachable from a completed job (menu, Enter, toolbar)."""
import os
import sys
import time

import pytest
import yaml

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import job_scheduler as js  # noqa: E402
from ui.components.jobs_panel import JobsPanel  # noqa: E402


def _act(menu, name):
    return next((a for a in menu.actions() if a.objectName() == name), None)


@pytest.fixture()
def queue(win):
    """A private queue + panel (never the app's own queue, which would start real simulations)."""
    sched = js.JobScheduler(lambda p: None, lambda p: None, max_parallel=1)
    sched.pause(True)
    panel = JobsPanel()
    panel.bind(sched)
    yield sched, panel
    sched._timer.stop()


def _complete(sched, job):
    sched.on_status({"iid": job.path, "status": "Completed"})


def test_completed_signal_fires_once(queue):
    sched, _ = queue
    seen = []
    sched.job_completed.connect(seen.append)
    job = sched.submit(["runs/a.yaml"])[0]
    _complete(sched, job)
    _complete(sched, job)                       # a repeated report must not re-trigger
    assert seen == [job.id]


def test_menu_offers_plot_only_for_completed_jobs(queue):
    sched, panel = queue
    job = sched.submit(["runs/a.yaml"])[0]
    panel.tree.topLevelItem(0).setSelected(True)
    assert not _act(panel._build_menu([job.id]), "act_plot_results").isEnabled()
    _complete(sched, job)
    panel.refresh()
    panel.tree.topLevelItem(0).setSelected(True)
    menu = panel._build_menu([job.id])
    assert _act(menu, "act_plot_results").isEnabled()
    assert _act(menu, "act_open_results").isEnabled()


def test_plot_action_emits_request_for_the_completed_job(queue):
    sched, panel = queue
    job = sched.submit(["runs/a.yaml"])[0]
    _complete(sched, job)
    panel.refresh()
    panel.tree.topLevelItem(0).setSelected(True)
    got = []
    panel.plot_requested.connect(got.append)
    _act(panel._build_menu([job.id]), "act_plot_results").trigger()
    assert got == [job.id]


def test_duplicate_queues_the_same_file_again(queue):
    sched, panel = queue
    job = sched.submit(["runs/a.yaml"])[0]
    panel.tree.topLevelItem(0).setSelected(True)
    _act(panel._build_menu([job.id]), "act_duplicate").trigger()
    assert [j.path for j in sched.jobs] == ["runs/a.yaml", "runs/a.yaml"]
    assert sched.jobs[0].id != sched.jobs[1].id


def _result_folder(tmp_path, name="out"):
    d = tmp_path / name
    d.mkdir(parents=True)
    (d / "imt_coupling_loss.csv").write_text("x\n1\n", encoding="utf-8")
    return d


@pytest.fixture()
def results_tab(win, monkeypatch):
    tab = win.tab_results
    monkeypatch.setattr(tab, "_schedule_update", lambda *a, **k: None)     # no real plot rendering here
    before = list(win.res_dirs) if hasattr(win, "res_dirs") else []
    yield tab
    tab.app.res_dirs[:] = before
    tab._refresh_dir_listbox()


def test_add_result_dir_ignores_duplicates(results_tab, tmp_path):
    d = _result_folder(tmp_path)
    assert results_tab.add_result_dir(d) is True
    assert results_tab.add_result_dir(d) is False
    assert results_tab.app.res_dirs.count(str(d)) == 1
    assert results_tab.lb_dirs.count() == len(results_tab.app.res_dirs)


def test_detect_results_adds_found_folders_and_keeps_manual_ones(results_tab, tmp_path):
    manual = tmp_path / "somewhere_else"
    manual.mkdir()
    results_tab.add_result_dir(manual)
    a = _result_folder(tmp_path / "root", "run_a")
    added = results_tab.detect_results(roots=[tmp_path / "root"])
    assert added == 1
    assert str(a.resolve()) in results_tab.app.res_dirs
    assert str(manual) in results_tab.app.res_dirs                      # manual choice is untouched
    assert results_tab.detect_results(roots=[tmp_path / "root"]) == 0   # second scan finds nothing new


def test_completed_job_results_reach_the_results_tab(win, results_tab, tmp_path):
    """job completed -> workbench locates its folder -> Results lists it and the page opens."""
    out = _result_folder(tmp_path)
    y = tmp_path / "job.yaml"
    y.write_text(yaml.safe_dump({"general": {"output_dir": str(out), "overwrite_output": True}}), encoding="utf-8")
    job = js.Job(path=str(y), name="job", id=987654, status=js.COMPLETED, finished=time.time())
    win.scheduler.jobs.append(job)
    try:
        win._switch_page("general", "General Settings")
        assert win.plot_job_results(job.id) is True
        assert str(out) in win.res_dirs
        assert win.current_key == "results"
    finally:
        win.scheduler.jobs.remove(job)


def test_rerun_into_same_folder_forces_a_refresh(win, results_tab, tmp_path, monkeypatch):
    """Overwrite mode reuses one folder: a second completion must drop cached data, not just say 'listed'."""
    out = _result_folder(tmp_path)
    y = tmp_path / "job.yaml"
    y.write_text(yaml.safe_dump({"general": {"output_dir": str(out), "overwrite_output": True}}), encoding="utf-8")
    job = js.Job(path=str(y), name="job", id=987656, status=js.COMPLETED, finished=time.time())
    win.scheduler.jobs.append(job)
    calls = []
    monkeypatch.setattr(results_tab, "_schedule_update", lambda *a, **k: calls.append(k))
    try:
        win.plot_job_results(job.id, switch=False)
        win.plot_job_results(job.id, switch=False)
        assert calls[-1].get("force_refresh") is True
    finally:
        win.scheduler.jobs.remove(job)


def test_job_without_results_reports_instead_of_failing(win, results_tab, tmp_path):
    y = tmp_path / "job.yaml"
    y.write_text(yaml.safe_dump({"general": {"output_dir": str(tmp_path / "nothing"), "overwrite_output": True}}),
                 encoding="utf-8")
    job = js.Job(path=str(y), name="job", id=987655, status=js.COMPLETED, finished=time.time())
    win.scheduler.jobs.append(job)
    try:
        assert win.plot_job_results(job.id) is False
        assert "No result files found" in win.messages_view.toPlainText()
    finally:
        win.scheduler.jobs.remove(job)
