# real_terrain

Download real **terrain (DEM)** and **clutter (land cover)** for SHARC, build an
optional **adaptive-resolution mesh**, and read them back into memory. Terrain and
clutter share the same grid/resolution.

**Output location.** Generated maps are written to `data/` next to this module
(absolute path, git-ignored) unless you pass an absolute path. `RealTerrain(...)`
etc. read from wherever you point them. A bare filename like `"terrain.tif"`
resolves to `sharc/propagation/real_terrain/data/terrain.tif`.

Adapted from `sharc/terrain_tests/generate_terrain.py`. Source data is the public,
no-auth **AWS `elevation-tiles-prod`** dataset (Skadi / SRTM, 1 arc-second HGT tiles,
~30 m native over land). Tiles are downloaded, **resampled** to a chosen resolution
and **merged into a single GeoTIFF (COG)** per region.

## Pipeline

1. **Region** — a rectangle (`bbox`) *or* a country name (Natural Earth admin_0,
   already shipped in `sharc/topology/map/`). For a country, only tiles that
   intersect the polygon are downloaded, and cells outside it become `nodata`.
2. **Download** — 1°×1° HGT tiles fetched in parallel.
3. **Resample** — each tile to the target ground resolution (`--resolution`, metres).
   Downsampling uses averaging; upsampling uses bilinear.
4. **Merge + write** — cropped to the region, written as an `int16` LZW-compressed
   GeoTIFF (Cloud-Optimized when the COG driver is available).

## Just edit and run (CONFIG block)

The top of `download_terrain.py` has a `CONFIG` dict. Edit the values (region,
resolution, output, live preview...) and run the file with **no arguments** — it
uses `CONFIG` directly and, with `also_clutter=True`, builds **both** the terrain
DEM and a matching clutter map in one run:

```bash
python -m sharc.propagation.real_terrain.download_terrain
# or:  python sharc/propagation/real_terrain/download_terrain.py
```

Any command-line argument overrides the matching `CONFIG` value. The clutter map
is written on the exact same grid as the terrain (`like_path`), so the two align
pixel-for-pixel.

> **bbox order is `(LON_min, LAT_min, LON_max, LAT_max)` — longitude first.**
> e.g. Rio de Janeiro is `(-44.9, -23.3, -40.8, -21.5)`, not the other way round.

## Clutter / land cover (ESA WorldCover)

The clutter map comes from **ESA WorldCover 10 m** (public COGs on AWS, no auth),
read remotely (windowed) and resampled with **nearest neighbour** (categorical).
Classes: `10` Tree cover, `20` Shrubland, `30` Grassland, `40` Cropland, `50`
Built-up, `60` Bare/sparse, `70` Snow/ice, `80` Permanent water, `90` Herbaceous
wetland, `95` Mangroves, `100` Moss/lichen. Output is a `uint8` GeoTIFF with an
embedded colour table.

```bash
# Standalone, aligned to an existing terrain DEM
python -m sharc.propagation.real_terrain.download_clutter \
    --bbox -44.9 -23.3 -40.8 -21.5 --resolution 100 \
    --out rio_clutter.tif --like rio_terrain.tif --live-preview
```

```python
from sharc.propagation.real_terrain import download_clutter, RealClutter

download_clutter(bbox=(-44.9, -23.3, -40.8, -21.5), resolution_m=100.0,
                 out_path="rio_clutter.tif", like_path="rio_terrain.tif")

cl = RealClutter("rio_clutter.tif"); cl.load()
code = cl.clutter_class(-22.95, -43.2)     # e.g. 10
print(code, RealClutter.class_name(code))  # 10 Tree cover
```

## Download (CLI)

```bash
# By country, 1 km grid
python -m sharc.propagation.real_terrain.download_terrain \
    --country Brazil --resolution 1000 --out brazil_1km.tif

# By rectangle (lon_min lat_min lon_max lat_max), 200 m grid, with live preview
python -m sharc.propagation.real_terrain.download_terrain \
    --bbox -48.2 -16.0 -47.8 -15.6 --resolution 200 --out brasilia_200m.tif \
    --live-preview
```

Useful flags: `--no-mask` (keep the full bbox instead of clipping to the country
polygon), `--workers N` (download threads), `--no-cog` (plain tiled GeoTIFF),
`--live-preview` (real-time mosaic), `--preview-res M` / `--preview-every N` /
`--preview-png PATH`.

## Tile cache

Downloaded terrain tiles are cached (compressed `.hgt.gz`) in `tile_cache/` next
to this module, so a tile is **never downloaded twice** — re-runs (even at a
different resolution) reuse the cache. Each run prints how many tiles are already
present. Disable with `cache_dir=None`, or point elsewhere with `cache_dir=...`.
The folder is git-ignored. (Clutter is read remotely from the WorldCover COGs, so
it has no local tile cache.)

## Live preview

With `live_preview=True` (or `--live-preview`) a matplotlib window shows the
mosaic filling in tile-by-tile, already at the chosen resampling — like the old
`generate_terrain.py`. It runs on the main thread while tiles download in
parallel. Set `preview_res_m` coarser than the output to keep the preview light
for large regions, and `preview_png` to save the final image. Requires an
interactive matplotlib backend (a display); it is auto-disabled if none is
available.

When several maps are built in one run, earlier previews **stay open
(non-blocking)** and only the last one blocks, so terrain + clutter + mesh
previews appear together. Close the windows to finish. The `preview_block`
argument controls this per call.

## Adaptive-resolution mesh

`build_adaptive_mesh(terrain, clutter, ...)` turns the two uniform GeoTIFFs into a
**variable-resolution vector mesh** — dense sampling in cities, sparse over nature
— because a single GeoTIFF cannot store variable cell sizes.

Three tiers are set by **urban density** (fraction of built-up in a moving window):

| Tier     | Condition                          | Resolution (default) |
|----------|------------------------------------|----------------------|
| urban    | density ≥ `dens_high` (0.5)        | `urban` (30 m)       |
| suburban | `dens_low` (0.1) ≤ density < high  | `suburban` (150 m)   |
| rural    | everything else                    | `rural` (500 m)      |

Sampling is a nested decimation of the fine grid (quadtree-like) so tiers share
nodes. Each node stores `elev_m`, `clutter`, `tier`, `tier_name`, `res_m`. Output
is a **GeoPackage** (default, compact + indexed) or **GeoJSON**. Permanent water is
excluded by default (`mesh_water="coarse"` to keep sparse sea nodes). Pass
`tier_out_path` to also dump the tier map as a `uint8` GeoTIFF for QA/threshold
tuning. Enable it in the CONFIG block with `adaptive_mesh=True` (it builds clutter
automatically if needed).

```bash
# From existing terrain + clutter GeoTIFFs
python -m sharc.propagation.real_terrain.adaptive_mesh \
    data/terrain.tif data/clutter.tif --out mesh.gpkg \
    --urban-res 30 --suburban-res 150 --rural-res 500 --live-preview
```

```python
from sharc.propagation.real_terrain import build_adaptive_mesh, RealAdaptiveMesh

build_adaptive_mesh("terrain.tif", "clutter.tif", out_path="mesh.gpkg",
                    mesh_res_m={"urban": 30, "suburban": 150, "rural": 500})

mesh = RealAdaptiveMesh("mesh.gpkg")
h = mesh.elevation(-22.95, -43.2)                 # nearest node (fast)
h = mesh.elevation(-22.95, -43.2, method="linear")  # Delaunay (smoother)
d_km, h_m = mesh.elevation_profile(-22.9, -43.2, -22.8, -43.1, n=301)
```

> The mesh reader interpolates from scattered nodes (KDTree / Delaunay), which is
> heavier than a raster lookup — expected, since the mesh trades storage for
> node-count savings in the simulation.

## Download (Python)

```python
from sharc.propagation.real_terrain import download_terrain

download_terrain(country="Finland", resolution_m=250.0, out_path="finland_250m.tif")
download_terrain(bbox=(-48.2, -16.0, -47.8, -15.6), resolution_m=200.0,
                 out_path="brasilia_200m.tif")
```

## Read in SHARC

```python
from sharc.propagation.real_terrain import RealTerrain

dem = RealTerrain("brazil_1km.tif")
print(dem.estimate_ram())        # RAM to hold the full array, from metadata only
dem.load()                       # read the whole DEM into RAM (int16)

h = dem.elevation(-15.79, -47.88)                       # metres (bilinear)
d_km, h_m = dem.elevation_profile(-15.79, -47.88,       # terrain profile for
                                  -22.9, -43.2, n=301)   # e.g. P.452 diffraction
```

`elevation()` accepts scalars or arrays; points outside the raster or over
`nodata` return `NaN`.

## RAM estimate

The full array uses `width × height × 2 bytes` (`int16`). `estimate_ram()` reports
it without reading the data. `download_terrain(..., verbose=True)` prints it after
writing. Rough figures for a full-array load (windowed reads use far less):

| Region span        | 1 km grid | 250 m grid | 200 m grid |
|--------------------|-----------|------------|------------|
| 1°×1° (~110 km)    | ~0.02 MB  | ~0.4 MB    | ~0.6 MB    |
| 10°×10°            | ~2.5 MB   | ~40 MB     | ~62 MB     |
| Brazil (~39°×39°)  | ~38 MB    | ~0.6 GB    | ~0.9 GB    |
| Continental (~60°) | ~90 MB    | ~1.4 GB    | ~2.2 GB    |

Coarser resolution = smaller file and less RAM. For large countries at fine
resolutions, prefer a coarser grid or crop to the actual area of interest.
