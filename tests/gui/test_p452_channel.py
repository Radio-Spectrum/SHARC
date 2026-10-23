"""Canal P.452 (com clutter) da Single Earth Station: o YAML da GUI tem de chegar ao motor."""
import os
import sys

import pytest
import yaml

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_in_engine(y, tmp_path):
    from sharc.parameters.parameters import Parameters
    f = tmp_path / "t.yaml"
    f.write_text(yaml.safe_dump(y), encoding="utf-8")
    p = Parameters()
    p.set_file_name(str(f))
    p.read_params()
    return p


@pytest.mark.parametrize("polarization", ["horizontal", "vertical"])
@pytest.mark.parametrize("clutter", [False, True])
def test_p452_with_and_without_clutter_reaches_the_engine(win, tmp_path, polarization, clutter):
    from core.yaml_builder import build_yaml_structure
    win.var_system.set("SINGLE_EARTH_STATION")
    win.se_channel_model.set("P452")
    win.p452_clutter_loss.set(clutter)
    win.p452_clutter_type.set("both_ends")
    win.p452_polarization.set(polarization)
    win.p452_Hre.set(12.0)

    y = build_yaml_structure(win)
    block = y["single_earth_station"]["param_p452"]
    assert block["clutter_loss"] is clutter
    assert block["clutter_type"] == "both_ends"
    assert block["polarization"] == polarization
    assert block["Hre"] == 12.0

    p = _load_in_engine(y, tmp_path)
    p452 = p.single_earth_station.param_p452
    assert p452.clutter_loss is clutter
    assert p452.polarization == polarization
    assert p452.Hre == 12.0


def test_legacy_numeric_polarization_falls_back_to_horizontal(win):
    from core.yaml_builder import build_yaml_structure
    win.var_system.set("SINGLE_EARTH_STATION")
    win.se_channel_model.set("P452")
    win.p452_polarization.set(0.0)
    assert build_yaml_structure(win)["single_earth_station"]["param_p452"]["polarization"] == "horizontal"


def test_database_options_reach_the_yaml_and_the_engine(win, tmp_path):
    from core.yaml_builder import build_yaml_structure
    win.var_system.set("SINGLE_EARTH_STATION")
    win.se_channel_model.set("P452")
    win.se_loc_type.set("FIXED_GEO")
    win.se_loc_geo_lat.set(-3.8735)
    win.se_loc_geo_lon.set(-38.42216)
    win.se_loc_geo_alt.set(30.0)
    win.p452_hte_from_db.set(True)
    win.p452_profile_source.set("mesh")
    win.p452_profile_step_m.set(50.0)
    win.p452_clutter_heights.set("p452_tab3")
    win.p452_clutter_raster.set("")

    y = build_yaml_structure(win)
    ses = y["single_earth_station"]
    assert ses["geometry"]["location"]["fixed_geo"] == {
        "latitude": -3.8735, "longitude": -38.42216, "altitude": 30.0}
    blk = ses["param_p452"]
    assert blk["hte_from_db"] is True and blk["override_from_db"] is False
    assert blk["profile_source"] == "mesh" and blk["profile_step_m"] == 50.0
    assert blk["clutter_heights"] == "p452_tab3"
    assert blk["profile_raster"] == "" and blk["clutter_raster"] == "" and blk["zone_raster"] == ""

    p = _load_in_engine(y, tmp_path)
    assert p.single_earth_station.geometry.location.type == "FIXED_GEO"
    assert p.single_earth_station.geometry.location.fixed_geo.latitude == -3.8735
    assert p.single_earth_station.param_p452.hte_from_db is True
    assert p.single_earth_station.param_p452.profile_step_m == 50.0


def test_raster_paths_are_written_absolute(win):
    from core.yaml_builder import build_yaml_structure
    win.var_system.set("SINGLE_EARTH_STATION")
    win.p452_zone_raster.set("zones.tif")
    blk = build_yaml_structure(win)["single_earth_station"]["param_p452"]
    assert os.path.isabs(blk["zone_raster"]) and blk["zone_raster"].endswith("zones.tif")


def test_override_status_lists_what_is_missing_then_apply_fixes_it(win):
    section = win.tab_station.chan_section
    win.se_channel_model.set("P452")
    win.se_loc_type.set("FIXED")
    db = win.tab_database.state
    db.get("db_enabled").set(False)
    db.get("db_file").set("")
    win.p452_override_from_db.set(True)
    assert "FIXED_GEO" in section.lbl_db_status.text()
    assert "Database tab" in section.lbl_db_status.text()

    section.apply_required_settings()
    assert win.se_loc_type.get() == "FIXED_GEO"
    assert str(db.get("db_use_terrain").get()).lower() in ("true", "1")
    # only the database file is left, which is the user's choice
    assert section.database_requirements() == ["Database tab: enable the database and choose its file"]


def test_session_save_and_load_keeps_database_options(win):
    from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence
    win.p452_override_from_db.set(True)
    win.p452_profile_source.set("grid")
    win.p452_profile_raster.set("dem.tif")
    win.se_loc_geo_lat.set(-12.5)
    cfg = SESPersistence.collect_config(win)
    assert cfg["p452"]["override_from_db"] is True and cfg["p452"]["profile_raster"] == "dem.tif"
    win.p452_override_from_db.set(False)
    win.p452_profile_raster.set("")
    win.se_loc_geo_lat.set(0.0)
    SESPersistence.apply_config(win, cfg)
    assert win.p452_override_from_db.get() in (True, "True")
    assert win.p452_profile_source.get() == "grid" and win.p452_profile_raster.get() == "dem.tif"
    assert float(win.se_loc_geo_lat.get()) == -12.5


def test_use_loaded_terrain_fills_grid_profiles_and_worldcover_heights(win, tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from core.yaml_builder import build_yaml_structure
    section = win.tab_station.chan_section
    win.var_system.set("SINGLE_EARTH_STATION")
    win.se_channel_model.set("P452")
    win.p452_override_from_db.set(True)

    # nothing loaded: says so and changes nothing
    monkeypatch.setattr(win.tab_terrain, "active", None, raising=False)
    win.p452_profile_source.set("mesh")
    assert section.use_loaded_terrain() is False
    assert win.p452_profile_source.get() == "mesh"

    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    kw = dict(driver="GTiff", height=60, width=60, count=1, crs="EPSG:4326", transform=from_origin(-39.0, -3.0, 0.01, 0.01))
    land = np.full((60, 60), 10, dtype=np.uint8)
    land[:, :15] = 80                                         # sea on the west side
    with rasterio.open(tmp_path / "clutter.tif", "w", dtype="uint8", **kw) as ds:
        ds.write(land, 1)
    with rasterio.open(tmp_path / "terrain.tif", "w", dtype="float32", **kw) as ds:
        ds.write(np.full((60, 60), 20.0, dtype=np.float32), 1)
    tset = SimpleNamespace(folder=tmp_path, terrain=tmp_path / "terrain.tif", clutter=tmp_path / "clutter.tif",
                           bbox=(-39.0, -3.6, -38.4, -3.0), ready=True)
    monkeypatch.setattr(win.tab_terrain, "active", tset, raising=False)
    assert section.use_loaded_terrain() is True
    assert win.p452_profile_source.get() == "grid"
    assert win.p452_clutter_heights.get() == "worldcover"
    blk = build_yaml_structure(win)["single_earth_station"]["param_p452"]
    assert blk["profile_raster"].endswith("terrain.tif") and blk["clutter_raster"].endswith("clutter.tif")
    assert blk["clutter_heights"] == "worldcover"
    assert blk["zone_raster"].endswith("zones.tif") and (tmp_path / "zones.tif").is_file()
    with rasterio.open(tmp_path / "zones.tif") as z:
        assert set(np.unique(z.read(1))) >= {2, 3}            # inland and sea cells were derived

    # a station outside the downloaded region is reported
    win.se_loc_geo_lat.set(-3.3)
    win.se_loc_geo_lon.set(-38.7)
    assert section.coverage_problem() == ""
    win.se_loc_geo_lat.set(10.0)
    assert "does not cover" in section.coverage_problem()
    assert any("does not cover" in m for m in section.database_requirements())

    # the downloaded land cover with a CelPlan table is flagged, not silently accepted
    win.p452_clutter_heights.set("celplan")
    assert any("worldcover" in m for m in section.database_requirements())
