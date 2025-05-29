import os
from pathlib import Path
from sharc.results import Results
from sharc.post_processor import PostProcessor
import argparse
import csv

# Command line argument parser
parser = argparse.ArgumentParser(description="Generate and plot results.")
parser.add_argument("--auto_open", action="store_true", default=False, help="Set this flag to open plots in a browser.")
parser.add_argument("--scenario", type=int, choices=[0, 1], required=True,
                    help="Scenario parameter: 0 or 1. 0 for MSS-D2D to IMT-UL/DL,"
                    "1 for MSS-D2D to IMT-UL/DL with varying latitude.")
args = parser.parse_args()
scenario = args.scenario
auto_open = args.auto_open

local_dir = os.path.dirname(os.path.abspath(__file__))
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

post_processor = PostProcessor()

# Add a legend to results in folder that match the pattern
# This could easily come from a config file
if scenario == 0:
    many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"),
                                              filter_fn=lambda x: "system_A" in x,
                                              only_latest=True)
    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_ul_co_channel_system_A",
            legend="MSS-D2D to IMT-UL"
        )

    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_dl_co_channel_system_A",
            legend="MSS-D2D to IMT-DL"
        )
    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_ul_co_channel_AAS_k_1_system_A",
            legend="MSS-D2D to IMT-UL (AAS, K=1)"
        )
    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_ul_co_channel_AAS_k_3_system_A",
            legend="MSS-D2D to IMT-UL (AAS, K=3)"
        )
    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains="_mss_d2d_to_imt_ul_co_channel_AAS_k_6_system_A",
            legend="MSS-D2D to IMT-UL (AAS, K=6)"
        )
elif scenario == 1:
    many_results = Results.load_many_from_dir(os.path.join(campaign_base_dir, "output"),
                                              filter_fn=lambda x: "_lat_" in x,
                                              only_latest=True)
    for link in ["ul", "dl"]:
        for i in range(0, 70, 10):
            post_processor.add_plot_legend_pattern(
                dir_name_contains="_lat_" + link + "_" + str(i) + "_deg",
                legend="IMT-Link=" + link.upper() + " latitude=" + str(i) + "deg"
            )
else:
    raise ValueError("Invalid scenario. Choose 0 or 1.")

# ^: typing.List[Results]

post_processor.add_results(many_results)

plots = post_processor.generate_cdf_plots_from_results(
    many_results
)

post_processor.add_plots(plots)

plots = post_processor.generate_ccdf_plots_from_results(
    many_results
)

post_processor.add_plots(plots)

# Add a protection criteria line:
protection_criteria = -6
imt_dl_inr = post_processor.get_plot_by_results_attribute_name("imt_dl_inr", plot_type="cdf")
imt_dl_inr.add_vline(protection_criteria, line_dash="dash", annotation=dict(
    text="Protection Criteria: " + str(protection_criteria) + " dB",
    xref="x", yref="y",
    x=protection_criteria + 0.5, y=0.8,
    font=dict(size=12, color="red")
))
imt_dl_inr.update_layout(template="plotly_white")
imt_ul_inr = post_processor.get_plot_by_results_attribute_name("imt_ul_inr", plot_type="cdf")
imt_ul_inr.add_vline(protection_criteria, line_dash="dash")

# Export imt_ul_inr trace to CSV
csv_file = os.path.join(campaign_base_dir, "output", "imt_ul_inr_trace.csv")
with open(csv_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["x", "y"])  # Write header
    for trace in imt_ul_inr.data:
        if "x" in trace and "y" in trace:
            writer.writerows(zip(trace["x"], trace["y"]))

# Combine INR plots into one:

for trace in imt_ul_inr.data:
    imt_dl_inr.add_trace(trace)

# Add a trace with x and y data
# Rabie ref
x = [-28.093615233944515, -26.205757226683524, -25.538606771104078, -24.878754735655797, -24.319209192266584, -23.555120746227068, -22.328424747258413, -20.76506572736762, -19.94726839472185, -18.92623813226983, -17.98380624046111, -17.33630537754249, -16.282712932966817, -14.933066625634712, -14.385497976819718, -14.002050211467044, -13.016950632737675, -11.621268136885924, -11.176438786840386, -9.947497120139065, -4.975963037972576, -0.04653522579357272, 5.048510581669532, 9.97606700407131]
y = [-0.003966325840797701, 0.09870394625654892, 0.19841663849923946, 0.30035279702551965, 0.39727691397667736, 0.5002323812742944, 0.6017249028223761, 0.7017280716579347, 0.7318531350346459, 0.7579854656075713, 0.7717804630725029, 0.7807852374514112, 0.7977279449045124, 0.8361976085854318, 0.8580572925468987, 0.877535068446848, 0.8979899019773533, 0.9237789420314347, 0.9435947270576305, 0.955013097853642, 0.9638647118472198, 0.9741000507013688, 0.9854180750380259, 0.9999260605036335]
imt_dl_inr.add_trace({
    "x": x,
    "y": y,
    "mode": "lines",
    "name": "Apple IMT-DL"
})

# Update layout if needed
imt_dl_inr.update_layout(title_text="CDF Plot for IMT Downlink and Uplink INR",
                         xaxis_title="IMT INR [dB]",
                         yaxis_title="Cumulative Probability",
                         legend_title="Legend")

# Export imt_dl_inr trace to CSV

csv_file = os.path.join(campaign_base_dir, "output", "imt_dl_inr_trace.csv")
with open(csv_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["x", "y"])  # Write header
    for trace in imt_dl_inr.data:
        if "x" in trace and "y" in trace:
            writer.writerows(zip(trace["x"], trace["y"]))

# Save the plot as HTML
file = os.path.join(campaign_base_dir, "output", "imt_dl_ul_inr.html")
imt_dl_inr.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

file = os.path.join(campaign_base_dir, "output", "imt_system_antenna_gain.html")
imt_system_antenna_gain = post_processor.get_plot_by_results_attribute_name("imt_system_antenna_gain")
imt_system_antenna_gain.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

file = os.path.join(campaign_base_dir, "output", "system_imt_antenna_gain.html")
system_imt_antenna_gain = post_processor.get_plot_by_results_attribute_name("system_imt_antenna_gain")
system_imt_antenna_gain.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

# Export imt_dl_inr trace to CSV
csv_file = os.path.join(campaign_base_dir, "output", "system_imt_antenna_gain_trace.csv")
with open(csv_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["x", "y"])  # Write header
    for trace in system_imt_antenna_gain.data:
        if "x" in trace and "y" in trace:
            writer.writerows(zip(trace["x"], trace["y"]))

file = os.path.join(campaign_base_dir, "output", "sys_to_imt_coupling_loss.html")
imt_system_path_loss = post_processor.get_plot_by_results_attribute_name("imt_system_path_loss")
imt_system_path_loss.write_html(file=file, include_plotlyjs="cdn", auto_open=auto_open)

imt_dl_inr_ccdf = post_processor.get_plot_by_results_attribute_name("imt_dl_inr", plot_type="ccdf")
imt_dl_inr_ccdf.add_vline(protection_criteria, line_dash="dash")
imt_ul_inr_ccdf = post_processor.get_plot_by_results_attribute_name("imt_ul_inr", plot_type="ccdf")
# Combine INR plots into one:
for trace in imt_ul_inr_ccdf.data:
    imt_dl_inr_ccdf.add_trace(trace)

# Update layout if needed
imt_dl_inr_ccdf.update_layout(
    title_text="CCDF Plot for IMT Downlink and Uplink INR",
    xaxis_title="IMT INR [dB]",
    yaxis_title="P(X > I)",
    legend_title="Legend",
    # log_x=True
)
imt_dl_inr_ccdf.write_image(file=os.path.join(campaign_base_dir, "output", "imt_dl_inr_ccdf.png"))

for result in many_results:
    # This generates the mean, median, variance, etc
    stats = PostProcessor.generate_statistics(
        result=result
    ).write_to_results_dir()
