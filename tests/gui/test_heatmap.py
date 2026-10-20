"""Ground heat maps of the IMT network (PSD, strongest-BS power, I/N) computed from the engine scene."""
import json
import os
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

from core import heatmap  # noqa: E402


def _scene(win):
    st = win.tab_imt.state
    for key, val in {"topo_type": "MACROCELL", "macro_intersite": "800", "macro_clusters": "1"}.items():
        st.get(key).set(val)
    return json.loads(win.tab_preview._cesium_scene_provider("MACROCELL"))


def test_scene_carries_three_heat_maps_with_geo_bounds(win):
    heat = _scene(win)["heat"]
    assert heat and set(heat["maps"]) == {"psd", "power", "inr"}
    n = heat["n"]
    assert heat["west"] < heat["east"] and heat["south"] < heat["north"]
    for m in heat["maps"].values():
        assert len(m["values"]) == n * n and m["vmax"] > m["vmin"]
        assert np.isfinite(m["values"]).all()


def test_power_falls_with_distance_from_the_nearest_base_station(win):
    _scene(win)
    from core import engine_scene as eng
    es = list(eng._CACHE.values())[-1]
    heat = heatmap.compute(es)
    n = heat["n"]
    power = np.array(heat["maps"]["power"]["values"]).reshape(n, n)
    g = es.bs.geom
    ref = es.reference
    # a cell right under the central site is stronger than one at the edge of the grid
    centre = power[n // 2 - 3:n // 2 + 3, n // 2 - 3:n // 2 + 3].max()
    edge = power[:3, :3].max()
    assert centre > edge + 10.0
    assert ref["lat_deg"] == pytest.approx((heat["south"] + heat["north"]) / 2)
    assert len(g.x_global) == 57


def test_aggregate_is_never_below_the_strongest_single_station_psd(win):
    _scene(win)
    from core import engine_scene as eng
    es = list(eng._CACHE.values())[-1]
    heat = heatmap.compute(es)
    p = es.params.imt
    shift = 10 * np.log10(float(p.bandwidth))                    # total power -> per-MHz density
    psd = np.array(heat["maps"]["psd"]["values"])
    power = np.array(heat["maps"]["power"]["values"])
    assert (psd >= power - shift - 0.2).all()                    # aggregate >= strongest (rounding tolerance)


def test_inr_is_psd_minus_noise_floor(win):
    _scene(win)
    from core import engine_scene as eng
    es = list(eng._CACHE.values())[-1]
    heat = heatmap.compute(es)
    psd = np.array(heat["maps"]["psd"]["values"])
    inr = np.array(heat["maps"]["inr"]["values"])
    diff = psd - inr
    assert np.allclose(diff, diff[0], atol=0.2)                  # constant offset = victim noise PSD
    assert -125.0 < diff[0] < -100.0                             # about -114 dBm/MHz at 290 K
