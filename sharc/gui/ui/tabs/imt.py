import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QMenu, QScrollArea, QMessageBox, QFileDialog, QFrame
)
from PySide6.QtCore import Qt

from ui.tabs.assets.imt_tab.imt_state import IMTStateManager
from ui.tabs.assets.imt_tab.imt_sections import IMTSections
from ui.tabs.assets.imt_tab.imt_topology import IMTTopologySection

class IMTTab(QWidget):
    """
    Main controller for the IMT Configuration Tab in PySide6.
    """

    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app
        
        # O IMTStateManager usa QObject e SharcVar agora
        self.state = IMTStateManager()
        self.topo_section = None

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Toolbar Superior
        toolbar_layout = QHBoxLayout()
        self.btn_files = QPushButton("📁 File Operations (Presets)")
        self.btn_files.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 6px;")
        
        self.menu_files = QMenu(self)
        self.menu_files.addAction("💾 Save IMT Preset (.json)", self.save_config)
        self.menu_files.addAction("📂 Load IMT Preset (.json)", self.load_config)
        self.btn_files.setMenu(self.menu_files)
        
        toolbar_layout.addWidget(self.btn_files)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # 2. Área de Rolagem Vertical Nativa
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.inner_widget = QWidget()
        self.inner_layout = QVBoxLayout(self.inner_widget)

        # 3. Construção das Seções na Área Interna
        IMTSections.build_general(self.inner_layout, self.state)
        self.topo_section = IMTTopologySection(self.inner_layout, self.state)
        IMTSections.build_bs(self.inner_layout, self.state)
        IMTSections.build_ue(self.inner_layout, self.state)
        IMTSections.build_channel(self.inner_layout, self.state)

        self.inner_layout.addStretch()
        self.scroll_area.setWidget(self.inner_widget)
        main_layout.addWidget(self.scroll_area)

    def save_config(self):
        data = {"config_type": "IMT"}

        # Coleta das variáveis
        if hasattr(self.state, 'vars'):
            for key, var in self.state.vars.items():
                try:
                    data[key] = var.get()
                except Exception:
                    pass

        if self.topo_section:
            data["countries_text"] = self.topo_section.get_countries_text()
            data["mss_dc_text"] = self.topo_section.get_mss_dc_text()

        fpath, _ = QFileDialog.getSaveFileName(self, "Save IMT Preset", "", "JSON (*.json)")
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                QMessageBox.information(self, "Success", f"Preset saved to:\n{Path(fpath).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save preset:\n{e}")

    def load_config(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Load IMT Preset", "", "JSON (*.json)")
        if not fpath:
            return

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if hasattr(self.state, 'vars'):
                for key, value in data.items():
                    if key in self.state.vars:
                        self.state.vars[key].set(value)

            if self.topo_section:
                self.topo_section.toggle_visibility()
                self.topo_section._toggle_raster_state()
                if "countries_text" in data:
                    self.topo_section.set_countries_text(data["countries_text"])
                elif "countries" in data:
                    self.topo_section.set_countries_text(data["countries"])

            QMessageBox.information(self, "Success", "Configuration loaded successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset:\n{e}")