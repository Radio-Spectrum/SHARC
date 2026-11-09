"""Help dock: a Context tab (what the current page, section and parameters mean) and the Handbook."""
import html
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDockWidget, QLineEdit, QListWidget, QSplitter, QTabWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from ui.shell import help_content as hc
from ui.shell.handbook import TOPICS

_TAG = re.compile(r"<[^>]+>")


def context_html(page_key, page_label, section_title, rows):
    """HTML for the Context tab. `rows` are the visible parameter labels of the selected page or section."""
    esc = html.escape
    parts = [f"<h3>{esc(page_label or 'SHARC')}</h3>"]
    if hc.PAGES.get(page_key):
        parts.append(f"<p>{esc(hc.PAGES[page_key])}</p>")
    if section_title:
        parts.append(f"<h4>{esc(section_title)}</h4>")
        text = hc.section_text(page_key, section_title)
        if text:
            parts.append(f"<p>{esc(text)}</p>")
    described = [(r, hc.lookup(page_key, r)) for r in rows]
    described = [(r, d) for r, d in described if d]
    if described:
        parts.append("<p><b>Parameters</b></p><ul>" +
                     "".join(f"<li><b>{esc(r)}</b>: {esc(d)}</li>" for r, d in described) + "</ul>")
    if page_key == "preview":
        parts.append("<p><b>3D buttons</b></p><ul>" +
                     "".join(f"<li><b>{esc(a)}</b>: {esc(b)}</li>" for a, b in hc.PREVIEW_BUTTONS) + "</ul>")
    parts.append("<p><i>Hover a parameter name to see its description. Open the Handbook tab for the full manual.</i></p>")
    return "".join(parts)


class HelpDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Help", parent)
        self.setObjectName("DockHelp")
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
                         | QDockWidget.DockWidgetClosable)

        self.tabs = QTabWidget()
        self.context = QTextBrowser()
        self.context.setObjectName("HelpContext")
        self.tabs.addTab(self.context, "Context")

        book = QWidget()
        lay = QVBoxLayout(book)
        lay.setContentsMargins(4, 4, 4, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the handbook...")
        self.search.setClearButtonEnabled(True)
        self.topics = QListWidget()
        self.topics.setObjectName("HandbookTopics")
        self.page = QTextBrowser()
        self.page.setObjectName("HandbookPage")
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.topics)
        split.addWidget(self.page)
        split.setSizes([120, 360])
        lay.addWidget(self.search)
        lay.addWidget(split, 1)
        self.tabs.addTab(book, "Handbook")
        self.setWidget(self.tabs)

        self._plain = [_TAG.sub(" ", h).lower() for _, h in TOPICS]
        self.search.textChanged.connect(self._fill_topics)
        self.topics.currentRowChanged.connect(self._show_topic)
        self._fill_topics("")

    def _fill_topics(self, text):
        q = (text or "").strip().lower()
        self.topics.blockSignals(True)
        self.topics.clear()
        self._visible = [i for i, (title, _) in enumerate(TOPICS)
                         if not q or q in title.lower() or q in self._plain[i]]
        for i in self._visible:
            self.topics.addItem(TOPICS[i][0])
        self.topics.blockSignals(False)
        if self._visible:
            self.topics.setCurrentRow(0)
            self._show_topic(0)
        else:
            self.page.setHtml("<p>No topic matches.</p>")

    def _show_topic(self, row):
        if 0 <= row < len(self._visible):
            self.page.setHtml(TOPICS[self._visible[row]][1])

    def show_context(self, page_key, page_label, section_title, rows):
        self.context.setHtml(context_html(page_key, page_label, section_title, rows))

    def open_topic(self, title):
        self.search.clear()
        for row, i in enumerate(self._visible):
            if TOPICS[i][0] == title:
                self.topics.setCurrentRow(row)
                break
        self.tabs.setCurrentIndex(1)
