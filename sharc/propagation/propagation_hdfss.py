# -*- coding: utf-8 -*-
"""
Created on Tue Aug 28 13:57:48 2018

@author: Calil
"""

import numpy as np
import sys

from sharc.parameters.parameters_fss_es import ParametersFssEs
from sharc.propagation.propagation import Propagation
from sharc.station_manager import StationManager
from sharc.parameters.parameters import Parameters
from sharc.propagation.propagation_hdfss_roof_top import PropagationHDFSSRoofTop
from sharc.propagation.propagation_hdfss_building_side import PropagationHDFSSBuildingSide
from sharc.propagation.propagation_path import PropagationPath


class PropagationHDFSS(Propagation):
    """
    High-Density Fixed Satellite System Propagation Model
    This is a compoposition of HDFSS Rooftop and Indoor models using during simulation run-time.
    """

    def __init__(
            self,
            param: ParametersFssEs,
            rnd_num_gen: np.random.RandomState):
        super().__init__(rnd_num_gen)

        if param.es_position == "ROOFTOP":
            self.propagation = PropagationHDFSSRoofTop(param, rnd_num_gen)
        elif param.es_position == "BUILDINGSIDE":
            self.propagation = PropagationHDFSSBuildingSide(param, rnd_num_gen)
        else:
            sys.stderr.write(
                "ERROR\nInvalid es_position: " + param.es_position,
            )
            sys.exit(1)

    def get_path_loss(
        self,
        params: Parameters,
        frequency: float,
        path: PropagationPath,
        station_a_gains=None,
        station_b_gains=None,
    ) -> np.array:
        """Wrapper function for the get_loss method to fit the Propagation ABC class interface
        Calculates the loss between station_a and station_b

        Parameters
        ----------
        params : Parameters
            Simulation parameters needed for the propagation class
        frequency: float
            Center frequency
        station_a : StationManager
            StationManager container representing the system station
        station_b : StationManager
            StationManager container representing the IMT station
        station_a_gains: np.ndarray defaults to None
            System antenna gains
        station_b_gains: np.ndarray defaults to None
            IMT antenna gains

        Returns
        -------
        np.array
            Return an array station_a.num_stations x station_b.num_stations with the path loss
            between each station
        """
        distance = path.sta_a.geom.get_3d_distance_to(path.sta_b.geom)  # P.452 expects Kms
        distance = path.mtx_to_masked(distance)

        elevation = path.sta_b.geom.get_local_elevation(path.sta_a.geom)
        elevation = path.mtx_to_masked(elevation.T)

        frequency_array = frequency * np.ones(distance.shape)  # P.452 expects GHz

        if path.sta_a.geom.uses_local_coords or path.sta_b.geom.uses_local_coords:
            raise NotImplementedError(
                "HDFSS currently assumes stations z == height. "
                "If stations has local coords != global coords, this probably isn't true"
            )

        loss, build_loss, diff_loss = self.propagation.get_loss(
            distance_3D=distance,
            elevation=elevation,
            imt_sta_type=path.sta_b.station_type,
            frequency=frequency_array,
            imt_x=path.sta_b_to_masked(path.sta_b.geom.x_global),
            imt_y=path.sta_b_to_masked(path.sta_b.geom.y_global),
            imt_z=path.sta_b_to_masked(path.sta_b.geom.z_global),
            es_x=path.sta_a_to_masked(path.sta_a.geom.x_global),
            es_y=path.sta_a_to_masked(path.sta_a.geom.y_global),
            es_z=path.sta_a_to_masked(path.sta_a.geom.z_global),
        )
        return (
            path.from_masked_mtx(loss),
            path.from_masked_mtx(build_loss),
            path.from_masked_mtx(diff_loss)
        )
