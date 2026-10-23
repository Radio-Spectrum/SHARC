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


def current_engine_scene(win):
    """Engine scene of the YAML now in the GUI. `eng._CACHE` keeps an old entry in place on a hit, so its last item is not it."""
    from core import engine_scene as eng
    return eng.build_engine_scene(win.tab_preview._current_yaml())


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
    es = current_engine_scene(win)
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
    es = current_engine_scene(win)
    heat = heatmap.compute(es)
    p = es.params.imt
    shift = 10 * np.log10(float(p.bandwidth))                    # total power -> per-MHz density
    psd = np.array(heat["maps"]["psd"]["values"])
    power = np.array(heat["maps"]["power"]["values"])
    assert (psd >= power - shift - 0.2).all()                    # aggregate >= strongest (rounding tolerance)


def test_inr_is_psd_minus_noise_floor(win):
    _scene(win)
    es = current_engine_scene(win)
    heat = heatmap.compute(es)
    psd = np.array(heat["maps"]["psd"]["values"])
    inr = np.array(heat["maps"]["inr"]["values"])
    diff = psd - inr
    assert np.allclose(diff, diff[0], atol=0.2)                  # constant offset = victim noise PSD
    assert -125.0 < diff[0] < -100.0                             # about -114 dBm/MHz at 290 K


def test_heat_map_lists_base_stations_for_figures(win):
    heat = _scene(win)["heat"]
    assert heat["n"] >= 100 and len(heat["bs_km"]) > 0
    assert all(len(p) == 2 for p in heat["bs_km"])


def _engine_scene(win):
    _scene(win)
    return current_engine_scene(win)


def test_free_space_loss_matches_the_engine_propagation_class(win):
    from core import gain_lobe
    from sharc.propagation.propagation_free_space import PropagationFreeSpace
    es = _engine_scene(win)
    data = gain_lobe.sample_bs_gain(es)
    px = np.array([100.0, -350.0, 900.0])
    py = np.array([40.0, 700.0, -250.0])
    _, _, _, fspl, dist = heatmap.levels(es, data, px, py, 1.5)
    f = float(es.params.imt.frequency)
    ref = PropagationFreeSpace(np.random.RandomState(1)).get_free_space_loss(frequency=f, distance=dist)
    assert np.allclose(fspl, ref, atol=0.05)


def test_sector_gain_matches_the_engine_antenna_toward_each_receiver(win):
    import copy
    from core import gain_lobe
    es = _engine_scene(win)
    data = gain_lobe.sample_bs_gain(es)
    g = es.bs.geom
    rng = np.random.RandomState(7)
    k = 5
    bx, by, bz = float(g.x_global[k]), float(g.y_global[k]), float(g.z_global[k])
    px, py = bx + rng.uniform(-900, 900, 150), by + rng.uniform(-900, 900, 150)
    _, _, gain, _, _ = heatmap.levels(es, data, px, py, 1.5)
    az, el = float(g.pointn_azim_global[k]), float(g.pointn_elev_global[k])
    ant = copy.deepcopy(es.bs.antenna[k])                          # each sector antenna is mounted with its own orientation
    ant.beams_list, ant.w_vec_list = [], []
    if hasattr(ant, "co_correction_factor_list"):
        ant.co_correction_factor_list = []
    ant.add_beam(az, 90.0 - el)
    phi = np.degrees(np.arctan2(py - by, px - bx))
    theta = 90.0 - np.degrees(np.arctan2(1.5 - bz, np.hypot(px - bx, py - by)))
    direct = np.asarray(ant.calculate_gain(phi_vec=phi, theta_vec=theta, beams_l=np.zeros(phi.size, dtype=int)), float)
    err = np.abs(gain[:, k] - direct)
    assert np.percentile(err, 90) < 1.5 and err.max() < 6.0        # grid interpolation only, at 3 x 2.5 deg steps


def test_eirp_and_noise_budget_close_by_hand(win):
    from core import gain_lobe
    es = _engine_scene(win)
    data = gain_lobe.sample_bs_gain(es)
    p = es.params.imt
    psd_m, power_m, gain, fspl, _ = heatmap.levels(es, data, np.array([250.0]), np.array([120.0]), 1.5)
    eirp = float(p.bs.conducted_power) - float(p.bs.ohmic_loss)
    assert np.allclose(power_m, eirp + gain - fspl)
    assert np.allclose(psd_m, power_m - 10 * np.log10(float(p.bandwidth)))


def test_gui_downtilt_reaches_the_engine_and_changes_the_ground_map(win):
    st = win.tab_imt.state
    values = {}
    for tilt in ("0", "10"):
        st.get("bs_downtilt").set(tilt)
        _scene(win)
        es = current_engine_scene(win)
        assert np.allclose(es.bs.geom.pointn_elev_global, -float(tilt))
        values[tilt] = np.array(heatmap.compute(es)["maps"]["power"]["values"])
    assert not np.allclose(values["0"], values["10"])          # a tilted beam lights the ground differently
