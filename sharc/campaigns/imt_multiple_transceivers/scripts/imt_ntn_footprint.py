import numpy as np
import matplotlib.pyplot as plt

from sharc.topology.topology_ntn import TopologyNTN
from sharc.station_factory import StationFactory
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.parameters.parameters_mss_ss import ParametersMssSs
from sharc.antenna.antenna_multiple_transceiver import AntennaMultipleTransceiver
from sharc.antenna.antenna_s1528 import AntennaS1528
from sharc.campaigns.imt_multiple_transceivers.scripts.calculate_gain_multiple_transceivers import calculate_gain_multiple_transceivers

if __name__ == "__main__":
    # Input parameters for MSS_SS
    param_mss = ParametersMssSs()
    param_mss.frequency = 2100.0  # MHz
    param_mss.bandwidth = 20.0  # MHz
    param_mss.altitude = 500e3  # meters
    param_mss.azimuth = 0
    param_mss.elevation = 90  # degrees
    param_mss.cell_radius = 19e3  # meters
    param_mss.intersite_distance = param_mss.cell_radius * np.sqrt(3)
    param_mss.num_sectors = 19
    param_mss.antenna_gain = 30  # dBi
    param_mss.antenna_3_dB_bw = 4.4127
    param_mss.antenna_l_s = -20  # in dB
    param_mss.antenna_pattern = "ITU-R-S.1528-Taylor"
    roll_off = 7

    param_mss.antenna_s1528.antenna_3_dB = param_mss.antenna_s1528.antenna_3_dB_bw 
    param_mss.antenna_s1528.set_external_parameters(
        frequency=param_mss.frequency,
        bandwidth=param_mss.bandwidth,
        antenna_gain=param_mss.antenna_gain,
        antenna_l_s=param_mss.antenna_l_s,
        antenna_3_dB_bw=param_mss.antenna_3_dB_bw,
        a_deg=param_mss.antenna_3_dB_bw / 2,
        b_deg=param_mss.antenna_3_dB_bw / 2,
        roll_off=roll_off
    )
    antenna_model = AntennaS1528(param_mss.antenna_s1528)

    # Initialize NTN topology
    ntn_topology = TopologyNTN(
        param_mss.intersite_distance,
        param_mss.cell_radius,
        param_mss.altitude,
        param_mss.azimuth,
        param_mss.elevation,
        param_mss.num_sectors
    )
    ntn_topology.calculate_coordinates()

    # Initialize UE distribution
    seed = 100
    rng = np.random.RandomState(seed)
    param_imt = ParametersImt()
    param_imt.topology.type = "NTN"
    param_imt.ue.azimuth_range = (-180, 180)
    param_imt.bandwidth = 10  # MHz
    param_imt.frequency = 2100  # MHz
    param_imt.spurious_emissions = -13  # dB
    param_imt.ue.distribution_azimuth = "UNIFORM"
    param_imt.ue.k = 1000

    param_ue_ant = ParametersAntennaImt()
    ntn_ue = StationFactory.generate_imt_ue_outdoor(param_imt, param_ue_ant, rng, ntn_topology)
    ntn_ue.active = np.ones(ntn_ue.num_stations, dtype=bool)
    
    # Generate base station
    ntn_bs = StationFactory.generate_mss_ss(param_mss)
    num_beams = param_mss.num_sectors
    azimuths = np.linspace(-180, 180, num_beams)
    elevations = np.full(num_beams, param_mss.elevation)
    
    # Creating instance for Antenna Multiple 
    ntn_bs.antenna = AntennaMultipleTransceiver(
        num_beams=num_beams,
        transceiver_radiation_pattern=[antenna_model] * num_beams,  # Lista com objetos que possuem calculate_gain()
        azimuths=azimuths,
        elevations=elevations
    )

    # Computing gain for station_1 and station_2
    phi, theta = ntn_bs.get_pointing_vector_to(ntn_ue)
    station_1_active = np.where(ntn_bs.active)[0]
    station_2_active = np.where(ntn_ue.active)[0]

    # Using calculate gain for multiple transceivers
    gains = calculate_gain_multiple_transceivers(ntn_bs.antenna, phi, theta)
    gains = gains.flatten()

    # Flatten array for calculate gains
    min_length = min(gains.shape[0], ntn_ue.x.shape[0])
    gains = gains[:min_length]
    ntn_ue_x = ntn_ue.x[:min_length] / 1000
    ntn_ue_y = ntn_ue.y[:min_length] / 1000

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ntn_topology.plot_3d(ax, False)  # Plot the 3D topology
    im = ax.scatter(xs=ntn_ue_x, ys=ntn_ue_y,
                    c=gains - np.max(param_mss.antenna_gain), vmin=-50, cmap='jet')
    ax.view_init(azim=0, elev=90)
    fig.colorbar(im, label='Normalized antenna gain (dBi)')

    plt.show()