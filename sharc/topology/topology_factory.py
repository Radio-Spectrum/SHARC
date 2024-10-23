# -*- coding: utf-8 -*-
"""
Created on Thu Mar 23 16:41:25 2017

@author: edgar
"""
import sys

from sharc.topology.topology import Topology
from sharc.topology.topology_macrocell import TopologyMacrocell
from sharc.topology.topology_hotspot import TopologyHotspot
from sharc.topology.topology_indoor import TopologyIndoor
from sharc.topology.topology_ntn import TopologyNTN
from sharc.topology.topology_single_base_station import TopologySingleBaseStation
from sharc.parameters.parameters import Parameters

class TopologyFactory(object):
    
    @staticmethod
    def createTopology(parameters: Parameters) -> Topology:
        if parameters.imt.topology == "SINGLE_BS":
            return TopologySingleBaseStation(parameters.imt.intersite_distance*2/3, parameters.imt.num_clusters)
        elif parameters.imt.topology == "MACROCELL":
            return TopologyMacrocell(parameters.imt.intersite_distance, parameters.imt.num_clusters)
        elif parameters.imt.topology == "HOTSPOT":
            return TopologyHotspot(parameters.hotspot, parameters.imt.intersite_distance, parameters.imt.num_clusters)
        elif parameters.imt.topology == "INDOOR":
            return TopologyIndoor(parameters.indoor)
        elif parameters.imt.topology == "NTN":
            return TopologyNTN(parameters.ntn.intersite_distance, parameters.ntn.cell_radius, parameters.ntn.bs_height,
                               parameters.ntn.bs_azimuth, parameters.ntn.bs_elevation,parameters.ntn.num_sectors)
        else:
            sys.stderr.write("ERROR\nInvalid topology: " + parameters.imt.topology)
            sys.exit(1)            
