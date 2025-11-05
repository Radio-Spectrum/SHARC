"""
Small UI helpers and lightweight widget builders.
These are convenience functions to keep tab modules concise.
"""

import os
import sys
from tkinter import ttk, messagebox
import tkinter as tk
import traceback
from typing import Iterable, Tuple
import yaml

def _report_callback_exception(self, exc, val, tb):
        # Mostra um diálogo e NÃO fecha o programa
    msg = ''.join(traceback.format_exception(exc, val, tb))
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