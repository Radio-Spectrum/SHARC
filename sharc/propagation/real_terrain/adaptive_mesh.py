# -*- coding: utf-8 -*-
"""
Adaptive-resolution terrain mesh for SHARC.

Takes the uniform terrain DEM and clutter (land-cover) GeoTIFFs produced by
:mod:`download_terrain` / :mod:`download_clutter` (same grid) and builds a
*variable-resolution* mesh of sample points: dense in built-up (urban) areas,
sparser in suburban zones, and coarse over natural land (forest / cropland /
etc.). The mesh is a genuinely irregular sampling, so it is stored as a **vector
file** (GeoPackage by default, GeoJSON optional) -- a single GeoTIFF cannot hold
variable cell sizes.

Three clutter tiers drive the resolution, defined by **urban density** (fraction
of built-up pixels in a moving window):
    * urban    (density >= dens_high)              -> fine   (e.g. 30 m)
    * suburban (dens_low <= density < dens_high)   -> medium (e.g. 150 m)
    * rural    (everything else)                   -> coarse (e.g. 500 m)

Sampling is a nested decimation of the fine terrain grid (quadtree-like), so
tiers share nodes and transition cleanly. Each node stores elevation, clutter
class, tier and its nominal resolution.

Example
-------
    from sharc.propagation.real_terrain.adaptive_mesh import build_adaptive_mesh
    build_adaptive_mesh("terrain.tif", "clutter.tif", out_path="mesh.gpkg")

Requires: numpy, rasterio, scipy, geopandas, shapely.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.transform import xy as _rowcol_to_xy
from scipy.ndimage import uniform_filter

from sharc.propagation.real_terrain.download_terrain import (
    NODATA_I16,
    _METERS_PER_DEG_LAT,
    human_bytes,
    resolve_output,
)

# ESA WorldCover built-up class and permanent-water class.
_BUILTUP_CLASS = 50
_WATER_CLASS = 80

# Tier codes.
TIER_URBAN, TIER_SUBURBAN, TIER_RURAL, TIER_NONE = 1, 2, 3, 0
TIER_NAMES = {TIER_URBAN: "urban", TIER_SUBURBAN: "suburban", TIER_RURAL: "rural"}
TIER_COLORS = {TIER_URBAN: "#d7191c", TIER_SUBURBAN: "#fdae61",
               TIER_RURAL: "#1a9641"}

DEFAULT_MESH_RES_M = {"urban": 30.0, "suburban": 150.0, "rural": 500.0}


# ============================================================
# Tier classification
# ============================================================
def classify_tiers(clutter, terrain, px_size_m, *, urban_window_m=1000.0,
                   dens_high=0.5, dens_low=0.1, mesh_water="exclude"):
    """Return a uint8 tier map (1 urban, 2 suburban, 3 rural, 0 none)."""
    builtup = (clutter == _BUILTUP_CLASS).astype(np.float32)
    win_px = max(1, int(round(urban_window_m / px_size_m)))
    density = uniform_filter(builtup, size=win_px, mode="constant")

    tier = np.full(clutter.shape, TIER_RURAL, dtype=np.uint8)
    tier[density >= dens_low] = TIER_SUBURBAN
    tier[density >= dens_high] = TIER_URBAN

    # Drop nodata / outside-region / no-terrain cells.
    tier[clutter == 0] = TIER_NONE
    tier[terrain == NODATA_I16] = TIER_NONE
    if mesh_water == "exclude":
        tier[clutter == _WATER_CLASS] = TIER_NONE
    return tier


# ============================================================
# Node estimate (before generating)
# ============================================================
def _steps_px(px_size_m, mesh_res_m):
    return {
        TIER_URBAN: max(1, int(round(mesh_res_m["urban"] / px_size_m))),
        TIER_SUBURBAN: max(1, int(round(mesh_res_m["suburban"] / px_size_m))),
        TIER_RURAL: max(1, int(round(mesh_res_m["rural"] / px_size_m))),
    }


def estimate_nodes(tier, steps):
    """Approximate node count from tier pixel counts and per-tier steps."""
    total = 0
    per_tier = {}
    for t, step in steps.items():
        px = int(np.count_nonzero(tier == t))
        n = px // (step * step)
        per_tier[TIER_NAMES[t]] = n
        total += n
    return total, per_tier


# ============================================================
# Main entry point
# ============================================================
def build_adaptive_mesh(
    terrain_path: str,
    clutter_path: str,
    *,
    out_path: str = "mesh.gpkg",
    mesh_format: str = "gpkg",
    mesh_res_m: Optional[dict] = None,
    urban_window_m: float = 1000.0,
    dens_high: float = 0.5,
    dens_low: float = 0.1,
    mesh_water: str = "exclude",
    tier_out_path: Optional[str] = None,
    live_preview: bool = False,
    preview_png: Optional[str] = None,
    preview_block: bool = True,
    verbose: bool = True,
) -> Path:
    """Build an adaptive-resolution terrain mesh and save it as a vector file.

    Parameters
    ----------
    terrain_path, clutter_path : str
        The uniform DEM and clutter GeoTIFFs (must share the same grid).
    out_path : str, default "mesh.gpkg"
        Output vector path (resolved under the module data/ dir if relative).
    mesh_format : {"gpkg", "geojson"}
        Vector driver. GeoPackage is compact + indexed; GeoJSON is portable.
    mesh_res_m : dict, optional
        {"urban":30, "suburban":150, "rural":500} nominal spacings in metres.
    urban_window_m, dens_high, dens_low :
        Urban-density moving-window size and the two tier thresholds.
    mesh_water : {"exclude", "coarse"}
        Whether permanent water gets no nodes or coarse (rural) nodes.
    tier_out_path : str, optional
        If given, also write the tier map as a uint8 GeoTIFF (for QA).
    """
    mesh_res_m = {**DEFAULT_MESH_RES_M, **(mesh_res_m or {})}

    with rasterio.open(terrain_path) as ds:
        terrain = ds.read(1)
        transform = ds.transform
        crs = ds.crs
    with rasterio.open(clutter_path) as ds:
        clutter = ds.read(1)
    if clutter.shape != terrain.shape:
        raise ValueError(
            f"Terrain {terrain.shape} and clutter {clutter.shape} grids differ; "
            "build clutter with like_path=<terrain> so they align.")

    # Pixel size in metres (latitude-based; adequate for mesh spacing).
    px_size_m = abs(transform.a) * _METERS_PER_DEG_LAT
    if verbose:
        print(f"[real_mesh] Grid {terrain.shape[1]}x{terrain.shape[0]} "
              f"@ ~{px_size_m:.0f} m/px")

    tier = classify_tiers(
        clutter, terrain, px_size_m, urban_window_m=urban_window_m,
        dens_high=dens_high, dens_low=dens_low, mesh_water=mesh_water)
    steps = _steps_px(px_size_m, mesh_res_m)

    total, per_tier = estimate_nodes(tier, steps)
    if verbose:
        print(f"[real_mesh] Tiers (px steps): urban={steps[TIER_URBAN]}, "
              f"suburban={steps[TIER_SUBURBAN]}, rural={steps[TIER_RURAL]}")
        print(f"[real_mesh] Estimated nodes: {total:,} {per_tier}")
        print(f"[real_mesh]   (approx file: {human_bytes(total * 135)} GPKG / "
              f"{human_bytes(total * 200)} GeoJSON)")

    # Nested decimation: keep pixel (r,c) if it belongs to tier t and sits on
    # that tier's sub-grid. Broadcasting avoids a full meshgrid.
    H, W = tier.shape
    row_idx = np.arange(H)[:, None]
    col_idx = np.arange(W)[None, :]
    keep = np.zeros((H, W), dtype=bool)
    for t, step in steps.items():
        keep |= ((tier == t)
                 & (row_idx % step == 0) & (col_idx % step == 0))
    ys, xs = np.nonzero(keep)
    if ys.size == 0:
        raise RuntimeError("Adaptive mesh is empty (no valid land nodes).")

    node_tier = tier[ys, xs]
    node_elev = terrain[ys, xs].astype(np.int16)
    node_clut = clutter[ys, xs].astype(np.uint8)
    tier_res = np.array([mesh_res_m["urban"], mesh_res_m["suburban"],
                         mesh_res_m["rural"]])
    node_res = tier_res[node_tier - 1].astype(np.float32)

    # Pixel-centre geographic coordinates.
    lon, lat = _rowcol_to_xy(transform, ys, xs, offset="center")
    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)

    if verbose:
        print(f"[real_mesh] Generated {ys.size:,} nodes.")

    _write_vector(lon, lat, node_elev, node_clut, node_tier, node_res,
                  crs, out_path, mesh_format, verbose)

    if tier_out_path is not None:
        _write_tier_raster(tier, transform, crs, tier_out_path, verbose)

    if live_preview:
        _preview_mesh(lon, lat, node_tier, ys, xs, out_path, preview_png,
                      preview_block, verbose)

    return resolve_output(out_path)


# ============================================================
# Writers
# ============================================================
def _write_vector(lon, lat, elev, clut, tier, res, crs, out_path,
                  mesh_format, verbose):
    import geopandas as gpd

    out_path = resolve_output(out_path)
    gdf = gpd.GeoDataFrame(
        {
            "elev_m": elev,
            "clutter": clut,
            "tier": tier,
            "tier_name": [TIER_NAMES.get(int(t), "?") for t in tier],
            "res_m": res,
        },
        geometry=gpd.points_from_xy(lon, lat),
        crs=crs or "EPSG:4326",
    )
    driver = "GPKG" if mesh_format.lower() == "gpkg" else "GeoJSON"
    gdf.to_file(out_path, driver=driver)
    if verbose:
        size = out_path.stat().st_size
        print(f"[real_mesh] Wrote {out_path} ({driver}, {human_bytes(size)}).")


def _write_tier_raster(tier, transform, crs, tier_out_path, verbose):
    tier_out_path = resolve_output(tier_out_path)
    profile = {
        "driver": "GTiff", "height": tier.shape[0], "width": tier.shape[1],
        "count": 1, "dtype": "uint8", "crs": crs or "EPSG:4326",
        "transform": transform, "nodata": 0, "compress": "LZW",
        "tiled": True, "blockxsize": 256, "blockysize": 256,
    }
    with rasterio.open(tier_out_path, "w", **profile) as ds:
        ds.write(tier, 1)
    if verbose:
        print(f"[real_mesh] Wrote tier map {tier_out_path}.")


# ============================================================
# Preview (scatter coloured by tier)
# ============================================================
def _preview_mesh(lon, lat, tier, ys, xs, title_src, preview_png, block,
                  verbose, max_points=120000):
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except Exception as exc:  # pragma: no cover
        if verbose:
            print(f"[real_mesh] Preview disabled ({exc}).")
        return

    # Subsample by a SPATIAL stride on the pixel indices so the display keeps a
    # regular sub-lattice (and the urban/rural density contrast), instead of the
    # scrambled look an index-strided sample would give.
    n = lon.size
    if n > max_points:
        s = int(np.ceil(np.sqrt(n / max_points)))
        keep = (ys % s == 0) & (xs % s == 0)
        lon, lat, tier = lon[keep], lat[keep], tier[keep]
        if verbose:
            print(f"[real_mesh] Preview shows {lon.size:,}/{n:,} nodes "
                  f"(spatial stride {s}px, lattice preserved).")

    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = np.array([TIER_COLORS.get(int(t), "#999999") for t in tier])
    ax.scatter(lon, lat, s=1.5, c=colors, linewidths=0)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"adaptive mesh | {Path(str(title_src)).name}")
    ax.legend(handles=[Patch(color=TIER_COLORS[t], label=TIER_NAMES[t])
                       for t in (TIER_URBAN, TIER_SUBURBAN, TIER_RURAL)],
              loc="center left", bbox_to_anchor=(1.01, 0.5))
    fig.tight_layout()
    if preview_png:
        fig.savefig(preview_png, dpi=180)
        if verbose:
            print(f"[real_mesh] Saved preview PNG: {preview_png}")
    if block:
        plt.ioff()
        try:
            plt.show(block=True)
        except Exception:
            pass
    else:
        plt.pause(0.1)


# ============================================================
# CLI
# ============================================================
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build an adaptive-resolution terrain mesh (vector) from a "
                    "terrain DEM + clutter GeoTIFF.")
    p.add_argument("terrain", help="Terrain DEM GeoTIFF.")
    p.add_argument("clutter", help="Clutter GeoTIFF (same grid).")
    p.add_argument("--out", default="mesh.gpkg", help="Output vector path.")
    p.add_argument("--format", choices=["gpkg", "geojson"], default="gpkg")
    p.add_argument("--urban-res", type=float, default=30.0)
    p.add_argument("--suburban-res", type=float, default=150.0)
    p.add_argument("--rural-res", type=float, default=500.0)
    p.add_argument("--window", type=float, default=1000.0,
                   help="Urban-density window in metres.")
    p.add_argument("--dens-high", type=float, default=0.5)
    p.add_argument("--dens-low", type=float, default=0.1)
    p.add_argument("--water", choices=["exclude", "coarse"], default="exclude")
    p.add_argument("--tier-out", default=None, help="Also write a tier GeoTIFF.")
    p.add_argument("--live-preview", action="store_true")
    p.add_argument("--preview-png", default=None)
    return p


def main(argv=None) -> None:
    a = _build_parser().parse_args(argv)
    build_adaptive_mesh(
        a.terrain, a.clutter, out_path=a.out, mesh_format=a.format,
        mesh_res_m={"urban": a.urban_res, "suburban": a.suburban_res,
                    "rural": a.rural_res},
        urban_window_m=a.window, dens_high=a.dens_high, dens_low=a.dens_low,
        mesh_water=a.water, tier_out_path=a.tier_out,
        live_preview=a.live_preview, preview_png=a.preview_png, verbose=True,
    )


if __name__ == "__main__":
    main()
