# -*- coding: utf-8 -*-
"""
Created on Mon Aug 21 12:17:34 2017

@author: Andre Barreto
"""

import unittest
import numpy as np
import numpy.testing as npt
from sharc.propagation.scintillation import Scintillation


class TestScintillation(unittest.TestCase):
    def setUp(self):
        self.scintillation = Scintillation(np.random.RandomState())

    def test_tropo_scintillation_attenuation(self):
        # compare with benchmark from ITU-R P-619 Fig. 8
        antenna_gain = 0.0
        frequency_MHz = 30000.0
        wet_refractivity = 42.5

        elevation_vec = np.array(
            [5.0, 10.0, 20.0, 90.0, 35.0, 5.0, 10.0, 20.0, 35.0, 90.0]
        )
        percentage_gain_exceeded = np.array(
            [0.01, 0.1, 1, 3, 10, 90, 98, 99, 99.9, 99.99]
        )
        attenuation_lower = [5, 1, 0.5, 0.1, 0.1, 1, 1, 0.5, 0.4, 0.3]
        attenuation_upper = [7, 2, 0.6, 0.2, 0.2, 2, 2, 0.7, 0.6, 0.5]
        sign = [-1, -1, -1, -1, -1, +1, +1, +1, +1, +1]
        attenuation = self.scintillation.get_tropospheric_attenuation(
            elevation=elevation_vec,
            frequency_MHz=frequency_MHz,
            antenna_gain_dB=antenna_gain,
            time_ratio=percentage_gain_exceeded / 100,
            wet_refractivity=wet_refractivity,
        )

        npt.assert_array_less(attenuation_lower, np.abs(attenuation))
        npt.assert_array_less(np.abs(attenuation), attenuation_upper)

        npt.assert_array_equal(np.sign(attenuation), sign)


if __name__ == "__main__":
    unittest.main()
