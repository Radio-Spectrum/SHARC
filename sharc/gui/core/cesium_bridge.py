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

        return {
            "topology_type": "SINGLE_EARTH_STATION",
            "reference": self._reference_dict(local),
            "bs_height_m": local.bs_height_m,
            "station": {"x": float(x0), "y": float(y0), "z": float(local.bs_height_m)},
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
            scene["country_bs"] = [
                {"lat_deg": float(lat), "lon_deg": float(lon)}
                for lat, lon in zip(glob.country_bs_lats, glob.country_bs_lons)
            ]

        return scene

    def _scene_graph_to_cesium_dict(self, topo_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the real SceneGraph for *topo_type* and return Cesium-ready JSON."""
        scene = self._build_scene_graph(topo_type, data)

        if scene.is_global:
            return self._global_scene_dict(topo_type, scene.global_)

        local = scene.local
        if topo_type == "INDOOR" and local.indoor_topo is not None:
            return self._indoor_scene_dict(local)
        if topo_type == "NTN" and local.ntn_topo is not None:
            return self._ntn_scene_dict(local)
        if topo_type == "MSS_D2D":
            return self._mss_d2d_scene_dict(local)
        if topo_type == "SINGLE_EARTH_STATION":
            return self._single_earth_station_scene_dict(local)
        return self._hex_sector_scene_dict(topo_type, local)

    def _cesium_scene_provider(self, topo_type: str) -> str:
        """``PyBridge.scene_provider``-shaped callable, backed by the real
        scenario the user configured in the GUI (see ``web/cesium_preview/
        spike_widget.py``'s ``CesiumSpikeWidget(scene_provider=...)``)."""
        try:
            data = self._current_yaml()
            return json.dumps(self._scene_graph_to_cesium_dict(topo_type, data))
        except Exception as e:
            return json.dumps({"error": str(e), "topology_type": topo_type})
