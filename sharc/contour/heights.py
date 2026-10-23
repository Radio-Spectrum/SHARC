"""Height of the reference base station at a distance from the protected station.

Rule: at distance d, the median height of the base stations of a database whose distance to the station lies in
[d (1 - window), d (1 + window)] (the whole ring, 360 degrees, the same for every ray). A ring with fewer than
``n_min`` stations is widened continuously until it holds ``n_min`` (the ``n_min`` stations with the smallest |r - d|),
so the median is never taken over an empty set. Without a database, a constant height is used.
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple

import numpy as np

from sharc.contour import geometry


class HeightTable:
    def __init__(self, base_csv: str, lat0: float, lon0: float, window: float = 0.10, n_min: int = 20):
        import pandas as pd
        base = pd.read_csv(base_csv)
        for col in ("latitude", "longitude", "altura"):
            if col not in base.columns:
                raise KeyError(f"the base station database has no column {col!r}: {base_csv}")
        for col in ("latitude", "longitude", "altura"):
            base[col] = pd.to_numeric(base[col], errors="coerce")
        valid = np.isfinite(base[["latitude", "longitude", "altura"]]).all(axis=1) & (base.altura > 0)
        self.dropped = int((~valid).sum())               # rows with a missing / non-numeric field or a height <= 0
        base = base[valid]
        if base.empty:
            raise ValueError(f"the base station database has no usable row (latitude, longitude, altura > 0): {base_csv}")
        self.r_m = geometry.distance_m(lat0, lon0, base.latitude.to_numpy(), base.longitude.to_numpy())
        self.h = base.altura.to_numpy(dtype=float)
        self.window, self.n_min = float(window), int(n_min)
        self._cache: Dict[float, Tuple[float, int, float]] = {}

    def height(self, d_m: float) -> Tuple[float, int, float]:
        """(height [m], number of stations used, effective relative half-width of the ring)."""
        key = round(float(d_m), 1)
        if key in self._cache:
            return self._cache[key]
        dist = np.abs(self.r_m - d_m)
        mask = dist <= self.window * d_m
        width = self.window
        if mask.sum() < self.n_min:
            k = min(self.n_min, dist.size)
            edge = np.partition(dist, k - 1)[k - 1]
            mask = dist <= edge
            width = float(edge / d_m)
        out = (float(np.median(self.h[mask])), int(mask.sum()), float(width))
        self._cache[key] = out
        return out

    def __call__(self, d_m: float) -> float:
        return self.height(d_m)[0]


def constant_height(height_m: float) -> Callable[[float], float]:
    """Height function for a scenario without a base station database."""
    if not np.isfinite(height_m) or height_m <= 0:
        raise ValueError("the base station height must be finite and > 0")
    return lambda d_m: float(height_m)
