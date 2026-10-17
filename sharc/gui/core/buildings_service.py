"""Building footprints with heights for the 3D preview (OpenStreetMap, via the Overpass API).

Buildings only matter when the camera is close, so they are fetched in small tiles (zoom 16,
about 600 m) the first time they are in view and cached on disk. Requests never block the GUI:
`query()` returns what is already cached and starts the missing tiles in background threads;
the preview asks again until `pending` is 0.

Heights: the OSM `height` tag, else `building:levels` x 3.2 m, else a default by building type.
Data (c) OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ATTRIBUTION = "Buildings: (c) OpenStreetMap contributors (ODbL)."
OVERPASS = ("https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter",
            "https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
ROUNDS = 3                # passes over the mirrors, with a pause, before a tile is given up for now
last_error = ""           # shown by the preview when buildings cannot be downloaded
ZOOM = 16
MAX_TILES = 16            # per request (view limit)
DEFAULT_HEIGHT = {"house": 6.0, "residential": 9.0, "apartments": 24.0, "commercial": 15.0, "industrial": 9.0,
                  "retail": 8.0, "office": 24.0, "church": 14.0, "school": 10.0, "hospital": 20.0, "garage": 3.5,
                  "shed": 3.0, "roof": 4.0}

ROAD_WIDTH = {"motorway": 14, "trunk": 14, "primary": 12, "secondary": 10, "tertiary": 8, "motorway_link": 7, "trunk_link": 7,
              "primary_link": 7, "secondary_link": 6, "tertiary_link": 6, "residential": 6, "unclassified": 6,
              "living_street": 5, "service": 3.5, "pedestrian": 4}

_cache: Optional[Path] = None
_inflight: Set[Tuple[int, int]] = set()
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="osm-buildings")


def set_cache_dir(path) -> None:
    global _cache
    _cache = Path(path)
    _cache.mkdir(parents=True, exist_ok=True)


def _tile_file(x: int, y: int) -> Path:
    assert _cache is not None
    return _cache / str(ZOOM) / str(x) / f"{y}.v3.json"


def _tile_bounds(x: int, y: int) -> Tuple[float, float, float, float]:
    n = 2.0 ** ZOOM
    w = x / n * 360 - 180
    e = (x + 1) / n * 360 - 180
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return w, south, e, north


def _tiles_for(west: float, south: float, east: float, north: float) -> List[Tuple[int, int]]:
    n = 2.0 ** ZOOM

    def tx(lon):
        return int((lon + 180) / 360 * n)

    def ty(lat):
        lat = max(-85.0511, min(85.0511, lat))
        return int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return [(x, y) for x in range(tx(west), tx(east) + 1) for y in range(ty(north), ty(south) + 1)]


def _height(tags: Dict[str, str]) -> float:
    raw = tags.get("height") or tags.get("building:height")
    if raw:
        m = re.search(r"[\d.]+", raw.replace(",", "."))
        if m:
            return max(2.0, float(m.group()))
    lv = tags.get("building:levels")
    if lv:
        m = re.search(r"[\d.]+", lv)
        if m:
            return max(3.0, float(m.group()) * 3.2 + 1.0)
    return DEFAULT_HEIGHT.get(tags.get("building", ""), 7.0)


def _fetch_tile(x: int, y: int) -> None:
    try:
        w, s, e, n = _tile_bounds(x, y)
        bb = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
        q = f'[out:json][timeout:50];(way["building"]{bb};node["natural"="tree"]{bb};way["highway"]{bb};);out tags geom;'
        body = None
        global last_error
        for rnd in range(ROUNDS):
            for url in OVERPASS:
                try:
                    data = urllib.parse.urlencode({"data": q}).encode()
                    req = urllib.request.Request(url, data=data, headers={"User-Agent": "SHARC-GUI/1.0 (research)"})
                    body = json.loads(urllib.request.urlopen(req, timeout=60).read())
                    last_error = ""
                    break
                except Exception as exc:  # noqa: BLE001 - try the next mirror
                    last_error = f"{type(exc).__name__}: {exc}"
            if body is not None:
                break
            time.sleep(1.5 * (rnd + 1))
        if body is None:
            return                                  # stay uncached; asked again next time
        feats, trees, roads = [], [], []
        for el in body.get("elements", []):
            if el.get("type") == "node":
                tags = el.get("tags", {})
                try:
                    th = float(re.search(r"[\d.]+", tags.get("height", "")).group())
                except (AttributeError, ValueError):
                    th = 0.0
                trees.append([round(el["lon"], 6), round(el["lat"], 6), th])
                continue
            geom = el.get("geometry")
            hw = el.get("tags", {}).get("highway")
            if hw:
                if hw in ROAD_WIDTH and geom and len(geom) >= 2:
                    roads.append([ROAD_WIDTH[hw], [[round(p["lon"], 6), round(p["lat"], 6)] for p in geom]])
                continue
            if not geom or len(geom) < 4:
                continue
            ring = [[p["lon"], p["lat"]] for p in geom]
            feats.append({"id": el["id"], "h": round(_height(el.get("tags", {})), 1), "ring": ring})
        f = _tile_file(x, y)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"b": feats, "t": trees, "r": roads}), encoding="utf-8")
    finally:
        with _lock:
            _inflight.discard((x, y))


def _veg_file(x: int, y: int) -> Path:
    from core import tile_service
    return tile_service.cache_dir() / "codes" / "14" / str(x) / f"{y}.npy"


def _veg_fetch(x: int, y: int) -> None:
    try:
        from core import tile_service
        tile_service.worldcover_codes(14, x, y)
    except Exception:  # noqa: BLE001 - trees are decoration; never break the scene
        pass
    finally:
        with _lock:
            _inflight.discard(("veg", x, y))


# land-cover class -> chance that a ~10 m pixel holds a tree (deterministic hash, so it never flickers)
_TREE_CHANCE = {10: 0.30, 20: 0.05, 50: 0.025, 30: 0.008, 40: 0.01}


def _hash01(a: int, b: int, salt: int) -> float:
    h = (a * 73856093) ^ (b * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 4294967295.0


def vegetation_trees(west: float, south: float, east: float, north: float, blocked: list, limit: int) -> Tuple[List[list], int]:
    """Trees planted where the ESA land cover says there is vegetation (or sparse street trees in built-up
    areas). Reproducible: the same place always gets the same trees. Returns (trees, tiles still loading)."""
    import numpy as np
    from core import tile_service
    z = 14
    n = 2.0 ** z
    pending, out = 0, []

    def tx(lon):
        return int((lon + 180) / 360 * n)

    def ty(lat):
        return int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    for x in range(tx(west), tx(east) + 1):
        for y in range(ty(north), ty(south) + 1):
            if not _veg_file(x, y).is_file():
                pending += 1
                with _lock:
                    if ("veg", x, y) in _inflight:
                        continue
                    _inflight.add(("veg", x, y))
                _pool.submit(_veg_fetch, x, y)
                continue
            codes = np.load(_veg_file(x, y))
            w0, s0, e0, n0 = tile_service.tile_lonlat_bounds(z, x, y)
            px_w, px_h = (e0 - w0) / 256.0, (n0 - s0) / 256.0
            c0, c1 = max(0, int((west - w0) / px_w)), min(255, int((east - w0) / px_w))
            r0, r1 = max(0, int((n0 - north) / px_h)), min(255, int((n0 - south) / px_h))
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    chance = _TREE_CHANCE.get(int(codes[r, c]))
                    if not chance or _hash01(x * 256 + c, y * 256 + r, 1) > chance:
                        continue
                    lon = w0 + (c + _hash01(c, r, 2)) * px_w
                    lat = n0 - (r + _hash01(c, r, 3)) * px_h
                    if not (west <= lon <= east and south <= lat <= north):
                        continue
                    if any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] for b in blocked):
                        continue
                    out.append([round(lon, 6), round(lat, 6), round(5.0 + 9.0 * _hash01(c, r, 4), 1), 1])
                    if len(out) >= limit:
                        return out, pending
    return out, pending


def query(west: float, south: float, east: float, north: float, want_trees: bool = True, tree_limit: int = 2500,
          want_roads: bool = False) -> dict:
    """Cached buildings in the box + how many tiles are still being fetched."""
    tiles = _tiles_for(west, south, east, north)
    if len(tiles) > MAX_TILES or _cache is None:
        return {"features": [], "pending": 0, "too_wide": len(tiles) > MAX_TILES, "trees": []}
    features, pending, trees, roads = [], 0, [], []
    for x, y in tiles:
        f = _tile_file(x, y)
        if f.is_file():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                features.extend(data["b"])
                roads.extend(data.get("r", []))
                trees.extend([t[0], t[1], t[2] or 8.0, 0] for t in data["t"])
            except (OSError, ValueError, KeyError):
                pass
            continue
        pending += 1
        with _lock:
            if (x, y) in _inflight:
                continue
            _inflight.add((x, y))
        _pool.submit(_fetch_tile, x, y)
    err = last_error if pending == 0 and not features else ""
    result = {"features": features, "pending": pending, "too_wide": False, "error": err, "trees": [], "roads": roads if want_roads else []}
    if want_trees:
        blocked = [(min(p[0] for p in b["ring"]), min(p[1] for p in b["ring"]),
                    max(p[0] for p in b["ring"]), max(p[1] for p in b["ring"])) for b in features]
        veg, veg_pending = vegetation_trees(west, south, east, north, blocked, max(0, tree_limit - len(trees)))
        result["trees"] = trees[:tree_limit] + veg
        result["pending"] += veg_pending
    return result
