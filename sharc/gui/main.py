import sys
import os
import yaml
import queue
import subprocess
import platform
import tempfile

# O Preview (CesiumJS) importa `sharc.*`; garante a raiz do repo no sys.path
# quando a GUI é iniciada de sharc/gui/ ou por caminho de arquivo.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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
    RunnerTab, ResultsTab, SingleEarthStationTab, DatabaseTab, TerrainTab, ContourTab
)
from ui.tabs.ssh_config import SSHTunnelTab
from ui.shell.workbench import WorkbenchMixin, ResponsiveScrollArea  # noqa: F401

PROJECT_ROOT = get_sharc_root()

from ui.theme import (  # noqa: E402  (tema extraído de main.py)
    THEMES, FONT_UI, FONT_MONO, theme_tokens, generate_theme_icon_assets,
    build_stylesheet, get_sharc_qss,
)


def _eta_seconds(text: str) -> int:
    """'1 day, 2:03:04' or '2:03:04' to seconds, so ETAs compare by time and not as text."""
    days = 0
    if "day" in text:
        head, text = text.split(",", 1)
        days = int(head.split()[0])
    try:
        h, m, sec = (int(x) for x in text.strip().split(":"))
    except ValueError:
        return 0
    return max(0, ((days * 24 + h) * 60 + m) * 60 + sec)


class App(WorkbenchMixin, QMainWindow):
    """
    SHARC GUI — PySide6:
    - Gerenciamento de janelas via QStackedWidget.
    - Layouts fluidos com QVBoxLayout/QHBoxLayout.
    - Timers assíncronos com QTimer.
    - Tema e ícones dirigidos por tokens (THEMES).
    """

    def __init__(self, defer_ui_init: bool = False):
        super().__init__()

        self._current_theme = "graphite"

        self.setWindowTitle("SHARC – SHARing and Compatibility")
        from ui.shell.app_art import app_icon
        self.setWindowIcon(app_icon())

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
            ("database", "Database",         DatabaseTab,           "mdi.database",            "configuration"),
            ("terrain", "Terrain & Clutter", TerrainTab,           "mdi.terrain",             "configuration"),
            ("victim",  "Space Station",      VictimTab,             "mdi.satellite-variant",   "configuration"),
            ("station", "Earth Station",      SingleEarthStationTab, "mdi.satellite-uplink",    "configuration"),
            ("preview", "Topology Preview",   PreviewTab,            "mdi.radar",               "operations"),
            ("ssh",     "SSH Connection",     SSHTunnelTab,          "mdi.lan-connect",         "operations"),
            ("runner",  "Execution Engine",   RunnerTab,             "mdi.console-line",        "operations"),
            ("results", "Analysis & Results", ResultsTab,            "mdi.chart-bell-curve-cumulative", "operations"),
            ("contour", "Protection Contour", ContourTab,          "mdi.radar",               "operations"),
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
        return theme_tokens(getattr(self, "_current_theme", "graphite"))

    def initialize_ui(self):
        if self._ui_initialized:
            return

        # 4. Interface Construction
        self._build_layout()
        self._init_pages()
        self._build_job_scheduler()
        self._build_menubar()

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

        from core.project_service import ProjectService
        self.projects = ProjectService(self)
        QTimer.singleShot(0, self._start_projects)

        from ui.shell.preferences import apply_saved_appearance
        apply_saved_appearance(self)
        QTimer.singleShot(800, self._show_welcome_toast)
        QTimer.singleShot(1000, self._disable_strict_validation)
        QTimer.singleShot(4000, self._check_updates_on_start)

        self._ui_initialized = True

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

    def _show_welcome_toast(self):
        self.lbl_status_msg.setText("System Ready.")

    def _check_updates_on_start(self):
        from ui.shell import update_dialog
        if update_dialog.check_on_start_enabled() and not os.environ.get("SHARC_GUI_NO_RESTORE"):
            update_dialog.check_for_updates(self)

    def _disable_strict_validation(self):
        print(">> UI Ready: SHARC ready!")

    # ==========================================================
    # MENUBAR (Mac e Windows nativos)
    # ==========================================================
    def _build_menubar(self):
        menubar = self.menuBar()

        # --- File ---
        m_file = menubar.addMenu("File")

        act_new = QAction("New Project", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.new_project)
        m_file.addAction(act_new)
        act_open_proj = QAction("Open Project...", self)
        act_open_proj.setShortcut("Ctrl+O")
        act_open_proj.triggered.connect(self.open_project_dialog)
        m_file.addAction(act_open_proj)
        self.menu_recent = m_file.addMenu("Open Recent")
        self.menu_recent.aboutToShow.connect(self._fill_recent_menu)
        act_save_proj = QAction("Save Project", self)
        act_save_proj.setShortcut("Ctrl+S")
        act_save_proj.triggered.connect(self.save_project)
        m_file.addAction(act_save_proj)
        act_save_as = QAction("Save Project As...", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self.save_project_as)
        m_file.addAction(act_save_as)
        act_manager = QAction("Project Manager...", self)
        act_manager.triggered.connect(self.show_project_manager)
        m_file.addAction(act_manager)
        m_file.addSeparator()

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

        act_export_figs = QAction("Export Publication Figures", self)
        act_export_figs.setShortcut("Ctrl+Shift+E")
        act_export_figs.triggered.connect(self._export_publication_figures)
        m_file.addAction(act_export_figs)

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
        self._populate_view_menu(m_view)

        # --- Settings ---
        m_settings = menubar.addMenu("Settings")

        from ui.shell.preferences import open_preferences
        from ui.shell.tray import TrayController
        act_prefs = QAction("Preferences...", self)
        act_prefs.setShortcut("Ctrl+,")
        act_prefs.triggered.connect(lambda: open_preferences(self))
        m_settings.addAction(act_prefs)
        m_settings.addSeparator()

        m_theme = m_settings.addMenu("Theme")
        theme_group = QActionGroup(self)
        for label, key in (("Graphite (dark)", "graphite"), ("Light", "light")):
            a_t = QAction(label, self)
            a_t.setCheckable(True)
            a_t.setChecked(key == getattr(self, "_current_theme", "graphite"))
            a_t.triggered.connect(lambda checked=False, k=key: self._apply_theme(k))
            theme_group.addAction(a_t)
            m_theme.addAction(a_t)

        m_font = m_settings.addMenu("Font size")
        font_group = QActionGroup(self)
        for pt in (9, 10, 11, 12):
            a_f = QAction(f"{pt} pt", self)
            a_f.setCheckable(True)
            a_f.setChecked(pt == 10)
            a_f.triggered.connect(lambda checked=False, v=pt: __import__("ui.shell.preferences", fromlist=["x"]).PreferencesDialog._set_font_size(None, v))
            font_group.addAction(a_f)
            m_font.addAction(a_f)

        act_tray = QAction("Keep running in the system tray when closing", self)
        act_tray.setCheckable(True)
        act_tray.setChecked(TrayController.keep_running_enabled())
        act_tray.setToolTip("While simulations are running, closing the window hides SHARC in the tray "
                            "instead of stopping them.")
        act_tray.toggled.connect(TrayController.set_keep_running)
        m_settings.addAction(act_tray)
        m_settings.addSeparator()

        act_layout = QAction("Reset window layout", self)
        act_layout.triggered.connect(self._reset_workbench_layout)
        m_settings.addAction(act_layout)
        act_cache = QAction("Open map cache folder", self)
        act_cache.triggered.connect(self._open_cache_folder)
        m_settings.addAction(act_cache)
        m_settings.addSeparator()

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

        m_help.addSeparator()
        from ui.shell import update_dialog
        act_update = QAction("Check for Updates...", self)
        act_update.triggered.connect(lambda: update_dialog.check_for_updates(self, manual=True))
        m_help.addAction(act_update)

        act_auto = QAction("Check for Updates on Start", self)
        act_auto.setCheckable(True)
        act_auto.setChecked(update_dialog.check_on_start_enabled())
        act_auto.toggled.connect(update_dialog.set_check_on_start)
        m_help.addAction(act_auto)

    # ==========================================================
    # THEME ENGINE
    # ==========================================================
    def _refresh_chrome_icons(self):
        """Repinta todos os ícones do chrome (sidebar, header, HUD, status bar)
        com as cores do tema atual — nada de hex hardcoded espalhado."""
        t = self.tk

        from ui.shell.app_art import app_icon
        self.setWindowIcon(app_icon())

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

        self._refresh_workbench_icons()

        if hasattr(self, "tray_button"):
            chevron = 'mdi.chevron-up' if getattr(self, 'tray_frame', None) and self.tray_frame.isVisible() else 'mdi.chevron-down'
            self.tray_button.setIcon(qta.icon(chevron, color=t["accent"]))

    def _apply_theme(self, theme: str):
        self._current_theme = theme
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            from PySide6.QtCore import QSettings
            QSettings("SHARC", "GUI").setValue("appearance/theme", theme)
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
        base = (os.path.join(os.path.expanduser("~"), "Documents", "SHARC")
                if getattr(sys, "frozen", False) else PROJECT_ROOT)
        log_dir = os.path.join(base, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir))

    def _export_publication_figures(self):
        """Save the preview heat maps and PSD/CDF plots as 300 dpi PNG plus vector PDF/SVG."""
        import json
        from core import figure_export
        embed = getattr(getattr(self, "tab_preview", None), "_cesium_embed", None)
        raw = getattr(getattr(embed, "bridge", None), "last_scene", None)
        try:
            scene = json.loads(raw) if raw else None
        except ValueError:
            scene = None
        if not scene:
            self.statusBar().showMessage("Open the 3D preview first: there is no scene to export.", 8000)
            return
        folder = os.environ.get("SHARC_SCREENSHOT_DIR") or os.path.join(
            os.path.expanduser("~"), "Pictures", "SHARC")
        folder = os.path.join(folder, "figures")
        try:
            from core.heat_style import load_style
            paths = figure_export.export_figures(scene, folder, style=load_style())
        except Exception as exc:  # noqa: BLE001 - report, never crash the GUI
            self.statusBar().showMessage(f"Figure export failed: {exc}", 10000)
            return
        if not paths:
            self.statusBar().showMessage("The scene has no heat maps or plots to export.", 8000)
            return
        self.statusBar().showMessage(f"Saved {len(paths)} figure files in {folder}", 12000)
        if not os.environ.get("SHARC_GUI_NO_RESTORE"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # ------------------------------------------------------------ projects (.sharc)
    def _start_projects(self):
        """Once the pages exist: remember the starting values, show the project in the title, open the file given on the
        command line (a double-clicked .sharc)."""
        self.projects.snapshot_defaults()
        self._project_timer = QTimer(self)
        self._project_timer.timeout.connect(self._refresh_project_title)
        self._project_timer.start(1500)
        self._refresh_project_title()
        paths = [a for a in sys.argv[1:] if a.lower().endswith(".sharc") and os.path.isfile(a)]
        if paths and not os.environ.get("SHARC_GUI_NO_RESTORE"):
            self.open_project(paths[0])

    def _refresh_project_title(self):
        title = f"{self.projects.title()} \u2013 SHARC"
        if self.windowTitle() != title:
            self.setWindowTitle(title)

    def _fill_recent_menu(self):
        self.menu_recent.clear()
        items = self.projects.recent()
        if not items:
            self.menu_recent.addAction("(no recent projects)").setEnabled(False)
            return
        for item in items:
            act = self.menu_recent.addAction(f"{item.get('name', '')}   {item['path']}")
            act.triggered.connect(lambda _=False, p=item["path"]: self.open_project(p))

    def _confirm_discard(self) -> bool:
        """True when it is fine to leave the current project: nothing unsaved, or the user chose Save / Discard."""
        if not self.projects.is_dirty() or os.environ.get("SHARC_GUI_NO_RESTORE"):
            return True
        box = QMessageBox(QMessageBox.Question, "Unsaved changes",
                          f"Save the changes of \"{self.projects.name}\" first?",
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
        choice = box.exec()
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            return self.save_project()
        return True

    def new_project(self) -> bool:
        if not self._confirm_discard():
            return False
        self.projects.new_project()
        self._refresh_project_title()
        self._safe_log("[PROJECT] New project")
        return True

    def open_project_dialog(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(self, "Open SHARC project", self._project_folder(),
                                              "SHARC projects (*.sharc);;All files (*)")
        return bool(path) and self.open_project(path)

    def open_project(self, path: str) -> bool:
        from core.project_file import ProjectError
        if not self._confirm_discard():
            return False
        try:
            report = self.projects.open(path)
        except ProjectError as exc:
            QMessageBox.warning(self, "Open project", str(exc))
            self._safe_log(f"[PROJECT] Could not open {path}: {exc}")
            return False
        self._refresh_project_title()
        extra = f" ({len(report['skipped'])} values from a different SHARC version were skipped)" if report["skipped"] else ""
        self._safe_log(f"[PROJECT] Opened {path}{extra}")
        self.statusBar().showMessage(f"Opened {path}{extra}", 8000)
        return True

    def _project_folder(self) -> str:
        if self.projects.path:
            return os.path.dirname(self.projects.path)
        return os.path.join(os.path.expanduser("~"), "Documents", "SHARC")

    def save_project(self) -> bool:
        if not self.projects.path:
            return self.save_project_as()
        return self._save_project_to(None)

    def save_project_as(self) -> bool:
        start = os.path.join(self._project_folder(), f"{self.projects.name}.sharc")
        path, _ = QFileDialog.getSaveFileName(self, "Save SHARC project", start, "SHARC projects (*.sharc)")
        return bool(path) and self._save_project_to(path)

    def _save_project_to(self, path) -> bool:
        from core.project_file import ProjectError
        try:
            saved = self.projects.save(path)
        except (ProjectError, OSError) as exc:
            QMessageBox.warning(self, "Save project", str(exc))
            self._safe_log(f"[PROJECT] Could not save: {exc}")
            return False
        self._refresh_project_title()
        self._safe_log(f"[PROJECT] Saved {saved}")
        self.statusBar().showMessage(f"Saved {saved}", 6000)
        return True

    def show_project_manager(self):
        from ui.shell.project_dialog import ProjectDialog
        ProjectDialog(self).exec()
        self._refresh_project_title()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        tray = getattr(self, "tray", None)
        leaving = tray is None or not tray.available or tray._quitting      # minimizing to the tray is not leaving
        if leaving and not self._confirm_discard():
            event.ignore()
            return
        super().closeEvent(event)

    def _clear_runner_log(self):
        if hasattr(self, 'tab_runner') and hasattr(self.tab_runner, 'text_log'):
            self.tab_runner.text_log.clear()

    def _refresh_preview(self):
        if hasattr(self, 'tab_preview') and hasattr(self.tab_preview, '_draw_preview'):
            self.tab_preview._draw_preview()

    def _toggle_theme_safely(self):
        new_theme = "light" if getattr(self, "_current_theme", "graphite") != "light" else "graphite"
        self._apply_theme(new_theme)

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

    @staticmethod
    def _saved_parallel() -> int:
        if os.environ.get("SHARC_GUI_NO_RESTORE"):
            return 2
        from PySide6.QtCore import QSettings
        try:
            return max(1, int(QSettings("SHARC", "GUI").value("sim/parallel", 2)))
        except (TypeError, ValueError):
            return 2

    def _build_job_scheduler(self):
        """Simulation queue: starts jobs in order, limited and (optionally) at a scheduled time."""
        from core.job_scheduler import JobScheduler
        self.scheduler = JobScheduler(
            start_fn=lambda path: self.runner_manager.run_local_parallel([path], 1),
            stop_fn=lambda path: self.runner_manager.stop_simulations([path]),
            log=self._safe_log, max_parallel=self._saved_parallel(), parent=self)
        self.jobs_panel.bind(self.scheduler)
        from ui.shell.tray import TrayController
        self.tray = TrayController(self, self.scheduler, color=self.tk["accent"])

    def _open_cache_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from core import terrain_service
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(terrain_service.cache_root())))

    def run_simulation(self, start_at=None):
        """Run button: generates the configuration in the background and queues the simulation."""
        from core.run_service import start_run
        return start_run(self, start_at=start_at)

    def run_simulation_later(self):
        """Run later: ask for a start time and queue the simulation for then."""
        from ui.components.jobs_panel import ScheduleDialog
        from PySide6.QtWidgets import QDialog
        dlg = ScheduleDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.run_simulation(start_at=dlg.value())

    def stop_simulation(self):
        from core.run_service import stop_run
        stop_run(self)

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
                        self._append_message(clean)
                    if hasattr(self, 'tab_runner') and hasattr(self.tab_runner, '_append_log'):
                        self.tab_runner._append_log(clean)
                elif msg == "row":
                    if hasattr(self, 'tab_runner') and hasattr(self.tab_runner, '_update_tree_row'):
                        self.tab_runner._update_tree_row(payload)
                    if getattr(self, "scheduler", None) is not None:
                        self.scheduler.on_status(payload)
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
                    pct_str = str(val.get('pct') or '0%')
                    try:
                        clean_pct = float(pct_str.replace('%', '').strip())
                    except (ValueError, TypeError):
                        clean_pct = 0.0
                    percentages.append(clean_pct)

                    snap_str = str(val.get('snap') or '0/0')
                    if '/' in snap_str:
                        try:
                            done, total = snap_str.split('/')
                            total_done_snaps += int(done)
                            total_max_snaps += int(total)
                        except (ValueError, TypeError):
                            pass

                    eta_str = str(val.get('eta') or '')
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
            final_eta = f"ETA {max(etas, key=_eta_seconds)}" if etas else "ETA --:--:--"

            self.sys_meter.setValue(int(avg_pct))
            self.sys_meter.setFormat(f"{avg_pct:.1f}%")
            self.lbl_hud_snaps.setText(snaps_text)
            self.lbl_hud_eta.setText(final_eta)

        except Exception as e:
            print(f"HUD Update Error: {e}")



def run():
    """Start the Qt application (also called by the frozen installer launcher)."""
    # Renderização consistente entre plataformas: o estilo Fusion
    # respeita 100% do QSS (nada de widgets nativos "vazando" no tema)
    if sys.platform == "win32":
        # Own taskbar identity, so Windows shows the SHARC icon instead of the Python one.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("UnB.SHARC.GUI")
        except Exception:  # noqa: BLE001 - cosmetic only
            pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    from ui.shell.app_art import app_icon
    app.setWindowIcon(app_icon())

    # Tema profissional (graphite) por padrão — folha única, sem dependências externas
    app.setStyleSheet(build_stylesheet("graphite"))

    from ui.shell.splash import run_startup
    splash, startup = run_startup(app)
    window = App()
    window.show()
    if splash:
        splash.finish(window)
    window._safe_log(startup.summary())
    if startup.problems:
        from PySide6.QtWidgets import QMessageBox
        lines = "\n".join(f"- {c or b}" for a, b, c in startup.problems)
        fix = f"{sys.executable} -m pip install rasterio requests tqdm geopandas"
        box = QMessageBox(QMessageBox.Warning, "Start-up check",
                          f"Some features are limited:\n\n{lines}\n\nTo fix, run:\n{fix}", window)
        box.setModal(False)
        box.show()
        window._startup_box = box
    sys.exit(app.exec())

if __name__ == "__main__":
    run()
