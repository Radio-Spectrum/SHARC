import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMenu, QScrollArea, QMessageBox, QFileDialog, QFrame
)
import qtawesome as qta

from ui.tabs.assets.victim_tab.victim_state import VictimStateManager
from ui.tabs.assets.victim_tab.victim_sections import (
    VictimBasicSection,
    VictimP619Section,
    VictimGeometrySection,
    VictimAntennaSection
)

class VictimTab(QWidget):
    """
    Manages the 'Victim' configuration tab in PySide6.
    """

    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app
        
        self.state = VictimStateManager()
        self.ant_section = None 

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Top Toolbar
        toolbar_layout = QHBoxLayout()
        self.btn_files = QPushButton("File Operations (Presets)")
        self.btn_files.setIcon(qta.icon('mdi.folder-outline'))
        self.btn_files.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 6px;")

        self.menu_files = QMenu(self)
        self.menu_files.addAction(qta.icon('mdi.content-save'), "Save SSS Preset (.json)", self.save_config)
        self.menu_files.addAction(qta.icon('mdi.folder-open'), "Load SSS Preset (.json)", self.load_config)
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
        VictimBasicSection.build(self.inner_layout, self.state)
        VictimP619Section.build(self.inner_layout, self.state)
        VictimGeometrySection.build(self.inner_layout, self.state)

        # Antenna Section (Store ref for refresh callback)
        self.ant_section = VictimAntennaSection(self.inner_layout, self.state)

        self.inner_layout.addStretch()
        self.scroll_area.setWidget(self.inner_widget)
        main_layout.addWidget(self.scroll_area)

    def save_config(self):
        data = {"config_type": "SSS"}

        if hasattr(self.state, 'vars') and isinstance(self.state.vars, dict):
            for key, var in self.state.vars.items():
                try:
                    data[key] = var.get()
                except Exception:
                    pass

        fpath, _ = QFileDialog.getSaveFileName(
            self, "Save SSS Preset", "", "JSON (*.json)"
        )
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                QMessageBox.information(self, "Success", f"Preset saved to:\n{Path(fpath).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")

    def load_config(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Load SSS Preset", "", "JSON (*.json)"
        )
        if not fpath:
            return

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if hasattr(self.state, 'vars') and isinstance(self.state.vars, dict):
                for key, value in data.items():
                    if key in self.state.vars:
                        self.state.vars[key].set(value)

            if self.ant_section:
                self.ant_section.refresh()

            QMessageBox.information(self, "Success", "Configuration loaded successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset:\n{e}")