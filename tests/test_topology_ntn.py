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
        self.cell_radius = self.bs_height * self.math.tan(np.radians(self.beamwidth)) /math.cos(self.bs_elevation)
        self.intersite_distance = self.cell_radius * np.sqrt(3)  # meters

    def tearDown(self):
        print('tearDown\n')
    
    def test_calculate_coordinates_function(self):
        #testando os atributos x,y,z,elevation e azimuth, considerando o num_sectors=1
        ntn_topology_1 = TopologyNTN(
        self.intersite_distance, self.cell_radius, self.bs_height, self.bs_azimuth, self.bs_elevation, num_sectors=1)
        ntn_topology_1.calculate_coordinates()  

        self.assertEqual(0,ntn_topology_1.azimuth)
        self.assertEqual(0,ntn_topology_1.elevation)
        self.assertEqual(0,ntn_topology_1.x)
        self.assertEqual(0,ntn_topology_1.y)
        self.assertEqual(0,ntn_topology_1.z)

        #testando os atributos x,y,z,elevation e azimuth, considerando o num_sectors=7
        ntn_topology_7 = TopologyNTN(
        self.intersite_distance, self.cell_radius, self.bs_height, self.bs_azimuth, self.bs_elevation, num_sectors=7)
        ntn_topology_7.calculate_coordinates()  

        self.assertEqual(0,ntn_topology_7.azimuth)
        self.assertEqual(0,ntn_topology_7.elevation)
        self.assertEqual(0,ntn_topology_7.x)
        self.assertEqual(0,ntn_topology_7.y)
        self.assertEqual(0,ntn_topology_7.z)

        #testando os atributos x,y,z,elevation e azimuth, considerando o num_sectors=19
        ntn_topology_19 = TopologyNTN(
        self.intersite_distance, self.cell_radius, self.bs_height, self.bs_azimuth, self.bs_elevation, num_sectors=19)
        ntn_topology_19.calculate_coordinates()  

        self.assertEqual(0,ntn_topology_19.azimuth)
        self.assertEqual(0,ntn_topology_19.elevation)
        self.assertEqual(0,ntn_topology_19.x)
        self.assertEqual(0,ntn_topology_19.y)
        self.assertEqual(0,ntn_topology_19.z)

       
if __name__ == 'main':
    unittest.main()