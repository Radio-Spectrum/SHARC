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