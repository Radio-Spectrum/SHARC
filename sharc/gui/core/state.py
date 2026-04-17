import tkinter as tk
from pathlib import Path
import sys
from functools import lru_cache

# --- Attempt to import DEFAULTS ---
try:
    from config import DEFAULTS
except ImportError:
    DEFAULTS = {
        "seed": 42, "num_snapshots": 10, "output_dir": "outputs",
        "default_dir": "",
        "ssh_host": "", "ssh_user": "", "ssh_port": 22,
        "remote_base_dir": "~/SHARC",
        "tunnel_bastion_host": "",
        "tunnel_bastion_user": "", "tunnel_bastion_port": 22,
        "tunnel_internal_ip": "", "tunnel_internal_port": 80,
        "tunnel_local_port": 8080, "tunnel_key_path": ""
    }

# --- GLOBAL PROJECT LOCATION FUNCTION ---


@lru_cache(maxsize=1)
def get_sharc_root() -> Path:
    try:
        current_path = Path(__file__).resolve()
    except NameError:
        current_path = Path.cwd()

    for parent in [current_path] + list(current_path.parents):
        if (parent / "topology").exists() and (parent / "topology").is_dir():
            return parent
        if parent.name.lower() == 'sharc':
            return parent

    print("WARNING: 'sharc' root not found automatically. Using script directory.")
    return current_path.parent


class AppState:
    """
    Class responsible solely for initializing and storing the application state (Tkinter variables).
    """

    def __init__(self):
        try:
            if not tk._default_root:
                pass
        except:
            pass

        self.project_root = get_sharc_root()

        self._create_vars()

    def _add(self, value, var_type=str):
        """
        Helper to create variables.
        CRITICAL CHANGE: int and float are now created as StringVar to allow 
        variable injection (e.g., "{frequency}") in the UI.
        """
        try:
            if var_type == bool:
                # Handle "True"/"False" strings and 1/0 integers
                if isinstance(value, str):
                    val = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    val = bool(value)
                return tk.BooleanVar(value=val)

            else:
                # EVERYTHING else (int, float, str) becomes StringVar.
                # This allows the user to type "{my_var}" into a numeric field.
                # Conversion to number happens only during YAML generation.
                return tk.StringVar(value=str(value) if value is not None else "")

        except (ValueError, TypeError) as e:
            print(
                f"ERROR: Failed to cast value '{value}'. Using empty string.")
            return tk.StringVar(value="")

    def _create_vars(self):
        """Initializes all state variables grouped by functional area."""

        # --- General Settings ---
        self.var_seed = self._add(DEFAULTS.get("seed", 42), int)
        self.var_snaps = self._add(DEFAULTS.get("num_snapshots", 10), int)
        self.var_overwrite = self._add(False, bool)

        # Output Directory
        default_out = Path(DEFAULTS.get("output_dir", "outputs"))
        if not default_out.is_absolute():
            abs_out_dir = self.project_root / default_out
        else:
            abs_out_dir = default_out

        self.var_outdir = self._add(abs_out_dir.as_posix())
        self.var_yaml_dir = self._add(abs_out_dir.as_posix())

        self.var_prefix = self._add("output_mss_{long}")
        self.var_system = self._add("SINGLE_SPACE_STATION")
        self.var_imt_link = self._add("DOWNLINK")
        self.var_adj = self._add(False, bool)
        self.var_coch = self._add(True, bool)

        # --- IMT (International Mobile Telecommunications) ---
        self.imt_min_sep = self._add("35")
        self.imt_interfered = self._add(False, bool)
        self.imt_freq = self._add("8150")
        self.imt_bw = self._add("100")
        self.imt_rb_bw = self._add("0.18")
        self.imt_spec_mask = self._add("IMT-2020")
        self.imt_spurious = self._add("-13")
        self.imt_adj_ant_model = self._add("SINGLE_ELEMENT")
        self.imt_guard_ratio = self._add("0.1")

        # --- Topology ---
        self.topo_c_lat = self._add("-15.793889")
        self.topo_c_lon = self._add("-47.882778")
        self.topo_c_alt = self._add("0")
        self.topo_type = self._add("Macro_countries")
        self.topo_dist_type = self._add("Urban")
        self.topo_num_bs = self._add(DEFAULTS.get("topo_num_bs", "100"))
        self.topo_cell_radius = self._add("400")
        self.topo_rng = self._add("10")
        self.topo_raster_enc = self._add("Denspop")

        self.topo_countries = self._add("\n".join([
            "Brazil", "Argentina", "Uruguay", "Paraguay", "Chile",
            "Bolivia", "Peru", "Ecuador", "Colombia", "Venezuela"
        ]))

        # --- Maps (GIS Data) ---
        path_shp_file = self.project_root / "topology/map/ne_110m_admin_0_countries.shp"
        path_raster_file = self.project_root / "topology/map/SEDAC_map2.tiff"

        self.path_shp = self._add(path_shp_file.as_posix())
        self.path_raster = self._add(path_raster_file.as_posix())

        self.raster_encoding = self._add("indexed")
        self.sedac_mode = self._add("log")
        self.sedac_min = self._add("1.0")
        self.sedac_max = self._add("1e4")
        self.pixel_area_method = self._add("spherical")

        # Topology Specifics
        self.macro_intersite = self._add("600")
        self.macro_wrap = self._add(False, bool)
        self.macro_clusters = self._add("1")

        self.hotspot_intersite = self._add("600")
        self.hotspot_wrap = self._add(False, bool)
        self.hotspot_clusters = self._add("1")
        self.hotspot_num_per_cell = self._add("3")
        self.hotspot_max_dist_ue = self._add("400.0")
        self.hotspot_min_dist_bs = self._add("40.0")

        self.sbs_intersite = self._add("600")
        self.sbs_cell_radius = self._add("400")
        self.sbs_clusters = self._add("1")
        self.sbs_azimuth = self._add("120")

        # INDOOR topology
        self.indoor_intersite = self._add("20")
        self.indoor_n_rows = self._add("3")
        self.indoor_n_cols = self._add("3")
        self.indoor_street_width = self._add("30")
        self.indoor_num_cells = self._add("6")
        self.indoor_num_floors = self._add("3")
        self.indoor_num_buildings = self._add("ALL")
        self.indoor_ue_indoor_percent = self._add("0.95")
        self.indoor_building_class = self._add("TRADITIONAL")

        # NTN topology
        self.ntn_intersite = self._add("100000")
        self.ntn_cell_radius = self._add("50000")
        self.ntn_bs_height = self._add("600000")
        self.ntn_bs_azimuth = self._add("45")
        self.ntn_bs_elevation = self._add("45")
        self.ntn_num_sectors = self._add("7")

        # --- Base Station (BS) ---
        self.bs_load_prob = self._add("0.2")
        self.bs_power = self._add("22")
        self.bs_height = self._add("18")
        self.bs_nf = self._add("6")
        self.bs_ohmic = self._add("0")
        self.bs_norm = self._add(False, bool)
        self.bs_elem_pat = self._add("M2101")
        self.bs_min_arr_gain = self._add("-200")
        self.bs_h_steer = (self._add("-60"), self._add("60"))
        self.bs_v_steer = (self._add("90"), self._add("100"))
        self.bs_downtilt = self._add("6")
        self.bs_elem_max_g = self._add("6.4")
        self.bs_phi3 = self._add("90")
        self.bs_theta3 = self._add("65")
        self.bs_rows = self._add("8")
        self.bs_cols = self._add("16")
        self.bs_elem_hs = self._add("0.5")
        self.bs_elem_vs = self._add("2.1")
        self.bs_elem_am = self._add("30")
        self.bs_elem_sla_v = self._add("30")
        self.bs_mult = self._add("12")
        self.bs_sub_enabled = self._add(True, bool)
        self.bs_sub_rows = self._add("3")
        self.bs_sub_evspace = self._add("0.7")
        self.bs_sub_e_downtilt = self._add("3")

        # --- User Equipment (UE) ---
        self.ue_k = self._add("3")
        self.ue_km = self._add("1")
        self.ue_indoor = self._add("70")
        self.ue_dist_type = self._add("Macro_countries")
        self.ue_dist_distance = self._add("RAYLEIGH")
        self.ue_dist_azimuth = self._add("NORMAL")
        self.ue_az_min = self._add("-60")
        self.ue_az_max = self._add("60")
        self.ue_tx_power_ctrl = self._add(True, bool)
        self.ue_p_o_pusch = self._add("-92.2")
        self.ue_alpha = self._add("0.8")
        self.ue_p_cmax = self._add("23")
        self.ue_p_dyn = self._add("56")
        self.ue_height = self._add("1.5")
        self.ue_nf = self._add("13")
        self.ue_ohmic = self._add("0")
        self.ue_body_loss = self._add("4")
        self.ue_norm = self._add(False, bool)
        self.ue_elem_pat = self._add("FIXED")
        self.ue_min_arr_gain = self._add("-200")
        self.ue_elem_max_g = self._add("-4")
        self.ue_phi3 = self._add("180")
        self.ue_theta3 = self._add("360")
        self.ue_rows = self._add("1")
        self.ue_cols = self._add("1")
        self.ue_elem_am = self._add("25")
        self.ue_elem_sla_v = self._add("25")
        self.ue_mult = self._add("12")
        self.ue_sub_enabled = self._add(False, bool)
        self.ue_sub_rows = self._add("1")
        self.ue_sub_evspace = self._add("1.0")
        self.ue_sub_e_downtilt = self._add("0.0")

        # Link Budget / Channel
        self.ul_att = self._add("0.4")
        self.ul_sinr_min = self._add("-10")
        self.ul_sinr_max = self._add("22")
        self.dl_att = self._add("0.6")
        self.dl_sinr_min = self._add("-10")
        self.dl_sinr_max = self._add("30")
        self.ch_model = self._add("UMa")
        self.shadowing = self._add(True, bool)

        # =========================================================
        # --- SINGLE EARTH STATION (Victim) ---
        # =========================================================

        # NOTE: All floats now use _add(val, float) which returns StringVar internally

        self.se_frequency = self._add(3800.0, float)
        self.se_bandwidth = self._add(100.0, float)
        self.se_noise_temperature = self._add(290.0, float)
        self.se_adjacent_ch_reception = self._add("OFF")
        self.se_adjacent_ch_selectivity = self._add(0.0, float)
        self.se_adjacent_ch_emissions = self._add("OFF")
        self.se_adjacent_ch_leak_ratio = self._add(0.0, float)
        self.se_spectral_mask = self._add("")
        self.se_spurious_emissions = self._add(-60.0, float)
        self.se_tx_power_density = self._add(-50.0, float)
        self.se_height = self._add(10.0, float)
        self.se_polarization_loss = self._add(0.0, float)

        # Location
        self.se_loc_type = self._add("FIXED")
        self.se_loc_fixed_x = self._add(0.0, float)
        self.se_loc_fixed_y = self._add(0.0, float)
        self.se_loc_cell_min_dist_to_bs = self._add(100.0, float)
        self.se_loc_network_min_dist_to_bs = self._add(500.0, float)
        self.se_loc_ud_min_dist_to_center = self._add(0.0, float)
        self.se_loc_ud_max_dist_to_center = self._add(1000.0, float)

        # Azimuth / Elevation
        self.se_az_type = self._add("FIXED")
        self.se_az_fixed = self._add(0.0, float)
        self.se_az_ud_min = self._add(0.0, float)
        self.se_az_ud_max = self._add(360.0, float)

        self.se_el_type = self._add("FIXED")
        self.se_el_fixed = self._add(0.0, float)
        self.se_el_ud_min = self._add(0.0, float)
        self.se_el_ud_max = self._add(90.0, float)

        # Antenna
        self.se_ant_pattern = self._add("ITU-R F.699")
        self.se_ant_gain = self._add(30.0, float)
        self.se_ant_diameter = self._add(1.2, float)
        self.se_ant_envelope_gain = self._add(0.0, float)
        self.se_ant_3db = self._add(0.0, float)
        self.se_ant_l_s = self._add(0.0, float)
        self.se_ant_f1245_gain = self._add(0.0, float)
        self.se_ant_f1245_diameter = self._add(0.0, float)
        self.se_ant_f1245_frequency = self._add(0.0, float)

        # Channel Model
        self.se_channel_model = self._add("FSPL")

        # P452 Parameters
        self.p452_atmospheric_pressure = self._add(1013.25, float)
        self.p452_air_temperature = self._add(293.15, float)
        self.p452_percentage_p = self._add(20.0, float)
        self.p452_N0 = self._add(315.0, float)
        self.p452_delta_N = self._add(45.0, float)
        self.p452_polarization = self._add(0.0, float)
        self.p452_Dct = self._add(500.0, float)
        self.p452_Dcr = self._add(500.0, float)
        self.p452_Hte = self._add(30.0, float)
        self.p452_Hre = self._add(10.0, float)
        self.p452_clutter_loss = self._add(False, bool)
        self.p452_clutter_type = self._add("one_end")
        self.p452_tx_lat = self._add(45.0, float)
        self.p452_rx_lat = self._add(45.0, float)
        self.p452_is_terrain = self._add(False, bool)

        # =========================================================

        # --- Victim (Legacy / Space Station) ---
        self.v_freq = self._add("8150")
        self.v_bw = self._add("40")
        self.v_txpsd = self._add("-200")
        self.v_pol_loss = self._add("0")
        self.v_tnoise = self._add("500")
        self.v_ch_model = self._add("P619")
        self.v_season = self._add("SUMMER")
        self.v_p619_clutter = self._add("Mid")
        self.v_p619_below_rooftop = self._add("65")
        self.ss_is_global_cs = self._add(True, bool)
        self.v_alt = self._add("35786000")
        self.v_fix_lat = self._add("0")
        self.v_fix_lon = self._add("-110")
        self.v_es_alt = self._add("200")
        self.v_es_lat = self._add("-10.871349")
        self.v_es_lon = self._add("-51.6424333")
        self.v_az_type = self._add("POINTING_AT_IMT")
        self.v_el_type = self._add("POINTING_AT_IMT")
        self.v_ant_pattern = self._add("ITU-R S.672")
        self.v_ant_gain = self._add("30")
        self.v_s672_3db = self._add("5")
        self.v_s672_ls = self._add("-20")

        # --- Visual / Export / Runner ---
        self.var_show_gainmap = self._add(False, bool)
        self.var_gain_vmin = self._add("auto")
        self.var_gain_vmax = self._add("auto")
        self.show_borders = self._add(True, bool)
        self.var_rows = self._add(1, int)
        self.var_cols = self._add(1, int)
        self.var_auto_update = self._add(True, bool)
        self.var_update_period_ms = self._add(2000, int)
        self.var_xlog = self._add(False, bool)
        self.var_export_dpi = self._add(200, int)
        self.var_export_fmt = self._add("PNG")

        self.var_run_mode = self._add("LOCAL")
        self.var_max_workers = self._add(2, int)

        # Execution Folder
        self.run_folder = self._add(abs_out_dir.as_posix())

        # --- SSH / Tunnel ---
        self.ssh_host = self._add(DEFAULTS.get("ssh_host", ""))
        self.ssh_user = self._add(DEFAULTS.get("ssh_user", ""))
        self.ssh_port = self._add(DEFAULTS.get("ssh_port", 22), int)

        self.ssh_remote_dir = self._add(DEFAULTS.get(
            "remote_base_dir", "~/SHARC/campaigns"))

        self.ssh_use_tunnel = self._add(False, bool)
        self.ssh_use_password = self._add(True, bool)
        self.ssh_key_path = self._add("")
        self.ssh_status = self._add("Disconnected")
        self.var_git_branch = self._add("")

        self.tunnel_bastion_host = self._add(
            DEFAULTS.get("tunnel_bastion_host", ""))
        self.tunnel_bastion_user = self._add(
            DEFAULTS.get("tunnel_bastion_user", ""))
        self.tunnel_bastion_port = self._add(
            DEFAULTS.get("tunnel_bastion_port", 22), int)
        self.tunnel_internal_ip = self._add(
            DEFAULTS.get("tunnel_internal_ip", ""))
        self.tunnel_internal_port = self._add(
            DEFAULTS.get("tunnel_internal_port", 80), int)
        self.tunnel_local_port = self._add(
            DEFAULTS.get("tunnel_local_port", 8080), int)
        self.tunnel_key_path = self._add(DEFAULTS.get("tunnel_key_path", ""))
        self.tunnel_status = self._add("🔴 Inactive Tunnel")
