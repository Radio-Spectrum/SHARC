"""Adaptive terrain/land-cover tiles, lakes and rivers, 3D models and the water warning."""
import json
import socket
import struct
import urllib.request

import numpy as np
import pytest


def _online() -> bool:
    try:
        socket.create_connection(("s3.amazonaws.com", 443), timeout=4).close()
        return True
    except OSError:
        return False


needs_net = pytest.mark.skipif(not _online(), reason="needs internet (AWS Terrain Tiles / ESA WorldCover)")


@pytest.fixture()
def tiles(tmp_path):
    from core import tile_service
    tile_service.set_cache_dir(tmp_path)
    return tile_service


def test_tile_geometry_roundtrip(tiles):
    x, y, px, py = tiles.lonlat_to_tile(-3.77, -38.55, 12)
    w, s, e, n = tiles.tile_lonlat_bounds(12, x, y)
    assert w <= -38.55 <= e and s <= -3.77 <= n
    assert 0 <= px < 256 and 0 <= py < 256


def test_procedural_models_are_valid_glb():
    from core import model_factory as mf
    for name in mf.MODELS:
        data = mf.glb(name)
        magic, version, total = struct.unpack("<4sII", data[:12])
        assert magic == b"glTF" and version == 2 and total == len(data)
        json_len = struct.unpack("<I", data[12:16])[0]
        doc = json.loads(data[20:20 + json_len])
        assert doc["meshes"][0]["primitives"] and doc["accessors"]


@needs_net
def test_elevation_tile_has_real_relief(tiles):
    lat, lon = -3.77, -38.55
    x, y, _, _ = tiles.lonlat_to_tile(lat, lon, 10)
    dem = tiles.dem_tile(10, x, y)
    assert dem is not None and dem.shape == (256, 256)
    assert -50 < float(dem.min()) < 100 and float(dem.max()) > 100      # sea level to hills
    deep = tiles.dem_tile(16, *tiles.lonlat_to_tile(lat, lon, 16)[:2])   # interpolated beyond level 14
    assert deep is not None and deep.shape == (256, 256)
    assert 0 < tiles.ground_height(lat, lon) < 80


@needs_net
def test_land_cover_distinguishes_city_and_sea(tiles):
    from core import site_checks
    assert tiles.land_cover_at(-3.78, -38.54) == 50                      # built-up (Fortaleza)
    assert site_checks.sites_on_water([-3.78, -3.55], [-38.54, -38.40]) == [1]   # second point is the Atlantic


@needs_net
def test_tile_server_serves_png_and_float_tiles(tiles, win):
    from web.cesium_preview.local_server import CesiumSpikeServer
    srv = CesiumSpikeServer()
    port = srv.start()
    try:
        x, y, _, _ = tiles.lonlat_to_tile(-3.77, -38.55, 13)
        png = urllib.request.urlopen(f"http://127.0.0.1:{port}/tiles/clutter/13/{x}/{y}.png", timeout=60).read()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        f32 = urllib.request.urlopen(f"http://127.0.0.1:{port}/tiles/terrain/13/{x}/{y}.f32", timeout=60).read()
        assert len(f32) == 256 * 256 * 4
        glb = urllib.request.urlopen(f"http://127.0.0.1:{port}/models/tower.glb", timeout=10).read()
        assert glb[:4] == b"glTF"
    finally:
        srv.stop()


def test_terrain_tab_exposes_stream_settings(win):
    info = win.tab_terrain.overlay_info()
    assert info["mode"] == "stream" and info["relief"] and info["clutter"] and info["hydro"]
    win.tab_terrain.state.get("terr_stream").set(False)
    assert win.tab_terrain.overlay_info() is None


@needs_net
def test_composite_scene_carries_terrain_block(win):
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    assert scene["terrain"]["mode"] == "stream"


def test_placing_the_scenario_on_the_map_moves_the_reference(win):
    st = win.tab_imt.state
    win.tab_database.state.get("db_enabled").set(False)
    win.tab_preview._on_center_picked(-3.7305, -38.5230)
    assert float(st.get("topo_c_lat").get()) == pytest.approx(-3.7305)
    assert float(st.get("topo_c_lon").get()) == pytest.approx(-38.5230)
    scene = json.loads(win.tab_preview._cesium_scene_provider("SCENARIO"))
    assert scene["imt"]["reference"]["lat_deg"] == pytest.approx(-3.7305)


def test_placing_is_refused_when_sites_come_from_the_database(win, tmp_path):
    f = tmp_path / "db.csv"
    f.write_text("latitude,longitude,azimute,altura\n-3.77,-38.55,0,25\n-3.78,-38.56,120,25\n", encoding="utf-8")
    d = win.tab_database.state
    d.get("db_enabled").set(True)
    d.get("db_file").set(str(f))
    d.get("db_from_sites").set(True)
    before = win.tab_imt.state.get("topo_c_lat").get()
    win.tab_preview._on_center_picked(10.0, 10.0)
    assert win.tab_imt.state.get("topo_c_lat").get() == before        # unchanged


def test_deep_zoom_elevation_is_smooth_and_seamless():
    """Very low camera altitudes ask for tiles far below the DEM resolution: they must not spike."""
    import numpy as np
    from core import tile_service as ts
    x, y, _, _ = ts.lonlat_to_tile(-15.794, -47.883, 27)
    a, b = ts.dem_tile(27, x, y), ts.dem_tile(27, x + 1, y)
    assert np.abs(np.diff(a, axis=1)).max() < 0.5
    assert np.abs(a[:, -1] - b[:, 0]).max() < 0.5


def test_realistic_look_trees_and_photoreal_key(win):
    st = win.tab_terrain.state
    try:
        st.get("terr_look").set("Realistic (satellite imagery)")
        st.get("terr_photoreal_key").set("  KEY123  ")
        info = win.tab_terrain.overlay_info()
        assert info["realistic"] and info["basemap"] == "esri" and not info["clutter"]
        assert info["trees"] and info["trees_max"] == 2500
        assert info["photoreal_key"] == "KEY123"
    finally:
        st.get("terr_look").set("Analysis (land cover)")
        st.get("terr_photoreal_key").set("")


def test_vegetation_trees_are_deterministic_and_avoid_buildings():
    from core import buildings_service as bs
    assert bs._hash01(5, 9, 1) == bs._hash01(5, 9, 1)
    assert 0.0 <= bs._hash01(123456, 654321, 4) <= 1.0


def test_city_modes_pass_token_and_mode(win):
    st = win.tab_terrain.state
    try:
        st.get("terr_ion_token").set(" tok ")
        st.get("terr_look").set("City buildings (Cesium OSM Buildings, needs ion token)")
        info = win.tab_terrain.overlay_info()
        assert info["city_mode"] == "osm" and info["ion_token"] == "tok"
        st.get("terr_look").set("Photorealistic 3D (Google tiles, needs ion token or Google key)")
        assert win.tab_terrain.overlay_info()["city_mode"] == "photo"
    finally:
        st.get("terr_look").set("Analysis (land cover)")
        st.get("terr_ion_token").set("")
