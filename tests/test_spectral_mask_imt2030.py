# -*- coding: utf-8 -*-
"""
Tests for sharc.mask.spectral_mask_imt2030 module (IMT-2030 spectral emission mask).
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.mask.spectral_mask_imt2030 import SpectralMaskImt2030
from sharc.support.enumerations import StationType


class TestSpectralMaskImt2030BsMacro(unittest.TestCase):
    """Tests for BS MACROCELL emission masks."""

    def test_bs_cat_a_macro_first_limit(self):
        """CatA MACROCELL: first emission limit should start at 12 dBm/MHz."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        )
        limits = mask.get_emission_limits(
            StationType.IMT_BS, 100, -13, "CatA", "MACROCELL"
        )
        # First element: 12 - 7/50 * (0.05 - 0.05) = 12
        npt.assert_allclose(limits[0], 12.0, atol=0.01)

    def test_bs_cat_a_macro_tail_values(self):
        """CatA MACROCELL: last 3 values should be [5, -4, -13]."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        )
        limits = mask.get_emission_limits(
            StationType.IMT_BS, 100, -13, "CatA", "MACROCELL"
        )
        npt.assert_allclose(limits[-3:], [5.0, -4.0, -13.0], atol=1e-10)

    def test_bs_cat_b_macro_first_limit(self):
        """CatB MACROCELL: first emission limit should start at 3 dBm/MHz."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -30, "CatB", "MACROCELL"
        ).get_emission_limits(StationType.IMT_BS, 100, -30, "CatB", "MACROCELL")
        npt.assert_allclose(limits[0], 3.0, atol=0.01)

    def test_bs_cat_b_macro_tail_values(self):
        """CatB MACROCELL: last 3 values should be [-4, -15, -30]."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -30, "CatB", "MACROCELL"
        ).get_emission_limits(StationType.IMT_BS, 100, -30, "CatB", "MACROCELL")
        npt.assert_allclose(limits[-3:], [-4.0, -15.0, -30.0], atol=1e-10)

    def test_bs_cat_a_macro_limits_decreasing(self):
        """CatA MACROCELL: piecewise emission limits should decrease."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        ).get_emission_limits(StationType.IMT_BS, 100, -13, "CatA", "MACROCELL")
        # The continuous portion should be monotonically decreasing
        continuous = limits[:-3]  # exclude appended discrete values
        for i in range(len(continuous) - 1):
            self.assertGreaterEqual(continuous[i], continuous[i + 1])


class TestSpectralMaskImt2030BsNonMacro(unittest.TestCase):
    """Tests for BS non-MACROCELL emission masks."""

    def test_bs_cat_a_non_macro_first_limit(self):
        """CatA non-macro: first emission limit should start at 3 dBm/MHz."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "HOTSPOT"
        ).get_emission_limits(StationType.IMT_BS, 100, -13, "CatA", "HOTSPOT")
        npt.assert_allclose(limits[0], 3.0, atol=0.01)

    def test_bs_cat_a_non_macro_tail_values(self):
        """CatA non-macro: last 3 values should be [-4, -13, -13]."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "HOTSPOT"
        ).get_emission_limits(StationType.IMT_BS, 100, -13, "CatA", "HOTSPOT")
        npt.assert_allclose(limits[-3:], [-4.0, -13.0, -13.0], atol=1e-10)

    def test_bs_cat_b_non_macro_first_limit(self):
        """CatB non-macro: first emission limit should start at -3 dBm/MHz."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -30, "CatB", "HOTSPOT"
        ).get_emission_limits(StationType.IMT_BS, 100, -30, "CatB", "HOTSPOT")
        npt.assert_allclose(limits[0], -3.0, atol=0.01)

    def test_bs_cat_b_non_macro_tail_values(self):
        """CatB non-macro: last 3 values should be [-4, -15, -30]."""
        limits = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -30, "CatB", "HOTSPOT"
        ).get_emission_limits(StationType.IMT_BS, 100, -30, "CatB", "HOTSPOT")
        npt.assert_allclose(limits[-3:], [-4.0, -15.0, -30.0], atol=1e-10)


class TestSpectralMaskImt2030UE(unittest.TestCase):
    """Tests for UE emission masks."""

    def test_ue_bw_20_limits(self):
        """UE BW=20: emission limits follow the expected pattern."""
        limits = SpectralMaskImt2030(
            StationType.IMT_UE, 3500, 20, -25
        ).get_emission_limits(StationType.IMT_UE, 20, -25, "CatA", "MACROCELL")
        # UE: limit_r1 = -13, then -13 + 10*log10(1/(0.01*20)) = -13 + 10*log10(5) ≈ -13 + 6.99 = -6.01
        expected_first = -13 + 10 * np.log10(1 / (0.01 * 20))
        npt.assert_allclose(limits[0], expected_first, atol=0.01)
        # Remaining: [-10, -13, -25, -25]
        npt.assert_allclose(limits[1:], [-10.0, -13.0, -25.0, -25.0], atol=1e-10)

    def test_ue_bw_100_limits(self):
        """UE BW=100: uses different limit_r1 formula."""
        limits = SpectralMaskImt2030(
            StationType.IMT_UE, 3500, 100, -25
        ).get_emission_limits(StationType.IMT_UE, 100, -25, "CatA", "MACROCELL")
        # BW > 50: limit_r1 = -24 + 10*log10(1/0.03)
        expected_first = -24 + 10 * np.log10(1 / 0.03)
        npt.assert_allclose(limits[0], expected_first, atol=0.01)

    def test_ue_spurious_emission_passthrough(self):
        """UE: last element of emission limits should be the spurious_emissions value."""
        spurious = -30.0
        limits = SpectralMaskImt2030(
            StationType.IMT_UE, 3500, 20, spurious
        ).get_emission_limits(StationType.IMT_UE, 20, spurious, "CatA", "MACROCELL")
        self.assertAlmostEqual(limits[-1], spurious)


class TestSpectralMaskImt2030FreqLimits(unittest.TestCase):
    """Tests for get_frequency_limits."""

    def test_bs_macro_freq_limits(self):
        """BS MACROCELL freq limits: 0 to 50 MHz (step 0.1) + 100 MHz."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        )
        delta_f = mask.get_frequency_limits(StationType.IMT_BS, 100, "MACROCELL")
        # Should be arange(0, 50, 0.1) + [100] = 500 + 1 = 501 elements
        self.assertEqual(len(delta_f), 501)
        npt.assert_allclose(delta_f[0], 0.0, atol=1e-10)
        npt.assert_allclose(delta_f[-1], 100.0, atol=1e-10)

    def test_bs_non_macro_freq_limits(self):
        """BS non-MACROCELL freq limits: 0 to 20 MHz (step 0.1) + 40 MHz."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "HOTSPOT"
        )
        delta_f = mask.get_frequency_limits(StationType.IMT_BS, 100, "HOTSPOT")
        self.assertEqual(len(delta_f), 201)
        npt.assert_allclose(delta_f[-1], 40.0, atol=1e-10)

    def test_ue_freq_limits_bw20(self):
        """UE BW=20 freq limits start with [0, 1, 5]."""
        mask = SpectralMaskImt2030(
            StationType.IMT_UE, 3500, 20, -25
        )
        delta_f = mask.get_frequency_limits(StationType.IMT_UE, 20, "MACROCELL")
        npt.assert_allclose(delta_f[:3], [0, 1, 5], atol=1e-10)
        # BW=20 adds [20, 25]
        npt.assert_allclose(delta_f[3], 20.0, atol=1e-10)
        npt.assert_allclose(delta_f[4], 25.0, atol=1e-10)


class TestSpectralMaskImt2030SetMask(unittest.TestCase):
    """Tests for set_mask."""

    def test_set_mask_symmetry(self):
        """After set_mask, the mask_dbm should be symmetric."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        )
        mask.set_mask(p_tx=23.0)
        n = len(mask.mask_dbm)
        # The center value is p_tx - 10*log10(BW)
        center_idx = n // 2
        # Check symmetry around center
        for i in range(center_idx):
            self.assertAlmostEqual(
                mask.mask_dbm[i],
                mask.mask_dbm[n - 1 - i],
                places=10,
                msg=f"Mask not symmetric at index {i}",
            )

    def test_set_mask_center_value(self):
        """Center of mask should be p_tx - 10*log10(BW)."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        )
        mask.set_mask(p_tx=23.0)
        n = len(mask.mask_dbm)
        center = mask.mask_dbm[n // 2]
        expected = 23.0 - 10 * np.log10(100)
        self.assertAlmostEqual(center, expected, places=6)

    def test_freq_lim_symmetric(self):
        """freq_lim should be symmetric around center frequency."""
        mask = SpectralMaskImt2030(
            StationType.IMT_BS, 3500, 100, -13, "CatA", "MACROCELL"
        )
        n = len(mask.freq_lim)
        center = 3500.0
        for i in range(n // 2):
            delta_lo = center - mask.freq_lim[i]
            delta_hi = mask.freq_lim[n - 1 - i] - center
            self.assertAlmostEqual(delta_lo, delta_hi, places=6)


if __name__ == "__main__":
    unittest.main()
