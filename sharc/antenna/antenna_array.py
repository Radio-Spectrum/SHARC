"""
This antenna was created after the already existing antenna_beamforming_imt
since that implementation is too slow for use with a lot of stations.

This is supposed to be a faster implementation, and substitute the previous one
in a future release
"""

from sharc.antenna.antenna import Antenna
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.support.geometry import RigidTransform

import numpy as np


class AntennaArray(Antenna):
    # par: ParametersAntennaImt

    def __init__(
        self,
        par: ParametersAntennaImt,
        # global2local_transform: RigidTransform
    ):
        super().__init__()
        self.par = par

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculates the antenan gain.
        """
        phi_vec = np.atleast_1d(kwargs["phi_vec"])
        theta_vec = np.atleast_1d(kwargs["theta_vec"])
        co_channel = kwargs.get("co_channel", True)
        adj_antenna_model = (
            self.par.adjacent_antenna_model == "SINGLE_ELEMENT"
            and not co_channel
        )
        if "beams_l" in kwargs.keys():
            beam_idxs = np.asarray(kwargs["beams_l"], dtype=int)
        else:
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
        return self._element_gain_dispatch(
            self.par, phi, theta,
        )

    def _array_gain(
        self,
        phi: np.ndarray, theta: np.ndarray,
        beam_idxs: np.ndarray
    ):
        v_vec = self._super_position_vector(
            phi, theta,
            self.par.n_rows, self.par.n_columns,
            self.par.element_vert_spacing,
            self.par.element_horiz_spacing,
        )
        if len(self.beams_list) == 0:
            beam_phi, beam_theta = phi, theta
        else:
            beam_phi, beam_theta = np.array(self.beams_list).T

        beam_etilt = beam_theta - 90.
        beams_w_vec = self._weight_vector(
            beam_phi, beam_etilt,
            self.par.n_rows, self.par.n_columns,
            self.par.element_vert_spacing,
            self.par.element_horiz_spacing,
        )
        w_vec = beams_w_vec[beam_idxs]

        g = 10 * np.log10(
            abs(
                np.sum(v_vec * w_vec, axis=(1, 2))
            )**2
        )

        return g

    @staticmethod
    def _weight_vector(
        phi_tilt: np.ndarray,
        theta_tilt: np.ndarray,
        n_rows: int, n_cols: int,
        dv: float, dh: float,
    ) -> np.array:
        """
        Calculates super position vector.
        Angles are in the local coordinate system.

        Parameters
        ----------
            phi_tilt (float): electrical horizontal steering [degrees]
            theta_tilt (float): electrical down-tilt steering [degrees]

        Returns
        -------
            w_vec (np.array): weighting vector
        """
        # shape (Na, 1, 1)
        r_phi = np.atleast_1d(
            np.deg2rad(phi_tilt)
        )[:, np.newaxis, np.newaxis]
        r_theta = np.atleast_1d(
            np.deg2rad(theta_tilt)
        )[:, np.newaxis, np.newaxis]

        # shape (1, Nr, 1)
        n = np.arange(n_rows)[np.newaxis, :, np.newaxis] + 1
        # shape (1, 1, Nc)
        m = np.arange(n_cols)[np.newaxis, np.newaxis, :] + 1

        exp_arg = (n - 1) * dv * np.sin(r_theta) - \
                  (m - 1) * dh * np.cos(r_theta) * np.sin(r_phi)

        w_vec = (1 / np.sqrt(n_rows * n_cols)) *\
            np.exp(2 * np.pi * 1.0j * exp_arg)

        # shape (Na, Nr, Nc)
        return w_vec

    @staticmethod
    def _super_position_vector(
        phi: float, theta: float,
        n_rows: int, n_cols: int,
        dv: float, dh: float,
    ) -> np.array:
        """
        Calculates super position vector.
        Angles are in the local coordinate system.

        Parameters
        ----------
            theta (float): elevation angle [degrees]
            phi (float): azimuth angle [degrees]

        Returns
        -------
            v_vec (np.array): superposition vector
        """
        # shape (Na, 1, 1)
        r_phi = np.atleast_1d(
            np.deg2rad(phi)
        )[:, np.newaxis, np.newaxis]
        r_theta = np.atleast_1d(
            np.deg2rad(theta)
        )[:, np.newaxis, np.newaxis]

        # shape (1, Nr, 1)
        n = np.arange(n_rows)[np.newaxis, :, np.newaxis] + 1
        # shape (1, 1, Nc)
        m = np.arange(n_cols)[np.newaxis, np.newaxis, :] + 1

        exp_arg = (n - 1) * dv * np.cos(r_theta) + \
                  (m - 1) * dh * np.sin(r_theta) * np.sin(r_phi)

        v_vec = np.exp(2 * np.pi * 1.0j * exp_arg)

        # shape (Na, Nr, Nc)
        return v_vec

    @staticmethod
    def _element_gain_dispatch(par: ParametersAntennaImt, phi, theta):
        if par.element_pattern == "M2101":
            return AntennaArray._calculate_m2101_element_gain(
                phi, theta,
                par.element_phi_3db, par.element_theta_3db,
                par.element_max_g, par.element_sla_v, par.element_am,
                par.multiplication_factor,
            )
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
        """Calculates and returns element gain as described in M.2101
        """
        g_horizontal = -1.0 * np.minimum(
            multiplication_factor * (phi / phi_3db)**2, am
        )
        g_vertical = -1.0 * np.minimum(
            multiplication_factor * ((theta-90.) / theta_3db)**2, sla_v
        )

        att = -1.0 * (
            g_horizontal +
            g_vertical
        )

        return g_max - np.minimum(att, am)

    def _to_local_coord(self, phi, theta):
        return np.array(phi), np.array(theta)

    def add_beam(self, phi_etilt: float, theta_etilt: float):
        """
        Add new beam to antenna.
        Does not receive angles in local coordinate system.
        Theta taken with z axis as reference.

        Parameters
        ----------
            phi_etilt (float): azimuth electrical tilt angle [degrees]
            theta_etilt (float): elevation electrical tilt angle [degrees]
        """
        # phi_etilt, theta_etilt = np.atleast_1d(phi_etilt), np.atleast_1d(theta_etilt)
        phi, theta = self._to_local_coord(phi_etilt, theta_etilt)
        self.beams_list.append(
            (np.ndarray.item(phi), np.ndarray.item(theta)),
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
    top_y_lim = np.ceil(np.max(gain) / 10) * 10
    ax1.set_xlim(-180, 180)
    ax1.set_ylim(top_y_lim - 60, top_y_lim)
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
    top_y_lim = np.ceil(np.max(gain) / 10) * 10
    ax2.set_xlim(0, 180.)
    ax2.set_ylim(top_y_lim - 60, top_y_lim)
    ax2.grid(True)
    ax2.set_xlabel(r"$\vartheta$ [deg]")
    ax2.set_ylabel("Gain [dBi]")

    plt.show()
