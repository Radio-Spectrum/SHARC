from sharc.plots.plot_cdf import all_plots

# Define the base directory
name = "imt_hotspot_eess_passive"

# Run the function with specific subfolders and legends
all_plots(
    name,
    legends=None,
    subfolders=None,
    save_file=False,
    show_plot=True,
)
