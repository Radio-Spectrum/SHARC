# -*- coding: utf-8 -*-
"""
Tests for sharc.antenna.antenna_ra_m2319 module (ITU-R M.2319 radio-altimeter antenna).
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.antenna.antenna_ra_m2319 import AntennaRA_M2319, ParametersRA


class TestAntennaRAM2319Inband(unittest.TestCase):
    """Tests for in-band mode of the M.2319 antenna."""

    def setUp(self):
        self.param = ParametersRA()
        self.param.gain_isotropic_dbi = 5.0
        self.param.phi_3db_deg = 20.0
        self.param.inband = True
        self.antenna = AntennaRA_M2319(self.param)

    def test_gain_on_axis(self):
        """φ=0° in-band should give G = G_RA,dBi."""
        phi = np.array([0.0])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [5.0], atol=1e-12)

    def test_gain_at_3dB_beamwidth(self):
        """At φ = φ_3dB, gain should be G_RA - 12 dBi."""
        phi = np.array([20.0])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        expected = -12.0 / (20.0**2) * (20.0**2) + 5.0  # = -12 + 5 = -7
        npt.assert_allclose(gain, [expected], atol=1e-12)

    def test_gain_quadratic_rolloff(self):
        """Gain follows -12/φ_3dB² · φ² + G_RA formula."""
        phi = np.array([0.0, 5.0, 10.0, 15.0, 20.0])
        k = -12.0 / (20.0**2)
        expected = k * phi**2 + 5.0
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, expected, atol=1e-12)

    def test_gain_decreases_with_angle(self):
        """Gain should monotonically decrease with increasing angle."""
        phi = np.linspace(0, 90, 50)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        for i in range(len(gain) - 1):
            self.assertGreater(gain[i], gain[i + 1])

    def test_gain_negative_angle_treated_as_positive(self):
        """Negative angles should be treated as positive (abs taken)."""
        phi_pos = np.array([10.0])
        phi_neg = np.array([-10.0])
        gain_pos = self.antenna.calculate_gain(off_axis_angle_vec=phi_pos)
        gain_neg = self.antenna.calculate_gain(off_axis_angle_vec=phi_neg)
        npt.assert_allclose(gain_pos, gain_neg, atol=1e-12)

    def test_gain_vectorized(self):
        """Array input should produce array output with correct shape."""
        phi = np.linspace(0, 180, 181)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        self.assertEqual(gain.shape, (181,))


class TestAntennaRAM2319Outband(unittest.TestCase):
    """Tests for out-of-band mode of the M.2319 antenna."""

    def setUp(self):
        self.param = ParametersRA()
        self.param.gain_isotropic_dbi = 5.0
        self.param.phi_3db_deg = 20.0
        self.param.inband = False
        self.antenna = AntennaRA_M2319(self.param)

    def test_gain_below_90(self):
        """For φ < 90° out-of-band, gain should be 0 dBi."""
        phi = np.array([0.0, 30.0, 60.0, 89.0])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [0.0, 0.0, 0.0, 0.0], atol=1e-12)

    def test_gain_at_90(self):
        """At φ = 90° out-of-band, gain should be 0 dBi (= -|90-90|)."""
        phi = np.array([90.0])
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, [0.0], atol=1e-12)

    def test_gain_above_90(self):
        """For φ ≥ 90° out-of-band, gain should be -|φ-90|."""
        phi = np.array([100.0, 120.0, 180.0])
        expected = -np.abs(phi - 90.0)
        gain = self.antenna.calculate_gain(off_axis_angle_vec=phi)
        npt.assert_allclose(gain, expected, atol=1e-12)


class TestAntennaRAM2319Validation(unittest.TestCase):
    """Tests for parameter validation."""

    def test_invalid_phi_3db_raises(self):
        """phi_3db_deg <= 0 should raise ValueError."""
        param = ParametersRA()
        param.phi_3db_deg = 0.0
        with self.assertRaises(ValueError):
            AntennaRA_M2319(param)

    def test_negative_phi_3db_raises(self):
        """Negative phi_3db_deg should raise ValueError."""
        param = ParametersRA()
        param.phi_3db_deg = -10.0
        with self.assertRaises(ValueError):
            AntennaRA_M2319(param)


if __name__ == "__main__":
    unittest.main()
