"""Real-engine scene data for the CesiumJS Preview spike (Fase 3).

Builds small JSON payloads directly from the real SHARC simulation engine
topology classes (``sharc.topology.topology_*``) — the same classes
``Geometry3DMixin._compute_local_geometry`` uses, see
``sharc/gui/core/geometry_3d.py`` — so what the spike renders is provably
the engine's own geometry, not a re-derived approximation.

Deliberately does not depend on the full PySide6 ``App``/``AppState`` — the
spike stays standalone (see ``tools/run_cesium_spike.py``). Positions are in
a local ENU frame (meters, site-cluster-relative); a fixed reference lat/lon
anchors that frame to a point on the globe so Cesium can place it — the
anchor/ENU math itself is done client-side by Cesium's own
``Transforms.eastNorthUpToFixedFrame``, not re-implemented here (see
CESIUMJS_MIGRATION_PLAN.md's Coordinate Transformation Layer section).

UE positions are illustrative scatter around each site (same idea as
``PlotEnginesMixin``'s current UE rendering), but seeded deterministically —
unlike the legacy Matplotlib renderer (see the Fase 1 "known limitations"
note in CESIUMJS_MIGRATION_PLAN.md), so the scene is reproducible run to
run.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict

import numpy as np

from sharc.topology.topology_macrocell import TopologyMacrocell
from sharc.topology.topology_hotspot import TopologyHotspot
from sharc.topology.topology_single_base_station import TopologySingleBaseStation
from sharc.topology.topology_indoor import TopologyIndoor
from sharc.topology.topology_ntn import TopologyNTN
from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
from sharc.parameters.imt.parameters_indoor import ParametersIndoor
from sharc.support.geodesy import lla_to_ecef, ecef_to_lla, WGS84_A

# Brasília — arbitrary demo anchor for the local ENU frame. A real
# integration (Fase 4+) would use the scenario's own reference station
# location instead of a hardcoded point.
REFERENCE_LAT_DEG = -15.78
REFERENCE_LON_DEG = -47.93
REFERENCE_ALT_M = 0.0

BS_HEIGHT_M = 30.0
UE_HEIGHT_M = 1.5
DOWNTILT_DEG = 6.0
UE_PER_SITE = 6
UE_RNG_SEED = 42

SUPPORTED_TOPOLOGIES = ("MACROCELL", "HOTSPOT", "SINGLE_BS", "INDOOR", "NTN", "SINGLE_SPACE_STATION")

# Demo GEO satellite + earth station lat/lon/alt (Fase 4 start — no YAML
# scenario is loaded in this standalone spike, so these are illustrative
# fixed values, same spirit as the terrestrial builders' default params).
DEMO_SAT_LAT_DEG = 0.0
DEMO_SAT_LON_DEG = -70.0
DEMO_SAT_ALT_M = 35786e3
DEMO_ES_LAT_DEG = -15.78
DEMO_ES_LON_DEG = -47.93
DEMO_ES_ALT_M = 0.0
DEMO_BEAMWIDTH_DEG = 8.7


def _reference() -> Dict[str, float]:
    return {"lat_deg": REFERENCE_LAT_DEG, "lon_deg": REFERENCE_LON_DEG, "alt_m": REFERENCE_ALT_M}


def _hex_sector_scene(
    topology_type: str, xs, ys, azs, hex_radius: float,
    hex_center_xs=None, hex_center_ys=None,
) -> Dict[str, Any]:
    """Shared packaging for hex-grid-of-sectorized-BS topologies.

    MACROCELL, HOTSPOT and SINGLE_BS are all "a handful of sectorized BS
    with an underlying hex grid" from the renderer's point of view — this
    mirrors how ``plot_engines.py`` itself treats them (one generic
    hex/sector code path, versus dedicated ones for INDOOR/NTN).

    ``hex_center_xs``/``hex_center_ys`` default to the BS positions
    themselves (true for MACROCELL/SINGLE_BS, where 3 co-located sectors
    share a site); HOTSPOT passes the underlying macrocell grid instead,
    since hotspot BS are scattered independently within each macro cell —
    matching ``Geometry3DMixin._compute_local_geometry``'s HOTSPOT branch.
    """
    base_stations = [
        {"x": float(x), "y": float(y), "azimuth_deg": float(az)}
        for x, y, az in zip(xs, ys, azs)
    ]
    if hex_center_xs is None:
        hex_center_xs, hex_center_ys = xs, ys
    hex_centers = sorted({(float(x), float(y)) for x, y in zip(hex_center_xs, hex_center_ys)})

    rng = np.random.RandomState(UE_RNG_SEED)
    ue_positions = []
    for cx, cy in hex_centers:
        for _ in range(UE_PER_SITE):
            ang = rng.uniform(0, 2 * np.pi)
            r = rng.uniform(0, hex_radius * 0.9)
            ue_positions.append({"x": cx + r * np.cos(ang), "y": cy + r * np.sin(ang)})

    return {
        "topology_type": topology_type,
        "reference": _reference(),
        "hex_radius_m": hex_radius,
        "bs_height_m": BS_HEIGHT_M,
        "ue_height_m": UE_HEIGHT_M,
        "downtilt_deg": DOWNTILT_DEG,
        "base_stations": base_stations,
        "hex_centers": [{"x": x, "y": y} for x, y in hex_centers],
        "ue_positions": ue_positions,
    }


def build_macrocell_scene(intersite_distance: float = 1500.0, num_clusters: int = 1) -> Dict[str, Any]:
    topo = TopologyMacrocell(intersite_distance=intersite_distance, num_clusters=num_clusters)
    topo.calculate_coordinates()
    hex_radius = intersite_distance / math.sqrt(3)
    return _hex_sector_scene("MACROCELL", topo.x, topo.y, topo.azimuth, hex_radius)


def build_hotspot_scene(intersite_distance: float = 1500.0, num_clusters: int = 1) -> Dict[str, Any]:
    p_hot = ParametersHotspot()
    # ParametersHotspot()'s raw default isn't guaranteed int-typed (the GUI
    # always overrides this from a validated UI field before use — see
    # Geometry3DMixin._compute_local_geometry's HOTSPOT branch).
    p_hot.num_hotspots_per_cell = int(p_hot.num_hotspots_per_cell or 3)
    topo = TopologyHotspot(param=p_hot, intersite_distance=intersite_distance, num_clusters=num_clusters)
    topo.calculate_coordinates()
    hex_radius = intersite_distance / math.sqrt(3)
    macro = getattr(topo, "macrocell", None)
    hex_xs, hex_ys = (macro.x, macro.y) if macro is not None else (topo.x, topo.y)
    return _hex_sector_scene(
        "HOTSPOT", topo.x, topo.y, topo.azimuth, hex_radius,
        hex_center_xs=hex_xs, hex_center_ys=hex_ys,
    )


def build_single_bs_scene(cell_radius: float = 100.0) -> Dict[str, Any]:
    topo = TopologySingleBaseStation(cell_radius=cell_radius, num_clusters=1)
    topo.calculate_coordinates()
    return _hex_sector_scene("SINGLE_BS", topo.x, topo.y, topo.azimuth, cell_radius)


def build_ntn_scene(
    intersite_distance: float = 100000.0, cell_radius: float = 50000.0,
    bs_height: float = 600000.0, bs_azimuth: float = 45.0, bs_elevation: float = 45.0,
    num_sectors: int = 7,
) -> Dict[str, Any]:
    """NTN topology: ground anchor points + one satellite, not a hex/sector grid."""
    topo = TopologyNTN(
        intersite_distance=intersite_distance, cell_radius=cell_radius,
        bs_height=bs_height, bs_azimuth=bs_azimuth, bs_elevation=bs_elevation,
        num_sectors=num_sectors,
    )
    anchor_points = [{"x": float(x), "y": float(y)} for x, y in zip(topo.x, topo.y)]

    rng = np.random.RandomState(UE_RNG_SEED)
    ue_positions = []
    n_ue = min(len(topo.x) * 5, 80)
    for i in range(n_ue):
        bi = i % len(topo.x)
        ue_positions.append({
            "x": float(topo.x[bi]) + rng.uniform(-cell_radius * 0.8, cell_radius * 0.8),
            "y": float(topo.y[bi]) + rng.uniform(-cell_radius * 0.8, cell_radius * 0.8),
        })

    return {
        "topology_type": "NTN",
        "reference": _reference(),
        "hex_radius_m": cell_radius,
        "anchor_points": anchor_points,
        "satellite": {
            "x": float(topo.space_station_x), "y": float(topo.space_station_y),
            "z": float(topo.space_station_z),
        },
        "elevation_deg": float(np.degrees(topo.bs_elevation)),
        "slant_range_m": float(topo.bs_radius),
        "ue_positions": ue_positions,
    }


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def _footprint_boundary_lla(sx: float, sy: float, sz: float, bw_deg: float, n: int = 128):
    """Sub-satellite footprint circle, in lat/lon degrees.

    Same ray/sphere-intersection algorithm as
    ``Geometry3DMixin._compute_footprint_boundary`` (geometry_3d.py) —
    reimplemented here rather than imported so this module stays
    independent of the GUI widget layer (``core.geometry_3d`` pulls in
    ``utils.py``, which imports PySide6 widgets). Converts the resulting
    ECEF points to lat/lon via ``sharc.support.geodesy.ecef_to_lla`` so the
    caller (Cesium) can place them directly with
    ``Cartesian3.fromDegreesArray``.
    """
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


def build_single_space_station_scene() -> Dict[str, Any]:
    """Real-global-coordinates satellite + earth station + footprint.

    Unlike the terrestrial builders above (local ENU frame anchored to a
    fixed demo lat/lon), this topology is genuinely global: the satellite
    and earth station each get their own real lat/lon/alt, matching how
    ``Geometry3DMixin._get_global_positions`` already positions them for
    the Matplotlib renderer (WGS-84 ``lla_to_ecef``) — this is the scene
    type Cesium is actually built for.
    """
    sx, sy, sz = lla_to_ecef(DEMO_SAT_LAT_DEG, DEMO_SAT_LON_DEG, DEMO_SAT_ALT_M)
    footprint = _footprint_boundary_lla(float(sx), float(sy), float(sz), DEMO_BEAMWIDTH_DEG)

    return {
        "topology_type": "SINGLE_SPACE_STATION",
        "satellite": {"lat_deg": DEMO_SAT_LAT_DEG, "lon_deg": DEMO_SAT_LON_DEG, "alt_m": DEMO_SAT_ALT_M},
        "earth_station": {"lat_deg": DEMO_ES_LAT_DEG, "lon_deg": DEMO_ES_LON_DEG, "alt_m": DEMO_ES_ALT_M},
        "beamwidth_deg": DEMO_BEAMWIDTH_DEG,
        "footprint": footprint,
    }


def build_indoor_scene() -> Dict[str, Any]:
    """Indoor office topology: real building footprints/floors, not a hex grid."""
    p_ind = ParametersIndoor()
    topo = TopologyIndoor(p_ind)
    topo.calculate_coordinates()

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

    heights = list(topo.height) if hasattr(topo, "height") and len(topo.height) > 0 else [BS_HEIGHT_M] * n_total_bs
    base_stations = [
        {"x": float(x), "y": float(y), "z": float(z)}
        for x, y, z in zip(topo.x, topo.y, heights)
    ]

    rng = np.random.RandomState(UE_RNG_SEED)
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
        "reference": _reference(),
        "ue_height_m": UE_HEIGHT_M,
        "buildings": buildings,
        "base_stations": base_stations,
        "ue_positions": ue_positions,
    }


_BUILDERS = {
    "MACROCELL": build_macrocell_scene,
    "HOTSPOT": build_hotspot_scene,
    "SINGLE_BS": build_single_bs_scene,
    "INDOOR": build_indoor_scene,
    "NTN": build_ntn_scene,
    "SINGLE_SPACE_STATION": build_single_space_station_scene,
}


def build_scene(topology_type: str) -> Dict[str, Any]:
    builder = _BUILDERS.get(topology_type.upper())
    if builder is None:
        raise ValueError(f"Unsupported topology_type for spike: {topology_type!r}")
    return builder()


def build_scene_json(topology_type: str) -> str:
    return json.dumps(build_scene(topology_type))
