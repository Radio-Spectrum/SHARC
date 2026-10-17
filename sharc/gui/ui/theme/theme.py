"""Tema do SHARC GUI: tokens de cor/tipografia, ícones do QSS e folha de estilo.

Movido de main.py (F1 do GUI_REDESIGN_PLAN.md). Mesma API: THEMES, theme_tokens,
generate_theme_icon_assets, build_stylesheet, get_sharc_qss.
"""
import os
import tempfile

import qtawesome as qta
from PySide6.QtCore import QSize

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
    # Tema profissional (referência: QGIS/Altium/CST/Ansys): cinza neutro,
    # campos rebaixados (inset), um único acento azul-aço.
    "graphite": {
        "bg_app":        "#1B1D20",
        "bg_panel":      "#222529",
        "bg_card":       "#272A2F",
        "bg_input":      "#1A1C1F",
        "bg_input_focus":"#16181B",
        "bg_hover":      "#30343A",
        "bg_console":    "#141618",

        "border":        "#383C42",
        "border_strong": "#4A4F57",
        "border_soft":   "#2D3035",

        "text_primary":  "#D6D9DD",
        "text_secondary":"#A0A6AD",
        "text_muted":    "#6E747B",
        "text_faint":    "#50555B",

        "accent":        "#4F9DDE",
        "accent_strong": "#6DB2EA",
        "accent_dim":    "#2F6FA6",
        "accent_deep":   "#244F75",
        "accent_soft":   "#243447",
        "accent_text_on":"#FFFFFF",

        "success":       "#5DB36A",
        "warn":          "#D9A23B",
        "danger":        "#E0605A",

        "scrollbar":     "#3A3E44",
        "scrollbar_hover":"#4D535B",
        "selection_bg":  "#2F5E8C",
        "selection_fg":  "#FFFFFF",

        "icon":          "#9AA0A7",
        "icon_active":   "#4F9DDE",
        "icon_muted":    "#5A6068",
        "icon_on_accent":"#FFFFFF",
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



# ==========================================================
# STYLESHEET — folha única dirigida por tokens
# ==========================================================
def _build_stylesheet_base(theme: str) -> str:
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
    is_dark = theme in ("dark", "graphite")

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



# ----------------------------------------------------------
# Métricas profissionais: cantos quase retos, controles densos
# ----------------------------------------------------------
PRO_THEMES = {"graphite"}
PRO_RADIUS_MAX = 2          # px
PRO_PAD_SCALE = 0.6         # paddings/margens
PRO_MIN_HEIGHT = 22         # px (altura de controle)


def _compact_qss(qss: str) -> str:
    """Converte a folha de estilo base para a densidade/geometria profissional."""
    import re
    qss = re.sub(r"border-radius:\s*(\d+)px",
                 lambda m: f"border-radius: {min(int(m.group(1)), PRO_RADIUS_MAX)}px", qss)

    def _scale(m):
        vals = [max(1, round(int(v) * PRO_PAD_SCALE)) if int(v) else 0
                for v in re.findall(r"\d+", m.group(2))]
        return f"{m.group(1)}: " + " ".join(f"{v}px" for v in vals)

    qss = re.sub(r"(padding(?:-(?:left|right|top|bottom))?):\s*((?:\d+px\s*)+)(?=;)", _scale, qss)
    qss = re.sub(r"min-height:\s*(\d+)px",
                 lambda m: f"min-height: {min(int(m.group(1)), PRO_MIN_HEIGHT)}px", qss)
    return qss


def _workbench_qss(t: dict) -> str:
    """Estilo da casca estilo estação de trabalho (docks, toolbar, status)."""
    return f"""
    QMainWindow::separator {{
        background: {t['border']};
        width: 1px; height: 1px;
    }}
    QMainWindow::separator:hover {{ background: {t['accent']}; }}

    QToolBar#MainToolBar {{
        background: {t['bg_panel']};
        border: none;
        border-bottom: 1px solid {t['border']};
        spacing: 2px;
        padding: 2px 6px;
    }}
    QToolBar#MainToolBar QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 2px;
        padding: 3px;
    }}
    QToolBar#MainToolBar QToolButton:hover {{
        background: {t['bg_hover']};
        border-color: {t['border_strong']};
    }}
    QToolBar#MainToolBar QToolButton:pressed {{ background: {t['accent_soft']}; }}
    QToolBar::separator {{ background: {t['border']}; width: 1px; margin: 4px 6px; }}

    QDockWidget {{ color: {t['text_secondary']}; }}
    QDockWidget::title {{
        background: {t['bg_panel']};
        color: {t['text_secondary']};
        border: none;
        border-bottom: 1px solid {t['border']};
        padding: 4px 8px;
        text-align: left;
        font-weight: 600;
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        background: transparent; border: none; padding: 1px;
    }}
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background: {t['bg_hover']};
    }}
    QDockWidget > QWidget {{ border: 1px solid {t['border']}; border-top: none; }}

    QMainWindow > QTabBar {{ background: {t['bg_panel']}; }}
    QMainWindow > QTabBar::tab {{
        min-width: 72px;
        background: {t['bg_panel']};
        color: {t['text_muted']};
        padding: 4px 12px;
        border: 1px solid {t['border']};
        border-top: none;
        margin-right: 1px;
    }}
    QMainWindow > QTabBar::tab:selected {{
        color: {t['text_primary']};
        background: {t['bg_app']};
        border-bottom: 2px solid {t['accent']};
    }}

    QFrame#DocHeader {{
        background: {t['bg_panel']};
        border-bottom: 1px solid {t['border']};
    }}
    QLabel#DocTitle {{ color: {t['text_primary']}; font-weight: 600; }}

    QTreeWidget#ScenarioTree {{
        background: {t['bg_panel']};
        border: none;
        outline: none;
        show-decoration-selected: 1;
    }}
    QTreeWidget#ScenarioTree::item {{ padding: 3px 4px; border-radius: 0; }}
    QTreeWidget#ScenarioTree::item:selected {{
        background: {t['accent_soft']};
        color: {t['text_primary']};
        border-left: 2px solid {t['accent']};
    }}
    QTreeWidget#ScenarioTree::item:hover:!selected {{ background: {t['bg_hover']}; }}

    QPlainTextEdit#MessagesView {{
        background: {t['bg_console']};
        color: {t['text_secondary']};
        border: none;
        selection-background-color: {t['selection_bg']};
    }}

    QStatusBar#WorkbenchStatusBar {{
        background: {t['bg_panel']};
        border-top: 1px solid {t['border']};
        color: {t['text_secondary']};
    }}
    QStatusBar#WorkbenchStatusBar::item {{ border: none; }}
    QStatusBar#WorkbenchStatusBar QProgressBar {{
        background: {t['bg_input']};
        border: 1px solid {t['border']};
        border-radius: 2px;
        text-align: center;
        font-size: 8pt;
        color: {t['text_secondary']};
    }}
    QStatusBar#WorkbenchStatusBar QProgressBar::chunk {{ background: {t['accent']}; }}
    """


def build_stylesheet(theme: str) -> str:
    """Folha de estilo completa do tema ('dark', 'light' ou 'graphite')."""
    from ui.components.properties import properties_qss
    t = theme_tokens(theme)
    qss = _build_stylesheet_base(theme) + _workbench_qss(t) + properties_qss(t)
    return _compact_qss(qss) if theme in PRO_THEMES else qss
