# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 15:35:51 2017

@author: Calil
@modified: Luciano Camilo Tue Jan 26 13:49:25 2021
"""

import numpy as np
import matplotlib.pyplot as plt
import sys

from sharc.antenna.antenna_element_imt_m2101 import AntennaElementImtM2101
from sharc.antenna.antenna_element_imt_f1336 import AntennaElementImtF1336
from sharc.antenna.antenna_element_imt_const import AntennaElementImtConst
from sharc.antenna.antenna import Antenna
from sharc.support.enumerations import StationType
from sharc.support.named_tuples import AntennaPar
from sharc.parameters.parameters_antenna_imt import ParametersAntennaImt


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

    def __init__(self, par: AntennaPar, azimuth: float, elevation: float):
        """
        Constructs an AntennaBeamformingImt object.
        Does not receive angles in local coordinate system.
        Elevation taken with x axis as reference.

        Parameters
        ---------
            param (AntennaPar): antenna IMT parameters
            azimuth (float): antenna's physical azimuth inclination
            elevation (float): antenna's physical elevation inclination
                referenced in the x axis
        """
        super().__init__()
        self.param = par

        if par.element_pattern.upper() == "M2101":
            self.element = AntennaElementImtM2101(par)
        elif par.element_pattern.upper() == "F1336":
            self.element = AntennaElementImtF1336(par)
        elif par.element_pattern.upper() == "FIXED":
            self.element = AntennaElementImtConst(par)
        else:
            sys.stderr.write("ERROR\nantenna element type {} not supported".format(par.element_pattern))
            sys.exit(1)

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

    def add_beam(self, phi_etilt: float, theta_etilt: float, peso):
        """
        Add new beam to antenna.
        Does not receive angles in local coordinate system.
        Theta taken with z axis as reference.

        Parameters
        ----------
            phi_etilt (float): azimuth electrical tilt angle [degrees]
            theta_etilt (float): elevation electrical tilt angle [degrees]
        """
        phi, theta = self.to_local_coord(phi_etilt, theta_etilt)
        self.beams_list.append((np.asscalar(phi), np.asscalar(theta-90)))
        self.w_vec_list.append(self._weight_vector(phi, theta-90, peso))

        if self.normalize:
            lin = int(phi/self.resolution)
            col = int(theta/self.resolution)
            self.co_correction_factor_list.append(self.co_correction_factor[lin, col])
        else:
            self.co_correction_factor_list.append(0.0)

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
        # Both options are explicitly written in order to improve readability
        if not co_channel:
            if self.adjacent_antenna_model == "SINGLE_ELEMENT":
                co_channel = False
            elif self.adjacent_antenna_model == "BEAMFORMING":
                co_channel = True
            else:
                sys.stderr.write("ERROR\nInvalid antenna pattern for adjacent channel calculations: " +
                                 self.adjacent_antenna_model)
                sys.exit(1)

        if "beams_l" in kwargs.keys():
            beams_l = np.asarray(kwargs["beams_l"], dtype=int)
            correction_factor = self.co_correction_factor_list
            correction_factor_idx = beams_l
        else:
            beams_l = -1*np.ones_like(phi_vec)
            if co_channel:
                if self.normalize:
                    lin_f = phi_vec/self.resolution
                    col_f = theta_vec/self.resolution
                    lin = lin_f.astype(int)
                    col = col_f.astype(int)
                    correction_factor = self.co_correction_factor[lin, col]
                else:
                    correction_factor = np.zeros_like(phi_vec)
                correction_factor_idx = [i for i in range(len(correction_factor))]

        lo_phi_vec, lo_theta_vec = self.to_local_coord(phi_vec, theta_vec)

        n_direct = len(lo_theta_vec)

        gains = np.zeros(n_direct)

        if co_channel:
            for g in range(n_direct):
                gains[g] = self._beam_gain(lo_phi_vec[g], lo_theta_vec[g], beams_l[g])\
                           + correction_factor[correction_factor_idx[g]]
        else:
            for g in range(n_direct):
                gains[g] = self.element.element_pattern(lo_phi_vec[g],
                                                        lo_theta_vec[g])\
                     + self.adj_correction_factor

        gains = np.maximum(gains, self.minimum_array_gain)

        return gains

    def reset_beams(self):
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

        exp_arg = (n[:, np.newaxis] - 1)*self.dv*np.cos(r_theta) + \
                  (m - 1)*self.dh*np.sin(r_theta)*np.sin(r_phi)

        v_vec = np.exp(2*np.pi*1.0j*exp_arg)

        return v_vec

    def _weight_vector(self, phi_tilt: float, theta_tilt: float, peso) -> np.array:
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

        exp_arg = (n[:, np.newaxis] - 1)*self.dv*np.sin(r_theta) - \
                  (m - 1)*self.dh*np.cos(r_theta)*np.sin(r_phi)

        if peso == 1:
            pesos = np.array([
                np.ones(8) * 0.28,
                np.ones(8) * 0.52,
                np.ones(8) * 0.80,
                np.ones(8) * 0.97,

                np.ones(8) * 0.97,
                np.ones(8) * 0.80,
                np.ones(8) * 0.52,
                np.ones(8) * 0.28,
            ])
            print(pesos)
            # pesos = np.array([[0.8,1,1,0.8]])
            # pesos = np.array([[1,1,1,1]])
            print(np.shape(pesos))
            #
            w_vec = pesos * (1 / np.sqrt(self.n_rows * self.n_cols)) * \
                    np.exp(2 * np.pi * 1.0j * exp_arg)
        if peso == 0:
            w_vec = (1/np.sqrt(self.n_rows*self.n_cols)) *\
                    np.exp(2*np.pi*1.0j*exp_arg)

        return w_vec

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

        element_g = self.element.element_pattern(phi, theta)

        v_vec = self._super_position_vector(phi, theta)

        if beam == -1:
            w_vec = self._weight_vector(phi, theta-90)
            array_g = 10*np.log10(abs(np.sum(np.multiply(v_vec, w_vec)))**2)
        else:
            array_g = 10*np.log10(abs(np.sum(np.multiply(v_vec, self.w_vec_list[beam])))**2)

        gain = element_g + array_g

        return gain

    def to_local_coord(self, phi: float, theta: float) -> tuple:

        phi_rad = np.ravel(np.array([np.deg2rad(phi)]))
        theta_rad = np.ravel(np.array([np.deg2rad(theta)]))

        points = np.matrix([np.sin(theta_rad)*np.cos(phi_rad),
                           np.sin(theta_rad)*np.sin(phi_rad),
                           np.cos(theta_rad)])

        rotated_points = self.rotation_mtx*points

        lo_phi = np.ravel(np.asarray(np.rad2deg(np.arctan2(rotated_points[1], rotated_points[0]))))
        lo_theta = np.ravel(np.asarray(np.rad2deg(np.arccos(rotated_points[2]))))

        return lo_phi, lo_theta

    def _calculate_rotation_matrix(self):

        alpha = np.deg2rad(self.azimuth)
        beta = np.deg2rad(self.elevation)

        ry = np.matrix([[np.cos(beta), 0.0, np.sin(beta)],
                        [0.0, 1.0,       0.0],
                        [-np.sin(beta), 0.0, np.cos(beta)]])
        rz = np.matrix([[np.cos(alpha), -np.sin(alpha), 0.0],
                        [np.sin(alpha), np.cos(alpha), 0.0],
                        [0.0,           0.0, 1.0]])
        self.rotation_mtx = ry*np.transpose(rz)

###############################################################################


class PlotAntennaPattern(object):
    """
    Plots imt antenna pattern.
    """
    def __init__(self, figs_dir):
        self.figs_dir = figs_dir

    def plot_element_pattern(self,
                             antenna: AntennaBeamformingImt,
                             sta_type: str,
                             plot_type: str,
                             label: str, peso):

        phi_escan = 0
        theta_tilt = 90
        # Plot horizontal pattern
        phi = np.linspace(-180, 180, num=3600)
        theta = theta_tilt*np.ones(np.size(phi))

        if plot_type == "ELEMENT":
            gain = antenna.element.element_pattern(phi, theta)
        elif plot_type == "ARRAY":
            antenna.add_beam(phi_escan, theta_tilt, peso)
            gain = antenna.calculate_gain(phi_vec=phi,
                                          theta_vec=theta,
                                          beams_l=np.zeros_like(phi, dtype=int))

        top_y_lim = np.ceil(np.max(gain)/10)*10

        fig = plt.figure(1,figsize=(15, 5), facecolor='w', edgecolor='k')
        ax1 = fig.add_subplot(121)

        ax1.plot(phi, gain, label=label)
        ax1.grid(True)
        ax1.set_xlabel(r"$\varphi$ [deg]")
        ax1.set_ylabel("Gain [dBi]")

        if plot_type == "ELEMENT":
            ax1.set_title("IMT" + sta_type + " element horizontal antenna pattern")
        elif plot_type == "ARRAY":
            ax1.set_title("IMT" + sta_type + " horizontal antenna pattern")

        ax1.set_xlim(-180, 180)

        # Plot vertical pattern
        theta = np.linspace(0, 180, num=3600)
        phi = phi_escan*np.ones(np.size(theta))

        if plot_type == "ELEMENT":
            gain = antenna.element.element_pattern(phi, theta)
        elif plot_type == "ARRAY":
            gain = antenna.calculate_gain(phi_vec=phi,
                                          theta_vec=theta,
                                          beams_l=np.zeros_like(phi, dtype=int))

        ax2 = fig.add_subplot(122, sharey=ax1)

        ax2.plot(theta, gain, label= label)
        ax2.legend()
        ax2.grid(True)
        ax2.set_xlabel(r"$\theta$ [deg]")
        ax2.set_ylabel("Gain [dBi]")

        if plot_type == "ELEMENT":
            ax2.set_title("IMT" + sta_type + " element vertical antenna pattern")
        elif plot_type == "ARRAY":
            ax2.set_title("IMT" + sta_type + " vertical antenna pattern")

        ax2.set_xlim(0, 180)
        if np.max(gain) > top_y_lim:
            top_y_lim = np.ceil(np.max(gain)/10)*10
        ax2.set_ylim(30 - 150, 30)

        if sta_type == "BS":
            file_name = self.figs_dir + "bs_"
        else:  # sta_type == "UE":
            file_name = self.figs_dir + "ue_"

        if plot_type == "ELEMENT":
            file_name = file_name + "element_pattern.png"
        elif plot_type == "ARRAY":
            file_name = file_name + "array_pattern.png"

        # plt.savefig(file_name)
        #plt.show()
        return fig


class PlotAntennaPattern3D(object):
    """
    Plots imt antenna pattern.
    """

    def __init__(self, figs_dir):
        self.figs_dir = figs_dir

    def plot_element_pattern3D(self,
                               antenna: AntennaBeamformingImt,
                               sta_type: str,
                               plot_type: str, peso):

        phi_escan = 0
        theta_tilt = 120

        # Plot horizontal pattern
        phi = np.linspace(-180, 180, num=180)
        theta = theta_tilt * np.ones(np.size(phi))

        if plot_type == "ELEMENT":
            gain = antenna.element.element_pattern(phi, theta)
        elif plot_type == "ARRAY":
            antenna.add_beam(phi_escan, theta_tilt, peso)
            gainh = antenna.calculate_gain(phi_vec=phi,
                                           theta_vec=theta,
                                           beams_l=np.zeros_like(phi, dtype=int))
            gainh = gainh

        #
        # top_y_lim = np.ceil(np.max(gainh)/10)*10
        #
        # fig = plt.figure(figsize=(15, 5), facecolor='w', edgecolor='k')
        # ax1 = fig.add_subplot(121)
        #
        # #ax1.plot(phi, gainh)
        # ax1.grid(True)
        # ax1.set_xlabel(r"$\varphi$ [deg]")
        # ax1.set_ylabel("Gain [dBi]")
        #
        # if plot_type == "ELEMENT":
        #     ax1.set_title("HIBS" + sta_type + " element horizontal antenna pattern")
        # elif plot_type == "ARRAY":
        #     ax1.set_title("HIBS" + sta_type + " horizontal antenna pattern")
        #
        # ax1.set_xlim(-180, 180)

        # Plot vertical pattern
        theta = np.linspace(0, 180, num=180)
        phi = phi_escan * np.ones(np.size(theta))

        if plot_type == "ELEMENT":
            gain = antenna.element.element_pattern(phi, theta)
        elif plot_type == "ARRAY":
            gainv = antenna.calculate_gain(phi_vec=phi,
                                           theta_vec=theta,
                                           beams_l=np.zeros_like(phi, dtype=int))
            gainv = gainv

        # ax2 = fig.add_subplot(122, sharey=ax1)
        #
        # #ax2.plot(theta, gainv)
        # ax2.grid(True)
        # ax2.set_xlabel(r"$\theta$ [deg]")
        # ax2.set_ylabel("Gain [dBi]")
        #
        # if plot_type == "ELEMENT":
        #     ax2.set_title("HIBS" + sta_type + " element vertical antenna pattern")
        # elif plot_type == "ARRAY":
        #     ax2.set_title("HIBS" + sta_type + " vertical antenna pattern")
        #
        # ax2.set_xlim(0, 180)
        # if np.max(gainv) > top_y_lim:
        #     top_y_lim = np.ceil(np.max(gainv)/10)*10
        # ax2.set_ylim(top_y_lim - 130, top_y_lim)
        #
        # if sta_type == "BS":
        #     file_name = self.figs_dir + "bs_"
        # else:  # sta_type == "UE":
        #     file_name = self.figs_dir + "ue_"
        #
        # if plot_type == "ELEMENT":
        #     file_name = file_name + "element_pattern.png"
        # elif plot_type == "ARRAY":
        #     file_name = file_name + "array_pattern.png"

        # plt.savefig(file_name)

        ######################################################################################################
        ######################################################################################################
        ######################################################################################################
        # # spherical coordinates
        # PHI, THETA = np.meshgrid(np.linspace(0, 360, 1000), np.linspace(0, 180, 1000))
        # # THETA, PHI = np.meshgrid(x, y)
        #
        # X, Y = np.sin(np.radians(PHI)) * np.cos(np.radians(THETA)), np.sin(np.radians(PHI)) * np.sin(np.radians(THETA))
        #
        # Z = Z = np.cos(np.radians(THETA)) + (gainv + gainh - np.max(gainv))
        #
        # fig = plt.figure(figsize=(10, 10))
        # ax = fig.gca(projection='3d')
        # # surf = ax.plot_surface(x, y, X + Y-np.max(gainv), cstride=1, rstride=1, cmap='rainbow', antialiased=True, alpha=1)
        # surf = ax.plot_surface(X, Y, Z, cstride=1, rstride=1, cmap='rainbow', antialiased=True, alpha=1)
        # fig.colorbar(surf, ax=ax,
        #              shrink=0.5,
        #              aspect=20, ticks=np.linspace(-250, np.max(gainv), 10))
        # ax.view_init(elev=25., azim=0)
        # ax.set_title('3D Antenna Pattern')
        # ax.set_xlabel('azimuth [degrees]')
        # ax.set_ylabel('elevation [degrees]')
        # ax.grid(False)
        # plt.show()

        ######################################################################################################
        ######################################################################################################
        ######################################################################################################
        x, y = np.meshgrid(np.linspace(-180, 180, 180), np.linspace(0, 180, 180))

        X, Y = np.meshgrid(gainh, gainv, sparse=False)
        clevs1 = np.arange(-250, np.max(gainv) + 10, 1)
        cs1 = plt.contourf(x, y, X + Y - np.max(gainv), clevs1, cmap='viridis', alpha=1)
        plt.colorbar(cs1)
        plt.xlabel('azimuth [degrees]')
        plt.ylabel('elevation [degrees]')

        fig = plt.figure(figsize=(10, 10))
        #ax = fig.gca(projection='3d')
        #surf = ax.plot_surface(x, y, X + Y-np.max(gainv), cstride=1, rstride=1, cmap='rainbow', antialiased=True,
        #                       alpha=1)
        #surf = ax.plot_surface(X, Y, Z, cstride=1, rstride=1, cmap='rainbow', antialiased=True, alpha=1)
        #fig.colorbar(surf, ax=ax,
        #             shrink=0.5,
        #             aspect=30, ticks=np.linspace(-220, np.max(gainv), 10))

        # ax.view_init(elev=35., azim=0)
        #ax.set_title('3D Antenna Pattern')
        #ax.set_xlabel('azimuth [degrees]')
        #ax.set_ylabel('elevation [degrees]')
        #ax.grid(False)
        plt.show()
        return fig


if __name__ == '__main__':
    figs_dir = "figs/"

    param = ParametersAntennaImt()
    param.co_channel = True
    param.adjacent_antenna_model = "BEAMFORMING"
    param.bs_normalization = True
    param.ue_normalization = False
    param.bs_normalization_file = 'beamforming_normalization\\bs_norm_8x8_050.npz'
    param.ue_normalization_file = 'beamforming_normalization\\ue_4x4_46_12.npz'
    param.bs_minimum_array_gain = -200
    param.ue_minimum_array_gain = -200
    param.bf_enable = "ON"

    param.bs_element_pattern = "M2101"
    param.bs_element_max_g = 5.5
    param.bs_element_phi_3db = 90
    param.bs_element_theta_3db = 90
    param.bs_element_am = 30
    param.bs_element_sla_v = 30
    param.bs_n_rows = 8
    param.bs_n_columns = 8
    param.bs_element_horiz_spacing = 0.5
    param.bs_element_vert_spacing = 0.5
    param.bs_multiplication_factor = 12
    param.bs_downtilt = 0

    param.ue_element_pattern = "M2101"
    param.ue_element_max_g = - 3
    param.ue_element_phi_3db = 90
    param.ue_element_theta_3db = 90
    param.ue_element_am = 25
    param.ue_element_sla_v = 25
    param.ue_n_rows = 2
    param.ue_n_columns = 2
    param.ue_element_horiz_spacing = 0.5
    param.ue_element_vert_spacing = 0.5
    param.ue_multiplication_factor = 12

    #plot = PlotAntennaPattern(figs_dir)

    # Plot BS TX radiation patterns
    par = param.get_antenna_parameters(StationType.IMT_BS)
    bs_array = AntennaBeamformingImt(par, 0, 0)
    #f = plot.plot_element_pattern(bs_array, " Base Station", "ELEMENT")
    # f.savefig(figs_dir + "BS_element.pdf", bbox_inches='tight')
    #f = plot.plot_element_pattern(bs_array, " Base Station", "ARRAY")
    # f.savefig(figs_dir + "BS_array.pdf", bbox_inches='tight')


    ###################################################################################################################

    figs_dir = "figs/"

    param1 = ParametersAntennaImt()
    param1.co_channel = True
    param1.adjacent_antenna_model = "BEAMFORMING"
    param1.bs_normalization = False
    param1.ue_normalization = False
    param1.bs_normalization_file = 'beamforming_normalization\\bs_8x8_46_12.npz'
    param1.ue_normalization_file = 'beamforming_normalization\\ue_4x4_46_12.npz'
    param1.bs_minimum_array_gain = -200
    param1.ue_minimum_array_gain = -200
    param1.bf_enable = "ON"

    param1.bs_element_pattern = "M2101"
    param1.bs_element_max_g = 5.5
    param1.bs_element_phi_3db = 90
    param1.bs_element_theta_3db = 90
    param1.bs_element_am = 30
    param1.bs_element_sla_v = 30
    param1.bs_n_rows = 8
    param1.bs_n_columns = 8
    param1.bs_element_horiz_spacing = 0.5
    param1.bs_element_vert_spacing = 0.5
    param1.bs_multiplication_factor = 12
    param1.bs_downtilt = 0

    param1.ue_element_pattern = "M2101"
    param1.ue_element_max_g = - 3
    param1.ue_element_phi_3db = 90
    param1.ue_element_theta_3db = 90
    param1.ue_element_am = 25
    param1.ue_element_sla_v = 25
    param1.ue_n_rows = 2
    param1.ue_n_columns = 2
    param1.ue_element_horiz_spacing = 0.5
    param1.ue_element_vert_spacing = 0.5
    param1.ue_multiplication_factor = 12
    #
    plot1 = PlotAntennaPattern(figs_dir)
    plot3D = PlotAntennaPattern3D(figs_dir)
    # Plot BS TX radiation patterns
    par1 = param1.get_antenna_parameters(StationType.IMT_BS)
    bs_array1 = AntennaBeamformingImt(par1, 0, 0)
    #f = plot.plot_element_pattern(bs_array1, " Base Station", "ELEMENT")
    # f.savefig(figs_dir + "BS_element.pdf", bbox_inches='tight')

    f = plot1.plot_element_pattern(bs_array1, " Base Station", "ARRAY", "Beamforming d/λ = 0.5, k = 12", 0)
    f1 = plot1.plot_element_pattern(bs_array, " Base Station", "ARRAY", "Beamforming d/λ = 0.5, k = 12, Weighting", 1)
    # f.savefig(figs_dir + "BS_array.pdf", bbox_inches='tight')
    #d = plot3D.plot_element_pattern3D(bs_array1, " Base Station", "ARRAY", 0)
    #d1 = plot3D.plot_element_pattern3D(bs_array, " Base Station", "ARRAY", 1)

    # Plot UE TX radiation patterns
    # par = param.get_antenna_parameters(StationType.IMT_UE)
    # ue_array = AntennaBeamformingImt(par, 0, 0)
    # plot.plot_element_pattern(ue_array, " User Equipment", "ELEMENT")
    # plot.plot_element_pattern(ue_array, " User Equipment", "ARRAY")
    plt.show()
    print('END')