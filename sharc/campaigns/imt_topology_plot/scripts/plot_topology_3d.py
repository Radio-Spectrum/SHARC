#!/usr/bin/env python3
"""
Script to plot IMT topology in 3D, showing base stations and UEs positions.
"""

import os
import sys
import yaml
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from sharc.topology.topology_factory import TopologyFactory
from sharc.station_factory import StationFactory


def load_params(yaml_file):
    """Load parameters from YAML file"""
    with open(yaml_file, "r") as f:
        yaml_data = yaml.safe_load(f)
    return yaml_data


def create_topology(yaml_data):
    """Create topology based on parameters"""
    topology_factory = TopologyFactory()
    topology = topology_factory.createTopology(yaml_data)
    topology.calculate_coordinates()
    return topology


def generate_ues(yaml_data, topology):
    """Generate UEs based on parameters and topology"""
    station_factory = StationFactory()
    ue_list = station_factory.generate_imt_ue(
        param=yaml_data["imt"],
        ue_param_ant=yaml_data["imt"]["ue"]["antenna"],
        topology=topology,
        random_number_gen=np.random.RandomState(yaml_data["general"]["seed"]),
    )
    return ue_list


def plot_topology_3d(topology, ue_list, output_dir):
    """Plot topology and UEs in 3D"""
    fig = plt.figure(figsize=(15, 15))
    ax = fig.add_subplot(111, projection="3d")

    # Plot base stations
    if topology.is_space_station:
        # For NTN topology, plot the space station
        ax.scatter(
            topology.space_station_x,
            topology.space_station_y,
            topology.space_station_z,
            c="red",
            marker="^",
            s=200,
            label="Space Station",
        )
    else:
        # For terrestrial topology, plot base stations
        ax.scatter(
            topology.x,
            topology.y,
            topology.height,
            c="red",
            marker="^",
            s=200,
            label="Base Stations",
        )

    # Plot UEs
    ax.scatter(
        ue_list.x,
        ue_list.y,
        ue_list.height,
        c="blue",
        marker="o",
        s=50,
        alpha=0.6,
        label="UEs",
    )

    # Add lines connecting BSs to their UEs
    for i in range(topology.num_base_stations):
        if topology.is_space_station:
            bs_x = topology.space_station_x
            bs_y = topology.space_station_y
            bs_z = topology.space_station_z
        else:
            bs_x = topology.x[i]
            bs_y = topology.y[i]
            bs_z = topology.height[i]

        # Get UEs for this BS
        ues_per_bs = int(len(ue_list.x) / topology.num_base_stations)
        start_idx = i * ues_per_bs
        end_idx = (i + 1) * ues_per_bs

        for j in range(start_idx, end_idx):
            ax.plot(
                [bs_x, ue_list.x[j]],
                [bs_y, ue_list.y[j]],
                [bs_z, ue_list.height[j]],
                "g-",
                alpha=0.1,
            )

    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")
    ax.set_title("IMT Network Topology")
    ax.legend()

    # Save plot
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, "topology_3d.png"))
    plt.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: python plot_topology_3d.py <yaml_file>")
        sys.exit(1)

    yaml_file = sys.argv[1]

    # Load parameters
    yaml_data = load_params(yaml_file)

    # Create output directory
    output_dir = os.path.join(os.path.dirname(yaml_file), "topology_plots")

    # Create topology
    topology = create_topology(yaml_data)

    # Generate UEs
    ue_list = generate_ues(yaml_data, topology)

    # Plot topology
    plot_topology_3d(topology, ue_list, output_dir)


if __name__ == "__main__":
    main()
