import numpy as np
import tkinter as tk
from tkinter import ttk

# Importa constantes definidas no config.py
# Se você ainda não criou o config.py, pode descomentar as linhas abaixo:
# WGS84_A = 6378137.0
# WGS84_F = 1.0 / 298.257223563
try:
    from config import WGS84_A, WGS84_F
except ImportError:
    # Fallback caso config.py não exista ou não tenha as constantes
    WGS84_A = 6378137.0
    WGS84_F = 1.0 / 298.257223563

# ============================================================================
# YAML HELPERS
# ============================================================================


def _yaml_bool(v: bool) -> str:
    """Converte booleano Python para string minúscula (padrão YAML)."""
    return "true" if v else "false"


def dump_yaml_block(d, indent=0):
    """
    Função recursiva para gerar texto YAML manualmente, 
    preservando ordem e formatação específica desejada.
    """
    lines = []
    sp = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.extend(dump_yaml_block(v, indent + 1))
            elif isinstance(v, (list, tuple)):
                lines.append(f"{sp}{k}:")
                for it in v:
                    if isinstance(it, (dict, list, tuple)):
                        lines.append(f"{sp}-")
                        lines.extend(dump_yaml_block(it, indent + 1))
                    elif isinstance(it, bool):
                        lines.append(f"{sp}- {_yaml_bool(it)}")
                    elif it is None:
                        lines.append(f"{sp}- null")
                    else:
                        lines.append(f"{sp}- {it}")
            elif isinstance(v, bool):
                lines.append(f"{sp}{k}: {_yaml_bool(v)}")
            elif v is None:
                lines.append(f"{sp}{k}: null")
            else:
                lines.append(f"{sp}{k}: {v}")
    else:
        lines.append(f"{sp}{d}")
    return lines


def build_yaml_text(root_dict: dict) -> str:
    """Constrói a string final do arquivo YAML a partir de um dicionário."""
    return "\n".join(dump_yaml_block(root_dict)) + "\n"

# ============================================================================
# GEODESY / MATH HELPERS
# ============================================================================


def lla_to_ecef(lat_deg, lon_deg, h_m, a=WGS84_A, f=WGS84_F):
    """
    Converte Latitude, Longitude, Altitude para coordenadas ECEF (X, Y, Z).
    Suporta arrays numpy ou escalares.
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    s, c = np.sin(lat), np.cos(lat)
    sl, cl = np.sin(lon), np.cos(lon)
    e2 = f * (2.0 - f)
    N = a / np.sqrt(1.0 - e2 * s * s)
    X = (N + h_m) * c * cl
    Y = (N + h_m) * c * sl
    Z = (N * (1.0 - e2) + h_m) * s
    return X, Y, Z

# ============================================================================
# UI LAYOUT HELPERS
# ============================================================================


def add_row_three(parent, r, items):
    """
    Cria uma linha de widgets organizados em pares (Label, Widget) dentro de um grid.
    Útil para formulários de 3 colunas de dados (6 colunas de grid).

    :param parent: O widget pai (ex: ttk.Frame)
    :param r: O índice da linha (row) no grid
    :param items: Lista de tuplas [("Label Texto", WidgetObject), ...]
    """
    col = 0
    for (txt, w) in items:
        # Cria o Label
        lbl = ttk.Label(parent, text=txt)
        lbl.grid(row=r, column=col, sticky="e", padx=(0, 6), pady=2)

        # Posiciona o Widget passado
        w.grid(row=r, column=col + 1, sticky="we", pady=2)

        # Configura peso da coluna do widget para expandir
        parent.grid_columnconfigure(col + 1, weight=1)
        col += 2

    # Garante que colunas vazias restantes também tenham peso, se necessário
    while col < 6:
        parent.grid_columnconfigure(col, weight=1)
        col += 1

# ============================================================================
# EXTENDED UI WIDGETS
# ============================================================================

class CollapsibleFrame(ttk.Frame):
    """
    Um frame expansível/retrátil (estilo accordion) para agrupar opções.
    Para adicionar widgets, coloque-os dentro de `self.sub_frame`.
    """
    def __init__(self, parent, text="", expanded=False, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self.show = tk.BooleanVar(value=expanded)
        self._text = text
        
        self.title_frame = ttk.Frame(self)
        self.title_frame.pack(fill="x", expand=False)
        
        # O botão alterna o estado do 'show'
        self.toggle_button = ttk.Checkbutton(
            self.title_frame, width=3, text="-" if expanded else "+", 
            command=self.toggle, variable=self.show, style="Toolbutton"
        )
        self.toggle_button.pack(side="left")
        
        self.title_label = ttk.Label(self.title_frame, text=self._text, font=("Segoe UI", 9, "bold"))
        self.title_label.pack(side="left", fill="x", expand=True, padx=5)
        
        self.sub_frame = ttk.Frame(self)
        
        if expanded:
            self.sub_frame.pack(fill="both", expand=True, pady=2, padx=5)
            
    def toggle(self):
        if self.show.get():
            self.sub_frame.pack(fill="both", expand=True, pady=2, padx=5)
            self.toggle_button.configure(text="-")
        else:
            self.sub_frame.pack_forget()
            self.toggle_button.configure(text="+")

