from sharc.topology.topology_ntn import TopologyNTN
import numpy as np
import math
import unittest

class TopologyNTNTest(unittest.TestCase):

    def setUp(self):
        print('setUp')
        self.bs_height = 1000e3  # meters
        self.bs_azimuth = 45  # degrees
        self.bs_elevation = 45  # degrees
        self.beamwidth = 10
        self.cell_radius = self.bs_height * math.tan(np.radians(self.beamwidth)) /math.cos(self.bs_elevation)
        self.intersite_distance = self.cell_radius * np.sqrt(3)  # meters

    def tearDown(self):
        print('tearDown\n')
    
    def test_calculate_coordinates_1sector(self):
        #testando os atributos x,y,z,elevation e azimuth, considerando o num_sectors=1
        ntn_topology_1 = TopologyNTN(
        self.intersite_distance, self.cell_radius, self.bs_height, self.bs_azimuth, self.bs_elevation, num_sectors=1)
        ntn_topology_1.calculate_coordinates()  

        np.testing.assert_array_equal(ntn_topology_1.azimuth,[-135])
        np.testing.assert_array_equal(ntn_topology_1.elevation,[-45])
        np.testing.assert_array_equal(ntn_topology_1.x,[0])
        np.testing.assert_array_equal(ntn_topology_1.y,[0])
        np.testing.assert_array_equal(ntn_topology_1.z,[0])

    def test_calculate_coordianates_7sectors(self):
        #testando os atributos x,y,z,elevation e azimuth, considerando o num_sectors=7
        ntn_topology_7 = TopologyNTN(
        self.intersite_distance, self.cell_radius, self.bs_height, self.bs_azimuth, self.bs_elevation, num_sectors=7)
        ntn_topology_7.calculate_coordinates()  

        np.testing.assert_array_equal(ntn_topology_7.azimuth,[0])
        np.testing.assert_array_equal(ntn_topology_7.elevation,[0])
        np.testing.assert_array_equal(ntn_topology_7.x,[0])
        np.testing.assert_array_equal(ntn_topology_7.y,[0])
        np.testing.assert_array_equal(ntn_topology_7.z,[0])

    def test_calculate_coordinates_19sectors(self):
        #testando os atributos x,y,z,elevation e azimuth, considerando o num_sectors=19
        ntn_topology_19 = TopologyNTN(
        self.intersite_distance, self.cell_radius, self.bs_height, self.bs_azimuth, self.bs_elevation, num_sectors=19)
        ntn_topology_19.calculate_coordinates()  

        np.testing.assert_array_equal(ntn_topology_19.azimuth,[0])
        np.testing.assert_array_equal(ntn_topology_19.elevation,[0])
        np.testing.assert_array_equal(ntn_topology_19.x,[0])
        np.testing.assert_array_equal(ntn_topology_19.y,[0])
        np.testing.assert_array_equal(ntn_topology_19.z,[0])

       
if __name__ == 'main':
    unittest.main()