"""Satellite footprint (gain, PSD on the ground) and the IMT interference at the satellite receiver."""
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

from core import sat_footprint  # noqa: E402


def _es(win):
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    from core import engine_scene as eng
    return eng.build_engine_scene(win.tab_preview._current_yaml())     # the cache keeps old entries in place on a hit


def test_footprint_gain_peaks_at_the_centre_and_falls_off(win):
    fp = sat_footprint.compute(_es(win))
    assert fp, "default scenario has a space station"
    n = fp["n"]
    g = np.array(fp["maps"]["sat_gain"]["values"]).reshape(n, n)
    assert g[n // 2, n // 2] == pytest.approx(g.max(), abs=1.0)          # boresight at nadir = grid centre
    assert g[0, 0] < g.max() - 3.0                                        # corners are outside the 3 dB beam
    assert fp["west"] < fp["east"] and fp["south"] < fp["north"]


def test_summary_has_a_consistent_interference_budget(win):
    s = sat_footprint.compute(_es(win))["summary"]
    assert 30000 < s["altitude_km"] < 40000                               # GSO by default
    assert s["beamwidth_deg"] > 0 and s["peak_gain_dbi"] > 20
    if s["pointing_type"] == "POINTING_AT_IMT":                           # the beam is aimed at the network
        assert s["gain_toward_network_dbi"] == pytest.approx(s["peak_gain_dbi"], abs=1.5)
    assert s["inr_db"] == pytest.approx(s["imt_psd_at_sat_dbm_mhz"] - s["noise_psd_dbm_mhz"], abs=0.11)
    assert s["n_bs"] == 57


def test_psd_footprint_is_present_when_the_system_has_a_tx_psd(win):
    fp = sat_footprint.compute(_es(win))
    psd = fp["maps"].get("sat_psd")
    assert psd is None or (psd["unit"] == "dBm/MHz" and psd["vmax"] > psd["vmin"])


def test_composite_scene_ships_the_footprint(win):
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    assert scene["system"]["footprint"]["summary"]["inr_db"] is not None


def test_roles_and_per_bs_contributions(win):
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    info = scene["imt"]["interference"]
    assert info["roles"] == {"imt": "interferer", "system": "victim"}      # default: IMT interferes with the system
    assert scene["system"]["roles"] == info["roles"]
    assert len(info["contrib"]) == 57 and info["cmin"] <= info["cmax"]
    # the aggregate is never below the strongest single base station
    assert info["psd_dbm_mhz"] >= info["cmax"] - 0.2
    assert info["inr_db"] == pytest.approx(info["psd_dbm_mhz"] - info["noise_psd_dbm_mhz"], abs=0.11)


def test_earth_station_victim_gets_contributions_too(win):
    win.var_system.set("SINGLE_EARTH_STATION")
    try:
        win.tab_imt.state.get("topo_type").set("MACROCELL")
        scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
        info = (scene.get("imt") or {}).get("interference")
        assert info and info["roles"]["system"] == "victim"
        assert info.get("victim_name") == "earth station" and len(info["contrib"]) == 57
        assert info["psd_dbm_mhz"] >= info["cmax"] - 0.2
    finally:
        win.var_system.set("SINGLE_SPACE_STATION")


def test_footprint_is_centred_on_where_the_engine_points_the_satellite(win):
    fp = sat_footprint.compute(_es(win))
    ref = _es(win).reference
    lat_c, lon_c = (fp["south"] + fp["north"]) / 2, (fp["west"] + fp["east"]) / 2
    assert fp["pointing"]["target_lat_deg"] == pytest.approx(ref["lat_deg"], abs=0.6)     # POINTING_AT_IMT
    assert fp["pointing"]["target_lon_deg"] == pytest.approx(ref["lon_deg"], abs=0.6)
    assert lat_c == pytest.approx(fp["pointing"]["target_lat_deg"], abs=0.01)
    assert lon_c == pytest.approx(fp["pointing"]["target_lon_deg"], abs=0.01)


def test_antenna_failure_is_reported_in_the_scene_not_hidden(win, monkeypatch):
    win.tab_imt.state.get("topo_type").set("MACROCELL")
    clean = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    assert not clean.get("warnings")

    from core import antenna_service

    def boom(block):
        raise ValueError("Unknown antenna pattern: 'X'")
    monkeypatch.setattr(antenna_service, "build_antenna_from_block", boom)
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    assert any("Unknown antenna pattern" in w for w in scene["warnings"])

    monkeypatch.undo()
    assert not json.loads(win.tab_preview._cesium_scene_provider("SCENARIO")).get("warnings")   # cleared on the next scene


# ------------------------------------------------- the footprint follows the antenna type (gain, directivity, shape)
def _taylor(l_r, l_t):
    from core.antenna_service import build_antenna
    return build_antenna("ITU-R-S.1528-Taylor", {"frequency": 2170.0, "antenna_gain": 35.0, "l_r": l_r, "l_t": l_t})


def _peak(ant):
    import numpy as np
    from core.antenna_service import gain_at
    return float(np.nanmax(gain_at(ant, np.linspace(0, 0.5, 11), np.zeros(11))))


def test_beamwidths_directivity_follow_the_pattern():
    from core.antenna_service import build_antenna
    s672 = build_antenna("ITU-R S.672", {"antenna_gain": 40, "antenna_3_dB_bw": 0.6, "antenna_l_s": -25})
    bw, bw_minor = sat_footprint._beamwidths_deg(s672, 40.0)
    assert bw == pytest.approx(0.6, abs=0.02) and bw_minor == pytest.approx(0.6, abs=0.02)
    d, _ = sat_footprint.pattern_directivity(s672, 40.0)
    assert d == pytest.approx(40.0, abs=1.5)                    # a consistent pattern: directivity ~ gain

    round_, ellipse = _taylor(1.6, 1.6), _taylor(1.6, 0.8)
    r_major, r_minor = sat_footprint._beamwidths_deg(round_, _peak(round_))
    e_major, e_minor = sat_footprint._beamwidths_deg(ellipse, _peak(ellipse))
    assert r_major == pytest.approx(r_minor, rel=0.02)
    assert e_major == pytest.approx(2.0 * e_minor, rel=0.08)    # half the aperture: twice the beamwidth in that plane
    d_round, _ = sat_footprint.pattern_directivity(round_, _peak(round_))
    d_ellipse, _ = sat_footprint.pattern_directivity(ellipse, _peak(ellipse))
    assert d_ellipse < d_round - 2.0      # same peak gain input, but the wider beam has less directivity: they differ


def test_footprint_shape_and_summary_change_with_the_antenna(win):
    import numpy as np
    es = _es(win)
    old = es.system.antenna
    old_fp = getattr(es, "_sat_footprint", "unset")
    shapes = {}
    try:
        for name, ant in (("round", _taylor(1.6, 1.6)), ("ellipse", _taylor(1.6, 0.8))):
            es.system.antenna = [ant]
            es._sat_footprint = "unset"
            fp = sat_footprint.compute(es)
            n = fp["n"]
            g = np.array(fp["maps"]["sat_gain"]["values"]).reshape(n, n)
            inside = g >= fp["maps"]["sat_gain"]["vmax"] - 3.0                # the -3 dB beam
            rows, cols = np.nonzero(inside)
            shapes[name] = ((cols.max() - cols.min() + 1) * (fp["east"] - fp["west"]),
                            (rows.max() - rows.min() + 1) * (fp["north"] - fp["south"]), fp["summary"])
    finally:
        es.system.antenna = old
        if old_fp == "unset":
            es.__dict__.pop("_sat_footprint", None)
        else:
            es._sat_footprint = old_fp
    (rw, rh, rs), (ew, eh, ens) = shapes["round"], shapes["ellipse"]
    assert 0.8 < rw / rh < 1.25                                  # a round beam gives a round footprint
    assert not (0.7 < ew / eh < 1.4)                             # an elliptical one does not
    assert ens["beamwidth_deg"] == pytest.approx(2.0 * ens["beamwidth_minor_deg"], rel=0.1)
    assert ens["directivity_dbi"] < rs["directivity_dbi"] - 2.0
    assert isinstance(ens["antenna_pattern"], str)               # the configured pattern name is reported


def test_3d_lobe_is_not_circular_for_an_elliptical_antenna():
    import numpy as np
    from core import gain_lobe
    round_ = gain_lobe.sample_axisymmetric_gain(_taylor(1.6, 1.6))
    ellipse = gain_lobe.sample_axisymmetric_gain(_taylor(1.6, 0.8))

    def at(d, az_off, el):                                        # gain at an azimuth offset / elevation of the lobe grid
        i = int(np.argmin(abs(d["elev"] - el)))
        j = int(np.argmin(abs(d["dphi"] - az_off)))
        assert abs(d["elev"][i] - el) < 1e-6 and abs(d["dphi"][j] - az_off) < 1e-6      # the angle exists on both grids
        return float(d["gain"][i, j])
    for angle in (15.0, 30.0):                                    # on the 3 deg azimuth grid and on the 2.5 deg elevation grid
        assert abs(at(round_, angle, 0.0) - at(round_, 0.0, angle)) < 0.5
    assert max(abs(at(ellipse, a, 0.0) - at(ellipse, 0.0, a)) for a in (15.0, 30.0)) > 1.5
