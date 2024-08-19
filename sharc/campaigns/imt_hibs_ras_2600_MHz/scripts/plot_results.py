from sharc.plots.plot_cdf import all_plots

# Define the base directory
name = "imt_hibs_ras_2600_MHz"

# Example with specific subfolders and legends
# Define legend names for the different subdirectories
legends = ["0 Km", "45 Km", "90 Km", "500 Km"]

# Define specific subfolders if needed
subfolder = [
    "output_imt_hibs_ras_2600_MHz_0km_2024-07-30_01", 
    "output_imt_hibs_ras_2600_MHz_45km_2024-07-30_01", 
    "output_imt_hibs_ras_2600_MHz_90km_2024-07-30_01", 
    "output_imt_hibs_ras_2600_MHz_500km_2024-07-30_01"
]

# Run the function with specific subfolders and legends
all_plots(name, legends=legends, subfolder=subfolder, save_file=True, show_plot=False)

# Example with all subfolders and no specific legends
# This will include all subfolders that start with "output_imt_hibs_ras_2600_MHz_" in the base directory
# and generate legends automatically based on the folder names

# Define legends and subfolders as None to include all automatically
#legends = None
#subpastas = None

# Run the function with all subfolders and auto-generated legends
#all_plots(name, legends=legends, subpastas=subpastas, save_file=True, show_plot=False)
