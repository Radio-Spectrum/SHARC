# Auto-split from original sharc_gui.py
from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import RESULT_FIELDNAME_TO_PLOT_INFO  # noqa

class GeneralTabTabMixin:
    def _tab_general(self, root):
            frm = ttk.LabelFrame(root, text="Parâmetros gerais")
            frm.pack(fill="x")

            e_seed = ttk.Entry(frm, textvariable=self.var_seed, width=12)
            e_snaps = ttk.Entry(frm, textvariable=self.var_snaps, width=12)
            cb_sys = ttk.Combobox(frm, textvariable=self.var_system,
                                  values=["SINGLE_EARTH_STATION","SINGLE_SPACE_STATION"],
                                  state="readonly", width=26)
            add_row_three(frm, 0, [("seed", e_seed),
                                   ("num_snapshots", e_snaps),
                                   ("system", cb_sys)])

            row2 = ttk.Frame(frm); row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
            ttk.Label(row2, text="output_dir (vai dentro do YAML)").pack(side="left")
            e_outdir = ttk.Entry(row2, textvariable=self.var_outdir)
            e_outdir.pack(side="left", fill="x", expand=True, padx=(6,6))
            ttk.Button(row2, text="Selecionar...", command=self._pick_outdir).pack(side="left")

            row2b = ttk.Frame(frm); row2b.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
            ttk.Label(row2b, text="yaml_dir (onde salvar os .yaml)").pack(side="left")
            e_yamldir = ttk.Entry(row2b, textvariable=self.var_yaml_dir)
            e_yamldir.pack(side="left", fill="x", expand=True, padx=(6,6))
            ttk.Button(row2b, text="Selecionar...", command=self._pick_yamldir).pack(side="left")

            e_prefix = ttk.Entry(frm, textvariable=self.var_prefix)
            cb_link = ttk.Combobox(frm, textvariable=self.var_imt_link,
                                   values=["DOWNLINK","UPLINK"], state="readonly", width=18)
            add_row_three(frm, 3, [("output_dir_prefix (usa {variavel})", e_prefix),
                                   ("imt_link", cb_link),
                                   ("overwrite_output", ttk.Checkbutton(frm, variable=self.var_overwrite, text="true/false"))])

            add_row_three(frm, 4, [
                ("enable_adjacent_channel", ttk.Checkbutton(frm, variable=self.var_adj, text="true/false")),
                ("enable_cochannel", ttk.Checkbutton(frm, variable=self.var_coch, text="true/false")),
                ("", ttk.Label(frm, text=""))
            ])

            # ---- Variáveis (nome / valores em [..]) ----
            box = ttk.LabelFrame(root, text="Variáveis para combinações (use {nome} no output_dir_prefix e no YAML)")
            box.pack(fill="both", expand=True, pady=(8,0))

            toolbar = ttk.Frame(box); toolbar.pack(fill="x")
            ttk.Button(toolbar, text="Adicionar variável", command=self._var_add).pack(side="left")
            ttk.Button(toolbar, text="Remover selecionadas", command=self._var_remove).pack(side="left", padx=(6,0))

            self.var_table = ttk.Treeview(box, columns=("name","values"), show="headings", height=5)
            self.var_table.heading("name", text="nome")
            self.var_table.heading("values", text="valores (lista: [10,20] ou [\"LOW\",\"MID\"])")
            self.var_table.column("name", width=180)
            self.var_table.column("values", width=640)
            self.var_table.pack(fill="both", expand=True, pady=(6,6))

            if not self.var_table.get_children():
                self.var_table.insert("", "end", values=("long", "[-10, -20, -30, -40, -50]"))

            row_gen = ttk.Frame(root)
            row_gen.pack(fill="x", pady=(8,0))
            ttk.Button(row_gen, text="Gerar YAML(s) no yaml_dir (todas combinações)", command=self._save_yaml_to_yamldir).pack(side="left")

    def _pick_outdir(self):
            cur = self.var_outdir.get() or os.getcwd()
            if not os.path.isdir(cur): cur = os.getcwd()
            path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta de saída (dentro do YAML)")
            if path:
                if not path.endswith(("/", "\\")):
                    path = path + os.sep
                self.var_outdir.set(path.replace("\\","/"))

    def _pick_yamldir(self):
            p = filedialog.askdirectory(title="Selecionar pasta para salvar os .yaml", initialdir=self.var_yaml_dir.get() or os.getcwd())
            if p:
                self.var_yaml_dir.set(p)

    def _save_yaml_to_yamldir(self):
            combos = self._collect_var_combos()
            if combos is None:
                return
            root = self._current_yaml()
            outdir = self.var_yaml_dir.get() or "."
            os.makedirs(outdir, exist_ok=True)
            self._write_yaml_combos(root, outdir, combos)
            messagebox.showinfo("OK", f"YAML(s) gerado(s) em:\n{outdir}")

    def _var_add(self):
            def _ok():
                name = e_name.get().strip()
                vals = e_vals.get().strip()
                if not name: 
                    messagebox.showwarning("Variáveis", "Informe um nome.")
                    return
                if not vals:
                    messagebox.showwarning("Variáveis", "Informe valores em lista, ex: [1,2] ou [\"LOW\",\"HIGH\"].")
                    return
                try:
                    lst = ast.literal_eval(vals)
                    if not isinstance(lst, (list, tuple)):
                        raise ValueError()
                except Exception:
                    messagebox.showwarning("Variáveis", "Valores devem ser uma lista Python válida.")
                    return
                self.var_table.insert("", "end", values=(name, vals))
                dlg.destroy()

            dlg = tk.Toplevel(self); dlg.title("Adicionar variável")
            ttk.Label(dlg, text="Nome da variável (use {nome} no prefix/YAML):").pack(anchor="w", padx=10, pady=(10,2))
            e_name = ttk.Entry(dlg); e_name.pack(fill="x", padx=10)
            ttk.Label(dlg, text="Valores (lista):").pack(anchor="w", padx=10, pady=(10,2))
            e_vals = ttk.Entry(dlg); e_vals.pack(fill="x", padx=10)
            btns = ttk.Frame(dlg); btns.pack(fill="x", pady=10)
            ttk.Button(btns, text="OK", command=_ok).pack(side="left", padx=(10,4))
            ttk.Button(btns, text="Cancelar", command=dlg.destroy).pack(side="left")
            e_name.focus_set()

    def _var_remove(self):
            sel = self.var_table.selection()
            for iid in sel:
                self.var_table.delete(iid)

