import os
from sharc.plots.plot_cdf import all_plots

# Define the base directory
name = "imt_hibs_ras_2600_MHz"

# this should behave similarly to `sharc/plots/plot_cdf:13`
# ideally the readable legend would be in the .ini metadata, so that we wouldn't need to do this here
workfolder = os.path.dirname(os.path.abspath(__file__))
csv_folder = os.path.abspath(os.path.join(workfolder, "..", "output"))

subdirs = [
    d
    for d in os.listdir(csv_folder)
    if os.path.isdir(os.path.join(csv_folder, d))
    and d.startswith(f"output_{name}_")
]


def get_date_from_dirname(dirname: str, prefix_length: int):
    return dirname[prefix_length : prefix_length + len("yyyy-mm-dd")]


legends_mapper = [
    {
        # same as from .ini
        # the legend should probably also be in the metadata there instead of making... this
        "output_dir_prefix": "output_imt_hibs_ras_2600_MHz_0km",
        "legend": "0 Km",
    },
    {
        "output_dir_prefix": "output_imt_hibs_ras_2600_MHz_45km",
        "legend": "45 Km",
    },
    {
        "output_dir_prefix": "output_imt_hibs_ras_2600_MHz_90km",
        "legend": "90 Km",
    },
    {
        "output_dir_prefix": "output_imt_hibs_ras_2600_MHz_500km",
        "legend": "500 Km",
    },
]

legend_and_subfolders = [
    {
        "legend": f"{mapped['legend']} ({get_date_from_dirname(d, 1 + len(mapped['output_dir_prefix']))})",
        "subfolder": d,
    }
    for d in subdirs
    for mapped in legends_mapper
    if mapped["output_dir_prefix"] in d
]

# Example with specific subfolders and legends
# Define legend names for the different subdirectories
# legends = None
legends = [x["legend"] for x in legend_and_subfolders]

# Define specific subfolders if needed
# subfolders = None
subfolders = [x["subfolder"] for x in legend_and_subfolders]

# Run the function with specific subfolders and legends
all_plots(
    name,
    legends=legends,
    subfolders=subfolders,
    save_file=False,
    show_plot=True,
)


# Example with all subfolders and no specific legends
# This will include all subfolders that start with "output_imt_hibs_ras_2600_MHz_" in the base directory
# and generate legends automatically based on the folder names

# Define legends and subfolders as None to include all automatically
# legends = None
# subpastas = None

# Run the function with all subfolders and auto-generated legends
# all_plots(name, legends=legends, subpastas=subpastas, save_file=True, show_plot=False)
