# -*- coding: utf-8 -*-
"""
Real terrain acquisition for SHARC.

Downloads SRTM/global DEM tiles from the public AWS "elevation-tiles-prod"
(Skadi / 1-arc-second HGT) dataset, resamples them to a user-chosen resolution
and merges everything into a single Cloud-Optimized GeoTIFF (COG) per region.

Two ways to specify the region:
    * a rectangle  -> bbox=(lon_min, lat_min, lon_max, lat_max)
    * a country    -> country="Brazil"  (Natural Earth admin_0 polygon)

The resulting GeoTIFF is read back by :mod:`sharc.propagation.real_terrain.terrain_reader`.

Example
-------
CLI::

    python -m sharc.propagation.real_terrain.download_terrain \
        --country Brazil --resolution 1000 --out brazil_1km.tif

    python -m sharc.propagation.real_terrain.download_terrain \
        --bbox -48 -16 -47 -15 --resolution 200 --out brasilia_200m.tif

Python::

    from sharc.propagation.real_terrain.download_terrain import download_terrain
    download_terrain(country="Brazil", resolution_m=1000.0, out_path="brazil_1km.tif")

Requires: numpy, requests, rasterio, geopandas, shapely (tqdm optional).
"""

from __future__ import annotations

import argparse
import gzip
import math
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.merge import merge as rio_merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely.geometry import box

try:  # progress bar is optional
    from tqdm import tqdm
except Exception:  # pragma: no cover
    def tqdm(it, **_kw):
        return it

# ============================================================
# CONFIG  --  edit these and just run the file:  python download_terrain.py
# (or `python -m sharc.propagation.real_terrain.download_terrain`)
# Any command-line argument you pass overrides the matching value here.
# ============================================================
CONFIG = {
    # --- region: set EITHER 'country' OR 'bbox' (leave the other None) ---
    # bbox order is (LON_min, LAT_min, LON_max, LAT_max) -- longitude FIRST.
    "country": None,                        # e.g. "Brazil", "Finland"
    #"bbox": None,                            # e.g. (-48, -16, -47, -15)
    "bbox": (-44.903642, -23.326557, -40.819770, -21.471170),   # Rio de Janeiro region

    # --- processing ---
        "resolution_m": 100,                 # output grid spacing in metres
        "out_path": "terrain.tif",              # output GeoTIFF
        "mask_to_country": True,                # clip outside the country polygon
        "max_workers": 12,                      # parallel download threads
        "as_cog": True,                         # Cloud-Optimized GeoTIFF

    # --- live map preview (matplotlib) ---
        "live_preview": True,                   # show the mosaic filling in real time
        "preview_res_m": None,                  # None -> same as resolution_m
        "preview_every_n": 5,                   # redraw every N completed tiles
        "preview_png": None,                    # save final preview PNG to this path

    # --- also build a clutter / land-cover map (ESA WorldCover) ---
        "also_clutter": True,                   # download a second map (clutter)
        "clutter_out_path": "clutter.tif",      # aligned to the terrain grid

    # --- also build an adaptive-resolution mesh (needs clutter) ---
        "adaptive_mesh": True,                 # variable-resolution vector mesh
        "mesh_out_path": "mesh.gpkg",           # GeoPackage (or .geojson)
        "mesh_format": "gpkg",                  # "gpkg" or "geojson"
        "mesh_res_m": {"urban": 30, "suburban": 150, "rural": 1000},
        "urban_window_m": 1000,                 # moving window for urban density
        "dens_high": 0.5, "dens_low": 0.1,      # tier thresholds
        "mesh_water": "exclude",                # "exclude" or "coarse"
        "tier_out_path": None,                  # e.g. "tiers.tif" for QA (optional)
}







# ============================================================
# Constants
# ============================================================
# Public, open, no-auth SRTM/global DEM (1" over land, ~30 m at the equator).
BASE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/"

NODATA_I16 = np.int16(-32768)
_METERS_PER_DEG_LAT = 111_320.0

# Max pixels on the longest side of the LIVE preview (output is unaffected).
PREVIEW_MAX_PX = 2000

# Persistent cache for raw downloaded tiles (.hgt.gz), reused across runs so a
# tile is never fetched twice. Stored compressed; any resolution reuses it.
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "tile_cache"

# Rough average size of a Skadi .hgt.gz land tile, for download estimates only.
AVG_HGT_GZ_BYTES = 7 * 1024 * 1024

# Canonical home for generated maps (terrain / clutter / mesh) that SHARC reads.
# Absolute, so it works regardless of the working directory. Git-ignored.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def resolve_output(path: str | os.PathLike) -> Path:
    """Resolve an output path under ``DEFAULT_DATA_DIR`` unless it is absolute.

    A bare filename (e.g. ``"terrain.tif"``) lands in the module's ``data/``
    folder; an absolute path is used as-is. The parent directory is created.
    """
    p = Path(path)
    if not p.is_absolute():
        p = DEFAULT_DATA_DIR / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

# Natural Earth country polygons already shipped with SHARC (used by topology).
_COUNTRIES_SHP = (
    Path(__file__).resolve().parents[2]
    / "topology" / "map" / "ne_110m_admin_0_countries.shp"
)





# ============================================================
# Unit helpers
# ============================================================
def meters_to_deg_lat(m: float) -> float:
    """Convert a north-south distance in metres to degrees of latitude."""
    return m / _METERS_PER_DEG_LAT


def estimate_ram_bytes(width: int, height: int,
                       dtype: np.dtype = np.int16) -> int:
    """RAM (bytes) to hold the full raster as a single numpy array."""
    return int(width) * int(height) * int(np.dtype(dtype).itemsize)


def human_bytes(n: float) -> str:
    """Human-readable byte string (e.g. '1.4 GB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


# ============================================================
# Region resolution (bbox or country)
# ============================================================
def _country_geometry(country: str):
    """Return (shapely_geometry, bbox) for a country name (Natural Earth)."""
    import geopandas as gpd

    if not _COUNTRIES_SHP.exists():
        raise FileNotFoundError(
            f"Country shapefile not found at {_COUNTRIES_SHP}. "
            "Pass a bbox instead, or provide the Natural Earth admin_0 shapefile."
        )
    gdf = gpd.read_file(_COUNTRIES_SHP).to_crs("EPSG:4326")

    # Match on the usual Natural Earth name columns, case-insensitively.
    name_cols = [c for c in ("NAME", "NAME_LONG", "ADMIN", "SOVEREIGNT")
                 if c in gdf.columns]
    key = country.strip().lower()
    mask = np.zeros(len(gdf), dtype=bool)
    for col in name_cols:
        mask |= gdf[col].astype(str).str.strip().str.lower() == key
    hit = gdf[mask]
    if hit.empty:  # fall back to substring match
        for col in name_cols:
            mask |= gdf[col].astype(str).str.strip().str.lower().str.contains(key)
        hit = gdf[mask]
    if hit.empty:
        sample = sorted(gdf[name_cols[0]].astype(str).unique())[:20]
        raise ValueError(
            f"Country '{country}' not found. Examples of valid names: {sample} ..."
        )

    geom = hit.geometry.union_all()
    minx, miny, maxx, maxy = geom.bounds
    return geom, (minx, miny, maxx, maxy)


def _resolve_region(country: Optional[str],
                    bbox: Optional[Tuple[float, float, float, float]]):
    """Return (mask_geometry_or_None, (lon_min, lat_min, lon_max, lat_max))."""
    if country and bbox:
        raise ValueError("Pass either 'country' or 'bbox', not both.")
    if country:
        return _country_geometry(country)
    if bbox:
        lon_min, lat_min, lon_max, lat_max = bbox
        if lon_min >= lon_max or lat_min >= lat_max:
            raise ValueError(
                "bbox must be (lon_min, lat_min, lon_max, lat_max) with min < max.")
        return None, (lon_min, lat_min, lon_max, lat_max)
    raise ValueError("You must provide either 'country' or 'bbox'.")


def _tiles_for_bbox(bbox, mask_geom=None) -> list[Tuple[int, int]]:
    """Integer 1x1 degree tile corners (lat0, lon0) covering the bbox.

    If ``mask_geom`` is given, only tiles that actually intersect the geometry
    are kept (avoids downloading ocean tiles for a country's bounding box).
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    lat0s = range(int(math.floor(lat_min)), int(math.floor(lat_max)) + 1)
    lon0s = range(int(math.floor(lon_min)), int(math.floor(lon_max)) + 1)
    tiles = []
    for lat0 in lat0s:
        for lon0 in lon0s:
            if mask_geom is not None:
                if not mask_geom.intersects(box(lon0, lat0, lon0 + 1, lat0 + 1)):
                    continue
            tiles.append((lat0, lon0))
    return tiles


# ============================================================
# Skadi tile download + read
# ============================================================
def _skadi_name(lat0: int, lon0: int) -> Tuple[str, str]:
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    folder = f"{ns}{abs(lat0):02d}"
    file_gz = f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}.hgt.gz"
    return folder, file_gz


def _hgt_bytes_to_array(raw: bytes) -> Optional[np.ndarray]:
    """Decode raw big-endian int16 HGT bytes into a square array."""
    nvals = len(raw) // 2
    n = int(round(math.sqrt(nvals)))
    if n * n != nvals:
        return None
    return np.frombuffer(raw, dtype=">i2").reshape((n, n)).astype(np.int16)


def _download_hgt(lat0: int, lon0: int, cache_dir: Optional[Path] = None,
                  timeout: int = 180) -> Optional[np.ndarray]:
    """Return one Skadi tile as an int16 array, using a persistent cache.

    If ``cache_dir`` holds the tile's ``.hgt.gz`` it is read from disk (no
    network); otherwise it is downloaded and cached. Returns ``None`` when the
    tile does not exist (e.g. all-ocean cells).
    """
    folder, file_gz = _skadi_name(lat0, lon0)
    cache_path = Path(cache_dir) / file_gz if cache_dir else None

    # 1) Cache hit -> no download.
    if cache_path is not None and cache_path.exists():
        try:
            return _hgt_bytes_to_array(gzip.decompress(cache_path.read_bytes()))
        except Exception:
            pass  # corrupt cache entry -> re-fetch below

    # 2) Download.
    url = BASE_URL + f"{folder}/{file_gz}"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        content = r.content
        arr = _hgt_bytes_to_array(gzip.decompress(content))
    except Exception:
        return None

    # 3) Cache the compressed bytes for next time.
    if cache_path is not None and arr is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(cache_path.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(cache_path)
        except Exception:
            pass
    return arr


def _resample_tile(arr: np.ndarray, lat0: int, lon0: int,
                   target_res_deg: float) -> Tuple[np.ndarray, "rasterio.Affine"]:
    """Resample one 1x1 degree tile to the target resolution (EPSG:4326)."""
    n = arr.shape[0]
    src_res_deg = 1.0 / (n - 1)  # HGT samples include both endpoints
    src_transform = from_origin(lon0, lat0 + 1.0, src_res_deg, src_res_deg)

    out_h = max(1, int(round(1.0 / target_res_deg)))
    out_w = out_h
    dst = np.full((out_h, out_w), NODATA_I16, dtype=np.int16)
    dst_transform = from_origin(lon0, lat0 + 1.0, target_res_deg, target_res_deg)

    # Downsample -> average; upsample -> bilinear.
    method = (Resampling.average if target_res_deg >= src_res_deg
              else Resampling.bilinear)
    reproject(
        source=arr, destination=dst,
        src_transform=src_transform, src_crs="EPSG:4326",
        dst_transform=dst_transform, dst_crs="EPSG:4326",
        src_nodata=NODATA_I16, dst_nodata=NODATA_I16,
        resampling=method,
    )
    return dst, dst_transform


def _write_temp_tile(dst: np.ndarray, transform, path: Path) -> Path:
    profile = {
        "driver": "GTiff", "height": dst.shape[0], "width": dst.shape[1],
        "count": 1, "dtype": "int16", "crs": "EPSG:4326",
        "transform": transform, "nodata": float(NODATA_I16),
        "compress": "LZW", "predictor": 2,
    }
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(dst, 1)
    return path


# ============================================================
# Live preview (real-time mosaic, matplotlib)
# ============================================================
class _LivePreview:
    """Real-time mosaic that fills in tile-by-tile, already resampled.

    Kept independent from the output: the preview buffer can be coarser than the
    output grid (``preview_res_m``) so watching a large country stays cheap.
    """

    def __init__(self, region_bbox, preview_res_deg, mask_geom, title, *,
                 cmap="terrain", vmin=0, vmax=3000, norm=None,
                 nodata=NODATA_I16, dtype=np.int16, cbar_label="Elevation (m)",
                 legend=None, resampling=Resampling.average):
        import matplotlib.pyplot as plt  # lazy import

        self.plt = plt
        self.region_bbox = region_bbox
        self.res = preview_res_deg
        self.nodata = nodata
        self.resampling = resampling
        lon_min, lat_min, lon_max, lat_max = region_bbox
        self.W = max(1, int(round((lon_max - lon_min) / preview_res_deg)))
        self.H = max(1, int(round((lat_max - lat_min) / preview_res_deg)))
        self.buffer = np.full((self.H, self.W), nodata, dtype=dtype)

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(11, 6))
        masked = np.ma.masked_equal(self.buffer, nodata)
        imshow_kw = dict(extent=[lon_min, lon_max, lat_min, lat_max],
                         origin="upper", cmap=cmap, alpha=0.97)
        if norm is not None:
            imshow_kw["norm"] = norm
        else:
            imshow_kw["vmin"], imshow_kw["vmax"] = vmin, vmax
        self.im = self.ax.imshow(masked, **imshow_kw)

        if legend is not None:
            # Categorical: discrete legend instead of a colorbar.
            self.ax.legend(handles=legend, loc="center left",
                           bbox_to_anchor=(1.01, 0.5), fontsize=8, framealpha=0.9)
        else:
            cbar = plt.colorbar(self.im, ax=self.ax, fraction=0.035, pad=0.02)
            cbar.set_label(cbar_label)
        self.ax.set_xlim(lon_min, lon_max)
        self.ax.set_ylim(lat_min, lat_max)
        self.ax.set_xlabel("Longitude")
        self.ax.set_ylabel("Latitude")
        self.ax.set_title(title)
        self.fig.tight_layout()

        # Optional country outline for context.
        if mask_geom is not None:
            try:
                import geopandas as gpd
                gpd.GeoSeries([mask_geom], crs="EPSG:4326").boundary.plot(
                    ax=self.ax, color="black", linewidth=0.6)
            except Exception:
                pass

        plt.draw()
        plt.pause(0.01)

    @classmethod
    def create(cls, region_bbox, preview_res_deg, mask_geom, title, verbose,
               **style):
        try:
            return cls(region_bbox, preview_res_deg, mask_geom, title, **style)
        except Exception as exc:  # matplotlib missing / no display
            if verbose:
                print(f"[real_terrain] Live preview disabled ({exc}).")
            return None

    def _window(self, lat0, lon0):
        lon_min, _lat_min, _lon_max, lat_max = self.region_bbox
        r0 = int(np.floor((lat_max - (lat0 + 1.0)) / self.res))
        r1 = int(np.ceil((lat_max - lat0) / self.res))
        c0 = int(np.floor((lon0 - lon_min) / self.res))
        c1 = int(np.ceil((lon0 + 1.0 - lon_min) / self.res))
        r0 = max(0, min(self.H, r0)); r1 = max(0, min(self.H, r1))
        c0 = max(0, min(self.W, c0)); c1 = max(0, min(self.W, c1))
        return r0, r1, c0, c1

    def paste(self, tile_arr, tile_transform, lat0, lon0):
        """Resample one finished tile into its slot of the preview buffer."""
        r0, r1, c0, c1 = self._window(lat0, lon0)
        if r1 <= r0 or c1 <= c0:
            return
        patch = np.full((r1 - r0, c1 - c0), self.nodata, dtype=self.buffer.dtype)
        lon_min, _lat_min, _lon_max, lat_max = self.region_bbox
        patch_transform = from_origin(
            lon_min + c0 * self.res, lat_max - r0 * self.res, self.res, self.res)
        reproject(
            source=tile_arr, destination=patch,
            src_transform=tile_transform, src_crs="EPSG:4326",
            dst_transform=patch_transform, dst_crs="EPSG:4326",
            src_nodata=self.nodata, dst_nodata=self.nodata,
            resampling=self.resampling,
        )
        sub = self.buffer[r0:r1, c0:c1]
        m = patch != self.nodata
        sub[m] = patch[m]
        self.buffer[r0:r1, c0:c1] = sub

    def paste_full(self, source, src_transform=None, src_crs="EPSG:4326"):
        """Reproject a whole source (array or rasterio.band) into the buffer.

        Only the overlapping area is written (rest stays nodata). Handy for
        sources whose native tiling differs from the terrain 1-degree grid.
        """
        lon_min, _lat_min, _lon_max, lat_max = self.region_bbox
        prev_transform = from_origin(lon_min, lat_max, self.res, self.res)
        tmp = np.full((self.H, self.W), self.nodata, dtype=self.buffer.dtype)
        reproject(
            source=source, destination=tmp,
            src_transform=src_transform, src_crs=src_crs,
            dst_transform=prev_transform, dst_crs="EPSG:4326",
            src_nodata=self.nodata, dst_nodata=self.nodata,
            resampling=self.resampling,
        )
        m = tmp != self.nodata
        self.buffer[m] = tmp[m]

    def redraw(self):
        self.im.set_data(np.ma.masked_equal(self.buffer, self.nodata))
        self.fig.canvas.draw_idle()
        self.plt.pause(0.001)

    def finalize(self, png_path=None, verbose=True, block=True):
        self.redraw()
        if png_path:
            self.fig.savefig(png_path, dpi=180)
            if verbose:
                print(f"[real_terrain] Saved preview PNG: {png_path}")
        if block:
            # Block on ALL open figures (terrain + clutter shown together).
            self.plt.ioff()
            try:
                self.plt.show(block=True)
            except Exception:
                pass
        else:
            # Keep the window open and interactive while more work continues.
            self.plt.pause(0.1)


# ============================================================
# Main entry point
# ============================================================
def download_terrain(
    *,
    country: Optional[str] = None,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    resolution_m: float = 250.0,
    out_path: str | os.PathLike = "terrain.tif",
    mask_to_country: bool = True,
    max_workers: int = 16,
    as_cog: bool = True,
    live_preview: bool = False,
    preview_res_m: Optional[float] = None,
    preview_every_n: int = 1,
    preview_png: Optional[str] = None,
    preview_block: bool = True,
    cache_dir: str | os.PathLike | None = DEFAULT_CACHE_DIR,
    verbose: bool = True,
) -> Path:
    """Download, resample and merge real terrain into a single GeoTIFF.

    Parameters
    ----------
    country : str, optional
        Country name (Natural Earth). Mutually exclusive with ``bbox``.
    bbox : (lon_min, lat_min, lon_max, lat_max), optional
        Geographic rectangle in degrees. Mutually exclusive with ``country``.
    resolution_m : float, default 250.0
        Output ground sampling distance in metres (e.g. 1000 for 1 km,
        200 for 200 m). Coarser => smaller file and less RAM.
    out_path : path
        Destination GeoTIFF.
    mask_to_country : bool, default True
        When downloading a country, set cells outside the polygon to nodata.
    max_workers : int, default 16
        Parallel download threads.
    as_cog : bool, default True
        Write a Cloud-Optimized GeoTIFF (tiled + overviews) if the driver is
        available; otherwise a plain tiled GeoTIFF.
    live_preview : bool, default False
        Show a matplotlib mosaic that fills in tile-by-tile (already resampled),
        like the old ``generate_terrain.py``. Requires matplotlib + a display.
    preview_res_m : float, optional
        Resolution of the preview buffer in metres. Defaults to ``resolution_m``.
        Use a coarser value to keep the preview light for large regions.
    preview_every_n : int, default 1
        Redraw the preview every N completed tiles.
    preview_png : str, optional
        If given, save the final preview to this PNG path.
    preview_block : bool, default True
        If True, block on the preview window at the end. Set False to keep it
        open non-blocking (e.g. so a following clutter preview can be shown too).
    cache_dir : path, optional
        Directory of cached ``.hgt.gz`` tiles. Tiles found here are not
        re-downloaded; new tiles are saved here. Defaults to ``tile_cache/``
        next to this module. Set to None to disable caching.
    verbose : bool, default True
        Print progress and the estimated RAM to load the result.

    Returns
    -------
    pathlib.Path
        The written GeoTIFF path.
    """
    mask_geom, region_bbox = _resolve_region(country, bbox)
    target_res_deg = meters_to_deg_lat(resolution_m)
    tiles = _tiles_for_bbox(region_bbox, mask_geom)
    if not tiles:
        raise RuntimeError("No terrain tiles intersect the requested region.")

    label = country or f"bbox {region_bbox}"
    if verbose:
        print(f"[real_terrain] Region: {label}")
        print(f"[real_terrain] Target resolution: {resolution_m:g} m "
              f"(~{target_res_deg:.6f} deg)")
        print(f"[real_terrain] Tiles to fetch: {len(tiles)}")

    # Optional real-time mosaic preview (main thread paints as tiles finish).
    preview = None
    if live_preview:
        preview_res_deg = meters_to_deg_lat(preview_res_m or resolution_m)
        # A live matplotlib image cannot sensibly render tens of millions of
        # pixels, so coarsen the PREVIEW (not the output) to a pixel budget.
        lon_span = region_bbox[2] - region_bbox[0]
        lat_span = region_bbox[3] - region_bbox[1]
        max_dim = max(lon_span, lat_span) / preview_res_deg
        if max_dim > PREVIEW_MAX_PX:
            preview_res_deg *= max_dim / PREVIEW_MAX_PX
            if verbose:
                eff_m = preview_res_deg * _METERS_PER_DEG_LAT
                print(f"[real_terrain] Preview capped to ~{eff_m:.0f} m "
                      f"({PREVIEW_MAX_PX}px max) to stay responsive; "
                      "output keeps full resolution.")
        preview = _LivePreview.create(
            region_bbox, preview_res_deg, mask_geom,
            f"real_terrain live preview | {label} @ {resolution_m:g} m", verbose)
        if preview is not None and verbose:
            print(f"[real_terrain] Live preview: {preview.W} x {preview.H} px "
                  "(close the window to finish).")

    cache_path = Path(cache_dir) if cache_dir else None
    n_cached = 0
    if cache_path is not None:
        n_cached = sum(
            1 for la, lo in tiles
            if (cache_path / _skadi_name(la, lo)[1]).exists())
    if verbose:
        n_new = len(tiles) - n_cached
        if cache_path is not None:
            print(f"[real_terrain] Cache: {cache_path} "
                  f"({n_cached}/{len(tiles)} tiles already present).")
        # Skadi .hgt.gz average ~7 MB/tile (land); rough estimate only.
        print(f"[real_terrain] Estimated download: ~{human_bytes(n_new * AVG_HGT_GZ_BYTES)} "
              f"({n_new} new tiles to fetch).")

    tmp_dir = Path(tempfile.mkdtemp(prefix="sharc_terrain_"))
    tile_paths: list[Path] = []

    def _job(lat0: int, lon0: int):
        arr = _download_hgt(lat0, lon0, cache_dir=cache_path)
        if arr is None:
            return None
        dst, transform = _resample_tile(arr, lat0, lon0, target_res_deg)
        p = tmp_dir / f"tile_{lat0:+03d}_{lon0:+04d}.tif"
        _write_temp_tile(dst, transform, p)
        # Return the resampled tile so the main thread can paint the preview.
        return (p, lat0, lon0, dst if preview is not None else None, transform)

    ok = fail = 0
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_job, la, lo): (la, lo) for la, lo in tiles}
            for fut in tqdm(as_completed(futs), total=len(futs),
                            desc="tiles", disable=not verbose):
                res = fut.result()
                if res is None:
                    fail += 1
                    continue
                p, lat0, lon0, dst, transform = res
                tile_paths.append(p)
                ok += 1
                if preview is not None:
                    preview.paste(dst, transform, lat0, lon0)
                    if ok % max(1, preview_every_n) == 0:
                        preview.redraw()

        if not tile_paths:
            raise RuntimeError("All tile downloads failed (no data over region).")
        if verbose:
            print(f"[real_terrain] Ready {ok} tiles ({fail} empty/missing). "
                  "Merging...")

        out_path = resolve_output(out_path)
        _merge_and_write(
            tile_paths, region_bbox, target_res_deg, out_path,
            mask_geom if (mask_to_country and mask_geom is not None) else None,
            as_cog=as_cog, verbose=verbose,
        )

        if preview is not None:
            preview.finalize(preview_png, verbose=verbose, block=preview_block)
    finally:
        for p in tile_paths:
            try:
                p.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    return out_path


def _merge_and_write(tile_paths, region_bbox, target_res_deg, out_path,
                     mask_geom, *, as_cog=True, verbose=True) -> None:
    """Merge tiles, crop to bbox, optionally mask, and write the GeoTIFF."""
    srcs = [rasterio.open(p) for p in tile_paths]
    try:
        mosaic, transform = rio_merge(
            srcs, bounds=region_bbox, res=target_res_deg,
            nodata=float(NODATA_I16), resampling=Resampling.nearest,
        )
    finally:
        for s in srcs:
            s.close()

    data = mosaic[0]  # single band
    height, width = data.shape

    if mask_geom is not None:
        outside = geometry_mask(
            [mask_geom.__geo_interface__], out_shape=(height, width),
            transform=transform, invert=False,
        )
        data[outside] = NODATA_I16

    ram = estimate_ram_bytes(width, height, np.int16)
    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 1,
        "dtype": "int16", "crs": "EPSG:4326", "transform": transform,
        "nodata": float(NODATA_I16), "compress": "LZW", "predictor": 2,
        "tiled": True, "blockxsize": 256, "blockysize": 256,
    }
    if as_cog:
        try:
            profile["driver"] = "COG"
            profile["overview_resampling"] = "average"
            # COG driver manages blocking/overviews itself.
            for k in ("tiled", "blockxsize", "blockysize", "predictor"):
                profile.pop(k, None)
            profile["compress"] = "LZW"
        except Exception:
            profile["driver"] = "GTiff"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(data, 1)

    if verbose:
        size = out_path.stat().st_size
        print(f"[real_terrain] Wrote {out_path}")
        print(f"[real_terrain]   grid : {width} x {height} px "
              f"@ {target_res_deg:.6f} deg")
        print(f"[real_terrain]   file : {human_bytes(size)} on disk")
        print(f"[real_terrain]   RAM  : ~{human_bytes(ram)} to load full array "
              f"(int16). Windowed reads use far less.")


# ============================================================
# CLI
# ============================================================
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download & resample real terrain into a GeoTIFF for SHARC. "
                    "With no arguments, the CONFIG block at the top of this file "
                    "is used.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--country", type=str, help="Country name (Natural Earth).")
    g.add_argument("--bbox", type=float, nargs=4,
                   metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
                   help="Bounding rectangle in degrees.")
    p.add_argument("--resolution", type=float, default=250.0,
                   help="Output resolution in metres (e.g. 1000, 200). Default 250.")
    p.add_argument("--out", type=str, default="terrain.tif",
                   help="Output GeoTIFF path.")
    p.add_argument("--no-mask", action="store_true",
                   help="Do not mask outside the country polygon.")
    p.add_argument("--workers", type=int, default=16, help="Download threads.")
    p.add_argument("--no-cog", action="store_true",
                   help="Write a plain tiled GeoTIFF instead of a COG.")
    p.add_argument("--live-preview", action="store_true",
                   help="Show a real-time mosaic preview while downloading.")
    p.add_argument("--preview-res", type=float, default=None,
                   help="Preview resolution in metres (default: same as output).")
    p.add_argument("--preview-every", type=int, default=5,
                   help="Redraw the preview every N tiles. Default 5.")
    p.add_argument("--preview-png", type=str, default=None,
                   help="Save the final preview to this PNG path.")
    return p


def main(argv=None) -> None:
    import sys

    argv = sys.argv[1:] if argv is None else list(argv)

    # No command-line arguments -> run straight from the CONFIG block.
    if not argv:
        cfg = dict(CONFIG)
        also_clutter = cfg.pop("also_clutter", False)
        clutter_out = cfg.pop("clutter_out_path", "clutter.tif")
        adaptive_mesh = cfg.pop("adaptive_mesh", False)
        mesh_kw = {k: cfg.pop(k) for k in (
            "mesh_format", "mesh_res_m", "urban_window_m",
            "dens_high", "dens_low", "mesh_water", "tier_out_path")
            if k in cfg}
        # CONFIG uses 'mesh_out_path'; the function's parameter is 'out_path'.
        if "mesh_out_path" in cfg:
            mesh_kw["out_path"] = cfg.pop("mesh_out_path")

        # The mesh needs clutter; build it as an intermediate if not requested.
        clutter_stage = also_clutter or adaptive_mesh
        # Only the LAST previewed stage blocks; earlier ones stay open.
        terrain_path = download_terrain(
            **cfg, preview_block=not clutter_stage, verbose=True)

        clutter_path = None
        if clutter_stage:
            # Lazy import avoids a circular import at module load.
            from sharc.propagation.real_terrain.download_clutter import (
                download_clutter,
            )
            clutter_path = download_clutter(
                country=cfg["country"], bbox=cfg["bbox"],
                resolution_m=cfg["resolution_m"], out_path=clutter_out,
                like_path=str(terrain_path),
                mask_to_country=cfg["mask_to_country"], as_cog=cfg["as_cog"],
                live_preview=cfg["live_preview"],
                preview_res_m=cfg["preview_res_m"],
                preview_block=not adaptive_mesh, verbose=True,
            )

        if adaptive_mesh:
            from sharc.propagation.real_terrain.adaptive_mesh import (
                build_adaptive_mesh,
            )
            build_adaptive_mesh(
                str(terrain_path), str(clutter_path),
                live_preview=cfg["live_preview"], preview_block=True,
                verbose=True, **mesh_kw,
            )
        return

    args = _build_parser().parse_args(argv)
    if not args.country and not args.bbox:
        raise SystemExit("Provide --country or --bbox (or run with no arguments "
                         "to use the CONFIG block).")
    download_terrain(
        country=args.country,
        bbox=tuple(args.bbox) if args.bbox else None,
        resolution_m=args.resolution,
        out_path=args.out,
        mask_to_country=not args.no_mask,
        max_workers=args.workers,
        as_cog=not args.no_cog,
        live_preview=args.live_preview,
        preview_res_m=args.preview_res,
        preview_every_n=args.preview_every,
        preview_png=args.preview_png,
        verbose=True,
    )


if __name__ == "__main__":
    main()
