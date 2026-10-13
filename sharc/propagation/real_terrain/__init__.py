# -*- coding: utf-8 -*-
"""
Real terrain & clutter acquisition and reading for SHARC.

- :func:`download_terrain` downloads SRTM/global DEM tiles for a rectangle or a
  country, resamples them to a chosen resolution, and writes a single GeoTIFF.
- :func:`download_clutter` builds an ESA WorldCover land-cover ("clutter") map
  on the same grid as the terrain.
- :class:`RealTerrain` / :class:`RealClutter` load those GeoTIFFs into RAM and
  provide elevation / class lookups.
"""

from sharc.propagation.real_terrain.download_terrain import (  # noqa: F401
    download_terrain,
    estimate_ram_bytes,
    human_bytes,
)
from sharc.propagation.real_terrain.download_clutter import (  # noqa: F401
    download_clutter,
    WORLDCOVER_CLASSES,
    WORLDCOVER_COLORS,
)
from sharc.propagation.real_terrain.adaptive_mesh import (  # noqa: F401
    build_adaptive_mesh,
)
from sharc.propagation.real_terrain.terrain_reader import (  # noqa: F401
    RealTerrain,
    RealClutter,
    RealAdaptiveMesh,
)

__all__ = [
    "download_terrain",
    "download_clutter",
    "build_adaptive_mesh",
    "RealTerrain",
    "RealClutter",
    "RealAdaptiveMesh",
    "WORLDCOVER_CLASSES",
    "WORLDCOVER_COLORS",
    "estimate_ram_bytes",
    "human_bytes",
]
