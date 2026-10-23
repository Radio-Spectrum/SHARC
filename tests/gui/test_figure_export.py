"""Publication figures (heat maps and PSD / CDF plots) exported from the preview scene."""
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import figure_export  # noqa: E402


def _scene():
    n = 40
    xs = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(xs, xs)
    r = np.hypot(X, Y)
    inr = 8.0 - 30.0 * r
    maps = {q: {"values": (inr + off).round(1).ravel().tolist(), "vmin": float(inr.min() + off),
                "vmax": float(inr.max() + off), "unit": u, "title": t}
            for q, off, u, t in (("psd", -60, "dBm/MHz", "Aggregate IMT PSD"),
                                 ("power", -90, "dBm", "Strongest BS received power"),
                                 ("inr", 0, "dB", "Aggregate I/N"))}
    heat = {"n": n, "west": -48.0, "east": -47.9, "south": -15.1, "north": -15.0,
            "freq_mhz": 3500.0, "bandwidth_mhz": 100.0, "maps": maps}
    q = np.linspace(0, 1, 60)
    plots = {"imt": {"freq_mhz": 3500.0, "bandwidth_mhz": 100.0, "psd_dbm_mhz": -20.0},
             "victim": {"freq_mhz": 3650.0, "bandwidth_mhz": 36.0, "name": "SINGLE_SPACE_STATION"},
             "cdf": {"x": np.quantile(inr, q).round(1).tolist(), "p": q.round(3).tolist(), "unit": "dB"}}
    return {"imt": {"heat": heat, "plots": plots}}        # composite scenes keep both under `imt`


def test_scale_bar_length_is_round():
    assert figure_export._nice_length_km(12.0) == 2
    assert figure_export._nice_length_km(40.0) == 10 or figure_export._nice_length_km(40.0) == 5


def test_export_writes_raster_and_vector_for_every_map_and_the_plots(tmp_path):
    paths = figure_export.export_figures(_scene(), str(tmp_path), dpi=100)
    names = {os.path.basename(p) for p in paths}
    for stem in ("heatmap_psd", "heatmap_power", "heatmap_inr", "plots"):
        for ext in ("png", "pdf", "svg"):
            assert f"sharc_{stem}.{ext}" in names
    assert all(os.path.getsize(p) > 1000 for p in paths)


def test_file_menu_exports_the_real_preview_scene(win, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    st = win.tab_imt.state
    for key, val in {"topo_type": "MACROCELL", "macro_intersite": "800", "macro_clusters": "1"}.items():
        st.get(key).set(val)
    scene = win.tab_preview._cesium_scene_provider("MACROCELL")
    monkeypatch.setenv("SHARC_SCREENSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(win.tab_preview, "_cesium_embed", SimpleNamespace(bridge=SimpleNamespace(last_scene=scene)))
    win._export_publication_figures()
    out = tmp_path / "figures"
    assert (out / "sharc_heatmap_inr.png").stat().st_size > 5000
    assert (out / "sharc_plots.pdf").exists()
    assert json.loads(scene)


def test_scene_without_heat_or_plots_exports_nothing(tmp_path):
    assert figure_export.export_figures({}, str(tmp_path)) == []
