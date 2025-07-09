"""Script to process and plot results for MSS D2D to IMT cross-border campaign."""

import os
from pathlib import Path
import plotly.graph_objects as go
from sharc.results import ResultsManager
from sharc.post_processor import PostProcessor


import argparse

parser = argparse.ArgumentParser(
    description="You may plot the results for the different channel configs"
)

parser.add_argument(
    '--channel', type=str, required=True, choices=["co", "adj"],
    help='Set the channel to generate the parameters ("co" for cochannel or "adj" for adjacent channel)')

parser.add_argument(
    '--freq', type=str, required=True, choices=["0.8G", "2.1G"],
    help='Set the frequency to generate the parameters ("0.8G" or "2.1G")'
)

args = parser.parse_args()

selected_str = f"{args.freq}_{args.channel}"

output_start = f"output_{selected_str}"

post_processor = PostProcessor()

# If set to True the plots will be opened in the browser automatically
auto_open = False

# Add a legend to results in folder that match the pattern
# This could easily come from a config file

if args.freq == "0.8G":
    cell_radius = 113630
    max_pfd_margin_km = 149.07  # -109 dBW/mˆ2/MHz limit at 850MHz
elif args.freq == "2.1G":
    cell_radius = 39475
    max_pfd_margin_km = 67.71  # -109 dBW/mˆ2/MHz limit at 2100MHz
else:
    raise ValueError(f"Invalid frequency: {args.freq}")
cell_radius /= 1e3

country_border = 4 * cell_radius
dists = sorted([
    0,
    cell_radius,
    max_pfd_margin_km
])

prefixes = [f"{x}km" for x in dists]
for prefix in prefixes:
    km = prefix
    post_processor\
        .add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_base",
            legend=f"19 sectors ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_service_grid_100p",
            legend=f"Service grid, load=100% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_service_grid_20p",
            legend=f"Service grid, load=20% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_service_grid_50p",
            legend=f"Service grid, load=50% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_service_grid_padded_100p",
            legend=f"Service grid w/ sats outside, load=100% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_service_grid_padded_20p",
            legend=f"Service grid w/ sats outside, load=20% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_service_grid_padded_50p",
            legend=f"Service grid w/ sats outside, load=50% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_activate_random_beam_5p",
            legend=f"19 sectors, load=1/19 ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_activate_random_beam_30p",
            legend=f"19 sectors, load=30% ({km})"
        ).add_plot_legend_pattern(
            dir_name_contains=f"{prefix}_random_pointing_1beam",
            legend=f"1 sector random pointing ({km})"
        )

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

attributes_to_plot = [
    "imt_system_antenna_gain",
    "system_imt_antenna_gain",
    "sys_to_imt_coupling_loss",
    "imt_system_path_loss",
    "imt_dl_pfd_external",
    "imt_dl_pfd_external_aggregated",
    "imt_dl_inr",
    "imt_ul_inr"
]

results_dl = ResultsManager.load_many_from_dir(os.path.join(campaign_base_dir, f"{output_start}_dl"),
                                               only_latest=True,
                                               only_samples=attributes_to_plot)
# print("len(results_dl)", len(results_dl))
# for i in range(len(results_dl)):
#     print(results_dl[i].imt_dl_inr)
# exit()
results_ul = ResultsManager.load_many_from_dir(os.path.join(campaign_base_dir, f"{output_start}_ul"),
                                               only_latest=True,
                                               only_samples=attributes_to_plot)
# print("len(results_ul)", len(results_ul))
# ^: typing.List[ResultsManager]
all_results = [*results_ul, *results_dl]

post_processor.add_results(all_results)

# Define line styles for different prefixes - the size must match the
# number of unique legends
styles = ["solid", "dot", "dash", "longdash", "dashdot", "longdashdot"]


def linestyle_getter(result: ResultsManager):
    """
    Returns a line style string based on the prefix found in the result's output directory.
    """
    for i in range(len(prefixes)):
        if "_" + prefixes[i] in result.output_directory:
            return styles[i]
    return "solid"


post_processor.add_results_linestyle_getter(linestyle_getter)

plots = post_processor.generate_ccdf_plots_from_results(
    all_results
)

post_processor.add_plots(plots)

# Add a protection criteria line:
protection_criteria = -6
perc_of_time = 0.01

for attr in ["imt_dl_inr", "imt_ul_inr"]:
    plot = post_processor.get_plot_by_results_attribute_name(attr, plot_type='ccdf')
    if plot is not None:
        plot.add_vline(protection_criteria, line_dash="dash", annotation=dict(
            text="Protection criteria",
            xref="x",
            yref="paper",
            x=protection_criteria + 1.0,  # Offset for visibility
            y=0.95
        ))
        plot.add_hline(perc_of_time, line_dash="dash")
    else:
        print(f"Warning: No plot found for attribute '{attr}'")

pfd_protection_criteria = -109
for attr in ["imt_dl_pfd_external", "imt_dl_pfd_external_aggregated"]:
    plot = post_processor.get_plot_by_results_attribute_name(attr, plot_type='ccdf')
    if plot is not None:
        plot.add_vline(pfd_protection_criteria, line_dash="dash", annotation=dict(
            text="PFD protection criteria",
            xref="x",
            yref="paper",
            x=pfd_protection_criteria + 1.0,  # Offset for visibility
            y=0.95
        ))
    else:
        print(f"Warning: No plot found for attribute '{attr}'")

# for attr in attributes_to_plot:
#     post_processor.get_plot_by_results_attribute_name(attr).show()

# Ensure the "htmls" directory exists relative to the script directory
output_dir = Path(__file__).parent / "../output"
output_dir.mkdir(exist_ok=True)
htmls_dir = output_dir / "htmls"
htmls_dir.mkdir(exist_ok=True)
specific_dir = htmls_dir / selected_str
specific_dir.mkdir(exist_ok=True)
# print("specific_dir", specific_dir)

for attr in attributes_to_plot:
    plot = post_processor.get_plot_by_results_attribute_name(attr, plot_type="ccdf")
    if plot is None:
        print(f"Warning: No plot found for attribute '{attr}'")
        continue
    plot.write_html(specific_dir / f"{attr}.html")


# Now let's plot the beam per satellite results.
# We do it manually as PostProcessor does not support histograms yet.
# it doesn't matter from where get the results for that statistic.
results_num_beams_per_satellite = ResultsManager.load_many_from_dir(
    os.path.join(campaign_base_dir, f"{output_start}_ul"),
    only_latest=True,
    only_samples=["mss_d2d_num_beams_per_satellite"],
    filter_fn=(lambda dir_name: "output_mss_d2d_to_imt_cross_border_0km_service_grid_padded_50p" in dir_name)
)

mss_d2d_num_beams_per_satellite_attr = getattr(results_num_beams_per_satellite[0],
                                               "mss_d2d_num_beams_per_satellite", None)

if results_num_beams_per_satellite is not None:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=mss_d2d_num_beams_per_satellite_attr,
        nbinsx=15,
        histnorm='probability',
        marker_color='blue',
        opacity=0.75
    ))
    fig.update_layout(
        title="Number of Beams per Satellite Histogram",
        xaxis_title="Number of Beams per Satellite",
        yaxis_title="Frequency",
        # template="plotly_white",
        bargap=0.2,
    )
    fig.write_html(specific_dir / "mss_d2d_num_beams_per_satellite_hist.html")
    if auto_open:
        fig.show()
