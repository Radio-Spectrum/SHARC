"""Resume simulations that were cut short (crash, SHARC closed, power loss...).

Each run leaves a checkpoint next to its YAML (`<yaml>.resume.json`, see
`sharc/support/checkpoint.py`). On start-up (and from File > Resume Interrupted Simulations)
this dialog lists the runs under the GUI runs folder that stopped before the end and are not
running any more, and queues the chosen ones to continue from their last checkpoint.
"""
from __future__ import annotations

import os
from datetime import datetime

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)


def interrupted_runs(app) -> list:
    """Interrupted, resumable runs that are not already in the job queue."""
    try:
        from sharc.support import checkpoint
        from core.run_service import run_root
    except Exception:  # noqa: BLE001
        return []
    busy = set()
    sched = getattr(app, "scheduler", None)
    if sched is not None:
        from core import job_scheduler as js
        busy = {os.path.normcase(os.path.abspath(j.path)) for j in sched.jobs
                if j.status in js.ACTIVE + js.WAITING}
    return [c for c in checkpoint.find_interrupted(str(run_root()))
            if os.path.normcase(os.path.abspath(c.param_file)) not in busy]


class ResumeDialog(QDialog):
    def __init__(self, runs: list, parent=None):
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.setWindowTitle("Resume interrupted simulations")
        self.resize(720, 340)
        self.runs = runs
        self.discard = False
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"{len(runs)} simulation(s) stopped before the end (crash, SHARC closed, power loss...).\n"
            "Checked runs continue from their last checkpoint; the samples already computed are kept."))
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels(["Simulation", "Progress", "Last checkpoint", "Results folder"])
        for col, w in enumerate((240, 120, 130, 200)):
            self.tree.setColumnWidth(col, w)
        for c in runs:
            parts = os.path.normpath(c.param_file).split(os.sep)
            it = QTreeWidgetItem(self.tree, [
                "/".join(parts[-2:]),
                f"{c.snapshot}/{c.num_snapshots} ({c.pct:.0f}%)",
                datetime.fromtimestamp(c.updated).strftime("%Y-%m-%d %H:%M") if c.updated else "--",
                c.output_dir,
            ])
            it.setToolTip(0, c.param_file)
            it.setToolTip(3, c.output_dir)
            it.setCheckState(0, Qt.Checked)
        lay.addWidget(self.tree, 1)

        box = QDialogButtonBox()
        self.btn_resume = box.addButton("Resume checked", QDialogButtonBox.AcceptRole)
        self.btn_resume.setIcon(qta.icon("mdi.restore", color="#4F9DDE"))
        btn_discard = QPushButton("Discard checked")
        btn_discard.setToolTip("Forget these checkpoints (the partial results stay on disk)")
        box.addButton(btn_discard, QDialogButtonBox.DestructiveRole)
        box.addButton("Later", QDialogButtonBox.RejectRole)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        btn_discard.clicked.connect(self._discard)
        lay.addWidget(box)

    def _discard(self):
        self.discard = True
        self.accept()

    def checked(self) -> list:
        return [c for i, c in enumerate(self.runs)
                if self.tree.topLevelItem(i).checkState(0) == Qt.Checked]


def offer_resume_interrupted(app, quiet: bool = True) -> int:
    """Show the dialog when there is something to resume; returns how many runs were queued."""
    runs = interrupted_runs(app)
    if not runs:
        if not quiet:
            QMessageBox.information(app, "Resume", "There are no interrupted simulations to resume.")
        return 0
    dlg = ResumeDialog(runs, app)
    if dlg.exec() != QDialog.Accepted:
        return 0
    chosen = dlg.checked()
    if dlg.discard:
        from sharc.support import checkpoint
        for c in chosen:
            checkpoint.clear(c.param_file)
        return 0
    sched = getattr(app, "scheduler", None)
    if sched is None or not chosen:
        return 0
    jobs = sched.submit([c.param_file for c in chosen], resume=True)
    for job, c in zip(jobs, chosen):
        job.pct = c.pct
    if hasattr(app, "dock_jobs"):
        app.dock_jobs.show()
        app.dock_jobs.raise_()
    return len(jobs)
