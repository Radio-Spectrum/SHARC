import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import queue
import os
import itertools
import ast
from pathlib import Path

# --- Importações dos Módulos Locais ---
from config import DEFAULTS, RESULT_FIELDNAME_TO_PLOT_INFO
from utils import build_yaml_text
from managers import RunnerManager
from ui.tabs import (
    GeneralTab, IMTTab, VictimTab,
    PreviewTab, RunnerTab, ResultsTab
)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SHARC – YAML GUI Modularizada")
        self.geometry("1280x900")
        self.minsize(1100, 800)

        # 1. Fila para Thread-Safety (Backend -> UI)
        self.line_q = queue.Queue()

        # 2. Inicializar Variáveis de Estado (Model)
        self._init_variables()

        # 3. Inicializar Backend (Runner Manager)
        # Passamos callbacks que colocam dados na fila, garantindo thread-safety
        self.runner_manager = RunnerManager(
            log_callback=self._safe_log,
            update_row_callback=self._safe_update_row
        )

        # 4. Construir Interface (View)
        self._build_ui()

        # 5. Iniciar Loop de Consumo da Fila
        self.after(100, self._drain_log_queue)

    def _init_variables(self):
        """Inicializa todas as variáveis Tkinter compartilhadas pelas abas."""

        # --- General ---
        self.var_seed = tk.IntVar(value=DEFAULTS["seed"])
        self.var_snaps = tk.IntVar(value=DEFAULTS["num_snapshots"])
        self.var_overwrite = tk.BooleanVar(value=False)
        self.var_outdir = tk.StringVar(value=DEFAULTS["output_dir"])
        self.var_yaml_dir = tk.StringVar(value=DEFAULTS["output_dir"])
        self.var_prefix = tk.StringVar(value="output_mss_{long}")
        self.var_system = tk.StringVar(value="SINGLE_SPACE_STATION")
        self.var_imt_link = tk.StringVar(value="DOWNLINK")
        self.var_adj = tk.BooleanVar(value=False)
        self.var_coch = tk.BooleanVar(value=True)

        # --- IMT (Gerais) ---
        self.imt_min_sep = tk.StringVar(value="35")
        self.imt_interfered = tk.BooleanVar(value=False)
        self.imt_freq = tk.StringVar(value="8150")
        self.imt_bw = tk.StringVar(value="100")
        self.imt_rb_bw = tk.StringVar(value="0.18")
        self.imt_spec_mask = tk.StringVar(value="IMT-2020")
        self.imt_spurious = tk.StringVar(value="-13")
        self.imt_adj_ant_model = tk.StringVar(value="SINGLE_ELEMENT")
        self.imt_guard_ratio = tk.StringVar(value="0.1")

        # --- Topologia (IMT) ---
        self.topo_c_lat = tk.StringVar(value="-15.793889")
        self.topo_c_lon = tk.StringVar(value="-47.882778")
        self.topo_c_alt = tk.StringVar(value="0")
        self.topo_type = tk.StringVar(value="Macro_countries")
        self.topo_dist_type = tk.StringVar(value="Urban")
        self.topo_num_bs = tk.StringVar(value="100")
        self.topo_cell_radius = tk.StringVar(value="400")
        self.topo_rng = tk.StringVar(value="10")
        self.topo_raster_enc = tk.StringVar(value="Denspop")

        # Texto default para países (usado na inicialização da aba IMT)
        self.topo_countries = tk.StringVar(value="\n".join([
            "Brazil", "Argentina", "Uruguay", "Paraguay", "Chile",
            "Bolivia", "Peru", "Ecuador", "Colombia", "Venezuela"
        ]))

        # Caminhos de Mapas (Padrão ou Vazio)
        self.path_shp = tk.StringVar(
            value=str(Path.cwd()/"sharc/topology/map/ne_110m_admin_0_countries.shp"))
        self.path_raster = tk.StringVar(
            value=str(Path.cwd()/"sharc/topology/map/SEDAC_map2.tiff"))
        self.raster_encoding = tk.StringVar(value="indexed")
        self.sedac_mode = tk.StringVar(value="log")
        self.sedac_min = tk.StringVar(value="1.0")
        self.sedac_max = tk.StringVar(value="1e4")
        self.pixel_area_method = tk.StringVar(value="spherical")

        # --- Topologia (Específicos) ---
        self.macro_intersite = tk.StringVar(value="600")
        self.macro_wrap = tk.BooleanVar(value=False)
        self.macro_clusters = tk.StringVar(value="1")

        self.hotspot_intersite = tk.StringVar(value="600")
        self.hotspot_wrap = tk.BooleanVar(value=False)
        self.hotspot_clusters = tk.StringVar(value="1")
        self.hotspot_num_per_cell = tk.StringVar(value="3")
        self.hotspot_max_dist_ue = tk.StringVar(value="400.0")
        self.hotspot_min_dist_bs = tk.StringVar(value="40.0")

        self.sbs_intersite = tk.StringVar(value="600")
        self.sbs_cell_radius = tk.StringVar(value="400")
        self.sbs_clusters = tk.StringVar(value="1")
        self.sbs_azimuth = tk.StringVar(value="120")

        # --- BS ---
        self.bs_load_prob = tk.StringVar(value="0.2")
        self.bs_power = tk.StringVar(value="22")
        self.bs_height = tk.StringVar(value="18")
        self.bs_nf = tk.StringVar(value="6")
        self.bs_ohmic = tk.StringVar(value="0")
        self.bs_norm = tk.BooleanVar(value=False)
        self.bs_elem_pat = tk.StringVar(value="M2101")
        self.bs_min_arr_gain = tk.StringVar(value="-200")
        self.bs_h_steer = (tk.StringVar(value="-60"), tk.StringVar(value="60"))
        self.bs_v_steer = (tk.StringVar(value="90"),
                           tk.StringVar(value="100"))
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

        # --- UE ---
        self.ue_k = tk.StringVar(value="3")
        self.ue_km = tk.StringVar(value="1")
        self.ue_indoor = tk.StringVar(value="70")
        self.ue_dist_type = tk.StringVar(value="Macro_countries")
        self.ue_dist_distance = tk.StringVar(value="RAYLEIGH")
        self.ue_dist_azimuth = tk.StringVar(value="NORMAL")
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
        self.ue_sub_enabled = tk.BooleanVar(value=False)
        self.ue_sub_rows = tk.StringVar(value="1")
        self.ue_sub_evspace = tk.StringVar(value="1.0")
        self.ue_sub_e_downtilt = tk.StringVar(value="0.0")

        self.ul_att = tk.StringVar(value="0.4")
        self.ul_sinr_min = tk.StringVar(value="-10")
        self.ul_sinr_max = tk.StringVar(value="22")
        self.dl_att = tk.StringVar(value="0.6")
        self.dl_sinr_min = tk.StringVar(value="-10")
        self.dl_sinr_max = tk.StringVar(value="30")
        self.ch_model = tk.StringVar(value="UMa")
        self.shadowing = tk.BooleanVar(value=True)

        # --- Victim (Single Space Station) ---
        self.v_freq = tk.StringVar(value="8150")
        self.v_bw = tk.StringVar(value="40")
        self.v_txpsd = tk.StringVar(value="-200")
        self.v_pol_loss = tk.StringVar(value="0")
        self.v_tnoise = tk.StringVar(value="500")
        self.v_ch_model = tk.StringVar(value="P619")
        self.v_season = tk.StringVar(value="SUMMER")
        self.v_p619_clutter = tk.StringVar(value="Mid")
        self.v_p619_below_rooftop = tk.StringVar(value="65")
        self.ss_is_global_cs = tk.BooleanVar(value=True)
        self.v_alt = tk.StringVar(value="35786000")
        self.v_fix_lat = tk.StringVar(value="0")
        self.v_fix_lon = tk.StringVar(value="-110")
        self.v_es_alt = tk.StringVar(value="200")
        self.v_es_lat = tk.StringVar(value="-10.871349")
        self.v_es_lon = tk.StringVar(value="-51.6424333")
        self.v_az_type = tk.StringVar(value="POINTING_AT_IMT")
        self.v_el_type = tk.StringVar(value="POINTING_AT_IMT")
        self.v_ant_pattern = tk.StringVar(value="ITU-R S.672")
        self.v_ant_gain = tk.StringVar(value="30")
        self.v_s672_3db = tk.StringVar(value="5")
        self.v_s672_ls = tk.StringVar(value="-20")

        # --- Preview / Resultados ---
        self.var_show_gainmap = tk.BooleanVar(value=False)
        self.var_gain_vmin = tk.StringVar(value="auto")
        self.var_gain_vmax = tk.StringVar(value="auto")
        self.show_borders = tk.BooleanVar(value=True)
        self.var_rows = tk.IntVar(value=1)
        self.var_cols = tk.IntVar(value=1)
        self.var_auto_update = tk.BooleanVar(value=True)
        self.var_update_period_ms = tk.IntVar(value=2000)
        self.var_xlog = tk.BooleanVar(value=False)
        self.var_export_dpi = tk.IntVar(value=200)
        self.var_export_fmt = tk.StringVar(value="PNG")

        # --- Runner ---
        self.var_run_mode = tk.StringVar(value="LOCAL")
        self.var_max_workers = tk.IntVar(value=2)
        self.run_folder = tk.StringVar(value=DEFAULTS["output_dir"])

        # --- SSH / Túnel ---
        self.ssh_host = tk.StringVar(value=DEFAULTS["ssh_host"])
        self.ssh_user = tk.StringVar(value=DEFAULTS["ssh_user"])
        self.ssh_port = tk.IntVar(value=DEFAULTS["ssh_port"])
        self.ssh_remote_dir = tk.StringVar(
            value=DEFAULTS["remote_base_dir"] + "/sharc/campaigns")
        self.ssh_use_tunnel = tk.BooleanVar(value=False)
        self.ssh_use_password = tk.BooleanVar(value=True)
        self.ssh_key_path = tk.StringVar(value="")
        self.ssh_status = tk.StringVar(value="Desconectado")
        self.var_git_branch = tk.StringVar()

        self.tunnel_bastion_host = tk.StringVar(
            value=DEFAULTS["tunnel_bastion_host"])
        self.tunnel_bastion_user = tk.StringVar(
            value=DEFAULTS["tunnel_bastion_user"])
        self.tunnel_bastion_port = tk.IntVar(
            value=DEFAULTS["tunnel_bastion_port"])
        self.tunnel_internal_ip = tk.StringVar(
            value=DEFAULTS["tunnel_internal_ip"])
        self.tunnel_internal_port = tk.IntVar(
            value=DEFAULTS["tunnel_internal_port"])
        self.tunnel_local_port = tk.IntVar(value=DEFAULTS["tunnel_local_port"])
        self.tunnel_key_path = tk.StringVar(value=DEFAULTS["tunnel_key_path"])
        self.tunnel_status = tk.StringVar(value="🔴 Túnel Inativo")

        self.main_cli_path = tk.StringVar(value=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "main_cli.py"))

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # Cria os frames das abas
        tab_general = ttk.Frame(nb, padding=10)
        tab_imt = ttk.Frame(nb, padding=10)
        tab_victim = ttk.Frame(nb, padding=10)
        tab_preview = ttk.Frame(nb, padding=(10, 6, 10, 10))
        tab_runner = ttk.Frame(nb, padding=10)
        tab_results = ttk.Frame(nb)

        # Adiciona ao Notebook
        nb.add(tab_general, text="General")
        nb.add(tab_imt, text="IMT")
        nb.add(tab_victim, text="Single Space Station")
        nb.add(tab_preview, text="Visualização 3D & Export")
        nb.add(tab_runner, text="Runner")
        nb.add(tab_results, text="Resultados")

        # Instancia as classes modulares
        # Passamos 'self' para que elas acessem as variáveis declaradas acima
        self.tab_general = GeneralTab(self, tab_general)
        self.tab_imt = IMTTab(self, tab_imt)
        self.tab_victim = VictimTab(self, tab_victim)
        self.tab_preview = PreviewTab(self, tab_preview)
        self.tab_runner = RunnerTab(self, tab_runner)
        self.tab_results = ResultsTab(self, tab_results)

    # ---------------- Thread Safety & Logs ----------------

    def _safe_log(self, msg):
        """Callback para backend colocar logs na fila."""
        self.line_q.put(("log", msg))

    def _safe_update_row(self, data):
        """Callback para backend atualizar Treeview."""
        self.line_q.put(("row", data))

    def _drain_log_queue(self):
        """Consome a fila na thread principal e atualiza UI."""
        try:
            while True:
                item = self.line_q.get_nowait()
                msg_type = item[0]
                payload = item[1]

                if msg_type == "log":
                    # Atualiza o log na aba Runner
                    if hasattr(self.tab_runner, 'txt_log'):
                        w = self.tab_runner.txt_log
                        w.configure(state="normal")
                        w.insert("end", payload +
                                 ("\n" if not payload.endswith("\n") else ""))
                        w.see("end")
                        w.configure(state="disabled")
                    else:
                        print(payload)

                elif msg_type == "row":
                    # Atualiza Treeview na aba Runner
                    if hasattr(self.tab_runner, 'tree'):
                        tree = self.tab_runner.tree
                        iid = payload["iid"]
                        if tree.exists(iid):
                            cur = list(tree.item(iid, "values"))
                            if payload["status"] is not None:
                                cur[1] = payload["status"]
                            if payload["snap"] is not None:
                                cur[2] = payload["snap"]
                            if payload["pct"] is not None:
                                cur[3] = payload["pct"]
                            if payload["eta"] is not None:
                                cur[4] = payload["eta"]
                            tree.item(iid, values=cur)

        except queue.Empty:
            pass

        self.after(100, self._drain_log_queue)

    # ---------------- Geração de YAML ----------------

    def _num_or_str(self, s):
        """Helper para converter entrada de UI em número ou string (placeholder)."""
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return float(s)
        s2 = str(s).strip()
        try:
            return float(s2)
        except:
            return s2

    def current_yaml_dict(self) -> dict:
        """Coleta dados de todas as abas e retorna o dict raiz do YAML."""

        # 1. General
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

        # 2. Topology
        topo_type = str(self.topo_type.get())
        topology = {
            "central_latitude": self._num_or_str(self.topo_c_lat.get()),
            "central_longitude": self._num_or_str(self.topo_c_lon.get()),
            "central_altitude": self._num_or_str(self.topo_c_alt.get()),
            "type": topo_type,
        }

        if topo_type == "Macro_countries":
            # Acessa o widget Text da aba IMT
            raw_txt = self.tab_imt.txt_countries.get("1.0", "end")
            country_names = [c.strip()
                             for c in raw_txt.splitlines() if c.strip()]

            enc_ui = (self.topo_raster_enc.get() or "").strip()
            pop_raster = self.path_raster.get().strip() if enc_ui != "Uniforme" else ""

            topology["macrocell_countries"] = {
                "country_names": country_names,
                "num_bs_total": int(self._num_or_str(self.topo_num_bs.get())),
                "cell_radius": self._num_or_str(self.topo_cell_radius.get()),
                "rng_seed": int(self._num_or_str(self.topo_rng.get())),
                "dist_type": self.topo_dist_type.get(),
                "countries_shapefile": self.path_shp.get().strip() or None,
                "population_raster": pop_raster or None,
            }
            if enc_ui != "Uniforme":
                topology["macrocell_countries"]["raster_encoding"] = "indexed"

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
            az_text = (self.sbs_azimuth.get() or "").strip()
            try:
                sbs_az = [float(x.strip())
                          for x in az_text.split(",")] if az_text else None
            except:
                sbs_az = az_text

            topology["single_bs"] = {
                "intersite_distance": self._num_or_str(self.sbs_intersite.get()),
                "cell_radius": self._num_or_str(self.sbs_cell_radius.get()),
                "num_clusters": int(self._num_or_str(self.sbs_clusters.get())),
                "azimuth": sbs_az,
            }

        # 3. IMT Structure
        # ... Construção complexa do dicionário IMT ...
        # Para brevidade, simplificando a montagem (igual ao código original)
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
        if self.ue_sub_enabled.get():
            ue_array["subarray"] = {
                "is_enabled": True,
                "n_rows": self._num_or_str(self.ue_sub_rows.get()),
                "element_vert_spacing": self._num_or_str(self.ue_sub_evspace.get()),
                "eletrical_downtilt": self._num_or_str(self.ue_sub_e_downtilt.get()),
            }

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
        if self.ue_dist_type.get().upper() == "ANGLE_AND_DISTANCE":
            ue_block["distribution_distance"] = self.ue_dist_distance.get()
            ue_block["distribution_azimuth"] = self.ue_dist_azimuth.get()

        bs_array = {
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
                "antenna": {"array": bs_array}
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

        # 4. Single Space Station
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
                "altitude": self._num_or_str(self.v_alt.get()),
                "location": {
                    "type": "FIXED",
                    "fixed": {"lat_deg": self._num_or_str(self.v_fix_lat.get()), "long_deg": self._num_or_str(self.v_fix_lon.get())}
                },
                "es_altitude": self._num_or_str(self.v_es_alt.get()),
                "es_lat_deg": self._num_or_str(self.v_es_lat.get()),
                "es_long_deg": self._num_or_str(self.v_es_lon.get()),
                "azimuth": {"type": self.v_az_type.get()},
                "elevation": {"type": self.v_el_type.get()},
            },
            "antenna": {
                "pattern": self.v_ant_pattern.get(),
                "gain": self._num_or_str(self.v_ant_gain.get()),
                "itu_r_s_672": ({
                    "antenna_3_dB": self._num_or_str(self.v_s672_3db.get()),
                    "antenna_l_s": self._num_or_str(self.v_s672_ls.get()),
                } if self.v_ant_pattern.get() == "ITU-R S.672" else None)
            }
        }
        if single_space_station["antenna"]["itu_r_s_672"] is None:
            del single_space_station["antenna"]["itu_r_s_672"]

        return {"general": general, "imt": imt, "single_space_station": single_space_station}

    def _deep_format(self, obj, combo):
        """Aplica .format(**combo) recursivamente."""
        if isinstance(obj, dict):
            return {k: self._deep_format(v, combo) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_format(v, combo) for v in obj]
        if isinstance(obj, str):
            try:
                return obj.format(**combo)
            except:
                return obj
        return obj

    def save_yaml_to_yamldir(self):
        self._generate_and_save_yaml(self.var_yaml_dir.get())

    def save_yaml_dialog_multicombos(self):
        initdir = self.var_yaml_dir.get() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Escolha um nome (usaremos a pasta)",
            defaultextension=".yaml",
            initialdir=initdir,
            initialfile=(self.var_prefix.get() or "scenario") + ".yaml"
        )
        if path:
            outdir = os.path.dirname(path)
            self._generate_and_save_yaml(outdir)
            self.var_yaml_dir.set(outdir)

    def _generate_and_save_yaml(self, outdir):
        if not outdir:
            return
        os.makedirs(outdir, exist_ok=True)

        # Coleta combinações da aba General
        tree = self.tab_general.var_table
        names, lists = [], []

        for iid in tree.get_children():
            name, vals = tree.item(iid, "values")
            try:
                vlist = ast.literal_eval(vals)
                names.append(str(name))
                lists.append(list(vlist))
            except:
                messagebox.showwarning(
                    "Erro", f"Valores inválidos para variável {name}")
                return

        combos = [dict(zip(names, p))
                  for p in itertools.product(*lists)] if names else [{}]
        root = self.current_yaml_dict()
        base_prefix = root["general"]["output_dir_prefix"] or "scenario"

        for combo in combos:
            prefix = base_prefix
            try:
                prefix = prefix.format(**combo)
            except:
                pass

            root_fmt = self._deep_format(root, combo)
            text = build_yaml_text(root_fmt)

            fname = os.path.join(outdir, f"{prefix}.yaml")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)

        messagebox.showinfo(
            "Sucesso", f"{len(combos)} arquivo(s) gerado(s) em:\n{outdir}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
