from tkinter import ttk, filedialog
import os
from utils.ui_helpers import add_row_three

def build_tab_general(root, S):
    frm = ttk.LabelFrame(root, text="Parâmetros gerais")
    frm.pack(fill="x")

    # row 1
    e_seed = ttk.Entry(frm, textvariable=S.var_seed, width=12)
    e_snaps = ttk.Entry(frm, textvariable=S.var_snaps, width=12)
    cb_sys = ttk.Combobox(frm, textvariable=S.var_system,
                          values=["SINGLE_EARTH_STATION","SINGLE_SPACE_STATION"],
                          state="readonly", width=26)
    add_row_three(frm, 0, [("seed", e_seed),
                           ("num_snapshots", e_snaps),
                           ("system", cb_sys)])

    # row 2 (frame uses grid; inside we use pack, avoiding grid/pack mix on same container)
    row2 = ttk.Frame(frm)
    row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)

    ttk.Label(row2, text="output_dir").pack(side="left")

    e_outdir = ttk.Entry(row2, textvariable=S.var_outdir)
    e_outdir.pack(side="left", fill="x", expand=True, padx=(6,6))

    def _pick_outdir():
        cur = S.var_outdir.get() or os.getcwd()
        if not os.path.isdir(cur):
            cur = os.getcwd()
        path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta de saída")
        if path:
            if not path.endswith(("/", "\\")):
                path = path + os.sep
            S.var_outdir.set(path.replace("\\\\","/"))
    ttk.Button(row2, text="Selecionar pasta...", command=_pick_outdir).pack(side="left")

    # row 3
    e_prefix = ttk.Entry(frm, textvariable=S.var_prefix)
    cb_link = ttk.Combobox(frm, textvariable=S.var_imt_link,
                           values=["DOWNLINK","UPLINK"], state="readonly", width=18)
    add_row_three(frm, 2, [("output_dir_prefix", e_prefix),
                           ("imt_link", cb_link),
                           ("overwrite_output", ttk.Checkbutton(frm, variable=S.var_overwrite, text="true/false"))])

    # row 4
    add_row_three(frm, 3, [
        ("enable_adjacent_channel", ttk.Checkbutton(frm, variable=S.var_adj, text="true/false")),
        ("enable_cochannel", ttk.Checkbutton(frm, variable=S.var_coch, text="true/false")),
        ("", ttk.Label(frm, text=""))
    ])
