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
import re
def legend_gen(dir_name):
    beam_deg = re.search("_([1-6])beam", dir_name)
    if beam_deg is not None:
        beam_deg = beam_deg.group(1)
    else:
        return "None"
    long = re.search("_([0-9][0-9])long", dir_name)
    if long is not None:
        long = long.group(1)
        if long == "14":
            long = "14.5"
    else:
        return "None"
    link = re.search("_(dl|ul)", dir_name)
    if link is not None:
        link = link.group(1)
    else:
        return "None"

    return f"Long -{long}°, beamwidth = {beam_deg}° ({link.upper()})"

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

def filter_fn(result_dir: str) -> bool:
    return (
        "14long" in result_dir
        or
        "65long" in result_dir
    )
    # return True

dl_results = Results.load_many_from_dir(
    dl_dir, only_latest=True,
    only_samples=attributes_to_plot,
    filter_fn=filter_fn
)
ul_results = Results.load_many_from_dir(
    os.path.join(campaign_base_dir, "output_ul"), only_latest=True,
    only_samples=attributes_to_plot,
    filter_fn=filter_fn
)
# ^: typing.List[Results]

all_results = [
    *dl_results,
    *ul_results
]

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

    for dl_r in dl_results:
        legend1 = post_processor.get_results_possible_legends(dl_r)[0]
        ul_r = None

        for maybe in ul_results:
            legend2 = post_processor.get_results_possible_legends(maybe)[0]
            if legend1["legend"][:-4] in legend2["legend"][:-4]:
                ul_r = maybe
                break

        if None in [ul_r]:
            raise Exception(
                f"Cannot aggregate {legend1} and {legend2}"
            )
            # continue
        print("############")
        print("legend1", legend1)
        print("legend2", legend2)
        print("############")
        n_bs_sim = 19 * 3 * 3 * 7

        aggregated_results = PostProcessor.aggregate_results(
            dl_samples=dl_r.system_dl_interf_power_per_mhz,
            ul_samples=ul_r.system_ul_interf_power_per_mhz,
            ul_tdd_factor=0.25,
            n_bs_sim=n_bs_sim,
            # n_bs_actual=19*3*3*7
            # Ra1Rb1
            n_bs_actual=127736,
            # Ra2Rb2
            # n_bs_actual=766419,
        )
        # print(aggregated_results)
        # print("legend1['legend']",legend1["legend"])
        x, y = PostProcessor.cdf_from(aggregated_results)

        aggregated_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'{legend1["legend"][:-4]}',),
        )

        x, y = PostProcessor.ccdf_from(aggregated_results)
        aggregated_ccdf_plot.add_trace(
            go.Scatter(x=x, y=y, mode='lines', name=f'{legend1["legend"][:-4]}',),
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
