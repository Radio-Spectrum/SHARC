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

sistemas      = ["G04"]                       #["Sat_Q", "Sat_P"]
imt_cell      = ["macro"]                                #"macro", "micro"]
p_percentage  = ["RANDOM_CENARIO"]         # [20, "RANDOM", "RANDOM_CENARIO"]
clutter_type  = ["ter_OFF", "ter_ON"]                              # ["one_end", "both_ends"]
link_type     = ["dl"]                                 # ["ul", "dl"]
distances_km  = [140, 250]                                 # [5, 10, 50, 100]
#distances_km  = [30, 60] 
#distances_km  = [40, 80]

## Graphics adjustments
cutoff_percentage = 0.0001;
shift_scale = 0   # O padrão é dBm/MHz, porém é possível fazer o shift scale e atualizar a legenda
legenda_dens_potencia = "Interference Power [dBW/MHz]"


# Helper: pretty legend text
def pretty_p(p):
    return f"{(p)}%" if isinstance(p, (int, float)) else str(p)

def pretty_link(t):
    return t.upper()  # 'ul' -> 'UL', 'dl' -> 'DL'

def pretty_clutter(c):
    return "one end" if c == "one_end" else "both ends" if c == "both_ends" else c

# Build sorted combinations
combinations = [
    (s, a, b, c, d, e)
    for s in sorted(sistemas)
    for a in sorted(imt_cell)
    for b in sorted(p_percentage, key=lambda x: (0, x) if isinstance(x, (int, float)) else (1, str(x)))
    for c in sorted(clutter_type)
    for d in sorted(link_type)
    for e in sorted(distances_km)
]
valid_patterns = []
# Add patterns + legends
for s, a, b, c, d, e in combinations:
    # Directory name pattern (note: "cluter" as given in your template)
    dir_pattern = f"{a}_{s}_{d}_p_{b}_{c}_d_{e}km"
    valid_patterns.append(dir_pattern)

    # Nice legend
    legend = (
        f"{s}, "
        f"{pretty_clutter(c)}, D={int(e):03d} km"
    )
    post_processor.add_plot_legend_pattern(
        dir_name_contains=dir_pattern,
        legend=legend
    )

# Define filter function
filter_fn = lambda dir_path: any(
    pattern in os.path.basename(dir_path) for pattern in valid_patterns)

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

many_results = Results.load_many_from_dir(
    os.path.join(
        campaign_base_dir,
        "output"),
    only_latest=True,
    only_samples=[ "system_inr"],
    filter_fn=filter_fn
    )

post_processor.add_results(many_results)

plots = post_processor.generate_ccdf_plots_from_results(
    many_results, cutoff_percentage=cutoff_percentage, shift_scale=shift_scale
)

post_processor.add_plots(plots)

#### Add protection criteria

plots_to_add_vline = [
    "system_inr"]

for prop_name in plots_to_add_vline:
    plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type='ccdf')
    if plt:
        # Add vertical dashed line at x = -6
        plt.add_trace(
            go.Scatter(
                x=[-10.5, -10.5],
                y=[.2, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -10dB [20% of the time]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
        plt.add_trace(
            go.Scatter(
                x=[-7, -7],
                y=[.001, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -10dB [20% of the time]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
        plt.add_trace(
            go.Scatter(
                x=[-6, -6],
                y=[.0003, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -10dB [20% of the time]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )


# Plot every plot:
for plot in plots:
    plot.show()