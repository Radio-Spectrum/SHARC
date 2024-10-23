# -*- coding: utf-8 -*-
"""
Created on Tue Feb 14 12:51:22 2017

@author: edgar
"""

from sharc.topology.topology import Topology
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import math
import numpy as np

class TopologyMacrocell(Topology):
    """
    Generates the coordinates of the sites based on the macrocell network
    topology in 3D.
    """

    # possible values for base station azimuth [degrees]
    AZIMUTH = [60, 180, 300]

    ALLOWED_NUM_CLUSTERS = [1, 7]

    def __init__(self, intersite_distance: float, num_clusters: int):
        """
        Constructor method that sets the parameters and already calls the
        calculation methods.

        Parameters
        ----------
            intersite_distance : Distance between two sites
            num_clusters : Number of clusters, should be 1 or 7
        """
        if num_clusters not in TopologyMacrocell.ALLOWED_NUM_CLUSTERS:
            error_message = "invalid number of clusters ({})".format(num_clusters)
            raise ValueError(error_message)

        cell_radius = intersite_distance*2/3
        super().__init__(intersite_distance, cell_radius)
        self.num_clusters = num_clusters

        self.site_x = np.empty(0)
        self.site_y = np.empty(0)
        self.site_z = np.empty(0)  # Add z-coordinates

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """
        Calculates the coordinates of the stations according to the inter-site
        distance parameter. This method is invoked in all snapshots but it can
        be called only once for the macro cell topology. So we set
        static_base_stations to True to avoid unnecessary calculations.
        """
        if not self.static_base_stations:
            self.static_base_stations = True

            d = self.intersite_distance
            h = (d/3)*math.sqrt(3)/2

            # these are the coordinates of the central cluster
            x_central = np.array([0, d, d/2, -d/2, -d, -d/2,
                             d/2, 2*d, 3*d/2, d, 0, -d,
                             -3*d/2, -2*d, -3*d/2, -d, 0, d, 3*d/2])
            y_central = np.array([0, 0, 3*h, 3*h, 0, -3*h,
                             -3*h, 0, 3*h, 6*h, 6*h, 6*h,
                             3*h, 0, -3*h, -6*h, -6*h, -6*h, -3*h])
            z_central = np.zeros_like(x_central)  # Initialize z-coordinates to 0
            self.x = np.copy(x_central)
            self.y = np.copy(y_central)
            self.z = np.copy(z_central)  # Set z-coordinates

            # other clusters are calculated by shifting the central cluster
            if self.num_clusters == 7:
                x_shift = np.array([7*d/2, -d/2, -4*d, -7*d/2, d/2, 4*d])
                y_shift = np.array([9*h, 15*h, 6*h, -9*h, -15*h, -6*h])
                z_shift = np.zeros_like(x_shift)  # Initialize z-shifts to 0
                for xs, ys, zs in zip(x_shift, y_shift, z_shift):
                    self.x = np.concatenate((self.x, x_central + xs))
                    self.y = np.concatenate((self.y, y_central + ys))
                    self.z = np.concatenate((self.z, z_central + zs))

            self.x = np.repeat(self.x, 3)
            self.y = np.repeat(self.y, 3)
            self.z = np.repeat(self.z, 3)  # Repeat z-coordinates
            self.azimuth = np.tile(self.AZIMUTH, 19*self.num_clusters)

            # In the end, we have to update the number of base stations
            self.num_base_stations = len(self.x)

            self.indoor = np.zeros(self.num_base_stations, dtype = bool)

    def plot(self, ax: Axes3D):
        # create the hexagons
        r = self.intersite_distance/3
        for x, y, z, az in zip(self.x, self.y, self.z, self.azimuth):
            se = [np.array([x, y, z])]
            angle = int(az - 60)
            for a in range(6):
                se.append([se[-1][0] + r*math.cos(math.radians(angle)), se[-1][1] + r*math.sin(math.radians(angle)), se[-1][2]])
                angle += 60
            se = np.array(se)
            # Close the hexagon
            se = np.vstack([se, se[0]])
            ax.plot3D(se[:,0], se[:,1], se[:,2], 'k')  # Plot the edges of the hexagon

        # macro cell base stations
        ax.scatter(self.x, self.y, self.z, color='k', edgecolor="k", linewidth=4, label="Macro cell")

if __name__ == '__main__':
    intersite_distance = 500
    num_clusters = 7
    topology = TopologyMacrocell(intersite_distance, num_clusters)
    topology.calculate_coordinates()

    fig = plt.figure(figsize=(8,8), facecolor='w', edgecolor='k')  # create a figure object
    ax = fig.add_subplot(111, projection='3d')  # create a 3D axes object

    topology.plot(ax)

    ax.set_title("NTN Topology - 7 Cluster (19 Sectors)")
    ax.set_xlabel("x-coordinate [km]")
    ax.set_ylabel("y-coordinate [km]")
    ax.set_zlabel("z-coordinate [km]")
    ax.set_zlim(0, 1000)
    plt.tight_layout()
    plt.show()
