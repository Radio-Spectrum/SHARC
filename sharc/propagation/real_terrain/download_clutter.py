# -*- coding: utf-8 -*-
"""
Real clutter / land-cover acquisition for SHARC.

Companion to :mod:`sharc.propagation.real_terrain.download_terrain`. Builds a
categorical land-cover ("clutter") GeoTIFF from **ESA WorldCover** (10 m global
land cover, public Cloud-Optimized GeoTIFFs on AWS, no authentication).

The clutter map is written on the SAME grid as the terrain DEM (pass
``like_path`` = the terrain GeoTIFF) so terrain and clutter align pixel-for-pixel
at the same resolution. Categorical data is resampled with **nearest neighbour**
(never averaged).

WorldCover classes (v200 / 2021):
    10 Tree cover        20 Shrubland          30 Grassland
    40 Cropland          50 Built-up           60 Bare / sparse veg
    70 Snow and ice      80 Permanent water    90 Herbaceous wetland
    95 Mangroves        100 Moss and lichen

Example
-------
    from sharc.propagation.real_terrain.download_clutter import download_clutter
    download_clutter(bbox=(-44.9, -23.3, -40.8, -21.5), resolution_m=100.0,
                     out_path="rio_clutter.tif", like_path="rio_terrain.tif")

Requires: numpy, rasterio (built with libcurl for /vsicurl/), geopandas, shapely.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window, from_bounds
from rasterio.windows import transform as win_transform
from shapely.geometry import box

try:  # progress bar is optional
    from tqdm import tqdm
except Exception:  # pragma: no cover
    def tqdm(it, **_kw):
        return it

from sharc.propagation.real_terrain.download_terrain import (
    PREVIEW_MAX_PX,
    _LivePreview,
    _resolve_region,
    estimate_ram_bytes,
    human_bytes,
    meters_to_deg_lat,
    resolve_output,
)

# ============================================================
# ESA WorldCover source
# ============================================================
# Public, no-auth Cloud-Optimized GeoTIFFs. 3x3 degree tiles named by SW corner.
WORLDCOVER_VERSION = "v200"
WORLDCOVER_YEAR = "2021"
_WC_URL = (
    "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
    "{ver}/{year}/map/ESA_WorldCover_10m_{year}_{ver}_{tile}_Map.tif"
)
_WC_TILE_DEG = 3
WC_NODATA = np.uint8(0)

WORLDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse veg.",
    70: "Snow and ice",
    80: "Permanent water",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}
# Official ESA WorldCover colours.
WORLDCOVER_COLORS = {
    10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff",
    50: "#fa0000", 60: "#b4b4b4", 70: "#f0f0f0", 80: "#0064c8",
    90: "#0096a0", 95: "#00cf75", 100: "#fae6a0",
}


# ============================================================
# Tile enumeration (3x3 degree WorldCover grid)
# ============================================================
def _wc_tile_name(lat0: int, lon0: int) -> str:
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


def _wc_tiles_for_bbox(bbox, mask_geom=None) -> list[Tuple[int, int]]:
    """SW corners (lat0, lon0) of WorldCover 3x3 tiles covering the bbox."""
    lon_min, lat_min, lon_max, lat_max = bbox
    d = _WC_TILE_DEG

    def _floor_to(v):
        return int(math.floor(v / d) * d)

    tiles = []
    for lat0 in range(_floor_to(lat_min), _floor_to(lat_max) + 1, d):
        for lon0 in range(_floor_to(lon_min), _floor_to(lon_max) + 1, d):
            if mask_geom is not None:
                if not mask_geom.intersects(box(lon0, lat0, lon0 + d, lat0 + d)):
                    continue
            tiles.append((lat0, lon0))
    return tiles


# ============================================================
# Destination grid
# ============================================================
def _dest_grid(region_bbox, res_deg, like_path):
    """Return (transform, width, height) for the output.

    If ``like_path`` is given, copy its grid exactly so the clutter map aligns
    pixel-for-pixel with that raster (typically the terrain DEM).
    """
    if like_path:
        with rasterio.open(like_path) as ds:
            return ds.transform, ds.width, ds.height
    lon_min, lat_min, lon_max, lat_max = region_bbox
    width = max(1, int(round((lon_max - lon_min) / res_deg)))
    height = max(1, int(round((lat_max - lat_min) / res_deg)))
    transform = from_origin(lon_min, lat_max, res_deg, res_deg)
    return transform, width, height


# ============================================================
# Matplotlib legend / colormap for the categorical preview
# ============================================================
def _clutter_style():
    """Build (cmap, norm, legend_handles) for WorldCover classes."""
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch

    codes = sorted(WORLDCOVER_CLASSES)
    colors = [WORLDCOVER_COLORS[c] for c in codes]
    cmap = ListedColormap(colors)
    # Boundaries midway between (non-uniform) class codes.
    bounds = [codes[0] - 1]
    for a, b in zip(codes[:-1], codes[1:]):
        bounds.append((a + b) / 2.0)
    bounds.append(codes[-1] + 1)
    norm = BoundaryNorm(bounds, cmap.N)
    legend = [Patch(facecolor=WORLDCOVER_COLORS[c], edgecolor="k",
                    label=f"{c} {WORLDCOVER_CLASSES[c]}") for c in codes]
    return cmap, norm, legend


# ============================================================
# Main entry point
# ============================================================
def download_clutter(
    *,
    country: Optional[str] = None,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    resolution_m: float = 100.0,
    out_path: str = "clutter.tif",
    like_path: Optional[str] = None,
    mask_to_country: bool = True,
    as_cog: bool = True,
    live_preview: bool = False,
    preview_res_m: Optional[float] = None,
    preview_png: Optional[str] = None,
    preview_block: bool = True,
    verbose: bool = True,
) -> Path:
    """Build a WorldCover land-cover ("clutter") GeoTIFF for SHARC.

    Parameters mirror :func:`download_terrain`. ``like_path`` copies the grid of
    an existing raster (the terrain DEM) so both maps line up exactly; when
    given, ``resolution_m``/``bbox`` are only used to pick source tiles.
    Resampling is always nearest-neighbour (categorical data).
    """
    from rasterio.features import geometry_mask

    mask_geom, region_bbox = _resolve_region(country, bbox)
    res_deg = meters_to_deg_lat(resolution_m)
    transform, width, height = _dest_grid(region_bbox, res_deg, like_path)
    tiles = _wc_tiles_for_bbox(region_bbox, mask_geom)
    if not tiles:
        raise RuntimeError("No WorldCover tiles intersect the requested region.")

    label = country or f"bbox {region_bbox}"
    if verbose:
        print(f"[real_clutter] Region: {label}")
        print(f"[real_clutter] Grid: {width} x {height} px "
              f"({'from ' + str(like_path) if like_path else f'{resolution_m:g} m'})")
        print(f"[real_clutter] WorldCover tiles: {len(tiles)}")
        # Reads are windowed COG overviews (not full 10 m tiles). Order of the
        # data touched ~ the output grid; compression makes actual transfer less.
        print(f"[real_clutter] Estimated read: ~{human_bytes(width * height)} "
              "worst case (windowed COG, usually much less over the network).")

    # Optional live preview (categorical colours + legend).
    preview = None
    if live_preview:
        preview_res_deg = meters_to_deg_lat(preview_res_m or resolution_m)
        lon_span = region_bbox[2] - region_bbox[0]
        lat_span = region_bbox[3] - region_bbox[1]
        max_dim = max(lon_span, lat_span) / preview_res_deg
        if max_dim > PREVIEW_MAX_PX:
            preview_res_deg *= max_dim / PREVIEW_MAX_PX
        cmap, norm, legend = _clutter_style()
        preview = _LivePreview.create(
            region_bbox, preview_res_deg, mask_geom,
            f"real_clutter (WorldCover) | {label}", verbose,
            cmap=cmap, norm=norm, nodata=WC_NODATA, dtype=np.uint8,
            legend=legend, resampling=Resampling.nearest)

    dst = np.full((height, width), WC_NODATA, dtype=np.uint8)
    ok = fail = 0
    full_win = Window(0, 0, width, height)
    for lat0, lon0 in tqdm(tiles, desc="clutter tiles", disable=not verbose):
        url = _WC_URL.format(ver=WORLDCOVER_VERSION, year=WORLDCOVER_YEAR,
                             tile=_wc_tile_name(lat0, lon0))
        # Destination window covering just this 3x3 tile (intersected with grid),
        # so we never allocate/reproject the whole country per tile.
        tb = (max(lon0, region_bbox[0]), max(lat0, region_bbox[1]),
              min(lon0 + _WC_TILE_DEG, region_bbox[2]),
              min(lat0 + _WC_TILE_DEG, region_bbox[3]))
        if tb[0] >= tb[2] or tb[1] >= tb[3]:
            continue
        try:
            win = from_bounds(*tb, transform=transform)
            win = win.round_offsets().round_lengths().intersection(full_win)
            h_, w_ = int(win.height), int(win.width)
            if h_ <= 0 or w_ <= 0:
                continue
            r0, c0 = int(win.row_off), int(win.col_off)
            sub_transform = win_transform(win, transform)
            with rasterio.open(url) as src:
                tmp = np.full((h_, w_), WC_NODATA, dtype=np.uint8)
                reproject(
                    source=rasterio.band(src, 1), destination=tmp,
                    dst_transform=sub_transform, dst_crs="EPSG:4326",
                    src_nodata=0, dst_nodata=0,
                    resampling=Resampling.nearest,
                )
                m = tmp != WC_NODATA
                dst[r0:r0 + h_, c0:c0 + w_][m] = tmp[m]
                ok += 1
                if preview is not None:
                    preview.paste_full(rasterio.band(src, 1))
                    preview.redraw()
        except Exception as exc:
            fail += 1
            if verbose:
                print(f"[real_clutter]   tile {_wc_tile_name(lat0, lon0)} "
                      f"skipped ({exc}).")

    if ok == 0:
        raise RuntimeError("Could not read any WorldCover tile for the region.")
    if verbose:
        print(f"[real_clutter] Read {ok} tiles ({fail} failed). Writing...")

    if mask_to_country and mask_geom is not None:
        outside = geometry_mask([mask_geom.__geo_interface__],
                                out_shape=(height, width), transform=transform,
                                invert=False)
        dst[outside] = WC_NODATA

    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 1,
        "dtype": "uint8", "crs": "EPSG:4326", "transform": transform,
        "nodata": float(WC_NODATA), "compress": "LZW",
        "tiled": True, "blockxsize": 256, "blockysize": 256,
    }
    if as_cog:
        profile["driver"] = "COG"
        for k in ("tiled", "blockxsize", "blockysize"):
            profile.pop(k, None)

    out_path = resolve_output(out_path)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(dst, 1)
        try:
            ds.write_colormap(1, {c: tuple(int(WORLDCOVER_COLORS[c][i:i + 2], 16)
                                           for i in (1, 3, 5)) + (255,)
                                  for c in WORLDCOVER_CLASSES})
        except Exception:
            pass

    if verbose:
        size = out_path.stat().st_size
        ram = estimate_ram_bytes(width, height, np.uint8)
        print(f"[real_clutter] Wrote {out_path}")
        print(f"[real_clutter]   file : {human_bytes(size)} on disk")
        print(f"[real_clutter]   RAM  : ~{human_bytes(ram)} to load full array "
              "(uint8).")

    if preview is not None:
        preview.finalize(preview_png, verbose=verbose, block=preview_block)

    return out_path


# ============================================================
# CLI
# ============================================================
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download ESA WorldCover land-cover (clutter) into a GeoTIFF "
                    "for SHARC.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--country", type=str, help="Country name (Natural Earth).")
    g.add_argument("--bbox", type=float, nargs=4,
                   metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
                   help="Bounding rectangle in degrees.")
    p.add_argument("--resolution", type=float, default=100.0,
                   help="Output resolution in metres. Default 100.")
    p.add_argument("--out", type=str, default="clutter.tif",
                   help="Output GeoTIFF path.")
    p.add_argument("--like", type=str, default=None,
                   help="Copy the grid of this raster (e.g. the terrain DEM).")
    p.add_argument("--no-mask", action="store_true",
                   help="Do not mask outside the country polygon.")
    p.add_argument("--no-cog", action="store_true",
                   help="Write a plain tiled GeoTIFF instead of a COG.")
    p.add_argument("--live-preview", action="store_true",
                   help="Show a real-time land-cover preview.")
    p.add_argument("--preview-res", type=float, default=None)
    p.add_argument("--preview-png", type=str, default=None)
    return p


def main(argv=None) -> None:
    args = _build_parser().parse_args(argv)
    download_clutter(
        country=args.country,
        bbox=tuple(args.bbox) if args.bbox else None,
        resolution_m=args.resolution,
        out_path=args.out,
        like_path=args.like,
        mask_to_country=not args.no_mask,
        as_cog=not args.no_cog,
        live_preview=args.live_preview,
        preview_res_m=args.preview_res,
        preview_png=args.preview_png,
        verbose=True,
    )


if __name__ == "__main__":
    main()
