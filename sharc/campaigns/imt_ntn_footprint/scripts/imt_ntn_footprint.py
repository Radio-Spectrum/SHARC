import math
import numpy as np
import matplotlib.pyplot as plt

from sharc.topology.topology_ntn import TopologyNTN
from sharc.antenna.antenna_s1528 import AntennaS1528, AntennaS1528Leo
from sharc.station_manager import StationManager
from sharc.support.enumerations import StationType
from sharc.station_factory import StationFactory
from sharc.parameters.parameters_imt import ParametersImt
from sharc.parameters.parameters_mss_ss import ParametersMssSs
from sharc.parameters.parameters_antenna_imt import ParametersAntennaImt
from sharc.parameters.parameters_antenna_s1528 import ParametersAntennaS1528
from sharc.mask.spectral_mask_imt import SpectralMaskImt


def generate_mss_ss(param_mss: ParametersMssSs):
    # We borrow the TopologyNTN geometry as it's the same for MSS_SS
    ntn_topology = TopologyNTN(param_mss.intersite_distance,
                               param_mss.cell_radius,
                               param_mss.altitude,
                               param_mss.azimuth,
                               param_mss.elevation,
                               param_mss.num_sectors)

    ntn_topology.calculate_coordinates()
    
    num_bs = ntn_topology.num_base_stations
    mss_ss = StationManager(n=num_bs)
    mss_ss.station_type = StationType.MSS_SS
    mss_ss.x = ntn_topology.space_station_x * np.ones(num_bs) + param_mss.x
    mss_ss.y = ntn_topology.space_station_y * np.ones(num_bs) + param_mss.y
    mss_ss.height = ntn_topology.space_station_z*np.ones(num_bs)
    mss_ss.elevation = ntn_topology.elevation
    mss_ss.is_space_station = True
    mss_ss.azimuth = ntn_topology.azimuth
    mss_ss.active = np.ones(num_bs, dtype=int)
    mss_ss.tx_power = param_mss.eipr_density + 10*np.log10(param_mss.bandwidth * 10^6)
    mss_ss.antenna = np.empty(num_bs, dtype=AntennaS1528Leo)

    for i in range(num_bs):
        if param_mss.antenna_pattern == "ITU-R-S.1528-LEO":
            mss_ss.antenna[i] = AntennaS1528Leo(param_mss.antenna_param)
        elif param_mss.antenna_pattern == "ITU-R-S.1528-Section1.2":
            mss_ss.antenna[i] = AntennaS1528(param_mss.antenna_param)

    return mss_ss


if __name__ == "__main__":
    
    ## Input parameters for MSS_SS
    param_mss = ParametersMssSs()
    param_mss.altitude = 1200000 # meters
    param_mss.azimuth = 0
    param_mss.elevation = 80 # degrees
    param_mss.cell_radius = 45000 # meters
    param_mss.num_sectors = 19
     # Parameters used for the S.1528 antenna
    param_mss.antenna_pattern = "ITU-R-S.1528-LEO"
    param_mss.antenna_3_dB_bw = 4.4127
    param_mss.antenna_gain = 30 # dBi
    param_mss.antenna_param.load_from_paramters(param_mss)
    beam_idx = 10 # beam index used for gain analysis
    
    seed = 100
    rng = np.random.RandomState(seed)
    beam_radius = param_mss.altitude * math.tan(np.radians(param_mss.antenna_3_dB_bw/2)) / math.cos(np.radians(param_mss.elevation))
    print(f"Theoretical beam radius at nadir point (km) = {beam_radius/1000}")

    # Parameters used for IMT-NTN and UE distribution
    param_imt = ParametersImt()
    param_imt.topology = "NTN"
    param_imt.azimuth_range = (-180, 180)
    param_imt.bandwidth = 10  # MHz 
    param_imt.frequency = 2100  # MHz
    param_imt.spurious_emissions = -13  # dB
    param_imt.ue_distribution_azimuth = "UNIFORM"
    param_imt.ue_k = 1000

    ntn_topology = TopologyNTN(param_mss.intersite_distance,
                               param_mss.cell_radius,
                               param_mss.altitude,
                               param_mss.azimuth,
                               param_mss.elevation,
                               param_mss.num_sectors)

    ntn_topology.calculate_coordinates()
    param_ue_ant = ParametersAntennaImt()
    ntn_ue = StationFactory.generate_imt_ue_outdoor(
        param_imt, param_ue_ant, rng, ntn_topology)
    
    ntn_ue.active = np.ones(ntn_ue.num_stations, dtype=bool)
    ntn_bs = generate_mss_ss(param_mss)
    phi, theta = ntn_bs.get_pointing_vector_to(ntn_ue)
    station_1_active = np.where(ntn_bs.active)[0]
    station_2_active = np.where(ntn_ue.active)[0]
    beams_idx = np.zeros(len(station_2_active), dtype=int)
    off_axis_angle = ntn_bs.get_off_axis_angle(ntn_ue)
    gains = np.zeros(phi.shape)
    for k in station_1_active:
        gains[k, station_2_active] = \
            ntn_bs.antenna[k].calculate_gain(
                off_axis_angle_vec=off_axis_angle[k, station_2_active], theta_vec=theta[k, station_2_active])

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.set_xlim([-500, 500])
    ax.set_ylim([-500, 500])
    ntn_topology.plot_3d(ax, False)  # Plot the 3D topology
    im = ax.scatter(xs=ntn_ue.x/1000, ys=ntn_ue.y/1000, c=gains[beam_idx], cmap='jet')
    fig.colorbar(im)

    # Plot 3dB contour
    # fig = plt.figure()
    # ax = fig.add_subplot(111)
    # ntn_topology.plot(ax)
    # gain_3db_cont = np.where((gains[beam_idx] > param_mss.antenna_gain - 3.05) & 
    #                          (gains[beam_idx] < param_mss.antenna_gain - 2.95))[0]
    # ax.scatter(x=ntn_ue.x[gain_3db_cont]/1000, y=ntn_ue.y[gain_3db_cont]/1000)
    
    plt.show()
    exit()
