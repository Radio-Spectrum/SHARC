import os
from pathlib import Path

import numpy as np

from sharc.post_processor import PostProcessor
from sharc.results import Results

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

# Generate CCDF (1 - CDF)
ccdf_plots = []
for plot in cdf_plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        ccdf_plot = plot  # Copy plot structure
        for trace in ccdf_plot.data:
            trace.y = 1 - trace.y  # CCDF = 1 - CDF
        ccdf_plot.update_layout(
            title="CCDF Plot for [SYS] System INR",
            yaxis_title="CCDF",
        )

        # Add -6 dB marker to CCDF
        ccdf_plot.add_vline(
            x=-6,
            line_dash="dash",
            line_color="red",
            annotation_text="-6 dB",
            annotation_position="top right"
        )

        ccdf_plots.append(ccdf_plot)

# Add CCDF plots to the post_processor
post_processor.add_plots(ccdf_plots)

# Apply INR transformation to CCDF plots
for plot in ccdf_plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        for trace in plot.data:
            trace.x = trace.x + (-10 * np.log10(0.75))

# Show all CCDF plots
for plot in ccdf_plots:
    plot.show()

# Generate statistics for each filtered result
for result in filtered_results:
    stats = PostProcessor.generate_statistics(result=result).write_to_results_dir()
