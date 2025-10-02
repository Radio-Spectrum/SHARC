# from sharc.support.sharc_geom import CoordinateSystem
# from sharc.satellite.utils.sat_utils import lla2ecef

import numpy as np
from abc import ABC


def readonly_properties(*fields):
    """
    Decorator to update 'field's to be readonly,
    and creates the private '_field's for mutations
    """
    def decorator(cls):
        for field in fields:
            private_name = f"_{field}"

            def getter(self, name=private_name):
                return getattr(self, name)
            setattr(cls, field, property(getter))
        return cls
    return decorator


# TODO: make these properties readonly
# @readonly_properties(
#     "x_global", "y_global", "z_global",
#     "pointn_azim_global", "pointn_elev_global",
#     "num_geometries"
# )
class GlobalGeometry(ABC):
    """
    Abstract class defining global simulator geometry implementation.
    """
    x_global: np.ndarray
    y_global: np.ndarray
    z_global: np.ndarray
    pointn_azim_global: np.ndarray
    pointn_elev_global: np.ndarray

    num_geometries: int

    # TODO: remove this from here
    # gambiarra_intersite_dist: float
    intersite_dist: float

    def setup(
        self,
        num_geometries,
    ):
        """
        Initializes variables based on number of geometries
        """
        self.x_global = np.empty(num_geometries)
        self.y_global = np.empty(num_geometries)
        self.z_global = np.empty(num_geometries)
        self.pointn_azim_global = np.empty(num_geometries)
        self.pointn_elev_global = np.empty(num_geometries)

        self.num_geometries = num_geometries

    def set_global_coords(
        self,
        x=None,
        y=None,
        z=None,
        azim=None,
        elev=None,
    ):
        """Set passed values to objects global coordinates.
        If None is passed, attribute will not be changed.
        """
        if x is not None:
            self.x_global = x
        if y is not None:
            self.y_global = y
        if z is not None:
            self.z_global = z
        if elev is not None:
            self.pointn_elev_global = elev
        if azim is not None:
            self.pointn_azim_global = azim

    def get_global_distance_to(self, other: "GlobalGeometry") -> np.array:
        """Calculate the 2D distance between this geometry and another
        considering their global (x,y)

        Parameters
        ----------
        other : GlobalGeometry
            GlobalGeometry to which the distance is calculated.

        Returns
        -------
        np.array
            2D distance matrix between others.
        """
        distance = np.empty([self.num_geometries, other.num_geometries])
        for i in range(self.num_geometries):
            distance[i] = np.sqrt(
                np.power(self.x_global[i] - other.x_global, 2) +
                np.power(self.y_global[i] - other.y_global, 2),
            )
        return distance

    def get_3d_distance_to(self, other: "GlobalGeometry") -> np.array:
        """Calculate the 3D distance between this manager's stations and another's.

        Parameters
        ----------
        other : GlobalGeometry
            GlobalGeometry to which the distance is calculated.

        Returns
        -------
        np.array
            3D distance matrix between stations.
        """
        dx = np.subtract.outer(self.x_global, other.x_global).astype(np.float64)
        dy = np.subtract.outer(self.y_global, other.y_global).astype(np.float64)
        dz = np.subtract.outer(self.z_global, other.z_global).astype(np.float64)
        np.square(dx, out=dx)
        np.square(dy, out=dy)
        np.square(dz, out=dz)
        np.sqrt(
            dx + dy + dz,
            out=dx
        )
        return dx

    def get_global_dist_angles_wrap_around(self, other) -> np.array:
        """Calculate distances and angles using the wrap-around technique.

        Parameters
        ----------
        other : GlobalGeometry
            GlobalGeometry to which distances and angles are calculated.

        Returns
        -------
        tuple
            distance_2D (np.array): 2D distance between stations
            distance_3D (np.array): 3D distance between stations
            phi (np.array): azimuth of pointing vector to other stations
            theta (np.array): elevation of pointing vector to other stations
        """
        if self._num_of_local_refs != 0 or other._num_of_local_refs != 0:
            raise ValueError("Wrap around was not implemented for local coord sys")
        # Initialize variables
        distance_3D = np.empty([self.num_geometries, other.num_geometries])
        distance_2D = np.inf * np.ones_like(distance_3D)
        cluster_num = np.zeros_like(distance_3D, dtype=int)

        # Cluster coordinates
        cluster_x = np.array([
            other.x_global,
            other.x_global + 3.5 * self.intersite_dist,
            other.x_global - 0.5 * self.intersite_dist,
            other.x_global - 4.0 * self.intersite_dist,
            other.x_global - 3.5 * self.intersite_dist,
            other.x_global + 0.5 * self.intersite_dist,
            other.x_global + 4.0 * self.intersite_dist,
        ])

        cluster_y = np.array([
            other.y_global,
            other.y_global + 1.5 *
            np.sqrt(3.0) * self.intersite_dist,
            other.y_global + 2.5 *
            np.sqrt(3.0) * self.intersite_dist,
            other.y_global + 1.0 *
            np.sqrt(3.0) * self.intersite_dist,
            other.y_global - 1.5 *
            np.sqrt(3.0) * self.intersite_dist,
            other.y_global - 2.5 *
            np.sqrt(3.0) * self.intersite_dist,
            other.y_global - 1.0 * np.sqrt(3.0) * self.intersite_dist,
        ])

        # Calculate 2D distance
        temp_distance = np.zeros_like(distance_2D)
        for k, (x, y) in enumerate(zip(cluster_x, cluster_y)):
            temp_distance = np.sqrt(
                np.power(x - self.x_global[:, np.newaxis], 2) +
                np.power(y - self.y_global[:, np.newaxis], 2),
            )
            is_shorter = temp_distance < distance_2D
            distance_2D[is_shorter] = temp_distance[is_shorter]
            cluster_num[is_shorter] = k

        # Calculate 3D distance
        distance_3D = np.sqrt(
            np.power(distance_2D, 2) +
            np.power(other.z_global - self.z_global[:, np.newaxis], 2),
        )

        # Calcualte pointing vector
        point_vec_x = cluster_x[cluster_num, np.arange(other.num_geometries)] \
            - self.x_global[:, np.newaxis]
        point_vec_y = cluster_y[cluster_num, np.arange(other.num_geometries)] \
            - self.y_global[:, np.newaxis]
        point_vec_z = other.z_global - self.z_global[:, np.newaxis]

        phi = np.array(
            np.rad2deg(
                np.arctan2(
                    point_vec_y, point_vec_x,
                ),
            ), ndmin=2,
        )
        theta = np.rad2deg(np.arccos(point_vec_z / distance_3D))

        return distance_2D, distance_3D, phi, theta

    def get_global_elevation(self, other: "GlobalGeometry") -> np.array:
        """Calculate the elevation angle between this manager's stations and another's.

        Parameters
        ----------
        other : GlobalGeometry
            GlobalGeometry to which the elevation angle is calculated.

        Returns
        -------
        np.array
            Elevation angle matrix (degrees).
        """
        elevation = np.empty([self.num_geometries, other.num_geometries])

        for i in range(self.num_geometries):
            distance = np.sqrt(
                np.power(self.x_global[i] - other.x_global, 2) +
                np.power(self.y_global[i] - other.y_global, 2),
            )
            rel_z = other.z_global - self.z_global[i]
            elevation[i] = np.degrees(np.arctan2(rel_z, distance))

        return elevation

    def get_global_pointing_vector_to(self, other: "GlobalGeometry") -> tuple:
        """Calculate the pointing vector (angles) with respect to another other.

        Parameters
        ----------
        other : GlobalGeometry
            The other GlobalGeometry to calculate the pointing vector to.

        Returns
        -------
        tuple
            phi, theta (phi is calculated with respect to x counter-clockwise and
            theta is calculated with respect to z counter-clockwise).
        """

        # malloc
        dx = (other.x_global - self.x_global[:, np.newaxis]).astype(np.float64)
        dy = (other.y_global - self.y_global[:, np.newaxis]).astype(np.float64)
        dz = (other.z_global - self.z_global[:, np.newaxis]).astype(np.float64)

        dist = self.get_3d_distance_to(other)

        # NOTE: doing in place calculations
        phi = np.rad2deg(np.arctan2(dy, dx, out=dx), out=dx)
        # delete reference dx
        del dx

        # in place calculations
        theta = np.rad2deg(np.arccos(np.clip(dz / dist, -1.0, 1.0, out=dz), out=dz), out=dz)
        # delete reference dz
        del dz

        return phi, theta

    def get_off_axis_angle(self, other: "GlobalGeometry") -> np.array:
        """Calculate the off-axis angle between this manager's stations and another's.

        Parameters
        ----------
        other : GlobalGeometry
            The other GlobalGeometry to calculate the off-axis angle to.

        Returns
        -------
        np.array
            Off-axis angle matrix (degrees).
        """
        Az, b = self.get_global_pointing_vector_to(other)
        Az0 = self.pointn_azim_global

        a = 90 - self.pointn_elev_global[:, np.newaxis]
        C = Az0[:, np.newaxis] - Az

        cos_phi = np.cos(np.radians(a)) * np.cos(np.radians(b)) \
            + np.sin(np.radians(a)) * np.sin(np.radians(b)) * np.cos(np.radians(C))
        phi = np.arccos(
            # imprecision may accumulate enough for numbers to be slightly out
            # of arccos range
            np.clip(cos_phi, -1., 1.)
        )
        phi_deg = np.degrees(phi)

        return phi_deg


@readonly_properties(
    "x_local", "y_local", "z_local",
    "pointn_azim_local", "pointn_elev_local",
    "global_lla_reference"
)
class SimulatorGeometry(GlobalGeometry):
    """
    Class with simplified coordinate system operations.
    Just global and local conversion.
    """
    # N = num of geometries
    # M = num of local references
    # M < N
    x_local: np.ndarray            # (M,)
    y_local: np.ndarray            # (M,)
    z_local: np.ndarray            # (M,)
    pointn_azim_local: np.ndarray  # (M,)
    pointn_elev_local: np.ndarray  # (M,)

    __local_lla_references: np.ndarray[np.ndarray[float]]  # (3, M)
    global_lla_reference: tuple[float, float, float]

    _num_of_local_refs: int  # M
    _geometry_reference_i: np.ndarray[int]  # (N,)

    def __init__(
        self,
        num_geometries,
        num_of_local_refs=0,
        global_cs: tuple[float, float, float] = None,
    ):
        """
        Initialize a geometry object with a global coordinate system
        and defining how many local coordinate systems should exist
        """
        # super().__init__(num_geometries)
        self.setup(
            num_geometries,
            num_of_local_refs,
            global_cs,
        )

    def setup(
        self,
        num_geometries,
        num_of_local_refs=0,
        global_cs: tuple[float, float, float] = None,
    ):
        """
        Initializes variables based on number of geometries considered
        """
        super().setup(num_geometries)

        self.__global_coord_sys = global_cs
        self._num_of_local_refs = num_of_local_refs

        if num_of_local_refs == 0:
            self.uses_local_coords = False
            self._x_local = None
            self._y_local = None
            self._z_local = None
            self._pointn_azim_local = None
            self._pointn_elev_local = None
            return
        elif global_cs is None:
            raise ValueError(
                "If there will be a local ref, global coord sys must be passed"
            )

        self._x_local = np.empty(num_geometries)
        self._y_local = np.empty(num_geometries)
        self._z_local = np.empty(num_geometries)
        self._pointn_azim_local = np.empty(num_geometries)
        self._pointn_elev_local = np.empty(num_geometries)

    def set_local_coord_sys(
        self,
        ref_lats,
        ref_lons,
        ref_alts,
    ):
        """

        """
        for r in [ref_lats, ref_lons, ref_alts]:
            if len(r) != self._num_of_local_refs:
                raise ValueError(
                    "Incongruent number of coordinate systems. "
                    f"Passed {len(r)} but should have passed {len(self._num_of_local_refs)}"
                )
        self.__local_lla_references = np.stack((ref_lats, ref_lons, ref_alts))

    def set_local_coords(
        self,
        x=None,
        y=None,
        z=None,
        azim=None,
        elev=None,
    ):
        """Set values to local coordinate values.
        If None is passed, attribute will not be updated.
        """
        if x is not None:
            self.x_local = x
        if y is not None:
            self.y_local = y
        if z is not None:
            self.z_local = z
        if elev is not None:
            self.pointn_elev_local = elev
        if azim is not None:
            self.pointn_azim_local = azim

    # def _compute_local_to_global_transf(self):
    #     return
        # local_lat, local_lon, local_alt = self.__local_lla_references
        # rotation_around_z = -local_lon - 90
        # rotation_around_x = local_lat - 90

        # self.rotation = scipy.spatial.transform.Rotation.from_euler(
        #     'zx',
        #     np.stack([rotation_around_z, rotation_around_x], axis=-1),
        #     degrees=True
        # )
        # # (M,3,3) or (3,3)
        # rot_mtx = self.rotation.as_matrix()
        # if rot_mtx.ndim == 2:
        #     # guarantee (M, 3, 3)
        #     rot_mtx = rot_mtx[None, ...]
        # # broadcastable (M, 1, 3, 3)
        # self.rotation_mtx = rot_mtx[:, None, :, :]

        # inv_rot_mtx = self.rotation.inv().as_matrix()
        # if inv_rot_mtx.ndim == 2:
        #     # guarantee (M, 3, 3)
        #     inv_rot_mtx = inv_rot_mtx[None, ...]
        # # broadcastable (M, 1, 3, 3)
        # self.inv_rotation_mtx = inv_rot_mtx[:, None, :, :]

    def get_local_distance_to(self, other: "SimulatorGeometry") -> np.array:
        """Calculate the 2D distance between this manager's stations and another's
        considering this ones coordinate system

        Parameters
        ----------
        station : StationManager
            StationManager to which the distance is calculated.

        Returns
        -------
        np.array
            2D distance matrix between stations.
        """
        if not self.uses_local_coords:
            return self.get_global_distance_to(other)
        # TODO: 2d distance calculation
        raise NotImplementedError()

    def get_local_elevation(self, other: "SimulatorGeometry") -> np.array:
        """Calculate the elevation angle between this manager's stations and another's
        considering this one's loca coordinate system

        Parameters
        ----------
        other : GlobalAndLocalGeometry
            GlobalAndLocalGeometry to which the elevation angle is calculated.

        Returns
        -------
        np.array
            Elevation angle matrix (degrees).
        """
        if not self.uses_local_coords:
            return self.get_global_elevation(other)

        raise NotImplementedError()


# \.(get_global_distance_to|get_3d_distance_to|get_global_dist_angles_wrap_around|get_global_elevation|get_global_pointing_vector_to|get_off_axis_angle)
