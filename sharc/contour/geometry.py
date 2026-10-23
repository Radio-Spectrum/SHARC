"""Ray geometry on the WGS84 ellipsoid and azimuth conventions.

Inside the calculation the azimuth is the ENU one used by SHARC (0 = east, counter-clockwise); maps and CSV files also
use the azimuth from North (clockwise). The conversion is the same in both directions: ``(90 - az) mod 360``.
"""
from __future__ import annotations

import numpy as np
from pyproj import Geod

GEOD = Geod(ellps="WGS84")


def enu_to_north(az_enu):
    """ENU azimuth (0 = east, counter-clockwise) to azimuth from North (clockwise), in degrees."""
    return np.mod(90.0 - np.asarray(az_enu, dtype=float), 360.0)


def north_to_enu(az_north):
    """Azimuth from North (clockwise) to ENU azimuth (0 = east, counter-clockwise), in degrees."""
    return np.mod(90.0 - np.asarray(az_north, dtype=float), 360.0)


def points_on_ray(lat0, lon0, az_enu, distance_m):
    """(lat, lon) of the points at `distance_m` (scalar or array, metres) from the centre along an ENU azimuth."""
    d = np.atleast_1d(np.asarray(distance_m, dtype=float))
    az = np.full(d.shape, float(enu_to_north(az_enu)))
    lon, lat, _ = GEOD.fwd(np.full(d.shape, lon0), np.full(d.shape, lat0), az, d)
    return lat, lon


def distance_m(lat0, lon0, lat, lon):
    """Geodesic distance [m] from the centre to each point."""
    lat, lon = np.atleast_1d(lat), np.atleast_1d(lon)
    _, _, d = GEOD.inv(np.full(lat.shape, lon0), np.full(lat.shape, lat0), lon, lat)
    return d


def bearing_north(lat1, lon1, lat2, lon2) -> float:
    """Azimuth from North (clockwise) of the geodesic from point 1 to point 2, in [0, 360)."""
    az, _, _ = GEOD.inv(lon1, lat1, lon2, lat2)
    return float(np.mod(az, 360.0))


def ray_azimuths(step_deg: float, az_start: float = 0.0, az_end: float = 360.0):
    """ENU azimuths of the rays: `step_deg` apart from `az_start` up to (not including) `az_end`."""
    n = int(round((az_end - az_start) / step_deg))
    return az_start + step_deg * np.arange(n)
