import os
import json
import random
import copy
import itertools
import yaml
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, 
    QTableWidget, QTableWidgetItem, QMenu, QFileDialog, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, Slot

# --- Core Imports ---
from core.yaml_builder import build_yaml_structure
from ui.tabs.assets.general_tab.variable_editor import VariableEditor
from ui.tabs.assets.general_tab.general_tools import parse_list_safe
from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence

GUI_SYSTEM_TYPES = [
    "SINGLE_EARTH_STATION",
    "SINGLE_SPACE_STATION",
    "HAPS",
    "MSS_SS",
    "MSS_D2D",
    "MSS_DC",
]

GUI_TOPOLOGY_TYPES = [
    "MACROCELL",
    "HOTSPOT",
    "SINGLE_BS",
    "Macro_countries",
    "INDOOR",
    "NTN",
    "MSS_DC",
]


# =============================================================================
# Helper Functions (Pure Python - kept intact)
# =============================================================================

def _sanitize_for_yaml(obj: Any) -> Any:
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
    if isinstance(data, dict):
        return {k: _sanitize_recursive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_recursive(v) for v in data]
    return _num_or_str(data)

def _parse_mapping_text(raw_text: Any) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}
    try:
        data = yaml.safe_load(text)
    except Exception as exc:
        print(f"Error parsing mapping text: {exc}")
        return {}
    if isinstance(data, dict):
        return _sanitize_recursive(data)
    return {}

def _default_mss_dc_config(country_names: List[str]) -> Dict[str, Any]:
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

def load_param_file(filepath: str) -> Dict[str, Any]:
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
    for key, value in new_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict

def _sanitize_filename(name: str, max_len: int = 140) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        name = "config"
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name

def _normalize_topology_type(t: str) -> str:
    if not t:
        return "HOTSPOT"
    raw = str(t).strip()
    official = {"HOTSPOT", "MACROCELL", "SINGLE_BS", "Macro_countries", "INDOOR", "NTN", "MSS_DC"}
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
    if low in {"indoor"}:
        return "INDOOR"
    if low in {"ntn"}:
        return "NTN"
    if low in {"mss_dc", "mss dc", "mss-dc"}:
        return "MSS_DC"
    return raw

def _normalize_raster_encoding(value: Any) -> str:
    raw = str(value or "").strip()
    legacy = {"Uniforme": "uniform", "Denspop": "indexed", "": "uniform"}
    enc = legacy.get(raw, raw.lower())
    return enc if enc in {"uniform", "density", "indexed"} else "uniform"

def _normalize_imt_spectral_mask(value: Any) -> str:
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

def _normalize_adjacent_antenna_model(value: Any) -> str:
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

def _normalize_imt_channel_model(value: Any) -> str:
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

def _normalize_num_imt_buildings(value: Any) -> Any:
    parsed = _num_or_str(value)
    if parsed is None:
        return "ALL"
    if isinstance(parsed, str):
        return "ALL" if parsed.strip().upper() == "ALL" else parsed.strip()
    return int(parsed)

def _consolidate_param_p452(block: Dict[str, Any]) -> Dict[str, Any]:
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
# General Tab (PySide6)
# =============================================================================

class GeneralTab(QWidget):
    """
    Manages the 'General' tab for simulation parameters in PySide6.
    """
    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)
        self.app = app
        self.data_collectors = []
        
        self.use_random_seed = False

        self._build_ui()
        self._setup_connections()
        self._update_preview()

    def register_data_collector(self, collector_func):
        self.data_collectors.append(collector_func)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Top Toolbar ---
        toolbar_layout = QHBoxLayout()
        self.btn_files = QPushButton("📁 File Operations (Presets)")
        
        self.menu_files = QMenu(self)
        self.menu_files.addAction("💾 Save Current Preset (.json)", self.save_config)
        self.menu_files.addAction("📂 Load Preset (.json)", self.load_config)
        self.btn_files.setMenu(self.menu_files)
        
        toolbar_layout.addWidget(self.btn_files)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        # --- Main Form ---
        form_group = QGroupBox("General Parameters")
        grid = QGridLayout(form_group)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(5, 1)

        grid.addWidget(QLabel("Seed"), 0, 0)
        seed_layout = QHBoxLayout()
        self.e_seed = QLineEdit()
        self.cb_rnd = QCheckBox("Random")
        self.cb_rnd.toggled.connect(self._toggle_random_seed)
        seed_layout.addWidget(self.e_seed)
        seed_layout.addWidget(self.cb_rnd)
        grid.addLayout(seed_layout, 0, 1)

        grid.addWidget(QLabel("Num Snapshots"), 0, 2)
        self.e_snaps = QLineEdit()
        grid.addWidget(self.e_snaps, 0, 3)

        grid.addWidget(QLabel("System Type"), 0, 4)
        self.cb_sys = QComboBox()
        self.cb_sys.addItems(GUI_SYSTEM_TYPES)
        grid.addWidget(self.cb_sys, 0, 5)

        grid.addWidget(QLabel("Output Dir"), 1, 0)
        out_layout = QHBoxLayout()
        self.e_outdir = QLineEdit()
        btn_outdir = QPushButton("Browse")
        btn_outdir.clicked.connect(self._pick_outdir)
        out_layout.addWidget(self.e_outdir)
        out_layout.addWidget(btn_outdir)
        grid.addLayout(out_layout, 1, 1, 1, 5)

        grid.addWidget(QLabel("YAML Dir"), 2, 0)
        yaml_layout = QHBoxLayout()
        self.e_yamldir = QLineEdit()
        btn_yamldir = QPushButton("Browse")
        btn_yamldir.clicked.connect(self._pick_yamldir)
        yaml_layout.addWidget(self.e_yamldir)
        yaml_layout.addWidget(btn_yamldir)
        grid.addLayout(yaml_layout, 2, 1, 1, 5)

        grid.addWidget(QLabel("Filename Prefix"), 3, 0)
        self.e_prefix = QLineEdit()
        grid.addWidget(self.e_prefix, 3, 1)

        grid.addWidget(QLabel("IMT Link Direction"), 3, 2)
        self.cb_link = QComboBox()
        self.cb_link.addItems(["DOWNLINK", "UPLINK"])
        grid.addWidget(self.cb_link, 3, 3)

        self.cb_overwrite = QCheckBox("Overwrite")
        grid.addWidget(self.cb_overwrite, 3, 5)

        self.cb_adj = QCheckBox("Enable Adj Channel")
        grid.addWidget(self.cb_adj, 4, 1)
        self.cb_coch = QCheckBox("Enable Co-Channel")
        grid.addWidget(self.cb_coch, 4, 3)

        main_layout.addWidget(form_group)

        self.lbl_preview = QLabel("Preview: ...")
        self.lbl_preview.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(self.lbl_preview)

        # --- Variables Table UI ---
        var_group = QGroupBox("Combination Variables (Tags -> YAML Values)")
        var_layout = QVBoxLayout(var_group)
        
        var_tools = QHBoxLayout()
        btn_add_var = QPushButton("+ Add Variable")
        btn_add_var.clicked.connect(self._var_add)
        btn_edit_var = QPushButton("✎ Edit")
        btn_edit_var.clicked.connect(self._var_edit)
        btn_rm_var = QPushButton("🗑 Remove")
        btn_rm_var.clicked.connect(self._var_remove)
        
        var_tools.addWidget(btn_add_var)
        var_tools.addWidget(btn_edit_var)
        var_tools.addWidget(btn_rm_var)
        var_tools.addStretch()
        var_layout.addLayout(var_tools)

        self.var_table = QTableWidget(0, 3)
        self.var_table.setHorizontalHeaderLabels(["Variable Name", "Replacement Tags", "Values List"])
        self.var_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.var_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.var_table.cellDoubleClicked.connect(self._var_edit)
        var_layout.addWidget(self.var_table)

        main_layout.addWidget(var_group)

        # --- Bottom Generation ---
        bot_layout = QHBoxLayout()
        self.btn_actions = QPushButton("⚡ ACTIONS / GENERATION")
        self.btn_actions.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 6px;")
        
        self.menu_actions = QMenu(self)
        self.menu_actions.addAction("🚀 Batch Generate (from Table Variables)", self.save_yaml_to_yamldir)
        self.btn_actions.setMenu(self.menu_actions)
        
        bot_layout.addWidget(self.btn_actions)
        bot_layout.addStretch()
        main_layout.addLayout(bot_layout)

    def _setup_connections(self):
        self._bind_var(self.e_seed, self.app.var_seed)
        self._bind_var(self.e_snaps, self.app.var_snaps)
        self._bind_var(self.cb_sys, self.app.var_system)
        self._bind_var(self.e_outdir, self.app.var_outdir)
        self._bind_var(self.e_yamldir, self.app.var_yaml_dir)
        self._bind_var(self.e_prefix, self.app.var_prefix)
        self._bind_var(self.cb_link, self.app.var_imt_link)
        self._bind_var(self.cb_overwrite, self.app.var_overwrite)
        self._bind_var(self.cb_adj, self.app.var_adj)
        self._bind_var(self.cb_coch, self.app.var_coch)

        self.app.var_outdir.value_changed.connect(lambda v: self._check_path(self.e_outdir, v))
        self.app.var_yaml_dir.value_changed.connect(lambda v: self._check_path(self.e_yamldir, v))
        self.app.var_prefix.value_changed.connect(self._update_preview)

        self._check_path(self.e_outdir, self.app.var_outdir.get())
        self._check_path(self.e_yamldir, self.app.var_yaml_dir.get())

    def _bind_var(self, widget, sharc_var):
        if isinstance(widget, QLineEdit):
            sharc_var.value_changed.connect(lambda v: widget.setText(str(v)))
            widget.textChanged.connect(lambda t: sharc_var.set(t))
            widget.setText(str(sharc_var.get()))
        
        elif isinstance(widget, QComboBox):
            widget.setEditable(True)
            sharc_var.value_changed.connect(lambda v: widget.setCurrentText(str(v)))
            widget.currentTextChanged.connect(lambda t: sharc_var.set(t))
            widget.setCurrentText(str(sharc_var.get()))
            
        elif isinstance(widget, QCheckBox):
            sharc_var.value_changed.connect(lambda v: widget.setChecked(bool(v)))
            widget.toggled.connect(lambda c: sharc_var.set(c))
            widget.setChecked(bool(sharc_var.get()))

    # =========================================================================
    # UI Callbacks
    # =========================================================================

    @Slot()
    def _toggle_random_seed(self):
        self.use_random_seed = self.cb_rnd.isChecked()
        if self.use_random_seed:
            self.app.var_seed.set(str(random.randint(1, 9999)))
            self.e_seed.setEnabled(False)
        else:
            self.e_seed.setEnabled(True)

    def _check_path(self, widget, path):
        if path and Path(str(path)).is_dir():
            widget.setStyleSheet("")
        else:
            widget.setStyleSheet("color: red;")

    @Slot()
    def _update_preview(self, *args):
        text = str(self.app.var_prefix.get())
        if self.var_table.rowCount() == 0:
            self.lbl_preview.setText(f"Preview (no variables): {text}")
            return
        try:
            name = self.var_table.item(0, 0).text()
            tags_str = self.var_table.item(0, 1).text()
            tags_list = parse_list_safe(tags_str, [])
            first_tag = tags_list[0] if tags_list else "?"
            simulated = text.replace(f"{{{name}}}", str(first_tag))
            self.lbl_preview.setText(f"Example: {simulated}")
        except Exception:
            self.lbl_preview.setText("Error generating preview")

    def _pick_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.app.var_outdir.set(path)

    def _pick_yamldir(self):
        path = QFileDialog.getExistingDirectory(self, "Select YAML Save Folder")
        if path:
            self.app.var_yaml_dir.set(path)

    # =========================================================================
    # Variable Table Logic
    # =========================================================================

    def _var_add(self):
        row_idx = self.var_table.rowCount()
        self.var_table.insertRow(row_idx)
        self.var_table.setItem(row_idx, 0, QTableWidgetItem("new_var"))
        self.var_table.setItem(row_idx, 1, QTableWidgetItem("[]"))
        self.var_table.setItem(row_idx, 2, QTableWidgetItem("[]"))
        self._open_editor_for_item(row_idx)

    def _var_edit(self, row=None, col=None):
        if row is None:
            selected = self.var_table.selectedItems()
            if not selected:
                return
            row = selected[0].row()
        self._open_editor_for_item(row)

    def _var_remove(self):
        rows = sorted(list(set(item.row() for item in self.var_table.selectedItems())), reverse=True)
        for r in rows:
            self.var_table.removeRow(r)
        self._update_preview()

    def _open_editor_for_item(self, row_idx):
        name = self.var_table.item(row_idx, 0).text()
        tags = self.var_table.item(row_idx, 1).text()
        vals = self.var_table.item(row_idx, 2).text()

        def save_callback(new_name, new_tags, new_values):
            self.var_table.item(row_idx, 0).setText(str(new_name))
            self.var_table.item(row_idx, 1).setText(str(new_tags))
            self.var_table.item(row_idx, 2).setText(str(new_values))
            self._update_preview()

        dialog = VariableEditor(self, name, tags, vals, save_callback)
        dialog.exec()

    # =========================================================================
    # Generation Logic
    # =========================================================================

    def save_yaml_to_yamldir(self):
        self._internal_save_logic(use_combinations=True)

    def save_single_yaml_snapshot(self):
        self._internal_save_logic(use_combinations=False)

    def _recursive_inject(self, obj, mapping):
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

    def _internal_save_logic(self, use_combinations=True):
        if use_combinations:
            if self.var_table.rowCount() == 0:
                QMessageBox.warning(self, "Generation Aborted", "The variable table is empty.")
                return

        sys_type = self.app.var_system.get()
        sys_key = str(sys_type or "").strip().lower() or "system"
        base_structure = build_yaml_structure(self.app)
        combinations = [[]]
        
        if use_combinations:
            vars_processed = []
            for row in range(self.var_table.rowCount()):
                v_name = self.var_table.item(row, 0).text()
                v_tags = parse_list_safe(self.var_table.item(row, 1).text(), [])
                v_vals = parse_list_safe(self.var_table.item(row, 2).text(), [])
                if len(v_tags) == len(v_vals) and len(v_tags) > 0:
                    vars_processed.append([(v_name, t, v) for t, v in zip(v_tags, v_vals)])
            if vars_processed:
                combinations = list(itertools.product(*vars_processed))

        save_dir = Path(self.app.var_yaml_dir.get())
        save_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        prefix_tmpl = str(self.app.var_prefix.get())

        for combo in combinations:
            final_structure = copy.deepcopy(base_structure)
            fname_vars = {}
            mapping_vars = {}

            for var_name, var_tag, var_val in combo:
                fname_vars[var_name] = var_tag
                mapping_vars[var_name] = var_val

                if isinstance(var_val, str) and var_val.lower().endswith((".json", ".yaml", ".yml")) and Path(var_val).exists():
                    external_data = load_param_file(var_val)
                    config_type = str(external_data.get("config_type", "")).upper()
                    if "config_type" in external_data:
                        del external_data["config_type"]

                    if config_type == "IMT":
                        self._apply_flat_to_app(external_data)
                        final_structure["imt"] = build_yaml_structure(self.app).get("imt", {})
                    elif config_type in {"SSS", "SES", "SYSTEM", "SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION", "MSS_SS", "MSS_D2D", "MSS_DC", "HAPS"}:
                        SESPersistence.apply_config(self.app, external_data)
                        final_structure[sys_key] = build_yaml_structure(self.app).get(sys_key, {})
                    else:
                        if self._is_imt_data(external_data):
                            deep_merge(final_structure["imt"], external_data)
                        elif self._is_hierarchical_sys_data(external_data):
                            deep_merge(final_structure[sys_key], external_data)
                        elif self._is_system_data(external_data):
                            self._apply_flat_to_app(external_data)
                            deep_merge(final_structure[sys_key], build_yaml_structure(self.app).get(sys_key, {}))
                        else:
                            deep_merge(final_structure, external_data)

            final_structure = self._recursive_inject(final_structure, mapping_vars)

            try:
                topo = final_structure.get("imt", {}).get("topology", {})
                if isinstance(topo, dict) and "type" in topo:
                    topo["type"] = _normalize_topology_type(topo["type"])
            except Exception:
                pass

            if isinstance(final_structure.get(sys_key), dict):
                final_structure[sys_key] = _consolidate_param_p452(final_structure[sys_key])

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
                QMessageBox.critical(self, "Error", f"Prefix requires variable {e}")
                return

            if final_structure["general"].get("seed") == "RANDOM":
                final_structure["general"]["seed"] = random.randint(1, 999999)
            
            out_path = save_dir / fname
            _yaml_safe_dump(final_structure, out_path)
            count += 1

        QMessageBox.information(self, "Success", f"Generated {count} configuration files in {save_dir}")

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

    def save_config(self):
        table_data = []
        for r in range(self.var_table.rowCount()):
            table_data.append([
                self.var_table.item(r, 0).text(),
                self.var_table.item(r, 1).text(),
                self.var_table.item(r, 2).text(),
            ])
            
        data = {
            "seed": self.app.var_seed.get(),
            "use_random_seed": self.use_random_seed,
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
        fpath, _ = QFileDialog.getSaveFileName(self, "Save Preset", "", "JSON Files (*.json)")
        if fpath:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

    def load_config(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Load Preset", "", "JSON Files (*.json)")
        if not fpath:
            return
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.app.var_seed.set(data.get("seed", "123"))
        self.cb_rnd.setChecked(data.get("use_random_seed", False))

        self.app.var_snaps.set(data.get("snaps", "100"))
        self.app.var_system.set(data.get("system", "SINGLE_EARTH_STATION"))
        self.app.var_outdir.set(data.get("output_dir", ""))
        self.app.var_yaml_dir.set(data.get("yaml_dir", ""))
        self.app.var_prefix.set(data.get("prefix", "sim_{var}"))
        self.app.var_imt_link.set(data.get("imt_link", "DOWNLINK"))
        self.app.var_overwrite.set(data.get("overwrite", False))
        self.app.var_adj.set(data.get("adj_channel", False))
        self.app.var_coch.set(data.get("co_channel", False))

        self.var_table.setRowCount(0)
        for row in data.get("variables_table", []):
            r_idx = self.var_table.rowCount()
            self.var_table.insertRow(r_idx)
            self.var_table.setItem(r_idx, 0, QTableWidgetItem(str(row[0])))
            self.var_table.setItem(r_idx, 1, QTableWidgetItem(str(row[1])))
            self.var_table.setItem(r_idx, 2, QTableWidgetItem(str(row[2])))

        self._update_preview()