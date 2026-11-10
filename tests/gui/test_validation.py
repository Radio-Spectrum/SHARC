"""Scenario validation: the default scenario is clean, each rule fires on its own broken input."""
import copy
import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import validation as v  # noqa: E402


@pytest.fixture()
def base(win):
    return copy.deepcopy(win.tab_preview._current_yaml())


def _msgs(issues, sev=v.ERROR):
    return [(i.page, i.field) for i in issues if i.severity == sev]


def test_default_scenario_has_no_static_errors(base):
    assert _msgs(v.static_issues(base)) == []


def test_default_scenario_passes_engine_check(base):
    issues = v.validate(base)
    assert not v.has_errors(issues), issues


def test_zero_snapshots_is_error(base):
    base["general"]["num_snapshots"] = 0
    assert ("general", "Number of snapshots") in _msgs(v.static_issues(base))


def test_no_interference_mode_is_error(base):
    base["general"]["enable_cochannel"] = False
    base["general"]["enable_adjacent_channel"] = False
    assert ("general", "Co-channel / adjacent channel") in _msgs(v.static_issues(base))


def test_missing_imt_bandwidth_is_error(base):
    base["imt"]["bandwidth"] = None
    assert ("imt", "Frequency / bandwidth") in _msgs(v.static_issues(base))


def test_missing_database_file_is_error(base):
    base["database"] = {"database_file_name": "no_such_dir/no_such_file.csv"}
    assert ("database", "Database file") in _msgs(v.static_issues(base))


def test_non_overlapping_cochannel_bands_warn(base):
    base["general"]["enable_cochannel"] = True
    base["general"]["enable_adjacent_channel"] = False
    base["imt"]["frequency"], base["imt"]["bandwidth"] = 1000.0, 10.0
    sys_key = base["general"]["system"].lower()
    base[sys_key]["frequency"], base[sys_key]["bandwidth"] = 9000.0, 10.0
    assert ("general", "Co-channel") in _msgs(v.static_issues(base), v.WARNING)


def test_engine_rejection_is_reported_not_raised(base):
    base["imt"]["topology"]["type"] = "NOT_A_TOPOLOGY"
    issues = v.engine_issues(base)
    assert v.has_errors(issues) and "engine rejected" in issues[0].message


def test_validate_action_fills_problems_dock(win):
    issues = win.check_scenario(show=False)
    assert not v.has_errors(issues), issues
    assert win.problems_panel.rowCount() == len(issues)
    win.var_snaps.set("0")
    issues = win.check_scenario(show=False)
    assert win.problems_panel.counts()[0] >= 1
    assert win.problems_panel.item(0, 0).text() == "Error"        # errors sort first
    errors, _ = win.problems_panel.counts()
    assert win.dock_problems.windowTitle() == f"Problems ({errors} errors, 0 warnings)"


def test_double_click_on_problem_opens_its_page(win):
    win.var_snaps.set("0")
    win.check_scenario(show=False)
    win._switch_page("imt", "IMT System")
    row = next(r for r in range(win.problems_panel.rowCount()) if win.problems_panel.item(r, 1).text() == "general")
    win.problems_panel.cellDoubleClicked.emit(row, 0)
    assert win.current_key == "general"


def test_run_is_blocked_when_scenario_has_errors(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from core import run_service
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    submitted = []
    monkeypatch.setattr(win.scheduler, "submit", lambda *a, **k: submitted.append(a))
    win.var_snaps.set("0")
    assert run_service.start_run(win) is False
    assert shown and "not started" in shown[0]
    assert submitted == []


def test_engine_check_is_skipped_when_static_errors_exist(base, monkeypatch):
    base["general"]["num_snapshots"] = 0
    monkeypatch.setattr(v, "engine_issues", lambda d: pytest.fail("engine must not run"))
    assert v.has_errors(v.validate(base))
