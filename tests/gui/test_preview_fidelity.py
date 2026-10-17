"""O preview deve refletir o que o simulador fará (mesmo YAML, mesmas fábricas)."""
import json
import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GUI = os.path.join(_REPO, "sharc", "gui")
for _p in (_GUI, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _scene(win, topo):
    return json.loads(win.tab_preview._cesium_scene_provider(topo))


def test_macrocell_scene_matches_gui_parameters(win):
    st = win.tab_imt.state
    for key, val in {"topo_type": "MACROCELL", "macro_intersite": "2400", "macro_clusters": "1",
                     "bs_height": "25", "ue_height": "1.8", "ue_k": "4", "bs_downtilt": "10"}.items():
        st.get(key).set(val)
    scene = _scene(win, "MACROCELL")
    assert not scene.get("error"), scene.get("error")
    assert scene["source"] == "engine"
    assert len(scene["base_stations"]) == 57          # 19 sites x 3 setores
    assert len(scene["hex_centers"]) == 19
    assert len(scene["ue_positions"]) == 57 * 4       # k UEs por BS
    assert scene["bs_height_m"] == pytest.approx(25.0)
    assert scene["ue_height_m"] == pytest.approx(1.8)
    assert scene["downtilt_deg"] == pytest.approx(10.0)
    assert scene["hex_radius_m"] == pytest.approx(2400 / 3 ** 0.5)


def test_invalid_parameter_becomes_readable_error(win):
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    win.tab_imt.state.get("macro_intersite").set("abc")
    scene = _scene(win, "MACROCELL")
    assert "error" in scene and "intersite_distance" in scene["error"]
    win.tab_imt.state.get("macro_intersite").set("600")


def test_composite_scene_shows_imt_and_victim_system(win):
    win.var_system.set("SINGLE_EARTH_STATION")
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    scene = _scene(win, "SCENARIO")
    assert scene.get("composite") and not scene.get("error"), scene.get("error")
    assert len(scene["imt"]["base_stations"]) == 57
    assert scene["system"] is not None and "station" in scene["system"]
    # a estação-vítima fica no referencial do IMT
    assert scene["system"]["reference"]["lat_deg"] == pytest.approx(scene["imt"]["reference"]["lat_deg"])


def test_composite_with_satellite_victim(win):
    win.var_system.set("SINGLE_SPACE_STATION")
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    scene = _scene(win, "SCENARIO")
    assert scene.get("composite") and not scene.get("error"), scene.get("error")
    assert scene["system"]["satellite"]["alt_m"] == pytest.approx(35786000.0)
    # o satélite mira o centro da rede IMT
    assert scene["system"]["earth_station"]["lat_deg"] == pytest.approx(scene["imt"]["reference"]["lat_deg"])


def test_hotspot_scene_builds_with_numpy2(win):
    st = win.tab_imt.state
    st.get("topo_type").set("HOTSPOT")
    for key, val in {"hotspot_intersite": "1740", "hotspot_clusters": "1", "hotspot_num_per_cell": "1",
                     "hotspot_max_dist_ue": "100", "hotspot_min_dist_bs": "0"}.items():
        st.get(key).set(val)
    try:
        for _ in range(3):                      # hotspot placement is random; a rare draw can fail
            scene = _scene(win, "HOTSPOT")
            if not scene.get("error"):
                break
        assert not scene.get("error"), scene.get("error")
        assert scene["source"] == "engine" and scene["base_stations"]
    finally:
        st.get("topo_type").set("MACROCELL")


def test_eta_never_negative_and_orders_by_time():
    from main import _eta_seconds
    assert _eta_seconds("10:00:00") > _eta_seconds("9:59:59")
    assert _eta_seconds("1 day, 0:00:01") > _eta_seconds("23:59:59")
    assert _eta_seconds("garbage") == 0
