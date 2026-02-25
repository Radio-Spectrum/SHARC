#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import math
import gzip
import requests
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt

from tqdm import tqdm
from shapely.geometry import box
from concurrent.futures import ThreadPoolExecutor, as_completed

import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling

# ============================================================
# CONFIG
# ============================================================
OUT_DIR = "sharc/terrain_tests/global_dem"
TILES_RAW_DIR = os.path.join(OUT_DIR, "tiles_raw_hgt")       # .hgt (raw)
TILES_250_DIR = os.path.join(OUT_DIR, "tiles_250m_tif")      # GeoTIFF 250m por tile
PREVIEW_PNG = os.path.join(OUT_DIR, "preview_2km_final.png")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(TILES_RAW_DIR, exist_ok=True)
os.makedirs(TILES_250_DIR, exist_ok=True)

BASE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/"

LAT_MIN, LAT_MAX = -60, 80
LON_MIN, LON_MAX = -180, 180

# preview em tempo real (2 km)
RES_PREVIEW_KM = 1.0

# saída por tile (250 m)
RES_OUT_M = 250.0

MAX_WORKERS = 16          # aumente se sua internet aguentar
PLOT_EVERY_N = 1000         # atualiza a tela a cada N tiles prontos

NODATA_I16 = np.int16(-32768)

# ============================================================
# HELPERS: graus por metro (aprox)
# ============================================================
def meters_to_deg_lat(m: float) -> float:
    return m / 111_320.0

def km_to_deg_lat(km: float) -> float:
    return (km * 1000.0) / 111_320.0

# ============================================================
# LAND MASK (Natural Earth)
# ============================================================
print("Loading land mask (Natural Earth)...")
world = gpd.read_file("https://naturalearth.s3.amazonaws.com/110m_physical/ne_110m_land.zip")
land_union = world.geometry.union_all()

def tile_over_land(lat0: int, lon0: int) -> bool:
    return land_union.intersects(box(lon0, lat0, lon0 + 1, lat0 + 1))

# ============================================================
# TILE NAME (Skadi): N10/N10W060.hgt.gz
# ============================================================
def tile_tiff_name(lat0, lon0):
    return f"tile_{lat0:+03d}_{lon0:+04d}_250m.tif".replace("+","p").replace("-","m")

def tile_name(lat0: int, lon0: int):
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    folder = f"{ns}{abs(lat0):02d}"
    file = f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}.hgt.gz"
    return folder, file

# ============================================================
# DOWNLOAD + UNZIP (.hgt)
# ============================================================
def download_tile_hgt(lat0: int, lon0: int):
    folder, file_gz = tile_name(lat0, lon0)

    gz_path = os.path.join(TILES_RAW_DIR, file_gz)
    hgt_path = gz_path.replace(".gz", "")

    url = BASE_URL + f"{folder}/{file_gz}"

    try:
        r = requests.get(url, stream=True, timeout=180)
        if r.status_code != 200:
            return None

        tmp = gz_path + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)
        os.replace(tmp, gz_path)

        with gzip.open(gz_path, "rb") as f_in:
            raw = f_in.read()

        with open(hgt_path + ".part", "wb") as f_out:
            f_out.write(raw)
        os.replace(hgt_path + ".part", hgt_path)

        return hgt_path, gz_path

    except Exception:
        return None

# ============================================================
# READ HGT -> array + transform (EPSG:4326)
# ============================================================
def read_hgt(path_hgt: str, lat0: int, lon0: int):
    nbytes = os.path.getsize(path_hgt)
    nvals = nbytes // 2
    n = int(round(math.sqrt(nvals)))
    if n * n != nvals:
        raise ValueError(f"HGT size not square: {path_hgt} (vals={nvals})")

    arr = np.fromfile(path_hgt, dtype=">i2").reshape((n, n)).astype(np.int16, copy=False)

    # inclui endpoints -> passo = 1/(n-1)
    src_res_deg = 1.0 / (n - 1)
    src_transform = from_origin(lon0, lat0 + 1.0, src_res_deg, src_res_deg)

    return arr, src_transform, src_res_deg

# ============================================================
# WRITE 250m GeoTIFF tile
# ============================================================
def write_tile_250m(lat0: int, lon0: int, src_arr: np.ndarray, src_transform, src_res_deg: float):
    out_name = f"tile_{lat0:+03d}_{lon0:+04d}_250m.tif".replace("+", "p").replace("-", "m")
    out_path = os.path.join(TILES_250_DIR, out_name)

    if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
        return out_path

    target_res_deg = meters_to_deg_lat(RES_OUT_M)

    # fator (src_res_deg ~ 0.000277..., target_res_deg ~ 0.002245...) => downsample
    scale = target_res_deg / src_res_deg
    out_h = max(2, int(round(src_arr.shape[0] / scale)))
    out_w = max(2, int(round(src_arr.shape[1] / scale)))

    dst = np.full((out_h, out_w), NODATA_I16, dtype=np.int16)
    dst_transform = from_origin(lon0, lat0 + 1.0, target_res_deg, target_res_deg)

    reproject(
        source=src_arr,
        destination=dst,
        src_transform=src_transform,
        src_crs="EPSG:4326",
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        src_nodata=NODATA_I16,
        dst_nodata=NODATA_I16,
        resampling=Resampling.average
    )

    profile = {
        "driver": "GTiff",
        "height": dst.shape[0],
        "width": dst.shape[1],
        "count": 1,
        "dtype": "int16",
        "crs": "EPSG:4326",
        "transform": dst_transform,
        "nodata": NODATA_I16,
        "compress": "LZW",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "predictor": 2,
    }

    with rasterio.open(out_path, "w", **profile) as ds_out:
        ds_out.write(dst, 1)

    return out_path

# ============================================================
# PREVIEW MOSAIC 2km (buffer em RAM)
# ============================================================
preview_res_deg = km_to_deg_lat(RES_PREVIEW_KM)

preview_width = int(round((LON_MAX - LON_MIN) / preview_res_deg))
preview_height = int(round((LAT_MAX - LAT_MIN) / preview_res_deg))

preview_transform_global = from_origin(LON_MIN, LAT_MAX, preview_res_deg, preview_res_deg)
preview_buffer = np.full((preview_height, preview_width), NODATA_I16, dtype=np.int16)

def preview_window_indices(lat0: int, lon0: int):
    """
    Calcula o retângulo do tile (1°x1°) no grid do preview global.
    """
    # linhas aumentam para baixo; topo é LAT_MAX
    r0 = int(np.floor((LAT_MAX - (lat0 + 1.0)) / preview_res_deg))
    r1 = int(np.ceil ((LAT_MAX - (lat0 + 0.0)) / preview_res_deg))
    c0 = int(np.floor(((lon0 + 0.0) - LON_MIN) / preview_res_deg))
    c1 = int(np.ceil (((lon0 + 1.0) - LON_MIN) / preview_res_deg))

    r0 = max(0, min(preview_height, r0))
    r1 = max(0, min(preview_height, r1))
    c0 = max(0, min(preview_width, c0))
    c1 = max(0, min(preview_width, c1))
    return r0, r1, c0, c1

def make_preview_patch(lat0: int, lon0: int, src_arr: np.ndarray, src_transform):
    """
    Gera somente o patch do preview (2km) correspondente a esse tile,
    para o thread principal colar no buffer global.
    """
    r0, r1, c0, c1 = preview_window_indices(lat0, lon0)
    ph = max(1, r1 - r0)
    pw = max(1, c1 - c0)

    patch = np.full((ph, pw), NODATA_I16, dtype=np.int16)

    # transform do patch: canto superior esquerdo em lon = LON_MIN + c0*res, lat = LAT_MAX - r0*res
    patch_lon0 = LON_MIN + c0 * preview_res_deg
    patch_lat1 = LAT_MAX - r0 * preview_res_deg
    patch_transform = from_origin(patch_lon0, patch_lat1, preview_res_deg, preview_res_deg)

    reproject(
        source=src_arr,
        destination=patch,
        src_transform=src_transform,
        src_crs="EPSG:4326",
        dst_transform=patch_transform,
        dst_crs="EPSG:4326",
        src_nodata=NODATA_I16,
        dst_nodata=NODATA_I16,
        resampling=Resampling.average
    )

    return (r0, r1, c0, c1, patch)

# ============================================================
# BUILD TILE LIST (somente terra)
# ============================================================
print("Building tile list (land only)...")
tiles = []
for lat0 in range(LAT_MIN, LAT_MAX):
    for lon0 in range(LON_MIN, LON_MAX):
        if tile_over_land(lat0, lon0):
            tiles.append((lat0, lon0))
print("Tiles over land:", len(tiles))

# ============================================================
# WORKER: tudo pesado em paralelo
# ============================================================
def worker_full(lat0: int, lon0: int):

    # ⭐ cache check baseado no TIFF
    tiff_name = tile_tiff_name(lat0, lon0)
    tiff_path = os.path.join(TILES_250_DIR, tiff_name)

    if os.path.exists(tiff_path) and os.path.getsize(tiff_path) > 10000:
        # já existe → só gera preview patch a partir do TIFF
        try:
            with rasterio.open(tiff_path) as ds:
                src_arr = ds.read(1)
                src_transform = ds.transform
            patch_info = make_preview_patch(lat0, lon0, src_arr, src_transform)
            return patch_info
        except Exception:
            pass

    # ⭐ precisa baixar HGT
    got = download_tile_hgt(lat0, lon0)
    if got is None:
        return None

    hgt_path, gz_path = got

    try:
        src_arr, src_transform, src_res_deg = read_hgt(hgt_path, lat0, lon0)

        # ⭐ gera TIFF 250m
        out_tiff = write_tile_250m(lat0, lon0, src_arr, src_transform, src_res_deg)

        # ⭐ gera preview patch
        patch_info = make_preview_patch(lat0, lon0, src_arr, src_transform)

        # ⭐ delete temporários
        try:
            if os.path.exists(hgt_path):
                os.remove(hgt_path)
        except Exception:
            pass

        try:
            if os.path.exists(gz_path):
                os.remove(gz_path)
        except Exception:
            pass

        return patch_info

    except Exception:
        # se deu erro, mantém temporários
        return None

# ============================================================
# PLOT SETUP
# ============================================================
plt.ion()
fig, ax = plt.subplots(figsize=(12, 6))
world.boundary.plot(ax=ax, color="black", linewidth=0.5)

ax.set_xlim(LON_MIN, LON_MAX)
ax.set_ylim(LAT_MIN, LAT_MAX)
ax.set_title(f"Preview mosaico em tempo real ({RES_PREVIEW_KM:.0f} km) | gerando tiles {int(RES_OUT_M)} m")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

masked = np.ma.masked_equal(preview_buffer, NODATA_I16)
im = ax.imshow(
    masked,
    extent=[LON_MIN, LON_MAX, LAT_MIN, LAT_MAX],
    origin="upper",
    cmap="terrain",
    vmin=0,
    vmax=3000,
    alpha=0.95
)
cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
cbar.set_label("Elevação (m)")

plt.draw()
plt.pause(0.01)

# ============================================================
# PARALLEL EXECUTION + REAL-TIME MOSAIC PREVIEW
# ============================================================
ok = 0
fail = 0

print("Running parallel pipeline (download + 250m tile + preview patch)...")
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futures = [ex.submit(worker_full, lat0, lon0) for (lat0, lon0) in tiles]

    for fut in tqdm(as_completed(futures), total=len(futures), desc="Tiles"):
        out = fut.result()
        if out is None:
            fail += 1
            continue

        r0, r1, c0, c1, patch = out

        # cola patch no buffer global (rápido) - main thread
        sub = preview_buffer[r0:r1, c0:c1]
        m = (patch != NODATA_I16)
        sub[m] = patch[m]
        preview_buffer[r0:r1, c0:c1] = sub

        ok += 1

        # atualiza plot (main thread)
        if ok % PLOT_EVERY_N == 0:
            masked = np.ma.masked_equal(preview_buffer, NODATA_I16)
            im.set_data(masked)
            fig.canvas.draw_idle()
            plt.pause(0.001)

print(f"Done. OK={ok}, FAIL={fail}")

# ============================================================
# FINAL PREVIEW SAVE
# ============================================================
masked = np.ma.masked_equal(preview_buffer, NODATA_I16)
im.set_data(masked)
fig.canvas.draw_idle()
plt.pause(0.1)

fig.savefig(PREVIEW_PNG, dpi=180)
print("Saved preview PNG:", PREVIEW_PNG)

plt.ioff()
plt.show(block=True)

print("\nTiles 250m gerados em:", TILES_250_DIR)
print("Sugestão: criar VRT para mosaico virtual (instantâneo):")
print(f'  gdalbuildvrt -overwrite "{os.path.join(OUT_DIR, "global_250m.vrt")}" "{TILES_250_DIR}\\*.tif"')