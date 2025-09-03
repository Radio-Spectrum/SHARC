import numpy as np
import shapely as shp
import shapely.vectorized
import pyproj
import scipy.spatial.transform
import typing

from sharc.satellite.utils.sat_utils import lla2ecef
from sharc.station_manager import StationManager
from sharc.support.sharc_utils import to_scalar
from sharc.satellite.ngso.constants import EARTH_RADIUS_M, EARTH_DEFAULT_CRS, EARTH_SPHERICAL_CRS


def cartesian_to_polar(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    """Convert cartesian coordinates to polar coordinates (range, azimuth, elevation).

    Parameters
    ----------
    x : np.ndarray
        X coordinate(s) in meters.
    y : np.ndarray
        Y coordinate(s) in meters.
    z : np.ndarray
        Z coordinate(s) in meters.

    Returns
    -------
    tuple
        Tuple of (range, azimuth in degrees, elevation in degrees).
    """
    # range calculation
    r = np.sqrt(x**2 + y**2 + z**2)

    # azimuth calculation
    azimuth = np.arctan2(y, x)

    # elevation calculation
    elevation = np.arcsin(z / r)

    return r, np.degrees(azimuth), np.degrees(elevation)


def polar_to_cartesian(
        r: np.ndarray,
        azimuth: np.ndarray,
        elevation: np.ndarray) -> tuple:
    """Convert polar coordinates to cartesian coordinates.

    Parameters
    ----------
    r : np.ndarray
        Range in meters.
    azimuth : np.ndarray
        Azimuth in degrees.
    elevation : np.ndarray
        Elevation in degrees.

    Returns
    -------
    tuple
        x, y, and z coordinates in meters.
    """
    azimuth = np.radians(azimuth)
    elevation = np.radians(elevation)
    x = r * np.cos(elevation) * np.cos(azimuth)
    y = r * np.cos(elevation) * np.sin(azimuth)
    z = r * np.sin(elevation)

    return x, y, z


def get_rotation_matrix(around_z, around_y):
    """Return rotation matrix for right-hand rule around z and y axes.

    Rotates with the right-hand rule around the z axis (azimuth) and y axis (elevation).

    Parameters
    ----------
    around_z : float
        Angle in degrees to rotate around the z axis (azimuth).
    around_y : float
        Angle in degrees to rotate around the y axis (elevation).

    Returns
    -------
    np.matrix
        The combined rotation matrix.
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
    """Rotate elevation and azimuth so that base_elev and base_azim are at 0 deg.

    Receives elevation and azimuth arrays, rotates around base so that base_elev and base_azim are at 0 deg,
    with elevation being 0 at the horizon (xy plane) and azimuth 0 at the x axis.

    Parameters
    ----------
    elev : array-like
        Elevation angles in degrees.
    azim : array-like
        Azimuth angles in degrees.
    nadir_elev : float
        Reference elevation (nadir) in degrees.
    nadir_azim : float
        Reference azimuth (nadir) in degrees.

    Returns
    -------
    tuple
        Rotated elevation and azimuth arrays (xy plane elevation).
    """
    # translating to normal polar coordinate system, with theta being angle from z axis
    # and phi being angle from x axis in the xy plane
    nadir_theta = 90 - nadir_elev
    nadir_phi = nadir_azim

    # nadir_point = np.matrix([
    #     np.sin(np.deg2rad(nadir_theta)) * np.cos(np.deg2rad(nadir_phi)),
    #     np.sin(np.deg2rad(nadir_theta)) * np.sin(np.deg2rad(nadir_phi)),
    #     np.cos(np.deg2rad(nadir_theta)),
    # ])
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


# NOTE: this works for both spherical an ellipsoidal Earth,
# just need to change ecef2lla and lla2ecef implementations
# TODO: refactor class and method names
class GeometryConverter():
    """Class for transforming coordinates to local ENU using a reference lat, lon, alt.

    This class receives a reference lat, lon, alt and may transform other coordinate types to local ENU.
    """

    def __init__(self):
        """Initialize GeometryConverter with unset reference coordinates."""
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

    def get_translation(self):
        """Return the translation value for the reference altitude and Earth's radius."""
        """Return the translation value for the reference altitude.

        Returns
        -------
        float
            The sum of the reference altitude and Earth's radius in meters.
        """
        return self.ref_alt + EARTH_RADIUS_M

    def validate(self):
        """Validate that the reference coordinates for transformation are set."""
        """Validate that the reference for coordinate transformation is set.

        Raises
        ------
        ValueError
            If the reference latitude, longitude, or altitude is not set.
        """
        if None in [self.ref_lat, self.ref_long, self.ref_alt]:
            raise ValueError(
                "You need to set a reference for coordinate transformation before using it")

    def set_reference(self, ref_lat: float, ref_long: float, ref_alt: float):
        """Set the reference latitude, longitude, and altitude for coordinate transformation."""
        """Set the reference latitude, longitude, and altitude for coordinate transformation.

        Parameters
        ----------
        ref_lat : float
            Reference latitude in degrees.
        ref_long : float
            Reference longitude in degrees.
        ref_alt : float
            Reference altitude in meters.
        """
        self.ref_lat = to_scalar(ref_lat)
        self.ref_long = to_scalar(ref_long)
        self.ref_alt = to_scalar(ref_alt)
        ref_x, ref_y, ref_z = lla2ecef(
            self.ref_lat, self.ref_long, self.ref_alt)
        self.ref_x = to_scalar(ref_x)
        self.ref_y = to_scalar(ref_y)
        self.ref_z = to_scalar(ref_z)

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

    def convert_cartesian_to_transformed_cartesian(
        self, x, y, z, *, translate=None
    ):
        """Transform points by the same transformation required to bring reference to (0,0,0).

        You can only rotate by specifying translate=0.

        Parameters
        ----------
        x, y, z : array-like
            Cartesian coordinates to transform.
        translate : array-like or None, optional
            Translation vector to use (default: use reference translation).

        Returns
        -------
        np.ndarray
            Transformed coordinates.
        """
        self.validate()

        translate_val = self.translation
        if translate is not None:
            translate_val = np.atleast_1d(translate)

        # broadcast translate to have same number of dimensions as expected
        xyz = np.stack([x, y, z], axis=-1)  # Nx3

        rshp = (xyz.ndim - 1) * (1,) + translate_val.shape
        xyz = xyz - translate_val.reshape(rshp)

        # rotate so axis are same as ENU
        return self.rotation.apply(xyz).T

    def revert_transformed_cartesian_to_cartesian(
        self, x2, y2, z2, *, translate=None
    ):
        """Reverse transformed points by the same transformation required to bring reference to (0,0,0).

        You can only rotate by specifying translate=0. You need to use the same 'translate' value used
        in transformation if you wish to reverse the transformation correctly.

        Parameters
        ----------
        x2, y2, z2 : array-like
            Transformed cartesian coordinates to revert.
        translate : array-like or None, optional
            Translation vector to use (default: use reference translation).

        Returns
        -------
        np.ndarray
            Reverted coordinates.
        """
        self.validate()

        # translate everything so ES is at (0, 0, 0)
        translate_val = self.translation
        if translate is not None:
            translate_val = np.atleast_1d(translate)

        # broadcast translate to have same number of dimensions as expected
        xyz = np.stack([x2, y2, z2], axis=-1)  # Nx3

        # rotate xyz back to ecef coord system
        xyz = self.rotation.apply(xyz, inverse=True)

        # translate earth reference back to its original ecef coord
        return (xyz + translate_val[np.newaxis, :]).T

    def convert_lla_to_transformed_cartesian(
        self, lat: np.array, long: np.array, alt: np.array
    ):
        """Convert latitude, longitude, altitude to transformed cartesian coordinates.

        This rotates and translates every point considering the reference that was set
        and a geodesical coordinate system.

        Parameters
        ----------
        lat : np.array
            Latitude values.
        long : np.array
            Longitude values.
        alt : np.array
            Altitude values.

        Returns
        -------
        np.ndarray
            Transformed cartesian coordinates.
        """
        # get cartesian position by geodesical
        x, y, z = lla2ecef(lat, long, alt)

        return self.convert_cartesian_to_transformed_cartesian(x, y, z)

    def convert_station_3d_to_2d(
        self, station: StationManager, idx=None
    ) -> None:
        """In-place rotate and translate all coordinates so that reference parameters end up in (0,0,0).

        Stations end up in the same relative position according to each other, adapting their angles to the rotation.
        If idx is specified, only stations[idx] will be converted.

        Parameters
        ----------
        station : StationManager
            The station manager whose stations will be transformed.
        idx : array-like or None, optional
            Indices of stations to convert (default: all).
        """
        # transform positions
        if idx is None:
            nx, ny, nz = self.convert_cartesian_to_transformed_cartesian(
                station.x, station.y, station.z)
        else:
            nx, ny, nz = self.convert_cartesian_to_transformed_cartesian(
                station.x[idx], station.y[idx], station.z[idx])

        if idx is None:
            azim = station.azimuth
            elev = station.elevation
        else:
            azim = station.azimuth[idx]
            elev = station.elevation[idx]

        r = 1
        # then get pointing vec
        pointing_vec_x, pointing_vec_y, pointing_vec_z = polar_to_cartesian(
            r, azim, elev)

        # transform pointing vectors, without considering geodesical earth
        # coord system
        pointing_vec_x, pointing_vec_y, pointing_vec_z = self.convert_cartesian_to_transformed_cartesian(
            pointing_vec_x, pointing_vec_y, pointing_vec_z, translate=0)

        if idx is None:
            station.x = nx
            station.y = ny
            station.z = nz

            _, station.azimuth, station.elevation = cartesian_to_polar(
                pointing_vec_x, pointing_vec_y, pointing_vec_z)
        else:
            station.x[idx] = nx
            station.y[idx] = ny
            station.z[idx] = nz

            _, azimuth, elevation = cartesian_to_polar(
                pointing_vec_x, pointing_vec_y, pointing_vec_z)

            station.azimuth[idx] = azimuth
            station.elevation[idx] = elevation

    def revert_station_2d_to_3d(
        self, station: StationManager, idx=None
    ) -> None:
        """In-place rotate and translate all coordinates so that reference parameters end up in (0,0,0).

        Stations end up in the same relative position according to each other, adapting their angles to the rotation.
        If idx is specified, only stations[idx] will be converted.

        Parameters
        ----------
        station : StationManager
            The station manager whose stations will be transformed.
        idx : array-like or None, optional
            Indices of stations to convert (default: all).
        """
        # transform positions
        if idx is None:
            nx, ny, nz = self.revert_transformed_cartesian_to_cartesian(
                station.x, station.y, station.z)
        else:
            nx, ny, nz = self.revert_transformed_cartesian_to_cartesian(
                station.x[idx], station.y[idx], station.z[idx])

        if idx is None:
            azim = station.azimuth
            elev = station.elevation
        else:
            azim = station.azimuth[idx]
            elev = station.elevation[idx]

        r = 1
        # then get pointing vec
        pointing_vec_x, pointing_vec_y, pointing_vec_z = polar_to_cartesian(
            r, azim, elev)

        # transform pointing vectors, without considering geodesical earth
        # coord system
        pointing_vec_x, pointing_vec_y, pointing_vec_z = self.revert_transformed_cartesian_to_cartesian(
            pointing_vec_x, pointing_vec_y, pointing_vec_z, translate=0)

        if idx is None:
            station.x = nx
            station.y = ny
            station.z = nz

            _, station.azimuth, station.elevation = cartesian_to_polar(
                pointing_vec_x, pointing_vec_y, pointing_vec_z)
        else:
            station.x[idx] = nx
            station.y[idx] = ny
            station.z[idx] = nz

            _, azimuth, elevation = cartesian_to_polar(
                pointing_vec_x, pointing_vec_y, pointing_vec_z)

            station.azimuth[idx] = azimuth
            station.elevation[idx] = elevation


def get_lambert_equal_area_crs(polygon: shp.geometry.Polygon):
    """Return a Lambert Azimuthal Equal Area CRS centered on the polygon centroid.

    Parameters
    ----------
    polygon : shp.geometry.Polygon
        Polygon to center the projection on.

    Returns
    -------
    pyproj.CRS
        Lambert Azimuthal Equal Area CRS.
    """
    if EARTH_DEFAULT_CRS == "EPSG:4326":
        datum = "+datum=WGS84"
    elif EARTH_DEFAULT_CRS == EARTH_SPHERICAL_CRS:
        datum = f"+a={EARTH_RADIUS_M} +b={EARTH_RADIUS_M}"
    centroid = polygon.centroid
    return pyproj.CRS.from_user_input(
        f"+proj=laea +lat_0={centroid.y} +lon_0={centroid.x} +x_0=0 +y_0=0 {datum} +units=m +no_defs"
    )


def shrink_country_polygon_by_km(
    polygon: shp.geometry.Polygon, km: float
) -> shp.geometry.Polygon:
    """Project a Polygon to Lambert Azimuthal Equal Area, shrink by km, and reproject back.

    Projects a Polygon in EARTH_DEFAULT_CRS to Lambert Azimuthal Equal Area projection,
    shrinks the polygon by x km, and projects the polygon back to EARTH_DEFAULT_CRS.

    Parameters
    ----------
    polygon : shp.geometry.Polygon
        Polygon to shrink.
    km : float
        Number of kilometers to shrink the polygon by.

    Returns
    -------
    shp.geometry.Polygon
        The shrunken polygon in EARTH_DEFAULT_CRS.

    Notes
    -----
    Check for polygon validity after transformation:
        if poly.is_valid: raise Exception("bad polygon")
        if not poly.is_empty and poly.area > 0: continue # ignore
    """
    # Lambert is more precise, but could prob. get UTM projection
    # Didn't see any practical difference for current use cases
    proj_crs = get_lambert_equal_area_crs(polygon)

    # Create transformer objects
    # NOTE: important always_xy=True to not mix lat lon up order
    to_proj = pyproj.Transformer.from_crs(
        EARTH_DEFAULT_CRS, proj_crs, always_xy=True).transform
    from_proj = pyproj.Transformer.from_crs(
        proj_crs, EARTH_DEFAULT_CRS, always_xy=True).transform

    # Transform to projection where unit is meters
    polygon_proj = shp.ops.transform(to_proj, polygon)

    # Shrink (negative buffer in meters)
    polygon_proj_shrunk = polygon_proj.buffer(-km * 1000)

    # Return to EARTH_DEFAULT_CRS
    return shp.ops.transform(from_proj, polygon_proj_shrunk)


def shrink_countries_by_km(
    countries: list[shp.geometry.MultiPolygon],
    km: float
) -> list[shp.geometry.MultiPolygon]:
    """Shrink all countries in a list of MultiPolygons by a given number of kilometers.

    Parameters
    ----------
    countries : list of shp.geometry.MultiPolygon
        List of country polygons to shrink.
    km : float
        Number of kilometers to shrink each country by.

    Returns
    -------
    list of shp.geometry.MultiPolygon
        List of shrunken country polygons.
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


def generate_grid_in_polygon(
    polygon: shp.geometry.Polygon,
    hexagon_radius: float,
    rotation_deg: typing.Optional[float] = None,
    translation: typing.Optional[typing.Tuple[float, float]] = None,
):
    """Generate a hexagonal grid inside a polygon and return points in EARTH_DEFAULT_CRS.

    Projects a Polygon in EARTH_DEFAULT_CRS to Lambert Azimuthal Equal Area projection,
    creates a hexagonal grid inside the polygon, where the points are in the hexagon center,
    and projects the points back to EARTH_DEFAULT_CRS.

    Parameters
    ----------
    polygon : shp.geometry.Polygon
        Polygon to fill with a grid.
    hexagon_radius : float
        Radius of the hexagons in the grid (in meters).

    Returns
    -------
    np.ndarray
        Array with shape (2, N): longitude in first row, latitude in second row.
    """
    if hexagon_radius < 0:
        raise ValueError(
            "generate_grid_in_polygon.hexagon radius must be positive")
    # Lambert is more precise, but could prob. get UTM projection
    # Didn't see any practical difference for current use cases
    proj_crs = get_lambert_equal_area_crs(polygon)

    # Create transformer objects
    # NOTE: important always_xy=True to not mix lat lon up order
    to_proj = pyproj.Transformer.from_crs(
        EARTH_DEFAULT_CRS, proj_crs, always_xy=True).transform
    from_proj = pyproj.Transformer.from_crs(
        proj_crs, EARTH_DEFAULT_CRS, always_xy=True).transform

    # Transform to projection where unit is meters
    polygon_proj = shp.ops.transform(to_proj, polygon)

    # Determine x/y spacing
    x_spacing = 3 * hexagon_radius
    y_spacing = hexagon_radius * np.sqrt(3) / 2

    # Create a bounding circle, afterwards we filter to polygon site
    cx, cy = polygon_proj.centroid.coords[0]
    minx, miny, maxx, maxy = polygon_proj.bounds
    bbox_diag = np.hypot(maxx - minx, maxy - miny)
    bound_radius = bbox_diag / 2 + 3 * hexagon_radius

    x_vals = np.arange(cx - bound_radius, cx + bound_radius + x_spacing, x_spacing)
    y_vals = np.arange(cy - bound_radius, cy + bound_radius + y_spacing, y_spacing)

    x_vals, y_vals = np.meshgrid(x_vals, y_vals)

    # dislocate every i%2==0 row to create a hexagonal grid
    x_vals[::2] += x_spacing / 2

    x_vals = x_vals.ravel()
    y_vals = y_vals.ravel()

    if rotation_deg is not None:
        theta = np.deg2rad(rotation_deg)
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        x_rot = cos_t * (x_vals - cx) - sin_t * (y_vals - cy) + cx
        y_rot = sin_t * (x_vals - cx) + cos_t * (y_vals - cy) + cy
        x_vals, y_vals = x_rot, y_rot

    if translation is not None:
        dx, dy = translation
        if abs(dx) > x_spacing or abs(dy) > y_spacing:
            raise ValueError("generate_grid_in_polygon.translation (dx, dy) must be positive")
        x_vals += dx
        y_vals += dy

    # Return to EARTH_DEFAULT_CRS
    xt, yt = from_proj(x_vals, y_vals)

    # we buffer the polygon very slightly to include points
    # right on the border of the polygon
    polygon = polygon.buffer(1e-9)
    msk = shp.vectorized.contains(polygon, xt, yt)
    xt = xt[msk]
    yt = yt[msk]

    return np.stack((xt, yt))


def generate_grid_in_multipolygon(
    poly: typing.Union[shp.geometry.MultiPolygon, shp.geometry.Polygon],
    km: float,
    random_transform_on_grid: bool = False,
    rng: np.random.RandomState = None,
) -> list[shp.geometry.MultiPolygon]:
    """Generate a hexagonal grid in a MultiPolygon or Polygon,
    considering a hexagon radius in km.

    For each polygon, create a grid and return a single 2xN array of longitudes and latitudes
    containing all grids.

    Parameters
    ----------
    poly : typing.Union[shp.geometry.MultiPolygon, shp.geometry.Polygon]
        The MultiPolygon or Polygon to process.
    km : float
        Hexagon radius in km

    Returns
    -------
    np.ndarray
        2xN array: first row is longitudes, second row is latitudes.
    """
    if random_transform_on_grid:
        assert rng is not None

    lons = []
    lats = []

    if poly.geom_type == 'Polygon':
        if random_transform_on_grid:
            x, y = generate_grid_in_polygon(
                poly, km,
                rng.uniform(-180., 180.),
                (
                    3 * rng.uniform(-km, km),
                    rng.uniform(-km, km) * np.sqrt(3) / 2
                )
            )
        else:
            x, y = generate_grid_in_polygon(poly, km)
        lons.extend(x)
        lats.extend(y)
    elif poly.geom_type == 'MultiPolygon':
        for p in poly.geoms:
            if random_transform_on_grid:
                x, y = generate_grid_in_polygon(
                    p, km,
                    rng.uniform(-180., 180.),
                    (
                        3 * rng.uniform(-km, km),
                        rng.uniform(-km, km) * np.sqrt(3) / 2
                    )
                )
            else:
                x, y = generate_grid_in_polygon(p, km)

            lons.extend(x)
            lats.extend(y)

    return np.stack((lons, lats))


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

    geoconv = GeometryConverter()

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
    # geoconv.convert_station_3d_to_2d(stat)
    # print("#########")

    # print("stat.x", stat.x)
    # print("stat.y", stat.y)
    # print("stat.z", stat.z)

    # print("stat.azimuth", stat.azimuth)
    # print("stat.elevation", stat.elevation)
