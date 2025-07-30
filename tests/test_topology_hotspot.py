# -*- coding: utf-8 -*-
"""
Created on Tue May 23 16:43:09 2017

@author: edgar
"""

import unittest
import numpy as np
import numpy.testing as npt
from collections import Counter

from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
from sharc.topology.topology_hotspot import TopologyHotspot


class TopologyHotspotTest(unittest.TestCase):
    """Unit tests for the TopologyHotspot class, including coordinate and overlap logic."""

    def setUp(self):
        """Set up a TopologyHotspot instance for testing coordinate calculations."""
        # For this test case, hotspot parameters are useless because we are
        # testing only the validation methods
        param = ParametersHotspot()
        param.num_hotspots_per_cell = 1
        param.max_dist_hotspot_ue = 100
        param.min_dist_hotspot_ue = 5
        param.min_dist_bs_hotspot = 105

        intersite_distance = 1000
        num_clusters = 1
        self.topology = TopologyHotspot(
            param, intersite_distance, num_clusters,
        )

    def test_calculate_coordinates(self):
        """Test calculation of hotspot coordinates and hexagonal grid logic."""
        # algorithms for hexagonal coordinate systems (axial and cube)
        # based on https://www.redblobgames.com/grids/hexagons/
        def cube_round(q, r, s):
            qr, rr, sr = np.round(q), np.round(r), np.round(s)
            q_diff = np.abs(qr - q)
            r_diff = np.abs(rr - r)
            s_diff = np.abs(sr - s)

            c1 = (q_diff > r_diff) & (q_diff > s_diff)
            qr[c1] = -rr[c1] - sr[c1]

            c2 = (r_diff > s_diff) & (~c1)
            rr[c2] = -qr[c2] - sr[c2]

            c3 = (~c1) & (~c2)
            sr[c3] = -qr[c3] - rr[c3]

            return qr, rr, sr

        def cube_to_axial(q, r, s):
            return q, r

        def axial_to_cube(q, r):
            return q, r, -q - r

        def axial_round(q, r):
            return cube_to_axial(*cube_round(*axial_to_cube(q, r)))

        def xy_to_axial(x, y, hex_radius):
            """
            Gets hexagon axial indice (q,r)
                that contains (x,y) position
            """
            x += hex_radius

            x, y = x / hex_radius, y / hex_radius
            q = 2 * x / 3
            r = -1 * x / 3 + np.sqrt(3) * y / 3

            return axial_round(q, r)

        # Test for 1 hotspot in 1 cluster grid
        n_hexagons = 19 * 3

        rng = np.random.RandomState(11111)
        param = ParametersHotspot()
        param.num_hotspots_per_cell = 1
        param.max_dist_hotspot_ue = 100
        param.min_dist_hotspot_ue = 5
        param.min_dist_bs_hotspot = 105

        intersite_distance = 1000
        num_clusters = 1
        topology = TopologyHotspot(
            param, intersite_distance, num_clusters,
        )
        topology.calculate_coordinates(rng)

        expected_shp = (n_hexagons,)

        self.assertEqual(topology.num_base_stations, expected_shp[0])
        self.assertEqual(topology.x.shape, expected_shp)
        self.assertEqual(topology.y.shape, expected_shp)
        self.assertEqual(topology.z.shape, expected_shp)
        self.assertEqual(topology.azimuth.shape, expected_shp)

        hex_qr = xy_to_axial(
            topology.x, topology.y, topology.intersite_distance / 3
        )
        count = Counter(zip(*hex_qr))
        self.assertEqual(len(count), n_hexagons)
        npt.assert_array_equal(list(count.values()), 1)

        # Test for 3 hotspots in 1 cluster grid
        param.num_hotspots_per_cell = 3
        topology = TopologyHotspot(
            param, intersite_distance, num_clusters,
        )
        topology.calculate_coordinates(rng)

        expected_shp = (n_hexagons * 3,)

        self.assertEqual(topology.num_base_stations, expected_shp[0])
        self.assertEqual(topology.x.shape, expected_shp)
        self.assertEqual(topology.y.shape, expected_shp)
        self.assertEqual(topology.z.shape, expected_shp)
        self.assertEqual(topology.azimuth.shape, expected_shp)

        hex_qr = xy_to_axial(
            topology.x, topology.y, topology.intersite_distance / 3
        )
        count = Counter(zip(*hex_qr))

        self.assertEqual(len(count), n_hexagons)
        npt.assert_array_equal(list(count.values()), 3)

        # Test for 3 hotspots in 7 cluster grid
        n_hexagons = 19 * 3 * 7
        num_clusters = 7
        topology = TopologyHotspot(
            param, intersite_distance, num_clusters,
        )
        topology.calculate_coordinates(rng)

        expected_shp = (n_hexagons * 3,)

        self.assertEqual(topology.num_base_stations, expected_shp[0])
        self.assertEqual(topology.x.shape, expected_shp)
        self.assertEqual(topology.y.shape, expected_shp)
        self.assertEqual(topology.z.shape, expected_shp)
        self.assertEqual(topology.azimuth.shape, expected_shp)

        hex_qr = xy_to_axial(
            topology.x, topology.y, topology.intersite_distance / 3
        )
        count = Counter(zip(*hex_qr))
        self.assertEqual(len(count), n_hexagons)
        npt.assert_array_equal(list(count.values()), 3)

    def test_overlapping_hotspots(self):
        """Test detection of overlapping hotspots in the topology."""
        candidate_x = np.array([300])
        candidate_y = np.array([0])
        candidate_azimuth = np.array([-180])
        set_x = np.array([0, 200])
        set_y = np.array([0, 0])
        set_azimuth = np.array([0, -180])
        radius = 100
        self.assertFalse(
            self.topology.overlapping_hotspots(
                candidate_x,
                candidate_y,
                candidate_azimuth,
                set_x,
                set_y,
                set_azimuth,
                radius,
            ),
        )

        candidate_x = np.array([0])
        candidate_y = np.array([0])
        candidate_azimuth = np.array([0])
        set_x = np.array([0, 0])
        set_y = np.array([150, 400])
        set_azimuth = np.array([270, 270])
        radius = 100
        self.assertTrue(
            self.topology.overlapping_hotspots(
                candidate_x,
                candidate_y,
                candidate_azimuth,
                set_x,
                set_y,
                set_azimuth,
                radius,
            ),
        )

        candidate_x = np.array([0])
        candidate_y = np.array([0])
        candidate_azimuth = np.array([0])
        set_x = np.array([-1, 101])
        set_y = np.array([0, 0])
        set_azimuth = np.array([180, 0])
        radius = 100
        self.assertFalse(
            self.topology.overlapping_hotspots(
                candidate_x,
                candidate_y,
                candidate_azimuth,
                set_x,
                set_y,
                set_azimuth,
                radius,
            ),
        )

        candidate_x = np.array([1])
        candidate_y = np.array([0])
        candidate_azimuth = np.array([0])
        set_x = np.array([0])
        set_y = np.array([1])
        set_azimuth = np.array([90])
        radius = 100
        self.assertTrue(
            self.topology.overlapping_hotspots(
                candidate_x,
                candidate_y,
                candidate_azimuth,
                set_x,
                set_y,
                set_azimuth,
                radius,
            ),
        )


if __name__ == '__main__':
    unittest.main()
