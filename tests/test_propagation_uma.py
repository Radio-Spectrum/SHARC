# -*- coding: utf-8 -*-
"""
Created on Tue Jun  6 14:12:43 2017

@author: edgar
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.propagation.propagation_uma import PropagationUMa


class PropagationUMaTest(unittest.TestCase):
    """Unit tests for the PropagationUMa class and its urban macrocell propagation loss calculations."""

    def setUp(self):
        """Set up test fixtures for PropagationUMa tests."""
        self.uma = PropagationUMa(np.random.RandomState())

    def test_los_probability(self):
        """Test the calculation of line-of-sight (LOS) probability."""
        distance_2D = np.array([
            [10, 15, 40],
            [17, 60, 80],
        ])
        h_ue = np.array([1.5, 8, 15])
        los_probability = np.array([
            [1, 1, 0.74],
            [1, 0.57, 0.45],
        ])
        npt.assert_allclose(
            self.uma.get_los_probability(distance_2D, h_ue),
            los_probability,
            atol=1e-2,
        )

    def test_los_probability_row_oriented(self):
        """Test the calculation of line-of-sight (LOS) probability when UEs are row-oriented."""
        distance_2D = np.array([
            [10, 15],
            [17, 60],
            [40, 80],
        ])
        h_ue = np.array([1.5, 8, 15])
        # Expected:
        # UT 0 (1.5m) and UT 1 (8m) have height <= 13 -> c_prime = 0
        # UT 2 (15m) has height > 13 -> c_prime = ((15-13)/10)**1.5 = 0.2**1.5 ≈ 0.0894
        c_prime = np.array([
            [0.0, 0.0],
            [0.0, 0.0],
            [0.0894427, 0.0894427]
        ])
        
        # We manually compute the expected p_los:
        # For d2d <= 18: p_los = 1
        # For d2d > 18:
        # p_los = (18/d + exp(-d/63)*(1 - 18/d)) * (1 + 1.25 * c_prime * (d/100)**3 * exp(-d/150))
        # UT 0: d=[10, 15] <= 18 -> p_los = [1.0, 1.0]
        # UT 1: d=17 <= 18 -> 1.0, d=60 > 18 -> p_los[1, 1]
        # UT 2: d=40 > 18, d=80 > 18 -> p_los[2, 0], p_los[2, 1]
        expected_p_los = np.ones((3, 2))
        
        # d = 60 (UT 1, BS 1)
        term1 = 18/60 + np.exp(-60/63)*(1 - 18/60)
        expected_p_los[1, 1] = term1
        
        # d = 40 (UT 2, BS 0)
        term1 = 18/40 + np.exp(-40/63)*(1 - 18/40)
        term2 = 1 + 1.25 * c_prime[2, 0] * (40/100)**3 * np.exp(-40/150)
        expected_p_los[2, 0] = term1 * term2
        
        # d = 80 (UT 2, BS 1)
        term1 = 18/80 + np.exp(-80/63)*(1 - 18/80)
        term2 = 1 + 1.25 * c_prime[2, 1] * (80/100)**3 * np.exp(-80/150)
        expected_p_los[2, 1] = term1 * term2

        npt.assert_allclose(
            self.uma.get_los_probability(distance_2D, h_ue),
            expected_p_los,
            atol=1e-5,
        )

    def test_breakpoint_distance(self):
        """Test the calculation of breakpoint distance for UMa scenario."""
        h_bs = np.array([15, 20, 25, 30])
        h_ue = np.array([3, 4])
        h_e = np.ones((h_ue.size, h_bs.size))
        frequency = 30000 * np.ones(h_e.shape)
        breakpoint_distance = np.array([
            [11200, 15200, 19200, 23200],
            [16800, 22800, 28800, 34800],
        ])
        npt.assert_array_equal(
            self.uma.get_breakpoint_distance(frequency, h_bs, h_ue, h_e),
            breakpoint_distance,
        )

    def test_loss_los(self):
        """Test the calculation of LOS path loss for UMa scenario."""
        distance_2D = np.array([
            [100, 500],
            [200, 600],
            [300, 700],
            [400, 800],
        ])
        h_bs = np.array([30, 35])
        h_ue = np.array([2, 3, 4, 5])
        h_e = np.ones(distance_2D.shape)
        distance_3D = np.sqrt(distance_2D**2 + (h_bs - h_ue[:, np.newaxis])**2)
        frequency = 30000 * np.ones(distance_2D.shape)
        shadowing_std = 0
        loss = np.array([
            [102.32, 115.99],
            [108.09, 117.56],
            [111.56, 118.90],
            [114.05, 120.06],
        ])
        npt.assert_allclose(
            self.uma.get_loss_los(
                distance_2D, distance_3D, frequency,
                h_bs, h_ue, h_e, shadowing_std,
            ),
            loss,
            atol=1e-2,
        )

        distance_2D = np.array([
            [100, 500],
            [200, 600],
            [300, 700],
            [400, 800],
        ])
        h_bs = np.array([30, 35])
        h_ue = np.array([2, 3, 4, 5])
        h_e = np.ones(distance_2D.shape)
        distance_3D = np.sqrt(distance_2D**2 + (h_bs - h_ue[:, np.newaxis])**2)
        frequency = 300 * np.ones(distance_2D.shape)
        shadowing_std = 0
        loss = np.array([
            [62.32, 87.06],
            [68.09, 84.39],
            [71.56, 83.57],
            [74.05, 83.40],
        ])
        npt.assert_allclose(
            self.uma.get_loss_los(
                distance_2D, distance_3D, frequency,
                h_bs, h_ue, h_e, shadowing_std,
            ),
            loss,
            atol=1e-2,
        )

    def test_loss_nlos(self):
        """Test the calculation of NLOS path loss for UMa scenario."""
        distance_2D = np.array([
            [100, 500],
            [200, 600],
            [300, 700],
            [400, 800],
        ])
        h_bs = np.array([30, 35])
        h_ue = np.array([2, 3, 4, 5])
        h_e = np.ones(distance_2D.shape)
        distance_3D = np.sqrt(distance_2D**2 + (h_bs - h_ue[:, np.newaxis])**2)
        frequency = 30000 * np.ones(distance_2D.shape)
        shadowing_std = 0
        loss = np.array([
            [121.58, 148.29],
            [132.25, 150.77],
            [138.45, 152.78],
            [142.70, 154.44],
        ])
        npt.assert_allclose(
            self.uma.get_loss_nlos(
                distance_2D, distance_3D, frequency,
                h_bs, h_ue, h_e, shadowing_std,
            ),
            loss,
            atol=1e-2,
        )

        distance_2D = np.array([
            [1000, 3000],
            [2000, 6000],
            [5000, 7000],
            [4000, 8000],
        ])
        h_bs = np.array([30, 35])
        h_ue = np.array([2, 3, 4, 5])
        h_e = np.ones(distance_2D.shape)
        distance_3D = np.sqrt(distance_2D**2 + (h_bs - h_ue[:, np.newaxis])**2)
        frequency = 300 * np.ones(distance_2D.shape)
        shadowing_std = 0
        loss = np.array([
            [120.02, 138.66],
            [131.18, 149.83],
            [146.13, 151.84],
            [141.75, 153.51],
        ])
        npt.assert_allclose(
            self.uma.get_loss_nlos(
                distance_2D, distance_3D, frequency,
                h_bs, h_ue, h_e, shadowing_std,
            ),
            loss,
            atol=1e-2,
        )


if __name__ == '__main__':
    unittest.main()
