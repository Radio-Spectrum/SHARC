import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
import random
import json
import yaml  # Requer: pip install PyYAML
import copy
import itertools

# --- Project Imports ---
from utils import add_row_three
from ui.tabs.assets.general_tab.variable_editor import VariableEditor
from ui.tabs.assets.general_tab.general_tools import parse_list_safe


# --- Helper Functions for Merging ---
def deep_merge(base_dict, new_dict):
    """
    Recursively merges new_dict into base_dict.
    Used to combine external parameter files into the main configuration.
    """
    for key, value in new_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value
    return base_dict


def load_param_file(filepath):
    """Loads JSON or YAML file content safely."""
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


class GeneralTab:
    """
    Manages the 'General' tab for simulation parameters.
    Handles Master/Slave configuration generation via external files.
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

        # Example entry
        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=("dist", "['D1','D2']", "[1000,2000]"))

        # --- Generate Button (UPDATED LOGIC) ---
        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(15, 0))
        ttk.Button(
            row_gen, text="⚡ GENERATE YAML FILES",
            command=self.save_yaml_to_yamldir,
            bootstyle="success", width=25
        ).pack(side="left")

    # =========================================================================
    # GENERATION LOGIC (UPDATED)
    # =========================================================================

    def save_yaml_to_yamldir(self):
        """
        Generates YAML files by combining:
        1. General Tab Parameters (Base)
        2. Variable combinations (Cartesian Product)
        3. External File Content (JSON/YAML) merged into the config.
        """
        # 1. Base Configuration
        base_config = {
            "seed": self.app.var_seed.get() if not self.var_use_random_seed.get() else "RANDOM",
            "snaps": self.app.var_snaps.get(),
            "system_type": self.app.var_system.get(),
            "output_dir": self.app.var_outdir.get(),
            "imt_link_direction": self.app.var_imt_link.get(),
            "interference": {
                "adj_channel": self.app.var_adj.get(),
                "co_channel": self.app.var_coch.get()
            },
            # Add other global variables here as needed
            "simulation_prefix": self.app.var_prefix.get()
        }

        # 2. Process Variable Table
        vars_processed = []
        for child in self.var_table.get_children():
            row = self.var_table.item(child)["values"]
            var_name = row[0]
            tags = parse_list_safe(row[1], [])
            vals = parse_list_safe(row[2], [])
            
            if len(tags) == len(vals):
                # Create tuples: (Variable Name, Tag, Value)
                vars_processed.append([(var_name, t, v) for t, v in zip(tags, vals)])
            else:
                messagebox.showerror("Error", f"Length mismatch in variable '{var_name}'")
                return

        # Cartesian Product
        if not vars_processed:
            combinations = [[]]
        else:
            combinations = list(itertools.product(*vars_processed))

        save_dir = Path(self.app.var_yaml_dir.get())
        if not save_dir.exists():
            try:
                save_dir.mkdir(parents=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create directory: {e}")
                return

        count = 0
        prefix_template = self.app.var_prefix.get()

        # 3. Generation Loop
        for combo in combinations:
            current_config = copy.deepcopy(base_config)
            filename_vars = {}

            for var_name, var_tag, var_val in combo:
                filename_vars[var_name] = var_tag
                
                # --- FILE LOADING & MERGING LOGIC ---
                is_file = False
                if isinstance(var_val, str):
                    clean_val = var_val.strip()
                    if clean_val.lower().endswith(('.json', '.yaml', '.yml')):
                        if Path(clean_val).exists():
                            is_file = True
                
                if is_file:
                    # Load external parameters
                    external_data = load_param_file(var_val)
                    # Merge into current config
                    current_config = deep_merge(current_config, external_data)
                    
                    # Metadata tracking
                    if "meta_info" not in current_config: current_config["meta_info"] = {}
                    current_config["meta_info"][f"source_{var_name}"] = Path(var_val).name
                else:
                    # Standard simple value replacement
                    current_config[var_name] = var_val

            # 4. Filename Formatting
            try:
                fname = prefix_template.format(**filename_vars)
                if not fname.endswith('.yaml'):
                    fname += ".yaml"
            except KeyError as e:
                messagebox.showerror("Error", f"Filename prefix requires missing variable: {e}")
                return

            # Handle Random Seed per File
            if current_config.get("seed") == "RANDOM":
                current_config["seed"] = random.randint(1, 999999)

            # 5. Save to File
            out_path = save_dir / fname
            try:
                with open(out_path, 'w', encoding='utf-8') as f:
                    yaml.dump(current_config, f, default_flow_style=False, sort_keys=False)
                count += 1
            except Exception as e:
                print(f"Error saving {fname}: {e}")

        messagebox.showinfo("Success", f"Generated {count} configuration files in:\n{save_dir}")

    # =========================================================================
    # PRESET & INTERNAL LOGIC (UNCHANGED)
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