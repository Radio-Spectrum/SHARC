import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.utils import add_row_three

# Note: The helper function add_row_three was not provided,
# but the main function logic is translated below.

def build_general_tab(self, root):
    """Builds the 'General' tab UI elements."""
    
    frm = ttk.LabelFrame(root, text="General Parameters")
    frm.pack(fill="x")

    e_seed = ttk.Entry(frm, textvariable=self.var_seed, width=12)
    e_snaps = ttk.Entry(frm, textvariable=self.var_snaps, width=12)
    cb_sys = ttk.Combobox(frm, textvariable=self.var_system,
                          values=["SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"],
                          state="readonly", width=26)
    # Assuming add_row_three is a helper function you have defined elsewhere
    add_row_three(frm, 0, [("seed", e_seed),
                           ("num_snapshots", e_snaps),
                           ("system", cb_sys)])

    row2 = ttk.Frame(frm)
    row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row2, text="output_dir (goes inside YAML)").pack(side="left")
    e_outdir = ttk.Entry(row2, textvariable=self.var_outdir)
    e_outdir.pack(side="left", fill="x", expand=True, padx=(6, 6))
    ttk.Button(row2, text="Browse...", command=self._pick_outdir).pack(side="left")

    row2b = ttk.Frame(frm)
    row2b.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row2b, text="yaml_dir (where to save .yaml files)").pack(side="left")
    e_yamldir = ttk.Entry(row2b, textvariable=self.var_yaml_dir)
    e_yamldir.pack(side="left", fill="x", expand=True, padx=(6, 6))
    ttk.Button(row2b, text="Browse...", command=self._pick_yamldir).pack(side="left")

    e_prefix = ttk.Entry(frm, textvariable=self.var_prefix)
    cb_link = ttk.Combobox(frm, textvariable=self.var_imt_link,
                           values=["DOWNLINK", "UPLINK"], state="readonly", width=18)
    add_row_three(frm, 3, [("output_dir_prefix (uses {variable})", e_prefix),
                           ("imt_link", cb_link),
                           ("overwrite_output", ttk.Checkbutton(frm, variable=self.var_overwrite, text="true/false"))])

    add_row_three(frm, 4, [
        ("enable_adjacent_channel", ttk.Checkbutton(frm, variable=self.var_adj, text="true/false")),
        ("enable_cochannel", ttk.Checkbutton(frm, variable=self.var_coch, text="true/false")),
        ("", ttk.Label(frm, text="")) # Placeholder
    ])

    # ---- Variables (name / values in [..]) ----
    box = ttk.LabelFrame(root, text="Variables for Combinations (use {name} in output_dir_prefix and YAML)")
    box.pack(fill="both", expand=True, pady=(8, 0))

    toolbar = ttk.Frame(box)
    toolbar.pack(fill="x")
    ttk.Button(toolbar, text="Add Variable", command=self._var_add).pack(side="left")
    ttk.Button(toolbar, text="Remove Selected", command=self._var_remove).pack(side="left", padx=(6, 0))

    self.var_table = ttk.Treeview(box, columns=("name", "values"), show="headings", height=5)
    self.var_table.heading("name", text="Name")
    self.var_table.heading("values", text="Values (list: [10,20] or [\"LOW\",\"MID\"])")
    self.var_table.column("name", width=180)
    self.var_table.column("values", width=640)
    self.var_table.pack(fill="both", expand=True, pady=(6, 6))

    # Add a default example row if the table is empty
    if not self.var_table.get_children():
        self.var_table.insert("", "end", values=("long", "[-10, -20, -30, -40, -50]"))

    row_gen = ttk.Frame(root)
    row_gen.pack(fill="x", pady=(8, 0))
    ttk.Button(row_gen, text="Generate YAML(s) in yaml_dir (all combinations)",
               command=self._save_yaml_to_yamldir).pack(side="left")