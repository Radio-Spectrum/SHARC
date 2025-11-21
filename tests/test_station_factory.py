# -*- coding: utf-8 -*-
"""
Created on Thu Jun 29 13:49:09 2017

@author: edgar
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.station_factory import StationFactory
from sharc.topology.topology_ntn import TopologyNTN
from sharc.topology.topology_single_base_station import TopologySingleBaseStation
from sharc.parameters.parameters_single_space_station import ParametersSingleSpaceStation
from sharc.station_manager import StationManager
from sharc.antenna.antenna_mss_adjacent import AntennaMSSAdjacent
from sharc.satellite.ngso.constants import EARTH_RADIUS_M


class StationFactoryTest(unittest.TestCase):
    """Test cases for StationFactory."""

    def setUp(self):
        """Set up a StationFactory instance for testing."""
        self.station_factory = StationFactory()

    def test_generate_imt_base_stations(self):
        """Test IMT base station generation (placeholder)."""

    def test_generate_imt_base_stations_oob_antennas(self):
        """Test IMT base station generation with and without out-of-band antennas."""
        rng = np.random.RandomState(42)
        param_imt = ParametersImt()

        # First test with ARRAY antenna pattern. The oob antenna should be the same object.
        param_imt.bs.antenna.pattern = "ARRAY"
        param_imt.bs.use_oob_antenna = True

        param_imt.topology.type = "SINGLE_BS"
        param_imt.topology.single_bs.num_clusters = 1
        param_imt.topology.single_bs.intersite_distance = 500
        param_imt.topology.single_bs.cell_radius = 500
        param_imt.topology.single_bs.azimuth = "random"

        param_imt.validate("station factory test")

        single_bs_topology = TopologySingleBaseStation(
            param_imt.topology.single_bs.cell_radius,
            param_imt.topology.single_bs.num_clusters,
            param_imt.topology.single_bs.azimuth,
        )

        single_bs_topology.calculate_coordinates()

        imt_bs = StationFactory.generate_imt_base_stations(
            param_imt, param_imt.bs.antenna.array, single_bs_topology, rng)

        # When the in-band antenna is ARRAY, the oob antenna should be the same object
        self.assertIs(imt_bs.oob_antenna, imt_bs.antenna)  # both should point to the same list

        # What if the user sets a non-ARRAY oob-antenna pattern but the in-band is ARRAY?
        param_imt.bs.oob_antenna.pattern = "MSS Adjacent"
        param_imt.bs.oob_antenna.gain = 0.0
        param_imt.bs.oob_antenna.mss_adjacent.frequency = 2000.0
        param_imt.validate("station factory test 2")
        imt_bs = StationFactory.generate_imt_base_stations(
            param_imt, param_imt.bs.antenna.array, single_bs_topology, rng)
        # When the in-band antenna is ARRAY, the oob antenna should be the same object no matter what
        self.assertIs(imt_bs.oob_antenna, imt_bs.antenna)  # both should point to the same list

        # Now test with non-ARRAY antenna pattern. The oob antenna should be a different object.
        # Re-create the imt_bs with a non-ARRAY oob-antenna pattern
        param_imt.bs.use_oob_antenna = True
        param_imt.bs.antenna.gain = 30.0
        param_imt.bs.antenna.pattern = "ITU-R-S.1528-Taylor"
        param_imt.bs.antenna.itu_r_s_1528.frequency = 2000.0
        param_imt.bs.antenna.itu_r_s_1528.bandwidth = 5.0
        param_imt.bs.antenna.itu_r_s_1528.slr = 20.0
        param_imt.bs.antenna.itu_r_s_1528.n_side_lobes = 2
        param_imt.bs.oob_antenna.pattern = "MSS Adjacent"
        param_imt.bs.oob_antenna.gain = 0.0
        param_imt.bs.oob_antenna.mss_adjacent.frequency = 2000.0
        param_imt.validate("station factory test 2")

        imt_bs = StationFactory.generate_imt_base_stations(
            param_imt, param_imt.bs.antenna.array, single_bs_topology, rng)

        # When the in-band antenna is not ARRAY, the oob antenna should be a different object
        self.assertIsNot(imt_bs.oob_antenna, imt_bs.antenna)
        for oob_antenna in imt_bs.oob_antenna:
            self.assertIsInstance(oob_antenna, AntennaMSSAdjacent)

    def test_generate_imt_base_stations_ntn(self):
        """Test for IMT-NTN space station generation."""
        # seed = 100  # Unused variable removed
        rng = np.random.RandomState(100)

        param_imt = ParametersImt()
        param_imt.topology.type = "NTN"

        # Paramters for IMT-NTN
        param_imt.topology.ntn.bs_height = 1200000  # meters
        param_imt.topology.ntn.cell_radius = 45000  # meters
        param_imt.topology.ntn.bs_azimuth = 60  # degrees
        param_imt.topology.ntn.bs_elevation = 45  # degrees
        param_imt.topology.ntn.num_sectors = 1

        ntn_topology = TopologyNTN(
            param_imt.topology.ntn.intersite_distance,
            param_imt.topology.ntn.cell_radius,
            param_imt.topology.ntn.bs_height,
            param_imt.topology.ntn.bs_azimuth,
            param_imt.topology.ntn.bs_elevation,
            param_imt.topology.ntn.num_sectors,
        )

        ntn_topology.calculate_coordinates()
        ntn_bs = StationFactory.generate_imt_base_stations(
            param_imt, param_imt.bs.antenna.array, ntn_topology, rng)
        npt.assert_equal(ntn_bs.height, param_imt.topology.ntn.bs_height)
        # the azimuth seen from BS antenna
        npt.assert_almost_equal(
            ntn_bs.azimuth[0],
            param_imt.topology.ntn.bs_azimuth - 180,
            1e-3)
        # Elevation w.r.t to xy plane
        npt.assert_almost_equal(ntn_bs.elevation[0], -45.0, 1e-2)
        npt.assert_almost_equal(
            ntn_bs.x, param_imt.topology.ntn.bs_height *
            np.tan(np.radians(param_imt.topology.ntn.bs_elevation)) *
            np.cos(np.radians(param_imt.topology.ntn.bs_azimuth)), 1e-2,
        )

    def test_generate_imt_ue_outdoor_ntn(self):
        """Basic test for IMT UE NTN generation."""
        seed = 100
        rng = np.random.RandomState(seed)

        # Parameters used for IMT-NTN and UE distribution
        param_imt = ParametersImt()
        param_imt.topology.type = "NTN"
        param_imt.ue.azimuth_range = (-180, 180)
        param_imt.ue.distribution_type = "ANGLE_AND_DISTANCE"
        param_imt.ue.distribution_azimuth = "UNIFORM"
        param_imt.ue.distribution_distance = "UNIFORM"
        param_imt.ue.k = 1000

        # Paramters for IMT-NTN
        param_imt.topology.ntn.bs_height = 1200000  # meters
        param_imt.topology.ntn.cell_radius = 45000  # meters
        param_imt.topology.ntn.bs_azimuth = 60  # degrees
        param_imt.topology.ntn.bs_elevation = 45  # degrees
        param_imt.topology.ntn.num_sectors = 1

        ntn_topology = TopologyNTN(
            param_imt.topology.ntn.intersite_distance,
            param_imt.topology.ntn.cell_radius,
            param_imt.topology.ntn.bs_height,
            param_imt.topology.ntn.bs_azimuth,
            param_imt.topology.ntn.bs_elevation,
            param_imt.topology.ntn.num_sectors,
        )

        ntn_topology.calculate_coordinates()
        ntn_ue = StationFactory.generate_imt_ue_outdoor(
            param_imt, param_imt.ue.antenna.array, rng, ntn_topology)
        dist = np.sqrt(ntn_ue.x**2 + ntn_ue.y**2)
        # test if the maximum distance is close to the cell radius within a
        # 100km range
        npt.assert_almost_equal(
            dist.max(), param_imt.topology.ntn.cell_radius, -2)

    def test_generate_single_space_station(self):
        """Basic test for space station generation."""

        param = ParametersSingleSpaceStation()
        # just passing required parameters:
        param.frequency = 8000
        param.bandwidth = 100
        param.channel_model = "P619"
        param.tx_power_density = -200
        param.geometry.es_altitude = 0
        param.geometry.azimuth.fixed = 0
        param.antenna.pattern = "OMNI"
        param.antenna.gain = 10

        param.geometry.location.type = "FIXED"
        param.geometry.altitude = 35786000.0
        param.geometry.es_lat_deg = 0
        param.geometry.es_long_deg = 0
        param.geometry.location.fixed.lat_deg = 0
        param.geometry.location.fixed.long_deg = 0

        param.propagate_parameters()
        # This should not error on this test:
        param.validate()

        # experimental from simulator
        max_gso_fov = 81.299501

        def get_ground_elevation(ss):
            return np.rad2deg(
                np.arctan2(
                    ss.height,
                    np.sqrt(
                        ss.x**2 +
                        ss.y**2)))

        space_station = StationFactory.generate_single_space_station(param)

        # test if the maximum distance is close to the cell radius within a
        # 100km range
        npt.assert_almost_equal(space_station.height, param.geometry.altitude)
        npt.assert_almost_equal(get_ground_elevation(space_station), 90)

        param.geometry.es_lat_deg = max_gso_fov

        space_station = StationFactory.generate_single_space_station(param)

        npt.assert_almost_equal(get_ground_elevation(space_station), 0, 5)
        npt.assert_almost_equal(space_station.height, 0, 0)

        param.geometry.es_lat_deg = 0
        param.geometry.es_long_deg = max_gso_fov

        space_station = StationFactory.generate_single_space_station(param)

        npt.assert_almost_equal(get_ground_elevation(space_station), 0, 5)
        npt.assert_almost_equal(space_station.height, 0, 0)

        param.geometry.es_long_deg = 0
        param.geometry.location.fixed.lat_deg = max_gso_fov

        space_station = StationFactory.generate_single_space_station(param)

        npt.assert_almost_equal(get_ground_elevation(space_station), 0, 5)
        npt.assert_almost_equal(space_station.height, 0, 0)

        param.geometry.location.fixed.lat_deg = 0
        param.geometry.location.fixed.long_deg = max_gso_fov

        space_station = StationFactory.generate_single_space_station(param)
        npt.assert_almost_equal(get_ground_elevation(space_station), 0, 5)
        npt.assert_almost_equal(space_station.height, 0, 0)

    def test_single_space_station_pointing(self):
        """Basic test for space station generation."""

        param = ParametersSingleSpaceStation()
        # just passing required parameters:
        param.frequency = 8000
        param.bandwidth = 100
        param.channel_model = "P619"
        param.tx_power_density = -200
        param.geometry.es_altitude = 0
        param.geometry.azimuth.fixed = 0
        param.antenna.pattern = "OMNI"
        param.antenna.gain = 10

        param.geometry.location.type = "FIXED"
        param.geometry.altitude = 35786000.0
        param.geometry.es_lat_deg = 0
        param.geometry.es_long_deg = 0
        param.geometry.es_altitude = 1200
        param.geometry.location.fixed.lat_deg = -5
        param.geometry.location.fixed.long_deg = 5

        param.propagate_parameters()
        # This should not error on this test:
        param.validate()

        imt_center = StationManager(1)
        imt_center.x = np.array([0.])
        imt_center.y = np.array([0.])
        imt_center.z = np.array([0.])

        # Test point it toward IMT center (0, 0, 0)
        param.geometry.azimuth.type = "POINTING_AT_IMT"
        param.geometry.elevation.type = "POINTING_AT_IMT"

        space_station = StationFactory.generate_single_space_station(param)

        npt.assert_almost_equal(space_station.get_off_axis_angle(imt_center), 0, 5)

        # Test pointing it toward IMT center (0, 0, 0)
        # but in another way
        param.geometry.azimuth.type = "POINTING_AT_LAT_LONG_ALT"
        param.geometry.elevation.type = "POINTING_AT_LAT_LONG_ALT"
        param.geometry.pointing_at_lat = 0
        param.geometry.pointing_at_long = 0
        param.geometry.pointing_at_alt = 1200

        space_station = StationFactory.generate_single_space_station(param)

        npt.assert_almost_equal(space_station.get_off_axis_angle(imt_center), 0, 5)

        # Test pointing it toward subsatellite.
        # In spherical earth model,
        # same as pointing toward center of earth
        center_of_earth = StationManager(1)

        center_of_earth.x = np.array([0.])
        center_of_earth.y = np.array([0.])
        center_of_earth.z = -np.array([EARTH_RADIUS_M + 1200])

        param.geometry.azimuth.type = "POINTING_AT_LAT_LONG_ALT"
        param.geometry.elevation.type = "POINTING_AT_LAT_LONG_ALT"
        param.geometry.pointing_at_lat = -5
        param.geometry.pointing_at_long = 5
        param.geometry.pointing_at_alt = 1200

        space_station = StationFactory.generate_single_space_station(param)

        npt.assert_almost_equal(space_station.get_off_axis_angle(center_of_earth), 0, 5)


if __name__ == '__main__':
    unittest.main()
