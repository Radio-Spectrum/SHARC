import os
from pathlib import Path

from sharc.post_processor import PostProcessor
from sharc.results import Results

# List of values for 'y' (distance) and 'elevation'
y_values = list(range(1700, 3400, 100))  # Example values for 'y'
elevations = [30]  # Example values for 'elevation'

post_processor = PostProcessor()

# Function to dynamically add legends
def add_plot_legends(y_values, elevations):
    for y in y_values:
        for elevation in elevations:
            dir_pattern = f"y_{y}_elevation_{elevation}"
            legend = f"Dist(m)={y} and elevation={elevation}"
            post_processor.add_plot_legend_pattern(
                dir_name_contains=dir_pattern,
                legend=legend
            )

# Add legends dynamically
add_plot_legends(y_values, elevations)

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
        for elevation in elevations:
            dir_pattern = f"y_{y}_elevation_{elevation}"
            if dir_pattern in result_dir:
                filtered_results.append(result)
                break

# Add filtered results to the post_processor
post_processor.add_results(filtered_results)

# Generate CDF plots only for the filtered results
plots = post_processor.generate_cdf_plots_from_results(filtered_results)

# Add plots to the post_processor
post_processor.add_plots(plots)

# Add a dashed vertical line at -6 dB to the "system_inr" plot
for plot in plots:
    if plot.layout.meta["related_results_attribute"] == "system_inr":
        plot.add_vline(
            x=-6,  # Value in dB
            line_dash="dash",  # Dashed line
            line_color="red",  # Line color
            annotation_text="-6 dB",  # Annotation text
            annotation_position="top right"  # Annotation position
        )

# Show all plots
for plot in plots:
    plot.show()

# Generate statistics for each filtered result
for result in filtered_results:
    stats = PostProcessor.generate_statistics(result=result).write_to_results_dir()