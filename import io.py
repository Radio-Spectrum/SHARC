# sharc_yaml_gui_topology_imt_plus.py
import os
import io
import time
import math
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Wedge

# ===================== YAML helpers (sem PyYAML) =====================
def to_bool_yaml(v: bool) -> str:
    return "true" if v else "false"

def dump_yaml_block(d, indent=0):
    """dump YAML simples (apenas dict, bool, int, float, str, listas simples)."""
    lines = []
    sp = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.extend(dump_yaml_block(v, indent + 1))
            elif isinstance(v, list):
                lines.append(f"{sp}{k}:")
                for it in v:
                    if isinstance(it, (dict, list)):
                        lines.append(f"{sp}-")
                        lines.extend(dump_yaml_block(it, indent + 1))
                    elif isinstance(it, bool):
                        lines.append(f"{sp}- {to_bool_yaml(it)}")
                    else:
                        lines.append(f"{sp}- {it}")
            elif isinstance(v, bool):
                lines.append(f"{sp}{k}: {to_bool_yaml(v)}")
            else:
                lines.append(f"{sp}{k}: {v}")
    else:
        # fallback
        lines.append(f"{sp}{d}")
    return lines

def build_yaml_text(cfg_general, cfg_imt):
    root = {
        "general": cfg_general,
        "imt": cfg_imt
    }
    return "\n".join(dump_yaml_block(root)) + "\n"

# ===================== Geometria/hex grid =====================
def hex_center_grid(intersite_distance, num_clusters=7):
    """Gera grade de centros hexa (1 ou 7 clusters) em metros."""
    if num_clusters == 1:
        return np.array([[0.0, 0.0]])
    # 7: centro + 6 em volta
    R = float(intersite_distance)
    centers = [(0.0, 0.0)]
    for k in range(6):
        ang = 2 * math.pi * k / 6.0
        centers.append((R * math.cos(ang), R * math.sin(ang)))
    return np.array(centers)

def rotate_points(pts_xy, deg):
    th = np.deg2rad(deg)
    c, s = np.cos(th), np.sin(th)
    R = np.array([[c, -s],
                  [s,  c]])
    return pts_xy @ R.T

# ===================== GUI =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SHARC – YAML + IMT Topology (Hotspot com UEs)")
        self.geometry("1120x720")
        self.minsize(1040, 680)

        # -------- General --------
        self.var_seed = tk.IntVar(value=157)
        self.var_snaps = tk.IntVar(value=10000)
        self.var_overwrite = tk.BooleanVar(value=False)
        self.var_outdir = tk.StringVar(value="campaigns/01_DC_MSS_to_FS/output/")
        self.var_prefix = tk.StringVar(value="output_mss_d2d_to_fs_h_az_mo_lf")
        self.var_system = tk.StringVar(value="SINGLE_EARTH_STATION")
        self.var_imt_link = tk.StringVar(value="DOWNLINK")
        self.var_adj = tk.BooleanVar(value=False)
        self.var_coch = tk.BooleanVar(value=True)

        # -------- Topology (básico dos Parameters* do SHARC) --------
        self.topo_type = tk.StringVar(value="HOTSPOT")
        # Macro
        self.var_macro_isd = tk.DoubleVar(value=500.0)
        self.var_macro_clusters = tk.IntVar(value=7)
        # Hotspot
        self.var_hot_isd = tk.DoubleVar(value=500.0)
        self.var_hot_clusters = tk.IntVar(value=7)
        self.var_hot_num_hotspots_per_cell = tk.IntVar(value=2)
        self.var_hot_max_dist_hotspot_ue = tk.DoubleVar(value=120.0)
        self.var_hot_min_dist_bs_hotspot = tk.DoubleVar(value=50.0)
        # Preview-only: nº de small-cell BS por hotspot e nº de UEs
        self.var_hot_bs_per_hotspot = tk.IntVar(value=1)
        self.var_hot_ue_per_hotspot = tk.IntVar(value=40)

        # Indoor (placeholders)
        self.var_indoor_isd = tk.DoubleVar(value=40.0)
        self.var_indoor_rows = tk.IntVar(value=3)
        self.var_indoor_cols = tk.IntVar(value=2)
        self.var_indoor_cells = tk.IntVar(value=3)
        self.var_indoor_floors = tk.IntVar(value=1)

        # NTN (subset) – espelha ParametersNTN (cell_radius/intersite linkados) :contentReference[oaicite:3]{index=3}
        self.var_ntn_isd = tk.DoubleVar(value=90000*np.sqrt(3))
        self.var_ntn_cell_r = tk.DoubleVar(value=90000.0)
        self.var_ntn_bs_h = tk.DoubleVar(value=600_000.0)
        self.var_ntn_az = tk.DoubleVar(value=45.0)
        self.var_ntn_el = tk.DoubleVar(value=90.0)
        self.var_ntn_sectors = tk.IntVar(value=7)

        # Single BS (subset) :contentReference[oaicite:4]{index=4}
        self.var_sbs_radius = tk.DoubleVar(value=150.0)
        self.var_sbs_clusters = tk.IntVar(value=1)

        # MSS-DC (placeholder)
        self.var_mss_beam_r = tk.DoubleVar(value=36_516.0)
        self.var_mss_nbeams = tk.IntVar(value=7)
        self.var_mss_min_el = tk.DoubleVar(value=20.0)

        # -------- Antenas (BS e UE) – subset de ParametersAntennaImt :contentReference[oaicite:5]{index=5}
        self.var_bs_elem_pattern = tk.StringVar(value="M2101")
        self.var_bs_n_rows = tk.IntVar(value=8)
        self.var_bs_n_cols = tk.IntVar(value=8)
        self.var_bs_phi3 = tk.DoubleVar(value=65.0)
        self.var_bs_theta3 = tk.DoubleVar(value=65.0)
        self.var_bs_downtilt = tk.DoubleVar(value=6.0)
        # UE antenna
        self.var_ue_elem_pattern = tk.StringVar(value="M2101")
        self.var_ue_n_rows = tk.IntVar(value=2)
        self.var_ue_n_cols = tk.IntVar(value=2)

        # -------- UEs – subset de ParametersImt.UE :contentReference[oaicite:6]{index=6}
        self.var_ue_dist_type = tk.StringVar(value="ANGLE_AND_DISTANCE")
        self.var_ue_dist_dist = tk.StringVar(value="RAYLEIGH")
        self.var_ue_dist_az = tk.StringVar(value="NORMAL")
        self.var_ue_az_min = tk.DoubleVar(value=-60.0)
        self.var_ue_az_max = tk.DoubleVar(value=60.0)
        self.var_ue_k = tk.IntVar(value=3)
        self.var_ue_km = tk.IntVar(value=1)
        self.var_ue_height = tk.DoubleVar(value=1.5)
        self.var_ue_indoor = tk.DoubleVar(value=5.0)

        self._build_ui()

    # ---------------- UI construction ----------------
    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        tab_general = ttk.Frame(nb, padding=10)
        tab_topology = ttk.Frame(nb, padding=10)
        tab_ue_ant = ttk.Frame(nb, padding=10)
        tab_preview = ttk.Frame(nb, padding=(10, 6, 10, 10))

        nb.add(tab_general, text="General")
        nb.add(tab_topology, text="IMT Topology")
        nb.add(tab_ue_ant, text="IMT – BS/UE & UEs")
        nb.add(tab_preview, text="Preview & Export")

        # ---- General ----
        r = 0
        ttk.Label(tab_general, text="seed").grid(row=r, column=0, sticky="w")
        ttk.Entry(tab_general, textvariable=self.var_seed, width=10).grid(row=r, column=1, sticky="w")
        ttk.Button(tab_general, text="Randomize", command=lambda: self.var_seed.set(random.randint(1, 2**31-1))).grid(row=r, column=2, sticky="w")

        ttk.Label(tab_general, text="num_snapshots").grid(row=r, column=3, sticky="e", padx=(20,6))
        ttk.Entry(tab_general, textvariable=self.var_snaps, width=12).grid(row=r, column=4, sticky="w")

        r += 1
        ttk.Checkbutton(tab_general, text="overwrite_output", variable=self.var_overwrite).grid(row=r, column=0, columnspan=2, sticky="w")
        ttk.Label(tab_general, text="output_dir").grid(row=r, column=2, sticky="e", padx=(20,6))
        out_entry = ttk.Entry(tab_general, textvariable=self.var_outdir, width=40); out_entry.grid(row=r, column=3, columnspan=2, sticky="we")
        ttk.Button(tab_general, text="Selecionar pasta...", command=self._pick_outdir).grid(row=r, column=5, sticky="w")

        r += 1
        ttk.Label(tab_general, text="output_dir_prefix").grid(row=r, column=0, sticky="w")
        ttk.Entry(tab_general, textvariable=self.var_prefix, width=40).grid(row=r, column=1, columnspan=3, sticky="we")
        ttk.Button(tab_general, text="Sugerir prefixo", command=self._suggest_prefix).grid(row=r, column=4, sticky="w")

        r += 1
        ttk.Label(tab_general, text="system").grid(row=r, column=0, sticky="w")
        ttk.Combobox(tab_general, textvariable=self.var_system, values=["SINGLE_EARTH_STATION"], state="readonly", width=28).grid(row=r, column=1, sticky="w")
        ttk.Label(tab_general, text="imt_link").grid(row=r, column=2, sticky="e", padx=(20,6))
        ttk.Combobox(tab_general, textvariable=self.var_imt_link, values=["DOWNLINK","UPLINK"], state="readonly", width=20).grid(row=r, column=3, sticky="w")

        r += 1
        ttk.Checkbutton(tab_general, text="enable_adjacent_channel", variable=self.var_adj).grid(row=r, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(tab_general, text="enable_cochannel", variable=self.var_coch).grid(row=r, column=2, columnspan=2, sticky="w")

        for c in range(6):
            tab_general.grid_columnconfigure(c, weight=1)

        # ---- Topology ----
        rr = 0
        ttk.Label(tab_topology, text="Topology type").grid(row=rr, column=0, sticky="w")
        cb = ttk.Combobox(tab_topology, textvariable=self.topo_type,
                          values=["HOTSPOT","MACROCELL","INDOOR","NTN","SINGLE_BS","MSS_DC"],
                          state="readonly", width=18)
        cb.grid(row=rr, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_topo_fields(tab_topology))
        self.fr_topo_fields = ttk.Frame(tab_topology); self.fr_topo_fields.grid(row=rr+1, column=0, columnspan=8, sticky="nsew", pady=(8,0))
        for c in range(8): tab_topology.grid_columnconfigure(c, weight=1)
        self._refresh_topo_fields(tab_topology)

        # ---- Antenas e UEs ----
        self._build_tab_ue_ant(tab_ue_ant)

        # ---- Preview & Export ----
        left = ttk.Frame(tab_preview); right = ttk.Frame(tab_preview)
        left.pack(side="left", fill="both", expand=True); right.pack(side="right", fill="y")

        self.fig, self.ax = plt.subplots(figsize=(6.2, 6.2))
        self.ax.set_aspect("equal"); self.ax.grid(True, alpha=0.25)
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

        ttk.Button(right, text="Gerar preview", command=self._draw_preview).pack(fill="x", pady=(4,4))
        ttk.Button(right, text="Salvar imagem...", command=self._save_image).pack(fill="x", pady=(4,4))
        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(right, text="Atualizar YAML", command=self._update_yaml_preview).pack(fill="x", pady=(4,4))
        ttk.Button(right, text="Salvar YAML...", command=self._save_yaml).pack(fill="x", pady=(4,4))
        ttk.Label(right, text="Prévia do YAML:").pack(anchor="w", pady=(10,2))
        self.txt_yaml = tk.Text(right, width=40, height=26, wrap="none"); self.txt_yaml.pack(fill="both", expand=True)

        self._draw_preview()
        self._update_yaml_preview()

    def _build_tab_ue_ant(self, root):
        # BS antenna
        frm_bs = ttk.LabelFrame(root, text="BS Antenna (ARRAY) – subset ParametersAntennaImt")
        frm_bs.pack(fill="x", padx=4, pady=4)
        r=0
        ttk.Label(frm_bs, text="element_pattern").grid(row=r, column=0, sticky="w")
        ttk.Combobox(frm_bs, textvariable=self.var_bs_elem_pattern, values=["M2101","F1336","FIXED"], state="readonly", width=12).grid(row=r, column=1, sticky="w")
        ttk.Label(frm_bs, text="n_rows").grid(row=r, column=2, sticky="e"); ttk.Entry(frm_bs, textvariable=self.var_bs_n_rows, width=8).grid(row=r, column=3, sticky="w")
        ttk.Label(frm_bs, text="n_columns").grid(row=r, column=4, sticky="e"); ttk.Entry(frm_bs, textvariable=self.var_bs_n_cols, width=8).grid(row=r, column=5, sticky="w"); r+=1
        ttk.Label(frm_bs, text="phi_3dB [deg]").grid(row=r, column=0, sticky="w"); ttk.Entry(frm_bs, textvariable=self.var_bs_phi3, width=8).grid(row=r, column=1, sticky="w")
        ttk.Label(frm_bs, text="theta_3dB [deg]").grid(row=r, column=2, sticky="e"); ttk.Entry(frm_bs, textvariable=self.var_bs_theta3, width=8).grid(row=r, column=3, sticky="w")
        ttk.Label(frm_bs, text="downtilt [deg]").grid(row=r, column=4, sticky="e"); ttk.Entry(frm_bs, textvariable=self.var_bs_downtilt, width=8).grid(row=r, column=5, sticky="w")
        for c in range(6): frm_bs.grid_columnconfigure(c, weight=1)

        # UE antenna
        frm_uea = ttk.LabelFrame(root, text="UE Antenna (ARRAY simplificado)")
        frm_uea.pack(fill="x", padx=4, pady=4)
        r=0
        ttk.Label(frm_uea, text="element_pattern").grid(row=r, column=0, sticky="w")
        ttk.Combobox(frm_uea, textvariable=self.var_ue_elem_pattern, values=["M2101","F1336","FIXED"], state="readonly", width=12).grid(row=r, column=1, sticky="w")
        ttk.Label(frm_uea, text="n_rows").grid(row=r, column=2, sticky="e"); ttk.Entry(frm_uea, textvariable=self.var_ue_n_rows, width=8).grid(row=r, column=3, sticky="w")
        ttk.Label(frm_uea, text="n_columns").grid(row=r, column=4, sticky="e"); ttk.Entry(frm_uea, textvariable=self.var_ue_n_cols, width=8).grid(row=r, column=5, sticky="w")
        for c in range(6): frm_uea.grid_columnconfigure(c, weight=1)

        # UE distribution
        frm_ued = ttk.LabelFrame(root, text="UE Distribution – subset ParametersImt.UE")
        frm_ued.pack(fill="x", padx=4, pady=4)
        r=0
        ttk.Label(frm_ued, text="type").grid(row=r, column=0, sticky="w")
        ttk.Combobox(frm_ued, textvariable=self.var_ue_dist_type, values=["ANGLE_AND_DISTANCE"], state="readonly").grid(row=r, column=1, sticky="w")
        ttk.Label(frm_ued, text="distance").grid(row=r, column=2, sticky="e")
        ttk.Combobox(frm_ued, textvariable=self.var_ue_dist_dist, values=["RAYLEIGH","UNIFORM"], state="readonly").grid(row=r, column=3, sticky="w")
        ttk.Label(frm_ued, text="azimuth").grid(row=r, column=4, sticky="e")
        ttk.Combobox(frm_ued, textvariable=self.var_ue_dist_az, values=["NORMAL","UNIFORM"], state="readonly").grid(row=r, column=5, sticky="w"); r+=1
        ttk.Label(frm_ued, text="azimuth_range [deg]").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm_ued, textvariable=self.var_ue_az_min, width=8).grid(row=r, column=1, sticky="w")
        ttk.Entry(frm_ued, textvariable=self.var_ue_az_max, width=8).grid(row=r, column=2, sticky="w")
        ttk.Label(frm_ued, text="k / k_m").grid(row=r, column=3, sticky="e")
        ttk.Entry(frm_ued, textvariable=self.var_ue_k, width=6).grid(row=r, column=4, sticky="w")
        ttk.Entry(frm_ued, textvariable=self.var_ue_km, width=6).grid(row=r, column=5, sticky="w"); r+=1
        ttk.Label(frm_ued, text="UE height [m]").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm_ued, textvariable=self.var_ue_height, width=8).grid(row=r, column=1, sticky="w")
        ttk.Label(frm_ued, text="indoor_percent [%]").grid(row=r, column=2, sticky="e")
        ttk.Entry(frm_ued, textvariable=self.var_ue_indoor, width=8).grid(row=r, column=3, sticky="w")
        for c in range(6): frm_ued.grid_columnconfigure(c, weight=1)

        # Preview opts só para Hotspot
        frm_prev = ttk.LabelFrame(root, text="Preview (Hotspot snapshot)")
        frm_prev.pack(fill="x", padx=4, pady=4)
        r=0
        ttk.Label(frm_prev, text="# BS por hotspot (small cells)").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm_prev, textvariable=self.var_hot_bs_per_hotspot, width=8).grid(row=r, column=1, sticky="w")
        ttk.Label(frm_prev, text="# UEs por hotspot").grid(row=r, column=2, sticky="e")
        ttk.Entry(frm_prev, textvariable=self.var_hot_ue_per_hotspot, width=8).grid(row=r, column=3, sticky="w")
        for c in range(4): frm_prev.grid_columnconfigure(c, weight=1)

    def _refresh_topo_fields(self, parent):
        for w in self.fr_topo_fields.winfo_children():
            w.destroy()
        t = self.topo_type.get()
        r=0
        if t == "HOTSPOT":
            ttk.Label(self.fr_topo_fields, text="intersite_distance [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_hot_isd, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="num_clusters (1/7)").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_hot_clusters, width=8).grid(row=r, column=3, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="num_hotspots_per_cell").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_hot_num_hotspots_per_cell, width=8).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="max_dist_hotspot_ue [m]").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_hot_max_dist_hotspot_ue, width=10).grid(row=r, column=3, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="min_dist_bs_hotspot [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_hot_min_dist_bs_hotspot, width=10).grid(row=r, column=1, sticky="w")
        elif t == "MACROCELL":
            ttk.Label(self.fr_topo_fields, text="intersite_distance [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_macro_isd, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="num_clusters (1/7)").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_macro_clusters, width=8).grid(row=r, column=3, sticky="w")
        elif t == "INDOOR":
            ttk.Label(self.fr_topo_fields, text="intersite_distance [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_indoor_isd, width=12).grid(row=r, column=1, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="n_rows").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_indoor_rows, width=8).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="n_columns").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_indoor_cols, width=8).grid(row=r, column=3, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="num_cells").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_indoor_cells, width=8).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="num_floors").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_indoor_floors, width=8).grid(row=r, column=3, sticky="w")
        elif t == "NTN":
            ttk.Label(self.fr_topo_fields, text="intersite_distance [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_ntn_isd, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="cell_radius [m]").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_ntn_cell_r, width=12).grid(row=r, column=3, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="bs_height [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_ntn_bs_h, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="bs_azimuth [deg]").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_ntn_az, width=12).grid(row=r, column=3, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="bs_elevation [deg]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_ntn_el, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="num_sectors").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_ntn_sectors, width=8).grid(row=r, column=3, sticky="w")
        elif t == "SINGLE_BS":
            ttk.Label(self.fr_topo_fields, text="cell_radius [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_sbs_radius, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="num_clusters (1/2)").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_sbs_clusters, width=8).grid(row=r, column=3, sticky="w")
        elif t == "MSS_DC":
            ttk.Label(self.fr_topo_fields, text="beam_radius [m]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_mss_beam_r, width=12).grid(row=r, column=1, sticky="w")
            ttk.Label(self.fr_topo_fields, text="num_beams").grid(row=r, column=2, sticky="e")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_mss_nbeams, width=8).grid(row=r, column=3, sticky="w"); r+=1
            ttk.Label(self.fr_topo_fields, text="min_elevation_from_es [deg]").grid(row=r, column=0, sticky="w")
            ttk.Entry(self.fr_topo_fields, textvariable=self.var_mss_min_el, width=10).grid(row=r, column=1, sticky="w")

    # ---------------- Preview logic (independente do SHARC) ----------------
    def _draw_preview(self):
        self.ax.clear()
        self.ax.set_aspect("equal"); self.ax.grid(True, alpha=0.25)
        t = self.topo_type.get()
        rng = np.random.RandomState(int(self.var_seed.get()))

        if t == "HOTSPOT":
            isd = float(self.var_hot_isd.get())
            ncl = int(self.var_hot_clusters.get())
            nhpc = int(self.var_hot_num_hotspots_per_cell.get())
            r_ue = float(self.var_hot_max_dist_hotspot_ue.get())
            dmin = float(self.var_hot_min_dist_bs_hotspot.get())
            bs_per_hot = int(self.var_hot_bs_per_hotspot.get())
            ue_per_hot = int(self.var_hot_ue_per_hotspot.get())

            centers = hex_center_grid(isd, ncl)  # macro-BS centers
            self.ax.scatter(centers[:,0], centers[:,1], marker="^", s=70, c="tab:orange", label="Macro BS")

            # desenhar “pizza” 3 setores por macro
            for cx, cy in centers:
                self._draw_sector_pizza(cx, cy, isd/np.sqrt(3), base_az=0.0, nsec=3, alpha=0.12)

            hotspot_bs = []
            ue_points = []

            for (cx, cy) in centers:
                # gere nhpc hotspots por célula, aleatórios, a >= dmin do macro-BS
                for _ in range(nhpc):
                    # raio aleatório entre dmin e ~0.8*cell_radius (heurístico)
                    cell_r = isd/np.sqrt(3)
                    rad = rng.uniform(dmin, 0.8*cell_r)
                    ang = rng.uniform(-math.pi, math.pi)
                    hx, hy = cx + rad*math.cos(ang), cy + rad*math.sin(ang)

                    # para cada hotspot, gere bs_per_hot BS (pequena célula)
                    for __ in range(bs_per_hot):
                        # pequena perturbação ~10 m
                        dx, dy = rng.normal(0, 10.0), rng.normal(0, 10.0)
                        bx, by = hx + dx, hy + dy
                        hotspot_bs.append((bx, by))

                    # UEs ao redor do hotspot (raio r_ue)
                    for __ in range(ue_per_hot):
                        if self.var_ue_dist_dist.get() == "RAYLEIGH":
                            # sigma ~ r_ue/2
                            sigma = r_ue/2.0
                            rr = rng.rayleigh(sigma)
                            rr = min(rr, r_ue)
                        else:
                            rr = rng.uniform(0, r_ue)

                        if self.var_ue_dist_az.get() == "NORMAL":
                            mu = 0.0
                            # std ~ (az_range/2) em rad
                            azmin, azmax = float(self.var_ue_az_min.get()), float(self.var_ue_az_max.get())
                            std = math.radians((azmax-azmin)/4.0) if azmax>azmin else math.radians(30.0)
                            th = rng.normal(mu, std)
                        else:
                            th = rng.uniform(-math.pi, math.pi)
                        ux, uy = hx + rr*math.cos(th), hy + rr*math.sin(th)
                        ue_points.append((ux, uy))

            if hotspot_bs:
                hb = np.array(hotspot_bs)
                self.ax.scatter(hb[:,0], hb[:,1], s=20, c="tab:red", label="Hotspot BS")
            if ue_points:
                ue = np.array(ue_points)
                self.ax.scatter(ue[:,0], ue[:,1], s=6, c="tab:blue", alpha=0.7, label="UEs")

            self.ax.legend(loc="upper right")
            self.ax.set_title("HOTSPOT – 1 snapshot (BS aleatórias por hotspot + UEs)")

        elif t == "MACROCELL":
            isd = float(self.var_macro_isd.get()); ncl = int(self.var_macro_clusters.get())
            centers = hex_center_grid(isd, ncl)
            self.ax.scatter(centers[:,0], centers[:,1], marker="^", s=70, c="tab:orange", label="Macro BS")
            for cx, cy in centers:
                self._draw_sector_pizza(cx, cy, isd/np.sqrt(3), base_az=0.0, nsec=3, alpha=0.12)
            self.ax.legend(loc="upper right")
            self.ax.set_title("MACROCELL – 3 setores por macro")

        elif t == "SINGLE_BS":
            r = float(self.var_sbs_radius.get())
            self.ax.scatter([0.0],[0.0], marker="^", s=80, c="tab:orange", label="BS")
            self._draw_sector_pizza(0.0, 0.0, r, base_az=0.0, nsec=3, alpha=0.12)
            self.ax.legend(loc="upper right")
            self.ax.set_title("SINGLE_BS")

        elif t == "INDOOR":
            # simple grid placeholder
            isd = float(self.var_indoor_isd.get()); rows=int(self.var_indoor_rows.get()); cols=int(self.var_indoor_cols.get())
            pts=[]
            for i in range(rows):
                for j in range(cols):
                    pts.append((j*isd, i*isd))
            pts=np.array(pts)
            self.ax.scatter(pts[:,0], pts[:,1], marker="s", s=60, c="tab:gray", label="Buildings")
            self.ax.legend(loc="upper right"); self.ax.set_title("INDOOR (preview)")

        elif t == "NTN":
            isd = float(self.var_ntn_isd.get()); cellr=float(self.var_ntn_cell_r.get())
            centers = hex_center_grid(isd, 7)
            self.ax.scatter(centers[:,0], centers[:,1], marker="^", s=70, c="tab:orange", label="NTN cell centers")
            for cx, cy in centers:
                circ = plt.Circle((cx, cy), cellr, fill=False, ls="--", lw=1.0, ec="tab:orange")
                self.ax.add_patch(circ)
            self.ax.legend(loc="upper right"); self.ax.set_title("NTN (footprints)")

        else:  # MSS_DC
            self.ax.text(0.5, 0.5, "MSS-DC preview esquemático", ha="center", va="center", transform=self.ax.transAxes)
            self.ax.set_title("MSS-DC (placeholder)")

        self.ax.set_xlabel("x [m]"); self.ax.set_ylabel("y [m]")
        self.ax.autoscale(enable=True, tight=True)
        self.canvas.draw()

    def _draw_sector_pizza(self, cx, cy, r, base_az=0.0, nsec=3, alpha=0.15):
        """Desenha wedges de setor."""
        for s in range(nsec):
            az = base_az + s*360.0/nsec
            wedge = Wedge((cx, cy), r, az-60/2, az+60/2,
                          facecolor="tab:green", alpha=alpha, edgecolor="tab:green", lw=0.6)
            self.ax.add_patch(wedge)

    # ---------------- YAML building ----------------
    def _current_general_cfg(self):
        return {
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

    def _current_imt_cfg(self):
        # Antena BS e UE (subset ParametersAntennaImt)  :contentReference[oaicite:7]{index=7}
        bs_ant = {
            "pattern": "ARRAY",
            "array": {
                "element_pattern": self.var_bs_elem_pattern.get(),
                "n_rows": int(self.var_bs_n_rows.get()),
                "n_columns": int(self.var_bs_n_cols.get()),
                "element_phi_3db": float(self.var_bs_phi3.get()),
                "element_theta_3db": float(self.var_bs_theta3.get()),
                "downtilt": float(self.var_bs_downtilt.get()),
            }
        }
        ue_ant = {
            "pattern": "ARRAY",
            "array": {
                "element_pattern": self.var_ue_elem_pattern.get(),
                "n_rows": int(self.var_ue_n_rows.get()),
                "n_columns": int(self.var_ue_n_cols.get()),
            }
        }

        # UE (subset ParametersImt.UE)  :contentReference[oaicite:8]{index=8}
        ue = {
            "k": int(self.var_ue_k.get()),
            "k_m": int(self.var_ue_km.get()),
            "height": float(self.var_ue_height.get()),
            "indoor_percent": float(self.var_ue_indoor.get()),
            "distribution_type": self.var_ue_dist_type.get(),
            "distribution_distance": self.var_ue_dist_dist.get(),
            "distribution_azimuth": self.var_ue_dist_az.get(),
            "azimuth_range": [float(self.var_ue_az_min.get()), float(self.var_ue_az_max.get())],
            "antenna": ue_ant
        }

        # Topologia IMT (ParametersImtTopology + específicos) :contentReference[oaicite:9]{index=9}
        t = self.topo_type.get()
        topo_params = {"type": t}
        if t == "HOTSPOT":  # :contentReference[oaicite:10]{index=10}
            topo_params["hotspot"] = {
                "intersite_distance": float(self.var_hot_isd.get()),
                "num_clusters": int(self.var_hot_clusters.get()),
                "num_hotspots_per_cell": int(self.var_hot_num_hotspots_per_cell.get()),
                "max_dist_hotspot_ue": float(self.var_hot_max_dist_hotspot_ue.get()),
                "min_dist_bs_hotspot": float(self.var_hot_min_dist_bs_hotspot.get()),
            }
        elif t == "MACROCELL":  # :contentReference[oaicite:11]{index=11}
            topo_params["macrocell"] = {
                "intersite_distance": float(self.var_macro_isd.get()),
                "num_clusters": int(self.var_macro_clusters.get()),
            }
        elif t == "INDOOR":  # :contentReference[oaicite:12]{index=12}
            topo_params["indoor"] = {
                "intersite_distance": float(self.var_indoor_isd.get()),
                "n_rows": int(self.var_indoor_rows.get()),
                "n_colums": int(self.var_indoor_cols.get()),
                "num_cells": int(self.var_indoor_cells.get()),
                "num_floors": int(self.var_indoor_floors.get()),
            }
        elif t == "NTN":  # :contentReference[oaicite:13]{index=13}
            topo_params["ntn"] = {
                "intersite_distance": float(self.var_ntn_isd.get()),
                "cell_radius": float(self.var_ntn_cell_r.get()),
                "bs_height": float(self.var_ntn_bs_h.get()),
                "bs_azimuth": float(self.var_ntn_az.get()),
                "bs_elevation": float(self.var_ntn_el.get()),
                "num_sectors": int(self.var_ntn_sectors.get()),
            }
        elif t == "SINGLE_BS":  # :contentReference[oaicite:14]{index=14}
            topo_params["single_bs"] = {
                "cell_radius": float(self.var_sbs_radius.get()),
                "num_clusters": int(self.var_sbs_clusters.get()),
            }
        else:  # MSS_DC – apenas campos básicos do ParametersImtMssDc  :contentReference[oaicite:15]{index=15}
            topo_params["mss_dc"] = {
                "beam_radius": float(self.var_mss_beam_r.get()),
                "num_beams": int(self.var_mss_nbeams.get()),
            }

        # bloco imt (subset coerente com ParametersImt)  :contentReference[oaicite:16]{index=16}
        imt = {
            "topology": topo_params,
            "bs": {
                "antenna": bs_ant
            },
            "ue": ue,
            # campos adicionais podem ser expostos depois (freq, BW, channel_model etc.)
        }
        return imt

    def _update_yaml_preview(self):
        g = self._current_general_cfg()
        imt = self._current_imt_cfg()
        text = build_yaml_text(g, imt)
        self.txt_yaml.delete("1.0", tk.END)
        self.txt_yaml.insert(tk.END, text)

    # ---------------- Save actions ----------------
    def _save_yaml(self):
        g = self._current_general_cfg()
        imt = self._current_imt_cfg()
        text = build_yaml_text(g, imt)
        suggested = f"{g['output_dir_prefix'] or 'scenario'}_{self.topo_type.get().lower()}.yaml"
        path = filedialog.asksaveasfilename(
            title="Salvar YAML",
            defaultextension=".yaml",
            initialfile=suggested,
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if not path:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        messagebox.showinfo("OK", f"YAML salvo em:\n{path}")

    def _save_image(self):
        suggested = f"topology_{self.topo_type.get().lower()}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            title="Salvar imagem",
            defaultextension=".png",
            initialfile=suggested,
            filetypes=[("PNG", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        self.fig.savefig(path, dpi=160, bbox_inches="tight")
        messagebox.showinfo("OK", f"Imagem salva em:\n{path}")

    # ---------------- Helpers ----------------
    def _pick_outdir(self):
        cur = self.var_outdir.get() or os.getcwd()
        if not os.path.isdir(cur): cur = os.getcwd()
        path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta de saída")
        if path:
            self.var_outdir.set(path.replace("\\","/") + "/")

    def _suggest_prefix(self):
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.var_prefix.set(f"output_imt_{ts}")

if __name__ == "__main__":
    App().mainloop()
