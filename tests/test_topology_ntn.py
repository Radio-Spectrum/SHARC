import unittest
import numpy as np

from sharc.topology.topology_ntn import TopologyNTN

class TopologyNTNTest(unittest.TestCase):
    def setUp(self):
        self.bs_height = 1000e3 
        self.bs_azimuth = 45 
        self.bs_elevation = 45
        self.cell_radius = 1000
        self.intersite_distance = self.cell_radius * np.sqrt(3)
        self.num_sectors = 7
        
        self.topology = TopologyNTN(self.intersite_distance, self.cell_radius, self.bs_height,
                                    self.bs_azimuth, self.bs_elevation, self.num_sectors)
    
    def test_invalid_num_sectors(self):
        with self.assertRaises(ValueError):
            TopologyNTN(self.intersite_distance, self.cell_radius, self.bs_height,
                        self.bs_azimuth, self.bs_elevation, num_sectors=5)

    def test_valid_one_sector(self):
        self.topology.num_sectors = 1
        self.topology.calculate_coordinates()
        self.assertEqual(len(self.topology.x), 1)
        self.assertEqual(len(self.topology.y), 1)
    
    def test_valid_seven_sectors(self):
        self.topology.num_sectors = 7
        self.topology.calculate_coordinates()
        self.assertEqual(len(self.topology.x), 7)
        self.assertEqual(len(self.topology.y), 7)

    def test_valid_nineteen_sectors(self):
        self.topology.num_sectors = 19
        self.topology.calculate_coordinates()
        self.assertEqual(len(self.topology.x), 19)
        self.assertEqual(len(self.topology.y), 19)

    def test_rotation(self):
        self.topology.num_sectors = 1
        self.topology.calculate_coordinates()

        x = np.array([0])
        y = np.array([0])

        theta = np.radians(30)
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)
        x_rotated = x * cos_theta - y * sin_theta
        y_rotated = x * sin_theta + y * cos_theta
        
        np.testing.assert_array_almost_equal(x_rotated, self.topology.x)
        np.testing.assert_array_almost_equal(y_rotated, self.topology.y)
    
    def test_azimuth_and_elevation_calculation(self):
        expected_azimuth = np.arctan2(self.topology.y_rotated - self.topology.space_station_y, 
                                      self.topology.x_rotated - self.topology.space_station_x) * 180 / np.pi
        expected_distance_xy = np.sqrt((self.topology.x_rotated - self.topology.space_station_x)**2 + 
                                       (self.topology.y_rotated - self.topology.space_station_y)**2)
        expected_elevation = np.arctan2(self.topology.z - self.topology.space_station_z, expected_distance_xy) * 180 / np.pi
        
        np.testing.assert_array_almost_equal(self.topology.azimuth, expected_azimuth)
        np.testing.assert_array_almost_equal(self.topology.elevation, expected_elevation)

if __name__ == '__main__':
    unittest.main()