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
    """
    Performing Unit Test on the Footprint class in various scenarios with angles
    of latitude of the ground station antennas and the space station, various
    elevation angles, and different heights using the unittest library.
    Constructor:
        unittest.TestCase - Object from the unittest library that assists in testing.
    """

    def setUp(self):
        """
        Defining a method that creates test objects for each scenario, respecting
        the expected inputs by the class.
        """
        # half of beam width in degrees equal to 0.1, and the rest of the parameters are null
        self.fa1 = Footprint(0.1, bore_lat_deg=0, bore_subsat_long_deg=0.0)
        # half of beam width in degrees equal to 0.325, and the rest of the parameters are null
        self.fa2 = Footprint(0.325, bore_lat_deg=0)
        # Changing the elevation to 20º
        self.fa3 = Footprint(0.325, elevation_deg=20)
        # Now with elevation of 30º and changing the height of the satellites relative to the receiver
        self.fa4 = Footprint(0.325, elevation_deg=30, sat_height=1200000)
        self.fa5 = Footprint(0.325, elevation_deg=30, sat_height=600000)

    def test_construction(self):
        """
        Defining a method that tests if the Footprint class is correctly constructed for
        the objects defined above, comparing with expected values calculated externally.
        """
        # Testing if the constructor works correctly for the first object
        # that is, testing if the calibration of angles both in radians and degrees corresponds to the expected
        self.assertEqual(self.fa1.bore_lat_deg, 0)
        self.assertEqual(self.fa1.bore_subsat_long_deg, 0)
        self.assertEqual(self.fa1.beam_width_deg, 0.1)
        self.assertEqual(self.fa1.bore_lat_rad, 0)
        self.assertEqual(self.fa1.bore_subsat_long_rad, 0)
        self.assertEqual(self.fa1.beam_width_rad, np.pi / 1800)
        self.assertEqual(self.fa1.beta, 0)
        self.assertEqual(self.fa1.bore_tilt, 0)

        # Testing the second object to check if the unset parameters remain null
        self.assertEqual(self.fa2.bore_lat_deg, 0)
        self.assertEqual(self.fa2.bore_subsat_long_deg, 0)
        self.assertEqual(self.fa2.bore_lat_rad, 0)
        self.assertEqual(self.fa2.bore_subsat_long_rad, 0)

        # With non-null elevation angle and geostationary satellite height (35786000 m)
        self.assertEqual(self.fa3.bore_lat_deg, 0)  # If an elevation angle value has been passed, it is expected that this parameter will be null
        self.assertAlmostEqual(self.fa3.bore_subsat_long_deg, 61.84, delta=0.01)  # Testing if the longitude of boresight with respect to sub-satellite point is close to the expected

        # With non-null elevation angle and height of 1200000 m
        self.assertEqual(self.fa4.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa4.bore_subsat_long_deg, 13.22, delta=0.01)

        # With non-null elevation angle and height of 600000 m
        self.assertEqual(self.fa5.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa5.bore_subsat_long_deg, 7.68, delta=0.01)

    def test_set_elevation(self):
        """
        Creating a method that tests if the set_elevation method is capable of modifying
        the initial elevation.
        """
        # Modifying the initial elevation of object 2 to the same as object 3, so the objects will be the same
        self.fa2.set_elevation(20)
        self.assertEqual(self.fa2.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa2.bore_subsat_long_deg, 61.84, delta=0.01)  # Same test performed on object 3

    def test_calc_footprint(self):
        """
        Creating a method that tests if the coordinates generated for the n polygons for the footprint are correct.
        """
        fp_long, fp_lat = self.fa1.calc_footprint(4)
        npt.assert_allclose(fp_long, np.array([0.0, 0.487, -0.487, 0.0]), atol=1e-2)
        npt.assert_allclose(fp_lat, np.array([-0.562, 0.281, 0.281, -0.562]), atol=1e-2)

    def test_calc_area(self):
        """
        Creating a method that tests if the final footprint area calculation is correct (calculated externally).
        """
        a1 = self.fa2.calc_area(1000)  # Performing the area calculation with 1000 approximation polygons
        # Testing the footprint area with the expected value, with a tolerance of 0.25% or deviation of 0.0025
        self.assertAlmostEqual(a1, 130000, delta=130000 * 0.0025)
        a2 = self.fa3.calc_area(1000)
        self.assertAlmostEqual(a2, 486300, delta=486300 * 0.0025)
        a3 = self.fa4.calc_area(1000)
        self.assertAlmostEqual(a3, 810, delta=810 * 0.0025)
        a4 = self.fa5.calc_area(1000)
        self.assertAlmostEqual(a4, 234, delta=234 * 0.0025)

if __name__ == '__main__':
    unittest.main()
