"""Scenario validation before Run (no Qt).

`validate(data)` takes the YAML dict the GUI would write and returns a list of `Issue`.
Two layers:
  - static rules: cheap checks on the dict, no engine needed;
  - engine check: `build_engine_scene` runs the real parameter loader, topology and station
    factories, so anything the simulation would reject at start-up shows up here first.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    severity: str          # ERROR | WARNING
    page: str              # key of the GUI page that owns the field ("general", "imt", ...)
    field: str             # human label of the field ("" when the issue is about the whole page)
    message: str


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _band(block: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    f, bw = _num(block.get("frequency")), _num(block.get("bandwidth"))
    if f is None or bw is None or bw <= 0:
        return None
    return f - bw / 2.0, f + bw / 2.0


def static_issues(data: Dict[str, Any]) -> List[Issue]:
    out: List[Issue] = []
    gen = data.get("general", {}) or {}
    imt = data.get("imt", {}) or {}
    system = str(gen.get("system", "") or "").strip()

    snaps = _num(gen.get("num_snapshots"))
    if snaps is None or snaps < 1:
        out.append(Issue(ERROR, "general", "Number of snapshots", "must be at least 1"))
    if not system:
        out.append(Issue(ERROR, "general", "System", "no victim system selected"))
    if not (gen.get("enable_cochannel") or gen.get("enable_adjacent_channel")):
        out.append(Issue(ERROR, "general", "Co-channel / adjacent channel",
                         "both are off, so no interference is computed"))

    imt_band = _band(imt)
    if imt_band is None:
        out.append(Issue(ERROR, "imt", "Frequency / bandwidth", "frequency and a positive bandwidth are required"))

    victim = (data.get(system.lower()) or {}) if system else {}
    if victim:
        vic_band = _band(victim)
        vic_page = "victim" if system == "SINGLE_SPACE_STATION" else "station"
        if vic_band is None:
            out.append(Issue(ERROR, vic_page, "Frequency / bandwidth",
                             "frequency and a positive bandwidth are required"))
        elif imt_band is not None and gen.get("enable_cochannel") and not gen.get("enable_adjacent_channel"):
            if imt_band[1] <= vic_band[0] or vic_band[1] <= imt_band[0]:
                out.append(Issue(WARNING, "general", "Co-channel",
                                 "co-channel is on but the IMT and victim bands do not overlap "
                                 f"(IMT {imt_band[0]:g}-{imt_band[1]:g} MHz, victim {vic_band[0]:g}-{vic_band[1]:g} MHz)"))

        # the engine aborts in simulation.py ("Polarization loss is not initialized") when this is blank
        if "polarization_loss" in victim and _num(victim.get("polarization_loss")) is None:
            out.append(Issue(ERROR, vic_page, "polarization_loss",
                             "is blank; enter a value in dB (0 for none)"))

    db = data.get("database") or {}
    name = db.get("database_file_name")
    if name and not (os.path.isfile(str(name)) or os.path.isfile(os.path.join(os.getcwd(), str(name)))):
        out.append(Issue(ERROR, "database", "Database file", f"file not found: {name}"))
    return out


def engine_issues(data: Dict[str, Any]) -> List[Issue]:
    """Run the engine's own loaders; an engine rejection becomes one error naming the scenario."""
    from core.engine_scene import EngineSceneError, build_engine_scene
    try:
        scene = build_engine_scene(data)
    except EngineSceneError as exc:
        return [Issue(ERROR, "general", "", f"engine rejected the scenario: {exc}")]
    out: List[Issue] = []
    if getattr(scene, "system_error", ""):
        out.append(Issue(WARNING, "victim", "", f"victim system could not be built: {scene.system_error}"))
    return out


def validate(data: Dict[str, Any], engine: bool = True) -> List[Issue]:
    """Static rules first; the engine check runs only when the static rules found no error
    (a missing field would otherwise be reported twice, once cryptically)."""
    issues = static_issues(data)
    if engine and not any(i.severity == ERROR for i in issues):
        issues += engine_issues(data)
    return issues


def has_errors(issues: List[Issue]) -> bool:
    return any(i.severity == ERROR for i in issues)
