"""Colour-scale legend: a detached window fed by the 3D view."""
import json
import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ITEMS = [{"id": "lobe", "title": "Antenna gain", "unit": "dBi", "vmin": 0.0, "vmax": 23.1},
         {"id": "heat", "title": "Aggregate IMT PSD", "unit": "dBm/MHz", "vmin": -68.0, "vmax": -48.0}]


def test_panel_keeps_valid_items_and_ignores_garbage():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.components.legend_panel import LegendPanel
    panel = LegendPanel()
    panel.set_payload(json.dumps(ITEMS + [{"title": "broken"}]))
    assert [i["id"] for i in panel.items] == ["lobe", "heat"]          # the item without a range is dropped
    assert panel.sizeHint().width() >= 2 * 160                         # one column per scale
    panel.set_payload("not json")
    assert panel.items == []


def test_dock_shows_and_hides_with_the_scales_on_screen(win):
    bridge = win.tab_preview._cesium_embed.bridge
    bridge.legend_changed.emit(json.dumps(ITEMS))
    assert win.dock_legend.isVisible() and win.dock_legend.isFloating()
    assert len(win.legend_panel.items) == 2
    bridge.legend_changed.emit("[]")
    assert not win.dock_legend.isVisible()


def test_panel_paints_without_error():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.components.legend_panel import LegendPanel
    panel = LegendPanel()
    panel.set_items(ITEMS)
    panel.resize(panel.sizeHint())
    img = panel.grab().toImage()
    assert img.width() >= 320 and img.height() > 200
