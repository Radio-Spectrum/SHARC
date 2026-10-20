"""Capture the 3D preview with the antenna gain lobes switched on.

    python sharc/gui/tools/screenshot_lobes.py <out.png> [altitude_m] [pitch_deg] [js]

`js` replaces the default "setLobes(true);", e.g. "setLobes(true); setHeat('psd');".

Set SHARC_SHOT_SCREEN=1 to grab the whole screen (shows floating windows such as the legend).
Uses the default scenario (Brasilia). Run on the real display platform, not QT_QPA_PLATFORM=offscreen.
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
    alt = float(sys.argv[2]) if len(sys.argv) > 2 else 1800.0
    pitch = float(sys.argv[3]) if len(sys.argv) > 3 else -38.0
    js = sys.argv[4] if len(sys.argv) > 4 else "setLobes(true);"

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    import main as gui_main
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(gui_main.build_stylesheet("graphite"))
    win = gui_main.App()
    win.resize(1500, 920)
    win.show()
    win._switch_page("preview", "Topology Preview")
    view = win.tab_preview._cesium_embed.view
    page = view.page()
    from PySide6.QtWebEngineCore import QWebEngineScript
    spy = QWebEngineScript()                           # collect page errors from the very start
    spy.setName("sharc-error-spy")
    spy.setInjectionPoint(QWebEngineScript.DocumentCreation)
    spy.setWorldId(QWebEngineScript.MainWorld)
    spy.setSourceCode("window.__errs = []; window.addEventListener('error', e => window.__errs.push(String(e.message)));"
                      "const _ce = console.error; console.error = function() { window.__errs.push([].join.call(arguments, ' ')); _ce.apply(console, arguments); };")
    page.scripts().insert(spy)
    view.reload()

    def toggle():
        page.runJavaScript(js)

    def fly():
        page.runJavaScript(
            "viewer.camera.setView({destination: Cesium.Cartesian3.fromDegrees(-47.88, -15.80, %f),"
            " orientation: {heading: 0.0, pitch: Cesium.Math.toRadians(%f), roll: 0.0}});" % (alt, pitch))

    def errors():
        page.runJavaScript("JSON.stringify(window.__errs || [])", lambda r: print("PAGE ERRORS:", r))

    def shot():
        img = app.primaryScreen().grabWindow(0) if os.environ.get("SHARC_SHOT_SCREEN") else win.grab()
        ok = img.save(out)
        print("saved", out, ok)
        app.quit()

    wait = int(float(os.environ.get("SHARC_SHOT_WAIT", "0")) * 1000)      # extra seconds for slow scenes
    QTimer.singleShot(9000 + wait, toggle)
    QTimer.singleShot(10000 + wait, fly)
    QTimer.singleShot(13500 + wait, errors)
    QTimer.singleShot(16000 + wait, shot)
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
