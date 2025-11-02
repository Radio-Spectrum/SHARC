"""
General tab builder: project-level parameters and YAML output folder controls.
"""

from tkinter import ttk, filedialog
import tkinter as tk
from core.utils import add_row_three


def build_general_tab(app: tk.Tk, root: tk.Widget) -> None:
    """Populate the 'General' tab with controls."""
    frm = ttk.LabelFrame(root, text="General parameters")
    frm.pack(fill="x")

    entry_seed = ttk.Entry(frm, textvariable=app.var_seed, width=12)
    entry_snaps = ttk.Entry(frm, textvariable=app.var_snaps, width=12)
    cb_sys = ttk.Combobox(
        frm,
        textvariable=app.var_system,
        values=["SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"],
        state="readonly",
        width=26,
    )

    add_row_three(frm, 0, [("seed", entry_seed), ("num_snapshots", entry_snaps), ("system", cb_sys)])

    # output_dir row
    row_out = ttk.Frame(frm)
    row_out.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row_out, text="output_dir (stored in YAML)").pack(side="left")
    e_outdir = ttk.Entry(row_out, textvariable=app.var_outdir)
    e_outdir.pack(side="left", fill="x", expand=True, padx=(6, 6))
    ttk.Button(row_out, text="Browse...", command=lambda: _pick_outdir(app)).pack(side="left")

    # yaml_dir row
    row_yaml = ttk.Frame(frm)
    row_yaml.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row_yaml, text="yaml_dir (where YAML files are saved)").pack(side="left")
    e_yaml = ttk.Entry(row_yaml, textvariable=app.var_yaml_dir)
    e_yaml.pack(side="left", fill="x", expand=True, padx=(6, 6))
    ttk.Button(row_yaml, text="Browse...", command=lambda: _pick_yamldir(app)).pack(side="left")

    # prefix and link
    e_prefix = ttk.Entry(frm, textvariable=app.var_prefix)
    cb_link = ttk.Combobox(
        frm, textvariable=app.var_imt_link, values=["DOWNLINK", "UPLINK"], state="readonly", width=18
    )
    add_row_three(
        frm,
        3,
        [
            ("output_dir_prefix (supports {variable})", e_prefix),
            ("imt_link", cb_link),
            ("overwrite_output", ttk.Checkbutton(frm, variable=app.var_overwrite, text="")),
        ],
    )


def _pick_outdir(app: tk.Tk) -> None:
    path = filedialog.askdirectory(initialdir=app.var_outdir.get() or ".")
    if path:
        app.var_outdir.set(path)


def _pick_yamldir(app: tk.Tk) -> None:
    path = filedialog.askdirectory(initialdir=app.var_yaml_dir.get() or ".")
    if path:
        app.var_yaml_dir.set(path)
