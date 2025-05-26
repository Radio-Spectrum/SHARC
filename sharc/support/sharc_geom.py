import numpy as np
import shapely as shp
import typing
import pyproj
import scipy.spatial.transform

from sharc.satellite.utils.sat_utils import lla2ecef, ecef2lla
from sharc.station_manager import StationManager


def cartesian_to_polar(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    """
    Converts cartesian coordinates to polar coordinates.

    Parameters
    ----------
    x : np.ndarray
        x coordinate in meters
    y : np.ndarray
        y coordinate in meters
    z : np.ndarray
        z coordinate in meters

    Returns
    -------
    tuple
        range, azimuth and elevation in meters, degrees and degrees
    """
    # range calculation
    r = np.sqrt(x**2 + y**2 + z**2)

    # azimuth calculation
    azimuth = np.arctan2(y, x)

    # elevation calculation
    elevation = np.arcsin(z / r)

    return r, np.degrees(azimuth), np.degrees(elevation)


def polar_to_cartesian(r: np.ndarray, azimuth: np.ndarray, elevation: np.ndarray) -> tuple:
    """
    Converts polar coordinates to cartesian coordinates.

    Parameters
    ----------
    r : np.ndarray
        range in meters
    azimuth : np.ndarray
        azimuth in degrees
    elevation : np.ndarray
        elevation in degrees

    Returns
    -------
    tuple
        x, y and z coordinates in meters
    """
    azimuth = np.radians(azimuth)
    elevation = np.radians(elevation)
    x = r * np.cos(elevation) * np.cos(azimuth)
    y = r * np.cos(elevation) * np.sin(azimuth)
    z = r * np.sin(elevation)

    return x, y, z


def get_rotation_matrix(around_z, around_y):
    """
    Rotates with the right hand rule around the z axis (similar to simulator azimuth)
    and with the right hand rule around the y axis (similar to simulator elevation)
    """
    alpha = np.deg2rad(around_z)
    beta = np.deg2rad(around_y)

    ry = np.matrix([
        [np.cos(beta), 0.0, np.sin(beta)],
        [0.0, 1.0, 0.0],
        [-np.sin(beta), 0.0, np.cos(beta)],
    ])
    rz = np.matrix([
        [np.cos(alpha), -np.sin(alpha), 0.0],
        [np.sin(alpha), np.cos(alpha), 0.0],
        [0.0, 0.0, 1.0],
    ])

    return rz * ry


def rotate_angles_based_on_new_nadir(elev, azim, nadir_elev, nadir_azim):
    """
    Receives elevation and azimuth 2d, rotates around base
    so that base_elev <> 0deg and base_azim <> 0deg
    elevation being 0 at horizon (xy plane) and azimuth 0 at x axis

    Returns
    ------
        elevation, azimuth
        (xy plane elevation)
    """
    # translating to normal polar coordinate system, with theta being angle from z axis
    # and phi being angle from x axis in the xy plane
    nadir_theta = 90 - nadir_elev
    nadir_phi = nadir_azim

    nadir_point = np.matrix([
        np.sin(np.deg2rad(nadir_theta)) * np.cos(np.deg2rad(nadir_phi)),
        np.sin(np.deg2rad(nadir_theta)) * np.sin(np.deg2rad(nadir_phi)),
        np.cos(np.deg2rad(nadir_theta)),
    ])
    # first rotate around y axis nadir_theta-180 to reach new theta
    # since nadir_theta in (0,180), rotation will end up to azimuth=0
    # so we rotate it around z axis nadir_phi
    rotation_matrix = get_rotation_matrix(nadir_phi, nadir_theta - 180)

    theta = 90 - elev
    phi = azim

    phi_rad = np.ravel(np.array([np.deg2rad(phi)]))
    theta_rad = np.ravel(np.array([np.deg2rad(theta)]))

    points = np.matrix([
        np.sin(theta_rad) * np.cos(phi_rad),
        np.sin(theta_rad) * np.sin(phi_rad),
        np.cos(theta_rad),
    ])

    rotated_points = rotation_matrix @ points

    rotated_phi = np.ravel(
        np.asarray(
            np.rad2deg(
                np.arctan2(rotated_points[1], rotated_points[0]),
            ),
        ),
    )
    rotated_theta = np.ravel(
        np.asarray(
            np.rad2deg(np.arccos(rotated_points[2])),
        ),
    )

    # back to elevation = 0 deg at xy plane, 90 at zenith and -90 at nadir
    res_elev = 90 - rotated_theta

    return res_elev, rotated_phi


class LocalENUConverter():
    """
    This class receives a reference lat, lon, alt and may transform other coordinate types
    to local ENU
    """
    def __init__(self):
        # geodesical
        self.ref_lat = None
        self.ref_long = None
        self.ref_alt = None

        # cartesian
        self.ref_x = None
        self.ref_y = None
        self.ref_z = None

        # rotation matrix used
        self.translation = np.array([self.ref_x, self.ref_y, self.ref_z])
        self.rotation = None

    def validate(self):
        if None in [self.ref_lat, self.ref_long, self.ref_alt]:
            raise ValueError("You need to set a reference for coordinate transformation before using it")

    def set_reference(self, ref_lat: float, ref_long: float, ref_alt: float):
        self.ref_lat = ref_lat
        self.ref_long = ref_long
        self.ref_alt = ref_alt
        ref_x, ref_y, ref_z = lla2ecef(self.ref_lat, self.ref_long, self.ref_alt)
        self.ref_x = ref_x
        self.ref_y = ref_y
        self.ref_z = ref_z

        # ECEF considers xy plane with x axis pointing at lon = 0,
        # local coords considers x axis pointing towards East
        # and y pointing towards North

        # translate everything so ES is at (0, 0, 0)
        self.translation = np.array([self.ref_x, self.ref_y, self.ref_z])

        # considering:
        # - that by definition the vector pointing East
        #     is already orthogonal to ECEF z axis,
        #     in other words, it is fully contained in the ECEF xy plane;
        # Then, a single rotation around ECEF z can align local East and positive x
        # Local east and ECEF x axis are parallel and with same direction at long=-90
        # rotation around ECEF z = -90 - ref_lon
        rotation_around_z = -self.ref_long - 90

        # considering:
        # - that the local zenith is orthogonal to local east;
        # - that the local zenith unit vector can be found by using geodetic (lat, lon)
        #    as polar coordinates (as follows from geodetic lat, lon definition)
        # - that the local east is now fully contained in the x axis;
        # Then the local zenith is fully contained in the yz plane,
        # and a single rotation around the x axis aligns it with global z
        # More specifically, z_vec = polar(lat, ref_long - ref_long) = polar(lat, 0)
        # and so a rotation of 90 - lat is what is necessary
        rotation_around_x = self.ref_lat - 90

        # since ECEF follows left hand rule and local coordinates also do,
        # x axis points to local East and z points to local zenith,
        # y axis already is aligned with local North after transformation
        self.rotation = scipy.spatial.transform.Rotation.from_euler(
            'zx', [rotation_around_z, rotation_around_x], degrees=True
        )
        # can also be confirmed comparing to here:
        # https://gssc.esa.int/navipedia/index.php/Transformations_between_ECEF_and_ENU_coordinates

    def ecef2enu(
        self, x, y, z, *, translate=None
    ):
        """
        Transforms points by the same transformation required to bring reference to (0,0,0)
        You can only rotate by specifying translate=0
        """
        self.validate()
        
        translate_val = self.translation
        if translate is not None:
            translate_val = np.atleast_1d(translate)

        # broadcast translate to have same number of dimensions as expected
        xyz = np.stack([x,y,z], axis=-1) # Nx3

        xyz = xyz - translate_val[np.newaxis, :]

        # rotate so axis are same as ENU
        return self.rotation.apply(xyz).T

    def enu2ecef(
        self, x2, y2, z2, *, translate=None
    ):
        """
        Reverses transformed points by the same transformation required to bring reference to (0,0,0)
        You can only rotate by specifying translate=0. You need to use the same 'translate' value used
        in transformation if you wish to reverse the transformation correctly
        """
        self.validate()
        
        # translate everything so ES is at (0, 0, 0)
        translate_val = self.translation
        if translate is not None:
            translate_val = np.atleast_1d(translate)

        # broadcast translate to have same number of dimensions as expected
        xyz = np.stack([x2,y2,z2], axis=-1) # Nx3

        # rotate xyz back to ecef coord system
        xyz = self.rotation.apply(xyz, inverse=True)

        # translate earth reference back to its original ecef coord
        return (xyz + translate_val[np.newaxis, :]).T

    def lla2enu(
        self, lat: np.array, long: np.array, alt: np.array
    ):
        """
        You cannot transform this back to lla and expect something useful...
        This rotates and translates every point considering the reference that was set
        and a geodesical coordinate system
        """
        # get cartesian position by geodesical
        x, y, z = lla2ecef(lat, long, alt)

        return self.ecef2enu(x, y, z)

    def station_ecef2enu(
        self, station: StationManager, idx=None
    ) -> None:
        """
        In place rotate and translate all coordinates so that reference parameters end up in (0,0,0)
        and stations end up in same relative position according to each other,
        adapting their angles to the rotation.

        if idx is specified, only stations[idx] will be converted
        """
        if idx is None:
            nx, ny, nz = self.ecef2enu(station.x, station.y, station.z)
        else:
            nx, ny, nz = self.ecef2enu(station.x[idx], station.y[idx], station.z[idx])

        if idx is None:
            azim = station.azimuth
            elev = station.elevation
        else:
            azim = station.azimuth[idx]
            elev = station.elevation[idx]

        r = 1
        # then get pointing vec
        pointing_vec_x, pointing_vec_y, pointing_vec_z = polar_to_cartesian(r, azim, elev)

        # transform pointing vectors, without considering geodesical earth coord system
        pointing_vec_x, pointing_vec_y, pointing_vec_z = self.ecef2enu(
            pointing_vec_x, pointing_vec_y, pointing_vec_z, translate=0
        )

        if idx is None:
            station.x = nx
            station.y = ny
            station.z = nz

            _, station.azimuth, station.elevation = cartesian_to_polar(pointing_vec_x, pointing_vec_y, pointing_vec_z)
        else:
            station.x[idx] = nx
            station.y[idx] = ny
            station.z[idx] = nz

            _, azimuth, elevation = cartesian_to_polar(pointing_vec_x, pointing_vec_y, pointing_vec_z)

            station.azimuth[idx] = azimuth
            station.elevation[idx] = elevation

    def station_enu2ecef(
        self, station: StationManager, idx=None
    ) -> None:
        """
        In place rotate and translate all coordinates so that reference parameters end up in (0,0,0)
        and stations end up in same relative position according to each other,
        adapting their angles to the rotation.

        if idx is specified, only stations[idx] will be converted
        """
        # transform positions
        # print("(station.x, station.y, station.z)", (station.x[idx], station.y[idx], station.z[idx]))
        if idx is None:
            nx, ny, nz = self.enu2ecef(station.x, station.y, station.z)
        else:
            nx, ny, nz = self.enu2ecef(station.x[idx], station.y[idx], station.z[idx])

        if idx is None:
            azim = station.azimuth
            elev = station.elevation
        else:
            azim = station.azimuth[idx]
            elev = station.elevation[idx]

        r = 1
        # then get pointing vec
        pointing_vec_x, pointing_vec_y, pointing_vec_z = polar_to_cartesian(r, azim, elev)

        # transform pointing vectors, without considering geodesical earth coord system
        pointing_vec_x, pointing_vec_y, pointing_vec_z = self.enu2ecef(
            pointing_vec_x, pointing_vec_y, pointing_vec_z, translate=0
        )

        if idx is None:
            station.x = nx
            station.y = ny
            station.z = nz

            _, station.azimuth, station.elevation = cartesian_to_polar(pointing_vec_x, pointing_vec_y, pointing_vec_z)
        else:
            station.x[idx] = nx
            station.y[idx] = ny
            station.z[idx] = nz

            _, azimuth, elevation = cartesian_to_polar(pointing_vec_x, pointing_vec_y, pointing_vec_z)

            station.azimuth[idx] = azimuth
            station.elevation[idx] = elevation


def get_lambert_equal_area_crs(polygon: shp.geometry.Polygon):
    centroid = polygon.centroid
    return pyproj.CRS.from_user_input(
        f"+proj=laea +lat_0={centroid.y} +lon_0={centroid.x} +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )


def shrink_country_polygon_by_km(
    polygon: shp.geometry.Polygon, km: float
) -> shp.geometry.Polygon:
    """
    Projects a Polygon in "EPSG:4326" to Lambert Azimuthal Equal Area projection,
    shrinks the polygon by x km,
    projects the polygon back to EPSG:4326.

    Hint:
        Check for polygon validity after transformation:
        if poly.is_valid: raise Exception("bad polygon")
        if not poly.is_empty and poly.area > 0: continue # ignore
        ...
    """
    # Lambert is more precise, but could prob. get UTM projection
    # Didn't see any practical difference for current use cases
    proj_crs = get_lambert_equal_area_crs(polygon)

    # Create transformer objects
    # NOTE: important always_xy=True to not mix lat lon up order
    to_proj = pyproj.Transformer.from_crs("EPSG:4326", proj_crs, always_xy=True).transform
    from_proj = pyproj.Transformer.from_crs(proj_crs, "EPSG:4326", always_xy=True).transform

    # Transform to projection where unit is meters
    polygon_proj = shp.ops.transform(to_proj, polygon)

    # Shrink (negative buffer in meters)
    polygon_proj_shrunk = polygon_proj.buffer(-km * 1000)

    # Return to EPSG:4326
    return shp.ops.transform(from_proj, polygon_proj_shrunk)


def shrink_countries_by_km(
    countries: list[shp.geometry.MultiPolygon],
    km: float
) -> list[shp.geometry.MultiPolygon]:
    """
    Receives a MultiPolygon containing multiple countries
    and diminishes
    """
    polys = []

    for ext_poly in countries:
        if ext_poly.geom_type == 'Polygon':
            polys.append(shrink_country_polygon_by_km(ext_poly, km))
        elif ext_poly.geom_type == 'MultiPolygon':
            polys.append(shp.ops.unary_union([
                shrink_country_polygon_by_km(poly, km) for poly in ext_poly.geoms
            ]))

    for poly in polys:
        if not poly.is_valid:
            # may be ignorable..?
            # TODO: check if this error can be safely removed
            # If you need to look into this, plot the erroring scenario
            # drops and check to see if unexpected behavior occurs
            raise ValueError("SOME BAD POLYGON")

    return [
        poly for poly in polys if poly.is_valid and not poly.is_empty and poly.area > 0
    ]


if __name__ == "__main__":
    # baixo, direita, frente, esquerda, atrás, cima, cima
    # elev = np.array([-90., 0., 0., 0., 0., 90., 90.])
    # azim = np.array([0., 0., 90., 180., -90., 0., 90.])
    elev = np.array([-89.93761622])
    azim = np.array([180.])
    n = len(azim)

    # print("pointing nadir to the right (rotated around earth to the left)")
    # print(np.concatenate((elev, azim)).reshape((2, n)).transpose())
    # res_elev, res_az = rotate_angles_based_on_new_nadir(elev, azim, 0, 0)
    # res = np.concatenate((res_elev, res_az)).reshape((2, n)).transpose()
    # print(res)

    # print("pointing nadir to the left (rotated around earth to the right)")
    # print(np.concatenate((elev, azim)).reshape((2, n)).transpose())
    # res_elev, res_az = rotate_angles_based_on_new_nadir(elev, azim, 0, 180)
    # res = np.concatenate((res_elev, res_az)).reshape((2, n)).transpose()
    # print(res)

    # print(get_rotation_matrix_between_vecs(np.array([0,1,0]), np.array([0,0,1])))

    geoconv = LocalENUConverter()

    sys_lat = 89
    sys_long = 0
    sys_alt = 1200

    # geoconv.set_reference(
    #     sys_lat, sys_long, sys_alt
    # )
    # stat = StationManager(1)
    # # stat.x = np.array([-2000.])
    # # stat.y = np.array([0.])
    # stat.x = np.array([0.])
    # stat.y = np.array([-2000.])
    # stat.z = np.array([0.])
    # stat.elevation = 0
    # stat.azimuth = -90

    # print("stat.x", stat.x)
    # print("stat.y", stat.y)
    # print("stat.z", stat.z)

    # print("stat.azimuth", stat.azimuth)
    # print("stat.elevation", stat.elevation)
    # print("#########")
    # geoconv.station_enu2ecef(stat)
    # print("#########")

    # print("stat.x", stat.x)
    # print("stat.y", stat.y)
    # print("stat.z", stat.z)

    # print("stat.azimuth", stat.azimuth)
    # print("stat.elevation", stat.elevation)
