"""Scene Builder: assembles a SceneGraph from the real SHARC engine objects.

See sharc/gui/CESIUMJS_MIGRATION_PLAN.md (Fase 1) for the architectural
rationale.
"""

from __future__ import annotations

from typing import Any, Dict

from utils import GLOBAL_PREVIEW_TYPES, _coerce_float, _safe_float, _safe_int, _yaml_first
from sharc.support.geodesy import ecef_to_lla

from core.scene_graph import SceneGraph, LocalSceneGraph, GlobalSceneGraph


def _app_float(app, attr: str, default: float) -> float:
    if not hasattr(app, attr):
        return default
    val = getattr(app, attr)
    val = val.get() if hasattr(val, "get") else val
    return _safe_float(val, default)


def _app_int(app, attr: str, default: int) -> int:
    if not hasattr(app, attr):
        return default
    val = getattr(app, attr)
    val = val.get() if hasattr(val, "get") else val
    return _safe_int(val, default)


class SceneBuilderMixin:
    """Builds a :class:`SceneGraph` from the real SHARC engine objects.

    This is the seam described in ``sharc/gui/CESIUMJS_MIGRATION_PLAN.md``
    (Fase 1): it does not recompute geometry itself — it calls the exact same
    ``Geometry3DMixin``/``PlotEnginesMixin`` methods the renderers already
    called directly, and packages their output into a stable, named
    structure. Renderers should call ``self._build_scene_graph(...)`` once per
    redraw and read positions from the returned ``SceneGraph`` instead of
    calling ``_compute_local_geometry``/``_get_global_positions``/
    ``_compute_macro_countries_bs`` themselves.
    """

    def _build_scene_graph(self, topo_type: str, data: Dict[str, Any]) -> SceneGraph:
        is_global = topo_type in GLOBAL_PREVIEW_TYPES

        if is_global:
            sx, sy, sz, ex, ey, ez, sat_obj = self._get_global_positions(data)
            sat_lat, sat_lon, sat_alt = ecef_to_lla(sx, sy, sz)
            es_lat, es_lon, es_alt = ecef_to_lla(ex, ey, ez)

            country_bs_lats = None
            country_bs_lons = None
            if topo_type == "Macro_countries":
                country_bs_lats, country_bs_lons = self._compute_macro_countries_bs(data)

            return SceneGraph(
                topo_type=topo_type,
                is_global=True,
                global_=GlobalSceneGraph(
                    satellite_x=sx, satellite_y=sy, satellite_z=sz,
                    earth_station_x=ex, earth_station_y=ey, earth_station_z=ez,
                    satellite_lat_deg=float(sat_lat), satellite_lon_deg=float(sat_lon),
                    satellite_alt_m=float(sat_alt),
                    earth_station_lat_deg=float(es_lat), earth_station_lon_deg=float(es_lon),
                    earth_station_alt_m=float(es_alt),
                    satellite_obj=sat_obj,
                    country_bs_lats=country_bs_lats,
                    country_bs_lons=country_bs_lons,
                ),
            )

        xs, ys, azs, hex_centers, hex_radius, draw_hex = self._compute_local_geometry(
            topo_type, data)

        # Same scenario parameters plot_engines.py's Matplotlib renderer
        # reads from self.app/YAML — kept here so any renderer (including
        # the CesiumJS bridge) has a single source for them.
        bs_height = _coerce_float(_yaml_first(data, (
            "imt.base_station.height_m", "imt.bs.height_m", "imt.bs_height",
            "bs_height", "general.bs_height"), None), 30.0)
        bs_height = _app_float(self.app, "bs_height", bs_height)

        ue_height = _coerce_float(_yaml_first(data, ("imt.ue.height", "ue_height"), None), 1.5)
        ue_height = _app_float(self.app, "ue_height", ue_height)

        downtilt = _app_float(self.app, "bs_downtilt", 6.0)
        ue_k = _app_int(self.app, "ue_k", 3)

        ref_lat = _coerce_float(_yaml_first(data, ("imt.topology.central_latitude",), None), -15.793889)
        ref_lat = _app_float(self.app, "topo_c_lat", ref_lat)
        ref_lon = _coerce_float(_yaml_first(data, ("imt.topology.central_longitude",), None), -47.882778)
        ref_lon = _app_float(self.app, "topo_c_lon", ref_lon)
        ref_alt = _coerce_float(_yaml_first(data, ("imt.topology.central_altitude",), None), 0.0)
        ref_alt = _app_float(self.app, "topo_c_alt", ref_alt)

        return SceneGraph(
            topo_type=topo_type,
            is_global=False,
            local=LocalSceneGraph(
                xs=xs, ys=ys, azimuths=azs,
                hex_centers=hex_centers, hex_radius=hex_radius, draw_hex=draw_hex,
                bs_height_m=bs_height, ue_height_m=ue_height,
                downtilt_deg=downtilt, ue_k=ue_k,
                reference_lat_deg=ref_lat, reference_lon_deg=ref_lon, reference_alt_m=ref_alt,
                # _compute_local_geometry sets these as side effects on self
                # for INDOOR/NTN topologies; carried over unchanged.
                indoor_topo=getattr(self, "_indoor_topo", None),
                ntn_topo=getattr(self, "_ntn_topo", None),
            ),
        )
