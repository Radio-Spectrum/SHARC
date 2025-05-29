import unittest
import numpy as np
import numpy.testing as npt
import sharc.satellite.utils.sat_utils as sat_utils
from sharc.satellite.ngso.constants import EARTH_RADIUS_M


class TestSatUtils(unittest.TestCase):

    def setUp(self):
        pass

    def test_ecef2lla(self):
        # Object is over the meridional plane at 1414km of altitude
        sx1 = EARTH_RADIUS_M + 1414e3
        sy1 = 0.0
        sz1 = 0.0
        lat, lng, alt = sat_utils.ecef2lla(sx1, sy1, sz1)
        npt.assert_almost_equal(lat, 0.0, 2)
        npt.assert_almost_equal(lng, 0.0, 2)
        npt.assert_almost_equal(alt, sx1 - EARTH_RADIUS_M, 1)

        # Object is over the meridional plane at sea level
        sx2 = EARTH_RADIUS_M
        sy2 = 0.0
        sz2 = 0.0
        lat, lng, alt = sat_utils.ecef2lla(sx2, sy2, sz2)
        npt.assert_almost_equal(lat, 0.0, 2)
        npt.assert_almost_equal(lng, 0.0, 2)
        npt.assert_almost_equal(alt, 0.0, 1)

        r = EARTH_RADIUS_M + 4209582
        expected_lat = 18.0316
        expected_lon = 39.30153
        sx3 = r * np.cos(np.deg2rad(expected_lat)) * np.cos(np.deg2rad(expected_lon))
        sy3 = r * np.cos(np.deg2rad(expected_lat)) * np.sin(np.deg2rad(expected_lon))
        sz3 = r * np.sin(np.deg2rad(expected_lat))

        lat, lng, alt = sat_utils.ecef2lla(sx3, sy3, sz3)
        npt.assert_almost_equal(lat, expected_lat, 3)
        npt.assert_almost_equal(lng, expected_lon, 3)
        npt.assert_almost_equal(alt, r - EARTH_RADIUS_M, 1)

        # test the array form
        sx = [sx1, sx2, sx3]
        sy = [sy1, sy2, sy3]
        sz = [sz1, sz2, sz3]
        lat, lng, alt = sat_utils.ecef2lla(sx, sy, sz)
        npt.assert_almost_equal(lat, [0.0, 0.0, 18.0316], 3)
        npt.assert_almost_equal(lng, [0.0, 0.0, 39.30153], 3)
        npt.assert_almost_equal(alt, [1414000.0, 0.0, 4209582], 1)

    def test_lla2ecef(self):
        # Object is over the meridional plane at 1414km of altitude
        lat = 0.0
        lng = 0.0
        alt = 1414000.0
        sx, sy, sz = sat_utils.lla2ecef(lat, lng, alt)

        npt.assert_almost_equal(sx, alt + EARTH_RADIUS_M, 1)
        npt.assert_almost_equal(sy, 0.0, 1)
        npt.assert_almost_equal(sz, 0.0, 1)

        # Object is over the meridional plane at sea level
        lat = 0.0
        lng = 0.0
        alt = 0.0
        sx, sy, sz = sat_utils.lla2ecef(lat, lng, alt)
        npt.assert_almost_equal(sx, EARTH_RADIUS_M, 1)
        npt.assert_almost_equal(sy, 0.0, 1)
        npt.assert_almost_equal(sz, 0.0, 1)

        lat = 43.0344
        lng = 46.839308
        alt = 141400.0
        sx, sy, sz = sat_utils.lla2ecef(lat, lng, alt)
        npt.assert_almost_equal(sx, 3259772.4, 1)
        npt.assert_almost_equal(sy, 3476081.0, 1)
        npt.assert_almost_equal(sz, 4449180.9, 1)

        # test the array form
        lat = [0.0, 0.0, 43.0344]
        lng = [0.0, 0.0, 46.839308]
        alt = [1414000.0, 0.0, 141400.0]
        sx, sy, sz = sat_utils.lla2ecef(lat, lng, alt)
        npt.assert_almost_equal(sx, [1414000.0 + EARTH_RADIUS_M, EARTH_RADIUS_M, 3259772.4], 1)
        npt.assert_almost_equal(sy, [0.0, 0.0, 3476081.0], 1)
        npt.assert_almost_equal(sz, [0.0, 0.0, 4449180.9], 1)

    def test_calculate_elev_angle(self):
        earth_station_coords = [
            (0.0, 0.0),
            (-15.0, -42.0),
            (10.0, 20.0),
            (-15.0, -25.0),
        ]

        space_station_coords = [
            (0.0, 0.0),
            (-10.0, -40.0),
            (12.0, 25.0),
            (0.0, -30.0),
        ]

        space_station_alts = [
            1414 * 1e3,
            525 * 1e3,
            340 * 1e3,
            35786 * 1e3,
        ]

        expected_elevations = [
            90.0,
            37.48,
            26.67,
            71.45,
        ]

        for i in range(len(expected_elevations)):
            e = sat_utils.calc_elevation(
                earth_station_coords[i][0],
                space_station_coords[i][0],
                earth_station_coords[i][1],
                space_station_coords[i][1],
                sat_height=space_station_alts[i],
                es_height=0
            )
            npt.assert_almost_equal(e, expected_elevations[i], 1)


if __name__ == '__main__':
    unittest.main()
