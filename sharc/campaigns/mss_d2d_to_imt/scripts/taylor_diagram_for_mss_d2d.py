
"""
Script to generate a Taylor diagram for the MSS D2D to IMT sharing scenario.
Parameters are based on Annex 4 to Working Party 4C Chair’s Report, Section 4.1.4.
"""

import numpy as np
import plotly.graph_objects as go

from sharc.antenna.antenna_s1528 import AntennaS1528Taylor
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528

# Antenna parameters
g_max = 34.1  # dBi
l_r = l_t = 1.6  # meters
slr = 20  # dB
n_side_lobes = 2  # number of side lobes
freq = 850  # MHz

antenna_params = ParametersAntennaS1528(
    antenna_gain=g_max,
    frequency=freq,  # in MHz
    bandwidth=5,  # in MHz
    slr=slr,
    n_side_lobes=n_side_lobes,
    l_r=l_r,
    l_t=l_t,
)

# Create an instance of AntennaS1528Taylor
antenna = AntennaS1528Taylor(antenna_params)

# Define phi angles from 0 to 60 degrees for plotting
theta_angles = np.linspace(0, 90, 901)

# Calculate gains for each phi angle at a fixed theta angle (e.g., theta=0)
gain_rolloff_7 = antenna.calculate_gain(off_axis_angle_vec=theta_angles,
                                        theta_vec=np.zeros_like(theta_angles))

# Create a plotly figure
fig = go.Figure()

# Add a trace for the antenna gain
fig.add_trace(
    go.Scatter(
        x=theta_angles,
        y=gain_rolloff_7 -
        g_max,
        mode='lines',
        name='Antenna Gain'))
# Limit the y-axis from 0 to 35 dBi
fig.update_yaxes(range=[-20 - g_max, 2])
fig.update_xaxes(range=[0, 90])
# Set the title and labels
fig.update_layout(
    title='Normalized SystemA Antenna Pattern',
    xaxis_title='Theta (degrees)',
    yaxis_title='Gain (dBi)'
)

# Show the plot
fig.show()

# Calculate slant range for a satellite at 525 km altitude and off-nadir angles in theta_angles
sat_altitude_km = 525  # Satellite altitude in km
earth_radius_km = 6371  # Mean Earth radius in km


# Slant range formula: sqrt(R^2 + (R+h)^2 - 2*R*(R+h)*cos(gamma)) where gamma is the central angle
R = earth_radius_km
h = sat_altitude_km

max_theta = np.degrees(np.arcsin(R / (R + h)))

theta_idxs = np.where(theta_angles <= max_theta)
# Convert theta_angles from degrees to radians
theta_rad = np.deg2rad(theta_angles[theta_idxs])

# elevation angle
# elevation_angle_rad = np.arcsin((h + R) / R * np.sin(theta_rad)) - np.pi / 2
gamma_rad = np.arcsin(((h + R) / R) * np.sin(theta_rad)) - theta_rad

# Slant range calculation
slant_range_km = np.sqrt(R**2 + (R + h)**2 - 2 * R * (R + h) * np.cos(gamma_rad))

# # Optionally, print or plot the slant range
# import matplotlib.pyplot as plt

# plt.figure()
# plt.plot(theta_angles, slant_range_km)
# plt.xlabel('Off-nadir angle (degrees)')
# plt.ylabel('Slant range (km)')
# plt.title('Slant Range vs Off-nadir Angle for 525 km Altitude')
# plt.grid(True)
# plt.show()

pfd_values = gain_rolloff_7[theta_idxs[0]] + (-54.2 - 60) - 10 * np.log10(4 * np.pi * (slant_range_km / 1000)**2)

fig_pfd = go.Figure()
fig_pfd.add_trace(
    go.Scatter(
        x=theta_angles,
        y=pfd_values,
        mode='lines',
        name='PFD'
    )
)
fig_pfd.update_layout(
    title='PFD vs Off-nadir Angle',
    xaxis_title='Off-nadir angle (degrees)',
    yaxis_title='PFD (dBW/m²/MHz)'
)
fig_pfd.update_xaxes(range=[0, 90])
fig_pfd.show()

fig_slant = go.Figure()
fig_slant.add_trace(
    go.Scatter(
        x=theta_angles,
        y=slant_range_km,
        mode='lines',
        name='Slant Range'
    )
)
fig_slant.update_layout(
    title='Slant Range vs Off-nadir Angle for 525 km Altitude',
    xaxis_title='Off-nadir angle (degrees)',
    yaxis_title='Slant Range (km)'
)
fig_slant.update_xaxes(range=[0, 90])
fig_slant.show()

arc_length = gamma_rad * R
fig_arc = go.Figure()
fig_arc.add_trace(
    go.Scatter(
        x=np.degrees(theta_rad),
        y=arc_length,
        mode='lines',
        name='Arc Length'
    )
)
fig_arc.update_layout(
    title='Arc Length vs Off-nadir Angle',
    xaxis_title='Off-nadir angle (degrees)',
    yaxis_title='Arc Length (km)'
)
fig_arc.update_xaxes(range=[0, 90])
fig_arc.show()
