"""End-to-end check that the 3D view can reach Cesium ion / Google Photorealistic 3D Tiles.

    python sharc/gui/tools/validate_photoreal.py

The token is read from $SHARC_ION_TOKEN or from the GUI's saved settings (Terrain tab). It is never printed.
It checks, in order: (1) the REST API (`core/photoreal_check.py`), (2) the real page in a headless WebEngine,
where the page's Content-Security-Policy applies, loading the Google tileset and Cesium World Terrain, and
(3) the app's own `setPhotoreal("photo", ...)` path. Exit code 0 = everything connected.
"""
from __future__ import annotations

import json
import os
import sys

GUI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(GUI_DIR))
for p in (GUI_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

TIMEOUT_MS = 45000


def _token() -> str:
    tok = os.environ.get("SHARC_ION_TOKEN", "").strip()
    if tok:
        return tok
    from PySide6.QtCore import QSettings
    return str(QSettings("SHARC", "GUI").value("terrain/terr_ion_token", "") or "").strip()


def main() -> int:
    token = _token()
    if not token:
        print("No ion token: set SHARC_ION_TOKEN or fill it in the Terrain tab first.")
        return 2

    from core import photoreal_check
    ok_rest, msg = photoreal_check.check_ion_token(token)
    print(("PASS" if ok_rest else "FAIL"), "REST:", msg)

    from PySide6.QtCore import QTimer
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWidgets import QApplication
    from web.cesium_preview.spike_widget import CesiumSpikeWidget

    class Page(QWebEnginePage):
        errors: list = []

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            if level == QWebEnginePage.ErrorMessageLevel or "Content Security Policy" in message:
                Page.errors.append(message[:200])

    app = QApplication(sys.argv)
    w = CesiumSpikeWidget(embedded=True)
    url = w.view.page().requestedUrl()
    page = Page(w.view)
    w.view.setPage(page)
    page.load(url)                                    # the replacement page starts blank
    results = {}

    def js(code, cb=None):
        page.runJavaScript(code, cb or (lambda _r: None))

    def start():
        tok = json.dumps(token)
        js(f"""window.__r = null; (async () => {{
          try {{
            Cesium.Ion.defaultAccessToken = {tok};
            await Cesium.Cesium3DTileset.fromIonAssetId(2275207);
            const terrain = await Cesium.createWorldTerrainAsync();
            window.__r = {{ ok: true }};
          }} catch (e) {{ window.__r = {{ ok: false, err: String((e && e.message) || e) }}; }}
        }})();""")
        js(f'setPhotoreal("photo", {tok}, "");')

    def poll():
        def got(r):
            if r:
                results["direct"] = json.loads(r)
        js("JSON.stringify(window.__r)", got)

        def got_app(r):
            results["app"] = r
        js('JSON.stringify({mode: photoreal.mode, hasTileset: !!photoreal.tileset})', got_app)

    QTimer.singleShot(6000, start)                    # let the page finish loading first
    for ms in range(12000, TIMEOUT_MS, 4000):
        QTimer.singleShot(ms, poll)
    QTimer.singleShot(TIMEOUT_MS, app.quit)
    app.exec()

    direct = results.get("direct") or {}
    app_state = json.loads(results["app"]) if results.get("app") else {}
    ok_direct = bool(direct.get("ok"))
    ok_app = app_state.get("mode") == "photo" and app_state.get("hasTileset")
    print(("PASS" if ok_direct else "FAIL"), "Page loads Google tileset + World Terrain",
          "" if ok_direct else f"-> {direct.get('err', 'no answer')}")
    print(("PASS" if ok_app else "FAIL"), "App setPhotoreal('photo') active", app_state)
    csp = [e for e in Page.errors if "Content Security Policy" in e]
    if csp:
        print("CSP violations:", *csp[:3], sep="\n  ")
    elif Page.errors:
        print("Page errors:", *Page.errors[:3], sep="\n  ")
    good = ok_rest and ok_direct and ok_app
    print("RESULT:", "OK" if good else "PROBLEMS")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
