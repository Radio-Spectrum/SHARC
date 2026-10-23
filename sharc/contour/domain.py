"""Land domain of each ray: where it ends.

A ray starting at the station must not enter the sea, leave the area of study, or run past the terrain data. It ends at
the FIRST of:

  * a sea cell (zone 3 of the P.452 zones raster, when there is one);
  * the exit from the boundary polygon (a GeoJSON of the country or state, optional: none means no boundary);
  * the edge of the terrain raster, or the first point without terrain data (sampled like the profile does: bilinear,
    at pixel centres). Near the edge the raster has empty pixels inside its frame, and a profile touching one fails.
"""
from __future__ import annotations

import json
from typing import Optional, Tuple

import numpy as np

from sharc.contour.geometry import points_on_ray

SEA, BOUNDARY, TERRAIN_EDGE, LIMIT = "sea", "boundary", "terrain_edge", "limit"
SEA_ZONE = 3


class Domain:
    def __init__(self, terrain_raster: str, zones_raster: str = "", polygon_geojson: str = "",
                 polygon_margin_m: float = 2000.0):
        from sharc.propagation.real_terrain.grade_raster import GridRaster
        import rasterio
        self.terrain = GridRaster(terrain_raster)
        with rasterio.open(terrain_raster) as dem:
            self.bounds = dem.bounds
        self.zones = None
        if zones_raster:
            with rasterio.open(zones_raster) as z:
                self.zones, self.zones_transform = z.read(1), z.transform
        self.polygon = None
        if polygon_geojson:
            import shapely
            from shapely.geometry import shape
            with open(polygon_geojson, encoding="utf-8") as fh:
                geometries = [shape(f["geometry"]) for f in json.load(fh)["features"]]
            # margin in degrees (about 111 km per degree): negligible error for a margin of a few km
            self.polygon = shapely.union_all(geometries).buffer(polygon_margin_m / 111000.0)
            shapely.prepare(self.polygon)

    def ray_end(self, lat0: float, lon0: float, az_enu: float, d_max_m: float, step_m: float = 50.0
                ) -> Tuple[float, str]:
        """(last valid distance [m], reason): reason is 'sea', 'boundary', 'terrain_edge' or 'limit'."""
        from rasterio.transform import rowcol
        d = np.arange(step_m, d_max_m + 0.5 * step_m, step_m)
        lat, lon = points_on_ray(lat0, lon0, az_enu, d)
        b = self.bounds
        inside = (lon >= b.left) & (lon <= b.right) & (lat >= b.bottom) & (lat <= b.top)
        sea = np.zeros(d.size, dtype=bool)
        if self.zones is not None:
            row, col = (np.asarray(v) for v in rowcol(self.zones_transform, lon, lat))
            on_raster = (row >= 0) & (row < self.zones.shape[0]) & (col >= 0) & (col < self.zones.shape[1])
            sea[on_raster] = self.zones[row[on_raster], col[on_raster]] == SEA_ZONE
        in_area = np.ones(d.size, dtype=bool)
        if self.polygon is not None:
            import shapely
            in_area = shapely.contains_xy(self.polygon, lon, lat)
        has_data = np.isfinite(self.terrain.sample(lat, lon, "bilinear"))
        ok = inside & ~sea & in_area & has_data
        bad = np.flatnonzero(~ok)
        if bad.size == 0:
            return float(d[-1]), LIMIT
        k = int(bad[0])
        reason = SEA if sea[k] else (BOUNDARY if not in_area[k] else TERRAIN_EDGE)
        return (float(d[k - 1]) if k > 0 else 0.0), reason
