"""Script to process and plot results for MSS D2D to IMT cross-border campaign."""

import os
from pathlib import Path
from sharc.results import Results
# import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

import argparse

parser = argparse.ArgumentParser(
    description="You may plot the results for the different channel configs"
)

parser.add_argument('--channel', type=str, required=True, choices=["co", "adj"],
    help='Set the channel to generate the parameters ("co" for cochannel or "adj" for adjacent channel)'
)

parser.add_argument('--freq', type=str, required=True, choices=["~0.8G", "~2.1G"],
    help='Set the frequency to generate the parameters ("~0.8G" or "~2.1G")'
)

args = parser.parse_args()

selected_str = f"{args.freq}_{args.channel}"

output_start = f"output_{selected_str}"

post_processor = PostProcessor()

# Add a legend to results in folder that match the pattern
# This could easily come from a config file

cell_radius = 113630 if args.freq == "~0.8G" else 39475
cell_radius /= 1e3

country_border = 4 * cell_radius
dists = sorted([
    0,
    cell_radius,
    # cell_radius + 111,
    cell_radius + 2 * 111,
    country_border,
    # country_border + 111,
    country_border + 2 * 111,
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
            legend=f"1 sector random pointn ({km})"
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
    "imt_ul_inr",
]

results_dl = Results.load_many_from_dir(os.path.join(campaign_base_dir, f"{output_start}_dl"), only_latest=True, only_samples=attributes_to_plot)
# print("len(results_dl)", len(results_dl))
# for i in range(len(results_dl)):
#     print(results_dl[i].imt_dl_inr)
# exit()
results_ul = Results.load_many_from_dir(os.path.join(campaign_base_dir, f"{output_start}_ul"), only_latest=True, only_samples=attributes_to_plot)
# print("len(results_ul)", len(results_ul))
# ^: typing.List[Results]
all_results = [*results_ul, *results_dl]

post_processor.add_results(all_results)

styles = ["solid", "longdash", "dash", "longdashdot", "dashdot", "dot"]


def linestyle_getter(result: Results):
    """
    Returns a line style string based on the prefix found in the result's output directory.
    """
    for i in range(len(prefixes)):
        if prefixes[i] in result.output_directory:
            return styles[i]
    return "solid"


post_processor.add_results_linestyle_getter(linestyle_getter)

plots = post_processor.generate_cdf_plots_from_results(
    all_results
)

post_processor.add_plots(plots)

# Add a protection criteria line:
protection_criteria = -6
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_inr")\
    .add_vline(protection_criteria, line_dash="dash")

post_processor\
    .get_plot_by_results_attribute_name("imt_ul_inr")\
    .add_vline(protection_criteria, line_dash="dash")

# Add a protection criteria line:
pfd_protection_criteria = -109
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_pfd_external_aggregated")\
    .add_vline(pfd_protection_criteria, line_dash="dash")

post_processor\
    .get_plot_by_results_attribute_name("imt_dl_pfd_external")\
    .add_vline(pfd_protection_criteria, line_dash="dash")

for attr in attributes_to_plot:
    post_processor.get_plot_by_results_attribute_name(attr).show()

# Ensure the "htmls" directory exists relative to the script directory
# output_dir = Path(__file__).parent / "../output"
# output_dir.mkdir(exist_ok=True)
# htmls_dir = output_dir / "htmls"
# htmls_dir.mkdir(exist_ok=True)
# specific_dir = htmls_dir / selected_str
# specific_dir.mkdir(exist_ok=True)
# # print("specific_dir", specific_dir)

# for attr in attributes_to_plot:
#     post_processor\
#         .get_plot_by_results_attribute_name(attr)\
#         .write_html(specific_dir / f"{attr}.html")
