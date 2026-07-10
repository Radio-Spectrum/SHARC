from __future__ import annotations

import math
import traceback
from typing import Any, Dict, Optional, Tuple

import numpy as np

from utils import (
    # Type-safe coercers
    _safe_float, _safe_int, _coerce_float, _coerce_int, _coerce_str,
    # YAML helpers
    _yaml_first, _yaml_get,
    # Geometry helpers
    _unit, _guess_antenna_beamwidth_deg, _approx_hex_cluster_centers,
    _antenna_gain_db, _antenna_gain_db_batch,
    # Geodetic
    lla_to_ecef,
    # Constants
    WGS84_A,
    # SHARC core flags and classes
    HAS_SHARC_CORE,
    TopologyMacrocell, TopologyHotspot, TopologySingleBaseStation,
    TopologyIndoor, TopologyNTN,
    ParametersHotspot, ParametersIndoor,
    StationFactory, ParametersSingleSpaceStation,
)

class Geometry3DMixin:
    def _compute_local_geometry(self, topo_type: str, data: Dict[str, Any]):
        xs, ys, azs = [], [], []
        hex_centers, hex_radius, draw_hex = [], 0.0, False

        # Reset topology-specific caches
        self._indoor_topo = None
        self._ntn_topo = None

        if not HAS_SHARC_CORE:
            return ([0], [0], [0], [], 0, False)

        try:
            if topo_type == "SINGLE_EARTH_STATION":
                xs, ys, azs = [0.0], [0.0], [0.0]

            elif topo_type == "MACROCELL":
                d = _coerce_float(_yaml_first(data, ("imt.topology.intersite_distance", "topology.intersite_distance",
                                  "macrocell.intersite_distance", "macro.intersite_distance", "macro_intersite"), None), 1500.0)
                if hasattr(self.app, "macro_intersite"):
                    d = _safe_float(
                        getattr(self.app, "macro_intersite", None), d)
                nc = _coerce_int(_yaml_first(data, ("imt.topology.num_clusters",
                                 "topology.num_clusters", "macrocell.num_clusters", "macro_clusters"), None), 1)
                if hasattr(self.app, "macro_clusters"):
                    nc = _safe_int(
                        getattr(self.app, "macro_clusters", None), nc)
                topo = TopologyMacrocell(intersite_distance=d, num_clusters=nc)
                topo.calculate_coordinates()
                xs, ys, azs = list(topo.x), list(topo.y), list(topo.azimuth)
                # Correct hexagon size for honeycomb packing:
                # If intersite distance is d, hex radius (center to corner) is d / sqrt(3)
                hex_radius = d / math.sqrt(3)
                draw_hex = True
                hex_centers = list(set(zip(xs, ys)))

            elif topo_type == "HOTSPOT":
                d = _coerce_float(_yaml_first(data, ("imt.hotspot.intersite_distance", "hotspot.intersite_distance",
                                  "imt.topology.intersite_distance", "hotspot_intersite"), None), 1500.0)
                if hasattr(self.app, "hotspot_intersite"):
                    d = _safe_float(
                        getattr(self.app, "hotspot_intersite", None), d)
                nc = _coerce_int(_yaml_first(
                    data, ("imt.hotspot.num_clusters", "hotspot.num_clusters", "hotspot_clusters"), None), 1)
                if hasattr(self.app, "hotspot_clusters"):
                    nc = _safe_int(
                        getattr(self.app, "hotspot_clusters", None), nc)
                p_hot = ParametersHotspot() if ParametersHotspot else None
                if p_hot:
                    p_hot.num_hotspots_per_cell = _coerce_int(_yaml_first(
                        data, ("imt.hotspot.num_hotspots_per_cell", "hotspot.num_hotspots_per_cell", "hotspot_num_per_cell"), None), 3)
                    if hasattr(self.app, "hotspot_num_per_cell"):
                        p_hot.num_hotspots_per_cell = _safe_int(
                            getattr(self.app, "hotspot_num_per_cell", None), p_hot.num_hotspots_per_cell)
                topo = TopologyHotspot(
                    param=p_hot, intersite_distance=d, num_clusters=nc)
                topo.calculate_coordinates()
                xs, ys, azs = list(topo.x), list(topo.y), list(topo.azimuth)
                if hasattr(topo, "macrocell"):
                    hex_radius = d / math.sqrt(3)
                    draw_hex = True
                    hex_centers = list(
                        set(zip(topo.macrocell.x, topo.macrocell.y)))

            elif topo_type in ("SINGLE_BS", "SINGLE_BASE_STATION"):
                cr = _safe_float(
                    getattr(self.app, "sbs_cell_radius", None), 100.0)
                topo = TopologySingleBaseStation(
                    cell_radius=cr, num_clusters=1)
                topo.calculate_coordinates()
                xs, ys, azs = list(topo.x), list(topo.y), list(topo.azimuth)

            elif topo_type == "INDOOR":
                if ParametersIndoor is not None and TopologyIndoor is not None:
                    p_ind = ParametersIndoor()
                    p_ind.intersite_distance = _safe_float(getattr(self.app, "indoor_intersite", None), 20.0)
                    p_ind.n_rows = _safe_int(getattr(self.app, "indoor_n_rows", None), 3)
                    p_ind.n_colums = _safe_int(getattr(self.app, "indoor_n_cols", None), 3)
                    p_ind.street_width = _safe_float(getattr(self.app, "indoor_street_width", None), 30.0)
                    p_ind.num_cells = _safe_int(getattr(self.app, "indoor_num_cells", None), 6)
                    p_ind.num_floors = _safe_int(getattr(self.app, "indoor_num_floors", None), 3)
                    nb = _coerce_str(getattr(self.app, "indoor_num_buildings", "ALL"), "ALL")
                    p_ind.num_imt_buildings = nb
                    p_ind.ue_indoor_percent = _safe_float(getattr(self.app, "indoor_ue_indoor_percent", None), 0.95)
                    p_ind.building_class = _coerce_str(getattr(self.app, "indoor_building_class", "TRADITIONAL"), "TRADITIONAL")
                    topo = TopologyIndoor(p_ind)
                    topo.calculate_coordinates()
                    xs = list(topo.x)
                    ys = list(topo.y)
                    azs = list(topo.azimuth) if len(topo.azimuth) > 0 else [0.0] * len(xs)
                    self._indoor_topo = topo
                else:
                    xs, ys, azs = [0], [0], [0]

            elif topo_type == "NTN":
                isd = _coerce_float(_yaml_first(data, ("imt.topology.ntn.intersite_distance",), None), 100000.0)
                cr = _coerce_float(_yaml_first(data, ("imt.topology.ntn.cell_radius",), None), 50000.0)
                bsh = _coerce_float(_yaml_first(data, ("imt.topology.ntn.bs_height",), None), 600000.0)
                bsa = _coerce_float(_yaml_first(data, ("imt.topology.ntn.bs_azimuth",), None), 45.0)
                bse = _coerce_float(_yaml_first(data, ("imt.topology.ntn.bs_elevation",), None), 45.0)
                ns = _coerce_int(_yaml_first(data, ("imt.topology.ntn.num_sectors",), None), 7)

                if hasattr(self.app, "ntn_intersite"):
                    isd = _safe_float(getattr(self.app, "ntn_intersite", None), isd)
                if hasattr(self.app, "ntn_cell_radius"):
                    cr = _safe_float(getattr(self.app, "ntn_cell_radius", None), cr)
                if hasattr(self.app, "ntn_bs_height"):
                    bsh = _safe_float(getattr(self.app, "ntn_bs_height", None), bsh)
                if hasattr(self.app, "ntn_bs_azimuth"):
                    bsa = _safe_float(getattr(self.app, "ntn_bs_azimuth", None), bsa)
                if hasattr(self.app, "ntn_bs_elevation"):
                    bse = _safe_float(getattr(self.app, "ntn_bs_elevation", None), bse)
                if hasattr(self.app, "ntn_num_sectors"):
                    ns = _safe_int(getattr(self.app, "ntn_num_sectors", None), ns)

                if ns not in (1, 7, 19):
                    ns = 7

                if TopologyNTN is not None:
                    topo = TopologyNTN(
                        intersite_distance=isd,
                        cell_radius=cr,
                        bs_height=bsh,
                        bs_azimuth=bsa,
                        bs_elevation=bse,
                        num_sectors=ns,
                    )
                    xs = list(topo.x)
                    ys = list(topo.y)
                    azs = list(topo.azimuth) if hasattr(topo, "azimuth") and len(topo.azimuth) > 0 else [0.0] * len(xs)
                    self._ntn_topo = topo
                else:
                    centers = _approx_hex_cluster_centers(ns, isd)
                    xs = [c[0] for c in centers]
                    ys = [c[1] for c in centers]
                    azs = [bsa] * len(centers)

                hex_radius = cr
                draw_hex = True
                hex_centers = list(set(zip(xs, ys)))

            elif topo_type == "MSS_DC":
                beam_radius = _coerce_float(
                    _yaml_first(data, ("imt.topology.mss_dc.beam_radius", "mss_dc.cell_radius", "mss_d2d.cell_radius"), None),
                    36516.0,
                )
                num_beams = _coerce_int(
                    _yaml_first(data, ("imt.topology.mss_dc.num_beams", "mss_dc.num_sectors", "mss_d2d.num_sectors"), None),
                    7,
                )
                if num_beams <= 0:
                    num_beams = 1
                spacing = beam_radius * math.sqrt(3.0)
                centers = _approx_hex_cluster_centers(num_beams, spacing)
                xs = [c[0] for c in centers]
                ys = [c[1] for c in centers]
                azs = [0.0] * len(centers)
                hex_centers = centers
                hex_radius = beam_radius
                draw_hex = True

            elif topo_type == "MSS_SS":
                cell_radius = _coerce_float(_yaml_first(data, ("mss_ss.cell_radius",), None), 45000.0)
                num_sectors = _coerce_int(_yaml_first(data, ("mss_ss.num_sectors",), None), 7)
                if num_sectors <= 0:
                    num_sectors = 1
                centers = _approx_hex_cluster_centers(num_sectors, cell_radius * math.sqrt(3.0))
                xs = [c[0] for c in centers]
                ys = [c[1] for c in centers]
                azs = [0.0] * len(centers)
                hex_centers = centers
                hex_radius = cell_radius
                draw_hex = True

            elif topo_type in ("HAPS", "SINGLE_SPACE_STATION"):
                xs, ys, azs = [0.0], [0.0], [0.0]

            elif topo_type == "MSS_D2D":
                # Simple fallback: two UE positions
                xs, ys, azs = [0.0, 200.0], [0.0, 100.0], [0.0, 180.0]

            else:
                # Generic fallback for unknown topology
                xs, ys, azs = [0.0], [0.0], [0.0]

        except Exception as e:
            print(f"Topology calc error: {e}")
            traceback.print_exc()
            xs, ys, azs = [0], [0], [0]

        return xs, ys, azs, hex_centers, hex_radius, draw_hex

    def _get_global_positions(self, data: Optional[Dict[str, Any]] = None):
        if data is None:
            data = {}
        ss_lat = _coerce_float(_yaml_first(data, ("single_space_station.geometry.location.fixed.lat_deg",
                               "space_station.geometry.location.fixed.lat_deg", "satellite.lat_deg", "general.satellite.lat_deg"), None), 0.0)
        ss_lon = _coerce_float(_yaml_first(data, ("single_space_station.geometry.location.fixed.long_deg",
                               "space_station.geometry.location.fixed.long_deg", "satellite.lon_deg", "general.satellite.lon_deg"), None), 0.0)
        ss_alt = _coerce_float(_yaml_first(data, ("single_space_station.geometry.altitude",
                               "space_station.geometry.altitude", "satellite.altitude_m", "general.satellite.altitude_m"), None), 35786e3)
        es_lat = _coerce_float(_yaml_first(data, ("single_earth_station.geometry.location.fixed.lat_deg",
                               "earth_station.geometry.location.fixed.lat_deg", "earth_station.lat_deg", "general.earth_station.lat_deg"), None), 0.0)
        es_lon = _coerce_float(_yaml_first(data, ("single_earth_station.geometry.location.fixed.long_deg",
                               "earth_station.geometry.location.fixed.long_deg", "earth_station.lon_deg", "general.earth_station.lon_deg"), None), 0.0)
        es_alt = _coerce_float(_yaml_first(data, ("single_earth_station.geometry.altitude", "earth_station.geometry.altitude",
                               "earth_station.altitude_m", "general.earth_station.altitude_m"), None), 0.0)

        # App fallbacks (older GUI vars)
        if hasattr(self.app, "v_fix_lat"):
            ss_lat = _safe_float(getattr(self.app, "v_fix_lat", None), ss_lat)
        if hasattr(self.app, "v_fix_lon"):
            ss_lon = _safe_float(getattr(self.app, "v_fix_lon", None), ss_lon)
        if hasattr(self.app, "v_alt"):
            ss_alt = _safe_float(getattr(self.app, "v_alt", None), ss_alt)
        if hasattr(self.app, "v_es_lat"):
            es_lat = _safe_float(getattr(self.app, "v_es_lat", None), es_lat)
        if hasattr(self.app, "v_es_lon"):
            es_lon = _safe_float(getattr(self.app, "v_es_lon", None), es_lon)
        if hasattr(self.app, "v_es_alt"):
            es_alt = _safe_float(getattr(self.app, "v_es_alt", None), es_alt)

        ex, ey, ez = lla_to_ecef(es_lat, es_lon, es_alt)

        sat_obj = None
        sx, sy, sz = None, None, None

        if HAS_SHARC_CORE and StationFactory and ParametersSingleSpaceStation:
            try:
                p_ss = ParametersSingleSpaceStation()
                try:
                    p_ss.geometry.altitude = ss_alt
                except:
                    pass
                try:
                    p_ss.geometry.location.fixed.lat_deg = ss_lat
                    p_ss.geometry.location.fixed.long_deg = ss_lon
                except:
                    pass

                pat_name = _coerce_str(_yaml_first(data, ("single_space_station.antenna.pattern",
                                       "space_station.antenna.pattern", "satellite.antenna.pattern"), None), "ITU-R S.672")
                if hasattr(self.app, "sat_pattern"):
                    pat_name = _coerce_str(
                        getattr(self.app, "sat_pattern", pat_name), pat_name)
                try:
                    p_ss.antenna.pattern = pat_name
                except:
                    pass

                sat_obj = StationFactory.generate_single_space_station(p_ss)
                sx, sy, sz = float(sat_obj.x[0]), float(
                    sat_obj.y[0]), float(sat_obj.z[0])
            except Exception:
                pass

        if sx is None:
            sx, sy, sz = lla_to_ecef(ss_lat, ss_lon, ss_alt)

        return sx, sy, sz, ex, ey, ez, sat_obj

    def _determine_beamwidth(self, sat_obj):
        if self.app.var_auto_beamwidth.get():
            if sat_obj:
                ant = getattr(sat_obj, "antenna", None)
                if isinstance(ant, list) and ant:
                    ant = ant[0]
                return _guess_antenna_beamwidth_deg(ant, fallback=float(self.app.var_beamwidth_deg.get()))
        return float(self.app.var_beamwidth_deg.get())

    def _compute_footprint_boundary(self, sx, sy, sz, bw_deg, n=128):
        Re = WGS84_A
        S = np.array([sx, sy, sz], dtype=float)
        rs = float(np.linalg.norm(S))
        if rs <= Re:
            return None

        alpha = math.radians(max(0.1, min(179.0, bw_deg)) / 2.0)

        u = -S / rs

        tmp = np.array([0, 0, 1.0])
        if abs(np.dot(tmp, u)) > 0.9:
            tmp = np.array([0, 1.0, 0])
        e1 = _unit(np.cross(u, tmp))
        e2 = _unit(np.cross(u, e1))

        pts = []
        for phi in np.linspace(0, 2*np.pi, n):
            d = math.cos(alpha)*u + math.sin(alpha) * \
                (math.cos(phi)*e1 + math.sin(phi)*e2)

            B = 2.0 * np.dot(S, d)
            C = rs*rs - Re*Re

            disc = B*B - 4*C
            if disc >= 0:
                t = (-B - math.sqrt(disc)) / 2.0
                pts.append(S + t*d)

        if not pts:
            return None
        return np.array(pts)

    def _compute_gain_surface(self, sx, sy, sz, antenna, X, Y, Z, vmin, vmax):
        """Compute gain map on the sphere surface using SHARC's antenna API."""
        S = np.array([sx, sy, sz])
        u_bore = _unit(-S)  # Nadir

        orig_shape = X.shape
        Xf, Yf, Zf = X.ravel(), Y.ravel(), Z.ravel()

        P = np.column_stack((Xf, Yf, Zf))

        D = P - S

        d_norms = np.linalg.norm(D, axis=1)
        d_norms[d_norms == 0] = 1.0
        D_unit = D / d_norms[:, np.newaxis]

        dots = np.dot(D_unit, u_bore)
        dots = np.clip(dots, -1.0, 1.0)
        angles_deg = np.degrees(np.arccos(dots))

        # Use vectorized batch call for performance
        gains = _antenna_gain_db_batch(antenna, angles_deg)

        gains = np.nan_to_num(gains, nan=vmin)
        gains = np.clip(gains, vmin, vmax)

        return gains.reshape(orig_shape)

