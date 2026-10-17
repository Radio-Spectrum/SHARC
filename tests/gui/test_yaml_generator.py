"""Gerador de YAML da GUI: toda combinação oferecida deve ser aceita pelo motor, e a
varredura de parâmetros (várias variáveis, várias combinações) deve gerar o produto
cartesiano com os valores certos."""
import itertools
import os
import sys

import pytest
import yaml

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TOPOLOGIES = ["MACROCELL", "HOTSPOT", "SINGLE_BS", "INDOOR", "NTN", "Macro_countries", "MSS_DC"]
LINKS = ["DOWNLINK", "UPLINK"]


def _systems(win):
    cb = win.tab_general.cb_sys
    return [cb.itemText(i) for i in range(cb.count())]


def _load_in_engine(y, tmp_path):
    from sharc.parameters.parameters import Parameters
    f = tmp_path / "t.yaml"
    f.write_text(yaml.safe_dump(y), encoding="utf-8")
    p = Parameters()
    p.set_file_name(str(f))
    p.read_params()
    return p


def test_every_offered_combination_is_accepted_by_the_engine(win, tmp_path):
    from core.yaml_builder import build_yaml_structure
    failures = []
    for system, topo, link in itertools.product(_systems(win), TOPOLOGIES, LINKS):
        win.var_system.set(system)
        win.tab_imt.state.get("topo_type").set(topo)
        win.var_imt_link.set(link)
        try:
            _load_in_engine(build_yaml_structure(win), tmp_path)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{system} / {topo} / {link}: {type(exc).__name__}: {str(exc)[:140]}")
    assert not failures, "combinações rejeitadas pelo motor:\n" + "\n".join(failures[:15])


def test_parameter_sweep_generates_cartesian_product(win, tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    win.var_system.set("SINGLE_SPACE_STATION")
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    win.var_imt_link.set("DOWNLINK")
    st = win.tab_imt.state
    st.get("imt_freq").set("{freq}")
    st.get("macro_intersite").set("{dist}")
    win.var_prefix.set("run_{freq}_{dist}")

    table = win.tab_general.var_table
    table.setRowCount(0)
    for name, tags, values in (("freq", "['f1','f2']", "[3500, 7000]"),
                               ("dist", "['d1','d2','d3']", "[500, 1000, 1500]")):
        r = table.rowCount()
        table.insertRow(r)
        for c, txt in enumerate((name, tags, values)):
            table.setItem(r, c, QTableWidgetItem(txt))

    files = win.tab_general._internal_save_logic(use_combinations=True, save_dir=tmp_path, quiet=True)
    names = sorted(os.path.basename(f) for f in files)
    assert names == sorted(f"run_{a}_{b}.yaml" for a in ("f1", "f2") for b in ("d1", "d2", "d3"))

    seen = set()
    for f in files:
        data = yaml.safe_load(open(f, encoding="utf-8"))
        freq, dist = data["imt"]["frequency"], data["imt"]["topology"]["macrocell"]["intersite_distance"]
        tag_f, tag_d = os.path.basename(f)[4:-5].split("_")
        assert freq == {"f1": 3500, "f2": 7000}[tag_f]
        assert dist == {"d1": 500, "d2": 1000, "d3": 1500}[tag_d]
        seen.add((freq, dist))
        _load_in_engine(data, tmp_path)      # cada arquivo da varredura é aceito pelo motor
    assert len(seen) == 6

    table.setRowCount(0)
    st.get("imt_freq").set("3500")
    st.get("macro_intersite").set("600")
    win.var_prefix.set("output_mss_{long}")
