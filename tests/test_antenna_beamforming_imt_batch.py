# -*- coding: utf-8 -*-
"""Batched beam and gain computation of AntennaBeamformingImt."""
import unittest

import numpy as np
import numpy.testing as npt

from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt


class AntennaBeamformingImtBatchTest(unittest.TestCase):
    """calculate_gain_batch against calculate_gain, as the downlink calls it."""

    def setUp(self):
        """Fifteen 8x8 arrays with four beams each, rows laid out as in the simulation."""
        param = ParametersAntennaImt()
        param.adjacent_antenna_model = "SINGLE_ELEMENT"
        param.normalization = False
        param.element_pattern = "M2101"
        param.minimum_array_gain = -200
        param.element_max_g = 3.65
        param.element_phi_3db = 90
        param.element_theta_3db = 65
        param.element_am = 30
        param.element_sla_v = 30
        param.n_rows = 8
        param.n_columns = 8
        param.element_horiz_spacing = 0.5
        param.element_vert_spacing = 4.2
        param.multiplication_factor = 12
        param.subarray.is_enabled = True
        param.subarray.n_rows = 6
        param.subarray.element_vert_spacing = 0.7
        param.subarray.eletrical_downtilt = 3.0
        par = param.get_antenna_parameters()

        rng = np.random.RandomState(7)
        self.k = 4
        n_bs = 15
        self.antennas = [
            AntennaBeamformingImt(par, az, -6.0) for az in rng.uniform(-180, 180, n_bs)
        ]
        for a in self.antennas:
            for _ in range(self.k):
                a.add_beam(rng.uniform(-180, 180), rng.uniform(80, 110))
        # one row per (BS, beam); every beam of a BS looks at the same victim
        phi_bs = rng.uniform(-180, 180, (n_bs, 1))
        theta_bs = rng.uniform(80, 100, (n_bs, 1))
        self.rows = [a for a in self.antennas for _ in range(self.k)]
        self.phi = np.repeat(phi_bs, self.k, axis=0)
        self.theta = np.repeat(theta_bs, self.k, axis=0)
        self.beams = np.tile(np.arange(self.k), n_bs)

    def loop(self, co_channel):
        """Reference: one calculate_gain call per row."""
        return np.array([
            a.calculate_gain(phi_vec=p, theta_vec=t, beams_l=np.array([b]), co_channel=co_channel)
            for a, p, t, b in zip(self.rows, self.phi, self.theta, self.beams)
        ])

    def test_adjacent_channel(self):
        """Beams of one antenna get exactly the same element gain."""
        gains = AntennaBeamformingImt.calculate_gain_batch(
            self.rows, self.phi, self.theta, self.beams, co_channel=False,
        )
        per_bs = gains.reshape(-1, self.k)
        npt.assert_array_equal(per_bs, np.repeat(per_bs[:, :1], self.k, axis=1))
        npt.assert_allclose(gains, self.loop(False), atol=1e-10)

    def test_co_channel(self):
        """Batched array gains match the per-row computation."""
        gains = AntennaBeamformingImt.calculate_gain_batch(
            self.rows, self.phi, self.theta, self.beams, co_channel=True,
        )
        npt.assert_allclose(gains, self.loop(True), atol=1e-10)


if __name__ == "__main__":
    unittest.main()
