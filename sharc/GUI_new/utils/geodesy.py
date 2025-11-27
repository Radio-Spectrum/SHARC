import numpy as np

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563

def lla_to_ecef(lat_deg, lon_deg, h_m, a=WGS84_A, f=WGS84_F):
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
