# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 08:53:15 2017

@author: Calil
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.support.footprint import Footprint


class FootprintAreaTest(unittest.TestCase):

    def setUp(self):
        self.fa1 = Footprint(0.1, bore_lat_deg=0, bore_subsat_long_deg=0.0)
        self.fa2 = Footprint(0.325, bore_lat_deg=0)
        self.fa3 = Footprint(0.325, elevation_deg=20)
        self.fa4 = Footprint(0.325, elevation_deg=20, sat_height=600000)
        self.fa5 = Footprint(0.325, elevation_deg=20, sat_height=1200000)
        self.fa6 = Footprint(
            0.325,
            sat_height=1200000,
            bore_lat_deg=0,
            bore_subsat_long_deg=17.744178387,
        )

    def test_construction(self):
        self.assertEqual(self.fa1.sat_height, 35786000)
        self.assertEqual(self.fa1.bore_lat_deg, 0)
        self.assertEqual(self.fa1.bore_subsat_long_deg, 0)
        self.assertEqual(self.fa1.beam_width_deg, 0.1)
        self.assertEqual(self.fa1.bore_lat_rad, 0)
        self.assertEqual(self.fa1.bore_subsat_long_rad, 0)
        self.assertEqual(self.fa1.beam_width_rad, np.pi / 1800)
        self.assertEqual(self.fa1.beta, 0)
        self.assertEqual(self.fa1.bore_tilt, 0)

        self.assertEqual(self.fa2.sat_height, 35786000)
        self.assertEqual(self.fa2.bore_lat_deg, 0)
        self.assertEqual(self.fa2.bore_subsat_long_deg, 0)
        self.assertEqual(self.fa2.bore_lat_rad, 0)
        self.assertEqual(self.fa2.bore_subsat_long_rad, 0)

        self.assertEqual(self.fa3.sat_height, 35786000)
        self.assertEqual(self.fa3.bore_lat_deg, 0)
        self.assertAlmostEqual(
            self.fa3.bore_subsat_long_deg, 61.84, delta=0.01
        )

        # 90 - elevation_deg - arcsin(
        #   cos(elevation_rad) * EARTH_RADIUS / (EARTH_RADIUS + sat_height)
        # )
        self.assertEqual(self.fa4.sat_height, 600000)
        self.assertAlmostEqual(
            self.fa4.bore_subsat_long_deg, 10.816493232, delta=0.01
        )

        self.assertEqual(self.fa5.sat_height, 1200000)
        self.assertAlmostEqual(
            self.fa5.bore_subsat_long_deg, 17.744178387, delta=0.01
        )

        self.assertEqual(self.fa6.sat_height, 1200000)
        self.assertAlmostEqual(self.fa6.elevation_deg, 20, delta=0.01)

    def test_sigma_precision(self):
        # test added after sat_heigth became "settable"
        # asserting delta from previously used `sigma`` for height=35786000
        # so that the results may be compared
        self.assertAlmostEqual(self.fa3.sigma, 0.151, delta=0.151 * 0.001)
        self.assertAlmostEqual(
            1 / self.fa3.sigma, 6.6235, delta=6.6235 * 0.001
        )

    def test_set_elevation(self):
        self.fa2.set_elevation(20)
        self.assertEqual(self.fa2.bore_lat_deg, 0)
        self.assertAlmostEqual(
            self.fa2.bore_subsat_long_deg, 61.84, delta=0.01
        )

    def test_calc_footprint(self):
        fp_long, fp_lat = self.fa1.calc_footprint(4)
        npt.assert_allclose(
            fp_long, np.array([0.0, 0.487, -0.487, 0.0]), atol=1e-2
        )
        npt.assert_allclose(
            fp_lat, np.array([-0.562, 0.281, 0.281, -0.562]), atol=1e-2
        )

    def test_calc_area(self):
        a1 = self.fa2.calc_area(1000)
        self.assertAlmostEqual(a1, 130000, delta=130000 * 0.002)
        a2 = self.fa3.calc_area(1000)
        self.assertAlmostEqual(a2, 486300, delta=486300 * 0.003)
        # [TODO]: find reference to also make fa4 and fa5 golden tests
        # if cannot, tilt elevation_deg while footprint is ellipsis to
        # at least test some elevation_deg != 90
        # with the heights 12000 and 6000 km

    def test_calc_area_with_changing_height_and_beam_deg(self):
        for i in range(1, 10):
            height = 3578600 * i
            beam_deg = 0.0325 * i
            footprint = Footprint(
                beam_deg, elevation_deg=90, sat_height=height
            )
            # cone base area works as golden test standard when
            # elevation_deg=90
            cone_radius_in_km = height * np.tan(np.deg2rad(beam_deg)) / 1000
            cone_base_area_in_km2 = np.pi * (cone_radius_in_km**2)
            footprint_area_in_km2 = footprint.calc_area(1000)
            self.assertAlmostEqual(
                footprint_area_in_km2,
                cone_base_area_in_km2,
                delta=cone_base_area_in_km2 * 0.01,
            )


if __name__ == "__main__":
    unittest.main()
