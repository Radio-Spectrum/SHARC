"""Fumaça da GUI: abre o App sem display e percorre todas as páginas."""
import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GUI = os.path.join(_REPO, "sharc", "gui")
for _p in (_GUI, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture
def gui(_gui_session):
    return _gui_session


def test_stylesheet_builds_for_both_themes(gui):
    gui_main, _, _ = gui
    for theme in ("dark", "light"):
        assert len(gui_main.build_stylesheet(theme)) > 1000


def test_all_pages_open(gui):
    _, app, win = gui
    for key, label, *_ in win.pages_config:
        win._switch_page(key, label)
        app.processEvents()
        assert win.current_key == key


def test_preview_cesium_available(gui):
    from ui.tabs import preview
    assert preview.HAS_CESIUM, "CesiumJS não encontrado em sharc/gui/web/cesium_preview/vendor/cesium"
