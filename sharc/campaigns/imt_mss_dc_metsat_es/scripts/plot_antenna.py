import matplotlib.pyplot as plt
import numpy as np
import os
from pathlib import Path
from sharc.results import Results
import plotly.graph_objects as go
from sharc.antenna.antenna_s1528 import AntennaS1528Taylor
from sharc.parameters.parameters import Parameters

parameters = Parameters()

parameters.set_file_name(
    "sharc/campaigns/imt_mss_dc_metsat_es/input/parameters_imt_omni_to_mss_d2d.yaml"
)

parameters.read_params()

antenna1 = AntennaS1528Taylor(
    parameters.mss_d2d.antenna_s1528
)
print("parameters.mss_d2d.antenna_s1528", parameters.mss_d2d.antenna_s1528)

parameters2 = Parameters()

parameters2.set_file_name(
    "sharc/campaigns/imt_mss_dc_metsat_es/input/parameters_imt_mss_dc_to_earth_station_omni.yaml"
)

parameters2.read_params()

print("parameters2.imt.bs.antenna.itu_r_s_1528", parameters2.imt.bs.antenna.itu_r_s_1528)
antenna2 = AntennaS1528Taylor(
    parameters2.imt.bs.antenna.itu_r_s_1528
)

# Define phi angles from 0 to 60 degrees for plotting
theta_angles = np.linspace(0, 60, 600)

gain1 = antenna1.calculate_gain(off_axis_angle_vec=theta_angles,
                                                  theta_vec=np.zeros_like(theta_angles))

gain2 = antenna2.calculate_gain(off_axis_angle_vec=theta_angles,
                                                  theta_vec=np.zeros_like(theta_angles))

# Plot the antenna gain as a function of phi angle
plt.figure(figsize=(10, 6))
plt.plot(theta_angles, gain1, label='System as MSS')
plt.plot(theta_angles, gain2, label='IMT as MSS')
plt.xlabel('Theta (degrees)')
plt.ylabel('Gain (dB)')
plt.title('Normalized Antenna - Section 1.4')
plt.legend()
plt.xticks(np.linspace(0, 60, 31))
plt.grid(True, which='both')

plt.show()


