"""Preferences window and the richer Settings menu."""
import pytest


def test_settings_menu_has_real_entries(win):
    labels = []
    for a in win.menuBar().actions():
        if a.text() == "Settings":
            labels = [x.text() for x in a.menu().actions()]
    for expected in ("Preferences...", "Theme", "Font size", "Resolution",
                     "Keep running in the system tray when closing", "Reset window layout",
                     "Open map cache folder"):
        assert expected in labels, expected


def test_preferences_dialog_pages_and_binding(win):
    from ui.shell.preferences import PreferencesDialog
    dlg = PreferencesDialog(win)
    titles = [dlg.nav.item(i).text() for i in range(dlg.nav.count())]
    assert titles == ["Appearance", "Map & Terrain", "Simulation", "Notifications & Tray", "Data & Cache", "Advanced"]
    # the map page edits the same variables as the Terrain tab
    var = win.tab_terrain.state.get("terr_quality")
    var.set("Ultra")
    from PySide6.QtWidgets import QComboBox
    combos = [c for c in dlg.stack.widget(1).findChildren(QComboBox) if c.currentText() == "Ultra"]
    assert combos, "map quality combo did not follow the variable"
    var.set("High")


def test_detail_options_reach_the_scene(win):
    st = win.tab_terrain.state
    st.get("terr_quality").set("Ultra")
    st.get("terr_relief_res").set("High (129 x 129)")
    st.get("terr_bld_limit").set("1000")
    st.get("terr_bld_distance").set("Far (6 km)")
    info = win.tab_terrain.overlay_info()
    assert info["sse"] == 1.0 and info["relief_samples"] == 129
    assert info["buildings_max"] == 1000 and info["buildings_distance_m"] == 6000
    st.get("terr_quality").set("Low")
    assert win.tab_terrain.overlay_info()["sse"] == 4.0
