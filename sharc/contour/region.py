"""Terrain data of a region: elevation, land cover and P.452 radio-climatic zones, as GeoTIFF files.

Nothing is tied to a place: the files are given by path, or taken from a terrain downloaded by the GUI
(``sharc.propagation.real_terrain``: SRTM elevation + ESA WorldCover land cover + zones derived from the water).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Region:
    terrain: str                         # elevation raster [m], geographic degrees
    clutter: str = ""                    # land-cover raster ('' = no clutter heights)
    zones: str = ""                      # P.452 zones raster: 1 = A1 coastal, 2 = A2 inland, 3 = B sea ('' = all inland)
    clutter_heights: str = "worldcover"  # height table of the land-cover classes: celplan, p452_tab3 or worldcover
    step_m: float = 50.0                 # spacing of the profile points

    def check(self) -> None:
        """Raise a clear error when a file is missing, instead of failing in the middle of a campaign."""
        for label, path in (("terrain", self.terrain), ("clutter", self.clutter), ("zones", self.zones)):
            if path and not os.path.isfile(path):
                raise FileNotFoundError(f"Region.{label}: file not found: {path}")
        if not self.terrain:
            raise ValueError("Region.terrain is required")
        if self.step_m <= 0:
            raise ValueError("Region.step_m must be > 0")

    @classmethod
    def from_terrain_set(cls, tset, step_m: float = 50.0, derive_zones: bool = True) -> "Region":
        """Region of a terrain loaded in the GUI (`TerrainSet`): terrain.tif, clutter.tif and, when asked, zones.tif.

        The zones are derived from the water of the land cover and the elevation (see
        `real_terrain.zones`) when the set has none yet."""
        zones = os.path.join(str(tset.folder), "zones.tif")
        if derive_zones and not os.path.isfile(zones):
            from sharc.propagation.real_terrain.zones import build_zone_raster
            build_zone_raster(str(tset.clutter), zones, str(tset.terrain))
        return cls(str(tset.terrain), str(tset.clutter), zones if os.path.isfile(zones) else "", "worldcover", step_m)
