# -*- coding: utf-8 -*-
"""3GPP mask on wide equivalent blocks, and the SA.509 pattern from the antenna factory."""
import unittest

import numpy as np

from sharc.antenna.antenna_factory import AntennaFactory
from sharc.antenna.antenna_sa509 import AntennaSA509
from sharc.mask.spectral_mask_3gpp import SpectralMask3Gpp
from sharc.parameters.constants import SPEED_OF_LIGHT
from sharc.parameters.parameters_antenna import ParametersAntenna
from sharc.support.enumerations import StationType


class WideBlock3GppMaskTest(unittest.TestCase):
    """SpectralMask3Gpp with 100 and 400 MHz blocks."""

    def mask(self, bandwidth):
        """BS mask of a 3500 MHz block, Cat-B spurious floor x4 operators."""
        mask = SpectralMask3Gpp(StationType.IMT_BS, 3500, bandwidth, -23.98)
        mask.set_mask(p_tx=40.0 + 10 * np.log10(64))
        return mask

    def test_far_victim_sees_spurious_floor(self):
        """A victim far beyond the edge gets the spurious floor, for 100 or 400 MHz."""
        far_100 = self.mask(100).power_calc(4895, 190)
        far_400 = self.mask(400).power_calc(4895, 190)
        self.assertAlmostEqual(far_400, far_100, places=9)
        self.assertAlmostEqual(far_400, -23.98 + 10 * np.log10(190), places=6)

    def test_invalid_bandwidth(self):
        """Unsupported bandwidths stop with a message instead of a TypeError."""
        with self.assertRaises(SystemExit):
            SpectralMask3Gpp(StationType.IMT_BS, 3500, 50, -30)


class SA509FromFactoryTest(unittest.TestCase):
    """The ITU-R SA.509 pattern registered in ParametersAntenna and AntennaFactory."""

    def test_pattern(self):
        """Peak gain from the aperture at the system frequency."""
        params = ParametersAntenna(pattern="ITU-R SA.509", gain=0.0)
        params.itu_r_sa_509.diameter = 12.0
        params.itu_r_sa_509.antenna_efficiency = 0.7
        params.set_external_parameters(frequency=4895.0)
        params.validate("antenna")

        antenna = AntennaFactory.create_antenna(params, 0.0, 90.0)
        self.assertIsInstance(antenna, AntennaSA509)
        wavelength = SPEED_OF_LIGHT / 4895e6
        g_0 = 10 * np.log10(0.7 * (np.pi * 12.0 / wavelength) ** 2)
        self.assertAlmostEqual(antenna.g_0, g_0)
        gain = antenna.calculate_gain(off_axis_angle_vec=np.array([0.0, 90.0]))
        self.assertAlmostEqual(gain[0], g_0)
        self.assertLess(gain[1], 0.0)

    def test_validation(self):
        """Diameter and efficiency are required."""
        params = ParametersAntenna(pattern="ITU-R SA.509", gain=0.0)
        params.set_external_parameters(frequency=4895.0)
        with self.assertRaises(ValueError):
            params.validate("antenna")


if __name__ == "__main__":
    unittest.main()
