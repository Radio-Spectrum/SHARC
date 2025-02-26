import os
from pathlib import Path
from sharc.results import Results, SampleList
from sharc.post_processor import PostProcessor
import plotly.graph_objects as go
from sharc.parameters.parameters import Parameters

import glob
import numpy as np
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt, PlotAntennaPattern

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
dl_dir = os.path.join(campaign_base_dir, "output_dl")

post_processor = PostProcessor()

# Add a legend to results in folder that match the pattern
# This could easily come from a config file
# Add a legend to results in folder that match the pattern
# This could easily come from a config file
import re
def legend_gen(dir_name):
    print(dir_name)
    beam_deg = re.search("_([1-6])beam", dir_name)
    if beam_deg is not None:
        beam_deg = beam_deg.group(1)
    else:
        return "None"
    long = re.search("_([0-9][0-9])long", dir_name)
    if long is not None:
        long = long.group(1)
        if long == "60":
            long = "65"
        elif long == "14":
            long = "14.5"
    else:
        return "None"
    link = re.search("_(dl|ul)", dir_name)
    if link is not None:
        link = link.group(1)
    else:
        return "None"
    t = re.search("_((sub){0,1}urban)", dir_name)
    if t is not None:
        t = t.group(1)
    else:
        return "None"
    print(t)

    return f"Long -{long}°, beamwidth = {beam_deg}° ({t.capitalize()} {link.upper()})"

post_processor\
    .add_plot_legend_generator(
        legend_gen
    )

attributes_to_plot = [
    "system_imt_antenna_gain",
    "imt_system_path_loss",
    "imt_system_antenna_gain",
    "system_dl_interf_power_per_mhz",
    "system_ul_interf_power_per_mhz",
]

def filter_fn(result_dir: str, is_suburban: bool) -> bool:
    sub = "_suburban" if is_suburban else "_urban"

    return (
        "14long" in result_dir
        or
        "60long" in result_dir
    ) and sub in result_dir

dl_urban_results = Results.load_many_from_dir(
    dl_dir, only_latest=True,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, False)
)
dl_suburban_results = Results.load_many_from_dir(
    dl_dir, only_latest=True,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, True)
)
ul_urban_results = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output_ul"), only_latest=True,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, False)
)
ul_suburban_results = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output_ul"), only_latest=True,
    only_samples=attributes_to_plot,
    filter_fn=lambda x: filter_fn(x, True)
)
# ^: list[Results]

all_results = [
    *dl_urban_results,
    *dl_suburban_results,
    *ul_urban_results,
    *ul_suburban_results
]
# ^: list[Results]

# transforming dBm / MHz to dB / kHz
# dBm -> dB means -30
# /MHz -> /kHz means -30
for result in all_results:
    result.system_dl_interf_power_per_mhz = SampleList(
      np.array(result.system_dl_interf_power_per_mhz) - 30 - 30
    )
    result.system_ul_interf_power_per_mhz = SampleList(
      np.array(result.system_ul_interf_power_per_mhz) - 30 - 30
    )

post_processor.add_results(all_results)

post_processor.add_plots(
    post_processor.generate_ccdf_plots_from_results(
        all_results,
        cutoff_percentage=0.001
    )
)
post_processor.add_plots(
    post_processor.generate_cdf_plots_from_results(
        all_results
    )
)

# Add a protection criteria line:
# dB to dBm (+ 30)
# the following conversion makes the criteria more strict, so there may not be a problem
plots_to_add_vline = [
    "system_ul_interf_power_per_mhz",
    "system_dl_interf_power_per_mhz"
]
interf_protection_criteria = -161

for prop_name in plots_to_add_vline:
    for plot_type in ["cdf", "ccdf"]:
        plt = post_processor\
            .get_plot_by_results_attribute_name(prop_name, plot_type=plot_type)
        if plt:
            plt.add_vline(
                interf_protection_criteria, line_dash="dash",
                name="0.1% criteria"
            )

system_dl_interf_power_plot = post_processor\
    .get_plot_by_results_attribute_name("system_dl_interf_power_per_mhz")

system_ul_interf_power_plot = post_processor\
    .get_plot_by_results_attribute_name("system_ul_interf_power_per_mhz")
aggregated_plot = None

if system_ul_interf_power_plot and system_dl_interf_power_plot:
    aggregated_plot = go.Figure()
    aggregated_plot.update_layout(
        title=f'CDF Plot for aggregated Spectral Power Density from Interference',
        xaxis_title="Interference (dB/KHz)",
        yaxis_title="CDF",
        yaxis=dict(tickmode="array", tickvals=[0, 0.25, 0.5, 0.75, 1]),
        xaxis=dict(tickmode="linear", dtick=5),
        legend_title="Labels",
        meta={"plot_type": "cdf"},
    )
    aggregated_ccdf_plot = go.Figure()
    cutoff_percentage = 0.001
    next_tick = 1
    ticks_at = []
    while next_tick > cutoff_percentage:
        ticks_at.append(next_tick)
        next_tick /= 10
    ticks_at.append(cutoff_percentage)
    ticks_at.reverse()
    aggregated_ccdf_plot.update_layout(
        title=f'CCDF Plot for aggregated Spectral Power Density from Interference',
        xaxis_title="Interference (dB/KHz)",
        yaxis_title="CCDF",
        yaxis=dict(tickmode="array", tickvals=ticks_at, type="log", range=[np.log10(cutoff_percentage), 0]),
        xaxis=dict(tickmode="linear", dtick=5),
        legend_title="Labels",
        meta={"plot_type": "cdf"},
    )

    # we need to specify a common dir_name_contains substring so that we know which results we need to aggregate
    for dl_urb_r in dl_urban_results:
        legend1 = post_processor.get_results_possible_legends(dl_urb_r)[0]
        ul_urb_r = None
        ul_sub_r = None
        dl_sub_r = None
        legend_should_eq_until = len("Long -65°, beamwidth = 6° (")
        for maybe in ul_urban_results:
            legend2 = post_processor.get_results_possible_legends(maybe)[0]
            if legend1["legend"][:legend_should_eq_until] == legend2["legend"][:legend_should_eq_until]:
                ul_urb_r = maybe
                break

        for maybe in ul_suburban_results:
            legend2 = post_processor.get_results_possible_legends(maybe)[0]
            if legend1["legend"][:legend_should_eq_until] == legend2["legend"][:legend_should_eq_until]:
                ul_sub_r = maybe
                break

        for maybe in dl_suburban_results:
            legend2 = post_processor.get_results_possible_legends(maybe)[0]
            if legend1["legend"][:legend_should_eq_until] == legend2["legend"][:legend_should_eq_until]:
                dl_sub_r = maybe
                break

        if None in [dl_sub_r, ul_sub_r, ul_urb_r]:
            raise Exception(
                f"Cannot aggregate {legend1} and {legend2}"
            )
            # continue

        n_bs_sim = 19*3*3*7

        aggregated_results_urb = PostProcessor.aggregate_results(
            dl_samples=dl_urb_r.system_dl_interf_power_per_mhz,
            ul_samples=ul_urb_r.system_ul_interf_power_per_mhz,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            # Ra1Rb1
            n_bs_actual=85157
            # Ra2Rb2
            # n_bs_actual=1149628
        )
        aggregated_results_sub = PostProcessor.aggregate_results(
            dl_samples=dl_sub_r.system_dl_interf_power_per_mhz,
            ul_samples=ul_sub_r.system_ul_interf_power_per_mhz,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            # Ra1Rb1
            n_bs_actual=10218
            # Ra2Rb2
            # n_bs_actual=122627
        )
        min_length = min(len(aggregated_results_sub), len(aggregated_results_urb))
        # print(aggregated_results)
        # print("legend1['legend']",legend1["legend"])
        aggregated_results = aggregated_results_sub[:min_length] + aggregated_results_urb[:min_length]
        x, y = PostProcessor.cdf_from(aggregated_results)

        aggregated_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'{legend1["legend"][:legend_should_eq_until-1]}',),
        )

        x, y = PostProcessor.ccdf_from(aggregated_results)
        aggregated_ccdf_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'{legend1["legend"][:legend_should_eq_until-1]}',),
        )

    aggregated_plot.add_vline(
        interf_protection_criteria, line_dash="dash",
        name="0.1% criteria"
    )
    aggregated_ccdf_plot.add_vline(
        interf_protection_criteria, line_dash="dash",
        name="0.1% criteria"
    )

PostProcessor.save_plots(
    os.path.join(campaign_base_dir, "output", "figs"),
    [*post_processor.plots, aggregated_plot, aggregated_ccdf_plot],
)

plot_antenna_imt = PlotAntennaPattern("")

# Plot BS TX radiation patterns
# f = plot_antenna_imt.plot_element_pattern(antenna_bs, "BS", "ELEMENT")
# # f.savefig(figs_dir + "BS_element.pdf", bbox_inches='tight')
# f = plot_antenna_imt.plot_element_pattern(antenna_bs, "TX", "ARRAY")
# # f.savefig(figs_dir + "BS_array.pdf", bbox_inches='tight')

# # Plot UE TX radiation patterns
# plot_antenna_imt.plot_element_pattern(antenna_ue, "UE", "ELEMENT")
# plot_antenna_imt.plot_element_pattern(antenna_ue, "UE", "ARRAY")

# Plot every plot:
# for plot in plots:
#     plot.show()

# full_results = ""

# for result in all_results:
#     # This generates the mean, median, variance, etc
#     stats = PostProcessor.generate_statistics(
#         result=result
#     ).write_to_results_dir()

#     full_results += str(stats) + "\n"
#     # # do whatever you want here:
#     # if "fspl_45deg" in stats.results_output_dir:
#     #     get some stat and do something

# with open(dl_dir + "/stats.txt", "w") as f:
#     f.write(full_results)
