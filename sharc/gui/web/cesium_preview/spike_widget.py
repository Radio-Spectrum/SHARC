"""CesiumJS Preview widget: offline Cesium viewer + QWebChannel bridge.

Two ways to use it:

- Standalone (``sharc/gui/tools/run_cesium_spike.py``): no ``scene_provider``
  given, defaults to ``demo_scene.py``'s hand-picked/default-parameter
  topology builders. Does not touch the main GUI's tab list.
- Embedded in the real ``PreviewTab`` (Fase 4+ of
  CESIUMJS_MIGRATION_PLAN.md's "integração real"): constructed with
  ``scene_provider=self._scene_graph_to_cesium_json`` (see
  ``core/cesium_bridge.py``), so ``PyBridge.get_scene`` returns the actual
  scenario the user configured in the GUI, built from the real SHARC engine
  objects — not demo data.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .local_server import CesiumSpikeServer
from .demo_scene import build_scene_json, SUPPORTED_TOPOLOGIES


def _default_scene_provider(topology_type: str) -> str:
    return build_scene_json(topology_type)


class PyBridge(QObject):
    """Python object exposed to the page over QWebChannel.

    ``scene_provider`` is a ``(topology_type: str) -> json_str`` callable —
    defaults to the standalone demo builders (``demo_scene.py``); the real
    ``PreviewTab`` passes its own that returns the actual scenario instead.
    """

    pong = Signal(str)

    def __init__(self, scene_provider: Optional[Callable[[str], str]] = None, parent=None):
        super().__init__(parent)
        self._scene_provider = scene_provider or _default_scene_provider

    @Slot(str)
    def ping(self, message: str) -> None:
        print(f"[cesium_spike] ping from JS: {message!r}")
        self.pong.emit(f"Python received: {message!r}")

    @Slot(result=str)
    def get_supported_topologies(self) -> str:
        return json.dumps(list(SUPPORTED_TOPOLOGIES))

    @Slot(str, result=str)
    def get_scene(self, topology_type: str) -> str:
        """Return a SceneGraph for *topology_type* as JSON (see class docstring)."""
        try:
            return self._scene_provider(topology_type)
        except Exception as e:
            print(f"[cesium_spike] get_scene({topology_type!r}) failed: {e}")
            return json.dumps({"error": str(e), "topology_type": topology_type})


class CesiumSpikeWidget(QWidget):
    """Offline CesiumJS viewer + QWebChannel bridge.

    ``embedded=True`` hides the standalone spike's manual topology
    dropdown/status label (Python drives what's rendered instead — see
    ``ui/tabs/preview.py``'s ``_refresh_cesium``).
    """

    def __init__(self, parent=None, scene_provider: Optional[Callable[[str], str]] = None, embedded: bool = False):
        super().__init__(parent)

        self._server = CesiumSpikeServer()
        port = self._server.start()
        self._embedded = embedded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not embedded:
            self._label = QLabel(f"CesiumJS spike — serving from http://127.0.0.1:{port}/")
            self._label.setStyleSheet("color: #888; font: 10px Consolas; padding: 2px;")
            layout.addWidget(self._label)

        self.view = QWebEngineView()
        layout.addWidget(self.view)

        self.bridge = PyBridge(scene_provider=scene_provider)
        self.channel = QWebChannel()
        self.channel.registerObject("pyBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        url = f"http://127.0.0.1:{port}/index.html"
        if embedded:
            url += "?embedded=1"
        self.view.load(QUrl(url))

    def request_scene(self, topology_type: str) -> None:
        """Ask the page to (re-)fetch and render *topology_type* now.

        Used by the real Preview tab every time it redraws — see
        ``PreviewTab._refresh_cesium``.
        """
        safe = json.dumps(topology_type)
        self.view.page().runJavaScript(f"requestScene({safe});")

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self._server.stop()
        super().closeEvent(event)
