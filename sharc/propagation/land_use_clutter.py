# -*- coding: utf-8 -*-
"""ESA WorldCover land-use sampling for representative clutter heights.

Used **offline** to derive (from real land cover) the clutter-height statistics
that feed the statistical clutter model of ITU-R P.1812. It is NOT imported at
simulation runtime — the simulation uses the fitted statistical parameters, so
``rasterio`` is only required for the estimation tooling.

ESA WorldCover (v200, 2021) is a 10 m global land-cover map distributed as 3x3
degree Cloud-Optimized GeoTIFF tiles, free and without authentication.
"""
import os
import warnings

import numpy as np

# ESA WorldCover class -> representative clutter height (m). Values are typical
# representative heights (ITU-R P.1812/P.2108-style clutter); override as needed.
WORLDCOVER_CLUTTER_HEIGHTS = {
    10: 15.0,   # Tree cover
    20: 3.0,    # Shrubland
    30: 1.0,    # Grassland
    40: 2.0,    # Cropland
    50: 20.0,   # Built-up
    60: 0.5,    # Bare / sparse vegetation
    70: 0.0,    # Snow and ice
    80: 0.0,    # Permanent water bodies
    90: 2.0,    # Herbaceous wetland
    95: 8.0,    # Mangroves
    100: 0.5,   # Moss and lichen
}

WORLDCOVER_CLASS_NAMES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare/sparse", 70: "Snow/ice", 80: "Water",
    90: "Wetland", 95: "Mangroves", 100: "Moss/lichen",
}

_DEFAULT_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)


class WorldCoverClutter:
    """Sample ESA WorldCover land cover and map it to representative clutter heights.

    Parameters
    ----------
    cache_dir : str
        Directory to cache downloaded WorldCover tiles.
    class_heights : dict, optional
        Mapping land-cover class code -> clutter height (m).
    auto_download : bool, optional
        Download missing tiles (~80 MB each) on demand. Default True.
    url_template : str, optional
        Tile URL template with a ``{tile}`` placeholder (e.g. "S24W048").
    """

    def __init__(self, cache_dir, class_heights=None, auto_download=True,
                 url_template=""):
        self.cache_dir = cache_dir
        self.class_heights = dict(class_heights or WORLDCOVER_CLUTTER_HEIGHTS)
        self.auto_download = auto_download
        self.url_template = url_template or _DEFAULT_URL
        self._datasets = {}
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def _tile_base(lat, lon):
        """WorldCover 3-degree tile base name (SW corner) for a coordinate."""
        tlat = int(np.floor(lat / 3.0) * 3)
        tlon = int(np.floor(lon / 3.0) * 3)
        ns = "N" if tlat >= 0 else "S"
        ew = "E" if tlon >= 0 else "W"
        return f"{ns}{abs(tlat):02d}{ew}{abs(tlon):03d}"

    def _tile_path(self, lat, lon):
        """Return a local path to the tile, downloading it if needed."""
        tile = self._tile_base(lat, lon)
        path = os.path.join(self.cache_dir, f"WorldCover_{tile}.tif")
        if os.path.isfile(path):
            return path
        if not self.auto_download:
            raise FileNotFoundError(
                f"WorldCover tile {tile} not present in '{self.cache_dir}'.")
        import urllib.request
        url = self.url_template.format(tile=tile)
        warnings.warn(f"Downloading WorldCover tile {tile} (~80 MB) ...")
        tmp = path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": "SHARC-P1812/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as out:
            out.write(resp.read())
        os.replace(tmp, path)
        return path

    def _dataset(self, lat, lon):
        """Open (and cache) the rasterio dataset for the tile covering (lat, lon)."""
        import rasterio
        tile = self._tile_base(lat, lon)
        if tile not in self._datasets:
            self._datasets[tile] = rasterio.open(self._tile_path(lat, lon))
        return self._datasets[tile]

    def sample_classes(self, lats, lons):
        """Return the WorldCover class code at each (lat, lon)."""
        lats = np.atleast_1d(np.asarray(lats, dtype=float))
        lons = np.atleast_1d(np.asarray(lons, dtype=float))
        out = np.zeros(lats.size, dtype=int)
        # Group points by tile to minimise dataset switches
        tiles = {}
        for i, (la, lo) in enumerate(zip(lats, lons)):
            tiles.setdefault(self._tile_base(la, lo), []).append(i)
        for tile, idx in tiles.items():
            ds = self._dataset(lats[idx[0]], lons[idx[0]])
            pts = [(lons[i], lats[i]) for i in idx]
            vals = np.array([v[0] for v in ds.sample(pts)], dtype=int)
            out[idx] = vals
        return out

    def sample_heights(self, lats, lons):
        """Return the representative clutter height (m) at each (lat, lon)."""
        classes = self.sample_classes(lats, lons)
        heights = np.array(
            [self.class_heights.get(int(c), 0.0) for c in classes], dtype=float)
        return heights, classes
