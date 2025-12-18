import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from matplotlib import cm, colors
import math
import time
import os
from typing import Optional, Tuple, Any, Dict, List

# Imports do projeto (Ajuste conforme sua estrutura de pastas)
from utils import lla_to_ecef, build_yaml_text
from config import WGS84_A

# --- Imports Opcionais Centralizados ---
HAS_TOPO = True
try:
    from sharc.topology.topology_countries import TopologyCountries
    from sharc.antenna.antenna_s672 import AntennaS672
    from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
    from sharc.topology.topology_macrocell import TopologyMacrocell
    from sharc.topology.topology_hotspot import TopologyHotspot
    from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation
except ImportError:
    HAS_TOPO = False

HAS_PYSHP = True
try:
    import shapefile as pyshp
except ImportError:
    HAS_PYSHP = False


# ==============================================================================
# 1. MOTOR DE CÁLCULO (MODEL)
# Responsável pela matemática e dados. Independente da Interface Gráfica.
# ==============================================================================
class TopologyEngine:
    def __init__(self):
        self._sphere_cache: Optional[Tuple[np.ndarray,
                                           np.ndarray, np.ndarray]] = None

    def get_sphere_geometry(self, resolution_u=360, resolution_v=180):
        """
        Gera a malha da esfera terrestre.
        Resolução 360x180 garante visual redondo sem serrilhados excessivos.
        """
        if self._sphere_cache is None:
            # WGS84_A * 0.98 para evitar z-fighting com as linhas de fronteira
            a = WGS84_A * 0.98
            u = np.linspace(0, 2 * np.pi, resolution_u)
            v = np.linspace(0, np.pi, resolution_v)
            X = a * np.outer(np.cos(u), np.sin(v))
            Y = a * np.outer(np.sin(u), np.sin(v))
            Z = a * np.outer(np.ones_like(u), np.cos(v))
            self._sphere_cache = (X, Y, Z)
        return self._sphere_cache

    def calculate_gain_map(self, sx, sy, sz, ex, ey, ez, gain_params: Dict[str, float]):
        """Calcula a matriz de ganho para a superfície esférica (S.672)."""
        if not HAS_TOPO:
            return None, None

        X, Y, Z = self.get_sphere_geometry()
        a = WGS84_A * 0.98

        # 1. Máscara de Visada (Line of Sight)
        dotSP = X * sx + Y * sy + Z * sz
        # Se o produto escalar for maior que R^2, está visível (simplificação esférica)
        los_mask = dotSP > (a * a * (1.0 + 1e-9))

        # 2. Vetor Boresight (Satélite -> Estação Terrena)
        b = np.array([ex - sx, ey - sy, ez - sz], dtype=float)
        norm_b = np.linalg.norm(b)
        if norm_b > 0:
            b /= norm_b

        # 3. Vetores do Satélite para cada ponto da grade
        RX, RY, RZ = X - sx, Y - sy, Z - sz
        Rnorm = np.sqrt(RX**2 + RY**2 + RZ**2)
        Rnorm[Rnorm == 0] = 1.0  # Evita divisão por zero

        # 4. Ângulo Off-Axis (Cosseno)
        cospsi = (RX/Rnorm)*b[0] + (RY/Rnorm)*b[1] + (RZ/Rnorm)*b[2]
        cospsi = np.clip(cospsi, -1.0, 1.0)
        psi_deg = np.degrees(np.arccos(cospsi))

        # 5. Cálculo do Ganho usando biblioteca SHARC
        try:
            p = ParametersAntennaS672()
            p.antenna_gain = gain_params.get('gain', 0.0)
            p.antenna_3_dB = gain_params.get('3db', 0.0)
            p.antenna_3_dB_bw = gain_params.get('3db', 0.0)
            p.antenna_l_s = gain_params.get('ls', 0.0)
            ant = AntennaS672(p)

            gain = ant.calculate_gain(
                off_axis_angle_vec=psi_deg.ravel()).reshape(psi_deg.shape)
            gain = gain.astype(float, copy=True)

            # Aplica máscara: pontos sem visada ganham -infinito (transparente depois)
            gain[~los_mask] = -np.inf
            return gain, los_mask
        except Exception:
            return None, None

    def get_borders_geometry(self, shp_path: str) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Lê shapefile otimizado para plotagem."""
        geometries = []
        if not HAS_PYSHP or not os.path.isfile(shp_path):
            return geometries

        try:
            r = pyshp.Reader(shp_path)
            for shp in r.iterShapes():
                if not shp.points:
                    continue
                parts = list(shp.parts) + [len(shp.points)]
                for i in range(len(parts) - 1):
                    pts = shp.points[parts[i]:parts[i+1]]
                    if len(pts) < 2:
                        continue
                    # Decimate: pega 1 a cada 3 pontos para performance
                    arr = np.array(pts)[::3]
                    if len(arr) < 2:
                        continue
                    x, y, z = lla_to_ecef(arr[:, 1], arr[:, 0], 0.0)
                    geometries.append((x, y, z))
        except Exception:
            pass
        return geometries

    def compute_local_topology(self, topo_type: str, params: Dict[str, Any]):
        """Retorna coordenadas locais baseadas no tipo selecionado."""
        xs, ys, azs, radius, bg_hex = [], [], [], None, []

        if not HAS_TOPO:
            return xs, ys, azs, radius, bg_hex

        try:
            if topo_type == "MACROCELL":
                t = TopologyMacrocell(params['intersite'], params['clusters'])
                t.calculate_coordinates()
                xs, ys, azs = np.asarray(t.x), np.asarray(
                    t.y), np.asarray(t.azimuth)
                radius = params['intersite'] / 3.0

            elif topo_type == "HOTSPOT":
                p = ParametersHotspot()
                if 'num_per_cell' in params:
                    p.num_hotspots_per_cell = params['num_per_cell']
                if 'max_dist_ue' in params:
                    p.max_dist_hotspot_ue = params['max_dist_ue']
                if 'min_dist_bs' in params:
                    p.min_dist_bs_hotspot = params['min_dist_bs']

                t = TopologyHotspot(p, params['intersite'], params['clusters'])
                t.calculate_coordinates()
                xs, ys, azs = np.asarray(t.x), np.asarray(
                    t.y), np.asarray(t.azimuth)
                radius = float(p.max_dist_hotspot_ue)

                # Extrair background macro se existir
                if hasattr(t, "macrocell"):
                    bg_hex = list(
                        zip(t.macrocell.x, t.macrocell.y, t.macrocell.azimuth))

            elif topo_type == "SINGLE_BS":
                t = TopologySingleBaseStation(
                    params['radius'], params['clusters'], azimuth=params['azimuth'])
                t.calculate_coordinates()
                xs, ys, azs = t.x, t.y, t.azimuth
                radius = params['radius']

        except ImportError:
            pass

        return xs, ys, azs, radius, bg_hex


# ==============================================================================
# 2. INTERFACE E CONTROLE (VIEW / CONTROLLER)
# Gerencia Widgets, Matplotlib Canvas e solicita dados ao Engine.
# ==============================================================================
class PreviewTab:
    def __init__(self, app: Any, parent_frame: tk.Widget):
        self.app = app
        self.frame = parent_frame

        # Instancia o motor de lógica
        self.engine = TopologyEngine()

        # Referência para a colorbar (para poder remover depois)
        self._gain_cbar = None

        self._ensure_app_variables()
        self._build_ui()

    def _ensure_app_variables(self):
        """Garante que as variáveis do Tkinter existam no App pai."""
        defaults = {
            'show_borders': (tk.BooleanVar, True),
            'var_show_gainmap': (tk.BooleanVar, False),
            'var_gain_vmin': (tk.StringVar, ""),
            'var_gain_vmax': (tk.StringVar, ""),
            'topo_type': (tk.StringVar, "")
        }
        for k, (cls, v) in defaults.items():
            if not hasattr(self.app, k):
                setattr(self.app, k, cls(value=v))

    def _build_ui(self):
        left = ttk.Frame(self.frame)
        right = ttk.Frame(self.frame)
        left.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        right.pack(side="right", fill="y", padx=5, pady=5)

        # Plot 3D
        self.fig3d = plt.figure(figsize=(6, 6), dpi=100)
        self.ax3d = self.fig3d.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)
        self._setup_mouse_events()

        # Painel de Controle
        self._build_control_panel(right)

        # Inicialização
        self._update_yaml_preview()

    def _setup_mouse_events(self):
        w = self.canvas3d.get_tk_widget()
        w.bind("<MouseWheel>", self._on_scroll)  # Windows
        w.bind("<Button-4>", self._on_scroll)   # Linux
        w.bind("<Button-5>", self._on_scroll)   # Linux

    def _build_control_panel(self, parent):
        # Grupo Visualização
        lf = ttk.LabelFrame(parent, text="Visualização 3D")
        lf.pack(fill="x", pady=(0, 10))

        ttk.Checkbutton(lf, text="Heatmap Ganho (S.672)", variable=self.app.var_show_gainmap,
                        command=self._draw_preview_3d).pack(fill="x", padx=5)

        f_g = ttk.Frame(lf)
        f_g.pack(fill="x", padx=5, pady=2)
        ttk.Label(f_g, text="Min/Max (dBi):").pack(side="left")
        ttk.Entry(f_g, textvariable=self.app.var_gain_vmin,
                  width=4).pack(side="left", padx=2)
        ttk.Entry(f_g, textvariable=self.app.var_gain_vmax,
                  width=4).pack(side="left", padx=2)

        ttk.Checkbutton(lf, text="Fronteiras Países", variable=self.app.show_borders,
                        command=self._draw_preview_3d).pack(anchor="w", padx=5, pady=5)

        # Ações
        ttk.Button(parent, text="🔄 Atualizar 3D",
                   command=self._draw_preview_3d).pack(fill="x", pady=2)

        f_z = ttk.Frame(parent)
        f_z.pack(fill="x")
        ttk.Button(f_z, text="Zoom +", command=lambda: self._zoom(1/1.15)
                   ).pack(side="left", fill="x", expand=True)
        ttk.Button(f_z, text="Zoom -", command=lambda: self._zoom(1.15)
                   ).pack(side="right", fill="x", expand=True)

        ttk.Button(parent, text="💾 Salvar Imagem",
                   command=self._save_image).pack(fill="x", pady=5)

        # YAML Preview
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text="YAML Preview:").pack(anchor="w")
        self.txt_yaml = tk.Text(
            parent, width=40, height=20, font=("Consolas", 8))
        self.txt_yaml.pack(fill="both", expand=True)
        ttk.Button(parent, text="Atualizar YAML",
                   command=self._update_yaml_preview).pack(fill="x")
        ttk.Button(parent, text="Salvar YAML...",
                   command=self.app.save_yaml_dialog_multicombos).pack(fill="x")

    # ---------------- Lógica de Desenho (Dispatcher) ----------------

    def _draw_preview_3d(self):
        """Gerencia o que será desenhado baseado no tipo de topologia."""
        topo_type = (self.app.topo_type.get() or "").strip()
        self.ax3d.clear()

        # Limpa colorbar antiga se existir
        if self._gain_cbar:
            try:
                self._gain_cbar.remove()
            except:
                pass
            self._gain_cbar = None

        if topo_type == "Macro_countries":
            self._draw_global_scene()
        else:
            self._draw_local_scene(topo_type)

        self.ax3d.set_xlabel("x [m]")
        self.ax3d.set_ylabel("y [m]")
        self.ax3d.set_zlabel("z [m]")
        self.canvas3d.draw_idle()

    # ---------------- Cenário Global ----------------

    def _draw_global_scene(self):
        # 1. Obter Geometria
        X, Y, Z = self.engine.get_sphere_geometry()

        # 2. Obter Dados
        def _g(v): return float(v.get()) if v.get() else 0.0
        sx, sy, sz = lla_to_ecef(_g(self.app.v_fix_lat), _g(
            self.app.v_fix_lon), _g(self.app.v_alt))
        ex, ey, ez = lla_to_ecef(_g(self.app.v_es_lat), _g(
            self.app.v_es_lon), _g(self.app.v_es_alt))

        # 3. Renderizar (Heatmap ou Simples)
        if self.app.var_show_gainmap.get() and HAS_TOPO:
            g_params = {
                'gain': _g(self.app.v_ant_gain), '3db': _g(self.app.v_s672_3db),
                'ls': _g(self.app.v_s672_ls)
            }
            gain_data, mask = self.engine.calculate_gain_map(
                sx, sy, sz, ex, ey, ez, g_params)

            if gain_data is not None:
                self._plot_heatmap_surface(X, Y, Z, gain_data, mask)
            else:
                self._plot_simple_sphere(X, Y, Z)
        else:
            self._plot_simple_sphere(X, Y, Z)

        # 4. Fronteiras e Marcadores
        if self.app.show_borders.get():
            borders = self.engine.get_borders_geometry(self.app.path_shp.get())
            for (bx, by, bz) in borders:
                self.ax3d.plot(bx, by, bz, lw=0.4, color="k",
                               alpha=0.5, zorder=5)

        self.ax3d.scatter([sx], [sy], [sz], c="purple",
                          marker="^", s=60, label="Sat", zorder=10)
        self.ax3d.scatter([ex], [ey], [ez], c="blue",
                          marker="o", s=30, label="ES", zorder=10)
        self.ax3d.plot([sx, ex], [sy, ey], [sz, ez],
                       c="purple", ls="--", alpha=0.7, zorder=9)

        # Limites
        lim = WGS84_A * 1.5
        self.ax3d.set_xlim(-lim, lim)
        self.ax3d.set_ylim(-lim, lim)
        self.ax3d.set_zlim(-lim, lim)
        self.ax3d.set_box_aspect([1, 1, 1])

    def _plot_simple_sphere(self, X, Y, Z):
        """Desenha a esfera com sombreamento para parecer 3D."""
        self.ax3d.plot_surface(
            X, Y, Z,
            rstride=2, cstride=2,  # Resolução fina
            color="#dbe7ff",
            alpha=1.0,
            shade=True,      # ESSENCIAL: Ativa luz/sombra
            linewidth=0,     # ESSENCIAL: Remove grade preta
            antialiased=False
        )

    def _plot_heatmap_surface(self, X, Y, Z, gain, mask):
        vmin, vmax = self._parse_vmin_vmax(gain)
        norm = colors.Normalize(vmin=vmin, vmax=vmax)
        fcolors = cm.viridis(norm(np.where(np.isfinite(gain), gain, vmin)))

        # Transparência onde não há visada
        fcolors[..., -1] *= np.where(mask, 1.0, 0.0)

        self.ax3d.plot_surface(
            X, Y, Z,
            rstride=2, cstride=2,
            facecolors=fcolors,
            shade=True,      # Heatmap com volume
            linewidth=0
        )

        m = cm.ScalarMappable(norm=norm, cmap=cm.viridis)
        m.set_array([])
        self._gain_cbar = self.fig3d.colorbar(
            m, ax=self.ax3d, shrink=0.7, pad=0.1)
        self._gain_cbar.set_label("Ganho (dBi)")

    # ---------------- Cenário Local ----------------

    def _draw_local_scene(self, topo_type):
        def _g(v): return float(v.get()) if v.get() else 0.0
        def _gi(v): return int(v.get()) if v.get() else 1

        params = {}
        if topo_type == "MACROCELL":
            params = {'intersite': _g(self.app.macro_intersite), 'clusters': _gi(
                self.app.macro_clusters)}
        elif topo_type == "HOTSPOT":
            params = {
                'intersite': _g(self.app.hotspot_intersite), 'clusters': _gi(self.app.hotspot_clusters),
                'num_per_cell': _gi(self.app.hotspot_num_per_cell), 'max_dist_ue': _g(self.app.hotspot_max_dist_ue),
                'min_dist_bs': _g(self.app.hotspot_min_dist_bs)
            }
        elif topo_type == "SINGLE_BS":
            az_str = self.app.sbs_azimuth.get()
            try:
                az = [float(x) for x in az_str.split(
                    ",")] if "," in az_str else float(az_str)
            except:
                az = 0.0
            params = {'radius': _g(self.app.sbs_cell_radius), 'clusters': _gi(
                self.app.sbs_clusters), 'azimuth': az}

        xs, ys, azs, radius, bg_hex = self.engine.compute_local_topology(
            topo_type, params)
        bs_h = _g(self.app.bs_height) or 18.0

        # Background (para hotspot)
        if bg_hex:
            for (bx, by, baz) in bg_hex:
                self._draw_hexagon(bx, by, baz, params.get(
                    'intersite', 1500)/3.0, color="0.8")

        # Células
        if xs is not None and len(xs) > 0:
            for x, y, az in zip(xs, ys, azs):
                self._draw_bs_post(x, y, bs_h)
                if topo_type == "MACROCELL":
                    self._draw_hexagon(x, y, az, radius)
                elif topo_type in ("HOTSPOT", "SINGLE_BS"):
                    self._draw_wedge(x, y, radius, az)

            # Zoom automático local
            span = max(np.ptp(xs), np.ptp(ys), bs_h) * \
                1.2 if len(xs) > 1 else radius * 4
            mid_x, mid_y = np.mean(xs), np.mean(ys)
            self.ax3d.set_xlim(mid_x-span/2, mid_x+span/2)
            self.ax3d.set_ylim(mid_y-span/2, mid_y+span/2)
            self.ax3d.set_zlim(0, span)
            self.ax3d.set_box_aspect([1, 1, 1])

    # ---------------- Primitivas Gráficas ----------------

    def _draw_bs_post(self, x, y, h):
        self.ax3d.plot([x, x], [y, y], [0, h], color="tab:blue", lw=2)

    def _draw_hexagon(self, x, y, az, r, color="k"):
        pts = []
        angle = int(az - 60)
        for _ in range(7):
            rad = math.radians(angle)
            pts.append((x + r*math.cos(rad), y + r*math.sin(rad), 0.0))
            angle += 60
        self.ax3d.add_collection3d(Line3DCollection(
            [pts], colors=color, linewidths=1))

    def _draw_wedge(self, x, y, r, az):
        th = np.radians(np.linspace(az-60, az+60, 24))
        arc_x, arc_y = x + r*np.cos(th), y + r*np.sin(th)
        xs = np.concatenate(([x], arc_x, [x]))
        ys = np.concatenate(([y], arc_y, [y]))
        self.ax3d.plot(xs, ys, np.zeros_like(xs), color="green", lw=1)

    def _parse_vmin_vmax(self, data):
        try:
            v_min = float(self.app.var_gain_vmin.get())
            v_max = float(self.app.var_gain_vmax.get())
            return v_min, v_max
        except:
            valid = data[np.isfinite(data)]
            return (float(valid.min()), float(valid.max())) if valid.size else (0, 1)

    # ---------------- IO & Utilitários ----------------

    def _update_yaml_preview(self):
        if hasattr(self.app, 'current_yaml_dict'):
            txt = build_yaml_text(self.app.current_yaml_dict())
            self.txt_yaml.delete("1.0", tk.END)
            self.txt_yaml.insert(tk.END, txt)

    def _save_image(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.fig3d.savefig(path, dpi=200, bbox_inches='tight')

    def _zoom(self, factor):
        ax = self.ax3d
        # Compatibilidade com versões novas e antigas do Matplotlib
        if hasattr(ax, 'dist'):
            ax.dist = max(1, ax.dist * factor)
        else:
            xl, yl, zl = ax.get_xlim3d(), ax.get_ylim3d(), ax.get_zlim3d()

            def scl(l):
                c = (l[0]+l[1])/2
                w = (l[1]-l[0])*factor/2
                return (c-w, c+w)
            ax.set_xlim3d(scl(xl))
            ax.set_ylim3d(scl(yl))
            ax.set_zlim3d(scl(zl))
        self.canvas3d.draw_idle()

    def _on_scroll(self, event):
        delta = -1 if (getattr(event, 'delta', 0) >
                       0 or getattr(event, 'num', 0) == 4) else 1
        self._zoom(1.15 if delta > 0 else 1/1.15)
