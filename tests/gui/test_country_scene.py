"""Macro_countries preview data: sites, UEs, links and ground maps on the sphere (core/country_scene.py)."""
import math
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

_YAML = os.path.join(_REPO, "sharc", "campaigns", "IMT_TO_SES_Database", "input", "teste_instalacao.yaml")


@pytest.fixture(scope="module")
def es():
    yaml = pytest.importorskip("yaml")
    if not os.path.isfile(_YAML):
        pytest.skip("campaign YAML not available")
    from core.engine_scene import build_engine_scene
    with open(_YAML, encoding="utf-8") as fh:
        data = yaml.unsafe_load(fh)                       # the repo's own file: it carries python/tuple tags
    data.pop("database", None)                            # the CSV is not versioned; random sites instead
    mc = data["imt"]["topology"]["macrocell_countries"]
    mc["num_bs_total"], mc["cell_radius"] = 40, 2000.0
    return build_engine_scene(data)


@pytest.fixture(scope="module")
def built(es):
    from core import country_scene
    return country_scene.build(es)


def test_build_has_every_decoration_and_no_problems(built, es):
    assert built["problems"] == []
    assert len(built["sites"]) == es.bs.geom.num_geometries
    assert built["lobe"] and built["heat"] and built["links"]
    assert built["cell_radius_m"] == pytest.approx(2000.0)


def test_site_height_is_the_configured_antenna_height(built, es):
    """A wrong Earth radius shows up here as ~7 km of height (the engine sphere is 6378.145 km)."""
    assert np.allclose([s["height_m"] for s in built["sites"]], float(es.params.imt.bs.height), atol=0.5)


def test_sector_downtilt_is_the_site_frame_value_not_the_global_one(built, es):
    expected = -float(np.asarray(es.bs.geom.pointn_elev_local)[0])
    assert built["sites"][0]["downtilt_deg"] == pytest.approx(expected)
    global_el = np.asarray(es.bs.geom.pointn_elev_global)
    assert np.ptp(global_el) > 5.0                          # the global one varies with Earth curvature: unusable


def test_links_use_the_engine_association_and_stay_inside_the_cell(built, es):
    k = int(es.params.imt.ue.k)
    assert all(link["bs"] == link["ue"] // k for link in built["links"])
    assert max(link["dist_m"] for link in built["links"]) < 2.5 * built["cell_radius_m"]


def test_gain_toward_a_point_on_the_boresight_matches_the_antenna_table(es):
    """Receiver 1 km from site 0 along its azimuth: dphi = 0 and elevation = -atan((h - 1.5) / 1 km)."""
    from core import country_scene as cs, gain_lobe
    sites = cs.Sites(es)
    data = gain_lobe.sample_bs_gain(es, local_frame=True)
    az, d = math.radians(sites.az[0]), 1000.0
    lat = sites.lat[0] + math.degrees(d * math.sin(az) / cs.EARTH_RADIUS_M)
    lon = sites.lon[0] + math.degrees(d * math.cos(az) / (cs.EARTH_RADIUS_M * math.cos(math.radians(sites.lat[0]))))
    _psd, _pw, gain, fspl, dist = cs.levels(es, sites, data, np.array([lat]), np.array([lon]), 1.5)
    elev = -math.degrees(math.atan2(float(sites.height[0]) - 1.5, d))
    assert gain[0, 0] == pytest.approx(float(cs._interp(data)([[elev, 0.0]])[0]), abs=0.3)
    assert dist[0, 0] == pytest.approx(math.hypot(d, float(sites.height[0]) - 1.5), rel=1e-3)
    f = float(es.params.imt.frequency)
    assert fspl[0, 0] == pytest.approx(32.44 + 20 * math.log10(dist[0, 0] / 1000) + 20 * math.log10(f), abs=1e-6)


def test_heat_grid_covers_all_sites_and_is_finite(built):
    h = built["heat"]
    lats = [s["lat_deg"] for s in built["sites"]]
    lons = [s["lon_deg"] for s in built["sites"]]
    assert h["south"] < min(lats) and h["north"] > max(lats) and h["west"] < min(lons) and h["east"] > max(lons)
    for m in h["maps"].values():
        assert len(m["values"]) == h["n"] ** 2 and np.isfinite(m["values"]).all() and m["vmax"] > m["vmin"]


# ── other topologies, through the real GUI -> YAML -> engine -> scene path ───────────────────────────────────────

def _scene(win, topo, system=None):
    import json
    if system:
        win.var_system.set(system)
    win.tab_imt.state.get("topo_type").set(topo)
    return json.loads(win.tab_preview._cesium_scene_provider(system or topo))


def _engine(win):
    from core.engine_scene import build_engine_scene
    return build_engine_scene(win.tab_preview._current_yaml())


def test_hotspot_defaults_build(win):
    """The default hotspot parameters used to make the engine loop ('Infinite loop while creating hotspots')."""
    scene = _scene(win, "HOTSPOT")
    assert not scene.get("error"), scene.get("error")
    assert scene["base_stations"] and scene["ue_positions"]


def test_indoor_uses_the_engine_ues_and_has_layers(win):
    scene = _scene(win, "INDOOR")
    es = _engine(win)
    assert scene["source"] == "engine"
    assert len(scene["ue_positions"]) == min(int(es.ue.geom.num_geometries), 600)
    assert scene["lobe"] and scene["heat"] and scene["links"]


def test_ntn_uses_the_engine_ues(win):
    scene = _scene(win, "NTN")
    es = _engine(win)
    assert scene["source"] == "engine"
    xs = np.asarray(es.ue.geom.x_global, float)
    assert [round(u["x"], 3) for u in scene["ue_positions"]] == [round(float(v), 3) for v in xs[:len(scene["ue_positions"])]]


def test_mss_dc_draws_the_constellation_with_ues_inside_footprints(win):
    from core import country_scene as cs
    from core.engine_scene import station_lat_lon
    scene = _scene(win, "MSS_DC")
    c = scene["constellation"]
    es = _engine(win)
    assert c["beams_missing"] == 0 and len(c["beams"]) == int(es.bs.geom.num_geometries)
    assert all(abs(s["alt_m"] - 525_000.0) < 1_000.0 for s in c["satellites"])          # the configured orbit
    # Independent check of the footprint centres: the engine puts each UE inside a beam, so the nearest centre of
    # every UE has to be within about one beam radius (a wrong pointing convention puts the median hundreds of km off).
    ulat, ulon = station_lat_lon(es, es.ue.geom)
    u = cs._ecef(ulat, ulon, cs.EARTH_RADIUS_M)
    b = cs._ecef([x["lat_deg"] for x in c["beams"]], [x["lon_deg"] for x in c["beams"]], cs.EARTH_RADIUS_M)
    nearest = np.array([np.linalg.norm(b - p, axis=1).min() for p in u[::10]])
    assert np.median(nearest) < c["beam_radius_m"]
    assert np.percentile(nearest, 90) < 1.5 * c["beam_radius_m"]


def test_mss_d2d_as_system_draws_the_engine_constellation(win):
    scene = _scene(win, "MACROCELL", system="MSS_D2D")
    c = scene.get("constellation")
    assert c is not None and scene.get("as_system") is True
    assert c["beams_missing"] == 0 and c["satellites"] and c["ue_total"] == 0
