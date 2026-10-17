"""Adaptive terrain and land-cover tiles for the 3D preview (no Qt, thread-safe).

Instead of downloading a region, the preview asks for the tiles it is looking at, and
this module builds each tile on demand and caches it on disk:

* elevation   -> AWS Terrain Tiles "terrarium" (a global composite of NASA SRTM, USGS NED/GMTED
                 and other public DEMs): https://registry.opendata.aws/terrain-tiles/
* hillshade   -> computed here from the elevation tile
* land cover  -> ESA WorldCover 10 m (2021, v200), read by window from the public cloud-optimised
                 GeoTIFFs, so only the pixels in view are transferred

Tile scheme: XYZ web-mercator (same as web maps). `tile_*` functions return PNG/bytes, or None
when the data cannot be obtained (offline, no coverage); callers must treat that as "no data".
"""
from __future__ import annotations

import io
import math
import threading
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
WORLDCOVER_URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                  "ESA_WorldCover_10m_2021_v200_{name}_Map.tif")
MIN_CLUTTER_ZOOM = 9       # coarser tiles span too many 3-degree WorldCover files and are not useful
MAX_DEM_ZOOM = 14          # finest published terrarium level used; deeper levels are interpolated
TILE = 256
USER_AGENT = "SHARC-GUI/1.0 (spectrum sharing simulator)"

ATTRIBUTION = ("Elevation: AWS Terrain Tiles (NASA SRTM, USGS and other public DEMs). "
               "Land cover: ESA WorldCover 10 m 2021 v200 (CC BY 4.0).")

WORLDCOVER_COLORS = {
    10: (0, 100, 0), 20: (255, 187, 34), 30: (255, 255, 76), 40: (240, 150, 255),
    50: (250, 0, 0), 60: (180, 180, 180), 70: (240, 240, 240), 80: (0, 100, 200),
    90: (0, 150, 160), 95: (0, 207, 117), 100: (250, 230, 160),
}

# Soft palette for the "clean city model" look: neutral built-up ground, green vegetation, light water.
CLEAN_COLORS = {
    10: (96, 160, 84), 20: (150, 190, 110), 30: (190, 214, 150), 40: (206, 214, 160),
    50: (196, 199, 204), 60: (222, 214, 196), 70: (245, 247, 250), 80: (120, 176, 222),
    90: (140, 190, 170), 95: (110, 180, 130), 100: (222, 226, 196),
}

_dem_lock = threading.Lock()
_wc_lock = threading.Lock()
_wc_datasets: Dict[str, object] = {}
_cache_dir: Optional[Path] = None


def set_cache_dir(path) -> None:
    global _cache_dir
    _cache_dir = Path(path)
    _cache_dir.mkdir(parents=True, exist_ok=True)


def cache_dir() -> Path:
    global _cache_dir
    if _cache_dir is None:
        import tempfile
        _cache_dir = Path(tempfile.gettempdir()) / "sharc_tile_cache"
        _cache_dir.mkdir(parents=True, exist_ok=True)
    return _cache_dir


# --------------------------------------------------------------------------- geometry
def tile_lonlat_bounds(z: int, x: int, y: int) -> Tuple[float, float, float, float]:
    """(west, south, east, north) of an XYZ tile, degrees."""
    n = 2.0 ** z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def lonlat_to_tile(lat: float, lon: float, z: int) -> Tuple[int, int, float, float]:
    """Tile (x, y) containing a point, plus the fractional pixel position inside it."""
    n = 2.0 ** z
    fx = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(max(-85.0511, min(85.0511, lat)))
    fy = (1 - math.asinh(math.tan(lat_r)) / math.pi) / 2 * n
    return int(fx), int(fy), (fx - int(fx)) * TILE, (fy - int(fy)) * TILE


# --------------------------------------------------------------------------- helpers
_net_slots = threading.Semaphore(6)       # too many parallel requests make AWS time out


def _http_get(url: str, timeout: float = 25.0, retries: int = 2) -> Optional[bytes]:
    import urllib.error
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with _net_slots:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):          # no such tile (open sea, outside coverage): do not retry
                return None
        except Exception:  # noqa: BLE001 - timeouts, resets: try again
            pass
    return None


def _png_bytes(rgba: np.ndarray) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(rgba, dtype=np.uint8), "RGBA").save(buf, "PNG", optimize=False)
    return buf.getvalue()


def _transparent_png() -> bytes:
    return _png_bytes(np.zeros((TILE, TILE, 4), dtype=np.uint8))


# --------------------------------------------------------------------------- elevation
def _decode_terrarium(png: bytes) -> np.ndarray:
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float64)
    return (a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0).astype(np.float32)


def _dem_raw(z: int, x: int, y: int) -> Optional[np.ndarray]:
    """Elevation tile at a published zoom level (disk-cached)."""
    f = cache_dir() / "dem" / str(z) / str(x) / f"{y}.png"
    if f.is_file():
        return _decode_terrarium(f.read_bytes())
    data = _http_get(TERRARIUM_URL.format(z=z, x=x, y=y))
    if data is None:
        return None
    with _dem_lock:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    return _decode_terrarium(data)


def _bilinear_resize(a: np.ndarray, out: int) -> np.ndarray:
    h, w = a.shape
    ys = np.linspace(0, h - 1, out)
    xs = np.linspace(0, w - 1, out)
    y0 = np.clip(np.floor(ys).astype(int), 0, h - 2)
    x0 = np.clip(np.floor(xs).astype(int), 0, w - 2)
    ty = (ys - y0)[:, None]
    tx = (xs - x0)[None, :]
    return (a[np.ix_(y0, x0)] * (1 - ty) * (1 - tx) + a[np.ix_(y0, x0 + 1)] * (1 - ty) * tx
            + a[np.ix_(y0 + 1, x0)] * ty * (1 - tx) + a[np.ix_(y0 + 1, x0 + 1)] * ty * tx)


def dem_tile(z: int, x: int, y: int) -> Optional[np.ndarray]:
    """256x256 float32 elevation [m] for any zoom (deeper than MAX_DEM_ZOOM is interpolated)."""
    if z <= MAX_DEM_ZOOM:
        return _dem_raw(z, x, y)
    dz = z - MAX_DEM_ZOOM
    parent = _dem_raw(MAX_DEM_ZOOM, x >> dz, y >> dz)
    if parent is None:
        return None
    n = 1 << dz
    # Continuous bilinear sampling of the parent tile: neighbouring deep tiles stay seamless (a fixed
    # small window quantised the surface into spikes at very low camera altitudes).
    fx, fy = (x & (n - 1)) / n, (y & (n - 1)) / n
    step = np.arange(TILE) + 0.5
    cols = np.clip((fx + step / TILE / n) * TILE - 0.5, 0, TILE - 1)
    rows = np.clip((fy + step / TILE / n) * TILE - 0.5, 0, TILE - 1)
    c0, r0 = np.minimum(cols.astype(int), TILE - 2), np.minimum(rows.astype(int), TILE - 2)
    tc, tr = (cols - c0)[None, :], (rows - r0)[:, None]
    a00 = parent[np.ix_(r0, c0)]
    a01 = parent[np.ix_(r0, c0 + 1)]
    a10 = parent[np.ix_(r0 + 1, c0)]
    a11 = parent[np.ix_(r0 + 1, c0 + 1)]
    out = a00 * (1 - tc) * (1 - tr) + a01 * tc * (1 - tr) + a10 * (1 - tc) * tr + a11 * tc * tr
    return out.astype(np.float32)


def tile_terrain_f32(z: int, x: int, y: int) -> Optional[bytes]:
    """Little-endian float32 elevation samples (256*256), row 0 = north."""
    a = dem_tile(z, x, y)
    if a is None:
        return None
    if z >= 12:
        a = _bare_earth(a, z, y)
    a = np.maximum(a, 0.0)          # sea level is the floor: the 3D view shows water as a surface, not bathymetry
    return a.astype("<f4").tobytes()


def _bare_earth(a: np.ndarray, z: int, y: int) -> np.ndarray:
    """Approximate the ground under buildings and trees. Global elevation models are surface models: in a
    city they follow roofs (tens of metres), which, draped with imagery, shows as waves across the streets.
    A minimum filter about 90 m wide removes the buildings, then a smoothing removes the filter's steps."""
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / 2.0 ** z))))
    mpp = 156543.03 * math.cos(math.radians(lat)) / 2.0 ** z          # metres per pixel of a 256 px tile
    k = int(max(3, min(61, round(160.0 / max(mpp, 0.1)))))
    k += (k + 1) % 2                                                   # odd
    try:
        from scipy.ndimage import minimum_filter
        a = minimum_filter(a, size=k, mode="nearest")
    except ImportError:
        pass
    return _smooth(a, max(5, k))


def _smooth(a: np.ndarray, k: int) -> np.ndarray:
    """Mean filter (k x k, edge padded). Urban elevation models carry building and tree noise that, draped
    with imagery, shows as waves across streets; a gentle smoothing keeps the real relief and drops the noise."""
    r = k // 2
    p = np.pad(a.astype(np.float64), r, mode="edge")
    c = p.cumsum(axis=0).cumsum(axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    h, w = a.shape
    s = c[k:k + h, k:k + w] - c[0:h, k:k + w] - c[k:k + h, 0:w] + c[0:h, 0:w]
    return (s / (k * k)).astype(np.float32)


def tile_hillshade_png(z: int, x: int, y: int, azimuth: float = 315.0, altitude: float = 40.0,
                       exaggeration: float = 2.0) -> Optional[bytes]:
    f = cache_dir() / "hillshade" / str(z) / str(x) / f"{y}.png"
    if f.is_file():
        return f.read_bytes()
    a = dem_tile(z, x, y)
    if a is None:
        return None
    w, s, e, n = tile_lonlat_bounds(z, x, y)
    cell_m = max(0.5, (e - w) * 111320.0 * math.cos(math.radians((s + n) / 2)) / TILE)
    gy, gx = np.gradient(a.astype(np.float64) * exaggeration, cell_m)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(360.0 - azimuth + 90.0), math.radians(altitude)
    shade = np.clip(math.sin(alt) * np.cos(slope) + math.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    # neutral grey ramp; only the relative lighting matters when it is draped under other layers
    g = (60 + 195 * shade).astype(np.uint8)
    rgba = np.stack([g, g, g, np.full_like(g, 255)], axis=-1)
    png = _png_bytes(rgba)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(png)
    return png


# --------------------------------------------------------------------------- land cover
def _wc_name(lat0: int, lon0: int) -> str:
    return f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"


class LandCoverUnavailable(RuntimeError):
    """The land-cover source could not be reached (transient): never cache a blank tile for it."""


_wc_failed_at: dict = {}
_WC_RETRY_S = 20.0


def _wc_dataset(name: str):
    """Open one 3x3 degree WorldCover COG. None = no such tile (ocean). Network trouble raises
    LandCoverUnavailable and is retried, so one timeout cannot blank a whole region for good."""
    import time
    import rasterio
    with _wc_lock:
        ds = _wc_datasets.get(name)
        if ds is not None:
            return ds or None
        if time.time() - _wc_failed_at.get(name, 0.0) < _WC_RETRY_S:
            raise LandCoverUnavailable(name)
        url = "/vsicurl/" + WORLDCOVER_URL.format(name=name)
        last = None
        for attempt in range(3):
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                              GDAL_HTTP_TIMEOUT="20", GDAL_HTTP_MAX_RETRY="2"):
                try:
                    ds = rasterio.open(url)
                    _wc_datasets[name] = ds
                    return ds
                except Exception as exc:  # noqa: BLE001
                    last = str(exc)
            if "404" in last or "not exist" in last.lower() or "No such file" in last:
                _wc_datasets[name] = False                 # definitely no data here (open sea)
                return None
            time.sleep(0.5 * (attempt + 1))
        _wc_failed_at[name] = time.time()
        raise LandCoverUnavailable(f"{name}: {last}")


def worldcover_tile(z: int, x: int, y: int) -> Optional[np.ndarray]:
    """256x256 uint8 WorldCover class codes (0 = no data) for an XYZ tile."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    if z < MIN_CLUTTER_ZOOM:
        return np.zeros((TILE, TILE), dtype=np.uint8)
    west, south, east, north = tile_lonlat_bounds(z, x, y)
    lats = np.array([math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + (r + 0.5) / TILE) / 2.0 ** z))))
                     for r in range(TILE)])
    lons = west + (east - west) * (np.arange(TILE) + 0.5) / TILE
    out = np.zeros((TILE, TILE), dtype=np.uint8)
    for lat0 in range(int(math.floor(south / 3.0)) * 3, int(math.floor(north / 3.0)) * 3 + 1, 3):
        for lon0 in range(int(math.floor(west / 3.0)) * 3, int(math.floor(east / 3.0)) * 3 + 1, 3):
            ds = _wc_dataset(_wc_name(lat0, lon0))
            if ds is None:
                continue
            w0, e0 = max(west, lon0), min(east, lon0 + 3)
            s0, n0 = max(south, lat0), min(north, lat0 + 3)
            if w0 >= e0 or s0 >= n0:
                continue
            with _wc_lock:
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
                    win = from_bounds(w0, s0, e0, n0, ds.transform)
                    cols = max(2, int(round((e0 - w0) / (east - west) * TILE)) * 2)
                    rows = max(2, int(round((n0 - s0) / max(1e-9, north - south) * TILE)) * 2)
                    arr = ds.read(1, window=win, out_shape=(rows, cols), resampling=Resampling.nearest,
                                  boundless=False)
            # map every output pixel to a window pixel
            col = np.clip(((lons - w0) / (e0 - w0) * (cols - 1)).round().astype(int), 0, cols - 1)
            row = np.clip(((n0 - lats) / (n0 - s0) * (rows - 1)).round().astype(int), 0, rows - 1)
            in_lon = (lons >= w0) & (lons <= e0)
            in_lat = (lats >= s0) & (lats <= n0)
            patch = arr[np.ix_(row, col)]
            mask = np.outer(in_lat, in_lon)
            out[mask] = patch[mask]
    return out


def worldcover_codes(z: int, x: int, y: int) -> Optional[np.ndarray]:
    """WorldCover class codes of a tile, cached on disk (.npy); None when unavailable."""
    f = cache_dir() / "codes" / str(z) / str(x) / f"{y}.npy"
    if f.is_file():
        return np.load(f)
    try:
        codes = worldcover_tile(z, x, y)
    except Exception:  # noqa: BLE001
        return None
    f.parent.mkdir(parents=True, exist_ok=True)
    np.save(f, codes)
    return codes


def tile_clutter_png(z: int, x: int, y: int, opacity: float = 1.0, clean: bool = False) -> Optional[bytes]:
    palette = CLEAN_COLORS if clean else WORLDCOVER_COLORS
    f = cache_dir() / ("clutter_clean" if clean else "clutter") / str(z) / str(x) / f"{y}.png"
    if f.is_file():
        return f.read_bytes()
    try:
        codes = worldcover_tile(z, x, y)
    except Exception:  # noqa: BLE001
        return None
    if codes is None or not codes.any():
        png = _transparent_png()
    else:
        rgba = np.zeros((TILE, TILE, 4), dtype=np.uint8)
        for code, rgb in palette.items():
            m = codes == code
            rgba[m, 0], rgba[m, 1], rgba[m, 2], rgba[m, 3] = rgb[0], rgb[1], rgb[2], 255
        png = _png_bytes(rgba)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(png)
    return png


# --------------------------------------------------------------------------- point queries
def ground_height(lat: float, lon: float, zoom: int = 12) -> Optional[float]:
    """Ground height [m] at a point (bilinear on an elevation tile); None without data."""
    x, y, px, py = lonlat_to_tile(lat, lon, zoom)
    a = dem_tile(zoom, x, y)
    if a is None:
        return None
    x0, y0 = int(min(px, TILE - 2)), int(min(py, TILE - 2))
    tx, ty = px - x0, py - y0
    return float(a[y0, x0] * (1 - tx) * (1 - ty) + a[y0, x0 + 1] * tx * (1 - ty)
                 + a[y0 + 1, x0] * (1 - tx) * ty + a[y0 + 1, x0 + 1] * tx * ty)


def land_cover_at(lat: float, lon: float, zoom: int = 14) -> Optional[int]:
    """WorldCover class code at a point; None without data."""
    x, y, px, py = lonlat_to_tile(lat, lon, zoom)
    try:
        codes = worldcover_tile(zoom, x, y)
    except Exception:  # noqa: BLE001
        return None
    v = int(codes[int(min(py, TILE - 1)), int(min(px, TILE - 1))])
    return v or None


# --------------------------------------------------------------------------- cache warming
_warm_lock = threading.Lock()
_warm_done: set = set()


def warm(lat: float, lon: float, max_zoom: int = 15, with_clutter: bool = True, with_dem: bool = True) -> int:
    """Fetch, in parallel, the chain of tiles from the world view down to `max_zoom` at a point.

    The 3D view refines level by level (each level only after its parent arrived); doing the whole
    chain at once turns ~15 sequential network round trips into one. Returns the tiles requested."""
    from concurrent.futures import ThreadPoolExecutor
    key = (round(lat, 3), round(lon, 3), max_zoom, with_clutter, with_dem)
    with _warm_lock:
        if key in _warm_done:
            return 0
        _warm_done.add(key)
    jobs = []
    for z in range(0, max_zoom + 1):
        x, y, _, _ = lonlat_to_tile(lat, lon, z)
        if with_dem and z <= MAX_DEM_ZOOM:
            jobs.append((_dem_raw, (z, x, y)))
        if with_clutter and z >= MIN_CLUTTER_ZOOM:
            jobs.append((tile_clutter_png, (z, x, y)))

    def run(job):
        fn, args = job
        try:
            fn(*args)
        except Exception:  # noqa: BLE001 - warming is best effort
            pass

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(run, jobs))
    return len(jobs)
