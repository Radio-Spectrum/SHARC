"""
Small UI helpers and lightweight widget builders.
These are convenience functions to keep tab modules concise.
"""

import os
import sys
import ast
from tkinter import ttk, messagebox
import tkinter as tk
import traceback
from typing import Iterable, Tuple
import yaml


def _report_callback_exception(self, exc, val):
        # Mostra um diálogo e NÃO fecha o programa
    msg = ''.join(traceback.format_exception(exc, val))
    messagebox.showerror(
        "Erro inesperado",
        "Ocorreu um erro, mas o programa continuará aberto.\n\n"
        f"{val}\n\nDetalhes:\n{msg[:4000]}"  # evita caixa gigante
    )


def add_row_three(parent: tk.Widget, row: int, items: Iterable[Tuple[str, tk.Widget]]) -> None:
    """
    Place up to three (label, widget) pairs in a single grid row.
    Each pair occupies two columns: label at col, widget at col+1.
    Ensures minimum layout columns for stability.
    """
    col = 0
    for (label_text, widget) in items:
        lbl = ttk.Label(parent, text=label_text)
        lbl.grid(row=row, column=col, sticky="e", padx=(0, 6), pady=2)
        widget.grid(row=row, column=col + 1, sticky="we", pady=2)
        parent.grid_columnconfigure(col + 1, weight=1)
        col += 2

    # Ensure at least 6 columns (three pairs) are configured to avoid layout shift.
    while col < 6:
        parent.grid_columnconfigure(col, weight=1)
        col += 1


def paired_entry(parent: tk.Widget, var_left: tk.StringVar, var_right: tk.StringVar, width: int = 8) -> ttk.Frame:
    """
    Create a small frame containing two side-by-side Entry widgets separated by a '/' label.
    Returns the frame (so it can be placed with grid/pack).
    """
    frm = ttk.Frame(parent)
    left = ttk.Entry(frm, textvariable=var_left, width=width)
    sep = ttk.Label(frm, text="/")
    right = ttk.Entry(frm, textvariable=var_right, width=width)
    left.pack(side="left")
    sep.pack(side="left", padx=2)
    right.pack(side="left")
    return frm

# Get the absolute path to the directory containing this file (utils.py)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Join this directory path with the YAML filename
# (Update 'plot_info.yaml' if your file is named 'plot_config.yaml')
YAML_PATH = os.path.join(SCRIPT_DIR, 'plot_info.yaml') 


def _load_plot_info():
    """
    Loads plot information from the YAML file in the same directory.
    """
    try:
        # Use the new, robust YAML_PATH
        with open(YAML_PATH, 'r') as file:
            data = yaml.safe_load(file)
            if data is None:
                return {} 
            return data
    except FileNotFoundError:
        # This error message will now show the full, correct path
        print(f"Error: The file '{YAML_PATH}' was not found.", file=sys.stderr)
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{YAML_PATH}': {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return None


def _var_add(self):
    def _ok():
        name = e_name.get().strip()
        vals = e_vals.get().strip()
        if not name: 
            messagebox.showwarning("Variáveis", "Informe um nome.")
            return
        if not vals:
            messagebox.showwarning("Variáveis", "Informe valores em lista, ex: [1,2] ou [\"LOW\",\"HIGH\"].")
            return
        try:
            lst = ast.literal_eval(vals)
            if not isinstance(lst, (list, tuple)):
                raise ValueError()
        except Exception:
            messagebox.showwarning("Variáveis", "Valores devem ser uma lista Python válida.")
            return
        self.var_table.insert("", "end", values=(name, vals))
        dlg.destroy()

    dlg = tk.Toplevel(self); dlg.title("Adicionar variável")
    ttk.Label(dlg, text="Nome da variável (use {nome} no prefix/YAML):").pack(anchor="w", padx=10, pady=(10,2))
    e_name = ttk.Entry(dlg); e_name.pack(fill="x", padx=10)
    ttk.Label(dlg, text="Valores (lista):").pack(anchor="w", padx=10, pady=(10,2))
    e_vals = ttk.Entry(dlg); e_vals.pack(fill="x", padx=10)
    btns = ttk.Frame(dlg); btns.pack(fill="x", pady=10)
    ttk.Button(btns, text="OK", command=_ok).pack(side="left", padx=(10,4))
    ttk.Button(btns, text="Cancelar", command=dlg.destroy).pack(side="left")
    e_name.focus_set()

def _pair_entries(parent, var1, var2, w=6):
    try:
        f = ttk.Frame(parent)
        e1 = ttk.Entry(f, textvariable=var1, width=w)
        e1.pack(side="left")
        ttk.Label(f, text=" / ").pack(side="left")
        e2 = ttk.Entry(f, textvariable=var2, width=w)
        e2.pack(side="left")
        return f
    except Exception as e:
        print(f"[WARN] _pair_entries falhou ({e})")
        tmp = ttk.Frame(parent)
        ttk.Label(tmp, text="Erro em entradas").pack()
        return tmp


def _var_remove(self):
    sel = self.var_table.selection()
    for iid in sel:
        self.var_table.delete(iid)


def _add_field(self_or_parent, parent=None, row=None, label=None, widget=None, col=0, col_span=2):
    """Versão híbrida: funciona tanto como método (com self) quanto como função global."""
    # Detecta se o primeiro argumento é 'self' (classe) ou um parent direto
    if parent is None and hasattr(self_or_parent, "tk") and not hasattr(self_or_parent, "root"):
        parent = self_or_parent
        self = None
    else:
        self = self_or_parent


def _add_range(*args, **kwargs):
    try:
        self = None
        parent = None
        row = 0
        label = "?"
        wmin = None
        wmax = None
        sep_text = "a"
        if len(args) >= 1 and hasattr(args[0], "tk"):
            parent = args[0]
        elif len(args) >= 2 and hasattr(args[1], "tk"):
            parent = args[1]
        if len(args) >= 2 and isinstance(args[1], int):
            row = args[1]
        elif len(args) >= 3 and isinstance(args[2], int):
            row = args[2]
        if len(args) >= 3 and isinstance(args[2], str):
            label = args[2]
        elif len(args) >= 4 and isinstance(args[3], str):
            label = args[3]
        parent = kwargs.get("parent", parent)
        row = kwargs.get("row", row)
        label = kwargs.get("label", label)
        sep_text = kwargs.get("sep_text", sep_text)
        wmin = kwargs.get("wmin", kwargs.get("w_hmin", None))
        wmax = kwargs.get("wmax", kwargs.get("w_hmax", None))
        if not hasattr(parent, "tk"):
            print(f"[WARN] _add_range: parent inválido ({type(parent)}), criando Frame temporário.")
            try:
                parent = ttk.Frame()
            except Exception:
                try:
                    root = tk.Tk()
                    parent = ttk.Frame(root)
                    parent.grid()
                except Exception:
                    return None, None
        def ensure_widget(w, name):
            if hasattr(w, "grid"):
                return w
            print(f"[WARN] _add_range: {name} inválido ({type(w)}), criando Entry temporário.")
            try:
                return ttk.Entry(parent)
            except Exception:
                try:
                    return tk.Entry(parent)
                except Exception:
                    return None
        wmin = ensure_widget(wmin, "wmin")
        wmax = ensure_widget(wmax, "wmax")
        try:
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(6, 4), pady=2)
            if wmin: wmin.grid(row=row, column=1, sticky="we", padx=(0, 4), pady=2)
            ttk.Label(parent, text=f" {sep_text} ").grid(row=row, column=2, padx=(0, 4))
            if wmax: wmax.grid(row=row, column=3, sticky="we", padx=(0, 6), pady=2)
        except Exception as e:
            print(f"[ERROR] _add_range falhou ao desenhar '{label}': {e}")
    except Exception as e:
        print(f"[FATAL] Erro interno em _add_range: {e}")
    return wmin, wmax
