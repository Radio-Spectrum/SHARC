from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import * 
from sharc_gui.core import CoreMixin
from sharc_gui.tabs.general_tab import GeneralTabTabMixin
from sharc_gui.tabs.imt_tab import ImtTabTabMixin
from sharc_gui.tabs.victim_tab import VictimTabTabMixin
from sharc_gui.tabs.victim_earth_tab import VictimEarthTabTabMixin
from sharc_gui.tabs.preview_tab import PreviewTabTabMixin
from sharc_gui.tabs.runner_tab import RunnerTabTabMixin
from sharc_gui.tabs.results_tab import ResultsTabTabMixin

class App(tk.Tk, CoreMixin,
          GeneralTabTabMixin,
          ImtTabTabMixin,
          VictimTabTabMixin,
          VictimEarthTabTabMixin,
          PreviewTabTabMixin,
          RunnerTabTabMixin,
          ResultsTabTabMixin):
    def __init__(self):
        super().__init__()


        # ===== SSH PASSWORD MODE (PARAMIKO) =====
        self.ssh_use_password = tk.BooleanVar(value=True)
        self.ssh_password = tk.StringVar(value="7MLRfdkhUL")
        self.var_ssh_auth = tk.StringVar(value="KEY")
        self.ssh_client = None
        # ===== SSH TUNNEL VARIABLES =====
        self.var_use_tunnel = tk.BooleanVar(value=False)  # mostra/oculta túnel
        self.tunnel_bastion_host = tk.StringVar(value="164.41.75.34")
        self.tunnel_bastion_user = tk.StringVar(value="anatel")
        self.tunnel_bastion_port = tk.IntVar(value=13508)

        self.tunnel_internal_ip = tk.StringVar(value="192.168.0.204")
        self.tunnel_internal_port = tk.IntVar(value=22)

        self.tunnel_local_port = tk.IntVar(value=2222)
        self.tunnel_key_path = tk.StringVar(value="C:/Users/PC-CASA/OneDrive/Achiles/Pessoal/1 - UNB/3 - Pós-Graduação/3 - Pesquisas/Atuais/10 - Anatel 2/23 - Servidor/key")

        self.tunnel_status = tk.StringVar(value="🔴 Túnel Inativo")
        self.tunnel_process = None
        # ===== SSH GUI Variables =====
        self.var_run_mode = tk.StringVar(value="LOCAL")
        self.ssh_host = tk.StringVar(value="164.41.75.34")
        self.ssh_user = tk.StringVar(value="achiles.mota")
        self.ssh_port = tk.IntVar(value=2222)
        self.ssh_remote_dir = tk.StringVar(value="")
        self.ssh_use_tunnel = tk.BooleanVar(value=False)
        self.ssh_key_path = tk.StringVar()
        self.ssh_status = tk.StringVar(value="Desconectado")
        self.ssh_connected = False
        self._remote_downloading = set()   # YAMLs (iid/local_yaml) em download
        self._downloaded_yamls = set()
        
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
        self.path_raster = tk.StringVar(value=str(Path.cwd()/"sharc/topology/map/SEDAC_map2.TIFF"))
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
        self.var_auto_update = tk.BooleanVar(value=False)
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

        # ===========================
        # SINGLE_EARTH_STATION (Victim) tab variables
        # Add these in App.__init__ (after self.var_system is created)
        # ===========================
        # Basics
        self.se_frequency = tk.StringVar(value="8000")            # MHz
        self.se_bandwidth = tk.StringVar(value="40")            # MHz
        self.se_noise_temperature = tk.StringVar(value="513")    # K
        self.se_polarization_loss = tk.StringVar(value="0")    # dB (optional)

        self.se_adjacent_ch_reception = tk.StringVar(value="OFF")  # "ACS"|"OFF"
        self.se_adjacent_ch_selectivity = tk.StringVar(value="")   # dB
        self.se_adjacent_ch_emissions = tk.StringVar(value="OFF")  # "ACLR"|"SPECTRAL_MASK"|"OFF"
        self.se_adjacent_ch_leak_ratio = tk.StringVar(value="")    # dB (only if ACLR)
        self.se_spectral_mask = tk.StringVar(value="")             # only if SPECTRAL_MASK
        self.se_spurious_emissions = tk.StringVar(value="")        # dBm/MHz

        self.se_tx_power_density = tk.StringVar(value="-200")     # dBW/Hz
        self.se_height = tk.StringVar(value="20")               # m

        # Geometry - location
        self.se_loc_type = tk.StringVar(value="FIXED")        # FIXED|CELL|NETWORK|UNIFORM_DIST
        self.se_loc_fixed_x = tk.StringVar(value="15000.0")
        self.se_loc_fixed_y = tk.StringVar(value="0.0")
        self.se_loc_cell_min_dist_to_bs = tk.StringVar(value="15000")
        self.se_loc_network_min_dist_to_bs = tk.StringVar(value="20000")
        self.se_loc_ud_min_dist_to_center = tk.StringVar(value="15000")
        self.se_loc_ud_max_dist_to_center = tk.StringVar(value="20000")

        # Geometry - azimuth/elevation
        self.se_az_type = tk.StringVar(value="FIXED")         # UNIFORM_DIST|FIXED|POINTING_AT_IMT_CENTER
        self.se_az_fixed = tk.StringVar(value="0.0")
        self.se_az_ud_min = tk.StringVar(value="-180.0")
        self.se_az_ud_max = tk.StringVar(value="180.0")

        self.se_el_type = tk.StringVar(value="FIXED")         # UNIFORM_DIST|FIXED|POINTING_AT_IMT_CENTER
        self.se_el_fixed = tk.StringVar(value="0.0")
        self.se_el_ud_min = tk.StringVar(value="0.0")
        self.se_el_ud_max = tk.StringVar(value="90.0")

        # Antenna
        self.se_ant_pattern = tk.StringVar(value="OMNI")
        self.se_ant_gain = tk.StringVar(value="5")             # dBi (not required for ARRAY, but keep)
        # Diameter-family patterns
        self.se_ant_diameter = tk.StringVar(value="5")         # m
        # Envelope gain (MODIFIED ITU-R S.465)
        self.se_ant_envelope_gain = tk.StringVar(value="5")    # dB
        # S.672
        self.se_ant_3db = tk.StringVar(value="5")
        self.se_ant_l_s = tk.StringVar(value="-25")
        # F.1245_fs
        self.se_ant_f1245_gain = tk.StringVar(value="-25")
        self.se_ant_f1245_diameter = tk.StringVar(value="5")
        self.se_ant_f1245_frequency = tk.StringVar(value="5")

        # Channel model
        self.se_channel_model = tk.StringVar(value="FSPL")    # FSPL|P452

        # P452 (defaults from ParametersP452)
        self.p452_atmospheric_pressure = tk.StringVar(value="1017")
        self.p452_air_temperature = tk.StringVar(value="293.15")
        self.p452_N0 = tk.StringVar(value="352.58")
        self.p452_delta_N = tk.StringVar(value="60")
        self.p452_percentage_p = tk.StringVar(value="RANDOM")
        self.p452_Dct = tk.StringVar(value="100")
        self.p452_Dcr = tk.StringVar(value="101")
        self.p452_Hte = tk.StringVar(value="18.0")
        self.p452_Hre = tk.StringVar(value="3.0")
        self.p452_tx_lat = tk.StringVar(value="-15.46")
        self.p452_rx_lat = tk.StringVar(value="-15.47")
        self.p452_polarization = tk.StringVar(value="horizontal")
        self.p452_clutter_loss = tk.BooleanVar(value=True)
        self.p452_clutter_type = tk.StringVar(value="one_end")
        self.p452_is_terrain = tk.BooleanVar(value=False)

        # UI
        self._build_ui()

    def _build_ui(self):
            nb = ttk.Notebook(self)
            nb.pack(fill="both", expand=True)

            tab_general = ttk.Frame(nb, padding=10)
            tab_imt = ttk.Frame(nb, padding=10)
            tab_victim = ttk.Frame(nb, padding=10)
            tab_victim_earth = ttk.Frame(nb, padding=10)
            tab_preview = ttk.Frame(nb, padding=(10, 6, 10, 10))
            tab_runner = ttk.Frame(nb, padding=10)
            tab_results = ttk.Frame(nb)

            nb.add(tab_general, text="General")
            nb.add(tab_imt, text="IMT")
            nb.add(tab_victim, text="Single Space Station")
            nb.add(tab_victim_earth, text="Single Earth Station")
            # Start hidden; shown only when system == SINGLE_EARTH_STATION
            nb.hide(tab_victim_earth)
            nb.add(tab_preview, text="Visualização 3D & Export")
            nb.add(tab_runner, text="Runner")
            nb.add(tab_results, text="Resultados")

            self._tab_general(tab_general)
            self._tab_imt(tab_imt)
            self._tab_victim(tab_victim)
            self._tab_victim_earth(tab_victim_earth)

            def _toggle_victim_tabs(*_):
                sysv = (self.var_system.get() or '').strip()
                try:
                    tabs = nb.tabs()
                    # Ensure both exist at least once
                    if str(tab_victim) not in tabs:
                        nb.add(tab_victim, text='Single Space Station')
                    if str(tab_victim_earth) not in tabs:
                        nb.add(tab_victim_earth, text='Single Earth Station')

                    if sysv == 'SINGLE_EARTH_STATION':
                        nb.hide(tab_victim)
                        # Make sure earth is visible
                        try: nb.add(tab_victim_earth, text='Single Earth Station')
                        except Exception: pass
                        #nb.select(tab_victim_earth)
                    else:
                        nb.hide(tab_victim_earth)
                        try: nb.add(tab_victim, text='Single Space Station')
                        except Exception: pass
                        #nb.select(tab_victim)
                except Exception:
                    pass

            # React to system changes
            self.var_system.trace_add('write', _toggle_victim_tabs)
            _toggle_victim_tabs()
            self._tab_preview(tab_preview)
            self._tab_runner(tab_runner)
            self._tab_results(tab_results)