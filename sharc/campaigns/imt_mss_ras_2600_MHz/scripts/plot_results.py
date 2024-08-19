from sharc.plots.plot_cdf import all_plots

# Define the base directory
name = "imt_mss_ras_2600_MHz"

# Example with specific subfolders and legends
# Define legend names for the different subdirectories
legends = ["30 deg (P619)", "45 deg (P619)", "60 deg (P619)", "90 deg (P619)","30 deg (fspl)", "45 deg (fspl)", "60 deg (fspl)", "90 deg (fspl)"]
#legends = None
# Define specific subfolders if needed
subfolders = [
    "output_imt_mss_ras_2600_MHz_30deg_2024-08-15_01", 
    "output_imt_mss_ras_2600_MHz_45deg_2024-08-15_01", 
    "output_imt_mss_ras_2600_MHz_60deg_2024-08-15_01", 
    "output_imt_mss_ras_2600_MHz_90deg_2024-08-15_01",
    "output_imt_mss_ras_2600_MHz_fspl_30deg_2024-08-15_01", 
    "output_imt_mss_ras_2600_MHz_fspl_45deg_2024-08-15_01", 
    "output_imt_mss_ras_2600_MHz_fspl_60deg_2024-08-15_01", 
    "output_imt_mss_ras_2600_MHz_fspl_90deg_2024-08-15_01"
]
#subfolders = None
# Run the function with specific subfolders and legends
all_plots(name, legends=legends, subfolders=subfolders, save_file=False, show_plot=True)

# Example with all subfolders and no specific legends
# This will include all subfolders that start with "output_imt_hibs_ras_2600_MHz_" in the base directory
# and generate legends automatically based on the folder names

# Define legends and subfolders as None to include all automatically
#legends = None
#subpastas = None

# Run the function with all subfolders and auto-generated legends
#all_plots(name, legends=legends, subpastas=subpastas, save_file=True, show_plot=False)