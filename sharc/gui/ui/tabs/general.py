import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
import random
import json
import yaml  # Requires: pip install PyYAML
import copy
import itertools

# --- Project Imports ---
# Ensure these exist in your project
from utils import add_row_three
from ui.tabs.assets.general_tab.variable_editor import VariableEditor
from ui.tabs.assets.general_tab.general_tools import parse_list_safe


def load_param_file(filepath):
    """Safely loads a JSON or YAML file."""
    path = Path(filepath)
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            if path.suffix.lower() == '.json':
                return json.load(f)
            elif path.suffix.lower() in ['.yaml', '.yml']:
                return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
    return {}


def deep_merge(base_dict, new_dict):
    """Recursively merges new_dict into base_dict."""
    for key, value in new_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


class GeneralTab:
    """
    Manages the 'General' tab and orchestrates the generation of complex YAML configuration files.
    Includes builders to translate 'flat' UI variables into hierarchical Simulator structures.
    """

    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        # Local State
        self.var_use_random_seed = tk.BooleanVar(value=False)
        self.path_entries = {}

        # Build Interface
        self._build_top_toolbar()
        self._build_main_form()
        self._setup_traces()

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_top_toolbar(self):
        toolbar_frame = ttk.Frame(self.frame)
        toolbar_frame.pack(side="top", fill="x", padx=5, pady=(10, 10))

        self.btn_files = ttk.Menubutton(
            toolbar_frame,
            text="📁 File Operations (Presets)",
            bootstyle="primary",
            width=25
        )
        self.btn_files.pack(side="left")

        self.menu_files = tk.Menu(self.btn_files, tearoff=0)
        self.btn_files.configure(menu=self.menu_files)

        self.menu_files.add_command(label="💾 Save Current Preset (.json)", command=self.save_config)
        self.menu_files.add_command(label="📂 Load Preset (.json)", command=self.load_config)

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", pady=(0, 15))

    def _build_main_form(self):
        vcmd = (self.frame.register(self._validate_int), '%P')
        frm = ttk.Labelframe(self.frame, text="General Parameters", padding=10)
        frm.pack(fill="x", pady=(0, 6))

        # --- Row 1: Seed & Snapshots ---
        f_seed_cont = ttk.Frame(frm)
        self.e_seed = ttk.Entry(
            f_seed_cont, textvariable=self.app.var_seed,
            width=8, validate='key', validatecommand=vcmd
        )
        self.e_seed.pack(side="left")

        cb_rnd = ttk.Checkbutton(
            f_seed_cont, text="Random",
            variable=self.var_use_random_seed,
            command=self._toggle_random_seed,
            bootstyle="round-toggle"
        )
        cb_rnd.pack(side="left", padx=(10, 0))

        e_snaps = ttk.Entry(
            frm, textvariable=self.app.var_snaps,
            width=12, validate='key', validatecommand=vcmd
        )

        cb_sys = ttk.Combobox(
            frm, textvariable=self.app.var_system,
            values=["SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"],
            state="readonly", width=26
        )

        add_row_three(frm, 0, [
            ("Seed", f_seed_cont),
            ("Num Snapshots", e_snaps),
            ("System Type", cb_sys)
        ])

        # --- Row 2 & 3: Paths ---
        self._build_path_row(frm, 1, "Output Dir", self.app.var_outdir, self._pick_outdir)
        self._build_path_row(frm, 2, "YAML Dir", self.app.var_yaml_dir, self._pick_yamldir)

        # --- Row 4: Config & Overwrite ---
        e_prefix = ttk.Entry(frm, textvariable=self.app.var_prefix)
        cb_link = ttk.Combobox(
            frm, textvariable=self.app.var_imt_link,
            values=["DOWNLINK", "UPLINK"], state="readonly", width=18
        )
        cb_overwrite = ttk.Checkbutton(
            frm, variable=self.app.var_overwrite,
            text="Overwrite", bootstyle="round-toggle"
        )

        add_row_three(frm, 3, [
            ("Filename Prefix", e_prefix),
            ("IMT Link Direction", cb_link),
            ("Output Options", cb_overwrite)
        ])

        # --- Preview Label ---
        self.lbl_preview = ttk.Label(
            frm, text="Preview: ...", foreground="gray", font=("Segoe UI", 8, "italic"))
        self.lbl_preview.grid(row=4, column=0, columnspan=6, sticky="w", padx=5, pady=(0, 5))

        # --- Row 5: Interference Flags ---
        cb_adj = ttk.Checkbutton(frm, variable=self.app.var_adj, text="Active", bootstyle="square-toggle")
        cb_coch = ttk.Checkbutton(frm, variable=self.app.var_coch, text="Active", bootstyle="square-toggle")

        add_row_three(frm, 5, [
            ("Enable Adj Channel", cb_adj),
            ("Enable Co-Channel", cb_coch),
            ("", ttk.Label(frm, text=""))
        ])

        # --- Variable Table ---
        self._build_var_table_ui()

    def _build_path_row(self, parent, row_idx, label_text, var, cmd):
        row = ttk.Frame(parent)
        row.grid(row=row_idx, column=0, columnspan=6, sticky="we", pady=5)
        ttk.Label(row, text=label_text).pack(side="left")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row, text="Browse", command=cmd, bootstyle="secondary-outline").pack(side="left")
        self.path_entries[str(var)] = entry

    def _build_var_table_ui(self):
        box = ttk.Labelframe(self.frame, text="Combination Variables (Tags -> YAML Values)", padding=10)
        box.pack(fill="both", expand=True, pady=(15, 0))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="+ Add Variable", command=self._var_add, bootstyle="info-outline").pack(side="left")
        ttk.Button(toolbar, text="✎ Edit", command=self._var_edit, bootstyle="secondary-outline").pack(side="left", padx=6)
        ttk.Button(toolbar, text="🗑 Remove", command=self._var_remove, bootstyle="danger-outline").pack(side="left", padx=6)

        self.var_table = ttk.Treeview(
            box, columns=("var", "tags", "values"), show="headings", height=6, bootstyle="info"
        )
        self.var_table.heading("var", text="Variable Name")
        self.var_table.heading("tags", text="Replacement Tags")
        self.var_table.heading("values", text="Values List")
        self.var_table.column("var", width=150)
        self.var_table.column("tags", width=250)
        self.var_table.column("values", width=450)
        self.var_table.pack(fill="both", expand=True, pady=(4, 6))
        self.var_table.bind("<Double-1>", lambda e: self._var_edit())

        # Generate Button
        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(15, 0))
        ttk.Button(
            row_gen, text="⚡ GENERATE YAML FILES",
            command=self.save_yaml_to_yamldir,
            bootstyle="success", width=25
        ).pack(side="left")

    # =========================================================================
    # CORE GENERATION LOGIC (UPDATED WITH BUILDERS)
    # =========================================================================

    def save_yaml_to_yamldir(self):
        """
        Generates YAML files using a structured builder pattern.
        Converts flat UI variables into nested dictionary structures.
        """
        
        # 1. Identify System Type and Key
        sys_type = self.app.var_system.get()
        # Ensure correct mapping: SINGLE_SPACE_STATION -> single_space_station
        sys_key = sys_type.lower() 

        # 2. Base Configuration (The 'general' block)
        general_conf = {
            "seed": int(self.app.var_seed.get()) if not self.var_use_random_seed.get() else "RANDOM",
            "num_snapshots": int(self.app.var_snaps.get()),
            "overwrite_output": self.app.var_overwrite.get(),
            "output_dir": self.app.var_outdir.get(),
            "output_dir_prefix": self.app.var_prefix.get(),
            "system": sys_type,
            "imt_link": self.app.var_imt_link.get(),
            "enable_adjacent_channel": self.app.var_adj.get(),
            "enable_cochannel": self.app.var_coch.get()
        }

        # 3. Prepare Combinations
        vars_processed = []
        for child in self.var_table.get_children():
            row = self.var_table.item(child)["values"]
            tags = parse_list_safe(row[1], [])
            vals = parse_list_safe(row[2], [])
            
            if len(tags) == len(vals):
                vars_processed.append([(row[0], t, v) for t, v in zip(tags, vals)])
            else:
                messagebox.showerror("Error", f"Length mismatch in variable '{row[0]}'")
                return
        
        combinations = list(itertools.product(*vars_processed)) if vars_processed else [[]]
        
        save_dir = Path(self.app.var_yaml_dir.get())
        if not save_dir.exists():
            try:
                save_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create directory: {e}")
                return

        count = 0
        prefix_tmpl = self.app.var_prefix.get()

        # 4. Loop through combinations
        for combo in combinations:
            # Initialize Strict Structure
            final_structure = {
                "general": copy.deepcopy(general_conf),
                "imt": {},
                sys_key: {}
            }
            
            fname_vars = {}

            for var_name, var_tag, var_val in combo:
                fname_vars[var_name] = var_tag
                
                # Check if value is a file path to load
                is_file = False
                if isinstance(var_val, str):
                    clean_val = var_val.strip()
                    if clean_val.lower().endswith(('.json', '.yaml', '.yml')) and Path(clean_val).exists():
                        is_file = True
                
                if is_file:
                    flat_data = load_param_file(var_val)
                    
                    # --- BUILDER LOGIC ---
                    # 1. Check if it's IMT data (flat)
                    if self._is_imt_data(flat_data):
                        structured_imt = self._build_imt_hierarchy(flat_data)
                        deep_merge(final_structure["imt"], structured_imt)
                    
                    # 2. Check if it's System data (flat or partial)
                    elif self._is_system_data(flat_data):
                        structured_sys = self._build_system_hierarchy(flat_data, sys_type)
                        deep_merge(final_structure[sys_key], structured_sys)
                    
                    # 3. Fallback: Maybe it's already a structured YAML fragment?
                    else:
                        # Try to merge into root if keys match root keys, else default to general?
                        # For safety, we merge to root
                        deep_merge(final_structure, flat_data)
                
                else:
                    # Simple variable (not file)
                    # We can assume it might be used for prefix, or we could add to general
                    # final_structure["general"][var_name] = var_val
                    pass

            # 5. Finalize Filename
            try:
                fname = prefix_tmpl.format(**fname_vars)
                final_structure["general"]["output_dir_prefix"] = fname
                if not fname.endswith('.yaml'): fname += ".yaml"
            except KeyError as e:
                messagebox.showerror("Error", f"Prefix requires variable {e} which is missing.")
                return

            # Handle Random Seed
            if final_structure["general"]["seed"] == "RANDOM":
                final_structure["general"]["seed"] = random.randint(1, 999999)

            # 6. Save
            out_path = save_dir / fname
            try:
                with open(out_path, 'w', encoding='utf-8') as f:
                    yaml.dump(final_structure, f, default_flow_style=False, sort_keys=False)
                count += 1
            except Exception as e:
                print(f"Error saving {fname}: {e}")

        messagebox.showinfo("Success", f"Generated {count} configuration files in:\n{save_dir}")

    # =========================================================================
    # HIERARCHY BUILDERS (TRANSLATORS)
    # =========================================================================

    def _is_imt_data(self, data):
        """Heuristic to detect if flat data belongs to IMT tab."""
        # Look for unique keys defined in IMT tab
        markers = ["bs_power", "ue_height", "topo_type", "imt_freq", "ue_indoor", "macro_intersite"]
        return any(k in data for k in markers)

    def _is_system_data(self, data):
        """Heuristic to detect if flat data belongs to System tab."""
        # Look for unique keys defined in SES/SSS tab
        markers = ["tx_power_density", "noise_temperature", "p452", "geometry", "es_lat_deg"]
        return any(k in data for k in markers)

    def _build_imt_hierarchy(self, flat):
        """
        Translates flat IMT variables into the nested YAML structure.
        """
        def g(k, d=None): return flat.get(k, d)
        
        imt = {}

        # 1. Global IMT Parameters
        if "imt_min_sep" in flat: imt["minimum_separation_distance_bs_ue"] = g("imt_min_sep")
        if "imt_interfered" in flat: imt["interfered_with"] = g("imt_interfered")
        if "imt_freq" in flat: imt["frequency"] = g("imt_freq")
        if "imt_bw" in flat: imt["bandwidth"] = g("imt_bw")
        if "imt_rb_bw" in flat: imt["rb_bandwidth"] = g("imt_rb_bw")
        if "imt_spec_mask" in flat: imt["spectral_mask"] = g("imt_spec_mask")
        if "imt_spurious" in flat: imt["spurious_emissions"] = g("imt_spurious")
        if "imt_adj_ant_model" in flat: imt["adjacent_antenna_model"] = g("imt_adj_ant_model")
        if "imt_guard_ratio" in flat: imt["guard_band_ratio"] = g("imt_guard_ratio")

        # 2. Topology
        if "topo_type" in flat:
            imt["topology"] = {
                "central_latitude": g("topo_c_lat"),
                "central_longitude": g("topo_c_lon"),
                "central_altitude": g("topo_c_alt"),
                "type": g("topo_type")
            }
            if g("topo_type") == "MACROCELL":
                imt["topology"]["macrocell"] = {
                    "intersite_distance": g("macro_intersite"),
                    "wrap_around": g("macro_wrap"),
                    "num_clusters": int(g("macro_clusters", 1))
                }
            # Add other topology types (HOTSPOT/SBS) if needed using similar logic

        # 3. Base Station (BS)
        if "bs_power" in flat:
            imt["bs"] = {
                "load_probability": g("bs_load_prob"),
                "conducted_power": g("bs_power"),
                "height": g("bs_height"),
                "noise_figure": g("bs_nf"),
                "ohmic_loss": g("bs_ohmic"),
                "antenna": {
                    "array": {
                        "normalization": g("bs_norm"),
                        "element_pattern": g("bs_elem_pat"),
                        "minimum_array_gain": g("bs_min_arr_gain"),
                        "horizontal_beamsteering_range": [g("bs_h_steer_min"), g("bs_h_steer_max")],
                        "vertical_beamsteering_range": [g("bs_v_steer_min"), g("bs_v_steer_max")],
                        "downtilt": g("bs_downtilt"),
                        "element_max_g": g("bs_elem_max_g"),
                        "element_phi_3db": g("bs_phi3"),
                        "element_theta_3db": g("bs_theta3"),
                        "n_rows": g("bs_rows"),
                        "n_columns": g("bs_cols"),
                        "element_horiz_spacing": g("bs_elem_hs"),
                        "element_vert_spacing": g("bs_elem_vs"),
                        "element_am": g("bs_elem_am"),
                        "element_sla_v": g("bs_elem_sla_v"),
                        "multiplication_factor": g("bs_mult"),
                        "subarray": {
                            "is_enabled": g("bs_sub_enabled"),
                            "n_rows": g("bs_sub_rows"),
                            "element_vert_spacing": g("bs_sub_evspace"),
                            "eletrical_downtilt": g("bs_sub_e_downtilt")
                        }
                    }
                }
            }

        # 4. UE
        if "ue_height" in flat:
            imt["ue"] = {
                "k": int(g("ue_k", 1)),
                "k_m": int(g("ue_km", 1)),
                "indoor_percent": g("ue_indoor"),
                "distribution_type": g("ue_dist_type"),
                "tx_power_control": g("ue_tx_power_ctrl"),
                "p_o_pusch": g("ue_p_o_pusch"),
                "alpha": g("ue_alpha"),
                "p_cmax": g("ue_p_cmax"),
                "power_dynamic_range": g("ue_p_dyn"),
                "height": g("ue_height"),
                "noise_figure": g("ue_nf"),
                "ohmic_loss": g("ue_ohmic"),
                "body_loss": g("ue_body_loss"),
                "antenna": {
                    "array": {
                        "normalization": g("ue_norm"),
                        "element_pattern": g("ue_elem_pat"),
                        "minimum_array_gain": g("ue_min_arr_gain"),
                        "element_max_g": g("ue_elem_max_g"),
                        "element_phi_3db": g("ue_phi3"),
                        "element_theta_3db": g("ue_theta3"),
                        "n_rows": g("ue_rows"),
                        "n_columns": g("ue_cols"),
                        "element_am": g("ue_elem_am"),
                        "element_sla_v": g("ue_elem_sla_v"),
                        "multiplication_factor": g("ue_mult")
                    }
                }
            }

        # 5. Link & Channel
        if "ul_sinr_min" in flat:
            imt["uplink"] = {
                "attenuation_factor": g("ul_att"),
                "sinr_min": g("ul_sinr_min"),
                "sinr_max": g("ul_sinr_max")
            }
        if "dl_sinr_min" in flat:
            imt["downlink"] = {
                "attenuation_factor": g("dl_att"),
                "sinr_min": g("dl_sinr_min"),
                "sinr_max": g("dl_sinr_max")
            }
        if "ch_model" in flat: imt["channel_model"] = g("ch_model")
        if "shadowing" in flat: imt["shadowing"] = g("shadowing")

        return imt

    def _build_system_hierarchy(self, flat, sys_type):
        """
        Translates flat System variables into the nested YAML structure.
        """
        def g(k, d=None): return flat.get(k, d)
        
        sys = {}
        
        # Standard Params
        if "frequency" in flat: sys["frequency"] = g("frequency")
        if "bandwidth" in flat: sys["bandwidth"] = g("bandwidth")
        if "tx_power_density" in flat: sys["tx_power_density"] = g("tx_power_density")
        if "noise_temperature" in flat: sys["noise_temperature"] = g("noise_temperature")
        if "channel_model" in flat: sys["channel_model"] = g("channel_model")
        if "polarization_loss" in flat: sys["polarization_loss"] = g("polarization_loss")

        # Complex Blocks (Usually saved as dicts in the JSON by SES/SSS tabs)
        if "geometry" in flat: sys["geometry"] = flat["geometry"]
        if "antenna" in flat: sys["antenna"] = flat["antenna"]
        if "param_p619" in flat: sys["param_p619"] = flat["param_p619"]
        
        # P452 Handling
        # If the key 'p452' exists at the top level of the JSON, ensure it goes into the system block
        if "p452" in flat: sys["p452"] = flat["p452"]

        return sys

    # =========================================================================
    # PRESET LOGIC
    # =========================================================================

    def save_config(self):
        table_data = []
        for child in self.var_table.get_children():
            table_data.append(self.var_table.item(child)["values"])

        data = {
            "seed": self.app.var_seed.get(),
            "use_random_seed": self.var_use_random_seed.get(),
            "snaps": self.app.var_snaps.get(),
            "system": self.app.var_system.get(),
            "output_dir": self.app.var_outdir.get(),
            "yaml_dir": self.app.var_yaml_dir.get(),
            "prefix": self.app.var_prefix.get(),
            "imt_link": self.app.var_imt_link.get(),
            "overwrite": self.app.var_overwrite.get(),
            "adj_channel": self.app.var_adj.get(),
            "co_channel": self.app.var_coch.get(),
            "variables_table": table_data
        }
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Configuration", "*.json")], title="Save Configuration Preset"
        )
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                messagebox.showinfo("Success", f"Preset saved to:\n{Path(fpath).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save preset:\n{e}")

    def load_config(self):
        fpath = filedialog.askopenfilename(filetypes=[("JSON Configuration", "*.json")], title="Load Configuration Preset")
        if not fpath: return
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.app.var_seed.set(data.get("seed", "123"))
            self.var_use_random_seed.set(data.get("use_random_seed", False))
            self._toggle_random_seed()
            self.app.var_snaps.set(data.get("snaps", "100"))
            self.app.var_system.set(data.get("system", ""))
            self.app.var_outdir.set(data.get("output_dir", ""))
            self.app.var_yaml_dir.set(data.get("yaml_dir", ""))
            self.app.var_prefix.set(data.get("prefix", "sim_{var}"))
            self.app.var_imt_link.set(data.get("imt_link", "DOWNLINK"))
            self.app.var_overwrite.set(data.get("overwrite", False))
            self.app.var_adj.set(data.get("adj_channel", False))
            self.app.var_coch.set(data.get("co_channel", False))

            for item in self.var_table.get_children(): self.var_table.delete(item)
            for row in data.get("variables_table", []): self.var_table.insert("", "end", values=row)

            self._check_path(self.app.var_outdir)
            self._check_path(self.app.var_yaml_dir)
            self._update_preview()
            messagebox.showinfo("Success", "Configuration loaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset:\n{e}")

    def _toggle_random_seed(self):
        if self.var_use_random_seed.get():
            self.app.var_seed.set(str(random.randint(1, 9999)))
            self.e_seed.configure(state='disabled')
        else:
            self.e_seed.configure(state='normal')

    def _setup_traces(self):
        self.app.var_outdir.trace_add("write", lambda *a: self._check_path(self.app.var_outdir))
        self.app.var_yaml_dir.trace_add("write", lambda *a: self._check_path(self.app.var_yaml_dir))
        self.app.var_prefix.trace_add("write", self._update_preview)
        self._check_path(self.app.var_outdir)
        self._check_path(self.app.var_yaml_dir)
        self._update_preview()

    def _validate_int(self, P):
        if P == "" or P == "-": return True
        return P.isdigit() or (P.startswith("-") and P[1:].isdigit())

    def _check_path(self, var):
        entry = self.path_entries.get(str(var))
        if not entry: return
        path = var.get()
        if path and Path(path).is_dir():
            entry.configure(foreground="black")
        else:
            entry.configure(foreground="red")

    def _update_preview(self, *args):
        text = self.app.var_prefix.get()
        children = self.var_table.get_children()
        if not children:
            self.lbl_preview.config(text=f"Preview (no variables): {text}")
            return
        try:
            item = self.var_table.item(children[0])
            name, tags_str, _ = item['values']
            tags_list = parse_list_safe(tags_str, [])
            first_tag = tags_list[0] if tags_list else "?"
            simulated = text.replace(f"{{{name}}}", str(first_tag))
            suffix = " (varying others...)" if len(children) > 1 else ""
            self.lbl_preview.config(text=f"Example: {simulated}{suffix}")
        except Exception:
            self.lbl_preview.config(text="Error generating preview")

    def _pick_outdir(self):
        cur = self.app.var_outdir.get()
        path = self._ask_directory(cur, "Select Output Directory")
        if path: self.app.var_outdir.set(path)

    def _pick_yamldir(self):
        cur = self.app.var_yaml_dir.get()
        path = self._ask_directory(cur, "Select YAML Save Folder")
        if path: self.app.var_yaml_dir.set(path)

    def _ask_directory(self, start_path, title):
        start = start_path if start_path and Path(start_path).is_dir() else Path.cwd()
        path = filedialog.askdirectory(initialdir=start, title=title)
        if path: return Path(path).as_posix()
        return None

    def _var_add(self):
        iid = self.var_table.insert("", "end", values=("new_var", "[]", "[]"))
        self.var_table.selection_set(iid)
        self._open_editor_for_item(iid)

    def _var_edit(self):
        sel = self.var_table.selection()
        if not sel: return
        self._open_editor_for_item(sel[0])

    def _var_remove(self):
        for iid in self.var_table.selection(): self.var_table.delete(iid)
        self._update_preview()

    def _open_editor_for_item(self, iid):
        vals = self.var_table.item(iid, "values")
        def save_callback(new_name, tags, values):
            self.var_table.item(iid, values=(new_name, str(tags), str(values)))
            self._update_preview()
        VariableEditor(self.frame, vals[0], vals[1], vals[2], save_callback)