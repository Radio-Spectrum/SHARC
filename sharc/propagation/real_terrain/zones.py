"""Radio-climatic zone raster for ITU-R P.452 built from a land-cover raster (and optionally the DEM).

The P.452 zones are 1 = A1 (coastal land), 2 = A2 (inland) and 3 = B (sea). The land cover of
``download_clutter`` (ESA WorldCover) only tells where there is permanent water (class 80), so:

* **B (3)**: permanent-water components that are a sea or a large water body. A component counts when its area is
  at least ``min_sea_km2`` (P.452 treats inland water bodies of about 7 800 km2 or more as zone B) or when it
  touches the raster border with at least ``border_sea_km2`` (a cropped piece of ocean); smaller lakes and rivers
  stay land.
* **A1 (1)**: land within ``coast_km`` (50 km) of a B cell and, when a DEM is given, not higher than
  ``coastal_max_alt_m`` (100 m) above the water level (P.452-18 Table 2).
* **A2 (2)**: every other land cell (and cells with no land-cover data).

This is an approximation of the official zone maps (ITU-R P.836 / the CelPlan zones of the Ceara package): use an
official zone raster when you have one.

Usage:
    build_zone_raster("clutter.tif", "zones.tif", terrain_path="terrain.tif")
"""
from __future__ import annotations

import math
import os
from typing import Optional

import numpy as np

WATER_CLASS = 80                  # ESA WorldCover permanent water bodies
A1, A2, B = 1, 2, 3
M_PER_DEG = 111_320.0


def zones_from_land_cover(land_cover: np.ndarray, pixel_m: tuple, elevation: Optional[np.ndarray] = None,
                          coast_km: float = 50.0, coastal_max_alt_m: float = 100.0, min_sea_km2: float = 7800.0,
                          border_sea_km2: float = 50.0) -> np.ndarray:
    """Zone array (uint8, 1 = A1, 2 = A2, 3 = B) for a land-cover array; `pixel_m` = (height_m, width_m) of a cell."""
    from scipy import ndimage

    water = land_cover == WATER_CLASS
    labels, count = ndimage.label(water)                       # 4-connected components
    sea = np.zeros_like(water)
    if count:
        cell_km2 = pixel_m[0] * pixel_m[1] / 1e6
        area = ndimage.sum(water, labels, index=np.arange(1, count + 1)) * cell_km2
        border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
        is_sea = area >= min_sea_km2
        for lab in border[border > 0]:
            if area[lab - 1] >= border_sea_km2:
                is_sea[lab - 1] = True
        sea = np.isin(labels, np.flatnonzero(is_sea) + 1)

    zones = np.full(land_cover.shape, A2, dtype=np.uint8)
    if sea.any():
        dist_m = ndimage.distance_transform_edt(~sea, sampling=pixel_m)
        coastal = dist_m <= coast_km * 1000.0
        if elevation is not None:
            coastal &= np.nan_to_num(np.asarray(elevation, dtype=float), nan=np.inf) <= coastal_max_alt_m
        zones[coastal] = A1
    zones[sea] = B
    return zones


def build_zone_raster(clutter_path: str, out_path: str, terrain_path: Optional[str] = None, **options) -> str:
    """Write the zone GeoTIFF on the grid of `clutter_path`; returns `out_path`. See module docstring for options."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(clutter_path) as src:
        land = src.read(1)
        profile = src.profile.copy()
        lat_mid = 0.5 * (src.bounds.top + src.bounds.bottom)
        pixel_m = (abs(src.res[1]) * M_PER_DEG, abs(src.res[0]) * M_PER_DEG * max(math.cos(math.radians(lat_mid)), 0.05))
        elevation = None
        if terrain_path:
            elevation = np.full(land.shape, np.nan, dtype=np.float32)
            with rasterio.open(terrain_path) as dem:
                reproject(rasterio.band(dem, 1), elevation, src_nodata=dem.nodata, dst_transform=src.transform,
                          dst_crs=src.crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
    zones = zones_from_land_cover(land, pixel_m, elevation, **options)
    profile.update(driver="GTiff", dtype="uint8", count=1, nodata=0, compress="lzw")
    profile.pop("photometric", None)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(zones, 1)
    return out_path
