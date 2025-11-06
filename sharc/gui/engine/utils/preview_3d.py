"""
3D preview drawing helpers. This module draws a simple Earth sphere and
example satellite markers. It is intentionally lightweight and purely
visual — the real application should feed satellite/topology data.
"""

from tkinter import messagebox
from typing import Any
import numpy as np
import math
import core.topology_control as tc
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from core.geodesy import lla_to_ecef, WGS84_A, WGS84_F
from core._tools_ import _num_or_str
from utils.drawer_tool import _draw_country_borders

from sharc.topology.topology_countries import TopologyCountries, ParametersCountries
from sharc.support.sharc_geom_countries import GeometryConverter



def _draw_preview_3d(root):

    def draw_country_borders():
        _draw_country_borders(root)

    topo_type = (root.topo_type.get() or "").strip()
    root.ax3d.cla()
    if topo_type == "Macro_countries":
        # Terra – grid esférico
        a = WGS84_A * 0.98
        u = np.linspace(0, 2*np.pi, 720)
        v = np.linspace(0, np.pi, 360)
        X = a*np.outer(np.cos(u), np.sin(v))
        Y = a*np.outer(np.sin(u), np.sin(v))
        Z = a*np.outer(np.ones_like(u), np.cos(v))

        # Posição do Spacecraft e Earth Station (alvo de boresight)
        ss_alt = _num_or_str(root, root.v_alt.get())
        ss_lat = _num_or_str(root, root.v_fix_lat.get())
        ss_lon = _num_or_str(root, root.v_fix_lon.get())
        es_alt = _num_or_str(root, root.v_es_alt.get())
        es_lat = _num_or_str(root, root.v_es_lat.get())
        es_lon = _num_or_str(root, root.v_es_lon.get())

        sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)
        ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)  # Earth Station (boresight alvo)

        show_map = bool(root.var_show_gainmap.get())

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
            ant = root._make_s672_antenna()
            gain = ant.calculate_gain(off_axis_angle_vec=psi_deg.ravel()).reshape(psi_deg.shape)

            # Onde NÃO há LoS, ganho = -inf (como você pediu)
            gain = gain.astype(float, copy=True)
            gain[~los_mask] = -np.inf

            # ---------- Normalização de cores (ignora -inf) ----------
            try:
                vmin_txt = (root.var_gain_vmin.get() or "auto").strip().lower()
                vmax_txt = (root.var_gain_vmax.get() or "auto").strip().lower()
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
            root.ax3d.plot_surface(
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
            if hasattr(root, "_gain_cbar") and root._gain_cbar:
                try:
                    root._gain_cbar.remove()
                except Exception:
                    pass
            root._gain_cbar = root.fig3d.colorbar(mappable, ax=root.ax3d, shrink=0.8, pad=0.02)
            root._gain_cbar.set_label("Ganho (dBi)")

        else:
            # Terra opaca em cor sólida
            root.ax3d.plot_surface(
                X, Y, Z,
                rstride=6, cstride=6,
                color="#dbe7ff",
                alpha=1.0,
                edgecolor="none",
                zorder=1
            )
            if hasattr(root, "_gain_cbar") and root._gain_cbar:
                try:
                    root._gain_cbar.remove()
                except Exception:
                    pass
                root._gain_cbar = None

        # Contornos (se você tiver essa função)
        draw_country_borders()

        # COUNTRIES preview (se aplicável)
        if tc.HAS_TOPO and TopologyCountries and ParametersCountries:
            population_shp = "" if root.topo_raster_enc.get() == "Uniforme" else (root.path_raster.get().strip() or "")
            try:
                countries = [c.strip() for c in root.txt_countries.get("1.0","end").splitlines() if c.strip()]
                params = ParametersCountries(
                    country_names=countries,
                    num_bs_total=int(float(root.topo_num_bs.get())),
                    rng_seed=int(float(root.topo_rng.get())),
                    cell_radius=float(root.topo_cell_radius.get()),
                    countries_shapefile=root.path_shp.get(),
                    population_raster=population_shp,
                    raster_encoding=root.raster_encoding.get(),
                    sedac_palette_mode=root.sedac_mode.get(),
                    sedac_min=float(root.sedac_min.get()),
                    sedac_max=float(root.sedac_max.get()),
                    pixel_area_method=root.pixel_area_method.get(),
                    dist_type=root.topo_dist_type.get(),
                    fixed_azimuth=None,
                )
                geoconv = GeometryConverter()
                geoconv.set_reference(float(root.topo_c_lat.get()), float(root.topo_c_lon.get()), float(root.topo_c_alt.get()))
                topo = TopologyCountries(params, geoconv).calculate_coordinates()
                x, y, z = lla_to_ecef(topo.lats, topo.lons, np.zeros_like(topo.lats) + 500)
                root.ax3d.scatter(x, y, z, c="tab:red", s=6, depthshade=False, label="BS (countries)", zorder=10)
            except Exception as e:
                messagebox.showwarning("Preview Countries", f"Falha ao renderizar COUNTRIES:\n{e}")

        # Marcadores de Spacecraft e Earth Station
        try:
            # Spacecraft
            root.ax3d.scatter([sx],[sy],[sz], c="tab:purple", s=60, marker="^", depthshade=False, label="Spacecraft (FIXED)", zorder=7)
            # Earth Station
            root.ax3d.scatter([ex],[ey],[ez], c="tab:blue", s=24, marker="o", depthshade=False, label="Earth Station", zorder=7)
            # Link/boresight (S -> ES)
            root.ax3d.plot([sx, ex], [sy, ey], [sz, ez], color="tab:purple", lw=1.6, alpha=0.9, label="Pointing to ES", zorder=6)
        except Exception:
            pass

        # Caixa/labels
        R = WGS84_A + 4.0e7/6.0
        root.ax3d.set_xlim([-R, R]); root.ax3d.set_ylim([-R, R]); root.ax3d.set_zlim([-R, R])
        root.ax3d.set_box_aspect([1,1,1])
        root.ax3d.set_xlabel("X [m]"); root.ax3d.set_ylabel("Y [m]"); root.ax3d.set_zlabel("Z [m]")
        root.ax3d.legend(loc="upper right")
        root.fig3d.tight_layout()
        root.canvas3d.draw()
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
    bs_height = float(root._num_or_str(root.bs_height.get()) or 18.0)  # altura da BS (m)

    if topo_type == "MACROCELL":
        from sharc.topology.topology_macrocell import TopologyMacrocell
        d = float(root._num_or_str(root.macro_intersite.get()) or 1500.0)
        nc = int(root._num_or_str(root.macro_clusters.get()) or 1)
        topo = TopologyMacrocell(d, nc)
        topo.calculate_coordinates()  # fornece root.x, root.y, root.azimuth

        xs = np.asarray(topo.x)
        ys = np.asarray(topo.y)
        azs = np.asarray(topo.azimuth)

        # Raio do hex (padrão que você indicou)
        r = d / 3.0

        # Altura do "postinho"
        bs_height = float(root._num_or_str(root.bs_height.get()) or 18.0)

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
            root._add_polyline3d(root.ax3d, se, z=0.0, color="k", lw=1.0)
            all_x.append(x); all_y.append(y)

        # Macro cell base stations (pontos)
        root.ax3d.scatter(xs, ys, np.zeros_like(xs), color="k", s=18, depthshade=False)

        # Postinhos (mastros)
        for x, y in zip(xs, ys):
            root._draw_bs_post(root.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

        # Escala igual em x,y,z (mastros ficam "baixos")
        root._set_equal_3d(root.ax3d, np.array(all_x), np.array(all_y), z_top=bs_height, margin=0.12)

        root.ax3d.set_xlabel("x [m]")
        root.ax3d.set_ylabel("y [m]")
        root.ax3d.set_zlabel("z [m]  (altura)")
        root.ax3d.set_title("Topologia: MACROCELL (hexágonos + mastros)")
        root.canvas3d.draw_idle()

        return

    elif topo_type == "SINGLE_BS":
        from sharc.topology.topology_single_base_station import TopologySingleBaseStation
        cr = float(root._num_or_str(root.sbs_cell_radius.get()) or 100.0)
        nc = int(root._num_or_str(root.sbs_clusters.get()) or 1)

        # azimute: aceita lista "0,120,240" ou string/literal
        az_text = (root.sbs_azimuth.get() or "").strip()
        if az_text == "":
            az_param = None
        else:
            try:
                az_param = [float(x.strip()) for x in az_text.split(",")]
            except Exception:
                az_param = az_text  # pode ser "random"
        topo = TopologySingleBaseStation(cr, nc, azimuth=az_param)
        topo.calculate_coordinates()  # gera x,y,azimuth
        xs, ys, azs = topo.x, topo.y, topo.azimuth
        cell_radius = cr  # usamos no desenho da “pizza”

    elif topo_type == "HOTSPOT":
        from sharc.topology.topology_hotspot import TopologyHotspot  # gera x,y,azimuth dos hotspots
        from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
        d  = float(root._num_or_str(root.hotspot_intersite.get()) or 1500.0)
        nc = int(root._num_or_str(root.hotspot_clusters.get()) or 1)

        p = ParametersHotspot()
        if root.hotspot_num_per_cell.get():
            p.num_hotspots_per_cell = int(root._num_or_str(root.hotspot_num_per_cell.get()))
        if root.hotspot_max_dist_ue.get():
            p.max_dist_hotspot_ue = float(root._num_or_str(root.hotspot_max_dist_ue.get()))
        if root.hotspot_min_dist_bs.get():
            p.min_dist_bs_hotspot = float(root._num_or_str(root.hotspot_min_dist_bs.get()))

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
        bs_height    = float(root._num_or_str(root.bs_height.get()) or 18.0)

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
                root._add_polyline3d(root.ax3d, se, z=0.0, color="0.25", lw=0.9)

        # ---------- HOTSPOTS (pontos) ----------
        root.ax3d.scatter(xs, ys, np.zeros_like(xs), color="g", edgecolors="w",
                        linewidths=0.5, s=18, depthshade=False)

        # ---------- COBERTURA (WEDGE: fill=False) ----------
        for xh, yh, a in zip(xs, ys, azs):
            root._add_wedge_outline3d(root.ax3d, xh, yh, cell_radius, a, half_bw_deg=60,
                                     color="green", lw=1.0)

        # ---------- POSTINHOS (mastros nos hotspots) ----------
        for xh, yh in zip(xs, ys):
            root._draw_bs_post(root.ax3d, xh, yh, bs_height, color="tab:blue", lw=2.0)

        # ---------- Limites e rótulos ----------
        if xs.size:
            root._set_equal_3d(root.ax3d, xs, ys, z_top=bs_height, margin=0.12)
        root.ax3d.set_xlabel("x [m]"); root.ax3d.set_ylabel("y [m]"); root.ax3d.set_zlabel("z [m] (altura)")
        root.ax3d.set_title("Topologia: HOTSPOT (hex macro + hotspots + wedges)")
        root.canvas3d.draw_idle()
        return

    else:
        # fallback seguro
        root.ax3d.text2D(0.05, 0.95, f"type '{topo_type}' não suportado no preview 3D", transform=root.ax3d.transAxes)
        root.canvas3d.draw_idle()
        return

    # --- Desenho: posts (mastros) e “pizzas” (quando aplicável)
    if xs is None or len(xs) == 0:
        root.ax3d.text2D(0.05, 0.95, "Sem coordenadas para desenhar.", transform=root.ax3d.transAxes)
        root.canvas3d.draw_idle()
        return

    xs = np.asarray(xs)
    ys = np.asarray(ys)
    if azs is None:
        azs = np.zeros_like(xs)
    else:
        azs = np.asarray(azs)

    # posts (um por BS)
    for x, y in zip(xs, ys):
        root._draw_bs_post(root.ax3d, x, y, bs_height, color="tab:blue", lw=2.0)

    # “pizzas” para HOTSPOT e SINGLE_BS (e opcionalmente para MACROCELL)
    if cell_radius is None:
        # nada a fazer
        pass
    else:
        # half beamwidth padrão de 60° como nos módulos 2D
        hbw = 60.0
        edge = "tab:green" if topo_type in ("HOTSPOT", "SINGLE_BS") else "0.6"
        for x, y, az in zip(xs, ys, azs):
            poly_xy = root._sector_polygon_xy(x, y, cell_radius, az, half_bw_deg=hbw)
            root._add_sector3d(root.ax3d, poly_xy, z=0.0, face_alpha=0.10, edge_color=edge)

    # --- Ajustes de limites/estética
    (xlim, ylim) = root._auto_xy_lim(xs, ys, margin=0.18)
    root.ax3d.set_xlim(xlim)
    root.ax3d.set_ylim(ylim)
    # eixo Z: um pouco acima da altura para sobrar espaço
    root.ax3d.set_zlim(0, max(1.0, bs_height) * 1.25)

    root.ax3d.set_xlabel("x [m]")
    root.ax3d.set_ylabel("y [m]")
    root.ax3d.set_zlabel("z [m]  (altura)")
    root.ax3d.set_title(f"Topologia: {topo_type} (preview 3D)")

    root.canvas3d.draw_idle()