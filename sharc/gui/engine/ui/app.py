"""
Main application class: holds shared variables and creates the notebook tabs.
Tabs are built by separate modules (tab_*.py).
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import List, Tuple

# Tab builder imports (each module exposes build_<tab>_tab(app, frame))
from ui.tab_general import build_general_tab
from ui.tab_imt import build_imt_tab
from ui.tab_victim import build_victim_tab
from ui.tab_preview import build_preview_tab
from ui.tab_runner import build_runner_tab
from ui.tab_results import build_results_tab


class App(tk.Tk):
    """Main Tk application. Keeps shared state variables here so tabs can access them."""

    def __init__(self) -> None:
        super().__init__()
        self.title("SHARC – YAML GUI (IMT & Single Space Station)")
        self.geometry("1260x900")
        self.minsize(1100, 800)

        # === General parameters ===
        self.var_seed = tk.IntVar(value=157)
        self.var_snaps = tk.IntVar(value=10000)
        self.var_overwrite = tk.BooleanVar(value=False)
        self.var_outdir = tk.StringVar(value=str(Path.cwd() / "sharc" / "campaigns"))
        self.var_yaml_dir = tk.StringVar(value=str(Path.cwd() / "sharc" / "campaigns"))
        self.var_prefix = tk.StringVar(value="output_mss_{long}")
        self.var_system = tk.StringVar(value="SINGLE_SPACE_STATION")
        self.var_imt_link = tk.StringVar(value="DOWNLINK")
        self.var_enable_adjacent = tk.BooleanVar(value=False)
        self.var_enable_cochannel = tk.BooleanVar(value=True)

        # === IMT parameters (subset) ===
        self.imt_min_sep = tk.StringVar(value="35")
        self.imt_freq = tk.StringVar(value="8150")
        self.imt_bw = tk.StringVar(value="100")

        # === Topology / countries ===
        self.topo_c_lat = tk.StringVar(value="-15.793889")
        self.topo_c_lon = tk.StringVar(value="-47.882778")
        self.topo_c_alt = tk.StringVar(value="0")
        self.topo_type = tk.StringVar(value="Macro_countries")
        self.topo_num_bs = tk.StringVar(value="100")
        self.topo_cell_radius = tk.StringVar(value="400")
        self.topo_countries = tk.StringVar(
            value="\n".join(
                [
                    "Brazil",
                    "Argentina",
                    "Uruguay",
                    "Paraguay",
                    "Chile",
                ]
            )
        )

        # === Base station (BS) ===
        self.bs_load_prob = tk.StringVar(value="0.2")
        self.bs_power = tk.StringVar(value="22")
        self.bs_height = tk.StringVar(value="18")

        # === User equipment (UE) ===
        self.ue_k = tk.StringVar(value="3")
        self.ue_km = tk.StringVar(value="1")

        # === Single Space Station (victim) ===
        self.v_freq = tk.StringVar(value="8150")
        self.v_bw = tk.StringVar(value="40")
        self.v_txpsd = tk.StringVar(value="-200")
        self.v_ant_pattern = tk.StringVar(value="ITU-R S.672")
        self.v_ant_gain = tk.StringVar(value="30")
        self.v_alt = tk.StringVar(value="35786000")
        self.v_fix_lat = tk.StringVar(value="0")
        self.v_fix_lon = tk.StringVar(value="-110")

        # === Preview settings ===
        self.var_show_gainmap = tk.BooleanVar(value=False)
        self.var_gain_vmin = tk.StringVar(value="auto")
        self.var_gain_vmax = tk.StringVar(value="auto")

        # === Runner ===
        self.var_max_workers = tk.IntVar(value=2)
        self.run_folder = tk.StringVar(value=str(Path.cwd() / "sharc" / "campaigns"))

        # === Results ===
        self.res_dirs: List[str] = []
        self.var_auto_update = tk.BooleanVar(value=True)
        self.var_update_period_ms = tk.IntVar(value=2000)
        self.var_rows = tk.IntVar(value=1)
        self.var_cols = tk.IntVar(value=1)

        # Storage for UI objects created by tab modules when needed
        self._preview_fig = None
        self._preview_ax = None
        self._preview_canvas = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Create Notebook and add all tab frames using the tab builder modules."""
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        tabs: Tuple[Tuple[str, callable], ...] = (
            ("General", build_general_tab),
            ("IMT", build_imt_tab),
            ("Single Space Station", build_victim_tab),
            ("3D Preview & Export", build_preview_tab),
            ("Runner", build_runner_tab),
            ("Results", build_results_tab),
        )

        for title, builder in tabs:
            frame = ttk.Frame(notebook, padding=10)
            notebook.add(frame, text=title)
            builder(self, frame)
