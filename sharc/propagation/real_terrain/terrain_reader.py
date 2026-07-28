# -*- coding: utf-8 -*-
"""
Reader for the real-terrain GeoTIFFs produced by
:mod:`sharc.propagation.real_terrain.download_terrain`.

Loads the DEM into RAM as a single numpy array and provides elevation lookups
and elevation profiles (for e.g. P.452 diffraction paths).

Example
-------
    from sharc.propagation.real_terrain.terrain_reader import RealTerrain

    dem = RealTerrain("brazil_1km.tif")
    print(dem.estimate_ram())          # {'bytes': ..., 'human': '...'} without loading
    dem.load()                         # read full array into RAM
    h = dem.elevation(-15.79, -47.88)  # Brasilia, metres
    d_km, h_m = dem.elevation_profile(-15.79, -47.88, -22.9, -43.2, n=301)
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np
import rasterio

from sharc.propagation.real_terrain.download_terrain import (
    NODATA_I16, estimate_ram_bytes, human_bytes,
)


class RealTerrain:
    """Lazy/loaded access to a real-terrain GeoTIFF (EPSG:4326, int16 metres)."""

    def __init__(self, path: str | os.PathLike):
        self.path = str(path)
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        with rasterio.open(self.path) as ds:
            self.width = ds.width
            self.height = ds.height
            self.transform = ds.transform
            self.bounds = ds.bounds  # (left, bottom, right, top)
            self.crs = ds.crs
            self.dtype = np.dtype(ds.dtypes[0])
            self.nodata = ds.nodata if ds.nodata is not None else float(NODATA_I16)
        self._data: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # RAM estimate (no data read)
    # ------------------------------------------------------------------
    def estimate_ram(self) -> dict:
        """Estimate RAM to hold the full raster, from metadata only."""
        n = estimate_ram_bytes(self.width, self.height, self.dtype)
        return {
            "bytes": n,
            "human": human_bytes(n),
            "width": self.width,
            "height": self.height,
            "dtype": str(self.dtype),
        }

    # ------------------------------------------------------------------
    # Full load
    # ------------------------------------------------------------------
    def load(self, verbose: bool = True) -> np.ndarray:
        """Read the whole DEM into RAM (cached). Returns the 2-D array."""
        if self._data is None:
            if verbose:
                est = self.estimate_ram()
                print(f"[real_terrain] Loading {self.width}x{self.height} DEM "
                      f"(~{est['human']} RAM) from {self.path}")
            with rasterio.open(self.path) as ds:
                self._data = ds.read(1)
        return self._data

    @property
    def data(self) -> np.ndarray:
        """The loaded array (loads on first access)."""
        return self.load(verbose=False)

    # ------------------------------------------------------------------
    # Coordinate <-> pixel
    # ------------------------------------------------------------------
    def _rowcol(self, lat, lon):
        inv = ~self.transform
        col, row = inv * (np.asarray(lon, float), np.asarray(lat, float))
        return np.asarray(row), np.asarray(col)

    def elevation(self, lat, lon) -> np.ndarray | float:
        """Elevation (m) at lat/lon via bilinear interpolation on the loaded array.

        Accepts scalars or arrays. Cells outside the raster or over nodata
        return ``np.nan``.
        """
        data = self.data
        row, col = self._rowcol(lat, lon)
        scalar = (row.ndim == 0)
        row = np.atleast_1d(row).astype(float)
        col = np.atleast_1d(col).astype(float)

        h, w = data.shape
        r0 = np.floor(row).astype(int)
        c0 = np.floor(col).astype(int)
        fr = row - r0
        fc = col - c0
        # Clamp the upper neighbours so edge pixels interpolate against
        # themselves (nearest at the boundary) instead of returning NaN.
        r1 = np.clip(r0 + 1, 0, h - 1)
        c1 = np.clip(c0 + 1, 0, w - 1)

        valid = (r0 >= 0) & (c0 >= 0) & (r0 < h) & (c0 < w)
        out = np.full(row.shape, np.nan, float)

        if np.any(valid):
            rr0, cc0 = r0[valid], c0[valid]
            rr1, cc1 = r1[valid], c1[valid]
            frr, fcc = fr[valid], fc[valid]

            v00 = data[rr0, cc0].astype(float)
            v01 = data[rr0, cc1].astype(float)
            v10 = data[rr1, cc0].astype(float)
            v11 = data[rr1, cc1].astype(float)

            for v in (v00, v01, v10, v11):
                v[v == self.nodata] = np.nan

            top = v00 * (1 - fcc) + v01 * fcc
            bot = v10 * (1 - fcc) + v11 * fcc
            out[valid] = top * (1 - frr) + bot * frr

        return float(out[0]) if scalar else out

    # ------------------------------------------------------------------
    # Great-circle-ish elevation profile between two points
    # ------------------------------------------------------------------
    def elevation_profile(self, lat0, lon0, lat1, lon1,
                          n: int = 301) -> Tuple[np.ndarray, np.ndarray]:
        """Sample ``n`` elevations along the straight lat/lon line P0->P1.

        Returns ``(distance_km, height_m)``. Suitable as a terrain profile for
        diffraction models such as P.452. Distances use a local spherical-earth
        approximation (adequate for < ~1000 km paths).
        """
        lats = np.linspace(lat0, lat1, n)
        lons = np.linspace(lon0, lon1, n)
        heights = np.asarray(self.elevation(lats, lons), float)

        # cumulative great-circle distance
        r_earth = 6371.0  # km
        la = np.radians(lats)
        lo = np.radians(lons)
        dla = np.diff(la)
        dlo = np.diff(lo)
        a = (np.sin(dla / 2) ** 2
             + np.cos(la[:-1]) * np.cos(la[1:]) * np.sin(dlo / 2) ** 2)
        seg = 2 * r_earth * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        dist_km = np.concatenate([[0.0], np.cumsum(seg)])
        return dist_km, heights

    def __repr__(self) -> str:
        return (f"RealTerrain(path={self.path!r}, {self.width}x{self.height}, "
                f"bounds={tuple(round(b, 3) for b in self.bounds)})")


class RealClutter(RealTerrain):
    """Reader for the categorical land-cover / clutter GeoTIFF (uint8 classes).

    Same grid handling as :class:`RealTerrain`, but lookups use nearest
    neighbour and return the WorldCover class code (see ``class_name``).
    """

    def clutter_class(self, lat, lon):
        """WorldCover class code at lat/lon (nearest). Scalar or array; 0 = nodata."""
        data = self.data
        row, col = self._rowcol(lat, lon)
        scalar = (row.ndim == 0)
        row = np.atleast_1d(np.round(row)).astype(int)
        col = np.atleast_1d(np.round(col)).astype(int)
        h, w = data.shape
        valid = (row >= 0) & (col >= 0) & (row < h) & (col < w)
        out = np.zeros(row.shape, dtype=data.dtype)
        out[valid] = data[row[valid], col[valid]]
        return int(out[0]) if scalar else out

    @staticmethod
    def class_name(code) -> str:
        """Human-readable name for a WorldCover class code."""
        from sharc.propagation.real_terrain.download_clutter import (
            WORLDCOVER_CLASSES,
        )
        return WORLDCOVER_CLASSES.get(int(code), "Unknown")

    def __repr__(self) -> str:
        return (f"RealClutter(path={self.path!r}, {self.width}x{self.height}, "
                f"bounds={tuple(round(b, 3) for b in self.bounds)})")


class RealAdaptiveMesh:
    """Reader for the adaptive-resolution terrain mesh (vector points).

    Loads the mesh produced by :func:`adaptive_mesh.build_adaptive_mesh` and
    interpolates elevation from the irregularly-spaced nodes. Nearest-neighbour
    is the default (fast); ``method="linear"`` uses a Delaunay interpolation
    (smoother, heavier). Longitudes are scaled by cos(lat) before the spatial
    query so "nearest" is measured in roughly isotropic ground distance.
    """

    def __init__(self, path: str | os.PathLike):
        import geopandas as gpd

        self.path = str(path)
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        gdf = gpd.read_file(self.path)
        self.gdf = gdf
        self.lon = gdf.geometry.x.to_numpy(dtype=float)
        self.lat = gdf.geometry.y.to_numpy(dtype=float)
        self.elev = gdf["elev_m"].to_numpy(dtype=float)
        self.tier = (gdf["tier"].to_numpy() if "tier" in gdf
                     else np.zeros(len(gdf)))
        self._lat0 = float(np.mean(self.lat)) if len(self.lat) else 0.0
        self._coslat = max(1e-6, np.cos(np.radians(self._lat0)))
        self._tree = None
        self._lin = None

    def __len__(self):
        return len(self.elev)

    def _xy(self, lon, lat):
        return np.column_stack([np.asarray(lon) * self._coslat, np.asarray(lat)])

    def _kdtree(self):
        from scipy.spatial import cKDTree
        if self._tree is None:
            self._tree = cKDTree(self._xy(self.lon, self.lat))
        return self._tree

    def elevation(self, lat, lon, method: str = "nearest"):
        """Interpolated elevation (m) at lat/lon. Scalar or array in/out."""
        lon_a = np.atleast_1d(np.asarray(lon, dtype=float))
        lat_a = np.atleast_1d(np.asarray(lat, dtype=float))
        scalar = np.ndim(lat) == 0

        if method == "linear":
            from scipy.interpolate import LinearNDInterpolator
            if self._lin is None:
                self._lin = LinearNDInterpolator(
                    self._xy(self.lon, self.lat), self.elev)
            out = self._lin(lon_a * self._coslat, lat_a)
        else:
            _d, idx = self._kdtree().query(self._xy(lon_a, lat_a))
            out = self.elev[idx]
        out = np.asarray(out, dtype=float)
        return float(out[0]) if scalar else out

    def elevation_profile(self, lat0, lon0, lat1, lon1, n: int = 301,
                          method: str = "nearest"):
        """Elevation profile P0->P1 sampled from the mesh. (distance_km, h_m)."""
        lats = np.linspace(lat0, lat1, n)
        lons = np.linspace(lon0, lon1, n)
        heights = np.asarray(self.elevation(lats, lons, method=method), float)
        r_earth = 6371.0
        la, lo = np.radians(lats), np.radians(lons)
        dla, dlo = np.diff(la), np.diff(lo)
        a = (np.sin(dla / 2) ** 2
             + np.cos(la[:-1]) * np.cos(la[1:]) * np.sin(dlo / 2) ** 2)
        seg = 2 * r_earth * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        dist_km = np.concatenate([[0.0], np.cumsum(seg)])
        return dist_km, heights

    def __repr__(self) -> str:
        return f"RealAdaptiveMesh(path={self.path!r}, nodes={len(self):,})"
