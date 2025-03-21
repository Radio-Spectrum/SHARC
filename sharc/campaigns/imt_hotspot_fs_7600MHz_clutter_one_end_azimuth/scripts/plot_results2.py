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
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_0deg",
        legend= "DL - Az = 0°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_0.5deg",
        legend= "DL - Az = 0.5°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_1deg",
        legend="DL - Az = 1°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_5deg",
        legend="DL - Az = 5°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_10deg",
        legend="DL - Az = 10°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_15deg",
        legend= "DL - Az = 15°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_20deg",
        legend= "DL - Az = 20°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_25deg",
        legend="DL - Az = 25°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_30deg",
        legend="DL - Az = 30°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_60deg",
        legend="DL - Az = 60°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_dl_80deg",
        legend="DL - Az = 80°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_0deg",
        legend= "UL - Az = 0°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_0.5deg",
        legend= "UL - Az = 0.5°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_1deg",
        legend="UL - Az = 1°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_5deg",
        legend="UL - Az = 5°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_10deg",
        legend="UL - Az = 10°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_15deg",
        legend= "UL - Az = 15°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_20deg",
        legend= "UL - Az = 20°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_25deg",
        legend="UL - Az = 25°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_30deg",
        legend="UL - Az = 30°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_60deg",
        legend="UL - Az = 60°"
    ).add_plot_legend_pattern(
        dir_name_contains="output_imt_hotspot_fs_7600MHz_clutter_one_end_ul_80deg",
        legend="UL - Az = 80°"
    )

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
print(campaign_base_dir)

many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)
# ^: typing.List[Results]

post_processor.add_results(many_results)

plots = post_processor.generate_cdf_plots_from_results(
    many_results
)



post_processor.add_plots(plots)

plots_to_add_vline = [
    "system_inr"
]

# Add a protection criteria line:
interf_protection_criteria0 = -127
interf_protection_criteria1 = -148

for prop_name in plots_to_add_vline:
    plt = post_processor\
        .get_plot_by_results_attribute_name(prop_name)
    if plt:
        plt.add_vline(
            -10, line_dash="dash",
            name="20% criteria"
        )
        plt.add_hline(
            0.2, line_dash="dash",
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
