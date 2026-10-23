"""Protection Contour page: configuration, a real (small) campaign at a site far from Brazil, exports and navigation."""
import csv
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402

N = 300


@pytest.fixture()
def rasters(tmp_path):
    """Synthetic terrain around 50.5 N, 6.9 E (Germany): a hill, tree cover, inland zones; sea in the far west."""
    kw = dict(driver="GTiff", height=N, width=N, count=1, crs="EPSG:4326", transform=from_origin(6.3, 51.2, 0.005, 0.005))
    ys, xs = np.mgrid[0:N, 0:N]
    dem = (300.0 + 120.0 * np.exp(-(((xs - 150) / 30.0) ** 2 + ((ys - 150) / 30.0) ** 2))).astype(np.float32)
    zones = np.full((N, N), 2, dtype=np.uint8)
    zones[:, :20] = 3                                                    # a sea strip on the west edge
    out = {}
    for name, dtype, data in (("dem", "float32", dem), ("cover", "uint8", np.full((N, N), 10, dtype=np.uint8)),
                              ("zones", "uint8", zones)):
        out[name] = str(tmp_path / f"{name}.tif")
        with rasterio.open(out[name], "w", dtype=dtype, **kw) as ds:
            ds.write(data, 1)
    return out


def _fill(tab, rasters):
    w = tab.w
    w["name"].setText("Test dish")
    w["lat"].setValue(50.5249)
    w["lon"].setValue(6.8836)
    w["height"].setValue(10.0)
    w["dish"].setValue(100.0)
    w["freq"].setValue(4900.0)
    w["bw"].setValue(100.0)
    w["elev"].setValue(30.0)
    w["temp"].setValue(40.0)
    w["dem"].setText(rasters["dem"])
    w["cover"].setText(rasters["cover"])
    w["zones"].setText(rasters["zones"])
    w["heights"].setCurrentText("worldcover")
    w["spur"].setValue(-10.0)
    w["ray_step"].setValue(60.0)                                         # 6 rays
    w["offs"].setText("0, 90")
    w["step"].setValue(250.0)
    w["dmin"].setValue(500.0)
    w["dmax"].setValue(45.0)
    w["tol"].setValue(5.0)


def test_page_is_registered_as_a_document_tab_and_reachable(win):
    assert hasattr(win, "tab_contour")
    assert "contour" in win._doc_pages
    win._switch_page("contour", "Protection Contour")
    assert win.doc_tabs.currentWidget() is win._doc_pages["contour"]
    assert win.doc_tabs.tabText(win.doc_tabs.indexOf(win._doc_pages["contour"])) == "Protection Contour"


def test_preset_fills_the_site_and_editing_it_switches_to_custom(win):
    tab = win.tab_contour
    tab._apply_preset("ROEN")
    assert tab.w["lat"].value() == pytest.approx(-3.8735) and tab.w["freq"].value() == pytest.approx(4895.0)
    assert tab.w["preset"].currentText() == "ROEN"
    tab.w["lat"].setValue(10.0)
    assert tab.w["preset"].currentText() == "Custom"


def test_run_is_refused_with_a_clear_message_when_data_is_missing(win):
    tab = win.tab_contour
    tab.w["dem"].setText("")
    assert tab.run(1) is False
    assert "elevation raster" in tab.lbl_status.text()
    tab.w["dem"].setText("no_such_file.tif")
    assert tab.run(1) is False
    assert "not found" in tab.lbl_status.text()
    tab.w["dem"].setText("x.tif")
    tab._apply_preset("ROEN")
    tab.w["offs"].setText("0, abc")
    assert tab.run(1) is False and "numbers" in tab.lbl_status.text()
    tab.w["offs"].setText("0, 90, 135")


def test_campaign_runs_shows_results_and_exports(win, rasters, tmp_path):
    tab = win.tab_contour
    _fill(tab, rasters)
    assert tab.run(1) is True
    assert tab.btn_cancel.isEnabled() and not tab.btn_run.isEnabled()          # busy while it runs
    assert tab.wait()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    assert len(tab.rows) == 6 * 2, tab.lbl_status.text()
    assert tab.progress.value() == tab.progress.maximum() == 6
    assert tab.btn_run.isEnabled() and tab.btn_csv.isEnabled() and not tab.btn_cancel.isEnabled()
    assert tab.table.rowCount() == 2
    assert tab.table.item(0, 0).text() == "0" and tab.table.item(1, 0).text() == "90"
    assert len(tab.canvas.figure.axes[0].lines) >= 3                           # contours, ray ends, the station

    rows = [r for r in tab.rows if r["off_axis_deg"] == 0.0]
    assert all(np.isfinite(r["contour_m"]) and 500.0 <= r["contour_m"] <= 45000.0 for r in rows)
    assert {r["ray_end_reason"] for r in rows} <= {"sea", "terrain_edge", "limit"}
    west = [r for r in rows if abs(r["az_enu_deg"] - 180.0) < 1e-6][0]
    assert west["ray_end_reason"] == "sea"                                     # the sea strip ends the westward ray
    # the contour of the beam pointed at the station reaches further than with the sector pointed 90 degrees away
    off0 = np.array([r["contour_m"] for r in tab.rows if r["off_axis_deg"] == 0.0])
    off90 = np.array([r["contour_m"] for r in tab.rows if r["off_axis_deg"] == 90.0])
    assert off0.mean() >= off90.mean()

    path = tab.export_csv(str(tmp_path / "out" / "contour.csv"))
    with open(path, encoding="utf-8") as fh:
        table = list(csv.DictReader(fh))
    assert len(table) == 12 and set(table[0]) >= {"az_enu_deg", "off_axis_deg", "contour_m", "marker", "lat", "lon"}
    files = tab.export_figure(str(tmp_path / "figs"))
    assert [os.path.basename(f) for f in files] == ["sharc_contour.png", "sharc_contour.pdf", "sharc_contour.svg"]
    assert all(os.path.getsize(f) > 1500 for f in files)


def test_cancel_stops_early_and_keeps_the_page_usable(win, rasters):
    tab = win.tab_contour
    _fill(tab, rasters)
    tab.w["ray_step"].setValue(5.0)                                            # 72 rays: enough time to cancel
    assert tab.run(1)
    tab.cancel()
    assert tab.wait()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    assert len(tab.rows) < 72 * 2
    assert tab.btn_run.isEnabled() and not tab.btn_cancel.isEnabled()


def test_worker_processes_give_the_same_rows_as_serial(rasters):
    from sharc.contour import campaign
    from sharc.contour.budget import ReferenceBs
    from sharc.contour.calculator import Sweep
    from sharc.contour.region import Region
    from sharc.contour.site import RasSite
    cfg = campaign.ContourConfig(
        site=RasSite("T", 50.5249, 6.8836, 10.0, 100.0, 0.6, 4900.0, 100.0, 30.0, 40.0),
        region=Region(rasters["dem"], rasters["cover"], rasters["zones"], "worldcover", 250.0),
        bs=ReferenceBs(spurious_dbm_mhz=-10.0), sweep=Sweep(250.0, 500.0, 45000.0, 5.0), ray_step_deg=90.0,
        off_axis_deg=(0.0,))
    serial = campaign.run_campaign(cfg, 1)
    parallel = campaign.run_campaign(cfg, 2)
    assert [round(r["contour_m"], 6) for r in serial] == [round(r["contour_m"], 6) for r in parallel]
    assert len(serial) == 4
    assert set(campaign.summary(serial)) == {0.0}


# ------------------------------------------------------------------ 3D scene
def _rows(n=8):
    rows = []
    for off, base in ((0.0, 5000.0), (90.0, 2000.0)):
        for k in range(n):
            az = 360.0 / n * k
            d = base * (1 + 0.1 * k)
            from sharc.contour import geometry
            lat, lon = geometry.points_on_ray(50.5, 6.9, az, d)
            rows.append({"az_enu_deg": az, "az_north_deg": float(geometry.enu_to_north(az)), "off_axis_deg": off,
                         "contour_m": d, "marker": "not_met_at_end" if (off == 0.0 and k == 2) else "ok",
                         "ray_end_m": 20000.0 + 1000.0 * k, "ray_end_reason": "limit", "evaluations": 5,
                         "lat": float(lat[0]), "lon": float(lon[0])})
    rows.append({"az_enu_deg": 0.0, "az_north_deg": 90.0, "off_axis_deg": 0.0, "contour_m": float("nan"),
                 "marker": "no_points", "ray_end_m": 0.0, "ray_end_reason": "sea", "evaluations": 0,
                 "lat": float("nan"), "lon": float("nan")})
    return rows


def test_scene_payload_has_one_closed_curve_per_off_axis_and_the_violated_ends():
    from core import contour_scene
    data = contour_scene.payload(_rows(), "Test dish", 50.5, 6.9)
    assert [c["off_axis_deg"] for c in data["curves"]] == [0.0, 90.0]
    for c in data["curves"]:
        assert c["points"][0] == c["points"][-1] and len(c["points"]) == 9            # 8 rays, closed
    assert len(data["violated"]) == 1 and data["violated"][0]["off_axis_deg"] == 0.0
    w, s, e, n = data["bounds"]
    assert w < 6.9 < e and s < 50.5 < n
    assert data["ray_ends"][0] == data["ray_ends"][-1] and len(data["ray_ends"]) >= 8
    import json
    json.dumps(data)                                                                      # JSON-safe: no NaN leaks through
    assert "NaN" not in json.dumps(data)


def test_show_in_3d_sends_the_contour_to_the_preview_and_switches_page(win, monkeypatch):
    import json
    import re
    tab = win.tab_contour
    tab.rows = []
    assert tab.show_in_3d() is False and "Run the contour first" in tab.lbl_status.text()

    tab.rows = _rows()
    tab.w["name"].setText("Test dish")
    tab.w["lat"].setValue(50.5)
    tab.w["lon"].setValue(6.9)
    sent = []
    page = SimpleNamespace(runJavaScript=sent.append)
    monkeypatch.setattr(win.tab_preview, "_cesium_embed",
                        SimpleNamespace(view=SimpleNamespace(page=lambda: page), ready=SimpleNamespace(connect=lambda f: None)))
    tab._ready_connected = False
    assert tab.show_in_3d() is True
    match = re.match(r"setContour\((.*), true\);", sent[-1])
    data = json.loads(match.group(1))
    assert data["station"]["name"] == "Test dish" and len(data["curves"]) == 2
    assert win.current_key == "preview"                                                   # went to the 3D scene
    tab.clear_3d()
    assert sent[-1] == "clearContour();"
    tab.rows = []


def test_the_javascript_declares_what_the_python_sends():
    js = open(os.path.join(_REPO, "sharc", "gui", "web", "cesium_preview", "app.js"), encoding="utf-8").read()
    for name in ("function setContour(", "function clearContour(", "CustomDataSource(\"Protection contour\")"):
        assert name in js
    assert "ds.entities.removeAll()" in js          # redrawing replaces the old contour, never stacks them


def test_progress_shows_an_estimate_only_when_there_is_something_to_extrapolate(win):
    import time
    tab = win.tab_contour
    tab._started = time.time() - 30.0
    tab._on_progress(1, 20)
    assert "left" not in tab.lbl_status.text()
    tab._on_progress(5, 20)
    text = tab.lbl_status.text()
    assert "5 of 20 rays" in text and "left" in text and "1 min" in text          # 30 s for 5 rays: about 90 s left
    tab._on_progress(20, 20)
    assert "left" not in tab.lbl_status.text() or "20 of 20" not in tab.lbl_status.text()
