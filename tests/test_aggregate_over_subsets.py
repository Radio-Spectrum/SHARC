# -*- coding: utf-8 -*-
"""Second Monte Carlo over the subsets of a base-station database run."""
import unittest

import numpy as np
import numpy.testing as npt

from sharc.post_processor import PostProcessor


class AggregateOverSubsetsTest(unittest.TestCase):
    """PostProcessor.aggregate_over_subsets."""

    def test_constant_subsets(self):
        """With one value per subset, every aggregate is their linear sum."""
        samples = [-10.0] * 5 + [-13.0] * 7 + [-20.0] * 4
        subsets = [0] * 5 + [1] * 7 + [2] * 4
        aggregate = PostProcessor.aggregate_over_subsets(samples, subsets)
        self.assertEqual(aggregate.size, 4)
        expected = 10 * np.log10(10 ** -1.0 + 10 ** -1.3 + 10 ** -2.0)
        npt.assert_allclose(aggregate, expected)

    def test_draws_one_sample_per_subset(self):
        """The mean linear aggregate is the sum of the subset means."""
        rng = np.random.RandomState(3)
        a = rng.normal(-10, 3, 4000)
        b = rng.normal(-15, 3, 4000)
        aggregate = PostProcessor.aggregate_over_subsets(
            np.concatenate([a, b]), [0] * 4000 + [1] * 4000, n_aggregate=20000,
        )
        expected = np.mean(10 ** (a / 10)) + np.mean(10 ** (b / 10))
        self.assertAlmostEqual(np.mean(10 ** (aggregate / 10)) / expected, 1.0, delta=0.03)
        # the aggregate is never below the louder subset alone
        self.assertGreaterEqual(aggregate.min(), min(a.min(), b.min()))

    def test_repeatable_and_validated(self):
        """Fixed default seed; mismatched or empty inputs are rejected."""
        samples, subsets = [-1.0, -2.0, -3.0, -4.0], [0, 0, 1, 1]
        npt.assert_array_equal(
            PostProcessor.aggregate_over_subsets(samples, subsets),
            PostProcessor.aggregate_over_subsets(samples, subsets),
        )
        with self.assertRaises(ValueError):
            PostProcessor.aggregate_over_subsets(samples, [0, 1])
        with self.assertRaises(ValueError):
            PostProcessor.aggregate_over_subsets([], [])
        with self.assertRaises(ValueError):
            PostProcessor.aggregate_over_subsets(samples, subsets, n_aggregate=0)


if __name__ == "__main__":
    unittest.main()
