import os
from pathlib import Path
from sharc.results import Results
from sharc.post_processor import PostProcessor

auto_open = False  # set to True if you want to open the plots automatically


local_dir = os.path.dirname(os.path.abspath(__file__))

post_processor = PostProcessor()

for dist in [10, 20, 30, 40, 50]:
    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_excl_dist_" + str(dist) + "_km_dl",
            legend="exclusion distance=" + str(dist) + "km - DL"
        )

    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_excl_dist_" + str(dist) + "_km_ul",
            legend="exclusion distance=" + str(dist) + "km - UL"
        )

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"), only_latest=True)

post_processor.add_results(many_results)

# plots = post_processor.generate_cdf_plots_from_results(
#     many_results
# )

# post_processor.add_plots(plots)

plots = post_processor.generate_ccdf_plots_from_results(
    many_results
)

post_processor.add_plots(plots)

# Add a protection criteria line:
protection_criteria = -6
imt_dl_inr = post_processor.get_plot_by_results_attribute_name("imt_dl_inr", plot_type="ccdf")
imt_dl_inr.add_vline(protection_criteria, line_dash="dash")

imt_ul_inr = post_processor.get_plot_by_results_attribute_name("imt_ul_inr", plot_type="ccdf")
imt_ul_inr.add_vline(protection_criteria, line_dash="dash")

# Combine INR plots into one:

for trace in imt_ul_inr.data:
    imt_dl_inr.add_trace(trace)

# Update layout if needed
imt_dl_inr.update_layout(title_text="CCDF Plot for IMT Downlink and Uplink INR",
                         xaxis_title="IMT INR [dB]",
                         yaxis_title="Cumulative Probability",
                         legend_title="Legend")

file = os.path.join(campaign_base_dir, "output", "imt_dl_ul_inr.html")
imt_dl_inr.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

file = os.path.join(campaign_base_dir, "output", "imt_system_antenna_gain.html")
imt_system_antenna_gain = post_processor.get_plot_by_results_attribute_name("imt_system_antenna_gain", plot_type="ccdf")
imt_system_antenna_gain.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

file = os.path.join(campaign_base_dir, "output", "system_imt_antenna_gain.html")
system_imt_antenna_gain = post_processor.get_plot_by_results_attribute_name("system_imt_antenna_gain", plot_type="ccdf")
system_imt_antenna_gain.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

file = os.path.join(campaign_base_dir, "output", "sys_to_imt_coupling_loss.html")
imt_system_path_loss = post_processor.get_plot_by_results_attribute_name("imt_system_path_loss", plot_type="ccdf")
imt_system_path_loss.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

for result in many_results:
    # This generates the mean, median, variance, etc
    stats = PostProcessor.generate_statistics(
        result=result
    ).write_to_results_dir()
