import numpy as np

# CONSTANTS
EARTH_RADIUS_M = 6378145  # radius of the Earth, in m
EARTH_RADIUS_KM = 6378.145  # radius of the Earth, in km
KEPLER_CONST = 398601.8  # Kepler's constant, in km^3/s^2
# earth's average rotation rate, in rad/s
EARTH_ROTATION_RATE = 2 * np.pi / (24 * 3600)
EARTH_SPHERICAL_CRS = f"+proj=longlat +a={EARTH_RADIUS_M} +b={EARTH_RADIUS_M} +no_defs"
EARTH_DEFAULT_CRS = EARTH_SPHERICAL_CRS

# EARTH_DEFAULT_CRS = "EPSG:4326"
# # NOTE: This is no source of truth, but if you wish for non spherical earth,
# # the functions lla2ecef and ecef2lla should also be changed
# # More functionality may also need to be changed as the simulator grows
