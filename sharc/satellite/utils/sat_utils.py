import numpy as np
from sharc.satellite.ngso.constants import EARTH_RADIUS_M


def ecef2lla(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    """Coverts ECEF cartesian coordinates to lat long in spherical earth model.

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
        lat long and altitude in spherical earth model
    """
    x = np.atleast_1d(x)
    y = np.atleast_1d(y)
    z = np.atleast_1d(z)
    xy = np.sqrt(x**2 + y**2)

    lon = np.arccos(x / xy)
    lon[y < 0] = -lon[y < 0]

    lat = np.arctan2(z, xy)

    xyz = np.sqrt(x**2 + y**2 + z**2)
    alt = xyz - EARTH_RADIUS_M

    lat = np.rad2deg(lat)
    lon = np.rad2deg(lon)

    return lat, lon, alt


def lla2ecef(lat: np.ndarray, lon: np.ndarray, alt: np.ndarray) -> tuple:
    """Converts from spherical earth model lla to ECEF coordinates

    Parameters
    ----------
    lat : np.ndarray
        latitude in degrees
    lon : np.ndarray
        longitute in degrees
    alt : np.ndarray
        altitude in meters

    Returns
    -------
    tuple
        x, y and z coordinates
    """
    lat = np.atleast_1d(lat)
    lon = np.atleast_1d(lon)
    alt = np.atleast_1d(alt)

    r = (alt + EARTH_RADIUS_M)
    x = r * np.cos(np.deg2rad(lat)) * np.cos(np.deg2rad(lon))
    y = r * np.cos(np.deg2rad(lat)) * np.sin(np.deg2rad(lon))
    z = r * np.sin(np.deg2rad(lat))

    return x, y, z


def calc_elevation(Le: np.ndarray,
                   Ls: np.ndarray,
                   le: np.ndarray,
                   ls: np.ndarray,
                   *,
                   sat_height: np.ndarray,
                   es_height: np.ndarray,
               ) -> np.ndarray:
    """Calculates the elevation angle from the earth station
    to space station, given earth and space station coordinates.
    Negative elevation angles means the space stations is not visible from Earth station.

    Parameters
    ----------
    Le : (ndarray)
        latitudes of the earth station
    Ls : (ndarray)
        latitudes of the space station
    le : (ndarray)
        longitudes of the earth station
    ls : (ndarray)
        latitudes of the space station
    sat_height : (ndarray)
        space station altitudes in meters
    es_height : (ndarray)
        earth station altitudes in meters

    Returns
    -------
    (ndarray)
        array of elevation angles from the earth station in degrees.
    """
    Le = np.radians(Le)
    Ls = np.radians(Ls)
    le = np.radians(le)
    ls = np.radians(ls)
    gamma = np.arccos(
        np.cos(Le) * np.cos(Ls) * np.cos(ls - le) + np.sin(Le) * np.sin(Ls)
    )
    rs = EARTH_RADIUS_M + sat_height
    re = EARTH_RADIUS_M + es_height
    slant = np.sqrt(rs**2 + re**2 - 2 * rs * re * np.cos(gamma))
    elev_angle = np.arccos((slant**2 + re**2 - rs**2) / \
                           (2 * slant * re)) - np.pi / 2

    return np.degrees(elev_angle)


if __name__ == "__main__":
    r1 = ecef2lla(7792.1450, 0, 0)
    print(r1)
    r2 = lla2ecef(r1[0], r1[1], r1[2])
    print(r2)
