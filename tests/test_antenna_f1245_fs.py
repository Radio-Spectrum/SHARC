# -*- coding: utf-8 -*-
"""
Tests for sharc.antenna.antenna_f1245_fs module (ITU-R F.1245 FS antenna pattern).
"""

import unittest
import math
import numpy as np
import numpy.testing as npt

from sharc.antenna.antenna_f1245_fs import Atenna_f1245_fs
from sharc.parameters.parameters_antenna import ParametersAntenna


class _MockParam:
    """Lightweight parameter mock for Atenna_f1245_fs.__init__."""

    def __init__(self, gain, frequency_mhz, diameter):
        self.gain = gain
        self.frequency = frequency_mhz
        self.diameter = diameter


class TestAntennaF1245FsGreater(unittest.TestCase):
    """Tests for Atenna_f1245_fs with d/λ > 100 (large antenna)."""

    def setUp(self):
        # D=5m, f=8000MHz => λ=0.0375m => d/λ = 133.3 > 100
        self.param = _MockParam(gain=40.0, frequency_mhz=8000, diameter=5.0)
        self.antenna = Atenna_f1245_fs(self.param)
        self.antenna.add_beam(0, 0)

    def test_d_lambda_greater_than_100(self):
        """Verify d/λ > 100 for this config."""
        self.assertGreater(self.antenna.d_lmbda, 100)

    def test_gain_on_axis(self):
        """On-axis (φ≈0) gain should equal peak gain (nearly)."""
        phi = np.array([1e-6])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [self.param.gain], atol=0.01)

    def test_gain_mainlobe_rolloff(self):
        """Gain should decrease with increasing φ in mainlobe."""
        phi = np.array([0.01, 0.05, 0.1])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        self.assertGreater(gain[0], gain[1])
        self.assertGreater(gain[1], gain[2])

    def test_gain_sidelobe_level_at_phi_m(self):
        """At φ = φ_m the gain should equal G_l."""
        phi_m = self.antenna.phi_m
        # Just past phi_m should give G_l
        phi = np.array([phi_m + 0.001])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [self.antenna.g_l], atol=0.5)

    def test_gain_far_sidelobe(self):
        """For 48° ≤ φ ≤ 180°, gain should be -13 dBi."""
        phi = np.array([48.0, 90.0, 120.0, 180.0])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [-13.0, -13.0, -13.0, -13.0], atol=1e-10)

    def test_gain_intermediate_region(self):
        """Between max(φ_m, φ_r) and 48°, gain follows 29 - 25·log10(φ)."""
        phi = np.array([10.0, 20.0, 40.0])
        expected = 29 - 25 * np.log10(phi)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, expected, atol=0.5)

    def test_gain_vectorized_shape(self):
        """Array input should produce same-shaped output."""
        phi = np.linspace(0.1, 180, 100)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        self.assertEqual(gain.shape, phi.shape)


class TestAntennaF1245FsLess(unittest.TestCase):
    """Tests for Atenna_f1245_fs with d/λ ≤ 100 (smaller antenna)."""

    def setUp(self):
        # D=2m, f=8000MHz => λ=0.0375m => d/λ = 53.3 ≤ 100
        self.param = _MockParam(gain=35.0, frequency_mhz=8000, diameter=2.0)
        self.antenna = Atenna_f1245_fs(self.param)
        self.antenna.add_beam(0, 0)

    def test_d_lambda_less_or_equal_100(self):
        """Verify d/λ ≤ 100 for this config."""
        self.assertLessEqual(self.antenna.d_lmbda, 100)

    def test_gain_on_axis(self):
        """On-axis gain should equal peak gain."""
        phi = np.array([1e-6])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [self.param.gain], atol=0.01)

    def test_gain_far_sidelobe_less(self):
        """For 48° ≤ φ < 180°, gain should be -3 - 5·log10(d/λ)."""
        expected = -3 - 5 * math.log10(self.antenna.d_lmbda)
        phi = np.array([48.0, 90.0, 150.0])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [expected] * 3, atol=1e-10)

    def test_gain_intermediate_less(self):
        """Between φ_m and 48°, gain follows 39 - 5·log10(d/λ) - 25·log10(φ)."""
        phi = np.array([10.0, 20.0, 40.0])
        expected = 39 - 5 * math.log10(self.antenna.d_lmbda) - 25 * np.log10(phi)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, expected, atol=0.5)

    def test_gain_monotonically_decreasing_near_axis(self):
        """Gain should monotonically decrease near axis in mainlobe."""
        phi = np.linspace(0.01, self.antenna.phi_m * 0.9, 20)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        for i in range(len(gain) - 1):
            self.assertGreaterEqual(gain[i], gain[i + 1])


class TestAntennaF1245FsBeams(unittest.TestCase):
    """Tests for beam management and off-axis angle calculation."""

    def setUp(self):
        self.param = _MockParam(gain=35.0, frequency_mhz=8000, diameter=2.0)
        self.antenna = Atenna_f1245_fs(self.param)

    def test_add_beam(self):
        """add_beam should grow the beams list."""
        self.assertEqual(len(self.antenna.beams_list), 0)
        self.antenna.add_beam(10.0, 20.0)
        self.assertEqual(len(self.antenna.beams_list), 1)
        self.antenna.add_beam(30.0, 40.0)
        self.assertEqual(len(self.antenna.beams_list), 2)

    def test_off_axis_angle_on_beam(self):
        """Off-axis angle to the beam direction should be 0°."""
        self.antenna.add_beam(45.0, 30.0)
        # b is elevation angle, Az is azimuth
        off_axis = self.antenna.calculate_off_axis_angle(
            Az=np.array([45.0]), b=np.array([90 - 30.0])
        )
        npt.assert_allclose(off_axis, [0.0], atol=1e-8)

    def test_off_axis_angle_perpendicular(self):
        """Off-axis angle 90° from beam should be ~90°."""
        self.antenna.add_beam(0.0, 0.0)  # beam at az=0, el=0 → a=90
        off_axis = self.antenna.calculate_off_axis_angle(
            Az=np.array([90.0]), b=np.array([90.0])
        )
        npt.assert_allclose(off_axis, [90.0], atol=1e-6)


if __name__ == "__main__":
    unittest.main()
