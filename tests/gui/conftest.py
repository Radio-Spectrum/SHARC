"""Uma única janela do GUI para toda a sessão de testes.

Criar vários `App()` no mesmo processo (cada um com seu QtWebEngine/Cesium) é lento e
pode derrubar o Qt; por isso as fixtures `win` dos módulos usam esta instância.
"""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _isolate_qsettings():
    """QSettings("SHARC", "GUI") of the tests lives in a temporary INI folder: a test must never change the user's
    saved theme, Cesium token or heat-map style (the Windows registry is the default store)."""
    import tempfile
    from PySide6.QtCore import QSettings
    folder = tempfile.mkdtemp(prefix="sharc_test_settings_")
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, folder)
    QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, folder)


@pytest.fixture(scope="session")
def _gui_session():
    pytest.importorskip("PySide6")
    _isolate_qsettings()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import main as gui_main
    app.setStyleSheet(gui_main.build_stylesheet("graphite"))
    window = gui_main.App()
    window.resize(1400, 900)
    window.show()
    yield gui_main, app, window
    window.close()


@pytest.fixture(scope="session")
def win(_gui_session):
    return _gui_session[2]


def _all_vars(window):
    """Todas as SharcVar do app (estado global + estados por aba)."""
    from core.state import SharcVar
    found = {}
    for name, val in list(vars(window.state_model).items()) if hasattr(window, "state_model") else []:
        if isinstance(val, SharcVar):
            found[("app", name)] = val
    for tab in ("tab_imt", "tab_victim", "tab_database", "tab_terrain"):
        st = getattr(getattr(window, tab, None), "state", None)
        for name, val in (getattr(st, "vars", {}) or {}).items():
            found[(tab, name)] = val
    return found


@pytest.fixture(autouse=True)
def _restore_gui_state(request):
    """Cada teste começa e termina com os valores que encontrou (a janela é compartilhada)."""
    if "win" not in request.fixturenames and "gui" not in request.fixturenames:
        yield
        return
    window = request.getfixturevalue("win")
    snap = {k: v.get() for k, v in _all_vars(window).items()}
    yield
    for key, var in _all_vars(window).items():
        if key in snap and var.get() != snap[key]:
            var.set(snap[key])


_EXIT = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _EXIT["code"] = int(exitstatus)


def pytest_unconfigure(config):
    """QtWebEngine can crash while the interpreter tears Qt down (after all tests ran and
    were reported). Leave without that teardown so the exit code reflects the tests."""
    try:
        from PySide6.QtWidgets import QApplication
        created = QApplication.instance() is not None
    except Exception:  # noqa: BLE001
        created = False
    if created:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_EXIT["code"])
