from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import os
import posixpath
import math
import traceback
import numpy as np

from PySide6.QtWidgets import QFileDialog, QMessageBox

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    from matplotlib.patches import RegularPolygon
    import matplotlib.colors as mcolors
except ImportError:
    pass

try:
    import plotly.graph_objects as go
except ImportError:
    pass

from utils import (
    # Type coercers
    _safe_float, _safe_int, _coerce_float, _coerce_int, _coerce_str,
    # YAML helpers
    _yaml_first, _yaml_get,
    # Geodetic
    lla_to_ecef,
    # Constants
    WGS84_A,
    WGS84_F,
    GLOBAL_PREVIEW_TYPES,
    # Preview GUI helpers
    _get_imt_value, _get_countries_text, _parse_country_names, _normalize_raster_encoding,
    # Geometry helpers
    _approx_hex_cluster_centers, _antenna_gain_db_batch,
    # Optional lib flags
    HAS_PLOTLY, HAS_PYSHP, HAS_GEOPANDAS,
    # SHARC core classes
    HAS_SHARC_CORE,
    TopologyCountries, ParametersCountries,
)

# Re-import optional libs for local use if available
try:
    import shapefile as pyshp
except ImportError:
    pyshp = None

try:
    import geopandas as gpd
except ImportError:
    gpd = None


class PlotEnginesMixin:
    """
    Fornece as lógicas de renderização para o PreviewTab (Matplotlib QtAgg & Plotly HTML).
    Essa classe presume estar rodando como Mixin no escopo de um QWidget.
    """

    def _draw_preview(self):
        data = self._current_yaml()
        topo_type = self._detect_topology_type(data)
        sys_type = self._detect_system_type(data)
        engine = str(self.app.plot_engine.get())

        # Update simulation summary and scenario header
        self._update_sim_summary()
        self._update_supported_catalog(topo_type, sys_type)
        
        scenario_label = f"🎯 {topo_type}"
        if sys_type:
            scenario_label += f"  |  System: {sys_type}"
        link = _coerce_str(getattr(self.app, "var_imt_link", ""), "")
        if hasattr(link, 'get'):
            link = link.get()
        if link:
            scenario_label += f"  |  {link}"
            
        if hasattr(self, "_lbl_scenario"):
            self._lbl_scenario.setText(scenario_label) # [PYSIDE6 FIX]

        print(f"[PreviewTab] Drawing {topo_type} using {engine}")

        # [PYSIDE6 FIX] Troca de visibilidade dos widgets embutidos
        if engine == "plotly" and HAS_PLOTLY:
            self.canvas3d.hide()
            self._plotly_embed.show()
            self._draw_preview_plotly(topo_type, data)
        else:
            self._plotly_embed.hide()
            self.canvas3d.show()
            self._draw_preview_matplotlib(topo_type, data)

    def _draw_preview_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        self.ax3d.cla()

        # --- Dark theme styling ---
        self.fig3d.set_facecolor("#1a1a2e")
        self.ax3d.set_facecolor("#16213e")
        for axis_pane in [self.ax3d.xaxis, self.ax3d.yaxis, self.ax3d.zaxis]:
            axis_pane.set_pane_color((0.08, 0.13, 0.24, 0.9))
            axis_pane.label.set_color("#b0c4de")
            axis_pane._axinfo["tick"]["color"] = "#b0c4de"
            axis_pane._axinfo["grid"]["color"] = "#2a3a5e"
        self.ax3d.tick_params(colors="#8899aa", labelsize=7)

        is_global = topo_type in GLOBAL_PREVIEW_TYPES

        try:
            if is_global:
                self._draw_global_matplotlib(topo_type, data)
            else:
                self._draw_local_matplotlib(topo_type, data)
        except Exception as e:
            traceback.print_exc()
            self.ax3d.text2D(
                0.05, 0.95, f"Error: {e}", transform=self.ax3d.transAxes, color="red")

        # --- Clean axis labels ---
        self.ax3d.set_xlabel("x", fontsize=8, color="#b0c4de")
        self.ax3d.set_ylabel("y", fontsize=8, color="#b0c4de")
        self.ax3d.set_zlabel("z", fontsize=8, color="#b0c4de")

        # --- Title ---
        sys_var = getattr(self.app, "var_system", "")
        sys_type = _coerce_str(sys_var.get() if hasattr(sys_var, 'get') else sys_var, "")
        
        title = f"{topo_type}"
        if sys_type:
            title += f" — {sys_type}"
        self.ax3d.set_title(title, fontsize=10, color="#e0e0e0", pad=2)

        # --- Legend ---
        leg = self.ax3d.legend(loc='upper right', fontsize=6,
                               facecolor="#1a1a2e", edgecolor="#3a4a6e",
                               labelcolor="#d0d0e0", framealpha=0.8)

        self.fig3d.tight_layout(pad=1.0)
        self.canvas3d.draw_idle()

    def _draw_local_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        bs_height = _coerce_float(_yaml_first(data, ("imt.base_station.height_m",
                                  "imt.bs.height_m", "imt.bs_height", "bs_height", "general.bs_height"), None), 30.0)
        if hasattr(self.app, "bs_height"):
            val = self.app.bs_height.get() if hasattr(self.app.bs_height, 'get') else self.app.bs_height
            bs_height = _safe_float(val, bs_height)

        xs, ys, azs, hex_centers, hex_radius, draw_hex = self._compute_local_geometry(
            topo_type, data)

        if not xs:
            xs, ys = [0.0], [0.0]

        ue_height = _coerce_float(_yaml_first(data, ("imt.ue.height", "ue_height"), None), 1.5)
        if hasattr(self.app, "ue_height"):
            val = self.app.ue_height.get() if hasattr(self.app.ue_height, 'get') else self.app.ue_height
            ue_height = _safe_float(val, ue_height)

        # ============================================================
        # INDOOR topology
        # ============================================================
        if topo_type == "INDOOR" and self._indoor_topo is not None:
            topo = self._indoor_topo
            b_w, b_d, b_h = topo.b_w, topo.b_d, topo.b_h
            num_cells = topo.num_cells
            cell_radius = topo.cell_radius
            num_floors = topo.num_floors
            n_total_bs = len(topo.x)
            bs_per_floor = max(1, n_total_bs // max(1, num_floors))

            drawn_first = False
            for b_idx in range(bs_per_floor // max(1, num_cells)):
                floor_i = b_idx * num_cells
                if floor_i >= len(topo.x):
                    break
                x_b = topo.x[floor_i] - cell_radius
                y_b = topo.y[floor_i] - b_d / 2
                for f in range(num_floors):
                    z0, z1 = f * b_h, (f + 1) * b_h
                    cx = [x_b, x_b + b_w, x_b + b_w, x_b, x_b]
                    cy = [y_b, y_b, y_b + b_d, y_b + b_d, y_b]
                    lbl = "Building" if not drawn_first else None
                    self.ax3d.plot(cx, cy, [z0]*5, color="#d4a574", lw=0.8, alpha=0.7, label=lbl)
                    self.ax3d.plot(cx, cy, [z1]*5, color="#d4a574", lw=0.8, alpha=0.7)
                    for vx, vy in [(x_b, y_b), (x_b+b_w, y_b), (x_b+b_w, y_b+b_d), (x_b, y_b+b_d)]:
                        self.ax3d.plot([vx, vx], [vy, vy], [z0, z1], color="#d4a574", lw=0.5, alpha=0.5)
                    drawn_first = True

            heights = list(topo.height) if hasattr(topo, "height") and len(topo.height) > 0 else [bs_height]*len(xs)
            self.ax3d.scatter(xs, ys, heights, c="blue", marker="s", s=20, depthshade=False, label="Indoor BS", zorder=5)
            n_ue = min(len(xs) * 3, 60)
            if n_ue > 0:
                ue_xs = [xs[i % len(xs)] + np.random.uniform(-cell_radius, cell_radius) for i in range(n_ue)]
                ue_ys = [ys[i % len(ys)] + np.random.uniform(-b_d/2, b_d/2) for i in range(n_ue)]
                ue_zs = [heights[i % len(heights)] - np.random.uniform(0, b_h*0.8) for i in range(n_ue)]
                self.ax3d.scatter(ue_xs, ue_ys, ue_zs, c="#ff6b6b", marker=".", s=12,
                                  alpha=0.6, label="UE (sample)", zorder=4)
            if xs:
                span = max(max(xs)-min(xs), max(ys)-min(ys), 50) * 1.3
                cx_m, cy_m = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2
                self.ax3d.set_xlim(cx_m - span/2, cx_m + span/2)
                self.ax3d.set_ylim(cy_m - span/2, cy_m + span/2)
                self.ax3d.set_zlim(0, max(heights)*1.5 if heights else b_h*num_floors*1.5)
            return

        # ============================================================
        # NTN topology
        # ============================================================
        if topo_type == "NTN" and self._ntn_topo is not None:
            topo = self._ntn_topo
            sc = 1000.0
            cr_km = topo.cell_radius / sc
            first_hex = True
            for x, y in zip(topo.x / sc, topo.y / sc):
                lbl = "Sector Cells" if first_hex else None
                angs = np.linspace(0, 2*np.pi, 7)
                self.ax3d.plot(x + cr_km*np.cos(angs), y + cr_km*np.sin(angs),
                               np.zeros(7), color="#7986cb", lw=1, label=lbl)
                first_hex = False
            self.ax3d.scatter(topo.x/sc, topo.y/sc, np.zeros(len(topo.x)),
                              c="#e0e0e0", marker="v", s=50, depthshade=False, label="Anchor Points", zorder=5)
            sx, sy, sz = topo.space_station_x/sc, topo.space_station_y/sc, topo.space_station_z/sc
            self.ax3d.scatter([sx], [sy], [sz], c="#ff5252", marker="^", s=100, depthshade=False,
                              label=f"Satellite (el={np.degrees(topo.bs_elevation):.0f}°)", zorder=10)
            self.ax3d.plot([sx, sx], [sy, sy], [0, sz], color="#4fc3f7", lw=1.5,
                           label=f"Height = {sz:.0f} km")
            self.ax3d.plot([0, sx], [0, sy], [0, sz], color="green", linestyle="-.", lw=1.5,
                           label=f"Slant = {topo.bs_radius/1000.0:.0f} km")
            n_ue = min(len(topo.x)*5, 80)
            if n_ue > 0:
                ue_x = [topo.x[i%len(topo.x)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                ue_y = [topo.y[i%len(topo.y)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                self.ax3d.scatter(ue_x, ue_y, [0]*n_ue, c="#ff6b6b", marker=".", s=10,
                                  alpha=0.6, label="UE (sample)", zorder=3)
            self.ax3d.set_xlabel("x [km]")
            self.ax3d.set_ylabel("y [km]")
            self.ax3d.set_zlabel("z [km]")
            return

        # Hexagon Grid (Honeycomb)
        if draw_hex and hex_centers:
            first = True
            for cx, cy in hex_centers:
                label = "Cell Grid" if first else None
                self._draw_hexagon_shape_mpl(cx, cy, hex_radius, rotation_deg=30,
                                             color="#4a5a8a", lw=1.0, alpha=0.3, label=label)
                self.ax3d.plot([cx, cx], [cy, cy], [0, bs_height],
                               color="#4a5a8a", lw=0.5, alpha=0.5)
                first = False

        marker = "o" if topo_type == "HOTSPOT" else "^"
        color = "#4fc3f7"
        label_bs = f"{topo_type.replace('_', ' ').title()} BS"

        self.ax3d.scatter(xs, ys, [bs_height]*len(xs), c=color, marker=marker, s=40,
                          depthshade=False, label=label_bs)

        for x, y in zip(xs, ys):
            self.ax3d.plot([x, x], [y, y], [0, bs_height], color=color, lw=1.5)

        radius = hex_radius * 0.85 if hex_radius > 0 else 50.0
        if topo_type == "HOTSPOT":
            radius = 20.0

        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            first_sector = True
            for x, y, az in zip(xs, ys, azs):
                lbl = "Sector" if first_sector else None
                self._add_wedge_outline3d_mpl(
                    self.ax3d, x, y, radius, az, z_plane=bs_height, color=color, label=lbl)
                first_sector = False

        # ============================================================
        # BS Antenna direction arrows
        # ============================================================
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            downtilt = 6.0
            if hasattr(self.app, "bs_downtilt"):
                val = self.app.bs_downtilt.get() if hasattr(self.app.bs_downtilt, 'get') else self.app.bs_downtilt
                downtilt = _safe_float(val, 6.0)
            arrow_len = radius * 0.5 if radius > 0 else 30.0
            first_arrow = True
            for x, y, az in zip(xs, ys, azs):
                az_rad = np.radians(az)
                dt_rad = np.radians(downtilt)
                avx = arrow_len * np.cos(-dt_rad) * np.cos(az_rad)
                avy = arrow_len * np.cos(-dt_rad) * np.sin(az_rad)
                avz = -arrow_len * np.sin(dt_rad)
                lbl_a = f"Antenna (dt={downtilt:.0f}°)" if first_arrow else None
                self.ax3d.quiver(x, y, bs_height, avx, avy, avz,
                                 color="#ffab40", arrow_length_ratio=0.15,
                                 linewidth=1.2, label=lbl_a)
                first_arrow = False

        # ============================================================
        # UE positions
        # ============================================================
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            ue_k = 3
            if hasattr(self.app, "ue_k"):
                val = self.app.ue_k.get() if hasattr(self.app.ue_k, 'get') else self.app.ue_k
                ue_k = _safe_int(val, 3)
            n_ue_per_bs = max(ue_k, 1)
            ue_radius = hex_radius * 0.9 if hex_radius > 0 else radius * 0.9
            if topo_type == "HOTSPOT":
                hotspot_max_dist = 50.0
                if hasattr(self.app, "hotspot_max_dist_ue"):
                    val = self.app.hotspot_max_dist_ue.get() if hasattr(self.app.hotspot_max_dist_ue, 'get') else self.app.hotspot_max_dist_ue
                    hotspot_max_dist = _safe_float(val, 50.0)
                ue_radius = hotspot_max_dist

            ue_xs, ue_ys = [], []
            unique_bs = list(set(zip(xs, ys)))
            n_ue_total = min(len(unique_bs) * n_ue_per_bs, 120)
            for i in range(n_ue_total):
                bi = i % len(unique_bs)
                bx, by = unique_bs[bi]
                ang = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(0, ue_radius)
                ue_xs.append(bx + r * np.cos(ang))
                ue_ys.append(by + r * np.sin(ang))
            if ue_xs:
                self.ax3d.scatter(ue_xs, ue_ys, [ue_height]*len(ue_xs),
                                  c="#ff6b6b", marker=".", s=15, alpha=0.7,
                                  depthshade=False, label=f"UE (K={ue_k})", zorder=4)

        # ============================================================
        # MSS_D2D
        # ============================================================
        if topo_type == "MSS_D2D":
            self.ax3d.scatter(xs[:1], ys[:1], [ue_height], c="#66bb6a", marker="D",
                              s=60, depthshade=False, label="Device 1", zorder=5)
            if len(xs) > 1:
                self.ax3d.scatter(xs[1:2], ys[1:2], [ue_height], c="#ab47bc", marker="D",
                                  s=60, depthshade=False, label="Device 2", zorder=5)
                self.ax3d.plot([xs[0], xs[1]], [ys[0], ys[1]], [ue_height, ue_height],
                               color="#ffab40", linestyle="--", lw=2, label="D2D Link")

        if str(self.app.var_system.get()) == "SINGLE_EARTH_STATION":
            def set_equal_3d(ax):
                xlim = ax.get_xlim3d()
                ylim = ax.get_ylim3d()
                zlim = ax.get_zlim3d()

                xmid = 0.5 * (xlim[0] + xlim[1])
                ymid = 0.5 * (ylim[0] + ylim[1])
                zmid = 0.5 * (zlim[0] + zlim[1])

                radius = 0.5 * max(
                    xlim[1] - xlim[0],
                    ylim[1] - ylim[0],
                    zlim[1] - zlim[0]
                )

                ax.set_xlim3d([xmid - radius, xmid + radius])
                ax.set_ylim3d([ymid - radius, ymid + radius])
                ax.set_zlim3d([zmid - radius, zmid + radius])   
           
            mode = getattr(self.app, "se_loc_type", None)
            mode = str(mode.get() if hasattr(mode, "get") else "FIXED").strip()

            if mode == "FIXED":
                vx = getattr(self.app, "se_loc_fixed_x", None)
                x0 = _safe_float(vx.get() if hasattr(vx, 'get') else vx, 0.0)
                vy = getattr(self.app, "se_loc_fixed_y", None)
                y0 = _safe_float(vy.get() if hasattr(vy, 'get') else vy, 0.0)

                self.ax3d.scatter([x0], [y0], [bs_height], c="red", s=40, depthshade=False, label="Single Earth Station")

            elif mode == "UNIFORM_DIST":
                vmin = getattr(self.app, "se_loc_ud_min_dist_to_center", None)
                rmin = _safe_float(vmin.get() if hasattr(vmin, 'get') else vmin)
                vmax = getattr(self.app, "se_loc_ud_max_dist_to_center", None)
                rmax = _safe_float(vmax.get() if hasattr(vmax, 'get') else vmax)

                ang = np.random.uniform(0, 2*np.pi)
                r = np.random.uniform(rmin, rmax)
                x0, y0 = r*np.cos(ang), r*np.sin(ang)

                self.ax3d.scatter([x0], [y0], [bs_height], c="red", s=40, depthshade=False, label="Single Earth Station")

                th = np.linspace(0, 2*np.pi, 120)
                self.ax3d.plot(rmin*np.cos(th), rmin*np.sin(th), [bs_height]*len(th), color="red", linestyle="dotted", label="min radius")
                self.ax3d.plot(rmax*np.cos(th), rmax*np.sin(th), [bs_height]*len(th), color="red", linestyle="dotted", label="max radius")

            # Pointing Vector
            se_az_type = getattr(self.app, "se_az_type", None)
            se_el_type = getattr(self.app, "se_el_type", None)
            az_type_val = str(se_az_type.get() if hasattr(se_az_type, "get") else "FIXED").strip()
            el_type_val = str(se_el_type.get() if hasattr(se_el_type, "get") else "FIXED").strip()

            if az_type_val == "UNIFORM_DIST" or el_type_val == "UNIFORM_DIST":
                if az_type_val == "UNIFORM_DIST":
                    az_min = _safe_float(getattr(self.app, "se_az_ud_min").get())
                    az_max = _safe_float(getattr(self.app, "se_az_ud_max").get())
                else:
                    az0 = _safe_float(getattr(self.app, "se_az_fixed").get())
                    az_min, az_max = az0-1, az0+1

                if el_type_val == "UNIFORM_DIST":
                    el_min = _safe_float(getattr(self.app, "se_el_ud_min").get())
                    el_max = _safe_float(getattr(self.app, "se_el_ud_max").get())
                else:
                    el0 = _safe_float(getattr(self.app, "se_el_fixed").get())
                    el_min, el_max = el0-1, el0+1

                az_vals = np.linspace(az_min, az_max, 30)
                el_vals = np.linspace(el_min, el_max, 30)
                AZ, EL = np.meshgrid(az_vals, el_vals)

                R = max(np.sqrt(x0**2 + y0**2)/4, 100)
                X = x0 + R*np.cos(np.radians(EL))*np.cos(np.radians(AZ))
                Y = y0 + R*np.cos(np.radians(EL))*np.sin(np.radians(AZ))
                Z = bs_height + R*np.sin(np.radians(EL))

                self.ax3d.plot_surface(X, Y, Z, color="blue", alpha=0.35, linewidth=0, antialiased=True)
                
                az_c = 0.5*(az_min + az_max)
                el_c = 0.5*(el_min + el_max)
                vx = R*np.cos(np.radians(el_c))*np.cos(np.radians(az_c))
                vy = R*np.cos(np.radians(el_c))*np.sin(np.radians(az_c))
                vz = R*np.sin(np.radians(el_c))

                self.ax3d.quiver(x0, y0, bs_height, vx, vy, vz, color="red", arrow_length_ratio=0.2, linewidth=2, label="Pointing center")
            else:
                length = np.sqrt(x0**2 + y0**2)/3
                target = np.array([0, 0, 0])
                origin = np.array([x0, y0, bs_height])
                v = target - origin
                v = v/np.linalg.norm(v)
                vx, vy, vz = v*length
                
                el_var = getattr(self.app, "se_el_fixed", None)
                el = _safe_float(el_var.get() if hasattr(el_var, 'get') else 0.0)
                az_var = getattr(self.app, "se_az_fixed", None)
                az = _safe_float(az_var.get() if hasattr(az_var, 'get') else 0.0)
                
                vx2 = length * np.cos(np.radians(el)) * np.cos(np.radians(az))
                vy2 = length * np.cos(np.radians(el)) * np.sin(np.radians(az))
                vz2 = length * np.sin(np.radians(el))
                
                if az_type_val == "FIXED" and el_type_val == "FIXED":
                    vx, vy, vz = vx2, vy2, vz2
                if az_type_val == "FIXED" and el_type_val == "POINTING_AT_IMT_CENTER":
                    vx, vy = vx2, vy2
                if el_type_val == "FIXED" and az_type_val == "POINTING_AT_IMT_CENTER":
                    vz = vz2

                self.ax3d.quiver(x0, y0, bs_height, vx, vy, vz, color="red")
            set_equal_3d(self.ax3d)

    def _draw_global_matplotlib(self, topo_type: str, data: Dict[str, Any]):
        a = WGS84_A
        b = WGS84_A * (1.0 - WGS84_F)  # WGS84 polar radius
        u = np.linspace(0, 2 * np.pi, 60)
        v = np.linspace(0, np.pi, 30)
        X = a * np.outer(np.cos(u), np.sin(v))
        Y = a * np.outer(np.sin(u), np.sin(v))
        # Draw the true WGS84 ellipsoid (shortened polar axis) so georeferenced
        # points from lla_to_ecef(h=0) lie exactly on the surface instead of
        # sinking below an equatorial-radius sphere at high latitudes.
        Z = b * np.outer(np.ones_like(u), np.cos(v))

        # Resolve satellite/earth-station positions up-front so the satellite
        # antenna can colour the globe with its gain pattern (parity with the
        # plotly engine, which previously was the only one to show the heatmap).
        sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)

        facecolors = None
        if self.app.var_show_gainmap.get() and sat_obj is not None:
            ant = getattr(sat_obj, "antenna", None)
            has_ant = ant is not None and (not hasattr(ant, "__len__") or len(ant) > 0)
            if has_ant:
                try:
                    vmin = float(self.app.var_gain_vmin.get())
                    vmax = float(self.app.var_gain_vmax.get())
                    gains = self._compute_gain_surface(sx, sy, sz, ant, X, Y, Z, vmin, vmax)
                    norm = (gains - vmin) / (vmax - vmin) if vmax > vmin else np.zeros_like(gains)
                    facecolors = plt.cm.turbo(np.clip(norm, 0.0, 1.0))
                except Exception:
                    traceback.print_exc()
                    facecolors = None

        if facecolors is not None:
            self.ax3d.plot_surface(X, Y, Z, facecolors=facecolors, alpha=0.9,
                                   linewidth=0, antialiased=False, shade=False)
        else:
            self.ax3d.plot_surface(X, Y, Z, color="#1e3a5f", alpha=0.85, edgecolor="#2a4a7f", lw=0.3)

        if self.app.show_borders.get():
            self._draw_borders_mpl()

        if topo_type == "Macro_countries":
            bs_lats, bs_lons = self._compute_macro_countries_bs(data)

            bs_x, bs_y, bs_z = lla_to_ecef(bs_lats, bs_lons, 0)
            offset = 1.005
            self.ax3d.scatter(np.asarray(bs_x) * offset, np.asarray(bs_y) * offset, np.asarray(bs_z) * offset,
                              c="#4fc3f7", marker="^", s=12, alpha=0.9, depthshade=False, label=f"BS ({len(bs_lats)})", zorder=10)

        self.ax3d.scatter([sx], [sy], [sz], c="#ff5252", s=80, marker="^", label="Satellite", zorder=10)
        self.ax3d.scatter([ex], [ey], [ez], c="#4fc3f7", s=50, marker="o", label="Earth Station", zorder=10)
        self.ax3d.plot([sx, ex], [sy, ey], [sz, ez], color="#ffab40", linestyle="--", lw=1.5, alpha=0.9, label="Link")

        if self.app.show_beamwidth.get():
            bw = self._determine_beamwidth(sat_obj)
            self._draw_footprint_mpl(sx, sy, sz, bw)

        limit = WGS84_A * 2.5
        self.ax3d.set_xlim(-limit, limit)
        self.ax3d.set_ylim(-limit, limit)
        self.ax3d.set_zlim(-limit, limit)
        self.ax3d.set_box_aspect([1, 1, 1])

    def _draw_preview_plotly(self, topo_type: str, data: Dict[str, Any]):
        if not HAS_PLOTLY:
            return

        fig = go.Figure()
        is_global = topo_type in GLOBAL_PREVIEW_TYPES

        try:
            if is_global:
                self._draw_global_plotly(fig, topo_type, data)
            else:
                self._draw_local_plotly(fig, topo_type, data)
        except Exception as e:
            traceback.print_exc()
            fig.add_annotation(text=f"Error: {e}", showarrow=False)

        fig.update_layout(showlegend=True, legend=dict(x=0, y=1))
        self._plotly_last_fig = fig
        self._plotly_embed.set_figure(fig, open_external=self.app.open_plotly_external.get())

    def _draw_local_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        bs_height = _coerce_float(_yaml_first(data, ("imt.base_station.height_m", "imt.bs.height_m", "imt.bs_height", "bs_height", "general.bs_height"), None), 30.0)
        if hasattr(self.app, "bs_height"):
            val = self.app.bs_height.get() if hasattr(self.app.bs_height, 'get') else self.app.bs_height
            bs_height = _safe_float(val, bs_height)
            
        xs, ys, azs, hex_centers, hex_radius, draw_hex = self._compute_local_geometry(topo_type, data)

        ue_height = _coerce_float(_yaml_first(data, ("imt.ue.height", "ue_height"), None), 1.5)
        if hasattr(self.app, "ue_height"):
            val = self.app.ue_height.get() if hasattr(self.app.ue_height, 'get') else self.app.ue_height
            ue_height = _safe_float(val, ue_height)

        if topo_type == "INDOOR" and self._indoor_topo is not None:
            topo = self._indoor_topo
            b_w, b_d, b_h = topo.b_w, topo.b_d, topo.b_h
            num_cells = topo.num_cells
            cell_radius = topo.cell_radius
            num_floors = topo.num_floors
            n_total_bs = len(topo.x)
            bs_per_floor = max(1, n_total_bs // max(1, num_floors))

            bld_x, bld_y, bld_z = [], [], []
            for b_idx in range(bs_per_floor // max(1, num_cells)):
                floor_i = b_idx * num_cells
                if floor_i >= len(topo.x): break
                x_b = topo.x[floor_i] - cell_radius
                y_b = topo.y[floor_i] - b_d / 2
                for f in range(num_floors):
                    z0, z1 = f * b_h, (f + 1) * b_h
                    corners = [(x_b, y_b), (x_b+b_w, y_b), (x_b+b_w, y_b+b_d), (x_b, y_b+b_d), (x_b, y_b)]
                    for cx, cy in corners: bld_x.append(cx); bld_y.append(cy); bld_z.append(z0)
                    bld_x.append(None); bld_y.append(None); bld_z.append(None)
                    for cx, cy in corners: bld_x.append(cx); bld_y.append(cy); bld_z.append(z1)
                    bld_x.append(None); bld_y.append(None); bld_z.append(None)
                    for cx, cy in corners[:4]:
                        bld_x.extend([cx, cx, None]); bld_y.extend([cy, cy, None]); bld_z.extend([z0, z1, None])

            fig.add_trace(go.Scatter3d(x=bld_x, y=bld_y, z=bld_z, mode="lines", line=dict(color="sienna", width=2), name="Buildings"))
            heights = list(topo.height) if hasattr(topo, "height") and len(topo.height) > 0 else [bs_height]*len(xs)
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=heights, mode="markers", marker=dict(size=4, color="blue", symbol="square"), name="Indoor BS"))
            
            n_ue = min(len(xs) * 3, 60)
            if n_ue > 0:
                ue_xs = [xs[i % len(xs)] + np.random.uniform(-cell_radius, cell_radius) for i in range(n_ue)]
                ue_ys = [ys[i % len(ys)] + np.random.uniform(-b_d/2, b_d/2) for i in range(n_ue)]
                ue_zs = [heights[i % len(heights)] - np.random.uniform(0, b_h*0.8) for i in range(n_ue)]
                fig.add_trace(go.Scatter3d(x=ue_xs, y=ue_ys, z=ue_zs, mode="markers", marker=dict(size=2, color="red"), name="UE (sample)", opacity=0.6))
                
            return

        if topo_type == "NTN" and self._ntn_topo is not None:
            topo = self._ntn_topo
            sc = 1000.0
            cr_km = topo.cell_radius / sc
            hex_x, hex_y, hex_z = [], [], []
            for x, y in zip(topo.x / sc, topo.y / sc):
                angs = np.linspace(0, 2*np.pi, 7)
                hx = list(x + cr_km * np.cos(angs))
                hy = list(y + cr_km * np.sin(angs))
                hex_x.extend(hx + [None]); hex_y.extend(hy + [None]); hex_z.extend([0]*7 + [None])

            fig.add_trace(go.Scatter3d(x=hex_x, y=hex_y, z=hex_z, mode="lines", line=dict(color="gray", width=2), name="Sector Cells"))
            fig.add_trace(go.Scatter3d(x=list(topo.x/sc), y=list(topo.y/sc), z=[0]*len(topo.x), mode="markers", marker=dict(size=5, color="black", symbol="diamond"), name="Anchor Points"))
            sx, sy, sz = topo.space_station_x/sc, topo.space_station_y/sc, topo.space_station_z/sc
            fig.add_trace(go.Scatter3d(x=[sx], y=[sy], z=[sz], mode="markers", marker=dict(size=8, color="red", symbol="diamond"), name=f"Satellite (el={np.degrees(topo.bs_elevation):.0f}°)"))
            fig.add_trace(go.Scatter3d(x=[sx, sx], y=[sy, sy], z=[0, sz], mode="lines", line=dict(color="blue", width=3), name=f"Height = {sz:.0f} km"))
            fig.add_trace(go.Scatter3d(x=[0, sx], y=[0, sy], z=[0, sz], mode="lines", line=dict(color="green", width=3, dash="dash"), name=f"Slant = {topo.bs_radius/sc:.0f} km"))
            
            n_ue = min(len(topo.x)*5, 80)
            if n_ue > 0:
                ue_x = [topo.x[i%len(topo.x)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                ue_y = [topo.y[i%len(topo.y)]/sc + np.random.uniform(-cr_km*0.8, cr_km*0.8) for i in range(n_ue)]
                fig.add_trace(go.Scatter3d(x=ue_x, y=ue_y, z=[0]*n_ue, mode="markers", marker=dict(size=2, color="red"), name="UE (sample)", opacity=0.5))
                
            fig.update_layout(scene=dict(xaxis_title="x [km]", yaxis_title="y [km]", zaxis_title="z [km]"))
            return

        if draw_hex and hex_centers:
            hex_x, hex_y, hex_z = [], [], []
            for cx, cy in hex_centers:
                pts = self._hexagon_points(cx, cy, hex_radius, rotation_deg=30)
                pts = np.vstack([pts, pts[0]])
                hex_x.extend(pts[:, 0]); hex_x.append(None)
                hex_y.extend(pts[:, 1]); hex_y.append(None)
                hex_z.extend([0]*len(pts)); hex_z.append(None)

            fig.add_trace(go.Scatter3d(x=hex_x, y=hex_y, z=hex_z, mode="lines", line=dict(color="lightgray", width=2), name="Grid / Cells"))

        color = "blue"
        if topo_type == "HOTSPOT": color = "green"
        elif topo_type == "SINGLE_EARTH_STATION": color = "red"

        fig.add_trace(go.Scatter3d(x=xs, y=ys, z=[bs_height]*len(xs), mode="markers", marker=dict(size=5, color=color), name=f"{topo_type.replace('_', ' ').title()} BS"))

        post_x, post_y, post_z = [], [], []
        for x, y in zip(xs, ys):
            post_x.extend([x, x, None]); post_y.extend([y, y, None]); post_z.extend([0, bs_height, None])

        fig.add_trace(go.Scatter3d(x=post_x, y=post_y, z=post_z, mode="lines", line=dict(color=color, width=3), showlegend=False))

        sec_radius = hex_radius * 0.8 if hex_radius > 0 else 50.0
        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            for x, y, az in zip(xs, ys, azs):
                self._add_wedge_plotly(fig, x, y, sec_radius, az, bs_height, color)

        if topo_type not in ("SINGLE_EARTH_STATION", "MSS_D2D"):
            val = getattr(self.app, "ue_k", None)
            ue_k = _safe_int(val.get() if hasattr(val, 'get') else val, 3)
            ue_radius = hex_radius * 0.9 if hex_radius > 0 else sec_radius * 0.9
            if topo_type == "HOTSPOT":
                val_h = getattr(self.app, "hotspot_max_dist_ue", None)
                ue_radius = _safe_float(val_h.get() if hasattr(val_h, 'get') else val_h, 50.0)
            unique_bs = list(set(zip(xs, ys)))
            n_ue = min(len(unique_bs) * max(ue_k, 1), 120)
            ue_xs, ue_ys = [], []
            for i in range(n_ue):
                bx, by = unique_bs[i % len(unique_bs)]
                ang = np.random.uniform(0, 2*np.pi)
                r = np.random.uniform(0, ue_radius)
                ue_xs.append(bx + r*np.cos(ang))
                ue_ys.append(by + r*np.sin(ang))
            if ue_xs:
                fig.add_trace(go.Scatter3d(x=ue_xs, y=ue_ys, z=[ue_height]*len(ue_xs), mode="markers", marker=dict(size=2, color="red"), name=f"UE (K={ue_k})", opacity=0.6))

        if topo_type == "MSS_D2D":
            fig.add_trace(go.Scatter3d(x=xs[:1], y=ys[:1], z=[ue_height], mode="markers", marker=dict(size=6, color="green", symbol="diamond"), name="Device 1"))
            if len(xs) > 1:
                fig.add_trace(go.Scatter3d(x=xs[1:2], y=ys[1:2], z=[ue_height], mode="markers", marker=dict(size=6, color="purple", symbol="diamond"), name="Device 2"))
                fig.add_trace(go.Scatter3d(x=[xs[0], xs[1]], y=[ys[0], ys[1]], z=[ue_height]*2, mode="lines", line=dict(color="orange", width=4, dash="dash"), name="D2D Link"))

        if str(self.app.var_system.get()) == "SINGLE_EARTH_STATION":
            mode_var = getattr(self.app, "se_loc_type", None)
            mode = str(mode_var.get() if hasattr(mode_var, "get") else "FIXED").strip()

            if mode == "FIXED":
                vx = getattr(self.app, "se_loc_fixed_x", None)
                x0 = _safe_float(vx.get() if hasattr(vx, 'get') else vx, 0.0)
                vy = getattr(self.app, "se_loc_fixed_y", None)
                y0 = _safe_float(vy.get() if hasattr(vy, 'get') else vy, 0.0)

                fig.add_trace(go.Scatter3d(x=[x0], y=[y0], z=[bs_height], mode="markers", marker=dict(size=6, color="red"), name="Single Earth Station"))
            elif mode == "UNIFORM_DIST":
                vmin = getattr(self.app, "se_loc_ud_min_dist_to_center", None)
                rmin = _safe_float(vmin.get() if hasattr(vmin, 'get') else vmin, 10)
                vmax = getattr(self.app, "se_loc_ud_max_dist_to_center", None)
                rmax = _safe_float(vmax.get() if hasattr(vmax, 'get') else vmax, 100)

                ang = np.random.uniform(0, 2*np.pi)
                r = np.random.uniform(rmin, rmax)
                x0, y0 = r*np.cos(ang), r*np.sin(ang)

                fig.add_trace(go.Scatter3d(x=[x0], y=[y0], z=[bs_height], mode="markers", marker=dict(size=6, color="red"), name="Single Earth Station"))
                th = np.linspace(0, 2*np.pi, 100)
                fig.add_trace(go.Scatter3d(x=rmin*np.cos(th), y=rmin*np.sin(th), z=[bs_height]*len(th), mode="lines", line=dict(color="red", dash="dot"), name="min radius"))
                fig.add_trace(go.Scatter3d(x=rmax*np.cos(th), y=rmax*np.sin(th), z=[bs_height]*len(th), mode="lines", line=dict(color="red", dash="dot"), name="max radius"))
        fig.update_layout(scene=dict(aspectmode="data"))

    def _draw_global_plotly(self, fig: "go.Figure", topo_type: str, data: Dict[str, Any]):
        Re = WGS84_A
        b = WGS84_A * (1.0 - WGS84_F)  # WGS84 polar radius
        u = np.linspace(0, 2*np.pi, 80)
        v = np.linspace(0, np.pi, 40)
        X = Re * np.outer(np.cos(u), np.sin(v))
        Y = Re * np.outer(np.sin(u), np.sin(v))
        # True WGS84 ellipsoid so georeferenced surface points sit on the globe.
        Z = b * np.outer(np.ones_like(u), np.cos(v))

        if topo_type == "Macro_countries":
            fig.add_trace(go.Surface(
                x=X, y=Y, z=Z, surfacecolor=np.zeros_like(Z),
                colorscale=[[0, "lightblue"], [1, "lightblue"]],
                opacity=0.3, showscale=False, name="Earth Surface"
            ))

            if self.app.show_borders.get():
                self._draw_borders_plotly(fig)

            bs_lats, bs_lons = self._compute_macro_countries_bs(data)

            bs_x, bs_y, bs_z = lla_to_ecef(bs_lats, bs_lons, 0)
            offset = 1.005
            fig.add_trace(go.Scatter3d(
                x=np.asarray(bs_x) * offset, y=np.asarray(bs_y) * offset, z=np.asarray(bs_z) * offset,
                mode="markers", marker=dict(size=3, color="cyan", symbol="diamond"), name=f"BS ({len(bs_lats)})"
            ))

        sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)

        surface_color = None
        cmin, cmax = None, None

        if self.app.var_show_gainmap.get() and sat_obj:
            ant = getattr(sat_obj, "antenna", None)
            if ant:
                vmin = float(self.app.var_gain_vmin.get())
                vmax = float(self.app.var_gain_vmax.get())
                surface_color = self._compute_gain_surface(sx, sy, sz, ant, X, Y, Z, vmin, vmax)
                cmin, cmax = vmin, vmax

        fig.add_trace(go.Surface(
            x=X, y=Y, z=Z,
            surfacecolor=surface_color if surface_color is not None else np.zeros_like(Z),
            colorscale="Turbo" if surface_color is not None else [[0, "lightblue"], [1, "lightblue"]],
            cmin=cmin, cmax=cmax,
            opacity=0.7 if surface_color is not None else 0.3,
            showscale=bool(surface_color is not None),
            name="Earth Surface"
        ))

        if self.app.show_borders.get():
            self._draw_borders_plotly(fig)

        fig.add_trace(go.Scatter3d(x=[sx], y=[sy], z=[sz], mode="markers", marker=dict(size=6, color="purple"), name="Satellite"))
        fig.add_trace(go.Scatter3d(x=[ex], y=[ey], z=[ez], mode="markers", marker=dict(size=5, color="blue"), name="Earth Station"))
        fig.add_trace(go.Scatter3d(x=[sx, ex], y=[sy, ey], z=[sz, ez], mode="lines", line=dict(color="purple", dash="dash", width=2), name="Link Path"))

        if self.app.show_beamwidth.get():
            bw = self._determine_beamwidth(sat_obj)
            fp_pts = self._compute_footprint_boundary(sx, sy, sz, bw)
            if fp_pts is not None:
                fig.add_trace(go.Scatter3d(x=fp_pts[:, 0], y=fp_pts[:, 1], z=fp_pts[:, 2], mode="lines", line=dict(color="magenta", width=4), name=f"Footprint ({bw:.1f}°)"))

        fig.update_layout(scene=dict(aspectmode="data"))

    def _sharc_data_dir(self) -> str:
        """Absolute path to the SHARC package root (…/sharc), used to locate the
        bundled shapefile / SEDAC raster. This file lives at
        …/sharc/gui/ui/components/plot_engines.py, so four levels up is …/sharc.
        """
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))

    def _compute_macro_countries_bs(self, data: Dict[str, Any]):
        """Resolve base-station lat/lon for the 'Macro_countries' topology using
        the real SHARC ``TopologyCountries`` engine, with a per-parameter cache
        and a deterministic random fallback.

        Shared by the matplotlib and plotly global renderers so both show
        identical station placement (previously this logic was duplicated and
        could drift between the two engines).
        """
        countries_str = _get_countries_text(self.app, "Brazil")
        num_bs_val = _safe_int(_get_imt_value(self.app, "topo_num_bs"), 50)
        raster_encoding = _normalize_raster_encoding(_get_imt_value(self.app, "topo_raster_enc", "uniform"))
        raster_path_ui = _coerce_str(_get_imt_value(self.app, "path_raster", ""), "")
        cache_key = "|".join([
            countries_str, str(num_bs_val), raster_encoding, raster_path_ui,
            _coerce_str(_get_imt_value(self.app, "topo_dist_type", ""), ""),
            _coerce_str(_get_imt_value(self.app, "topo_min_density_threshold", ""), ""),
            _coerce_str(_get_imt_value(self.app, "topo_density_exponent", ""), ""),
            _coerce_str(_get_imt_value(self.app, "topo_sedac_palette_mode", ""), ""),
            _coerce_str(_get_imt_value(self.app, "topo_sedac_min", ""), ""),
            _coerce_str(_get_imt_value(self.app, "topo_sedac_max", ""), ""),
        ])

        bs_lats = getattr(self.app, "_mc_bs_lats", None)
        bs_lons = getattr(self.app, "_mc_bs_lons", None)
        last_key = getattr(self.app, "_mc_cache_key", None)
        if bs_lats is not None and bs_lons is not None and last_key == cache_key:
            return bs_lats, bs_lons

        try:
            if TopologyCountries is None or ParametersCountries is None:
                raise ImportError("TopologyCountries/ParametersCountries not available")

            param_c = ParametersCountries()
            names = _parse_country_names(countries_str)
            param_c.country_names = names if names else ["Brazil"]
            param_c.num_bs_total = num_bs_val
            param_c.rng_seed = _safe_int(_get_imt_value(self.app, "topo_rng"), param_c.rng_seed)
            param_c.cell_radius = _safe_float(_get_imt_value(self.app, "topo_cell_radius"), param_c.cell_radius)
            param_c.dist_type = _coerce_str(_get_imt_value(self.app, "topo_dist_type", ""), "") or None
            param_c.raster_encoding = raster_encoding if raster_encoding != "uniform" else "indexed"
            param_c.sedac_palette_mode = _coerce_str(_get_imt_value(self.app, "topo_sedac_palette_mode", ""), param_c.sedac_palette_mode)
            param_c.sedac_min = _safe_float(_get_imt_value(self.app, "topo_sedac_min"), param_c.sedac_min)
            param_c.sedac_max = _safe_float(_get_imt_value(self.app, "topo_sedac_max"), param_c.sedac_max)
            param_c.min_density_threshold = _safe_float(_get_imt_value(self.app, "topo_min_density_threshold"), param_c.min_density_threshold)
            param_c.density_exponent = _safe_float(_get_imt_value(self.app, "topo_density_exponent"), param_c.density_exponent)

            base_dir = self._sharc_data_dir()
            shp_path = os.path.join(base_dir, "topology", "map", "ne_110m_admin_0_countries.shp")
            act_path = os.path.join(base_dir, "topology", "map", "sedac_pop.act")
            # SEDAC raster is shipped as .TIFF (upper case); accept either case.
            ras_candidates = [
                os.path.join(base_dir, "topology", "map", "SEDAC_map2.TIFF"),
                os.path.join(base_dir, "topology", "map", "SEDAC_map2.tiff"),
            ]
            ras_path = next((p for p in ras_candidates if os.path.exists(p)), ras_candidates[0])

            shp_path_ui = _coerce_str(_get_imt_value(self.app, "path_shp", ""), "")
            if shp_path_ui:
                param_c.shapefile_path = shp_path_ui
            elif os.path.exists(shp_path):
                param_c.shapefile_path = shp_path
            if raster_encoding != "uniform":
                if raster_path_ui:
                    param_c.population_raster = raster_path_ui
                elif os.path.exists(ras_path):
                    param_c.population_raster = ras_path
            else:
                param_c.population_raster = None
            if os.path.exists(act_path):
                param_c.act_colormap_path = act_path

            topo = TopologyCountries(param_c, None)
            topo.calculate_coordinates()
            bs_lats, bs_lons = topo.lats, topo.lons
        except Exception as e:
            print(f"[PreviewTab] TopologyCountries failed: {e}")
            # Deterministic fallback: a fixed RandomState keeps the preview
            # stable across redraws instead of re-randomising every refresh.
            n_bs = num_bs_val
            center_lat = _safe_float(_get_imt_value(self.app, "topo_center_lat"), -15.0)
            center_lon = _safe_float(_get_imt_value(self.app, "topo_center_lon"), -47.0)
            rng = np.random.RandomState(42)
            bs_lats = center_lat + rng.uniform(-15, 15, n_bs)
            bs_lons = center_lon + rng.uniform(-20, 20, n_bs)

        self.app._mc_bs_lats = bs_lats
        self.app._mc_bs_lons = bs_lons
        self.app._mc_cache_key = cache_key
        return bs_lats, bs_lons

    def _draw_hexagon_shape_mpl(self, x, y, r, rotation_deg=0, label=None, **kwargs):
        pts = self._hexagon_points(x, y, r, rotation_deg=rotation_deg)
        pts = np.vstack([pts, pts[0]])
        line = self.ax3d.plot(pts[:, 0], pts[:, 1], [0]*len(pts), **kwargs)
        if label:
            line[0].set_label(label)

    def _add_wedge_outline3d_mpl(self, ax, x, y, r, az_deg, half_bw=30, z_plane=0, color="k", label=None):
        th0 = np.radians(az_deg - half_bw)
        th1 = np.radians(az_deg + half_bw)
        ths = np.linspace(th0, th1, 12)
        pts = [(x, y)] + [(x + r*math.cos(t), y + r*math.sin(t)) for t in ths] + [(x, y)]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.plot(xs, ys, [z_plane]*len(xs), color=color, lw=1, label=label)

    def _set_equal_3d_mpl(self, ax, xs, ys, z_top):
        xs = np.array(xs)
        ys = np.array(ys)
        span = max(xs.max()-xs.min(), ys.max()-ys.min(), 100)
        cx = (xs.max()+xs.min())/2
        cy = (ys.max()+ys.min())/2
        ax.set_xlim(cx - span/2, cx + span/2)
        ax.set_ylim(cy - span/2, cy + span/2)
        ax.set_zlim(0, max(z_top, span/4))

    def _get_border_coords(self) -> List[Tuple[np.ndarray, np.ndarray, bool]]:
        coords = []
        tc_var = getattr(self.app, "topo_countries", None)
        tc_val = str(tc_var.get() if hasattr(tc_var, 'get') else tc_var)
        selected_names = [c.strip().lower() for c in tc_val.split(",") if c.strip()]
        
        paths_to_try = []
        path_shp_var = getattr(self.app, "path_shp", None)
        path_shp_val = str(path_shp_var.get() if hasattr(path_shp_var, 'get') else path_shp_var)
        
        if path_shp_val:
            paths_to_try.append(path_shp_val.strip())
            
        try:
            base_dir = self._sharc_data_dir()
            paths_to_try.extend([
                os.path.join(base_dir, "topology", "map", "ne_110m_admin_0_countries.shp"),
                os.path.join(base_dir, "data", "countries", "ne_110m_admin_0_countries.shp")
            ])
        except Exception:
            pass

        def _is_selected(record_vals):
            for val in record_vals:
                if str(val).lower() in selected_names: return True
            return False

        if HAS_PYSHP:
            for p in paths_to_try:
                if os.path.exists(p):
                    try:
                        r = pyshp.Reader(p)
                        for sr in r.shapeRecords():
                            is_seq = _is_selected(sr.record)
                            if sr.shape.points:
                                lons, lats = zip(*sr.shape.points)
                                coords.append((np.array(lats), np.array(lons), is_seq))
                        if coords: return coords
                    except Exception:
                        pass

        if HAS_GEOPANDAS:
            for p in paths_to_try:
                if os.path.exists(p):
                    try:
                        gdf = gpd.read_file(p)
                        name_cols = [c for c in gdf.columns if c in ["ADMIN", "name", "NAME", "admin", "Country", "SOVEREIGNT"]]
                        for idx, row in gdf.iterrows():
                            is_seq = any(str(row[c]).lower() in selected_names for c in name_cols) if name_cols else False
                            geom = row.geometry
                            if geom is None: continue
                            if geom.geom_type == 'Polygon':
                                lons, lats = geom.exterior.coords.xy
                                coords.append((np.array(lats), np.array(lons), is_seq))
                            elif geom.geom_type == 'MultiPolygon':
                                for poly in geom.geoms:
                                    lons, lats = poly.exterior.coords.xy
                                    coords.append((np.array(lats), np.array(lons), is_seq))
                        if coords: return coords
                    except Exception:
                        pass
            try:
                if hasattr(gpd.datasets, "get_path"):
                    gdf = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
                    name_cols = [c for c in gdf.columns if c in ["ADMIN", "name", "NAME", "admin", "Country", "SOVEREIGNT"]]
                    for idx, row in gdf.iterrows():
                        is_seq = any(str(row[c]).lower() in selected_names for c in name_cols) if name_cols else False
                        geom = row.geometry
                        if geom is None: continue
                        if geom.geom_type == 'Polygon':
                            lons, lats = geom.exterior.coords.xy
                            coords.append((np.array(lats), np.array(lons), is_seq))
                        elif geom.geom_type == 'MultiPolygon':
                            for poly in geom.geoms:
                                lons, lats = poly.exterior.coords.xy
                                coords.append((np.array(lats), np.array(lons), is_seq))
                    if coords: return coords
            except Exception:
                pass
                
        return coords

    def _draw_borders_mpl(self):
        coords = self._get_border_coords()
        for lat, lon, is_selected in coords:
            x, y, z = lla_to_ecef(lat, lon, 0)
            offset = 1.002
            x = np.asarray(x) * offset; y = np.asarray(y) * offset; z = np.asarray(z) * offset
            if is_selected:
                self.ax3d.plot(x, y, z, color="#00ff00", lw=2.0, alpha=1.0)
            else:
                self.ax3d.plot(x, y, z, color="#ffffff", lw=0.6, alpha=0.9)

    def _draw_footprint_mpl(self, sx, sy, sz, bw):
        fp = self._compute_footprint_boundary(sx, sy, sz, bw)
        if fp is not None:
            self.ax3d.plot(fp[:, 0], fp[:, 1], fp[:, 2], color="magenta", lw=1.5, label="Footprint")

    def _draw_borders_plotly(self, fig):
        coords = self._get_border_coords()
        for lat, lon, is_selected in coords:
            x, y, z = lla_to_ecef(lat, lon, 0.0)
            norm = np.sqrt(x*x + y*y + z*z)
            scale = (WGS84_A * 1.001) / norm
            color = "lime" if is_selected else "white"
            width = 3 if is_selected else 1
            fig.add_trace(go.Scatter3d(
                x=x*scale, y=y*scale, z=z*scale,
                mode="lines", line=dict(color=color, width=width), showlegend=False
            ))

    def _add_wedge_plotly(self, fig, x, y, r, az, z, color):
        th0, th1 = np.radians(az - 30), np.radians(az + 30)
        ths = np.linspace(th0, th1, 10)
        px = [x] + [x + r*math.cos(t) for t in ths] + [x]
        py = [y] + [y + r*math.sin(t) for t in ths] + [y]
        pz = [z] * len(px)
        fig.add_trace(go.Scatter3d(x=px, y=py, z=pz, mode="lines", line=dict(color=color, width=2), showlegend=False))

    def _hexagon_points(self, x, y, r, rotation_deg=0):
        angles = np.linspace(np.radians(rotation_deg), np.radians(rotation_deg+360), 7)[:-1]
        return np.column_stack([x + r * np.cos(angles), y + r * np.sin(angles)])

    def _save_image(self):
        if self.app.plot_engine.get() == "plotly":
            QMessageBox.information(
                self, "Save Image",
                "For Plotly, please use the 'camera' icon in the plot toolbar \n"
                "or open in browser and save from there."
            )
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG Image (*.png);;All Files (*.*)")
        if path:
            try:
                self.fig3d.savefig(path, dpi=200, bbox_inches='tight')
                QMessageBox.information(self, "Saved", f"Image saved successfully to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save image:\n{e}")