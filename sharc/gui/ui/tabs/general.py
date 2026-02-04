import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
import random
import json

# --- Project Imports ---
# Ensure these modules exist in your project structure
from utils import add_row_three
from ui.tabs.assets.general_tab.variable_editor import VariableEditor
from ui.tabs.assets.general_tab.general_tools import parse_list_safe


class GeneralTab:
    """
    Manages the 'General' tab for simulation parameters.

    Features:
    - Top toolbar for Save/Load presets (JSON).
    - Main form for global parameters (Seed, System, Paths).
    - Variable combination table management.
    - Integration with ttkbootstrap for modern UI styling.
    """

    def __init__(self, app, parent_frame):
        """
        Initialize the General Tab.

        :param app: The main application controller (holds shared Tkinter variables).
        :param parent_frame: The parent widget where this tab will be displayed.
        """
        self.app = app
        self.frame = parent_frame

        # Local State
        self.var_use_random_seed = tk.BooleanVar(value=False)
        self.path_entries = {}  # Store entry references for validation coloring

        # Build Interface
        self._build_top_toolbar()
        self._build_main_form()
        self._setup_traces()

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_top_toolbar(self):
        """
        Creates a high-visibility top toolbar containing File Operations.
        Uses a 'primary' colored Menubutton to stand out.
        """
        toolbar_frame = ttk.Frame(self.frame)
        toolbar_frame.pack(side="top", fill="x", padx=5, pady=(10, 10))

        # File Menu (Cascade Style)
        # bootstyle='primary' gives it a solid accent color
        self.btn_files = ttk.Menubutton(
            toolbar_frame,
            text="📁 File Operations (Presets)",
            bootstyle="primary",
            width=25
        )
        self.btn_files.pack(side="left")

        # Dropdown Menu
        self.menu_files = tk.Menu(self.btn_files, tearoff=0)
        self.btn_files.configure(menu=self.menu_files)

        self.menu_files.add_command(
            label="💾 Save Current Preset (.json)",
            command=self.save_config
        )
        self.menu_files.add_command(
            label="📂 Load Preset (.json)",
            command=self.load_config
        )

        # Visual Separator
        ttk.Separator(self.frame, orient="horizontal").pack(
            fill="x", pady=(0, 15))

    def _build_main_form(self):
        """
        Constructs the main parameter input form using a Labelframe.
        """
        vcmd = (self.frame.register(self._validate_int), '%P')

        # NOTE: Using 'Labelframe' (lowercase f) which is correct for ttk/ttkbootstrap
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
        self._build_path_row(frm, 1, "Output Dir",
                             self.app.var_outdir, self._pick_outdir)

        self._build_path_row(frm, 2, "YAML Dir",
                             self.app.var_yaml_dir, self._pick_yamldir)

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
        self.lbl_preview.grid(row=4, column=0, columnspan=6,
                              sticky="w", padx=5, pady=(0, 5))

        # --- Row 5: Interference Flags ---
        cb_adj = ttk.Checkbutton(
            frm, variable=self.app.var_adj, text="Active", bootstyle="square-toggle")
        cb_coch = ttk.Checkbutton(
            frm, variable=self.app.var_coch, text="Active", bootstyle="square-toggle")

        add_row_three(frm, 5, [
            ("Enable Adj Channel", cb_adj),
            ("Enable Co-Channel", cb_coch),
            ("", ttk.Label(frm, text=""))  # Placeholder
        ])

        # --- Variable Table ---
        self._build_var_table_ui()

    def _build_path_row(self, parent, row_idx, label_text, var, cmd):
        """Helper to create consistent path selection rows with Browse buttons."""
        row = ttk.Frame(parent)
        row.grid(row=row_idx, column=0, columnspan=6, sticky="we", pady=5)

        ttk.Label(row, text=label_text).pack(side="left")

        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row, text="Browse", command=cmd,
                   bootstyle="secondary-outline").pack(side="left")

        # Save reference for validation
        self.path_entries[str(var)] = entry

    def _build_var_table_ui(self):
        """Builds the table for Combination Variables."""
        # NOTE: Using 'Labelframe' (lowercase f)
        box = ttk.Labelframe(
            self.frame, text="Combination Variables (Tags -> YAML Values)", padding=10)
        box.pack(fill="both", expand=True, pady=(15, 0))

        # Toolbar
        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 5))

        ttk.Button(toolbar, text="+ Add Variable",
                   command=self._var_add, bootstyle="info-outline").pack(side="left")
        ttk.Button(toolbar, text="✎ Edit",
                   command=self._var_edit, bootstyle="secondary-outline").pack(side="left", padx=6)
        ttk.Button(toolbar, text="🗑 Remove",
                   command=self._var_remove, bootstyle="danger-outline").pack(side="left", padx=6)

        # Treeview
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

        # Default entry example
        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=(
                "dist", "['D1','D2']", "[1000,2000]"))

        # --- Bottom Generate Button ---
        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(15, 0))

        ttk.Button(
            row_gen,
            text="⚡ GENERATE YAML FILES",
            command=self.app.save_yaml_to_yamldir,
            bootstyle="success",
            width=25
        ).pack(side="left")

    # =========================================================================
    # PRESET LOGIC (SAVE / LOAD)
    # =========================================================================

    def save_config(self):
        """
        Collects all UI states and saves them to a JSON file.
        Includes table data and all simple variables.
        """
        # 1. Collect Table Data
        table_data = []
        for child in self.var_table.get_children():
            table_data.append(self.var_table.item(child)["values"])

        # 2. Build Dictionary
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

        # 3. Write to File
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Configuration", "*.json")],
            title="Save Configuration Preset"
        )
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                messagebox.showinfo(
                    "Success", f"Preset saved to:\n{Path(fpath).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save preset:\n{e}")

    def load_config(self):
        """
        Loads a JSON file and populates the UI fields.
        Clears existing table data before loading.
        """
        fpath = filedialog.askopenfilename(
            filetypes=[("JSON Configuration", "*.json")],
            title="Load Configuration Preset"
        )
        if not fpath:
            return

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Restore Simple Variables (using .get for safety)
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

            # 2. Restore Table Data
            for item in self.var_table.get_children():
                self.var_table.delete(item)

            saved_rows = data.get("variables_table", [])
            for row in saved_rows:
                self.var_table.insert("", "end", values=row)

            # 3. Refresh Visuals
            self._check_path(self.app.var_outdir)
            self._check_path(self.app.var_yaml_dir)
            self._update_preview()

            messagebox.showinfo(
                "Success", "Configuration loaded successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset:\n{e}")

    # =========================================================================
    # INTERNAL LOGIC & EVENTS
    # =========================================================================

    def _toggle_random_seed(self):
        """Disables the seed entry if 'Random' is checked."""
        if self.var_use_random_seed.get():
            self.app.var_seed.set(str(random.randint(1, 9999)))
            self.e_seed.configure(state='disabled')
        else:
            self.e_seed.configure(state='normal')

    def _setup_traces(self):
        """Sets up observers for variable changes."""
        self.app.var_outdir.trace_add(
            "write", lambda *a: self._check_path(self.app.var_outdir))
        self.app.var_yaml_dir.trace_add(
            "write", lambda *a: self._check_path(self.app.var_yaml_dir))
        self.app.var_prefix.trace_add("write", self._update_preview)

        # Initial check
        self._check_path(self.app.var_outdir)
        self._check_path(self.app.var_yaml_dir)
        self._update_preview()

    def _validate_int(self, P):
        """Tkinter validator for integer-only input."""
        if P == "" or P == "-":
            return True
        return P.isdigit() or (P.startswith("-") and P[1:].isdigit())

    def _check_path(self, var):
        """
        Validates if the path exists. 
        Changes text color to red if invalid, black (or default) if valid.
        """
        entry = self.path_entries.get(str(var))
        if not entry:
            return

        path = var.get()
        if path and Path(path).is_dir():
            entry.configure(foreground="black")
        else:
            entry.configure(foreground="red")

    def _update_preview(self, *args):
        """Updates the filename preview based on the prefix and the first variable tag."""
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
        if path:
            self.app.var_outdir.set(path)

    def _pick_yamldir(self):
        cur = self.app.var_yaml_dir.get()
        path = self._ask_directory(cur, "Select YAML Save Folder")
        if path:
            self.app.var_yaml_dir.set(path)

    def _ask_directory(self, start_path, title):
        """Opens a directory picker dialog."""
        start = start_path if start_path and Path(
            start_path).is_dir() else Path.cwd()
        path = filedialog.askdirectory(initialdir=start, title=title)
        if path:
            return Path(path).as_posix()
        return None

    # =========================================================================
    # TABLE MANAGEMENT
    # =========================================================================

    def _var_add(self):
        """Adds a new placeholder row to the variables table."""
        iid = self.var_table.insert("", "end", values=("new_var", "[]", "[]"))
        self.var_table.selection_set(iid)
        self._open_editor_for_item(iid)

    def _var_edit(self):
        """Opens the editor for the selected row."""
        sel = self.var_table.selection()
        if not sel:
            return
        self._open_editor_for_item(sel[0])

    def _var_remove(self):
        """Removes the selected row(s)."""
        for iid in self.var_table.selection():
            self.var_table.delete(iid)
        self._update_preview()

    def _open_editor_for_item(self, iid):
        """Launches the VariableEditor dialog."""
        vals = self.var_table.item(iid, "values")

        def save_callback(new_name, tags, values):
            self.var_table.item(iid, values=(new_name, str(tags), str(values)))
            self._update_preview()

        VariableEditor(self.frame, vals[0], vals[1], vals[2], save_callback)
