# from sharc.support.sharc_geom import CoordinateSystem
# from sharc.satellite.utils.sat_utils import lla2ecef

from sharc.satellite.ngso.constants import EARTH_RADIUS_M
from sharc.support.sharc_geom import cartesian_to_polar, polar_to_cartesian
import scipy
import numpy as np
from dataclasses import dataclass
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


@readonly_properties(
    "x_global", "y_global", "z_global",
    "pointn_azim_global", "pointn_elev_global",
    "num_geometries"
)
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

    intersite_dist: float

    def setup(
        self,
        num_geometries,
    ):
        """
        Initializes variables based on number of geometries
        """
        self._x_global = np.empty(num_geometries)
        self._y_global = np.empty(num_geometries)
        self._z_global = np.empty(num_geometries)
        self._pointn_azim_global = np.empty(num_geometries)
        self._pointn_elev_global = np.empty(num_geometries)

        self._num_geometries = num_geometries

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
            self._x_global = x
        if y is not None:
            self._y_global = y
        if z is not None:
            self._z_global = z
        if elev is not None:
            self._pointn_elev_global = elev
        if azim is not None:
            self._pointn_azim_global = azim

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
        if self.uses_local_coords or other.uses_local_coords:
            raise NotImplementedError(
                "Wrap around was not implemented for local coord sys"
            )
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


@dataclass(frozen=True)
class RigidTransform:
    """
    Defines a transformation of the type
        A(X) = rot @ X + t
    where it applies rotation to X and then translates the result.
    """
    rot: scipy.spatial.transform.Rotation  # N rotations
    t: np.ndarray                          # (N, 3)

    def __post_init__(self):
        if not isinstance(self.rot, scipy.spatial.transform.Rotation):
            raise ValueError("rot must be a scipy Rotation")

        # NOTE: this throws if the rotation isn't defined as a batch rotation
        n_rot = len(self.rot)
        n_t = self.t.shape[0]

        if self.t.shape != (n_t, 3):
            raise ValueError(f"Invalid transform shape t={n_t}")

        # if some is equal to one, broadcasting still works
        if not (n_rot == n_t or n_rot == 1 or n_t == 1):
            raise ValueError(
                f"Incompatible RigidTransform shapes: rot={n_rot}, t={n_t}"
            )
        self.t.flags.writeable = False

    @property
    def N(self):
        """Number of transforms represented"""
        n_rot = len(self.rot)
        n_t = self.t.shape[0]
        return max(n_rot, n_t)

    def inv(self) -> "RigidTransform":
        """Returns the inverse transform"""
        rot_inv = self.rot.inv()
        t_inv = -rot_inv.apply(self.t)
        return RigidTransform(rot_inv, t_inv)

    def and_then(self, other: "RigidTransform") -> "RigidTransform":
        """Apply self, then other (composition: other @ self)."""
        return RigidTransform(
            rot=other.rot * self.rot,
            t=other.rot.apply(self.t) + other.t
        )

    def take(self, idx: int) -> "RigidTransform":
        """Takes the idx-th transform from the batch"""
        # NOTE: we slice instead of taking indice to maintain
        # array shape structure for functional broadcasting
        # and batch computing
        return RigidTransform(
            rot=self.rot[idx:idx + 1],
            t=self.t[idx:idx + 1],
        )

    def apply_points(self, x: np.ndarray) -> np.ndarray:
        """Applies transform to the points.

        Parameters
        ----------
        x : np.ndarray
            Array of input points of shape (N, 3). Each row is a 3D point in
            Cartesian coordinates.

        Returns
        -------
        np.ndarray
            Array of transformed points of shape (N, 3), where ``N`` is the
            number of transforms represented by this ``RigidTransform``.
        """
        return self.apply_vectors(x) + self.t

    def apply_points_permutation(self, x: np.ndarray) -> np.ndarray:
        """Applies transform to points with permutation broadcasting.

        Parameters
        ----------
        x : np.ndarray
            Array of input points of shape (M, 3). Each row is a 3D point in
            Cartesian coordinates.

        Returns
        -------
        np.ndarray
            Array of transformed points of shape (N, M, 3), where ``N`` is the
            number of transforms represented by this ``RigidTransform``. The
            slice ``result[n, :, :]`` contains all ``M`` input points
            transformed by the ``n``-th rigid transform.
        """
        t = self.t                     # (N,3)

        return self.apply_vectors_permutation(x) + t[:, None, :]

    def apply_vectors(self, v: np.ndarray) -> np.ndarray:
        """Applies transform rotation-only to the points.

        Parameters
        ----------
        x : np.ndarray
            Array of input points of shape (N, 3). Each row is a 3D point in
            Cartesian coordinates.

        Returns
        -------
        np.ndarray
            Array of rotated points of shape (N, 3), where ``N`` is the
            number of transforms represented by this ``RigidTransform``.

        Note
        ----
        This only applies rotation, it ignores translation. It is useful for
        transforming pointing vectors.
        """
        v = np.atleast_2d(v)
        assert v.ndim == 2 and v.shape[1] == 3
        M = v.shape[0]
        assert self.N == 1 or M == 1 or M == self.N

        return self.rot.apply(v) + np.zeros_like(self.t)

    def apply_vectors_permutation(self, v: np.ndarray) -> np.ndarray:
        """Applies rotation-only to points with permutation broadcasting.

        Parameters
        ----------
        x : np.ndarray
            Array of input points of shape (M, 3). Each row is a 3D point in
            Cartesian coordinates.

        Returns
        -------
        np.ndarray
            Array of transformed points of shape (N, M, 3), where ``N`` is the
            number of transforms represented by this ``RigidTransform``. The
            slice ``result[n, :, :]`` contains all ``M`` input points
            transformed by the ``n``-th rigid transform rotation.

        Note
        ----
        This only applies rotation, it ignores translation. It is useful for
        transforming pointing vectors.
        """
        v = np.atleast_2d(v)
        assert v.ndim == 2 and v.shape[1] == 3

        # (N,3,3)
        R = self.rot.as_matrix()

        # einsum: (N,3,3) . (M,3) -> (N,M,3)
        return (
            np.einsum("nij,mj->nmi", R, v)
            + np.zeros_like(self.t)[:, None, :]
        )


class ReferenceFrame(ABC):
    """
    Defines a reference frame, which generates a rigid transform
    between ecef and its own local coordinate system.
    It should be noted that, while this may define axis position,
    the bearing considered (azimuth, elevation) for calculations
    CANNOT USE NAVIGATION CONVENTION.
    """
    __slots__ = ('_from_ecef', '_to_ecef')

    @property
    def from_ecef(self) -> RigidTransform:
        """Returns the transform from ECEF to the local coordinate system."""
        return self._from_ecef

    @property
    def to_ecef(self) -> RigidTransform:
        """Returns the transform from the local coordinate system to ECEF."""
        return self._to_ecef


class ENUReferenceFrame(ReferenceFrame):
    """
    Defines ENU reference frame.

    NOTE: this does not change bearing convention to azimuth being
    angular distance from North. Azimuth is still from x axis towards y axis.
    """
    __slots__ = ("_lat", "_lon", "_alt")

    def __init__(
        self,
        *,
        lat: np.ndarray,
        lon: np.ndarray,
        alt: np.ndarray,
    ):
        lat = np.atleast_1d(lat)
        lon = np.atleast_1d(lon)
        alt = np.atleast_1d(alt)
        if lat.shape != lon.shape or lat.shape != alt.shape:
            raise ValueError("lat, lon, alt must have identical shapes")

        if lat.shape != (len(lat),):
            raise ValueError(
                "The lla shapes used must be one dimensional: (N,), but is"
                f" {lat.shape}"
            )

        self._lat = np.copy(lat)
        self._lon = np.copy(lon)
        self._alt = np.copy(alt)

        self._from_ecef = self._compute_to_local()
        self._to_ecef = self._from_ecef.inv()

        # freeze frame
        self._lat.flags.writeable = False
        self._lon.flags.writeable = False
        self._alt.flags.writeable = False

    def _compute_to_local(self):
        return self._compute_to_enu()

    def _compute_to_enu(self):
        lat = self._lat
        lon = self._lon
        alt = self._alt
        N = lat.shape[0]

        rotation_around_z = -lon - 90
        rotation_around_x = lat - 90

        ecef2local_rot = scipy.spatial.transform.Rotation.from_euler(
            'zx',
            np.stack([rotation_around_z, rotation_around_x], axis=-1),
            degrees=True
        )
        ecef2local_translation = np.zeros((N, 3))
        # NOTE: using constant earth radius works because of spherical Earth
        ecef2local_translation[:, 2] = -(alt + EARTH_RADIUS_M)
        ecef2local = RigidTransform(
            ecef2local_rot, ecef2local_translation
        )
        return ecef2local


class DWNReferenceFrame(ENUReferenceFrame):
    """
    Defines DWN reference frame. x=Down, y=West, z=North
    DWN is a custom reference frame for simplification of satellite's ref frame
    useful for antenna usage.
    """
    ENU2DWN_ROT = scipy.spatial.transform.Rotation.from_matrix(
        np.array([[
            [0, 0, -1],
            [-1, 0, 0],
            [0, 1, 0],
        ]])
    )

    def _compute_to_local(self):
        ecef2enu = self._compute_to_enu()
        # basis change
        # ENU <> x: east, y: north, z: up
        # DWN <> x: down, y: west, z: north
        # x2 = -z1, y2 = -x1, z2 = y
        enu2dwn = RigidTransform(self.ENU2DWN_ROT, np.zeros((1, 3)))

        return ecef2enu.and_then(enu2dwn)


@readonly_properties(
    "x_local", "y_local", "z_local",
    "pointn_azim_local", "pointn_elev_local",
    "global_reference_frame", "local_reference_frame"
)
class SimulatorGeometry(GlobalGeometry):
    """
    Class with simplified coordinate system operations.
    Just global and local conversion.
    """
    # N = num of geometries
    x_local: np.ndarray            # (N,)
    y_local: np.ndarray            # (N,)
    z_local: np.ndarray            # (N,)
    pointn_azim_local: np.ndarray  # (N,)
    pointn_elev_local: np.ndarray  # (N,)

    local_reference_frame: ReferenceFrame
    global_reference_frame: ReferenceFrame

    uses_local_coords: bool

    def __init__(
        self,
        num_geometries,
        uses_local_coords=False,
        global_cs: ReferenceFrame = None,
    ):
        """
        Initialize a geometry object with a global coordinate system
        and defining how many local coordinate systems should exist
        """
        self.setup(
            num_geometries,
            uses_local_coords,
            global_cs,
        )

    def setup(
        self,
        num_geometries,
        uses_local_coords=False,
        global_cs: ReferenceFrame = None,
    ):
        """
        Initializes variables based on number of geometries considered
        """
        super().setup(num_geometries)

        self._global_reference_frame = global_cs
        self.uses_local_coords = True

        if not uses_local_coords:
            self.uses_local_coords = False
            self._x_local = self._x_global
            self._y_local = self._y_global
            self._z_local = self._z_global
            self._pointn_azim_local = self._pointn_azim_global
            self._pointn_elev_local = self._pointn_elev_global
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
        self._local_reference_frame = None

    def set_local_reference_frame(
        self, frame: ReferenceFrame
    ):
        """
        Sets local coord system references and prepares
        global<->local coordinate transformation
        """
        if not self.uses_local_coords:
            raise ValueError(
                "Cannot set local reference frame when not using local coords"
            )
        self._local_reference_frame = frame

        self._compute_global_local_transform()

    def set_global_coords(
        self,
        x=None,
        y=None,
        z=None,
        azim=None,
        elev=None,
    ):
        """Set passed values to objects global coordinates. If geometry does not have local reference
        it will be assumed to be the same as global reference, with local == global
        If None is passed, attribute will not be changed.
        """
        super().set_global_coords(
            x=x,
            y=y,
            z=z,
            azim=azim,
            elev=elev,
        )

        self._compute_local_from_global()

    def set_local_coords(
        self,
        x=None,
        y=None,
        z=None,
        azim=None,
        elev=None,
    ):
        """Set values to local coordinate values. If geometry does not have local reference
        it will be assumed to be the same as global reference, with local == global
        If None is passed, attribute will not be updated.
        """
        if x is not None:
            self._x_local = x
        if y is not None:
            self._y_local = y
        if z is not None:
            self._z_local = z
        if elev is not None:
            self._pointn_elev_local = elev
        if azim is not None:
            self._pointn_azim_local = azim

        self._compute_global_from_local()

    def _compute_global_from_local(self):
        if not self.uses_local_coords:
            self._x_global = self._x_local
            self._y_global = self._y_local
            self._z_global = self._z_local
            self._pointn_elev_global = self._pointn_elev_local
            self._pointn_azim_global = self._pointn_azim_local
            return

        p_local = np.stack([self.x_local, self.y_local, self.z_local], axis=-1)

        p_global = self._local2global_points(p_local)

        # Store results
        self._x_global = p_global[:, 0]
        self._y_global = p_global[:, 1]
        self._z_global = p_global[:, 2]

        r = 1
        # then get pointing vec
        point_local = np.stack(polar_to_cartesian(
            r, self.pointn_azim_local, self.pointn_elev_local), axis=-1)

        point_global_x, point_global_y, point_global_z = self._local2global_vectors(
            point_local
        ).T

        _, global_azimuth, global_elevation = cartesian_to_polar(
            point_global_x, point_global_y, point_global_z)

        self._pointn_elev_global = global_elevation
        self._pointn_azim_global = global_azimuth

    def _local2global_points(
        self, p_local,
    ):
        """Receives points shaped as (N, 3) and applies local2global transform,
        returning (N, 3), where N is the number of local coordinate systems.
        """
        return self.local2global.apply_points(p_local)

    def _local2global_vectors(
        self, p_local,
    ):
        """Receives a vector shaped as (N, 3) and applies local2global transform,
        returning (N, 3), where N is the number of local coordinate systems.
        Does not apply translations, just rotations
        """
        return self.local2global.apply_vectors(p_local)

    def _local2global_points_permutation(
        self, p_local,
    ):
        """Receives points as (M, 3), returning (N, M, 3),
        where N is the number of local coordinate systems
        """
        return self.local2global.apply_points_permutation(p_local)

    def _local2global_vectors_permutation(
        self, p_local,
    ):
        """Receives points as (M, 3), returning (N, M, 3),
        where N is the number of local coordinate systems.
        Does not apply translations, just rotations
        """
        return self.local2global.apply_vectors_permutation(p_local)

    def _global2local_points(
        self, p_local,
    ):
        """Receives points shaped as (N, 3) and applies global2local transform,
        returning (N, 3), where N is the number of local coordinate systems.
        """
        return self.global2local.apply_points(p_local)

    def _global2local_vectors(
        self, p_local,
    ):
        """Receives a vector shaped as (N, 3) and applies global2local transform,
        returning (N, 3), where N is the number of local coordinate systems.
        Does not apply translations, just rotations
        """
        return self.global2local.apply_vectors(p_local)

    def _global2local_points_permutation(
        self, p_local,
    ):
        """Receives points as (M, 3), returning (N, M, 3),
        where N is the number of local coordinate systems
        """
        return self.global2local.apply_points_permutation(p_local)

    def _global2local_vectors_permutation(
        self, p_local,
    ):
        """Receives points as (M, 3), returning (N, M, 3),
        where N is the number of local coordinate systems.
        Does not apply translations, just rotations
        """
        return self.global2local.apply_vectors_permutation(p_local)

    def _compute_local_from_global(self):
        if not self.uses_local_coords:
            self._x_local = self._x_global
            self._y_local = self._y_global
            self._z_local = self._z_global
            self._pointn_elev_local = self._pointn_elev_global
            self._pointn_azim_local = self._pointn_azim_global
            return

        p_global = np.stack([self.x_global, self.y_global, self.z_global], axis=-1)

        p_local = self._global2local_points(p_global)

        # Store results
        self._x_local = p_local[:, 0]
        self._y_local = p_local[:, 1]
        self._z_local = p_local[:, 2]

        r = 1
        # then get pointing vec
        point_global = np.stack(polar_to_cartesian(
            r, self.pointn_azim_global, self.pointn_elev_global), axis=-1)

        point_local_x, point_local_y, point_local_z = self._global2local_vectors(
            point_global
        ).T

        _, local_azimuth, local_elevation = cartesian_to_polar(
            point_local_x, point_local_y, point_local_z)

        self._pointn_elev_local = local_elevation
        self._pointn_azim_local = local_azimuth

    def _compute_global_local_transform(self):
        # get ecef to local
        self.global2local = (
            self.global_reference_frame
                .to_ecef
                .and_then(
                    self.local_reference_frame.from_ecef
                )
        )
        self.local2global = (
            self.local_reference_frame
                .to_ecef
                .and_then(
                    self.global_reference_frame.from_ecef
                )
        )

    def get_local_distance_to(
        self,
        other: "SimulatorGeometry",
        *,
        return_z_dist=False
    ) -> np.array:
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

        p_global = np.stack([other.x_global, other.y_global, other.z_global], axis=-1)
        other_local = self._global2local_points_permutation(
            p_global,
        )
        own_local = np.stack([self.x_local, self.y_local, np.zeros_like(self.z_local)], axis=-1)

        if return_z_dist:
            z_dist = other_local[..., 2] - self.z_local[:, None]
        other_local[..., 2] = 0.

        dist2d = np.sqrt(np.sum(np.power(other_local - own_local[:, None, :], 2), axis=-1))

        if return_z_dist:
            return dist2d, z_dist
        return dist2d

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

        dist2d, z_dist = self.get_local_distance_to(other, return_z_dist=True)

        return np.degrees(np.arctan2(z_dist, dist2d))


def plot_geom(
    fig: "go.Figure",
    geom: SimulatorGeometry,
    scatter_params: dict = {},
    plot_pointing=False,
):
    """Adds a given SimulatorGeometry to a plotly figure
    considering global coordinates
    """
    import plotly.graph_objects as go
    scatter_params = {
        "mode": 'markers',
        "marker": dict(size=1, color='red', opacity=1),
        "showlegend": False,
        **scatter_params
    }
    fig.add_trace(
        go.Scatter3d(
            x=geom.x_global,
            y=geom.y_global,
            z=geom.z_global,
            **scatter_params
        )
    )

    if plot_pointing:
        from sharc.support.sharc_geom import polar_to_cartesian
        # Plot beam boresight vectors
        boresight_length = 100 * 1e3  # Length of the boresight vectors for visualization
        boresight_x, boresight_y, boresight_z = polar_to_cartesian(
            boresight_length,
            geom.pointn_azim_global,
            geom.pointn_elev_global
        )
        # Add arrow heads to the end of the boresight vectors
        for x, y, z, bx, by, bz in zip(geom.x_global,
                                       geom.y_global,
                                       geom.z_global,
                                       boresight_x,
                                       boresight_y,
                                       boresight_z):
            fig.add_trace(go.Cone(
                x=[x + bx],
                y=[y + by],
                z=[z + bz],
                u=[bx],
                v=[by],
                w=[bz],
                colorscale=[[0, 'orange'], [1, 'orange']],
                sizemode='absolute',
                sizeref=2 * boresight_length / 5,
                showscale=False,
                showlegend=False,
            ))
        for x, y, z, bx, by, bz in zip(geom.x_global,
                                       geom.y_global,
                                       geom.z_global,
                                       boresight_x,
                                       boresight_y,
                                       boresight_z):
            fig.add_trace(go.Scatter3d(
                x=[x, x + bx],
                y=[y, y + by],
                z=[z, z + bz],
                mode='lines',
                line=dict(color='orange', width=2),
                showlegend=False,
            ))


if __name__ == "__main__":
    global_lla = (-14, -45, 1200)
    global_reference_frame = ENUReferenceFrame(
        lat=np.array([global_lla[0]]),
        lon=np.array([global_lla[1]]),
        alt=np.array([global_lla[2]]),
    )
    # tg = SimulatorGeometry(
    #     1,
    #     1,
    #     global_reference_frame
    # )
    # tg.set_local_reference_frame(
    #     np.array([-14]),
    #     np.array([-45]),
    #     np.array([1200]),
    # )

    from sharc.topology.topology_macrocell import TopologyMacrocell
    rng = np.random.RandomState(seed=0xcaffe)
    topology = TopologyMacrocell(
        3 * 111e3, 1
    )

    topology.calculate_coordinates(rng)

    num_ue = 3

    bs_geom = SimulatorGeometry(
        topology.num_base_stations,
        topology.num_base_stations,
        global_reference_frame
    )
    ue_geom = SimulatorGeometry(
        num_ue * topology.num_base_stations,
        num_ue * topology.num_base_stations,
        global_reference_frame
    )

    bs_geom.set_local_reference_frame(
        DWNReferenceFrame(
            lat=np.repeat(11, topology.num_base_stations),
            lon=np.repeat(-47, topology.num_base_stations),
            alt=np.repeat(1200, topology.num_base_stations),
        )
    )
    ue_geom.set_local_reference_frame(
        DWNReferenceFrame(
            lat=np.repeat(11, num_ue * topology.num_base_stations),
            lon=np.repeat(-47, num_ue * topology.num_base_stations),
            alt=np.repeat(1200, num_ue * topology.num_base_stations),
        )
    )

    bs_geom.set_local_coords(
        topology.x,
        topology.y,
        topology.z,
    )

    from sharc.station_factory import StationFactory
    ue_x, ue_y, ue_z, _, _ = StationFactory.get_random_position(
        num_ue * topology.num_base_stations,
        topology,
        rng,
        deterministic_cell=True
    )
    ue_geom.set_local_coords(
        np.array(ue_x),
        np.array(ue_y),
        np.array(ue_z),
    )

    from sharc.satellite.scripts.plot_globe import plot_globe_with_borders
    from sharc.support.sharc_geom import CoordinateSystem

    # for plotting
    global_cs = CoordinateSystem()
    global_cs.set_reference(
        *global_lla
    )
    fig = plot_globe_with_borders(
        False, global_cs, False
    )

    import plotly.graph_objects as go

    plot_geom(
        fig,
        bs_geom,
        dict(
            marker=dict(
                size=2,
                color='blue',
                opacity=1.0
            ),
            name='BS'
        )
    )
    plot_geom(
        fig,
        ue_geom,
        dict(
            marker=dict(
                size=1,
                color='red',
                opacity=1.0
            ),
            name='UE'
        )
    )

    fig.show()
