"""
Script for post-processing and plotting IMT HIBS RAS 2600 MHz simulation results.
Adds legends to result folders and generates plots using SHARC's PostProcessor.
"""
import os
from pathlib import Path
from sharc.results import Results
import plotly.graph_objects as go
from sharc.post_processor import PostProcessor
import numpy as np  # <- garantir esse import no topo


## Definition of plot variable (what to plot)
n_array = [4, 8]
N = 31                 # número de pontos/distâncias
max_dist_km = 30000    # distância máxima ao centro da pista (km)
aux = (np.linspace(0, max_dist_km, N))
distances_km = [int(val) for val in aux]
#distances_km = [10714]

## Graphics adjustments
cutoff_percentage = 0.001;
shift_scale = -10 * np.log10(6000 / (3 * 57)) - 6   # Segment Factor + Filtro
legenda_INR_potencia = "INR [dB]"
legenda_dens_potencia = "dBm"

# Change default legent to the shifited
post_processor = PostProcessor()
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_inr']['x_label'] = legenda_dens_potencia
post_processor.RESULT_FIELDNAME_TO_PLOT_INFO['system_dl_interf_power_per_mhz']['x_label'] = legenda_dens_potencia

# Build sorted combinations
combinations = [
    (a,s)
    for s in sorted(distances_km)
    for a in sorted(n_array)
]
valid_patterns = []
# Add them in sorted order
for a, s in (combinations):
    post_processor.add_plot_legend_pattern(
        dir_name_contains=f"{a}_approach_{s}m",
        legend=f"N={a} d ={s}m"
    )
    valid_patterns.append(f"{a}_approach_{s}m")


# Define filter function
filter_fn = lambda dir_path: any(
    pattern in os.path.basename(dir_path) for pattern in valid_patterns)

campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())

many_results = Results.load_many_from_dir(
    os.path.join(
        campaign_base_dir,
        "output_dl"),
    only_latest=True,
    only_samples=["imt_system_antenna_gain", "imt_bs_antenna_gain", "system_imt_antenna_gain", "imt_system_path_loss","system_dl_interf_power_per_mhz"],
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
]

for prop_name in plots_to_add_vline:
    plt = post_processor.get_plot_by_results_attribute_name(prop_name, plot_type='ccdf')
    if plt:
        # Add vertical dashed line at x = -6
        plt.add_trace(
            go.Scatter(
                x=[-36, -36],
                y=[cutoff_percentage, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -36 dB/100MHz [Cat 1]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
        # Add vertical dashed line at x = -6
        plt.add_trace(
            go.Scatter(
                x=[-74, -74],
                y=[cutoff_percentage, 1],
                mode="lines",
                line=dict(dash="dash", color="black"),
                name=" -74dB/100MHz [Cat 2&3]",
                hoverinfo="skip",    # avoids mouse hover box on the guide line
                showlegend=True      # make sure it appears in the legend
            )
        )
# Plot every plot:
for plot in plots:
    plot.show()