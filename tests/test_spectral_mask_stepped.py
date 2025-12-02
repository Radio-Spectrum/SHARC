# -*- coding: utf-8 -*-
"""
Created on Tue Dec  5 11:56:10 2017

@author: Calil
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.mask.spectral_mask_stepped import SpectralMaskStepped


class SpectalMaskSteppedTest(unittest.TestCase):
    """Unit tests for the SpectralMaskStepped class and its power calculation method."""

    def test_power_calc(self):
        """Test power calculation for the Stepped spectral mask at a given frequency and bandwidth."""
        freq = 2100  # MHz
        band = 5  # MHz
        p_tx_density = 0.0  # dBm / MHz
        p_tx = p_tx_density + 10 * np.log10(band)  # dBm
        spurious_emissions = -30.0  # dBm/MHz
        mask_steps = [-10, -15, -20]  # dBm/MHz
        mask_steps = np.concatenate([mask_steps, [spurious_emissions]])

        # Create mask
        msk = SpectralMaskStepped(freq, band, mask_steps)
        msk.set_mask(p_tx)

        N = len(msk.delta_f_lim)

        should_eq = np.zeros(2 * N)
        eq = np.zeros(2 * N)
        for i in range(N):
            f_offset = band + (i) * band

            # center to right edge
            should_eq[i + N] = mask_steps[i] + 10 * np.log10(band)
            eq[i + N] = msk.power_calc(freq + f_offset, band)

            # center to left edge
            should_eq[N - i - 1] = should_eq[i + N]
            eq[N - i - 1] = msk.power_calc(freq - f_offset, band)

        npt.assert_almost_equal(should_eq, eq)

        npt.assert_equal(
            -np.inf,
            msk.power_calc(
                freq, band,
            ),
        )

        # test between step edges
        for i in range(len(msk.mask_steps_dBm_mhz) - 1):
            center_f = freq + 3 * band / 2 + i * band
            actual_tx_oob = msk.power_calc(center_f=center_f, band=5)
            desired_tx_oob = 10 * np.log10(np.power(10, (msk.mask_steps_dBm_mhz[i] + 10 * np.log10(band / 2)) / 10) +
                                           np.power(10, (msk.mask_steps_dBm_mhz[i + 1] + 10 * np.log10(band / 2)) / 10))
            npt.assert_almost_equal(actual_tx_oob, desired_tx_oob)

        # test between step edges plus an offset
        for _ in range(1000):  # test for flaky behavior
            for i in range(len(msk.mask_steps_dBm_mhz) - 1):
                center_f = freq + 3 * band / 2 + i * band
                offset = np.random.random() * (2.5)
                actual_tx_oob = msk.power_calc(center_f=center_f + offset, band=5)
                desired_tx_oob = 10 * np.log10(
                    np.power(10, (msk.mask_steps_dBm_mhz[i] + 10 * np.log10(band / 2 - offset)) / 10) +
                    np.power(10, (msk.mask_steps_dBm_mhz[i + 1] + 10 * np.log10(band / 2 + offset)) / 10))
                npt.assert_almost_equal(actual_tx_oob, desired_tx_oob)


if __name__ == '__main__':
    unittest.main()
