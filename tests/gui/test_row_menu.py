"""Right-click menu on parameter rows: reset to default, copy value, copy name."""
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

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton  # noqa: E402

from ui.components import properties as props  # noqa: E402


def _act(menu, name):
    return next(a for a in menu.actions() if a.objectName() == name)


def _menu(editor, default, key="some_param"):
    lbl = QLabel("Some param")
    return props.build_row_menu(lbl, lbl, editor, key, default)


@pytest.mark.parametrize("make,default,changed", [
    (lambda: QLineEdit("5"), "5", "9"),
    (QCheckBox, False, True),
])
def test_reset_restores_default_for_line_edit_and_checkbox(win, make, default, changed):
    editor = make()          # widgets must be built after the QApplication exists, not at collection time
    props._write_value(editor, changed)
    menu = _menu(editor, default)
    assert _act(menu, "act_reset").isEnabled()
    _act(menu, "act_reset").trigger()
    assert props._read_value(editor) == default
    assert not _act(_menu(editor, default), "act_reset").isEnabled()     # already at default


def test_reset_restores_combo(win):
    cb = QComboBox()
    cb.addItems(["A", "B", "C"])
    default = cb.currentText()
    cb.setCurrentIndex(2)
    _act(_menu(cb, default), "act_reset").trigger()
    assert cb.currentText() == "A"


def test_copy_value_and_name_go_to_clipboard(win):
    ed = QLineEdit("123.5")
    menu = _menu(ed, "0", key="Some Key")
    _act(menu, "act_copy_value").trigger()
    assert QGuiApplication.clipboard().text() == "123.5"
    _act(menu, "act_copy_name").trigger()
    assert QGuiApplication.clipboard().text() == "Some Key"


def test_rows_without_a_single_value_disable_reset_and_copy(win):
    menu = _menu(QPushButton("go"), None)
    assert not _act(menu, "act_reset").isEnabled()
    assert not _act(menu, "act_copy_value").isEnabled()


def test_real_gui_row_resets_its_bound_variable(win, monkeypatch):
    """Right-click on the Snapshots row in General, change the value, Reset: variable follows the editor."""
    ed = win.tab_general.e_snaps
    original = ed.text()
    captured = []
    monkeypatch.setattr(props, "_exec_menu", lambda menu, pos: captured.append(menu))
    props._write_value(ed, "7777")
    assert str(win.var_snaps.get()) == "7777"
    cell = ed.parent()
    cell.customContextMenuRequested.emit(QPoint(1, 1))
    assert captured, "row has no context menu"
    _act(captured[-1], "act_reset").trigger()
    assert ed.text() == original
    assert str(win.var_snaps.get()) == original
