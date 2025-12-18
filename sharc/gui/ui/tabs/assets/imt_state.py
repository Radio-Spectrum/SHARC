import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os


class IMTStateManager:
    """
    Gerencia todas as variáveis Tkinter para a aba IMT.
    Carrega padrões de um JSON e lida com Salvar/Carregar.
    """

    def __init__(self, json_filename="imt_defaults.json"):
        self.vars = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_json_path = os.path.join(base_dir, json_filename)
        print(f"Buscando config em: {self.default_json_path}")
        self._load_from_defaults()

    def get(self, key):
        """Retorna a variável Tkinter correspondente à chave."""
        if key not in self.vars:
            self.vars[key] = tk.StringVar()
        return self.vars[key]

    def _load_from_defaults(self):
        """Lê o JSON e cria as variáveis com os tipos corretos."""
        if not os.path.exists(self.default_json_path):
            print(
                f"ERRO CRÍTICO: Arquivo não encontrado: {self.default_json_path}")
            return

        try:
            with open(self.default_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, value in data.items():
                self._create_var(key, value)
        except Exception as e:
            print(f"Erro ao ler JSON: {e}")

    def _create_var(self, key, value):
        if isinstance(value, bool):
            var = tk.BooleanVar(value=value)
        elif isinstance(value, (int, float)):
            var = tk.DoubleVar(value=value)
        else:
            var = tk.StringVar(value=str(value))
        self.vars[key] = var

    def save_to_file(self, extra_data=None):
        data = {}
        for key, var in self.vars.items():
            data[key] = var.get()

        if extra_data:
            data.update(extra_data)

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="imt_config.json"
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
            return None

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
                callback_after_load(data)

            messagebox.showinfo("Sucesso", "Configuração carregada.")
            return data

        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return None
