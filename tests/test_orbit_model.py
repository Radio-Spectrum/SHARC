import unittest
import numpy as np
from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.support.sharc_utils import angular_dist


class TestOrbitModel(unittest.TestCase):
    """Unit tests for the OrbitModel class and its orbital calculations."""

    def setUp(self):
        """Set up test fixtures for OrbitModel tests."""
        self.orbit = OrbitModel(
            Nsp=6,
            Np=8,
            phasing=7.5,
            long_asc=0,
            omega=0,
            delta=52,
            hp=1414,
            ha=1414,
            Mo=0,
            model_time_as_random_variable=False,
            t_min=0.0,
            t_max=None
        )

    def test_initialization(self):
        """Test initialization and parameter assignment of OrbitModel."""
        self.assertEqual(self.orbit.Nsp, 6)
        self.assertEqual(self.orbit.Np, 8)
        self.assertAlmostEqual(self.orbit.phasing, 7.5)
        self.assertAlmostEqual(self.orbit.long_asc, 0)
        self.assertAlmostEqual(self.orbit.omega, 0)
        self.assertAlmostEqual(self.orbit.delta, 52)
        self.assertAlmostEqual(self.orbit.perigee_alt_km, 1414)
        self.assertAlmostEqual(self.orbit.apogee_alt_km, 1414)
        self.assertAlmostEqual(self.orbit.Mo, 0)

    def test_orbit_parameters(self):
        """Test calculation of orbital parameters."""
        self.assertAlmostEqual(self.orbit.semi_major_axis, 7792.145)
        self.assertAlmostEqual(self.orbit.eccentricity, 0.0)
        self.assertAlmostEqual(
            self.orbit.orbital_period_sec,
            6845.3519,
            places=4)
        self.assertAlmostEqual(self.orbit.sat_sep_angle_deg, 60.0)
        self.assertAlmostEqual(self.orbit.orbital_plane_spacing, 45.0)

    def test_mean_anomalies(self):
        """Test mean anomaly calculations and satellite phasing logic."""
        self.orbit.get_orbit_positions_time_instant(time_instant_secs=0)
        ma_deg = np.degrees(
            self.orbit.mean_anomaly.reshape(
                (self.orbit.Np, self.orbit.Nsp)))

        # Check phasing between satellites in the same plane
        r = np.ones(
            (ma_deg.shape[0] - 1,
             ma_deg.shape[1])) * self.orbit.phasing
        np.testing.assert_array_almost_equal(
            np.diff(ma_deg, axis=0), r, decimal=4)

        # Check phase between planes
        r = np.ones((ma_deg.shape[0], ma_deg.shape[1] - 1)
                    ) * self.orbit.sat_sep_angle_deg
        np.testing.assert_array_almost_equal(
            np.diff(ma_deg, axis=1), r, decimal=4)

        # Check mean anomaly values with randon time
        self.orbit.get_orbit_positions_random(rng=np.random.RandomState())
        ma_deg = np.unwrap(
            np.degrees(
                self.orbit.mean_anomaly.reshape(
                    (self.orbit.Np, self.orbit.Nsp))), period=360)

        # Check phasing between satellites in the same plane
        r = np.ones(
            (ma_deg.shape[0] - 1,
             ma_deg.shape[1])) * self.orbit.phasing
        phasing_diff = np.diff(ma_deg, axis=0)
        phasing_diff[phasing_diff < 0] += 360
        np.testing.assert_array_almost_equal(phasing_diff, r, decimal=4)

        # Check phase between planes
        r = np.ones((ma_deg.shape[0], ma_deg.shape[1] - 1)
                    ) * self.orbit.sat_sep_angle_deg
        np.testing.assert_array_almost_equal(
            np.diff(ma_deg, axis=1), r, decimal=4)

    def test_limiting_time_range_for_random_drops(self):
        """
        Testing if using model_time_as_random_variable
        and t_min, t_max works correctly
        """
        # if we limit time max to period / frac
        # and considering a circular orbit
        # then only 2 * pi / frac is traveled at max per each satellit
        frac = 36
        self.orbit.t_max = self.orbit.orbital_period_sec / frac
        max_traveled_angular_dist = 2 * np.pi / frac

        self.orbit.model_time_as_random_variable = True
        # NOTE: choosing a larger frac lets you choose less samples
        n_samples = int(2e2)
        positions = self.orbit.get_orbit_positions_random(
            rng=np.random.RandomState(123),
            n_samples=n_samples,
        )
        all_lats = positions["lat"]
        all_lons = positions["lon"]
        all_alts = positions["alt"]
        all_xs = positions["sx"]
        all_ys = positions["sy"]
        all_zs = positions["sz"]

        self.assertEqual(all_lons.shape, all_lats.shape)
        self.assertEqual(all_lons.shape, all_xs.shape)
        self.assertEqual(all_lons.shape, all_ys.shape)
        self.assertEqual(all_lons.shape, all_zs.shape)
        self.assertEqual(all_lons.shape, all_alts.shape)
        self.assertEqual(all_lons.shape, (self.orbit.Np * self.orbit.Nsp, n_samples))

        for sat_lats, sat_lons in zip(all_lats, all_lons):
            d_lon = np.deg2rad(angular_dist(
                sat_lons[:, np.newaxis], sat_lons[np.newaxis, :]
            ))

            # exhaustively get angular distance between all samples
            a = np.pi / 2 - np.deg2rad(sat_lats[:, np.newaxis])
            b = np.pi / 2 - np.deg2rad(sat_lats[np.newaxis, :])
            cos_phi = np.cos(a) * np.cos(b) \
                + np.sin(a) * np.sin(b) * np.cos(d_lon)
            phi = np.max(np.arccos(
                # imprecision may accumulate enough for numbers to be slightly out
                # of arccos range
                np.clip(cos_phi, -1., 1.)
            ))

            self.assertLessEqual(phi, max_traveled_angular_dist)
            self.assertGreaterEqual(phi, max_traveled_angular_dist * 0.9)


if __name__ == '__main__':
    unittest.main()
