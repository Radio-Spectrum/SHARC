# Auto-split from original sharc_gui.py
from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import RESULT_FIELDNAME_TO_PLOT_INFO  # noqa
import math

class GeneralTabTabMixin:
    def _tab_general(self, root):
        # =========================================================
        # ESTADOS (garanta que existam)
        # =========================================================
        if not hasattr(self, "var_seed_random"):
            self.var_seed_random = tk.BooleanVar(value=False)

        # =========================================================
        # 1) TOPO: seed / num_snapshots / system
        # =========================================================
        frm_top = ttk.LabelFrame(root, text="Parâmetros gerais")
        frm_top.pack(fill="x", pady=(0, 6))

        row0 = ttk.Frame(frm_top)
        row0.pack(fill="x", pady=4)

        ttk.Label(row0, text="seed").pack(side="left")
        e_seed = ttk.Entry(row0, textvariable=self.var_seed, width=12)
        e_seed.pack(side="left", padx=(6, 18))

        cb_seed_rand = ttk.Checkbutton(row0, variable=self.var_seed_random,
                                    text="Seed aleatório (1–9999 por YAML)")
        cb_seed_rand.pack(side="left", padx=(0, 18))

        ttk.Label(row0, text="num_snapshots").pack(side="left")
        e_snaps = ttk.Entry(row0, textvariable=self.var_snaps, width=12)
        e_snaps.pack(side="left", padx=(6, 18))

        ttk.Label(row0, text="system").pack(side="left")
        cb_sys = ttk.Combobox(row0, textvariable=self.var_system,
                            values=["SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"],
                            state="readonly", width=26)
        cb_sys.pack(side="left", padx=(6, 0))


        # =========================================================
        # 2) OPÇÕES: imt_link + enable_adjacent/cochannel (abaixo do topo)
        # =========================================================
        frm_opts = ttk.LabelFrame(root, text="Opções IMT")
        frm_opts.pack(fill="x", pady=(0, 6))

        cb_link = ttk.Combobox(frm_opts, textvariable=self.var_imt_link,
                            values=["DOWNLINK", "UPLINK"],
                            state="readonly", width=18)

        chk_adj = ttk.Checkbutton(frm_opts, variable=self.var_adj, text="enable_adjacent_channel")
        chk_coch = ttk.Checkbutton(frm_opts, variable=self.var_coch, text="enable_cochannel")
        chk_over = ttk.Checkbutton(frm_opts, variable=self.var_overwrite, text="overwrite_output")

        row1 = ttk.Frame(frm_opts)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="imt_link").pack(side="left")
        cb_link.pack(side="left", padx=(6, 16))
        chk_adj.pack(side="left", padx=(0, 16))
        chk_coch.pack(side="left", padx=(0, 16))
        chk_over.pack(side="left", padx=(0, 0))

        # =========================================================
        # 3) PASTAS: output_dir e yaml_dir (subsessão)
        # =========================================================
        frm_dirs = ttk.LabelFrame(root, text="Pastas")
        frm_dirs.pack(fill="x", pady=(0, 8))

        # output_dir (vai dentro do YAML)
        rowd1 = ttk.Frame(frm_dirs)
        rowd1.pack(fill="x", pady=2)
        ttk.Label(rowd1, text="output_dir (vai dentro do YAML)").pack(side="left")
        e_outdir = ttk.Entry(rowd1, textvariable=self.var_outdir)
        e_outdir.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(rowd1, text="Selecionar...", command=self._pick_outdir).pack(side="left")

        # yaml_dir (onde salvar os .yaml)
        rowd2 = ttk.Frame(frm_dirs)
        rowd2.pack(fill="x", pady=2)
        ttk.Label(rowd2, text="yaml_dir (onde salvar os .yaml)").pack(side="left")
        e_yamldir = ttk.Entry(rowd2, textvariable=self.var_yaml_dir)
        e_yamldir.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(rowd2, text="Selecionar...", command=self._pick_yamldir).pack(side="left")

        # =========================================================
        # 4) VARIÁVEIS + PREFIX: output_dir_prefix + tabela + editor
        # =========================================================
        box = ttk.LabelFrame(root, text="Variáveis para combinações (tags para nome do YAML / valores para o YAML)")
        box.pack(fill="both", expand=True, pady=(0, 0))

        # output_dir_prefix aqui dentro
        rowp = ttk.Frame(box)
        rowp.pack(fill="x", pady=(6, 4))
        ttk.Label(rowp, text="output_dir_prefix (usa {variavel} = TAG no nome do YAML)").pack(side="left")
        e_prefix = ttk.Entry(rowp, textvariable=self.var_prefix)
        e_prefix.pack(side="left", fill="x", expand=True, padx=(6, 6))

        # Toolbar
        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="Adicionar variável", command=self._var_add).pack(side="left")

        # editar selecionada (se você implementou _var_edit)
        ttk.Button(toolbar, text="Editar selecionada", command=getattr(self, "_var_edit", lambda: None)).pack(side="left", padx=(6, 0))

        # selecionar arquivos para a variável selecionada (se você implementou _var_pick_files)
        #ttk.Button(toolbar, text="Selecionar arquivos...", command=getattr(self, "_var_pick_files", lambda: None)).pack(side="left", padx=(6, 0))

        ttk.Button(toolbar, text="Remover selecionadas", command=self._var_remove).pack(side="left", padx=(6, 0))

        # Tabela: var_key | tags | values
        self.var_table = ttk.Treeview(box, columns=("var", "tags", "values"), show="headings", height=6)
        self.var_table.heading("var", text="variável (placeholder no YAML)")
        self.var_table.heading("tags", text="tags (nome no YAML)  ex: [\"D1\",\"D2\"]")
        self.var_table.heading("values", text="valores (número ou path)  ex: [1000,2000] ou [\"a.yaml\",\"b.yaml\"]")
        self.var_table.column("var", width=240)
        self.var_table.column("tags", width=300)
        self.var_table.column("values", width=520)
        self.var_table.pack(fill="both", expand=True, pady=(4, 6))

        # Duplo-clique para editar (se existir _var_edit)
        if hasattr(self, "_var_edit"):
            self.var_table.bind("<Double-1>", lambda e: self._var_edit())

        # Exemplo inicial
        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=("dist", "['D1','D2']", "[1000,2000]"))
            self.var_table.insert("", "end", values=("lat", "['Brasilia','Peru']", "[-40,-80]"))

        # =========================================================
        # 5) AÇÃO: gerar YAMLs
        # =========================================================
        row_gen = ttk.Frame(root)
        row_gen.pack(fill="x", pady=(8, 0))
        ttk.Button(
            row_gen,
            text="Gerar YAML(s) no yaml_dir (todas combinações)",
            command=self._save_yaml_to_yamldir
        ).pack(side="left")


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
        # cria uma linha vazia e abre o editor
        iid = self.var_table.insert("", "end", values=("nova_var", "[]", "[]"))
        self.var_table.selection_set(iid)
        self.var_table.focus(iid)
        self._open_var_editor(iid, "nova_var", "[]", "[]")


    def _var_remove(self):
            sel = self.var_table.selection()
            for iid in sel:
                self.var_table.delete(iid)

    def _var_edit(self):
        sel = self.var_table.selection()
        if not sel:
            messagebox.showwarning("Variáveis", "Selecione uma variável para editar.")
            return
        iid = sel[0]
        var_key, tags_raw, vals_raw = self.var_table.item(iid, "values")
        self._open_var_editor(iid, var_key, tags_raw, vals_raw)

                
    def _open_var_editor(self, iid, var_key, tags_raw, vals_raw):
        dlg = tk.Toplevel(self)
        dlg.title(f"Editar variável: {var_key}")

        top = ttk.Frame(dlg)
        top.pack(fill="x", padx=10, pady=(10, 6))

        ttk.Label(top, text="Variável (placeholder no YAML):").pack(side="left")
        e_var = ttk.Entry(top, width=24)
        e_var.insert(0, str(var_key))
        e_var.pack(side="left", padx=(6, 0))

        # frame da tabela
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=6)

        # cabeçalho
        ttk.Label(frm, text="Tag (nome no arquivo)").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Valor (número ou path)").grid(row=0, column=1, sticky="w", padx=(10,0))




        rows = []  # lista de (entry_tag, entry_val)

        def _parse_list(s, default):
            s = (s or "").strip()
            if not s:
                return default
            try:
                obj = ast.literal_eval(s)
                if isinstance(obj, (list, tuple)):
                    return list(obj)
            except Exception:
                pass
            return default

        tags = _parse_list(tags_raw, [])
        vals = _parse_list(vals_raw, [])

        n = max(len(tags), len(vals), 1)
        while len(tags) < n: tags.append("")
        while len(vals) < n: vals.append("")

        def _add_row(t="", v=""):
            r = len(rows) + 1
            e1 = ttk.Entry(frm, width=18); e1.insert(0, str(t))
            e2 = ttk.Entry(frm, width=60); e2.insert(0, str(v))
            e1.grid(row=r, column=0, sticky="we", pady=2)
            e2.grid(row=r, column=1, sticky="we", pady=2, padx=(10,0))
            rows.append((e1, e2))

        for t, v in zip(tags, vals):
            _add_row(t, v)

        frm.grid_columnconfigure(1, weight=1)

        # =========================================================
        # GERAR AUTOMATICAMENTE (range / linspace)
        # =========================================================
        auto = ttk.LabelFrame(dlg, text="Gerar valores automaticamente")
        auto.pack(fill="x", padx=10, pady=(6, 0))

        mode = tk.StringVar(value="STEP")  # "STEP" | "NPTS"

        rowm = ttk.Frame(auto)
        rowm.pack(fill="x", pady=(4, 2))
        ttk.Radiobutton(rowm, text="Start/End/Step", variable=mode, value="STEP").pack(side="left")
        ttk.Radiobutton(rowm, text="Start/End/N pontos", variable=mode, value="NPTS").pack(side="left", padx=(12, 0))

        rowa = ttk.Frame(auto)
        rowa.pack(fill="x", pady=(2, 4))

        ttk.Label(rowa, text="start").pack(side="left")
        e_start = ttk.Entry(rowa, width=10)
        e_start.pack(side="left", padx=(6, 12))

        ttk.Label(rowa, text="end").pack(side="left")
        e_end = ttk.Entry(rowa, width=10)
        e_end.pack(side="left", padx=(6, 12))

        lbl3 = ttk.Label(rowa, text="step")
        lbl3.pack(side="left")
        e_third = ttk.Entry(rowa, width=10)
        e_third.pack(side="left", padx=(6, 12))

        ttk.Label(rowa, text="tag base").pack(side="left")
        e_tagbase = ttk.Entry(rowa, width=10)
        e_tagbase.insert(0, "V")
        e_tagbase.pack(side="left", padx=(6, 0))

        def _update_mode(*_):
            if mode.get() == "STEP":
                lbl3.config(text="step")
                if not e_third.get().strip():
                    e_third.delete(0, "end")
                    e_third.insert(0, "1")
            else:
                lbl3.config(text="N pontos")
                if not e_third.get().strip():
                    e_third.delete(0, "end")
                    e_third.insert(0, "5")

        mode.trace_add("write", _update_mode)
        _update_mode()

        def _clear_rows():
            while rows:
                e1, e2 = rows.pop()
                e1.destroy()
                e2.destroy()

        def _try_float(s: str):
            s = s.strip()
            if not s:
                raise ValueError("vazio")
            return float(s)

        def _format_num(x: float):
            # Se for quase inteiro, salva como int
            if abs(x - round(x)) < 1e-12:
                return str(int(round(x)))
            return str(x)

        def _generate_values():
            try:
                start = _try_float(e_start.get())
                end = _try_float(e_end.get())
            except Exception:
                messagebox.showwarning("Auto", "Preencha start e end (números).")
                return

            tagbase = e_tagbase.get().strip() or "V"

            try:
                third = _try_float(e_third.get()) if mode.get() == "STEP" else int(float(e_third.get()))
            except Exception:
                messagebox.showwarning("Auto", "Preencha step ou N pontos corretamente.")
                return

            vals = []
            if mode.get() == "STEP":
                step = third
                if step == 0:
                    messagebox.showwarning("Auto", "step não pode ser 0.")
                    return
                # range inclusivo (inclui end quando bater)
                x = start
                # direção
                if step > 0 and start > end:
                    messagebox.showwarning("Auto", "Com step > 0, start deve ser <= end.")
                    return
                if step < 0 and start < end:
                    messagebox.showwarning("Auto", "Com step < 0, start deve ser >= end.")
                    return

                # loop seguro
                max_iter = 20000
                it = 0
                if step > 0:
                    while x <= end + 1e-12 and it < max_iter:
                        vals.append(x)
                        x += step
                        it += 1
                else:
                    while x >= end - 1e-12 and it < max_iter:
                        vals.append(x)
                        x += step
                        it += 1
                if it >= max_iter:
                    messagebox.showwarning("Auto", "Geração interrompida (muitos pontos). Ajuste step.")
                    return
            else:
                npts = int(third)
                if npts <= 0:
                    messagebox.showwarning("Auto", "N pontos deve ser > 0.")
                    return
                if npts == 1:
                    vals = [start]
                else:
                    vals = [start + (end - start) * i / (npts - 1) for i in range(npts)]

            # Preenche a tabela Tag/Valor
            _clear_rows()
            for i, v in enumerate(vals, start=1):
                tag = f"{tagbase}{i}"
                _add_row(tag, _format_num(v))

        ttk.Button(auto, text="Gerar", command=_generate_values).pack(anchor="w", padx=10, pady=(0, 6))


        # botões de ação
        actions = ttk.Frame(dlg)
        actions.pack(fill="x", padx=10, pady=(6, 0))

        def add_line():
            _add_row("", "")

        def remove_last():
            if not rows:
                return
            e1, e2 = rows.pop()
            e1.destroy(); e2.destroy()

        def pick_files():
            files = filedialog.askopenfilenames(
                title=f"Selecionar arquivos para {var_key}",
                filetypes=[("All files", "*.*")]
            )
            if not files:
                return
            # limpa e cria linhas novas
            while rows:
                remove_last()
            for f in files:
                f = f.replace("\\", "/")
                tag = Path(f).stem  # sugestão; você pode editar
                _add_row(tag, f)

        ttk.Button(actions, text="Adicionar linha", command=add_line).pack(side="left")
        ttk.Button(actions, text="Remover última", command=remove_last).pack(side="left", padx=(6,0))
        ttk.Button(actions, text="Selecionar arquivos...", command=pick_files).pack(side="left", padx=(6,0))

        # OK / Cancel
        btns = ttk.Frame(dlg)
        btns.pack(fill="x", padx=10, pady=10)

        def ok():
            tags_out = []
            vals_out = []
            for e1, e2 in rows:
                t = e1.get().strip()
                v = e2.get().strip()
                if not t and not v:
                    continue
                tags_out.append(t)
                # tenta converter número se for número
                try:
                    vv = ast.literal_eval(v)
                except Exception:
                    vv = v
                vals_out.append(vv)

            if len(tags_out) != len(vals_out) or len(tags_out) == 0:
                messagebox.showwarning("Variáveis", "Tags e valores devem ter o mesmo tamanho e não podem ficar vazios.")
                return

            new_key = e_var.get().strip()
            if not new_key:
                messagebox.showwarning("Variáveis", "O nome da variável não pode ficar vazio.")
                return

            # opcional: evitar duplicatas
            for other in self.var_table.get_children():
                if other == iid:
                    continue
                v, _, _ = self.var_table.item(other, "values")
                if str(v).strip() == new_key:
                    messagebox.showwarning("Variáveis", f"Já existe uma variável chamada '{new_key}'.")
                    return

            self.var_table.item(iid, values=(new_key, str(tags_out), str(vals_out)))
            dlg.destroy()


        ttk.Button(btns, text="OK", command=ok).pack(side="left")
        ttk.Button(btns, text="Cancelar", command=dlg.destroy).pack(side="left", padx=(6,0))

