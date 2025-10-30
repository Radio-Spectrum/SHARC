import os
import sys
import re
import ast
import json
import time
import queue
import yaml
import itertools
import datetime
import threading
import subprocess
from pathlib import Path
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from sharc.antenna.antenna_s672 import AntennaS672
from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
from matplotlib import cm, colors
import pandas as pd
import glob
from tkinter import filedialog
import traceback
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ====== Optional: Countries topology (for 3D preview) ======
HAS_TOPO = True
try:
    from sharc.topology.topology_countries import TopologyCountries, ParametersCountries
    from sharc.support.sharc_geom_countries import GeometryConverter
except Exception:
    HAS_TOPO = False
    TopologyCountries = None
    ParametersCountries = None
    GeometryConverter = None

# ====== Optional: shapefile borders (pyshp) ======
try:
    import shapefile as pyshp  # pip install pyshp
    HAS_PYSHP = True
except Exception:
    HAS_PYSHP = False

# ===================== Simple YAML dumper =====================
def _yaml_bool(v: bool) -> str:
    return "true" if v else "false"

def dump_yaml_block(d, indent=0):
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
    return "\n".join(dump_yaml_block(root_dict)) + "\n"

# ===================== Geodesy helpers =====================
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563

def lla_to_ecef(lat_deg, lon_deg, h_m, a=WGS84_A, f=WGS84_F):
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

# ===================== UI Helpers =====================
def add_row_three(parent, r, items):
    col = 0
    for (txt, w) in items:
        lbl = ttk.Label(parent, text=txt)
        lbl.grid(row=r, column=col, sticky="e", padx=(0,6), pady=2)
        w.grid(row=r, column=col+1, sticky="we", pady=2)
        parent.grid_columnconfigure(col+1, weight=1)
        col += 2
    while col < 6:
        parent.grid_columnconfigure(col, weight=1)
        col += 1


# ===================== GUI =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.report_callback_exception = self._report_callback_exception
        self.title("SHARC – YAML GUI (IMT + Single Space Station)")
        self.geometry("1260x900")
        self.minsize(1100, 800)
        
        # ------ General ------
        self.var_seed = tk.IntVar(value=157)
        self.var_snaps = tk.IntVar(value=10000)
        self.var_overwrite = tk.BooleanVar(value=False)
        self.var_outdir = tk.StringVar(value=str(Path.cwd() / "sharc/campaigns"))
        self.var_yaml_dir = tk.StringVar(value=str(Path.cwd() / "sharc/campaigns"))
        self.var_prefix = tk.StringVar(value="output_mss_{long}")
        self.var_system = tk.StringVar(value="SINGLE_SPACE_STATION")
        self.var_imt_link = tk.StringVar(value="DOWNLINK")
        self.var_adj = tk.BooleanVar(value=False)
        self.var_coch = tk.BooleanVar(value=True)

        # ------ Variables (General) ------
        self.vars_model = []  # list of dicts: {"name": str, "values": list}

        # ------ IMT: gerais ------
        self.imt_min_sep = tk.StringVar(value="35")
        self.imt_interfered = tk.BooleanVar(value=False)
        self.imt_freq = tk.StringVar(value="8150")
        self.imt_bw = tk.StringVar(value="100")       # StringVar to accept {bw}
        self.imt_rb_bw = tk.StringVar(value="0.18")
        self.imt_spec_mask = tk.StringVar(value="IMT-2020")
        self.imt_spurious = tk.StringVar(value="-13")
        self.imt_adj_ant_model = tk.StringVar(value="SINGLE_ELEMENT")
        self.imt_guard_ratio = tk.StringVar(value="0.1")

        # ------ Topologia: COUNTRIES ------
        self.topo_c_lat = tk.StringVar(value="-15.793889")
        self.topo_c_lon = tk.StringVar(value="-47.882778")
        self.topo_c_alt = tk.StringVar(value="0")
        self.topo_type = tk.StringVar(value="Macro_countries")
        self.topo_dist_type = tk.StringVar(value="Urban")
        self.topo_num_bs = tk.StringVar(value="100")
        self.topo_cell_radius = tk.StringVar(value="400")
        self.topo_rng = tk.StringVar(value="10")
        self.topo_raster_enc = tk.StringVar(value="Denspop")
        self.topo_countries = tk.StringVar(value="\n".join([
            "Brazil","Argentina","Uruguay","Paraguay","Chile",
            "Bolivia","Peru","Ecuador","Colombia","Venezuela",
            "Guyana","Suriname","Belize","Guatemala","El Salvador",
            "Honduras","Nicaragua","Costa Rica","Panama",
            "Mexico","United States of America","Canada",
            "Cuba","Haiti","Dominican Republic","Jamaica","Trinidad and Tobago"
        ]))
        self.path_shp = tk.StringVar(value=str(Path.cwd()/"sharc/topology/map/ne_110m_admin_0_countries.shp"))
        self.path_raster = tk.StringVar(value=str(Path.cwd()/"sharc/topology/map/SEDAC_map2.tiff"))
        self.raster_encoding = tk.StringVar(value="indexed")
        self.sedac_mode = tk.StringVar(value="log")
        self.sedac_min = tk.StringVar(value="1.0")
        self.sedac_max = tk.StringVar(value="1e4")
        self.pixel_area_method = tk.StringVar(value="spherical")
        # ------ Topologia: TYPE selector ------
        self.topo_type = tk.StringVar(value="Macro_countries")  # será controlado por Combobox

        # ------ TOPOS: MACROCELL ------
        self.macro_intersite = tk.StringVar(value="600")           # None por padrão (vazio mostra None)
        self.macro_wrap = tk.BooleanVar(value=False)
        self.macro_clusters = tk.StringVar(value="1")

        # ------ TOPOS: HOTSPOT ------
        self.hotspot_intersite = tk.StringVar(value="600")         # None
        self.hotspot_wrap = tk.BooleanVar(value=False)
        self.hotspot_clusters = tk.StringVar(value="1")
        self.hotspot_num_per_cell = tk.StringVar(value="3")
        self.hotspot_max_dist_ue = tk.StringVar(value="400.0")
        self.hotspot_min_dist_bs = tk.StringVar(value="40.0")

        # ------ TOPOS: SINGLE_BS ------
        self.sbs_intersite = tk.StringVar(value="600")             # None
        self.sbs_cell_radius = tk.StringVar(value="400")
        self.sbs_clusters = tk.StringVar(value="1")
        self.sbs_azimuth = tk.StringVar(value="120")               # aceita lista "0,120,240" ou vazio
        # ------ BS ------
        self.bs_load_prob = tk.StringVar(value="0.2")
        self.bs_power = tk.StringVar(value="22")
        self.bs_height = tk.StringVar(value="18")
        self.bs_nf = tk.StringVar(value="6")
        self.bs_ohmic = tk.StringVar(value="0")
        self.bs_norm = tk.BooleanVar(value=False)
        self.bs_elem_pat = tk.StringVar(value="M2101")
        self.bs_min_arr_gain = tk.StringVar(value="-200")
        self.bs_h_steer = (tk.StringVar(value="-60"), tk.StringVar(value="60"))
        self.bs_v_steer = (tk.StringVar(value="90"),  tk.StringVar(value="100"))
        self.bs_downtilt = tk.StringVar(value="6")
        self.bs_elem_max_g = tk.StringVar(value="6.4")
        self.bs_phi3 = tk.StringVar(value="90")
        self.bs_theta3 = tk.StringVar(value="65")
        self.bs_rows = tk.StringVar(value="8")
        self.bs_cols = tk.StringVar(value="16")
        self.bs_elem_hs = tk.StringVar(value="0.5")
        self.bs_elem_vs = tk.StringVar(value="2.1")
        self.bs_elem_am = tk.StringVar(value="30")
        self.bs_elem_sla_v = tk.StringVar(value="30")
        self.bs_mult = tk.StringVar(value="12")
        self.bs_sub_enabled = tk.BooleanVar(value=True)
        self.bs_sub_rows = tk.StringVar(value="3")
        self.bs_sub_evspace = tk.StringVar(value="0.7")
        self.bs_sub_e_downtilt = tk.StringVar(value="3")

        # ------ UE ------
        self.ue_k = tk.StringVar(value="3")
        self.ue_km = tk.StringVar(value="1")
        self.ue_indoor = tk.StringVar(value="70")
        # --- UE: distribuição ---
        self.ue_dist_type = tk.StringVar(value="Macro_Countries")  # "Macro_Countries", UNIFORM, CELL, UNIFORM_IN_CELL, ANGLE_AND_DISTANCE
        self.ue_dist_distance = tk.StringVar(value="RAYLEIGH")   # RAYLEIGH | UNIFORM | SQRT(UNIFORM)
        self.ue_dist_azimuth  = tk.StringVar(value="NORMAL")     # NORMAL | UNIFORM
        # azimuth_range exigido pela geração outdoor
        self.ue_az_min = tk.StringVar(value="-60")
        self.ue_az_max = tk.StringVar(value="60")
        self.ue_tx_power_ctrl = tk.BooleanVar(value=True)
        self.ue_p_o_pusch = tk.StringVar(value="-92.2")
        self.ue_alpha = tk.StringVar(value="0.8")
        self.ue_p_cmax = tk.StringVar(value="23")
        self.ue_p_dyn = tk.StringVar(value="56")
        self.ue_height = tk.StringVar(value="1.5")
        self.ue_nf = tk.StringVar(value="13")
        self.ue_ohmic = tk.StringVar(value="0")
        self.ue_body_loss = tk.StringVar(value="4")
        self.ue_norm = tk.BooleanVar(value=False)
        self.ue_elem_pat = tk.StringVar(value="FIXED")
        self.ue_min_arr_gain = tk.StringVar(value="-200")
        self.ue_elem_max_g = tk.StringVar(value="-4")
        self.ue_phi3 = tk.StringVar(value="180")
        self.ue_theta3 = tk.StringVar(value="360")
        self.ue_rows = tk.StringVar(value="1")
        self.ue_cols = tk.StringVar(value="1")
        self.ue_elem_am = tk.StringVar(value="25")
        self.ue_elem_sla_v = tk.StringVar(value="25")
        self.ue_mult = tk.StringVar(value="12")

        self.ul_att = tk.StringVar(value="0.4")
        self.ul_sinr_min = tk.StringVar(value="-10")
        self.ul_sinr_max = tk.StringVar(value="22")
        self.dl_att = tk.StringVar(value="0.6")
        self.dl_sinr_min = tk.StringVar(value="-10")
        self.dl_sinr_max = tk.StringVar(value="30")
        self.ch_model = tk.StringVar(value="UMa")
        self.shadowing = tk.BooleanVar(value=True)
        # --- UE: sub-array (opcional) ---
        self.ue_sub_enabled     = tk.BooleanVar(value=False)
        self.ue_sub_rows        = tk.StringVar(value="1")
        self.ue_sub_evspace     = tk.StringVar(value="1.0")
        self.ue_sub_e_downtilt  = tk.StringVar(value="0.0")

        # ------ Single Space Station (vítima) ------
        self.v_freq = tk.StringVar(value="8150")
        self.v_bw = tk.StringVar(value="40")
        self.v_txpsd = tk.StringVar(value="-200")
        self.v_pol_loss = tk.StringVar(value="0")
        self.v_tnoise = tk.StringVar(value="500")
        self.v_ch_model = tk.StringVar(value="P619")
        self.v_season = tk.StringVar(value="SUMMER")
        self.v_p619_clutter = tk.StringVar(value="Mid")  # Low/Mid/High (combobox)
        self.v_p619_below_rooftop = tk.StringVar(value="65")
        self.ss_is_global_cs = tk.BooleanVar(value=True)  # default = True


        # Spacecraft FIXED position:
        self.v_alt = tk.StringVar(value="35786000")
        self.v_fix_lat = tk.StringVar(value="0")
        self.v_fix_lon = tk.StringVar(value="-110")

        # Earth Station point (ES):
        self.v_es_alt = tk.StringVar(value="200")
        self.v_es_lat = tk.StringVar(value="-10.871349")
        self.v_es_lon = tk.StringVar(value="-51.6424333")

        # Pointing types (export only; viz usa spacecraft->ES)
        self.v_az_type = tk.StringVar(value="POINTING_AT_IMT")
        self.v_el_type = tk.StringVar(value="POINTING_AT_IMT")

        # Antenna
        self.v_ant_pattern = tk.StringVar(value="ITU-R S.672")
        self.v_ant_gain = tk.StringVar(value="30")
        self.v_s672_3db = tk.StringVar(value="5")
        self.v_s672_ls = tk.StringVar(value="-20")
        self.var_show_gainmap = tk.BooleanVar(value=False)
        self.var_gain_vmin = tk.StringVar(value="auto")  # ou ex.: "30"
        self.var_gain_vmax = tk.StringVar(value="auto")

        # Runner parallelism
        self.var_max_workers = tk.IntVar(value=2)

        # runtime maps for runner
        self.proc_threads = {}  # file -> thread
        self.runtime = {}       # file -> dict(status, total, done, t0, last_time)
        self.line_q = queue.Queue()
        self.jobs_q = queue.Queue()
        self.running = set()
        self.procs = {}         # file -> subprocess.Popen

        # ---- Resultados (plots) ----
        self.res_dirs = []  # lista de pastas selecionadas (strings)
        self.var_auto_update = tk.BooleanVar(value=True)
        self.var_update_period_ms = tk.IntVar(value=2000)
        self.var_rows = tk.IntVar(value=1)
        self.var_cols = tk.IntVar(value=1)
        self._plot_auto_job = None  # job id do after()
        # ---- Resultados: extras ----
        self.var_xlog = tk.BooleanVar(value=False)        # escala log no eixo X
        self.var_export_dpi = tk.IntVar(value=200)        # DPI de exportação
        self.var_export_fmt = tk.StringVar(value="PNG")   # PNG, SVG, PDF

        # Linhas de referência globais (lista de dicts: {"x": float, "label": str})
        self.ref_lines = []
        # configuração de cada subfigura: lista de dicts {"field": str, "mode": "CDF"/"CCDF"}
        self.result_fields = sorted(list(RESULT_FIELDNAME_TO_PLOT_INFO.keys()))
        # capacidade máx de subplots (ex.: 9 painéis)
        self._max_axes = 9
        # field/mode/yscale/refs (refs em %, ex.: "5,10,50")
        self._axes_cfg = [{
            "field": self.result_fields[0],
            "mode": "CDF",         # ou "CCDF"
            "yscale": "Linear",    # ou "Log"
            "refs": ""             # ex.: "5,10"
        } for _ in range(self._max_axes)]
        # UI
        self._build_ui()

    # ---------------- UI builder ----------------
    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        tab_general = ttk.Frame(nb, padding=10)
        tab_imt = ttk.Frame(nb, padding=10)
        tab_victim = ttk.Frame(nb, padding=10)
        tab_preview = ttk.Frame(nb, padding=(10, 6, 10, 10))
        tab_runner = ttk.Frame(nb, padding=10)
        tab_results = ttk.Frame(nb)

        nb.add(tab_general, text="General")
        nb.add(tab_imt, text="IMT")
        nb.add(tab_victim, text="Single Space Station")
        nb.add(tab_preview, text="Visualização 3D & Export")
        nb.add(tab_runner, text="Runner")
        nb.add(tab_results, text="Resultados")

        self._tab_general(tab_general)
        self._tab_imt(tab_imt)
        self._tab_victim(tab_victim)
        self._tab_preview(tab_preview)
        self._tab_runner(tab_runner)
        self._tab_results(tab_results)

    # ---------- helpers to accept placeholders ----------
    def _num_or_str(self, s):
        """Converte para float se possível; senão retorna string (p/ placeholders)."""
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return float(s)
        s2 = str(s).strip()
        try:
            return float(s2)
        except Exception:
            return s2

    def _deep_format(self, obj, combo):
        """Aplica .format(**combo) recursivamente em strings do dicionário."""
        if isinstance(obj, dict):
            return {k: self._deep_format(v, combo) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_format(v, combo) for v in obj]
        if isinstance(obj, str):
            try:
                return obj.format(**combo)
            except Exception:
                return obj
        return obj

    # ---------------- Tabs ----------------
    def _tab_general(self, root):
        frm = ttk.LabelFrame(root, text="Parâmetros gerais")
        frm.pack(fill="x")

        e_seed = ttk.Entry(frm, textvariable=self.var_seed, width=12)
        e_snaps = ttk.Entry(frm, textvariable=self.var_snaps, width=12)
        cb_sys = ttk.Combobox(frm, textvariable=self.var_system,
                              values=["SINGLE_EARTH_STATION","SINGLE_SPACE_STATION"],
                              state="readonly", width=26)
        add_row_three(frm, 0, [("seed", e_seed),
                               ("num_snapshots", e_snaps),
                               ("system", cb_sys)])

        row2 = ttk.Frame(frm); row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2, text="output_dir (vai dentro do YAML)").pack(side="left")
        e_outdir = ttk.Entry(row2, textvariable=self.var_outdir)
        e_outdir.pack(side="left", fill="x", expand=True, padx=(6,6))
        ttk.Button(row2, text="Selecionar...", command=self._pick_outdir).pack(side="left")

        row2b = ttk.Frame(frm); row2b.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2b, text="yaml_dir (onde salvar os .yaml)").pack(side="left")
        e_yamldir = ttk.Entry(row2b, textvariable=self.var_yaml_dir)
        e_yamldir.pack(side="left", fill="x", expand=True, padx=(6,6))
        ttk.Button(row2b, text="Selecionar...", command=self._pick_yamldir).pack(side="left")

        e_prefix = ttk.Entry(frm, textvariable=self.var_prefix)
        cb_link = ttk.Combobox(frm, textvariable=self.var_imt_link,
                               values=["DOWNLINK","UPLINK"], state="readonly", width=18)
        add_row_three(frm, 3, [("output_dir_prefix (usa {variavel})", e_prefix),
                               ("imt_link", cb_link),
                               ("overwrite_output", ttk.Checkbutton(frm, variable=self.var_overwrite, text="true/false"))])

        add_row_three(frm, 4, [
            ("enable_adjacent_channel", ttk.Checkbutton(frm, variable=self.var_adj, text="true/false")),
            ("enable_cochannel", ttk.Checkbutton(frm, variable=self.var_coch, text="true/false")),
            ("", ttk.Label(frm, text=""))
        ])

        # ---- Variáveis (nome / valores em [..]) ----
        box = ttk.LabelFrame(root, text="Variáveis para combinações (use {nome} no output_dir_prefix e no YAML)")
        box.pack(fill="both", expand=True, pady=(8,0))

        toolbar = ttk.Frame(box); toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Adicionar variável", command=self._var_add).pack(side="left")
        ttk.Button(toolbar, text="Remover selecionadas", command=self._var_remove).pack(side="left", padx=(6,0))

        self.var_table = ttk.Treeview(box, columns=("name","values"), show="headings", height=5)
        self.var_table.heading("name", text="nome")
        self.var_table.heading("values", text="valores (lista: [10,20] ou [\"LOW\",\"MID\"])")
        self.var_table.column("name", width=180)
        self.var_table.column("values", width=640)
        self.var_table.pack(fill="both", expand=True, pady=(6,6))

        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=("long", "[-10, -20, -30, -40, -50]"))

        row_gen = ttk.Frame(root)
        row_gen.pack(fill="x", pady=(8,0))
        ttk.Button(row_gen, text="Gerar YAML(s) no yaml_dir (todas combinações)", command=self._save_yaml_to_yamldir).pack(side="left")

    def _tab_imt(self, root):
        # ===== Scrollable container para a aba IMT =====
        container = ttk.Frame(root)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Frame real onde você adiciona os widgets
        imt_body = ttk.Frame(canvas)
        # cria uma window dentro do canvas
        canvas_window = canvas.create_window((0, 0), window=imt_body, anchor="nw")

        def _on_frame_config(event):
            # ajusta região de scroll para caber o conteúdo
            canvas.configure(scrollregion=canvas.bbox("all"))
            # mantém a largura do frame igual à largura visível do canvas
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        imt_body.bind("<Configure>", _on_frame_config)

        # suporte a rodinha do mouse
        def _on_mousewheel(event):
            # Windows / Linux
            delta = int(-1*(event.delta/120))
            canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)      # Windows
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll( 1, "units"))  # Linux

        # >>> A partir daqui, use 'imt_body' no lugar de 'root' para montar a UI da aba IMT
        root = imt_body

        topbar = ttk.Frame(root); topbar.pack(fill="x", pady=(0,6))
        ttk.Button(topbar, text="Salvar configuração IMT (.json)", command=self._save_imt_config).pack(side="left")
        ttk.Button(topbar, text="Carregar configuração IMT (.json)", command=self._load_imt_config).pack(side="left", padx=(6,0))

        frm_g = ttk.LabelFrame(root, text="IMT – Parâmetros gerais")
        frm_g.pack(fill="x", pady=(2,8))

        add_row_three(frm_g, 0, [
            ("minimum_separation_distance_bs_ue [m]", ttk.Entry(frm_g, textvariable=self.imt_min_sep, width=10)),
            ("interfered_with", ttk.Combobox(frm_g, textvariable=self.imt_interfered, values=[False, True], state="readonly", width=8)),
            ("frequency [MHz]", ttk.Entry(frm_g, textvariable=self.imt_freq, width=12)),
        ])
        add_row_three(frm_g, 1, [
            ("bandwidth [MHz]", ttk.Entry(frm_g, textvariable=self.imt_bw, width=10)),
            ("rb_bandwidth [MHz]", ttk.Entry(frm_g, textvariable=self.imt_rb_bw, width=10)),
            ("spectral_mask", ttk.Combobox(frm_g, textvariable=self.imt_spec_mask, values=["IMT-2020","3GPP"], state="readonly", width=12)),
        ])
        add_row_three(frm_g, 2, [
            ("spurious_emissions [dBc]", ttk.Entry(frm_g, textvariable=self.imt_spurious, width=10)),
            ("adjacent_antenna_model", ttk.Entry(frm_g, textvariable=self.imt_adj_ant_model, width=16)),
            ("guard_band_ratio", ttk.Entry(frm_g, textvariable=self.imt_guard_ratio, width=10)),
        ])

        # ---------- Topologia (seletor de tipo + subframes) ----------
        frm_t = ttk.LabelFrame(root, text="Topologia – IMT")
        frm_t.pack(fill="x", pady=(2,8))

        # Linha 0: seletor de TYPE vem primeiro
        row_type = ttk.Frame(frm_t); row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0,4))
        ttk.Label(row_type, text="type").pack(side="left")
        cb_topo_type = ttk.Combobox(
            row_type, textvariable=self.topo_type,
            values=["MACROCELL","HOTSPOT","SINGLE_BS","Macro_countries"], state="readonly", width=18
        )
        cb_topo_type.pack(side="left", padx=(6,0))

        # Linha 1: parâmetros centrais (comuns)
        add_row_three(frm_t, 1, [
            ("central_latitude", ttk.Entry(frm_t, textvariable=self.topo_c_lat, width=12)),
            ("central_longitude", ttk.Entry(frm_t, textvariable=self.topo_c_lon, width=12)),
            ("central_altitude [m]", ttk.Entry(frm_t, textvariable=self.topo_c_alt, width=12)),
        ])

        # ---- Subframe: Countries ----
        self.frm_t_countries = ttk.LabelFrame(frm_t, text="Topologia – COUNTRIES (Macro_countries)")
        self.frm_t_countries.grid(row=2, column=0, columnspan=6, sticky="we", pady=(4,8))

        # Linha 0: raster_encoding + dist_type (ACIMA da lista de countries)
        row_opts = ttk.Frame(self.frm_t_countries)
        row_opts.grid(row=0, column=0, columnspan=6, sticky="we", pady=(2,4))

        ttk.Label(row_opts, text="raster_encoding").pack(side="left")
        cb_renc = ttk.Combobox(
            row_opts, textvariable=self.topo_raster_enc,
            values=["Uniforme", "Denspop"], state="readonly", width=12
        )
        cb_renc.pack(side="left", padx=(6,16))

        ttk.Label(row_opts, text="dist_type").pack(side="left")
        cb_dist = ttk.Combobox(
            row_opts, textvariable=self.topo_dist_type,
            values=["Urban", "Suburban", "Rural"], state="readonly", width=12
        )
        cb_dist.pack(side="left", padx=(6,0))
        # Dica visual: "" = None (sem filtro)

        # Linha 1: Lista de countries (Text)
        row_c = ttk.Frame(self.frm_t_countries)
        row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row_c, text="country_names (1/linha)").pack(side="left")
        self.txt_countries = tk.Text(row_c, width=48, height=7)
        self.txt_countries.insert("1.0", self.topo_countries.get())
        self.txt_countries.pack(side="left", fill="x", expand=True, padx=(6,6))

        # Linha 2: num_bs_total, cell_radius, rng_seed (se já tinha, mantenha)
        add_row_three(self.frm_t_countries, 2, [
            ("num_bs_total", ttk.Entry(self.frm_t_countries, textvariable=self.topo_num_bs, width=10)),
            ("cell_radius [m]", ttk.Entry(self.frm_t_countries, textvariable=self.topo_cell_radius, width=10)),
            ("rng_seed", ttk.Entry(self.frm_t_countries, textvariable=self.topo_rng, width=10)),
        ])

        # ---- Shapefile (linha ocupando as 3 colunas, com botão "...") ----
        row_shp = ttk.Frame(self.frm_t_countries)
        row_shp.grid(row=3, column=0, columnspan=6, sticky="we", pady=(2,2))
        ttk.Label(row_shp, text="countries_shapefile").pack(side="left")
        self.ent_shp = ttk.Entry(row_shp, textvariable=self.path_shp, width=64)
        self.ent_shp.pack(side="left", fill="x", expand=True, padx=(6,6))
        self.btn_shp = ttk.Button(row_shp, text="…", width=3, command=self._browse_shapefile)
        self.btn_shp.pack(side="left")
        # ---- Population raster (linha ocupando as 3 colunas, com botão "...") ----
        row_ras = ttk.Frame(self.frm_t_countries)
        row_ras.grid(row=4, column=0, columnspan=6, sticky="we", pady=(2,2))
        ttk.Label(row_ras, text="population_raster").pack(side="left")
        self.ent_raster = ttk.Entry(row_ras, textvariable=self.path_raster, width=64)
        self.ent_raster.pack(side="left", fill="x", expand=True, padx=(6,6))
        self.btn_raster = ttk.Button(row_ras, text="…", width=3, command=self._browse_raster)
        self.btn_raster.pack(side="left")
        cb_renc.bind("<<ComboboxSelected>>", self._toggle_raster_by_encoding)
        self._toggle_raster_by_encoding()

        # ---- Subframe: MACROCELL ----
        self.frm_t_macro = ttk.LabelFrame(frm_t, text="Topologia – MACROCELL")
        self.frm_t_macro.grid(row=3, column=0, columnspan=6, sticky="we", pady=(4,8))
        add_row_three(self.frm_t_macro, 0, [
            ("intersite_distance [m]", ttk.Entry(self.frm_t_macro, textvariable=self.macro_intersite, width=10)),
            ("wrap_around", ttk.Combobox(self.frm_t_macro, textvariable=self.macro_wrap, values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(self.frm_t_macro, textvariable=self.macro_clusters, width=8)),
        ])

        # ---- Subframe: HOTSPOT ----
        self.frm_t_hotspot = ttk.LabelFrame(frm_t, text="Topologia – HOTSPOT")
        self.frm_t_hotspot.grid(row=4, column=0, columnspan=6, sticky="we", pady=(4,8))
        add_row_three(self.frm_t_hotspot, 0, [
            ("intersite_distance [m]", ttk.Entry(self.frm_t_hotspot, textvariable=self.hotspot_intersite, width=10)),
            ("wrap_around", ttk.Combobox(self.frm_t_hotspot, textvariable=self.hotspot_wrap, values=[False, True], state="readonly", width=8)),
            ("num_clusters", ttk.Entry(self.frm_t_hotspot, textvariable=self.hotspot_clusters, width=8)),
        ])
        add_row_three(self.frm_t_hotspot, 1, [
            ("num_hotspots_per_cell", ttk.Entry(self.frm_t_hotspot, textvariable=self.hotspot_num_per_cell, width=10)),
            ("max_dist_hotspot_ue [m]", ttk.Entry(self.frm_t_hotspot, textvariable=self.hotspot_max_dist_ue, width=12)),
            ("min_dist_bs_hotspot [m]", ttk.Entry(self.frm_t_hotspot, textvariable=self.hotspot_min_dist_bs, width=12)),
        ])

        # ---- Subframe: SINGLE_BS ----
        self.frm_t_sbs = ttk.LabelFrame(frm_t, text="Topologia – SINGLE_BS")
        self.frm_t_sbs.grid(row=5, column=0, columnspan=6, sticky="we", pady=(4,8))
        add_row_three(self.frm_t_sbs, 0, [
            ("intersite_distance [m]", ttk.Entry(self.frm_t_sbs, textvariable=self.sbs_intersite, width=10)),
            ("cell_radius [m]", ttk.Entry(self.frm_t_sbs, textvariable=self.sbs_cell_radius, width=10)),
            ("num_clusters", ttk.Entry(self.frm_t_sbs, textvariable=self.sbs_clusters, width=8)),
        ])
        add_row_three(self.frm_t_sbs, 1, [
            ("azimuth (lista ou str)", ttk.Entry(self.frm_t_sbs, textvariable=self.sbs_azimuth, width=28)),
            ("", ttk.Label(self.frm_t_sbs, text="")),
            ("", ttk.Label(self.frm_t_sbs, text="")),
        ])

        def _toggle_topology_frames(*_):
            t = self.topo_type.get()
            # esconde todos
            for f in (self.frm_t_countries, self.frm_t_macro, self.frm_t_hotspot, self.frm_t_sbs):
                f.grid_remove()
            # mostra o correspondente
            if t == "Macro_countries":
                self.frm_t_countries.grid()
            elif t == "MACROCELL":
                self.frm_t_macro.grid()
            elif t == "HOTSPOT":
                self.frm_t_hotspot.grid()
            elif t == "SINGLE_BS":
                self.frm_t_sbs.grid()

        cb_topo_type.bind("<<ComboboxSelected>>", _toggle_topology_frames)
        _toggle_topology_frames()

        # ======= Seção BS (3 colunas) =======
        frm_bs = ttk.LabelFrame(root, text="BS – Parâmetros")
        frm_bs.pack(fill="x", padx=4, pady=6)

        # grade 3 colunas
        frm_bs.columnconfigure(0, weight=1)
        frm_bs.columnconfigure(1, weight=1)
        frm_bs.columnconfigure(2, weight=1)

        # ======= Seção BS (3 colunas, só grid) =======
        frm_bs = ttk.LabelFrame(root, text="BS – Parâmetros")
        frm_bs.pack(fill="x", padx=6, pady=8)

        # 3 colunas fluidas
        for c in range(3):
            frm_bs.columnconfigure(c, weight=1, uniform="bscols")

        # ----- Coluna 1: BS – Básico -----
        col_basic = ttk.LabelFrame(frm_bs, text="BS – Básico")
        col_basic.grid(row=0, column=0, sticky="nsew", padx=(6,3), pady=6)
        # duas colunas internas
        col_basic.columnconfigure(0, weight=0)
        col_basic.columnconfigure(1, weight=1)

        self._add_field(col_basic, 0, "load_probability",
                        ttk.Entry(col_basic, textvariable=self.bs_load_prob, width=10))
        self._add_field(col_basic, 1, "conducted_power [dBm]",
                        ttk.Entry(col_basic, textvariable=self.bs_power, width=10))
        self._add_field(col_basic, 2, "height [m]",
                        ttk.Entry(col_basic, textvariable=self.bs_height, width=10))
        self._add_field(col_basic, 3, "noise_figure [dB]",
                        ttk.Entry(col_basic, textvariable=self.bs_nf, width=10))
        self._add_field(col_basic, 4, "ohmic_loss [dB]",
                        ttk.Entry(col_basic, textvariable=self.bs_ohmic, width=10))

        # ----- Coluna 2: BS – Array da Antena -----
        col_array = ttk.LabelFrame(frm_bs, text="BS – Array da Antena")
        col_array.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
        # quatro colunas internas (para ranges ficarem bonitos)
        for c in range(4):
            col_array.columnconfigure(c, weight=(1 if c in (1,3) else 0))

        # normalization (use Checkbutton para evitar "0/1" na UI)
        norm_chk = ttk.Checkbutton(col_array, variable=self.bs_norm, text="")
        self._add_field(col_array, 0, "normalization", norm_chk)

        # element_pattern
        cb_pat = ttk.Combobox(col_array, textvariable=self.bs_elem_pat,
                            values=["M2101", "ITU-R S.672", "Custom"], state="readonly", width=14)
        self._add_field(col_array, 1, "element_pattern", cb_pat)

        # minimum_array_gain
        self._add_field(col_array, 2, "minimum_array_gain [dB]",
                        ttk.Entry(col_array, textvariable=self.bs_min_arr_gain, width=10))

        # horizontal_beamsteering_range
        w_hmin = ttk.Entry(col_array, textvariable=self.bs_h_steer[0], width=7)
        w_hmax = ttk.Entry(col_array, textvariable=self.bs_h_steer[1], width=7)
        self._add_range(col_array, 3, "h_beamsteer [deg]", w_hmin, w_hmax)

        # vertical_beamsteering_range
        w_vmin = ttk.Entry(col_array, textvariable=self.bs_v_steer[0], width=7)
        w_vmax = ttk.Entry(col_array, textvariable=self.bs_v_steer[1], width=7)
        self._add_range(col_array, 4, "v_beamsteer [deg]", w_vmin, w_vmax)

        # demais campos (linha simples)
        self._add_field(col_array, 5, "downtilt [deg]",
                        ttk.Entry(col_array, textvariable=self.bs_downtilt, width=10))
        self._add_field(col_array, 6, "element_max_g [dBi]",
                        ttk.Entry(col_array, textvariable=self.bs_elem_max_g, width=10))
        self._add_field(col_array, 7, "element_phi_3db [deg]",
                        ttk.Entry(col_array, textvariable=self.bs_phi3, width=10))
        self._add_field(col_array, 8, "element_theta_3db [deg]",
                        ttk.Entry(col_array, textvariable=self.bs_theta3, width=10))
        self._add_field(col_array, 9, "n_rows",
                        ttk.Entry(col_array, textvariable=self.bs_rows, width=10))
        self._add_field(col_array,10, "n_columns",
                        ttk.Entry(col_array, textvariable=self.bs_cols, width=10))
        self._add_field(col_array,11, "element_horiz_spacing [λ]",
                        ttk.Entry(col_array, textvariable=self.bs_elem_hs, width=10))
        self._add_field(col_array,12, "element_vert_spacing [λ]",
                        ttk.Entry(col_array, textvariable=self.bs_elem_vs, width=10))
        self._add_field(col_array,13, "element_am [dB]",
                        ttk.Entry(col_array, textvariable=self.bs_elem_am, width=10))
        self._add_field(col_array,14, "element_sla_v [dB]",
                        ttk.Entry(col_array, textvariable=self.bs_elem_sla_v, width=10))
        self._add_field(col_array,15, "multiplication_factor",
                        ttk.Entry(col_array, textvariable=self.bs_mult, width=10))

        # ----- Coluna 3: BS – Sub-array -----
        col_sub = ttk.LabelFrame(frm_bs, text="BS – Sub-array")
        col_sub.grid(row=0, column=2, sticky="nsew", padx=(3,6), pady=6)
        col_sub.columnconfigure(0, weight=0)
        col_sub.columnconfigure(1, weight=1)

        # is_enabled
        sub_en_chk = ttk.Checkbutton(col_sub, variable=self.bs_sub_enabled, text="")
        self._add_field(col_sub, 0, "is_enabled", sub_en_chk)

        self._add_field(col_sub, 1, "n_rows",
                        ttk.Entry(col_sub, textvariable=self.bs_sub_rows, width=10))
        self._add_field(col_sub, 2, "element_vert_spacing [λ]",
                        ttk.Entry(col_sub, textvariable=self.bs_sub_evspace, width=10))
        self._add_field(col_sub, 3, "eletrical_downtilt [deg]",
                        ttk.Entry(col_sub, textvariable=self.bs_sub_e_downtilt, width=10))


        # ======= Seção UE (3 colunas, só grid) =======
        frm_ue = ttk.LabelFrame(root, text="UE – Parâmetros")
        frm_ue.pack(fill="x", padx=6, pady=8)

        # 3 colunas fluidas
        for c in range(3):
            frm_ue.columnconfigure(c, weight=1, uniform="uecols")

        # ----- Coluna 1: UE – Básico -----
        col_basic_ue = ttk.LabelFrame(frm_ue, text="UE – Básico")
        col_basic_ue.grid(row=0, column=0, sticky="nsew", padx=(6,3), pady=6)
        col_basic_ue.columnconfigure(0, weight=0)
        col_basic_ue.columnconfigure(1, weight=1)

        self._add_field(col_basic_ue, 0, "k", ttk.Entry(col_basic_ue, textvariable=self.ue_k, width=8))
        self._add_field(col_basic_ue, 1, "k_m", ttk.Entry(col_basic_ue, textvariable=self.ue_km, width=8))
        self._add_field(col_basic_ue, 2, "indoor_percent [%]", ttk.Entry(col_basic_ue, textvariable=self.ue_indoor, width=8))

        # distribution_type (Combobox)
        cb_ue_dist = ttk.Combobox(col_basic_ue, textvariable=self.ue_dist_type,
                                values=["Macro_countries", "UNIFORM","CELL","UNIFORM_IN_CELL","ANGLE_AND_DISTANCE"],
                                state="readonly", width=18)
        self._add_field(col_basic_ue, 3, "distribution_type", cb_ue_dist)
        cb_ue_dist.bind("<<ComboboxSelected>>", lambda e: self._toggle_ue_distribution())
        self._add_field(col_basic_ue, 3, "distribution_type", cb_ue_dist)

        # tx_power_control (Checkbutton)
        chk_tx = ttk.Checkbutton(col_basic_ue, variable=self.ue_tx_power_ctrl, text="")
        self._add_field(col_basic_ue, 4, "tx_power_control", chk_tx)

        self._add_field(col_basic_ue, 5, "p_o_pusch [dBm]", ttk.Entry(col_basic_ue, textvariable=self.ue_p_o_pusch, width=10))
        self._add_field(col_basic_ue, 6, "alpha", ttk.Entry(col_basic_ue, textvariable=self.ue_alpha, width=10))
        self._add_field(col_basic_ue, 7, "p_cmax [dBm]", ttk.Entry(col_basic_ue, textvariable=self.ue_p_cmax, width=10))
        self._add_field(col_basic_ue, 8, "power_dynamic_range [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_p_dyn, width=10))
        self._add_field(col_basic_ue, 9, "height [m]", ttk.Entry(col_basic_ue, textvariable=self.ue_height, width=10))
        self._add_field(col_basic_ue,10, "noise_figure [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_nf, width=10))
        self._add_field(col_basic_ue,11, "ohmic_loss [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_ohmic, width=10))
        self._add_field(col_basic_ue,12, "body_loss [dB]", ttk.Entry(col_basic_ue, textvariable=self.ue_body_loss, width=10))

        # ----- Coluna 2: UE – Array da Antena -----
        col_array_ue = ttk.LabelFrame(frm_ue, text="UE – Array da Antena")
        col_array_ue.grid(row=0, column=1, sticky="nsew", padx=3, pady=6)
        for c in range(4):
            col_array_ue.columnconfigure(c, weight=(1 if c in (1,3) else 0))

        chk_norm_ue = ttk.Checkbutton(col_array_ue, variable=self.ue_norm, text="")
        self._add_field(col_array_ue, 0, "normalization", chk_norm_ue)

        cb_pat_ue = ttk.Combobox(col_array_ue, textvariable=self.ue_elem_pat,
                                values=["FIXED","M2101","Custom"], state="readonly", width=14)
        self._add_field(col_array_ue, 1, "element_pattern", cb_pat_ue)

        self._add_field(col_array_ue, 2, "minimum_array_gain [dB]", ttk.Entry(col_array_ue, textvariable=self.ue_min_arr_gain, width=10))
        self._add_field(col_array_ue, 3, "element_max_g [dBi]", ttk.Entry(col_array_ue, textvariable=self.ue_elem_max_g, width=10))
        self._add_field(col_array_ue, 4, "element_phi_3db [deg]", ttk.Entry(col_array_ue, textvariable=self.ue_phi3, width=10))
        self._add_field(col_array_ue, 5, "element_theta_3db [deg]", ttk.Entry(col_array_ue, textvariable=self.ue_theta3, width=10))
        self._add_field(col_array_ue, 6, "n_rows", ttk.Entry(col_array_ue, textvariable=self.ue_rows, width=10))
        self._add_field(col_array_ue, 7, "n_columns", ttk.Entry(col_array_ue, textvariable=self.ue_cols, width=10))
        self._add_field(col_array_ue, 8, "element_am [dB]", ttk.Entry(col_array_ue, textvariable=self.ue_elem_am, width=10))
        self._add_field(col_array_ue, 9, "element_sla_v [dB]", ttk.Entry(col_array_ue, textvariable=self.ue_elem_sla_v, width=10))
        self._add_field(col_array_ue,10, "multiplication_factor", ttk.Entry(col_array_ue, textvariable=self.ue_mult, width=10))

        # ----- Coluna 3: UE – Sub-array -----
        col_sub_ue = ttk.LabelFrame(frm_ue, text="UE – Sub-array")
        col_sub_ue.grid(row=0, column=2, sticky="nsew", padx=(3,6), pady=6)
        col_sub_ue.columnconfigure(0, weight=0)
        col_sub_ue.columnconfigure(1, weight=1)

        chk_sub_en_ue = ttk.Checkbutton(col_sub_ue, variable=self.ue_sub_enabled, text="")
        self._add_field(col_sub_ue, 0, "is_enabled", chk_sub_en_ue)
        self._add_field(col_sub_ue, 1, "n_rows", ttk.Entry(col_sub_ue, textvariable=self.ue_sub_rows, width=10))
        self._add_field(col_sub_ue, 2, "element_vert_spacing [λ]", ttk.Entry(col_sub_ue, textvariable=self.ue_sub_evspace, width=10))
        self._add_field(col_sub_ue, 3, "eletrical_downtilt [deg]", ttk.Entry(col_sub_ue, textvariable=self.ue_sub_e_downtilt, width=10))

        col_dist_ue = ttk.LabelFrame(frm_ue, text="UE – Distribuição (Angle&Distance)")
        col_dist_ue.grid(row=1, column=0, sticky="nsew", padx=(3,6), pady=(0,6))  # mesma coluna, linha abaixo
        for c in range(4):
            col_dist_ue.columnconfigure(c, weight=(1 if c in (1,3) else 0))

        # distribution_distance
        cb_dist_d = ttk.Combobox(col_dist_ue, textvariable=self.ue_dist_distance,
                                values=["RAYLEIGH","UNIFORM","SQRT(UNIFORM)"],
                                state="readonly", width=16)

        # distribution_azimuth
        cb_dist_a = ttk.Combobox(col_dist_ue, textvariable=self.ue_dist_azimuth,
                                values=["NORMAL","UNIFORM"], state="readonly", width=16)
        self._add_field(col_dist_ue, 1, "distribution_azimuth", cb_dist_a)

        # azimuth_range (min a max)
        w_azmin = ttk.Entry(col_dist_ue, textvariable=self.ue_az_min, width=8)
        w_azmax = ttk.Entry(col_dist_ue, textvariable=self.ue_az_max, width=8)
        self._add_range(col_dist_ue, 2, "azimuth_range [deg]", w_azmin, w_azmax)

        # guarde a referência para o toggle
        self._ue_col_dist_frame = col_dist_ue

        frm_l = ttk.LabelFrame(root, text="UL / DL / Channel / Shadowing")
        frm_l.pack(fill="x", pady=(2,8))
        add_row_three(frm_l, 0, [
            ("uplink.attenuation_factor", ttk.Entry(frm_l, textvariable=self.ul_att, width=8)),
            ("uplink.sinr_min / sinr_max [dB]", self._pair_entries(frm_l, self.ul_sinr_min, self.ul_sinr_max, w=8)),
            ("downlink.attenuation_factor", ttk.Entry(frm_l, textvariable=self.dl_att, width=8)),
        ])
        add_row_three(frm_l, 1, [
            ("downlink.sinr_min / sinr_max [dB]", self._pair_entries(frm_l, self.dl_sinr_min, self.dl_sinr_max, w=8)),
            ("channel_model", ttk.Entry(frm_l, textvariable=self.ch_model, width=12)),
            ("shadowing", ttk.Combobox(frm_l, textvariable=self.shadowing, values=[True, False], state="readonly", width=8)),
        ])
        self._toggle_ue_distribution()

    def _tab_victim(self, root):
        topbar = ttk.Frame(root); topbar.pack(fill="x", pady=(0,6))
        ttk.Button(topbar, text="Salvar config Single Space Station (.json)", command=self._save_victim_config).pack(side="left")
        ttk.Button(topbar, text="Carregar config Single Space Station (.json)", command=self._load_victim_config).pack(side="left", padx=(6,0))

        # ==== Básicos ====
        frm0 = ttk.LabelFrame(root, text="Parâmetros básicos")
        frm0.pack(fill="x", padx=2, pady=4)
        add_row_three(frm0, 0, [
            ("frequency [MHz]", ttk.Entry(frm0, textvariable=self.v_freq, width=10)),
            ("bandwidth [MHz]", ttk.Entry(frm0, textvariable=self.v_bw, width=10)),
            ("tx_power_density [dBW/Hz]", ttk.Entry(frm0, textvariable=self.v_txpsd, width=12)),
        ])
        add_row_three(frm0, 1, [
            ("polarization_loss [dB]", ttk.Entry(frm0, textvariable=self.v_pol_loss, width=10)),
            ("noise_temperature [K]", ttk.Entry(frm0, textvariable=self.v_tnoise, width=10)),
            ("channel_model", ttk.Combobox(frm0, textvariable=self.v_ch_model, values=["P619","FSPL"], state="readonly", width=12)),
        ])
        add_row_three(frm0, 2, [
            ("season", ttk.Combobox(
                frm0, textvariable=self.v_season,
                values=["SUMMER", "WINTER"], state="readonly", width=10
            )),
            ("Terra Esférica?", ttk.Checkbutton(
                frm0, variable=self.ss_is_global_cs  # <- só passa o widget, sem .grid()
            )),
            ("", ttk.Label(frm0, text="")),
        ])

        # ==== P619 ====
        frm1 = ttk.LabelFrame(root, text="P619 parameters")
        frm1.pack(fill="x", padx=2, pady=4)
        add_row_three(frm1, 0, [
            ("mean_clutter_height", ttk.Combobox(frm1, textvariable=self.v_p619_clutter,
                                                 values=["Low","Mid","High"], state="readonly", width=10)),
            ("below_rooftop [%]", ttk.Entry(frm1, textvariable=self.v_p619_below_rooftop, width=10)),
            ("", ttk.Label(frm1, text="")),
        ])

        # ==== Geometria (subdividida) ====
        wrap = ttk.LabelFrame(root, text="Geometria – Classes")
        wrap.pack(fill="x", padx=2, pady=4)

        # Spacecraft (FIXED)
        frm_sc = ttk.LabelFrame(wrap, text="Spacecraft – Location (FIXED/GEO)")
        frm_sc.pack(fill="x", padx=2, pady=(6,6))
        add_row_three(frm_sc, 0, [
            ("altitude [m] (sat)", ttk.Entry(frm_sc, textvariable=self.v_alt, width=12)),
            ("location.fixed.lat_deg", ttk.Entry(frm_sc, textvariable=self.v_fix_lat, width=12)),
            ("location.fixed.long_deg", ttk.Entry(frm_sc, textvariable=self.v_fix_lon, width=12)),
        ])

        # Earth Station
        frm_es = ttk.LabelFrame(wrap, text="Earth Station – Reference point on Earth")
        frm_es.pack(fill="x", padx=2, pady=(0,6))
        add_row_three(frm_es, 0, [
            ("es_altitude [m]", ttk.Entry(frm_es, textvariable=self.v_es_alt, width=12)),
            ("es_lat_deg", ttk.Entry(frm_es, textvariable=self.v_es_lat, width=12)),
            ("es_long_deg", ttk.Entry(frm_es, textvariable=self.v_es_lon, width=12)),
        ])

        # Pointing (export only)
        frm_pt = ttk.LabelFrame(wrap, text="Pointing (export only)")
        frm_pt.pack(fill="x", padx=2, pady=(0,6))
        add_row_three(frm_pt, 0, [
            ("azimuth.type", ttk.Combobox(frm_pt, textvariable=self.v_az_type, values=["POINTING_AT_IMT","FIXED"], state="readonly", width=18)),
            ("elevation.type", ttk.Combobox(frm_pt, textvariable=self.v_el_type, values=["POINTING_AT_IMT","FIXED"], state="readonly", width=18)),
            ("", ttk.Label(frm_pt, text="")),
        ])

        # Antenna
        frm3 = ttk.LabelFrame(root, text="Antenna")
        frm3.pack(fill="x", padx=2, pady=4)
        add_row_three(frm3, 0, [
            ("pattern", ttk.Combobox(frm3, textvariable=self.v_ant_pattern,
                                     values=["ITU-R S.672","ITU-R M.2101","3GPP TR 38.901","Custom"], state="readonly", width=18)),
            ("gain [dBi]", ttk.Entry(frm3, textvariable=self.v_ant_gain, width=10)),
            ("", ttk.Label(frm3, text="")),
        ])
        self.frm_s672 = ttk.Frame(frm3)
        self.frm_s672.grid(row=1, column=0, columnspan=6, sticky="we", pady=(4,0))
        add_row_three(self.frm_s672, 0, [
            ("itu_r_s_672.antenna_3_dB", ttk.Entry(self.frm_s672, textvariable=self.v_s672_3db, width=8)),
            ("itu_r_s_672.antenna_l_s [dB]", ttk.Entry(self.frm_s672, textvariable=self.v_s672_ls, width=8)),
            ("", ttk.Label(self.frm_s672, text="")),
        ])
        self.frm_other_ant = ttk.Frame(frm3)
        ttk.Label(self.frm_other_ant, text="Parâmetros para este padrão ainda não implementados.").grid(row=0, column=0, sticky="w")

        def _toggle_antenna(*_):
            if self.v_ant_pattern.get() == "ITU-R S.672":
                self.frm_other_ant.grid_remove()
                self.frm_s672.grid()
            else:
                self.frm_s672.grid_remove()
                self.frm_other_ant.grid(row=1, column=0, columnspan=6, sticky="w", pady=(4,0))
        self.v_ant_pattern.trace_add("write", _toggle_antenna)
        _toggle_antenna()

    def _tab_preview(self, root):
        left = ttk.Frame(root); right = ttk.Frame(root)
        left.pack(side="left", fill="both", expand=True); right.pack(side="right", fill="y")

        # 3D figure
        self.fig3d = plt.figure(figsize=(6.6, 6.6))
        self.ax3d = self.fig3d.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

        # Colormap
        ttk.Checkbutton(
            right,
            text="Mostrar mapa de ganho (S.672)",
            variable=self.var_show_gainmap,
            command=self._draw_preview_3d
        ).pack(fill="x", pady=(0,8))

        # (Opcional) limites de cor do colormap:
        frm_gain = ttk.Frame(right); frm_gain.pack(fill="x", pady=(0,8))
        ttk.Label(frm_gain, text="vmin (dBi):").pack(side="left")
        e_vmin = ttk.Entry(frm_gain, textvariable=self.var_gain_vmin, width=7); e_vmin.pack(side="left", padx=(4,8))
        ttk.Label(frm_gain, text="vmax (dBi):").pack(side="left")
        e_vmax = ttk.Entry(frm_gain, textvariable=self.var_gain_vmax, width=7); e_vmax.pack(side="left", padx=(4,0))

        # Scroll do mouse
        w3d = self.canvas3d.get_tk_widget()
        # Windows/macOS: <MouseWheel> com delta +/-;
        w3d.bind("<MouseWheel>", self._on_scroll_3d)
        # Linux: rolagem vem como botões 4 (up) e 5 (down)
        w3d.bind("<Button-4>", self._on_scroll_3d)
        w3d.bind("<Button-5>", self._on_scroll_3d)
        # Borders toggle
        self.show_borders = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Mostrar fronteiras dos países", variable=self.show_borders).pack(anchor="w", pady=(4,6))

        ttk.Button(right, text="Gerar preview 3D", command=self._draw_preview_3d).pack(fill="x", pady=(4,4))
        ttk.Button(right, text="Zoom +", command=lambda: self._zoom_preview_3d(1/1.15)).pack(fill="x", pady=(0,4))
        ttk.Button(right, text="Zoom -", command=lambda: self._zoom_preview_3d(1.15)).pack(fill="x", pady=(0,8))
        ttk.Button(right, text="Salvar imagem...", command=self._save_image_3d).pack(fill="x", pady=(4,4))
        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(right, text="Atualizar YAML (preview)", command=self._update_yaml_preview).pack(fill="x", pady=(4,4))
        ttk.Button(right, text="Salvar YAML(s)...", command=self._save_yaml_dialog_multicombos).pack(fill="x", pady=(4,4))
        ttk.Label(right, text="Prévia do YAML (sem expandir combinações):").pack(anchor="w", pady=(10,2))
        self.txt_yaml = tk.Text(right, width=44, height=28, wrap="none")
        self.txt_yaml.pack(fill="both", expand=True)

        self._draw_preview_3d()
        self._update_yaml_preview()

    def _tab_runner(self, root):
        top = ttk.Frame(root); top.pack(fill="x")
        self.run_folder = tk.StringVar(value=os.path.join(Path.cwd(), "/sharc/campaigns"))
        ttk.Label(top, text="Pasta com arquivos .yaml").pack(side="left")
        e = ttk.Entry(top, textvariable=self.run_folder)
        e.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Escolher...", command=lambda: self._pick_folder(self.run_folder)).pack(side="left")
        ttk.Button(top, text="Atualizar lista", command=self._scan_yaml_files).pack(side="left", padx=(6,0))
        ttk.Label(top, text="Paralelo (máx execuções):").pack(side="left", padx=(14,4))
        tk.Spinbox(top, from_=1, to=32, width=4, textvariable=self.var_max_workers).pack(side="left")

        # Tree for files + progress
        mid = ttk.Frame(root); mid.pack(fill="both", expand=True, pady=(8,0))
        self.tree = ttk.Treeview(mid, columns=("yaml","status","snap","pct","eta"), show="headings", height=12)
        self.tree.heading("yaml", text="YAML")
        self.tree.heading("status", text="Status")
        self.tree.heading("snap", text="Snapshots (done/total)")
        self.tree.heading("pct", text="%")
        self.tree.heading("eta", text="ETA")
        self.tree.column("yaml", width=380)
        self.tree.column("status", width=220)
        self.tree.column("snap", width=180)
        self.tree.column("pct", width=60, anchor="e")
        self.tree.column("eta", width=120)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview); sb.pack(side="left", fill="y")
        self.tree.configure(yscroll=sb.set)

        right = ttk.Frame(root); right.pack(fill="x", pady=(8,0))
        self.main_cli_path = tk.StringVar(value=os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_cli.py"))
        ttk.Label(right, text="main_cli.py:").pack(side="left")
        ttk.Entry(right, textvariable=self.main_cli_path, width=44).pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(right, text="Parar selecionados", command=self._stop_selected).pack(side="right", padx=(6,0))
        ttk.Button(right, text="Executar selecionados", command=self._run_selected_yaml_parallel).pack(side="right")

        logf = ttk.LabelFrame(root, text="Log")
        logf.pack(fill="both", expand=True, pady=(8,0))
        self.txt_log = tk.Text(logf, height=10, wrap="none")
        self.txt_log.pack(fill="both", expand=True)

        self._scan_yaml_files()
        self.after(150, self._drain_log_queue)
        self.after(250, self._runner_scheduler_tick)
        
    def _tab_results(self, root):
        # Lado esquerdo: controles / Lado direito: figura
        left = ttk.Frame(root); right = ttk.Frame(root)
        left.pack(side="left", fill="y"); right.pack(side="right", fill="both", expand=True)

        # ---- Seleção de pastas ----
        ttk.Label(left, text="Pastas de resultados (comparação):").pack(anchor="w", pady=(6,2))
        frm_dirs = ttk.Frame(left); frm_dirs.pack(fill="x")
        self.lb_dirs = tk.Listbox(frm_dirs, height=6, selectmode="extended")
        self.lb_dirs.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frm_dirs, orient="vertical", command=self.lb_dirs.yview)
        sb.pack(side="right", fill="y"); self.lb_dirs.config(yscrollcommand=sb.set)

        def _add_dir():
            init = str(Path(self.var_outdir.get() or Path.cwd()))
            path = filedialog.askdirectory(initialdir=init, title="Selecionar pasta de resultados")
            if path and path not in self.res_dirs:
                self.res_dirs.append(path)
                self.lb_dirs.insert("end", path)
                self._draw_results_plots()

        def _add_current_outdir():
            path = str(Path(self.var_outdir.get()))
            if path and path not in self.res_dirs:
                self.res_dirs.append(path)
                self.lb_dirs.insert("end", path)
                self._draw_results_plots()

        def _remove_dir():
            sel = list(self.lb_dirs.curselection())[::-1]
            for idx in sel:
                path = self.lb_dirs.get(idx)
                self.res_dirs.remove(path)
                self.lb_dirs.delete(idx)
            self._draw_results_plots()

        frm_btn = ttk.Frame(left); frm_btn.pack(fill="x", pady=(4,8))
        ttk.Button(frm_btn, text="Adicionar pasta…", command=_add_dir).pack(side="left", padx=(0,4))
        ttk.Button(frm_btn, text="Usar output_dir atual", command=_add_current_outdir).pack(side="left", padx=(0,4))
        ttk.Button(frm_btn, text="Remover selecionadas", command=_remove_dir).pack(side="left")

        # ---- Grid de subplots ----
        frm_grid = ttk.LabelFrame(left, text="Layout de subfiguras")
        frm_grid.pack(fill="x", pady=(6,6))
        ttk.Label(frm_grid, text="Linhas").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.var_rows, width=5, command=self._draw_results_plots).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frm_grid, text="Colunas").grid(row=0, column=2, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.var_cols, width=5, command=self._draw_results_plots).grid(row=0, column=3, padx=4, pady=4)

        # ---- Configuração por subfigura (até _max_axes)
        frm_cfg = ttk.LabelFrame(left, text="Configuração de cada subfigura")
        frm_cfg.pack(fill="x", pady=(6,8))
        self._subplot_cfg_rows = []
        for i in range(self._max_axes):
            r = ttk.Frame(frm_cfg); r.pack(fill="x", pady=2)
            ttk.Label(r, text=f"{i+1:02d}").pack(side="left", padx=(2,6))

            # MÉTRICA
            cb_field = ttk.Combobox(r, values=self.result_fields, width=34)
            cb_field.set(self._axes_cfg[i]["field"])
            cb_field.pack(side="left", padx=(0,6))

            # CDF/CCDF
            cb_mode = ttk.Combobox(r, values=["CDF","CCDF"], width=6)
            cb_mode.set(self._axes_cfg[i]["mode"])
            cb_mode.pack(side="left", padx=(0,6))

            # Y-SCALE (Linear/Log)
            cb_ys = ttk.Combobox(r, values=["Linear","Log"], width=7)
            cb_ys.set(self._axes_cfg[i]["yscale"])
            cb_ys.pack(side="left", padx=(0,6))

            # REFERÊNCIAS (%, ex.: 5,10,50)
            ttk.Label(r, text="Refs(%)").pack(side="left")
            ent_refs = ttk.Entry(r, width=10)
            ent_refs.insert(0, self._axes_cfg[i]["refs"])
            ent_refs.pack(side="left", padx=(4,6))

            def _mk_upd(idx, combof, combom, comboys, entryrefs):
                def _upd(*_):
                    self._axes_cfg[idx]["field"]  = combof.get()
                    self._axes_cfg[idx]["mode"]   = combom.get()
                    self._axes_cfg[idx]["yscale"] = comboys.get()
                    self._axes_cfg[idx]["refs"]   = entryrefs.get()
                    self._draw_results_plots()
                return _upd

            upd = _mk_upd(i, cb_field, cb_mode, cb_ys, ent_refs)
            cb_field.bind("<<ComboboxSelected>>", upd)
            cb_mode.bind("<<ComboboxSelected>>", upd)
            cb_ys.bind("<<ComboboxSelected>>", upd)
            ent_refs.bind("<FocusOut>", upd)
            ent_refs.bind("<Return>", upd)

            self._subplot_cfg_rows.append((cb_field, cb_mode, cb_ys, ent_refs))

        # ---- Atualização automática ----
        frm_auto = ttk.LabelFrame(left, text="Atualização")
        frm_auto.pack(fill="x", pady=(6,8))
        ttk.Checkbutton(frm_auto, text="Atualização automática", variable=self.var_auto_update,
                        command=self._schedule_auto_update).pack(side="left", padx=(4,8))
        ttk.Label(frm_auto, text="Período (ms):").pack(side="left")
        ttk.Spinbox(frm_auto, from_=500, to=10000, increment=500, textvariable=self.var_update_period_ms, width=8,
                    command=self._schedule_auto_update).pack(side="left", padx=(4,8))
        ttk.Button(frm_auto, text="Atualizar agora", command=self._draw_results_plots).pack(side="left")

        # ---- Exportar figura ----
        frm_export = ttk.LabelFrame(left, text="Exportar")
        frm_export.pack(fill="x", pady=(6,8))
        ttk.Label(frm_export, text="DPI:").pack(side="left", padx=(6,4))
        self.var_export_dpi = tk.IntVar(value=200)
        ttk.Spinbox(frm_export, from_=100, to=600, increment=50, textvariable=self.var_export_dpi, width=6).pack(side="left", padx=(0,8))
        ttk.Button(frm_export, text="Exportar figura…", command=self._export_results_fig).pack(side="left")
        # ---- Escala / Exportar ----
        frm_extras = ttk.LabelFrame(left, text="Escala e Exportação")
        frm_extras.pack(fill="x", pady=(6,8))

        # Escala log no X
        ttk.Checkbutton(
            frm_extras, text="Escala log no eixo X",
            variable=self.var_xlog,
            command=self._draw_results_plots
        ).pack(fill="x", padx=4, pady=(2,6))

        # Exportar figura
        fexp = ttk.Frame(frm_extras); fexp.pack(fill="x", pady=(2,4))
        ttk.Label(fexp, text="Formato:").pack(side="left")
        ttk.Combobox(
            fexp, textvariable=self.var_export_fmt,
            values=["PNG","SVG","PDF"], width=6, state="readonly"
        ).pack(side="left", padx=(4,8))
        ttk.Label(fexp, text="DPI:").pack(side="left")
        ttk.Spinbox(
            fexp, from_=72, to=600, increment=10, width=6,
            textvariable=self.var_export_dpi
        ).pack(side="left", padx=(4,8))
        #ttk.Button(fexp, text="Exportar figura…", command=self._export_results_figure).pack(side="left")

        # ---- Linhas de referência (globais) ----
        frm_refs = ttk.LabelFrame(left, text="Linhas de referência (todas as subfiguras)")
        frm_refs.pack(fill="x", pady=(6,8))

        ref_row = ttk.Frame(frm_refs); ref_row.pack(fill="x", pady=(2,4))
        ttk.Label(ref_row, text="x=").pack(side="left")
        self._ref_x_entry = ttk.Entry(ref_row, width=10)
        self._ref_x_entry.pack(side="left", padx=(4,8))
        ttk.Label(ref_row, text="rótulo:").pack(side="left")
        self._ref_label_entry = ttk.Entry(ref_row, width=18)
        self._ref_label_entry.pack(side="left", padx=(4,8))
        ttk.Button(ref_row, text="Adicionar", command=self._ref_add).pack(side="left")

        # lista de linhas
        list_frame = ttk.Frame(frm_refs); list_frame.pack(fill="x", pady=(2,4))
        self.lb_refs = tk.Listbox(list_frame, height=5, selectmode="extended")
        self.lb_refs.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(list_frame, orient="vertical", command=self.lb_refs.yview)
        sb2.pack(side="right", fill="y")
        self.lb_refs.config(yscrollcommand=sb2.set)

        btns = ttk.Frame(frm_refs); btns.pack(fill="x")
        ttk.Button(btns, text="Remover selecionadas", command=self._ref_remove).pack(side="left")
        ttk.Button(btns, text="Aplicar (redesenhar)", command=self._draw_results_plots).pack(side="left", padx=(6,0))

        # ---- Figura de resultados (matplotlib)
        self.fig_res = plt.figure(figsize=(7.8, 6.2))
        self.canvas_res = FigureCanvasTkAgg(self.fig_res, master=right)
        self.canvas_res.get_tk_widget().pack(fill="both", expand=True)

        self._draw_results_plots()
        self._schedule_auto_update()

    # ---------------- YAML root ----------------
    def _current_yaml(self) -> dict:
        general = {
            "seed": int(self.var_seed.get()),
            "num_snapshots": int(self.var_snaps.get()),
            "overwrite_output": bool(self.var_overwrite.get()),
            "output_dir": str(self.var_outdir.get()),
            "output_dir_prefix": str(self.var_prefix.get()),
            "system": str(self.var_system.get()),
            "imt_link": str(self.var_imt_link.get()),
            "enable_adjacent_channel": bool(self.var_adj.get()),
            "enable_cochannel": bool(self.var_coch.get()),
        }

        topo_type = str(self.topo_type.get())

        topology = {
            "central_latitude": self._num_or_str(self.topo_c_lat.get()),
            "central_longitude": self._num_or_str(self.topo_c_lon.get()),
            "central_altitude": self._num_or_str(self.topo_c_alt.get()),
            "type": topo_type,
        }

        if topo_type == "Macro_countries":
            country_names = [c.strip() for c in self.txt_countries.get("1.0", "end").splitlines() if c.strip()]

            enc_ui = (self.topo_raster_enc.get() or "").strip()
            # Se "Uniforme": raster vazio (None). Se "Denspop": usa caminho.
            if enc_ui == "Uniforme":
                pop_raster = ''
                raster_encoding = None  # opcional: pode omitir essa chave
            else:
                pop_raster = self.path_raster.get().strip() or None
                raster_encoding = "indexed"  # se quiser explicitar no YAML

            topology["macrocell_countries"] = {
                "country_names": country_names,
                "num_bs_total": int(self._num_or_str(self.topo_num_bs.get())),
                "cell_radius": self._num_or_str(self.topo_cell_radius.get()),
                "rng_seed": int(self._num_or_str(self.topo_rng.get())),
                "dist_type": self.topo_dist_type.get(),
                "countries_shapefile": self.path_shp.get().strip() or None,
                "population_raster": pop_raster,
            }
            # Se quiser incluir raster_encoding somente quando Denspop:
            if raster_encoding is not None:
                topology["macrocell_countries"]["raster_encoding"] = raster_encoding

        elif topo_type == "MACROCELL":
            topology["macrocell"] = {
                "intersite_distance": self._num_or_str(self.macro_intersite.get()),
                "wrap_around": bool(self.macro_wrap.get()),
                "num_clusters": int(self._num_or_str(self.macro_clusters.get())),
            }

        elif topo_type == "HOTSPOT":
            topology["hotspot"] = {
                "intersite_distance": self._num_or_str(self.hotspot_intersite.get()),
                "wrap_around": bool(self.hotspot_wrap.get()),
                "num_clusters": int(self._num_or_str(self.hotspot_clusters.get())),
                "num_hotspots_per_cell": int(self._num_or_str(self.hotspot_num_per_cell.get())),
                "max_dist_hotspot_ue": self._num_or_str(self.hotspot_max_dist_ue.get()),
                "min_dist_bs_hotspot": self._num_or_str(self.hotspot_min_dist_bs.get()),
            }

        elif topo_type == "SINGLE_BS":
            # azimuth: interpreta "0,120,240" como lista; vazio -> None/string
            az_text = (self.sbs_azimuth.get() or "").strip()
            if az_text == "":
                sbs_az = None
            else:
                try:
                    sbs_az = [float(x.strip()) for x in az_text.split(",")]
                except Exception:
                    sbs_az = az_text  # deixa string literal se quiser usar placeholder

            topology["single_bs"] = {
                "intersite_distance": self._num_or_str(self.sbs_intersite.get()),
                "cell_radius": self._num_or_str(self.sbs_cell_radius.get()),
                "num_clusters": int(self._num_or_str(self.sbs_clusters.get())),
                "azimuth": sbs_az,
            }

        ue_array = {
            "normalization": bool(self.ue_norm.get()),
            "element_pattern": self.ue_elem_pat.get(),
            "minimum_array_gain": self._num_or_str(self.ue_min_arr_gain.get()),
            "element_max_g": self._num_or_str(self.ue_elem_max_g.get()),
            "element_phi_3db": self._num_or_str(self.ue_phi3.get()),
            "element_theta_3db": self._num_or_str(self.ue_theta3.get()),
            "n_rows": self._num_or_str(self.ue_rows.get()),
            "n_columns": self._num_or_str(self.ue_cols.get()),
            "element_am": self._num_or_str(self.ue_elem_am.get()),
            "element_sla_v": self._num_or_str(self.ue_elem_sla_v.get()),
            "multiplication_factor": self._num_or_str(self.ue_mult.get()),
        }

        # Sub-array opcional
        if bool(self.ue_sub_enabled.get()):
            ue_array["subarray"] = {
                "is_enabled": True,
                "n_rows": self._num_or_str(self.ue_sub_rows.get()),
                "element_vert_spacing": self._num_or_str(self.ue_sub_evspace.get()),
                "eletrical_downtilt": self._num_or_str(self.ue_sub_e_downtilt.get()),
            }

        # Agora sim: coloca o array dentro de "antenna"
        ue_block = {
            "k": int(self._num_or_str(self.ue_k.get())),
            "k_m": int(self._num_or_str(self.ue_km.get())),
            "indoor_percent": self._num_or_str(self.ue_indoor.get()),
            "distribution_type": self.ue_dist_type.get(),
            "tx_power_control": bool(self.ue_tx_power_ctrl.get()),
            "p_o_pusch": self._num_or_str(self.ue_p_o_pusch.get()),
            "alpha": self._num_or_str(self.ue_alpha.get()),
            "p_cmax": self._num_or_str(self.ue_p_cmax.get()),
            "power_dynamic_range": self._num_or_str(self.ue_p_dyn.get()),
            "height": self._num_or_str(self.ue_height.get()),
            "noise_figure": self._num_or_str(self.ue_nf.get()),
            "ohmic_loss": self._num_or_str(self.ue_ohmic.get()),         
            "body_loss": self._num_or_str(self.ue_body_loss.get()),
            "antenna": {"array": ue_array},
        }


        # Só inclui distribution_distance/azimuth se ANGLE_AND_DISTANCE
        if self.ue_dist_type.get().upper() == "ANGLE_AND_DISTANCE":
            ue_block["distribution_distance"] = self.ue_dist_distance.get()
            ue_block["distribution_azimuth"]  = self.ue_dist_azimuth.get()

        imt = {
            "minimum_separation_distance_bs_ue": self._num_or_str(self.imt_min_sep.get()),
            "interfered_with": bool(self.imt_interfered.get()),
            "frequency": self._num_or_str(self.imt_freq.get()),
            "bandwidth": self._num_or_str(self.imt_bw.get()),
            "rb_bandwidth": self._num_or_str(self.imt_rb_bw.get()),
            "spectral_mask": self.imt_spec_mask.get(),
            "spurious_emissions": self._num_or_str(self.imt_spurious.get()),
            "adjacent_antenna_model": self.imt_adj_ant_model.get(),
            "guard_band_ratio": self._num_or_str(self.imt_guard_ratio.get()),
            "topology": topology,
            "bs": {
                "load_probability": self._num_or_str(self.bs_load_prob.get()),
                "conducted_power": self._num_or_str(self.bs_power.get()),
                "height": self._num_or_str(self.bs_height.get()),
                "noise_figure": self._num_or_str(self.bs_nf.get()),
                "ohmic_loss": self._num_or_str(self.bs_ohmic.get()),
                "antenna": {
                    "array": {
                        "normalization": bool(self.bs_norm.get()),
                        "element_pattern": self.bs_elem_pat.get(),
                        "minimum_array_gain": self._num_or_str(self.bs_min_arr_gain.get()),
                        "horizontal_beamsteering_range": [self._num_or_str(self.bs_h_steer[0].get()), self._num_or_str(self.bs_h_steer[1].get())],
                        "vertical_beamsteering_range": [self._num_or_str(self.bs_v_steer[0].get()), self._num_or_str(self.bs_v_steer[1].get())],
                        "downtilt": self._num_or_str(self.bs_downtilt.get()),
                        "element_max_g": self._num_or_str(self.bs_elem_max_g.get()),
                        "element_phi_3db": self._num_or_str(self.bs_phi3.get()),
                        "element_theta_3db": self._num_or_str(self.bs_theta3.get()),
                        "n_rows": self._num_or_str(self.bs_rows.get()),
                        "n_columns": self._num_or_str(self.bs_cols.get()),
                        "element_horiz_spacing": self._num_or_str(self.bs_elem_hs.get()),
                        "element_vert_spacing": self._num_or_str(self.bs_elem_vs.get()),
                        "element_am": self._num_or_str(self.bs_elem_am.get()),
                        "element_sla_v": self._num_or_str(self.bs_elem_sla_v.get()),
                        "multiplication_factor": self._num_or_str(self.bs_mult.get()),
                        "subarray": {
                            "is_enabled": bool(self.bs_sub_enabled.get()),
                            "n_rows": self._num_or_str(self.bs_sub_rows.get()),
                            "element_vert_spacing": self._num_or_str(self.bs_sub_evspace.get()),
                            "eletrical_downtilt": self._num_or_str(self.bs_sub_e_downtilt.get()),
                        }
                    }
                }
            },
            "ue": ue_block,
            "uplink": {
                "attenuation_factor": self._num_or_str(self.ul_att.get()),
                "sinr_min": self._num_or_str(self.ul_sinr_min.get()),
                "sinr_max": self._num_or_str(self.ul_sinr_max.get()),
            },
            "downlink": {
                "attenuation_factor": self._num_or_str(self.dl_att.get()),
                "sinr_min": self._num_or_str(self.dl_sinr_min.get()),
                "sinr_max": self._num_or_str(self.dl_sinr_max.get()),
            },
            "channel_model": self.ch_model.get(),
            "shadowing": bool(self.shadowing.get()),
        }

        single_space_station = {
            "frequency": self._num_or_str(self.v_freq.get()),
            "bandwidth": self._num_or_str(self.v_bw.get()),
            "tx_power_density": self._num_or_str(self.v_txpsd.get()),
            "polarization_loss": self._num_or_str(self.v_pol_loss.get()),
            "noise_temperature": self._num_or_str(self.v_tnoise.get()),
            "channel_model": self.v_ch_model.get(),
            "is_global_coordinate_system": bool(self.ss_is_global_cs.get()),
            "season": self.v_season.get(),
            "param_p619": {
                "mean_clutter_height": self.v_p619_clutter.get(),
                "below_rooftop": self._num_or_str(self.v_p619_below_rooftop.get()),
            },
            "geometry": {
                # Spacecraft FIXED
                "altitude": self._num_or_str(self.v_alt.get()),
                "location": {
                    "type": "FIXED",
                    "fixed": {"lat_deg": self._num_or_str(self.v_fix_lat.get()), "long_deg": self._num_or_str(self.v_fix_lon.get())}
                },
                # ES (reference)
                "es_altitude": self._num_or_str(self.v_es_alt.get()),
                "es_lat_deg": self._num_or_str(self.v_es_lat.get()),
                "es_long_deg": self._num_or_str(self.v_es_lon.get()),
                # Pointing types (export only; viz usa spacecraft->ES)
                "azimuth": {"type": self.v_az_type.get()},
                "elevation": {"type": self.v_el_type.get()},
            },
            "antenna": {
                "pattern": self.v_ant_pattern.get(),
                "gain": self._num_or_str(self.v_ant_gain.get()),
                "itu_r_s_672": ({
                    "antenna_3_dB": self._num_or_str(self.v_s672_3db.get()),
                    "antenna_l_s": self._num_or_str(self.v_s672_ls.get()),
                } if self.v_ant_pattern.get()=="ITU-R S.672" else None)
            }
        }
        if single_space_station["antenna"]["itu_r_s_672"] is None:
            del single_space_station["antenna"]["itu_r_s_672"]

        return {"general": general, "imt": imt, "single_space_station": single_space_station}

    # ---------------- preview 3D ----------------
    def _draw_country_borders(self):
        """Draw country borders from a shapefile onto the globe."""
        if not self.show_borders.get() or not HAS_PYSHP:
            return
        shp_path = self.path_shp.get()
        if not os.path.isfile(shp_path):
            return
        try:
            r = pyshp.Reader(shp_path)
            for sr in r.shapeRecords():
                shp = sr.shape
                pts = shp.points
                if not pts:
                    continue
                parts = list(shp.parts) + [len(pts)]
                for i in range(len(parts) - 1):
                    sub = pts[parts[i]:parts[i+1]]
                    if len(sub) < 2:
                        continue
                    lons = [p[0] for p in sub]
                    lats = [p[1] for p in sub]
                    x, y, z = lla_to_ecef(lats, lons, 0.0)
                    self.ax3d.plot(x, y, z, lw=0.35, color="k", alpha=0.55, zorder=5, antialiased=True)
        except Exception:
            pass

    def _draw_preview_3d(self):
        import numpy as np
        from matplotlib import cm, colors
        topo_type = (self.topo_type.get() or "").strip()
        self.ax3d.cla()
        if topo_type == "Macro_countries":
            # Terra – grid esférico
            a = WGS84_A * 0.98
            u = np.linspace(0, 2*np.pi, 720)
            v = np.linspace(0, np.pi, 360)
            X = a*np.outer(np.cos(u), np.sin(v))
            Y = a*np.outer(np.sin(u), np.sin(v))
            Z = a*np.outer(np.ones_like(u), np.cos(v))

            # Posição do Spacecraft e Earth Station (alvo de boresight)
            ss_alt = self._num_or_str(self.v_alt.get())
            ss_lat = self._num_or_str(self.v_fix_lat.get())
            ss_lon = self._num_or_str(self.v_fix_lon.get())
            es_alt = self._num_or_str(self.v_es_alt.get())
            es_lat = self._num_or_str(self.v_es_lat.get())
            es_lon = self._num_or_str(self.v_es_lon.get())

            sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)
            ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)  # Earth Station (boresight alvo)

            show_map = bool(self.var_show_gainmap.get())

            if show_map:
                # ---------- Linha de Visada (LoS) ----------
                # Condição de visibilidade do ponto P (X,Y,Z) a partir de S=(sx,sy,sz):
                # LoS <=> S•P > a^2   (produto escalar com raio ao ponto)
                # Usa tolerância pequena para estabilidade numérica
                dotSP = X * sx + Y * sy + Z * sz
                los_mask = dotSP > (a*a * (1.0 + 1e-12))

                # ---------- Vetores para off-axis ----------
                # boresight: S -> ES
                b = np.array([ex - sx, ey - sy, ez - sz], dtype=float)
                b /= np.linalg.norm(b)

                RX = X - sx
                RY = Y - sy
                RZ = Z - sz
                Rnorm = np.sqrt(RX*RX + RY*RY + RZ*RZ)
                RX /= Rnorm; RY /= Rnorm; RZ /= Rnorm

                # Ângulo off-axis (graus) = arccos( dot(R_hat, b_hat) )
                cospsi = RX*b[0] + RY*b[1] + RZ*b[2]
                cospsi = np.clip(cospsi, -1.0, 1.0)
                psi_deg = np.degrees(np.arccos(cospsi))  # (nu x nv)

                # ---------- Ganho S.672 ----------
                ant = self._make_s672_antenna()
                gain = ant.calculate_gain(off_axis_angle_vec=psi_deg.ravel()).reshape(psi_deg.shape)

                # Onde NÃO há LoS, ganho = -inf (como você pediu)
                gain = gain.astype(float, copy=True)
                gain[~los_mask] = -np.inf

                # ---------- Normalização de cores (ignora -inf) ----------
                try:
                    vmin_txt = (self.var_gain_vmin.get() or "auto").strip().lower()
                    vmax_txt = (self.var_gain_vmax.get() or "auto").strip().lower()
                except Exception:
                    vmin_txt, vmax_txt = "auto", "auto"

                # valores finitos para definir escala
                finite = np.isfinite(gain)
                if vmin_txt in ("auto","") or vmax_txt in ("auto",""):
                    if finite.any():
                        gfinite = gain[finite]
                        auto_vmin = float(np.nanmin(gfinite))
                        auto_vmax = float(np.nanmax(gfinite))
                    else:
                        # fallback seguro
                        auto_vmin, auto_vmax = 0.0, 1.0
                vmin = auto_vmin if (vmin_txt in ("auto","")) else float(vmin_txt)
                vmax = auto_vmax if (vmax_txt in ("auto","")) else float(vmax_txt)
                if vmin >= vmax:
                    vmax = vmin + 1.0

                norm = colors.Normalize(vmin=vmin, vmax=vmax)

                # Mapeia cores; pontos sem LoS ficam transparentes (alpha=0)
                facecolors = cm.viridis(norm(np.where(np.isfinite(gain), gain, vmin)))
                alpha = np.where(los_mask, 1.0, 0.0)
                facecolors[..., -1] = facecolors[..., -1] * alpha

                # ---------- Desenha superfície colorida (opaca onde há LoS) ----------
                self.ax3d.plot_surface(
                    X, Y, Z,
                    rstride=6, cstride=6,
                    facecolors=facecolors,
                    linewidth=0,
                    antialiased=False,
                    shade=False,
                    zorder=1
                )

                # Colorbar (baseada só nos finitos)
                mappable = cm.ScalarMappable(norm=norm, cmap=cm.viridis)
                mappable.set_array([])
                if hasattr(self, "_gain_cbar") and self._gain_cbar:
                    try:
                        self._gain_cbar.remove()
                    except Exception:
                        pass
                self._gain_cbar = self.fig3d.colorbar(mappable, ax=self.ax3d, shrink=0.8, pad=0.02)
                self._gain_cbar.set_label("Ganho (dBi)")

            else:
                # Terra opaca em cor sólida
                self.ax3d.plot_surface(
                    X, Y, Z,
                    rstride=6, cstride=6,
                    color="#dbe7ff",
                    alpha=1.0,
                    edgecolor="none",
                    zorder=1
                )
                if hasattr(self, "_gain_cbar") and self._gain_cbar:
                    try:
                        self._gain_cbar.remove()
                    except Exception:
                        pass
                    self._gain_cbar = None

            # Contornos (se você tiver essa função)
            self._draw_country_borders()

            # COUNTRIES preview (se aplicável)
            if HAS_TOPO and TopologyCountries and ParametersCountries:
                population_shp = "" if self.topo_raster_enc.get() == "Uniforme" else (self.path_raster.get().strip() or "")
                try:
                    countries = [c.strip() for c in self.txt_countries.get("1.0","end").splitlines() if c.strip()]
                    params = ParametersCountries(
                        country_names=countries,
                        num_bs_total=int(float(self.topo_num_bs.get())),
                        rng_seed=int(float(self.topo_rng.get())),
                        cell_radius=float(self.topo_cell_radius.get()),
                        countries_shapefile=self.path_shp.get(),
                        population_raster=population_shp,
                        raster_encoding=self.raster_encoding.get(),
                        sedac_palette_mode=self.sedac_mode.get(),
                        sedac_min=float(self.sedac_min.get()),
                        sedac_max=float(self.sedac_max.get()),
                        pixel_area_method=self.pixel_area_method.get(),
                        dist_type=self.topo_dist_type.get(),
                        fixed_azimuth=None,
                    )
                    geoconv = GeometryConverter()
                    geoconv.set_reference(float(self.topo_c_lat.get()), float(self.topo_c_lon.get()), float(self.topo_c_alt.get()))
                    topo = TopologyCountries(params, geoconv).calculate_coordinates()
                    x, y, z = lla_to_ecef(topo.lats, topo.lons, np.zeros_like(topo.lats) + 500)
                    self.ax3d.scatter(x, y, z, c="tab:red", s=6, depthshade=False, label="BS (countries)", zorder=10)
                except Exception as e:
                    messagebox.showwarning("Preview Countries", f"Falha ao renderizar COUNTRIES:\n{e}")

            # Marcadores de Spacecraft e Earth Station
            try:
                # Spacecraft
                self.ax3d.scatter([sx],[sy],[sz], c="tab:purple", s=60, marker="^", depthshade=False, label="Spacecraft (FIXED)", zorder=7)
                # Earth Station
                self.ax3d.scatter([ex],[ey],[ez], c="tab:blue", s=24, marker="o", depthshade=False, label="Earth Station", zorder=7)
                # Link/boresight (S -> ES)
                self.ax3d.plot([sx, ex], [sy, ey], [sz, ez], color="tab:purple", lw=1.6, alpha=0.9, label="Pointing to ES", zorder=6)
            except Exception:
                pass

            # Caixa/labels
            R = WGS84_A + 4.0e7/6.0
            self.ax3d.set_xlim([-R, R]); self.ax3d.set_ylim([-R, R]); self.ax3d.set_zlim([-R, R])
            self.ax3d.set_box_aspect([1,1,1])
            self.ax3d.set_xlabel("X [m]"); self.ax3d.set_ylabel("Y [m]"); self.ax3d.set_zlabel("Z [m]")
            self.ax3d.legend(loc="upper right")
            self.fig3d.tight_layout()
            self.canvas3d.draw()
            return
        try:
            import matplotlib as mpl
            # um quadradão default; limites serão ajustados depois
            grid = np.linspace(-1, 1, 2)
            Xg, Yg = np.meshgrid(grid, grid)
            Zg = np.zeros_like(Xg)
            # só para dar referência: linhas do contorno
            # (opcional: manter vazio e só usar posts/“pizzas”)
        except Exception:
            pass

        # --- Seleção de topologia e cálculo das coordenadas (usa suas classes)
        xs = ys = azs = None
        cell_radius = None
        bs_height = float(self._num_or_str(self.bs_height.get()) or 18.0)  # altura da BS (m)

        if topo_type == "MACROCELL":
            from sharc.topology.topology_macrocell import TopologyMacrocell
            d = float(self._num_or_str(self.macro_intersite.get()) or 1500.0)
            nc = int(self._num_or_str(self.macro_clusters.get()) or 1)
            topo = TopologyMacrocell(d, nc)
            topo.calculate_coordinates()  # fornece self.x, self.y, self.azimuth

            xs = np.asarray(topo.x)
            ys = np.asarray(topo.y)
            azs = np.asarray(topo.azimuth)

            # Raio do hex (padrão que você indicou)
            r = d / 3.0

            # Altura do "postinho"
            bs_height = float(self._num_or_str(self.bs_height.get()) or 18.0)

            # Desenha os hexágonos (arestas) como no seu plot 2D
            all_x, all_y = [], []
            for x, y, az in zip(xs, ys, azs):
                se = [[x, y]]
                angle = int(az - 60)
                for _ in range(6):
                    se.append([
                        se[-1][0] + r * math.cos(math.radians(angle)),
                        se[-1][1] + r * math.sin(math.radians(angle)),
                    ])
                    angle += 60
                # Arestas em z=0 (sem fill)
                self._add_polyline3d(self.ax3d, se, z=0.0, color="k", lw=1.0)
                all_x.append(x); all_y.append(y)

            # Macro cell base stations (pontos)
            self.ax3d.scatter(xs, ys, np.zeros_like(xs), color="k", s=18, depthshade=False)

            # Postinhos (mastros)
            for x, y in zip(xs, ys):
                self._draw_bs_post(self.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

            # Escala igual em x,y,z (mastros ficam "baixos")
            self._set_equal_3d(self.ax3d, np.array(all_x), np.array(all_y), z_top=bs_height, margin=0.12)

            self.ax3d.set_xlabel("x [m]")
            self.ax3d.set_ylabel("y [m]")
            self.ax3d.set_zlabel("z [m]  (altura)")
            self.ax3d.set_title("Topologia: MACROCELL (hexágonos + mastros)")
            self.canvas3d.draw_idle()

            return

        elif topo_type == "SINGLE_BS":
            from sharc.topology.topology_single_base_station import TopologySingleBaseStation  # :contentReference[oaicite:5]{index=5}
            cr = float(self._num_or_str(self.sbs_cell_radius.get()) or 100.0)
            nc = int(self._num_or_str(self.sbs_clusters.get()) or 1)

            # azimute: aceita lista "0,120,240" ou string/literal
            az_text = (self.sbs_azimuth.get() or "").strip()
            if az_text == "":
                az_param = None
            else:
                try:
                    az_param = [float(x.strip()) for x in az_text.split(",")]
                except Exception:
                    az_param = az_text  # pode ser "random"
            topo = TopologySingleBaseStation(cr, nc, azimuth=az_param)
            topo.calculate_coordinates()  # gera x,y,azimuth  :contentReference[oaicite:6]{index=6}
            xs, ys, azs = topo.x, topo.y, topo.azimuth
            cell_radius = cr  # usamos no desenho da “pizza”

        elif topo_type == "HOTSPOT":
            from sharc.topology.topology_hotspot import TopologyHotspot  # gera x,y,azimuth dos hotspots
            from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
            d  = float(self._num_or_str(self.hotspot_intersite.get()) or 1500.0)
            nc = int(self._num_or_str(self.hotspot_clusters.get()) or 1)

            p = ParametersHotspot()
            if self.hotspot_num_per_cell.get():
                p.num_hotspots_per_cell = int(self._num_or_str(self.hotspot_num_per_cell.get()))
            if self.hotspot_max_dist_ue.get():
                p.max_dist_hotspot_ue = float(self._num_or_str(self.hotspot_max_dist_ue.get()))
            if self.hotspot_min_dist_bs.get():
                p.min_dist_bs_hotspot = float(self._num_or_str(self.hotspot_min_dist_bs.get()))

            topo = TopologyHotspot(p, d, nc)
            topo.calculate_coordinates()  # <-- pode levantar o erro do loop infinito
            if topo.x.size == 0:
                messagebox.showwarning(
                    "Hotspot: parâmetros inviáveis",
                    "Loop infinito ao criar hotspots.\n\n"
                    "Tente reduzir 'num_hotspots_per_cell' ou aumentar 'intersite_distance'.\n\n"
                )
                return

            xs, ys, azs = np.asarray(topo.x), np.asarray(topo.y), np.asarray(topo.azimuth)
            cell_radius  = float(p.max_dist_hotspot_ue)
            bs_height    = float(self._num_or_str(self.bs_height.get()) or 18.0)

            # ---------- HEXÁGONOS DE REFERÊNCIA DO MACROCELL ----------
            # Se TopologyHotspot expõe o macrocell, usamos diretamente:
            macro = getattr(topo, "macrocell", None)
            if macro is not None and hasattr(macro, "x") and hasattr(macro, "y") and hasattr(macro, "azimuth"):
                mx, my, maz = np.asarray(macro.x), np.asarray(macro.y), np.asarray(macro.azimuth)
                # raio do hex conforme seu padrão: r = ISD/3
                r_hex = d / 3.0
                # desenha hex exatamente com o algoritmo incremental do seu plot 2D
                for x0, y0, az0 in zip(mx, my, maz):
                    se = [[x0, y0]]
                    angle = int(az0 - 60)
                    for _ in range(6):
                        se.append([
                            se[-1][0] + r_hex * np.cos(np.radians(angle)),
                            se[-1][1] + r_hex * np.sin(np.radians(angle)),
                        ])
                        angle += 60
                    self._add_polyline3d(self.ax3d, se, z=0.0, color="0.25", lw=0.9)

            # ---------- HOTSPOTS (pontos) ----------
            self.ax3d.scatter(xs, ys, np.zeros_like(xs), color="g", edgecolors="w",
                            linewidths=0.5, s=18, depthshade=False)

            # ---------- COBERTURA (WEDGE: fill=False) ----------
            for xh, yh, a in zip(xs, ys, azs):
                self._add_wedge_outline3d(self.ax3d, xh, yh, cell_radius, a, half_bw_deg=60,
                                        color="green", lw=1.0)

            # ---------- POSTINHOS (mastros nos hotspots) ----------
            for xh, yh in zip(xs, ys):
                self._draw_bs_post(self.ax3d, xh, yh, bs_height, color="tab:blue", lw=2.0)

            # ---------- Limites e rótulos ----------
            if xs.size:
                self._set_equal_3d(self.ax3d, xs, ys, z_top=bs_height, margin=0.12)
            self.ax3d.set_xlabel("x [m]"); self.ax3d.set_ylabel("y [m]"); self.ax3d.set_zlabel("z [m] (altura)")
            self.ax3d.set_title("Topologia: HOTSPOT (hex macro + hotspots + wedges)")
            self.canvas3d.draw_idle()
            return


        else:
            # fallback seguro
            self.ax3d.text2D(0.05, 0.95, f"type '{topo_type}' não suportado no preview 3D", transform=self.ax3d.transAxes)
            self.canvas3d.draw_idle()
            return

        # --- Desenho: posts (mastros) e “pizzas” (quando aplicável)
        if xs is None or len(xs) == 0:
            self.ax3d.text2D(0.05, 0.95, "Sem coordenadas para desenhar.", transform=self.ax3d.transAxes)
            self.canvas3d.draw_idle()
            return

        xs = np.asarray(xs)
        ys = np.asarray(ys)
        if azs is None:
            azs = np.zeros_like(xs)
        else:
            azs = np.asarray(azs)

        # posts (um por BS)
        for x, y in zip(xs, ys):
            self._draw_bs_post(self.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

        # “pizzas” para HOTSPOT e SINGLE_BS (e opcionalmente para MACROCELL)
        if cell_radius is None:
            # nada a fazer
            pass
        else:
            # half beamwidth padrão de 60° como nos módulos 2D
            hbw = 60.0
            edge = "tab:green" if topo_type in ("HOTSPOT", "SINGLE_BS") else "0.6"
            for x, y, az in zip(xs, ys, azs):
                poly_xy = self._sector_polygon_xy(x, y, cell_radius, az, half_bw_deg=hbw)
                self._add_sector3d(self.ax3d, poly_xy, z=0.0, face_alpha=0.10, edge_color=edge)

        # --- Ajustes de limites/estética
        (xlim, ylim) = self._auto_xy_lim(xs, ys, margin=0.18)
        self.ax3d.set_xlim(xlim)
        self.ax3d.set_ylim(ylim)
        # eixo Z: um pouco acima da altura para sobrar espaço
        self.ax3d.set_zlim(0, max(1.0, bs_height) * 1.25)

        self.ax3d.set_xlabel("x [m]")
        self.ax3d.set_ylabel("y [m]")
        self.ax3d.set_zlabel("z [m]  (altura)")
        self.ax3d.set_title(f"Topologia: {topo_type} (preview 3D)")

        self.canvas3d.draw_idle()
    def _browse_shapefile(self):
                fn = filedialog.askopenfilename(
                    title="Escolher shapefile de países",
                    filetypes=[("Shapefile", "*.shp"), ("Todos os arquivos", "*.*")]
                )
                if fn:
                    self.path_shp.set(fn)

    def _browse_raster(self):
        fn = filedialog.askopenfilename(
            title="Escolher raster de população (SEDAC/GeoTIFF)",
            filetypes=[("GeoTIFF", "*.tif;*.tiff"), ("Todos os arquivos", "*.*")]
        )
        if fn:
            self.path_raster.set(fn)

    def _toggle_raster_by_encoding(self, *_):
        enc = (self.topo_raster_enc.get() or "").strip()
        if enc == "Uniforme":
            # desliga e limpa o raster
            self.path_raster.set("")
            self.ent_raster.configure(state="disabled")
            self.btn_raster.configure(state="disabled")
        else:
            # habilita para Denspop
            self.ent_raster.configure(state="normal")
            self.btn_raster.configure(state="normal")

    def _make_s672_antenna(self):
        """
        Constrói uma AntennaS672 a partir dos controles da UI (ganho de pico, L_s e 3 dB).
        """
        param = ParametersAntennaS672()
        # seus vars (ajuste os nomes se forem diferentes):
        # ganho de pico [dBi]
        param.antenna_gain = float(self.v_ant_gain.get())
        # largura de feixe 3 dB (atenção: o objeto original usa 'antenna_3_dB' ou 'antenna_3_dB_bw';
        # mapeie para 'antenna_3_dB' se necessário)
        param.antenna_3_dB = float(self.v_s672_3db.get())
        param.antenna_3_dB_bw = float(self.v_s672_3db.get())
        # L_s (-20, -25, -30 dB)
        param.antenna_l_s = float(self.v_s672_ls.get())
        return AntennaS672(param)

    def _zoom_preview_3d(self, factor):
        """Zoom no 3D: factor>1 dá zoom out; <1 dá zoom in."""
        try:
            # Preferível quando disponível (Matplotlib 3D antigo)
            if hasattr(self.ax3d, "dist"):
                self.ax3d.dist = max(1, float(self.ax3d.dist) * float(factor))
                self.canvas3d.draw_idle()
                return
        except Exception:
            pass

        # Fallback: escala limites X/Y/Z ao redor do centro (robusto)
        import numpy as np
        for getter, setter in [(self.ax3d.get_xlim3d, self.ax3d.set_xlim3d),
                            (self.ax3d.get_ylim3d, self.ax3d.set_ylim3d),
                            (self.ax3d.get_zlim3d, self.ax3d.set_zlim3d)]:
            lo, hi = getter()
            c = 0.5*(lo + hi)
            half = 0.5*(hi - lo)*factor
            setter(c - half, c + half)
        self.canvas3d.draw_idle()
    def _on_scroll_3d(self, event):
        """
        Zoom pelo scroll do mouse.
        - Windows/macOS: event.delta > 0 (zoom in), < 0 (zoom out)
        - Linux/X11: event.num == 4 (up -> in), 5 (down -> out)
        """
        # fator base (suave). maior => zoom mais “forte”
        base = 1.12
        direction = 0
        try:
            if hasattr(event, "num") and event.num in (4, 5):
                # Linux
                direction = -1 if event.num == 4 else 1
            else:
                # Windows/macOS
                direction = -1 if getattr(event, "delta", 0) > 0 else 1
        except Exception:
            direction = 1

        factor = (1.0 / base) if direction < 0 else base
        self._zoom_preview_3d(factor)

    # ---------------- Variáveis (General) ----------------
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

    def _var_remove(self):
        sel = self.var_table.selection()
        for iid in sel:
            self.var_table.delete(iid)

    def _collect_var_combos(self):
        names, lists = [], []
        for iid in self.var_table.get_children():
            name, vals = self.var_table.item(iid, "values")
            try:
                vlist = ast.literal_eval(vals)
                if not isinstance(vlist, (list, tuple)):
                    raise ValueError()
            except Exception:
                messagebox.showwarning("Variáveis", f"Valores inválidos para '{name}'. Use lista Python.")
                return None
            names.append(str(name))
            lists.append(list(vlist))
        if not names:
            return [{}]  # sem variáveis → apenas 1 combinação vazia
        combos = [dict(zip(names, prod)) for prod in itertools.product(*lists)]
        return combos

    # ---------------- YAML preview/save ----------------
    def _apply_variables_to_prefix(self, prefix: str, combo: dict) -> str:
        try:
            return prefix.format(**combo)
        except Exception:
            return prefix

    def _update_yaml_preview(self):
        root = self._current_yaml()
        text = build_yaml_text(root)
        self.txt_yaml.delete("1.0", tk.END)
        self.txt_yaml.insert(tk.END, text)

    def _save_yaml_dialog_multicombos(self):
        combos = self._collect_var_combos()
        if combos is None:
            return
        root = self._current_yaml()
        initdir = self.var_yaml_dir.get() or os.getcwd()
        os.makedirs(initdir, exist_ok=True)
        path = filedialog.asksaveasfilename(
            title="Escolha um nome (usaremos apenas a pasta selecionada)",
            defaultextension=".yaml",
            initialdir=initdir,
            initialfile=(self.var_prefix.get() or "scenario") + ".yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if not path:
            return
        outdir = os.path.dirname(path)
        os.makedirs(outdir, exist_ok=True)
        self._write_yaml_combos(root, outdir, combos)
        self.var_yaml_dir.set(outdir)
        messagebox.showinfo("OK", f"YAML(s) salvo(s) em:\n{outdir}")

    def _save_yaml_to_yamldir(self):
        combos = self._collect_var_combos()
        if combos is None:
            return
        root = self._current_yaml()
        outdir = self.var_yaml_dir.get() or "."
        os.makedirs(outdir, exist_ok=True)
        self._write_yaml_combos(root, outdir, combos)
        messagebox.showinfo("OK", f"YAML(s) gerado(s) em:\n{outdir}")

    def _write_yaml_combos(self, root, outdir, combos):
        base_prefix = root["general"]["output_dir_prefix"] or "scenario"
        for combo in combos:
            # aplica placeholders no prefix do arquivo
            prefix = self._apply_variables_to_prefix(base_prefix, combo)
            # aplica placeholders em TODO o dicionário (strings apenas)
            root_fmt = self._deep_format(root, combo)
            text = build_yaml_text(root_fmt)
            path = os.path.join(outdir, f"{prefix}.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def _save_image_3d(self):
        suggested = f"topology3d_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            title="Salvar imagem",
            defaultextension=".png",
            initialfile=suggested,
            filetypes=[("PNG", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        self.fig3d.savefig(path, dpi=180, bbox_inches="tight")
        messagebox.showinfo("OK", f"Imagem salva em:\n{path}")

    # ---------------- Save/Load sections ----------------
    def _save_imt_config(self):
        data = {
            "imt_min_sep": self.imt_min_sep.get(),
            "imt_interfered": self.imt_interfered.get(),
            "imt_freq": self.imt_freq.get(),
            "imt_bw": self.imt_bw.get(),
            "imt_rb_bw": self.imt_rb_bw.get(),
            "imt_spec_mask": self.imt_spec_mask.get(),
            "imt_spurious": self.imt_spurious.get(),
            "imt_adj_ant_model": self.imt_adj_ant_model.get(),
            "imt_guard_ratio": self.imt_guard_ratio.get(),
            "topo_c_lat": self.topo_c_lat.get(),
            "topo_c_lon": self.topo_c_lon.get(),
            "topo_c_alt": self.topo_c_alt.get(),
            "topo_type": self.topo_type.get(),
            "topo_dist_type": self.topo_dist_type.get(),
            "topo_num_bs": self.topo_num_bs.get(),
            "topo_cell_radius": self.topo_cell_radius.get(),
            "topo_rng": self.topo_rng.get(),
            "countries": self.txt_countries.get("1.0","end"),
            "path_shp": self.path_shp.get(),
            "path_raster": self.path_raster.get(),
            "raster_encoding": self.raster_encoding.get(),
            "sedac_mode": self.sedac_mode.get(),
            "sedac_min": self.sedac_min.get(),
            "sedac_max": self.sedac_max.get(),
            "pixel_area_method": self.pixel_area_method.get(),
            # BS
            "bs_load_prob": self.bs_load_prob.get(),
            "bs_power": self.bs_power.get(),
            "bs_height": self.bs_height.get(),
            "bs_nf": self.bs_nf.get(),
            "bs_ohmic": self.bs_ohmic.get(),
            "bs_norm": self.bs_norm.get(),
            "bs_elem_pat": self.bs_elem_pat.get(),
            "bs_min_arr_gain": self.bs_min_arr_gain.get(),
            "bs_downtilt": self.bs_downtilt.get(),
            "bs_elem_max_g": self.bs_elem_max_g.get(),
            "bs_phi3": self.bs_phi3.get(),
            "bs_theta3": self.bs_theta3.get(),
            "bs_rows": self.bs_rows.get(),
            "bs_cols": self.bs_cols.get(),
            "bs_elem_hs": self.bs_elem_hs.get(),
            "bs_elem_vs": self.bs_elem_vs.get(),
            "bs_elem_am": self.bs_elem_am.get(),
            "bs_elem_sla_v": self.bs_elem_sla_v.get(),
            "bs_mult": self.bs_mult.get(),
            "bs_sub_enabled": self.bs_sub_enabled.get(),
            "bs_sub_rows": self.bs_sub_rows.get(),
            "bs_sub_evspace": self.bs_sub_evspace.get(),
            "bs_sub_e_downtilt": self.bs_sub_e_downtilt.get(),
            # UE
            "ue_k": self.ue_k.get(),
            "ue_km": self.ue_km.get(),
            "ue_indoor": self.ue_indoor.get(),
            "ue_dist_type": self.ue_dist_type.get(),
            "ue_tx_power_ctrl": self.ue_tx_power_ctrl.get(),
            "ue_p_o_pusch": self.ue_p_o_pusch.get(),
            "ue_alpha": self.ue_alpha.get(),
            "ue_p_cmax": self.ue_p_cmax.get(),
            "ue_p_dyn": self.ue_p_dyn.get(),
            "ue_height": self.ue_height.get(),
            "ue_nf": self.ue_nf.get(),
            "ue_ohmic": self.ue_ohmic.get(),
            "ue_body_loss": self.ue_body_loss.get(),
            "ue_norm": self.ue_norm.get(),
            "ue_elem_pat": self.ue_elem_pat.get(),
            "ue_min_arr_gain": self.ue_min_arr_gain.get(),
            "ue_elem_max_g": self.ue_elem_max_g.get(),
            "ue_phi3": self.ue_phi3.get(),
            "ue_theta3": self.ue_theta3.get(),
            "ue_rows": self.ue_rows.get(),
            "ue_cols": self.ue_cols.get(),
            "ue_elem_am": self.ue_elem_am.get(),
            "ue_elem_sla_v": self.ue_elem_sla_v.get(),
            "ue_mult": self.ue_mult.get(),
            # UL/DL
            "ul_att": self.ul_att.get(),
            "ul_sinr_min": self.ul_sinr_min.get(),
            "ul_sinr_max": self.ul_sinr_max.get(),
            "dl_att": self.dl_att.get(),
            "dl_sinr_min": self.dl_sinr_min.get(),
            "dl_sinr_max": self.dl_sinr_max.get(),
            "ch_model": self.ch_model.get(),
            "shadowing": self.shadowing.get(),
        }
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], initialfile="imt_config.json")
        if not path: return
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        messagebox.showinfo("IMT", f"Configuração salva em:\n{path}")

    def _load_imt_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path: return
        with open(path, "r", encoding="utf-8") as f: vals = json.load(f)
        def S(name, var):
            if name in vals:
                try: var.set(vals[name])
                except: pass
        for k, v in vals.items():
            # generic assign where possible
            pass
        S("imt_min_sep", self.imt_min_sep); S("imt_interfered", self.imt_interfered)
        S("imt_freq", self.imt_freq); S("imt_bw", self.imt_bw); S("imt_rb_bw", self.imt_rb_bw)
        S("imt_spec_mask", self.imt_spec_mask); S("imt_spurious", self.imt_spurious)
        S("imt_adj_ant_model", self.imt_adj_ant_model); S("imt_guard_ratio", self.imt_guard_ratio)
        S("topo_c_lat", self.topo_c_lat); S("topo_c_lon", self.topo_c_lon); S("topo_c_alt", self.topo_c_alt)
        S("topo_type", self.topo_type); S("topo_dist_type", self.topo_dist_type)
        S("topo_num_bs", self.topo_num_bs); S("topo_cell_radius", self.topo_cell_radius); S("topo_rng", self.topo_rng)
        if "countries" in vals:
            self.txt_countries.delete("1.0","end"); self.txt_countries.insert("1.0", vals["countries"])
        S("path_shp", self.path_shp); S("path_raster", self.path_raster)
        S("raster_encoding", self.raster_encoding); S("sedac_mode", self.sedac_mode)
        S("sedac_min", self.sedac_min); S("sedac_max", self.sedac_max); S("pixel_area_method", self.pixel_area_method)
        # BS
        S("bs_load_prob", self.bs_load_prob); S("bs_power", self.bs_power); S("bs_height", self.bs_height)
        S("bs_nf", self.bs_nf); S("bs_ohmic", self.bs_ohmic); S("bs_norm", self.bs_norm)
        S("bs_elem_pat", self.bs_elem_pat); S("bs_min_arr_gain", self.bs_min_arr_gain)
        S("bs_downtilt", self.bs_downtilt); S("bs_elem_max_g", self.bs_elem_max_g)
        S("bs_phi3", self.bs_phi3); S("bs_theta3", self.bs_theta3)
        S("bs_rows", self.bs_rows); S("bs_cols", self.bs_cols)
        S("bs_elem_hs", self.bs_elem_hs); S("bs_elem_vs", self.bs_elem_vs)
        S("bs_elem_am", self.bs_elem_am); S("bs_elem_sla_v", self.bs_elem_sla_v)
        S("bs_mult", self.bs_mult); S("bs_sub_enabled", self.bs_sub_enabled)
        S("bs_sub_rows", self.bs_sub_rows); S("bs_sub_evspace", self.bs_sub_evspace)
        S("bs_sub_e_downtilt", self.bs_sub_e_downtilt)
        # UE
        S("ue_k", self.ue_k); S("ue_km", self.ue_km); S("ue_indoor", self.ue_indoor); S("ue_dist_type", self.ue_dist_type)
        S("ue_tx_power_ctrl", self.ue_tx_power_ctrl); S("ue_p_o_pusch", self.ue_p_o_pusch)
        S("ue_alpha", self.ue_alpha); S("ue_p_cmax", self.ue_p_cmax); S("ue_p_dyn", self.ue_p_dyn)
        S("ue_height", self.ue_height); S("ue_nf", self.ue_nf); S("ue_ohmic", self.ue_ohmic); S("ue_body_loss", self.ue_body_loss)
        S("ue_norm", self.ue_norm); S("ue_elem_pat", self.ue_elem_pat); S("ue_min_arr_gain", self.ue_min_arr_gain)
        S("ue_elem_max_g", self.ue_elem_max_g); S("ue_phi3", self.ue_phi3); S("ue_theta3", self.ue_theta3)
        S("ue_rows", self.ue_rows); S("ue_cols", self.ue_cols); S("ue_elem_am", self.ue_elem_am)
        S("ue_elem_sla_v", self.ue_elem_sla_v); S("ue_mult", self.ue_mult)
        # UL/DL
        S("ul_att", self.ul_att); S("ul_sinr_min", self.ul_sinr_min); S("ul_sinr_max", self.ul_sinr_max)
        S("dl_att", self.dl_att); S("dl_sinr_min", self.dl_sinr_min); S("dl_sinr_max", self.dl_sinr_max)
        S("ch_model", self.ch_model); S("shadowing", self.shadowing)
        messagebox.showinfo("IMT", "Configuração IMT carregada.")

    def _save_victim_config(self):
        data = {
            "v_freq": self.v_freq.get(), "v_bw": self.v_bw.get(), "v_txpsd": self.v_txpsd.get(),
            "v_pol_loss": self.v_pol_loss.get(), "v_tnoise": self.v_tnoise.get(),
            "v_ch_model": self.v_ch_model.get(), "v_season": self.v_season.get(),
            "v_p619_clutter": self.v_p619_clutter.get(), "v_p619_below_rooftop": self.v_p619_below_rooftop.get(),
            "v_alt": self.v_alt.get(), "v_fix_lat": self.v_fix_lat.get(), "v_fix_lon": self.v_fix_lon.get(),
            "v_es_alt": self.v_es_alt.get(), "v_es_lat": self.v_es_lat.get(), "v_es_lon": self.v_es_lon.get(),
            "v_az_type": self.v_az_type.get(), "v_el_type": self.v_el_type.get(),
            "v_ant_pattern": self.v_ant_pattern.get(), "v_ant_gain": self.v_ant_gain.get(),
            "v_s672_3db": self.v_s672_3db.get(), "v_s672_ls": self.v_s672_ls.get(),
        }
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], initialfile="single_space_station_config.json")
        if not path: return
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        messagebox.showinfo("Single Space Station", f"Configuração salva em:\n{path}")

    def _load_victim_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path: return
        with open(path, "r", encoding="utf-8") as f: vals = json.load(f)
        def S(name, var):
            if name in vals:
                try: var.set(vals[name])
                except: pass
        S("v_freq", self.v_freq); S("v_bw", self.v_bw); S("v_txpsd", self.v_txpsd)
        S("v_pol_loss", self.v_pol_loss); S("v_tnoise", self.v_tnoise)
        S("v_ch_model", self.v_ch_model); S("v_season", self.v_season)
        S("v_p619_clutter", self.v_p619_clutter); S("v_p619_below_rooftop", self.v_p619_below_rooftop)
        S("v_alt", self.v_alt); S("v_fix_lat", self.v_fix_lat); S("v_fix_lon", self.v_fix_lon)
        S("v_es_alt", self.v_es_alt); S("v_es_lat", self.v_es_lat); S("v_es_lon", self.v_es_lon)
        S("v_az_type", self.v_az_type); S("v_el_type", self.v_el_type)
        S("v_ant_pattern", self.v_ant_pattern); S("v_ant_gain", self.v_ant_gain)
        S("v_s672_3db", self.v_s672_3db); S("v_s672_ls", self.v_s672_ls)
        messagebox.showinfo("Single Space Station", "Configuração carregada.")

    # ---------------- Runner helpers (parallel) ----------------
    def _pick_outdir(self):
        cur = self.var_outdir.get() or os.getcwd()
        if not os.path.isdir(cur): cur = os.getcwd()
        path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta de saída (dentro do YAML)")
        if path:
            if not path.endswith(("/", "\\")):
                path = path + os.sep
            self.var_outdir.set(path.replace("\\","/"))

    def _pick_yamldir(self):
        p = filedialog.askdirectory(title="Selecionar pasta para salvar os .yaml", initialdir=self.var_yaml_dir.get() or os.getcwd())
        if p:
            self.var_yaml_dir.set(p)

    def _pick_folder(self, var):
        cur = var.get() or os.getcwd()
        if not os.path.isdir(cur):
            cur = os.getcwd()
        path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta")
        if path:
            var.set(path)
            self._scan_yaml_files()

    def _scan_yaml_files(self):
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        folder = getattr(self, "run_folder", tk.StringVar(value=os.getcwd())).get()
        if not os.path.isdir(folder):
            return
        files = [f for f in os.listdir(folder) if f.lower().endswith((".yaml",".yml"))]
        files.sort()
        for f in files:
            path = os.path.join(folder, f)
            total = self._yaml_num_snapshots(path) or int(self.var_snaps.get())
            self.tree.insert("", "end", iid=path, values=(os.path.basename(path), "Pronto", f"0/{total}", "0", "--"))

    def _yaml_num_snapshots(self, ypath):
        try:
            with open(ypath, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict):
                if "general" in data and isinstance(data["general"], dict) and "num_snapshots" in data["general"]:
                    return int(data["general"]["num_snapshots"])
                if "num_snapshots" in data:
                    return int(data["num_snapshots"])
        except Exception:
            pass
        return None

    def _run_selected_yaml_parallel(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Runner", "Selecione pelo menos um arquivo YAML.")
            return
        for iid in sel:
            if iid in self.proc_threads and self.proc_threads[iid].is_alive():
                continue
            self.jobs_q.put(iid)
            self._update_row(iid, status="Na fila", snap=None, pct=None, eta="--")

    def _stop_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Runner", "Selecione pelo menos um YAML.")
            return
        for iid in sel:
            p = self.procs.get(iid)
            if p and (p.poll() is None):
                try:
                    p.terminate()
                    try:
                        p.wait(timeout=2.0)
                    except Exception:
                        p.kill()
                    self._update_row(iid, status="Parado pelo usuário", eta="--")
                except Exception as e:
                    self._update_row(iid, status=f"Erro ao parar: {e}")
            else:
                self._update_row(iid, status="Não está rodando")

    def _runner_scheduler_tick(self):
        # inicia até max_workers simultâneos
        maxw = max(1, int(self.var_max_workers.get()))
        while len(self.running) < maxw and not self.jobs_q.empty():
            iid = self.jobs_q.get()
            if iid in self.running:
                continue
            if iid in self.proc_threads and self.proc_threads[iid].is_alive():
                continue
            t = threading.Thread(target=self._run_one_yaml, args=(iid,), daemon=True)
            self.proc_threads[iid] = t
            self.running.add(iid)
            t.start()
        # reaplicar em loop
        self.after(300, self._runner_scheduler_tick)

    def _run_one_yaml(self, ypath):
        declared_total = self._yaml_num_snapshots(ypath) or int(self.var_snaps.get())
        self.runtime[ypath] = {"status":"Rodando", "done":0, "total":declared_total, "declared_total":declared_total, "t0":time.time(), "last_snap_time":None}
        self._update_row(ypath, status="Rodando", snap=f"0/{declared_total}", pct="0", eta="--")

        try:
            cmd = [sys.executable, self.main_cli_path.get(), "-p", ypath]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, text=True)
            self.procs[ypath] = proc

            pat_xy = re.compile(r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
            pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

            total = declared_total
            for line in proc.stdout:
                self.line_q.put(f"[{os.path.basename(ypath)}] {line}")
                m1 = pat_xy.search(line)
                m2 = pat_hash.search(line)

                if m1:
                    done = int(m1.group(1)); total_in_line = int(m1.group(2))
                    if total_in_line:
                        total = max(total, total_in_line)
                    self.runtime[ypath]["done"] = done
                    self.runtime[ypath]["total"] = total
                elif m2:
                    done = int(m2.group(1))
                    self.runtime[ypath]["done"] = done
                    total = max(total, self.runtime[ypath]["total"])
                else:
                    continue

                now = time.time()
                self.runtime[ypath]["last_snap_time"] = now
                pct = f"{(100.0*self.runtime[ypath]['done']/max(total,1)):.1f}"
                eta = self._eta_string(self.runtime[ypath]["t0"], now, self.runtime[ypath]["done"], total)
                self._update_row(ypath, status="Rodando", snap=f"{self.runtime[ypath]['done']}/{total}", pct=pct, eta=eta)

            proc.wait()
            rc = proc.returncode
            done = self.runtime[ypath]["done"]
            pct = "100" if rc == 0 else f"{(100.0*done/max(total,1)):.1f}"
            self._update_row(ypath, status=("OK" if rc==0 else f"Erro {rc}"), snap=f"{done}/{total}", pct=pct, eta="00:00")
        except Exception as e:
            self._update_row(ypath, status=f"Falha: {e}", snap=f"--/--", pct="--", eta="--")
        finally:
            if ypath in self.running:
                self.running.remove(ypath)
            if ypath in self.procs:
                self.procs.pop(ypath, None)

    def _eta_string(self, t0, now, done, total):
        if done <= 0 or total <= 0:
            return "--"
        elapsed = now - t0
        rate = elapsed / max(done, 1)  # seg/snapshot
        remain = max(total - done, 0) * rate
        return str(datetime.timedelta(seconds=int(remain)))

    def _update_row(self, iid, status=None, snap=None, pct=None, eta=None):
        try:
            cur = list(self.tree.item(iid, "values"))
            if not cur:
                return
            if status is not None: cur[1] = status
            if snap   is not None: cur[2] = snap
            if pct    is not None: cur[3] = pct
            if eta    is not None: cur[4] = eta
            self.tree.item(iid, values=cur)
        except Exception:
            pass

    def _drain_log_queue(self):
        try:
            while True:
                line = self.line_q.get_nowait()
                self.txt_log.insert("end", line)
                if not line.endswith("\n"):
                    self.txt_log.insert("end", "\n")
                self.txt_log.see("end")
        except queue.Empty:
            pass
        self.after(150, self._drain_log_queue)

    # ---------------- helpers ----------------
    def _pick_file(self, tk_strvar, patterns):
        init = os.path.dirname(tk_strvar.get()) if tk_strvar.get() else os.getcwd()
        path = filedialog.askopenfilename(initialdir=init, title="Selecionar arquivo", filetypes=patterns)
        if path:
            tk_strvar.set(path)

    def _pair_entries(self, parent, var1, var2, w=6):
        f = ttk.Frame(parent)
        e1 = ttk.Entry(f, textvariable=var1, width=w); e1.pack(side="left")
        ttk.Label(f, text=" / ").pack(side="left")
        e2 = ttk.Entry(f, textvariable=var2, width=w); e2.pack(side="left")
        return f
    
    # ---------------- Plot_results ----------------
    def _collect_series_from_folder(self, folder: str, field: str):
        """
        Estratégia:
        1) Tenta ler <folder>/<field>.csv (coluna única ou coluna 'value').
        2) Se não existir, globa *.csv e tenta encontrar uma coluna chamada <field>.
        Retorna np.ndarray ou None.
        """
        import os
        import numpy as np

        def _read_csv_1col(path):
            try:
                df = pd.read_csv(path)
                # coluna com mesmo nome do field?
                if field in df.columns:
                    s = df[field].dropna().values
                else:
                    # se só houver 1 coluna, usa ela
                    if df.shape[1] == 1:
                        s = df.iloc[:,0].dropna().values
                    elif "value" in df.columns:
                        s = df["value"].dropna().values
                    else:
                        return None
                return s.astype(float)
            except Exception:
                return None

        # 1) nome exato
        cand = os.path.join(folder, f"{field}.csv")
        if os.path.exists(cand):
            s = _read_csv_1col(cand)
            if s is not None and s.size > 0:
                return s

        # 2) varrer outros csvs
        for path in glob.glob(os.path.join(folder, "*.csv")):
            s = _read_csv_1col(path)
            if s is not None and s.size > 0:
                return s

        return None


    def _compute_ecdf(self, x: np.ndarray, ccdf: bool = False):
        import numpy as np
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if x.size == 0:
            return None, None
        x_sorted = np.sort(x)
        y = np.arange(1, x_sorted.size+1) / x_sorted.size
        if ccdf:
            y = 1.0 - y
        return x_sorted, y

    def _draw_results_plots(self):
        """
        Desenha os subplots de resultados (CDF/CCDF), com Y linear/log,
        linhas de referência e comparação entre múltiplas pastas.
        """
        # Se auto-update foi desligado, cancele job pendente
        if self._plot_auto_job is not None and not self.var_auto_update.get():
            try:
                self.after_cancel(self._plot_auto_job)
            except Exception:
                pass
            self._plot_auto_job = None

        import numpy as np
        from pathlib import Path

        # Layout
        rows = max(1, int(self.var_rows.get()))
        cols = max(1, int(self.var_cols.get()))
        n_axes = min(rows * cols, self._max_axes)

        # Recria grade
        self.fig_res.clf()
        axes = self.fig_res.subplots(rows, cols)
        if isinstance(axes, np.ndarray):
            axes_flat = axes.ravel()
        else:
            axes_flat = [axes]

        # Pastas selecionadas (fallback: output_dir atual)
        dirs = list(self.res_dirs)
        if not dirs:
            od = str(Path(self.var_outdir.get()))
            if od:
                dirs = [od]

        # Desenho por subfigura
        for i in range(n_axes):
            ax   = axes_flat[i]
            cfg  = self._axes_cfg[i]
            field = cfg.get("field", "")
            mode  = (cfg.get("mode") or "CDF").strip().upper()

            # Y-scale (parsing robusto)
            ytxt = (cfg.get("yscale") or "").strip().lower()
            if ytxt in {"log", "log10", "logarítmica", "logaritmica", "log-scale", "logscale"}:
                ysc = "Log"
            else:
                ysc = "Linear"

            ccdf = (mode == "CCDF")
            eps  = 1e-4 if ysc == "Log" else 0.0  # evita log(0)

            ax.cla()
            plotted_any = False

            for folder in dirs:
                s = self._collect_series_from_folder(folder, field)
                if s is None or s.size == 0:
                    continue

                xs, ys = self._compute_ecdf(s, ccdf=ccdf)
                if xs is None:
                    continue

                yplot = np.clip(ys, eps, 1.0) if ysc == "Log" else ys
                (line,) = ax.plot(xs, yplot, label=Path(folder).name)
                plotted_any = True

                # ----- Linhas de referência -----
                refs_txt = (cfg.get("refs") or "").strip()
                # fallback para referência global (opcional)
                if not refs_txt and hasattr(self, "var_global_refs"):
                    refs_txt = (self.var_global_refs.get() or "").strip()

                if refs_txt:
                    # "5, 10, 50" -> [0.05, 0.10, 0.50]
                    refs = []
                    for tok in refs_txt.replace(";", ",").split(","):
                        tok = tok.strip()
                        if not tok:
                            continue
                        try:
                            val = float(tok)
                            if val > 1.0:
                                val = val / 100.0
                            if 0.0 < val < 1.0:
                                refs.append(val)
                        except Exception:
                            pass

                    color = line.get_color()
                    finite = s[np.isfinite(s)]
                    for r in refs:
                        # r é a referência em CCDF; o quantil na CDF correspondente é q = 1 - r
                        try:
                            x_ref = np.quantile(finite, 1.0 - r)
                        except Exception:
                            continue

                        if ccdf:
                            y0, y1 = (1.0, r)  # de 100% até a referência (CCDF)
                        else:
                            y0, y1 = (0.0, 1.0 - r)  # de 0% até (1 - referência) (CDF)

                        if ysc == "Log":
                            y0 = max(eps, y0)
                            y1 = max(eps, y1)

                        ax.vlines(x_ref, y0, y1, colors=color, linestyles="dashed", linewidth=1.2, alpha=0.85)
                        ax.text(x_ref, y1, f"{int(round(r*100))}%", rotation=90, va="bottom", ha="center",
                                fontsize=8, color=color, alpha=0.8)

            # Títulos/labels
            info = RESULT_FIELDNAME_TO_PLOT_INFO.get(field, {})
            ax.set_title(info.get("title", field))
            ax.set_xlabel(info.get("x_label", field))
            ax.set_ylabel("CCDF" if ccdf else "CDF")

            # Y-scale
            try:
                ax.set_yscale("log" if ysc == "Log" else "linear")
            except Exception:
                pass

            # Grade/legenda
            ax.grid(True, which="both", alpha=0.3)
            if plotted_any:
                ax.legend()
            else:
                ax.text(0.5, 0.5, "sem dados", ha="center", va="center",
                        transform=ax.transAxes, alpha=0.6)

            # Limites Y seguros para log
            if ysc == "Log":
                ax.set_ylim(max(eps, 1e-6), 1.0)

        # Remove eixos além de n_axes
        for j in range(n_axes, len(axes_flat)):
            try:
                self.fig_res.delaxes(axes_flat[j])
            except Exception:
                pass

        self.fig_res.tight_layout()
        self.canvas_res.draw_idle()

        # (re)agenda auto-update se ligado
        if self.var_auto_update.get():
            period = max(200, int(self.var_update_period_ms.get()))
            def _tick():
                self._draw_results_plots()
            if self._plot_auto_job is not None:
                try:
                    self.after_cancel(self._plot_auto_job)
                except Exception:
                    pass
            self._plot_auto_job = self.after(period, _tick)


    def _ref_add(self):
        try:
            x = float(self._ref_x_entry.get().strip())
        except Exception:
            messagebox.showwarning("Linha de referência", "Valor de x inválido.")
            return
        label = self._ref_label_entry.get().strip()
        self.ref_lines.append({"x": x, "label": label})
        self.lb_refs.insert("end", f"{x:g}  —  {label or '(sem rótulo)'}")
        self._ref_x_entry.delete(0, "end"); self._ref_label_entry.delete(0, "end")
        self._draw_results_plots()

    def _ref_remove(self):
        sel = list(self.lb_refs.curselection())[::-1]
        for idx in sel:
            self.lb_refs.delete(idx)
            del self.ref_lines[idx]
        self._draw_results_plots()

    def _schedule_auto_update(self):
        # cancela anterior
        if self._plot_auto_job is not None:
            try:
                self.after_cancel(self._plot_auto_job)
            except Exception:
                pass
            self._plot_auto_job = None

        if not self.var_auto_update.get():
            return

        period = max(200, int(self.var_update_period_ms.get()))

        def _tick():
            self._draw_results_plots()
            self._plot_auto_job = self.after(period, _tick)
        self._plot_auto_job = self.after(period, _tick)

    def _export_results_fig(self):
        path = filedialog.asksaveasfilename(
            title="Exportar figura",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf"), ("All files", "*.*")]
        )
        if not path:
            return
        dpi = max(72, int(self.var_export_dpi.get()))
        try:
            self.fig_res.savefig(path, dpi=dpi, bbox_inches="tight")
            messagebox.showinfo("Exportar figura", f"Figura salva em:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportar figura", f"Falha ao exportar:\n{e}")

    def _draw_bs_post(self, ax3d, x, y, h, color="tab:blue", lw=2.0):
        """Desenha o 'postinho' (mastro) da BS em (x,y) com altura h."""
        ax3d.plot([x, x], [y, y], [0, h], color=color, lw=lw)

    def _sector_polygon_xy(self, x, y, radius, az_deg, half_bw_deg=60, n=48):
        """Gera os pontos (x,y) do setor (wedge) no plano z=0."""
        th0 = np.radians(az_deg - half_bw_deg)
        th1 = np.radians(az_deg + half_bw_deg)
        ths = np.linspace(th0, th1, n)
        xs = x + radius * np.cos(ths)
        ys = y + radius * np.sin(ths)
        # polígono: vértice central -> arco -> volta ao centro
        poly_xy = [(x, y)] + list(zip(xs, ys)) + [(x, y)]
        return poly_xy

    def _add_sector3d(self, ax3d, poly_xy, z=0.0, face_alpha=0.12, edge_color="tab:green"):
        """Adiciona o polígono do setor no plano z fixo."""
        verts3d = [(px, py, z) for (px, py) in poly_xy]
        pcoll = Poly3DCollection([verts3d], alpha=face_alpha, edgecolor=edge_color)
        pcoll.set_facecolor(edge_color)
        ax3d.add_collection3d(pcoll)

    def _auto_xy_lim(self, xs, ys, margin=0.15):
        """Ajusta limites XY com margem fracionária."""
        if len(xs) == 0:
            return (-1, 1), (-1, 1)
        xmin, xmax = np.min(xs), np.max(xs)
        ymin, ymax = np.min(ys), np.max(ys)
        dx = xmax - xmin if xmax > xmin else 1.0
        dy = ymax - ymin if ymax > ymin else 1.0
        xpad = dx * margin
        ypad = dy * margin
        return (xmin - xpad, xmax + xpad), (ymin - ypad, ymax + ypad)

    def _hexagon_xy(self, x0, y0, R):
        """
        Hex regular 'flat-top' no plano z=0, centrado em (x0,y0),
        com raio R (centro -> vértice). Giro de +30° para lados horizontais.
        """
        ang = np.deg2rad(30 + np.arange(0, 360, 60))  # 30, 90, 150, ...
        xs = x0 + R * np.cos(ang)
        ys = y0 + R * np.sin(ang)
        return list(zip(xs, ys))


    def _add_polygon3d(self, ax3d, poly_xy, z=0.0, face_alpha=0.06, edge_color="k", lw=1.0):
        """Adiciona polígono no plano z fixo."""
        verts3d = [(px, py, z) for (px, py) in poly_xy]
        pcoll = Poly3DCollection([verts3d], alpha=face_alpha, edgecolor=edge_color, linewidths=lw)
        pcoll.set_facecolor(edge_color)
        ax3d.add_collection3d(pcoll)

    def _set_equal_3d(self, ax3d, xs, ys, z_top, margin=0.10):
        """
        Força mesma escala em x,y,z. z vai de 0 até z_top (baixo visual dos mastros).
        O cubo tem aresta = max(dx, dy, z_top), com margem.
        """
        xs = np.asarray(xs); ys = np.asarray(ys)
        xmin, xmax = float(np.min(xs)), float(np.max(xs))
        ymin, ymax = float(np.min(ys)), float(np.max(ys))
        dx = max(1e-9, xmax - xmin)
        dy = max(1e-9, ymax - ymin)
        span = max(dx, dy, float(z_top))
        pad = span * margin
        cx = 0.5 * (xmax + xmin)
        cy = 0.5 * (ymax + ymin)
        ax3d.set_xlim(cx - 0.5*span - pad, cx + 0.5*span + pad)
        ax3d.set_ylim(cy - 0.5*span - pad, cy + 0.5*span + pad)
        ax3d.set_zlim(0.0, span + pad)
        # exige Matplotlib 3.3+:
        try:
            ax3d.set_box_aspect((1, 1, 1))
        except Exception:
            pass

    def _add_polyline3d(self, ax3d, xy_points, z=0.0, color="k", lw=1.0):
        """
        Desenha as arestas de um polígono no plano z, sem preenchimento.
        xy_points: lista [(x0,y0), (x1,y1), ..., (xN,yN)] (fecharemos automaticamente).
        """
        from mpl_toolkits.mplot3d.art3d import Line3DCollection
        if not xy_points:
            return
        # garante fechado
        if xy_points[0] != xy_points[-1]:
            xy_points = xy_points + [xy_points[0]]

        segs = [((xy_points[i][0], xy_points[i][1], z),
                (xy_points[i+1][0], xy_points[i+1][1], z))
                for i in range(len(xy_points)-1)]
        lc = Line3DCollection(segs, colors=[color], linewidths=lw)
        ax3d.add_collection3d(lc)

    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    def _add_polyline3d(self, ax3d, xy_points, z=0.0, color="k", lw=1.0):
        """Arestas de polígono/linha no plano z, sem preenchimento."""
        if not xy_points:
            return
        # fecha
        if xy_points[0] != xy_points[-1]:
            xy_points = xy_points + [xy_points[0]]
        segs = [((xy_points[i][0], xy_points[i][1], z),
                (xy_points[i+1][0], xy_points[i+1][1], z))
                for i in range(len(xy_points)-1)]
        self.ax3d.add_collection3d(Line3DCollection(segs, colors=[color], linewidths=lw))

    def _add_wedge_outline3d(self, ax3d, x, y, r, az_deg, half_bw_deg=60, n=64, color="green", lw=1.0):
        """Contorno de um wedge (arco + 2 raios) no plano z=0 (fill=False)."""
        th0 = np.radians(az_deg - half_bw_deg)
        th1 = np.radians(az_deg + half_bw_deg)
        ths = np.linspace(th0, th1, n)
        arc_xy = [(x + r*np.cos(t), y + r*np.sin(t)) for t in ths]
        center = (x, y)
        # segmentos: centro->p0, arco, p_last->centro
        segs = []
        p0 = arc_xy[0]; pN = arc_xy[-1]
        segs.append(((center[0], center[1], 0.0), (p0[0], p0[1], 0.0)))
        for a, b in zip(arc_xy[:-1], arc_xy[1:]):
            segs.append(((a[0], a[1], 0.0), (b[0], b[1], 0.0)))
        segs.append(((pN[0], pN[1], 0.0), (center[0], center[1], 0.0)))
        self.ax3d.add_collection3d(Line3DCollection(segs, colors=[color], linewidths=lw))

    def _report_callback_exception(self, exc, val, tb):
        # Mostra um diálogo e NÃO fecha o programa
        msg = ''.join(traceback.format_exception(exc, val, tb))
        messagebox.showerror(
            "Erro inesperado",
            "Ocorreu um erro, mas o programa continuará aberto.\n\n"
            f"{val}\n\nDetalhes:\n{msg[:4000]}"  # evita caixa gigante
        )

    def _add_field(self, parent, row, label, widget, col=0, col_span=2):
        """Linha 'label : widget' usando grid."""
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(6,4), pady=2)
        widget.grid(row=row, column=col+1, columnspan=col_span-1,
                    sticky="we", padx=(0,6), pady=2)

    def _add_range(self, parent, row, label, wmin, wmax, sep_text="a"):
        """Linha 'label : [min]  a  [max]'."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(6,4), pady=2)
        wmin.grid(row=row, column=1, sticky="we", padx=(0,4), pady=2)
        ttk.Label(parent, text=f" {sep_text} ").grid(row=row, column=2, padx=(0,4))
        wmax.grid(row=row, column=3, sticky="we", padx=(0,6), pady=2)

    def _toggle_ue_distribution(self):
        is_ang_dist = (self.ue_dist_type.get().upper() == "ANGLE_AND_DISTANCE")
        if hasattr(self, "_ue_col_dist_frame"):
            if is_ang_dist:
                self._ue_col_dist_frame.grid()      # mostra
            else:
                self._ue_col_dist_frame.grid_remove()  # esconde

    def _scatter_ues(self, ax3d, ue_mgr, s=6):
        """Plota UEs do StationManager no 3D (x,y,z). Indoor em cor diferente."""
        xs, ys = np.asarray(ue_mgr.x), np.asarray(ue_mgr.y)
        zs = np.asarray(getattr(ue_mgr, "z", np.zeros_like(xs)))
        # flag indoor (se existir)
        is_indoor = np.asarray(getattr(ue_mgr, "is_indoor", np.zeros_like(xs, dtype=bool)))
        # OUTDOOR
        mask_out = ~is_indoor
        if mask_out.any():
            ax3d.scatter(xs[mask_out], ys[mask_out], zs[mask_out],
                        s=s, depthshade=False, color="tab:orange", edgecolors="none", label="UE outdoor")
        # INDOOR
        if is_indoor.any():
            ax3d.scatter(xs[is_indoor], ys[is_indoor], zs[is_indoor],
                        s=s, depthshade=False, color="tab:purple", edgecolors="none", label="UE indoor")
            

# --- Plot labels/titles for result fields ---
RESULT_FIELDNAME_TO_PLOT_INFO = {
    "imt_ul_tx_power_density": {"x_label": "Transmit power density [dBm/Hz]", "title": "[IMT] UE transmit power density"},
    "imt_ul_tx_power": {"x_label": "Transmit power [dBm]", "title": "[IMT] UE transmit power"},
    "imt_ul_sinr_ext": {"x_label": "SINR [dB]", "title": "[IMT] UL SINR with external interference"},
    "imt_ul_snr": {"title": "[IMT] UL SNR", "x_label": "SNR [dB]"},
    "imt_ul_inr": {"title": "[IMT] UL interference-to-noise ratio", "x_label": "$I/N$ [dB]"},
    "imt_ul_sinr": {"x_label": "SINR [dB]", "title": "[IMT] UL SINR"},
    "imt_system_build_entry_loss": {"x_label": "Building entry loss [dB]", "title": "[SYS] IMT to system building entry loss"},
    "imt_ul_tput_ext": {"title": "[IMT] UL throughput with external interference", "x_label": "Throughput [bits/s/Hz]"},
    "imt_ul_tput": {"title": "[IMT] UL throughput", "x_label": "Throughput [bits/s/Hz]"},
    "imt_path_loss": {"title": "[IMT] path loss", "x_label": "Path loss [dB]"},
    "imt_coupling_loss": {"title": "[IMT] coupling loss", "x_label": "Coupling loss [dB]"},
    "imt_bs_antenna_gain": {"x_label": "Antenna gain [dBi]", "title": "[IMT] BS antenna gain towards the UE"},
    "imt_ue_antenna_gain": {"x_label": "Antenna gain [dBi]", "title": "[IMT] UE antenna gain towards the BS"},
    "system_imt_antenna_gain": {"x_label": "Antenna gain [dBi]", "title": "[SYS] system antenna gain towards IMT stations"},
    "imt_system_antenna_gain": {"x_label": "Antenna gain [dBi]", "title": "[IMT] IMT station antenna gain towards system"},
    "imt_system_path_loss": {"x_label": "Path Loss [dB]", "title": "[SYS] IMT to system path loss"},
    "sys_to_imt_coupling_loss": {"x_label": "Coupling Loss [dB]", "title": "[SYS] IMT to system coupling loss"},
    "system_dl_interf_power": {"x_label": "Interference Power [dB]", "title": "[SYS] system interference power from IMT DL"},
    "imt_system_diffraction_loss": {"x_label": "Building entry loss [dB]", "title": "[SYS] IMT to system diffraction loss"},
    "imt_dl_sinr_ext": {"x_label": "SINR [dB]", "title": "[IMT] DL SINR with external interference"},
    "imt_dl_sinr": {"x_label": "SINR [dB]", "title": "[IMT] DL SINR"},
    "imt_dl_snr": {"title": "[IMT] DL SNR", "x_label": "SNR [dB]"},
    "imt_dl_inr": {"title": "[IMT] DL interference-to-noise ratio", "x_label": "$I/N$ [dB]"},
    "imt_dl_tput_ext": {"title": "[IMT] DL throughput with external interference", "x_label": "Throughput [bits/s/Hz]"},
    "imt_dl_tput": {"title": "[IMT] DL throughput", "x_label": "Throughput [bits/s/Hz]"},
    "system_ul_interf_power": {"title": "[SYS] system interference power from IMT UL", "x_label": "Interference Power [dBm/BMHz]"},
    "system_ul_interf_power_per_mhz": {"title": "[SYS] system interference PSD from IMT UL", "x_label": "Interference Power [dBm/MHz]"},
    "system_dl_interf_power_per_mhz": {"title": "[SYS] system interference PSD from IMT DL", "x_label": "Interference Power [dBm/MHz]"},
    "system_inr": {"title": "[SYS] system INR", "x_label": "INR [dB]"},
    "system_pfd": {"title": "[SYS] system PFD", "x_label": "PFD [dBm/m^2]"},
    "imt_dl_tx_power": {"x_label": "Transmit power [dBm]", "title": "[IMT] DL transmit power"},
    "imt_dl_pfd_external": {"title": "[IMT] DL external Power Flux Density (PFD) ", "x_label": "PFD [dBW/m²/MHz]"},
    "imt_dl_pfd_external_aggregated": {"title": "[IMT] Aggregated DL external Power Flux Density (PFD)", "x_label": "PFD [dBW/m²/MHz]"},
}


# --------------- main ---------------
if __name__ == "__main__":
    App().mainloop()
