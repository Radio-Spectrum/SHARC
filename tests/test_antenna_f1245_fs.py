# -*- coding: utf-8 -*-
"""ITU-R F.1245 fixed-service antenna built by the antenna factory."""
import unittest

import numpy as np

from sharc.antenna.antenna_f1245_fs import Antenna_f1245_fs
from sharc.antenna.antenna_factory import AntennaFactory
from sharc.parameters.parameters_antenna import ParametersAntenna


class AntennaF1245FsTest(unittest.TestCase):
    """Peak gain from antenna.gain, diameter and the injected frequency."""

    def test_from_factory(self):
        """The pattern is created from ParametersAntenna and peaks at antenna.gain."""
        params = ParametersAntenna(pattern="ITU-R F.1245_fs", gain=38.4)
        params.itu_r_f_1245_fs.diameter = 4.0
        params.set_external_parameters(frequency=6460.0)
        params.validate("antenna")

        antenna = AntennaFactory.create_antenna(params, 0.0, 0.0)
        self.assertIsInstance(antenna, Antenna_f1245_fs)
        gain = antenna.calculate_gain(off_axis_angle_vec=np.array([0.0, 5.0, 90.0]))
        self.assertAlmostEqual(gain[0], 38.4)
        self.assertLess(gain[1], gain[0])
        self.assertLess(gain[2], 0.0)


if __name__ == "__main__":
    unittest.main()
