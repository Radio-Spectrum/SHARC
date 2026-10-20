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
    scenes = [e for e in eng._CACHE.values() if str(e.params.general.system).upper() == "SINGLE_SPACE_STATION"]
    return scenes[-1]


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
