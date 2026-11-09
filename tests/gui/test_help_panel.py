"""Help button, context panel, handbook and parameter tooltips."""
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


def test_handbook_topics_are_unique_and_non_empty():
    from ui.shell.handbook import TOPICS
    titles = [t for t, _ in TOPICS]
    assert len(titles) == len(set(titles)) >= 10
    assert all(len(h) > 80 for _, h in TOPICS)


def test_help_texts_use_real_page_keys(win):
    from ui.shell import help_content as hc
    keys = set(win._page_sections) | set(win._doc_pages) | set(win._page_widgets)
    assert set(hc.PAGES) <= keys | {"preview", "results", "contour", "ssh", "runner"}
    assert set(hc.PARAMS) <= set(hc.PAGES)


def test_param_descriptions_match_real_rows(win):
    """Every described parameter must correspond to a row that exists, so the texts cannot silently rot."""
    from PySide6.QtWidgets import QLabel
    from ui.shell import help_content as hc
    present = {}
    for key, boxes in win._page_sections.items():
        for box in boxes:
            for lbl in box.findChildren(QLabel):
                if lbl.objectName() == "PropLabel":
                    present.setdefault(key, set()).add(lbl.text().strip().lower())
    missing = [(k, name) for k, d in hc.PARAMS.items() for name in d if name not in present.get(k, set())]
    assert not missing, missing


def test_tooltips_are_applied_to_described_rows(win):
    from PySide6.QtWidgets import QLabel
    n = 0
    for boxes in win._page_sections.values():
        for box in boxes:
            for lbl in box.findChildren(QLabel):
                if lbl.objectName() == "PropLabel" and lbl.text().strip().lower() == "num snapshots":
                    assert "Monte Carlo" in lbl.toolTip()
                    n += 1
    assert n == 1


def test_help_button_is_round_and_opens_the_panel(win):
    assert win.btn_help.width() == win.btn_help.height() == 26
    assert "border-radius: 13px" in win.btn_help.styleSheet()
    assert not win.btn_help.icon().isNull()
    win._ensure_help_dock().hide()
    win._toggle_help()
    assert win._dock_on_top(win.dock_help)
    win._switch_page("general", "General Settings")
    win._raise_dock(win.dock_help)
    html = win.dock_help.context.toHtml()
    assert "Num Snapshots" in html and "Monte Carlo" in html
    win._toggle_help()
    assert not win.dock_help.isVisible()


def test_handbook_comes_to_front_after_properties_was_raised(win):
    """Regression: Help is tabbed behind Properties; raise_() alone does not switch the tab, and isVisible() is
    True for a tab that is behind, so the '?' button used to hide the panel instead of showing it."""
    win._ensure_help_dock().hide()
    win._toggle_help()
    assert win._dock_on_top(win.dock_help)
    win._switch_page("imt", "IMT System")
    win._switch_page("general", "General Settings")
    win.dock_properties.raise_()
    assert not win._dock_on_top(win.dock_help)
    win._open_handbook("Parameter sweep")
    assert win._dock_on_top(win.dock_help)
    assert win.dock_help.tabs.currentIndex() == 1
    assert "Parameter sweep" in win.dock_help.page.toPlainText()
    win.dock_properties.raise_()
    win._toggle_help()
    assert win._dock_on_top(win.dock_help), "the '?' button must bring a hidden-behind Help forward"
    win._toggle_help()
    assert not win.dock_help.isVisible()


def test_handbook_search_filters_topics(win):
    dock = win._ensure_help_dock()
    dock.search.setText("sweep")
    titles = [dock.topics.item(i).text() for i in range(dock.topics.count())]
    assert "Parameter sweep" in titles and len(titles) < 8
    dock.search.setText("zzzz-nothing")
    assert dock.topics.count() == 0
    dock.search.clear()
    assert dock.topics.count() >= 10


def test_feko_layout_toggles_and_reports_model_status(win):
    win._set_layout_mode("feko", persist=False)
    assert win.ribbon_toolbar.isVisible() and not win.main_toolbar.isVisible()
    assert win.dock_scenario.windowTitle() == "Items"
    assert win.ribbon.count() == 5
    assert all(not b.icon().isNull() for g in win.ribbon.groups for b, _ in g.buttons)
    ok = win._refresh_model_status()
    state = win.dock_model_status.state.text()
    assert state == ("Model is valid" if ok else "Model has errors")
    win._set_layout_mode("classic", persist=False)
    assert win.main_toolbar.isVisible() and not win.ribbon_toolbar.isVisible()
    assert not win.dock_model_status.isVisible()
    assert win.dock_scenario.windowTitle() == "Scenario"
