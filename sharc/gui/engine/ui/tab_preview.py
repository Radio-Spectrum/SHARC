 def _tab_preview(self, root):
        left = ttk.Frame(root); right = ttk.Frame(root)
        left.pack(side="left", fill="both", expand=True); right.pack(side="right", fill="y")

        # 3D figure
        self.fig3d = plt.figure(figsize=(6.6, 6.6))
        self.ax3d = self.fig3d.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

        # Colormap
        ttk.Checkbutton(
            right,
            text="Mostrar mapa de ganho (S.672)",
            variable=self.var_show_gainmap,
            command=self._draw_preview_3d
        ).pack(fill="x", pady=(0,8))

        # (Opcional) limites de cor do colormap:
        frm_gain = ttk.Frame(right); frm_gain.pack(fill="x", pady=(0,8))
        ttk.Label(frm_gain, text="vmin (dBi):").pack(side="left")
        e_vmin = ttk.Entry(frm_gain, textvariable=self.var_gain_vmin, width=7); e_vmin.pack(side="left", padx=(4,8))
        ttk.Label(frm_gain, text="vmax (dBi):").pack(side="left")
        e_vmax = ttk.Entry(frm_gain, textvariable=self.var_gain_vmax, width=7); e_vmax.pack(side="left", padx=(4,0))

        # Scroll do mouse
        w3d = self.canvas3d.get_tk_widget()
        # Windows/macOS: <MouseWheel> com delta +/-;
        w3d.bind("<MouseWheel>", self._on_scroll_3d)
        # Linux: rolagem vem como botões 4 (up) e 5 (down)
        w3d.bind("<Button-4>", self._on_scroll_3d)
        w3d.bind("<Button-5>", self._on_scroll_3d)
        # Borders toggle
        self.show_borders = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Mostrar fronteiras dos países", variable=self.show_borders).pack(anchor="w", pady=(4,6))

        ttk.Button(right, text="Gerar preview 3D", command=self._draw_preview_3d).pack(fill="x", pady=(4,4))
        ttk.Button(right, text="Zoom +", command=lambda: self._zoom_preview_3d(1/1.15)).pack(fill="x", pady=(0,4))
        ttk.Button(right, text="Zoom -", command=lambda: self._zoom_preview_3d(1.15)).pack(fill="x", pady=(0,8))
        ttk.Button(right, text="Salvar imagem...", command=self._save_image_3d).pack(fill="x", pady=(4,4))
        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(right, text="Atualizar YAML (preview)", command=self._update_yaml_preview).pack(fill="x", pady=(4,4))
        ttk.Button(right, text="Salvar YAML(s)...", command=self._save_yaml_dialog_multicombos).pack(fill="x", pady=(4,4))
        ttk.Label(right, text="Prévia do YAML (sem expandir combinações):").pack(anchor="w", pady=(10,2))
        self.txt_yaml = tk.Text(right, width=44, height=28, wrap="none")
        self.txt_yaml.pack(fill="both", expand=True)

        self._draw_preview_3d()
        self._update_yaml_preview()
