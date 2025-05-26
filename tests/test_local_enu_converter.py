import unittest
import numpy as np
import numpy.testing as npt
from sharc.support.sharc_geom import LocalENUConverter
from sharc.satellite.utils.sat_utils import ecef2lla, lla2ecef
from sharc.station_manager import StationManager


class TestLocalEnuConverter(unittest.TestCase):
    def setUp(self):
        self.conv0_0km = LocalENUConverter()
        self.conv0_0km.set_reference(
            0, 0, 0
        )
        self.conv0_52km = LocalENUConverter()
        self.conv0_52km.set_reference(
            0, 0, 52e3
        )

        self.conv1_0km = LocalENUConverter()
        self.conv1_0km.set_reference(
            -15, -47, 0
        )
        self.conv1_10km = LocalENUConverter()
        self.conv1_10km.set_reference(
            -15, -47, 10e3
        )

        self.all_converters = [
            self.conv0_0km,
            self.conv0_52km,
            self.conv1_0km,
            self.conv1_10km,
        ]

    def test_set_reference(self):
        """
        Checking if set reference sets both lla and ecef coordinates
        """
        # negative x in xaxis
        self.conv0_0km.set_reference(0, 180, 1200)
        self.assertEqual(self.conv0_0km.ref_alt, 1200)
        self.assertEqual(self.conv0_0km.ref_long, 180)
        self.assertEqual(self.conv0_0km.ref_lat, 0)

        # almost radius of earth
        self.assertAlmostEqual(self.conv0_0km.ref_x, -6378145, delta=self.conv0_0km.ref_alt)
        self.assertAlmostEqual(self.conv0_0km.ref_y, 0)
        self.assertAlmostEqual(self.conv0_0km.ref_z, 0)

        # positive x in xaxis
        self.conv0_0km.set_reference(0, 0, 200)
        self.assertEqual(self.conv0_0km.ref_alt, 200)
        self.assertEqual(self.conv0_0km.ref_long, 0)
        self.assertEqual(self.conv0_0km.ref_lat, 0)

        # almost radius of earth
        self.assertAlmostEqual(self.conv0_0km.ref_x, 6378145, delta=self.conv0_0km.ref_alt)
        self.assertAlmostEqual(self.conv0_0km.ref_y, 0)
        self.assertAlmostEqual(self.conv0_0km.ref_z, 0)

    def test_reference_ecef(self):
        for conv in self.all_converters:
            lat, lon, alt = ecef2lla(conv.ref_x, conv.ref_y, conv.ref_z)
            # ecef2lla approximation requires "almost equal" directive
            self.assertAlmostEqual(lat, conv.ref_lat, places=8)
            self.assertAlmostEqual(lon, conv.ref_long, places=8)
            self.assertAlmostEqual(alt, conv.ref_alt, places=8)

    def test_ecef_to_enu(self):
        """
        Testing if ecef to enu works correctly
        """
        # for each converter defined at the setup
        for conv in self.all_converters:
            # check if reference point always goes to (0,0,0)
            x, y, z = conv.ecef2enu(conv.ref_x, conv.ref_y, conv.ref_z)
            self.assertEqual(x, 0)
            self.assertEqual(y, 0)
            self.assertEqual(z, 0)

    def test_lla_to_enu(self):
        """
        Testing if lla to enu works correctly
        """
        # for each converter defined at the setup
        for conv in self.all_converters:
            x, y, z = conv.lla2enu(conv.ref_lat, conv.ref_long, conv.ref_alt)
            self.assertEqual(x, 0)
            self.assertEqual(y, 0)
            self.assertEqual(z, 0)

    def test_enu_to_ecef(self):
        """
        Testing if enu to ecef works correctly
        """
        # for each converter defined at the setup
        for conv in self.all_converters:
            # check if the reverse is true
            x, y, z = conv.enu2ecef(0, 0, 0)
            self.assertEqual(x, conv.ref_x)
            self.assertEqual(y, conv.ref_y)
            self.assertEqual(z, conv.ref_z)

    def test_station_converter(self):
        """
        Testing if station conversion works correctly
        """
        # for each converter defined at the setup
        for conv in self.all_converters:
            rng = np.random.default_rng(0)
            n_samples = 100
            stations = StationManager(n_samples)
            # place stations randomly with ecef
            lla_bef = (
                rng.uniform(-90, 90, n_samples),
                rng.uniform(-180, 180, n_samples),
                rng.uniform(0, 35e3, n_samples),
            )
            lla_bef[0][0] = conv.ref_lat
            lla_bef[1][0] = conv.ref_long
            lla_bef[2][0] = conv.ref_alt
            xyz_bef = lla2ecef(
                lla_bef[0],
                lla_bef[1],
                lla_bef[2],
            )
            # set first station to be the reference
            # point them randomly
            azim_bef = rng.uniform(-180, 180, n_samples)
            elev_bef = rng.uniform(-90, 90, n_samples)

            stations.x, stations.y, stations.z = xyz_bef
            stations.azimuth = azim_bef
            stations.elevation = elev_bef

            # get relative distances and off axis while in ecef
            dists_bef = stations.get_3d_distance_to(stations)
            off_axis_bef = stations.get_off_axis_angle(stations)

            # convert stations to enu
            conv.station_ecef2enu(stations)

            # check if reference origin
            self.assertEqual(stations.x[0], 0)
            self.assertEqual(stations.y[0], 0)
            self.assertEqual(stations.z[0], 0)

            # get relative distances and off axis while in enu
            dists_aft = stations.get_3d_distance_to(stations)
            off_axis_aft = stations.get_off_axis_angle(stations)

            # all stations should maintain same relative distances and off axis
            # since their relative positioning and pointing should eq in ECEF and ENU
            npt.assert_allclose(dists_aft, dists_bef)
            npt.assert_allclose(off_axis_aft, off_axis_bef)

            # NOTE: the next set of tests may not pass and the code still be correct...

            # we can try to check if there are differences between stations before
            # and after transformation.
            # TODO: It would be more correct to not force equality for all cases,
            # but only for most of them

            # sometimes some values can be really similar before and after the transformation

            # for example, reference may be on the same axis after and before transformation
            # so we ignore the first station (used as reference) on these checks
            npt.assert_equal(
                np.abs(stations.x[1:] - xyz_bef[0][1:]) > 1e3,
                True
            )
            npt.assert_equal(
                np.abs(stations.y[1:] - xyz_bef[1][1:]) > 1e3,
                True
            )
            npt.assert_equal(
                np.abs(stations.z[1:] - xyz_bef[2][1:]) > 1e3,
                True
            )
            # and the elevation angle may not change much if pointing vector is to the east/west
            # since the pointing vector is aligned with the x axis, the rotation along it
            # won't change the value much
            npt.assert_equal(
                np.abs(stations.azimuth - azim_bef) > 0.4,
                True
            )
            npt.assert_equal(
                np.abs(stations.elevation - elev_bef) > 0.4,
                True
            )

            # return stations to starting case:
            conv.station_enu2ecef(stations)

            # check if their position is the same as at the start
            # some precision error occurs, so "almost equal" is needed
            npt.assert_allclose(stations.x, xyz_bef[0], atol=1e-500)
            npt.assert_allclose(stations.y, xyz_bef[1], atol=1e-500)
            npt.assert_allclose(stations.z, xyz_bef[2], atol=1e-500)
            npt.assert_allclose(stations.azimuth, azim_bef, atol=1e-500)
            npt.assert_allclose(stations.elevation, elev_bef, atol=1e-500)

            earth_center = StationManager(1)

            earth_center.x = np.array([0.])
            earth_center.y = np.array([0.])
            earth_center.z = np.array([0.])

            # point stations downwards
            stations.azimuth = (lla_bef[1] + 360.) % 360 - 180
            stations.elevation = -1 * lla_bef[0]
            off_axis_angle = stations.get_off_axis_angle(earth_center)

            # when station is pointing at nadir, it should have a maximum off axis
            # of 0.2deg from earth center
            npt.assert_allclose(off_axis_angle, 0.0, atol=0.2)


if __name__ == '__main__':
    unittest.main()

