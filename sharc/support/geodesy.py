# -*- coding: utf-8 -*-
"""
Canonical WGS-84 ellipsoidal geodesy helpers.

This module exists to remove duplicate copies of the same
lat/lon/alt -> ECEF conversion that used to be defined independently in
``sharc/station_manager.py``, ``sharc/station_factory.py`` and
``sharc/gui/utils.py``. All three now import from here; the formulas and
constants are unchanged, so numerical output is byte-identical to before.

NOTE: this is deliberately *not* the same model used by
``sharc.satellite.utils.sat_utils`` / ``sharc.support.sharc_geom`` for
satellite/NTN geometry (elevation angle, ENU transforms for space
stations), which intentionally use a spherical Earth approximation. Do not
replace that spherical model with this WGS-84 one without a deliberate,
reviewed decision — the two serve different purposes today (see
``sharc/gui/CESIUMJS_MIGRATION_PLAN.md``, section on coordinates).
"""

import numpy as np

WGS84_A = 6378137.0                    # semi-major axis [m]
WGS84_F = 1.0 / 298.257223563          # flattening
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)   # first eccentricity squared


def lla_to_ecef(lat_deg, lon_deg, h_m, a: float = WGS84_A, f: float = WGS84_F):
    """Vectorized geodetic (deg, deg, m) -> ECEF XYZ (m) on WGS-84.

    Parameters
    ----------
    lat_deg, lon_deg : array-like
        Geodetic latitude/longitude in degrees.
    h_m : array-like
        Height above the WGS-84 ellipsoid in meters.
    a, f : float, optional
        Semi-major axis and flattening, defaults to WGS-84.

    Returns
    -------
    tuple
        X, Y, Z coordinates in meters.
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    h = np.asarray(h_m, dtype=float)

    sl, cl = np.sin(lat), np.cos(lat)
    sb, cb = np.sin(lon), np.cos(lon)

    e2 = f * (2.0 - f)
    N = a / np.sqrt(1.0 - e2 * sl * sl)
    X = (N + h) * cl * cb
    Y = (N + h) * cl * sb
    Z = (N * (1.0 - e2) + h) * sl
    return X, Y, Z


def ecef_to_lla(x, y, z, a: float = WGS84_A, f: float = WGS84_F, tol: float = 1e-12, max_iter: int = 10):
    """Vectorized ECEF XYZ (m) -> geodetic (deg, deg, m) on WGS-84.

    Inverse of :func:`lla_to_ecef`. Iterative (Bowring-style) method,
    converges to double precision in a handful of iterations for any
    altitude relevant here (terrestrial through GEO).

    Parameters
    ----------
    x, y, z : array-like
        ECEF coordinates in meters.
    a, f : float, optional
        Semi-major axis and flattening, defaults to WGS-84.

    Returns
    -------
    tuple
        Latitude, longitude (degrees) and height above the ellipsoid
        (meters).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    z = np.asarray(z, dtype=float)

    e2 = f * (2.0 - f)
    lon = np.arctan2(y, x)
    p = np.sqrt(x * x + y * y)

    # Initial guess ignores ellipsoidal flattening; refined below.
    lat = np.arctan2(z, p * (1.0 - e2))
    for _ in range(max_iter):
        sin_lat = np.sin(lat)
        N = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)
        h = p / np.cos(lat) - N
        lat_new = np.arctan2(z, p * (1.0 - e2 * N / (N + h)))
        if np.all(np.abs(lat_new - lat) < tol):
            lat = lat_new
            break
        lat = lat_new

    sin_lat = np.sin(lat)
    N = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)
    h = p / np.cos(lat) - N

    return np.degrees(lat), np.degrees(lon), h


def rot_ecef_to_enu(lat_deg, lon_deg):
    """Vectorized rotation matrices R (N,3,3) mapping v_ecef -> [E,N,U] at each (lat,lon).

    Rows of each matrix are the ENU basis vectors, on the WGS-84 ellipsoid.
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    sl, cl = np.sin(lat), np.cos(lat)
    sb, cb = np.sin(lon), np.cos(lon)

    # Each R has rows [east; north; up]
    # east  = [-sin(lon),  cos(lon), 0]
    # north = [-sin(lat)cos(lon), -sin(lat)sin(lon), cos(lat)]
    # up    = [ cos(lat)cos(lon),  cos(lat)sin(lon), sin(lat)]
    R = np.empty((lat.shape[0], 3, 3), dtype=float)
    R[:, 0, 0] = -sb
    R[:, 0, 1] = cb
    R[:, 0, 2] = 0.0

    R[:, 1, 0] = -sl * cb
    R[:, 1, 1] = -sl * sb
    R[:, 1, 2] = cl

    R[:, 2, 0] = cl * cb
    R[:, 2, 1] = cl * sb
    R[:, 2, 2] = sl

    return R
