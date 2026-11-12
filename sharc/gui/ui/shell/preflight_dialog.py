"""Run review: parameters, resource estimate, validation result and a real test run, before the simulation starts."""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from core import preflight as pf


class _ProbeBridge(QObject):
    progress = Signal(int, int)
    phase = Signal(str)
    done = Signal(object)


class PreflightDialog(QDialog):
    """Accepted = start the simulation. Rejected = go back and edit."""

    def __init__(self, parent, data: Dict[str, Any], plan: pf.Plan, issues: List[Any]):
        super().__init__(parent)
        self.setWindowTitle("Review and run")
        self.setMinimumSize(720, 640)
        self._data, self.plan, self._issues = data, plan, issues
        self._cancel = threading.Event()
        self._probe_state = "idle"           # idle | running | ok | failed
        self._bridge = _ProbeBridge(self)
        self._bridge.progress.connect(self._on_progress)
        self._bridge.phase.connect(self._on_phase)
        self._bridge.done.connect(self._on_done)

        lay = QVBoxLayout(self)
        lay.addWidget(self._title("Scenario"))
        self.tbl_params = self._table()
        lay.addWidget(self.tbl_params)
        lay.addWidget(self._title("Resources"))
        self.tbl_res = self._table()
        lay.addWidget(self.tbl_res)
        self.lbl_source = QLabel()
        self.lbl_source.setWordWrap(True)
        self.lbl_source.setObjectName("StatusMsg")
        lay.addWidget(self.lbl_source)
        lay.addWidget(self._title("Checks"))
        self.lbl_checks = QLabel()
        self.lbl_checks.setWordWrap(True)
        self.lbl_checks.setTextFormat(Qt.RichText)
        lay.addWidget(self.lbl_checks)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.hide()
        lay.addWidget(self.log)
        lay.addStretch(1)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.hide()
        lay.addWidget(self.bar)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._advance_bar)
        self._t0 = 0.0
        self._phase = "starting"
        self._last_seconds = None            # duration of the previous test run, to pace the bar

        row = QHBoxLayout()
        self.btn_probe = QPushButton(f"Run test ({min(pf.PROBE_SNAPSHOTS, max(plan.snapshots, 1))} snapshots)")
        self.btn_probe.setToolTip("Runs the real engine for a few snapshots in a temporary folder to measure "
                                  "time, peak RAM and output size. Nothing is kept.")
        self.btn_probe.clicked.connect(self._start_probe)
        row.addWidget(self.btn_probe)
        row.addStretch(1)
        self.box = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.btn_go = self.box.addButton("Start simulation", QDialogButtonBox.AcceptRole)
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        row.addWidget(self.box)
        lay.addLayout(row)

        self._fill_params()
        self._refresh()

    # -- layout helpers
    @staticmethod
    def _title(text):
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        return lbl

    @staticmethod
    def _table():
        t = QTableWidget(0, 3)
        t.horizontalHeader().setVisible(False)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.setFrameShape(QFrame.NoFrame)
        t.setShowGrid(False)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        return t

    @staticmethod
    def _fill(table: QTableWidget, rows: List[tuple]):
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                table.setItem(i, j, QTableWidgetItem(str(v)))
        table.resizeRowsToContents()
        table.setFixedHeight(sum(table.rowHeight(i) for i in range(len(rows))) + 4)

    # -- content
    def _fill_params(self):
        p = self.plan
        freq = (f"{p.freq_mhz:g} MHz / {p.bw_mhz:g} MHz"
                if p.freq_mhz is not None and p.bw_mhz is not None else "-")
        self._fill(self.tbl_params, [
            ("Victim system", p.system or "-", ""),
            ("IMT band (centre / bandwidth)", freq, ""),
            ("IMT topology", p.topology or "-", ""),
            ("Base stations / UEs (one snapshot)", f"{p.n_bs} / {p.n_ue}", ""),
            ("Snapshots per run", p.snapshots, ""),
            ("Runs (parameter sweep)", p.runs, ""),
            ("Parallel jobs", f"{p.workers} (limit {p.parallel})", ""),
            ("Seed", p.seed or "-", ""),
            ("Output folder", p.out_dir, ""),
        ])

    def _refresh(self):
        p = self.plan
        src = "measured" if p.measured else "estimated"
        ram_all = pf.fmt_bytes(p.ram_total_bytes)
        if p.avail_ram_bytes:
            ram_all += f" of {pf.fmt_bytes(p.avail_ram_bytes)} free"
        self._fill(self.tbl_res, [
            ("RAM per job", pf.fmt_bytes(p.ram_per_proc_bytes), src),
            ("RAM, all parallel jobs", ram_all, src),
            ("Output on disk",
             (f"{pf.fmt_bytes(p.disk_total_bytes)} of {pf.fmt_bytes(p.free_disk_bytes)} free" if p.measured else
              f"{pf.fmt_bytes(p.disk_total_bytes)} fixed files + result CSVs (size needs the test); "
              f"{pf.fmt_bytes(p.free_disk_bytes)} free"),
             "measured" if p.measured else "partial"),
            ("Estimated time", pf.fmt_duration(p.time_seconds), "measured" if p.measured else "needs test"),
        ])
        self.lbl_source.setText(
            "Figures marked 'measured' come from the test run on this machine. Before the test, RAM is the "
            "baseline measured on a default scenario plus a matrix term; time and CSV size are unknown." if not p.measured
            else "Figures are scaled from the test run. Time grows with the scenario, so treat it as a guide.")

        errors = [i for i in self._issues if i.severity == "error"]
        warns = [i for i in self._issues if i.severity == "warning"]
        res_checks = pf.resource_checks(p)
        lines = [self._line("ok" if not errors else "error",
                            "Validation passed" if not errors else f"Validation found {len(errors)} error(s)")]
        for i in errors + warns:
            lines.append(self._line(i.severity, f"{i.field + ': ' if i.field else ''}{i.message}", indent=True))
        for sev, text in res_checks:
            lines.append(self._line(sev, text))
        lines.append({
            "idle": self._line("info", "Test run not done. Optional, but it is the only check that executes the engine."),
            "running": self._line("info", "Test run in progress..."),
            "ok": self._line("ok", "Test run finished: the engine runs this scenario."),
            "failed": self._line("error", "Test run failed. See the log below."),
        }[self._probe_state])
        self.lbl_checks.setText("<br>".join(lines))

        blocked = bool(errors) or self._probe_state == "running"
        self.btn_go.setEnabled(not blocked)
        warn = bool(warns) or self._probe_state == "failed" or bool(res_checks)
        self.btn_go.setText("Start anyway" if warn and not blocked else "Start simulation")
        self.btn_probe.setEnabled(not errors and self._probe_state != "running")

    @staticmethod
    def _line(sev: str, text: str, indent: bool = False) -> str:
        mark, color = {"ok": ("OK", "#3fb950"), "error": ("ERROR", "#f85149"),
                       "warning": ("WARN", "#d29922"), "info": ("INFO", "#8b949e")}[sev]
        pad = "&nbsp;&nbsp;&nbsp;&nbsp;" if indent else ""
        text = text.replace("&", "&amp;").replace("<", "&lt;")
        return f"{pad}<span style='color:{color}'><b>{mark}</b></span> {text}"

    # -- test run
    def _start_probe(self):
        self._probe_state = "running"
        self._cancel.clear()
        self.log.clear()
        self.log.hide()
        self.btn_probe.setText("Testing...")
        self._phase, self._t0 = "starting", time.time()
        self.bar.setValue(0)
        self.bar.setFormat("Starting the engine... %p%")
        self.bar.show()
        self._tick.start(100)
        self._refresh()

        def work():
            self._bridge.done.emit(pf.run_probe(
                self._data, self._cancel, on_progress=lambda a, b: self._bridge.progress.emit(a, b),
                work_root=self.plan.work_root, on_phase=self._bridge.phase.emit))
        threading.Thread(target=work, daemon=True).start()

    def _advance_bar(self):
        """The engine reports no per-snapshot progress before the first CSV flush, so the bar is paced by
        elapsed time against the last run (or a default) and held at 95% until the engine really finishes."""
        expected = self._last_seconds or (pf.DEFAULT_PROBE_SECONDS)
        self.bar.setValue(min(95, int(100 * (time.time() - self._t0) / expected)))

    def _on_phase(self, phase: str):
        self._phase = phase
        self.bar.setFormat("Running snapshots... %p%")

    def _on_progress(self, cur: int, total: int):
        self.btn_probe.setText(f"Testing... snapshot {cur}/{total}")

    def _on_done(self, res: pf.ProbeResult):
        self._tick.stop()
        self._last_seconds = max(res.wall_seconds, 1.0) if res.ok else self._last_seconds
        if res.ok:
            self.bar.setValue(100)
            self.bar.setFormat("Test finished %p%")
        else:
            self.bar.hide()
        self.btn_probe.setText("Run test again")
        if res.cancelled:
            self._probe_state = "idle"
        elif res.ok:
            self._probe_state = "ok"
            pf.apply_probe(self.plan, res)
        else:
            self._probe_state = "failed"
            self.log.setPlainText(f"{res.error}\n\n{res.log_tail}")
            self.log.show()
        self._refresh()

    def done(self, code):
        self._cancel.set()                      # never leave a test engine running behind the dialog
        super().done(code)
