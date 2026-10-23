"""Capture and restore the whole GUI as plain JSON-able data, and build / apply a `Project` (see `project_file`).

Captured: every SharcVar of the app and of the pages (IMT, victim, database, terrain), the parameter-sweep table, the
Protection Contour page (fields and results) and the heat-map style. Restored values go back through `SharcVar.set`, so
every page updates as if the user had typed them. Anything unknown in a project (a variable renamed by a newer SHARC) is
skipped and reported, never fatal.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox

from core import project_file
from core.state import SharcVar

TAB_STATES = ("tab_imt", "tab_victim", "tab_database", "tab_terrain")
SWEEP_COLUMNS = 3


def _json_value(v: Any) -> Any:
    return v if isinstance(v, (bool, int, float, str)) or v is None else str(v)


def _var_groups(app) -> Dict[str, Dict[str, SharcVar]]:
    groups: Dict[str, Dict[str, SharcVar]] = {}
    model = getattr(app, "state_model", None)
    if model is not None:
        groups["app"] = {k: v for k, v in vars(model).items() if isinstance(v, SharcVar)}
    for tab in TAB_STATES:
        state = getattr(getattr(app, tab, None), "state", None)
        found = getattr(state, "vars", None)
        if isinstance(found, dict):
            groups[tab] = {k: v for k, v in found.items() if isinstance(v, SharcVar)}
    return groups


def widget_values(widgets: Dict[str, Any]) -> Dict[str, Any]:
    """Values of a dict of Qt input widgets (the fields of the Protection Contour page)."""
    out: Dict[str, Any] = {}
    for key, w in widgets.items():
        if isinstance(w, QLineEdit):
            out[key] = w.text()
        elif isinstance(w, (QDoubleSpinBox, QSpinBox)):
            out[key] = w.value()
        elif isinstance(w, QComboBox):
            out[key] = w.currentText()
        elif isinstance(w, QCheckBox):
            out[key] = w.isChecked()
    return out


def apply_widget_values(widgets: Dict[str, Any], values: Dict[str, Any]) -> List[str]:
    """Set the widgets from `values`; returns the keys that could not be applied."""
    skipped: List[str] = []
    for key, value in (values or {}).items():
        w = widgets.get(key)
        try:
            if isinstance(w, QLineEdit):
                w.setText(str(value))
            elif isinstance(w, (QDoubleSpinBox, QSpinBox)):
                w.setValue(value)
            elif isinstance(w, QComboBox):
                if w.findText(str(value)) < 0:
                    raise ValueError(value)
                w.setCurrentText(str(value))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(value))
            else:
                raise KeyError(key)
        except (TypeError, ValueError, KeyError):
            skipped.append(key)
    return skipped


def _sweep_table(app):
    return getattr(getattr(app, "tab_general", None), "var_table", None)


def capture(app) -> Dict[str, Any]:
    """Everything the GUI holds, as JSON-able data."""
    state: Dict[str, Any] = {"vars": {g: {k: _json_value(v.get()) for k, v in d.items()} for g, d in _var_groups(app).items()}}
    table = _sweep_table(app)
    state["sweep_table"] = [[(table.item(r, c).text() if table.item(r, c) else "") for c in range(SWEEP_COLUMNS)]
                            for r in range(table.rowCount())] if table is not None else []
    style = getattr(getattr(app, "tab_preview", None), "heat_style", None)
    if style is not None:
        from dataclasses import asdict
        state["heat_style"] = asdict(style)
    return state


def apply_vars(app, state: Dict[str, Any]) -> Dict[str, Any]:
    """Restore only the SharcVar values of a captured state (no tables, no styles): cheap enough to run before every
    combination of a parameter sweep. Returns {"applied": n, "skipped": [names]}."""
    applied, skipped = 0, []
    groups = _var_groups(app)
    for group, values in (state.get("vars") or {}).items():
        known = groups.get(group, {})
        for name, value in values.items():
            var = known.get(name)
            if var is None:
                skipped.append(f"{group}.{name}")
                continue
            try:
                var.set(value)
                applied += 1
            except Exception:  # noqa: BLE001 - one bad value must not stop the others
                skipped.append(f"{group}.{name}")
    return {"applied": applied, "skipped": skipped}


def apply(app, state: Dict[str, Any]) -> Dict[str, Any]:
    """Restore a captured state. Returns {"applied": n, "skipped": [names]}: values for variables this SHARC does not
    have are skipped, not errors."""
    report = apply_vars(app, state)
    applied, skipped = report["applied"], report["skipped"]
    table = _sweep_table(app)
    if table is not None and "sweep_table" in state:
        from PySide6.QtWidgets import QTableWidgetItem
        table.setRowCount(0)
        for row in state["sweep_table"]:
            r = table.rowCount()
            table.insertRow(r)
            for c, text in enumerate(row[:SWEEP_COLUMNS]):
                table.setItem(r, c, QTableWidgetItem(str(text)))
    if state.get("heat_style") and getattr(app, "tab_preview", None) is not None:
        _apply_heat_style(app.tab_preview, state["heat_style"])
    return {"applied": applied, "skipped": skipped}


def _apply_heat_style(preview, data: Dict[str, Any]) -> None:
    from core.heat_style import HeatStyle
    widgets = getattr(preview, "heat_widgets", None)
    if not widgets:
        return
    s = HeatStyle(**{k: v for k, v in data.items() if k in HeatStyle.__dataclass_fields__}).sanitized()
    widgets["palette"].setCurrentIndex(max(0, widgets["palette"].findData(s.palette)))
    widgets["reverse"].setChecked(s.reverse)
    widgets["fixed"].setChecked(not s.auto_range)
    widgets["vmin"].setValue(s.vmin)
    widgets["vmax"].setValue(s.vmax)
    widgets["opacity"].setValue(int(round(s.opacity * 100)))
    widgets["isolines"].setChecked(s.isolines)
    widgets["bands"].setValue(s.bands)
    widgets["thr_on"].setChecked(s.threshold_on)
    widgets["thr"].setValue(s.threshold_db)


# ------------------------------------------------------------------------------------------------- projects
def scenario_yaml(app) -> str:
    """The engine YAML of the current scenario, as `main_cli` reads it."""
    import yaml
    from core.yaml_builder import build_yaml_structure
    from ui.tabs.general import _sanitize_for_yaml
    return yaml.safe_dump(_sanitize_for_yaml(build_yaml_structure(app)), sort_keys=False, default_flow_style=False,
                          allow_unicode=True)


def _version() -> str:
    try:
        from core import updater
        info = updater.load_build_info()
        return info.version if info else ""
    except Exception:  # noqa: BLE001 - a source checkout has no build info
        return ""


def build_project(app, name: str, notes: str = "", created: Optional[str] = None) -> project_file.Project:
    """The current state of the GUI as a project, ready for `project_file.save`."""
    from core import campaign_csv
    text = scenario_yaml(app)
    summary: Dict[str, Any] = {}
    try:
        summary["system"] = str(app.var_system.get())
        summary["topology"] = str(app.tab_imt.state.get("topo_type").get())
    except Exception:  # noqa: BLE001 - a summary is only a label
        pass
    contour = getattr(app, "tab_contour", None)
    config = results = None
    if contour is not None:
        config = {"widgets": widget_values(contour.w)}
        results = campaign_csv.rows_to_csv(contour.rows) if contour.rows else ""
    project = project_file.Project(name=name, scenario_yaml=text, gui_state=capture(app), notes=notes,
                                   contour_config=config, contour_results_csv=results or "", summary=summary,
                                   sharc_version=_version())
    if created:
        project.created = created
    return project


def apply_project(app, project: project_file.Project) -> Dict[str, Any]:
    """Open a project in the GUI: all pages, the sweep table, the heat style and the contour page with its results."""
    report = apply(app, project.gui_state)
    contour = getattr(app, "tab_contour", None)
    if contour is not None and project.contour_config:
        report["skipped"] += [f"contour.{k}" for k in apply_widget_values(contour.w, project.contour_config.get("widgets", {}))]
        if project.contour_results_csv.strip():
            from core import campaign_csv
            contour.rows = campaign_csv.rows_from_csv(project.contour_results_csv)
            contour._show(contour.rows)
            contour._set_buttons(False)
    return report
