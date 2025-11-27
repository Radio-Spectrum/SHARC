import unittest
import numpy as np
from sharc.propagation.propagation_clutter_loss import PropagationClutterLoss
from sharc.support.enumerations import StationType


class TestPropagationClutterLoss(unittest.TestCase):
    """Unit tests for the PropagationClutterLoss class and its loss calculations."""

    def setUp(self):
        """Set up test fixtures for PropagationClutterLoss tests."""
        self.clutter_loss = PropagationClutterLoss(np.random.RandomState(42))

    def test_spatial_clutter_loss(self):
        """Test spatial clutter loss for different elevations and location percentages."""
        frequency = np.array([27000, 27000, 27000])  # MHz
        elevation = np.array([10, 20, 30])
        loc_percentage = np.array([.1, .5, .9])
        distance = np.array([1000, 1000, 1000])  # meters, dummy value
        earth_station_height = np.array([10, 10, 10])
        mean_clutter_height = 'high'
        below_rooftop = 100
        loss = self.clutter_loss.get_loss(
            distance=distance,
            frequency=frequency,
            elevation=elevation,
            loc_percentage=loc_percentage,
            clutter_scenario="spatial",
            earth_station_height=earth_station_height,
            mean_clutter_height=mean_clutter_height,
            below_rooftop=below_rooftop,
        )

        # Check the shape of the output
        self.assertEqual(loss.shape, (3,))

        # Check if loss decreases with increasing elevation
        self.assertTrue(loss[0] <= loss[1] <= loss[2])

    def test_terrestrial_clutter_loss(self):
        """Test terrestrial clutter loss for different frequencies and distances."""
        frequency = np.array([2000, 6000])  # MHz
        distance = np.array([500, 2000])  # meters
        # Using a single value for location percentage
        loc_percentage = np.array([0.5])
        clutter_type = 'one_end'
        loss = self.clutter_loss.get_loss(
            frequency=frequency,
            distance=distance,
            loc_percentage=loc_percentage,
            clutter_scenario="terrestrial",
            clutter_type=clutter_type
        )

        self.assertEqual(loss.shape, (2,))

        self.assertTrue(loss[1] >= loss[0])

    def test_random_loc_percentage(self):
        """Test clutter loss calculation with random location percentage."""
        frequency = np.array([4000])  # MHz
        distance = np.array([1000])  # meters
        clutter_type = 'one_end'
        loss = self.clutter_loss.get_loss(
            frequency=frequency,
            distance=distance,
            loc_percentage="RANDOM",
            clutter_scenario="terrestrial",
            clutter_type=clutter_type
        )

        self.assertTrue(0 <= loss <= 100)


if __name__ == '__main__':
    unittest.main()
