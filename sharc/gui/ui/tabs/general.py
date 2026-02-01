import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import random

# Imports from your project structure
from utils import add_row_three
from ui.tabs.assets.general_tab.variable_editor import VariableEditor
from ui.tabs.assets.general_tab.general_tools import parse_list_safe


class GeneralTab:
    """
    Manages the 'General' tab simulation parameters.
    """

    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        # State
        self.var_use_random_seed = tk.BooleanVar(value=False)

        self._build_ui()
        self._setup_traces()

    def _build_ui(self):
        vcmd = (self.frame.register(self._validate_int), '%P')

        frm = ttk.LabelFrame(self.frame, text="General Parameters")
        frm.pack(fill="x", pady=(0, 6))

        # --- Row 1 ---
        f_seed_cont = ttk.Frame(frm)
        self.e_seed = ttk.Entry(
            f_seed_cont, textvariable=self.app.var_seed,
            width=8, validate='key', validatecommand=vcmd
        )
        self.e_seed.pack(side="left")

        cb_rnd = ttk.Checkbutton(
            f_seed_cont, text="Random",
            variable=self.var_use_random_seed, command=self._toggle_random_seed
        )
        cb_rnd.pack(side="left", padx=(5, 0))

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
            ("seed", f_seed_cont),
            ("num_snapshots", e_snaps),
            ("system", cb_sys)
        ])

        # --- Row 2: Output Dir ---
        self._build_path_row(frm, 1, "output_dir (written to YAML)",
                             self.app.var_outdir, self._pick_outdir)

        # --- Row 3: YAML Dir ---
        self._build_path_row(frm, 2, "yaml_dir (where to save .yaml files)",
                             self.app.var_yaml_dir, self._pick_yamldir)

        # --- Row 4 ---
        e_prefix = ttk.Entry(frm, textvariable=self.app.var_prefix)
        cb_link = ttk.Combobox(
            frm, textvariable=self.app.var_imt_link,
            values=["DOWNLINK", "UPLINK"], state="readonly", width=18
        )

        add_row_three(frm, 3, [
            ("output_dir_prefix (uses {variable})", e_prefix),
            ("imt_link", cb_link),
            ("overwrite_output", ttk.Checkbutton(
                frm, variable=self.app.var_overwrite, text="true/false"))
        ])

        # --- Preview Label ---
        self.lbl_preview = ttk.Label(
            frm, text="Preview: ...", foreground="gray")
        self.lbl_preview.grid(row=4, column=0, columnspan=6,
                              sticky="w", padx=5, pady=(0, 5))

        # --- Row 5 ---
        add_row_three(frm, 5, [
            ("enable_adjacent_channel", ttk.Checkbutton(
                frm, variable=self.app.var_adj, text="true/false")),
            ("enable_cochannel", ttk.Checkbutton(
                frm, variable=self.app.var_coch, text="true/false")),
            ("", ttk.Label(frm, text=""))
        ])

        # --- Combination Variables ---
        self._build_var_table_ui()

    def _build_path_row(self, parent, row_idx, label_text, var, cmd):
        """Helper to reduce code duplication for path selection rows."""
        row = ttk.Frame(parent)
        row.grid(row=row_idx, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row, text=label_text).pack(side="left")

        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row, text="Select...", command=cmd).pack(side="left")

        # Store entry reference for validation coloring later
        if not hasattr(self, 'path_entries'):
            self.path_entries = {}
        self.path_entries[str(var)] = entry

    def _build_var_table_ui(self):
        box = ttk.LabelFrame(
            self.frame, text="Combination Variables (Tags in filename -> Values in YAML)")
        box.pack(fill="both", expand=True, pady=(8, 0))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="Add Variable",
                   command=self._var_add).pack(side="left")
        ttk.Button(toolbar, text="Edit Selected",
                   command=self._var_edit).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Remove Selected",
                   command=self._var_remove).pack(side="left", padx=6)

        self.var_table = ttk.Treeview(
            box, columns=("var", "tags", "values"), show="headings", height=6
        )
        self.var_table.heading("var", text="Variable (placeholder)")
        self.var_table.heading("tags", text="Tags")
        self.var_table.heading("values", text="Values")

        self.var_table.column("var", width=150)
        self.var_table.column("tags", width=250)
        self.var_table.column("values", width=450)

        self.var_table.pack(fill="both", expand=True, pady=(4, 6))
        self.var_table.bind("<Double-1>", lambda e: self._var_edit())

        # Default Example
        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=(
                "dist", "['D1','D2']", "[1000,2000]"))

        # Generate Button
        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(8, 0))
        ttk.Button(
            row_gen, text="Generate YAML(s) in yaml_dir",
            command=self.app.save_yaml_to_yamldir
        ).pack(side="left")

    # --- Logic ---

    def _toggle_random_seed(self):
        if self.var_use_random_seed.get():
            self.app.var_seed.set(str(random.randint(1, 9999)))
            self.e_seed.configure(state='disabled')
        else:
            self.e_seed.configure(state='normal')

    def _setup_traces(self):
        # Watch paths to color them red if invalid
        self.app.var_outdir.trace_add(
            "write", lambda *a: self._check_path(self.app.var_outdir))
        self.app.var_yaml_dir.trace_add(
            "write", lambda *a: self._check_path(self.app.var_yaml_dir))
        self.app.var_prefix.trace_add("write", self._update_preview)

        self._check_path(self.app.var_outdir)
        self._check_path(self.app.var_yaml_dir)
        self._update_preview()

    def _validate_int(self, P):
        if P == "" or P == "-":
            return True
        return P.isdigit() or (P.startswith("-") and P[1:].isdigit())

    def _check_path(self, var):
        entry = self.path_entries.get(str(var))
        if not entry:
            return

        path = var.get()
        # Use Pathlib for modernization
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
        if path:
            self.app.var_outdir.set(path)

    def _pick_yamldir(self):
        cur = self.app.var_yaml_dir.get()
        path = self._ask_directory(cur, "Select YAML Save Folder")
        if path:
            self.app.var_yaml_dir.set(path)

    def _ask_directory(self, start_path, title):
        start = start_path if start_path and Path(
            start_path).is_dir() else Path.cwd()
        path = filedialog.askdirectory(initialdir=start, title=title)
        if path:
            # Modernize: return forward slashes
            return Path(path).as_posix()
        return None

    # --- Variable Table Logic ---

    def _var_add(self):
        iid = self.var_table.insert("", "end", values=("new_var", "[]", "[]"))
        self.var_table.selection_set(iid)
        self._open_editor_for_item(iid)

    def _var_edit(self):
        sel = self.var_table.selection()
        if not sel:
            return
        self._open_editor_for_item(sel[0])

    def _var_remove(self):
        for iid in self.var_table.selection():
            self.var_table.delete(iid)
        self._update_preview()

    def _open_editor_for_item(self, iid):
        vals = self.var_table.item(iid, "values")
        # Define callback to handle data coming back from the dialog

        def save_callback(new_name, tags, values):
            self.var_table.item(iid, values=(new_name, str(tags), str(values)))
            self._update_preview()

        VariableEditor(self.frame, vals[0], vals[1], vals[2], save_callback)
