import pandas as pd
from pathlib import Path
import numpy as np
import plotly.graph_objects as go

# Generate the relative path
output_dir = Path(__file__).parent / "../output/output_mss_d2d_to_imt_dl_co_channel_system_A_2025-05-12_04"

# Load data from CSV files
path_loss_data = pd.read_csv(output_dir / 'imt_system_path_loss.csv')
antenna_gain_data = pd.read_csv(output_dir / 'system_imt_antenna_gain.csv')

# Histogram for Path Loss
path_loss_hist, path_loss_bins = np.histogram(path_loss_data['samples'],
                                              density=True,
                                              bins=np.histogram_bin_edges(path_loss_data['samples'], bins='auto'),)

# Export histogram data to Excel
histogram_data = pd.DataFrame({
    'Path Loss Bin Start': path_loss_bins[:-1],
    'Path Loss Bin End': path_loss_bins[1:],
    'Path Loss Probability': path_loss_hist
})
histogram_data.to_excel(output_dir / 'imt_system_path_loss_histogram.xlsx', index=False)

# Create histogram plot for Path Loss
fig_path_loss = go.Figure()

fig_path_loss.add_trace(go.Bar(
    x=path_loss_bins[:-1],
    y=path_loss_hist,
    name='Path Loss',
    marker_color='blue',
    opacity=0.7
))

# Update layout for Path Loss
fig_path_loss.update_layout(
    title='Histogram of Path Loss',
    xaxis_title='Path Loss Value',
    yaxis_title='Probability Density',
)

# Save Path Loss histogram
fig_path_loss.write_html(output_dir / 'imt_system_path_loss_histogram.html', include_plotlyjs='cdn', auto_open=False)


# Histogram for Antenna Gain
antenna_gain_hist, antenna_gain_bins = np.histogram(antenna_gain_data['samples'],
                                                    density=True,
                                                    bins=np.histogram_bin_edges(antenna_gain_data['samples'],
                                                                                bins='auto'))

# Export histogram data to Excel
antenna_gain_histogram_data = pd.DataFrame({
    'Antenna Gain Bin Start': antenna_gain_bins[:-1],
    'Antenna Gain Bin End': antenna_gain_bins[1:],
    'Antenna Gain Probability': antenna_gain_hist
})
antenna_gain_histogram_data.to_excel(output_dir / 'system_imt_antenna_gain_histogram.xlsx', index=False)

# Create histogram plot for Antenna Gain
fig_antenna_gain = go.Figure()

fig_antenna_gain.add_trace(go.Bar(
    x=antenna_gain_bins[:-1],
    y=antenna_gain_hist,
    name='Antenna Gain',
    marker_color='green',
    opacity=0.7
))

# Update layout for Antenna Gain
fig_antenna_gain.update_layout(
    title='Histogram of Antenna Gain',
    xaxis_title='Antenna Gain Value',
    yaxis_title='Probability Density',
)

# Save Antenna Gain histogram
fig_antenna_gain.write_html(output_dir / 'system_imt_antenna_gain_histogram.html', include_plotlyjs='cdn', auto_open=False)


## Plot the histrogram for the off_axis_angles
off_axis_angles_data = pd.read_csv(output_dir / 'off_axis_angle.csv')
off_axis_angles_hist, off_axis_angles_bins = np.histogram(off_axis_angles_data['samples'],
                                                           density=True,
                                                           bins=np.histogram_bin_edges(off_axis_angles_data['samples'],
                                                                                        bins='auto'))
# Export histogram data to Excel
off_axis_angles_histogram_data = pd.DataFrame({
    'Off Axis Angle Bin Start': off_axis_angles_bins[:-1],
    'Off Axis Angle Bin End': off_axis_angles_bins[1:],
    'Off Axis Angle Probability': off_axis_angles_hist
})
off_axis_angles_histogram_data.to_excel(output_dir / 'off_axis_angle_histogram.xlsx', index=False)
# Create histogram plot for Off Axis Angles
fig_off_axis_angles = go.Figure()
fig_off_axis_angles.add_trace(go.Bar(
    x=off_axis_angles_bins[:-1],
    y=off_axis_angles_hist,
    name='Off Axis Angles',
    marker_color='red',
    opacity=0.7
))
# Update layout for Off Axis Angles
fig_off_axis_angles.update_layout(
    title='Histogram of Off Axis Angles',
    xaxis_title='Off Axis Angle Value',
    yaxis_title='Probability Density',
)
# Save Off Axis Angles histogram
fig_off_axis_angles.write_html(output_dir / 'off_axis_angle_histogram.html', include_plotlyjs='cdn', auto_open=False)
