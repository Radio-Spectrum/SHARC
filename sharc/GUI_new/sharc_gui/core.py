# Auto-split from original sharc_gui.py
from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import RESULT_FIELDNAME_TO_PLOT_INFO  # noqa
from pathlib import Path
import random 

class CoreMixin:
    def _add_polygon3d(self, ax3d, poly_xy, z=0.0, face_alpha=0.06, edge_color="k", lw=1.0):
            """Adiciona polígono no plano z fixo."""
            verts3d = [(px, py, z) for (px, py) in poly_xy]
            pcoll = Poly3DCollection([verts3d], alpha=face_alpha, edgecolor=edge_color, linewidths=lw)
            pcoll.set_facecolor(edge_color)
            ax3d.add_collection3d(pcoll)

    def _apply_variables_to_prefix(self, base_prefix: str, combo_tags: dict) -> str:
        """
        Usa o output_dir_prefix como template e substitui {var} pelo TAG.
        Ex: base_prefix="output_{dist}" + combo_tags={"dist":"D1"} -> "output_D1"
        """
        try:
            return (base_prefix or "scenario").format(**(combo_tags or {}))
        except Exception:
            return base_prefix or "scenario"




    def _collect_var_combos(self):
        """
        Agora cada variável fornece uma lista de PARES (tag, value).
        Ex. dist: tags=["D1","D2"], values=[10000,20000]
            -> [("D1",10000), ("D2",20000)]
        Retorno:
        [{"vars": {...}, "tags": {...}}, ...]
        """
        var_names = []
        pair_lists = []

        for iid in self.var_table.get_children():
            var_key, tags_raw, vals_raw = self.var_table.item(iid, "values")

            var_key = str(var_key).strip()
            if not var_key:
                messagebox.showwarning("Variáveis", "var_key vazio.")
                return None

            # tags: precisa ser lista
            try:
                tags = ast.literal_eval(str(tags_raw))
                if not isinstance(tags, (list, tuple)) or len(tags) == 0:
                    raise ValueError()
                tags = [str(t).strip() for t in tags]
            except Exception:
                messagebox.showwarning("Variáveis", f"Tags inválidas para '{var_key}'. Use lista, ex: [\"D1\",\"D2\"].")
                return None

            # values: pode ser lista python OU glob/pasta (se você quiser manter paths automáticos)
            vals = self._expand_paths_field(str(vals_raw)) if hasattr(self, "_expand_paths_field") else None
            if vals is None or len(vals) == 0:
                try:
                    vals = ast.literal_eval(str(vals_raw))
                    if not isinstance(vals, (list, tuple)) or len(vals) == 0:
                        raise ValueError()
                    vals = list(vals)
                except Exception:
                    messagebox.showwarning("Variáveis", f"Valores inválidos para '{var_key}'.")
                    return None

            if len(tags) != len(vals):
                messagebox.showwarning(
                    "Variáveis",
                    f"'{var_key}': quantidade de tags ({len(tags)}) diferente da quantidade de valores ({len(vals)})."
                )
                return None

            pairs = list(zip(tags, vals))  # [(tag,value),...]
            var_names.append(var_key)
            pair_lists.append(pairs)

        if not var_names:
            return [{"vars": {}, "tags": {}}]

        combos = []
        for prod in itertools.product(*pair_lists):
            # prod é uma tupla com 1 par por variável: ((tag1,val1),(tag2,val2),...)
            combo_vars = {}
            combo_tags = {}
            for (var_key, (tag, val)) in zip(var_names, prod):
                combo_vars[var_key] = val
                combo_tags[var_key] = tag

            combos.append({"vars": combo_vars, "tags": combo_tags})

        return combos



    def _expand_paths_field(self, raw: str):
        s = (raw or "").strip()
        if not s:
            return []

        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, (list, tuple)):
                return [str(x) for x in obj]
        except Exception:
            pass

        if any(ch in s for ch in ["*", "?", "["]):
            return sorted(glob.glob(s))

        if os.path.isdir(s):
            return sorted(glob.glob(os.path.join(s, "*.yaml"))) + \
                sorted(glob.glob(os.path.join(s, "*.yml")))

        return [s]

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


            # =========================
            # SINGLE EARTH STATION (victim)
            # =========================
            def _build_single_earth_station():
                # --------- ANTENNA ----------
                pat = (self.se_ant_pattern.get() or "").strip()
                ant = {
                    "pattern": pat,
                    "gain": self._num_or_str(self.se_ant_gain.get()),
                }

                # Mapeia pattern -> chave do YAML (nome do objeto no parameters_antenna)
                # (mantive só os que sua GUI expõe campos específicos hoje)
                if pat in {
                    "ITU-R F.699",
                    "ITU-R S.465",
                    "ITU-R S.580",
                    "ITU-R S.1855",
                    "ITU-R Reg. RR. Appendice 7 Annex 3",
                }:
                    # todos usam "diameter"
                    key_map = {
                        "ITU-R F.699": "itu_r_f_699",
                        "ITU-R S.465": "itu_r_s_465",
                        "ITU-R S.580": "itu_r_s_580",
                        "ITU-R S.1855": "itu_r_s_1855",
                        "ITU-R Reg. RR. Appendice 7 Annex 3": "itu_reg_rr_a7_3",
                    }
                    ant[key_map[pat]] = {
                        "diameter": self._num_or_str(self.se_ant_diameter.get()),
                    }

                elif pat == "MODIFIED ITU-R S.465":
                    ant["itu_r_s_465_modified"] = {
                        "envelope_gain": self._num_or_str(self.se_ant_envelope_gain.get()),
                    }

                elif pat == "ITU-R S.672":
                    ant["itu_r_s_672"] = {
                        "antenna_3_dB": self._num_or_str(self.se_ant_3db.get()),
                        "antenna_l_s": self._num_or_str(self.se_ant_l_s.get()),
                    }

                elif pat == "ITU-R F.1245_fs":
                    ant["itu_r_f_1245_fs"] = {
                        "gain": self._num_or_str(self.se_ant_f1245_gain.get()),
                        "diameter": self._num_or_str(self.se_ant_f1245_diameter.get()),
                        "frequency": self._num_or_str(self.se_ant_f1245_frequency.get()),
                    }

                # --------- GEOMETRY ----------
                geo = {
                    "height": self._num_or_str(self.se_height.get()),
                    "location": {"type": (self.se_loc_type.get() or "").strip()},
                    "azimuth": {"type": (self.se_az_type.get() or "").strip()},
                    "elevation": {"type": (self.se_el_type.get() or "").strip()},
                }

                # location.* conforme o type
                loc_t = geo["location"]["type"]
                if loc_t == "FIXED":
                    geo["location"]["fixed"] = {
                        "x": self._num_or_str(self.se_loc_fixed_x.get()),
                        "y": self._num_or_str(self.se_loc_fixed_y.get()),
                    }
                elif loc_t == "CELL":
                    geo["location"]["cell"] = {
                        "min_dist_to_bs": self._num_or_str(self.se_loc_cell_min_dist_to_bs.get()),
                    }
                elif loc_t == "NETWORK":
                    geo["location"]["network"] = {
                        "min_dist_to_bs": self._num_or_str(self.se_loc_network_min_dist_to_bs.get()),
                    }
                elif loc_t == "UNIFORM_DIST":
                    geo["location"]["uniform_dist"] = {
                        "min_dist_to_center": self._num_or_str(self.se_loc_ud_min_dist_to_center.get()),
                        "max_dist_to_center": self._num_or_str(self.se_loc_ud_max_dist_to_center.get()),
                    }

                # azimuth.* conforme type
                az_t = geo["azimuth"]["type"]
                if az_t == "FIXED":
                    geo["azimuth"]["fixed"] = self._num_or_str(self.se_az_fixed.get())
                elif az_t == "UNIFORM_DIST":
                    geo["azimuth"]["uniform_dist"] = {
                        "min": self._num_or_str(self.se_az_ud_min.get()),
                        "max": self._num_or_str(self.se_az_ud_max.get()),
                    }
                # POINTING_AT_IMT_CENTER: só type mesmo

                # elevation.* conforme type (para POINTING_AT_IMT_CENTER você já comentou que é n/a)
                el_t = geo["elevation"]["type"]
                if el_t == "FIXED":
                    geo["elevation"]["fixed"] = self._num_or_str(self.se_el_fixed.get())
                elif el_t == "UNIFORM_DIST":
                    geo["elevation"]["uniform_dist"] = {
                        "min": self._num_or_str(self.se_el_ud_min.get()),
                        "max": self._num_or_str(self.se_el_ud_max.get()),
                    }

                # --------- CHANNEL MODEL ----------
                ch_model = (self.se_channel_model.get() or "").strip()

                se = {
                    "frequency": self._num_or_str(self.se_frequency.get()),
                    "bandwidth": self._num_or_str(self.se_bandwidth.get()),
                    "noise_temperature": self._num_or_str(self.se_noise_temperature.get()),
                    "adjacent_ch_reception": (self.se_adjacent_ch_reception.get() or "").strip(),
                    "adjacent_ch_selectivity": self._num_or_str(self.se_adjacent_ch_selectivity.get()),
                    "adjacent_ch_emissions": (self.se_adjacent_ch_emissions.get() or "").strip(),
                    "adjacent_ch_leak_ratio": self._num_or_str(self.se_adjacent_ch_leak_ratio.get()),
                    "spectral_mask": (self.se_spectral_mask.get() or "").strip(),
                    "spurious_emissions": self._num_or_str(self.se_spurious_emissions.get()),
                    "tx_power_density": self._num_or_str(self.se_tx_power_density.get()),
                    "polarization_loss": self._num_or_str(self.se_polarization_loss.get()),
                    "channel_model": ch_model,
                    "geometry": geo,
                    "antenna": ant,
                }

                # remove polarization_loss se vazio (opcional)
                if se["polarization_loss"] in ("", None):
                    del se["polarization_loss"]

                # P452 somente se selecionado
                if ch_model == "P452":
                    p452 = {
                        "atmospheric_pressure": self._num_or_str(self.p452_atmospheric_pressure.get()),
                        "air_temperature": self._num_or_str(self.p452_air_temperature.get()),
                        "percentage_p": self._num_or_str(self.p452_percentage_p.get()),
                        "N0": self._num_or_str(self.p452_N0.get()),
                        "delta_N": self._num_or_str(self.p452_delta_N.get()),
                        "polarization": (self.p452_polarization.get() or "").strip(),
                        "Dct": self._num_or_str(self.p452_Dct.get()),
                        "Dcr": self._num_or_str(self.p452_Dcr.get()),
                        "Hte": self._num_or_str(self.p452_Hte.get()),
                        "Hre": self._num_or_str(self.p452_Hre.get()),
                        "clutter_loss": bool(self.p452_clutter_loss.get()),
                        "tx_lat": self._num_or_str(self.p452_tx_lat.get()),
                        "rx_lat": self._num_or_str(self.p452_rx_lat.get()),
                        "is_terrain": bool(self.p452_is_terrain.get()),
                    }
                    # clutter_type só se clutter_loss=True
                    if p452["clutter_loss"]:
                        p452["clutter_type"] = (self.p452_clutter_type.get() or "").strip()

                    se["param_p452"] = p452

                return se


            # =========================================================
            # ... seu código que monta general, imt, etc acima ...
            # =========================================================

            yaml_dict = {
                "general": general,
                "imt": imt,
            }
            system = (self.var_system.get() or "").strip()
            if system == "SINGLE_EARTH_STATION":
                yaml_dict["single_earth_station"] = _build_single_earth_station()
            else:
                yaml_dict["single_space_station"] = single_space_station

            # 🔥 LIMPA tudo automaticamente
            return self._clean_yaml(yaml_dict)

    def _deep_format(self, obj, combo_vars):
            """Aplica .format(**combo) recursivamente em strings do dicionário."""
            if isinstance(obj, dict):
                return {k: self._deep_format(v, combo_vars) for k, v in obj.items()}
            if isinstance(obj, list):
                return [self._deep_format(v, combo_vars) for v in obj]
            if isinstance(obj, str):
                try:
                    return obj.format(**combo_vars)
                except Exception:
                    return obj
            return obj

    def _hexagon_xy(self, x0, y0, R):
            """
            Hex regular 'flat-top' no plano z=0, centrado em (x0,y0),
            com raio R (centro -> vértice). Giro de +30° para lados horizontais.
            """
            ang = np.deg2rad(30 + np.arange(0, 360, 60))  # 30, 90, 150, ...
            xs = x0 + R * np.cos(ang)
            ys = y0 + R * np.sin(ang)
            return list(zip(xs, ys))

    def _kill_remote_yaml(self, remote_yaml, tree_iid):

            try:
                # 1) Localizar PID remoto
                find_pid_cmd = (
                    f"ps -eo pid,cmd | grep '{remote_yaml}' "
                    f"| grep -v grep | awk '{{print $1}}'"
                )

                stdin, stdout, stderr = self.ssh_client.exec_command(find_pid_cmd)
                pid = stdout.read().decode().strip()

                if not pid:
                    self._append_log(f"[REMOTE] Nenhum processo encontrado para {remote_yaml}.")
                    self._update_row(tree_iid, status="Finalizado")
                    return

                self._append_log(f"[REMOTE] Matando processo PID={pid} para {remote_yaml}")

                # 2) Enviar sinal de término
                kill_cmd = f"kill -9 {pid}"
                self.ssh_client.exec_command(kill_cmd)

                self._update_row(tree_iid, status="Cancelado")
                self._append_log(f"[REMOTE] Processo {pid} finalizado.")

            except Exception as e:
                messagebox.showerror("SSH Kill", f"Erro ao parar execução remota:\n{e}")
                self._append_log(f"[REMOTE][ERRO kill] {e}")

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

    def _report_callback_exception(self, exc, val, tb):
            # Mostra um diálogo e NÃO fecha o programa
            msg = ''.join(traceback.format_exception(exc, val, tb))
            messagebox.showerror(
                "Erro inesperado",
                "Ocorreu um erro, mas o programa continuará aberto.\n\n"
                f"{val}\n\nDetalhes:\n{msg[:4000]}"  # evita caixa gigante
            )

    def _run_remote_yaml_paramiko(self, remote_yaml, tree_iid, declared_total):
            """
            Executa main_cli.py remotamente via Paramiko e atualiza a Treeview
            em tempo real, de forma análoga ao runner local.
            """

            cmd = (
                "cd /home/achiles.mota/SHARC && "
                "source /home/achiles.mota/SHARC/.sharc_env/bin/activate && "
                f"python3 /home/achiles.mota/SHARC/sharc/main_cli.py -p {remote_yaml} 2>&1"
            )

            # Arquitetura similar ao _run_one_yaml
            pat_xy = re.compile(r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
            pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

            done = 0
            total = declared_total
            t0 = time.time()

            # Marca início
            self._update_row(
                tree_iid,
                status="Rodando (remoto)",
                snap=f"0/{total}",
                pct="0",
                eta="--",
            )

            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            if not declared_total or declared_total <= 0:
                declared_total = 1_000_000  # fallback de segurança
            # Lê linha a linha, em tempo real
            for line in iter(stdout.readline, ""):
                if not line:
                    break

                line = line.rstrip("\n")
                self._append_log(f"[REMOTE] {line}")

                m1 = pat_drop1.search(line)
                m2 = pat_drop2.search(line)
                m3 = pat_hash.search(line)

                if m1:
                    done = int(m1.group(1))
                    total = int(m1.group(2))
                elif m2:
                    done = int(m2.group(1))
                    total = int(m2.group(2))
                elif m3 and total:
                    done = int(m3.group(1))
                if "drop" in line.lower() or "mc" in line.lower() or "iter" in line.lower():
                    self._append_log(f"[REMOTE][PROGRESS RAW] {line}")
                if done:
                    now = time.time()
                    pct = f"{(100.0 * done / max(total, 1)):.1f}"
                    eta = self._eta_string(t0, now, done, total)

                    self._update_row(
                        tree_iid,
                        status="Rodando (remoto)",
                        snap=f"{done}/{total}",
                        pct=pct,
                        eta=eta,
                    )

            # Espera fim do comando
            rc = stdout.channel.recv_exit_status()
            final_status = "OK" if rc == 0 else f"Erro {rc}"

            self._update_row(
                tree_iid,
                status=final_status,
                snap=f"{done}/{total}",
                pct="100" if rc == 0 else f"{(100.0 * done / max(total, 1)):.1f}",
                eta="00:00",
            )
            # Limpeza automática da pasta temporária
            self._cleanup_remote_tmp_dir()

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

    def _write_yaml_combos(self, root, outdir, combos):
        base_prefix = (root.get("general", {}) or {}).get("output_dir_prefix") or "scenario"

        os.makedirs(outdir, exist_ok=True)

        for combo in combos:
            combo_vars = combo.get("vars", {})
            combo_tags = combo.get("tags", {})

            # 1) Nome do YAML usa TAGS
            prefix_final = self._apply_variables_to_prefix(base_prefix, combo_tags)

            # 2) Conteúdo base do YAML usa VALORES
            root_fmt = self._deep_format(root, combo_vars)

            # 3) output_dir_prefix no YAML = nome do YAML
            root_fmt.setdefault("general", {})
            root_fmt["general"]["output_dir_prefix"] = prefix_final

            # 4) Seed aleatório por YAML
            try:
                if hasattr(self, "var_seed_random") and bool(self.var_seed_random.get()):
                    root_fmt["general"]["seed"] = random.randint(1, 9999)
            except Exception:
                pass

            # =========================================================
            # 5) IMT config: carregar por combo e INJETAR no root_fmt
            # =========================================================
            imt_cfg_path = None

            # Preferência 1: variável dedicada
            if "imt_config_path" in combo_vars:
                imt_cfg_path = combo_vars.get("imt_config_path")

            # Preferência 2: campo global (resolvido por VALORES)
            if not imt_cfg_path and hasattr(self, "var_imt_config_path"):
                tpl = (self.var_imt_config_path.get() or "").strip()
                if tpl:
                    try:
                        imt_cfg_path = tpl.format(**combo_vars)  # VALORES primeiro
                    except Exception:
                        imt_cfg_path = tpl

            # Preferência 3: autodetect .json em combo_vars
            if not imt_cfg_path:
                for v in combo_vars.values():
                    if isinstance(v, str):
                        s = v.strip().strip('"').strip("'")
                        if s.lower().endswith(".json"):
                            imt_cfg_path = s
                            break

            # Se houver IMT json, carrega e injeta no YAML
            if imt_cfg_path:
                imt_cfg_path = str(imt_cfg_path).strip()

                if "{" in imt_cfg_path and "}" in imt_cfg_path:
                    raise FileNotFoundError(f"IMT config ainda tem placeholder não resolvido: {imt_cfg_path}")

                if not os.path.isfile(imt_cfg_path):
                    raise FileNotFoundError(f"IMT config não encontrado: {imt_cfg_path}")

                ok = self._load_imt_config_from_path(imt_cfg_path, silent=True)
                if not ok:
                    raise RuntimeError(f"Falha ao carregar IMT config: {imt_cfg_path}")

                # >>> A LINHA QUE FALTAVA <<<
                # Atualiza o bloco IMT do YAML com o estado recém-carregado
                root_fmt["imt"] = self._imt_to_dict()

            # 6) Escreve YAML
            text = build_yaml_text(root_fmt)
            fpath = os.path.join(outdir, f"{prefix_final}.yaml")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(text)







    def _clean_yaml(self, obj):
        """
        Remove keys with empty / None / "" values recursively.
        """
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():
                v_clean = self._clean_yaml(v)
                if v_clean in (None, "", {}, []):
                    continue
                cleaned[k] = v_clean
            return cleaned

        if isinstance(obj, list):
            cleaned = [self._clean_yaml(v) for v in obj]
            return [v for v in cleaned if v not in (None, "", {}, [])]

        return obj