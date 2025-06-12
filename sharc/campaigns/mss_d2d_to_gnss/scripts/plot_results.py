#!/usr/bin/env python3
import os
import webbrowser
from pathlib import Path

from sharc.post_processor import PostProcessor
from sharc.results import Results

auto_open = True  # Open plots in browser

# === Define base campaign directory ===
local_dir = os.path.dirname(os.path.abspath(__file__))
campaign_base_dir = str((Path(__file__) / ".." / "..").resolve())
output_dir = os.path.join(campaign_base_dir, "output")

# === Initialize post processor ===
post_processor = PostProcessor()

# === Load results for CCDFs ===
results_power_mhz = Results.load_many_from_dir(
    output_dir,
    filter_fn=lambda x: "mss_d2d_to_gnss" in x,
    only_latest=True,
    only_samples=["system_dl_interf_power_per_mhz"]
)

results_inr = Results.load_many_from_dir(
    output_dir,
    filter_fn=lambda x: "mss_d2d_to_gnss" in x,
    only_latest=True,
    only_samples=["system_inr"]
)

# Debug: Print how many samples were loaded
print("\nCCDF Samples Loaded:")
for res in results_inr:
    print(f"- {res.output_directory}: system_inr = {len(res.system_inr)}")
for res in results_power_mhz:
    print(f"- {res.output_directory}: system_dl_interf_power_per_mhz = {len(res.system_dl_interf_power_per_mhz)}")

# === Load CDF results ===
cdf_results = Results.load_many_from_dir(
    output_dir,
    filter_fn=lambda x: "mss_d2d_to_gnss" in x,
    only_latest=True,
    only_samples=[
        "imt_system_antenna_gain",
        "imt_system_path_loss",
        "system_dl_interf_power",
        "system_imt_antenna_gain",
    ]
)

# === Add legends by elevation angle ===
for elev in [5, 30, 60, 90]:
    post_processor.add_plot_legend_pattern(
        dir_name_contains=f"elev_{elev}_deg",
        legend=f"Elevation = {elev}°"
    )

# === Set line style ===
post_processor.add_results_linestyle_getter(lambda res: "solid")

# === Generate and add plots ===
post_processor.add_plots(post_processor.generate_ccdf_plots_from_results(results_inr))
post_processor.add_plots(post_processor.generate_ccdf_plots_from_results(results_power_mhz))
post_processor.add_plots(post_processor.generate_cdf_plots_from_results(cdf_results))

# === Add horizontal/vertical protection lines ===
perc_time = 0.01  # 1%

# For system_dl_interf_power_per_mhz
protection_criteria_mhz = -147.4  # dBW/MHz
ccdf_plot_mhz = post_processor.get_plot_by_results_attribute_name("system_dl_interf_power_per_mhz", plot_type="ccdf")
if ccdf_plot_mhz:
    ccdf_plot_mhz.add_vline(protection_criteria_mhz, line_dash="dash", annotation=dict(
        text="Protection Criteria: -147.4 dBW/MHz",
        x=protection_criteria_mhz + 0.5, y=0.8,
        font=dict(size=12, color="red")
    ))
    ccdf_plot_mhz.add_hline(perc_time, line_dash="dash", annotation=dict(
        text="Time Percentage: 1%",
        x=protection_criteria_mhz + 0.5, y=perc_time + 0.01,
        font=dict(size=12, color="blue")
    ))

# For system_inr
protection_criteria_inr = -6.0  # dB
ccdf_plot_inr = post_processor.get_plot_by_results_attribute_name("system_inr", plot_type="ccdf")
if ccdf_plot_inr:
    ccdf_plot_inr.add_vline(protection_criteria_inr, line_dash="dash", annotation=dict(
        text="INR Protection: -6 dB",
        x=protection_criteria_inr + 0.5, y=0.8,
        font=dict(size=12, color="red")
    ))
    ccdf_plot_inr.add_hline(perc_time, line_dash="dash", annotation=dict(
        text="Time Percentage: 1%",
        x=protection_criteria_inr + 0.5, y=perc_time + 0.01,
        font=dict(size=12, color="blue")
    ))

# === Attributes to export (only these will be saved/exported) ===
attributes_to_plot = [
    ("imt_system_antenna_gain", "cdf"),
    ("imt_system_path_loss", "cdf"),
    ("system_dl_interf_power", "cdf"),
    ("system_dl_interf_power_per_mhz", "ccdf"),
    ("system_imt_antenna_gain", "cdf"),
    ("system_inr", "ccdf"),
]

# === Export plots ===
for attr, plot_type in attributes_to_plot:
    fig = post_processor.get_plot_by_results_attribute_name(attr, plot_type=plot_type)
    if fig:
        file_path = os.path.join(output_dir, f"{attr}.html")
        fig.write_html(file=file_path, include_plotlyjs="cdn", auto_open=auto_open)

        # Open in browser if desired
        if auto_open and attr in ["system_inr", "system_dl_interf_power_per_mhz"]:
            webbrowser.open(f"file://{file_path}")
