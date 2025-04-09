import os
import re
from pathlib import Path

import plotly.graph_objects as go

from sharc.post_processor import PostProcessor
from sharc.results import Results

# Initialize PostProcessor
post_processor = PostProcessor()

# Define campaign base path
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

# Add legend for matching results
post_processor.add_plot_legend_pattern(
    dir_name_contains="_mss_d2d_to_imt_co_channel_system_A",
    legend="SystemA MSS-D2D"
)

# Load simulation results (only latest result per folder)
many_results = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output"),
    only_latest=True
)


# Add a legend to results in folder that match the pattern
for result in many_results:
    dir_name = os.path.basename(result.output_directory)
    match = re.search(r"_min_(\d+)_max_(\d+)", dir_name)
    if match:
        min_elev = match.group(1)
        max_elev = match.group(2)
        legend = f"SystemA MSS-D2D ({min_elev}°–{max_elev}°)"
    else:
        legend = "SystemA MSS-D2D"
    
    post_processor.add_plot_legend_pattern(
        dir_name_contains=dir_name,
        legend=legend
    )

# Add results to processor
post_processor.add_results(many_results)

# Generate CDF plots
plots = post_processor.generate_cdf_plots_from_results(many_results)
post_processor.add_plots(plots)

# Add a protection criteria vertical line to a specific plot
protection_criteria = -6
fig = post_processor.get_plot_by_results_attribute_name("imt_dl_inr")
if fig:
    fig.add_vline(
        x=protection_criteria,
        line_dash="dash",
        line_color="red",
        annotation_text="Protection Criterion",
        annotation_position="top left"
    )


# Show key plots safely
key_attributes = [
    #"imt_system_antenna_gain",
    #"system_imt_antenna_gain",
    #"sys_to_imt_coupling_loss",
    #"imt_system_path_loss",
    #"imt_dl_inr",
    "imt_dl_pfd_external",
    "imt_dl_pfd_external_aggregated"
]

for attr in key_attributes:
    fig = post_processor.get_plot_by_results_attribute_name(attr)
    if fig:
        fig.show()
    else:
        print(f"[WARNING] Plot for '{attr}' not found or no data available.")

# Generate and write statistics for each result
for result in many_results:
    stats = PostProcessor.generate_statistics(result=result)
    stats.write_to_results_dir()

# Optional: Aggregate results example (commented)
# dl_res = post_processor.get_results_by_output_dir("1_cluster")
# ul_res = post_processor.get_results_by_output_dir("uplink_results_folder")

# aggregated_results = PostProcessor.aggregate_results(
#     dl_samples=dl_res.system_dl_interf_power,
#     ul_samples=ul_res.system_ul_interf_power,
#     ul_tdd_factor=0.75,
#     n_bs_sim=1 * 19 * 3 * 3,
#     n_bs_actual=7 * 19 * 3 * 3
# )

# aggr_x, aggr_y = PostProcessor.cdf_from(aggregated_results)
# fig = post_processor.get_plot_by_results_attribute_name("system_ul_interf_power")
# fig.add_trace(go.Scatter(x=aggr_x, y=aggr_y, mode='lines', name='Aggregate Interference'))
# fig.show()
