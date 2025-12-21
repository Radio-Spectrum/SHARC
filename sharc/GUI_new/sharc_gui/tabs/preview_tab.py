# Auto-split from original sharc_gui.py
from sharc_gui.common.imports import *  # noqa
from sharc_gui.common.plot_info import RESULT_FIELDNAME_TO_PLOT_INFO  # noqa

class PreviewTabTabMixin:
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

    def _add_polyline3d(self, ax3d, xy_points, z=0.0, color="k", lw=1.0):
            """Arestas de polígono/linha no plano z, sem preenchimento."""
            if not xy_points:
                return
            # fecha
            if xy_points[0] != xy_points[-1]:
                xy_points = xy_points + [xy_points[0]]
            segs = [((xy_points[i][0], xy_points[i][1], z),
                    (xy_points[i+1][0], xy_points[i+1][1], z))
                    for i in range(len(xy_points)-1)]
            self.ax3d.add_collection3d(Line3DCollection(segs, colors=[color], linewidths=lw))

    def _add_sector3d(self, ax3d, poly_xy, z=0.0, face_alpha=0.12, edge_color="tab:green"):
            """Adiciona o polígono do setor no plano z fixo."""
            verts3d = [(px, py, z) for (px, py) in poly_xy]
            pcoll = Poly3DCollection([verts3d], alpha=face_alpha, edgecolor=edge_color)
            pcoll.set_facecolor(edge_color)
            ax3d.add_collection3d(pcoll)

    def _add_wedge_outline3d(self, ax3d, x, y, r, az_deg, half_bw_deg=60, n=64, color="green", lw=1.0):
            """Contorno de um wedge (arco + 2 raios) no plano z=0 (fill=False)."""
            th0 = np.radians(az_deg - half_bw_deg)
            th1 = np.radians(az_deg + half_bw_deg)
            ths = np.linspace(th0, th1, n)
            arc_xy = [(x + r*np.cos(t), y + r*np.sin(t)) for t in ths]
            center = (x, y)
            # segmentos: centro->p0, arco, p_last->centro
            segs = []
            p0 = arc_xy[0]; pN = arc_xy[-1]
            segs.append(((center[0], center[1], 0.0), (p0[0], p0[1], 0.0)))
            for a, b in zip(arc_xy[:-1], arc_xy[1:]):
                segs.append(((a[0], a[1], 0.0), (b[0], b[1], 0.0)))
            segs.append(((pN[0], pN[1], 0.0), (center[0], center[1], 0.0)))
            self.ax3d.add_collection3d(Line3DCollection(segs, colors=[color], linewidths=lw))

    def _auto_xy_lim(self, xs, ys, margin=0.15):
            """Ajusta limites XY com margem fracionária."""
            if len(xs) == 0:
                return (-1, 1), (-1, 1)
            xmin, xmax = np.min(xs), np.max(xs)
            ymin, ymax = np.min(ys), np.max(ys)
            dx = xmax - xmin if xmax > xmin else 1.0
            dy = ymax - ymin if ymax > ymin else 1.0
            xpad = dx * margin
            ypad = dy * margin
            return (xmin - xpad, xmax + xpad), (ymin - ypad, ymax + ypad)

    def _draw_bs_post(self, ax3d, x, y, h, color="tab:blue", lw=2.0):
            """Desenha o 'postinho' (mastro) da BS em (x,y) com altura h."""
            ax3d.plot([x, x], [y, y], [0, h], color=color, lw=lw)

    def _draw_country_borders(self):
            """Draw country borders from a shapefile onto the globe."""
            if not self.show_borders.get() or not HAS_PYSHP:
                return
            shp_path = self.path_shp.get()
            if not os.path.isfile(shp_path):
                return
            try:
                r = pyshp.Reader(shp_path)
                for sr in r.shapeRecords():
                    shp = sr.shape
                    pts = shp.points
                    if not pts:
                        continue
                    parts = list(shp.parts) + [len(pts)]
                    for i in range(len(parts) - 1):
                        sub = pts[parts[i]:parts[i+1]]
                        if len(sub) < 2:
                            continue
                        lons = [p[0] for p in sub]
                        lats = [p[1] for p in sub]
                        x, y, z = lla_to_ecef(lats, lons, 0.0)
                        self.ax3d.plot(x, y, z, lw=0.35, color="k", alpha=0.55, zorder=5, antialiased=True)
            except Exception:
                pass

    def _draw_preview_3d(self):
            import numpy as np
            from matplotlib import cm, colors
            topo_type = (self.topo_type.get() or "").strip()
            self.ax3d.cla()
            if topo_type == "Macro_countries":
                # Terra – grid esférico
                a = WGS84_A * 0.98
                u = np.linspace(0, 2*np.pi, 720)
                v = np.linspace(0, np.pi, 360)
                X = a*np.outer(np.cos(u), np.sin(v))
                Y = a*np.outer(np.sin(u), np.sin(v))
                Z = a*np.outer(np.ones_like(u), np.cos(v))

                # Posição do Spacecraft e Earth Station (alvo de boresight)
                ss_alt = self._num_or_str(self.v_alt.get())
                ss_lat = self._num_or_str(self.v_fix_lat.get())
                ss_lon = self._num_or_str(self.v_fix_lon.get())
                es_alt = self._num_or_str(self.v_es_alt.get())
                es_lat = self._num_or_str(self.v_es_lat.get())
                es_lon = self._num_or_str(self.v_es_lon.get())

                sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)
                ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)  # Earth Station (boresight alvo)

                show_map = bool(self.var_show_gainmap.get())

                if show_map:
                    # ---------- Linha de Visada (LoS) ----------
                    # Condição de visibilidade do ponto P (X,Y,Z) a partir de S=(sx,sy,sz):
                    # LoS <=> S•P > a^2   (produto escalar com raio ao ponto)
                    # Usa tolerância pequena para estabilidade numérica
                    dotSP = X * sx + Y * sy + Z * sz
                    los_mask = dotSP > (a*a * (1.0 + 1e-12))

                    # ---------- Vetores para off-axis ----------
                    # boresight: S -> ES
                    b = np.array([ex - sx, ey - sy, ez - sz], dtype=float)
                    b /= np.linalg.norm(b)

                    RX = X - sx
                    RY = Y - sy
                    RZ = Z - sz
                    Rnorm = np.sqrt(RX*RX + RY*RY + RZ*RZ)
                    RX /= Rnorm; RY /= Rnorm; RZ /= Rnorm

                    # Ângulo off-axis (graus) = arccos( dot(R_hat, b_hat) )
                    cospsi = RX*b[0] + RY*b[1] + RZ*b[2]
                    cospsi = np.clip(cospsi, -1.0, 1.0)
                    psi_deg = np.degrees(np.arccos(cospsi))  # (nu x nv)

                    # ---------- Ganho S.672 ----------
                    ant = self._make_s672_antenna()
                    gain = ant.calculate_gain(off_axis_angle_vec=psi_deg.ravel()).reshape(psi_deg.shape)

                    # Onde NÃO há LoS, ganho = -inf (como você pediu)
                    gain = gain.astype(float, copy=True)
                    gain[~los_mask] = -np.inf

                    # ---------- Normalização de cores (ignora -inf) ----------
                    try:
                        vmin_txt = (self.var_gain_vmin.get() or "auto").strip().lower()
                        vmax_txt = (self.var_gain_vmax.get() or "auto").strip().lower()
                    except Exception:
                        vmin_txt, vmax_txt = "auto", "auto"

                    # valores finitos para definir escala
                    finite = np.isfinite(gain)
                    if vmin_txt in ("auto","") or vmax_txt in ("auto",""):
                        if finite.any():
                            gfinite = gain[finite]
                            auto_vmin = float(np.nanmin(gfinite))
                            auto_vmax = float(np.nanmax(gfinite))
                        else:
                            # fallback seguro
                            auto_vmin, auto_vmax = 0.0, 1.0
                    vmin = auto_vmin if (vmin_txt in ("auto","")) else float(vmin_txt)
                    vmax = auto_vmax if (vmax_txt in ("auto","")) else float(vmax_txt)
                    if vmin >= vmax:
                        vmax = vmin + 1.0

                    norm = colors.Normalize(vmin=vmin, vmax=vmax)

                    # Mapeia cores; pontos sem LoS ficam transparentes (alpha=0)
                    facecolors = cm.viridis(norm(np.where(np.isfinite(gain), gain, vmin)))
                    alpha = np.where(los_mask, 1.0, 0.0)
                    facecolors[..., -1] = facecolors[..., -1] * alpha

                    # ---------- Desenha superfície colorida (opaca onde há LoS) ----------
                    self.ax3d.plot_surface(
                        X, Y, Z,
                        rstride=6, cstride=6,
                        facecolors=facecolors,
                        linewidth=0,
                        antialiased=False,
                        shade=False,
                        zorder=1
                    )

                    # Colorbar (baseada só nos finitos)
                    mappable = cm.ScalarMappable(norm=norm, cmap=cm.viridis)
                    mappable.set_array([])
                    if hasattr(self, "_gain_cbar") and self._gain_cbar:
                        try:
                            self._gain_cbar.remove()
                        except Exception:
                            pass
                    self._gain_cbar = self.fig3d.colorbar(mappable, ax=self.ax3d, shrink=0.8, pad=0.02)
                    self._gain_cbar.set_label("Ganho (dBi)")

                else:
                    # Terra opaca em cor sólida
                    self.ax3d.plot_surface(
                        X, Y, Z,
                        rstride=6, cstride=6,
                        color="#dbe7ff",
                        alpha=1.0,
                        edgecolor="none",
                        zorder=1
                    )
                    if hasattr(self, "_gain_cbar") and self._gain_cbar:
                        try:
                            self._gain_cbar.remove()
                        except Exception:
                            pass
                        self._gain_cbar = None

                # Contornos (se você tiver essa função)
                self._draw_country_borders()

                # COUNTRIES preview (se aplicável)
                if HAS_TOPO and TopologyCountries and ParametersCountries:
                    population_shp = "" if self.topo_raster_enc.get() == "Uniforme" else (self.path_raster.get().strip() or "")
                    try:
                        countries = [c.strip() for c in self.txt_countries.get("1.0","end").splitlines() if c.strip()]
                        params = ParametersCountries(
                            country_names=countries,
                            num_bs_total=int(float(self.topo_num_bs.get())),
                            rng_seed=int(float(self.topo_rng.get())),
                            cell_radius=float(self.topo_cell_radius.get()),
                            countries_shapefile=self.path_shp.get(),
                            population_raster=population_shp,
                            raster_encoding=self.raster_encoding.get(),
                            sedac_palette_mode=self.sedac_mode.get(),
                            sedac_min=float(self.sedac_min.get()),
                            sedac_max=float(self.sedac_max.get()),
                            pixel_area_method=self.pixel_area_method.get(),
                            dist_type=self.topo_dist_type.get(),
                            fixed_azimuth=None,
                        )
                        geoconv = GeometryConverter()
                        geoconv.set_reference(float(self.topo_c_lat.get()), float(self.topo_c_lon.get()), float(self.topo_c_alt.get()))
                        topo = TopologyCountries(params, geoconv).calculate_coordinates()
                        x, y, z = lla_to_ecef(topo.lats, topo.lons, np.zeros_like(topo.lats) + 500)
                        self.ax3d.scatter(x, y, z, c="tab:red", s=6, depthshade=False, label="BS (countries)", zorder=10)
                    except Exception as e:
                        messagebox.showwarning("Preview Countries", f"Falha ao renderizar COUNTRIES:\n{e}")

                # Marcadores de Spacecraft e Earth Station
                try:
                    # Spacecraft
                    self.ax3d.scatter([sx],[sy],[sz], c="tab:purple", s=60, marker="^", depthshade=False, label="Spacecraft (FIXED)", zorder=7)
                    # Earth Station
                    self.ax3d.scatter([ex],[ey],[ez], c="tab:blue", s=24, marker="o", depthshade=False, label="Earth Station", zorder=7)
                    # Link/boresight (S -> ES)
                    self.ax3d.plot([sx, ex], [sy, ey], [sz, ez], color="tab:purple", lw=1.6, alpha=0.9, label="Pointing to ES", zorder=6)
                except Exception:
                    pass

                # Caixa/labels
                R = WGS84_A + 4.0e7/6.0
                self.ax3d.set_xlim([-R, R]); self.ax3d.set_ylim([-R, R]); self.ax3d.set_zlim([-R, R])
                self.ax3d.set_box_aspect([1,1,1])
                self.ax3d.set_xlabel("X [m]"); self.ax3d.set_ylabel("Y [m]"); self.ax3d.set_zlabel("Z [m]")
                self.ax3d.legend(loc="upper right")
                self.fig3d.tight_layout()
                self.canvas3d.draw()
                return
            try:
                import matplotlib as mpl
                # um quadradão default; limites serão ajustados depois
                grid = np.linspace(-1, 1, 2)
                Xg, Yg = np.meshgrid(grid, grid)
                Zg = np.zeros_like(Xg)
                # só para dar referência: linhas do contorno
                # (opcional: manter vazio e só usar posts/“pizzas”)
            except Exception:
                pass

            # --- Seleção de topologia e cálculo das coordenadas (usa suas classes)
            xs = ys = azs = None
            cell_radius = None
            bs_height = float(self._num_or_str(self.bs_height.get()) or 18.0)  # altura da BS (m)

            if topo_type == "MACROCELL":
                from sharc.topology.topology_macrocell import TopologyMacrocell
                d = float(self._num_or_str(self.macro_intersite.get()) or 1500.0)
                nc = int(self._num_or_str(self.macro_clusters.get()) or 1)
                topo = TopologyMacrocell(d, nc)
                topo.calculate_coordinates()  # fornece self.x, self.y, self.azimuth

                xs = np.asarray(topo.x)
                ys = np.asarray(topo.y)
                azs = np.asarray(topo.azimuth)

                # Raio do hex (padrão que você indicou)
                r = d / 3.0

                # Altura do "postinho"
                bs_height = float(self._num_or_str(self.bs_height.get()) or 18.0)

                # Desenha os hexágonos (arestas) como no seu plot 2D
                all_x, all_y = [], []
                for x, y, az in zip(xs, ys, azs):
                    se = [[x, y]]
                    angle = int(az - 60)
                    for _ in range(6):
                        se.append([
                            se[-1][0] + r * math.cos(math.radians(angle)),
                            se[-1][1] + r * math.sin(math.radians(angle)),
                        ])
                        angle += 60
                    # Arestas em z=0 (sem fill)
                    self._add_polyline3d(self.ax3d, se, z=0.0, color="k", lw=1.0)
                    all_x.append(x); all_y.append(y)

                # Macro cell base stations (pontos)
                self.ax3d.scatter(xs, ys, np.zeros_like(xs), color="k", s=18, depthshade=False)

                # Postinhos (mastros)
                for x, y in zip(xs, ys):
                    self._draw_bs_post(self.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

                # Escala igual em x,y,z (mastros ficam "baixos")
                self._set_equal_3d(self.ax3d, np.array(all_x), np.array(all_y), z_top=bs_height, margin=0.12)

                self.ax3d.set_xlabel("x [m]")
                self.ax3d.set_ylabel("y [m]")
                self.ax3d.set_zlabel("z [m]  (altura)")
                self.ax3d.set_title("Topologia: MACROCELL (hexágonos + mastros)")
                self.canvas3d.draw_idle()

                return

            elif topo_type == "SINGLE_BS":
                from sharc.topology.topology_single_base_station import TopologySingleBaseStation  # :contentReference[oaicite:5]{index=5}
                cr = float(self._num_or_str(self.sbs_cell_radius.get()) or 100.0)
                nc = int(self._num_or_str(self.sbs_clusters.get()) or 1)

                # azimute: aceita lista "0,120,240" ou string/literal
                az_text = (self.sbs_azimuth.get() or "").strip()
                if az_text == "":
                    az_param = None
                else:
                    try:
                        az_param = [float(x.strip()) for x in az_text.split(",")]
                    except Exception:
                        az_param = az_text  # pode ser "random"
                topo = TopologySingleBaseStation(cr, nc, azimuth=az_param)
                topo.calculate_coordinates()  # gera x,y,azimuth  :contentReference[oaicite:6]{index=6}
                xs, ys, azs = topo.x, topo.y, topo.azimuth
                cell_radius = cr  # usamos no desenho da “pizza”

            elif topo_type == "HOTSPOT":
                from sharc.topology.topology_hotspot import TopologyHotspot  # gera x,y,azimuth dos hotspots
                from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
                d  = float(self._num_or_str(self.hotspot_intersite.get()) or 1500.0)
                nc = int(self._num_or_str(self.hotspot_clusters.get()) or 1)

                p = ParametersHotspot()
                if self.hotspot_num_per_cell.get():
                    p.num_hotspots_per_cell = int(self._num_or_str(self.hotspot_num_per_cell.get()))
                if self.hotspot_max_dist_ue.get():
                    p.max_dist_hotspot_ue = float(self._num_or_str(self.hotspot_max_dist_ue.get()))
                if self.hotspot_min_dist_bs.get():
                    p.min_dist_bs_hotspot = float(self._num_or_str(self.hotspot_min_dist_bs.get()))

                topo = TopologyHotspot(p, d, nc)
                topo.calculate_coordinates()  # <-- pode levantar o erro do loop infinito
                if topo.x.size == 0:
                    messagebox.showwarning(
                        "Hotspot: parâmetros inviáveis",
                        "Loop infinito ao criar hotspots.\n\n"
                        "Tente reduzir 'num_hotspots_per_cell' ou aumentar 'intersite_distance'.\n\n"
                    )
                    return

                xs, ys, azs = np.asarray(topo.x), np.asarray(topo.y), np.asarray(topo.azimuth)
                cell_radius  = float(p.max_dist_hotspot_ue)
                bs_height    = float(self._num_or_str(self.bs_height.get()) or 18.0)

                # ---------- HEXÁGONOS DE REFERÊNCIA DO MACROCELL ----------
                # Se TopologyHotspot expõe o macrocell, usamos diretamente:
                macro = getattr(topo, "macrocell", None)
                if macro is not None and hasattr(macro, "x") and hasattr(macro, "y") and hasattr(macro, "azimuth"):
                    mx, my, maz = np.asarray(macro.x), np.asarray(macro.y), np.asarray(macro.azimuth)
                    # raio do hex conforme seu padrão: r = ISD/3
                    r_hex = d / 3.0
                    # desenha hex exatamente com o algoritmo incremental do seu plot 2D
                    for x0, y0, az0 in zip(mx, my, maz):
                        se = [[x0, y0]]
                        angle = int(az0 - 60)
                        for _ in range(6):
                            se.append([
                                se[-1][0] + r_hex * np.cos(np.radians(angle)),
                                se[-1][1] + r_hex * np.sin(np.radians(angle)),
                            ])
                            angle += 60
                        self._add_polyline3d(self.ax3d, se, z=0.0, color="0.25", lw=0.9)

                # ---------- HOTSPOTS (pontos) ----------
                self.ax3d.scatter(xs, ys, np.zeros_like(xs), color="g", edgecolors="w",
                                linewidths=0.5, s=18, depthshade=False)

                # ---------- COBERTURA (WEDGE: fill=False) ----------
                for xh, yh, a in zip(xs, ys, azs):
                    self._add_wedge_outline3d(self.ax3d, xh, yh, cell_radius, a, half_bw_deg=60,
                                            color="green", lw=1.0)

                # ---------- POSTINHOS (mastros nos hotspots) ----------
                for xh, yh in zip(xs, ys):
                    self._draw_bs_post(self.ax3d, xh, yh, bs_height, color="tab:blue", lw=2.0)

                # ---------- Limites e rótulos ----------
                if xs.size:
                    self._set_equal_3d(self.ax3d, xs, ys, z_top=bs_height, margin=0.12)
                self.ax3d.set_xlabel("x [m]"); self.ax3d.set_ylabel("y [m]"); self.ax3d.set_zlabel("z [m] (altura)")
                self.ax3d.set_title("Topologia: HOTSPOT (hex macro + hotspots + wedges)")
                self.canvas3d.draw_idle()
                return


            else:
                # fallback seguro
                self.ax3d.text2D(0.05, 0.95, f"type '{topo_type}' não suportado no preview 3D", transform=self.ax3d.transAxes)
                self.canvas3d.draw_idle()
                return

            # --- Desenho: posts (mastros) e “pizzas” (quando aplicável)
            if xs is None or len(xs) == 0:
                self.ax3d.text2D(0.05, 0.95, "Sem coordenadas para desenhar.", transform=self.ax3d.transAxes)
                self.canvas3d.draw_idle()
                return

            xs = np.asarray(xs)
            ys = np.asarray(ys)
            if azs is None:
                azs = np.zeros_like(xs)
            else:
                azs = np.asarray(azs)

            # posts (um por BS)
            for x, y in zip(xs, ys):
                self._draw_bs_post(self.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

            # “pizzas” para HOTSPOT e SINGLE_BS (e opcionalmente para MACROCELL)
            if cell_radius is None:
                # nada a fazer
                pass
            else:
                # half beamwidth padrão de 60° como nos módulos 2D
                hbw = 60.0
                edge = "tab:green" if topo_type in ("HOTSPOT", "SINGLE_BS") else "0.6"
                for x, y, az in zip(xs, ys, azs):
                    poly_xy = self._sector_polygon_xy(x, y, cell_radius, az, half_bw_deg=hbw)
                    self._add_sector3d(self.ax3d, poly_xy, z=0.0, face_alpha=0.10, edge_color=edge)

            # --- Ajustes de limites/estética
            (xlim, ylim) = self._auto_xy_lim(xs, ys, margin=0.18)
            self.ax3d.set_xlim(xlim)
            self.ax3d.set_ylim(ylim)
            # eixo Z: um pouco acima da altura para sobrar espaço
            self.ax3d.set_zlim(0, max(1.0, bs_height) * 1.25)

            self.ax3d.set_xlabel("x [m]")
            self.ax3d.set_ylabel("y [m]")
            self.ax3d.set_zlabel("z [m]  (altura)")
            self.ax3d.set_title(f"Topologia: {topo_type} (preview 3D)")

            self.canvas3d.draw_idle()

    def _make_s672_antenna(self):
            """
            Constrói uma AntennaS672 a partir dos controles da UI (ganho de pico, L_s e 3 dB).
            """
            param = ParametersAntennaS672()
            # seus vars (ajuste os nomes se forem diferentes):
            # ganho de pico [dBi]
            param.antenna_gain = float(self.v_ant_gain.get())
            # largura de feixe 3 dB (atenção: o objeto original usa 'antenna_3_dB' ou 'antenna_3_dB_bw';
            # mapeie para 'antenna_3_dB' se necessário)
            param.antenna_3_dB = float(self.v_s672_3db.get())
            param.antenna_3_dB_bw = float(self.v_s672_3db.get())
            # L_s (-20, -25, -30 dB)
            param.antenna_l_s = float(self.v_s672_ls.get())
            return AntennaS672(param)

    def _on_scroll_3d(self, event):
            """
            Zoom pelo scroll do mouse.
            - Windows/macOS: event.delta > 0 (zoom in), < 0 (zoom out)
            - Linux/X11: event.num == 4 (up -> in), 5 (down -> out)
            """
            # fator base (suave). maior => zoom mais “forte”
            base = 1.12
            direction = 0
            try:
                if hasattr(event, "num") and event.num in (4, 5):
                    # Linux
                    direction = -1 if event.num == 4 else 1
                else:
                    # Windows/macOS
                    direction = -1 if getattr(event, "delta", 0) > 0 else 1
            except Exception:
                direction = 1

            factor = (1.0 / base) if direction < 0 else base
            self._zoom_preview_3d(factor)

    def _save_image_3d(self):
            suggested = f"topology3d_{time.strftime('%Y%m%d_%H%M%S')}.png"
            path = filedialog.asksaveasfilename(
                title="Salvar imagem",
                defaultextension=".png",
                initialfile=suggested,
                filetypes=[("PNG", "*.png"), ("All files", "*.*")]
            )
            if not path:
                return
            self.fig3d.savefig(path, dpi=180, bbox_inches="tight")
            messagebox.showinfo("OK", f"Imagem salva em:\n{path}")

    def _save_yaml_dialog_multicombos(self):
            combos = self._collect_var_combos()
            if combos is None:
                return
            root = self._current_yaml()
            initdir = self.var_yaml_dir.get() or os.getcwd()
            os.makedirs(initdir, exist_ok=True)
            path = filedialog.asksaveasfilename(
                title="Escolha um nome (usaremos apenas a pasta selecionada)",
                defaultextension=".yaml",
                initialdir=initdir,
                initialfile=(self.var_prefix.get() or "scenario") + ".yaml",
                filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
            )
            if not path:
                return
            outdir = os.path.dirname(path)
            os.makedirs(outdir, exist_ok=True)
            self._write_yaml_combos(root, outdir, combos)
            self.var_yaml_dir.set(outdir)
            messagebox.showinfo("OK", f"YAML(s) salvo(s) em:\n{outdir}")

    def _sector_polygon_xy(self, x, y, radius, az_deg, half_bw_deg=60, n=48):
            """Gera os pontos (x,y) do setor (wedge) no plano z=0."""
            th0 = np.radians(az_deg - half_bw_deg)
            th1 = np.radians(az_deg + half_bw_deg)
            ths = np.linspace(th0, th1, n)
            xs = x + radius * np.cos(ths)
            ys = y + radius * np.sin(ths)
            # polígono: vértice central -> arco -> volta ao centro
            poly_xy = [(x, y)] + list(zip(xs, ys)) + [(x, y)]
            return poly_xy

    def _set_equal_3d(self, ax3d, xs, ys, z_top, margin=0.10):
            """
            Força mesma escala em x,y,z. z vai de 0 até z_top (baixo visual dos mastros).
            O cubo tem aresta = max(dx, dy, z_top), com margem.
            """
            xs = np.asarray(xs); ys = np.asarray(ys)
            xmin, xmax = float(np.min(xs)), float(np.max(xs))
            ymin, ymax = float(np.min(ys)), float(np.max(ys))
            dx = max(1e-9, xmax - xmin)
            dy = max(1e-9, ymax - ymin)
            span = max(dx, dy, float(z_top))
            pad = span * margin
            cx = 0.5 * (xmax + xmin)
            cy = 0.5 * (ymax + ymin)
            ax3d.set_xlim(cx - 0.5*span - pad, cx + 0.5*span + pad)
            ax3d.set_ylim(cy - 0.5*span - pad, cy + 0.5*span + pad)
            ax3d.set_zlim(0.0, span + pad)
            # exige Matplotlib 3.3+:
            try:
                ax3d.set_box_aspect((1, 1, 1))
            except Exception:
                pass

    def _update_yaml_preview(self):
            root = self._current_yaml()
            text = build_yaml_text(root)
            self.txt_yaml.delete("1.0", tk.END)
            self.txt_yaml.insert(tk.END, text)

    def _zoom_preview_3d(self, factor):
            """Zoom no 3D: factor>1 dá zoom out; <1 dá zoom in."""
            try:
                # Preferível quando disponível (Matplotlib 3D antigo)
                if hasattr(self.ax3d, "dist"):
                    self.ax3d.dist = max(1, float(self.ax3d.dist) * float(factor))
                    self.canvas3d.draw_idle()
                    return
            except Exception:
                pass

            # Fallback: escala limites X/Y/Z ao redor do centro (robusto)
            import numpy as np
            for getter, setter in [(self.ax3d.get_xlim3d, self.ax3d.set_xlim3d),
                                (self.ax3d.get_ylim3d, self.ax3d.set_ylim3d),
                                (self.ax3d.get_zlim3d, self.ax3d.set_zlim3d)]:
                lo, hi = getter()
                c = 0.5*(lo + hi)
                half = 0.5*(hi - lo)*factor
                setter(c - half, c + half)
            self.canvas3d.draw_idle()

