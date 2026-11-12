"""State of the four workflow stages shown in the toolbar strip: Setup, Validate, Run, Results.

Pure functions over counts the window already knows (problems, jobs), so the strip's logic can be tested without Qt.
Which workbench page belongs to which stage is presentation knowledge and lives in `ui.shell.workflow_strip`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Tuple

Stage = Literal["setup", "validate", "run", "results"]
SETUP: Stage = "setup"
VALIDATE: Stage = "validate"
RUN: Stage = "run"
RESULTS: Stage = "results"
STAGES: Tuple[Tuple[Stage, str], ...] = ((SETUP, "Setup"), (VALIDATE, "Validate"), (RUN, "Run"), (RESULTS, "Results"))

# visual states; the stylesheet keys off these names
Visual = Literal["idle", "ok", "warn", "error", "active"]
IDLE: Visual = "idle"
OK: Visual = "ok"
WARN: Visual = "warn"
ERROR: Visual = "error"
ACTIVE: Visual = "active"


@dataclass(frozen=True)
class StageState:
    """How one stage is drawn: its visual state, a short badge next to the caption and a tooltip."""
    state: Visual = IDLE
    badge: str = ""
    tip: str = ""


@dataclass(frozen=True)
class WorkflowFacts:
    validated: bool = False
    errors: int = 0
    warnings: int = 0
    running: int = 0
    queued: int = 0
    completed: int = 0
    results_loaded: int = 0  # result folders in the Results page


def stage_states(facts: WorkflowFacts) -> Dict[Stage, StageState]:
    """The visual state of each stage for the given facts."""
    f = facts
    setup = StageState(OK, "", "Scenario pages: system, IMT network, terrain and victim")

    if not f.validated:
        validate = StageState(IDLE, "", "Not validated yet. Click to check the scenario (Ctrl+Shift+V).")
    elif f.errors:
        validate = StageState(ERROR, str(f.errors), f"{f.errors} error(s) block the run. Open the Problems tab.")
    elif f.warnings:
        validate = StageState(WARN, str(f.warnings), f"{f.warnings} warning(s). The scenario can run.")
    else:
        validate = StageState(OK, "", "No problems found.")

    if f.running:
        run = StageState(ACTIVE, f"{f.running} running", f"{f.running} simulation(s) running, {f.queued} queued")
    elif f.queued:
        run = StageState(WARN, f"{f.queued} queued", f"{f.queued} simulation(s) waiting in the queue")
    elif f.completed:
        run = StageState(OK, "", f"{f.completed} simulation(s) finished")
    else:
        run = StageState(IDLE, "", "Run the simulation (Ctrl+R) or open the Execution Engine")

    total = f.completed + f.results_loaded
    if total:
        results = StageState(OK, str(total) if total > 1 else "", "Open Analysis & Results")
    else:
        results = StageState(IDLE, "", "No results yet")

    return {SETUP: setup, VALIDATE: validate, RUN: run, RESULTS: results}
