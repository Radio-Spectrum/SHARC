"""Lakes and rivers for the 3D preview (Natural Earth 10 m, public domain).

The two shapefiles are downloaded once and kept in the tile cache; `query()` then returns the
features inside a bounding box as GeoJSON, simplified to the size of the view, so the preview
can request only what is on screen. Detailed (10 m) open water is already visible in the
ESA WorldCover layer; this layer adds named, vector rivers and lakes.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, Optional

BASE = "https://naciscdn.org/naturalearth/10m/physical/"
LAYERS = {"rivers": "ne_10m_rivers_lake_centerlines", "lakes": "ne_10m_lakes"}
ATTRIBUTION = "Rivers and lakes: Natural Earth (public domain)."

_lock = threading.Lock()
_data: Dict[str, object] = {}
_cache: Optional[Path] = None


def set_cache_dir(path) -> None:
    global _cache
    _cache = Path(path)
    _cache.mkdir(parents=True, exist_ok=True)


def _load(kind: str):
    """GeoDataFrame for 'rivers' or 'lakes' (downloaded once, then read from the cache)."""
    import geopandas as gpd
    with _lock:
        if kind in _data:
            return _data[kind]
        name = LAYERS[kind]
        local = (_cache / f"{name}.gpkg") if _cache else None
        gdf = None
        if local is not None and local.is_file():
            gdf = gpd.read_file(local)
        else:
            try:
                gdf = gpd.read_file(BASE + name + ".zip")[["name", "scalerank", "geometry"]]
                if local is not None:
                    gdf.to_file(local, driver="GPKG")
            except Exception:  # noqa: BLE001 - offline: the layer is simply empty
                gdf = False
        _data[kind] = gdf
        return gdf


def query(west: float, south: float, east: float, north: float, max_features: int = 600) -> dict:
    """GeoJSON FeatureCollection with the rivers and lakes inside the box."""
    features = []
    span = max(east - west, north - south)
    tol = span / 400.0                       # simplification follows the view size
    for kind in ("lakes", "rivers"):
        gdf = _load(kind)
        if gdf is False or gdf is None:
            continue
        part = gdf.cx[west:east, south:north]
        if len(part) > max_features:
            part = part.nsmallest(max_features, "scalerank")      # keep the most important ones
        for _, row in part.iterrows():
            geom = row.geometry.simplify(tol) if tol > 0 else row.geometry
            if geom.is_empty:
                continue
            features.append({"type": "Feature", "geometry": json.loads(json.dumps(geom.__geo_interface__)),
                             "properties": {"kind": kind, "name": row.get("name") or ""}})
    return {"type": "FeatureCollection", "features": features}
