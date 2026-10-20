"""UE links with a link budget, HUD plot data and the snapshot sequence, all from the engine scene."""
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

from core import preview_extras  # noqa: E402


def _scene(win):
    st = win.tab_imt.state
    for key, val in {"topo_type": "MACROCELL", "macro_intersite": "800", "macro_clusters": "1"}.items():
        st.get(key).set(val)
    return json.loads(win.tab_preview._cesium_scene_provider("MACROCELL"))


def test_links_carry_a_consistent_link_budget(win):
    links = _scene(win)["links"]
    assert links and len(links) <= preview_extras.MAX_LINKS
    for k in links:
        # P_rx = P_tx + G_tx - FSPL + G_rx - body loss   (all in dB / dBm)
        expect = k["tx_power_dbm"] + k["g_tx_dbi"] - k["fspl_db"] + k["g_rx_dbi"] - k["body_loss_db"]
        assert k["rx_power_dbm"] == pytest.approx(expect, abs=0.31)
        assert k["snr_db"] == pytest.approx(k["rx_power_dbm"] - k["noise_dbm"], abs=0.11)
        assert k["dist_m"] > 0 and 0 <= k["bs"] < 57


def test_serving_station_is_the_strongest_one(win):
    _scene(win)
    from core import engine_scene as eng, gain_lobe, heatmap
    es = list(eng._CACHE.values())[-1]
    link = preview_extras.links(es)[0]
    data = gain_lobe.sample_bs_gain(es)
    ux, uy, uz = link["ue_xyz"]
    _psd, power, *_ = heatmap.levels(es, data, np.array([ux]), np.array([uy]), uz)
    assert int(power[0].argmax()) == link["bs"]


def test_plots_describe_the_imt_psd_and_the_inr_cdf(win):
    plots = _scene(win)["plots"]
    assert plots["imt"]["bandwidth_mhz"] > 0 and plots["imt"]["freq_mhz"] > 0
    cdf = plots["cdf"]
    assert len(cdf["x"]) == len(cdf["p"]) == 60
    assert cdf["x"] == sorted(cdf["x"]) and cdf["p"][0] == 0.0 and cdf["p"][-1] == 1.0


def test_snapshots_redraw_the_ues_each_time(win):
    snaps = _scene(win)["snapshots"]
    assert len(snaps) == preview_extras.N_SNAPSHOTS
    assert all(len(s["x"]) == len(s["y"]) == 57 for s in snaps)
    assert snaps[0]["x"] != snaps[1]["x"]                       # different draw per snapshot
    assert all(len(s["bs"]) == len(s["snr"]) == 57 and max(s["bs"]) < 57 for s in snaps)
