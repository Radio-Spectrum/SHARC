import yaml
from tkinter import messagebox, filedialog

def _save_imt_config(self):
    """Save IMT configuration to a YAML file."""
    data = {
        # General IMT
        "imt_min_sep": self.imt_min_sep.get(),
        "imt_interfered": self.imt_interfered.get(),
        "imt_freq": self.imt_freq.get(),
        "imt_bw": self.imt_bw.get(),
        "imt_rb_bw": self.imt_rb_bw.get(),
        "imt_spec_mask": self.imt_spec_mask.get(),
        "imt_spurious": self.imt_spurious.get(),
        "imt_adj_ant_model": self.imt_adj_ant_model.get(),
        "imt_guard_ratio": self.imt_guard_ratio.get(),

        # Topography
        "topo_c_lat": self.topo_c_lat.get(),
        "topo_c_lon": self.topo_c_lon.get(),
        "topo_c_alt": self.topo_c_alt.get(),
        "topo_type": self.topo_type.get(),
        "topo_dist_type": self.topo_dist_type.get(),
        "topo_num_bs": self.topo_num_bs.get(),
        "topo_cell_radius": self.topo_cell_radius.get(),
        "topo_rng": self.topo_rng.get(),
        "countries": self.txt_countries.get("1.0", "end"),
        "path_shp": self.path_shp.get(),
        "path_raster": self.path_raster.get(),
        "raster_encoding": self.raster_encoding.get(),
        "sedac_mode": self.sedac_mode.get(),
        "sedac_min": self.sedac_min.get(),
        "sedac_max": self.sedac_max.get(),
        "pixel_area_method": self.pixel_area_method.get(),

        # Base Station (BS)
        "bs_load_prob": self.bs_load_prob.get(),
        "bs_power": self.bs_power.get(),
        "bs_height": self.bs_height.get(),
        "bs_nf": self.bs_nf.get(),
        "bs_ohmic": self.bs_ohmic.get(),
        "bs_norm": self.bs_norm.get(),
        "bs_elem_pat": self.bs_elem_pat.get(),
        "bs_min_arr_gain": self.bs_min_arr_gain.get(),
        "bs_downtilt": self.bs_downtilt.get(),
        "bs_elem_max_g": self.bs_elem_max_g.get(),
        "bs_phi3": self.bs_phi3.get(),
        "bs_theta3": self.bs_theta3.get(),
        "bs_rows": self.bs_rows.get(),
        "bs_cols": self.bs_cols.get(),
        "bs_elem_hs": self.bs_elem_hs.get(),
        "bs_elem_vs": self.bs_elem_vs.get(),
        "bs_elem_am": self.bs_elem_am.get(),
        "bs_elem_sla_v": self.bs_elem_sla_v.get(),
        "bs_mult": self.bs_mult.get(),
        "bs_sub_enabled": self.bs_sub_enabled.get(),
        "bs_sub_rows": self.bs_sub_rows.get(),
        "bs_sub_evspace": self.bs_sub_evspace.get(),
        "bs_sub_e_downtilt": self.bs_sub_e_downtilt.get(),

        # User Equipment (UE)
        "ue_k": self.ue_k.get(),
        "ue_km": self.ue_km.get(),
        "ue_indoor": self.ue_indoor.get(),
        "ue_dist_type": self.ue_dist_type.get(),
        "ue_tx_power_ctrl": self.ue_tx_power_ctrl.get(),
        "ue_p_o_pusch": self.ue_p_o_pusch.get(),
        "ue_alpha": self.ue_alpha.get(),
        "ue_p_cmax": self.ue_p_cmax.get(),
        "ue_p_dyn": self.ue_p_dyn.get(),
        "ue_height": self.ue_height.get(),
        "ue_nf": self.ue_nf.get(),
        "ue_ohmic": self.ue_ohmic.get(),
        "ue_body_loss": self.ue_body_loss.get(),
        "ue_norm": self.ue_norm.get(),
        "ue_elem_pat": self.ue_elem_pat.get(),
        "ue_min_arr_gain": self.ue_min_arr_gain.get(),
        "ue_elem_max_g": self.ue_elem_max_g.get(),
        "ue_phi3": self.ue_phi3.get(),
        "ue_theta3": self.ue_theta3.get(),
        "ue_rows": self.ue_rows.get(),
        "ue_cols": self.ue_cols.get(),
        "ue_elem_am": self.ue_elem_am.get(),
        "ue_elem_sla_v": self.ue_elem_sla_v.get(),
        "ue_mult": self.ue_mult.get(),

        # Uplink / Downlink
        "ul_att": self.ul_att.get(),
        "ul_sinr_min": self.ul_sinr_min.get(),
        "ul_sinr_max": self.ul_sinr_max.get(),
        "dl_att": self.dl_att.get(),
        "dl_sinr_min": self.dl_sinr_min.get(),
        "dl_sinr_max": self.dl_sinr_max.get(),
        "ch_model": self.ch_model.get(),
        "shadowing": self.shadowing.get(),
    }

    path = filedialog.asksaveasfilename(
        defaultextension=".yaml",
        filetypes=[("YAML files", "*.yaml"), ("YML files", "*.yml")],
        initialfile="imt_config.yaml"
    )
    if not path:
        return

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)

    messagebox.showinfo("IMT", f"Configuration saved successfully:\n{path}")


def _toggle_ue_distribution(self):
    is_ang_dist = (self.ue_dist_type.get().upper() == "ANGLE_AND_DISTANCE")
    if hasattr(self, "_ue_col_dist_frame"):
        if is_ang_dist:
            self._ue_col_dist_frame.grid()      # mostra
        else:
            self._ue_col_dist_frame.grid_remove()  # esconde


def _load_imt_config(self):
    """Load IMT configuration from a YAML file."""
    path = filedialog.askopenfilename(
        filetypes=[("YAML files", "*.yaml *.yml")]
    )
    if not path:
        return

    with open(path, "r", encoding="utf-8") as f:
        vals = yaml.safe_load(f) or {}

    # Generic variable loader
    for key, tk_var in vars(self).items():
        if hasattr(tk_var, "set") and key in vals:
            try:
                tk_var.set(vals[key])
            except Exception:
                pass

    # Handle Text widget separately
    if "countries" in vals:
        self.txt_countries.delete("1.0", "end")
        self.txt_countries.insert("1.0", vals["countries"])

    messagebox.showinfo("IMT", "IMT configuration successfully loaded.")
