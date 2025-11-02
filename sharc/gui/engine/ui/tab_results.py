def _tab_results(self, root):
        # Lado esquerdo: controles / Lado direito: figura
        left = ttk.Frame(root); right = ttk.Frame(root)
        left.pack(side="left", fill="y"); right.pack(side="right", fill="both", expand=True)

        # ---- Seleção de pastas ----
        ttk.Label(left, text="Pastas de resultados (comparação):").pack(anchor="w", pady=(6,2))
        frm_dirs = ttk.Frame(left); frm_dirs.pack(fill="x")
        self.lb_dirs = tk.Listbox(frm_dirs, height=6, selectmode="extended")
        self.lb_dirs.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frm_dirs, orient="vertical", command=self.lb_dirs.yview)
        sb.pack(side="right", fill="y"); self.lb_dirs.config(yscrollcommand=sb.set)

        def _add_dir():
            init = str(Path(self.var_outdir.get() or Path.cwd()))
            path = filedialog.askdirectory(initialdir=init, title="Selecionar pasta de resultados")
            if path and path not in self.res_dirs:
                self.res_dirs.append(path)
                self.lb_dirs.insert("end", path)
                self._draw_results_plots()

        def _add_current_outdir():
            path = str(Path(self.var_outdir.get()))
            if path and path not in self.res_dirs:
                self.res_dirs.append(path)
                self.lb_dirs.insert("end", path)
                self._draw_results_plots()

        def _remove_dir():
            sel = list(self.lb_dirs.curselection())[::-1]
            for idx in sel:
                path = self.lb_dirs.get(idx)
                self.res_dirs.remove(path)
                self.lb_dirs.delete(idx)
            self._draw_results_plots()

        frm_btn = ttk.Frame(left); frm_btn.pack(fill="x", pady=(4,8))
        ttk.Button(frm_btn, text="Adicionar pasta…", command=_add_dir).pack(side="left", padx=(0,4))
        ttk.Button(frm_btn, text="Usar output_dir atual", command=_add_current_outdir).pack(side="left", padx=(0,4))
        ttk.Button(frm_btn, text="Remover selecionadas", command=_remove_dir).pack(side="left")

        # ---- Grid de subplots ----
        frm_grid = ttk.LabelFrame(left, text="Layout de subfiguras")
        frm_grid.pack(fill="x", pady=(6,6))
        ttk.Label(frm_grid, text="Linhas").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.var_rows, width=5, command=self._draw_results_plots).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frm_grid, text="Colunas").grid(row=0, column=2, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.var_cols, width=5, command=self._draw_results_plots).grid(row=0, column=3, padx=4, pady=4)

        # ---- Configuração por subfigura (até _max_axes)
        frm_cfg = ttk.LabelFrame(left, text="Configuração de cada subfigura")
        frm_cfg.pack(fill="x", pady=(6,8))
        self._subplot_cfg_rows = []
        for i in range(self._max_axes):
            r = ttk.Frame(frm_cfg); r.pack(fill="x", pady=2)
            ttk.Label(r, text=f"{i+1:02d}").pack(side="left", padx=(2,6))

            # MÉTRICA
            cb_field = ttk.Combobox(r, values=self.result_fields, width=34)
            cb_field.set(self._axes_cfg[i]["field"])
            cb_field.pack(side="left", padx=(0,6))

            # CDF/CCDF
            cb_mode = ttk.Combobox(r, values=["CDF","CCDF"], width=6)
            cb_mode.set(self._axes_cfg[i]["mode"])
            cb_mode.pack(side="left", padx=(0,6))

            # Y-SCALE (Linear/Log)
            cb_ys = ttk.Combobox(r, values=["Linear","Log"], width=7)
            cb_ys.set(self._axes_cfg[i]["yscale"])
            cb_ys.pack(side="left", padx=(0,6))

            # REFERÊNCIAS (%, ex.: 5,10,50)
            ttk.Label(r, text="Refs(%)").pack(side="left")
            ent_refs = ttk.Entry(r, width=10)
            ent_refs.insert(0, self._axes_cfg[i]["refs"])
            ent_refs.pack(side="left", padx=(4,6))

            def _mk_upd(idx, combof, combom, comboys, entryrefs):
                def _upd(*_):
                    self._axes_cfg[idx]["field"]  = combof.get()
                    self._axes_cfg[idx]["mode"]   = combom.get()
                    self._axes_cfg[idx]["yscale"] = comboys.get()
                    self._axes_cfg[idx]["refs"]   = entryrefs.get()
                    self._draw_results_plots()
                return _upd

            upd = _mk_upd(i, cb_field, cb_mode, cb_ys, ent_refs)
            cb_field.bind("<<ComboboxSelected>>", upd)
            cb_mode.bind("<<ComboboxSelected>>", upd)
            cb_ys.bind("<<ComboboxSelected>>", upd)
            ent_refs.bind("<FocusOut>", upd)
            ent_refs.bind("<Return>", upd)

            self._subplot_cfg_rows.append((cb_field, cb_mode, cb_ys, ent_refs))

        # ---- Atualização automática ----
        frm_auto = ttk.LabelFrame(left, text="Atualização")
        frm_auto.pack(fill="x", pady=(6,8))
        ttk.Checkbutton(frm_auto, text="Atualização automática", variable=self.var_auto_update,
                        command=self._schedule_auto_update).pack(side="left", padx=(4,8))
        ttk.Label(frm_auto, text="Período (ms):").pack(side="left")
        ttk.Spinbox(frm_auto, from_=500, to=10000, increment=500, textvariable=self.var_update_period_ms, width=8,
                    command=self._schedule_auto_update).pack(side="left", padx=(4,8))
        ttk.Button(frm_auto, text="Atualizar agora", command=self._draw_results_plots).pack(side="left")

        # ---- Exportar figura ----
        frm_export = ttk.LabelFrame(left, text="Exportar")
        frm_export.pack(fill="x", pady=(6,8))
        ttk.Label(frm_export, text="DPI:").pack(side="left", padx=(6,4))
        self.var_export_dpi = tk.IntVar(value=200)
        ttk.Spinbox(frm_export, from_=100, to=600, increment=50, textvariable=self.var_export_dpi, width=6).pack(side="left", padx=(0,8))
        ttk.Button(frm_export, text="Exportar figura…", command=self._export_results_fig).pack(side="left")
        # ---- Escala / Exportar ----
        frm_extras = ttk.LabelFrame(left, text="Escala e Exportação")
        frm_extras.pack(fill="x", pady=(6,8))

        # Escala log no X
        ttk.Checkbutton(
            frm_extras, text="Escala log no eixo X",
            variable=self.var_xlog,
            command=self._draw_results_plots
        ).pack(fill="x", padx=4, pady=(2,6))

        # Exportar figura
        fexp = ttk.Frame(frm_extras); fexp.pack(fill="x", pady=(2,4))
        ttk.Label(fexp, text="Formato:").pack(side="left")
        ttk.Combobox(
            fexp, textvariable=self.var_export_fmt,
            values=["PNG","SVG","PDF"], width=6, state="readonly"
        ).pack(side="left", padx=(4,8))
        ttk.Label(fexp, text="DPI:").pack(side="left")
        ttk.Spinbox(
            fexp, from_=72, to=600, increment=10, width=6,
            textvariable=self.var_export_dpi
        ).pack(side="left", padx=(4,8))
        #ttk.Button(fexp, text="Exportar figura…", command=self._export_results_figure).pack(side="left")

        # ---- Linhas de referência (globais) ----
        frm_refs = ttk.LabelFrame(left, text="Linhas de referência (todas as subfiguras)")
        frm_refs.pack(fill="x", pady=(6,8))

        ref_row = ttk.Frame(frm_refs); ref_row.pack(fill="x", pady=(2,4))
        ttk.Label(ref_row, text="x=").pack(side="left")
        self._ref_x_entry = ttk.Entry(ref_row, width=10)
        self._ref_x_entry.pack(side="left", padx=(4,8))
        ttk.Label(ref_row, text="rótulo:").pack(side="left")
        self._ref_label_entry = ttk.Entry(ref_row, width=18)
        self._ref_label_entry.pack(side="left", padx=(4,8))
        ttk.Button(ref_row, text="Adicionar", command=self._ref_add).pack(side="left")

        # lista de linhas
        list_frame = ttk.Frame(frm_refs); list_frame.pack(fill="x", pady=(2,4))
        self.lb_refs = tk.Listbox(list_frame, height=5, selectmode="extended")
        self.lb_refs.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(list_frame, orient="vertical", command=self.lb_refs.yview)
        sb2.pack(side="right", fill="y")
        self.lb_refs.config(yscrollcommand=sb2.set)

        btns = ttk.Frame(frm_refs); btns.pack(fill="x")
        ttk.Button(btns, text="Remover selecionadas", command=self._ref_remove).pack(side="left")
        ttk.Button(btns, text="Aplicar (redesenhar)", command=self._draw_results_plots).pack(side="left", padx=(6,0))

        # ---- Figura de resultados (matplotlib)
        self.fig_res = plt.figure(figsize=(7.8, 6.2))
        self.canvas_res = FigureCanvasTkAgg(self.fig_res, master=right)
        self.canvas_res.get_tk_widget().pack(fill="both", expand=True)

        self._draw_results_plots()
        self._schedule_auto_update()
