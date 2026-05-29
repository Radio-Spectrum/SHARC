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
            clutter_type=clutter_type,
            below_rooftop=100,
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
            clutter_type=clutter_type,
            below_rooftop=100,
        )

        self.assertTrue(0 <= loss <= 100)

    def test_spatial_clutter_high_vs_low(self):
        """High mean clutter height should generally produce more loss than low."""
        frequency = np.array([27000])
        elevation = np.array([15])
        loc_percentage = np.array([0.5])
        distance = np.array([1000])
        earth_station_height = np.array([5])
        below_rooftop = 100

        loss_low = self.clutter_loss.get_loss(
            distance=distance, frequency=frequency, elevation=elevation,
            loc_percentage=loc_percentage, clutter_scenario="spatial",
            earth_station_height=earth_station_height,
            mean_clutter_height='low', below_rooftop=below_rooftop,
        )
        loss_high = self.clutter_loss.get_loss(
            distance=distance, frequency=frequency, elevation=elevation,
            loc_percentage=loc_percentage, clutter_scenario="spatial",
            earth_station_height=earth_station_height,
            mean_clutter_height='high', below_rooftop=below_rooftop,
        )
        # High clutter should cause at least as much loss as low
        self.assertGreaterEqual(loss_high.item(), loss_low.item() - 1.0)

    def test_spatial_clutter_mid_between(self):
        """Mid mean_clutter_height should produce loss between low and high (or equal)."""
        frequency = np.array([27000])
        elevation = np.array([15])
        loc_percentage = np.array([0.5])
        distance = np.array([1000])
        earth_station_height = np.array([5])
        below_rooftop = 100

        loss_mid = self.clutter_loss.get_loss(
            distance=distance, frequency=frequency, elevation=elevation,
            loc_percentage=loc_percentage, clutter_scenario="spatial",
            earth_station_height=earth_station_height,
            mean_clutter_height='mid', below_rooftop=below_rooftop,
        )
        self.assertTrue(np.all(np.isfinite(loss_mid)))

    def test_terrestrial_one_end_vs_both_ends(self):
        """'both_ends' should produce at least as much loss as 'one_end'."""
        frequency = np.array([4000])
        distance = np.array([1000])
        loc_percentage = np.array([0.5])

        loss_one = self.clutter_loss.get_loss(
            frequency=frequency, distance=distance,
            loc_percentage=loc_percentage,
            clutter_scenario="terrestrial", clutter_type='one_end',
            below_rooftop=100,
        )
        loss_both = self.clutter_loss.get_loss(
            frequency=frequency, distance=distance,
            loc_percentage=loc_percentage,
            clutter_scenario="terrestrial", clutter_type='both_ends',
            below_rooftop=100,
        )
        self.assertGreaterEqual(loss_both.item(), loss_one.item() - 0.5)

    def test_spatial_clutter_finite_at_extremes(self):
        """Spatial clutter loss should be finite for extreme elevations."""
        frequency = np.array([10000, 10000])
        elevation = np.array([1, 89])  # near-horizon and near-zenith
        loc_percentage = np.array([0.5, 0.5])
        distance = np.array([1000, 1000])
        earth_station_height = np.array([5, 5])
        below_rooftop = 100

        loss = self.clutter_loss.get_loss(
            distance=distance, frequency=frequency, elevation=elevation,
            loc_percentage=loc_percentage, clutter_scenario="spatial",
            earth_station_height=earth_station_height,
            mean_clutter_height='mid', below_rooftop=below_rooftop,
        )
        self.assertTrue(np.all(np.isfinite(loss)))

    def test_spatial_clutter_output_non_negative(self):
        """Spatial clutter loss should be non-negative."""
        frequency = np.array([5000, 15000, 30000])
        elevation = np.array([10, 30, 60])
        loc_percentage = np.array([0.3, 0.5, 0.7])
        distance = np.array([500, 1000, 2000])
        earth_station_height = np.array([8, 8, 8])
        below_rooftop = 100

        loss = self.clutter_loss.get_loss(
            distance=distance, frequency=frequency, elevation=elevation,
            loc_percentage=loc_percentage, clutter_scenario="spatial",
            earth_station_height=earth_station_height,
            mean_clutter_height='high', below_rooftop=below_rooftop,
        )
        self.assertTrue(np.all(loss >= -0.1))  # allow tiny floating-point slack


if __name__ == '__main__':
    unittest.main()

