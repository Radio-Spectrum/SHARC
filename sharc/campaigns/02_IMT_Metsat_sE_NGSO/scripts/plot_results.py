"""
Script for post-processing and plotting IMT HIBS RAS 2600 MHz simulation results.
Adds legends to result folders and generates plots using SHARC's PostProcessor.
"""
import os
from pathlib import Path
from sharc.results import Results
import plotly.graph_objects as go
from sharc.post_processor import PostProcessor

## Definition of plot variable (what to plot)
sistemas      = ["Sat_E&G", "Sat_C&S"] #["Sat_Q", "Sat_P"]
imt_cell      = ["micro"] #"macro", "micro"]
p_percentage  = [0.2, 20, "RANDOM_CENARIO"] # [20, "RANDOM", "RANDOM_CENARIO"]
clutter_type  = ["one_end"] # ["one_end", "both_ends"]
link_type     = ["dl"] # ["ul", "dl"]
distances_km  = [100, 200] # [5, 10, 50, 100]

## Graphics adjustments
cutoff_percentage = 0.00001;
shift_scale = 20   # O padrão é dBm/MHz, porém é possível fazer o shift scale e atualizar a legenda
legenda_dens_potencia = "Interference Power [dBW/10MHz]"

# Change default legent to the shifited
post_processor = PostProcessor()
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_dl_interf_power_per_mhz']['x_label'] = legenda_dens_potencia
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_ul_interf_power_per_mhz']['x_label'] = legenda_dens_potencia

# Helper: pretty legend text
def pretty_p(p):
    if p=="RANDOM_CENARIO": 
        p = "RANDOM"
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
    dir_pattern = f"{a}_{s}_link_{d}_p_{b}_cluter_{c}_dist_{e}km"
    valid_patterns.append(dir_pattern)

    # Nice legend
    legend = (
        f"{a}, sys={s}, link={pretty_link(d)}, "
        f"p={pretty_p(b)}, clutter={pretty_clutter(c)}, D={e} km"
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
    only_samples=["system_dl_interf_power_per_mhz"],
    filter_fn=filter_fn
    )

post_processor.add_results(many_results)

plots = post_processor.generate_ccdf_plots_from_results(
    many_results, cutoff_percentage=cutoff_percentage, shift_scale=shift_scale, legenda_dens_potencia=legenda_dens_potencia
)

post_processor.add_plots(plots)

#### Add protection criteria

plots_to_add_vline = [
    "system_dl_interf_power_per_mhz"
]

for prop_name in plots_to_add_vline:
    plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type='ccdf')
    if plt:
        # Add vertical dashed line at x = -6
        plt.add_trace(
            go.Scatter(
                x=[-148, -148],
                y=[cutoff_percentage, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -148dB/10MHz [20% of the time]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
        plt.add_trace(
            go.Scatter(
                x=[-127, -127],
                y=[cutoff_percentage, 1],
                mode="lines",
                line=dict(dash="dot", color="black"),
                name=" -127dB/MHz [0.0016% of the time]",
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
        plt.add_hline(
            y=0.000016,
            line_dash="dot",
            #annotation_text="TEst",
            #annotation_position="left",
            line_color="black"
        )
# Plot every plot:
for plot in plots:
    plot.show()