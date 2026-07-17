"""SceneGraph dataclasses: the data contract between the SHARC engine-backed
Scene Builder (core/scene_builder.py) and the Preview renderers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import numpy as np


@dataclass
class LocalSceneGraph:
    """Geometry for non-global (terrestrial-style) topologies.

    Values come straight from ``Geometry3DMixin._compute_local_geometry``,
    which already instantiates the real SHARC topology classes
    (``TopologyMacrocell``, ``TopologyHotspot``, etc.) — this dataclass only
    gives that output a name and a stable shape, it does not recompute
    anything.
    """

    xs: List[float]
    ys: List[float]
    azimuths: List[float]
    hex_centers: List[Tuple[float, float]]
    hex_radius: float
    draw_hex: bool
    # Scenario parameters that shape rendering (same values
    # plot_engines.py's Matplotlib code already reads from self.app/YAML)
    # — kept here too so the CesiumJS bridge (core/cesium_bridge.py)
    # doesn't have to re-derive them independently.
    bs_height_m: float = 30.0
    ue_height_m: float = 1.5
    downtilt_deg: float = 6.0
    ue_k: int = 3
    # Real georeferencing for this topology's local ENU frame — the IMT
    # tab's "central_latitude/longitude/altitude" fields (imt.topology.
    # central_latitude/... in the YAML), not a hardcoded demo point. Lets
    # Cesium place this local-coordinate topology on the actual globe the
    # same place the scenario says it belongs.
    reference_lat_deg: float = -15.793889
    reference_lon_deg: float = -47.882778
    reference_alt_m: float = 0.0
    # Live topology objects kept around for topology-specific rendering
    # (INDOOR building geometry, NTN satellite/slant range). Not
    # JSON-serializable yet — that is deferred to the CesiumJS phase, where
    # these will need to be flattened into plain entity data.
    indoor_topo: Any = None
    ntn_topo: Any = None


@dataclass
class GlobalSceneGraph:
    """Geometry for global (ECEF/lat-lon) topologies: satellites, earth
    stations, and country-based base stations.

    Positions come from ``Geometry3DMixin._get_global_positions`` /
    ``PlotEnginesMixin._compute_macro_countries_bs`` unchanged.
    """

    satellite_x: float
    satellite_y: float
    satellite_z: float
    earth_station_x: float
    earth_station_y: float
    earth_station_z: float
    # Real geodetic coordinates, recovered from the ECEF values above via
    # sharc.support.geodesy.ecef_to_lla (round-trips to ~1e-15 deg / ~1e-9 m,
    # see CESIUMJS_MIGRATION_PLAN.md Fase 3). Matplotlib only ever needed
    # ECEF; Cesium needs real lat/lon/alt, since — unlike the terrestrial
    # topologies — satellites/earth stations have genuine global
    # coordinates, not a local ENU frame anchored to an arbitrary point.
    satellite_lat_deg: float = 0.0
    satellite_lon_deg: float = 0.0
    satellite_alt_m: float = 0.0
    earth_station_lat_deg: float = 0.0
    earth_station_lon_deg: float = 0.0
    earth_station_alt_m: float = 0.0
    # Live station object, used only to access the real antenna for gain-map
    # rendering — never for positioning (see geometry_3d.py comments).
    satellite_obj: Any = None
    country_bs_lats: Optional[np.ndarray] = None
    country_bs_lons: Optional[np.ndarray] = None


@dataclass
class SceneGraph:
    """Top-level scene description consumed by the renderers.

    Exactly one of ``local``/``global_`` is populated, matching
    ``topo_type in GLOBAL_PREVIEW_TYPES``. This is intentionally still a
    Python-only, in-process structure (may hold live SHARC objects) — it is
    the seam future work will use to swap the renderer (e.g. for CesiumJS)
    without touching how the scene is derived from the simulation engine.
    """

    topo_type: str
    is_global: bool
    local: Optional[LocalSceneGraph] = None
    global_: Optional[GlobalSceneGraph] = None
