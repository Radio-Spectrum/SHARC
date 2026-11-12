"""Run review dialog, resource plan and telemetry widget."""
import os
import sys
import types

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import preflight as pf  # noqa: E402
from core.validation import Issue  # noqa: E402


def _scene(n_bs=57, n_ue=570):
    return types.SimpleNamespace(bs=types.SimpleNamespace(num_stations=n_bs),
                                 ue=types.SimpleNamespace(num_stations=n_ue))


DATA = {"general": {"num_snapshots": 100, "system": "RAS", "seed": 7},
        "imt": {"frequency": 2600, "bandwidth": 20, "topology": {"type": "MACROCELL"}}}


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_sweep_runs_follow_general_tab_rule():
    assert pf.count_sweep_runs([]) == 1
    assert pf.count_sweep_runs([(3, 3), (2, 2)]) == 6
    assert pf.count_sweep_runs([(3, 2), (2, 2)]) == 2     # mismatched row is ignored, like the generator


def test_plan_numbers_and_time_needs_probe(tmp_path):
    plan = pf.build_plan(DATA, _scene(), runs=4, parallel=2, out_root=str(tmp_path))
    assert (plan.n_bs, plan.n_ue, plan.snapshots, plan.workers) == (57, 570, 100, 2)
    assert plan.time_seconds is None and not plan.measured
    assert plan.ram_total_bytes == 2 * plan.ram_per_proc_bytes
    assert plan.free_disk_bytes > 0
    assert plan.out_per_snapshot_bytes is None
    assert plan.disk_total_bytes == 4 * 11_500            # only the fixed files are known before the test


def test_probe_replaces_estimates_and_time_uses_waves(tmp_path):
    plan = pf.build_plan(DATA, _scene(), runs=3, parallel=2, out_root=str(tmp_path))
    res = pf.ProbeResult(ok=True, snapshots=10, seconds_per_snapshot=2.0, setup_seconds=10.0,
                         peak_rss_bytes=500 * 2**20, out_bytes=11_500 + 90_000)
    pf.apply_probe(plan, res)
    assert plan.measured and plan.ram_per_proc_bytes == 500 * 2**20
    assert plan.out_per_snapshot_bytes == 9_000
    assert plan.disk_total_bytes == 3 * (11_500 + 9_000 * 100)   # 100 snapshots = ten flushes of 10
    assert plan.time_seconds == 2 * (10 + 100 * 2.0)       # 3 runs, 2 workers -> 2 waves


def test_probe_shorter_than_one_flush_learns_no_csv_slope(tmp_path):
    plan = pf.build_plan(DATA, _scene(), runs=1, parallel=1, out_root=str(tmp_path))
    pf.apply_probe(plan, pf.ProbeResult(ok=True, snapshots=8, seconds_per_snapshot=1.0, out_bytes=11_450))
    assert plan.measured and plan.out_per_snapshot_bytes is None


def test_failed_probe_changes_nothing(tmp_path):
    plan = pf.build_plan(DATA, _scene(), runs=1, parallel=1, out_root=str(tmp_path))
    before = plan.ram_per_proc_bytes
    pf.apply_probe(plan, pf.ProbeResult(ok=False, error="x"))
    assert not plan.measured and plan.ram_per_proc_bytes == before


def test_formatters():
    assert pf.fmt_bytes(1536) == "1.5 KB"
    assert pf.fmt_duration(3725) == "1h 02m"
    assert pf.fmt_duration(None).startswith("run the test")


def test_dialog_blocks_start_on_errors_and_flags_warnings(tmp_path):
    _app()
    from ui.shell.preflight_dialog import PreflightDialog
    plan = pf.build_plan(DATA, _scene(), runs=1, parallel=1, out_root=str(tmp_path))

    bad = PreflightDialog(None, DATA, plan, [Issue("error", "general", "System", "no victim system selected")])
    assert not bad.btn_go.isEnabled() and not bad.btn_probe.isEnabled()

    warn = PreflightDialog(None, DATA, plan, [Issue("warning", "general", "Co-channel", "bands do not overlap")])
    assert warn.btn_go.isEnabled() and warn.btn_go.text() == "Start anyway"

    ok = PreflightDialog(None, DATA, plan, [])
    assert ok.btn_go.isEnabled() and ok.btn_go.text() == "Start simulation"
    assert ok.tbl_res.item(3, 2).text() == "needs test"


def test_dialog_probe_result_updates_figures(tmp_path):
    _app()
    from ui.shell.preflight_dialog import PreflightDialog
    plan = pf.build_plan(DATA, _scene(), runs=1, parallel=1, out_root=str(tmp_path))
    dlg = PreflightDialog(None, DATA, plan, [])
    dlg._on_done(pf.ProbeResult(ok=True, snapshots=10, seconds_per_snapshot=1.0, setup_seconds=5.0,
                                peak_rss_bytes=2**30, out_bytes=101_500))
    assert dlg.bar.value() == 100 and "finished" in dlg.bar.format()
    assert plan.measured and dlg.tbl_res.item(0, 2).text() == "measured"
    assert dlg.tbl_res.item(3, 1).text() == "1m 45s"
    dlg._on_done(pf.ProbeResult(ok=False, error="boom", log_tail="trace"))
    assert dlg.btn_go.text() == "Start anyway"
    assert dlg.log.toPlainText().startswith("boom")
    assert dlg.bar.isHidden()                               # a failed test leaves no misleading bar


def test_bar_is_paced_by_time_and_held_below_100_until_done(tmp_path):
    _app()
    import time
    from ui.shell.preflight_dialog import PreflightDialog
    plan = pf.build_plan(DATA, _scene(), runs=1, parallel=1, out_root=str(tmp_path))
    dlg = PreflightDialog(None, DATA, plan, [])
    dlg._t0 = time.time() - 3.5                             # half of the 7 s default
    dlg._advance_bar()
    assert 45 <= dlg.bar.value() <= 55
    dlg._t0 = time.time() - 100
    dlg._advance_bar()
    assert dlg.bar.value() == 95                            # never 100 before the engine exits
    dlg._on_phase("running")
    assert "Running snapshots" in dlg.bar.format()


@pytest.mark.slow
def test_real_probe_runs_the_engine_on_the_default_scenario(tmp_path, win):
    import threading
    win.tab_general.e_snaps.setText("20")
    data = win.tab_preview._current_yaml()
    res = pf.run_probe(data, threading.Event(), work_root=str(tmp_path))
    assert res.ok, res.log_tail
    assert res.snapshots == 10                                  # one CSV flush period
    assert res.seconds_per_snapshot > 0 and res.setup_seconds > 0   # start-up split from the loop
    assert res.peak_rss_bytes > 50 * 2**20                      # needs psutil
    assert res.out_bytes > 11_500 + 10_000                      # CSVs were written
    plan = pf.build_plan(data, _scene(), runs=1, parallel=1, out_root=str(tmp_path))
    pf.apply_probe(plan, res)
    assert plan.out_per_snapshot_bytes and plan.time_seconds
    assert not [p for p in tmp_path.iterdir()], "the probe folder must be removed"


def test_telemetry_reports_machine_and_idle_simulator():
    pytest.importorskip("psutil")
    _app()
    from ui.components.telemetry import TelemetryWidget
    w = TelemetryWidget(lambda: None, lambda: os.getcwd(), interval_ms=60000)
    w.refresh()
    assert w.lbl_sys.text().startswith("CPU") and "DISK" in w.lbl_sys.text()
    assert w.lbl_sim.text() == "SIM idle"
