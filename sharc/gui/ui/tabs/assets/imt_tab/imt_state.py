import json
import os
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox

# Import the SharcVar from your newly refactored state.py
from core.state import SharcVar 

class IMTStateManager(QObject):
    """
    Gerencia todas as variáveis para a aba IMT usando SharcVar do PySide6.
    Carrega padrões de um JSON e lida com Salvar/Carregar.
    """
    def __init__(self, json_filename="imt_defaults.json", parent=None):
        super().__init__(parent)
        self.vars = {}
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
            print(f"ERRO CRÍTICO: Arquivo não encontrado: {self.default_json_path}")
            return
        try:
            with open(self.default_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                self._create_var(key, value)
        except Exception as e:
            print(f"Erro ao ler JSON: {e}")

    def _create_var(self, key, value):
        # A própria classe SharcVar cuida da conversão de tipos (permitindo tags como "{var}")
        self.vars[key] = SharcVar(value)

    def save_to_file(self, extra_data=None):
        data = {"config_type": "IMT"}
        for key, var in self.vars.items():
            data[key] = var.get()

        if extra_data:
            data.update(extra_data)

        path, _ = QFileDialog.getSaveFileName(
            None, "Salvar IMT Config", "imt_config.json", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                QMessageBox.information(None, "Sucesso", f"Salvo em:\n{path}")
            except Exception as e:
                QMessageBox.critical(None, "Erro", str(e))

    def load_from_file(self, callback_after_load=None):
        path, _ = QFileDialog.getOpenFileName(None, "Carregar IMT Config", "", "JSON (*.json)")
        if not path:
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, val in data.items():
                if key in self.vars:
                    self.vars[key].set(val)

            if callback_after_load:
                callback_after_load(data)

            QMessageBox.information(None, "Sucesso", "Configuração carregada.")
            return data
        except Exception as e:
            QMessageBox.critical(None, "Erro", str(e))
            return None