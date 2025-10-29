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
    elev_angle = np.arccos((slant**2 + re**2 - rs**2) /
                           (2 * slant * re)) - np.pi / 2

    return np.degrees(elev_angle)


def haversine(
    lon1: np.ndarray,
    lat1: np.ndarray,
    lon2: np.ndarray,
    lat2: np.ndarray,
    R=EARTH_RADIUS_M
):
    """Calculates great-circle distance between 2 points on the surface of Earth.
    Considers spherical earth.

    Returns np.ndarray with N distances in meters
    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


def sat_elevation_to_offaxis(elevation_angle_deg: float | np.ndarray, sat_altitude_m: float | np.ndarray) -> float:
    """
    Convert satellite elevation angle to off-axis angle (angle from nadir).

    Parameters
    ----------
    elevation_angle_deg : float
        Elevation angle in degrees.
    sat_altitude_m : float
        Satellite altitude above Earth's surface in meters.

    Returns
    -------
    float
        Off-axis angle in degrees.
    """
    if np.isscalar(elevation_angle_deg):
        if elevation_angle_deg < 0 or elevation_angle_deg > 90:
            raise ValueError("Elevation angle must be between 0 and 90 degrees.")
    else:
        if (elevation_angle_deg < 0).any() or (elevation_angle_deg > 90).any():
            raise ValueError("Elevation angle must be between 0 and 90 degrees.")

    # Convert elevation angle to radians
    elevation_angle_rad = np.deg2rad(elevation_angle_deg)

    # Calculate the distance from the Earth's center to the satellite
    r_sat = EARTH_RADIUS_M + sat_altitude_m

    # Calculate the off-axis angle using the spherical triangle relationship
    offaxis_angle_rad = np.arcsin(
        (EARTH_RADIUS_M / r_sat) * np.sin(elevation_angle_rad + np.pi / 2)
    )

    # Convert off-axis angle back to degrees
    offaxis_angle_deg = np.rad2deg(offaxis_angle_rad)

    return offaxis_angle_deg


def offaxis_to_sat_elevation(offaxis_angle_deg: float | np.ndarray, sat_altitude_m: float | np.ndarray) -> float:
    """
    Convert off-axis angle (angle from nadir) to satellite elevation angle.

    Parameters
    ----------
    offaxis_angle_deg : float
        Off-axis angle in degrees.
    sat_altitude_km : float
        Satellite altitude above Earth's surface in meters.

    Returns
    -------
    float
        Elevation angle in degrees.
    """
    # We know that 90 deg offaxis is physically impossible, so raise ValueError
    if np.isscalar(offaxis_angle_deg):
        if offaxis_angle_deg < 0 or offaxis_angle_deg >= 90:
            raise ValueError("Elevation angle must be between 0 and 90 degrees.")
    else:
        if (offaxis_angle_deg < 0).any() or (offaxis_angle_deg >= 90).any():
            raise ValueError("Elevation angle must be between 0 and 90 degrees.")
    # Convert off-axis angle to radians
    offaxis_angle_rad = np.deg2rad(offaxis_angle_deg)

    # Calculate the distance from the Earth's center to the satellite
    r_sat = EARTH_RADIUS_M + sat_altitude_m

    # Calculate the elevation angle using the sine law.
    elevation_angle_rad = np.pi / 2 - np.arcsin((r_sat) / EARTH_RADIUS_M * np.sin(offaxis_angle_rad))

    # Convert elevation angle back to degrees
    elevation_angle_deg = np.rad2deg(elevation_angle_rad)

    return elevation_angle_deg


def earth_arc_length_from_nadir(offaxis_angle_deg: float | np.ndarray, sat_altitude_m: float | np.ndarray) -> float:
    """
    Calculate the Earth's surface arc length from nadir to the point
    corresponding to the given off-axis angle.

    Parameters
    ----------
    offaxis_angle_deg : float
        Off-axis angle in degrees.
    sat_altitude_km : float
        Satellite altitude above Earth's surface in meters.

    Returns
    -------
    float
        Arc length on Earth's surface in meters.
    """
    # Convert off-axis angle to radians
    offaxis_angle_rad = np.deg2rad(offaxis_angle_deg)

    phi_rad = np.deg2rad(offaxis_to_sat_elevation(offaxis_angle_deg, sat_altitude_m) + 90.0)

    central_angle_rad = np.pi - phi_rad - offaxis_angle_rad

    # Calculate the arc length on Earth's surface
    arc_length_m = EARTH_RADIUS_M * central_angle_rad

    return arc_length_m


if __name__ == "__main__":
    r1 = ecef2lla(7792.1450, 0, 0)
    print(r1)
    r2 = lla2ecef(r1[0], r1[1], r1[2])
    print(r2)

    print(earth_arc_length_from_nadir(2.19, 520.0 * 1e3))

    print(sat_elevation_to_offaxis(50.0, 520e3))
