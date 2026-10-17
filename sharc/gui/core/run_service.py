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

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = run_root() / stamp
    use_sweep = general.var_table.rowCount() > 0
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
