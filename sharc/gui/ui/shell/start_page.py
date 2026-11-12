"""Start Page: the first document tab (New scenario from a template, Open / Recent projects, Learn).

Modelled on the welcome pages of CAE tools (Ansys Discovery, CST "New and Recent", STK "Welcome"). The page is a
view: it emits what the user chose and the workbench performs the action. `recent_provider` returns the recent
projects (`name`, `path`, `system`, `topology`, `modified`) so the page does not depend on the project service.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple

import qtawesome as qta
from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from core.scenario_templates import TEMPLATES, ScenarioTemplate
from ui.shell.app_art import ArtBanner

SETTINGS_KEY = "appearance/start_page"
TAGLINE = "SHARing and Compatibility studies — Monte Carlo interference simulator for IMT and other services"

REPO_URL = "https://github.com/Radio-Spectrum/SHARC"


@dataclass(frozen=True)
class LearnLink:
    """One entry of the Learn column. `kind` tells the workbench what to open; `target` is the manual volume
    (`kind="manual"`) or the URL (`kind="url"`)."""
    key: str
    caption: str
    glyph: str
    hint: str
    kind: Literal["help", "handbook", "manual", "url"]
    target: str = ""


LEARN_LINKS: Tuple[LearnLink, ...] = (
    LearnLink("help", "Help panel (F1)", "mdi.lifebuoy", "Explains the current page and each parameter", "help"),
    LearnLink("handbook", "Handbook", "mdi.book-open-page-variant-outline",
              "Concepts, workflow and scenario families", "handbook"),
    LearnLink("manual_vol1", "User manual (PDF)", "mdi.file-document-outline",
              "Installation, interface and every page", "manual", "vol1"),
    LearnLink("manual_vol2", "Scenario guide (PDF)", "mdi.map-outline",
              "Guidelines for the scenarios the templates cover", "manual", "vol2"),
    LearnLink("manual_vol3", "Architecture (PDF)", "mdi.sitemap", "How the simulator is built", "manual", "vol3"),
    LearnLink("website", "Project repository", "mdi.github", "Source code, issues and releases", "url", REPO_URL),
)


def find_learn_link(key: str) -> Optional[LearnLink]:
    return next((link for link in LEARN_LINKS if link.key == key), None)


def start_page_enabled() -> bool:
    value = QSettings("SHARC", "GUI").value(SETTINGS_KEY, True)
    return value in (True, "true", "True", 1, "1")


def set_start_page_enabled(on: bool) -> None:
    QSettings("SHARC", "GUI").setValue(SETTINGS_KEY, bool(on))


class TemplateCard(QFrame):
    chosen = Signal(str)

    def __init__(self, template: ScenarioTemplate, parent=None):
        super().__init__(parent)
        self.template = template
        self.setObjectName("TemplateCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(f"{template.system} · {template.link}\n{template.summary}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(4)
        head = QHBoxLayout()
        self.icon = QLabel()
        self.icon.setFixedSize(22, 22)
        head.addWidget(self.icon)
        title = QLabel(template.title)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        lay.addLayout(head)
        summary = QLabel(template.summary)
        summary.setObjectName("CardSummary")
        summary.setWordWrap(True)
        lay.addWidget(summary, 1)
        tags = QLabel("  ·  ".join(template.tags))
        tags.setObjectName("CardTags")
        lay.addWidget(tags)

    def refresh_icons(self, tokens: Mapping[str, str]) -> None:
        self.icon.setPixmap(qta.icon(self.template.glyph, color=tokens["accent"]).pixmap(20, 20))

    def mouseReleaseEvent(self, ev):  # noqa: N802 (Qt override)
        if ev.button() == Qt.LeftButton and self.rect().contains(ev.position().toPoint()):
            self.chosen.emit(self.template.key)
        super().mouseReleaseEvent(ev)


class _LinkButton(QPushButton):
    """A left-aligned icon + caption button used by the Start and Learn columns."""

    def __init__(self, caption: str, glyph: str, hint: str = "", parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.setObjectName("StartLink")
        self.setFlat(True)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.PointingHandCursor)
        self.setText(caption)
        self.setToolTip(hint or caption)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def refresh_icons(self, tokens: Mapping[str, str], role: str = "icon") -> None:
        self.setIcon(qta.icon(self.glyph, color=tokens.get(role, tokens["icon"])))


def _short_path(path: str, limit: int = 48) -> str:
    return path if len(path) <= limit else "…" + path[-(limit - 1):]


def _column_title(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("ColumnTitle")
    return lbl


class StartPage(QWidget):
    template_chosen = Signal(str)        # template key
    blank_requested = Signal()
    open_requested = Signal()
    recent_chosen = Signal(str)          # project path
    learn_requested = Signal(str)        # LEARN_LINKS key
    close_requested = Signal()

    def __init__(self, recent_provider: Callable[[], Iterable[Mapping]],
                 templates: Sequence[ScenarioTemplate] = TEMPLATES, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StartPage")
        self._recent_provider = recent_provider
        self._cards: List[TemplateCard] = []
        self._links: List[_LinkButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.banner = ArtBanner("SHARC", TAGLINE)
        outer.addWidget(self.banner)

        scroll = QScrollArea()
        scroll.setObjectName("StartScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("StartBody")
        cols = QHBoxLayout(body)
        cols.setContentsMargins(28, 22, 28, 18)
        cols.setSpacing(28)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # --- Start: blank / open, then the template cards
        start = QVBoxLayout()
        start.setSpacing(8)
        start.addWidget(_column_title("Start"))
        self.btn_blank = _LinkButton("New blank scenario", "mdi.file-plus-outline",
                                     "Start from the default values of every page")
        self.btn_blank.clicked.connect(self.blank_requested)
        self.btn_open = _LinkButton("Open project...", "mdi.folder-open-outline", "Open a .sharc project file")
        self.btn_open.clicked.connect(self.open_requested)
        start.addWidget(self.btn_blank)
        start.addWidget(self.btn_open)
        self._links += [self.btn_blank, self.btn_open]
        start.addSpacing(10)
        start.addWidget(_column_title("Scenario templates"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for i, tpl in enumerate(templates):
            card = TemplateCard(tpl)
            card.chosen.connect(self.template_chosen)
            grid.addWidget(card, i // 2, i % 2)
            self._cards.append(card)
        start.addLayout(grid)
        start.addStretch(1)
        cols.addLayout(start, 5)

        # --- Recent projects
        recent = QVBoxLayout()
        recent.setSpacing(8)
        recent.addWidget(_column_title("Recent projects"))
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("RecentList")
        self.recent_list.setIconSize(QSize(18, 18))
        self.recent_list.itemActivated.connect(self._on_recent)
        recent.addWidget(self.recent_list, 1)
        self.lbl_no_recent = QLabel("Projects you save (File > Save Project) appear here.")
        self.lbl_no_recent.setObjectName("CardSummary")
        self.lbl_no_recent.setWordWrap(True)
        recent.addWidget(self.lbl_no_recent)
        recent.addStretch(1)
        cols.addLayout(recent, 3)

        # --- Learn
        learn = QVBoxLayout()
        learn.setSpacing(8)
        learn.addWidget(_column_title("Learn"))
        for link in LEARN_LINKS:
            b = _LinkButton(link.caption, link.glyph, link.hint)
            b.clicked.connect(lambda _=False, k=link.key: self.learn_requested.emit(k))
            learn.addWidget(b)
            self._links.append(b)
        learn.addStretch(1)
        cols.addLayout(learn, 2)

        # --- Footer
        foot = QFrame()
        foot.setObjectName("StartFooter")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(28, 8, 28, 8)
        self.chk_startup = QCheckBox("Show this page on start-up")
        self.chk_startup.setChecked(start_page_enabled())
        self.chk_startup.toggled.connect(set_start_page_enabled)
        fl.addWidget(self.chk_startup)
        fl.addStretch(1)
        self.btn_close = QPushButton("Go to workbench")
        self.btn_close.setObjectName("PrimaryButton")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.close_requested)
        fl.addWidget(self.btn_close)
        outer.addWidget(foot)

        self._tokens: dict = {}
        self.refresh_recent()

    # ------------------------------------------------------------------ data
    def refresh_recent(self) -> None:
        self.recent_list.clear()
        items = list(self._recent_provider() or [])
        for it in items:
            name = it.get("name") or it.get("path", "")
            parts = (it.get("system", ""), it.get("topology", ""), it.get("modified", ""))
            sub = " · ".join(x for x in parts if x)
            row = QListWidgetItem(f"{name}\n{sub or _short_path(it.get('path', ''))}")
            row.setData(Qt.UserRole, it.get("path", ""))
            row.setToolTip(it.get("path", ""))
            if self._tokens:
                row.setIcon(qta.icon("mdi.folder-outline", color=self._tokens["icon"]))
            self.recent_list.addItem(row)
        self.recent_list.setVisible(bool(items))
        self.lbl_no_recent.setVisible(not items)

    def refresh_icons(self, tokens: Mapping[str, str]) -> None:
        self._tokens = dict(tokens)
        self.banner.refresh_icons(tokens)
        for card in self._cards:
            card.refresh_icons(tokens)
        for link in self._links:
            link.refresh_icons(tokens)
        self.btn_blank.refresh_icons(tokens, "accent")
        self.refresh_recent()

    def _on_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.recent_chosen.emit(path)
