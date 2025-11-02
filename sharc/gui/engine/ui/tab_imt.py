"""
IMT tab builder: IMT parameters and topology selector.
This module creates a scrollable container to host many controls.
"""

import tkinter as tk
from tkinter import ttk
from core.utils import add_row_three


def build_imt_tab(app: tk.Tk, root: tk.Widget) -> None:
    # Create a scrollable container so the UI can host many controls
    container = ttk.Frame(root)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0)
    vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    body = ttk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")

    def on_frame_config(event: tk.Event) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(canvas_window, width=canvas.winfo_width())

    body.bind("<Configure>", on_frame_config)

    # Top bar with save/load buttons (connect these to actual save/load logic later)
    topbar = ttk.Frame(body)
    topbar.pack(fill="x", pady=(0, 6))
    ttk.Button(topbar, text="Save IMT config (.json)", command=lambda: None).pack(side="left")
    ttk.Button(topbar, text="Load IMT config (.json)", command=lambda: None).pack(side="left", padx=(6, 0))

    # IMT general parameters
    frm_g = ttk.LabelFrame(body, text="IMT – General parameters")
    frm_g.pack(fill="x", pady=(2, 8))

    add_row_three(
        frm_g,
        0,
        [
            ("minimum_separation_distance_bs_ue [m]", ttk.Entry(frm_g, textvariable=app.imt_min_sep, width=10)),
            ("interfered_with", ttk.Combobox(frm_g, values=[False, True], state="readonly", width=8)),
            ("frequency [MHz]", ttk.Entry(frm_g, textvariable=app.imt_freq, width=12)),
        ],
    )

    add_row_three(
        frm_g,
        1,
        [
            ("bandwidth [MHz]", ttk.Entry(frm_g, textvariable=app.imt_bw, width=10)),
            ("rb_bandwidth [MHz]", ttk.Entry(frm_g, textvariable=tk.StringVar(value="0.18"), width=10)),
            ("spectral_mask", ttk.Combobox(frm_g, values=["IMT-2020", "3GPP"], state="readonly", width=12)),
        ],
    )

    # Topology selector
    frm_t = ttk.LabelFrame(body, text="Topology – IMT")
    frm_t.pack(fill="x", pady=(2, 8))

    row_type = ttk.Frame(frm_t)
    row_type.grid(row=0, column=0, columnspan=6, sticky="we", pady=(0, 4))
    ttk.Label(row_type, text="type").pack(side="left")
    cb_topo_type = ttk.Combobox(
        row_type,
        textvariable=app.topo_type,
        values=["MACROCELL", "HOTSPOT", "SINGLE_BS", "Macro_countries"],
        state="readonly",
        width=18,
    )
    cb_topo_type.pack(side="left", padx=(6, 0))

    add_row_three(
        frm_t,
        1,
        [
            ("central_latitude", ttk.Entry(frm_t, textvariable=app.topo_c_lat, width=12)),
            ("central_longitude", ttk.Entry(frm_t, textvariable=app.topo_c_lon, width=12)),
            ("central_altitude [m]", ttk.Entry(frm_t, textvariable=app.topo_c_alt, width=12)),
        ],
    )

    # Topology: Countries subframe (simple UI — reading/writing handled elsewhere)
    frm_c = ttk.LabelFrame(frm_t, text="Topology – COUNTRIES (Macro_countries)")
    frm_c.grid(row=2, column=0, columnspan=6, sticky="we", pady=(4, 8))

    row_c = ttk.Frame(frm_c)
    row_c.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
    ttk.Label(row_c, text="country_names (one per line)").pack(side="left")
    txt = tk.Text(row_c, width=48, height=7)
    txt.insert("1.0", app.topo_countries.get())
    txt.pack(side="left", fill="x", expand=True, padx=(6, 6))
