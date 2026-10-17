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

# Folder with the current terrain overlays (land cover, hillshade, height-map), served at /terrain/.
_OVERLAY = {"dir": None}


def set_overlay_dir(path) -> None:
    """Choose the folder served under /terrain/ (None disables it)."""
    _OVERLAY["dir"] = os.path.abspath(path) if path else None



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

    def _send_bytes(self, body: bytes, ctype: str, cache: str = "public, max-age=3600") -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _serve_tile(self) -> bool:
        """Adaptive terrain/land-cover tiles: /tiles/<terrain|hillshade|clutter>/<z>/<x>/<y>.<ext>."""
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) != 5 or parts[0] != "tiles":
            return False
        try:
            kind, z, x, y = parts[1], int(parts[2]), int(parts[3]), int(parts[4].split(".")[0])
            from core import tile_service as ts
        except (ValueError, ImportError):
            self.send_error(400, "bad tile request")
            return True
        try:
            if kind == "terrain":
                body = ts.tile_terrain_f32(z, x, y)
                ctype = "application/octet-stream"
            elif kind == "hillshade":
                body, ctype = ts.tile_hillshade_png(z, x, y), "image/png"
            elif kind in ("clutter", "clutter_clean"):
                body, ctype = ts.tile_clutter_png(z, x, y, clean=(kind == "clutter_clean")), "image/png"
            else:
                self.send_error(404, "unknown tile layer")
                return True
        except Exception as exc:  # noqa: BLE001 - one bad tile must not kill the server
            print(f"[cesium_spike server] tile error {kind}/{z}/{x}/{y}: {exc}")
            body = None
        if body is None:
            if kind == "terrain":
                self.send_error(404, "no elevation data")
            else:   # imagery unavailable right now: 503 so the 3D view retries instead of keeping a blank
                self.send_error(503, "tile temporarily unavailable")
            return True
        self._send_bytes(body, ctype)
        return True

    def _serve_warm(self) -> bool:
        """/warm?lat=..&lon=..&z=15 : download the tile chain at a point in the background."""
        if not self.path.startswith("/warm"):
            return False
        from urllib.parse import parse_qs, urlparse
        try:
            from core import tile_service as ts
            q = parse_qs(urlparse(self.path).query)
            lat, lon = float(q["lat"][0]), float(q["lon"][0])
            zmax = int(q.get("z", ["15"])[0])
        except (KeyError, ValueError, ImportError):
            self.send_error(400, "bad warm request")
            return True
        threading.Thread(target=ts.warm, args=(lat, lon, zmax), daemon=True, name="TileWarm").start()
        self._send_bytes(b"{}", "application/json", "no-store")
        return True

    def _serve_hydro(self) -> bool:
        """/hydro?west=..&south=..&east=..&north=.. : rivers and lakes in view as GeoJSON."""
        if not self.path.startswith("/hydro"):
            return False
        import json
        from urllib.parse import parse_qs, urlparse
        try:
            from core import hydro_service as hs
            q = parse_qs(urlparse(self.path).query)
            box = [float(q[k][0]) for k in ("west", "south", "east", "north")]
            body = json.dumps(hs.query(*box)).encode("utf-8")
        except (KeyError, ValueError, ImportError) as exc:
            self.send_error(400, f"bad hydro request: {exc}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[cesium_spike server] hydro error: {exc}")
            body = b'{"type":"FeatureCollection","features":[]}'
        self._send_bytes(body, "application/json", "no-store")
        return True

    def _serve_model(self) -> bool:
        """/models/<name>.glb : procedural 3D models (satellite, tower, earth station)."""
        if not self.path.startswith("/models/"):
            return False
        name = self.path.split("?", 1)[0].rsplit("/", 1)[-1].replace(".glb", "")
        try:
            from core import model_factory
            body = model_factory.glb(name)
        except (KeyError, ImportError):
            self.send_error(404, "unknown model")
            return True
        self._send_bytes(body, "model/gltf-binary")
        return True

    def _serve_buildings(self) -> bool:
        """/buildings?west=..&south=..&east=..&north=.. : cached OSM buildings + pending count."""
        if not self.path.startswith("/buildings"):
            return False
        import json
        from urllib.parse import parse_qs, urlparse
        try:
            from core import buildings_service as bs
            q = parse_qs(urlparse(self.path).query)
            box = [float(q[k][0]) for k in ("west", "south", "east", "north")]
            tmax = int(q.get("trees", ["0"])[0])
            body = json.dumps(bs.query(*box, want_trees=tmax > 0, tree_limit=max(1, tmax), want_roads=q.get("roads", ["0"])[0] == "1")).encode("utf-8")
        except (KeyError, ValueError, ImportError) as exc:
            self.send_error(400, f"bad buildings request: {exc}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[cesium_spike server] buildings error: {exc}")
            body = b'{"features":[],"pending":0}'
        self._send_bytes(body, "application/json", "no-store")
        return True

    def do_GET(self):  # noqa: N802 (stdlib method name)
        if self._serve_buildings():
            return
        if self._serve_model():
            return
        if self._serve_hydro():
            return
        if self._serve_warm():
            return
        if self.path.startswith("/tiles/") and self._serve_tile():
            return
        if self.path.startswith("/terrain/") and _OVERLAY["dir"]:
            name = os.path.basename(self.path.split("?", 1)[0])
            full = os.path.join(_OVERLAY["dir"], name)
            if name in ("clutter.png", "hillshade.png", "heightmap.bin", "overlay.json") and os.path.isfile(full):
                body = open(full, "rb").read()
                ctype = {"png": "image/png", "bin": "application/octet-stream", "json": "application/json"}[name.rsplit(".", 1)[1]]
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404, "terrain overlay not found")
            return
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


class _QuietServer(http.server.ThreadingHTTPServer):
    """The browser cancels tile requests when the camera moves; that is normal, not an error."""

    daemon_threads = True

    def handle_error(self, request, client_address):  # noqa: D401
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class CesiumSpikeServer:
    """Background thread running the offline static server."""

    def __init__(self):
        self._httpd: Optional[_QuietServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        """Start the server (idempotent) and return the bound port."""
        if self._httpd is not None:
            return self._httpd.server_address[1]

        handler = functools.partial(_Handler)
        self._httpd = _QuietServer(("127.0.0.1", 0), handler)
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
