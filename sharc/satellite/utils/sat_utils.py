import numpy as np
from sharc.parameters.constants import EARTH_RADIUS

EARTH_RADIUS_KM = EARTH_RADIUS / 1000


class WGS84Defs:
    """Constants for the WGS84 ellipsoid model."""
    SEMI_MAJOR_AXIS = 6378137.0  # Semi-major axis (in meters)
    SEMI_MINOR_AXIS = 6356752.3  # Semi-major axis (in meters)
    ECCENTRICITY = 8.1819190842622e-2  # WGS84 ellipsoid eccentricity
    FLATTENING = 0.0033528106647474805
    FIRST_ECCENTRICITY_SQRD = 6.69437999014e-3


def ecef2lla(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    """Coverts ECEF cartesian coordinates to lat long in WSG84 CRS.

    Parameters
    ----------
    x : np.ndarray
        x coordintate in meters
    y : np.ndarray
        y coordintate in meters
    z : np.ndarray
        x coordintate in meters

    Returns
    -------
    tuple (lat, long, alt)
        lat long and altitude in WSG84 format
    """
    # Longitude calculation
    lon = np.arctan2(y, x)

    # Iteratively solve for latitude and altitude
    p = np.sqrt(np.power(x, 2) + np.power(y, 2))
    lat = np.arctan2(z, p * (1 - WGS84Defs.ECCENTRICITY**2))  # Initial estimate for latitude
    for _ in range(5):  # Iteratively improve the estimate
        N = WGS84Defs.SEMI_MAJOR_AXIS / np.sqrt(1 - WGS84Defs.ECCENTRICITY**2 * np.sin(lat)**2)
        alt = p / np.cos(lat) - N
        lat = np.arctan2(z, p * (1 - WGS84Defs.ECCENTRICITY**2 * (N / (N + alt))))

    # Convert latitude and longitude from radians to degrees
    lat = np.degrees(lat)
    lon = np.degrees(lon)
    return lat, lon, alt


def lla2ecef(lat: np.ndarray, lng: np.ndarray, alt: np.ndarray) -> tuple:
    """Converts from geodetic WSG84 to ECEF coordinates

    Parameters
    ----------
    lat : np.ndarray
        latitude in degrees
    lng : np.ndarray
        longitute in degrees
    alt : np.ndarray
        altitude in meters

    Returns
    -------
    tuple
        x, y and z coordinates
    """
    lat = np.deg2rad(lat)
    lng = np.deg2rad(lng)
    n_phi = WGS84Defs.SEMI_MAJOR_AXIS / np.sqrt(1 - WGS84Defs.FIRST_ECCENTRICITY_SQRD * np.sin(lat)**2)
    x = (n_phi + alt) * np.cos(lat) * np.cos(lng)
    y = (n_phi + alt) * np.cos(lat) * np.sin(lng)
    z = ((1 - WGS84Defs.FLATTENING)**2 * n_phi + alt) * np.sin(lat)

    return x, y, z


def calc_elevation(
        earth_station_lat: np.ndarray,
        space_station_lat: np.ndarray,
        earth_station_long: np.ndarray,
        space_station_long: np.ndarray,
        *,
        earth_station_altitude: np.ndarray,
        space_station_altitude: np.ndarray,
) -> np.ndarray:
    """
    Calculates the elevation angle from an Earth station to a space station using geodesic coordinates.
    The function converts latitude, longitude, and altitude (LLA) coordinates of both the Earth station and the space station
    to Earth-Centered, Earth-Fixed (ECEF) coordinates, computes the line-of-sight (LOS) vector, and gets its projection
    on local zenith and xy
    Args:
        earth_station_lat (np.ndarray): Geodetic Latitude(s) of the Earth station(s) in degrees.
        earth_station_long (np.ndarray): Geodetic Longitude(s) of the Earth station(s) in degrees.
        earth_station_altitude (np.ndarray): Altitude(s) of the Earth station(s) in meters.
        space_station_lat (np.ndarray): Geodetic Latitude(s) of the space station(s) in degrees.
        space_station_long (np.ndarray): Geodetic Longitude(s) of the space station(s) in raddegreesians.
        space_station_altitude (np.ndarray): Altitude(s) of the space station(s) in m.
    Returns:
        float or np.ndarray: Elevation angle(s) in degrees from the Earth station(s) to the space station(s).
    """
    # Convert inputs to arrays if they are scalars
    earth_station_lat = np.atleast_1d(earth_station_lat)
    space_station_lat = np.atleast_1d(space_station_lat)
    earth_station_long = np.atleast_1d(earth_station_long)
    space_station_long = np.atleast_1d(space_station_long)
    earth_station_altitude = np.atleast_1d(earth_station_altitude)
    space_station_altitude = np.atleast_1d(space_station_altitude)

    # Convert LLA to ECEF coordinates
    e_ecef = lla2ecef(
        earth_station_lat, earth_station_long, earth_station_altitude
    )
    e_ecef = np.array(e_ecef)
    s_ecef = lla2ecef(
        space_station_lat, space_station_long, space_station_altitude
    )
    s_ecef = np.array(s_ecef)

    # los_vector shape: (3, N)
    los_vector = s_ecef - e_ecef
    # get its norm
    los_norm = np.linalg.norm(los_vector, axis=0)

    # unit vector representing local earth station zenith
    # NOTE: lat, lon represents the zenith pointing in geodesic, but not if geocentric lat lon
    zenith_unit = np.stack([
        np.cos(np.deg2rad(earth_station_lat)) * np.cos(np.deg2rad(earth_station_long)),
        np.cos(np.deg2rad(earth_station_lat)) * np.sin(np.deg2rad(earth_station_long)),
        np.sin(np.deg2rad(earth_station_lat))
    ])

    # get los projection at zenith vector (same as local coords z diff)
    los_z_projection = np.sum(zenith_unit * los_vector, axis=0)

    # get los xy plane projection with pythagoras
    los_xy_dist_proj = np.sqrt(los_norm ** 2 - los_z_projection ** 2)

    elevation_angles = np.arctan2(los_z_projection, los_xy_dist_proj)

    return np.degrees(elevation_angles)


if __name__ == "__main__":
    r1 = ecef2lla(7792.1450, 0, 0)
    print(r1)
    r2 = lla2ecef(r1[0], r1[1], r1[2])
    print(r2)
