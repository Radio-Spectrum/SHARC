# -*- coding: utf-8 -*-
"""
Created on Thu Jun 29 13:49:09 2017

@author: edgar
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.parameters.parameters_imt import ParametersImt
from sharc.parameters.parameters_ntn import ParametersNTN
from sharc.parameters.parameters_antenna_imt import ParametersAntennaImt
from sharc.station_factory import StationFactory
from sharc.topology.topology_ntn import TopologyNTN


class StationFactoryTest(unittest.TestCase):
    """Test cases for StationFactory."""

    def setUp(self):
        self.station_factory = StationFactory()

    def test_generate_imt_base_stations(self):
        pass

    def test_generate_imt_base_stations_ntn(self):
        """Test for IMT-NTN space station generation."""
        seed = 100
        rng = np.random.RandomState(seed)

        param_imt = ParametersImt()
        param_imt.topology = "NTN"

        param_bs_ant = ParametersAntennaImt()

        # Paramters for IMT-NTN
        param_ntn = ParametersNTN()
        param_ntn.bs_height = 1200000  # meters
        param_ntn.cell_radius = 45000  # meters
        param_ntn.bs_azimuth = 60  # degrees
        param_ntn.bs_elevation = 45  # degrees
        param_ntn.num_sectors = 1

        ntn_topology = TopologyNTN(
            param_ntn.intersite_distance,
            param_ntn.cell_radius,
            param_ntn.bs_height,
            param_ntn.bs_azimuth,
            param_ntn.bs_elevation,
            param_ntn.num_sectors)

        ntn_topology.calculate_coordinates()
        ntn_bs = StationFactory.generate_imt_base_stations(param_imt, param_bs_ant, ntn_topology, rng)
        npt.assert_equal(ntn_bs.height, param_ntn.bs_height)
        # the azimuth seen from BS antenna
        npt.assert_almost_equal(ntn_bs.azimuth[0], param_ntn.bs_azimuth - 180, 1e-3)
        # Elevation w.r.t to xy plane
        npt.assert_almost_equal(ntn_bs.elevation[0], -45.0, 1e-2)
        npt.assert_almost_equal(ntn_bs.x, param_ntn.bs_height * np.tan(np.radians(param_ntn.bs_elevation)) *
                                np.cos(np.radians(param_ntn.bs_azimuth)), 1e-2)

    def test_generate_imt_ue_outdoor_ntn(self):
        """Basic test for IMT UE NTN generation."""
        seed = 100
        rng = np.random.RandomState(seed)

        # Parameters used for IMT-NTN and UE distribution
        param_imt = ParametersImt()
        param_imt.topology = "NTN"
        param_imt.azimuth_range = (-180, 180)
        param_imt.ue_distribution_type = "ANGLE_AND_DISTANCE"
        param_imt.ue_distribution_azimuth = "UNIFORM"
        param_imt.ue_distribution_distance = "UNIFORM"
        param_imt.ue_k = 1000

        # Paramters for IMT-NTN
        param_ntn = ParametersNTN()
        param_ntn.bs_height = 1200000  # meters
        param_ntn.cell_radius = 45000  # meters
        param_ntn.bs_azimuth = 60  # degrees
        param_ntn.bs_elevation = 45  # degrees
        param_ntn.num_sectors = 1

        ntn_topology = TopologyNTN(
            param_ntn.intersite_distance,
            param_ntn.cell_radius,
            param_ntn.bs_height,
            param_ntn.bs_azimuth,
            param_ntn.bs_elevation,
            param_ntn.num_sectors)

        ntn_topology.calculate_coordinates()
        param_ue_ant = ParametersAntennaImt()
        ntn_ue = StationFactory.generate_imt_ue_outdoor(param_imt, param_ue_ant, rng, ntn_topology)
        dist = np.sqrt(ntn_ue.x**2 + ntn_ue.y**2)
        # test if the maximum distance is close to the cell radius within a 100km range
        npt.assert_almost_equal(dist.max(), param_ntn.cell_radius, -2)


if __name__ == '__main__':
    unittest.main()
