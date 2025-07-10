"""Script to process and plot results for MSS D2D to IMT cross-border campaign."""

import os
from pathlib import Path
from sharc.results import Results
# import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

post_processor = PostProcessor()

# If set to True the plots will be opened in the browser automatically
auto_open = False

# Add a legend to results in folder that match the pattern
# This could easily come from a config file

prefixes = [
    "0km",
    "157.9km",
    "213.4km",
    "268.9km",
    "324.4km",
    "379.9km",
    "border"]
for link in ["dl", "ul"]:
    for prefix in prefixes:
        if prefix == "border":
            km = "0km"
        else:
            km = prefix
        post_processor\
            .add_plot_legend_pattern(
                dir_name_contains=f"{prefix}_base_" + link,
                legend=f"19 sectors ({km})"
            ).add_plot_legend_pattern(
                dir_name_contains=f"{prefix}_activate_random_beam_5p_" + link,
                legend=f"19 sectors, load=1/19 ({km})"
            ).add_plot_legend_pattern(
                dir_name_contains=f"{prefix}_activate_random_beam_30p_" + link,
                legend=f"19 sectors, load=30% ({km})"
            ).add_plot_legend_pattern(
                dir_name_contains=f"{prefix}_random_pointing_1beam_" + link,
                legend=f"1 sector random pointing ({km})"
            )

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

results_dl = Results.load_many_from_dir(
    os.path.join(
        campaign_base_dir,
        "output_base_dl"),
    only_latest=True)
results_ul = Results.load_many_from_dir(
    os.path.join(
        campaign_base_dir,
        "output_base_ul"),
    only_latest=True)
# ^: typing.List[Results]
all_results = [*results_ul, *results_dl]

post_processor.add_results(all_results)

# Define line styles for different prefixes - the size must match the
# number of unique legends
styles = ["solid", "dot", "dash", "longdash", "dashdot", "longdashdot"]


def linestyle_getter(result: Results):
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
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_inr", plot_type='ccdf')\
    .add_vline(protection_criteria, line_dash="dash", annotation=dict(
        text="Protection criteria",
        xref="x",
        yref="paper",
        x=protection_criteria + 1.0,  # Offset for visibility
        y=0.95
    ))
perc_of_time = 0.01
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_inr", plot_type="ccdf")\
    .add_hline(perc_of_time, line_dash="dash")
post_processor\
    .get_plot_by_results_attribute_name("imt_ul_inr", plot_type='ccdf')\
    .add_vline(protection_criteria, line_dash="dash", annotation=dict(
        text="Protection criteria",
        xref="x",
        yref="paper",
        x=protection_criteria + 1.0,  # Offset for visibility
        y=0.95
    ))
post_processor\
    .get_plot_by_results_attribute_name("imt_ul_inr", plot_type="ccdf")\
    .add_hline(perc_of_time, line_dash="dash")

# Add a protection criteria line:
pfd_protection_criteria = -109
post_processor\
    .get_plot_by_results_attribute_name("imt_dl_pfd_external_aggregated", plot_type='ccdf')\
    .add_vline(pfd_protection_criteria, line_dash="dash", annotation=dict(
        text="PFD protection criteria",
        xref="x",
        yref="paper",
        x=pfd_protection_criteria + 1.0,  # Offset for visibility
        y=0.95
    ))


attributes_to_plot = [
    # "imt_system_antenna_gain",
    # "system_imt_antenna_gain",
    # "sys_to_imt_coupling_loss",
    # "imt_system_path_loss",
    "imt_dl_pfd_external",
    "imt_dl_pfd_external_aggregated",
    "imt_dl_inr",
    "imt_ul_inr",
]

# Ensure the "htmls" directory exists relative to the script directory
htmls_dir = Path(__file__).parent / "htmls"
htmls_dir.mkdir(exist_ok=True)
for attr in attributes_to_plot:
    fig = post_processor.get_plot_by_results_attribute_name(
        attr, plot_type='ccdf')
    fig.update_layout(template="plotly_white")
    fig.write_html(
        htmls_dir / f"{attr}.html",
        include_plotlyjs="cdn",
        auto_open=auto_open)
