"""Sanity checks on station positions, using real land cover (ESA WorldCover).

`sites_on_water()` flags base stations that fall on permanent water (WorldCover class 80), which
usually means a wrong coordinate. The check needs land-cover tiles, so it runs in a background
thread (`SiteCheckJob`) and never blocks the GUI.
"""
from __future__ import annotations

from typing import List, Sequence

import numpy as np
from PySide6.QtCore import QThread, Signal

WATER = 80
ZOOM = 14          # ~9.5 m per pixel, the native WorldCover resolution


def sites_on_water(lat: Sequence[float], lon: Sequence[float], zoom: int = ZOOM) -> List[int]:
    """Indices of the points that lie on permanent water."""
    from core import tile_service as ts
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    by_tile = {}
    for i, (la, lo) in enumerate(zip(lat, lon)):
        x, y, px, py = ts.lonlat_to_tile(float(la), float(lo), zoom)
        by_tile.setdefault((x, y), []).append((i, px, py))
    wet: List[int] = []
    for (x, y), points in by_tile.items():
        codes = ts.worldcover_codes(zoom, x, y)
        if codes is None:
            continue
        for i, px, py in points:
            if int(codes[int(min(py, ts.TILE - 1)), int(min(px, ts.TILE - 1))]) == WATER:
                wet.append(i)
    return sorted(wet)


class SiteCheckJob(QThread):
    """Runs `sites_on_water` off the GUI thread."""

    done = Signal(object, object, object)       # indices, lat array, lon array

    def __init__(self, lat, lon, parent=None):
        super().__init__(parent)
        self.lat, self.lon = np.asarray(lat, float), np.asarray(lon, float)

    def run(self):  # noqa: D401 (Qt override)
        try:
            wet = sites_on_water(self.lat, self.lon)
        except Exception:  # noqa: BLE001 - offline: no warning rather than a false one
            wet = []
        self.done.emit(wet, self.lat, self.lon)
