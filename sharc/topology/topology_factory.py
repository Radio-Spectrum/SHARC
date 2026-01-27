# -*- coding: utf-8 -*-
"""
Created on Thu Mar 23 16:41:25 2017

@author: edgar
"""
import sys

from sharc.topology.topology import Topology
from sharc.topology.topology_macrocell import TopologyMacrocell
from sharc.topology.topology_imt_mss_dc import TopologyImtMssDc
from sharc.topology.topology_hotspot import TopologyHotspot
from sharc.topology.topology_indoor import TopologyIndoor
from sharc.topology.topology_ntn import TopologyNTN
from sharc.topology.topology_single_base_station import TopologySingleBaseStation
from sharc.topology.topology_spherical_sampling_from_grid import TopologySamplingFromSphericalGrid
from sharc.parameters.parameters import Parameters
from sharc.support.sharc_geom import CoordinateSystem


class TopologyFactory(object):
    """Factory class for creating topology objects based on parameters."""

    @staticmethod
    def createTopology(parameters: Parameters,
                       coordinate_system: CoordinateSystem) -> Topology:
        """Create and return a topology object based on the provided parameters."""
        if parameters.imt.topology.type == "SINGLE_BS":
            return TopologySingleBaseStation(
                parameters.imt.topology.single_bs.cell_radius,
                parameters.imt.topology.single_bs.num_clusters,
                parameters.imt.topology.single_bs.azimuth
            )
        elif parameters.imt.topology.type == "MACROCELL":
            return TopologyMacrocell(
                parameters.imt.topology.macrocell.intersite_distance,
                parameters.imt.topology.macrocell.num_clusters
            )
        elif parameters.imt.topology.type == "HOTSPOT":
            return TopologyHotspot(
                parameters.imt.topology.hotspot,
                parameters.imt.topology.hotspot.intersite_distance,
                parameters.imt.topology.hotspot.num_clusters
            )
        elif parameters.imt.topology.type == "INDOOR":
            return TopologyIndoor(parameters.imt.topology.indoor)
        elif parameters.imt.topology.type == "NTN":
            return TopologyNTN(
                parameters.imt.topology.ntn.intersite_distance,
                parameters.imt.topology.ntn.cell_radius,
                parameters.imt.topology.ntn.bs_height,
                parameters.imt.topology.ntn.bs_azimuth,
                parameters.imt.topology.ntn.bs_elevation,
                parameters.imt.topology.ntn.num_sectors,
            )
        elif parameters.imt.topology.type == "MSS_DC":
            return TopologyImtMssDc(
                parameters.imt.topology.mss_dc,
                coordinate_system
            )
        elif parameters.imt.topology.type == "SAMPLING_FROM_SPHERICAL_GRID":
            return TopologySamplingFromSphericalGrid(
                parameters.imt.topology.sampling_from_spherical_grid.max_ue_distance,
                parameters.imt.topology.sampling_from_spherical_grid.num_bs,
                (coordinate_system.ref_lat, coordinate_system.ref_long, coordinate_system.ref_alt),
                parameters.imt.topology.sampling_from_spherical_grid.grid,
            )
        else:
            sys.stderr.write(
                "ERROR\nInvalid topology: " +
                parameters.imt.topology,
            )
            sys.exit(1)
