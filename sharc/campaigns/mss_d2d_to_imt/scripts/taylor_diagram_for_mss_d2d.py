# Generate a Taylor diagram for the MSS D2D to IMT sharing scenario with parameters from
# Annex 4 to Working Party 4C Chair’s Report
# WORKING DOCUMENT ON SHARING AND COMPATIBILITY STUDIES IN RELATION TO WRC-27 AGENDA ITEM 1.13
# Section 4.1.4

import numpy as np
import plotly.graph_objects as go

from sharc.parameters.parameters_mss_d2d import ParametersMssD2d
from sharc.antenna.antenna_s1528 import AntennaS1528Taylor
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528
import pandas as pd
from pathlib import Path

# Input parameters
local_dir = Path(__file__).parent.resolve()
param_file = local_dir / ".." / "input" / "parameters_mss_d2d_to_imt_dl_co_channel_system_A.yaml"
params = ParametersMssD2d()
params.load_parameters_from_file(param_file)

antenna_params = params.antenna_s1528
antenna_params.frequency = 2e3

# Create an instance of AntennaS1528Taylor
antenna = AntennaS1528Taylor(antenna_params)

print("Antenna parameters:")
print(f"Frequency: {antenna.frequency_mhz} MHz")
print(f"lambda: {antenna.lamb:.2f} m")
print(f"Max Gain: {antenna.peak_gain:.2f} dBi")
print(f"Lr: {antenna.l_r:.2f} m")
print(f"Lt: {antenna.l_t:.2f} m")
print(f"SLR: {antenna.slr:.2f}")
print(f"Number of side lobes: {antenna.n_side_lobes}")

# Define phi angles from 0 to 60 degrees for plotting
theta_angles = np.linspace(0, 90, 901)

# Calculate gains for each phi angle at a fixed theta angle (e.g., theta=0)
gain_rolloff_7 = antenna.calculate_gain(off_axis_angle_vec=theta_angles,
                                        theta_vec=np.zeros_like(theta_angles))

# Export theta_angles and gain_rolloff_7 to a CSV file
output_file = local_dir / "sat_antenna_pattern_s1528_rec14.csv"
export_data = pd.DataFrame({'Theta (degrees)': theta_angles, 'Gain (dBi)': gain_rolloff_7})
export_data.to_csv(output_file, index=False)

print(f"Theta angles and gain data exported to {output_file}")

# Create a plotly figure
fig = go.Figure()

# Add a trace for the antenna gain
# fig.add_trace(go.Scatter(x=theta_angles, y=gain_rolloff_7 - g_max, mode='lines', name='Antenna Gain'))
fig.add_trace(go.Scatter(x=theta_angles, y=gain_rolloff_7, mode='lines', name='Antenna Gain'))
# Limit the y-axis from 0 to 35 dBi
# fig.update_yaxes(range=[-20 - g_max, 35])
fig.update_yaxes(range=[-15, 35])
fig.update_xaxes(range=[0, 90])
# Set the title and labels
fig.update_layout(
    title='Normalized SystemA Antenna Pattern',
    xaxis_title='Theta (degrees)',
    yaxis_title='Gain (dBi)'
)
# Update the layout for a white background and scientific aspect
fig.update_layout(
    plot_bgcolor='white',
    title_font=dict(size=16, family='Arial'),
    font=dict(size=12, family='Arial'),
    xaxis=dict(
        title='Theta (degrees)',
        title_font=dict(size=14),
        gridcolor='lightgray',
        zerolinecolor='black'
    ),
    yaxis=dict(
        title='Gain (dBi)',
        title_font=dict(size=14),
        gridcolor='lightgray',
        zerolinecolor='lightgray',
    ),
    legend=dict(
        bgcolor='white',
        bordercolor='black',
        borderwidth=1
    )
)
# Show the plot
# fig.show()
# Load the reference data from the CSV file
# Define the path to the current directory and the reference CSV file
current_dir = Path(__file__).parent
ref_file = current_dir / "ref-s1528-system-a.csv"

# Load the reference data from the CSV file
ref_data = pd.read_csv(ref_file)

# Extract theta and gain values from the reference data
ref_theta = ref_data['x']
ref_gain = ref_data['y']

# Add a trace for the reference antenna gain
fig.add_trace(go.Scatter(x=ref_theta, y=ref_gain, mode='lines', name='Reference Gain'))

# Update the layout to include a legend for both plots
fig.update_layout(
    title='SystemA Antenna Pattern vs Reference',
    legend=dict(
        title="Legend",
        x=0.5,
        y=1.1,
        xanchor='center',
        orientation='h'
    )
)
fig.write_image(local_dir / "antenna_pattern.png")

print("Figure saved as antenna_pattern.png")
