import unittest
import numpy as np
import numpy.testing as npt
from sharc.support.sharc_geom import GeometryConverter
from sharc.satellite.utils.sat_utils import ecef2lla, lla2ecef
from sharc.station_manager import StationManager


class TestGeometryConverter(unittest.TestCase):
    """Unit tests for the GeometryConverter class and related coordinate transformations."""

    def setUp(self):
        """Set up test fixtures for GeometryConverter tests."""
        self.conv0_0km = GeometryConverter()
        self.conv0_0km.set_reference(
            0, 0, 0
        )
        self.conv0_52km = GeometryConverter()
        self.conv0_52km.set_reference(
            0, 0, 52e3
        )

        self.conv1_0km = GeometryConverter()
        self.conv1_0km.set_reference(
            -15, -47, 0
        )
        self.conv1_10km = GeometryConverter()
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
        """Check if set_reference sets both LLA and ECEF coordinates correctly."""
        # negative x in xaxis
        self.conv0_0km.set_reference(0, 180, 1200)
        self.assertEqual(self.conv0_0km.ref_alt, 1200)
        self.assertEqual(self.conv0_0km.ref_long, 180)
        self.assertEqual(self.conv0_0km.ref_lat, 0)

        # almost radius of earth
        self.assertAlmostEqual(self.conv0_0km.ref_x, -
                               6378145, delta=self.conv0_0km.ref_alt)
        self.assertAlmostEqual(self.conv0_0km.ref_y, 0)
        self.assertAlmostEqual(self.conv0_0km.ref_z, 0)

        # positive x in xaxis
        self.conv0_0km.set_reference(0, 0, 200)
        self.assertEqual(self.conv0_0km.ref_alt, 200)
        self.assertEqual(self.conv0_0km.ref_long, 0)
        self.assertEqual(self.conv0_0km.ref_lat, 0)

        # almost radius of earth
        self.assertAlmostEqual(
            self.conv0_0km.ref_x,
            6378145,
            delta=self.conv0_0km.ref_alt)
        self.assertAlmostEqual(self.conv0_0km.ref_y, 0)
        self.assertAlmostEqual(self.conv0_0km.ref_z, 0)

    def test_reference_ecef(self):
        """Test ECEF to LLA conversion for reference points."""
        for conv in self.all_converters:
            lat, lon, alt = ecef2lla(conv.ref_x, conv.ref_y, conv.ref_z)
            # ecef2lla approximation requires "almost equal" directive
            print("conv.ref_lat", conv.ref_lat)
            self.assertAlmostEqual(lat[0], conv.ref_lat, places=8)
            self.assertAlmostEqual(lon[0], conv.ref_long, places=8)
            self.assertAlmostEqual(alt[0], conv.ref_alt, places=8)

    def test_ecef_to_enu(self):
        """Test ECEF to ENU coordinate transformation."""
        # for each converter defined at the setup
        for conv in self.all_converters:
            # check if reference point always goes to (0,0,0)
            x, y, z = conv.convert_cartesian_to_transformed_cartesian(
                conv.ref_x, conv.ref_y, conv.ref_z)
            self.assertEqual(x, 0)
            self.assertEqual(y, 0)
            self.assertEqual(z, 0)

    def test_lla_to_enu(self):
        """Test LLA to ENU coordinate transformation."""
        # for each converter defined at the setup
        for conv in self.all_converters:
            x, y, z = conv.convert_lla_to_transformed_cartesian(
                conv.ref_lat, conv.ref_long, conv.ref_alt)
            self.assertEqual(x, 0)
            self.assertEqual(y, 0)
            self.assertEqual(z, 0)

    def test_enu_to_ecef(self):
        """Test ENU to ECEF coordinate transformation."""
        # for each converter defined at the setup
        for conv in self.all_converters:
            # check if the reverse is true
            x, y, z = conv.revert_transformed_cartesian_to_cartesian(0, 0, 0)
            self.assertEqual(x, conv.ref_x)
            self.assertEqual(y, conv.ref_y)
            self.assertEqual(z, conv.ref_z)

    def test_station_converter(self):
        """Test station coordinate and orientation conversions between ECEF and ENU."""
        # for each converter defined at the setup
        for conv in self.all_converters:
            rng = np.random.default_rng(0)
            n_samples = 100
            stations = StationManager(n_samples)
            # place stations randomly with ecef
            xyz_bef = lla2ecef(
                rng.uniform(-90, 90, n_samples),
                rng.uniform(-180, 180, n_samples),
                rng.uniform(0, 35e3, n_samples),
            )
            # set first station to be the reference
            xyz_bef[0][0] = conv.ref_x
            xyz_bef[1][0] = conv.ref_y
            xyz_bef[2][0] = conv.ref_z
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
            conv.convert_station_3d_to_2d(stations)

            # check if reference origin
            self.assertEqual(stations.x[0], 0)
            self.assertEqual(stations.y[0], 0)
            self.assertEqual(stations.z[0], 0)

            # get relative distances and off axis while in enu
            dists_aft = stations.get_3d_distance_to(stations)
            off_axis_aft = stations.get_off_axis_angle(stations)

            # all stations should maintain same relative distances and off axis
            # since their relative positioning and pointing should eq in ECEF
            # and ENU
            npt.assert_allclose(dists_aft, dists_bef)
            npt.assert_allclose(off_axis_aft, off_axis_bef)

            # NOTE: the next set of tests may not pass and the code still be
            # correct...

            # we can try to check if there are differences between stations before
            # and after transformation.
            # TODO: It would be more correct to not force equality for all cases,
            # but only for most of them

            # sometimes some values can be really similar before and after the
            # transformation

            # for example, reference may be on the same axis after and before transformation
            # so we ignore the first station (used as reference) on these
            # checks
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
            conv.revert_station_2d_to_3d(stations)

            # check if their position is the same as at the start
            # some precision error occurs, so "almost equal" is needed
            npt.assert_almost_equal(stations.x, xyz_bef[0])
            npt.assert_almost_equal(stations.y, xyz_bef[1])
            npt.assert_almost_equal(stations.z, xyz_bef[2])
            npt.assert_almost_equal(stations.azimuth, azim_bef)
            npt.assert_almost_equal(stations.elevation, elev_bef)


if __name__ == '__main__':
    unittest.main()
