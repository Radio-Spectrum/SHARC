import os
from pathlib import Path

import numpy as np

from sharc.post_processor import PostProcessor
from sharc.results import Results

# List of values for 'y' (distance) and 'elevation'
Ro = 1600
y_values = [Ro - 600, Ro - 300, Ro, Ro + 300, Ro + 600, Ro + 900, Ro + 1200, Ro + 1500]  # Example values for 'y'
load_probabilities = [20,50]  # Example values for 'elevation'

post_processor = PostProcessor()

# Function to dynamically add legends
def add_plot_legends(y_values, load_probabilities):
    for y in y_values:
        for load_probability in load_probabilities:
            y_circ = y - Ro
            dir_pattern = f"y_{y}_load_probability_{load_probability}"
            legend = f"Dist(m)={y_circ} and load_probability={load_probability}"
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
    # Get the result directory name
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
plots = post_processor.generate_cdf_plots_from_results(filtered_results)

# Add plots to the post_processor
post_processor.add_plots(plots)

# Iterate through all plots
for plot in plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        # Apply the transformation to the x-axis: add -10 * log10(0.75)
        for trace in plot.data:  # Iterate over all traces in the plot
            trace.x = trace.x + (-10 * np.log10(0.75))
        
        # Update the x-axis title to reflect the transformation
        #plot.update_layout(xaxis_title="INR [dB] (transformed)")
        
        # Add a dashed vertical line at -6 dB
        plot.add_vline(
            x=-6,  # Value in dB
            line_dash="dash",  # Dashed line
            line_color="red",  # Line color
            annotation_text="-6 dB",  # Annotation text
            annotation_position="top right"  # Annotation position
        )
        
        # Display the updated plot
        # plot.show()
# Show all plots
for plot in plots:
    plot.show()

# Generate statistics for each filtered result
for result in filtered_results:
    stats = PostProcessor.generate_statistics(result=result).write_to_results_dir()