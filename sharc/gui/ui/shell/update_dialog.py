"""Update prompt: checks the branch release in the background and lets the user decide.

``check_for_updates(window, manual)`` is the only entry point. Start-up checks stay silent unless a
newer build exists (and the user has not skipped it); manual checks always answer.
"""
import threading

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QTextBrowser, QVBoxLayout,
)

from core import updater

KEY_CHECK_ON_START = "updates/check_on_start"
KEY_SKIPPED = "updates/skipped_commit"


def check_on_start_enabled() -> bool:
    value = QSettings("SHARC", "GUI").value(KEY_CHECK_ON_START, True)
    return str(value).lower() in ("true", "1", "yes")


def set_check_on_start(enabled: bool) -> None:
    QSettings("SHARC", "GUI").setValue(KEY_CHECK_ON_START, enabled)


def _changelog_markdown(info: "updater.UpdateInfo") -> str:
    parts = []
    if info.changes:
        parts.append("### Changes since your build\n" + "\n".join(f"- {c}" for c in info.changes))
    if info.notes:
        parts.append("### Release notes\n" + info.notes)
    return "\n\n".join(parts) or "No changelog available for this update."


class _CheckWorker(QObject):
    found = Signal(object)    # UpdateInfo
    uptodate = Signal()
    failed = Signal(str)

    def __init__(self, build):
        super().__init__()
        self._build = build

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            info = updater.check_for_update(self._build)
        except updater.UpdateError as exc:
            self.failed.emit(str(exc))
            return
        if info is None:
            self.uptodate.emit()
        else:
            self.found.emit(info)


class UpdateDialog(QDialog):
    _progress = Signal(int, int)
    _downloaded = Signal(str)
    _download_failed = Signal(str)

    def __init__(self, info, parent=None):
        super().__init__(parent)
        self._info = info
        self._cancel = False
        self.setWindowTitle("SHARC update available")
        self.resize(640, 520)

        cur = info.current
        title = QLabel(f"<b>A new build of SHARC is available</b> (branch <i>{cur.branch}</i>)")
        detail = QLabel(f"Installed: {cur.short_commit}   ->   New: {info.short_commit}"
                        f"   |   Installer: {info.asset_size / 1e6:.0f} MB")
        detail.setStyleSheet("color: gray;")
        self._notes = QTextBrowser()
        self._notes.setOpenExternalLinks(True)
        self._notes.setMarkdown(_changelog_markdown(info))

        self._bar = QProgressBar()
        self._bar.setVisible(False)
        self._status = QLabel("")

        self._btn_now = QPushButton("Update now")
        self._btn_now.setDefault(True)
        self._btn_later = QPushButton("Remind me later")
        self._btn_skip = QPushButton("Skip this version")
        self._btn_now.clicked.connect(self._start_download)
        self._btn_later.clicked.connect(self.reject)
        self._btn_skip.clicked.connect(self._skip)

        buttons = QHBoxLayout()
        buttons.addWidget(self._btn_skip)
        buttons.addStretch(1)
        buttons.addWidget(self._btn_later)
        buttons.addWidget(self._btn_now)

        lay = QVBoxLayout(self)
        for w in (title, detail, self._notes, self._bar, self._status):
            lay.addWidget(w)
        lay.addLayout(buttons)

        self._progress.connect(self._on_progress)
        self._downloaded.connect(self._on_downloaded)
        self._download_failed.connect(self._on_failed)

    def _skip(self):
        QSettings("SHARC", "GUI").setValue(KEY_SKIPPED, self._info.latest_commit)
        self.reject()

    def _start_download(self):
        for b in (self._btn_now, self._btn_skip):
            b.setEnabled(False)
        self._btn_later.setText("Cancel")
        self._btn_later.clicked.disconnect()
        self._btn_later.clicked.connect(self._cancel_download)
        self._bar.setVisible(True)
        self._status.setText("Downloading installer...")
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            path = updater.download_installer(
                self._info, progress=self._progress.emit, cancelled=lambda: self._cancel)
        except updater.UpdateError as exc:
            self._download_failed.emit(str(exc))
            return
        self._downloaded.emit(path)

    def _cancel_download(self):
        self._cancel = True

    def _on_progress(self, done, total):
        if total:
            self._bar.setMaximum(total)
            self._bar.setValue(done)
            self._status.setText(f"Downloading installer... {done / 1e6:.0f} / {total / 1e6:.0f} MB")

    def _on_failed(self, message):
        self._bar.setVisible(False)
        self._status.setText(message)
        self._btn_now.setEnabled(True)
        self._btn_now.setText("Retry")
        self._btn_skip.setEnabled(True)
        self._cancel = False
        self._btn_later.setText("Close")
        self._btn_later.clicked.disconnect()
        self._btn_later.clicked.connect(self.reject)

    def _on_downloaded(self, path):
        self._status.setText("Starting installer... SHARC will close so the update can finish.")
        updater.launch_installer(path)
        QApplication.quit()


def check_for_updates(window, manual: bool = False):
    """Look for a newer build of this branch; prompt if there is one."""
    build = updater.load_build_info()
    if build is None:
        if manual:
            QMessageBox.information(
                window, "Check for updates",
                "Updates are only available in the installed SHARC build, not when running from source.")
        return
    worker = _CheckWorker(build)
    window._update_worker = worker  # keep alive until the thread reports back

    def on_found(info):
        skipped = QSettings("SHARC", "GUI").value(KEY_SKIPPED, "")
        if not manual and skipped == info.latest_commit:
            return
        UpdateDialog(info, window).exec()

    def on_uptodate():
        if manual:
            QMessageBox.information(
                window, "Check for updates",
                f"SHARC is up to date.\n\nBranch: {build.branch}\nBuild: {build.short_commit}")

    def on_failed(message):
        if manual:
            QMessageBox.warning(window, "Check for updates", message)
        else:
            print(f">> Update check skipped: {message}")

    worker.found.connect(on_found, Qt.QueuedConnection)
    worker.uptodate.connect(on_uptodate, Qt.QueuedConnection)
    worker.failed.connect(on_failed, Qt.QueuedConnection)
    worker.start()
