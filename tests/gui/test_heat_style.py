"""User-chosen heat-map style: settings, the 3D view contract, the figure export and the View panel controls."""
import json
import os
import re
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import figure_export, heat_style  # noqa: E402
from core.heat_style import HeatStyle  # noqa: E402

APP_JS = os.path.join(_REPO, "sharc", "gui", "web", "cesium_preview", "app.js")


class FakeSettings:
    """The QSettings of the GUI without touching the user's registry."""
    store = {}

    def __init__(self, *_):
        pass

    def setValue(self, k, v):
        FakeSettings.store[k] = v

    def value(self, k, default=None):
        return FakeSettings.store.get(k, default)


def _heat(n=30):
    xs = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(xs, xs)
    z = -60 - 40 * np.hypot(X, Y)
    return {"n": n, "west": -48.0, "east": -47.9, "south": -15.1, "north": -15.0, "freq_mhz": 3500.0,
            "bandwidth_mhz": 100.0, "bs_km": [[0, 0]],
            "maps": {"psd": {"values": z.round(1).ravel().tolist(), "vmin": float(z.min()), "vmax": float(z.max()),
                             "unit": "dBm/MHz", "title": "Aggregate IMT PSD"},
                     "inr": {"values": (z + 100).round(1).ravel().tolist(), "vmin": float((z + 100).min()),
                             "vmax": float((z + 100).max()), "unit": "dB", "title": "Aggregate I/N"}}}


def _legend_texts(fig):
    legend = fig.axes[0].get_legend()
    return [t.get_text() for t in legend.get_texts()] if legend else []


def test_palette_names_match_the_colours_defined_in_the_3d_view():
    import matplotlib as mpl
    js = open(APP_JS, encoding="utf-8").read()
    block = js[js.index("const HEAT_STOPS = {"):js.index("const HEAT_RGB")]
    in_js = set(re.findall(r"^\s{2}(\w+): \[", block, flags=re.M))
    assert in_js == set(heat_style.PALETTES) - {"auto"}
    assert set(heat_style.PALETTE_LABELS) == set(heat_style.PALETTES)
    for cmap in heat_style.PALETTES.values():
        assert not cmap or cmap in mpl.colormaps


def test_defaults_keep_the_previous_look_and_send_no_manual_range():
    d = json.loads(HeatStyle().to_js())
    assert d["palette"] == "auto" and d["vmin"] is None and d["vmax"] is None
    assert d["bands"] == 0 and d["isolines"] is True and d["threshold"] == -6.0


def test_sanitize_repairs_bad_values():
    s = HeatStyle(palette="nope", opacity=7, bands=99, vmin=10, vmax=5, reverse="false", threshold_db="x").sanitized()
    assert s.palette == "auto" and s.opacity == 1.0 and s.bands == heat_style.MAX_BANDS
    assert s.vmax > s.vmin and s.reverse is False and s.threshold_db == -6.0
    assert HeatStyle(bands=1).sanitized().bands == 0                     # one band is just "smooth"


def test_manual_range_and_threshold_off_are_sent_as_numbers_or_null():
    d = json.loads(HeatStyle(auto_range=False, vmin=-90, vmax=-30, threshold_on=False).to_js())
    assert (d["vmin"], d["vmax"], d["threshold"]) == (-90.0, -30.0, None)


def test_settings_round_trip():
    FakeSettings.store.clear()
    HeatStyle(palette="turbo", reverse=True, auto_range=False, vmin=-80, vmax=-20, bands=8, isolines=False,
              threshold_on=False, threshold_db=-3).save(FakeSettings())
    s = HeatStyle.load(FakeSettings())
    assert (s.palette, s.reverse, s.auto_range, s.vmin, s.vmax, s.bands, s.isolines, s.threshold_on, s.threshold_db) == \
        ("turbo", True, False, -80.0, -20.0, 8, False, False, -3.0)
    FakeSettings.store.clear()
    assert HeatStyle.load(FakeSettings()) == HeatStyle()                 # nothing saved: defaults


def test_mpl_cmap_auto_follows_the_quantity_and_reverse_adds_suffix():
    assert HeatStyle().mpl_cmap("psd") == "viridis" and HeatStyle().mpl_cmap("inr") == "magma"
    assert HeatStyle(palette="plasma", reverse=True).mpl_cmap("inr") == "plasma_r"


def test_figure_uses_palette_range_bands_and_threshold_of_the_style():
    style = HeatStyle(palette="plasma", reverse=True, auto_range=False, vmin=-100, vmax=-40, bands=5)
    im = figure_export.heatmap_figure(_heat(), "psd", style=style).axes[0].images[0]
    assert im.cmap.name == "plasma_r" and im.cmap.N == 5
    assert (im.norm.boundaries[0], im.norm.boundaries[-1]) == (-100.0, -40.0)

    assert "I/N = -1 dB" in _legend_texts(figure_export.heatmap_figure(_heat(), "inr", style=HeatStyle(threshold_db=-1.0)))
    off = figure_export.heatmap_figure(_heat(), "inr", style=HeatStyle(threshold_on=False))
    assert not any("I/N" in t for t in _legend_texts(off))


def test_exported_files_follow_the_style(tmp_path):
    scene = {"imt": {"heat": _heat()}}
    paths = figure_export.export_figures(scene, str(tmp_path), dpi=80, formats=("png",),
                                         style=HeatStyle(palette="gray", bands=4))
    assert len(paths) == 2 and all(os.path.getsize(p) > 1000 for p in paths)


def test_view_panel_controls_save_the_style_and_push_it_to_the_3d_view(win, monkeypatch):
    from types import SimpleNamespace

    from PySide6 import QtCore
    FakeSettings.store.clear()
    monkeypatch.setattr(QtCore, "QSettings", FakeSettings)
    calls = []
    page = SimpleNamespace(runJavaScript=calls.append)
    monkeypatch.setattr(win.tab_preview, "_cesium_embed", SimpleNamespace(view=SimpleNamespace(page=lambda: page)))
    w = win.tab_preview.heat_widgets

    def last():
        return json.loads(re.match(r"setHeatStyle\((.*)\);", calls[-1]).group(1))

    w["palette"].setCurrentIndex(w["palette"].findData("cividis"))
    w["bands"].setValue(6)
    w["fixed"].setChecked(True)
    w["vmin"].setValue(-90.0)
    w["vmax"].setValue(-30.0)
    sent = last()
    assert sent["palette"] == "cividis" and sent["bands"] == 6 and (sent["vmin"], sent["vmax"]) == (-90.0, -30.0)
    assert HeatStyle.load(FakeSettings()).palette == "cividis"          # kept for the next session
    assert win.tab_preview.heat_style.bands == 6

    w["fixed"].setChecked(False)
    assert not w["vmin"].isEnabled() and last()["vmin"] is None

    w["reset"].click()
    assert win.tab_preview.heat_style == HeatStyle().sanitized()
    assert w["palette"].currentData() == "auto" and w["bands"].value() == 0
