"""Local, offline-only static file server for the CesiumJS Preview spike.

Serves the files in this directory (index.html, app.js, vendor/cesium/...)
over plain HTTP on 127.0.0.1 so CesiumJS's Web Workers can load correctly —
unlike the tempfile-under-``file://`` approach the Preview's old Plotly
engine used, Cesium's worker pool does not reliably start under the
``file://`` scheme. Binds to an OS-assigned free port and only to loopback;
never reachable off-box.

``/qwebchannel.js`` is special-cased: instead of shipping a copy of Qt's
JS helper (which would silently drift from whatever PySide6/Qt version is
installed), it is read fresh from the Qt resource system
(``:/qtwebchannel/qwebchannel.js``) on every request.
"""

from __future__ import annotations

import functools
import http.server
import os
import threading
from typing import Optional

_WEB_ROOT = os.path.dirname(os.path.abspath(__file__))


def _read_qwebchannel_js() -> bytes:
    from PySide6.QtCore import QFile, QIODevice

    f = QFile(":/qtwebchannel/qwebchannel.js")
    if not f.open(QIODevice.ReadOnly):
        raise RuntimeError(
            "Could not read :/qtwebchannel/qwebchannel.js from the Qt "
            "resource system — is PySide6.QtWebChannel imported?"
        )
    try:
        return bytes(f.readAll().data())
    finally:
        f.close()


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=_WEB_ROOT, **kwargs)

    def do_GET(self):  # noqa: N802 (stdlib method name)
        if self.path in ("/qwebchannel.js", "/qwebchannel.js/"):
            try:
                body = _read_qwebchannel_js()
            except Exception as e:
                self.send_error(500, str(e))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        print(f"[cesium_spike server] {self.address_string()} - {fmt % args}")


class CesiumSpikeServer:
    """Background thread running the offline static server."""

    def __init__(self):
        self._httpd: Optional[http.server.ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        """Start the server (idempotent) and return the bound port."""
        if self._httpd is not None:
            return self._httpd.server_address[1]

        handler = functools.partial(_Handler)
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="CesiumSpikeServer", daemon=True
        )
        self._thread.start()
        return self._httpd.server_address[1]

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None

    @property
    def port(self) -> Optional[int]:
        return self._httpd.server_address[1] if self._httpd else None
