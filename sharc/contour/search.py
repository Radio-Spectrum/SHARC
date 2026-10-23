"""Search of the smallest distance at which a ray meets the protection criterion.

A plain bisection between the station and the end of the ray is only safe when the margin is monotonic; with terrain
it is not (shadows and line-of-sight "islands"). So:

  1. start at ``d_start`` (the end of the ray, or a safety distance when that is smaller);
  2. sweep INWARDS on a fixed grid of multiples of ``step`` (the same for every off-axis angle and elevation, so the
     losses already computed are reused) up to the first point that does NOT meet the criterion;
  3. bisect between that point and the previous one (which meets it) down to ``tol``.

``margin(d) > 0`` means the criterion is not met. Markers: ``ok``; ``not_met_at_end`` (the point is the end of the
ray); ``met_everywhere`` (the point is ``d_min``).
"""
from __future__ import annotations

import math
from typing import Callable, Tuple

OK = "ok"
NOT_MET_AT_END = "not_met_at_end"
MET_EVERYWHERE = "met_everywhere"


def search_ray(margin: Callable[[float], float], d_start: float, d_min: float, step: float, tol: float
               ) -> Tuple[float, str, int]:
    """Return (distance, marker, number of margin evaluations)."""
    n = [0]

    def m(d):
        n[0] += 1
        return margin(d)

    if d_start <= d_min:
        return d_min, (MET_EVERYWHERE if m(d_min) <= 0 else NOT_MET_AT_END), n[0]
    if m(d_start) > 0:
        return d_start, NOT_MET_AT_END, n[0]
    d_ok = d_start
    d = math.floor(d_start / step) * step
    if d >= d_start:
        d -= step
    while d >= d_min:
        if m(d) > 0:
            lo, hi = d, d_ok
            while hi - lo > tol:
                mid = 0.5 * (lo + hi)
                if m(mid) > 0:
                    lo = mid
                else:
                    hi = mid
            return hi, OK, n[0]
        d_ok = d
        d -= step
    return d_min, MET_EVERYWHERE, n[0]
