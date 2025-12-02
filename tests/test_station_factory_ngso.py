import unittest
from sharc.parameters.parameters_mss_d2d import ParametersOrbit, ParametersMssD2d
from sharc.support.enumerations import StationType
from sharc.station_factory import StationFactory
from sharc.station_manager import StationManager
from sharc.antenna.antenna_element_cosine import AntennaElementCosine
from sharc.support.sharc_geom import CoordinateSystem, lla2ecef

import numpy as np
import numpy.testing as npt


class StationFactoryNgsoTest(unittest.TestCase):
    """Unit tests for NGSO station factory and related coordinate/antenna logic."""

    def setUp(self):
        """Set up NGSO constellation parameters and geometry for testing."""
        # Adding multiple shells to this constellation
        # Creating orbital parameters for the first orbit
        orbit_1 = ParametersOrbit(
            n_planes=20,                  # Number of orbital planes
            sats_per_plane=32,            # Satellites per plane
            phasing_deg=3.9,              # Phasing angle in degrees
            long_asc_deg=18.0,            # Longitude of ascending node
            inclination_deg=54.5,         # Orbital inclination in degrees
            perigee_alt_km=525.0,         # Perigee altitude in kilometers
            apogee_alt_km=525.0,           # Apogee altitude in kilometers
        )

        # Creating orbital parameters for the second orbit
        orbit_2 = ParametersOrbit(
            n_planes=12,                  # Number of orbital planes
            sats_per_plane=20,            # Satellites per plane
            phasing_deg=2.0,              # Phasing angle in degrees
            long_asc_deg=30.0,            # Longitude of ascending node
            inclination_deg=26.0,         # Orbital inclination in degrees
            perigee_alt_km=580.0,         # Perigee altitude in kilometers
            apogee_alt_km=580.0,           # Apogee altitude in kilometers
        )

        # Creating an NGSO constellation and adding the defined orbits
        self.lat = -15.7801
        self.long = -47.9292
        self.alt = 1200

        self.coord_sys = CoordinateSystem()
        self.coord_sys.set_reference(
            -15.7801,
            -47.9292,
            1200,
        )
        self.param = ParametersMssD2d(
            name="Acme-Star-1",                         # Name of the constellation
            antenna_pattern="ITU-R-S.1528-Taylor",     # Antenna type
            # List of orbital parameters
            orbits=[orbit_1, orbit_2],
            num_sectors=1,
        )
        self.param.antenna.pattern = "ITU-R-S.1528-Taylor"
        self.param.antenna.itu_r_s_1528.frequency = 43000.0
        self.param.antenna.itu_r_s_1528.bandwidth = 500.0
        self.param.antenna.itu_r_s_1528.antenna_gain = 46.6
        self.param.antenna.itu_r_s_1528.slr = 20.0
        self.param.antenna.itu_r_s_1528.n_side_lobes = 2
        self.param.antenna.itu_r_s_1528.l_r = 1.6
        self.param.antenna.itu_r_s_1528.l_t = 1.6

        self.param.propagate_parameters()
        self.param.validate("MSS_D2D_Test")

        # Creating an IMT topology
        # imt_topology = TopologySingleBaseStation(
        #     cell_radius=500,
        #     num_clusters=2,
        # )  # Unused variable removed

        # random number generator
        self.seed = 42
        rng = np.random.RandomState(seed=self.seed)

        self.ngso_manager = StationFactory.generate_mss_d2d(
            self.param, rng, self.coord_sys)

    def test_ngso_manager(self):
        """Test that the NGSO manager creates the correct number and type of stations."""
        self.assertEqual(self.ngso_manager.station_type, StationType.MSS_D2D)
        self.assertEqual(self.ngso_manager.num_stations, 20 * 32 + 12 * 20)
        self.assertEqual(self.ngso_manager.x.shape, (20 * 32 + 12 * 20,))
        self.assertEqual(self.ngso_manager.y.shape, (20 * 32 + 12 * 20,))
        self.assertEqual(self.ngso_manager.height.shape, (20 * 32 + 12 * 20,))

    def test_satellite_antenna_pointing(self):
        """Test that satellite antennas point to nadir and off-axis angles are correct."""
        # by default, satellites should always point to nadir (earth center)

        # Test: check if azimuth is pointing towards correct direction
        # y > 0 <=> azimuth < 0
        # y < 0 <=> azimuth > 0
        npt.assert_array_equal(
            np.sign(self.ngso_manager.azimuth), -np.sign(self.ngso_manager.y))

        # Test: check if center of earth is 0deg off axis, and that its
        # distance to satellite is correct
        earth_center = StationManager(1)
        earth_center.x = np.array([0.])
        earth_center.y = np.array([0.])
        x, y, z = lla2ecef(self.lat, self.long, self.alt)
        earth_center.z = -np.sqrt(
            x * x + y * y + z * z,
        )

        self.assertNotAlmostEqual(earth_center.z[0], 0.)

        off_axis_angle = self.ngso_manager.get_off_axis_angle(earth_center)
        distance_to_center_of_earth = self.ngso_manager.get_3d_distance_to(
            earth_center)
        distance_to_center_of_earth_should_eq = np.sqrt(
            self.ngso_manager.x ** 2 +
            self.ngso_manager.y ** 2 +
            (np.sqrt(x * x + y * y + z * z) + self.ngso_manager.z) ** 2,
        )

        npt.assert_allclose(off_axis_angle, 0.0, atol=1e-05)

        npt.assert_allclose(
            distance_to_center_of_earth.flatten(),
            distance_to_center_of_earth_should_eq,
            atol=1e-05,
        )

    def test_satellite_coordinate_reversing(self):
        """Test coordinate conversion and azimuth direction for NGSO satellites."""
        # by default, satellites should always point to nadir (earth center)
        rng = np.random.RandomState(seed=self.seed)

        ngso_original_coord = StationFactory.generate_mss_d2d(
            self.param, rng, self.coord_sys)
        self.coord_sys.station_enu2ecef(ngso_original_coord)
        # Test: check if azimuth is pointing towards correct direction
        # y > 0 <=> azimuth < 0
        # y < 0 <=> azimuth > 0
        npt.assert_array_equal(
            np.sign(ngso_original_coord.azimuth), -np.sign(ngso_original_coord.y))

        # Test: check if center of earth is 0deg off axis
        earth_center = StationManager(1)
        earth_center.x = np.array([0.])
        earth_center.y = np.array([0.])
        earth_center.z = np.array([0.])

        off_axis_angle = ngso_original_coord.get_off_axis_angle(earth_center)

        npt.assert_allclose(off_axis_angle, 0.0, atol=1e-05)

        self.coord_sys.station_ecef2enu(ngso_original_coord)

        npt.assert_allclose(
            self.ngso_manager.x,
            ngso_original_coord.x,
            atol=1e-500)
        npt.assert_allclose(
            self.ngso_manager.y,
            ngso_original_coord.y,
            atol=1e-500)
        npt.assert_allclose(
            self.ngso_manager.z,
            ngso_original_coord.z,
            atol=1e-500)
        npt.assert_allclose(
            self.ngso_manager.height,
            ngso_original_coord.height,
            atol=1e-500)
        npt.assert_allclose(
            self.ngso_manager.azimuth,
            ngso_original_coord.azimuth,
            atol=1e-500)
        npt.assert_allclose(
            self.ngso_manager.elevation,
            ngso_original_coord.elevation,
            atol=1e-500)

    def test_ngso_oob_antenna(self):
        """Test that out-of-band antenna patterns are created correctly for NGSO stations."""
        rng = np.random.RandomState(seed=self.seed)

        self.param.use_oob_antenna = False
        self.param.validate("oob_antenna_test")

        ngso_manager = StationFactory.generate_mss_d2d(self.param, rng, self.coord_sys)

        # If oob_antenna is disabled, both antennas should point to the same object
        self.assertIs(ngso_manager.oob_antenna, ngso_manager.antenna)

        self.param.use_oob_antenna = True
        self.param.oob_antenna.pattern = "Cosine Antenna"
        self.param.oob_antenna.gain = 0.0
        self.param.propagate_parameters()
        self.param.validate("oob_antenna_test")

        ngso_manager = StationFactory.generate_mss_d2d(self.param, rng, self.coord_sys)

        # the oob_antenna should be a different object now
        self.assertIsNot(ngso_manager.oob_antenna, ngso_manager.antenna)
        for a in ngso_manager.oob_antenna:
            self.assertIsInstance(a, AntennaElementCosine)

    def test_ngso_spectral_mask_stepped(self):
        """Test that NGSO stations use the STEPPED spectral mask when specified."""
        rng = np.random.RandomState(seed=self.seed)

        self.param.spectral_mask = "STEPPED"
        self.param.spectral_mask_steps = (-10., -15., -20.)
        self.param.propagate_parameters()
        self.param.validate("spectral_mask_stepped_test")

        ngso_manager = StationFactory.generate_mss_d2d(self.param, rng, self.coord_sys)

        # Check that all stations have the correct spectral mask type
        self.assertEqual(ngso_manager.spectral_mask.__class__.__name__, "SpectralMaskStepped")
        self.assertEqual(
            ngso_manager.spectral_mask.mask_steps_dBm_mhz,
            list(self.param.spectral_mask_steps)
        )


if __name__ == '__main__':
    unittest.main()
