# -*- coding: utf-8 -*-
"""
Created on Mon Jun  5 16:56:13 2017

@author: edgar
"""

import numpy as np
import matplotlib.pyplot as plt

from sharc.support.enumerations import StationType
from sharc.propagation.propagation import Propagation
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.propagation.propagation import Propagation
from sharc.station_manager import StationManager
from sharc.parameters.parameters import Parameters
from sharc.propagation.propagation_path import PropagationPath


class PropagationTvro(Propagation):
    """
    Implements the propagation model used in paper
    Fernandes, Linhares, "Coexistence conditions of LTE-advanced at 3400-3600MHz with TVRO
                          at 3625-4200 MHz in Brazil", Wireless Networks, 2017
    TODO: calculate the effective environment height for the generic case
    """

    def __init__(
        self,
        random_number_gen: np.random.RandomState,
        environment: str,
    ):
        super().__init__(random_number_gen)
        if environment.upper() == "URBAN":
            self.d_k = 0.02  # km
            self.shadowing_std = 6
            self.h_a = 20
        elif environment.upper() == "SUBURBAN":
            self.d_k = 0.025  # km
            self.shadowing_std = 8
            self.h_a = 9
        self.building_loss = 20

        self.free_space_path_loss = PropagationFreeSpace(random_number_gen)

    def get_path_loss(
        self,
        params: Parameters,
        frequency: float,
        path: "PropagationPath",
        station_a_gains=None,
        station_b_gains=None,
    ) -> np.array:
        """Wrapper function for the PropagationUMi get_loss method
        Calculates the loss between station_a and station_b

        Parameters
        ----------
        station_a : StationManager
            StationManager container representing IMT UE station - Station_type.IMT_UE for IMT-IMT links or Sistem
            station for IMT-System links
        station_b : StationManager
            StationManager container representing IMT BS stattion
        params : Parameters
            Simulation parameters needed for the propagation class - Station_type.IMT_BS

        Returns
        -------
        np.array
            Return an array station_a.num_stations x station_b.num_stations with the path loss
            between each station
        """
        wrap_around_enabled = False
        if params.imt.topology.type == "MACROCELL":
            wrap_around_enabled = params.imt.topology.macrocell.wrap_around \
                and params.imt.topology.macrocell.num_clusters == 1
        if params.imt.topology.type == "HOTSPOT":
            wrap_around_enabled = params.imt.topology.hotspot.wrap_around \
                and params.imt.topology.hotspot.num_clusters == 1

        if wrap_around_enabled and (
                path.sta_a.is_imt_station() and path.sta_b.is_imt_station()):
            distances_2d, distances_3d, _, _ = \
                path.sta_a.geom.get_global_dist_angles_wrap_around(path.sta_b.geom)
        else:
            distances_2d = path.sta_a.geom.get_local_distance_to(path.sta_b.geom)
            distances_3d = path.sta_a.geom.get_3d_distance_to(path.sta_b.geom)

        indoor_stations = path.sta_a.indoor

        # Use the right interface whether the link is IMT-IMT or IMT-System
        # TODO: Refactor __get_loss and get rid of that if-else.
        if path.sta_a.is_imt_station() and path.sta_b.is_imt_station():
            if path.sta_a.geom.uses_local_coords:
                raise NotImplementedError(
                    "TVRO currently assumes UE z == height. "
                    "If UE has local coords != global coords, this probably isn't true"
                )
            mskd_distance_3d = path.mtx_to_masked(distances_3d)
            loss = self._get_loss(
                distance_3D=mskd_distance_3d,
                distance_2D=path.mtx_to_masked(distances_2d),
                frequency=frequency * np.ones(mskd_distance_3d.shape),
                ue_height=path.sta_a_to_masked(path.sta_a.geom.z_local),
                indoor_stations=path.sta_a_to_masked(indoor_stations)
            )
        else:
            imt_station, sys_station = (path.sta_a, path.sta_b) \
                if path.sta_a.is_imt_station() else (path.sta_b, path.sta_a)

            if sys_station.geom.uses_local_coords:
                raise NotImplementedError(
                    "TVRO currently assumes System z == height. "
                    "If System has local coords != global coords, this probably isn't true"
                )

            es_z = sys_station.geom.z_local
            if sys_station == path.sta_a:
                es_z = path.sta_a_to_masked(es_z)
            else:
                es_z = path.sta_b_to_masked(es_z)

            mskd_distance_3d = path.mtx_to_masked(distances_3d)
            loss = self._get_loss(
                distance_3D=mskd_distance_3d,
                distance_2D=path.mtx_to_masked(distances_2d),
                frequency=frequency * np.ones(mskd_distance_3d.shape),
                imt_sta_type=imt_station.station_type,
                es_z=es_z,
                indoor_stations=path.sta_a_to_masked(indoor_stations)
            )

        return path.from_masked_mtx(loss)

    def _get_loss(self, *args, **kwargs) -> np.array:
        """
        Calculates path loss

        Parameters
        ----------
            distance_3D (np.array) : 3D distances between stations
            distance_2D (np.array) : 2D distances between stations
            frequency (np.array) : center frequencie [MHz]
        Returns
        -------
            array with path loss values with dimensions of distance_2D

        """
        distance_3D = kwargs["distance_3D"]
        frequency = kwargs["frequency"]
        # shadowing is enabled by default
        shadowing = kwargs.pop("shadowing", True)
        indoor_stations = kwargs["indoor_stations"]

        if "imt_sta_type" in kwargs.keys():
            # calculating path loss for the IMT-system link
            height = kwargs["es_z"]
            # check if IMT staton is BS or UE
            imt_sta_type = kwargs["imt_sta_type"]
            if imt_sta_type is StationType.IMT_BS:
                loss = self.get_loss_macrocell(
                    distance_3D,
                    frequency,
                    height,
                    indoor_stations,
                    shadowing,
                )
            else:
                loss = self.get_loss_microcell(
                    distance_3D,
                    frequency,
                    indoor_stations,
                    shadowing,
                )
        else:
            # calculating path loss for the IMT-IMT link
            height = kwargs["ue_height"]
            loss = self.get_loss_macrocell(
                distance_3D,
                frequency,
                height,
                indoor_stations,
                shadowing,
            )

        return loss

    def get_loss_microcell(
        self,
        distance_3D: np.array,
        frequency: np.array,
        indoor_stations: np.array,
        shadowing,
    ) -> np.array:
        """Calculate the microcell path loss for TVRO-IMT scenarios.

        Parameters
        ----------
        distance_3D : np.array
            3D distance array between stations.
        frequency : np.array
            Frequency array for the links.
        indoor_stations : np.array
            Boolean array indicating indoor stations.
        shadowing : bool
            Whether to include shadow fading.

        Returns
        -------
        np.array
            Path loss values for the microcell scenario.
        """
        pl_los = 102.93 + 20 * np.log10(distance_3D / 1000)
        pl_nlos = 153.5 + 40 * np.log10(distance_3D / 1000)
        pr_los = self.get_los_probability(distance_3D)
        loss = pl_los * pr_los + pl_nlos * (1 - pr_los)

        if shadowing:
            shadowing_fading = self.random_number_gen.normal(
                0,
                3.89,
                loss.shape,
            )
            loss = loss + shadowing_fading

        loss = loss + self.building_loss * indoor_stations

        free_space_path_loss = self.free_space_path_loss.get_free_space_loss(
            distance=distance_3D,
            frequency=frequency,
        )
        loss = np.maximum(loss, free_space_path_loss)

        return loss

    def get_loss_macrocell(
        self,
        distance_3D: np.array,
        frequency: np.array,
        height: np.array,
        indoor_stations: np.array,
        shadowing: bool,
    ) -> np.array:
        """Calculate the macrocell path loss for TVRO-IMT scenarios.

        Parameters
        ----------
        distance_3D : np.array
            3D distance array between stations.
        frequency : np.array
            Frequency array for the links.
        height : np.array
            Height array for the user equipment.
        indoor_stations : np.array
            Boolean array indicating indoor stations.
        shadowing : bool
            Whether to include shadow fading.

        Returns
        -------
        np.array
            Path loss values for the macrocell scenario.
        """

        free_space_path_loss = self.free_space_path_loss.get_free_space_loss(
            distance=distance_3D,
            frequency=frequency,
        )

        f_fc = .25 + .375 * (1 + np.tanh(7.5 * (frequency / 1000 - .5)))
        clutter_loss = 10.25 * f_fc * np.exp(-self.d_k) * \
            (1 - np.tanh(6 * (height[:, np.newaxis] / self.h_a - .625))) - .33

        loss = free_space_path_loss.copy()

        indices = (distance_3D >= 40) & (distance_3D < 10 * self.d_k * 1000)
        loss[indices] = loss[indices] + \
            (distance_3D[indices] / 1000 - 0.04) / \
            (10 * self.d_k - 0.04) * clutter_loss[indices]

        indices = (distance_3D >= 10 * self.d_k * 1000)
        loss[indices] = loss[indices] + clutter_loss[indices]

        loss = loss + self.building_loss * indoor_stations

        if shadowing:
            shadowing_fading = self.random_number_gen.normal(
                0,
                self.shadowing_std,
                loss.shape,
            )
            loss = loss + shadowing_fading

        loss = np.maximum(loss, free_space_path_loss)

        return loss

    def get_los_probability(
        self,
        distance: np.array,
        distance_transition: float = 70,
    ) -> np.array:
        """
        Returns the line-of-sight (LOS) probability

        Parameters
        ----------
            distance : distance between transmitter and receiver [m]
            distance_transition : transition distance from LOS to NLOS [m]

        Returns
        -------
            LOS probability as a numpy array with same length as distance
        """
        p_los = 1 / (1 + (1 / np.exp(-0.1 * (distance - distance_transition))))
        return p_los


if __name__ == '__main__':
    distance_2D = np.linspace(10, 1000, num=1000)[:, np.newaxis]
    frequency = 3600 * np.ones(distance_2D.shape)
    h_bs = 25 * np.ones(len(distance_2D[:, 0]))
    h_ue = 1.5 * np.ones(len(distance_2D[0, :]))
    h_tvro = 6 * np.ones(len(distance_2D[0, :]))
    distance_3D = np.sqrt(distance_2D**2 + (h_bs[:, np.newaxis] - h_ue)**2)
    indoor_stations = np.zeros(distance_3D.shape, dtype=bool)
    shadowing = False

    rand_gen = np.random.RandomState(101)
    prop_urban = PropagationTvro(rand_gen, "URBAN")
    prop_suburban = PropagationTvro(rand_gen, "SUBURBAN")
    prop_free_space = PropagationFreeSpace(rand_gen)

    loss_urban_bs_ue = prop_urban._get_loss(
        distance_3D=distance_3D,
        frequency=frequency,
        indoor_stations=indoor_stations,
        shadowing=shadowing,
        ue_height=h_ue,
    )
    loss_suburban_bs_ue = prop_suburban._get_loss(
        distance_3D=distance_3D,
        frequency=frequency,
        indoor_stations=indoor_stations,
        shadowing=shadowing,
        ue_height=h_ue,
    )

    loss_urban_bs_tvro = prop_urban._get_loss(
        distance_3D=distance_3D,
        frequency=frequency,
        indoor_stations=indoor_stations,
        shadowing=shadowing,
        imt_sta_type=StationType.IMT_BS,
        es_z=h_tvro,
    )
    loss_suburban_bs_tvro = prop_suburban._get_loss(
        distance_3D=distance_3D,
        frequency=frequency,
        indoor_stations=indoor_stations,
        shadowing=shadowing,
        imt_sta_type=StationType.IMT_BS,
        es_z=h_tvro,
    )

    loss_ue_tvro = prop_urban._get_loss(
        distance_3D=distance_3D,
        frequency=frequency,
        indoor_stations=indoor_stations,
        imt_sta_type=StationType.IMT_UE,
        shadowing=shadowing,
        es_z=h_tvro,
    )

    loss_fs = prop_free_space.get_free_space_loss(
        distance=distance_3D,
        frequency=frequency,
    )

    fig = plt.figure(figsize=(7, 5), facecolor='w', edgecolor='k')
    ax = fig.gca()

    ax.semilogx(
        distance_3D, loss_urban_bs_tvro, "-r",
        label="urban, BS-to-TVRO", linewidth=1,
    )
    ax.semilogx(
        distance_3D, loss_suburban_bs_tvro, "--r",
        label="suburban, BS-to-TVRO", linewidth=1,
    )
    ax.semilogx(
        distance_3D, loss_urban_bs_ue, "-b",
        label="urban, BS-to-UE", linewidth=1,
    )
    ax.semilogx(
        distance_3D, loss_suburban_bs_ue, "--b",
        label="suburban, BS-to-UE", linewidth=1,
    )
    ax.semilogx(
        distance_3D, loss_ue_tvro, "-.y",
        label="UE-to-TVRO", linewidth=1,
    )
    ax.semilogx(distance_3D, loss_fs, "-g", label="free space", linewidth=1.5)

    plt.title("Path loss (no shadowing)")
    plt.xlabel("distance [m]")
    plt.ylabel("path loss [dB]")
    plt.xlim((distance_3D[0, 0], distance_3D[-1, 0]))
    plt.ylim((70, 140))
    plt.legend(loc="upper left")
    plt.tight_layout()
    plt.grid()

    # plt.show()

    ###########################################################################
    p_los = prop_urban.get_los_probability(distance_3D)
    fig = plt.figure(figsize=(7, 5), facecolor='w', edgecolor='k')
    ax = fig.gca()

    ax.semilogy(distance_3D, p_los, "-r", linewidth=1)

    plt.title("LOS probability")
    plt.xlabel("distance [m]")
    plt.ylabel("probability")
    plt.xlim((distance_3D[0, 0], 200))
    plt.ylim((1e-6, 1))
    plt.tight_layout()
    plt.grid()

    plt.show()
