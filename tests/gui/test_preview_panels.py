"""Link-budget window and PSD/CDF plots fed by the 3D view."""
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

LINK = {"ue": 7, "bs": 12, "dist_m": 412.0, "freq_mhz": 3500.0, "bandwidth_mhz": 100.0, "tx_power_dbm": 7.0,
        "g_tx_dbi": 18.4, "fspl_db": 95.2, "g_rx_dbi": 5.0, "body_loss_db": 4.0, "rx_power_dbm": -68.8,
        "noise_dbm": -89.0, "snr_db": 20.2}
PLOTS = {"imt": {"freq_mhz": 3500.0, "bandwidth_mhz": 100.0, "psd_dbm_mhz": -13.0},
         "victim": {"freq_mhz": 3550.0, "bandwidth_mhz": 50.0, "name": "SINGLE_SPACE_STATION"},
         "cdf": {"x": [float(v) for v in range(-60, 0, 1)], "p": [i / 59 for i in range(60)], "unit": "dB", "label": "I/N"}}


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_link_panel_shows_every_budget_line_and_clears():
    _app()
    from ui.components.preview_panels import LinkBudgetPanel
    panel = LinkBudgetPanel()
    panel.set_payload(json.dumps(LINK))
    text = panel.body.text()
    assert "UE 7" in panel.title.text() and "BS 12" in panel.title.text()
    for needle in ("412", "-95.2", "+18.4", "-68.8", "+20.2", "Free-space path loss", "SNR"):
        assert needle in text, needle
    panel.set_payload("garbage")
    assert panel.link is None and panel.body.text() == ""


def test_plots_panel_paints_with_and_without_data():
    _app()
    from ui.components.preview_panels import PlotsPanel
    panel = PlotsPanel()
    panel.resize(700, 200)
    empty = panel.grab().toImage()
    panel.set_payload(json.dumps(PLOTS))
    full = panel.grab().toImage()
    assert empty != full                                     # data really changes what is drawn
    panel.set_payload("null")
    assert panel.data is None


def test_workbench_docks_follow_the_bridge(win):
    bridge = win.tab_preview._cesium_embed.bridge
    bridge.link_selected.emit(json.dumps(LINK))
    assert win.dock_link.isVisible() and win.link_panel.link["bs"] == 12
    bridge.plots_changed.emit(json.dumps(PLOTS))
    assert win.plots_panel.data["victim"]["name"] == "SINGLE_SPACE_STATION"
    assert win.dock_plots.windowTitle() == "Plots"
