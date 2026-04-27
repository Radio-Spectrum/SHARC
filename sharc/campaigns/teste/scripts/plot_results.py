"""
Script for post-processing and plotting IMT HIBS RAS 2600 MHz simulation results.
Adds legends to result folders and generates plots using SHARC's PostProcessor.
"""
import os
from pathlib import Path
from sharc.results import Results
import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

post_processor = PostProcessor()
heights = [40]  # meters
azis = [90, 180]  # degrees
lfs = [0.2, 0.5]  # fraction (20%, 50%)
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
cutoff_percentage=0.001
plots = post_processor.generate_ccdf_plots_from_results(
    many_results, cutoff_percentage=cutoff_percentage
)
post_processor.add_plots(plots)


#### Add protection criteria

plots_to_add_vline = [
    "system_inr"
]

for prop_name in plots_to_add_vline:
    plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type='ccdf')
    if plt:
        # Add vertical dashed line at x = -6
        plt.add_trace(
            go.Scatter(
                x=[-6, -6],
                y=[cutoff_percentage, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -6dB [20% of the time]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
        # Add horizontal dashed line at y = 0.2
        plt.add_hline(
            y=0.2,
            line_dash="dash",
            #annotation_text="TEst",
            #annotation_position="left",
            line_color="black"
        )


# Plot every plot:
for plot in plots:
    plot.show()