def _num_or_str(s):
    """Conversor robusto de strings para float/int."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return s
    s_str = str(s).strip()
    if not s_str:
        return None

    # Tenta int primeiro (se não tiver ponto ou e)
    if '.' not in s_str and 'e' not in s_str.lower():
        try:
            return int(s_str)
        except:
            pass

    try:
        return float(s_str)
    except:
        return s_str


def build_yaml_structure(app_state):
    """
    Constrói o dicionário completo do YAML usando o objeto app_state.
    O 'app_state' pode ser a instância do App principal, já que ele
    contém todas as variáveis atreladas a si.
    """

    # Alias curto para converter números
    n = _num_or_str

    # --- 1. General ---
    general = {
        "seed": int(n(app_state.var_seed.get())),
        "num_snapshots": int(n(app_state.var_snaps.get())),
        "overwrite_output": bool(app_state.var_overwrite.get()),
        "output_dir": str(app_state.var_outdir.get()),
        "output_dir_prefix": str(app_state.var_prefix.get()),
        "system": str(app_state.var_system.get()),
        "imt_link": str(app_state.var_imt_link.get()),
        "enable_adjacent_channel": bool(app_state.var_adj.get()),
        "enable_cochannel": bool(app_state.var_coch.get()),
    }

    # --- 2. Topology ---
    topo_type = str(app_state.topo_type.get())
    topology = {
        "central_latitude": n(app_state.topo_c_lat.get()),
        "central_longitude": n(app_state.topo_c_lon.get()),
        "central_altitude": n(app_state.topo_c_alt.get()),
        "type": topo_type,
    }

    if topo_type == "Macro_countries":
        # Nota: Acesso ao widget Text depende de como foi passado.
        # Assumindo que o builder roda no contexto onde a UI já populou algo ou
        # a variável topo_countries já tem o texto bruto.
        # Se 'topo_countries' for um StringVar atualizado, usamos ele:
        raw_txt = app_state.topo_countries.get()
        country_names = [c.strip() for c in raw_txt.splitlines() if c.strip()]

        enc_ui = (app_state.topo_raster_enc.get() or "").strip()
        pop_raster = app_state.path_raster.get().strip() if enc_ui != "Uniforme" else None

        topology["macrocell_countries"] = {
            "country_names": country_names,
            "num_bs_total": int(n(app_state.topo_num_bs.get()) or 0),
            "cell_radius": n(app_state.topo_cell_radius.get()),
            "rng_seed": int(n(app_state.topo_rng.get()) or 0),
            "dist_type": app_state.topo_dist_type.get(),
            "countries_shapefile": app_state.path_shp.get().strip() or None,
            "population_raster": pop_raster,
        }
        if enc_ui != "Uniforme":
            topology["macrocell_countries"]["raster_encoding"] = "indexed"

    elif topo_type == "MACROCELL":
        topology["macrocell"] = {
            "intersite_distance": n(app_state.macro_intersite.get()),
            "wrap_around": bool(app_state.macro_wrap.get()),
            "num_clusters": int(n(app_state.macro_clusters.get()) or 1),
        }

    elif topo_type == "HOTSPOT":
        topology["hotspot"] = {
            "intersite_distance": n(app_state.hotspot_intersite.get()),
            "wrap_around": bool(app_state.hotspot_wrap.get()),
            "num_clusters": int(n(app_state.hotspot_clusters.get()) or 1),
            "num_hotspots_per_cell": int(n(app_state.hotspot_num_per_cell.get()) or 1),
            "max_dist_hotspot_ue": n(app_state.hotspot_max_dist_ue.get()),
            "min_dist_bs_hotspot": n(app_state.hotspot_min_dist_bs.get()),
        }

    elif topo_type == "SINGLE_BS":
        az_text = (app_state.sbs_azimuth.get() or "").strip()
        try:
            sbs_az = [float(x.strip())
                      for x in az_text.split(",")] if az_text else None
        except:
            sbs_az = az_text

        topology["single_bs"] = {
            "intersite_distance": n(app_state.sbs_intersite.get()),
            "cell_radius": n(app_state.sbs_cell_radius.get()),
            "num_clusters": int(n(app_state.sbs_clusters.get()) or 1),
            "azimuth": sbs_az,
        }

    # --- 3. IMT Structure ---
    ue_array = {
        "normalization": bool(app_state.ue_norm.get()),
        "element_pattern": app_state.ue_elem_pat.get(),
        "minimum_array_gain": n(app_state.ue_min_arr_gain.get()),
        "element_max_g": n(app_state.ue_elem_max_g.get()),
        "element_phi_3db": n(app_state.ue_phi3.get()),
        "element_theta_3db": n(app_state.ue_theta3.get()),
        "n_rows": n(app_state.ue_rows.get()),
        "n_columns": n(app_state.ue_cols.get()),
        "element_am": n(app_state.ue_elem_am.get()),
        "element_sla_v": n(app_state.ue_elem_sla_v.get()),
        "multiplication_factor": n(app_state.ue_mult.get()),
    }
    if app_state.ue_sub_enabled.get():
        ue_array["subarray"] = {
            "is_enabled": True,
            "n_rows": n(app_state.ue_sub_rows.get()),
            "element_vert_spacing": n(app_state.ue_sub_evspace.get()),
            "eletrical_downtilt": n(app_state.ue_sub_e_downtilt.get()),
        }

    ue_block = {
        "k": int(n(app_state.ue_k.get()) or 0),
        "k_m": int(n(app_state.ue_km.get()) or 0),
        "indoor_percent": n(app_state.ue_indoor.get()),
        "distribution_type": app_state.ue_dist_type.get(),
        "tx_power_control": bool(app_state.ue_tx_power_ctrl.get()),
        "p_o_pusch": n(app_state.ue_p_o_pusch.get()),
        "alpha": n(app_state.ue_alpha.get()),
        "p_cmax": n(app_state.ue_p_cmax.get()),
        "power_dynamic_range": n(app_state.ue_p_dyn.get()),
        "height": n(app_state.ue_height.get()),
        "noise_figure": n(app_state.ue_nf.get()),
        "ohmic_loss": n(app_state.ue_ohmic.get()),
        "body_loss": n(app_state.ue_body_loss.get()),
        "antenna": {"array": ue_array},
    }
    if app_state.ue_dist_type.get().upper() == "ANGLE_AND_DISTANCE":
        ue_block["distribution_distance"] = app_state.ue_dist_distance.get()
        ue_block["distribution_azimuth"] = app_state.ue_dist_azimuth.get()

    bs_array = {
        "normalization": bool(app_state.bs_norm.get()),
        "element_pattern": app_state.bs_elem_pat.get(),
        "minimum_array_gain": n(app_state.bs_min_arr_gain.get()),
        "horizontal_beamsteering_range": [n(app_state.bs_h_steer[0].get()), n(app_state.bs_h_steer[1].get())],
        "vertical_beamsteering_range": [n(app_state.bs_v_steer[0].get()), n(app_state.bs_v_steer[1].get())],
        "downtilt": n(app_state.bs_downtilt.get()),
        "element_max_g": n(app_state.bs_elem_max_g.get()),
        "element_phi_3db": n(app_state.bs_phi3.get()),
        "element_theta_3db": n(app_state.bs_theta3.get()),
        "n_rows": n(app_state.bs_rows.get()),
        "n_columns": n(app_state.bs_cols.get()),
        "element_horiz_spacing": n(app_state.bs_elem_hs.get()),
        "element_vert_spacing": n(app_state.bs_elem_vs.get()),
        "element_am": n(app_state.bs_elem_am.get()),
        "element_sla_v": n(app_state.bs_elem_sla_v.get()),
        "multiplication_factor": n(app_state.bs_mult.get()),
        "subarray": {
            "is_enabled": bool(app_state.bs_sub_enabled.get()),
            "n_rows": n(app_state.bs_sub_rows.get()),
            "element_vert_spacing": n(app_state.bs_sub_evspace.get()),
            "eletrical_downtilt": n(app_state.bs_sub_e_downtilt.get()),
        }
    }

    imt = {
        "minimum_separation_distance_bs_ue": n(app_state.imt_min_sep.get()),
        "interfered_with": bool(app_state.imt_interfered.get()),
        "frequency": n(app_state.imt_freq.get()),
        "bandwidth": n(app_state.imt_bw.get()),
        "rb_bandwidth": n(app_state.imt_rb_bw.get()),
        "spectral_mask": app_state.imt_spec_mask.get(),
        "spurious_emissions": n(app_state.imt_spurious.get()),
        "adjacent_antenna_model": app_state.imt_adj_ant_model.get(),
        "guard_band_ratio": n(app_state.imt_guard_ratio.get()),
        "topology": topology,
        "bs": {
            "load_probability": n(app_state.bs_load_prob.get()),
            "conducted_power": n(app_state.bs_power.get()),
            "height": n(app_state.bs_height.get()),
            "noise_figure": n(app_state.bs_nf.get()),
            "ohmic_loss": n(app_state.bs_ohmic.get()),
            "antenna": {"array": bs_array}
        },
        "ue": ue_block,
        "uplink": {
            "attenuation_factor": n(app_state.ul_att.get()),
            "sinr_min": n(app_state.ul_sinr_min.get()),
            "sinr_max": n(app_state.ul_sinr_max.get()),
        },
        "downlink": {
            "attenuation_factor": n(app_state.dl_att.get()),
            "sinr_min": n(app_state.dl_sinr_min.get()),
            "sinr_max": n(app_state.dl_sinr_max.get()),
        },
        "channel_model": app_state.ch_model.get(),
        "shadowing": bool(app_state.shadowing.get()),
    }

    # --- 4. Single Space Station ---
    single_space_station = {
        "frequency": n(app_state.v_freq.get()),
        "bandwidth": n(app_state.v_bw.get()),
        "tx_power_density": n(app_state.v_txpsd.get()),
        "polarization_loss": n(app_state.v_pol_loss.get()),
        "noise_temperature": n(app_state.v_tnoise.get()),
        "channel_model": app_state.v_ch_model.get(),
        "is_global_coordinate_system": bool(app_state.ss_is_global_cs.get()),
        "season": app_state.v_season.get(),
        "param_p619": {
            "mean_clutter_height": app_state.v_p619_clutter.get(),
            "below_rooftop": n(app_state.v_p619_below_rooftop.get()),
        },
        "geometry": {
            "altitude": n(app_state.v_alt.get()),
            "location": {
                "type": "FIXED",
                "fixed": {"lat_deg": n(app_state.v_fix_lat.get()), "long_deg": n(app_state.v_fix_lon.get())}
            },
            "es_altitude": n(app_state.v_es_alt.get()),
            "es_lat_deg": n(app_state.v_es_lat.get()),
            "es_long_deg": n(app_state.v_es_lon.get()),
            "azimuth": {"type": app_state.v_az_type.get()},
            "elevation": {"type": app_state.v_el_type.get()},
        },
        "antenna": {
            "pattern": app_state.v_ant_pattern.get(),
            "gain": n(app_state.v_ant_gain.get()),
        }
    }

    if app_state.v_ant_pattern.get() == "ITU-R S.672":
        single_space_station["antenna"]["itu_r_s_672"] = {
            "antenna_3_dB": n(app_state.v_s672_3db.get()),
            "antenna_l_s": n(app_state.v_s672_ls.get()),
        }

    return {"general": general, "imt": imt, "single_space_station": single_space_station}
