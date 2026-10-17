"""Database tab: the GUI must produce a `database` block the engine accepts and uses."""
import os

import numpy as np
import pytest
import yaml


def _write_db(path, n=30, antenna=True):
    rng = np.random.RandomState(1)
    lines = ["latitude,longitude,azimute,altura"
             + (",n_rows,n_columns,beamforming_gain,element_max_g,tx_power,sub_num_rows,downtilt" if antenna else "")]
    for i in range(n):
        lat = -3.77 + rng.uniform(-0.1, 0.1)
        lon = -38.55 + rng.uniform(-0.1, 0.1)
        row = f"{lat:.5f},{lon:.5f},{(i * 120) % 360 - 180},{25 + i % 5}"
        if antenna:
            row += ",8,8,26,5,46,1,6"
        lines.append(row)
    path.write_text("\n".join(lines), encoding="utf-8")


def test_database_tab_inspects_file(win, tmp_path):
    from ui.tabs.database import inspect_database
    f = tmp_path / "db.csv"
    _write_db(f, antenna=False)
    info = inspect_database(str(f), ",")
    assert info["ok"] and info["rows"] == 30
    assert info["missing_sites"] == [] and len(info["missing_antenna"]) == 7
    assert -39 < info["bbox"][0] < -38 and -4 < info["bbox"][1] < -3.5


def test_database_block_loads_in_engine_and_defines_sites(win, tmp_path):
    from core.yaml_builder import build_yaml_structure
    from sharc.parameters.parameters import Parameters
    f = tmp_path / "db.csv"
    _write_db(f)
    st = win.tab_database.state
    for k, v in {"db_enabled": True, "db_file": str(f), "db_num_subsets": "2",
                 "db_from_sites": True, "db_from_antenna": True}.items():
        st.get(k).set(v)
    assert win.tab_imt.state.get("topo_type").get() == "Macro_countries"   # set automatically

    y = build_yaml_structure(win)
    assert y["database"]["num_subsets"] == 2 and os.path.isabs(y["database"]["database_file_name"])
    assert y["imt"]["topology"]["type"] == "MACRO_COUNTRIES"

    yf = tmp_path / "t.yaml"
    yf.write_text(yaml.safe_dump(y), encoding="utf-8")
    p = Parameters()
    p.set_file_name(str(yf))
    p.read_params()
    assert p.database.is_loaded and len(p.database.data_full) == 30


def test_database_disabled_adds_no_block(win):
    from core.yaml_builder import build_yaml_structure
    win.tab_database.state.get("db_enabled").set(False)
    assert "database" not in build_yaml_structure(win)


def test_preview_places_database_sites_exactly(win, tmp_path):
    import json
    f = tmp_path / "db.csv"
    _write_db(f)
    st = win.tab_database.state
    for k, v in {"db_enabled": True, "db_file": str(f), "db_num_subsets": "2",
                 "db_from_sites": True, "db_from_antenna": True}.items():
        st.get(k).set(v)
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    assert not scene.get("error"), scene.get("error")
    sites = scene["imt"]["country_bs"]
    assert len(sites) == 15                      # first of 2 subsets of 30 rows
    rows = [l.split(",") for l in f.read_text().splitlines()[1:16]]
    got = {(round(s["lat_deg"], 3), round(s["lon_deg"], 3)) for s in sites}
    want = {(round(float(r[0]), 3), round(float(r[1]), 3)) for r in rows}
    assert got == want                           # same lat/lon as the database rows
    # the scenario is centred on the database, not on the default reference
    assert abs(win.tab_imt.state.get("topo_c_lat").get() and float(win.tab_imt.state.get("topo_c_lat").get()) + 3.77) < 0.2
