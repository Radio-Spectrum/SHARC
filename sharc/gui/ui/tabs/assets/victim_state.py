import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os


class VictimStateManager:
    """
    Gerencia as variáveis Tkinter para a aba Victim (Single Space Station).
    """

    def __init__(self, json_filename="victim_defaults.json"):
        self.vars = {}

        # Caminho relativo à pasta assets
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_json_path = os.path.join(base_dir, json_filename)

        self._load_from_defaults()

    def get(self, key):
        """Retorna a variável Tkinter correspondente à chave."""
        if key not in self.vars:
            self.vars[key] = tk.StringVar()
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
        if isinstance(value, bool):
            var = tk.BooleanVar(value=value)
        elif isinstance(value, (int, float)):
            var = tk.DoubleVar(value=value)
        else:
            var = tk.StringVar(value=str(value))
        self.vars[key] = var

    def save_to_file(self):
        data = {k: v.get() for k, v in self.vars.items()}

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="victim_config.json"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                messagebox.showinfo("Sucesso", f"Salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

    def load_from_file(self, callback_after_load=None):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, val in data.items():
                if key in self.vars:
                    try:
                        self.vars[key].set(val)
                    except:
                        pass

            if callback_after_load:
                callback_after_load()

            messagebox.showinfo("Sucesso", "Configuração carregada.")
        except Exception as e:
            messagebox.showerror("Erro", str(e))
