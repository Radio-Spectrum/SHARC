from sharc.topology.topology_single_base_station_spherical import (
    TopologySingleBaseStationSpherical,
)
from sharc.station_factory import StationFactory
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
import matplotlib.pyplot as plt
from sharc.station_manager import StationManager
import numpy as np


def test_basic_topology():
    # Test basic topology creation and coordinate calculation
    cell_radius = 1000  # 1km radius
    num_clusters = 2
    central_latitude = -15.7801  # Brasília
    central_longitude = -47.9292  # Brasília

    topology = TopologySingleBaseStationSpherical(
        cell_radius=cell_radius,
        num_clusters=num_clusters,
        central_latitude=central_latitude,
        central_longitude=central_longitude,
    )
    topology.calculate_coordinates()

    # Plot basic topology
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_subplot(111, projection="3d")
    topology.plot_3d(ax)
    plt.savefig("basic_topology.png")
    plt.close()


def test_topology_with_ues():
    # Test topology with UE generation
    cell_radius = 1000
    num_clusters = 2
    central_latitude = -15.7801
    central_longitude = -47.9292

    # Create topology
    topology = TopologySingleBaseStationSpherical(
        cell_radius=cell_radius,
        num_clusters=num_clusters,
        central_latitude=central_latitude,
        central_longitude=central_longitude,
    )
    topology.calculate_coordinates()

    # Configure IMT parameters
    param = ParametersImt()
    param.ue.k = 10  # UEs per base station
    param.ue.k_m = 1
    param.ue.indoor_percent = 0
    param.bandwidth = 100
    param.frequency = 26000
    param.ue.noise_figure = 7
    param.spectral_mask = "IMT-2020"
    param.spurious_emissions = -30

    # Configure UE antenna parameters
    ue_ant_param = ParametersAntennaImt()
    ue_ant_param.element_pattern = "FIXED"
    ue_ant_param.element_max_g = 5
    ue_ant_param.element_phi_3db = 90
    ue_ant_param.element_theta_3db = 90
    ue_ant_param.element_am = 25
    ue_ant_param.element_sla_v = 25
    ue_ant_param.n_rows = 4
    ue_ant_param.n_columns = 4
    ue_ant_param.element_horiz_spacing = 0.5
    ue_ant_param.element_vert_spacing = 0.5
    ue_ant_param.multiplication_factor = 12
    ue_ant_param.minimum_array_gain = -200
    ue_ant_param.normalization = False

    # Generate UEs
    station_factory = StationFactory()
    ue_list = station_factory.generate_imt_ue_outdoor(
        param=param,
        ue_param_ant=ue_ant_param,
        random_number_gen=np.random.RandomState(),
        topology=topology,
    )

    # Plot topology with UEs
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_subplot(111, projection="3d")
    topology.plot_3d(ax)
    topology.plot_ues_3d(ue_list, ax)
    plt.savefig("topology_with_ues.png")
    plt.close()

def plot_ues_3d(self, ue_list: StationManager, ax):
    """
    Adiciona os UEs ao plot 3D existente.

    Parameters
    ----------
    ue_list : StationManager
        Lista de UEs a serem plotados
    ax : matplotlib.axes.Axes
        Eixo onde plotar os UEs
    """
    # Extrai as coordenadas dos UEs
    ax.scatter(
        ue_list.x,
        ue_list.y,
        ue_list.height,
        color="blue",
        s=30,
        label="UEs",
        alpha=0.6,
    )


def test_kml_export():
    # Test KML export functionality
    cell_radius = 1000
    num_clusters = 2
    central_latitude = -15.7801
    central_longitude = -47.9292

    topology = TopologySingleBaseStationSpherical(
        cell_radius=cell_radius,
        num_clusters=num_clusters,
        central_latitude=central_latitude,
        central_longitude=central_longitude,
    )
    topology.calculate_coordinates()
    topology.export_to_kml("test_topology.kml")


def test_different_cluster_sizes():
    # Test topology with different cluster sizes
    central_latitude = -15.7801
    central_longitude = -47.9292
    cell_radius = 1000

    # Test with 1 cluster
    topology_1 = TopologySingleBaseStationSpherical(
        cell_radius=cell_radius,
        num_clusters=1,
        central_latitude=central_latitude,
        central_longitude=central_longitude,
    )
    topology_1.calculate_coordinates()

    # Test with 2 clusters
    topology_2 = TopologySingleBaseStationSpherical(
        cell_radius=cell_radius,
        num_clusters=2,
        central_latitude=central_latitude,
        central_longitude=central_longitude,
    )
    topology_2.calculate_coordinates()

    # Plot both topologies
    fig = plt.figure(figsize=(20, 10))

    # Plot first topology
    ax1 = fig.add_subplot(121, projection="3d")
    topology_1.plot_3d(ax1)
    ax1.set_title("Single Cluster Topology")

    # Plot second topology
    ax2 = fig.add_subplot(122, projection="3d")
    topology_2.plot_3d(ax2)
    ax2.set_title("Two Cluster Topology")

    plt.savefig("different_clusters.png")
    plt.close()


if __name__ == "__main__":
    print("Running topology tests...")

    print("Testing basic topology...")
    test_basic_topology()

    print("Testing topology with UEs...")
    test_topology_with_ues()

    print("Testing KML export...")
    test_kml_export()

    print("Testing different cluster sizes...")
    test_different_cluster_sizes()

    print("All tests completed!")
