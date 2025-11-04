"""
Main application class: holds shared variables and creates the notebook tabs.
Tabs are built by separate modules (tab_*.py).
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import queue

# Tab builder imports (each module exposes build_<tab>_tab(app, frame))
from ui.tab_general import build_general_tab
from ui.tab_imt import build_imt_tab
from ui.tab_victim import build_victim_tab
from ui.tab_preview import build_preview_tab
from ui.tab_runner import build_runner_tab
from ui.tab_results import build_results_tab

# Note: The original code assumes 'Path', 'queue', 'os', 
# and 'RESULT_FIELDNAME_TO_PLOT_INFO' are defined/imported elsewhere.

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

        # ------ IMT: General ------
        self.imt_min_sep = tk.StringVar(value="35")
        self.imt_interfered = tk.BooleanVar(value=False)
        self.imt_freq = tk.StringVar(value="8150")
        self.imt_bw = tk.StringVar(value="100")       # StringVar to accept {bw}
        self.imt_rb_bw = tk.StringVar(value="0.18")
        self.imt_spec_mask = tk.StringVar(value="IMT-2020")
        self.imt_spurious = tk.StringVar(value="-13")
        self.imt_adj_ant_model = tk.StringVar(value="SINGLE_ELEMENT")
        self.imt_guard_ratio = tk.StringVar(value="0.1")

        # ------ Topology: COUNTRIES ------
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
        
        # ------ Topology: TYPE selector ------
        self.topo_type = tk.StringVar(value="Macro_countries")  # will be controlled by Combobox

        # ------ TOPOS: MACROCELL ------
        self.macro_intersite = tk.StringVar(value="600")           # None by default (empty shows None)
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
        self.sbs_azimuth = tk.StringVar(value="120")               # accepts list "0,120,240" or empty
        
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
        # --- UE: distribution ---
        self.ue_dist_type = tk.StringVar(value="Macro_Countries")  # "Macro_Countries", UNIFORM, CELL, UNIFORM_IN_CELL, ANGLE_AND_DISTANCE
        self.ue_dist_distance = tk.StringVar(value="RAYLEIGH")   # RAYLEIGH | UNIFORM | SQRT(UNIFORM)
        self.ue_dist_azimuth  = tk.StringVar(value="NORMAL")     # NORMAL | UNIFORM
        # azimuth_range required by outdoor generation
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
        # --- UE: sub-array (optional) ---
        self.ue_sub_enabled     = tk.BooleanVar(value=False)
        self.ue_sub_rows        = tk.StringVar(value="1")
        self.ue_sub_evspace     = tk.StringVar(value="1.0")
        self.ue_sub_e_downtilt  = tk.StringVar(value="0.0")

        # ------ Single Space Station (victim) ------
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

        # Pointing types (export only; viz uses spacecraft->ES)
        self.v_az_type = tk.StringVar(value="POINTING_AT_IMT")
        self.v_el_type = tk.StringVar(value="POINTING_AT_IMT")

        # Antenna
        self.v_ant_pattern = tk.StringVar(value="ITU-R S.672")
        self.v_ant_gain = tk.StringVar(value="30")
        self.v_s672_3db = tk.StringVar(value="5")
        self.v_s672_ls = tk.StringVar(value="-20")
        self.var_show_gainmap = tk.BooleanVar(value=False)
        self.var_gain_vmin = tk.StringVar(value="auto")  # or e.g.: "30"
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

        # ---- Results (plots) ----
        self.res_dirs = []  # list of selected folders (strings)
        self.var_auto_update = tk.BooleanVar(value=True)
        self.var_update_period_ms = tk.IntVar(value=2000)
        self.var_rows = tk.IntVar(value=1)
        self.var_cols = tk.IntVar(value=1)
        self._plot_auto_job = None  # job id from after()
        
        # ---- Results: extras ----
        self.var_xlog = tk.BooleanVar(value=False)        # log scale on X-axis
        self.var_export_dpi = tk.IntVar(value=200)        # export DPI
        self.var_export_fmt = tk.StringVar(value="PNG")   # PNG, SVG, PDF

        # Global reference lines (list of dicts: {"x": float, "label": str})
        self.ref_lines = []
        # configuration for each subplot: list of dicts {"field": str, "mode": "CDF"/"CCDF"}
        self.result_fields = sorted(list(RESULT_FIELDNAME_TO_PLOT_INFO.keys()))
        # max subplot capacity (e.g., 9 panels)
        self._max_axes = 9
        # field/mode/yscale/refs (refs in %, e.g.: "5,10,50")
        self._axes_cfg = [{
            "field": self.result_fields[0],
            "mode": "CDF",         # or "CCDF"
            "yscale": "Linear",    # or "Log"
            "refs": ""             # e.g.: "5,10"
        } for _ in range(self._max_axes)]
        
        # UI
        self._build_ui()

    # ---------------- UI builder ----------------
    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        tab_general = ttk.Frame(nb, padding=10)
        tab_imt = ttk.Frame(nb, padding=120)
        tab_victim = ttk.Frame(nb, padding=10)
        tab_preview = ttk.Frame(nb, padding=(10, 6, 10, 10))
        tab_runner = ttk.Frame(nb, padding=10)
        tab_results = ttk.Frame(nb)

        nb.add(tab_general, text="General")
        nb.add(tab_imt, text="IMT")
        nb.add(tab_victim, text="Single Space Station")
        nb.add(tab_preview, text="3D Visualization & Export")
        nb.add(tab_runner, text="Runner")
        nb.add(tab_results, text="Results")

        self.build_general_tab(tab_general)
        self.build_imt_tab(tab_imt)
        self.build_victim_tab(tab_victim)
        self.build_preview_tab(tab_preview)
        self.build_runner_tab(tab_runner)
        self.build_results_tab(tab_results)