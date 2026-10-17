"""Serializes a real :class:`~core.scene_graph.SceneGraph` (built from the
actual SHARC engine objects and the actual GUI/YAML parameters) into the
JSON contract the CesiumJS Preview spike's ``app.js`` consumes.

This is the piece that replaces
``sharc/gui/web/cesium_preview/demo_scene.py``'s hardcoded/default-parameter
topology instantiations with the scenario the user actually configured in
the SHARC GUI — see CESIUMJS_MIGRATION_PLAN.md's Fase 4/"integração real"
notes. The JSON *shape* produced here is intentionally identical to what
``demo_scene.py`` produces, so ``app.js`` needed no changes to consume
either one.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict

import numpy as np

from utils import _safe_float
from sharc.support.geodesy import WGS84_A, ecef_to_lla


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def _footprint_boundary_lla(sx: float, sy: float, sz: float, bw_deg: float, n: int = 128):
    """Same algorithm as ``Geometry3DMixin._compute_footprint_boundary``,
    returning lat/lon degrees instead of ECEF (see
    ``web/cesium_preview/demo_scene.py`` for the twin implementation and
    why this one isn't just imported from there — that module deliberately
    stays independent of this GUI-only package)."""
    Re = WGS84_A
    S = np.array([sx, sy, sz], dtype=float)
    rs = float(np.linalg.norm(S))
    if rs <= Re:
        return []

    alpha = math.radians(max(0.1, min(179.0, bw_deg)) / 2.0)
    u = -S / rs
    tmp = np.array([0, 0, 1.0])
    if abs(np.dot(tmp, u)) > 0.9:
        tmp = np.array([0, 1.0, 0])
    e1 = _unit(np.cross(u, tmp))
    e2 = _unit(np.cross(u, e1))

    pts = []
    for phi in np.linspace(0, 2 * np.pi, n):
        d = math.cos(alpha) * u + math.sin(alpha) * (math.cos(phi) * e1 + math.sin(phi) * e2)
        B = 2.0 * np.dot(S, d)
        C = rs * rs - Re * Re
        disc = B * B - 4 * C
        if disc >= 0:
            t = (-B - math.sqrt(disc)) / 2.0
            pts.append(S + t * d)

    if not pts:
        return []
    pts_arr = np.array(pts)
    lat, lon, _ = ecef_to_lla(pts_arr[:, 0], pts_arr[:, 1], pts_arr[:, 2])
    return [{"lat_deg": float(a), "lon_deg": float(b)} for a, b in zip(lat, lon)]


class CesiumBridgeMixin:
    """Converts this tab's real :class:`SceneGraph` into Cesium-ready JSON."""

    def _compute_gain_map_cesium(self, glob, vmin_db: float, vmax_db: float,
                                  beamwidth_deg: float = None,
                                  grid_step_deg: float = 2.0) -> dict | None:
        """Compute antenna gain on a lat/lon grid for CesiumJS heatmap."""
        from utils import lla_to_ecef

        S = np.array([glob.satellite_x, glob.satellite_y, glob.satellite_z])
        rs = float(np.linalg.norm(S))
        if rs < WGS84_A:
            return None

        ant = None
        if glob.satellite_obj is not None:
            ant = getattr(glob.satellite_obj, "antenna", None)
            if isinstance(ant, (list, tuple, np.ndarray)) and len(ant) > 0:
                ant = ant[0]

        sub_lat = glob.satellite_lat_deg
        sub_lon = glob.satellite_lon_deg

        earth_ang = math.degrees(math.asin(min(1.0, WGS84_A / rs)))
        extent = min(earth_ang * 1.5, 80.0)

        lat_min = max(-85, sub_lat - extent)
        lat_max = min(85, sub_lat + extent)
        lon_min = sub_lon - extent
        lon_max = sub_lon + extent

        lats = np.arange(lat_min, lat_max + grid_step_deg, grid_step_deg)
        lons = np.arange(lon_min, lon_max + grid_step_deg, grid_step_deg)

        lon_grid, lat_grid = np.meshgrid(lons, lats)
        lat_flat = lat_grid.ravel()
        lon_flat = lon_grid.ravel()

        px, py, pz = lla_to_ecef(lat_flat, lon_flat, np.zeros_like(lat_flat))
        P = np.column_stack((px, py, pz))

        u_bore = _unit(-S)
        D = P - S
        d_norms = np.linalg.norm(D, axis=1)
        d_norms[d_norms == 0] = 1.0
        D_unit = D / d_norms[:, np.newaxis]

        dots = np.clip(np.dot(D_unit, u_bore), -1.0, 1.0)
        angles_deg = np.degrees(np.arccos(dots))

        # Ângulo azimutal em torno do eixo (padrões não simétricos: S.1855, S.1528-Taylor)
        ref = np.array([0.0, 0.0, 1.0]) if abs(u_bore[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = _unit(np.cross(u_bore, ref))
        e2 = np.cross(u_bore, e1)
        theta_deg = np.degrees(np.arctan2(D_unit @ e2, D_unit @ e1))

        if ant is not None:
            from core.antenna_service import gain_at
            try:
                gains = gain_at(ant, angles_deg, theta_deg)
            except Exception as exc:  # padrão sem suporte: avisa, não desenha parábola falsa
                self._report_scene_problem(f"gain map unavailable for this antenna pattern: {exc}")
                return None
            gains = np.nan_to_num(gains, nan=vmin_db)
        else:
            bw = beamwidth_deg or 8.7
            half_bw = max(bw / 2.0, 0.1)
            gains = vmax_db - (angles_deg / half_bw) ** 2 * (vmax_db - vmin_db)

        gains = np.clip(gains, vmin_db, vmax_db)

        gain_range = vmax_db - vmin_db
        norm = (gains - vmin_db) / gain_range if gain_range > 0 else np.zeros_like(gains)
        norm = np.clip(norm, 0.0, 1.0)

        cells = []
        for i in range(len(lat_flat)):
            if norm[i] < 0.01:
                continue
            cells.append({
                "lat": round(float(lat_flat[i]), 2),
                "lon": round(float(lon_flat[i]), 2),
                "v": round(float(norm[i]), 3),
            })

        if not cells:
            return None
        return {"cells": cells, "step": grid_step_deg, "vmin": vmin_db, "vmax": vmax_db}

    def _reference_dict(self, local) -> Dict[str, float]:
        return {
            "lat_deg": local.reference_lat_deg,
            "lon_deg": local.reference_lon_deg,
            "alt_m": local.reference_alt_m,
        }

    def _hex_sector_scene_dict(self, topo_type: str, local) -> Dict[str, Any]:
        base_stations = [
            {"x": float(x), "y": float(y), "azimuth_deg": float(az)}
            for x, y, az in zip(local.xs, local.ys, local.azimuths)
        ]
        hex_centers = [{"x": float(x), "y": float(y)} for x, y in local.hex_centers]

        rng = np.random.RandomState(42)
        ue_positions = []
        for hc in local.hex_centers:
            cx, cy = float(hc[0]), float(hc[1])
            for _ in range(local.ue_k * 2):
                ang = rng.uniform(0, 2 * np.pi)
                r = rng.uniform(0, local.hex_radius * 0.9) if local.hex_radius > 0 else 0.0
                ue_positions.append({"x": cx + r * np.cos(ang), "y": cy + r * np.sin(ang)})

        return {
            "topology_type": topo_type,
            "reference": self._reference_dict(local),
            "hex_radius_m": local.hex_radius if local.hex_radius > 0 else 50.0,
            "bs_height_m": local.bs_height_m,
            "ue_height_m": local.ue_height_m,
            "downtilt_deg": local.downtilt_deg,
            "base_stations": base_stations,
            "hex_centers": hex_centers,
            "ue_positions": ue_positions,
        }

    def _indoor_scene_dict(self, local) -> Dict[str, Any]:
        topo = local.indoor_topo
        n_total_bs = len(topo.x)
        bs_per_floor = max(1, n_total_bs // max(1, topo.num_floors))
        n_buildings = bs_per_floor // max(1, topo.num_cells)

        buildings = []
        for b_idx in range(n_buildings):
            floor_i = b_idx * topo.num_cells
            if floor_i >= len(topo.x):
                break
            x0 = float(topo.x[floor_i] - topo.cell_radius)
            y0 = float(topo.y[floor_i] - topo.b_d / 2)
            buildings.append({
                "x0": x0, "y0": y0,
                "width": float(topo.b_w), "depth": float(topo.b_d),
                "floor_height": float(topo.b_h), "num_floors": int(topo.num_floors),
            })

        heights = (list(topo.height) if hasattr(topo, "height") and len(topo.height) > 0
                   else [local.bs_height_m] * n_total_bs)
        base_stations = [
            {"x": float(x), "y": float(y), "z": float(z)}
            for x, y, z in zip(topo.x, topo.y, heights)
        ]

        rng = np.random.RandomState(42)
        ue_positions = []
        n_ue = min(n_total_bs * 3, 60)
        for i in range(n_ue):
            bi = i % n_total_bs
            ue_positions.append({
                "x": float(topo.x[bi]) + rng.uniform(-topo.cell_radius, topo.cell_radius),
                "y": float(topo.y[bi]) + rng.uniform(-topo.b_d / 2, topo.b_d / 2),
                "z": float(heights[bi]) - rng.uniform(0, topo.b_h * 0.8),
            })

        return {
            "topology_type": "INDOOR",
            "reference": self._reference_dict(local),
            "ue_height_m": local.ue_height_m,
            "buildings": buildings,
            "base_stations": base_stations,
            "ue_positions": ue_positions,
        }

    def _mss_d2d_scene_dict(self, local) -> Dict[str, Any]:
        """Two D2D devices + link — matches PlotEnginesMixin's dedicated
        MSS_D2D block (Device 1/Device 2/D2D Link), not the generic
        hex/sector rendering the other local topologies get."""
        devices = [{"x": float(x), "y": float(y)} for x, y in zip(local.xs, local.ys)]
        return {
            "topology_type": "MSS_D2D",
            "reference": self._reference_dict(local),
            "ue_height_m": local.ue_height_m,
            "devices": devices,
        }

    def _single_earth_station_scene_dict(self, local) -> Dict[str, Any]:
        """Single earth station placement — matches PlotEnginesMixin's
        dedicated SINGLE_EARTH_STATION block.

        Covers the FIXED placement mode (the common case). UNIFORM_DIST
        placement and the pointing-vector/uncertainty-cone visualization
        (also present in the legacy Matplotlib renderer) are not
        replicated here yet — see CESIUMJS_MIGRATION_PLAN.md.
        """
        mode_var = getattr(self.app, "se_loc_type", None)
        mode = str(mode_var.get() if hasattr(mode_var, "get") else "FIXED").strip()

        if mode == "UNIFORM_DIST":
            vmin = getattr(self.app, "se_loc_ud_min_dist_to_center", None)
            rmin = _safe_float(vmin.get() if hasattr(vmin, "get") else vmin, 10.0)
            vmax = getattr(self.app, "se_loc_ud_max_dist_to_center", None)
            rmax = _safe_float(vmax.get() if hasattr(vmax, "get") else vmax, 100.0)
            rng = np.random.RandomState(42)
            ang = rng.uniform(0, 2 * np.pi)
            r = rng.uniform(rmin, rmax)
            x0, y0 = r * np.cos(ang), r * np.sin(ang)
        else:
            vx = getattr(self.app, "se_loc_fixed_x", None)
            x0 = _safe_float(vx.get() if hasattr(vx, "get") else vx, 0.0)
            vy = getattr(self.app, "se_loc_fixed_y", None)
            y0 = _safe_float(vy.get() if hasattr(vy, "get") else vy, 0.0)

        el_var = getattr(self.app, "se_elevation", None)
        elevation_deg = _safe_float(el_var.get() if hasattr(el_var, "get") else el_var, 25.0)
        az_var = getattr(self.app, "se_azimuth", None)
        azimuth_deg = _safe_float(az_var.get() if hasattr(az_var, "get") else az_var, 0.0)

        z0 = float(local.bs_height_m)
        engine = getattr(self, "_current_engine", None)
        if engine is not None and engine.system is not None                 and str(engine.params.general.system).upper() == "SINGLE_EARTH_STATION":
            g = engine.system.geom       # posição e apontamento reais do motor
            x0, y0, z0 = float(g.x_global[0]), float(g.y_global[0]), float(g.z_global[0])
            azimuth_deg = float(g.pointn_azim_global[0])
            elevation_deg = float(g.pointn_elev_global[0])

        return {
            "topology_type": "SINGLE_EARTH_STATION",
            "reference": self._reference_dict(local),
            "bs_height_m": local.bs_height_m,
            "station": {"x": float(x0), "y": float(y0), "z": z0},
            "antenna_elevation_deg": elevation_deg,
            "antenna_azimuth_deg": azimuth_deg,
        }

    def _ntn_scene_dict(self, local) -> Dict[str, Any]:
        topo = local.ntn_topo
        anchor_points = [{"x": float(x), "y": float(y)} for x, y in zip(topo.x, topo.y)]

        rng = np.random.RandomState(42)
        ue_positions = []
        n_ue = min(len(topo.x) * 5, 80)
        for i in range(n_ue):
            bi = i % len(topo.x)
            ue_positions.append({
                "x": float(topo.x[bi]) + rng.uniform(-topo.cell_radius * 0.8, topo.cell_radius * 0.8),
                "y": float(topo.y[bi]) + rng.uniform(-topo.cell_radius * 0.8, topo.cell_radius * 0.8),
            })

        return {
            "topology_type": "NTN",
            "reference": self._reference_dict(local),
            "hex_radius_m": float(topo.cell_radius),
            "anchor_points": anchor_points,
            "satellite": {
                "x": float(topo.space_station_x), "y": float(topo.space_station_y),
                "z": float(topo.space_station_z),
            },
            "elevation_deg": float(np.degrees(topo.bs_elevation)),
            "slant_range_m": float(topo.bs_radius),
            "ue_positions": ue_positions,
        }

    def _borders_dict(self):
        """Country border polylines, reusing PlotEnginesMixin._get_border_coords()
        (same bundled Natural Earth shapefile the Matplotlib renderer uses) —
        one entry per polygon ring, lat/lon in degrees, ``selected`` marks the
        countries the user picked in the IMT/Countries field."""
        borders = []
        for lat, lon, is_selected in self._get_border_coords():
            borders.append({
                "lat_deg": [float(v) for v in lat],
                "lon_deg": [float(v) for v in lon],
                "selected": bool(is_selected),
            })
        return borders

    def _global_scene_dict(self, topo_type: str, glob) -> Dict[str, Any]:
        beamwidth = self._determine_beamwidth(glob.satellite_obj) if self.app.show_beamwidth.get() else None
        footprint = []
        if beamwidth is not None:
            footprint = _footprint_boundary_lla(
                glob.satellite_x, glob.satellite_y, glob.satellite_z, beamwidth,
            )

        scene = {
            "topology_type": topo_type,
            "satellite": {
                "lat_deg": glob.satellite_lat_deg, "lon_deg": glob.satellite_lon_deg,
                "alt_m": glob.satellite_alt_m,
            },
            "earth_station": {
                "lat_deg": glob.earth_station_lat_deg, "lon_deg": glob.earth_station_lon_deg,
                "alt_m": glob.earth_station_alt_m,
            },
            "beamwidth_deg": beamwidth,
            "footprint": footprint,
        }

        if self.app.show_borders.get():
            scene["borders"] = self._borders_dict()

        if topo_type == "Macro_countries" and glob.country_bs_lats is not None:
            bs_lats = glob.country_bs_lats
            bs_lons = glob.country_bs_lons
            scene["country_bs"] = [
                {"lat_deg": float(lat), "lon_deg": float(lon)}
                for lat, lon in zip(bs_lats, bs_lons)
            ]
            if len(bs_lats) > 0:
                scene["bs_centroid"] = {
                    "lat_deg": float(np.mean(bs_lats)),
                    "lon_deg": float(np.mean(bs_lons)),
                }

        if self.app.var_show_gainmap.get():
            try:
                vmin = float(self.app.var_gain_vmin.get())
                vmax = float(self.app.var_gain_vmax.get())
                gain_map = self._compute_gain_map_cesium(
                    glob, vmin, vmax, beamwidth_deg=beamwidth)
                if gain_map:
                    scene["gain_map"] = gain_map
            except Exception:
                pass

        return scene

    def _scene_graph_to_cesium_dict(self, topo_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the real SceneGraph for *topo_type* and return Cesium-ready JSON."""
        scene = self._build_scene_graph(topo_type, data)

        if scene.is_global:
            try:
                from core.engine_scene import build_engine_scene
                engine = build_engine_scene(data)
                self._current_engine = engine
                if engine.system is not None:
                    scene.global_.satellite_obj = engine.system   # antena real, parâmetros do YAML
                    self._patch_global_from_engine(scene.global_, engine)
                if topo_type == "Macro_countries" and str(engine.params.imt.topology.type).upper() == "MACRO_COUNTRIES":
                    from core.engine_scene import station_lat_lon
                    lat, lon = station_lat_lon(engine)          # sites as the engine placed them
                    scene.global_.country_bs_lats, scene.global_.country_bs_lons = lat, lon
                elif engine.system_error:
                    self._report_scene_problem(f"system: {engine.system_error}")
            except Exception as exc:  # noqa: BLE001
                self._report_scene_problem(f"invalid parameters for the simulator: {exc}")
            return self._global_scene_dict(topo_type, scene.global_)

        local = scene.local

        # Fonte da verdade: o motor do SHARC, alimentado pelo mesmo YAML da simulação.
        from core.engine_scene import (
            EngineSceneError, apply_to_local, build_engine_scene, hex_sector_scene,
        )
        try:
            engine = build_engine_scene(data)
        except EngineSceneError as exc:
            return {"error": f"invalid parameters for the simulator: {exc}", "topology_type": topo_type}
        apply_to_local(local, engine)
        if topo_type in ("MACROCELL", "HOTSPOT", "SINGLE_BS", "SINGLE_BASE_STATION")                 and str(engine.params.imt.topology.type).upper() == ("SINGLE_BS" if topo_type.startswith("SINGLE") else topo_type):
            return hex_sector_scene(topo_type, engine)

        if topo_type == "INDOOR" and local.indoor_topo is not None:
            return self._indoor_scene_dict(local)
        if topo_type == "NTN" and local.ntn_topo is not None:
            return self._ntn_scene_dict(local)
        if topo_type == "MSS_D2D":
            return self._mss_d2d_scene_dict(local)
        if topo_type == "SINGLE_EARTH_STATION":
            return self._single_earth_station_scene_dict(local)
        return self._hex_sector_scene_dict(topo_type, local)

    def _patch_global_from_engine(self, glob, engine) -> None:
        """Satélite nos parâmetros do motor; a estação-alvo é o centro da rede IMT."""
        from utils import lla_to_ecef
        ref = engine.reference
        glob.earth_station_lat_deg, glob.earth_station_lon_deg = ref["lat_deg"], ref["lon_deg"]
        glob.earth_station_alt_m = ref["alt_m"]
        glob.earth_station_x, glob.earth_station_y, glob.earth_station_z = lla_to_ecef(
            ref["lat_deg"], ref["lon_deg"], ref["alt_m"])
        if str(engine.params.general.system).upper() == "SINGLE_SPACE_STATION":
            ss = engine.params.single_space_station
            lat = float(ss.geometry.location.fixed.lat_deg)
            lon = float(ss.geometry.location.fixed.long_deg)
            alt = float(ss.geometry.altitude)
            glob.satellite_lat_deg, glob.satellite_lon_deg, glob.satellite_alt_m = lat, lon, alt
            glob.satellite_x, glob.satellite_y, glob.satellite_z = lla_to_ecef(lat, lon, alt)

    def _report_scene_problem(self, message: str) -> None:
        """Mostra o problema do cenário em Messages (sem repetir a mesma mensagem)."""
        if message != getattr(self, "_last_scene_problem", None):
            self._last_scene_problem = message
            try:
                self.app._safe_log(f"[SCENARIO] {message}")
            except Exception:
                pass

    def _composite_scene_dict(self, data) -> Dict[str, Any]:
        """Rede IMT + sistema vítima na mesma cena (mesmo referencial)."""
        imt_type = self._detect_topology_type(data)
        sys_type = self._detect_system_type(data)
        imt = self._scene_graph_to_cesium_dict(imt_type, data)
        if imt.get("error"):
            return imt
        system = None
        if sys_type and sys_type != imt_type:
            system = self._scene_graph_to_cesium_dict(sys_type, data)
            if system.get("error"):
                self._report_scene_problem(system["error"])
                system = None
        terrain = self._terrain_block(imt)
        return {"topology_type": f"{imt_type} + {sys_type}" if system else imt_type,
                "composite": True, "imt": imt, "system": system, "terrain": terrain}

    def _terrain_block(self, imt: Dict[str, Any]):
        """Terrain overlays for the scene; also puts stations on the ground."""
        tab = getattr(self.app, "tab_terrain", None)
        info = tab.overlay_info() if tab is not None else None
        if not info:
            return None
        try:
            ref = imt.get("reference")
            if ref:                                   # local scenes sit on the ground at the reference
                g = tab.ground_heights(ref["lat_deg"], ref["lon_deg"])
                ref["alt_m"] = float(ref.get("alt_m", 0.0)) * 0.0 + float(g[0]) if g is not None else ref.get("alt_m", 0.0)
            sites = imt.get("country_bs")
            if sites:                                 # database sites: each one on its own ground
                lat = [p["lat_deg"] for p in sites]
                lon = [p["lon_deg"] for p in sites]
                g = tab.ground_heights(lat, lon)
                for p, h in zip(sites, g):
                    p["ground_m"] = float(h)
        except Exception as exc:  # noqa: BLE001 - never let terrain break the scene
            self._report_scene_problem(f"terrain sampling failed: {exc}")
        return info

    def _cesium_scene_provider(self, topo_type: str) -> str:
        """``PyBridge.scene_provider``-shaped callable, backed by the real
        scenario the user configured in the GUI (see ``web/cesium_preview/
        spike_widget.py``'s ``CesiumSpikeWidget(scene_provider=...)``)."""
        try:
            data = self._current_yaml()
            if topo_type == "SCENARIO":
                scene = self._composite_scene_dict(data)
            else:
                scene = self._scene_graph_to_cesium_dict(topo_type, data)
            if isinstance(scene, dict) and scene.get("error"):
                self._report_scene_problem(scene["error"])
            return json.dumps(scene)
        except SystemExit as e:
            # The engine calls sys.exit() on impossible parameters (e.g. hotspots that cannot be placed);
            # that must never close the GUI.
            return json.dumps({"error": "The simulator rejected these parameters (e.g. too many hotspots for the "
                                        f"cell size). Exit code {e.code}.", "topology_type": topo_type})
        except Exception as e:
            return json.dumps({"error": str(e), "topology_type": topo_type})
