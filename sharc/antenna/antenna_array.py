"""
Optimized implementation of M.2101 antenna array.

This antenna was created after the already existing antenna_beamforming_imt
since that implementation is too slow for use with a lot of stations.

This is supposed to be a faster implementation, and substitute the previous one
in a future release
"""

from sharc.antenna.antenna import Antenna
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.support.geometry import RigidTransform
from sharc.support.sharc_geom import polar_to_cartesian, cartesian_to_polar

import numpy as np
import typing


class AntennaArray(Antenna):
    """Implements M.2101 antenna array."""

    def __init__(
        self,
        par: ParametersAntennaImt,
        global2local_transform: RigidTransform = None,
        *,
        per_element_taper_fn: typing.Callable = None
    ):
        """Constructs antenna array.

        Parameters
        ----------
        par: ParametersAntennaImt
            Antenna parameters. Partial support only.
        global2local_transform: RigidTransform, optional
            Transformation from global to local coordinate system. If None,
            no transformation is applied.

        Notes
        -----
        By partial support, it is meant that not all parameters
        from ParametersAntennaImt are used in this implementation.
        For example, normalization and subarray support are not
        implemented.
        """
        super().__init__()
        self.par = par
        self.always_first_beam = False
        self.taper_fn = per_element_taper_fn

        self.global2local_transform = global2local_transform
        if self.global2local_transform is not None:
            if self.global2local_transform.N > 1:
                raise ValueError(
                    "global2local_transform is supposed to have a single"
                    " transformation for the purposes of antenna calculations"
                )

    def set_always_first_beam(self):
        """Sets the antenna to always use the first beam.

        When this flag is set, :meth:`calculate_gain` ignores any ``beams_l``
        argument and selects the first beam (index 0) for all direction angles.
        """
        self.always_first_beam = True

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """Calculates the antenna gain.

        Parameters
        ----------
        phi_vec : np.ndarray
            Azimuth angles [degrees] in global coordinate system.
        theta_vec : np.ndarray
            Elevation angles [degrees] in global coordinate system.
        co_channel : bool, optional
            If True, co-channel interference is considered (default is True).
        beams_l : np.ndarray, optional
            Indices of beams to consider for each angle. If not provided,
            all beams are considered. Also, if always_first_beam is set,
            this parameter is ignored.

        Returns
        -------
        np.ndarray
            Antenna gain [dBi] for each direction.
        """
        phi_vec = np.atleast_1d(kwargs["phi_vec"])
        theta_vec = np.atleast_1d(kwargs["theta_vec"])
        co_channel = kwargs.get("co_channel", True)
        adj_antenna_model = (
            self.par.adjacent_antenna_model == "SINGLE_ELEMENT"
            and not co_channel
        )
        if self.always_first_beam:
            beam_idxs = np.zeros(len(phi_vec), dtype=int)
        elif "beams_l" in kwargs.keys():
            beam_idxs = np.asarray(kwargs["beams_l"], dtype=int)
        else:
            if len(self.beams_list):
                raise ValueError(
                    "If you added beams you must use them explicitly"
                )
            beam_idxs = np.arange(len(phi_vec))

        assert phi_vec.shape == (len(phi_vec),)
        assert theta_vec.shape == (len(theta_vec),)
        phi_vec, theta_vec = self._to_local_coord(
            phi_vec,
            theta_vec,
        )

        el_g = self._element_gain(
            phi_vec, theta_vec,
        )
        assert el_g.shape == theta_vec.shape

        if adj_antenna_model:
            return el_g

        ar_g = self._array_gain(
            phi_vec, theta_vec, beam_idxs
        )
        assert ar_g.shape == theta_vec.shape

        return ar_g + el_g

    def _element_gain(
        self, phi: np.ndarray, theta: np.ndarray
    ):
        """
        Calculates the element gain for given angles.

        Parameters
        ----------
        phi : np.ndarray
            Azimuth angles [degrees] in local coordinate system.
        theta : np.ndarray
            Elevation angles [degrees] in local coordinate system.
        """
        return self._element_gain_dispatch(
            self.par, phi, theta,
        )

    def _array_gain(
        self,
        phi: np.ndarray, theta: np.ndarray,
        beam_idxs: np.ndarray
    ):
        """Calculates the array gain for given angles and beam indices.

        Notes
        -----
        The mathematical formulation is based on M.2101, but formulation
        has been optimized for computational efficiency. It considers
        separability of the array factor into row and column components,
        allowing for reduced memory bandwidth and faster runtime.
        """
        if len(self.beams_list) == 0:
            beam_phi, beam_theta = phi, theta
        else:
            beam_phi, beam_theta = np.array(self.beams_list).T
            beam_phi, beam_theta = self._to_local_coord(beam_phi, beam_theta)

        beam_etilt = beam_theta - 90.
        beams_w_vec_row, beams_w_vec_col = self._weight_vector_components(
            beam_phi, beam_etilt,
            self.par.n_rows, self.par.n_columns,
            self.par.element_vert_spacing,
            self.par.element_horiz_spacing,
        )
        w_vec_row, w_vec_col = (
            beams_w_vec_row[beam_idxs],
            beams_w_vec_col[beam_idxs]
        )

        v_vec_row, v_vec_col = self._super_position_vector_components(
            phi, theta,
            self.par.n_rows, self.par.n_columns,
            self.par.element_vert_spacing,
            self.par.element_horiz_spacing,
        )

        # NOTE: this formula has the same result to the one presented on M.2101
        # but it is optimized for computation
        # considering W(m, n) = W(m)W(n) and V(m, n) = V(m)V(n)
        if self.taper_fn is None:
            g = 10 * np.log10(
                abs(
                    np.sum(v_vec_row * w_vec_row, axis=-1)
                    * np.sum(v_vec_col * w_vec_col, axis=-1)
                )**2
            )
        else:
            taper = self.taper_fn(
                beam_phi, beam_etilt,
            )
            # shape (..., N_rows)
            a = v_vec_row * w_vec_row
            # shape (..., N_cols)
            b = v_vec_col * w_vec_col
            # shape (N_rows, N_cols)
            T = taper.reshape((self.par.n_columns, self.par.n_rows)).T

            # guarantee that the end sum of weights gives physically consistent
            # gain results = self.par.n_columns * self.par.n_rows at max_g
            T = T * np.sqrt(
                self.par.n_columns * self.par.n_rows
                / np.sum(np.abs(T)**2, axis=(-1, -2))
            )

            tmp = T @ b.T
            AF = np.sum(a.T * tmp, axis=0)

            g = 20 * np.log10(np.abs(AF))

        return np.maximum(g, self.par.minimum_array_gain)

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

    @staticmethod
    def _element_gain_dispatch(par: ParametersAntennaImt, phi, theta):
        """
        Dispatch to the correct element gain calculation method.

        Parameters
        ----------
        par: ParametersAntennaImt
            Antenna parameters.
        phi: np.ndarray
            Azimuth angles [degrees] in local coordinate system.
        theta: np.ndarray
            Elevation angles [degrees] in local coordinate system.
        """
        if par.element_pattern == "M2101":
            return AntennaArray._calculate_m2101_element_gain(
                phi, theta,
                par.element_phi_3db, par.element_theta_3db,
                par.element_max_g, par.element_sla_v, par.element_am,
                par.multiplication_factor,
            )
        elif par.element_pattern == "FIXED":
            return np.full_like(phi, par.element_max_g)
        else:
            raise NotImplementedError(
                "No implementation done for element_pattern"
                f"='{par.element_pattern}'"
            )

    @staticmethod
    def _calculate_m2101_element_gain(
        phi: np.ndarray, theta: np.ndarray,
        phi_3db: np.ndarray, theta_3db: np.ndarray,
        g_max: np.ndarray, sla_v: np.ndarray, am: np.ndarray,
        multiplication_factor: np.ndarray = 12
    ):
        """Calculates and returns element gain as described in M.2101."""
        g_horizontal = -1.0 * np.minimum(
            multiplication_factor * (phi / phi_3db)**2, am
        )
        g_vertical = -1.0 * np.minimum(
            multiplication_factor * ((theta - 90.) / theta_3db)**2, sla_v
        )

        att = -1.0 * (
            g_horizontal +
            g_vertical
        )

        return g_max - np.minimum(att, am)

    def _to_local_coord(self, phi, theta):
        """
        Transform angles from global to local coordinate system.

        Parameters
        ----------
        phi: np.ndarray
            Azimuth angles [degrees] in global coordinate system.
        theta: np.ndarray
            Elevation angles [degrees] in global coordinate system.

        Returns
        -------
        phi: np.ndarray
            Azimuth angles [degrees] in local coordinate system.
        theta: np.ndarray
            Elevation angles [degrees] in local coordinate system.

        Notes
        -----
        The transformation is done by converting to Cartesian coordinates,
        applying the transformation defined on construction,
        and converting back to spherical coordinates. It is assumed that
        theta is defined with z axis as reference, and phi with x axis as reference
        and increasing towards y axis.
        """
        if self.global2local_transform is None:
            return np.array(phi), np.array(theta)

        theta_from_plane = 90 - theta
        vecs = np.stack(polar_to_cartesian(1, phi, theta_from_plane), axis=-1)
        transformed_vecs = self.global2local_transform.apply_vectors(
            vecs
        )
        x, y, z = transformed_vecs.T
        _r, phi, elev_from_plane = cartesian_to_polar(x, y, z)

        theta = 90 - elev_from_plane

        return phi, theta

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
        phi_etilt, theta_etilt = np.atleast_1d(phi_etilt), np.atleast_1d(theta_etilt)

        self.beams_list.append(
            (np.ndarray.item(phi_etilt), np.ndarray.item(theta_etilt)),
        )


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
