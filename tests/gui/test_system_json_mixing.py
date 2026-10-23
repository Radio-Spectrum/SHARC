"""Mixing of systems: a parameter sweep whose values are .json preset files (IMT and victim system) gives one YAML for each
combination, with the content of the chosen presets."""
import json
import os
import sys

import pytest
import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6.QtWidgets import QTableWidgetItem  # noqa: E402
from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence  # noqa: E402


def _row(table, name, tags, values):
    r = table.rowCount()
    table.insertRow(r)
    for c, text in enumerate((name, tags, values)):
        table.setItem(r, c, QTableWidgetItem(text))


def _preset_imt(win, path, downtilt, power):
    """The same file the 'Save IMT Preset (.json)' action writes (see IMTState.save_to_file), with other values."""
    data = {"config_type": "IMT"}
    data.update({k: v.get() for k, v in win.tab_imt.state.vars.items()})
    data["bs_downtilt"], data["bs_power"] = str(downtilt), str(power)
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _preset_system(win, path, frequency, tx_density):
    """The file 'Save Earth Station Config' writes (SESPersistence.save_to_file), with other values."""
    data = {"config_type": "SES", **SESPersistence.collect_config(win)}
    data["frequency"], data["tx_power_density"] = frequency, tx_density
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_json_presets_of_imt_and_system_are_mixed_into_one_yaml_per_combination(win, tmp_path):
    win.var_system.set("SINGLE_EARTH_STATION")
    imt_a = _preset_imt(win, tmp_path / "imt_a.json", 3, 20)
    imt_b = _preset_imt(win, tmp_path / "imt_b.json", 9, 25)
    sys_x = _preset_system(win, tmp_path / "ses_x.json", 3600.0, -70.0)
    sys_y = _preset_system(win, tmp_path / "ses_y.json", 4200.0, -55.0)

    table = win.tab_general.var_table
    table.setRowCount(0)
    _row(table, "imt", "['A', 'B']", repr([imt_a, imt_b]))
    _row(table, "sys", "['X', 'Y']", repr([sys_x, sys_y]))
    win.var_prefix.set("mix_{imt}_{sys}")

    files = win.tab_general._internal_save_logic(use_combinations=True, save_dir=str(tmp_path / "out"), quiet=True)
    names = sorted(os.path.basename(f) for f in files)
    assert names == ["mix_A_X.yaml", "mix_A_Y.yaml", "mix_B_X.yaml", "mix_B_Y.yaml"]           # 2 x 2 combinations

    got = {}
    for f in files:
        y = yaml.safe_load(open(f, encoding="utf-8"))
        got[os.path.basename(f)[4:-5]] = (y["imt"]["bs"]["antenna"]["array"]["downtilt"], y["imt"]["bs"]["conducted_power"],
                                          y["single_earth_station"]["frequency"], y["single_earth_station"]["tx_power_density"])
    assert got == {"A_X": (3, 20, 3600.0, -70.0), "A_Y": (3, 20, 4200.0, -55.0),
                   "B_X": (9, 25, 3600.0, -70.0), "B_Y": (9, 25, 4200.0, -55.0)}


def test_a_json_of_another_kind_than_imt_or_system_is_merged_as_plain_yaml_parameters(win, tmp_path):
    other = tmp_path / "general.json"
    other.write_text(json.dumps({"general": {"num_snapshots": 77}}), encoding="utf-8")
    table = win.tab_general.var_table
    table.setRowCount(0)
    _row(table, "g", "['G']", repr([str(other)]))
    win.var_prefix.set("m_{g}")
    files = win.tab_general._internal_save_logic(use_combinations=True, save_dir=str(tmp_path / "out2"), quiet=True)
    assert len(files) == 1 and yaml.safe_load(open(files[0], encoding="utf-8"))["general"]["num_snapshots"] == 77


def test_the_sweep_table_and_the_prefix_survive_a_sharc_project(win, tmp_path):
    from core import project_file
    table = win.tab_general.var_table
    table.setRowCount(0)
    _row(table, "imt", "['A', 'B']", "['a.json', 'b.json']")
    win.var_prefix.set("mix_{imt}")
    path = win.projects.save(str(tmp_path / "mix.sharc"))
    table.setRowCount(0)
    win.var_prefix.set("changed")
    win.projects.open(path)
    assert table.rowCount() == 1 and table.item(0, 2).text() == "['a.json', 'b.json']"
    assert win.var_prefix.get() == "mix_{imt}"
    assert project_file.load(path).gui_state["sweep_table"][0][0] == "imt"
    table.setRowCount(0)
    win.projects.new_project()


def test_generating_a_sweep_leaves_the_pages_as_the_user_had_them(win, tmp_path):
    win.var_system.set("SINGLE_EARTH_STATION")
    before_tilt = win.tab_imt.state.get("bs_downtilt").get()
    before_freq = win.tab_victim.state.get("v_freq").get() if "v_freq" in win.tab_victim.state.vars else None
    imt = _preset_imt(win, tmp_path / "imt_c.json", 17, 31)
    system = _preset_system(win, tmp_path / "ses_z.json", 5000.0, -40.0)
    table = win.tab_general.var_table
    table.setRowCount(0)
    _row(table, "imt", "['C']", repr([imt]))
    _row(table, "sys", "['Z']", repr([system]))
    win.var_prefix.set("keep_{imt}_{sys}")
    files = win.tab_general._internal_save_logic(use_combinations=True, save_dir=str(tmp_path / "o"), quiet=True)
    assert len(files) == 1 and yaml.safe_load(open(files[0], encoding="utf-8"))["imt"]["bs"]["antenna"]["array"]["downtilt"] == 17
    assert win.tab_imt.state.get("bs_downtilt").get() == before_tilt                  # not left at 17
    assert float(win.se_frequency.get()) != 5000.0
    table.setRowCount(0)


def test_a_combination_without_an_imt_preset_keeps_the_pages_values_not_the_previous_combinations(win, tmp_path):
    win.var_system.set("SINGLE_EARTH_STATION")
    win.tab_imt.state.get("bs_downtilt").set("4")
    imt = _preset_imt(win, tmp_path / "imt_d.json", 11, 22)
    win.tab_imt.state.get("bs_downtilt").set("4")
    table = win.tab_general.var_table
    table.setRowCount(0)
    _row(table, "imt", "['with', 'without']", repr([imt, "none"]))                  # the 2nd value is not a file
    win.var_prefix.set("c_{imt}")
    files = win.tab_general._internal_save_logic(use_combinations=True, save_dir=str(tmp_path / "o2"), quiet=True)
    got = {os.path.basename(f)[2:-5]: yaml.safe_load(open(f, encoding="utf-8"))["imt"]["bs"]["antenna"]["array"]["downtilt"]
           for f in files}
    assert got == {"with": 11, "without": 4}                                          # the second does not inherit 11
    table.setRowCount(0)
