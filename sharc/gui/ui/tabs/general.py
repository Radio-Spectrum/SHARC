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
import re
from typing import Any, Dict, List, Tuple

# --- Project Imports ---
from utils import add_row_three
from ui.tabs.assets.general_tab.variable_editor import VariableEditor
from ui.tabs.assets.general_tab.general_tools import parse_list_safe
from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence


# =============================================================================
# Helper Functions
# =============================================================================

def _sanitize_for_yaml(obj: Any) -> Any:
    """
    Recursively sanitize objects for yaml.safe_dump.
    Strips Python-specific objects (like tuples or Paths) to prevent YAML serialization errors
    or ugly Python tags in the output file.
    """
    if isinstance(obj, tuple):
        return [_sanitize_for_yaml(x) for x in obj]
    if isinstance(obj, list):
        return [_sanitize_for_yaml(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_for_yaml(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _num_or_str(s: Any) -> Any:
    """
    Robust converter:
    - Preserves None
    - Converts "true"/"false" to bool
    - Converts int-like strings to int
    - Converts float-like strings to float
    - Otherwise returns original string
    """
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

    if "." not in s_str and "e" not in low:
        try:
            return int(s_str)
        except Exception:
            pass

    try:
        return float(s_str)
    except Exception:
        return s_str


def _sanitize_recursive(data: Any) -> Any:
    """Recursively converts stringified numbers/booleans inside dicts/lists."""
    if isinstance(data, dict):
        return {k: _sanitize_recursive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_recursive(v) for v in data]
    return _num_or_str(data)


def load_param_file(filepath: str) -> Dict[str, Any]:
    """Safely loads a JSON or YAML file and sanitizes types."""
    path = Path(filepath)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix.lower() == ".json":
                data = json.load(f)
            elif path.suffix.lower() in [".yaml", ".yml"]:
                data = yaml.safe_load(f)
            else:
                return {}
        return _sanitize_recursive(data) if data else {}
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}


def deep_merge(base_dict: Dict[str, Any], new_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges new_dict into base_dict (in-place) and returns base_dict."""
    for key, value in new_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


def _sanitize_filename(name: str, max_len: int = 140) -> str:
    """
    Makes filenames safe across OSes:
    - replaces path separators and invalid characters
    - collapses whitespace
    - truncates
    """
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        name = "config"
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name


def _normalize_topology_type(t: str) -> str:
    """
    Normalizes topology type values that may appear in different UI styles.
    Example: "macro_countries" -> "Macro_countries"
    """
    if not t:
        return "HOTSPOT"
    raw = str(t).strip()

    official = {"HOTSPOT", "MACROCELL", "SINGLE_BS", "Macro_countries"}
    if raw in official:
        return raw

    low = raw.lower()
    if low in {"macro_countries", "macro countries", "macro-countries"}:
        return "Macro_countries"
    if low in {"hotspot"}:
        return "HOTSPOT"
    if low in {"macrocell"}:
        return "MACROCELL"
    if low in {"single_bs", "single bs", "single-bs"}:
        return "SINGLE_BS"
    return raw


def _consolidate_param_p452(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avoids duplicated keys for P.452 parameters.
    """
    if not isinstance(block, dict):
        return block

    has_p452 = "p452" in block and isinstance(block["p452"], dict)
    has_param = "param_p452" in block and isinstance(block["param_p452"], dict)

    if has_p452 and has_param:
        merged = copy.deepcopy(block["param_p452"])
        deep_merge(merged, block["p452"])
        block["param_p452"] = merged
        del block["p452"]
        return block

    if has_p452 and not has_param:
        block["param_p452"] = block["p452"]
        del block["p452"]
        return block

    return block


def _yaml_safe_dump(data: Dict[str, Any], out_path: Path) -> None:
    """
    Sanitizes data and writes YAML with stable formatting.
    Ensures no Python tags (e.g., !!python/tuple) leak into the output.
    """
    sanitized_data = _sanitize_for_yaml(data)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            sanitized_data,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )


# =============================================================================
# General Tab
# =============================================================================

class GeneralTab:
    """
    Manages the 'General' tab for simulation parameters.
    """

    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        self.var_use_random_seed = tk.BooleanVar(value=False)
        self.path_entries = {}
        self.data_collectors = []

        self._build_top_toolbar()
        self._build_main_form()
        self._setup_traces()

    # =========================================================================
    # Registry
    # =========================================================================

    def register_data_collector(self, collector_func):
        self.data_collectors.append(collector_func)

    # =========================================================================
    # UI
    # =========================================================================

    def _build_top_toolbar(self):
        toolbar_frame = ttk.Frame(self.frame)
        toolbar_frame.pack(side="top", fill="x", padx=5, pady=(10, 10))

        self.btn_files = ttk.Menubutton(
            toolbar_frame, text="📁 File Operations (Presets)", bootstyle="primary", width=25
        )
        self.btn_files.pack(side="left")

        self.menu_files = tk.Menu(self.btn_files, tearoff=0)
        self.btn_files.configure(menu=self.menu_files)

        self.menu_files.add_command(
            label="💾 Save Current Preset (.json)", command=self.save_config)
        self.menu_files.add_command(
            label="📂 Load Preset (.json)", command=self.load_config)

        ttk.Separator(self.frame, orient="horizontal").pack(
            fill="x", pady=(0, 15))

    def _build_main_form(self):
        frm = ttk.Labelframe(self.frame, text="General Parameters", padding=10)
        frm.pack(fill="x", pady=(0, 6))

        f_seed_cont = ttk.Frame(frm)
        self.e_seed = ttk.Entry(
            f_seed_cont, textvariable=self.app.var_seed, width=8)
        self.e_seed.pack(side="left")

        cb_rnd = ttk.Checkbutton(
            f_seed_cont,
            text="Random",
            variable=self.var_use_random_seed,
            command=self._toggle_random_seed,
            bootstyle="round-toggle",
        )
        cb_rnd.pack(side="left", padx=(10, 0))

        e_snaps = ttk.Entry(frm, textvariable=self.app.var_snaps, width=12)

        cb_sys = ttk.Combobox(
            frm,
            textvariable=self.app.var_system,
            values=["SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"],
            state="readonly",
            width=26,
        )

        add_row_three(frm, 0, [("Seed", f_seed_cont),
                      ("Num Snapshots", e_snaps), ("System Type", cb_sys)])

        self._build_path_row(frm, 1, "Output Dir",
                             self.app.var_outdir, self._pick_outdir)
        self._build_path_row(frm, 2, "YAML Dir",
                             self.app.var_yaml_dir, self._pick_yamldir)

        e_prefix = ttk.Entry(frm, textvariable=self.app.var_prefix)
        cb_link = ttk.Combobox(
            frm,
            textvariable=self.app.var_imt_link,
            values=["DOWNLINK", "UPLINK"],
            state="readonly",
            width=18,
        )
        cb_overwrite = ttk.Checkbutton(
            frm, variable=self.app.var_overwrite, text="Overwrite", bootstyle="round-toggle")

        add_row_three(frm, 3, [("Filename Prefix", e_prefix),
                      ("IMT Link Direction", cb_link), ("Output Options", cb_overwrite)])

        self.lbl_preview = ttk.Label(
            frm, text="Preview: ...", foreground="gray", font=("Segoe UI", 8, "italic"))
        self.lbl_preview.grid(row=4, column=0, columnspan=6,
                              sticky="w", padx=5, pady=(0, 5))

        cb_adj = ttk.Checkbutton(
            frm, variable=self.app.var_adj, text="Active", bootstyle="square-toggle")
        cb_coch = ttk.Checkbutton(
            frm, variable=self.app.var_coch, text="Active", bootstyle="square-toggle")
        add_row_three(frm, 5, [("Enable Adj Channel", cb_adj),
                      ("Enable Co-Channel", cb_coch), ("", ttk.Label(frm, text=""))])

        self._build_var_table_ui()

    def _build_path_row(self, parent, row_idx, label_text, var, cmd):
        row = ttk.Frame(parent)
        row.grid(row=row_idx, column=0, columnspan=6, sticky="we", pady=5)
        ttk.Label(row, text=label_text).pack(side="left")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(row, text="Browse", command=cmd,
                   bootstyle="secondary-outline").pack(side="left")
        self.path_entries[str(var)] = entry

    def _build_var_table_ui(self):
        box = ttk.Labelframe(
            self.frame, text="Combination Variables (Tags -> YAML Values)", padding=10)
        box.pack(fill="both", expand=True, pady=(15, 0))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 5))

        ttk.Button(toolbar, text="+ Add Variable", command=self._var_add,
                   bootstyle="info-outline").pack(side="left")
        ttk.Button(toolbar, text="✎ Edit", command=self._var_edit,
                   bootstyle="secondary-outline").pack(side="left", padx=6)
        ttk.Button(toolbar, text="🗑 Remove", command=self._var_remove,
                   bootstyle="danger-outline").pack(side="left", padx=6)

        self.var_table = ttk.Treeview(
            box,
            columns=("var", "tags", "values"),
            show="headings",
            height=6,
            bootstyle="info",
        )
        self.var_table.heading("var", text="Variable Name")
        self.var_table.heading("tags", text="Replacement Tags")
        self.var_table.heading("values", text="Values List")
        self.var_table.column("var", width=150)
        self.var_table.column("tags", width=250)
        self.var_table.column("values", width=450)
        self.var_table.pack(fill="both", expand=True, pady=(4, 6))
        self.var_table.bind("<Double-1>", lambda e: self._var_edit())

        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(15, 0))

        self.btn_actions = ttk.Menubutton(
            row_gen, text="⚡ ACTIONS / GENERATION", bootstyle="success", width=30)
        self.btn_actions.pack(side="left")

        self.menu_actions = tk.Menu(self.btn_actions, tearoff=0)
        self.btn_actions.configure(menu=self.menu_actions)

        self.menu_actions.add_command(
            label="🚀 Batch Generate (from Table Variables)", command=self.save_yaml_to_yamldir)

    # =========================================================================
    # Core generation
    # =========================================================================

    def _collect_app_globals(self) -> Dict[str, Any]:
        data = {}
        for key in dir(self.app):
            if key.startswith("_"):
                continue
            val = getattr(self.app, key)
            if isinstance(val, (tk.StringVar, tk.DoubleVar, tk.IntVar, tk.BooleanVar)):
                try:
                    data[key] = val.get()
                except Exception:
                    pass
        return data

    def save_yaml_to_yamldir(self):
        self._internal_save_logic(use_combinations=True)

    def save_single_yaml_snapshot(self):
        self._internal_save_logic(use_combinations=False)

    def _recursive_inject(self, obj: Any, mapping: Dict[str, Any]) -> Any:
        if isinstance(obj, dict):
            return {k: self._recursive_inject(v, mapping) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._recursive_inject(v, mapping) for v in obj]
        if isinstance(obj, str):
            new_val = obj
            replaced = False
            for tag, val in mapping.items():
                placeholder = f"{{{tag}}}"
                if placeholder in new_val:
                    if new_val == placeholder:
                        return val
                    new_val = new_val.replace(placeholder, str(val))
                    replaced = True
            return _num_or_str(new_val) if replaced else new_val
        return obj

    def _internal_save_logic(self, use_combinations: bool = True):
        if use_combinations:
            table_children = self.var_table.get_children()
            if not table_children:
                messagebox.showwarning(
                    "Generation Aborted", "The variable table is empty.")
                return

        sys_type = self.app.var_system.get()

        if sys_type == "SINGLE_EARTH_STATION":
            sys_key = "single_earth_station"
        elif sys_type == "SINGLE_SPACE_STATION":
            sys_key = "single_space_station"
        else:
            sys_key = sys_type.lower().strip() or "system"

        general_conf = {
            "seed": self.app.var_seed.get() if not self.var_use_random_seed.get() else "RANDOM",
            "num_snapshots": self.app.var_snaps.get(),
            "overwrite_output": bool(self.app.var_overwrite.get()),
            "output_dir": str(self.app.var_outdir.get()),
            "output_dir_prefix": str(self.app.var_prefix.get()),
            "system": sys_type,
            "imt_link": str(self.app.var_imt_link.get()),
            "enable_adjacent_channel": bool(self.app.var_adj.get()),
            "enable_cochannel": bool(self.app.var_coch.get()),
        }

        app_globals = self._collect_app_globals()
        combined_flat = app_globals.copy()
        for collector in self.data_collectors:
            try:
                flat_data = collector()
                if flat_data:
                    combined_flat.update(flat_data)
            except Exception as e:
                print(f"Warning: Collector error: {e}")

        live_imt = self._build_imt_hierarchy(combined_flat)
        live_sys = self._build_system_hierarchy(combined_flat, sys_type)

        combinations: List[List[Tuple[str, Any, Any]]] = [[]]
        if use_combinations:
            vars_processed = []
            for child in self.var_table.get_children():
                row = self.var_table.item(child)["values"]
                tags = parse_list_safe(row[1], [])
                vals = parse_list_safe(row[2], [])
                if len(tags) == len(vals) and len(tags) > 0:
                    vars_processed.append([(row[0], t, v)
                                          for t, v in zip(tags, vals)])
            if vars_processed:
                combinations = list(itertools.product(*vars_processed))

        save_dir = Path(self.app.var_yaml_dir.get())
        save_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        prefix_tmpl = str(self.app.var_prefix.get())

        for combo in combinations:
            final_structure = {
                "general": copy.deepcopy(general_conf),
                "imt": copy.deepcopy(live_imt),
                sys_key: copy.deepcopy(live_sys),
            }

            fname_vars: Dict[str, Any] = {}
            mapping_vars: Dict[str, Any] = {}

            for var_name, var_tag, var_val in combo:
                fname_vars[var_name] = var_tag
                mapping_vars[var_name] = var_val

                if (
                    isinstance(var_val, str)
                    and var_val.lower().endswith((".json", ".yaml", ".yml"))
                    and Path(var_val).exists()
                ):
                    external_data = load_param_file(var_val)

                    config_type = str(external_data.get(
                        "config_type", "")).upper()
                    if "config_type" in external_data:
                        del external_data["config_type"]

                    if config_type == "IMT":
                        self._apply_flat_to_app(external_data)
                        combined_flat2 = self._collect_app_globals()
                        final_structure["imt"] = self._build_imt_hierarchy(
                            combined_flat2)

                    elif config_type in {"SSS", "SES", "SYSTEM", "SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"}:
                        SESPersistence.apply_config(self.app, external_data)
                        combined_flat2 = self._collect_app_globals()
                        final_structure[sys_key] = self._build_system_hierarchy(
                            combined_flat2, sys_type)

                    else:
                        if self._is_imt_data(external_data):
                            deep_merge(
                                final_structure["imt"], self._build_imt_hierarchy(external_data))
                        elif self._is_hierarchical_sys_data(external_data):
                            deep_merge(final_structure[sys_key], external_data)
                        elif self._is_system_data(external_data):
                            deep_merge(final_structure[sys_key], self._build_system_hierarchy(
                                external_data, sys_type))
                        else:
                            deep_merge(final_structure, external_data)

            final_structure = self._recursive_inject(
                final_structure, mapping_vars)

            try:
                topo = final_structure.get("imt", {}).get("topology", {})
                if isinstance(topo, dict) and "type" in topo:
                    topo["type"] = _normalize_topology_type(topo["type"])
            except Exception:
                pass

            if isinstance(final_structure.get(sys_key), dict):
                final_structure[sys_key] = _consolidate_param_p452(
                    final_structure[sys_key])

            try:
                if use_combinations and fname_vars:
                    base = prefix_tmpl.format(**fname_vars)
                else:
                    base = prefix_tmpl.replace("{", "").replace("}", "")
                if not use_combinations:
                    base = f"{base}_snapshot"
                base = _sanitize_filename(base)
                final_structure["general"]["output_dir_prefix"] = base
                fname = base if base.endswith(".yaml") else f"{base}.yaml"
            except KeyError as e:
                messagebox.showerror("Error", f"Prefix requires variable {e}")
                return

            if final_structure["general"].get("seed") == "RANDOM":
                final_structure["general"]["seed"] = random.randint(1, 999999)
            else:
                try:
                    final_structure["general"]["seed"] = int(
                        final_structure["general"]["seed"])
                except Exception:
                    pass

            try:
                final_structure["general"]["num_snapshots"] = int(
                    final_structure["general"]["num_snapshots"])
            except Exception:
                pass

            out_path = save_dir / fname
            _yaml_safe_dump(final_structure, out_path)
            count += 1

        messagebox.showinfo(
            "Success", f"Generated {count} configuration files in {save_dir}")

    # =========================================================================
    # Routing helpers
    # =========================================================================

    def _apply_flat_to_app(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            if hasattr(self.app, k):
                var = getattr(self.app, k)
                if hasattr(var, "set"):
                    try:
                        var.set(v)
                    except Exception:
                        pass
                else:
                    setattr(self.app, k, v)

    def _is_imt_data(self, data: Dict[str, Any]) -> bool:
        markers = ["imt_freq", "bs_power", "ue_height", "topo_type"]
        return any(k in data for k in markers)

    def _is_system_data(self, data: Dict[str, Any]) -> bool:
        markers = ["v_freq", "se_frequency", "v_txpsd", "v_alt", "se_height"]
        return any(k in data for k in markers)

    def _is_hierarchical_sys_data(self, data: Dict[str, Any]) -> bool:
        unique_sys_keys = ["p452", "param_p619",
                           "itu_r_s_672", "itu_r_f_1245_fs"]
        if any(k in data for k in unique_sys_keys):
            return True
        if "geometry" in data and "antenna" in data:
            return True
        return False

    # =========================================================================
    # Hierarchy builders
    # =========================================================================

    def _build_imt_hierarchy(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        n = _num_or_str
        def g(k, d=None): return flat.get(k, d)

        topo_type = _normalize_topology_type(str(g("topo_type", "HOTSPOT")))
        topology: Dict[str, Any] = {
            "central_latitude": n(g("topo_c_lat", -15.79)),
            "central_longitude": n(g("topo_c_lon", -47.88)),
            "central_altitude": n(g("topo_c_alt", 1000.0)),
            "type": topo_type,
        }

        if topo_type == "Macro_countries":
            raw_txt = str(g("topo_countries", ""))
            country_names = [c.strip()
                             for c in raw_txt.splitlines() if c.strip()]
            enc_ui = str(g("topo_raster_enc", "")).strip()
            pop_raster = str(g("path_raster", "")).strip(
            ) if enc_ui != "Uniforme" else None

            topology["macrocell_countries"] = {
                "country_names": country_names,
                "num_bs_total": int(n(g("topo_num_bs", 0))),
                "cell_radius": n(g("topo_cell_radius", 50.0)),
                "rng_seed": int(n(g("topo_rng", 0))),
                "dist_type": str(g("topo_dist_type", "UNIFORM")),
                "countries_shapefile": str(g("path_shp", "")).strip() or None,
                "population_raster": pop_raster,
            }
            if enc_ui != "Uniforme":
                topology["macrocell_countries"]["raster_encoding"] = "indexed"

        elif topo_type == "MACROCELL":
            topology["macrocell"] = {
                "intersite_distance": n(g("macro_intersite", 500.0)),
                "wrap_around": bool(g("macro_wrap", False)),
                "num_clusters": int(n(g("macro_clusters", 1))),
            }

        elif topo_type == "HOTSPOT":
            topology["hotspot"] = {
                "intersite_distance": n(g("hotspot_intersite", 500.0)),
                "wrap_around": bool(g("hotspot_wrap", False)),
                "num_clusters": int(n(g("hotspot_clusters", 1))),
                "num_hotspots_per_cell": int(n(g("hotspot_num_per_cell", 3))),
                "max_dist_hotspot_ue": n(g("hotspot_max_dist_ue", 100.0)),
                "min_dist_bs_hotspot": n(g("hotspot_min_dist_bs", 50.0)),
            }

        elif topo_type == "SINGLE_BS":
            az_text = str(g("sbs_azimuth", "")).strip()
            try:
                sbs_az = [float(x.strip())
                          for x in az_text.split(",")] if az_text else None
            except Exception:
                sbs_az = az_text

            topology["single_bs"] = {
                "intersite_distance": n(g("sbs_intersite", 500.0)),
                "cell_radius": n(g("sbs_cell_radius", 1.0)),
                "num_clusters": int(n(g("sbs_clusters", 1))),
                "azimuth": sbs_az,
            }

        bs_array = {
            "normalization": bool(g("bs_norm", False)),
            "element_pattern": str(g("bs_elem_pat", "M2101")),
            "minimum_array_gain": n(g("bs_min_arr_gain", 0.0)),
            "horizontal_beamsteering_range": [n(g("bs_h_steer_min", -60.0)), n(g("bs_h_steer_max", 60.0))],
            "vertical_beamsteering_range": [n(g("bs_v_steer_min", -15.0)), n(g("bs_v_steer_max", 15.0))],
            "downtilt": n(g("bs_downtilt", 0.0)),
            "element_max_g": n(g("bs_elem_max_g", 5.0)),
            "element_phi_3db": n(g("bs_phi3", 65.0)),
            "element_theta_3db": n(g("bs_theta3", 65.0)),
            "n_rows": n(g("bs_rows", 8.0)),
            "n_columns": n(g("bs_cols", 8.0)),
            "element_horiz_spacing": n(g("bs_elem_hs", 0.5)),
            "element_vert_spacing": n(g("bs_elem_vs", 0.5)),
            "element_am": n(g("bs_elem_am", 30.0)),
            "element_sla_v": n(g("bs_elem_sla_v", 30.0)),
            "multiplication_factor": n(g("bs_mult", 1.0)),
            "subarray": {
                "is_enabled": bool(g("bs_sub_enabled", False)),
                "n_rows": n(g("bs_sub_rows", 2.0)),
                "element_vert_spacing": n(g("bs_sub_evspace", 0.8)),
                "eletrical_downtilt": n(g("bs_sub_e_downtilt", 0.0)),
            },
        }

        ue_array = {
            "normalization": bool(g("ue_norm", False)),
            "element_pattern": str(g("ue_elem_pat", "FIXED")),
            "minimum_array_gain": n(g("ue_min_arr_gain", -10.0)),
            "element_max_g": n(g("ue_elem_max_g", 0.0)),
            "element_phi_3db": n(g("ue_phi3", 90.0)),
            "element_theta_3db": n(g("ue_theta3", 90.0)),
            "n_rows": n(g("ue_rows", 1.0)),
            "n_columns": n(g("ue_cols", 1.0)),
            "element_am": n(g("ue_elem_am", 20.0)),
            "element_sla_v": n(g("ue_elem_sla_v", 20.0)),
            "multiplication_factor": n(g("ue_mult", 1.0)),
        }

        if bool(g("ue_sub_enabled", False)):
            ue_array["subarray"] = {
                "is_enabled": True,
                "n_rows": n(g("ue_sub_rows", 1.0)),
                "element_vert_spacing": n(g("ue_sub_evspace", 0.5)),
                "eletrical_downtilt": n(g("ue_sub_e_downtilt", 0.0)),
            }

        ue_block = {
            "k": int(n(g("ue_k", 1))),
            "k_m": int(n(g("ue_km", 1))),
            "indoor_percent": n(g("ue_indoor", 80.0)),
            "distribution_type": str(g("ue_dist_type", "UNIFORM")),
            "tx_power_control": bool(g("ue_tx_power_ctrl", True)),
            "p_o_pusch": n(g("ue_p_o_pusch", -90.0)),
            "alpha": n(g("ue_alpha", 0.8)),
            "p_cmax": n(g("ue_p_cmax", 23.0)),
            "power_dynamic_range": n(g("ue_p_dyn", 20.0)),
            "height": n(g("ue_height", 1.5)),
            "noise_figure": n(g("ue_nf", 9.0)),
            "ohmic_loss": n(g("ue_ohmic", 0.0)),
            "body_loss": n(g("ue_body_loss", 0.0)),
            "antenna": {"array": ue_array},
        }

        if str(g("ue_dist_type", "")).upper() == "ANGLE_AND_DISTANCE":
            ue_block["distribution_distance"] = g("ue_dist_distance", "")
            ue_block["distribution_azimuth"] = g("ue_dist_azimuth", "")

        imt = {
            "minimum_separation_distance_bs_ue": n(g("imt_min_sep", 10.0)),
            "interfered_with": bool(g("imt_interfered", False)),
            "frequency": n(g("imt_freq", 3500.0)),
            "bandwidth": n(g("imt_bw", 100.0)),
            "rb_bandwidth": n(g("imt_rb_bw", 0.18)),
            "spectral_mask": str(g("imt_spec_mask", "IMT-2020")),
            "spurious_emissions": n(g("imt_spurious", -13.0)),
            "adjacent_antenna_model": str(g("imt_adj_ant_model", "ITU-R F.1336")),
            "guard_band_ratio": n(g("imt_guard_ratio", 0.0)),
            "topology": topology,
            "bs": {
                "load_probability": n(g("bs_load_prob", 1.0)),
                "conducted_power": n(g("bs_power", 46.0)),
                "height": n(g("bs_height", 30.0)),
                "noise_figure": n(g("bs_nf", 5.0)),
                "ohmic_loss": n(g("bs_ohmic", 2.0)),
                "antenna": {"array": bs_array},
            },
            "ue": ue_block,
            "uplink": {
                "attenuation_factor": n(g("ul_att", 0.0)),
                "sinr_min": n(g("ul_sinr_min", -10.0)),
                "sinr_max": n(g("ul_sinr_max", 30.0)),
            },
            "downlink": {
                "attenuation_factor": n(g("dl_att", 0.0)),
                "sinr_min": n(g("dl_sinr_min", -10.0)),
                "sinr_max": n(g("dl_sinr_max", 30.0)),
            },
            "channel_model": str(g("ch_model", "Uma")),
            "shadowing": bool(g("shadowing", True)),
        }
        return imt

    def _build_system_hierarchy(self, flat: Dict[str, Any], sys_type: str) -> Dict[str, Any]:
        n = _num_or_str
        def g(k, d=None): return flat.get(k, d)

        if sys_type == "SINGLE_SPACE_STATION":
            pat = str(g("v_ant_pattern", "")).strip()

            sys = {
                "frequency": n(g("v_freq", 3500.0)),
                "bandwidth": n(g("v_bw", 100.0)),
                "tx_power_density": n(g("v_txpsd", -30.0)),
                "polarization_loss": n(g("v_pol_loss", 3.0)),
                "noise_temperature": n(g("v_tnoise", 290.0)),
                "channel_model": str(g("v_ch_model", "FSPL")),
                "is_global_coordinate_system": bool(g("ss_is_global_cs", False)),
                "season": str(g("v_season", "SUMMER")),
                "param_p619": {
                    "mean_clutter_height": str(g("v_p619_clutter", "Mid")),
                    "below_rooftop": n(g("v_p619_below_rooftop", 0.0)),
                },
                "geometry": {
                    "altitude": n(g("v_alt", 35786000.0)),
                    "location": {
                        "type": "FIXED",
                        "fixed": {
                            "lat_deg": n(g("v_fix_lat", 0.0)),
                            "long_deg": n(g("v_fix_lon", -47.0)),
                        },
                    },
                    "es_altitude": n(g("v_es_alt", 0.0)),
                    "es_lat_deg": n(g("v_es_lat", -15.79)),
                    "es_long_deg": n(g("v_es_lon", -47.88)),
                    "azimuth": {"type": str(g("v_az_type", "POINTING_AT_IMT"))},
                    "elevation": {"type": str(g("v_el_type", "POINTING_AT_IMT"))},
                },
                "antenna": {
                    "pattern": pat,
                    "gain": n(g("v_ant_gain", 30.0)),
                },
            }

            if pat == "ITU-R S.672":
                sys["antenna"]["itu_r_s_672"] = {
                    "antenna_3_dB": n(g("v_s672_3db", 2.0)),
                    "antenna_l_s": n(g("v_s672_ls", -20.0)),
                }

            return sys

        if sys_type == "SINGLE_EARTH_STATION":
            pat = str(g("se_ant_pattern", "")).strip()
            ch_model = str(g("se_channel_model", "FSPL")).strip()

            ant: Dict[str, Any] = {
                "pattern": pat,
                "gain": n(g("se_ant_gain", 30.0)),
            }

            if pat in {
                "ITU-R F.699",
                "ITU-R S.465",
                "ITU-R S.580",
                "ITU-R S.1855",
                "ITU-R Reg. RR. Appendice 7 Annex 3",
            }:
                key_map = {
                    "ITU-R F.699": "itu_r_f_699",
                    "ITU-R S.465": "itu_r_s_465",
                    "ITU-R S.580": "itu_r_s_580",
                    "ITU-R S.1855": "itu_r_s_1855",
                    "ITU-R Reg. RR. Appendice 7 Annex 3": "itu_reg_rr_a7_3",
                }
                ant[key_map[pat]] = {"diameter": n(g("se_ant_diameter", 1.2))}

            elif pat == "MODIFIED ITU-R S.465":
                ant["itu_r_s_465_modified"] = {
                    "envelope_gain": n(g("se_ant_envelope_gain", 0.0))}

            elif pat == "ITU-R S.672":
                ant["itu_r_s_672"] = {
                    "antenna_3_dB": n(g("se_ant_3db", 2.0)),
                    "antenna_l_s": n(g("se_ant_l_s", -20.0)),
                }

            elif pat == "ITU-R F.1245_fs":
                ant["itu_r_f_1245_fs"] = {
                    "gain": n(g("se_ant_f1245_gain", 30.0)),
                    "diameter": n(g("se_ant_f1245_diameter", 1.2)),
                    "frequency": n(g("se_ant_f1245_frequency", 3.8)),
                }

            geo: Dict[str, Any] = {
                "height": n(g("se_height", 10.0)),
                "location": {"type": str(g("se_loc_type", "FIXED")).strip()},
                "azimuth": {"type": str(g("se_az_type", "FIXED")).strip()},
                "elevation": {"type": str(g("se_el_type", "FIXED")).strip()},
            }

            loc_t = geo["location"]["type"]
            if loc_t == "FIXED":
                geo["location"]["fixed"] = {
                    "x": n(g("se_loc_fixed_x", 0.0)), "y": n(g("se_loc_fixed_y", 0.0))}
            elif loc_t == "CELL":
                geo["location"]["cell"] = {"min_dist_to_bs": n(
                    g("se_loc_cell_min_dist_to_bs", 100.0))}
            elif loc_t == "NETWORK":
                geo["location"]["network"] = {"min_dist_to_bs": n(
                    g("se_loc_network_min_dist_to_bs", 500.0))}
            elif loc_t == "UNIFORM_DIST":
                geo["location"]["uniform_dist"] = {
                    "min_dist_to_center": n(g("se_loc_ud_min_dist_to_center", 0.0)),
                    "max_dist_to_center": n(g("se_loc_ud_max_dist_to_center", 1000.0)),
                }

            az_t = geo["azimuth"]["type"]
            if az_t == "FIXED":
                geo["azimuth"]["fixed"] = n(g("se_az_fixed", 0.0))
            elif az_t == "UNIFORM_DIST":
                geo["azimuth"]["uniform_dist"] = {
                    "min": n(g("se_az_ud_min", 0.0)), "max": n(g("se_az_ud_max", 360.0))}

            el_t = geo["elevation"]["type"]
            if el_t == "FIXED":
                geo["elevation"]["fixed"] = n(g("se_el_fixed", 0.0))
            elif el_t == "UNIFORM_DIST":
                geo["elevation"]["uniform_dist"] = {
                    "min": n(g("se_el_ud_min", 0.0)), "max": n(g("se_el_ud_max", 90.0))}

            se: Dict[str, Any] = {
                "frequency": n(g("se_frequency", 3800.0)),
                "bandwidth": n(g("se_bandwidth", 100.0)),
                "noise_temperature": n(g("se_noise_temperature", 290.0)),
                "adjacent_ch_reception": str(g("se_adjacent_ch_reception", "OFF")),
                "adjacent_ch_selectivity": n(g("se_adjacent_ch_selectivity", 0.0)),
                "adjacent_ch_emissions": str(g("se_adjacent_ch_emissions", "OFF")),
                "adjacent_ch_leak_ratio": n(g("se_adjacent_ch_leak_ratio", 0.0)),
                "spectral_mask": str(g("se_spectral_mask", "")),
                "spurious_emissions": n(g("se_spurious_emissions", -60.0)),
                "tx_power_density": n(g("se_tx_power_density", -50.0)),
                "polarization_loss": n(g("se_polarization_loss", "")),
                "channel_model": ch_model,
                "geometry": geo,
                "antenna": ant,
            }

            if se.get("polarization_loss") in ("", None):
                del se["polarization_loss"]

            if ch_model == "P452":
                p452 = {
                    "atmospheric_pressure": n(g("p452_atmospheric_pressure", 1013.25)),
                    "air_temperature": n(g("p452_air_temperature", 293.15)),
                    "percentage_p": n(g("p452_percentage_p", 20.0)),
                    "N0": n(g("p452_N0", 315.0)),
                    "delta_N": n(g("p452_delta_N", 45.0)),
                    "polarization": str(g("p452_polarization", "")),
                    "Dct": n(g("p452_Dct", 500.0)),
                    "Dcr": n(g("p452_Dcr", 500.0)),
                    "Hte": n(g("p452_Hte", 18.0)),
                    "Hre": n(g("p452_Hre", 10.0)),
                    "clutter_loss": bool(g("p452_clutter_loss", False)),
                    "tx_lat": n(g("p452_tx_lat", 45.0)),
                    "rx_lat": n(g("p452_rx_lat", 45.0)),
                    "is_terrain": bool(g("p452_is_terrain", False)),
                }

                if p452["clutter_loss"]:
                    p452["clutter_type"] = str(
                        g("p452_clutter_type", "one_end"))

                se["param_p452"] = p452

            return se

        return {}

    # =========================================================================
    # Misc UI callbacks
    # =========================================================================

    def _toggle_random_seed(self):
        if self.var_use_random_seed.get():
            self.app.var_seed.set(str(random.randint(1, 9999)))
            self.e_seed.configure(state="disabled")
        else:
            self.e_seed.configure(state="normal")

    def _setup_traces(self):
        self.app.var_outdir.trace_add(
            "write", lambda *a: self._check_path(self.app.var_outdir))
        self.app.var_yaml_dir.trace_add(
            "write", lambda *a: self._check_path(self.app.var_yaml_dir))
        self.app.var_prefix.trace_add("write", self._update_preview)

        self._check_path(self.app.var_outdir)
        self._check_path(self.app.var_yaml_dir)
        self._update_preview()

    def _check_path(self, var):
        entry = self.path_entries.get(str(var))
        if not entry:
            return
        path = var.get()
        entry.configure(foreground="black" if path and Path(
            path).is_dir() else "red")

    def _update_preview(self, *args):
        text = str(self.app.var_prefix.get())
        children = self.var_table.get_children()
        if not children:
            self.lbl_preview.config(text=f"Preview (no variables): {text}")
            return
        try:
            item = self.var_table.item(children[0])
            name, tags_str, _ = item["values"]
            tags_list = parse_list_safe(tags_str, [])
            first_tag = tags_list[0] if tags_list else "?"
            simulated = text.replace(f"{{{name}}}", str(first_tag))
            self.lbl_preview.config(text=f"Example: {simulated}")
        except Exception:
            self.lbl_preview.config(text="Error generating preview")

    def _pick_outdir(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.app.var_outdir.set(path)

    def _pick_yamldir(self):
        path = filedialog.askdirectory(title="Select YAML Save Folder")
        if path:
            self.app.var_yaml_dir.set(path)

    # =========================================================================
    # Preset save/load
    # =========================================================================

    def save_config(self):
        table_data = [self.var_table.item(child)["values"]
                      for child in self.var_table.get_children()]
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
            "variables_table": table_data,
        }
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")])
        if fpath:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

    def load_config(self):
        fpath = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not fpath:
            return
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.app.var_seed.set(data.get("seed", "123"))
        self.var_use_random_seed.set(data.get("use_random_seed", False))
        self._toggle_random_seed()

        self.app.var_snaps.set(data.get("snaps", "100"))
        self.app.var_system.set(data.get("system", "SINGLE_EARTH_STATION"))
        self.app.var_outdir.set(data.get("output_dir", ""))
        self.app.var_yaml_dir.set(data.get("yaml_dir", ""))
        self.app.var_prefix.set(data.get("prefix", "sim_{var}"))
        self.app.var_imt_link.set(data.get("imt_link", "DOWNLINK"))
        self.app.var_overwrite.set(data.get("overwrite", False))
        self.app.var_adj.set(data.get("adj_channel", False))
        self.app.var_coch.set(data.get("co_channel", False))

        for item in self.var_table.get_children():
            self.var_table.delete(item)
        for row in data.get("variables_table", []):
            self.var_table.insert("", "end", values=row)

        self._update_preview()

    # =========================================================================
    # Variable editor helpers
    # =========================================================================

    def _var_add(self):
        iid = self.var_table.insert("", "end", values=("new_var", "[]", "[]"))
        self._open_editor_for_item(iid)

    def _var_edit(self):
        sel = self.var_table.selection()
        if sel:
            self._open_editor_for_item(sel[0])

    def _var_remove(self):
        for iid in self.var_table.selection():
            self.var_table.delete(iid)
        self._update_preview()

    def _open_editor_for_item(self, iid):
        vals = self.var_table.item(iid, "values")

        def save_callback(new_name, tags, values):
            self.var_table.item(iid, values=(new_name, str(tags), str(values)))
            self._update_preview()

        VariableEditor(self.frame, vals[0], vals[1], vals[2], save_callback)
