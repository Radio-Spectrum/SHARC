"""3D antenna gain lobes: real engine gain, valid GLB, served by the preview, shipped in the scene."""
import json
import os
import struct
import sys

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import gain_lobe, model_factory  # noqa: E402


def _scene(win, topo="MACROCELL"):
    st = win.tab_imt.state
    for key, val in {"topo_type": topo, "macro_intersite": "800", "macro_clusters": "1", "bs_downtilt": "10"}.items():
        st.get(key).set(val)
    return json.loads(win.tab_preview._cesium_scene_provider(topo))


def _parse_glb(blob):
    magic, version, length = struct.unpack("<4sII", blob[:12])
    assert magic == b"glTF" and version == 2 and length == len(blob)
    jlen, jtype = struct.unpack("<I4s", blob[12:20])
    assert jtype == b"JSON"
    return json.loads(blob[20:20 + jlen])


def test_scene_carries_a_lobe_with_the_engine_peak_gain(win):
    scene = _scene(win)
    lobe = scene["lobe"]
    assert lobe and lobe["uri"].startswith("/models/lobe_") and lobe["uri"].endswith(".glb")
    assert 6.0 <= lobe["range_db"] <= gain_lobe.RANGE_DB and len(lobe["colors"]) == gain_lobe.N_BANDS
    # an IMT sector array peaks well above an isotropic radiator
    assert 10.0 < lobe["peak_dbi"] < 40.0


def test_lobe_glb_is_valid_and_served(win):
    lobe = _scene(win)["lobe"]
    name = lobe["uri"].rsplit("/", 1)[-1].replace(".glb", "")
    doc = _parse_glb(model_factory.glb(name))
    (prim,) = doc["meshes"][0]["primitives"]                       # one smooth surface
    assert "COLOR_0" in prim["attributes"]                          # per-vertex heat colours, like STK
    assert doc["accessors"][prim["attributes"]["COLOR_0"]]["type"] == "VEC4"


def test_jet_scale_runs_blue_to_red():
    lo, mid, hi = gain_lobe.jet(np.array([0.0, 0.5, 1.0]))
    assert lo[2] > lo[0] and lo[2] > lo[1]            # cold end is blue
    assert mid[1] > mid[0] and mid[1] > mid[2]        # middle is green
    assert hi[0] > hi[1] and hi[0] > hi[2]            # hot end is red


def test_lobe_shape_main_beam_points_forward_and_down(win):
    es_scene = _scene(win)
    from core import engine_scene as eng
    es = next(iter(eng._CACHE.values()))
    data = gain_lobe.sample_bs_gain(es)
    peak = data["peak"]
    e_i, p_i = np.unravel_index(np.argmax(data["gain"]), data["gain"].shape)
    assert abs(data["dphi"][p_i]) <= 6.0                          # peak close to the sector azimuth
    assert data["elev"][e_i] == pytest.approx(data["el"], abs=8.0)  # and to the electrical downtilt
    side = data["gain"][e_i, int(np.argmin(abs(data["dphi"] - 90.0)))]   # broadside to the sector
    assert side < peak - 10.0
    assert es_scene["downtilt_deg"] == pytest.approx(10.0)


def test_lobe_model_geometry_is_closed_and_bounded(win):
    _scene(win)
    from core import engine_scene as eng
    es = next(iter(eng._CACHE.values()))
    model = gain_lobe.build_lobe_model(gain_lobe.sample_bs_gain(es))
    for part in model.parts:
        assert part.colors is not None and part.colors.shape == (len(part.positions), 4)
        assert np.isfinite(part.positions).all() and np.isfinite(part.normals).all()
        assert np.linalg.norm(part.positions, axis=1).max() <= 1.0 + 1e-4   # unit radius at the peak
        assert part.indices.max() < len(part.positions)


def test_unknown_model_still_raises():
    with pytest.raises(KeyError):
        model_factory.glb("definitely_not_a_model")


def test_victim_system_gets_a_lobe_from_the_engine_antenna(win):
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    system = scene.get("system")
    assert system is not None, "default scenario has a victim system"
    lobe = system["lobe"]
    assert lobe and lobe["uri"].startswith("/models/syslobe_")
    assert lobe["peak_dbi"] > 10.0                               # a dish or satellite beam is directive
    doc = _parse_glb(model_factory.glb(lobe["uri"].rsplit("/", 1)[-1].replace(".glb", "")))
    assert "COLOR_0" in doc["meshes"][0]["primitives"][0]["attributes"]
