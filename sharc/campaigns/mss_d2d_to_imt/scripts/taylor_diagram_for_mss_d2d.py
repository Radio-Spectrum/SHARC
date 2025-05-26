# Generate a Taylor diagram for the MSS D2D to IMT sharing scenario with parameters from
# Annex 4 to Working Party 4C Chair’s Report
# WORKING DOCUMENT ON SHARING AND COMPATIBILITY STUDIES IN RELATION TO WRC-27 AGENDA ITEM 1.13
# Section 4.1.4

import numpy as np
import plotly.graph_objects as go

from sharc.antenna.antenna_s1528 import AntennaS1528Taylor
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528
import pandas as pd
import os

# Antenna parameters
g_max = 34.1  # dBi
l_r = l_t = 1.6  # meters
slr = 20  # dB
n_side_lobes = 2  # number of side lobes
freq = 2.3e3  # MHz

antenna_params = ParametersAntennaS1528(
    antenna_gain=g_max,
    frequency=freq,  # in MHz
    bandwidth=0,  # in MHz  # we set lambda to the wavelength, so bandwidth is not used
    slr=slr,
    n_side_lobes=n_side_lobes,
    l_r=l_r,
    l_t=l_t,
)

# Create an instance of AntennaS1528Taylor
antenna = AntennaS1528Taylor(antenna_params)

# Load the reference data
# csv_path = os.path.join(os.path.dirname(__file__), "antenna_gain_data_matched_with_apple.csv")
csv_path = os.path.join(os.path.dirname(__file__), "antenna_gain_data.csv")
df = pd.read_csv(csv_path)

# Define phi angles from 0 to 60 degrees for plotting
theta_angles = np.array(df['theta'])

# Calculate gains for each phi angle at a fixed theta angle (e.g., theta=0)
gain_rolloff_7 = antenna.calculate_gain(off_axis_angle_vec=theta_angles,
                                        theta_vec=np.zeros_like(theta_angles))

# Create a plotly figure
fig = go.Figure()

# Add a trace for the antenna gain
fig.add_trace(go.Scatter(x=theta_angles, y=gain_rolloff_7, mode='lines', name='Antenna Gain'))
# Limit the y-axis from 0 to 35 dBi
fig.update_yaxes(range=[np.round(gain_rolloff_7) - 2, g_max + 2])
fig.update_xaxes(range=[0, 90])
# Set the title and labels
fig.update_layout(
    title='SystemA Antenna Pattern',
    xaxis_title='Theta (degrees)',
    yaxis_title='Gain (dBi)'
)

# Assume the CSV has columns: 'theta' and 'gain'
fig.add_trace(go.Scatter(
    x=df['theta'],
    y=df['gain'],
    mode='markers',
    name='Ref. Data'
))

fig.show()

# np.max(gain_rolloff_7 - df['gain'])
print("Max difference between calculated and reference data:", np.max(gain_rolloff_7 - df['gain']))
