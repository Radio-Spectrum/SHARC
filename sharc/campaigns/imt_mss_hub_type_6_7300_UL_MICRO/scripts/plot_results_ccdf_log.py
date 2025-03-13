import os
from pathlib import Path

import numpy as np

from sharc.post_processor import PostProcessor
from sharc.results import Results

# --- USER CONFIGURATION ---
apply_shift = True  # Set to True to apply shift, False to disable
#apply_shift = False  # Set to True to apply shift, False to disable
mode = "UL"  # "DL" for Downlink, "UL" for Uplink
output_filename = "CCDF_plot_MICRO"  # Base filename without extension

# Set shift value based on mode
shift_value = -10 * np.log10(0.75) if mode == "DL" else -10 * np.log10(0.25)

# Widescreen resolution (16:9 format)
image_width = 1600
image_height = 900

# List of values for 'y' (distance) and 'load_probability'
Ro = 1600
y_values = [Ro - Ro, Ro - 400, Ro + 1500, Ro + 5000, Ro + 10000]
load_probabilities = [20, 50]

post_processor = PostProcessor()

# Function to dynamically add legends
def add_plot_legends(y_values, load_probabilities):
    for y in y_values:
        for load_probability in load_probabilities:
            y_circ = y - Ro
            dir_pattern = f"y_{y}_load_probability_{load_probability}"
            legend = f"Dist(m)={y_circ}, Load={load_probability}%"
            post_processor.add_plot_legend_pattern(
                dir_name_contains=dir_pattern,
                legend=legend
            )

# Add legends dynamically
add_plot_legends(y_values, load_probabilities)

# Base directory for the results
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

# Load the results
many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)

# Filter results to include only those that match the desired pattern
filtered_results = []
for result in many_results:
    result_dir = os.path.basename(result.output_directory)
    for y in y_values:
        for load_probability in load_probabilities:
            dir_pattern = f"y_{y}_load_probability_{load_probability}"
            if dir_pattern in result_dir:
                filtered_results.append(result)
                break

# Add filtered results to the post_processor
post_processor.add_results(filtered_results)

# Generate CDF plots only for the filtered results
cdf_plots = list(post_processor.generate_cdf_plots_from_results(filtered_results))  # Convert to list

# Generate CCDF (1 - CDF) with log-scale Y-axis
ccdf_plots = []
for plot in cdf_plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        ccdf_plot = plot  # Copy plot structure
        for trace in ccdf_plot.data:
            trace.y = 1 - trace.y  # CCDF = 1 - CDF
            
            # Apply shift only if enabled
            if apply_shift:
                trace.x = trace.x + shift_value  # Shift INR values

        ccdf_plot.update_layout(
            title="CCDF Plot for [SYS] System INR",
            xaxis_title="INR (dB)",  # Make sure INR is labeled correctly
            yaxis_title="CCDF",
            yaxis_type="log",  # **Set log scale on Y-axis**
            yaxis=dict(
                tickvals=[1, 1e-1, 1e-2, 1e-3, 1e-4],  # Define tick positions
                ticktext=["$10^0$", "$10^{-1}$", "$10^{-2}$", "$10^{-3}$", "$10^{-4}$"],  # Tick labels
                range=[-4, 0]  # 🔹 Force Y-axis limits from 10^-4 to 10^0
            )
        )

        # Add -6 dB marker to CCDF (apply shift if enabled)
        ccdf_plot.add_vline(
            x=-6 ,
            line_dash="dash",
            line_color="red",
            annotation_text="-6 dB",
            annotation_position="top right"
        )

        ccdf_plots.append(ccdf_plot)

# Add CCDF plots to the post_processor
post_processor.add_plots(ccdf_plots)

# Function to save the plot
def save_plot(plot, filename):
    """Save plot as PNG with the given filename."""
    plot.write_image(filename, width=image_width, height=image_height, scale=2)    
    print(f"Plot saved as: {filename}")

# Main function to handle plot saving
def main():
    final_filename = f"{output_filename}_{mode}_bck.png" if apply_shift else f"{output_filename}_{mode}.png"
    for plot in ccdf_plots:
        save_plot(plot, final_filename)

# Run the main function
if __name__ == "__main__":
    main()
