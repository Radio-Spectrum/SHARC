import os
from sharc.plots.plot_cdf import all_plots

# Define the base directory
workfolder = os.path.dirname(os.path.abspath(__file__))
campaign_base_folder = workfolder.split("/")[-2]

# campaign_base_folder = "imt_hibs_ras_2600_MHz"

# This will include all subfolders that start with "output_imt_hibs_ras_2600_MHz_" in the f"{base_directory}/output/"
# and generate legends automatically based on the folder names

# Define legends and subfolders as None to include all automatically
all_plots(campaign_base_folder, legends=None, subfolders=None, save_file=False, show_plot=True)

# ALTERNATIVE: specify some folders and legends to plot

# Example with specific subfolders and legends

# Define legend names for the different subdirectories
# legends = ["0 Km", "45 Km", "90 Km", "500 Km"]

# Define specific subfolders if needed
# subfolders = [
#     "output_imt_hibs_ras_2600_MHz_0km_2024-07-30_01", 
#     "output_imt_hibs_ras_2600_MHz_45km_2024-07-30_01", 
#     "output_imt_hibs_ras_2600_MHz_90km_2024-07-30_01", 
#     "output_imt_hibs_ras_2600_MHz_500km_2024-07-30_01"
# ]

# Run the function with specific subfolders and legends
# all_plots(campaign_base_folder, legends=legends, subfolders=subfolders, save_file=False, show_plot=True)
