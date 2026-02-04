import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from matplotlib import cm, colors
import math
import time
import os

# Project Imports
from utils import lla_to_ecef, build_yaml_text
from config import WGS84_A

# ====== Optional Imports (Topology / Shapefile) ======
HAS_TOPO = True
try:
    from sharc.topology.topology_countries import TopologyCountries, ParametersCountries
    from sharc.support.sharc_geom_countries import GeometryConverter
    from sharc.antenna.antenna_s672 import AntennaS672
    from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
except ImportError:
    HAS_TOPO = False

HAS_PYSHP = True
try:
    import shapefile as pyshp
except ImportError:
    HAS_PYSHP = False


class PreviewTab:
    """
    Manages the 'Preview' tab, providing 3D visualization of the simulation scenario
    and a text preview of the generated YAML configuration.

    This class handles two main visualization modes:
    1. Global (Macro_countries): Renders the Earth, Satellite, and Earth Station in ECEF coordinates.
    2. Local (Macro/Hotspot): Renders hexagonal cell sites and antenna sectors.
    """

    def __init__(self, app, parent_frame):
        """
        Initializes the PreviewTab.

        Args:
            app: Instance of the main App class (main.py).
            parent_frame: The widget where this tab will be drawn.
        """
        self.app = app
        self.frame = parent_frame

        # Ensure control variables exist
        if not hasattr(self.app, 'show_borders'):
            self.app.show_borders = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        """Constructs the user interface layouts for the 3D canvas and side controls."""
        left = ttk.Frame(self.frame)
        right = ttk.Frame(self.frame)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y")

        # ---- 3D Figure ----
        self.fig3d = plt.figure(figsize=(6.6, 6.6))
        self.ax3d = self.fig3d.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=left)
        self.canvas3d.get_tk_widget().pack(fill="both", expand=True)

        # ---- Controls (Right Side) ----

        # Colormap Toggle
        ttk.Checkbutton(
            right,
            text="Show Gain Map (S.672)",
            variable=self.app.var_show_gainmap,
            command=self._draw_preview_3d
        ).pack(fill="x", pady=(0, 8))

        # Gain Limits
        frm_gain = ttk.Frame(right)
        frm_gain.pack(fill="x", pady=(0, 8))
        ttk.Label(frm_gain, text="vmin (dBi):").pack(side="left")
        e_vmin = ttk.Entry(
            frm_gain, textvariable=self.app.var_gain_vmin, width=7)
        e_vmin.pack(side="left", padx=(4, 8))
        ttk.Label(frm_gain, text="vmax (dBi):").pack(side="left")
        e_vmax = ttk.Entry(
            frm_gain, textvariable=self.app.var_gain_vmax, width=7)
        e_vmax.pack(side="left", padx=(4, 0))

        # Borders Checkbox
        ttk.Checkbutton(right, text="Show Country Borders",
                        variable=self.app.show_borders).pack(anchor="w", pady=(4, 6))

        # Action Buttons
        ttk.Button(right, text="Generate 3D Preview",
                   command=self._draw_preview_3d).pack(fill="x", pady=(4, 4))
        ttk.Button(right, text="Zoom +",
                   command=lambda: self._zoom_preview_3d(1/1.15)).pack(fill="x", pady=(0, 4))
        ttk.Button(right, text="Zoom -",
                   command=lambda: self._zoom_preview_3d(1.15)).pack(fill="x", pady=(0, 8))
        ttk.Button(right, text="Save Image...",
                   command=self._save_image_3d).pack(fill="x", pady=(4, 4))

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)

        # YAML Preview
        ttk.Button(right, text="Update YAML (Preview)",
                   command=self._update_yaml_preview).pack(fill="x", pady=(4, 4))
        ttk.Button(right, text="Save YAML(s)...",
                   command=self.app.save_yaml_dialog_multicombos).pack(fill="x", pady=(4, 4))

        ttk.Label(right, text="YAML Preview (Single instance):").pack(
            anchor="w", pady=(10, 2))
        self.txt_yaml = tk.Text(right, width=44, height=28, wrap="none")
        self.txt_yaml.pack(fill="both", expand=True)

        # Mouse Bindings for Zoom
        w3d = self.canvas3d.get_tk_widget()
        w3d.bind("<MouseWheel>", self._on_scroll_3d)  # Windows/Mac
        w3d.bind("<Button-4>", self._on_scroll_3d)    # Linux Up
        w3d.bind("<Button-5>", self._on_scroll_3d)    # Linux Down

        # Initial Draw
        self._update_yaml_preview()

    # ---------------- 3D Drawing Logic ----------------

    def _draw_preview_3d(self):
        """
        Main rendering logic. Clears the axis and draws either the Global/Earth scenario
        or the Local/Cell scenario based on 'topo_type'.
        """
        topo_type = (self.app.topo_type.get() or "").strip()
        self.ax3d.cla()

        # ==========================================
        # SCENARIO 1: Global / Countries (Spherical)
        # ==========================================
        if topo_type == "Macro_countries":
            #
            # This section converts Latitude/Longitude/Altitude to Earth-Centered, Earth-Fixed (ECEF)
            # cartesian coordinates to plot them on a 3D globe.

            # Earth - spherical grid
            a = WGS84_A * 0.98
            u = np.linspace(0, 2*np.pi, 720)
            v = np.linspace(0, np.pi, 360)
            X = a*np.outer(np.cos(u), np.sin(v))
            Y = a*np.outer(np.sin(u), np.sin(v))
            Z = a*np.outer(np.ones_like(u), np.cos(v))

            # Positions
            def _get(v): return float(v.get() if v.get() else 0.0)

            ss_alt = _get(self.app.v_alt)
            ss_lat = _get(self.app.v_fix_lat)
            ss_lon = _get(self.app.v_fix_lon)
            es_alt = _get(self.app.v_es_alt)
            es_lat = _get(self.app.v_es_lat)
            es_lon = _get(self.app.v_es_lon)

            sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)
            ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)

            show_map = bool(self.app.var_show_gainmap.get())

            if show_map and HAS_TOPO:
                #
                # We calculate the off-axis angle for every point on the globe relative to the
                # boresight vector to determine the antenna gain based on the S.672 standard.

                # --- Gain Heatmap Logic (LoS + S.672) ---
                dotSP = X * sx + Y * sy + Z * sz
                los_mask = dotSP > (a*a * (1.0 + 1e-12))

                # Boresight Vector (Spacecraft -> Earth Station)
                b = np.array([ex - sx, ey - sy, ez - sz], dtype=float)
                b /= np.linalg.norm(b)

                # Vector to each grid point
                RX = X - sx
                RY = Y - sy
                RZ = Z - sz
                Rnorm = np.sqrt(RX*RX + RY*RY + RZ*RZ)
                RX /= Rnorm
                RY /= Rnorm
                RZ /= Rnorm

                # Off-axis angle
                cospsi = RX*b[0] + RY*b[1] + RZ*b[2]
                cospsi = np.clip(cospsi, -1.0, 1.0)
                psi_deg = np.degrees(np.arccos(cospsi))

                # Calculate Gain
                ant = self._make_s672_antenna()
                gain = ant.calculate_gain(
                    off_axis_angle_vec=psi_deg.ravel()).reshape(psi_deg.shape)

                # Apply LoS Mask
                gain = gain.astype(float, copy=True)
                gain[~los_mask] = -np.inf

                # Color normalization
                try:
                    vmin_txt = (self.app.var_gain_vmin.get()
                                or "auto").strip().lower()
                    vmax_txt = (self.app.var_gain_vmax.get()
                                or "auto").strip().lower()
                except:
                    vmin_txt, vmax_txt = "auto", "auto"

                finite = np.isfinite(gain)
                if vmin_txt in ("auto", "") or vmax_txt in ("auto", ""):
                    if finite.any():
                        gfinite = gain[finite]
                        auto_vmin, auto_vmax = float(
                            np.nanmin(gfinite)), float(np.nanmax(gfinite))
                    else:
                        auto_vmin, auto_vmax = 0.0, 1.0

                vmin = auto_vmin if (vmin_txt in (
                    "auto", "")) else float(vmin_txt)
                vmax = auto_vmax if (vmax_txt in (
                    "auto", "")) else float(vmax_txt)
                if vmin >= vmax:
                    vmax = vmin + 1.0

                norm = colors.Normalize(vmin=vmin, vmax=vmax)
                facecolors = cm.viridis(
                    norm(np.where(np.isfinite(gain), gain, vmin)))
                alpha = np.where(los_mask, 1.0, 0.0)
                facecolors[..., -1] = facecolors[..., -1] * alpha

                self.ax3d.plot_surface(
                    X, Y, Z, rstride=6, cstride=6, facecolors=facecolors, linewidth=0, shade=False, zorder=1)

                # Colorbar
                mappable = cm.ScalarMappable(norm=norm, cmap=cm.viridis)
                mappable.set_array([])
                if hasattr(self, "_gain_cbar") and self._gain_cbar:
                    try:
                        self._gain_cbar.remove()
                    except:
                        pass
                self._gain_cbar = self.fig3d.colorbar(
                    mappable, ax=self.ax3d, shrink=0.8, pad=0.02)
                self._gain_cbar.set_label("Gain (dBi)")

            else:
                # Simple Blue Earth
                self.ax3d.plot_surface(
                    X, Y, Z, rstride=6, cstride=6, color="#dbe7ff", alpha=1.0, edgecolor="none", zorder=1)
                if hasattr(self, "_gain_cbar") and self._gain_cbar:
                    try:
                        self._gain_cbar.remove()
                    except:
                        pass
                    self._gain_cbar = None

            self._draw_country_borders()

            # --- MERGED: TopologyCountries Visualization ---
            if HAS_TOPO and TopologyCountries and ParametersCountries:
                # Helper to safely get value from tk var
                def _safe_get(var, default="0"):
                    val = var.get()
                    return val if val else default

                # Determine population raster
                pop_raster = ""
                if hasattr(self.app, 'topo_raster_enc') and self.app.topo_raster_enc.get() == "Uniforme":
                    pop_raster = ""
                else:
                    pop_raster = (self.app.path_raster.get().strip(
                    ) if hasattr(self.app, 'path_raster') else "")

                try:
                    # Retrieve country list from text widget (assumes it exists in app or tab_imt)
                    country_text = ""
                    if hasattr(self.app, 'tab_imt') and hasattr(self.app.tab_imt, 'txt_countries'):
                        country_text = self.app.tab_imt.txt_countries.get(
                            "1.0", "end")
                    elif hasattr(self.app, 'txt_countries'):
                        country_text = self.app.txt_countries.get("1.0", "end")

                    countries = [c.strip()
                                 for c in country_text.splitlines() if c.strip()]

                    # Instantiate ParametersCountries using app variables
                    params = ParametersCountries(
                        country_names=countries,
                        num_bs_total=int(
                            float(_safe_get(self.app.topo_num_bs))),
                        rng_seed=int(float(_safe_get(self.app.topo_rng))),
                        cell_radius=float(
                            _safe_get(self.app.topo_cell_radius)),
                        countries_shapefile=_safe_get(self.app.path_shp, ""),
                        population_raster=pop_raster,
                        raster_encoding=_safe_get(
                            self.app.raster_encoding, ""),
                        sedac_palette_mode=_safe_get(
                            self.app.sedac_mode, "Linear"),
                        sedac_min=float(_safe_get(self.app.sedac_min)),
                        sedac_max=float(_safe_get(self.app.sedac_max)),
                        pixel_area_method=_safe_get(
                            self.app.pixel_area_method, "Seno"),
                        dist_type=_safe_get(self.app.topo_dist_type),
                        fixed_azimuth=None,
                    )

                    geoconv = GeometryConverter()
                    geoconv.set_reference(
                        float(_safe_get(self.app.topo_c_lat)),
                        float(_safe_get(self.app.topo_c_lon)),
                        float(_safe_get(self.app.topo_c_alt))
                    )

                    # Calculate topology coordinates
                    topo = TopologyCountries(
                        params, geoconv).calculate_coordinates()

                    # Convert to ECEF for plotting (offset altitude slightly for visibility)
                    x, y, z = lla_to_ecef(
                        topo.lats, topo.lons, np.zeros_like(topo.lats) + 500)

                    self.ax3d.scatter(x, y, z, c="tab:red", s=6,
                                      depthshade=False, label="BS (countries)", zorder=10)

                except Exception as e:
                    # Fail silently or print to console to avoid spamming popups during preview adjustment
                    print(
                        f"Preview Warning: Failed to render COUNTRIES points: {e}")

            # Draw points (Spacecraft, Earth Station)
            self._draw_global_markers(sx, sy, sz, ex, ey, ez)

            # Limits
            R = WGS84_A + 4.0e7/6.0
            self.ax3d.set_xlim([-R, R])
            self.ax3d.set_ylim([-R, R])
            self.ax3d.set_zlim([-R, R])
            self.ax3d.set_box_aspect([1, 1, 1])
            self.ax3d.legend(loc="upper right")
            self.canvas3d.draw_idle()
            return

        # ==========================================
        # SCENARIO 2: Local (Macro/Hotspot/Single)
        # ==========================================
        #
        # Local scenarios often use hexagonal grids to represent cell coverage areas.

        xs = ys = azs = None
        cell_radius = None
        bs_height = float(self.app.bs_height.get() or 18.0)

        if topo_type == "MACROCELL":
            try:
                from sharc.topology.topology_macrocell import TopologyMacrocell
                d = float(self.app.macro_intersite.get() or 1500.0)
                nc = int(self.app.macro_clusters.get() or 1)
                topo = TopologyMacrocell(d, nc)
                topo.calculate_coordinates()
                xs, ys, azs = np.asarray(topo.x), np.asarray(
                    topo.y), np.asarray(topo.azimuth)

                # Draw Hexagons
                r = d / 3.0
                for x, y, az in zip(xs, ys, azs):
                    se = [[x, y]]
                    angle = int(az - 60)
                    for _ in range(6):
                        se.append([
                            se[-1][0] + r * math.cos(math.radians(angle)),
                            se[-1][1] + r * math.sin(math.radians(angle)),
                        ])
                        angle += 60
                    self._add_polyline3d(
                        self.ax3d, se, z=0.0, color="k", lw=1.0)

                # Markers
                self.ax3d.scatter(xs, ys, np.zeros_like(
                    xs), color="k", s=18, depthshade=False)
            except ImportError:
                self.ax3d.text2D(
                    0.5, 0.5, "SHARC library not found", transform=self.ax3d.transAxes)

        elif topo_type == "HOTSPOT":
            #
            # Hotspot topologies overlay small cells (hotspots) onto a macrocell grid to increase capacity.

            try:
                from sharc.topology.topology_hotspot import TopologyHotspot
                from sharc.parameters.imt.parameters_hotspot import ParametersHotspot

                d = float(self.app.hotspot_intersite.get() or 1500.0)
                nc = int(self.app.hotspot_clusters.get() or 1)

                p = ParametersHotspot()
                if self.app.hotspot_num_per_cell.get():
                    p.num_hotspots_per_cell = int(
                        self.app.hotspot_num_per_cell.get())
                if self.app.hotspot_max_dist_ue.get():
                    p.max_dist_hotspot_ue = float(
                        self.app.hotspot_max_dist_ue.get())
                if self.app.hotspot_min_dist_bs.get():
                    p.min_dist_bs_hotspot = float(
                        self.app.hotspot_min_dist_bs.get())

                topo = TopologyHotspot(p, d, nc)
                topo.calculate_coordinates()

                xs, ys, azs = np.asarray(topo.x), np.asarray(
                    topo.y), np.asarray(topo.azimuth)
                cell_radius = float(p.max_dist_hotspot_ue)

                # Macro Hexagons Background
                if hasattr(topo, "macrocell"):
                    mx, my, maz = np.asarray(topo.macrocell.x), np.asarray(
                        topo.macrocell.y), np.asarray(topo.macrocell.azimuth)
                    r_hex = d / 3.0
                    for x0, y0, az0 in zip(mx, my, maz):
                        se = [[x0, y0]]
                        angle = int(az0 - 60)
                        for _ in range(6):
                            se.append([
                                se[-1][0] + r_hex * np.cos(np.radians(angle)),
                                se[-1][1] + r_hex * np.sin(np.radians(angle)),
                            ])
                            angle += 60
                        self._add_polyline3d(
                            self.ax3d, se, z=0.0, color="0.25", lw=0.9)

                # Hotspot Points
                self.ax3d.scatter(xs, ys, np.zeros_like(
                    xs), color="g", edgecolors="w", s=18, depthshade=False)

                # Wedges
                for xh, yh, a in zip(xs, ys, azs):
                    self._add_wedge_outline3d(
                        self.ax3d, xh, yh, cell_radius, a, half_bw_deg=60, color="green", lw=1.0)

            except ImportError:
                pass

        elif topo_type == "SINGLE_BS":
            try:
                from sharc.topology.topology_single_base_station import TopologySingleBaseStation
                cr = float(self.app.sbs_cell_radius.get() or 100.0)
                nc = int(self.app.sbs_clusters.get() or 1)
                az_text = (self.app.sbs_azimuth.get() or "").strip()

                try:
                    az_param = [float(x.strip())
                                for x in az_text.split(",")] if az_text else None
                except:
                    az_param = az_text

                topo = TopologySingleBaseStation(cr, nc, azimuth=az_param)
                topo.calculate_coordinates()
                xs, ys, azs = topo.x, topo.y, topo.azimuth
                cell_radius = cr
            except ImportError:
                pass

        # Draw Masts (Common to all local topologies)
        if xs is not None and len(xs) > 0:
            for x, y in zip(xs, ys):
                self._draw_bs_post(self.ax3d, x, y, bs_height,
                                   color="tab:blue", lw=2.0)

            #
            # We visualize the sector coverage area to verify the azimuth orientation and cell radius.

            if cell_radius and topo_type in ("SINGLE_BS"):
                for x, y, az in zip(xs, ys, azs):
                    poly_xy = self._sector_polygon_xy(
                        x, y, cell_radius, az, half_bw_deg=60)
                    self._add_sector3d(
                        self.ax3d, poly_xy, z=0.0, face_alpha=0.10, edge_color="tab:green")

            # Adjust Limits
            self._set_equal_3d(self.ax3d, xs, ys, z_top=bs_height, margin=0.12)

        self.ax3d.set_xlabel("x [m]")
        self.ax3d.set_ylabel("y [m]")
        self.ax3d.set_zlabel("z [m]")
        self.canvas3d.draw_idle()

    # ---------------- Geometry Helpers ----------------

    def _draw_country_borders(self):
        """Reads the shapefile and draws borders on the 3D globe."""
        if not self.app.show_borders.get() or not HAS_PYSHP:
            return
        shp_path = self.app.path_shp.get()
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
                    self.ax3d.plot(x, y, z, lw=0.35, color="k",
                                   alpha=0.55, zorder=5)
        except Exception:
            pass

    def _draw_global_markers(self, sx, sy, sz, ex, ey, ez):
        """Draws the Spacecraft and Earth Station markers and line of sight."""
        # Spacecraft & ES
        self.ax3d.scatter([sx], [sy], [sz], c="tab:purple", s=60,
                          marker="^", depthshade=False, label="Spacecraft", zorder=7)
        self.ax3d.scatter([ex], [ey], [ez], c="tab:blue", s=24, marker="o",
                          depthshade=False, label="Earth Station", zorder=7)
        self.ax3d.plot([sx, ex], [sy, ey], [sz, ez],
                       color="tab:purple", lw=1.6, alpha=0.9, zorder=6)

    def _make_s672_antenna(self):
        """Instantiates an S.672 antenna object based on UI parameters."""
        if not HAS_TOPO:
            return None
        param = ParametersAntennaS672()
        param.antenna_gain = float(self.app.v_ant_gain.get())
        param.antenna_3_dB = float(self.app.v_s672_3db.get())
        param.antenna_3_dB_bw = float(self.app.v_s672_3db.get())
        param.antenna_l_s = float(self.app.v_s672_ls.get())
        return AntennaS672(param)

    # ---------------- YAML and Files ----------------

    def _update_yaml_preview(self):
        """Generates the YAML text and updates the preview text box."""
        if hasattr(self.app, 'current_yaml_dict'):
            root = self.app.current_yaml_dict()
            text = build_yaml_text(root)
            self.txt_yaml.delete("1.0", tk.END)
            self.txt_yaml.insert(tk.END, text)

    def _save_image_3d(self):
        """Saves the current 3D plot to a PNG file."""
        suggested = f"topology3d_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            title="Save Image",
            defaultextension=".png",
            initialfile=suggested,
            filetypes=[("PNG", "*.png"), ("All files", "*.*")]
        )
        if path:
            self.fig3d.savefig(path, dpi=180, bbox_inches="tight")
            messagebox.showinfo("OK", f"Image saved to:\n{path}")

    # ---------------- 3D Interaction ----------------

    def _on_scroll_3d(self, event):
        """Handles mouse scroll events for zooming."""
        base = 1.12
        direction = 0
        if hasattr(event, "num") and event.num in (4, 5):  # Linux
            direction = -1 if event.num == 4 else 1
        else:  # Win/Mac
            direction = -1 if getattr(event, "delta", 0) > 0 else 1
        factor = (1.0 / base) if direction < 0 else base
        self._zoom_preview_3d(factor)

    def _zoom_preview_3d(self, factor):
        """Applies zoom by scaling axis limits."""
        # Try .dist (older mpl versions)
        if hasattr(self.ax3d, "dist"):
            self.ax3d.dist = max(1, float(self.ax3d.dist) * float(factor))
        else:
            # Fallback for newer mpl
            for getter, setter in [(self.ax3d.get_xlim3d, self.ax3d.set_xlim3d),
                                   (self.ax3d.get_ylim3d, self.ax3d.set_ylim3d),
                                   (self.ax3d.get_zlim3d, self.ax3d.set_zlim3d)]:
                lo, hi = getter()
                c = 0.5*(lo + hi)
                half = 0.5*(hi - lo)*factor
                setter(c - half, c + half)
        self.canvas3d.draw_idle()

    # ---------------- Local Geometric Primitives ----------------

    def _draw_bs_post(self, ax, x, y, h, color="tab:blue", lw=2.0):
        """Draws a vertical line representing the Base Station mast."""
        ax.plot([x, x], [y, y], [0, h], color=color, lw=lw)

    def _add_polyline3d(self, ax, xy_points, z=0.0, color="k", lw=1.0):
        """Adds a closed polyline to the 3D axis."""
        if not xy_points:
            return
        if xy_points[0] != xy_points[-1]:
            xy_points = xy_points + [xy_points[0]]
        segs = [((xy_points[i][0], xy_points[i][1], z),
                 (xy_points[i+1][0], xy_points[i+1][1], z))
                for i in range(len(xy_points)-1)]
        ax.add_collection3d(Line3DCollection(
            segs, colors=[color], linewidths=lw))

    def _add_wedge_outline3d(self, ax, x, y, r, az_deg, half_bw_deg=60, n=64, color="green", lw=1.0):
        """Adds a wedge outline (sector) at a specific azimuth."""
        th0 = np.radians(az_deg - half_bw_deg)
        th1 = np.radians(az_deg + half_bw_deg)
        ths = np.linspace(th0, th1, n)
        arc_xy = [(x + r*np.cos(t), y + r*np.sin(t)) for t in ths]
        center = (x, y)
        segs = []
        p0 = arc_xy[0]
        pN = arc_xy[-1]
        segs.append(((center[0], center[1], 0.0), (p0[0], p0[1], 0.0)))
        for a, b in zip(arc_xy[:-1], arc_xy[1:]):
            segs.append(((a[0], a[1], 0.0), (b[0], b[1], 0.0)))
        segs.append(((pN[0], pN[1], 0.0), (center[0], center[1], 0.0)))
        ax.add_collection3d(Line3DCollection(
            segs, colors=[color], linewidths=lw))

    def _sector_polygon_xy(self, x, y, radius, az_deg, half_bw_deg=60, n=48):
        """Calculates XY points for a sector polygon."""
        th0 = np.radians(az_deg - half_bw_deg)
        th1 = np.radians(az_deg + half_bw_deg)
        ths = np.linspace(th0, th1, n)
        xs = x + radius * np.cos(ths)
        ys = y + radius * np.sin(ths)
        return [(x, y)] + list(zip(xs, ys)) + [(x, y)]

    def _add_sector3d(self, ax, poly_xy, z=0.0, face_alpha=0.12, edge_color="tab:green"):
        """Adds a filled sector polygon to the 3D axis."""
        verts3d = [(px, py, z) for (px, py) in poly_xy]
        pcoll = Poly3DCollection(
            [verts3d], alpha=face_alpha, edgecolor=edge_color)
        pcoll.set_facecolor(edge_color)
        ax.add_collection3d(pcoll)

    def _set_equal_3d(self, ax, xs, ys, z_top, margin=0.10):
        """Sets the aspect ratio of the 3D plot to be equal."""
        xmin, xmax = float(np.min(xs)), float(np.max(xs))
        ymin, ymax = float(np.min(ys)), float(np.max(ys))
        dx = max(1e-9, xmax - xmin)
        dy = max(1e-9, ymax - ymin)
        span = max(dx, dy, float(z_top))
        pad = span * margin
        cx = 0.5 * (xmax + xmin)
        cy = 0.5 * (ymax + ymin)
        ax.set_xlim(cx - 0.5*span - pad, cx + 0.5*span + pad)
        ax.set_ylim(cy - 0.5*span - pad, cy + 0.5*span + pad)
        ax.set_zlim(0.0, span + pad)
        try:
            ax.set_box_aspect((1, 1, 1))
        except:
            pass
