"""About SHARC: art banner, build identity (installed build or source checkout) and runtime versions."""
from __future__ import annotations

import os
import platform
import subprocess
from typing import List, Mapping, Optional, Sequence

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.shell.app_art import ArtBanner

from ui.shell.start_page import REPO_URL

TAGLINE = "SHARing and Compatibility studies"


def _git(args: List[str], cwd: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def build_lines() -> List[str]:
    """Human-readable identity of this copy: installer build info when present, else the git checkout."""
    from core import updater
    lines: List[str] = []
    info = updater.load_build_info()
    if info is not None:
        lines.append(f"Version {info.version or info.tag}  (installed build)")
        lines.append(f"Branch {info.branch}  ·  commit {info.commit[:10]}")
        if info.built_at:
            lines.append(f"Built {info.built_at}")
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        branch, commit = _git(["branch", "--show-current"], root), _git(["rev-parse", "--short=10", "HEAD"], root)
        lines.append("Source checkout" + (f"  ·  {branch} @ {commit}" if commit else ""))
    try:
        import PySide6
        qt = PySide6.__version__
    except Exception:  # noqa: BLE001 - only decorative
        qt = "?"
    lines.append(f"Python {platform.python_version()}  ·  PySide6 {qt}  ·  {platform.system()} "
                 f"{platform.release()}")
    return lines


class AboutDialog(QDialog):
    def __init__(self, parent=None, tokens: Optional[Mapping[str, str]] = None,
                 lines: Optional[Sequence[str]] = None):
        super().__init__(parent)
        self.setWindowTitle("About SHARC")
        self.setObjectName("AboutDialog")
        self.setFixedWidth(560)
        self._lines = list(lines) if lines is not None else build_lines()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        banner = ArtBanner("SHARC", TAGLINE, height=140)
        if tokens:
            banner.refresh_icons(tokens)
        root.addWidget(banner)

        body = QVBoxLayout()
        body.setContentsMargins(24, 16, 24, 16)
        body.setSpacing(6)
        for text in self._lines:
            lbl = QLabel(text)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.addWidget(lbl)
        credit = QLabel("Developed at the University of Brasília (UnB) with the Brazilian regulator and partners. "
                        "Open source under the project licence.")
        credit.setObjectName("CardSummary")
        credit.setWordWrap(True)
        body.addSpacing(6)
        body.addWidget(credit)
        root.addLayout(body)

        bar = QHBoxLayout()
        bar.setContentsMargins(24, 0, 24, 16)
        btn_repo = QPushButton("Project repository")
        btn_repo.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        btn_copy = QPushButton("Copy build info")
        btn_copy.clicked.connect(self.copy_build_info)
        btn_close = QPushButton("Close")
        btn_close.setObjectName("PrimaryButton")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        bar.addWidget(btn_repo)
        bar.addWidget(btn_copy)
        bar.addStretch(1)
        bar.addWidget(btn_close)
        root.addLayout(bar)

    def copy_build_info(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(self._lines))
