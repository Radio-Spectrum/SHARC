# -*- coding: utf-8 -*-
"""Raster sampling for the precomputed P.452 profiles.

``GridRaster`` loads a single-band GeoTIFF in geographic degrees and samples it
at arbitrary lat/lon, taking each pixel value as located at the pixel CENTRE:

* ``method="bilinear"`` for continuous data (terrain heights);
* ``method="nearest"`` for categorical data (land-cover classes, zones).

Points outside the raster or on nodata return ``np.nan`` (bilinear) or
``fill`` (nearest).

Also holds the clutter height tables used by P.452-18 eq. (6e).
"""
from __future__ import annotations

import os

import numpy as np
import rasterio

# Representative clutter heights (m) per CelPlan land-cover class.
CELPLAN_HEIGHTS = {1: 30, 2: 15, 3: 10, 4: 6, 5: 4, 6: 4, 7: 15, 8: 0, 9: 10, 10: 25,
                   11: 0, 12: 10, 13: 0, 14: 25, 15: 15, 16: 6, 17: 0, 18: 3, 19: 45,
                   20: 0, 21: 0, 22: 0, 23: 0, 24: 6, 25: 0, 26: 0, 27: 0, 28: 0}
# P.452-18 Table 3 (water/sea 0, open/rural 0, suburban 10, urban/trees/forest
# 15, dense urban 20) with the CelPlan classes assigned to each category.
P452_TAB3_HEIGHTS = {1: 20, 10: 20,
                     2: 15, 3: 15, 7: 15, 9: 15, 12: 15, 14: 15, 15: 15, 19: 15, 24: 15,
                     4: 10, 5: 10, 6: 10,
                     8: 0, 11: 0, 13: 0, 16: 0, 17: 0, 18: 0, 20: 0, 21: 0, 22: 0,
                     23: 0, 25: 0, 26: 0, 27: 0, 28: 0}
HEIGHT_TABLES = {"celplan": CELPLAN_HEIGHTS, "p452_tab3": P452_TAB3_HEIGHTS}


def height_lut(name: str) -> np.ndarray:
    """Lookup array class -> clutter height (m); classes not listed get 0."""
    if name not in HEIGHT_TABLES:
        raise ValueError(f"clutter_heights must be one of {sorted(HEIGHT_TABLES)}, got {name!r}")
    lut = np.zeros(256, float)
    for k, v in HEIGHT_TABLES[name].items():
        lut[k] = v
    return lut


class GridRaster:
    """Whole single-band raster in RAM, sampled at pixel centres."""

    def __init__(self, path: str | os.PathLike):
        self.path = str(path)
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        with rasterio.open(self.path) as ds:
            self.data = ds.read(1)
            self.transform = ds.transform
            self.nodata = ds.nodata
        self.inv = ~self.transform

    def _rc(self, lat, lon):
        col, row = self.inv * (np.asarray(lon, float), np.asarray(lat, float))
        # pixel (r, c) has its centre at fractional index (r + 0.5, c + 0.5)
        return np.atleast_1d(row) - 0.5, np.atleast_1d(col) - 0.5

    def sample(self, lat, lon, method: str = "bilinear", fill=0):
        """Sample the raster at the given points.

        Parameters
        ----------
        lat, lon : array_like
            Coordinates of the points [deg].
        method : str
            "bilinear" (continuous data) or "nearest" (categorical data).
        fill
            Value for points outside the raster or on nodata ("nearest" only;
            "bilinear" returns NaN there).

        Returns
        -------
        np.ndarray
            One value per point.
        """
        row, col = self._rc(lat, lon)
        h, w = self.data.shape
        if method == "nearest":
            r = np.rint(row).astype(int)
            c = np.rint(col).astype(int)
            ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
            out = np.full(row.shape, fill, dtype=self.data.dtype)
            out[ok] = self.data[r[ok], c[ok]]
            if self.nodata is not None:
                out[ok & (out == self.nodata)] = fill
            return out
        if method != "bilinear":
            raise ValueError(method)
        r0 = np.floor(row).astype(int)
        c0 = np.floor(col).astype(int)
        fr, fc = row - r0, col - c0
        r0c, r1c = np.clip(r0, 0, h - 1), np.clip(r0 + 1, 0, h - 1)
        c0c, c1c = np.clip(c0, 0, w - 1), np.clip(c0 + 1, 0, w - 1)
        ok = (row >= -0.5) & (row <= h - 0.5) & (col >= -0.5) & (col <= w - 0.5)
        v = [self.data[a, b].astype(float) for a, b in ((r0c, c0c), (r0c, c1c), (r1c, c0c), (r1c, c1c))]
        if self.nodata is not None:
            for x in v:
                x[x == self.nodata] = np.nan
        top = v[0] * (1 - fc) + v[1] * fc
        bot = v[2] * (1 - fc) + v[3] * fc
        out = top * (1 - fr) + bot * fr
        out[~ok] = np.nan
        return out
