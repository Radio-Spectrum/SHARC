"""Guided set-up for photorealistic 3D (Google Photorealistic 3D Tiles) in the preview.

Two sources work: a free Cesium ion access token (the tiles are Cesium ion asset 2275207, which has
to be added to the account's "My Assets" once) or a Google Map Tiles API key. This dialog explains
each step, opens the right web pages, takes the credential in a masked field, tests it and, when
the user saves, writes it into the Terrain tab's own fields (`terr_ion_token`, `terr_photoreal_key`),
so persistence and the 3D view follow the existing path. The credential stays in the user's
QSettings; it is never written to a project or YAML file.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout,
                               QWidget)

ION_TOKENS_URL = "https://ion.cesium.com/tokens"
ION_SIGNUP_URL = "https://ion.cesium.com/signup"
ION_ASSET_URL = "https://ion.cesium.com/assetdepot/2275207"
GOOGLE_KEYS_URL = "https://console.cloud.google.com/apis/credentials"
GOOGLE_API_URL = "https://console.cloud.google.com/apis/library/tile.googleapis.com"

ION_STEPS = (
    "Create a free account at ion.cesium.com (or sign in).",
    "Open <b>Asset Depot</b> and find <b>Google Photorealistic 3D Tiles</b>; click <b>Add to my assets</b>. "
    "Without this step the token is valid but the city does not appear.",
    "Open <b>Access Tokens</b>, click <b>Create token</b>, keep the default read permissions and copy the token.",
    "Paste it below, press <b>Test</b>, then <b>Save</b>.",
)
GOOGLE_STEPS = (
    "In Google Cloud Console, create or select a project with billing enabled.",
    "Enable the <b>Map Tiles API</b>.",
    "Under <b>Credentials</b>, create an <b>API key</b> and copy it.",
    "Paste it below, press <b>Test</b>, then <b>Save</b>. Google bills this API by use: check your quota.",
)


class _Result(QObject):
    done = Signal(bool, str)


class PhotorealSetupDialog(QDialog):
    def __init__(self, tab_terrain, parent=None):
        super().__init__(parent)
        self.tab = tab_terrain
        self._result = _Result()
        self._result.done.connect(self._show_result)
        self.setWindowTitle("Photorealistic 3D set-up")
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        intro = QLabel("Photorealistic 3D shows real city photogrammetry under the scenario. It needs one free "
                       "credential from the provider below. Your token stays on this computer.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.tabs = QTabWidget()
        self.ed_ion = self._page(ION_STEPS, "Cesium ion access token", "terr_ion_token",
                                 (("Create free account", ION_SIGNUP_URL), ("Add the 3D Tiles asset", ION_ASSET_URL),
                                  ("Open Access Tokens", ION_TOKENS_URL)), "Cesium ion token (free)")
        self.ed_google = self._page(GOOGLE_STEPS, "Google Map Tiles API key", "terr_photoreal_key",
                                    (("Enable Map Tiles API", GOOGLE_API_URL), ("Open Credentials", GOOGLE_KEYS_URL)),
                                    "Google Map Tiles key")
        lay.addWidget(self.tabs, 1)
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        self.lbl.setObjectName("StatusMsg")
        lay.addWidget(self.lbl)
        row = QHBoxLayout()
        self.btn_test = QPushButton("Test")
        self.btn_test.clicked.connect(self._test)
        self.btn_save = QPushButton("Save")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._save)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        row.addStretch(1)
        for b in (self.btn_test, self.btn_save, btn_close):
            row.addWidget(b)
        lay.addLayout(row)
        self._update_status()

    # ------------------------------------------------------------------ ui
    def _page(self, steps, field_label, state_key, links, tab_title) -> QLineEdit:
        w = QWidget()
        lay = QVBoxLayout(w)
        for i, text in enumerate(steps, 1):
            lab = QLabel(f"<b>{i}.</b> {text}")
            lab.setWordWrap(True)
            lay.addWidget(lab)
        row = QHBoxLayout()
        for text, url in links:
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        ed = QLineEdit(str(self.tab.state.get(state_key).get() or ""))
        ed.setEchoMode(QLineEdit.Password)
        ed.setPlaceholderText("Paste here")
        ed.setProperty("state_key", state_key)
        show = QPushButton("Show")
        show.setCheckable(True)
        show.toggled.connect(lambda on, e=ed, b=show: (e.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password),
                                                       b.setText("Hide" if on else "Show")))
        line = QHBoxLayout()
        line.addWidget(ed, 1)
        line.addWidget(show)
        form.addRow(field_label, line)
        lay.addLayout(form)
        lay.addStretch(1)
        self.tabs.addTab(w, tab_title)
        return ed

    def _current(self) -> QLineEdit:
        return self.ed_ion if self.tabs.currentIndex() == 0 else self.ed_google

    def _update_status(self) -> None:
        have_ion = bool(str(self.tab.state.get("terr_ion_token").get() or "").strip())
        have_google = bool(str(self.tab.state.get("terr_photoreal_key").get() or "").strip())
        if have_ion or have_google:
            what = " and ".join(n for n, h in (("Cesium ion token", have_ion), ("Google key", have_google)) if h)
            self.lbl.setText(f"Saved: {what}. Choose Scene look > Photorealistic 3D in the Terrain page to use it.")
        else:
            self.lbl.setText("No credential saved yet.")

    # --------------------------------------------------------------- actions
    def _test(self) -> None:
        ed = self._current()
        value = ed.text().strip()
        if not value:
            self.lbl.setText("Paste a credential first.")
            return
        self.lbl.setText("Checking...")
        self.btn_test.setEnabled(False)
        is_ion = ed is self.ed_ion

        def work():
            from core import photoreal_check
            try:
                ok, msg = photoreal_check.check_ion_token(value) if is_ion else photoreal_check.check_google_key(value)
            except Exception as exc:  # noqa: BLE001
                ok, msg = False, str(exc)
            self._result.done.emit(ok, msg)

        threading.Thread(target=work, daemon=True).start()

    def _show_result(self, ok: bool, msg: str) -> None:
        self.btn_test.setEnabled(True)
        self.lbl.setText(("OK: " if ok else "FAILED: ") + msg)

    def _save(self) -> None:
        for ed in (self.ed_ion, self.ed_google):
            self.tab.state.get(ed.property("state_key")).set(ed.text().strip())
        self._update_status()   # setting the state variables already redraws the preview (terrain tab)


def open_photoreal_setup(win) -> None:
    PhotorealSetupDialog(win.tab_terrain, win).exec()
