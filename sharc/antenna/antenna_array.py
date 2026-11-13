"""
Implementation of the IMT antenna array of M.2101, with beamforming.

The array factor uses the separability of the weight and superposition
matrices into row and column components, which keeps it fast with many stations.
"""

from sharc.antenna.antenna import Antenna
from sharc.antenna.antenna_element_imt_m2101 import AntennaElementImtM2101
from sharc.antenna.antenna_element_imt_f1336 import AntennaElementImtF1336
from sharc.antenna.antenna_element_imt_const import AntennaElementImtConst
from sharc.antenna.antenna_subarray_imt import AntennaSubarrayIMT
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.support.geometry import RigidTransform
from sharc.support.sharc_utils import wrap2_180, clip_angle

import matplotlib.pyplot as plt
import numpy as np
import typing


class AntennaArray(Antenna):
    """
    Implements an M.2101 antenna array.

    Attributes
    ----------
        par (ParametersAntennaImt): antenna parameters
        azimuth (float): physical azimuth inclination
        elevation (float): physical elevation inclination
        element (AntennaElementImt): antenna element
        subarray (AntennaSubarrayIMT): subarray, None when it is not enabled
        n_rows (int): number of rows in array
        n_cols (int): number of columns in array
        dh (float): horizontal element spacing over wavelenght (d/lambda)
        dv (float): vertical element spacing over wavelenght (d/lambda)
        beams_list (list): (phi, tilt) of each beam, in the antenna's coordinates
        w_vec_list (list): (row, column) weight components of each beam
        normalize (bool): if normalization is applied
        norm_data (dict): data used for beamforming normalization
        adj_correction_factor (float): correction factor for adjacent channel
            single element pattern
        co_correction_factor (2D np.array): correction factor for co-channel
            antenna array pattern for given beam pointing direction
        resolution (float): beam pointing resolution [deg] of co-channel
            correction factor array
        minimum_array_gain (float): lower limit of the total gain [dBi]
        constant_gain (bool): if the gain is the same in every direction and
            for any beam, in which case one object can be shared by stations
    """

    def __init__(
        self,
        par: ParametersAntennaImt,
        global2local_transform: RigidTransform = None,
        azimuth: float = 0.0,
        elevation: float = 0.0,
    ):
        """
        Constructs an antenna array.

        Parameters
        ----------
        par: ParametersAntennaImt
            Antenna parameters.
        global2local_transform: RigidTransform, optional
            Single transformation from global coordinates to the frame in which
            azimuth and elevation are defined. If None, they are defined in
            global coordinates.
        azimuth: float
            Antenna's physical azimuth inclination [degrees].
        elevation: float
            Antenna's physical elevation inclination [degrees], referenced in
            the x axis.
        """
        super().__init__()
        self.par = par
        self.always_first_beam = False
        self.subarray = None

        pattern = par.element_pattern.upper()
        if pattern == "M2101":
            self.element = AntennaElementImtM2101(par)
        elif pattern == "F1336":
            self.element = AntennaElementImtF1336(par)
        elif pattern == "FIXED":
            self.element = AntennaElementImtConst(par)
        else:
            raise ValueError(
                f"antenna element type {par.element_pattern} not supported"
            )

        if par.subarray.is_enabled:
            self.subarray = AntennaSubarrayIMT(
                element=self.element,
                eletrical_downtilt=par.subarray.eletrical_downtilt,
                n_rows=par.subarray.n_rows,
                element_vert_spacing=par.subarray.element_vert_spacing
            )

        self.global2local_transform = global2local_transform
        self.site_rotation_mtx = None
        if global2local_transform is not None:
            if global2local_transform.N > 1:
                raise ValueError(
                    "global2local_transform is supposed to have a single"
                    " transformation for the purposes of antenna calculations"
                )
            self.site_rotation_mtx = global2local_transform.rot.as_matrix()[0]

        self.azimuth = azimuth
        self.elevation = elevation
        self._calculate_rotation_matrix()
        self.minimum_array_gain = par.minimum_array_gain

        self.n_rows = par.n_rows
        self.n_cols = par.n_columns
        self.dh = par.element_horiz_spacing
        self.dv = par.element_vert_spacing

        self.adjacent_antenna_model = par.adjacent_antenna_model

        # Beamforming normalization
        self.normalize = par.normalization
        self.co_correction_factor_list = []
        self.adj_correction_factor = 0.0
        if self.normalize:
            # Load co-channel data
            self.norm_data = par.normalization_data
            self.adj_correction_factor = self.norm_data["correction_factor_adj_channel"]
            self.co_correction_factor = self.norm_data["correction_factor_co_channel"]
            self.resolution = self.norm_data["resolution"]

        # A 1x1 array of a constant-gain element, without subarray or
        # normalization, has the same gain in every direction and for any
        # beam (array factor is exactly 0 dB). Beams need not be stored and
        # one object can be shared between stations (see AntennaFactory).
        self.constant_gain = (
            self.n_rows == 1 and self.n_cols == 1
            and isinstance(self.element, AntennaElementImtConst)
            and self.subarray is None
            and not self.normalize
        )

    def set_always_first_beam(self):
        """Sets the antenna to always use the first beam.

        When this flag is set, :meth:`calculate_gain` ignores any ``beams_l``
        argument and selects the first beam (index 0) for all direction angles.
        """
        self.always_first_beam = True

    def clip_beam_direction(
        self, phi, theta, h_range, v_range, boresight_azimuth,
    ) -> tuple:
        """
        Limits a beam direction to the steering ranges of this antenna.

        When the antenna has a global to local transform, the ranges apply in
        that frame and boresight_azimuth is ignored in favor of the antenna's
        own azimuth. See :meth:`Antenna.clip_beam_direction`.
        """
        rot = self.site_rotation_mtx
        if rot is None:
            return super().clip_beam_direction(
                phi, theta, h_range, v_range, boresight_azimuth,
            )

        local = rot @ self._angles_to_vector(phi, theta)
        h_min, h_max = wrap2_180(np.asarray(h_range) + self.azimuth)
        local_phi = clip_angle(
            np.rad2deg(np.arctan2(local[1], local[0])), h_min, h_max,
        )
        local_theta = np.clip(
            np.rad2deg(np.arccos(np.clip(local[2], -1.0, 1.0))), *v_range,
        )

        clipped = rot.T @ self._angles_to_vector(local_phi, local_theta)
        return (
            np.rad2deg(np.arctan2(clipped[1], clipped[0])),
            np.rad2deg(np.arccos(np.clip(clipped[2], -1.0, 1.0))),
        )

    @staticmethod
    def _angles_to_vector(phi: float, theta: float) -> np.ndarray:
        """Unit vector for phi from the x axis and theta from the z axis [degrees]."""
        phi_rad, theta_rad = np.deg2rad(phi), np.deg2rad(theta)
        return np.array([
            np.sin(theta_rad) * np.cos(phi_rad),
            np.sin(theta_rad) * np.sin(phi_rad),
            np.cos(theta_rad),
        ])

    def add_beam(self, phi_etilt: float, theta_etilt: float):
        """
        Add new beam to antenna.
        Does not receive angles in local coordinate system.
        Theta taken with z axis as reference.

        Parameters
        ----------
            phi_etilt: float
                azimuth electrical tilt angle [degrees]
            theta_etilt: float
                elevation electrical tilt angle [degrees]
        """
        if self.constant_gain:
            # gain does not depend on the beam: nothing to store
            return
        phi, theta = self.to_local_coord(phi_etilt, theta_etilt)
        self.beams_list.append(
            (np.ndarray.item(phi), np.ndarray.item(theta - 90)),
        )
        w_row, w_col = self._weight_components(phi, theta - 90)
        self.w_vec_list.append((w_row[0], w_col[0]))

        if self.normalize:
            lin = int(np.ndarray.item(phi) / self.resolution)
            col = int(np.ndarray.item(theta) / self.resolution)
            self.co_correction_factor_list.append(
                self.co_correction_factor[lin, col],
            )
        else:
            self.co_correction_factor_list.append(0.0)

    @staticmethod
    def add_beams_batch(antennas, phi_etilt, theta_etilt):
        """
        Add one beam to each of many antennas at once.

        Equivalent to ``antennas[i].add_beam(phi_etilt[i], theta_etilt[i])``
        for every i, with the coordinate rotation and the weights of all beams
        computed in single NumPy operations. Antennas must share the same
        parameters; otherwise add_beam is called one by one.

        Parameters
        ----------
        antennas : sequence of AntennaArray, length N (may repeat)
        phi_etilt, theta_etilt : (N,) beam directions, simulator coordinates
        """
        phi = np.asarray(phi_etilt, dtype=float).ravel()
        theta = np.asarray(theta_etilt, dtype=float).ravel()
        if phi.size == 0:
            return

        ref = antennas[0]
        if not AntennaArray._is_homogeneous(antennas):
            for a, p, t in zip(antennas, phi, theta):
                a.add_beam(p, t)
            return
        if ref.constant_gain:
            return

        rot = np.stack([a.rotation_mtx for a in antennas])        # (N, 3, 3)
        points = AntennaArray._angles_to_vector(phi, theta).T[:, :, np.newaxis]
        rotated = (rot @ points)[:, :, 0]                         # (N, 3)
        lo_phi = np.rad2deg(np.arctan2(rotated[:, 1], rotated[:, 0]))
        lo_theta = np.rad2deg(np.arccos(np.clip(rotated[:, 2], -1.0, 1.0)))

        w_row, w_col = ref._weight_components(lo_phi, lo_theta - 90)
        if ref.normalize:
            lin = (lo_phi / ref.resolution).astype(int)
            col = (lo_theta / ref.resolution).astype(int)

        for i, ant in enumerate(antennas):
            ant.beams_list.append((float(lo_phi[i]), float(lo_theta[i] - 90)))
            ant.w_vec_list.append((w_row[i], w_col[i]))
            if ref.normalize:
                ant.co_correction_factor_list.append(
                    ant.co_correction_factor[lin[i], col[i]],
                )
            else:
                ant.co_correction_factor_list.append(0.0)

    @staticmethod
    def _is_homogeneous(antennas) -> bool:
        """Whether all antennas are arrays sharing the same parameters object."""
        ref = antennas[0]
        return all(
            isinstance(a, AntennaArray) and a.par is ref.par for a in antennas
        )

    def _uses_array_pattern(self, co_channel: bool) -> bool:
        """Whether the array pattern applies, or only the element pattern."""
        if co_channel:
            return True
        if self.adjacent_antenna_model == "SINGLE_ELEMENT":
            return False
        if self.adjacent_antenna_model == "BEAMFORMING":
            return True
        raise ValueError(
            "Invalid antenna pattern for adjacent channel calculations: "
            f"{self.adjacent_antenna_model}"
        )

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculates the gain in the given directions.
        Does not receive angles in local coordinate system.
        Theta taken with z axis as reference.

        Parameters
        ----------
        phi_vec : np.ndarray
            Azimuth angles [degrees] in global coordinate system.
        theta_vec : np.ndarray
            Elevation angles [degrees] in global coordinate system.
        co_channel : bool, optional
            Indicates whether the antenna array pattern (co-channel case), or
            the element pattern (adjacent channel case) will be used
            (default is True).
        beams_l : np.ndarray, optional
            Index of the beam to use for each direction. If not provided, the
            beam is steered at each direction. If always_first_beam is set,
            this parameter is ignored.

        Returns
        -------
        np.ndarray
            Antenna gain [dBi] for each direction, no lower than
            minimum_array_gain.
        """
        phi_vec = np.atleast_1d(kwargs["phi_vec"])
        theta_vec = np.atleast_1d(kwargs["theta_vec"])
        co_channel = self._uses_array_pattern(kwargs.get("co_channel", True))

        if self.constant_gain:
            # Same value as the general path below (element + 0 dB array
            # factor + 0 correction), without coordinates or beams.
            gains = self.element.element_pattern(phi_vec, theta_vec)
            if not co_channel:
                gains = gains + self.adj_correction_factor
            return np.maximum(gains, self.minimum_array_gain)

        lo_phi, lo_theta = self.to_local_coord(phi_vec, theta_vec)

        # Adjacent channel with single element pattern: no array gain.
        if not co_channel:
            gains = self.element.element_pattern(lo_phi, lo_theta) \
                + self.adj_correction_factor
            return np.maximum(gains, self.minimum_array_gain)

        element_g = self._element_gain(lo_phi, lo_theta)

        if self.always_first_beam:
            beams_l = np.zeros(len(lo_phi), dtype=int)
        elif "beams_l" in kwargs:
            beams_l = np.atleast_1d(
                np.asarray(kwargs["beams_l"], dtype=int)
            )[:len(lo_phi)]
        else:
            beams_l = None

        if beams_l is None:
            w_row, w_col = self._weight_components(lo_phi, lo_theta - 90)
            if self.normalize:
                lin = (phi_vec / self.resolution).astype(int)
                col = (theta_vec / self.resolution).astype(int)
                correction_factor = self.co_correction_factor[lin, col]
            else:
                correction_factor = 0.0
        else:
            w_row = np.stack([w[0] for w in self.w_vec_list])[beams_l]
            w_col = np.stack([w[1] for w in self.w_vec_list])[beams_l]
            correction_factor = np.asarray(self.co_correction_factor_list)[beams_l]

        v_row, v_col = self._super_position_components(lo_phi, lo_theta)
        gains = element_g + correction_factor \
            + self._array_gain(v_row, v_col, w_row, w_col)

        return np.maximum(gains, self.minimum_array_gain)

    @staticmethod
    def calculate_gain_batch(
        antennas,
        phi: np.ndarray,
        theta: np.ndarray,
        beams_l: np.ndarray,
        co_channel: bool = True,
    ) -> np.ndarray:
        """
        Gain of many antennas at once, one stored beam per row.

        Equivalent to calling ``antennas[i].calculate_gain(phi_vec=phi[i],
        theta_vec=theta[i], beams_l=beams_l[i], co_channel=co_channel)`` for
        every row, but with the coordinate rotation, element/subarray pattern
        and array factor evaluated for all rows in single NumPy operations.
        All antennas must share the same array parameters (same ``par``
        object); otherwise the per-antenna loop is used.

        Parameters
        ----------
        antennas : sequence of AntennaArray, length N
        phi, theta : (N, M) angles in the simulator coordinate system [deg]
        beams_l : (N,) index of the stored beam to use for each row
        co_channel : bool, co-channel (array pattern) or adjacent channel

        Returns
        -------
        (N, M) gains [dBi]
        """
        phi = np.atleast_2d(np.asarray(phi, dtype=float))
        theta = np.atleast_2d(np.asarray(theta, dtype=float))
        beams_l = np.asarray(beams_l, dtype=int)
        n_ant, n_dir = phi.shape
        if n_ant == 0:
            return np.zeros(phi.shape)

        ref = antennas[0]
        if not AntennaArray._is_homogeneous(antennas):
            gains = np.zeros(phi.shape)
            for i, ant in enumerate(antennas):
                gains[i] = ant.calculate_gain(
                    phi_vec=phi[i], theta_vec=theta[i],
                    beams_l=np.repeat(beams_l[i], n_dir),
                    co_channel=co_channel,
                )
            return gains

        co_channel = ref._uses_array_pattern(co_channel)

        if not co_channel:
            # Without the array factor the gain depends only on the antenna
            # and the direction. Rows of the same antenna asking for the same
            # directions (its beams) are computed once and copied, so that
            # they get exactly the same gain: evaluated as separate rows of a
            # stacked batch they could differ in the last bit, and the
            # downlink requires every beam of a BS to couple equally into the
            # adjacent channel.
            first_row = {}
            source = np.arange(n_ant)
            for i, a in enumerate(antennas):
                j = first_row.setdefault(id(a), i)
                if j != i and np.array_equal(phi[i], phi[j]) and np.array_equal(theta[i], theta[j]):
                    source[i] = j
            if np.any(source != np.arange(n_ant)):
                unique_rows, inverse = np.unique(source, return_inverse=True)
                gains = AntennaArray.calculate_gain_batch(
                    [antennas[r] for r in unique_rows],
                    phi[unique_rows], theta[unique_rows], beams_l[unique_rows],
                    co_channel=False,
                )
                return gains[inverse]

        if ref.constant_gain:
            gains = ref.element.element_pattern(phi, theta)
            if not co_channel:
                gains = gains + ref.adj_correction_factor
            return np.maximum(gains, ref.minimum_array_gain)

        # rotation to each antenna's local coordinates: (N,3,3)@(N,3,M)
        rot = np.stack([a.rotation_mtx for a in antennas])
        rotated = rot @ np.moveaxis(
            AntennaArray._angles_to_vector(phi, theta), 0, 1,
        )
        lo_phi = np.rad2deg(np.arctan2(rotated[:, 1, :], rotated[:, 0, :])).ravel()
        lo_theta = np.rad2deg(
            np.arccos(np.clip(rotated[:, 2, :], -1.0, 1.0)),
        ).ravel()

        if not co_channel:
            gains = ref.element.element_pattern(lo_phi, lo_theta) \
                + ref.adj_correction_factor
            return np.maximum(gains.reshape(n_ant, n_dir), ref.minimum_array_gain)

        element_g = ref._element_gain(lo_phi, lo_theta)

        v_row, v_col = ref._super_position_components(lo_phi, lo_theta)
        beams = [a.w_vec_list[b] for a, b in zip(antennas, beams_l)]
        w_row = np.repeat(np.stack([w[0] for w in beams]), n_dir, axis=0)
        w_col = np.repeat(np.stack([w[1] for w in beams]), n_dir, axis=0)
        correction_factor = np.repeat(
            np.array([
                a.co_correction_factor_list[b] for a, b in zip(antennas, beams_l)
            ], dtype=float),
            n_dir,
        )

        gains = element_g + correction_factor \
            + AntennaArray._array_gain(v_row, v_col, w_row, w_col)

        return np.maximum(gains.reshape(n_ant, n_dir), ref.minimum_array_gain)

    def reset_beams(self):
        """Reset beams lists
        """
        self.beams_list = []
        self.w_vec_list = []
        self.co_correction_factor_list = []

    def _element_gain(self, phi: np.ndarray, theta: np.ndarray) -> np.ndarray:
        """
        Calculates the element, or subarray when enabled, gain for given angles.

        Parameters
        ----------
        phi : np.ndarray
            Azimuth angles [degrees] in local coordinate system.
        theta : np.ndarray
            Elevation angles [degrees] in local coordinate system.
        """
        if self.subarray is None:
            return self.element.element_pattern(phi, theta)
        return self.subarray.calculate_gain(phi, theta)

    @staticmethod
    def _array_gain(
        v_row: np.ndarray, v_col: np.ndarray,
        w_row: np.ndarray, w_col: np.ndarray,
    ) -> np.ndarray:
        """Calculates the array gain [dB] from row and column components.

        Notes
        -----
        This formula has the same result as the one presented on M.2101, but
        considers W(m, n) = W(m)W(n) and V(m, n) = V(m)V(n), allowing for
        reduced memory bandwidth and faster runtime.
        """
        return 10 * np.log10(
            np.abs(
                np.sum(v_row * w_row, axis=-1) * np.sum(v_col * w_col, axis=-1)
            ) ** 2
        )

    def _weight_components(self, phi_tilt, theta_tilt):
        """Weight components of this array. See _weight_vector_components."""
        return self._weight_vector_components(
            phi_tilt, theta_tilt, self.n_rows, self.n_cols, self.dv, self.dh,
        )

    def _super_position_components(self, phi, theta):
        """Superposition components of this array. See _super_position_vector_components."""
        return self._super_position_vector_components(
            phi, theta, self.n_rows, self.n_cols, self.dv, self.dh,
        )

    def _beam_gain(self, phi: float, theta: float, beam=-1) -> float:
        """
        Calculates gain for a single beam in a given direction.
        Angles are in the local coordinate system.

        Parameters
        ----------
            phi (float): azimuth angle [degrees]
            theta (float): elevation angle [degrees]
            beam (int): Optional, beam index. If not provided, maximum gain is
                calculated

        Returns
        -------
            gain (float): beam gain [dBi]
        """
        scalar = np.isscalar(phi) and np.isscalar(theta)
        phi, theta = np.atleast_1d(phi), np.atleast_1d(theta)

        if beam == -1:
            w_row, w_col = self._weight_components(phi, theta - 90)
        else:
            w_row, w_col = self.w_vec_list[beam]

        v_row, v_col = self._super_position_components(phi, theta)
        gain = self._element_gain(phi, theta) \
            + self._array_gain(v_row, v_col, w_row, w_col)

        return gain.item() if scalar else gain

    @staticmethod
    def _super_position_vector(
        phi_tilt: np.ndarray,
        theta_tilt: np.ndarray,
        n_rows: int, n_cols: int,
        dv: float, dh: float,
    ) -> np.array:
        vn, vm = AntennaArray._super_position_vector_components(
            phi_tilt,
            theta_tilt,
            n_rows, n_cols,
            dv, dh,
        )

        return vn[:, :, None] * vm[:, None, :]

    @staticmethod
    def _weight_vector(
        phi_tilt: np.ndarray,
        theta_tilt: np.ndarray,
        n_rows: int, n_cols: int,
        dv: float, dh: float,
    ) -> np.array:
        wn, wm = AntennaArray._weight_vector_components(
            phi_tilt,
            theta_tilt,
            n_rows, n_cols,
            dv, dh,
        )

        return wn[:, :, None] * wm[:, None, :]

    @staticmethod
    def _weight_vector_components(
        phi_tilt: np.ndarray,
        theta_tilt: np.ndarray,
        n_rows: int, n_cols: int,
        dv: float, dh: float,
    ) -> typing.Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the complex weight vectors for beamforming.
        Angles are in the local coordinate system.

        Parameters
        ----------
            phi_tilt: np.ndarray
                electrical horizontal steering [degrees]
            theta_tilt: np.ndarray
                electrical down-tilt steering [degrees]

        Returns
        -------
            w_vec: (np.ndarray, np.ndarray)
                weighting vectors, first for rows, second for columns
        """
        # shape (Na, 1, 1)
        r_phi = np.atleast_1d(
            np.deg2rad(phi_tilt)
        )[:, np.newaxis]
        r_theta = np.atleast_1d(
            np.deg2rad(theta_tilt)
        )[:, np.newaxis]

        # shape (1, Nr, 1)
        n = np.arange(n_rows)[np.newaxis, :] + 1
        # shape (1, 1, Nc)
        m = np.arange(n_cols)[np.newaxis, :] + 1

        exp_arg_n = (n - 1) * dv * np.sin(r_theta)
        exp_arg_m = - (m - 1) * dh * np.cos(r_theta) * np.sin(r_phi)

        w_vec_n = (1 / np.sqrt(n_rows * n_cols)) *\
            np.exp(2 * np.pi * 1.0j * exp_arg_n)

        w_vec_m = np.exp(2 * np.pi * 1.0j * exp_arg_m)

        return (w_vec_n, w_vec_m)

    @staticmethod
    def _super_position_vector_components(
        phi: float, theta: float,
        n_rows: int, n_cols: int,
        dv: float, dh: float,
    ) -> typing.Tuple[np.ndarray, np.ndarray]:
        """
        Calculates super position vector.
        Angles are in the local coordinate system.

        Parameters
        ----------
            theta: float
                elevation angle [degrees]
            phi: float
                azimuth angle [degrees]

        Returns
        -------
        v_vec: typing.Tuple[np.ndarray, np.ndarray]:
            superposition vector components, first for rows, second for columns

        Notes
        -----
        This implementation is optimized for computational efficiency,
        using recursive relationships to avoid redundant calculations.
        """
        phi = np.atleast_1d(phi)
        theta = np.atleast_1d(theta)

        # (Na,)
        A = dv * np.cos(np.deg2rad(theta))
        B = dh * np.sin(np.deg2rad(theta)) * np.sin(np.deg2rad(phi))

        # instead of calculating exp for every row, there is a recursive
        # relation that speeds this up. Small n_rows means that floating
        # point error should not accumulate
        # The relationship is: V(n) = V(n-1)V(2) | n > 2
        # V(1) = 1., V(2) = exp(...)
        row_phase = np.empty((len(theta), n_rows), dtype=np.complex128)
        row_phase[:, 0] = 1.

        row_phase_term = np.exp(
            2j * np.pi * A
        )
        row_phase[:, 1:] = row_phase_term[:, None]
        # recursive relationship by cumulative product
        np.cumprod(row_phase, axis=-1, out=row_phase)

        # instead of calculating exp for every col, there is a recursive
        # relation that speeds this up. Small n_cols means that floating
        # point error should not accumulate
        # The relationship is: V(n) = V(n-1)V(2) | n > 2
        # V(1) = 1., V(2) = exp(...)
        col_phase = np.empty((len(theta), n_cols), dtype=np.complex128)
        col_phase[:, 0] = 1.

        col_phase_term = np.exp(
            2j * np.pi * B
        )
        col_phase[:, 1:] = col_phase_term[:, None]
        # recursive relationship by cumulative product
        np.cumprod(col_phase, axis=-1, out=col_phase)

        return (row_phase, col_phase)

    def to_local_coord(self, phi: float, theta: float) -> tuple:
        """Returns phi and theta in the antenna's local coordinate system.

        Parameters
        ----------
        phi : float
            phi in the simulator's coordinate system
        theta : float
            theta in the simulator's coordinate system

        Returns
        -------
        tuple
            phi, theta in the antenna's coordinate system
        """
        points = self._angles_to_vector(
            np.ravel(np.asarray(phi, dtype=float)),
            np.ravel(np.asarray(theta, dtype=float)),
        )                                               # (3, G)

        rotated_points = self.rotation_mtx @ points     # (3, G)

        lo_phi = np.rad2deg(np.arctan2(rotated_points[1], rotated_points[0]))
        # clip guards against |z| marginally > 1 from rounding
        lo_theta = np.rad2deg(np.arccos(np.clip(rotated_points[2], -1.0, 1.0)))

        return lo_phi, lo_theta

    def _calculate_rotation_matrix(self):
        """Sets the rotation from global to antenna coordinates."""
        alpha = np.deg2rad(self.azimuth)
        beta = np.deg2rad(self.elevation)

        ry = np.array([
            [np.cos(beta), 0.0, np.sin(beta)],
            [0.0, 1.0, 0.0],
            [-np.sin(beta), 0.0, np.cos(beta)],
        ])
        rz = np.array([
            [np.cos(alpha), -np.sin(alpha), 0.0],
            [np.sin(alpha), np.cos(alpha), 0.0],
            [0.0, 0.0, 1.0],
        ])
        self.rotation_mtx = ry @ rz.T
        if self.site_rotation_mtx is not None:
            self.rotation_mtx = self.rotation_mtx @ self.site_rotation_mtx

###############################################################################


class PlotAntennaPattern(object):
    """
    Plots imt antenna pattern.
    """

    def __init__(self, figs_dir):
        self.figs_dir = figs_dir

    def plot_element_pattern(
        self,
        antenna: AntennaArray,
        sta_type: str,
        plot_type: str,
    ):
        """
        Plot the element or array pattern for a given antenna.

        Parameters
        ----------
        antenna : AntennaArray
            The antenna object to plot.
        sta_type : str
            The station type (e.g., 'BS', 'UE').
        plot_type : str
            The type of pattern to plot ('ELEMENT' or 'ARRAY').
        """

        phi_escan = 0
        theta_tilt = 90

        # Plot horizontal pattern
        phi = np.linspace(-180, 180, num=360)
        theta = theta_tilt * np.ones(np.size(phi))
        gain = np.ones(phi.shape, dtype=float) * -500

        if plot_type == "ELEMENT":
            gain = antenna.element.element_pattern(phi, theta)
        elif plot_type == "ARRAY":
            antenna.add_beam(phi_escan, theta_tilt)
            gain = antenna.calculate_gain(
                phi_vec=phi,
                theta_vec=theta,
                beams_l=np.zeros_like(phi, dtype=int),
            )
        elif plot_type == "SUBARRAY":
            if antenna.subarray is None:
                print(
                    "An attempt to plot antenna subarrays was done, but antenna has no subarray!")
                return
            gain = antenna.subarray.calculate_gain(
                phi,
                theta,
            )

        top_y_lim = np.ceil(np.max(gain) / 10) * 10

        fig = plt.figure(figsize=(15, 5), facecolor='w', edgecolor='k')
        ax1 = fig.add_subplot(121)

        ax1.plot(phi, gain)
        ax1.grid(True)
        ax1.set_xlabel(r"$\varphi$ [deg]")
        ax1.set_ylabel("Gain [dBi]")

        if plot_type == "ELEMENT":
            ax1.set_title(
                "IMT " + sta_type +
                " element horizontal antenna pattern",
            )
        elif plot_type == "ARRAY":
            ax1.set_title("IMT " + sta_type + " horizontal antenna pattern")
        elif plot_type == "SUBARRAY":
            ax1.set_title(
                "IMT " +
                sta_type +
                " subarray horizontal antenna pattern")

        ax1.set_xlim(-180, 180)

        # Plot vertical pattern
        theta = np.linspace(0, 180, num=360)
        phi = phi_escan * np.ones(np.size(theta))

        if plot_type == "ELEMENT":
            gain = antenna.element.element_pattern(phi, theta)
        elif plot_type == "ARRAY":
            gain = antenna.calculate_gain(
                phi_vec=phi,
                theta_vec=theta,
                beams_l=np.zeros_like(phi, dtype=int),
            )
        elif plot_type == "SUBARRAY":
            if antenna.subarray is None:
                print(
                    "An attempt to plot antenna subarrays was done, but antenna has no subarray!")
                return
            gain = antenna.subarray.calculate_gain(
                phi,
                theta,
            )

        ax2 = fig.add_subplot(122, sharey=ax1)

        ax2.plot(theta, gain)
        ax2.grid(True)
        ax2.set_xlabel(r"$\theta$ [deg]")
        ax2.set_ylabel("Gain [dBi]")

        if plot_type == "ELEMENT":
            ax2.set_title(
                "IMT " + sta_type +
                " element vertical antenna pattern",
            )
        elif plot_type == "ARRAY":
            ax2.set_title("IMT " + sta_type + " vertical antenna pattern")
        elif plot_type == "SUBARRAY":
            ax2.set_title(
                "IMT " +
                sta_type +
                " subarray vertical antenna pattern")

        ax2.set_xlim(0, 180)
        if np.max(gain) > top_y_lim:
            top_y_lim = np.ceil(np.max(gain) / 10) * 10
        ax2.set_ylim(top_y_lim - 60, top_y_lim)

        if sta_type == "BS":
            file_name = self.figs_dir + "bs_"
        else:  # sta_type == "UE":
            file_name = self.figs_dir + "ue_"

        if plot_type == "ELEMENT":
            file_name = file_name + "element_pattern.png"
        elif plot_type == "ARRAY":
            file_name = file_name + "array_pattern.png"

        # plt.savefig(file_name)
        plt.show()
        return fig


if __name__ == "__main__":
    antenna_params = ParametersAntennaImt()
    antenna_params.adjacent_antenna_model = "SINGLE_ELEMENT"
    antenna_params.normalization = False
    antenna_params.minimum_array_gain = -200

    antenna_params.element_pattern = "M2101"
    antenna_params.element_max_g = 6.5
    antenna_params.element_phi_3db = 65
    antenna_params.element_theta_3db = 90
    antenna_params.element_am = 30
    antenna_params.element_sla_v = 30
    antenna_params.n_rows = 8
    antenna_params.n_columns = 8
    antenna_params.element_horiz_spacing = 0.5
    antenna_params.element_vert_spacing = 0.5
    antenna_params.multiplication_factor = 12

    par = antenna_params.get_antenna_parameters()
    # from sharc.support.geometry import ENUReferenceFrame
    # ref_frame = ENUReferenceFrame(
    #     lat=np.array([90.]),
    #     lon=np.array([-90.]),
    #     alt=np.array([0.]),
    # )
    # antenna = AntennaArray(par, ref_frame.from_ecef)
    antenna = AntennaArray(par)

    antenna.add_beam(np.array(0.), np.array(90.))

    phi_scan = np.linspace(-180., 180., num=360)
    theta = np.zeros_like(phi_scan) + 90.

    # gain = antenna._element_gain(
    #     phi_scan,
    #     theta,
    # )
    gain = antenna.calculate_gain(
        phi_vec=phi_scan,
        theta_vec=theta,
        beams_l=np.zeros_like(phi_scan),
    )

    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(15, 5), facecolor='w', edgecolor='k')
    ax1 = fig.add_subplot(121)

    ax1.plot(phi_scan, gain)
    top_y_lim1 = np.ceil(np.max(gain) / 10) * 10
    ax1.set_xlim(-180, 180)
    ax1.set_ylim(top_y_lim1 - 60, top_y_lim1)
    ax1.grid(True)
    ax1.set_xlabel(r"$\varphi$ [deg]")
    ax1.set_ylabel("Gain [dBi]")

    theta_scan = np.linspace(0., 180., num=360)
    phi = np.zeros_like(theta_scan)

    # gain = antenna._element_gain(
    #     phi,
    #     theta_scan,
    # )
    gain = antenna.calculate_gain(
        phi_vec=phi,
        theta_vec=theta_scan,
        beams_l=np.zeros_like(theta_scan),
    )
    # fig = plt.figure(figsize=(15, 5), facecolor='w', edgecolor='k')
    ax2 = fig.add_subplot(122, sharey=ax1)

    ax2.plot(theta_scan, gain)
    top_y_lim2 = np.ceil(np.max(gain) / 10) * 10
    top_y_lim2 = np.maximum(top_y_lim1, top_y_lim2)

    ax2.set_xlim(0, 180.)
    ax2.set_ylim(top_y_lim2 - 60, top_y_lim2)
    ax2.grid(True)
    ax2.set_xlabel(r"$\vartheta$ [deg]")
    ax2.set_ylabel("Gain [dBi]")

    plt.show()
