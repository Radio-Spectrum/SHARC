"""Rodar simulação em um clique: os YAMLs viram detalhe interno.

`start_run(app)` gera as configurações (com a varredura de parâmetros, se
houver) em uma pasta gerenciada, aponta o Execution Engine para ela e dispara
os jobs. O usuário só vê o progresso na tabela de jobs, nas Messages e na
barra de status.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from core.state import get_sharc_root


def run_root() -> Path:
    """Pasta onde as execuções do GUI guardam as configurações geradas."""
    root = Path(os.environ.get("SHARC_GUI_RUNS_DIR") or Path(get_sharc_root()) / ".sharc_gui" / "runs")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _review_run(app, general, issues, use_sweep: bool) -> bool:
    """Show the review dialog (parameters, resources, test run). True = the user confirmed.

    Skipped when SHARC_GUI_NO_REVIEW is set or the scene cannot be built (the validation gate
    above already reported why), so a failure here never blocks a run by itself.
    """
    if os.environ.get("SHARC_GUI_NO_REVIEW"):
        return True
    from PySide6.QtCore import QSettings
    if str(QSettings("SHARC", "GUI").value("sim/review", True)).lower() in ("false", "0", "no"):
        return True
    from core import preflight
    from core.engine_scene import EngineSceneError, build_engine_scene
    from ui.tabs.assets.general_tab.general_tools import parse_list_safe
    from ui.shell.preflight_dialog import PreflightDialog
    from PySide6.QtWidgets import QDialog

    try:
        data = app.tab_preview._current_yaml()
        scene = build_engine_scene(data)          # cached by the validation that just ran
    except (EngineSceneError, AttributeError):
        return True
    rows = []
    if use_sweep:
        t = general.var_table
        for r in range(t.rowCount()):
            rows.append((len(parse_list_safe(t.item(r, 1).text(), [])),
                         len(parse_list_safe(t.item(r, 2).text(), []))))
    parallel = app._saved_parallel() if hasattr(app, "_saved_parallel") else 1
    plan = preflight.build_plan(data, scene, preflight.count_sweep_runs(rows), parallel, str(run_root()))
    return PreflightDialog(app, data, plan, issues).exec() == QDialog.Accepted


def start_run(app, start_at=None) -> bool:
    """Gera as configurações em segundo plano e inicia a simulação. Retorna True se iniciou."""
    general = getattr(app, "tab_general", None)
    runner = getattr(app, "tab_runner", None)
    if general is None or runner is None:
        return False

    if not runner.rb_local.isChecked():
        QMessageBox.information(
            app, "Run",
            "Remote (SSH) mode needs to upload the files to the server. "
            "Use the Execution Engine for that case.")
        app._switch_page("runner", "Execution Engine")
        return False

    if hasattr(app, "check_scenario"):
        from core.validation import has_errors
        issues = app.check_scenario()
        if has_errors(issues):
            n = sum(1 for i in issues if i.severity == "error")
            QMessageBox.warning(
                app, "Run",
                f"The scenario has {n} error(s), so the simulation was not started.\n"
                "See the Problems tab (double-click a row to go to the page).")
            return False

    use_sweep = general.var_table.rowCount() > 0
    if not _review_run(app, general, issues if hasattr(app, "check_scenario") else [], use_sweep):
        return False

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = run_root() / stamp
    try:
        files = general._internal_save_logic(use_combinations=use_sweep, save_dir=run_dir, quiet=True)
    except Exception as exc:  # invalid parameter, etc.
        QMessageBox.critical(app, "Run", f"Could not prepare the simulation:\n{exc}")
        return False
    if not files:
        QMessageBox.warning(app, "Run", "No configuration was generated. Review the parameters.")
        return False

    app._safe_log(f"[RUN] {len(files)} simulation(s) prepared in {run_dir}")
    runner.e_run_folder.setText(str(run_dir))

    from ui.tabs.assets.runner_tab.runner_actions import scan_yaml_files
    scan_yaml_files(runner)            # creates the rows the runner updates while the jobs run
    scheduler = getattr(app, "scheduler", None)
    if scheduler is None:              # no queue available: fall back to running right away
        from ui.tabs.assets.runner_tab.runner_actions import run_selected
        runner.tree.selectAll()
        run_selected(runner)
        return True
    scheduler.submit(files, start_at=start_at)
    from PySide6.QtCore import QSettings
    if str(QSettings("SHARC", "GUI").value("sim/show_jobs", True)).lower() in ("true", "1", "yes"):
        app.dock_jobs.show()
        app.dock_jobs.raise_()
    return True


def stop_run(app) -> None:
    """Stop every running or waiting job."""
    scheduler = getattr(app, "scheduler", None)
    if scheduler is not None:
        for job in list(scheduler.jobs):
            if job.status in ("Running", "Queued", "Scheduled"):
                scheduler.stop(job.id)
        return
    runner = getattr(app, "tab_runner", None)
    if runner is None:
        return
    from ui.tabs.assets.runner_tab.runner_actions import stop_selected
    runner.tree.selectAll()
    stop_selected(runner)
