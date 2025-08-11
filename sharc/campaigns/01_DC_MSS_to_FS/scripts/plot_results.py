"""
Script for post-processing and plotting IMT HIBS RAS 2600 MHz simulation results.
Adds legends to result folders and generates plots using SHARC's PostProcessor.
"""
import os
from pathlib import Path
from sharc.results import Results
# import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

post_processor = PostProcessor()
heights = [20]  # meters
azis = [0, 90, 180, 270]  # degrees
lfs = [0.5]  # fraction (20%, 50%)
margins = [40, 80, 120]  # km

# Convert to the expected directory name format
height_strs = [f"{h}m" for h in heights]
azi_strs = [f"azi_{a}deg" for a in azis]
lf_strs = [f"lf_{lf}" if lf != 0.2 else "lf_0.2" for lf in lfs]  # match naming convention
margin_strs = [f"margin_{m}km" for m in margins]

combinations = [
    (h, azi, lf, margin)
    for h in sorted(heights)
    for azi in sorted(azis)
    for lf in sorted(lfs)
    for margin in sorted(margins)
]

# Add them in sorted order
for h, azi, lf, margin in combinations:
    post_processor.add_plot_legend_pattern(
        dir_name_contains=f"{h}m_azi_{azi}deg_lf_{lf}_margin_{margin}km",
        legend=f"h={h}m,azi={azi}deg,lf={int(lf*100)}%,M={margin}km"
    )


# Define filter function
filter_fn = lambda dir_path: (
    any(h in os.path.basename(dir_path) for h in height_strs) and
    any(a in os.path.basename(dir_path) for a in azi_strs) and
    any(l in os.path.basename(dir_path) for l in lf_strs) and
    any(m in os.path.basename(dir_path) for m in margin_strs)
)
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())



many_results = Results.load_many_from_dir(
    os.path.join(
        campaign_base_dir,
        "output"),
    only_latest=True,
    filter_fn=filter_fn
    )
# ^: typing.List[Results]

post_processor.add_results(many_results)

plots = post_processor.generate_ccdf_plots_from_results(
    many_results, cutoff_percentage=0.001
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
