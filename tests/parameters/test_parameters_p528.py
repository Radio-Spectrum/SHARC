# -*- coding: utf-8 -*-
"""
Tests for sharc.parameters.parameters_p528 module.
"""

import unittest
import numpy as np

from sharc.parameters.parameters_p528 import ParametersP528


class TestParametersP528Defaults(unittest.TestCase):
    """Tests for default values and properties."""

    def test_default_channel_model(self):
        """Default channel_model should be 'P528'."""
        p = ParametersP528()
        self.assertEqual(p.channel_model, "P528")

    def test_default_time_percentage_random(self):
        """Default time_percentage should be 'RANDOM'."""
        p = ParametersP528()
        self.assertEqual(p.time_percentage, "RANDOM")

    def test_default_polarization_random(self):
        """Default polarization should be 'RANDOM'."""
        p = ParametersP528()
        self.assertEqual(p.polarization, "RANDOM")

    def test_p_time_property_random(self):
        """When time_percentage='RANDOM', p_time should return 50.0."""
        p = ParametersP528()
        self.assertEqual(p.p_time, 50.0)

    def test_p_time_property_fixed(self):
        """When time_percentage is numeric, p_time returns that value."""
        p = ParametersP528(time_percentage=30.0)
        self.assertEqual(p.p_time, 30.0)

    def test_Tpol_property_random(self):
        """When polarization='RANDOM', Tpol should return 1 (vertical)."""
        p = ParametersP528()
        self.assertEqual(p.Tpol, 1)

    def test_Tpol_property_fixed(self):
        """When polarization is numeric, Tpol returns that value."""
        p = ParametersP528(polarization=0)
        self.assertEqual(p.Tpol, 0)

    def test_Tpol_property_invalid(self):
        """When polarization is invalid int, Tpol should raise ValueError."""
        p = ParametersP528(polarization=3)
        with self.assertRaises(ValueError):
            _ = p.Tpol


class TestParametersP528Validation(unittest.TestCase):
    """Tests for validate method."""

    def test_validate_valid_config(self):
        """Valid config should pass validation."""
        p = ParametersP528(time_percentage=50.0, polarization=1)
        try:
            p.validate("test")
        except ValueError:
            self.fail("validate() raised ValueError on valid config")

    def test_validate_random_fields(self):
        """Config with RANDOM fields should pass validation."""
        p = ParametersP528()
        try:
            p.validate("test")
        except ValueError:
            self.fail("validate() raised ValueError on RANDOM config")

    def test_validate_invalid_channel_model(self):
        """Invalid channel_model should raise ValueError."""
        p = ParametersP528(channel_model="P619")
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_time_percentage_zero(self):
        """time_percentage=0 (out of [1,99]) should raise ValueError."""
        p = ParametersP528(time_percentage=0.0)
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_time_percentage_100(self):
        """time_percentage=100 (out of [1,99]) should raise ValueError."""
        p = ParametersP528(time_percentage=100.0)
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_invalid_polarization(self):
        """polarization=3 should raise ValueError."""
        p = ParametersP528(polarization=3)
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_invalid_Ns_low(self):
        """Ns=50 (below 100) should raise ValueError."""
        p = ParametersP528(time_percentage=50.0, polarization=1, Ns=50.0)
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_invalid_Ns_high(self):
        """Ns=500 (above 450) should raise ValueError."""
        p = ParametersP528(time_percentage=50.0, polarization=1, Ns=500.0)
        with self.assertRaises(ValueError):
            p.validate("test")

    def test_validate_valid_Ns(self):
        """Ns=301 should pass validation."""
        p = ParametersP528(time_percentage=50.0, polarization=1, Ns=301.0)
        try:
            p.validate("test")
        except ValueError:
            self.fail("validate() raised ValueError on valid Ns=301")


class TestParametersP528Resolve(unittest.TestCase):
    """Tests for resolve method."""

    def test_resolve_random_time(self):
        """'RANDOM' time_percentage should be resolved to numeric in [1,99]."""
        rng = np.random.RandomState(42)
        p = ParametersP528(time_percentage="RANDOM", polarization=1)
        resolved = p.resolve(rng=rng)
        self.assertIsInstance(resolved.time_percentage, float)
        self.assertGreaterEqual(resolved.time_percentage, 1.0)
        self.assertLessEqual(resolved.time_percentage, 99.0)

    def test_resolve_random_polarization(self):
        """'RANDOM' polarization should be resolved to 0 or 1."""
        rng = np.random.RandomState(42)
        p = ParametersP528(time_percentage=50.0, polarization="RANDOM")
        resolved = p.resolve(rng=rng)
        self.assertIn(resolved.polarization, [0, 1])

    def test_resolve_fixed_values_preserved(self):
        """Fixed values should be preserved after resolve()."""
        rng = np.random.RandomState(42)
        p = ParametersP528(time_percentage=30.0, polarization=0, Ns=250.0)
        resolved = p.resolve(rng=rng)
        self.assertEqual(resolved.time_percentage, 30.0)
        self.assertEqual(resolved.polarization, 0)
        self.assertEqual(resolved.Ns, 250.0)

    def test_resolve_does_not_modify_original(self):
        """resolve() should return a new instance, not modify the original."""
        p = ParametersP528(time_percentage="RANDOM", polarization="RANDOM")
        rng = np.random.RandomState(42)
        _ = p.resolve(rng=rng)
        self.assertEqual(p.time_percentage, "RANDOM")
        self.assertEqual(p.polarization, "RANDOM")

    def test_resolve_custom_time_range(self):
        """resolve() with custom time_rng should respect the range."""
        rng = np.random.RandomState(42)
        p = ParametersP528(time_percentage="RANDOM", polarization=1)
        resolved = p.resolve(rng=rng, time_rng=(10.0, 20.0))
        self.assertGreaterEqual(resolved.time_percentage, 10.0)
        self.assertLessEqual(resolved.time_percentage, 20.0)

    def test_resolve_reproducibility(self):
        """Same seed should produce same resolved values."""
        p = ParametersP528(time_percentage="RANDOM", polarization="RANDOM")
        r1 = p.resolve(rng=np.random.RandomState(123))
        r2 = p.resolve(rng=np.random.RandomState(123))
        self.assertEqual(r1.time_percentage, r2.time_percentage)
        self.assertEqual(r1.polarization, r2.polarization)


if __name__ == "__main__":
    unittest.main()
