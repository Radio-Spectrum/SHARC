"""Empty states: what a panel shows while it has nothing to list (icon, headline, hint and an optional action).

`EmptyState` is a plain widget; `EmptyStateOverlay` floats one over a host widget (a tree, a table) and keeps it
centred while the host is empty, so the panel code only has to call `overlay.set_empty(True/False)`.
"""
from __future__ import annotations

from typing import Optional

import qtawesome as qta
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

_ICON_PX = 36


class EmptyState(QFrame):
    action_clicked = Signal()

    def __init__(self, glyph: str, headline: str, hint: str = "", action_text: str = "",
                 icon_color: str = "#5D6778", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self._glyph = glyph
        self._icon_color = icon_color
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignCenter)
        self.icon = QLabel()
        self.icon.setObjectName("EmptyStateIcon")
        self.icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.icon)
        self.headline = QLabel(headline)
        self.headline.setObjectName("EmptyStateHeadline")
        self.headline.setAlignment(Qt.AlignCenter)
        self.headline.setWordWrap(True)
        lay.addWidget(self.headline)
        self.hint = QLabel(hint)
        self.hint.setObjectName("EmptyStateHint")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))
        self.hint.setMaximumWidth(420)
        lay.addWidget(self.hint)
        self.action = QPushButton(action_text)
        self.action.setObjectName("EmptyStateAction")
        self.action.setCursor(Qt.PointingHandCursor)
        self.action.setVisible(bool(action_text))
        self.action.clicked.connect(self.action_clicked)
        lay.addWidget(self.action, 0, Qt.AlignCenter)
        self._paint_icon()

    def set_text(self, headline: Optional[str] = None, hint: Optional[str] = None) -> None:
        if headline is not None:
            self.headline.setText(headline)
        if hint is not None:
            self.hint.setText(hint)
            self.hint.setVisible(bool(hint))

    def refresh_icons(self, tokens: dict) -> None:
        self._icon_color = tokens.get("icon_muted", self._icon_color)
        self._paint_icon()

    def _paint_icon(self) -> None:
        self.icon.setPixmap(qta.icon(self._glyph, color=self._icon_color).pixmap(_ICON_PX, _ICON_PX))


class EmptyStateOverlay(QObject):
    """Keeps an EmptyState centred over `host` (its viewport when it has one) and shows it only while empty."""

    def __init__(self, host: QWidget, empty_state: EmptyState):
        super().__init__(host)
        self._surface = host.viewport() if hasattr(host, "viewport") else host
        self.widget = empty_state
        self.widget.setParent(self._surface)
        self._surface.installEventFilter(self)
        self._empty = False
        self.widget.hide()

    def set_empty(self, empty: bool) -> None:
        self._empty = empty
        self.widget.setVisible(empty)
        if empty:
            self._place()

    def set_text(self, headline: Optional[str] = None, hint: Optional[str] = None) -> None:
        self.widget.set_text(headline, hint)

    def refresh_icons(self, tokens: dict) -> None:
        self.widget.refresh_icons(tokens)

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802 (Qt override)
        if obj is self._surface and ev.type() in (QEvent.Resize, QEvent.Show) and self._empty:
            self._place()
        return False

    def _place(self) -> None:
        self.widget.adjustSize()
        host = self._surface.size()
        w = min(max(self.widget.sizeHint().width(), 460), max(120, host.width() - 16))
        h = self.widget.heightForWidth(w) if self.widget.hasHeightForWidth() else self.widget.sizeHint().height()
        h = max(h, self.widget.sizeHint().height())
        self.widget.setGeometry((host.width() - w) // 2, max(0, (host.height() - h) // 2), w, h)
        self.widget.raise_()
