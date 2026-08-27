import sys
import os
import yaml
import queue
import subprocess
import platform
import tempfile

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QStackedWidget,
    QMenuBar, QMenu, QProgressBar, QMessageBox, QFileDialog, QSizePolicy,
    QInputDialog, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, Slot, Signal, QUrl, QSize
from PySide6.QtGui import QFont, QAction, QClipboard, QCursor, QDesktopServices, QActionGroup, QColor
import qtawesome as qta

# --- Local and Core Imports ---
from utils import build_yaml_text
from managers import RunnerManager
from core.state import AppState, get_sharc_root
from core.yaml_builder import build_yaml_structure
from managers import ssh_runner

# Import Tabs
from ui.tabs import (
    GeneralTab, IMTTab, VictimTab, PreviewTab,
    RunnerTab, ResultsTab, SingleEarthStationTab
)
from ui.tabs.ssh_config import SSHTunnelTab

PROJECT_ROOT = get_sharc_root()

# ==========================================================
# DESIGN SYSTEM — palette tokens
# ==========================================================
# Uma única fonte de verdade para cores. O QSS e todos os
# ícones (qtawesome) derivam daqui, então nada "destoa":
# input, card, painel e fundo formam uma escala tonal coerente.
#
# Escala de elevação (dark):
#   bg_app  <  bg_panel  <  bg_card  <  bg_input
# O input é SEMPRE o tom mais claro do contexto — ele se lê
# como "campo" em vez de parecer um buraco recortado no fundo.
THEMES = {
    "dark": {
        # Surfaces (escala de elevação)
        "bg_app":        "#0B0E14",   # fundo geral (deep graphite)
        "bg_panel":      "#10141D",   # sidebar / header / status bar
        "bg_card":       "#141926",   # group boxes, HUD, cartões
        "bg_input":      "#1B2230",   # campos de texto (mais claro que o card)
        "bg_input_focus":"#1F2837",
        "bg_hover":      "#1A202E",
        "bg_console":    "#0D1017",   # logs / terminal (única superfície "funda")

        # Strokes
        "border":        "#242C3D",
        "border_strong": "#313C52",
        "border_soft":   "#1B212E",

        # Text
        "text_primary":  "#E8ECF4",
        "text_secondary":"#9AA4B8",
        "text_muted":    "#5D6778",
        "text_faint":    "#454E60",

        # Accent (ciano de instrumentação, calibrado — não neon)
        "accent":        "#3AC8E8",
        "accent_strong": "#6FDCF5",
        "accent_dim":    "#1E8FAC",
        "accent_deep":   "#136477",
        "accent_soft":   "#12283A",   # fundo de seleção / item ativo
        "accent_text_on":"#03181E",   # texto sobre o accent

        # Semantics
        "success":       "#3DDC97",
        "warn":          "#F5B841",
        "danger":        "#F16A6A",

        # Chrome
        "scrollbar":     "#2B3446",
        "scrollbar_hover":"#3A4763",
        "selection_bg":  "#1E5A6E",
        "selection_fg":  "#EAFBFF",

        # Icons
        "icon":          "#8E99AF",
        "icon_active":   "#3AC8E8",
        "icon_muted":    "#4A5568",
        "icon_on_accent":"#03181E",
    },
    "light": {
        "bg_app":        "#EDF0F4",
        "bg_panel":      "#F8FAFC",
        "bg_card":       "#FFFFFF",
        "bg_input":      "#F2F5F9",   # levemente rebaixado dentro do card branco
        "bg_input_focus":"#FFFFFF",
        "bg_hover":      "#E8EDF3",
        "bg_console":    "#101520",   # console continua escuro (leitura de log)

        "border":        "#D5DCE6",
        "border_strong": "#B9C3D2",
        "border_soft":   "#E3E8EF",

        "text_primary":  "#171E2B",
        "text_secondary":"#525E72",
        "text_muted":    "#8A94A6",
        "text_faint":    "#B4BCC9",

        "accent":        "#0E6E9E",
        "accent_strong": "#1287C0",
        "accent_dim":    "#0A5679",
        "accent_deep":   "#083F59",
        "accent_soft":   "#DDEDF6",
        "accent_text_on":"#FFFFFF",

        "success":       "#188A5E",
        "warn":          "#B07C14",
        "danger":        "#C24545",

        "scrollbar":     "#C4CCD8",
        "scrollbar_hover":"#9FABBD",
        "selection_bg":  "#BFE0F0",
        "selection_fg":  "#0B2B3C",

        "icon":          "#5F6B80",
        "icon_active":   "#0E6E9E",
        "icon_muted":    "#A6AFBF",
        "icon_on_accent":"#FFFFFF",
    },
}

# Tipografia — pilha coerente por função
FONT_UI   = "'Segoe UI Variable Text', 'Segoe UI', 'Inter', 'Roboto', sans-serif"
FONT_MONO = "'Cascadia Mono', 'JetBrains Mono', 'Consolas', 'DejaVu Sans Mono', monospace"


def theme_tokens(theme: str) -> dict:
    return THEMES.get(theme, THEMES["dark"])


# ==========================================================
# ICON ASSET FACTORY
# ==========================================================
# O stylesheet do Qt precisa de arquivos de imagem reais para
# indicadores (setas de combobox, checkboxes, radios, spinbox).
# Renderizamos um set coerente a partir da MESMA família de
# glifos usada no resto da UI (Material Design Icons), com as
# cores do tema — é isso que elimina o visual "Qt genérico".
_ICON_ASSET_DIR = os.path.join(tempfile.gettempdir(), "sharc_gui_assets")


def _render_icon_asset(glyph: str, filename: str, color: str, size: int = 18) -> str:
    os.makedirs(_ICON_ASSET_DIR, exist_ok=True)
    path = os.path.join(_ICON_ASSET_DIR, filename)
    try:
        pixmap = qta.icon(glyph, color=color).pixmap(QSize(size, size))
        pixmap.save(path, "PNG")
    except Exception:
        pass
    return path.replace("\\", "/")


def generate_theme_icon_assets(theme: str) -> dict:
    """Renderiza o set de indicadores (chevrons, checks, radios, spin) para o tema."""
    t = theme_tokens(theme)
    fg     = t["icon"]
    accent = t["accent"]
    muted  = t["icon_muted"]

    return {
        "chevron_down":  _render_icon_asset("mdi.chevron-down",  f"chevron_down_{theme}.png",  fg),
        "chevron_up":    _render_icon_asset("mdi.chevron-up",    f"chevron_up_{theme}.png",    fg),
        "spin_up":       _render_icon_asset("mdi.menu-up",       f"spin_up_{theme}.png",       fg, 14),
        "spin_down":     _render_icon_asset("mdi.menu-down",     f"spin_down_{theme}.png",     fg, 14),
        "check_on":      _render_icon_asset("mdi.checkbox-marked",        f"check_on_{theme}.png",  accent, 20),
        "check_off":     _render_icon_asset("mdi.checkbox-blank-outline", f"check_off_{theme}.png", muted, 20),
        "check_dis":     _render_icon_asset("mdi.checkbox-blank-outline", f"check_dis_{theme}.png", t["text_faint"], 20),
        "radio_on":      _render_icon_asset("mdi.radiobox-marked",        f"radio_on_{theme}.png",  accent, 20),
        "radio_off":     _render_icon_asset("mdi.radiobox-blank",         f"radio_off_{theme}.png", muted, 20),
        "branch_closed": _render_icon_asset("mdi.chevron-right", f"branch_closed_{theme}.png", fg, 14),
        "branch_open":   _render_icon_asset("mdi.chevron-down",  f"branch_open_{theme}.png",   fg, 14),
    }


class ResponsiveScrollArea(QScrollArea):
    """
    QScrollArea transparente: o conteúdo das abas herda o fundo
    da aplicação em vez de pintar um retângulo destoante.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.viewport().setAutoFillBackground(False)


class App(QMainWindow):
    """
    SHARC GUI — PySide6:
    - Gerenciamento de janelas via QStackedWidget.
    - Layouts fluidos com QVBoxLayout/QHBoxLayout.
    - Timers assíncronos com QTimer.
    - Tema e ícones dirigidos por tokens (THEMES).
    """

    def __init__(self, defer_ui_init: bool = False):
        super().__init__()

        self._current_theme = "dark"

        self.setWindowTitle("SHARC – SHARing and Compatibility")
        self.setWindowIcon(qta.icon('mdi.satellite-variant',
                                    color=theme_tokens(self._current_theme)["accent"]))

        # 1. Resolution Adaptation
        screen = QApplication.primaryScreen().geometry()
        target_w = int(screen.width() * 0.85)
        target_h = int(screen.height() * 0.85)

        target_w = min(1440, max(800, target_w))
        target_h = min(900, max(600, target_h))

        self.resize(target_w, target_h)
        self.setMinimumSize(800, 600)

        # 2. Initialize State Variables
        self.state_model = AppState()

        if not self.var_system.get():
            self.var_system.set("SINGLE_EARTH_STATION")

        self.main_cli_path = self.state_model._add(os.path.join(PROJECT_ROOT, "sharc_cli.py"))

        # 3. Backend and Queues
        self.line_q = queue.Queue()
        self.runner_manager = RunnerManager(
            log_callback=self._safe_log,
            update_row_callback=self._safe_update_row
        )

        # Page Control
        self.current_key = None
        self.nav_buttons = {}

        # (key, label, class, icon, section)
        self.pages_config = [
            ("general", "General Settings",   GeneralTab,            "mdi.tune-variant",        "configuration"),
            ("imt",     "IMT System",         IMTTab,                "mdi.access-point-network","configuration"),
            ("victim",  "Space Station",      VictimTab,             "mdi.satellite-variant",   "configuration"),
            ("station", "Earth Station",      SingleEarthStationTab, "mdi.satellite-uplink",    "configuration"),
            ("preview", "Topology Preview",   PreviewTab,            "mdi.radar",               "operations"),
            ("ssh",     "SSH Connection",     SSHTunnelTab,          "mdi.lan-connect",         "operations"),
            ("runner",  "Execution Engine",   RunnerTab,             "mdi.console-line",        "operations"),
            ("results", "Analysis & Results", ResultsTab,            "mdi.chart-bell-curve-cumulative", "operations"),
        ]
        self._section_titles = {
            "configuration": "CONFIGURATION",
            "operations":    "OPERATIONS",
        }

        # UX flags
        self._sidebar_visible = True

        self._ui_initialized = False
        if not defer_ui_init:
            self.initialize_ui()

    def __getattr__(self, name):
        state = self.__dict__.get("state_model")
        if state is not None and hasattr(state, name):
            return getattr(state, name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    @property
    def tk(self) -> dict:
        return theme_tokens(getattr(self, "_current_theme", "dark"))

    def initialize_ui(self):
        if self._ui_initialized:
            return

        # 4. Interface Construction
        self._build_layout()
        self._build_menubar()
        self._init_pages()

        # 5. Timers
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._drain_log_queue)
        self.log_timer.start(100)

        self.hud_timer = QTimer(self)
        self.hud_timer.timeout.connect(self.monitor_simulation_status)
        self.hud_timer.start(5000)

        # Callbacks
        self.var_system.value_changed.connect(self._on_system_changed)

        self._refresh_sidebar_items()
        self._switch_page("general", "General Settings")

        QTimer.singleShot(800, self._show_welcome_toast)
        QTimer.singleShot(1000, self._disable_strict_validation)

        self._ui_initialized = True

    # ==========================================================
    # LAYOUT PRINCIPAL
    # ==========================================================
    def _build_layout(self):
        central_widget = QWidget()
        central_widget.setObjectName("AppRoot")
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- A. Sidebar (Left) ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(248)
        self.sidebar.setObjectName("Sidebar")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(14, 18, 14, 16)
        self.sidebar_layout.setSpacing(0)

        self._build_sidebar_header()

        # Container de navegação (com labels de seção)
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(2)
        self.sidebar_layout.addLayout(self.nav_layout)
        self.sidebar_layout.addStretch()

        self._build_system_monitor()
        self._build_sidebar_footer()

        # --- Área Direita (Content + Header + Footer) ---
        right_container = QWidget()
        right_container.setObjectName("ContentColumn")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # B. Header Bar
        self.header = QFrame()
        self.header.setFixedHeight(64)
        self.header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(24, 0, 20, 0)
        header_layout.setSpacing(14)

        # Bloco de título: eyebrow + título do módulo
        title_col = QWidget()
        title_col_layout = QVBoxLayout(title_col)
        title_col_layout.setContentsMargins(0, 0, 0, 0)
        title_col_layout.setSpacing(1)

        self.lbl_page_eyebrow = QLabel("ACTIVE MODULE")
        self.lbl_page_eyebrow.setObjectName("PageEyebrow")

        self.lbl_page_title = QLabel("DASHBOARD")
        self.lbl_page_title.setObjectName("PageTitle")

        title_col_layout.addWidget(self.lbl_page_eyebrow)
        title_col_layout.addWidget(self.lbl_page_title)
        header_layout.addWidget(title_col)

        header_layout.addStretch()

        # Chip de status do sistema (dot + label)
        self.status_chip = QFrame()
        self.status_chip.setObjectName("StatusChip")
        chip_layout = QHBoxLayout(self.status_chip)
        chip_layout.setContentsMargins(10, 4, 12, 4)
        chip_layout.setSpacing(7)

        self.lbl_header_status_dot = QLabel()
        self.lbl_header_status_dot.setObjectName("StatusDot")
        self.lbl_header_status_dot.setFixedSize(10, 10)
        chip_layout.addWidget(self.lbl_header_status_dot)

        self.lbl_header_status_text = QLabel("NOMINAL")
        self.lbl_header_status_text.setObjectName("StatusChipText")
        chip_layout.addWidget(self.lbl_header_status_text)
        header_layout.addWidget(self.status_chip)

        self.btn_theme_toggle = QPushButton()
        self.btn_theme_toggle.setObjectName("IconButton")
        self.btn_theme_toggle.setIconSize(QSize(19, 19))
        self.btn_theme_toggle.setFixedSize(36, 36)
        self.btn_theme_toggle.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_theme_toggle.setToolTip("Toggle Light / Dark Theme")
        self.btn_theme_toggle.clicked.connect(self._toggle_theme_safely)
        header_layout.addWidget(self.btn_theme_toggle)

        self.btn_gen_main = QPushButton("  Actions")
        self.btn_gen_main.setIconSize(QSize(18, 18))
        self.btn_gen_main.setObjectName("ActionBtn")
        self.btn_gen_main.setCursor(QCursor(Qt.PointingHandCursor))
        gen_menu = QMenu(self)
        self._act_batch_menu = gen_menu.addAction("Batch Generate (from Table)", self._proxy_batch_generate)
        gen_menu.addSeparator()
        self._act_save_menu = gen_menu.addAction("Save Current State (Snapshot)", self.save_yaml_dialog_multicombos)
        self.btn_gen_main.setMenu(gen_menu)
        header_layout.addWidget(self.btn_gen_main)

        self.header_accent_strip = QFrame()
        self.header_accent_strip.setObjectName("HeaderAccentStrip")
        self.header_accent_strip.setFixedHeight(2)

        # C. Content Area (QStackedWidget)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("PageStack")

        # D. Status Bar (telemetria)
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(28)
        self.status_bar.setObjectName("StatusBar")
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(14, 0, 14, 0)
        status_layout.setSpacing(10)

        self.lbl_status_icon = QLabel()
        self.lbl_status_icon.setFixedSize(14, 14)
        status_layout.addWidget(self.lbl_status_icon)

        self.lbl_status_msg = QLabel("Ready.")
        self.lbl_status_msg.setObjectName("StatusMsg")
        status_layout.addWidget(self.lbl_status_msg)
        status_layout.addStretch()

        self.lbl_tun_status = QLabel("TUNNEL · INACTIVE")
        self.lbl_tun_status.setObjectName("StatusPill")
        self.lbl_ssh_status = QLabel("SSH · DISCONNECTED")
        self.lbl_ssh_status.setObjectName("StatusPill")
        status_layout.addWidget(self.lbl_tun_status)
        status_layout.addWidget(self.lbl_ssh_status)

        # Montando a área direita
        right_layout.addWidget(self.header)
        right_layout.addWidget(self.header_accent_strip)
        right_layout.addWidget(self.stacked_widget)
        right_layout.addWidget(self.status_bar)

        # Adicionando ao layout principal
        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(right_container)

        # Pinta os ícones do chrome com as cores do tema atual
        self._refresh_chrome_icons()

    def _build_sidebar_header(self):
        brand_row = QWidget()
        brand_row_layout = QHBoxLayout(brand_row)
        brand_row_layout.setContentsMargins(4, 0, 0, 0)
        brand_row_layout.setSpacing(10)

        self.lbl_brand_icon = QLabel()
        self.lbl_brand_icon.setObjectName("BrandIcon")
        self.lbl_brand_icon.setFixedSize(34, 34)

        brand_text_col = QWidget()
        brand_text_layout = QVBoxLayout(brand_text_col)
        brand_text_layout.setContentsMargins(0, 0, 0, 0)
        brand_text_layout.setSpacing(0)

        lbl_brand = QLabel("SHARC")
        lbl_brand.setObjectName("BrandLabel")

        lbl_sub = QLabel("SHARing and Compatibility")
        lbl_sub.setObjectName("SubBrandLabel")

        brand_text_layout.addWidget(lbl_brand)
        brand_text_layout.addWidget(lbl_sub)

        brand_row_layout.addWidget(self.lbl_brand_icon)
        brand_row_layout.addWidget(brand_text_col)
        brand_row_layout.addStretch()

        self.sidebar_layout.addWidget(brand_row)

        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFixedHeight(1)
        self.sidebar_layout.addSpacing(16)
        self.sidebar_layout.addWidget(divider)
        self.sidebar_layout.addSpacing(10)

    def _make_nav_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("NavSectionLabel")
        return lbl

    def _build_system_monitor(self):
        # HUD de telemetria no rodapé da sidebar
        self.hud_frame = QFrame()
        self.hud_frame.setObjectName("SystemMonitorCard")
        hud_layout = QVBoxLayout(self.hud_frame)
        hud_layout.setContentsMargins(14, 12, 14, 12)
        hud_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(7)
        self.lbl_hud_pulse_icon = QLabel()
        self.lbl_hud_pulse_icon.setFixedSize(15, 15)
        lbl_title = QLabel("SYSTEM MONITOR")
        lbl_title.setObjectName("HUDTitle")
        title_row.addWidget(self.lbl_hud_pulse_icon)
        title_row.addWidget(lbl_title)
        title_row.addStretch()
        hud_layout.addLayout(title_row)

        self.sys_meter = QProgressBar()
        self.sys_meter.setValue(0)
        self.sys_meter.setFixedHeight(6)
        self.sys_meter.setTextVisible(False)
        self.sys_meter.setObjectName("HUDProgress")
        hud_layout.addWidget(self.sys_meter)

        stats_layout = QHBoxLayout()

        self.lbl_hud_snaps = QLabel("SNAPS 0/0")
        self.lbl_hud_snaps.setObjectName("HUDStat")

        self.lbl_hud_eta = QLabel("ETA --:--:--")
        self.lbl_hud_eta.setObjectName("HUDStat")

        stats_layout.addWidget(self.lbl_hud_snaps)
        stats_layout.addStretch()
        stats_layout.addWidget(self.lbl_hud_eta)

        hud_layout.addLayout(stats_layout)

        self.tray_button = QPushButton("  Active Threads")
        self.tray_button.setObjectName("HUDTrayButton")
        self.tray_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.tray_button.clicked.connect(self._toggle_simulation_tray)
        hud_layout.addWidget(self.tray_button)

        self.tray_frame = QFrame()
        self.tray_frame.setObjectName("HUDTrayFrame")
        self.tray_frame.setVisible(False)
        self.tray_layout = QVBoxLayout(self.tray_frame)
        self.tray_layout.setContentsMargins(0, 6, 0, 0)
        self.tray_layout.setSpacing(6)
        hud_layout.addWidget(self.tray_frame)

        self.thread_widgets = {}

        self.sidebar_layout.addWidget(self.hud_frame)

    def _build_sidebar_footer(self):
        self.sidebar_layout.addSpacing(10)
        footer = QLabel("SHARC · SHARing and Compatibility")
        footer.setObjectName("SidebarFooter")
        footer.setAlignment(Qt.AlignHCenter)
        self.sidebar_layout.addWidget(footer)

    def _init_pages(self):
        """Inicializa as abas, agrupadas por seção na sidebar."""
        current_section = None
        for key, label, Cls, icon, section in self.pages_config:

            try:
                page_instance = Cls(self)
            except TypeError:
                page_instance = QWidget()
                l = QVBoxLayout(page_instance)
                l.addWidget(QLabel(f"Placeholder para {label}"))

            setattr(self, f"tab_{key}", page_instance)

            if key not in ["results", "preview"]:
                scroll = ResponsiveScrollArea()
                scroll.setWidget(page_instance)
                self.stacked_widget.addWidget(scroll)
            else:
                self.stacked_widget.addWidget(page_instance)

            # Label de seção (eyebrow) quando muda o grupo
            if section != current_section:
                current_section = section
                if self.nav_layout.count() > 0:
                    self.nav_layout.addSpacing(10)
                self.nav_layout.addWidget(
                    self._make_nav_section_label(self._section_titles.get(section, section.upper()))
                )

            btn = QPushButton(f"  {label}")
            btn.setIcon(qta.icon(icon, color=self.tk["icon"]))
            btn.setIconSize(QSize(19, 19))
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setObjectName("NavButton")

            btn.clicked.connect(lambda checked=False, k=key, l=label: self._switch_page(k, l))

            self.nav_layout.addWidget(btn)
            self.nav_buttons[key] = btn

    @Slot(str, str)
    def _switch_page(self, key, label_text):
        """Alterna a página visível no QStackedWidget."""
        self.lbl_page_title.setText(label_text.upper())

        index = next((i for i, cfg in enumerate(self.pages_config) if cfg[0] == key), 0)
        self.stacked_widget.setCurrentIndex(index)
        self.current_key = key

        t = self.tk
        for k, btn in self.nav_buttons.items():
            icon_name = next(cfg[3] for cfg in self.pages_config if cfg[0] == k)
            if k == key:
                btn.setProperty("active", True)
                btn.setIcon(qta.icon(icon_name, color=t["icon_active"]))
            else:
                btn.setProperty("active", False)
                btn.setIcon(qta.icon(icon_name, color=t["icon"]))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _space_ui_systems(self):
        return {
            "SINGLE_SPACE_STATION",
            "HAPS",
            "MSS_SS",
            "MSS_D2D",
            "MSS_DC",
            "FSS_SS",
            "EESS_SS",
            "METSAT_SS",
            "RNS",
        }

    def _earth_ui_systems(self):
        return {
            "SINGLE_EARTH_STATION",
            "FS",
            "FSS_ES",
            "RAS",
        }

    @Slot(object)
    def _on_system_changed(self, _=None):
        self._refresh_sidebar_items()

    def _get_visible_page_keys(self):
        sys_type = self.var_system.get()
        visible = set()
        for key, label, _, _, _ in self.pages_config:
            should_show = True
            if sys_type in self._earth_ui_systems():
                if key == "victim":
                    should_show = False
                if key == "station":
                    should_show = True
            elif sys_type in self._space_ui_systems():
                if key == "station":
                    should_show = False
                if key == "victim":
                    should_show = True
            else:
                if key == "victim":
                    should_show = False
            if should_show:
                visible.add(key)
        return visible

    def _refresh_sidebar_items(self):
        visible = self._get_visible_page_keys()
        for key, btn in self.nav_buttons.items():
            btn.setVisible(key in visible)

    def _show_welcome_toast(self):
        self.lbl_status_msg.setText("System Ready.")

    def _disable_strict_validation(self):
        print(">> UI Ready: SHARC ready!")

    # ==========================================================
    # MENUBAR (Mac e Windows nativos)
    # ==========================================================
    def _build_menubar(self):
        menubar = self.menuBar()

        # --- File ---
        m_file = menubar.addMenu("File")

        act_save = QAction("Save Snapshot (Current State)...", self)
        act_save.triggered.connect(self.save_yaml_dialog_multicombos)
        m_file.addAction(act_save)

        act_batch = QAction("Batch Generate (from Table)", self)
        act_batch.triggered.connect(self._proxy_batch_generate)
        m_file.addAction(act_batch)

        m_file.addSeparator()

        act_export = QAction("Export Current YAML As...", self)
        act_export.triggered.connect(self._export_current_yaml_as)
        m_file.addAction(act_export)

        act_copy = QAction("Copy Current YAML to Clipboard", self)
        act_copy.triggered.connect(self._copy_current_yaml_to_clipboard)
        m_file.addAction(act_copy)

        m_file.addSeparator()

        act_open_yaml = QAction("Open YAML Folder", self)
        act_open_yaml.triggered.connect(self._open_yaml_folder)
        m_file.addAction(act_open_yaml)

        act_open_results = QAction("Open Results Folder", self)
        act_open_results.triggered.connect(self._open_results_folder)
        m_file.addAction(act_open_results)

        m_file.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # --- Edit ---
        m_edit = menubar.addMenu("Edit")
        act_clear_log = QAction("Clear Runner Log", self)
        act_clear_log.triggered.connect(self._clear_runner_log)
        m_edit.addAction(act_clear_log)
        m_edit.addSeparator()
        act_refresh_preview = QAction("Refresh Preview", self)
        act_refresh_preview.triggered.connect(self._refresh_preview)
        m_edit.addAction(act_refresh_preview)

        # --- View ---
        m_view = menubar.addMenu("View")
        act_toggle_theme = QAction("Toggle Theme (Light/Dark)", self)
        act_toggle_theme.triggered.connect(self._toggle_theme_safely)
        m_view.addAction(act_toggle_theme)
        m_view.addSeparator()
        act_toggle_sidebar = QAction("Toggle Sidebar", self)
        act_toggle_sidebar.triggered.connect(self._toggle_sidebar)
        m_view.addAction(act_toggle_sidebar)

        act_toggle_tray = QAction("Toggle Simulation Tray", self)
        act_toggle_tray.triggered.connect(self._toggle_simulation_tray)
        m_view.addAction(act_toggle_tray)

        # --- Settings ---
        m_settings = menubar.addMenu("Settings")

        m_res = m_settings.addMenu("Resolution")
        res_group = QActionGroup(self)
        sizes = [
            "800x600", "1024x768", "1280x720",
            "1366x768", "1440x900", "1600x900", "1920x1080"
        ]
        for s in sizes:
            act = QAction(s, self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked=False, r=s: self._apply_resolution_from_settings(r))
            res_group.addAction(act)
            m_res.addAction(act)

        m_res.addSeparator()
        act_custom_res = QAction("Custom...", self)
        act_custom_res.triggered.connect(self._open_custom_resolution_dialog)
        m_res.addAction(act_custom_res)

        # --- Help ---
        m_help = menubar.addMenu("Help")
        act_about = QAction("About SHARC", self)
        act_about.triggered.connect(self._about_dialog)
        m_help.addAction(act_about)

    # ==========================================================
    # THEME ENGINE
    # ==========================================================
    def _refresh_chrome_icons(self):
        """Repinta todos os ícones do chrome (sidebar, header, HUD, status bar)
        com as cores do tema atual — nada de hex hardcoded espalhado."""
        t = self.tk

        self.setWindowIcon(qta.icon('mdi.satellite-variant', color=t["accent"]))

        if hasattr(self, "lbl_brand_icon"):
            self.lbl_brand_icon.setPixmap(
                qta.icon('mdi.orbit-variant', color=t["accent"]).pixmap(QSize(30, 30)))

        if hasattr(self, "lbl_header_status_dot"):
            self.lbl_header_status_dot.setPixmap(
                qta.icon('mdi.circle', color=t["success"]).pixmap(QSize(9, 9)))

        if hasattr(self, "btn_theme_toggle"):
            self.btn_theme_toggle.setIcon(
                qta.icon('mdi.theme-light-dark', color=t["icon"]))

        if hasattr(self, "btn_gen_main"):
            self.btn_gen_main.setIcon(
                qta.icon('mdi.play-circle-outline', color=t["accent_text_on"]))
            menu = self.btn_gen_main.menu()
            if menu is not None:
                if hasattr(self, "_act_batch_menu"):
                    self._act_batch_menu.setIcon(qta.icon('mdi.table-large', color=t["icon"]))
                if hasattr(self, "_act_save_menu"):
                    self._act_save_menu.setIcon(qta.icon('mdi.content-save-outline', color=t["icon"]))

        if hasattr(self, "lbl_hud_pulse_icon"):
            self.lbl_hud_pulse_icon.setPixmap(
                qta.icon('mdi.pulse', color=t["accent"]).pixmap(QSize(14, 14)))

        if hasattr(self, "lbl_status_icon"):
            self.lbl_status_icon.setPixmap(
                qta.icon('mdi.information-outline', color=t["text_muted"]).pixmap(QSize(12, 12)))

        if hasattr(self, "tray_button"):
            chevron = 'mdi.chevron-up' if getattr(self, 'tray_frame', None) and self.tray_frame.isVisible() else 'mdi.chevron-down'
            self.tray_button.setIcon(qta.icon(chevron, color=t["accent"]))

    def _apply_theme(self, theme: str):
        self._current_theme = theme
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet(theme))
        self._refresh_chrome_icons()
        # Repinta ícones de navegação com estado ativo correto
        if self.current_key:
            self._switch_page(self.current_key, self.lbl_page_title.text())

    # ==========================================================
    # LÓGICAS DE SISTEMA E SLOTS
    # ==========================================================
    def _about_dialog(self):
        QMessageBox.information(
            self, "About SHARC",
            "SHARC – SHARing and Compatibility\nGUI Manager\n\n©"
        )

    # --- Menu Actions ---
    def _open_yaml_folder(self):
        path = getattr(self.state_model, 'var_yaml_dir', None)
        path = path.get() if path else ""
        if os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.getcwd()))

    def _open_results_folder(self):
        log_dir = os.path.join(PROJECT_ROOT, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir))

    def _clear_runner_log(self):
        if hasattr(self, 'tab_runner') and hasattr(self.tab_runner, 'text_log'):
            self.tab_runner.text_log.clear()

    def _refresh_preview(self):
        if hasattr(self, 'tab_preview') and hasattr(self.tab_preview, '_draw_preview'):
            self.tab_preview._draw_preview()

    def _toggle_theme_safely(self):
        new_theme = 'light' if getattr(self, '_current_theme', 'dark') == 'dark' else 'dark'
        self._apply_theme(new_theme)

    def _toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _toggle_simulation_tray(self):
        if not hasattr(self, "tray_frame"):
            return
        is_visible = self.tray_frame.isVisible()
        self.tray_frame.setVisible(not is_visible)
        chevron = 'mdi.chevron-up' if not is_visible else 'mdi.chevron-down'
        self.tray_button.setText("  Active Threads")
        self.tray_button.setIcon(qta.icon(chevron, color=self.tk["accent"]))

    def _apply_resolution_from_settings(self, res_str):
        try:
            w, h = map(int, res_str.split('x'))
            self.resize(w, h)
        except Exception:
            pass

    def _open_custom_resolution_dialog(self):
        text, ok = QInputDialog.getText(self, "Custom Resolution", "Enter resolution (e.g. 1024x768):")
        if ok and text:
            self._apply_resolution_from_settings(text)

    def _export_current_yaml_as(self):
        init_dir = os.getcwd()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Current YAML",
            os.path.join(init_dir, "snapshot.yaml"),
            "YAML Files (*.yaml);;All Files (*)"
        )
        if not path:
            return
        try:
            data = self.current_yaml_dict()
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            QMessageBox.information(self, "Success", "Exported YAML successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export YAML:\n{e}")

    def _copy_current_yaml_to_clipboard(self):
        try:
            data = self.current_yaml_dict()
            yaml_text = yaml.dump(data, default_flow_style=False, sort_keys=False)

            clipboard = QApplication.clipboard()
            clipboard.setText(yaml_text)

            QMessageBox.information(self, "Success", "YAML copied to clipboard.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy YAML:\n{e}")

    def save_yaml_dialog_multicombos(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Snapshot", "snapshot.yaml", "YAML Files (*.yaml)"
        )
        if path:
            try:
                data = build_yaml_structure(self)
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                QMessageBox.information(self, "Success", f"Snapshot saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save snapshot:\n{e}")

    def _proxy_batch_generate(self):
        if hasattr(self, 'tab_general'):
            self.tab_general.save_yaml_to_yamldir()
        else:
            QMessageBox.critical(self, "Error", "General Tab not available.")

    def current_yaml_dict(self) -> dict:
        return build_yaml_structure(self)

    # --- Worker Communication ---
    def _safe_log(self, msg):
        self.line_q.put(("log", msg))

    def _safe_update_row(self, data):
        self.line_q.put(("row", data))

    @Slot()
    def _drain_log_queue(self):
        """Conectado ao self.log_timer para rodar sem travar a UI."""
        try:
            for _ in range(50):
                if self.line_q.empty():
                    break
                item = self.line_q.get_nowait()
                msg, payload = item
                if msg == "log":
                    clean = payload.strip()
                    if clean:
                        self.lbl_status_msg.setText(clean[:120])
                    if hasattr(self, 'tab_runner') and hasattr(self.tab_runner, '_append_log'):
                        self.tab_runner._append_log(clean)
                elif msg == "row":
                    if hasattr(self, 'tab_runner') and hasattr(self.tab_runner, '_update_tree_row'):
                        self.tab_runner._update_tree_row(payload)
        except queue.Empty:
            pass

    @Slot()
    def monitor_simulation_status(self):
        """Conectado ao self.hud_timer (a cada 5s)."""
        try:
            raw_data = getattr(ssh_runner, "SIMULATION_STATUS", {})
            if not raw_data or not isinstance(raw_data, dict):
                self.sys_meter.setValue(0)
                self.sys_meter.setFormat("0%")
                if hasattr(self, "lbl_hud_snaps"):
                    self.lbl_hud_snaps.setText("SNAPS 0/0")
                if hasattr(self, "lbl_hud_eta"):
                    self.lbl_hud_eta.setText("ETA --:--:--")
                if hasattr(self, "thread_widgets"):
                    for t, w in list(self.thread_widgets.items()):
                        try:
                            w['row'].deleteLater()
                        except Exception:
                            pass
                    self.thread_widgets.clear()
                return

            percentages = []
            total_done_snaps = 0
            total_max_snaps = 0
            etas = []

            current_threads = set(raw_data.keys())
            existing_threads = set(self.thread_widgets.keys())

            for t in existing_threads - current_threads:
                self.thread_widgets[t]['row'].deleteLater()
                del self.thread_widgets[t]

            for key, val in raw_data.items():
                if isinstance(val, dict):
                    pct_str = val.get('pct', '0%')
                    try:
                        clean_pct = float(pct_str.replace('%', '').strip())
                    except (ValueError, TypeError):
                        clean_pct = 0.0
                    percentages.append(clean_pct)

                    snap_str = val.get('snap', '0/0')
                    if '/' in snap_str:
                        try:
                            done, total = snap_str.split('/')
                            total_done_snaps += int(done)
                            total_max_snaps += int(total)
                        except (ValueError, TypeError):
                            pass

                    eta_str = val.get('eta', '')
                    if eta_str and ':' in eta_str:
                        etas.append(eta_str)

                    if key not in self.thread_widgets:
                        row = QFrame()
                        row_layout = QVBoxLayout(row)
                        row_layout.setContentsMargins(0, 2, 0, 2)
                        row_layout.setSpacing(2)

                        header_frame = QFrame()
                        header_layout = QHBoxLayout(header_frame)
                        header_layout.setContentsMargins(0, 0, 0, 0)

                        short_name = str(key).split("/")[-1][:20]
                        lbl_name = QLabel(short_name)
                        lbl_name.setObjectName("HUDThreadName")
                        header_layout.addWidget(lbl_name)

                        header_layout.addStretch()

                        lbl_eta = QLabel(eta_str or "--:--")
                        lbl_eta.setObjectName("HUDThreadEta")
                        header_layout.addWidget(lbl_eta)

                        row_layout.addWidget(header_frame)

                        pb = QProgressBar()
                        pb.setValue(int(clean_pct))
                        pb.setFixedHeight(4)
                        pb.setTextVisible(False)
                        pb.setObjectName("MiniProgress")
                        row_layout.addWidget(pb)

                        self.tray_layout.addWidget(row)

                        self.thread_widgets[key] = {
                            'row': row, 'lbl_eta': lbl_eta, 'pb': pb, 'lbl_name': lbl_name
                        }
                    else:
                        w = self.thread_widgets[key]
                        w['lbl_eta'].setText(eta_str or "--:--")
                        w['pb'].setValue(int(clean_pct))

            avg_pct = sum(percentages) / len(percentages) if percentages else 0
            snaps_text = f"SNAPS {total_done_snaps}/{total_max_snaps}" if total_max_snaps > 0 else "SNAPS 0/0"
            final_eta = f"ETA {max(etas)}" if etas else "ETA --:--:--"

            self.sys_meter.setValue(int(avg_pct))
            self.sys_meter.setFormat(f"{avg_pct:.1f}%")
            self.lbl_hud_snaps.setText(snaps_text)
            self.lbl_hud_eta.setText(final_eta)

        except Exception as e:
            print(f"HUD Update Error: {e}")


# ==========================================================
# STYLESHEET — folha única dirigida por tokens
# ==========================================================
def build_stylesheet(theme: str) -> str:
    """
    Folha de estilo completa e autossuficiente (sem qdarktheme).

    Arquitetura de fundo — a correção das "caixas destoando":
      1. Todo QWidget é TRANSPARENTE por padrão e herda a superfície
         em que está apoiado. Nenhum container pinta um retângulo
         de cor errada dentro de um card.
      2. Somente janelas top-level, popups e superfícies nomeadas
         (Sidebar, HeaderBar, cards, inputs) pintam fundo.
      3. Inputs são o degrau tonal ACIMA da superfície onde vivem,
         com borda de 1px consistente — leem-se como campos,
         não como buracos.
    """
    t = theme_tokens(theme)
    icons = generate_theme_icon_assets(theme)
    is_dark = theme == "dark"

    action_grad_top    = t["accent_strong"] if is_dark else t["accent_strong"]
    action_grad_bottom = t["accent_dim"]

    return f"""
    /* ============================================================
       GLOBAL — base transparente + tipografia
       ============================================================ */
    * {{
        font-family: {FONT_UI};
        outline: none;
    }}

    QWidget {{
        color: {t['text_primary']};
        background-color: transparent;
        selection-background-color: {t['selection_bg']};
        selection-color: {t['selection_fg']};
    }}

    /* Superfícies raiz — as únicas que pintam o fundo do app */
    QMainWindow,
    QDialog,
    QMessageBox,
    QInputDialog,
    QColorDialog,
    QFontDialog,
    QFileDialog {{
        background-color: {t['bg_app']};
    }}
    QStackedWidget#PageStack {{
        background-color: {t['bg_app']};
    }}

    /* ScrollAreas transparentes: o conteúdo das abas assenta
       diretamente no fundo do app */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollArea > QWidget > QScrollBar {{
        background: transparent;
    }}
    QAbstractScrollArea::corner {{
        background: transparent;
        border: none;
    }}

    QToolTip {{
        background-color: {t['bg_card'] if is_dark else t['text_primary']};
        color: {t['text_primary'] if is_dark else '#FFFFFF'};
        border: 1px solid {t['border_strong'] if is_dark else t['accent_dim']};
        padding: 6px 10px;
        border-radius: 4px;
        font-size: 11px;
    }}

    /* ============================================================
       MENU BAR / MENUS
       ============================================================ */
    QMenuBar {{
        background-color: {t['bg_panel']};
        color: {t['text_secondary']};
        border-bottom: 1px solid {t['border_soft']};
        padding: 3px 6px;
        font-size: 12px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 5px 11px;
        border-radius: 5px;
        color: {t['text_secondary']};
    }}
    QMenuBar::item:selected {{
        background-color: {t['bg_hover']};
        color: {t['text_primary']};
    }}
    QMenuBar::item:pressed {{
        background-color: {t['accent_soft']};
        color: {t['accent']};
    }}
    QMenu {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border_strong']};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 26px 7px 12px;
        border-radius: 5px;
        font-size: 12px;
        background: transparent;
    }}
    QMenu::item:selected {{
        background-color: {t['accent_soft']};
        color: {t['accent'] if is_dark else t['accent_dim']};
    }}
    QMenu::item:disabled {{
        color: {t['text_faint']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {t['border']};
        margin: 6px 6px;
    }}
    QMenu::icon {{
        padding-left: 8px;
    }}

    /* ============================================================
       SIDEBAR
       ============================================================ */
    QFrame#Sidebar {{
        background-color: {t['bg_panel']};
        border-right: 1px solid {t['border_soft']};
    }}
    QFrame#SidebarDivider {{
        background-color: {t['border_soft']};
        border: none;
        max-height: 1px;
    }}

    QLabel#BrandLabel {{
        font-family: {FONT_MONO};
        font-size: 21px;
        font-weight: 700;
        letter-spacing: 4px;
        color: {t['text_primary']};
    }}
    QLabel#SubBrandLabel {{
        font-family: {FONT_MONO};
        font-size: 8px;
        font-weight: 600;
        letter-spacing: 2px;
        color: {t['accent_dim'] if is_dark else t['text_muted']};
    }}

    QLabel#NavSectionLabel {{
        font-family: {FONT_MONO};
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 2px;
        color: {t['text_faint']};
        padding: 6px 12px 4px 12px;
    }}

    QPushButton#NavButton {{
        text-align: left;
        padding: 10px 12px;
        font-size: 13px;
        background: transparent;
        color: {t['text_secondary']};
        border: none;
        border-left: 3px solid transparent;
        border-radius: 7px;
    }}
    QPushButton#NavButton:hover {{
        background-color: {t['bg_hover']};
        color: {t['text_primary']};
    }}
    QPushButton#NavButton[active="true"] {{
        background-color: {t['accent_soft']};
        color: {t['text_primary'] if is_dark else t['accent_deep']};
        border-left: 3px solid {t['accent']};
        border-top-left-radius: 2px;
        border-bottom-left-radius: 2px;
        font-weight: 600;
    }}

    QLabel#SidebarFooter {{
        font-family: {FONT_MONO};
        font-size: 8px;
        letter-spacing: 1.5px;
        color: {t['text_faint']};
    }}

    /* ============================================================
       SYSTEM MONITOR (HUD)
       ============================================================ */
    QFrame#SystemMonitorCard {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 10px;
    }}
    QLabel#HUDTitle {{
        font-family: {FONT_MONO};
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 2px;
        color: {t['text_secondary']};
    }}
    QLabel#HUDStat {{
        font-family: {FONT_MONO};
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
        color: {t['text_primary']};
    }}
    QLabel#HUDThreadName {{
        font-size: 10px;
        font-weight: 600;
        color: {t['text_primary']};
    }}
    QLabel#HUDThreadEta {{
        font-family: {FONT_MONO};
        font-size: 10px;
        color: {t['text_secondary']};
    }}
    QPushButton#HUDTrayButton {{
        background: transparent;
        color: {t['accent'] if is_dark else t['accent_dim']};
        font-weight: 600;
        font-size: 11px;
        border: none;
        text-align: left;
        padding: 4px 0px;
    }}
    QPushButton#HUDTrayButton:hover {{
        color: {t['accent_strong']};
    }}

    /* ============================================================
       HEADER
       ============================================================ */
    QFrame#HeaderBar {{
        background-color: {t['bg_panel']};
        border-bottom: 1px solid {t['border_soft']};
    }}
    QFrame#HeaderAccentStrip {{
        border: none;
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {t['accent']}, stop:0.35 {t['accent_dim']}, stop:1 transparent
        );
    }}
    QLabel#PageEyebrow {{
        font-family: {FONT_MONO};
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 2.5px;
        color: {t['accent_dim'] if is_dark else t['text_muted']};
    }}
    QLabel#PageTitle {{
        font-size: 17px;
        font-weight: 600;
        letter-spacing: 1.5px;
        color: {t['text_primary']};
    }}

    QFrame#StatusChip {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 12px;
    }}
    QLabel#StatusChipText {{
        font-family: {FONT_MONO};
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: {t['success']};
    }}

    QPushButton#IconButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        padding: 0px;
    }}
    QPushButton#IconButton:hover {{
        background-color: {t['bg_hover']};
        border: 1px solid {t['border']};
    }}
    QPushButton#IconButton:pressed {{
        background-color: {t['accent_soft']};
    }}

    QPushButton#ActionBtn {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {action_grad_top}, stop:1 {action_grad_bottom}
        );
        color: {t['accent_text_on']};
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 1px;
        padding: 9px 20px;
        border-radius: 7px;
        border: 1px solid {t['accent_dim']};
    }}
    QPushButton#ActionBtn:hover {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {t['accent_strong']}, stop:1 {t['accent']}
        );
    }}
    QPushButton#ActionBtn:pressed {{
        background-color: {t['accent_dim']};
    }}
    QPushButton#ActionBtn::menu-indicator {{
        image: none;
    }}

    /* ============================================================
       STATUS BAR (telemetria)
       ============================================================ */
    QFrame#StatusBar {{
        background-color: {t['bg_panel']};
        border-top: 1px solid {t['border_soft']};
    }}
    QLabel#StatusMsg {{
        font-family: {FONT_MONO};
        font-size: 10px;
        color: {t['text_secondary']};
    }}
    QLabel#StatusPill {{
        font-family: {FONT_MONO};
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 1px;
        color: {t['text_muted']};
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        padding: 2px 9px;
    }}

    /* ============================================================
       BOTÕES GENÉRICOS
       ============================================================ */
    QPushButton {{
        background-color: {t['bg_input']};
        color: {t['text_primary']};
        border: 1px solid {t['border_strong']};
        border-radius: 6px;
        padding: 7px 14px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {t['bg_hover'] if is_dark else '#FFFFFF'};
        border: 1px solid {t['accent_dim']};
    }}
    QPushButton:pressed {{
        background-color: {t['accent_soft']};
    }}
    QPushButton:disabled {{
        color: {t['text_faint']};
        background-color: {t['bg_card']};
        border: 1px solid {t['border_soft']};
    }}
    QPushButton:focus {{
        border: 1px solid {t['accent']};
    }}

    QToolButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 4px;
        color: {t['text_secondary']};
    }}
    QToolButton:hover {{
        background-color: {t['bg_hover']};
        border: 1px solid {t['border']};
    }}
    QToolButton:pressed {{
        background-color: {t['accent_soft']};
    }}

    /* ============================================================
       PROGRESS BARS
       ============================================================ */
    QProgressBar {{
        border: 1px solid {t['border']};
        background: {t['bg_app'] if is_dark else t['bg_input']};
        border-radius: 4px;
        text-align: center;
        font-family: {FONT_MONO};
        font-size: 10px;
        color: {t['text_secondary']};
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {t['accent_dim']}, stop:1 {t['accent']}
        );
        border-radius: 3px;
    }}
    QProgressBar#HUDProgress, QProgressBar#MiniProgress {{
        border: none;
        background: {t['bg_app'] if is_dark else t['border_soft']};
        border-radius: 3px;
        color: transparent;
    }}
    QProgressBar#HUDProgress::chunk, QProgressBar#MiniProgress::chunk {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {t['accent_dim']}, stop:1 {t['accent']}
        );
        border-radius: 3px;
    }}

    /* ============================================================
       INPUTS — um degrau tonal acima da superfície onde vivem
       ============================================================ */
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QDateEdit, QTimeEdit, QDateTimeEdit, QAbstractSpinBox {{
        background-color: {t['bg_input']};
        border: 1px solid {t['border_strong']};
        border-radius: 6px;
        padding: 6px 10px;
        min-height: 18px;
        color: {t['text_primary']};
        font-size: 12px;
    }}
    QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover,
    QSpinBox:hover, QDateEdit:hover, QTimeEdit:hover {{
        border: 1px solid {t['scrollbar_hover']};
        background-color: {t['bg_input_focus']};
    }}
    QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus,
    QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {{
        border: 1px solid {t['accent']};
        background-color: {t['bg_input_focus']};
    }}
    QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled,
    QSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled {{
        color: {t['text_faint']};
        background-color: {t['bg_card']};
        border: 1px solid {t['border_soft']};
    }}
    QLineEdit[readOnly="true"] {{
        background-color: {t['bg_card']};
        color: {t['text_secondary']};
    }}
    QLineEdit::placeholder {{
        color: {t['text_muted']};
    }}

    QComboBox::drop-down {{
        border: none;
        border-left: 1px solid {t['border']};
        width: 26px;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }}
    QComboBox::down-arrow {{
        image: url({icons['chevron_down']});
        width: 13px;
        height: 13px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border_strong']};
        border-radius: 8px;
        selection-background-color: {t['accent_soft']};
        selection-color: {t['accent'] if is_dark else t['accent_deep']};
        color: {t['text_primary']};
        outline: none;
        padding: 4px;
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QDateEdit::up-button, QTimeEdit::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 18px;
        border-left: 1px solid {t['border']};
        border-bottom: 1px solid {t['border']};
        border-top-right-radius: 6px;
        background-color: transparent;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button,
    QDateEdit::down-button, QTimeEdit::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 18px;
        border-left: 1px solid {t['border']};
        border-bottom-right-radius: 6px;
        background-color: transparent;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {t['bg_hover']};
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
    QDateEdit::up-arrow, QTimeEdit::up-arrow {{
        image: url({icons['spin_up']});
        width: 11px; height: 11px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow,
    QDateEdit::down-arrow, QTimeEdit::down-arrow {{
        image: url({icons['spin_down']});
        width: 11px; height: 11px;
    }}

    /* Áreas de texto / logs */
    QTextEdit, QPlainTextEdit {{
        background-color: {t['bg_input']};
        border: 1px solid {t['border_strong']};
        border-radius: 6px;
        padding: 6px;
        color: {t['text_primary']};
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {t['accent']};
    }}
    QTextEdit#ConsoleLog, QPlainTextEdit#ConsoleLog {{
        background-color: {t['bg_console']};
        color: #C6E8D8;
        font-family: {FONT_MONO};
        font-size: 11px;
        border: 1px solid {t['border']};
        border-radius: 8px;
    }}

    /* ============================================================
       CHECKBOX / RADIO
       ============================================================ */
    QCheckBox, QRadioButton {{
        color: {t['text_secondary']};
        spacing: 8px;
        padding: 2px 0px;
        background: transparent;
    }}
    QCheckBox:hover, QRadioButton:hover {{
        color: {t['text_primary']};
    }}
    QCheckBox:disabled, QRadioButton:disabled {{
        color: {t['text_faint']};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px;
        height: 18px;
    }}
    QCheckBox::indicator:unchecked {{ image: url({icons['check_off']}); }}
    QCheckBox::indicator:checked   {{ image: url({icons['check_on']}); }}
    QCheckBox::indicator:disabled  {{ image: url({icons['check_dis']}); }}
    QRadioButton::indicator:unchecked {{ image: url({icons['radio_off']}); }}
    QRadioButton::indicator:checked   {{ image: url({icons['radio_on']}); }}

    /* ============================================================
       GROUP BOX — cards de parâmetros
       ============================================================ */
    QGroupBox {{
        border: 1px solid {t['border']};
        border-radius: 10px;
        margin-top: 18px;
        padding-top: 14px;
        background-color: {t['bg_card']};
        font-weight: 600;
        font-size: 12px;
        color: {t['text_secondary']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 2px 8px;
        background-color: {t['bg_app']};
        border: 1px solid {t['border']};
        border-radius: 5px;
        font-family: {FONT_MONO};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: {t['accent'] if is_dark else t['accent_dim']};
    }}

    /* ============================================================
       TABS (QTabWidget dentro das páginas)
       ============================================================ */
    QTabWidget::pane {{
        border: 1px solid {t['border']};
        border-radius: 8px;
        background-color: {t['bg_card']};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t['text_secondary']};
        padding: 8px 16px;
        margin-right: 4px;
        border: 1px solid transparent;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        font-size: 12px;
    }}
    QTabBar::tab:hover {{
        color: {t['text_primary']};
        background-color: {t['bg_hover']};
    }}
    QTabBar::tab:selected {{
        color: {t['accent'] if is_dark else t['accent_deep']};
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-bottom: 1px solid {t['bg_card']};
        font-weight: 600;
    }}

    /* ============================================================
       TABLES / TREES / LISTS
       ============================================================ */
    QTableWidget, QTableView {{
        background-color: {t['bg_card']};
        alternate-background-color: {t['bg_panel']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        color: {t['text_primary']};
        gridline-color: {t['border_soft']};
        selection-background-color: {t['accent_soft']};
        selection-color: {t['accent'] if is_dark else t['accent_deep']};
    }}
    QHeaderView {{
        background-color: transparent;
        border: none;
    }}
    QHeaderView::section {{
        background-color: {t['bg_panel']};
        color: {t['text_secondary']};
        padding: 7px 9px;
        border: none;
        border-right: 1px solid {t['border_soft']};
        border-bottom: 1px solid {t['border']};
        font-family: {FONT_MONO};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QTableCornerButton::section {{
        background-color: {t['bg_panel']};
        border: none;
        border-bottom: 1px solid {t['border']};
        border-right: 1px solid {t['border_soft']};
    }}

    QTreeView, QTreeWidget, QListView, QListWidget {{
        background-color: {t['bg_card']};
        alternate-background-color: {t['bg_panel']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        color: {t['text_primary']};
        outline: none;
    }}
    QTreeView::item, QTreeWidget::item, QListView::item, QListWidget::item {{
        padding: 4px 2px;
        border-radius: 4px;
    }}
    QTreeView::item:hover, QTreeWidget::item:hover,
    QListView::item:hover, QListWidget::item:hover {{
        background-color: {t['bg_hover']};
    }}
    QTreeView::item:selected, QTreeWidget::item:selected,
    QListView::item:selected, QListWidget::item:selected {{
        background-color: {t['accent_soft']};
        color: {t['accent'] if is_dark else t['accent_deep']};
    }}
    QTreeView::branch:has-children:!has-siblings:closed,
    QTreeView::branch:closed:has-children:has-siblings {{
        image: url({icons['branch_closed']});
    }}
    QTreeView::branch:open:has-children:!has-siblings,
    QTreeView::branch:open:has-children:has-siblings {{
        image: url({icons['branch_open']});
    }}

    /* ============================================================
       SCROLLBARS
       ============================================================ */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['scrollbar']};
        min-height: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t['scrollbar_hover']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t['scrollbar']};
        min-width: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {t['scrollbar_hover']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

    /* ============================================================
       SLIDER / SPLITTER / MISC
       ============================================================ */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {t['border']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t['accent_dim']};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {t['accent']};
        width: 14px; height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid {t['bg_panel']};
    }}

    QSplitter::handle {{
        background-color: {t['border_soft']};
    }}
    QSplitter::handle:hover {{
        background-color: {t['accent_dim']};
    }}

    QStatusBar {{
        background-color: {t['bg_panel']};
        color: {t['text_secondary']};
        border-top: 1px solid {t['border_soft']};
    }}

    QMessageBox QLabel, QInputDialog QLabel {{
        color: {t['text_primary']};
        background: transparent;
    }}

    QLabel {{
        background: transparent;
    }}
    QLabel:disabled {{
        color: {t['text_faint']};
    }}
    """


# Alias de compatibilidade (código externo pode importar o nome antigo)
def get_sharc_qss(theme: str) -> str:
    return build_stylesheet(theme)


if __name__ == "__main__":
    # Renderização consistente entre plataformas: o estilo Fusion
    # respeita 100% do QSS (nada de widgets nativos "vazando" no tema)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    # Tema escuro por padrão — folha única, sem dependências externas
    app.setStyleSheet(build_stylesheet("dark"))

    window = App()
    window.show()
    sys.exit(app.exec())