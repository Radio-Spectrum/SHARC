import json
import os
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox

# Import the SharcVar from your newly refactored state.py
from core.state import SharcVar

class VictimStateManager(QObject):
    """
    Gerencia as variáveis para a aba Victim (Single Space Station) usando PySide6.
    """

    def __init__(self, json_filename="victim_defaults.json", parent=None):
        super().__init__(parent)
        self.vars = {}

        # Caminho relativo à pasta assets
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_json_path = os.path.join(base_dir, json_filename)

        self._load_from_defaults()

    def get(self, key):
        """Retorna o SharcVar correspondente à chave."""
        if key not in self.vars:
            self.vars[key] = SharcVar("")
        return self.vars[key]

    def _load_from_defaults(self):
        if not os.path.exists(self.default_json_path):
            print(f"ERRO: {self.default_json_path} não encontrado.")
            return

        try:
            with open(self.default_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                self._create_var(key, value)
        except Exception as e:
            print(f"Erro ao ler JSON Victim: {e}")

    def _create_var(self, key, value):
        # A própria classe SharcVar cuida da conversão de tipos permitindo tags como "{var}"
        self.vars[key] = SharcVar(value)

    def save_to_file(self, parent_widget=None):
        data = {k: v.get() for k, v in self.vars.items()}

        path, _ = QFileDialog.getSaveFileName(
            parent_widget, "Salvar Victim Config", "victim_config.json", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                QMessageBox.information(parent_widget, "Sucesso", f"Salvo em:\n{path}")
            except Exception as e:
                QMessageBox.critical(parent_widget, "Erro", str(e))

    def load_from_file(self, callback_after_load=None, parent_widget=None):
        path, _ = QFileDialog.getOpenFileName(parent_widget, "Carregar Victim Config", "", "JSON (*.json)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, val in data.items():
                if key in self.vars:
                    self.vars[key].set(val)

            if callback_after_load:
                callback_after_load()

            QMessageBox.information(parent_widget, "Sucesso", "Configuração carregada.")
        except Exception as e:
            QMessageBox.critical(parent_widget, "Erro", str(e))