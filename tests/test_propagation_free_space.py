# -*- coding: utf-8 -*-
"""
Created on Mon Mar  13 15:14:34 2017

@author: edgar
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.propagation.propagation_free_space import PropagationFreeSpace


class PropagationFreeSpaceTest(unittest.TestCase):
    """Unit tests for the PropagationFreeSpace class and its free space loss calculations."""

    def setUp(self):
        """Set up test fixtures for PropagationFreeSpace tests."""
        self.freeSpace = PropagationFreeSpace(np.random.RandomState())

    def test_loss(self):
        """Test the get_loss method for various distances and frequencies."""
        d = np.array([10])
        f = np.array([10])
        loss = self.freeSpace.get_loss(d, f)
        ref_loss = np.array([12.45])
        npt.assert_allclose(ref_loss, loss, atol=1e-2)

        d = np.array([10, 100])
        f = np.array([10, 100])
        loss = self.freeSpace.get_loss(d, f)
        ref_loss = np.array([12.45, 52.45])
        npt.assert_allclose(ref_loss, loss, atol=1e-2)

        d = np.array([10, 100, 1000])
        f = np.array([10, 100, 1000])
        loss = self.freeSpace.get_loss(d, f)
        ref_loss = np.array([12.45, 52.45, 92.45])
        npt.assert_allclose(ref_loss, loss, atol=1e-2)

        d = np.array([[10, 20, 30], [40, 50, 60]])
        f = np.array([100])
        loss = self.freeSpace.get_loss(d, f)
        ref_loss = np.array([
            [32.45, 38.47, 41.99],
            [44.49, 46.42, 48.01],
        ])
        npt.assert_allclose(ref_loss, loss, atol=1e-2)


if __name__ == '__main__':
    unittest.main()
