"""Launcher for the standalone CesiumJS Preview spike.

Run from anywhere with:

    python sharc/gui/tools/run_cesium_spike.py

Opens a plain QMainWindow containing only the CesiumJS spike widget — it
does not touch ``sharc/gui/main.py`` or the real ``App``/tab list, so it
cannot destabilize the production GUI. See
``sharc/gui/CESIUMJS_MIGRATION_PLAN.md`` (Fase 2) for what this proves and
what it deliberately does not (no real SceneGraph data yet).

Requires the CesiumJS static build to be vendored locally first (not
committed to git, ~20-80MB):

    cd <scratch dir>
    npm init -y && npm install cesium
    # then copy node_modules/cesium/Build/Cesium/ into:
    #   sharc/gui/web/cesium_preview/vendor/cesium/
"""

from __future__ import annotations

import os
import sys

GUI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GUI_DIR not in sys.path:
    sys.path.insert(0, GUI_DIR)


def main() -> int:
    vendor_dir = os.path.join(GUI_DIR, "web", "cesium_preview", "vendor", "cesium")
    if not os.path.isdir(vendor_dir):
        print(
            "CesiumJS static build not found at:\n  "
            f"{vendor_dir}\n"
            "Fetch it first (see this file's module docstring)."
        )
        return 1

    from PySide6.QtWidgets import QApplication, QMainWindow

    from web.cesium_preview.spike_widget import CesiumSpikeWidget

    app = QApplication.instance() or QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("SHARC Preview — CesiumJS spike (Fase 2)")
    window.resize(1100, 750)
    window.setCentralWidget(CesiumSpikeWidget())
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
