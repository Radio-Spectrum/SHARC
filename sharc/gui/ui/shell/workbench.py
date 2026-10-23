"""Casca estilo estação de trabalho (referência: Feko, Ansys Electronics Desktop, QGIS).

Substitui sidebar + header + QStackedWidget por:
  - barra de ferramentas principal;
  - dock "Scenario" (árvore do projeto) à esquerda;
  - área central: abas "3D Scene" (Preview/Cesium) e "Results";
  - dock "Properties" (formulário da página) à direita;
  - docks "Messages" e "Jobs" abaixo;
  - barra de status com mensagem, progresso, ETA, túnel e SSH.

`WorkbenchMixin` define os métodos de layout do `App` (main.py): `_build_layout`,
`_init_pages`, `_switch_page`, `_refresh_sidebar_items` e afins. Os nomes dos
atributos usados pelo resto do código (`stacked_widget`, `lbl_status_msg`,
`sys_meter`, `lbl_hud_snaps`, `lbl_hud_eta`, `tray_*`, `thread_widgets`,
`lbl_tun_status`, `lbl_ssh_status`, `tab_<chave>`) foram mantidos.
"""
from __future__ import annotations

import os

import qtawesome as qta
from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QDockWidget, QFrame, QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QStackedWidget, QStatusBar,
    QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QMenu,
)

LAYOUT_VERSION = 3  # incrementar quando os docks mudarem (invalida layout salvo)
from ui.components.properties import (  # noqa: E402
    restructure_page, section_title, top_level_sections,
)

_SECTION_TITLES = {"configuration": "Project", "operations": "Simulation"}


def _find_owner_layout(widget):
    """Layout (em qualquer nível) que contém `widget`."""
    parent = widget.parentWidget()
    if parent is None or parent.layout() is None:
        return None
    stack = [parent.layout()]
    while stack:
        lay = stack.pop()
        for n in range(lay.count()):
            it = lay.itemAt(n)
            if it is None:
                continue
            if it.widget() is widget:
                return lay
            if it.layout() is not None:
                stack.append(it.layout())
    return None


class SectionWindow(QDockWidget):
    """Janela flutuante de parâmetros (estilo HFSS): leva a seção para fora da página
    e a devolve ao fechar."""

    def __init__(self, title, box, placeholder, owner_layout, parent):
        super().__init__(title, parent)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._box, self._placeholder, self._layout = box, placeholder, owner_layout
        wrapper = QWidget()
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(box)
        vl.addStretch(1)
        scroll = ResponsiveScrollArea()
        scroll.setWidget(wrapper)
        self.setWidget(scroll)
        box.setVisible(True)
        self._restored = False

    def restore(self):
        if self._restored:
            return
        self._restored = True
        try:
            self._layout.replaceWidget(self._placeholder, self._box)
            self._box.setParent(self._placeholder.parentWidget())
            self._box.show()
            self._placeholder.deleteLater()
        except RuntimeError:
            pass

    def closeEvent(self, ev):  # noqa: N802
        self.restore()
        super().closeEvent(ev)


class ResponsiveScrollArea(QScrollArea):
    """Área rolável que acompanha a largura do viewport (páginas de formulário)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


class WorkbenchMixin:
    # ------------------------------------------------------------------
    # Layout principal
    # ------------------------------------------------------------------
    def _build_layout(self):
        self.setDockNestingEnabled(True)
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # --- Área central: documentos (3D Scene, Results) ---
        self.doc_tabs = QTabWidget()
        self.doc_tabs.setObjectName("DocTabs")
        self.doc_tabs.setDocumentMode(True)
        self.doc_tabs.setTabsClosable(False)
        self.setCentralWidget(self.doc_tabs)

        # --- Painel Properties: formulário da página selecionada ---
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("PageStack")
        self.lbl_page_title = QLabel("General")  # legado: título mostrado no dock
        self.lbl_page_icon = QLabel()
        self.dock_properties = QDockWidget("Properties", self)
        self.dock_properties.setObjectName("DockProperties")
        props_host = QWidget()
        pl = QVBoxLayout(props_host)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        from PySide6.QtWidgets import QLineEdit
        self.prop_search = QLineEdit()
        self.prop_search.setObjectName("PropSearch")
        self.prop_search.setPlaceholderText("Search parameter…  (name, key or unit)")
        self.prop_search.setClearButtonEnabled(True)
        self.prop_search.textChanged.connect(self._on_prop_search)
        # The dock title stays "Properties" (short tab); the page context goes here.
        self.prop_crumb = QLabel("")
        self.prop_crumb.setObjectName("PropCrumb")
        self.prop_crumb.setContentsMargins(8, 4, 8, 4)
        self.prop_crumb.setStyleSheet("font-weight: 600;")
        pl.addWidget(self.prop_crumb)
        pl.addWidget(self.prop_search)
        pl.addWidget(self.stacked_widget, 1)
        self.dock_properties.setWidget(props_host)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_properties)

        self._page_widgets = {}
        self._doc_pages = {}
        self._page_sections = {}
        self._section_filter = {}
        self._section_windows = {}
        self._nav_items = {}
        self.nav_buttons = {}  # legado: mantido vazio

        self._build_toolbar()
        self._build_scenario_dock()
        self._build_bottom_docks()
        self._build_status_bar()
        self._refresh_chrome_icons()

    # ------------------------------------------------------------------
    # Barra de ferramentas
    # ------------------------------------------------------------------
    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setObjectName("MainToolBar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.TopToolBarArea, tb)
        self.main_toolbar = tb
        self._tb_actions = []  # (QAction, glifo, papel-de-cor)

        def add(text, glyph, slot, tip=None, role="icon"):
            act = QAction(text, self)
            act.setToolTip(tip or text)
            act.triggered.connect(slot)
            tb.addAction(act)
            self._tb_actions.append((act, glyph, role))
            return act

        add("Run", "mdi.play", self.run_simulation, "Run simulation (Ctrl+R)", "success").setShortcut("Ctrl+R")
        add("Run later", "mdi.calendar-clock", self.run_simulation_later, "Schedule the simulation for a later time")
        add("Stop", "mdi.stop", self.stop_simulation, "Stop running simulations", "danger")
        tb.addSeparator()
        add("Refresh preview", "mdi.refresh", self._refresh_preview, "Refresh scene preview")
        add("Parameter sweep", "mdi.table-large", self._proxy_batch_generate,
            "Generate the parameter sweep configurations without running")
        tb.addSeparator()
        add("Results", "mdi.chart-bell-curve-cumulative",
            lambda: self._switch_page("results", "Analysis & Results"), "Go to Analysis & Results")

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(spacer)
        add("Theme", "mdi.theme-light-dark", self._toggle_theme_safely, "Toggle graphite / light theme")

    # ------------------------------------------------------------------
    # Árvore do cenário (dock esquerdo)
    # ------------------------------------------------------------------
    def _build_scenario_dock(self):
        self.scenario_tree = QTreeWidget()
        self.scenario_tree.setObjectName("ScenarioTree")
        self.scenario_tree.setHeaderHidden(True)
        self.scenario_tree.setIndentation(14)
        self.scenario_tree.setIconSize(QSize(16, 16))
        self.scenario_tree.setUniformRowHeights(True)
        self.scenario_tree.itemClicked.connect(self._on_tree_clicked)
        self.scenario_tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        self.scenario_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.scenario_tree.customContextMenuRequested.connect(self._on_tree_menu)
        self.scenario_tree.currentItemChanged.connect(
            lambda cur, _prev: self._on_tree_clicked(cur, 0))

        dock = QDockWidget("Scenario", self)
        dock.setObjectName("DockScenario")
        dock.setWidget(self.scenario_tree)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
                         | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.dock_scenario = dock

    def _on_tree_double_clicked(self, item, _col):
        key, idx = item.data(0, Qt.UserRole), item.data(0, Qt.UserRole + 1)
        if key and idx is not None:
            self._open_section_window(key, idx)

    def _on_tree_menu(self, pos):
        item = self.scenario_tree.itemAt(pos)
        if item is None:
            return
        key, idx = item.data(0, Qt.UserRole), item.data(0, Qt.UserRole + 1)
        if key and idx is not None:
            menu = QMenu(self)
            menu.addAction("Open in window", lambda: self._open_section_window(key, idx))
            menu.exec(self.scenario_tree.viewport().mapToGlobal(pos))

    def _open_section_window(self, key, idx):
        """Abre os parâmetros do nó em uma janela própria (como o HFSS)."""
        boxes = self._page_sections.get(key, [])
        if idx >= len(boxes):
            return
        box = boxes[idx]
        existing = self._section_windows.get((key, idx))
        if existing is not None:
            existing.show()
            existing.raise_()
            return
        lay = _find_owner_layout(box)
        if lay is None:
            return
        placeholder = QWidget()
        lay.replaceWidget(box, placeholder)
        page_label = self._nav_items[key][0].text(0)
        title = f"{page_label} · {section_title(box)}"
        win = SectionWindow(title, box, placeholder, lay, self)
        win.setObjectName(f"SectionWindow_{key}_{idx}")
        self.addDockWidget(Qt.RightDockWidgetArea, win)
        win.setFloating(True)
        win.resize(480, 560)
        win.move(self.geometry().center().x() - 240 + 30 * len(self._section_windows),
                 self.geometry().top() + 120 + 30 * len(self._section_windows))
        win.destroyed.connect(lambda _=None, k=(key, idx): self._section_windows.pop(k, None))
        self._section_windows[(key, idx)] = win
        win.show()

    def _on_tree_clicked(self, item, _col):
        if item is None:
            return
        key = item.data(0, Qt.UserRole)
        if key:
            idx = item.data(0, Qt.UserRole + 1)
            label = item.text(0)
            if idx is not None:
                self._show_sections(key, idx, label)
            elif key != getattr(self, "current_key", None) or self._section_filter.get(key) is not None:
                self._section_filter[key] = None
                self._switch_page(key, label)
                self._show_sections(key, None, label)
            elif key in self._doc_pages:
                self.doc_tabs.setCurrentWidget(self._doc_pages[key])

    # ------------------------------------------------------------------
    # Docks inferiores: mensagens e jobs
    # ------------------------------------------------------------------
    def _build_bottom_docks(self):
        self.messages_view = QPlainTextEdit()
        self.messages_view.setObjectName("MessagesView")
        self.messages_view.setReadOnly(True)
        self.messages_view.setMaximumBlockCount(5000)
        mono = QFont("Cascadia Mono", 9)
        mono.setStyleHint(QFont.Monospace)
        self.messages_view.setFont(mono)
        from ui.shell.app_art import attach_backdrop
        attach_backdrop(self.messages_view)             # subtle Cerrado / UnB watermark

        self.dock_messages = QDockWidget("Messages", self)
        self.dock_messages.setObjectName("DockMessages")
        self.dock_messages.setWidget(self.messages_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_messages)

        # Jobs: the simulation queue (order, parallel limit, scheduled start)
        from ui.components.jobs_panel import JobsPanel
        self.jobs_panel = JobsPanel()
        # legacy HUD tray attributes still used by monitor_simulation_status(); kept off screen
        self.tray_button = QPushButton(self)
        self.tray_button.setVisible(False)
        self.tray_frame = QFrame(self)
        self.tray_frame.setVisible(False)
        self.tray_layout = QVBoxLayout(self.tray_frame)
        self.thread_widgets = {}
        jobs = self.jobs_panel
        attach_backdrop(jobs.tree)

        self.dock_jobs = QDockWidget("Jobs", self)
        self.dock_jobs.setObjectName("DockJobs")
        self.dock_jobs.setWidget(jobs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_jobs)
        self.tabifyDockWidget(self.dock_messages, self.dock_jobs)
        self.dock_messages.raise_()

    def _append_message(self, text: str):
        if hasattr(self, "messages_view") and text:
            self.messages_view.appendPlainText(text)

    # ------------------------------------------------------------------
    # Barra de status
    # ------------------------------------------------------------------
    def _build_status_bar(self):
        sb = QStatusBar()
        sb.setObjectName("WorkbenchStatusBar")
        sb.setSizeGripEnabled(True)
        self.setStatusBar(sb)
        self.status_bar = sb

        self.lbl_status_icon = QLabel()
        self.lbl_status_icon.setFixedSize(14, 14)
        sb.addWidget(self.lbl_status_icon)
        self.lbl_status_msg = QLabel("Ready.")
        self.lbl_status_msg.setObjectName("StatusMsg")
        sb.addWidget(self.lbl_status_msg, 1)

        self.lbl_scenario = QLabel("")
        self.lbl_scenario.setObjectName("StatusPill")
        sb.addPermanentWidget(self.lbl_scenario)

        self.sys_meter = QProgressBar()
        self.sys_meter.setObjectName("HUDProgress")
        self.sys_meter.setRange(0, 100)
        self.sys_meter.setValue(0)
        self.sys_meter.setFixedSize(140, 14)
        self.sys_meter.setTextVisible(True)
        sb.addPermanentWidget(self.sys_meter)
        self.lbl_hud_snaps = QLabel("SNAPS 0/0")
        self.lbl_hud_snaps.setObjectName("HUDStat")
        self.lbl_hud_eta = QLabel("ETA --:--:--")
        self.lbl_hud_eta.setObjectName("HUDStat")
        sb.addPermanentWidget(self.lbl_hud_snaps)
        sb.addPermanentWidget(self.lbl_hud_eta)

        self.lbl_tun_status = QLabel("TUNNEL · INACTIVE")
        self.lbl_tun_status.setObjectName("StatusPill")
        self.lbl_ssh_status = QLabel("SSH · DISCONNECTED")
        self.lbl_ssh_status.setObjectName("StatusPill")
        sb.addPermanentWidget(self.lbl_tun_status)
        sb.addPermanentWidget(self.lbl_ssh_status)

    # ------------------------------------------------------------------
    # Páginas
    # ------------------------------------------------------------------
    def _init_pages(self):
        """Cria cada página e a registra na árvore do cenário."""
        section_items = {}
        for key, label, Cls, icon, section in self.pages_config:
            try:
                page = Cls(self)
            except TypeError:
                page = QWidget()
                QVBoxLayout(page).addWidget(QLabel(f"Placeholder para {label}"))
            setattr(self, f"tab_{key}", page)
            if key not in ("preview", "results", "contour"):
                try:
                    restructure_page(page)
                except Exception as exc:  # a conversão nunca pode impedir a abertura
                    print(f"[workbench] restructure_page({key}) falhou: {exc}")

            if key == "preview":
                self.doc_tabs.insertTab(0, page, qta.icon(icon, color=self.tk["icon"]), "3D Scene")
                self._doc_pages[key] = page
                spec = getattr(page, "spectrum_widget", None)
                if spec is not None:
                    self.doc_tabs.insertTab(1, spec, qta.icon("mdi.chart-bell-curve", color=self.tk["icon"]),
                                            "Spectrum && Link Budget")
                self._build_legend_dock(page)
                ctl = getattr(page, "controls_panel", None)
                if ctl is not None:
                    self.dock_view = QDockWidget("View", self)
                    self.dock_view.setObjectName("DockView")
                    self.dock_view.setWidget(ctl)
                    self.addDockWidget(Qt.RightDockWidgetArea, self.dock_view)
                    self.tabifyDockWidget(self.dock_properties, self.dock_view)
                    self.dock_properties.raise_()
            elif key == "results":
                self.doc_tabs.addTab(page, qta.icon(icon, color=self.tk["icon"]), "Results")
                self._doc_pages[key] = page
            elif key == "contour":
                self.doc_tabs.addTab(page, qta.icon(icon, color=self.tk["icon"]), "Protection Contour")
                self._doc_pages[key] = page
            else:
                scroll = ResponsiveScrollArea()
                scroll.setWidget(page)
                self.stacked_widget.addWidget(scroll)
                self._page_widgets[key] = scroll

            if section not in section_items:
                top = QTreeWidgetItem(self.scenario_tree, [_SECTION_TITLES.get(section, section)])
                top.setFlags(Qt.ItemIsEnabled)
                top.setExpanded(True)
                section_items[section] = top
            item = QTreeWidgetItem(section_items[section], [label])
            item.setData(0, Qt.UserRole, key)
            self._nav_items[key] = (item, icon)
            if key in self._page_widgets and key not in ("runner", "ssh"):
                secs = top_level_sections(page)
                self._page_sections[key] = secs
                if len(secs) > 1:
                    for idx, box in enumerate(secs):
                        full = section_title(box)
                        short = full.split(" (")[0] if len(full) > 24 else full
                        child = QTreeWidgetItem(item, [short])
                        child.setToolTip(0, full)
                        child.setData(0, Qt.UserRole, key)
                        child.setData(0, Qt.UserRole + 1, idx)

        self.scenario_tree.expandAll()
        self.doc_tabs.currentChanged.connect(self._on_doc_tab_changed)
        self._resize_default_docks()
        self._default_dock_state = self.saveState(LAYOUT_VERSION)
        self._restore_workbench_layout()
        QTimer.singleShot(0, self._resize_default_docks)

    def _build_legend_dock(self, preview):
        """Detached window with the colour scales the 3D view is showing (gain lobes, heat maps)."""
        from ui.components.legend_panel import LegendPanel
        self.legend_panel = LegendPanel()
        self.dock_legend = QDockWidget("Legend", self)
        self.dock_legend.setObjectName("DockLegend")
        self.dock_legend.setWidget(self.legend_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_legend)
        self.dock_legend.setFloating(True)
        self.dock_legend.hide()
        self._legend_placed = False
        embed = getattr(preview, "_cesium_embed", None)
        if embed is not None:
            embed.bridge.legend_changed.connect(self._on_legend_changed)
            self._build_preview_panels(embed.bridge)

    def _build_preview_panels(self, bridge):
        """PSD / CDF plots (tab next to Messages and Jobs) and the link-budget window of the clicked link."""
        from ui.components.preview_panels import LinkBudgetPanel, PlotsPanel
        self.plots_panel = PlotsPanel()
        self.dock_plots = QDockWidget("Plots", self)
        self.dock_plots.setObjectName("DockPlots")
        self.dock_plots.setWidget(self.plots_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_plots)
        self.tabifyDockWidget(self.dock_messages, self.dock_plots)
        bridge.screenshot_saved.connect(self._on_screenshot_saved)
        bridge.plots_changed.connect(self.plots_panel.set_payload)
        bridge.satellite_changed.connect(self.plots_panel.set_satellite)

        self.link_panel = LinkBudgetPanel()
        self.dock_link = QDockWidget("Link budget", self)
        self.dock_link.setObjectName("DockLinkBudget")
        self.dock_link.setWidget(self.link_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_link)
        self.dock_link.setFloating(True)
        self.dock_link.hide()
        bridge.link_selected.connect(self._on_link_selected)

    def _on_screenshot_saved(self, path):
        """Tell the user where the 3D screenshot went (Messages, status bar and a clickable folder link)."""
        import os
        self._safe_log(f"[3D] Screenshot saved: {path}")
        self.statusBar().showMessage(f"Screenshot saved: {path}", 12000)
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            if not os.environ.get("SHARC_GUI_NO_RESTORE"):          # open the folder in Explorer, selecting nothing
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
        except Exception:  # noqa: BLE001 - convenience only
            pass

    def _on_link_selected(self, payload):
        self.link_panel.set_payload(payload)
        if self.link_panel.link:
            self.dock_link.show()
            self.dock_link.adjustSize()
            if not getattr(self, "_link_placed", False):
                from PySide6.QtCore import QPoint
                self._link_placed = True
                self.dock_link.move(self.doc_tabs.mapToGlobal(QPoint(70, 120)))

    def _on_legend_changed(self, payload):
        self.legend_panel.set_payload(payload)
        if not self.legend_panel.items:
            self.dock_legend.hide()
            return
        self.dock_legend.show()
        self.dock_legend.adjustSize()
        if not self._legend_placed:                         # first time: bottom-left of the 3D scene
            from PySide6.QtCore import QPoint
            self._legend_placed = True
            self.dock_legend.move(self.doc_tabs.mapToGlobal(QPoint(70, max(60, self.doc_tabs.height() - 330))))

    def _on_doc_tab_changed(self, index):
        page = self.doc_tabs.widget(index)
        # Results needs room for its controls and plot: give the width back to the
        # centre while it is open, and restore the Properties width on leaving.
        on_results = page is getattr(self, "tab_results", None)
        if on_results and not getattr(self, "_props_width_before_results", None):
            self._props_width_before_results = self.dock_properties.width()
            self.resizeDocks([self.dock_properties], [320], Qt.Horizontal)
        elif not on_results and getattr(self, "_props_width_before_results", None):
            self.resizeDocks([self.dock_properties], [self._props_width_before_results], Qt.Horizontal)
            self._props_width_before_results = None
        if page is getattr(self, "tab_preview", None):
            try:
                self.tab_preview.refresh()
            except Exception as exc:  # preview não deve derrubar a casca
                print(f"[workbench] preview refresh falhou: {exc}")

    def _resize_default_docks(self):
        self.resizeDocks([self.dock_scenario], [230], Qt.Horizontal)
        self.resizeDocks([self.dock_properties], [520], Qt.Horizontal)
        self.resizeDocks([self.dock_messages], [230], Qt.Vertical)

    def _on_prop_search(self, text):
        """Filtra as linhas de parâmetros da página atual."""
        from ui.components.properties import filter_sections
        key = getattr(self, "current_key", None)
        filter_sections(self._page_sections.get(key, []), text)

    def _show_sections(self, key, idx, label):
        """Mostra só a seção `idx` da página (None = todas), como o painel de propriedades do HFSS."""
        self._section_filter[key] = idx
        parent_item = self._nav_items.get(key, (None, None))[0]
        page_label = parent_item.text(0) if parent_item is not None else label
        for i, box in enumerate(self._page_sections.get(key, [])):
            box.setVisible(idx is None or i == idx)
        if idx is not None:
            self._switch_page(key, page_label, keep_filter=True)
            self.prop_crumb.setText(f"{page_label}  ›  {label}")

    @Slot(str, str)
    def _switch_page(self, key, label_text, keep_filter=False):
        """Documentos (3D Scene, Results) viram aba central; o resto abre em Properties."""
        self.current_key = key
        self.lbl_page_title.setText(label_text)
        if hasattr(self, "prop_search") and self.prop_search.text():
            self.prop_search.clear()
        entry = self._nav_items.get(key)
        if entry:
            item, _icon = entry
            self.scenario_tree.blockSignals(True)
            self.scenario_tree.setCurrentItem(item)
            self.scenario_tree.blockSignals(False)

        doc = self._doc_pages.get(key)
        if doc is not None:
            self.doc_tabs.setCurrentWidget(doc)
            return
        widget = self._page_widgets.get(key)
        if widget is not None:
            self.stacked_widget.setCurrentWidget(widget)
            self.prop_crumb.setText(label_text)
            self.dock_properties.show()
            self.dock_properties.raise_()

    def _refresh_sidebar_items(self):
        visible = self._get_visible_page_keys()
        for key, (item, _icon) in self._nav_items.items():
            item.setHidden(key not in visible)

    def _toggle_sidebar(self):
        self.dock_scenario.setVisible(not self.dock_scenario.isVisible())

    def _toggle_simulation_tray(self):
        self.dock_jobs.show()
        self.dock_jobs.raise_()

    # ------------------------------------------------------------------
    # Ícones, menu View e persistência do layout
    # ------------------------------------------------------------------
    def _refresh_workbench_icons(self):
        t = self.tk
        for act, glyph, role in getattr(self, "_tb_actions", []):
            act.setIcon(qta.icon(glyph, color=t.get(role, t["icon"])))
        for key, (item, icon) in getattr(self, "_nav_items", {}).items():
            item.setIcon(0, qta.icon(icon, color=t["icon"]))
        if hasattr(self, "tray_frame") and hasattr(self, "dock_jobs"):
            pass

    def _populate_view_menu(self, m_view: QMenu):
        """Adiciona ao menu View os atalhos dos docks e o reset do layout."""
        m_view.addSeparator()
        for dock in (self.dock_scenario, self.dock_properties, getattr(self, "dock_view", None),
                     self.dock_messages, self.dock_jobs):
            if dock is not None:
                m_view.addAction(dock.toggleViewAction())
        m_view.addSeparator()
        act = QAction("Reset Layout", self)
        act.triggered.connect(self._reset_workbench_layout)
        m_view.addAction(act)

    def _reset_workbench_layout(self):
        state = getattr(self, "_default_dock_state", None)
        if state:
            self.restoreState(state, LAYOUT_VERSION)
            for dock in (self.dock_scenario, self.dock_properties, getattr(self, "dock_view", None),
                         self.dock_messages, self.dock_jobs):
                if dock is not None:
                    dock.show()
            self._resize_default_docks()

    def _restore_workbench_layout(self):
        if os.environ.get("SHARC_GUI_NO_RESTORE"):
            return
        s = QSettings("SHARC", "GUI")
        geo, state = s.value("workbench/geometry"), s.value("workbench/state")
        if geo:
            self.restoreGeometry(geo)
        if state:
            self.restoreState(state, LAYOUT_VERSION)

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            s = QSettings("SHARC", "GUI")
            s.setValue("workbench/geometry", self.saveGeometry())
            s.setValue("workbench/state", self.saveState(LAYOUT_VERSION))
        tray = getattr(self, "tray", None)
        interactive = not os.environ.get("SHARC_GUI_NO_RESTORE")        # tests and screenshots never prompt
        if tray is not None and interactive and tray.available and not tray._quitting:
            choice = tray.close_choice()
            event.ignore()
            if choice == "minimize":
                tray.hide_to_tray()
            elif choice == "quit":
                tray.quit()                    # asks first when simulations would be interrupted
            return
        if tray is not None and tray.should_hide():
            # Simulations are still running: keep SHARC alive in the system tray.
            event.ignore()
            tray.hide_to_tray()
            return
        super().closeEvent(event)

