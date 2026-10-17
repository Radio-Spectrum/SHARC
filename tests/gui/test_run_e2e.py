"""Ponta a ponta: o botão Run gera a configuração em segundo plano e a simulação termina."""
import os
import sys
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GUI = os.path.join(_REPO, "sharc", "gui")
for _p in (_GUI, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.mark.slow
def test_run_button_completes_simulation(tmp_path, monkeypatch, win):
    monkeypatch.setenv("SHARC_GUI_RUNS_DIR", str(tmp_path))
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])

    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: None))

    win.tab_general.e_snaps.setText("2")
    assert win.run_simulation() is not False

    deadline = time.time() + 120
    status = ""
    while time.time() < deadline:
        app.processEvents()
        tree = win.tab_runner.tree
        rows = [tree.topLevelItem(i).text(1) for i in range(tree.topLevelItemCount())]
        if rows and all(r.startswith(("Completed", "Error")) for r in rows):
            status = rows[0]
            break
        time.sleep(0.2)
    runs = list(tmp_path.iterdir())
    assert runs, "nenhuma pasta de execução criada"
    assert any(p.suffix == ".yaml" for p in runs[0].iterdir()), "YAML não gerado em segundo plano"
    tail = win.messages_view.toPlainText()[-1800:]
    assert status == "Completed", f"simulação terminou com estado {status!r}: {tail}"
