"""Real terrain and land cover for the GUI: download, cache, overlays and sampling.

The heavy lifting is done by the engine's own tools
(`sharc/propagation/real_terrain/download_terrain.py` for SRTM elevation and
`download_clutter.py` for ESA WorldCover land cover). This module adds what a GUI needs:

* a cache keyed by region + resolution, so a region is downloaded once;
* a background job (`TerrainDownloadJob`) that reports progress without freezing the UI;
* overlays for the 3D preview: a coloured land-cover image, a hillshade image and a
  height-map file that Cesium turns into real 3D relief;
* ground-height sampling, so stations sit on the terrain.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QThread, Signal

# ESA WorldCover legend (class -> (name, RGB)).
WORLDCOVER = {
    10: ("Tree cover", (0, 100, 0)),
    20: ("Shrubland", (255, 187, 34)),
    30: ("Grassland", (255, 255, 76)),
    40: ("Cropland", (240, 150, 255)),
    50: ("Built-up", (250, 0, 0)),
    60: ("Bare / sparse vegetation", (180, 180, 180)),
    70: ("Snow and ice", (240, 240, 240)),
    80: ("Permanent water", (0, 100, 200)),
    90: ("Herbaceous wetland", (0, 150, 160)),
    95: ("Mangroves", (0, 207, 117)),
    100: ("Moss and lichen", (250, 230, 160)),
}

BBox = Tuple[float, float, float, float]   # lon_min, lat_min, lon_max, lat_max [deg]
HEIGHTMAP_SIZE = 513                        # samples per side of the 3D relief height-map


def cache_root() -> Path:
    """Folder that holds downloaded terrain (git-ignored, outside the package)."""
    from core.run_service import run_root
    root = run_root().parent / "terrain_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def bbox_around(lat: float, lon: float, radius_km: float) -> BBox:
    """Square region of half-side `radius_km` around a point."""
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(0.05, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def expand_bbox(bbox: BBox, margin_km: float) -> BBox:
    w, s, e, n = bbox
    lat = (s + n) / 2.0
    dlat = margin_km / 111.32
    dlon = margin_km / (111.32 * max(0.05, math.cos(math.radians(lat))))
    return (w - dlon, s - dlat, e + dlon, n + dlat)


def region_key(bbox: BBox, resolution_m: float) -> str:
    raw = json.dumps([round(v, 5) for v in bbox] + [round(float(resolution_m), 2)])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


@dataclass
class TerrainSet:
    """Files of one downloaded region."""
    folder: Path
    terrain: Path
    clutter: Path
    bbox: BBox
    resolution_m: float

    @property
    def ready(self) -> bool:
        return self.terrain.is_file() and self.clutter.is_file()


def terrain_set(bbox: BBox, resolution_m: float) -> TerrainSet:
    folder = cache_root() / region_key(bbox, resolution_m)
    return TerrainSet(folder, folder / "terrain.tif", folder / "clutter.tif", bbox, float(resolution_m))


class TerrainDownloadJob(QThread):
    """Downloads terrain and land cover for a region without blocking the GUI."""

    log = Signal(str)
    finished_ok = Signal(object)     # TerrainSet
    failed = Signal(str)

    def __init__(self, bbox: BBox, resolution_m: float, parent=None):
        super().__init__(parent)
        self.bbox, self.resolution_m = bbox, float(resolution_m)

    def run(self):  # noqa: D401 (Qt override)
        ts = terrain_set(self.bbox, self.resolution_m)
        try:
            if ts.ready:
                self.log.emit(f"[TERRAIN] Using cached data in {ts.folder}")
                self.finished_ok.emit(ts)
                return
            try:
                import requests  # noqa: F401
            except ImportError:
                self.failed.emit("The 'requests' package is required to download terrain: pip install requests tqdm")
                return
            from sharc.propagation.real_terrain.download_clutter import download_clutter
            from sharc.propagation.real_terrain.download_terrain import download_terrain
            ts.folder.mkdir(parents=True, exist_ok=True)
            w, s, e, n = self.bbox
            self.log.emit(f"[TERRAIN] Downloading SRTM elevation for lon {w:.3f}..{e:.3f}, lat {s:.3f}..{n:.3f} "
                          f"at {self.resolution_m:g} m")
            tp = download_terrain(bbox=self.bbox, resolution_m=self.resolution_m, out_path=str(ts.terrain),
                                  mask_to_country=False, as_cog=False, verbose=False)
            self.log.emit("[TERRAIN] Downloading ESA WorldCover land cover")
            download_clutter(bbox=self.bbox, resolution_m=self.resolution_m, out_path=str(ts.clutter),
                             like_path=str(tp), mask_to_country=False, as_cog=False, verbose=False)
            self.log.emit("[TERRAIN] Download finished")
            self.finished_ok.emit(ts)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Reading, summaries, sampling
# ---------------------------------------------------------------------------
def read_raster(path: Path):
    """Returns (array, (west, south, east, north)) with NaN for nodata."""
    import rasterio
    with rasterio.open(path) as r:
        a = r.read(1).astype("float64")
        nodata = r.nodata
        b = r.bounds
    if nodata is not None:
        a[a == nodata] = np.nan
    return a, (b.left, b.bottom, b.right, b.top)


def summarize(ts: TerrainSet) -> Dict[str, object]:
    elev, bounds = read_raster(ts.terrain)
    clut, _ = read_raster(ts.clutter)
    out: Dict[str, object] = {
        "size": f"{elev.shape[1]} x {elev.shape[0]}",
        "elev_min": float(np.nanmin(elev)), "elev_max": float(np.nanmax(elev)),
        "elev_mean": float(np.nanmean(elev)), "bounds": bounds,
    }
    classes = {}
    valid = clut[np.isfinite(clut)]
    for code, (name, _rgb) in WORLDCOVER.items():
        pct = 100.0 * float(np.sum(valid == code)) / max(1, valid.size)
        if pct > 0.05:
            classes[name] = pct
    out["classes"] = dict(sorted(classes.items(), key=lambda kv: -kv[1]))
    return out


def sample_ground(ts: TerrainSet, lat, lon) -> np.ndarray:
    """Ground height [m] at points (bilinear), 0 outside the raster."""
    elev, (w, s, e, n) = read_raster(ts.terrain)
    lat = np.atleast_1d(np.asarray(lat, float))
    lon = np.atleast_1d(np.asarray(lon, float))
    h, wd = elev.shape
    fx = (lon - w) / (e - w) * (wd - 1)
    fy = (n - lat) / (n - s) * (h - 1)
    inside = (fx >= 0) & (fx <= wd - 1) & (fy >= 0) & (fy <= h - 1)
    x0 = np.clip(np.floor(fx).astype(int), 0, wd - 2)
    y0 = np.clip(np.floor(fy).astype(int), 0, h - 2)
    tx, ty = fx - x0, fy - y0
    e00, e10 = elev[y0, x0], elev[y0, x0 + 1]
    e01, e11 = elev[y0 + 1, x0], elev[y0 + 1, x0 + 1]
    val = (e00 * (1 - tx) * (1 - ty) + e10 * tx * (1 - ty) + e01 * (1 - tx) * ty + e11 * tx * ty)
    return np.where(inside & np.isfinite(val), val, 0.0)


# ---------------------------------------------------------------------------
# Overlays for the 3D preview
# ---------------------------------------------------------------------------
def _save_png(rgba: np.ndarray, path: Path) -> None:
    from PySide6.QtGui import QImage
    h, w, _ = rgba.shape
    buf = np.ascontiguousarray(rgba, dtype=np.uint8)
    img = QImage(buf.data, w, h, 4 * w, QImage.Format_RGBA8888)
    img.copy().save(str(path), "PNG")


def hillshade(elev: np.ndarray, cell_m: float, azimuth: float = 315.0, altitude: float = 40.0,
              exaggeration: float = 2.0) -> np.ndarray:
    z = np.nan_to_num(elev, nan=float(np.nanmin(elev))) * exaggeration
    gy, gx = np.gradient(z, cell_m)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(360.0 - azimuth + 90.0), np.radians(altitude)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0.0, 1.0)


def build_overlays(ts: TerrainSet) -> Dict[str, object]:
    """Writes clutter.png, hillshade.png and heightmap.bin next to the rasters; returns metadata."""
    elev, bounds = read_raster(ts.terrain)
    clut, _ = read_raster(ts.clutter)
    w, s, e, n = bounds
    h_px, w_px = elev.shape
    cell_m = max(1.0, (e - w) * 111320.0 * math.cos(math.radians((s + n) / 2)) / max(1, w_px))

    # land cover (RGBA, transparent where unknown)
    rgba = np.zeros((h_px, w_px, 4), dtype=np.uint8)
    for code, (_name, rgb) in WORLDCOVER.items():
        m = clut == code
        rgba[m, 0], rgba[m, 1], rgba[m, 2], rgba[m, 3] = rgb[0], rgb[1], rgb[2], 255
    _save_png(rgba, ts.folder / "clutter.png")

    # hillshade, tinted by elevation (dark base, light from NW)
    shade = hillshade(elev, cell_m)
    lo, hi = float(np.nanmin(elev)), float(np.nanmax(elev))
    t = np.clip((np.nan_to_num(elev, nan=lo) - lo) / max(1.0, hi - lo), 0, 1)
    base = np.stack([60 + 90 * t, 90 + 80 * t, 70 + 40 * t], axis=-1)
    hs = np.concatenate([np.clip(base * (0.35 + 0.9 * shade[..., None]), 0, 255),
                         np.full((h_px, w_px, 1), 255)], axis=-1)
    _save_png(hs.astype(np.uint8), ts.folder / "hillshade.png")

    # height-map for real 3D relief: float32, row 0 = north
    size = min(HEIGHTMAP_SIZE, max(h_px, w_px))
    ys = np.linspace(0, h_px - 1, size)
    xs = np.linspace(0, w_px - 1, size)
    yi, xi = np.meshgrid(ys, xs, indexing="ij")
    y0 = np.clip(np.floor(yi).astype(int), 0, h_px - 2)
    x0 = np.clip(np.floor(xi).astype(int), 0, w_px - 2)
    ty, tx = yi - y0, xi - x0
    z = np.nan_to_num(elev, nan=lo)
    hm = (z[y0, x0] * (1 - tx) * (1 - ty) + z[y0, x0 + 1] * tx * (1 - ty)
          + z[y0 + 1, x0] * (1 - tx) * ty + z[y0 + 1, x0 + 1] * tx * ty).astype("<f4")
    (ts.folder / "heightmap.bin").write_bytes(hm.tobytes())

    meta = {"west": w, "south": s, "east": e, "north": n, "width": size, "height": size,
            "min_m": lo, "max_m": hi, "folder": str(ts.folder)}
    (ts.folder / "overlay.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def load_overlay_meta(ts: TerrainSet) -> Optional[Dict[str, object]]:
    f = ts.folder / "overlay.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def legend() -> List[Tuple[str, str]]:
    return [(name, "#%02x%02x%02x" % rgb) for _c, (name, rgb) in WORLDCOVER.items()]
