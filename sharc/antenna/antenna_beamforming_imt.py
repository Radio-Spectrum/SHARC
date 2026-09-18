# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 15:35:51 2017

@author: Calil
"""

import sys
import numpy as np
import matplotlib.pyplot as plt

from sharc.antenna.antenna_element_imt_m2101 import AntennaElementImtM2101
from sharc.antenna.antenna_element_imt_f1336 import AntennaElementImtF1336
from sharc.antenna.antenna_element_imt_const import AntennaElementImtConst
from sharc.antenna.antenna_subarray_imt import AntennaSubarrayIMT
from sharc.antenna.antenna import Antenna
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt


class AntennaBeamformingImt(Antenna):
    """
    Implements an antenna array

    Attributes
    ----------
        azimuth (float): physical azimuth inclination
        elevation (float): physical elevation inclination
        element (AntennaElementImt): antenna element
        n_rows (int): number of rows in array
        n_cols (int): number of columns in array
        dh (float): horizontal element spacing over wavelenght (d/lambda)
        dv (float): vertical element spacing over wavelenght (d/lambda)
        beams_list (list): vertical and horizontal tilts of beams
        normalize (bool): if normalization is applied
        norm_data (dict): data used for beamforming normalization
        adj_correction_factor (float): correction factor for adjacent channel
            single element pattern
        co_correction_factor (2D np.array): correction factor for co-channel
            antenna array pattern for given beam pointing direction
        resolution (float): beam pointing resolution [deg] of co-channel
            correction factor array
        minimum_array_gain (float): minimum array gain for beamforming
    """

    def __init__(
            self,
            par: ParametersAntennaImt,
            azimuth: float,
            elevation: float):
        """
        Constructs an AntennaBeamformingImt object.
        Does not receive angles in local coordinate system.
        Elevation taken with x axis as reference.

        Parameters
        ---------
            param (ParametersAntennaImt): antenna IMT parameters
            azimuth (float): antenna's physical azimuth inclination
            elevation (float): antenna's physical elevation inclination
                referenced in the x axis
        """
        super().__init__()
        self.param = par
        self.subarray = None

        if (par.element_pattern).upper() == "M2101":
            self.element = AntennaElementImtM2101(par)
        elif (par.element_pattern).upper() == "F1336":
            self.element = AntennaElementImtF1336(par)
        elif (par.element_pattern).upper() == "FIXED":
            self.element = AntennaElementImtConst(par)
        else:
            sys.stderr.write(
                f"ERROR\nantenna element type {
                    par.element_pattern} not supported", )
            sys.exit(1)

        if par.subarray.is_enabled:
            self.subarray = AntennaSubarrayIMT(
                element=self.element,
                eletrical_downtilt=par.subarray.eletrical_downtilt,
                n_rows=par.subarray.n_rows,
                element_vert_spacing=par.subarray.element_vert_spacing
            )

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
        if self.constant_gain:
            # gain does not depend on the beam: nothing to store
            return
        phi, theta = self.to_local_coord(phi_etilt, theta_etilt)
        self.beams_list.append(
            (np.ndarray.item(phi), np.ndarray.item(theta - 90)),
        )
        self.w_vec_list.append(self._weight_vector(phi, theta - 90))

        if self.normalize:
            lin = int(phi / self.resolution)
            col = int(theta / self.resolution)
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
        for every i, with the coordinate rotation and the weight matrices of
        all beams computed in single NumPy operations. Antennas must share
        the same array parameters; otherwise add_beam is called one by one.

        Parameters
        ----------
        antennas : sequence of AntennaBeamformingImt, length N (may repeat)
        phi_etilt, theta_etilt : (N,) beam directions, simulator coordinates
        """
        phi = np.asarray(phi_etilt, dtype=float).ravel()
        theta = np.asarray(theta_etilt, dtype=float).ravel()
        n = phi.size
        if n == 0:
            return

        ref = antennas[0]
        homogeneous = all(
            isinstance(a, AntennaBeamformingImt) and a.param is ref.param
            for a in antennas
        )
        if not homogeneous:
            for a, p, t in zip(antennas, phi, theta):
                a.add_beam(p, t)
            return
        if ref.constant_gain:
            return

        rot = np.stack([a.rotation_mtx for a in antennas])        # (N, 3, 3)
        phi_rad = np.deg2rad(phi)
        theta_rad = np.deg2rad(theta)
        points = np.stack([
            np.sin(theta_rad) * np.cos(phi_rad),
            np.sin(theta_rad) * np.sin(phi_rad),
            np.cos(theta_rad),
        ], axis=1)[:, :, np.newaxis]                              # (N, 3, 1)
        rotated = (rot @ points)[:, :, 0]                         # (N, 3)
        lo_phi = np.rad2deg(np.arctan2(rotated[:, 1], rotated[:, 0]))
        lo_theta = np.rad2deg(np.arccos(np.clip(rotated[:, 2], -1.0, 1.0)))

        w_all = ref._weight_matrix(lo_phi, lo_theta - 90)         # (N, r, c)
        if ref.normalize:
            lin = (lo_phi / ref.resolution).astype(int)
            col = (lo_theta / ref.resolution).astype(int)

        for i, ant in enumerate(antennas):
            ant.beams_list.append((float(lo_phi[i]), float(lo_theta[i] - 90)))
            ant.w_vec_list.append(w_all[i])
            if ref.normalize:
                ant.co_correction_factor_list.append(
                    ant.co_correction_factor[lin[i], col[i]],
                )
            else:
                ant.co_correction_factor_list.append(0.0)

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculates the gain in the given direction.
        Does not receive angles in local coordinate system.
        Theta taken with z axis as reference.

        Parameters
        ----------
        phi_vec (np.array): azimuth angles [degrees]
        theta_vec (np.array): elevation angles [degrees]
        beam_l (np.array of int): optional. Index of beams for gain calculation
                Default is -1, which corresponds to the beam of maximum gain in
                given direction.
        co_channel (bool): optional, default is True. Indicates whether the
                antenna array pattern (co-channel case), or the element pattern
                (adjacent channel case) will be used for gain calculation.

        Returns
        -------
        gains (np.array): gain corresponding to each of the given directions.
        """
        phi_vec = np.asarray(kwargs["phi_vec"])
        theta_vec = np.asarray(kwargs["theta_vec"])

        # Check if antenna gain has to be calculated on the co-channel or
        # on the adjacent channel
        if "co_channel" in kwargs.keys():
            co_channel = kwargs["co_channel"]
        else:
            co_channel = True

        # If gain has to be calculated on the adjacent channel, then check whether
        # to use beamforming or single element pattern.
        if not co_channel:
            if self.adjacent_antenna_model == "SINGLE_ELEMENT":
                co_channel = False
            elif self.adjacent_antenna_model == "BEAMFORMING":
                co_channel = True
            else:
                sys.stderr.write(
                    "ERROR\nInvalid antenna pattern for adjacent channel calculations: " +
                    self.adjacent_antenna_model,
                )
                sys.exit(1)

        if self.constant_gain:
            # Same value as the general path below (element + 0 dB array
            # factor + 0 correction), without coordinates or beams.
            gains = self.element.element_pattern(phi_vec, theta_vec)
            if not co_channel:
                gains = gains + self.adj_correction_factor
            return np.maximum(gains, self.minimum_array_gain)

        lo_phi_vec, lo_theta_vec = self.to_local_coord(phi_vec, theta_vec)

        # Adjacent channel with single element pattern: no array gain.
        if not co_channel:
            gains = self.element.element_pattern(lo_phi_vec, lo_theta_vec) \
                + self.adj_correction_factor
            return np.maximum(gains, self.minimum_array_gain)

        # ---- Co-channel: element/subarray gain + beamforming array gain ----
        # All directions handled at once (no Python loop): the per-direction
        # superposition/weight matrices are stacked into (G, n_rows, n_cols)
        # and the array gain is the reduction over the array axes.
        if self.subarray is None:
            element_g = self.element.element_pattern(lo_phi_vec, lo_theta_vec)
        else:
            element_g = self.subarray.calculate_gain(lo_phi_vec, lo_theta_vec)

        v_mtx = self._super_position_matrix(lo_phi_vec, lo_theta_vec)

        if "beams_l" in kwargs.keys():
            # One output per direction; align beams_l to the number of
            # directions (matches the previous per-direction loop, which was
            # bounded by len(lo_phi_vec)).
            n_direct = len(lo_phi_vec)
            beams_l = np.asarray(kwargs["beams_l"], dtype=int)[:n_direct]
            w_mtx = np.stack(self.w_vec_list)[beams_l]
            correction_factor = np.asarray(self.co_correction_factor_list)[beams_l]
        else:
            w_mtx = self._weight_matrix(lo_phi_vec, lo_theta_vec - 90)
            if self.normalize:
                lin = (phi_vec / self.resolution).astype(int)
                col = (theta_vec / self.resolution).astype(int)
                correction_factor = self.co_correction_factor[lin, col]
            else:
                correction_factor = 0.0

        array_g = 10 * np.log10(
            np.abs(np.sum(v_mtx * w_mtx, axis=(1, 2))) ** 2,
        )
        gains = element_g + array_g + correction_factor

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
        antennas : sequence of AntennaBeamformingImt, length N
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
        homogeneous = all(
            isinstance(a, AntennaBeamformingImt) and a.param is ref.param
            for a in antennas
        )
        if not homogeneous:
            gains = np.zeros(phi.shape)
            for i, ant in enumerate(antennas):
                gains[i] = ant.calculate_gain(
                    phi_vec=phi[i], theta_vec=theta[i],
                    beams_l=np.repeat(beams_l[i], n_dir),
                    co_channel=co_channel,
                )
            return gains

        # Same resolution of the adjacent-channel model as calculate_gain
        if not co_channel:
            if ref.adjacent_antenna_model == "SINGLE_ELEMENT":
                co_channel = False
            elif ref.adjacent_antenna_model == "BEAMFORMING":
                co_channel = True
            else:
                sys.stderr.write(
                    "ERROR\nInvalid antenna pattern for adjacent channel calculations: " +
                    ref.adjacent_antenna_model,
                )
                sys.exit(1)

        if ref.constant_gain:
            gains = ref.element.element_pattern(phi, theta)
            if not co_channel:
                gains = gains + ref.adj_correction_factor
            return np.maximum(gains, ref.minimum_array_gain)

        # ---- rotation to each antenna's local coordinates: (N,3,3)@(N,3,M)
        rot = np.stack([a.rotation_mtx for a in antennas])
        phi_rad = np.deg2rad(phi)
        theta_rad = np.deg2rad(theta)
        points = np.stack([
            np.sin(theta_rad) * np.cos(phi_rad),
            np.sin(theta_rad) * np.sin(phi_rad),
            np.cos(theta_rad),
        ], axis=1)                                          # (N, 3, M)
        rotated = rot @ points                              # (N, 3, M)
        lo_phi = np.rad2deg(np.arctan2(rotated[:, 1, :], rotated[:, 0, :]))
        lo_theta = np.rad2deg(
            np.arccos(np.clip(rotated[:, 2, :], -1.0, 1.0)),
        )
        lo_phi_f = lo_phi.ravel()
        lo_theta_f = lo_theta.ravel()

        if not co_channel:
            gains = ref.element.element_pattern(lo_phi_f, lo_theta_f) \
                + ref.adj_correction_factor
            return np.maximum(gains.reshape(n_ant, n_dir), ref.minimum_array_gain)

        if ref.subarray is None:
            element_g = ref.element.element_pattern(lo_phi_f, lo_theta_f)
        else:
            element_g = ref.subarray.calculate_gain(lo_phi_f, lo_theta_f)

        v_mtx = ref._super_position_matrix(lo_phi_f, lo_theta_f)   # (N*M, r, c)
        w_rows = np.stack([
            a.w_vec_list[b] for a, b in zip(antennas, beams_l)
        ])                                                          # (N, r, c)
        w_mtx = np.repeat(w_rows, n_dir, axis=0)                    # (N*M, r, c)
        corr = np.repeat(
            np.array([
                a.co_correction_factor_list[b] for a, b in zip(antennas, beams_l)
            ], dtype=float),
            n_dir,
        )

        array_g = 10 * np.log10(
            np.abs(np.sum(v_mtx * w_mtx, axis=(1, 2))) ** 2,
        )
        gains = (element_g + array_g + corr).reshape(n_ant, n_dir)

        return np.maximum(gains, ref.minimum_array_gain)

    def reset_beams(self):
        """Reset beams lists
        """
        self.beams_list = []
        self.w_vec_list = []
        self.co_correction_factor_list = []

    def _super_position_vector(self, phi: float, theta: float) -> np.array:
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
        r_phi = np.deg2rad(phi)
        r_theta = np.deg2rad(theta)

        n = np.arange(self.n_rows) + 1
        m = np.arange(self.n_cols) + 1

        exp_arg = (n[:, np.newaxis] - 1) * self.dv * np.cos(r_theta) + \
                  (m - 1) * self.dh * np.sin(r_theta) * np.sin(r_phi)

        v_vec = np.exp(2 * np.pi * 1.0j * exp_arg)

        return v_vec

    def _weight_vector(self, phi_tilt: float, theta_tilt: float) -> np.array:
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
        r_phi = np.deg2rad(phi_tilt)
        r_theta = np.deg2rad(theta_tilt)

        n = np.arange(self.n_rows) + 1
        m = np.arange(self.n_cols) + 1

        exp_arg = (n[:, np.newaxis] - 1) * self.dv * np.sin(r_theta) - \
                  (m - 1) * self.dh * np.cos(r_theta) * np.sin(r_phi)

        w_vec = (1 / np.sqrt(self.n_rows * self.n_cols)) *\
            np.exp(2 * np.pi * 1.0j * exp_arg)

        return w_vec

    def _super_position_matrix(self, phi, theta) -> np.array:
        """Vectorized version of `_super_position_vector` over many directions.

        Parameters
        ----------
            phi (np.array): azimuth angles [degrees], local coords, shape (G,)
            theta (np.array): elevation angles [degrees], local coords, shape (G,)

        Returns
        -------
            (G, n_rows, n_cols) complex array (one superposition matrix per direction)
        """
        r_phi = np.deg2rad(np.asarray(phi, dtype=float))[:, None, None]
        r_theta = np.deg2rad(np.asarray(theta, dtype=float))[:, None, None]
        n = np.arange(self.n_rows).reshape(1, self.n_rows, 1)
        m = np.arange(self.n_cols).reshape(1, 1, self.n_cols)
        exp_arg = n * self.dv * np.cos(r_theta) + \
            m * self.dh * np.sin(r_theta) * np.sin(r_phi)
        return np.exp(2 * np.pi * 1.0j * exp_arg)

    def _weight_matrix(self, phi_tilt, theta_tilt) -> np.array:
        """Vectorized version of `_weight_vector` over many directions.
        Returns a (G, n_rows, n_cols) complex array.
        """
        r_phi = np.deg2rad(np.asarray(phi_tilt, dtype=float))[:, None, None]
        r_theta = np.deg2rad(np.asarray(theta_tilt, dtype=float))[:, None, None]
        n = np.arange(self.n_rows).reshape(1, self.n_rows, 1)
        m = np.arange(self.n_cols).reshape(1, 1, self.n_cols)
        exp_arg = n * self.dv * np.sin(r_theta) - \
            m * self.dh * np.cos(r_theta) * np.sin(r_phi)
        return (1 / np.sqrt(self.n_rows * self.n_cols)) * \
            np.exp(2 * np.pi * 1.0j * exp_arg)

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

        if self.subarray is None:
            element_g = self.element.element_pattern(phi, theta)
        else:
            element_g = self.subarray.calculate_gain(phi, theta)

        v_vec = self._super_position_vector(phi, theta)

        if beam == -1:
            w_vec = self._weight_vector(phi, theta - 90)
            array_g = 10 * np.log10(abs(np.sum(np.multiply(v_vec, w_vec)))**2)
        else:
            array_g = 10 * np.log10(
                abs(
                    np.sum(
                        np.multiply(
                            v_vec,
                            self.w_vec_list[beam],
                        ),
                    ),
                )**2,
            )

        gain = element_g + array_g

        return gain

    def to_local_coord(self, phi: float, theta: float) -> tuple:
        """Returns phi and theta to antennas local coordintate system

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

        # Plain ndarrays (np.matrix is deprecated and much slower to build).
        phi_rad = np.deg2rad(np.ravel(np.asarray(phi, dtype=float)))
        theta_rad = np.deg2rad(np.ravel(np.asarray(theta, dtype=float)))

        points = np.vstack([
            np.sin(theta_rad) * np.cos(phi_rad),
            np.sin(theta_rad) * np.sin(phi_rad),
            np.cos(theta_rad),
        ])                                              # (3, G)

        rotated_points = self.rotation_mtx @ points     # (3, G)

        lo_phi = np.rad2deg(np.arctan2(rotated_points[1], rotated_points[0]))
        # clip guards against |z| marginally > 1 from rounding
        lo_theta = np.rad2deg(np.arccos(np.clip(rotated_points[2], -1.0, 1.0)))

        return lo_phi, lo_theta

    def _calculate_rotation_matrix(self):

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

###############################################################################


class PlotAntennaPattern(object):
    """
    Plots imt antenna pattern.
    """

    def __init__(self, figs_dir):
        self.figs_dir = figs_dir

    def plot_element_pattern(
        self,
        antenna: AntennaBeamformingImt,
        sta_type: str,
        plot_type: str,
    ):
        """
        Plot the element or array pattern for a given antenna.

        Parameters
        ----------
        antenna : AntennaBeamformingImt
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


if __name__ == '__main__':

    figs_dir = "figs/"

    bs_param = ParametersAntennaImt()
    ue_param = ParametersAntennaImt()
    bs_param.adjacent_antenna_model = "SINGLE_ELEMENT"
    ue_param.adjacent_antenna_model = "SINGLE_ELEMENT"
    bs_param.normalization = False
    ue_param.normalization = False
    bs_param.normalization_file = 'beamforming_normalization\\bs_indoor_norm.npz'
    ue_param.normalization_file = 'beamforming_normalization\\ue_norm.npz'
    bs_param.minimum_array_gain = -200
    ue_param.minimum_array_gain = -200

    bs_param.element_pattern = "M2101"
    bs_param.element_max_g = 6.5
    bs_param.element_phi_3db = 65
    bs_param.element_theta_3db = 90
    bs_param.element_am = 30
    bs_param.element_sla_v = 30
    bs_param.n_rows = 8
    bs_param.n_columns = 8
    bs_param.element_horiz_spacing = 0.5
    bs_param.element_vert_spacing = 0.5
    bs_param.multiplication_factor = 12
    bs_param.downtilt = 0

    # bs_param.element_pattern = "F1336"
    # bs_param.element_max_g = 16
    # bs_param.element_phi_3db = 0
    # bs_param.element_theta_3db = 90
    # bs_param.element_am = 30
    # bs_param.element_sla_v = 30
    # bs_param.n_rows = 1
    # bs_param.n_columns = 1
    # bs_param.element_horiz_spacing = 0.5
    # bs_param.element_vert_spacing = 0.5
    # bs_param.multiplication_factor = 12
    # bs_param.downtilt = 0

    ue_param.element_pattern = "M2101"
    ue_param.element_max_g = 5
    ue_param.element_phi_3db = 90
    ue_param.element_theta_3db = 90
    ue_param.element_am = 25
    ue_param.element_sla_v = 25
    ue_param.n_rows = 4
    ue_param.n_columns = 4
    ue_param.element_horiz_spacing = 0.5
    ue_param.element_vert_spacing = 0.5
    ue_param.multiplication_factor = 12

    plot = PlotAntennaPattern(figs_dir)

    # Plot BS TX radiation patterns
    par = bs_param.get_antenna_parameters()
    bs_array = AntennaBeamformingImt(par, 0, 0, bs_param.subarray)
    f = plot.plot_element_pattern(bs_array, "BS", "ELEMENT")
    # f.savefig(figs_dir + "BS_element.pdf", bbox_inches='tight')
    f = plot.plot_element_pattern(bs_array, "TX", "ARRAY")
    # f.savefig(figs_dir + "BS_array.pdf", bbox_inches='tight')

    # Plot UE TX radiation patterns
    par = ue_param.get_antenna_parameters()
    ue_array = AntennaBeamformingImt(par, 0, 0, ue_param.subarray)
    plot.plot_element_pattern(ue_array, "UE", "ELEMENT")
    plot.plot_element_pattern(ue_array, "UE", "ARRAY")

    print('END')
