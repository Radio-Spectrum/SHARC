"""Captura todas as páginas da GUI em PNG (baseline visual para o redesign).

    python sharc/gui/tools/screenshot_tour.py <pasta_saida> [largura altura]

Gera <pasta_saida>/tour_<pagina>.png. A página "preview" espera mais tempo
para o Cesium carregar.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SHARC_GUI_NO_RESTORE", "1")
GUI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(GUI_DIR))
for p in (GUI_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    out = os.path.abspath(sys.argv[1])
    os.makedirs(out, exist_ok=True)
    w, h = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) >= 4 else (1500, 920)

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    import main as gui_main

    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    theme = os.environ.get("SHARC_THEME", "graphite")
    app.setStyleSheet(gui_main.build_stylesheet(theme))
    win = gui_main.App()
    win._current_theme = theme
    win.resize(w, h)
    win.show()

    pages = [(c[0], c[1]) for c in win.pages_config]
    state = {"i": 0}

    def step():
        i = state["i"]
        if i > 0:
            key = pages[i - 1][0]
            win.grab().save(os.path.join(out, f"tour_{key}.png"))
            print("saved", key)
        if i >= len(pages):
            app.quit()
            return
        key, label = pages[i]
        win._switch_page(key, label)
        state["i"] += 1
        QTimer.singleShot(6000 if key == "preview" else 900, step)

    QTimer.singleShot(2500, step)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
