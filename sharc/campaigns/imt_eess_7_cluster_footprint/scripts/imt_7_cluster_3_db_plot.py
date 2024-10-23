# -*- coding: utf-8 -*-

"""
@author: Thiago Ferreira

"""

import matplotlib.pyplot as plt
import math
import numpy as np
import sharc.parameters.constants as constants
from mpl_toolkits.mplot3d import Axes3D, art3d
from matplotlib.collections import PolyCollection

from sharc.topology.topology import Topology
from sharc.parameters.parameters_imt import ParametersImt as param_imt
from sharc.parameters.parameters_eess_passive import ParametersEessPassive as param_eess
from sharc.parameters.parameters_antenna_imt import ParametersAntennaImt
from sharc.parameters.parameters_antenna_s1528 import ParametersAntennaS1528 as param_s1528
from sharc.mask.spectral_mask_imt import SpectralMaskImt as imt_mask
from sharc.antenna.antenna_s1528 import AntennaS1528, AntennaS1528Leo
from sharc.station_manager import StationManager as station_manager
from sharc.support.enumerations import StationType as station_type
from sharc.station_factory import StationFactory as station_factory

""" 

    Class topology macrocell is defined in sharc/topology, and was estabilished an imt macrocell structure that represents the 
SHARC simulation, validation and benchmarking, the objetive of this class is to implement the multi-cluster study for EESS
footprint satellite and the respective gain in different points of terrestrial macrocell structure.

"""

class TopologyMacrocell:
    AZIMUTH = [60, 180, 300]
    ALLOWED_NUM_CLUSTERS = [1, 7]

    def __init__(self, intersite_distance: float, num_clusters: int):
        if num_clusters not in TopologyMacrocell.ALLOWED_NUM_CLUSTERS:
            raise ValueError(f"Invalid number of clusters ({num_clusters})")

        cell_radius = intersite_distance * 2 / 3
        self.intersite_distance = intersite_distance
        self.num_clusters = num_clusters
        self.static_base_stations = False

        self.x = np.empty(0)
        self.y = np.empty(0)
        self.z = np.empty(0)  # Add z-coordinates
        self.azimuth = np.empty(0)
        self.num_base_stations = 0

    def calculate_coordinates(self):
        if not self.static_base_stations:
            self.static_base_stations = True

            d = self.intersite_distance
            h = (d / 3) * math.sqrt(3) / 2

            x_central = np.array([0, d, d / 2, -d / 2, -d, -d / 2,
                                 d / 2, 2 * d, 3 * d / 2, d, 0, -d,
                                 -3 * d / 2, -2 * d, -3 * d / 2, -d, 0, d, 3 * d / 2])
            y_central = np.array([0, 0, 3 * h, 3 * h, 0, -3 * h,
                                 -3 * h, 0, 3 * h, 6 * h, 6 * h, 6 * h,
                                 3 * h, 0, -3 * h, -6 * h, -6 * h, -6 * h, -3 * h])
            z_central = np.zeros_like(x_central)  # Initialize z-coordinates to 0
            self.x = np.copy(x_central)
            self.y = np.copy(y_central)
            self.z = np.copy(z_central)  # Set z-coordinates
            

            if self.num_clusters == 7:
                x_shift = np.array([7 * d / 2, -d / 2, -4 * d, -7 * d / 2, d / 2, 4 * d])
                y_shift = np.array([9 * h, 15 * h, 6 * h, -9 * h, -15 * h, -6 * h])
                z_shift = np.zeros_like(x_shift)  # Initialize z-shifts to 0
                for xs, ys, zs in zip(x_shift, y_shift, z_shift):
                    self.x = np.concatenate((self.x, x_central + xs))
                    self.y = np.concatenate((self.y, y_central + ys))
                    self.z = np.concatenate((self.z, z_central + zs))

            self.x = np.repeat(self.x, 3)
            self.y = np.repeat(self.y, 3)
            self.z = np.repeat(self.z, 3)  # Repeat z-coordinates
            self.azimuth = np.tile(self.AZIMUTH, 19 * self.num_clusters)
            self.num_base_stations = len(self.x)

    def plot(self, ax: Axes3D):
        r = self.intersite_distance / 3  # Radius of the hexagon
        signal_strengths = []  # To store signal strength values for color mapping
        hexagons = []
        
        # Calculation of the SAR (Synthetic Aperture Radar) parameters
        self.phi_3dB = 0.53 * 180 # Using the cut frequency phi declared in IMT-2020 / EESS-Active Sharing Study - 10Ghz
        self.theta_3dB = 1.13 * 180 # Using the cut frequency theta declared in IMT-2020 / EESS-Active Sharing Study - 10Ghz
        self.earth_radius = constants.EARTH_RADIUS/1000 
        i = param_eess.nadir_angle # Supposing that i angle is equal to theta(i) and is equivalent to off-nadir angle (in degrees)
        
        
        # Ellipse scaling factors
        a = (self.theta_3dB * self.earth_radius) / (2 * math.cos(i))  # Semi-major axis (east-west scaling)
        b =  (self.phi_3dB * self.earth_radius) / 2 # Semi-minor axis (north-south scaling)
        
        for x, y, z, az in zip(self.x, self.y, self.z, self.azimuth):
            se = [np.array([x, y, z])]
            angle = az - 60  # Start angle for hexagon
            for _ in range(6):
                se.append([se[-1][0] + r * math.cos(math.radians(angle)),
                           se[-1][1] + r * math.sin(math.radians(angle)),
                           se[-1][2]])
                angle += 60
            se = np.array(se)
            se = np.vstack([se, se[0]])
            hexagons.append(se)

            # Scale x and y by the ellipse factors
            scaled_x = x / a
            scaled_y = y / b
            

            # Distance for elliptical signal model
            altitude_kilometers = param_eess.altitude/1000
            satellite_position = np.array([0, 0, altitude_kilometers])  # Satellite at (0, 0, 1000)
            base_station_position = np.array([scaled_x, scaled_y, z])
            distance = np.linalg.norm(satellite_position - base_station_position)
            
            # Cosine law to account for the angle between the normal vector and the vector to the base station
            normal_vector = np.array([0, 0, 1])  # Normal vector pointing upwards from satellite
            vector_to_base_station = (base_station_position - satellite_position) / distance
            cosine_angle = np.dot(normal_vector, vector_to_base_station)  # Projection onto normal
                        
            signal_strength = (param_eess.antenna_gain / (distance)**2 ) * param_eess.antenna_efficiency # Issues in implementation of the signal strength related to propagation and atenuation of satellite beamforming
            signal_strengths.append(signal_strength) 
        
        signal_strengths = np.array(signal_strengths)
        signal_strengths_normalized = (signal_strengths - np.min(signal_strengths)) / (np.max(signal_strengths) - np.min(signal_strengths))
        
        hex_collection = art3d.Poly3DCollection(hexagons, facecolors=plt.cm.jet(signal_strengths_normalized), edgecolors='k', alpha=0.7)
        ax.add_collection3d(hex_collection)
        
        # Plot satellite and normal vector
        ax.quiver(0, 0, 0, 0, 0, satellite_position[2], color='k', label=f'Height = {satellite_position[2]} Km', arrow_length_ratio=0, pivot='tail')
        ax.scatter(satellite_position[0], satellite_position[1], satellite_position[2], c='k', marker='^', s=55, label='Satellite')
        
        # Add color bar for signal strength
        m = plt.cm.ScalarMappable(cmap='jet')
        m.set_array(signal_strengths_normalized)
        plt.colorbar(m, ax=ax, shrink=0.5, aspect=5)
        
        handles, labels = ax.get_legend_handles_labels()
        unique_labels = dict(zip(labels, handles))
        ax.legend(unique_labels.values(), unique_labels.keys())

if __name__ == '__main__':
    intersite_distance = 500
    num_clusters = 7
    topology = TopologyMacrocell(intersite_distance, num_clusters)
    topology.calculate_coordinates()

    fig = plt.figure(figsize=(8, 8), facecolor='w', edgecolor='k')
    ax = fig.add_subplot(111, projection='3d')

    topology.plot(ax)

    ax.set_title("EESS Topology - 7 Cluster (19 Sectors)")
    ax.set_xlabel("x-coordinate [km]")
    ax.set_ylabel("y-coordinate [km]")
    ax.set_zlabel("z-coordinate [km]")
    ax.set_zlim(0, 1000)
    plt.tight_layout()
    plt.show()
