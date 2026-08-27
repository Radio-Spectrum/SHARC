from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMenu, QScrollArea, QFrame, QMessageBox
)
import qtawesome as qta

from ui.tabs.assets.ses_tab.ses_sections import (
    SESBasicSection, SESGeometrySection, SESAntennaSection, SESChannelSection
)
from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence

class SingleEarthStationTab(QWidget):
    """
    Manages the 'Single Earth Station' (SES) configuration tab in PySide6.
    """

    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app

        # Section Controllers
        self.geom_section = None
        self.ant_section = None
        self.chan_section = None

        self._build_ui()
        self._setup_sync_logic()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Top Toolbar
        toolbar_layout = QHBoxLayout()
        self.btn_files = QPushButton("File Operations (Presets)")
        self.btn_files.setIcon(qta.icon('mdi.folder-outline'))
        self.btn_files.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 6px;")

        self.menu_files = QMenu(self)
        self.menu_files.addAction(qta.icon('mdi.content-save'), "Save SES Config", self.save_config)
        self.menu_files.addAction(qta.icon('mdi.folder-open'), "Load SES Config", self.load_config)
        self.btn_files.setMenu(self.menu_files)
        
        toolbar_layout.addWidget(self.btn_files)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # 2. Scrollable Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.inner_widget = QWidget()
        self.inner_layout = QVBoxLayout(self.inner_widget)

        # 3. Content Sections
        SESBasicSection.build(self.inner_layout, self.app)
        self.geom_section = SESGeometrySection(self.inner_layout, self.app)
        self.ant_section = SESAntennaSection(self.inner_layout, self.app)
        self.chan_section = SESChannelSection(self.inner_layout, self.app)

        self.inner_layout.addStretch()
        self.scroll_area.setWidget(self.inner_widget)
        main_layout.addWidget(self.scroll_area)

        self._refresh_sections()

    def _refresh_sections(self):
        """Updates all subsections with current variable values."""
        if self.geom_section:
            self.geom_section.refresh_all()
        if self.ant_section:
            self.ant_section.refresh()
        if self.chan_section:
            self.chan_section.refresh()

    def _setup_sync_logic(self):
        """Syncs heights between main parameters and channel model variables."""
        def _sync(*args):
            # Sync Earth Station Height (Rx)
            if hasattr(self.app, 'p452_Hre') and hasattr(self.app, 'se_height'):
                self.app.p452_Hre.set(self.app.se_height.get())

            # Sync Tx Height based on Link Direction
            if hasattr(self.app, 'bs_height') and hasattr(self.app, 'ue_height') and hasattr(self.app, 'var_imt_link') and hasattr(self.app, 'p452_Hte'):
                if str(self.app.var_imt_link.get()) == "DOWNLINK":
                    self.app.p452_Hte.set(self.app.bs_height.get())
                else:
                    self.app.p452_Hte.set(self.app.ue_height.get())

        # Connect all triggers that affect P.452 heights
        if hasattr(self.app, 'se_height'):
            self.app.se_height.value_changed.connect(_sync)
        if hasattr(self.app, 'var_imt_link'):
            self.app.var_imt_link.value_changed.connect(_sync)
        if hasattr(self.app, 'bs_height'):
            self.app.bs_height.value_changed.connect(_sync)
        if hasattr(self.app, 'ue_height'):
            self.app.ue_height.value_changed.connect(_sync)
            
        _sync()

    def save_config(self):
        SESPersistence.save_to_file(self.app, parent_widget=self)

    def load_config(self):
        def on_load_complete():
            self._refresh_sections()
            if hasattr(self.app, 'se_height'):
                self.app.se_height.set(self.app.se_height.get())

        SESPersistence.load_from_file(self.app, refresh_callback=on_load_complete, parent_widget=self)