import copy
import yaml


def _num_or_str(s):
    """Conversor robusto de strings para float/int."""
    if s is None:
        return None
    if isinstance(s, (int, float, bool)):
        return s
    s_str = str(s).strip()
    if not s_str:
        return None

    low = s_str.lower()
    if low == "true":
        return True
    if low == "false":
        return False

    if '.' not in s_str and 'e' not in s_str.lower():
        try:
            return int(s_str)
        except:
            pass

    try:
        return float(s_str)
    except:
        return s_str


def _get_var(app_state, tab_name, var_name):
    """
    Função universal para buscar variáveis da interface.
    1. Tenta buscar no state manager da aba específica (ex: tab_imt.state).
    2. Se falhar, busca na raiz do AppState (app_state.var_name).
    """
    try:
        tab = getattr(app_state, f"tab_{tab_name}")
        tk_var = tab.state.get(var_name)
        return tk_var.get()
    except:
        pass

    try:
        tk_var = getattr(app_state, var_name)
        if hasattr(tk_var, "get"):
            return tk_var.get()
        return tk_var
    except:
        return None


def _normalize_raster_encoding(value):
    raw = str(value or "").strip()
    legacy = {"Uniforme": "uniform", "Denspop": "indexed", "": "uniform"}
    enc = legacy.get(raw, raw.lower())
    return enc if enc in {"uniform", "density", "indexed"} else "uniform"


def _normalize_topology_type(value):
    raw = str(value or "").strip()
    if not raw:
        return "HOTSPOT"

    official = {"HOTSPOT", "MACROCELL", "SINGLE_BS", "Macro_countries", "INDOOR", "NTN", "MSS_DC"}
    if raw in official:
        return raw

    low = raw.lower()
    if low in {"macro_countries", "macro countries", "macro-countries"}:
        return "Macro_countries"
    if low == "macrocell":
        return "MACROCELL"
    if low == "single_bs":
        return "SINGLE_BS"
    if low == "indoor":
        return "INDOOR"
    if low == "ntn":
        return "NTN"
    if low in {"mss_dc", "mss dc", "mss-dc"}:
        return "MSS_DC"
    return raw


def _normalize_imt_spectral_mask(value):
    raw = str(value or "").strip()
    if not raw:
        return "IMT-2020"

    low = raw.lower()
    mapping = {
        "imt-2020": "IMT-2020",
        "3gpp": "3GPP E-UTRA",
        "3gpp e-utra": "3GPP E-UTRA",
        "mss": "MSS",
    }
    return mapping.get(low, raw)


def _normalize_adjacent_antenna_model(value):
    raw = str(value or "").strip()
    if not raw:
        return "SINGLE_ELEMENT"

    low = raw.lower()
    mapping = {
        "single_element": "SINGLE_ELEMENT",
        "single element": "SINGLE_ELEMENT",
        "beamforming": "BEAMFORMING",
        "itu-r f.1336": "SINGLE_ELEMENT",
        "f1336": "SINGLE_ELEMENT",
    }
    return mapping.get(low, raw)


def _normalize_imt_channel_model(value):
    raw = str(value or "").strip()
    if not raw:
        return "UMa"

    low = raw.lower()
    mapping = {
        "fspl": "FSPL",
        "ci": "CI",
        "uma": "UMa",
        "umi": "UMi",
        "tvro-urban": "TVRO-URBAN",
        "tvro-suburban": "TVRO-SUBURBAN",
        "abg": "ABG",
        "p619": "P619",
    }
    return mapping.get(low, raw)


def _normalize_num_imt_buildings(value):
    parsed = _num_or_str(value)
    if parsed is None:
        return "ALL"
    if isinstance(parsed, str):
        return "ALL" if parsed.strip().upper() == "ALL" else parsed.strip()
    return int(parsed)


def _deep_merge(base_dict, new_dict):
    for key, value in new_dict.items():
        if isinstance(value, dict) and isinstance(base_dict.get(key), dict):
            _deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


def _parse_mapping_text(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return {}
    try:
        data = yaml.safe_load(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _default_mss_dc_config(country_names):
    names = country_names or ["Brazil"]
    return {
        "name": "SystemA",
        "num_beams": 19,
        "beam_radius": 36516.0,
        "sat_is_active_if": {
            "conditions": [
                "LAT_LONG_INSIDE_COUNTRY",
                "MINIMUM_ELEVATION_FROM_ES",
            ],
            "minimum_elevation_from_es": 5.0,
            "lat_long_inside_country": {
                "country_names": list(names),
                "margin_from_border": 0.0,
            },
        },
        "beam_positioning": {
            "type": "SERVICE_GRID",
            "service_grid": {
                "country_names": list(names),
                "transform_grid_randomly": True,
                "grid_margin_from_border": 0.0,
                "eligible_sats_margin_from_border": 0.0,
            },
        },
        "orbits": [
            {
                "n_planes": 28,
                "inclination_deg": 53.0,
                "perigee_alt_km": 525.0,
                "apogee_alt_km": 525.0,
                "sats_per_plane": 120,
                "long_asc_deg": 0.0,
                "phasing_deg": 1.5,
                "initial_mean_anomaly": 0.0,
            }
        ],
    }


def _get_countries_text(app_state):
    try:
        return app_state.tab_imt.topo_section.get_countries_text()
    except Exception:
        return ""


def _get_mss_dc_text(app_state):
    try:
        return app_state.tab_imt.topo_section.get_mss_dc_text()
    except Exception:
        return ""


def _get_mss_dc_data(app_state):
    try:
        data = app_state.tab_imt.topo_section.get_mss_dc_data()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_yaml_structure(app_state):
    """
    Constrói o dicionário completo do YAML extraindo os dados em tempo real.
    Gera blocos dinâmicos dependendo do tipo de sistema escolhido.
    """
    n = _num_or_str

    # Helpers curtos para acessar variáveis de cada aba
    def g_gen(key): return _get_var(app_state, "general", key)
    def g_imt(key): return _get_var(app_state, "imt", key)
    def g_vic(key): return _get_var(app_state, "victim", key)
    def g_sta(key): return _get_var(app_state, "station", key)

    # --- 1. General ---
    system_type = str(g_gen("var_system") or "").strip()

    general = {
        "seed": int(n(g_gen("var_seed")) or 0),
        "num_snapshots": int(n(g_gen("var_snaps")) or 0),
        "overwrite_output": bool(g_gen("var_overwrite")),
        "output_dir": str(g_gen("var_outdir") or ""),
        "output_dir_prefix": str(g_gen("var_prefix") or ""),
        "system": system_type,
        "imt_link": str(g_gen("var_imt_link") or ""),
        "enable_adjacent_channel": bool(g_gen("var_adj")),
        "enable_cochannel": bool(g_gen("var_coch")),
    }

    # --- 2. Topology (IMT) ---
    topo_type = _normalize_topology_type(g_imt("topo_type"))
    topology = {
        "central_latitude": n(g_imt("topo_c_lat")),
        "central_longitude": n(g_imt("topo_c_lon")),
        "central_altitude": n(g_imt("topo_c_alt")),
        "type": topo_type,
    }

    if topo_type == "Macro_countries":
        try:
            raw_txt = _get_countries_text(app_state)
        except:
            raw_txt = str(g_imt("topo_countries") or "")

        country_names = [c.strip() for c in raw_txt.splitlines() if c.strip()]
        enc_ui = _normalize_raster_encoding(g_imt("topo_raster_enc"))
        pop_raster = (
            str(g_imt("path_raster")).strip() or None
        ) if enc_ui != "uniform" else None

        topology["macrocell_countries"] = {
            "country_names": country_names,
            "num_bs_total": int(n(g_imt("topo_num_bs")) or 0),
            "cell_radius": n(g_imt("topo_cell_radius")),
            "rng_seed": int(n(g_imt("topo_rng")) or 0),
            "dist_type": str(g_imt("topo_dist_type")),
            "countries_shapefile": str(g_imt("path_shp")).strip() or None,
            "population_raster": pop_raster,
        }
        if enc_ui != "uniform":
            topology["macrocell_countries"].update({
                "raster_encoding": enc_ui,
                "min_density_threshold": n(g_imt("topo_min_density_threshold")),
                "density_exponent": n(g_imt("topo_density_exponent")),
            })
            if enc_ui == "indexed":
                topology["macrocell_countries"].update({
                    "sedac_palette_mode": g_imt("topo_sedac_palette_mode"),
                    "sedac_min": n(g_imt("topo_sedac_min")),
                    "sedac_max": n(g_imt("topo_sedac_max")),
                })

    elif topo_type == "MACROCELL":
        topology["macrocell"] = {
            "intersite_distance": n(g_imt("macro_intersite")),
            "wrap_around": bool(g_imt("macro_wrap")),
            "num_clusters": int(n(g_imt("macro_clusters")) or 1),
        }

    elif topo_type == "HOTSPOT":
        topology["hotspot"] = {
            "intersite_distance": n(g_imt("hotspot_intersite")),
            "wrap_around": bool(g_imt("hotspot_wrap")),
            "num_clusters": int(n(g_imt("hotspot_clusters")) or 1),
            "num_hotspots_per_cell": int(n(g_imt("hotspot_num_per_cell")) or 1),
            "max_dist_hotspot_ue": n(g_imt("hotspot_max_dist_ue")),
            "min_dist_bs_hotspot": n(g_imt("hotspot_min_dist_bs")),
        }

    elif topo_type == "SINGLE_BS":
        az_text = str(g_imt("sbs_azimuth")).strip()
        try:
            sbs_az = [float(x.strip())
                      for x in az_text.split(",")] if az_text else None
        except:
            sbs_az = az_text

        single_bs = {
            "num_clusters": int(n(g_imt("sbs_clusters")) or 1),
            "azimuth": sbs_az,
        }
        sbs_cell_radius = n(g_imt("sbs_cell_radius"))
        sbs_intersite = n(g_imt("sbs_intersite"))
        if sbs_cell_radius is not None:
            single_bs["cell_radius"] = sbs_cell_radius
        elif sbs_intersite is not None:
            single_bs["intersite_distance"] = sbs_intersite
        topology["single_bs"] = single_bs

    elif topo_type == "INDOOR":
        topology["indoor"] = {
            "basic_path_loss": str(g_imt("indoor_basic_path_loss") or "INH_OFFICE"),
            "intersite_distance": n(g_imt("indoor_intersite")),
            "n_rows": int(n(g_imt("indoor_n_rows")) or 3),
            "n_colums": int(n(g_imt("indoor_n_cols")) or 2),
            "street_width": n(g_imt("indoor_street_width")),
            "num_cells": int(n(g_imt("indoor_num_cells")) or 3),
            "num_floors": int(n(g_imt("indoor_num_floors")) or 1),
            "num_imt_buildings": _normalize_num_imt_buildings(g_imt("indoor_num_buildings")),
            "building_class": str(g_imt("indoor_building_class") or "TRADITIONAL"),
            "ue_indoor_percent": n(g_imt("indoor_ue_indoor_percent")),
        }

    elif topo_type == "NTN":
        ntn = {
            "bs_height": n(g_imt("ntn_bs_height")),
            "bs_azimuth": n(g_imt("ntn_bs_azimuth")),
            "bs_elevation": n(g_imt("ntn_bs_elevation")),
            "num_sectors": int(n(g_imt("ntn_num_sectors")) or 7),
            "bs_backoff_power": int(n(g_imt("ntn_bs_backoff_power")) or 3),
            "bs_n_rows_layer1": int(n(g_imt("ntn_bs_n_rows_layer1")) or 2),
            "bs_n_columns_layer1": int(n(g_imt("ntn_bs_n_columns_layer1")) or 2),
            "bs_n_rows_layer2": int(n(g_imt("ntn_bs_n_rows_layer2")) or 4),
            "bs_n_columns_layer2": int(n(g_imt("ntn_bs_n_columns_layer2")) or 2),
        }
        ntn_cell_radius = n(g_imt("ntn_cell_radius"))
        ntn_intersite = n(g_imt("ntn_intersite"))
        if ntn_cell_radius is not None:
            ntn["cell_radius"] = ntn_cell_radius
        elif ntn_intersite is not None:
            ntn["intersite_distance"] = ntn_intersite
        topology["ntn"] = ntn

    elif topo_type == "MSS_DC":
        raw_txt = _get_countries_text(app_state) or str(g_imt("topo_countries") or "")
        countries = [c.strip() for c in raw_txt.splitlines() if c.strip()]
        mss_dc = copy.deepcopy(_default_mss_dc_config(countries))
        parsed = _get_mss_dc_data(app_state)
        if not parsed:
            parsed = _parse_mapping_text(_get_mss_dc_text(app_state) or g_imt("mss_dc_config"))
        if parsed:
            _deep_merge(mss_dc, parsed)

        sat_active = mss_dc.setdefault("sat_is_active_if", {})
        lat_long = sat_active.setdefault("lat_long_inside_country", {})
        if countries and not lat_long.get("country_names"):
            lat_long["country_names"] = list(countries)

        beam_positioning = mss_dc.setdefault("beam_positioning", {})
        service_grid = beam_positioning.setdefault("service_grid", {})
        if countries and not service_grid.get("country_names"):
            service_grid["country_names"] = list(countries)

        topology["mss_dc"] = mss_dc

    # --- 3. IMT Structure ---
    ue_array = {
        "normalization": bool(g_imt("ue_norm")),
        "element_pattern": g_imt("ue_elem_pat"),
        "minimum_array_gain": n(g_imt("ue_min_arr_gain")),
        "element_max_g": n(g_imt("ue_elem_max_g")),
        "element_phi_3db": n(g_imt("ue_phi3")),
        "element_theta_3db": n(g_imt("ue_theta3")),
        "n_rows": n(g_imt("ue_rows")),
        "n_columns": n(g_imt("ue_cols")),
        "element_am": n(g_imt("ue_elem_am")),
        "element_sla_v": n(g_imt("ue_elem_sla_v")),
        "multiplication_factor": n(g_imt("ue_mult")),
    }
    if g_imt("ue_sub_enabled"):
        ue_array["subarray"] = {
            "is_enabled": True,
            "n_rows": n(g_imt("ue_sub_rows")),
            "element_vert_spacing": n(g_imt("ue_sub_evspace")),
            "eletrical_downtilt": n(g_imt("ue_sub_e_downtilt")),
        }

    ue_block = {
        "k": int(n(g_imt("ue_k")) or 0),
        "k_m": int(n(g_imt("ue_km")) or 0),
        "indoor_percent": n(g_imt("ue_indoor")),
        "distribution_type": g_imt("ue_dist_type"),
        "tx_power_control": bool(g_imt("ue_tx_power_ctrl")),
        "p_o_pusch": n(g_imt("ue_p_o_pusch")),
        "alpha": n(g_imt("ue_alpha")),
        "p_cmax": n(g_imt("ue_p_cmax")),
        "power_dynamic_range": n(g_imt("ue_p_dyn")),
        "height": n(g_imt("ue_height")),
        "noise_figure": n(g_imt("ue_nf")),
        "ohmic_loss": n(g_imt("ue_ohmic")),
        "body_loss": n(g_imt("ue_body_loss")),
        "antenna": {"array": ue_array},
    }
    if str(g_imt("ue_dist_type")).upper() == "ANGLE_AND_DISTANCE":
        ue_block["distribution_distance"] = g_imt("ue_dist_distance")
        ue_block["distribution_azimuth"] = g_imt("ue_dist_azimuth")
        az_min = n(g_imt("ue_az_min"))
        az_max = n(g_imt("ue_az_max"))
        ue_block["azimuth_range"] = f"{az_min},{az_max}"

    bs_array = {
        "normalization": bool(g_imt("bs_norm")),
        "element_pattern": g_imt("bs_elem_pat"),
        "minimum_array_gain": n(g_imt("bs_min_arr_gain")),
        "horizontal_beamsteering_range": [n(g_imt("bs_h_steer_min")), n(g_imt("bs_h_steer_max"))],
        "vertical_beamsteering_range": [n(g_imt("bs_v_steer_min")), n(g_imt("bs_v_steer_max"))],
        "downtilt": n(g_imt("bs_downtilt")),
        "element_max_g": n(g_imt("bs_elem_max_g")),
        "element_phi_3db": n(g_imt("bs_phi3")),
        "element_theta_3db": n(g_imt("bs_theta3")),
        "n_rows": n(g_imt("bs_rows")),
        "n_columns": n(g_imt("bs_cols")),
        "element_horiz_spacing": n(g_imt("bs_elem_hs")),
        "element_vert_spacing": n(g_imt("bs_elem_vs")),
        "element_am": n(g_imt("bs_elem_am")),
        "element_sla_v": n(g_imt("bs_elem_sla_v")),
        "multiplication_factor": n(g_imt("bs_mult")),
        "subarray": {
            "is_enabled": bool(g_imt("bs_sub_enabled")),
            "n_rows": n(g_imt("bs_sub_rows")),
            "element_vert_spacing": n(g_imt("bs_sub_evspace")),
            "eletrical_downtilt": n(g_imt("bs_sub_e_downtilt")),
        }
    }

    bs_height = n(g_imt("bs_height"))
    if topo_type == "NTN":
        ntn_height = n(g_imt("ntn_bs_height"))
        if ntn_height is not None:
            bs_height = ntn_height

    imt = {
        "minimum_separation_distance_bs_ue": n(g_imt("imt_min_sep")),
        "interfered_with": bool(g_imt("imt_interfered")),
        "frequency": n(g_imt("imt_freq")),
        "bandwidth": n(g_imt("imt_bw")),
        "rb_bandwidth": n(g_imt("imt_rb_bw")),
        "spectral_mask": _normalize_imt_spectral_mask(g_imt("imt_spec_mask")),
        "spurious_emissions": n(g_imt("imt_spurious")),
        "adjacent_antenna_model": _normalize_adjacent_antenna_model(g_imt("imt_adj_ant_model")),
        "guard_band_ratio": n(g_imt("imt_guard_ratio")),
        "topology": topology,
        "bs": {
            "load_probability": n(g_imt("bs_load_prob")),
            "conducted_power": n(g_imt("bs_power")),
            "height": bs_height,
            "noise_figure": n(g_imt("bs_nf")),
            "ohmic_loss": n(g_imt("bs_ohmic")),
            "antenna": {"array": bs_array}
        },
        "ue": ue_block,
        "uplink": {
            "attenuation_factor": n(g_imt("ul_att")),
            "sinr_min": n(g_imt("ul_sinr_min")),
            "sinr_max": n(g_imt("ul_sinr_max")),
        },
        "downlink": {
            "attenuation_factor": n(g_imt("dl_att")),
            "sinr_min": n(g_imt("dl_sinr_min")),
            "sinr_max": n(g_imt("dl_sinr_max")),
        },
        "channel_model": _normalize_imt_channel_model(g_imt("ch_model")),
        "shadowing": bool(g_imt("shadowing")),
    }

    # Estrutura base do resultado (sempre contém general e imt)
    result = {
        "general": general,
        "imt": imt
    }

    # --- 4. Blocos Dinâmicos Baseados no Sistema Escolhido ---
    if system_type == "SINGLE_SPACE_STATION":
        single_space_station = {
            "frequency": n(g_vic("v_freq")),
            "bandwidth": n(g_vic("v_bw")),
            "tx_power_density": n(g_vic("v_txpsd")),
            "polarization_loss": n(g_vic("v_pol_loss")),
            "noise_temperature": n(g_vic("v_tnoise")),
            "channel_model": g_vic("v_ch_model"),
            "is_global_coordinate_system": bool(g_vic("ss_is_global_cs")),
            "season": g_vic("v_season"),
            "param_p619": {
                "mean_clutter_height": g_vic("v_p619_clutter"),
                "below_rooftop": n(g_vic("v_p619_below_rooftop")),
            },
            "geometry": {
                "altitude": n(g_vic("v_alt")),
                "location": {
                    "type": "FIXED",
                    "fixed": {"lat_deg": n(g_vic("v_fix_lat")), "long_deg": n(g_vic("v_fix_lon"))}
                },
                "es_altitude": n(g_vic("v_es_alt")),
                "es_lat_deg": n(g_vic("v_es_lat")),
                "es_long_deg": n(g_vic("v_es_lon")),
                "azimuth": {"type": g_vic("v_az_type")},
                "elevation": {"type": g_vic("v_el_type")},
            },
            "antenna": {
                "pattern": g_vic("v_ant_pattern"),
                "gain": n(g_vic("v_ant_gain")),
            }
        }

        if g_vic("v_ant_pattern") == "ITU-R S.672":
            single_space_station["antenna"]["itu_r_s_672"] = {
                "antenna_3_dB": n(g_vic("v_s672_3db")),
                "antenna_l_s": n(g_vic("v_s672_ls")),
            }

        result["single_space_station"] = single_space_station

    elif system_type == "SINGLE_EARTH_STATION":
        single_earth_station = {
            "frequency": n(g_sta("se_frequency")),
            "bandwidth": n(g_sta("se_bandwidth")),
            "noise_temperature": n(g_sta("se_noise_temperature")),
            "adjacent_ch_reception": g_sta("se_adjacent_ch_reception"),
            "adjacent_ch_selectivity": n(g_sta("se_adjacent_ch_selectivity")),
            "adjacent_ch_emissions": g_sta("se_adjacent_ch_emissions"),
            "adjacent_ch_leak_ratio": n(g_sta("se_adjacent_ch_leak_ratio")),
            "spectral_mask": g_sta("se_spectral_mask"),
            "spurious_emissions": n(g_sta("se_spurious_emissions")),
            "tx_power_density": n(g_sta("se_tx_power_density")),
            "height": n(g_sta("se_height")),
            "geometry": {
                "location": {
                    "type": g_sta("se_loc_type"),
                    "fixed": {"x": n(g_sta("se_loc_fixed_x")), "y": n(g_sta("se_loc_fixed_y"))},
                    "cell": {"min_dist_to_bs": n(g_sta("se_loc_cell_min_dist_to_bs"))},
                    "network": {"min_dist_to_bs": n(g_sta("se_loc_network_min_dist_to_bs"))},
                    "uniform_dist": {
                        "min_dist_to_center": n(g_sta("se_loc_ud_min_dist_to_center")),
                        "max_dist_to_center": n(g_sta("se_loc_ud_max_dist_to_center"))
                    },
                },
                "azimuth": {
                    "type": g_sta("se_az_type"),
                    "fixed": n(g_sta("se_az_fixed")),
                    "uniform_dist": {"min": n(g_sta("se_az_ud_min")), "max": n(g_sta("se_az_ud_max"))},
                },
                "elevation": {
                    "type": g_sta("se_el_type"),
                    "fixed": n(g_sta("se_el_fixed")),
                    "uniform_dist": {"min": n(g_sta("se_el_ud_min")), "max": n(g_sta("se_el_ud_max"))},
                },
            },
            "antenna": {
                "pattern": g_sta("se_ant_pattern"),
                "gain": n(g_sta("se_ant_gain")),
                "diameter": n(g_sta("se_ant_diameter")),
                "envelope_gain": n(g_sta("se_ant_envelope_gain")),
            },
            "channel_model": g_sta("se_channel_model"),
            "p452": {
                "atmospheric_pressure": n(g_sta("p452_atmospheric_pressure")),
                "air_temperature": n(g_sta("p452_air_temperature")),
                "N0": n(g_sta("p452_N0")),
                "delta_N": n(g_sta("p452_delta_N")),
                "percentage_p": n(g_sta("p452_percentage_p")),
                "Dct": n(g_sta("p452_Dct")),
                "Dcr": n(g_sta("p452_Dcr")),
                "Hte": n(g_sta("p452_Hte")),
                "tx_lat": n(g_sta("p452_tx_lat")),
                "rx_lat": n(g_sta("p452_rx_lat")),
                "polarization": n(g_sta("p452_polarization")),
                "clutter_loss": bool(g_sta("p452_clutter_loss")),
                "clutter_type": g_sta("p452_clutter_type"),
                "is_terrain": bool(g_sta("p452_is_terrain")),
            },
        }

        # Blocos opcionais para padrões específicos da Single Earth Station
        ant_pattern = g_sta("se_ant_pattern")
        if ant_pattern == "ITU-R S.672":
            single_earth_station["antenna"]["itu_r_s_672"] = {
                "antenna_3_dB": n(g_sta("se_ant_3db")),
                "antenna_l_s": n(g_sta("se_ant_l_s")),
            }
        elif ant_pattern == "ITU-R F.1245_fs":
            single_earth_station["antenna"]["itu_r_f_1245_fs"] = {
                "gain": n(g_sta("se_ant_f1245_gain")),
                "diameter": n(g_sta("se_ant_f1245_diameter")),
                "frequency": n(g_sta("se_ant_f1245_frequency"))
            }

        result["single_earth_station"] = single_earth_station

    elif system_type == "HAPS":
        result["haps"] = {
            "frequency": 27250.0,
            "bandwidth": 200.0,
            "antenna_gain": 28.1,
            "eirp_density": 4.4,
            "tx_power_density": -83.7,
            "altitude": 20000.0,
            "lat_deg": 0.0,
            "elevation": 270.0,
            "azimuth": 0.0,
            "antenna_pattern": "ITU-R F.1891",
            "earth_station_alt_m": 0.0,
            "earth_station_lat_deg": 0.0,
            "earth_station_long_diff_deg": 0.0,
            "season": "SUMMER",
            "acs": 30.0,
            "channel_model": "P619",
            "antenna_l_n": -25.0
        }

    elif system_type == "MSS_SS":
        import math
        result["mss_ss"] = {
            "is_space_to_earth": True,
            "frequency": 2110.0,
            "bandwidth": 20.0,
            "spectral_mask": "3GPP E-UTRA",
            "spurious_emissions": -13.0,
            "adjacent_ch_leak_ratio": 45.0,
            "altitude": 1200000.0,
            "cell_radius": 45000.0,
            "intersite_distance": 45000.0 * math.sqrt(3),
            "tx_power_density": 40.0,
            "antenna_gain": 30.0,
            "azimuth": 45.0,
            "elevation": 90.0,
            "num_sectors": 7,
            "antenna_pattern": "ITU-R-S.1528-LEO",
            "season": "SUMMER",
            "channel_model": "P619"
        }

    elif system_type == "MSS_D2D":
        import math
        result["mss_d2d"] = {
            "is_space_to_earth": True,
            "name": "Default",
            "frequency": 2110.0,
            "bandwidth": 5.0,
            "beams_load_factor": 1.0,
            "adjacent_ch_emissions": "OFF",
            "spectral_mask": "MSS",
            "spurious_emissions": -13.0,
            "adjacent_ch_leak_ratio": 45.0,
            "cell_radius": 19000.0,
            "intersite_distance": 19000.0 * math.sqrt(3),
            "tx_power_density": 40.0,
            "num_sectors": 19,
            "antenna_pattern": "ITU-R-S.1528-Taylor",
            "channel_model": "P619"
        }

    return result
