"""Optional "Feko-style" workbench layout: a tabbed ribbon with captioned groups of large buttons, plus a Model Status
panel. It only adds widgets and hides/shows existing ones; every button calls a slot the classic layout already has.
"""
import qtawesome as qta
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QDockWidget, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QTabWidget, QToolBar,
                               QToolButton, QVBoxLayout, QWidget)

RIBBON_HEIGHT = 96


class RibbonGroup(QFrame):
    def __init__(self, caption):
        super().__init__()
        self.setObjectName("RibbonGroup")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 2)
        lay.setSpacing(0)
        self.row = QHBoxLayout()
        self.row.setSpacing(2)
        lay.addLayout(self.row, 1)
        cap = QLabel(caption)
        cap.setObjectName("RibbonCaption")
        cap.setAlignment(Qt.AlignHCenter)
        lay.addWidget(cap)
        self.buttons = []

    def add(self, text, glyph, slot, tip=""):
        b = QToolButton()
        b.setObjectName("RibbonButton")
        b.setText(text)
        b.setToolTip(tip or text)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(28, 28))
        b.setMinimumWidth(62)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, s=slot: s())
        self.row.addWidget(b)
        self.buttons.append((b, glyph))
        return b


class Ribbon(QTabWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setObjectName("Ribbon")
        self.setDocumentMode(True)
        self.setFixedHeight(RIBBON_HEIGHT + 26)
        self.groups = []
        self._build()

    def _tab(self, title, groups):
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(2, 2, 2, 0)
        lay.setSpacing(0)
        for g in groups:
            lay.addWidget(g)
            self.groups.append(g)
        lay.addStretch(1)
        self.addTab(page, title)

    def _group(self, caption, items):
        g = RibbonGroup(caption)
        for text, glyph, slot, *tip in items:
            g.add(text, glyph, slot, tip[0] if tip else "")
        return g

    def _build(self):
        a = self.app
        pages = {k: (label, icon) for k, label, _c, icon, _s in a.pages_config}

        def go(key):
            return lambda: a._switch_page(key, pages[key][0])

        def page_items(keys):
            return [(pages[k][0], pages[k][1], go(k)) for k in keys]

        def toggle(dock):
            return lambda: dock.setVisible(not dock.isVisible())

        home = [
            self._group("File", [
                ("New", "mdi.file-outline", a.new_project, "New project (Ctrl+N)"),
                ("Open", "mdi.folder-open-outline", a.open_project_dialog, "Open project (Ctrl+O)"),
                ("Save", "mdi.content-save-outline", a.save_project, "Save project (Ctrl+S)"),
                ("Manager", "mdi.briefcase-outline", a.show_project_manager, "Project manager"),
            ]),
            self._group("Validate", [
                ("Model Status", "mdi.check-decagram-outline", a._refresh_model_status,
                 "Builds the scenario with the engine and reports whether the model is valid"),
            ]),
            self._group("Run / Launch", [
                ("Run", "mdi.play-circle-outline", a.run_simulation, "Run simulation (Ctrl+R)"),
                ("Run later", "mdi.calendar-clock", a.run_simulation_later, "Schedule the simulation"),
                ("Stop", "mdi.stop-circle-outline", a.stop_simulation, "Stop running simulations"),
            ]),
            self._group("Sweep", [
                ("Parameter sweep", "mdi.table-large", a._proxy_batch_generate,
                 "Generate the sweep configurations without running"),
                ("Refresh preview", "mdi.refresh", a._refresh_preview, "Rebuild the 3D preview"),
            ]),
            self._group("Help", [
                ("Help", "mdi.help-circle-outline", a._toggle_help, "Explains the current page and parameters (F1)"),
                ("Handbook", "mdi.book-open-page-variant-outline", lambda: a._open_handbook(), "Open the handbook"),
            ]),
        ]
        self._tab("Home", home)
        self._tab("Scenario", [
            self._group("IMT and database", page_items(["general", "imt", "database"])),
            self._group("Environment", page_items(["terrain"])),
            self._group("Systems", page_items(["victim", "station"])),
        ])
        self._tab("Simulate", [
            self._group("Preview", page_items(["preview", "contour"])),
            self._group("Execution", page_items(["runner", "ssh"])),
            self._group("Run / Launch", [
                ("Run", "mdi.play-circle-outline", a.run_simulation, "Run simulation (Ctrl+R)"),
                ("Stop", "mdi.stop-circle-outline", a.stop_simulation, "Stop running simulations"),
            ]),
        ])
        self._tab("Results", [
            self._group("Analysis", page_items(["results"])),
            self._group("Export", [
                ("Figures", "mdi.image-multiple-outline", a._export_publication_figures,
                 "Export publication figures (Ctrl+Shift+E)"),
                ("Results folder", "mdi.folder-outline", a._open_results_folder, "Open the results folder"),
            ]),
        ])
        self._tab("View", [
            self._group("Panels", [
                ("Items", "mdi.file-tree-outline", toggle(a.dock_scenario), "Show or hide the Items tree"),
                ("Properties", "mdi.tune-variant", toggle(a.dock_properties), "Show or hide Properties"),
                ("Status", "mdi.shield-check-outline", toggle(a.dock_model_status), "Show or hide Model Status"),
                ("Messages", "mdi.message-text-outline", toggle(a.dock_messages), "Show or hide Messages"),
                ("Jobs", "mdi.format-list-checks", toggle(a.dock_jobs), "Show or hide Jobs"),
            ]),
            self._group("Layout", [
                ("Reset", "mdi.view-dashboard-outline", a._reset_workbench_layout, "Restore the default panel layout"),
                ("Classic", "mdi.view-split-vertical", lambda: a._set_layout_mode("classic"),
                 "Go back to the classic layout"),
                ("Theme", "mdi.theme-light-dark", a._toggle_theme_safely, "Toggle graphite / light theme"),
            ]),
        ])

    def refresh_icons(self, tokens):
        for g in self.groups:
            for b, glyph in g.buttons:
                b.setIcon(qta.icon(glyph, color=tokens["icon"]))

    def stylesheet(self, t):
        return (
            f"QTabWidget#Ribbon::pane {{ border-top: 1px solid {t['border']}; background: {t['bg_panel']}; }}"
            f"QTabWidget#Ribbon QTabBar::tab {{ padding: 4px 12px; color: {t['text_secondary']}; border: none;"
            f" background: transparent; }}"
            f"QTabWidget#Ribbon QTabBar::tab:selected {{ color: {t['text_primary']};"
            f" border-bottom: 2px solid {t['accent']}; }}"
            f"QTabWidget#Ribbon QTabBar::tab:hover {{ color: {t['text_primary']}; }}"
            f"QFrame#RibbonGroup {{ border: none; border-right: 1px solid {t['border_soft']}; }}"
            f"QLabel#RibbonCaption {{ color: {t['text_muted']}; font-size: 9pt; }}"
            f"QToolButton#RibbonButton {{ border: 1px solid transparent; border-radius: 3px; padding: 3px 4px;"
            f" color: {t['text_primary']}; background: transparent; }}"
            f"QToolButton#RibbonButton:hover {{ background: {t['bg_hover']}; border-color: {t['border']}; }}"
            f"QToolButton#RibbonButton:pressed {{ background: {t['accent_dim']}; }}")


class ModelStatusDock(QDockWidget):
    """Feko's Model Status panel: whether the model builds, and the latest messages."""

    def __init__(self, parent=None):
        super().__init__("Model Status", parent)
        self.setObjectName("DockModelStatus")
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(6, 6, 6, 6)
        self.state = QLabel("Not checked")
        self.state.setObjectName("ModelStatusState")
        self.state.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.state.setWordWrap(True)
        self.detail = QLabel("Press Model Status in the Home tab to build the scenario with the engine.")
        self.detail.setWordWrap(True)
        head = QLabel("Messages")
        head.setStyleSheet("font-weight: bold;")
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setObjectName("ModelStatusMessages")
        lay.addWidget(self.state)
        lay.addWidget(self.detail)
        lay.addWidget(head)
        lay.addWidget(self.messages, 1)
        self.setWidget(host)

    def show_result(self, ok, summary, detail, lines, tokens):
        color = tokens["success"] if ok else tokens["danger"]
        self.state.setText(summary)
        self.state.setStyleSheet(f"font-weight: bold; font-size: 11pt; color: {color};")
        self.detail.setText(detail)
        self.messages.setPlainText("\n".join(lines))
        self.messages.verticalScrollBar().setValue(self.messages.verticalScrollBar().maximum())


def build_ribbon_toolbar(app):
    """Returns (toolbar, ribbon); the toolbar hosts the ribbon above the dock areas."""
    ribbon = Ribbon(app)
    tb = QToolBar("Ribbon", app)
    tb.setObjectName("RibbonToolBar")
    tb.setMovable(False)
    tb.setFloatable(False)
    tb.addWidget(ribbon)
    return tb, ribbon
