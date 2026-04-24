def _num_or_str(s):
    """Conversor robusto de strings para float/int."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return s
    s_str = str(s).strip()
    if not s_str:
        return None

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
    topo_type = str(g_imt("topo_type"))
    topology = {
        "central_latitude": n(g_imt("topo_c_lat")),
        "central_longitude": n(g_imt("topo_c_lon")),
        "central_altitude": n(g_imt("topo_c_alt")),
        "type": topo_type,
    }

    if topo_type == "Macro_countries":
        try:
            raw_txt = app_state.tab_imt.topo_section.get_countries_text()
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

        topology["single_bs"] = {
            "intersite_distance": n(g_imt("sbs_intersite")),
            "cell_radius": n(g_imt("sbs_cell_radius")),
            "num_clusters": int(n(g_imt("sbs_clusters")) or 1),
            "azimuth": sbs_az,
        }

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

    imt = {
        "minimum_separation_distance_bs_ue": n(g_imt("imt_min_sep")),
        "interfered_with": bool(g_imt("imt_interfered")),
        "frequency": n(g_imt("imt_freq")),
        "bandwidth": n(g_imt("imt_bw")),
        "rb_bandwidth": n(g_imt("imt_rb_bw")),
        "spectral_mask": g_imt("imt_spec_mask"),
        "spurious_emissions": n(g_imt("imt_spurious")),
        "adjacent_antenna_model": g_imt("imt_adj_ant_model"),
        "guard_band_ratio": n(g_imt("imt_guard_ratio")),
        "topology": topology,
        "bs": {
            "load_probability": n(g_imt("bs_load_prob")),
            "conducted_power": n(g_imt("bs_power")),
            "height": n(g_imt("bs_height")),
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
        "channel_model": g_imt("ch_model"),
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

    return result
