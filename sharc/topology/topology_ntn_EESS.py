from sharc.topology.topology import Topology
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import math
import numpy as np

class TopologyMacrocell(Topology):
    # Possible values for base station azimuth [degrees]
    AZIMUTH = [60, 180, 300]

    ALLOWED_NUM_CLUSTERS = [1, 7]

    def __init__(self, intersite_distance: float, num_clusters: int):
        if num_clusters not in TopologyMacrocell.ALLOWED_NUM_CLUSTERS:
            error_message = "invalid number of clusters ({})".format(num_clusters)
            raise ValueError(error_message)

        cell_radius = intersite_distance * 2 / 3
        super().__init__(intersite_distance, cell_radius)
        self.num_clusters = num_clusters

        self.site_x = np.empty(0)
        self.site_y = np.empty(0)
        self.site_z = np.empty(0)  # Add z-coordinates

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        if not self.static_base_stations:
            self.static_base_stations = True

            d = self.intersite_distance
            h = (d / 3) * math.sqrt(3) / 2

            # These are the coordinates of the central cluster
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

            # Other clusters are calculated by shifting the central cluster
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

            # In the end, we have to update the number of base stations
            self.num_base_stations = len(self.x)
            self.indoor = np.zeros(self.num_base_stations, dtype=bool)

    def plot(self, ax: Axes3D):
        r = self.intersite_distance / 3  # Radius of the hexagon

        for x, y, z, az in zip(self.x, self.y, self.z, self.azimuth):
            # Calculate hexagon vertices (maintaining original hexagon shape from the second code)
            se = [np.array([x, y, z])]
            angle = az - 60  # Start angle for hexagon
            for _ in range(6):
                se.append([se[-1][0] + r * math.cos(math.radians(angle)),
                           se[-1][1] + r * math.sin(math.radians(angle)),
                           se[-1][2]])
                angle += 60
            se = np.array(se)
            # Close the hexagon
            se = np.vstack([se, se[0]])
            ax.plot3D(se[:, 0], se[:, 1], se[:, 2], 'k')  # Plot the hexagon edges

            # Calculate the center of the hexagon
            center_x = np.mean(se[:, 0])
            center_y = np.mean(se[:, 1])
            center_z = np.mean(se[:, 2])
            
            # Plot the center point
            ax.scatter(center_x, center_y, center_z, c='black', marker='v', s=15, label='Anchor Points')

        # Calculate the center of the entire plot
        center_x = np.mean(self.x)
        center_y = np.mean(self.y)
        center_z = np.mean(self.z)
        
        # Define the normal vector for the satellite
        vector_length = 1000
        normal_vector = np.array([0, 0, vector_length])
        
        # Plot the vector representing the satellite
        ax.quiver(center_x, center_y, center_z, normal_vector[0], normal_vector[1], normal_vector[2],
                  color='b', label='Height = 1000 km', arrow_length_ratio=0, pivot='tail')
                  
        ax.scatter(0, 0, 1000, c ='r', marker = '^', s = 50, label = 'Satellite')

        # Add a legend, avoiding duplicate entries
        handles, labels = ax.get_legend_handles_labels()
        unique_labels = dict(zip(labels, handles))
        ax.legend(unique_labels.values(), unique_labels.keys())

if __name__ == '__main__':
    intersite_distance = 500
    num_clusters = 7
    topology = TopologyMacrocell(intersite_distance, num_clusters)
    topology.calculate_coordinates()

    fig = plt.figure(figsize=(8, 8), facecolor='w', edgecolor='k')  # Create a figure object
    ax = fig.add_subplot(111, projection='3d')  # Create a 3D axes object

    topology.plot(ax)

    ax.set_title("NTN Topology - 7 Cluster (19 Sectors)")
    ax.set_xlabel("x-coordinate [km]")
    ax.set_ylabel("y-coordinate [km]")
    ax.set_zlabel("z-coordinate [km]")
    ax.set_zlim(0, 1000)
    plt.tight_layout()
    plt.show()
