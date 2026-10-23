"""Projects (.sharc) in the GUI: save / open round trip, new, unsaved changes, recent list, manager, menu and the CLI."""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import project_file, project_state  # noqa: E402


@pytest.fixture()
def svc(win):
    """The window's project service, reset to a clean 'Untitled' project around each test."""
    service = win.projects
    service.new_project()
    yield service
    service.new_project()
    for item in service.recent():
        service.forget(item["path"])


def _rows():
    return [{"az_enu_deg": 0.0, "az_north_deg": 90.0, "off_axis_deg": 0.0, "contour_m": 5000.0, "marker": "ok",
             "ray_end_m": 20000.0, "ray_end_reason": "sea", "evaluations": 9, "lat": -3.9, "lon": -38.4},
            {"az_enu_deg": 90.0, "az_north_deg": 0.0, "off_axis_deg": 0.0, "contour_m": float("nan"), "marker": "no_points",
             "ray_end_m": 0.0, "ray_end_reason": "sea", "evaluations": 0, "lat": float("nan"), "lon": float("nan")}]


def test_save_then_open_restores_every_page(win, svc, tmp_path):
    imt = win.tab_imt.state
    imt.get("bs_downtilt").set("9")
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    win.var_system.set("SINGLE_SPACE_STATION")
    contour = win.tab_contour
    contour.w["lat"].setValue(50.5)
    contour.w["dem"].setText("D:/data/dem.tif")
    contour.w["offs"].setText("0, 45")
    contour.rows = _rows()
    win.tab_general.var_table.insertRow(0)
    from PySide6.QtWidgets import QTableWidgetItem
    for c, text in enumerate(["downtilt", "[d6, d9]", "[6, 9]"]):
        win.tab_general.var_table.setItem(0, c, QTableWidgetItem(text))
    svc.name, svc.notes = "My study", "notes here"

    path = svc.save(str(tmp_path / "study"))
    assert path.endswith(".sharc") and os.path.isfile(path)

    # a different state, then open: everything comes back
    imt.get("bs_downtilt").set("1")
    contour.w["lat"].setValue(-3.0)
    contour.w["dem"].setText("")
    contour.rows = []
    win.tab_general.var_table.setRowCount(0)
    report = svc.open(path)
    assert imt.get("bs_downtilt").get() == "9"
    assert contour.w["lat"].value() == pytest.approx(50.5) and contour.w["dem"].text() == "D:/data/dem.tif"
    assert contour.w["offs"].text() == "0, 45"
    assert len(contour.rows) == 2 and contour.rows[0]["contour_m"] == 5000.0 and contour.rows[1]["marker"] == "no_points"
    assert contour.rows[1]["contour_m"] != contour.rows[1]["contour_m"]            # the NaN came back as NaN
    assert win.tab_general.var_table.item(0, 0).text() == "downtilt"
    assert (svc.name, svc.notes, svc.path) == ("My study", "notes here", path)
    assert report["applied"] > 100 and report["skipped"] == []
    assert contour.btn_csv.isEnabled() and contour.btn_3d.isEnabled()                # results restored: exports available
    contour.rows = []


def test_the_scenario_inside_is_the_engine_yaml_main_cli_reads(win, svc, tmp_path):
    import yaml
    win.tab_imt.state.get("bs_downtilt").set("7")
    path = svc.save(str(tmp_path / "s.sharc"))
    out = project_file.extract_scenario(path, str(tmp_path / "x" / "scenario.yaml"))
    data = yaml.safe_load(open(out, encoding="utf-8"))
    assert data["imt"]["bs"]["antenna"]["array"]["downtilt"] == 7
    assert yaml.safe_load(project_state.scenario_yaml(win)) == data
    sys.path.insert(0, os.path.join(_REPO, "sharc"))
    import main_cli
    cli_path = main_cli._scenario_of_project(path)                                   # what `main_cli -p file.sharc` runs
    assert yaml.safe_load(open(cli_path, encoding="utf-8")) == data
    with pytest.raises(SystemExit, match="Cannot open the project"):
        main_cli._scenario_of_project(str(tmp_path / "missing.sharc"))


def test_unsaved_changes_are_detected_and_shown_in_the_title(win, svc, tmp_path):
    svc.name = "T"
    path = svc.save(str(tmp_path / "t.sharc"))
    win._refresh_project_title()
    assert not svc.is_dirty() and win.windowTitle().startswith("T \u2013")
    win.tab_imt.state.get("bs_downtilt").set("12")
    assert svc.is_dirty()
    win._refresh_project_title()
    assert win.windowTitle().startswith("T* ")
    svc.save()
    assert not svc.is_dirty()
    svc.notes = "edited"
    assert svc.is_dirty()
    svc.open(path)
    assert not svc.is_dirty() and svc.notes == ""                                    # open reloads the saved notes


def test_new_project_goes_back_to_the_starting_values(win, svc, tmp_path):
    start = win.tab_imt.state.get("bs_downtilt").get()
    win.tab_imt.state.get("bs_downtilt").set("33")
    win.tab_contour.w["lat"].setValue(12.0)
    win.tab_contour.rows = _rows()
    svc.save(str(tmp_path / "n.sharc"))
    svc.new_project()
    assert win.tab_imt.state.get("bs_downtilt").get() == start
    assert win.tab_contour.w["lat"].value() == pytest.approx(-3.8735)                # the ROEN preset the page starts with
    assert win.tab_contour.rows == [] and (svc.path, svc.name) == (None, "Untitled") and not svc.is_dirty()


def test_save_without_a_file_is_refused_and_save_as_names_the_project(win, svc, tmp_path):
    with pytest.raises(project_file.ProjectError, match="Save Project As"):
        svc.save()
    path = svc.save(str(tmp_path / "my_study.sharc"))
    assert svc.name == "my_study" and svc.path == path


def test_recent_list_orders_dedupes_forgets_and_is_capped(win, svc, tmp_path):
    paths = []
    for i in range(15):
        svc.name = f"p{i}"
        paths.append(svc.save(str(tmp_path / f"p{i}.sharc")))
    recent = svc.recent()
    assert len(recent) == 12 and recent[0]["path"].endswith("p14.sharc")
    svc.open(paths[5])                                                               # already in the list: moves to the top
    assert svc.recent()[0]["path"].endswith("p5.sharc") and len([r for r in svc.recent() if r["path"].endswith("p5.sharc")]) == 1
    svc.forget(paths[5])
    assert all(not r["path"].endswith("p5.sharc") for r in svc.recent())


def test_a_project_from_another_version_applies_what_it_can_and_reports_the_rest(win, svc, tmp_path):
    path = svc.save(str(tmp_path / "v.sharc"))
    project = project_file.load(path)
    project.gui_state["vars"]["app"]["a_variable_of_a_future_version"] = 5
    project.gui_state["vars"]["tab_future"] = {"x": 1}
    project_file.save(path, project)
    report = svc.open(path)
    assert "app.a_variable_of_a_future_version" in report["skipped"] and "tab_future.x" in report["skipped"]
    assert report["applied"] > 100


def test_opening_a_broken_file_warns_and_changes_nothing(win, svc, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    bad = tmp_path / "bad.sharc"
    bad.write_bytes(b"not a project")
    win.tab_imt.state.get("bs_downtilt").set("21")
    assert win.open_project(str(bad)) is False
    assert shown and "not a SHARC project" in shown[0]
    assert win.tab_imt.state.get("bs_downtilt").get() == "21" and svc.path is None


def test_menu_has_the_project_actions_with_shortcuts(win):
    file_menu = [m for m in win.menuBar().findChildren(type(win.menuBar().addMenu("x"))) if m.title() == "File"][0]
    texts = {a.text(): a.shortcut().toString() for a in file_menu.actions()}
    for name, key in (("New Project", "Ctrl+N"), ("Open Project...", "Ctrl+O"), ("Save Project", "Ctrl+S"),
                      ("Save Project As...", "Ctrl+Shift+S")):
        assert texts.get(name) == key, name
    assert "Project Manager..." in texts and "Open Recent" in texts


def test_project_manager_lists_recent_projects_and_opens_one(win, svc, tmp_path, monkeypatch):
    from ui.shell.project_dialog import ProjectDialog
    svc.name = "Alpha"
    svc.save(str(tmp_path / "alpha.sharc"))
    svc.name = "Beta"
    gone = svc.save(str(tmp_path / "beta.sharc"))
    os.remove(gone)
    dlg = ProjectDialog(win)
    assert dlg.table.rowCount() == 2
    names = {dlg.table.item(r, 0).text(): dlg.table.item(r, 3).text() for r in range(2)}
    assert "Alpha" in names and "unavailable" in names["Beta"] and "unavailable" not in names["Alpha"]          # a deleted file is marked, not fatal
    win.tab_imt.state.get("bs_downtilt").set("40")
    row = [r for r in range(2) if dlg.table.item(r, 0).text() == "Alpha"][0]
    dlg.table.setCurrentCell(row, 0)
    dlg._open_selected()
    assert win.tab_imt.state.get("bs_downtilt").get() != "40"
    dlg.table.setCurrentCell([r for r in range(2) if r != row][0], 0)
    dlg._remove()
    assert dlg.table.rowCount() == 1
    dlg.close()
