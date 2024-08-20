# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 08:53:15 2017

@author: Calil

Updated on Sun Jul 29 21:34:07 2024

Request for Issue 33 correction suggestion, adding the unitary tests for LEO type satellite in 600Km and 1200Km heights.

@author: Thiago Ferreira
"""

# Thiago Ferreira - 231025717

#from footprint import Footprint # Old importing for testing and debugging space
from sharc.support.footprint import Footprint  # Importing Footprint class from the given module in repository
import unittest
import numpy as np
import numpy.testing as npt

# Added the matplotlib for plotting the footprint generated in the test
import matplotlib.pyplot as plt

class FootprintTest(unittest.TestCase):
    """
    Unit testing class for Footprint calculations, focusing on different satellite configurations
    such as beam width, elevation angle, and satellite height.
    """

    def setUp(self):
        """
        Set up the test environment by initializing Footprint instances with different parameters.
        """
        # Geostationary (GEO type) satellite height (35786000 m) and different beam widths and elevations
        self.fa1 = Footprint(0.1, bore_lat_deg=0, bore_subsat_long_deg=0.0)
        self.fa2 = Footprint(0.325, bore_lat_deg=0)
        self.fa3 = Footprint(0.325, elevation_deg=20)
        self.fa4 = Footprint(0.325, elevation_deg=30, sat_height=1200000)
        self.fa5 = Footprint(0.325, elevation_deg=30, sat_height=600000)

        """
        Requested tests for Low Earth Orbit (LEO) Satellite at 1200Km and 600Km added bellow (Issue 33).
        """

        # New tests obtained for the LEO satellite type heights (1200km and 600km)
        self.elevations = np.linspace(5, 90, num=32)  # Expanded elevation angles from 5 to 90 degrees
        self.sat_heights = [1200000, 600000]  # Different satellite heights (1200 km and 600 km)

    def test_construction(self):
        """
        Test the correct construction of Footprint instances with expected values.
        """
        # Verify properties of fa1
        self.assertEqual(self.fa1.bore_lat_deg, 0)
        self.assertEqual(self.fa1.bore_subsat_long_deg, 0)
        self.assertEqual(self.fa1.beam_width_deg, 0.1)
        self.assertEqual(self.fa1.bore_lat_rad, 0)
        self.assertEqual(self.fa1.bore_subsat_long_rad, 0)
        self.assertEqual(self.fa1.beam_width_rad, np.pi / 1800)
        self.assertEqual(self.fa1.beta, 0)
        self.assertEqual(self.fa1.bore_tilt, 0)

        # Verify properties of fa2
        self.assertEqual(self.fa2.bore_lat_deg, 0)
        self.assertEqual(self.fa2.bore_subsat_long_deg, 0)
        self.assertEqual(self.fa2.bore_lat_rad, 0)
        self.assertEqual(self.fa2.bore_subsat_long_rad, 0)

        # Verify properties of fa3
        self.assertEqual(self.fa3.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa3.bore_subsat_long_deg, 61.84, delta=0.01)

        # Verify properties of fa4
        self.assertEqual(self.fa4.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa4.bore_subsat_long_deg, 13.22, delta=0.01)

        # Verify properties of fa5
        self.assertEqual(self.fa5.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa5.bore_subsat_long_deg, 7.68, delta=0.01)

    def test_set_elevation(self):
        """
        Test the set_elevation method to ensure it correctly updates the elevation angle.
        """
        self.fa2.set_elevation(20)
        self.assertEqual(self.fa2.bore_lat_deg, 0)
        self.assertAlmostEqual(self.fa2.bore_subsat_long_deg, 61.84, delta=0.01)

    def test_calc_footprint(self):
        """
        Test the calc_footprint method to verify the coordinates of the generated footprint polygon.
        """
        fp_long, fp_lat = self.fa1.calc_footprint(4)
        npt.assert_allclose(fp_long, np.array([0.0, 0.487, -0.487, 0.0]), atol=1e-2)
        npt.assert_allclose(fp_lat, np.array([-0.562, 0.281, 0.281, -0.562]), atol=1e-2)

    def test_calc_area(self):
        """
        Test the calc_area method to verify the calculation of the footprint area.
        """
        a1 = self.fa2.calc_area(1000)
        self.assertAlmostEqual(a1, 130000, delta=200)
        a2 = self.fa3.calc_area(1000)
        self.assertAlmostEqual(a2, 486300, delta=200)
        a3 = self.fa4.calc_area(1000)
        self.assertAlmostEqual(a3, 810, delta=810 * 0.0025)
        a4 = self.fa5.calc_area(1000)
        self.assertAlmostEqual(a4, 234, delta=234 * 0.0025)

    def plot_footprints(self, sat_height, title):
        """
        Plot the footprints for various elevation angles at a given satellite height.
        """
        plt.figure(figsize=(15, 2))
        n = 100
        colors = plt.cm.viridis(np.linspace(0, 1, len(self.elevations)))
        labels = [f'${e:.0f}^o$' for e in self.elevations]

        # Plotting footprint for each elevation
        for elevation, color, label in zip(self.elevations, colors, labels):
            footprint = Footprint(5, elevation_deg=elevation, sat_height=sat_height)
            lng, lat = footprint.calc_footprint(n)
            plt.plot(lng, lat, color=color, label=label)

        plt.title(f"Footprints at {sat_height / 1000} km")
        plt.legend(loc='upper right', bbox_to_anchor=(1.1, 1))
        plt.xlabel('Longitude [deg]')
        plt.ylabel('Latitude [deg]')
        plt.grid()
        plt.show()

    def test_plot_1200km(self):
        """
        Test plotting of footprints at 1200 km satellite height.
        """
        self.plot_footprints(1200000, "1200 km")

    def test_plot_600km(self):
        """
        Test plotting of footprints at 600 km satellite height.
        """
        self.plot_footprints(600000, "600 km")

    def test_area_vs_elevation(self):
        """
        Test the variation of footprint area with elevation angle for different satellite heights.
        """
        n_el = len(self.elevations)
        n_poly = 1000
        elevation = np.linspace(5, 90, num=n_el)
        area_1200km = np.zeros_like(elevation)
        area_600km = np.zeros_like(elevation)

        # Footprint objects for different satellite heights [Km]
        fprint_1200km = Footprint(5, elevation_deg=0, sat_height=1200000)
        fprint_600km = Footprint(5, elevation_deg=0, sat_height=600000)

        # Calculate footprint area for different elevation angles [Deg]
        for k in range(len(elevation)):
            fprint_1200km.set_elevation(elevation[k])
            area_1200km[k] = fprint_1200km.calc_area(n_poly)
            fprint_600km.set_elevation(elevation[k])
            area_600km[k] = fprint_600km.calc_area(n_poly)

        # Plotting area x elevation
        plt.plot(elevation, area_1200km, color='r', label='1200 km')
        plt.plot(elevation, area_600km, color='b', label='600 km')
        plt.xlabel('Elevation [deg]')
        plt.ylabel('Footprint area [$km^2$]')
        plt.legend(loc='upper right')
        plt.xlim([0, 90])
        plt.grid()
        plt.show()

if __name__ == '__main__':
    unittest.main()
