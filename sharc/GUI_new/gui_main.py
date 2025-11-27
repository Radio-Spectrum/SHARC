import tkinter as tk
from tkinter import ttk

from state import AppState
from tabs.tab_general import build_tab_general
from tabs.tab_imt import build_tab_imt
from tabs.tab_victim import build_tab_victim
from tabs.tab_preview import build_tab_preview

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SHARC – YAML GUI (Desktop) • IMT + Single Space Station • 3D")
        self.geometry("1180x760")
        self.minsize(1000, 700)

        # estado compartilhado (tk.Vars + métodos de YAML)
        self.state = AppState(self)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        tab_general = ttk.Frame(nb, padding=10)
        tab_imt = ttk.Frame(nb, padding=10)
        tab_victim = ttk.Frame(nb, padding=10)
        tab_preview = ttk.Frame(nb, padding=(10, 6, 10, 10))

        nb.add(tab_general, text="General")
        nb.add(tab_imt, text="IMT")
        nb.add(tab_victim, text="Single Space Station")
        nb.add(tab_preview, text="Visualização 3D & Export")

        build_tab_general(tab_general, self.state)
        build_tab_imt(tab_imt, self.state)
        build_tab_victim(tab_victim, self.state)
        build_tab_preview(tab_preview, self.state)

if __name__ == "__main__":
    App().mainloop()
