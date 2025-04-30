import os
from pathlib import Path
from sharc.results import Results
# import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

post_processor = PostProcessor()

# Add a legend to results in folder that match the pattern
# This could easily come from a config file
post_processor\
    .add_plot_legend_pattern(
        dir_name_contains="_base",
        legend="Base (19 sectors)"
    ).add_plot_legend_pattern(
        dir_name_contains="_random_beam",
        legend="19 sectors, load of 1/19"
    ).add_plot_legend_pattern(
        dir_name_contains="_random_pointing_1beam",
        legend="1 sector random pointing"
    )

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)
# ^: typing.List[Results]

post_processor.add_results(many_results)

plots = post_processor.generate_cdf_plots_from_results(
    many_results
)

post_processor.add_plots(plots)

# # This function aggregates IMT downlink and uplink
# aggregated_results = PostProcessor.aggregate_results(
#     downlink_result=post_processor.get_results_by_output_dir("MHz_60deg_dl"),
#     uplink_result=post_processor.get_results_by_output_dir("MHz_60deg_ul"),
#     ul_tdd_factor=(3, 4),
#     n_bs_sim=7 * 19 * 3 * 3,
#     n_bs_actual=int
# )

# Add a protection criteria line:
protection_criteria = -6
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_inr")\
    .add_vline(protection_criteria, line_dash="dash")

# Add a protection criteria line:
pfd_protection_criteria = -109
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_pfd_external_aggregated")\
    .add_vline(pfd_protection_criteria, line_dash="dash")


# # Show a single plot:
# post_processor\
#     .get_plot_by_results_attribute_name("imt_system_antenna_gain")\
#     .show()

post_processor\
    .get_plot_by_results_attribute_name("system_imt_antenna_gain")\
    .show()

# post_processor\
#     .get_plot_by_results_attribute_name("sys_to_imt_coupling_loss")\
#     .show()

# post_processor\
#     .get_plot_by_results_attribute_name("imt_system_path_loss")\
#     .show()

post_processor\
    .get_plot_by_results_attribute_name("imt_dl_pfd_external")\
    .show()

post_processor\
    .get_plot_by_results_attribute_name("imt_dl_pfd_external_aggregated")\
    .show()

post_processor\
    .get_plot_by_results_attribute_name("imt_dl_inr")\
    .show()

# Plot every plot:
# for plot in plots:
#     plot.update_layout(legend_traceorder="normal")
#     plot.show()

for result in many_results:
    # This generates the mean, median, variance, etc
    stats = PostProcessor.generate_statistics(
        result=result
    ).write_to_results_dir()
    # # do whatever you want here:
    # if "fspl_45deg" in stats.results_output_dir:
    #     get some stat and do something

# # example on how to aggregate results and add it to plot:
# dl_res = post_processor.get_results_by_output_dir("1_cluster")
# aggregated_results = PostProcessor.aggregate_results(
#     dl_samples=dl_res.system_dl_interf_power,
#     ul_samples=ul_res.system_ul_interf_power,
#     ul_tdd_factor=0.75,
#     n_bs_sim=1 * 19 * 3 * 3,
#     n_bs_actual=7 * 19 * 3 * 3
# )

# relevant = post_processor\
#     .get_plot_by_results_attribute_name("system_ul_interf_power")

# aggr_x, aggr_y = PostProcessor.cdf_from(aggregated_results)

# relevant.add_trace(
#     go.Scatter(x=aggr_x, y=aggr_y, mode='lines', name='Aggregate interference',),
# )

# relevant.show()
