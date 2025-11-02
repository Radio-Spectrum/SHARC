"""
Geodesy helpers: conversion from lat/lon/height (LLA) to ECEF coordinates.
Kept small and dependency-free (uses numpy).
"""

from typing import Tuple, Union
import numpy as np

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563


def lla_to_ecef(
    lat_deg: Union[float, list, tuple],
    lon_deg: Union[float, list, tuple],
    h_m: Union[float, list, tuple],
    a: float = WGS84_A,
    f: float = WGS84_F,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert latitude (deg), longitude (deg), height (m) to ECEF X, Y, Z (meters).
    Accepts scalars or array-like inputs (NumPy arrays returned).
    """
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    s, c = np.sin(lat), np.cos(lat)
    sl, cl = np.sin(lon), np.cos(lon)
    e2 = f * (2.0 - f)
    N = a / np.sqrt(1.0 - e2 * s * s)
    X = (N + h_m) * c * cl
    Y = (N + h_m) * c * sl
    Z = (N * (1.0 - e2) + h_m) * s
    return X, Y, Z
