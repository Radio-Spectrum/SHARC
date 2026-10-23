"""What the 3D scene needs to draw a protection contour: curves per BS off-axis angle, violated ray ends, station.

Pure data (no Qt, no engine): built from the rows of `sharc.contour.campaign`, consumed by `setContour` in app.js.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

from sharc.contour import geometry
from sharc.contour.plot import COLORS

NOT_MET_AT_END = "not_met_at_end"


def _finite(*values) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def payload(rows: Sequence[dict], station_name: str, lat: float, lon: float) -> Dict[str, Any]:
    """Curves (closed, ordered by azimuth), violated ray ends, the end of every ray and the bounds of the curves."""
    curves: List[dict] = []
    violated: List[dict] = []
    for i, off in enumerate(sorted({r["off_axis_deg"] for r in rows})):
        sel = sorted((r for r in rows if r["off_axis_deg"] == off), key=lambda r: r["az_enu_deg"])
        color = COLORS[i % len(COLORS)]
        pts = [[round(r["lon"], 6), round(r["lat"], 6)] for r in sel if _finite(r["lat"], r["lon"])]
        if len(pts) >= 2:
            curves.append({"label": f"BS off-axis {off:g} deg", "off_axis_deg": float(off), "color": color,
                           "points": pts + [pts[0]]})
        for r in sel:
            if r["marker"] == NOT_MET_AT_END and _finite(r["lat"], r["lon"]):
                violated.append({"lat": round(r["lat"], 6), "lon": round(r["lon"], 6), "color": color,
                                 "off_axis_deg": float(off)})
    ends: List[List[float]] = []
    for az, d in sorted({(r["az_enu_deg"], r["ray_end_m"]) for r in rows}):
        if d > 0:
            la, lo = geometry.points_on_ray(lat, lon, az, d)
            ends.append([round(float(lo[0]), 6), round(float(la[0]), 6)])
    xs = [p[0] for c in curves for p in c["points"]] + [lon]
    ys = [p[1] for c in curves for p in c["points"]] + [lat]
    return {"station": {"name": station_name, "lat": lat, "lon": lon}, "curves": curves, "violated": violated,
            "ray_ends": ends + ends[:1], "bounds": [min(xs), min(ys), max(xs), max(ys)]}
