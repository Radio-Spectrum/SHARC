import os
from pathlib import Path
from sharc.results import Results
import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

post_processor = PostProcessor()

# Add a legend to results in folder that match the pattern
# This could easily come from a config file
post_processor\
    .add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_dl_-6600m",
        legend= "DL - D = 5km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_dl_-16600m",
        legend= "DL - D = 15km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_dl_-26600m",
        legend="DL - D = 25km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_dl_-41600m",
        legend="DL - D = 40km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_ul_-6600m",
        legend= "UL - D = 5km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_ul_-16600m",
        legend= "UL - D = 15km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_ul_-26600m",
        legend="UL - D = 25km"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_macro_FS_example_ul_-41600m",
        legend="UL - D = 40km"
    )
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)
# ^: typing.List[Results]

post_processor.add_results(many_results)

plots = post_processor.generate_cdf_plots_from_results(
    many_results
)


post_processor.add_plots(plots)

## Add reference lines
plots_to_add_vline = [
    "system_inr"
]
for prop_name in plots_to_add_vline:
    plt = post_processor\
        .get_plot_by_results_attribute_name(prop_name)
    if plt:
        plt.add_vline(
            -10, line_dash="dash",
            name="20% criteria"
        )
        plt.add_hline(
            0.8, line_dash="dash",
            name="20% criteria y"
        )

# # This function aggregates IMT downlink and uplink
# aggregated_results = PostProcessor.aggregate_results(
#     downlink_result=post_processor.get_results_by_output_dir("MHz_60deg_dl"),
#     uplink_result=post_processor.get_results_by_output_dir("MHz_60deg_ul"),
#     ul_tdd_factor=(3, 4),
#     n_bs_sim=7 * 19 * 3 * 3,
#     n_bs_actual=int
# )

# Add a protection criteria line:
# protection_criteria = 160

# post_processor\
#     .get_plot_by_results_attribute_name("system_dl_interf_power")\
#     .add_vline(protection_criteria, line_dash="dash")

# Show a single plot:
# post_processor\
#     .get_plot_by_results_attribute_name("system_dl_interf_power")\
#     .show()

# Plot every plot:
for plot in plots:
    plot.show()

for result in many_results:
    # This generates the mean, median, variance, etc
    stats = PostProcessor.generate_statistics(
        result=result
    ).write_to_results_dir()


# # example on how to aggregate results and add it to plot:
# dl_res = post_processor.get_results_by_output_dir("1_cluster")
# aggregated_results = PostProcessor.aggregate_results(
#     dl_samples=dl_res.system_dl_interf_power,
#     ul_samples=ul_res.system_ul_interf_power,
#     ul_tdd_factor=0.25,
#     n_bs_sim=1 * 19 * 3 * 3,
#     n_bs_actual=7 * 19 * 3 * 3
# )

# relevant = post_processor\
#     .get_plot_by_results_attribute_name("system_dl_interf_power")

# aggr_x, aggr_y = PostProcessor.cdf_from(aggregated_results)

# relevant.add_trace(
#     go.Scatter(x=aggr_x, y=aggr_y, mode='lines', name='Aggregate interference',),
# )

# relevant.show()
