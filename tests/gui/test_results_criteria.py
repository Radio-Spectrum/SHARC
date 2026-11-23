"""Regression: Remove/Toggle on the protection-criteria table raised IndexError.

QTableWidget.selectedItems() returns one item per cell (4 columns), so the row list had each row 4 times:
Remove popped the same row 4 times, emptied the list, aborted before refreshing, and left a stale table.
"""
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


def _tab(win):
    tab = win.tab_results
    tab.cb_subplot_sel.setCurrentText("1")
    cfg = tab._axes_cfg[0]
    cfg["criteria"] = [{"val": float(v), "type": "Vertical (X)", "label": f"c{v}", "color": "red", "enabled": True}
                       for v in (1, 2, 3)]
    tab._refresh_criteria_list(cfg["criteria"])
    return tab, cfg


def test_remove_deletes_only_the_selected_row(win):
    tab, cfg = _tab(win)
    tab.tv_crit.selectRow(1)                                   # 4 cells selected
    tab._remove_criteria()
    assert [c["label"] for c in cfg["criteria"]] == ["c1", "c3"]
    assert tab.tv_crit.rowCount() == 2


def test_remove_several_rows_and_all_rows(win):
    tab, cfg = _tab(win)
    tab.tv_crit.selectAll()
    tab._remove_criteria()
    assert cfg["criteria"] == [] and tab.tv_crit.rowCount() == 0


def test_toggle_flips_once_per_row(win):
    tab, cfg = _tab(win)
    tab.tv_crit.selectRow(0)
    tab._toggle_criteria()
    assert [c["enabled"] for c in cfg["criteria"]] == [False, True, True]
    assert tab.tv_crit.item(0, 0).text() == "Off"


def test_stale_table_resyncs_instead_of_raising(win):
    tab, cfg = _tab(win)
    tab.tv_crit.selectAll()
    cfg["criteria"].clear()                                    # table still shows 3 rows: the state in the bug report
    tab._remove_criteria()
    tab.tv_crit.selectAll()
    tab._toggle_criteria()
    assert tab.tv_crit.rowCount() == 0
