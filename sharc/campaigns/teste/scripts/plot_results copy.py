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
sistemas      = ["System_340km"]
system_EESS      = ["System_B", "System_D"] 
type_adj  = ["spurious", "adjacent"] 
load_factor  = [.2, .5]


## Graphics adjustments
cutoff_percentage = 0.001;
shift_scale = 30   # O padrão é dBm/MHz, porém é possível fazer o shift scale e atualizar a legenda
legenda_dens_potencia = "Interference Power [dBW/MHz]"

# Change default legent to the shifited
post_processor = PostProcessor()
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_dl_interf_power_per_mhz']['x_label'] = legenda_dens_potencia
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_ul_interf_power_per_mhz']['x_label'] = legenda_dens_potencia

# Build sorted combinations
combinations = [
    (s, a, c, d)
    for s in sorted(sistemas)
    for a in sorted(system_EESS)
    for c in sorted(type_adj)
    for d in sorted(load_factor)
]
valid_patterns = []
# Add patterns + legends
for s, a, c, d in combinations:
    # Directory name pattern (note: "cluter" as given in your template)
    dir_pattern = f"to_eess_{s}_altant_{a}m_azi_{c}deg_lf_{d}"
    valid_patterns.append(dir_pattern)

    # Nice legend
    legend = (
        f"{a}, sys={s}, EESS={a}, "
        f"LF={d}%, AC = {c}"
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
    only_samples=["system_dl_interf_power_per_mhz","system_ul_interf_power_per_mhz"],
    filter_fn=filter_fn
    )

post_processor.add_results(many_results)

plots = post_processor.generate_ccdf_plots_from_results(
    many_results, cutoff_percentage=cutoff_percentage, shift_scale=shift_scale, legenda_dens_potencia=legenda_dens_potencia
)

post_processor.add_plots(plots)

#### Add protection criteria

plots_to_add_vline = [
    "system_dl_interf_power_per_mhz",
    "system_ul_interf_power_per_mhz"
]

for prop_name in plots_to_add_vline:
    plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type='ccdf')
    if plt:
        # Add vertical dashed line at x = -6
        plt.add_trace(
            go.Scatter(
                x=[-155, -155],
                y=[cutoff_percentage, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -148dB/10MHz [20% of the time]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
        # Add horizontal dashed line at y = 0.2
        plt.add_hline(
            y=0.01,
            line_dash="dash",
            #annotation_text="TEst",
            #annotation_position="left",
            line_color="black"
        )
# Plot every plot:
for plot in plots:
    plot.show()