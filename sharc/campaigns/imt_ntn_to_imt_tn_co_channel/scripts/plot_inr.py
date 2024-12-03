import os
import numpy as np
from sharc.plots.plot_cdf import plot_cdf
import plotly.graph_objects as go

# Define the base directory
name = "imt_ntn_to_imt_tn_co_channel"
sat_altitude = 500  # km
beam_cell_radius = 19  # km

# sat_altitude = 500 # km
# beam_cell_radius  = 19 # km

# this should behave similarly to `sharc/plots/plot_cdf:13`
# ideally the readable legend would be in the .ini metadata and all this code would be deleted
workfolder = os.path.dirname(os.path.abspath(__file__))
csv_folder = os.path.abspath(os.path.join(workfolder, "..", "output"))

subdirs = [
    d
    for d in os.listdir(csv_folder)
    if os.path.isdir(os.path.join(csv_folder, d))
    and d.startswith(f"output_{name}_")
]

subdirs = sorted(subdirs)

scenarios = ['no_overlap', '10MHz_overlap', '20MHz_overlap']
# scenarios = ['no_overlap']
# distance from topology boarders in kms
border_distances_array = np.array(
    [0, 20, 50, 100, 200, 300, 400, 500, 600, 700, 1000])

legends_mapper = []
for i, s in enumerate(scenarios):
    for i, d in enumerate(border_distances_array):
        legends_mapper.append(
            {
                "output_dir_prefix": "output_imt_ntn_to_imt_tn_co_channel_" + s + "_alt_" + str(sat_altitude) + "km_sep_" + str(d) + "km",
                "legend": s + " - border dist: " + str(d) + " km"
            }
        )


def get_date_from_dirname(dirname: str, prefix_length: int):
    return dirname[prefix_length: prefix_length + len("yyyy-mm-dd")]


def get_id_from_dirname(dirname: str):
    return dirname.split("_")[-1]


subfolders_filters = {}

for subdir in subdirs:
    for mapper in legends_mapper:
        if mapper["output_dir_prefix"] in subdir:
            subfolders_filters\
                .setdefault(mapper["output_dir_prefix"], {"id": "0", "date": "2024-01-01"})

            subfolders_filters[mapper["output_dir_prefix"]]["id"] = max(
                subfolders_filters[mapper["output_dir_prefix"]]["id"],
                get_id_from_dirname(subdir)
            )
            subfolders_filters[mapper["output_dir_prefix"]]["date"] = max(
                subfolders_filters[mapper["output_dir_prefix"]]["date"],
                get_date_from_dirname(
                    subdir, 1 + len(mapper['output_dir_prefix']))
            )


legend_and_subfolders = [
    {
        # "legend": f"{mapper['legend']} - ({get_date_from_dirname(d, 1 + len(mapper['output_dir_prefix']))}) {get_id_from_dirname(d)}",
        "legend": f"{mapper['legend']}",
        "subfolder": d,
    }
    for d in subdirs
    for mapper in legends_mapper
    if mapper["output_dir_prefix"] in d
    # comment filters out if needed
    and subfolders_filters[mapper["output_dir_prefix"]]["id"] == get_id_from_dirname(d)
    and subfolders_filters[mapper["output_dir_prefix"]]["date"] == get_date_from_dirname(d, len(mapper["output_dir_prefix"]) + 1)
]

# Example with specific subfolders and legends
# Define legend names for the different subdirectories
# legends = None
legends = [x["legend"] for x in legend_and_subfolders]

# Define specific subfolders if needed
# subfolders = None
subfolders = [x["subfolder"] for x in legend_and_subfolders]

# Run the function with specific subfolders and legends
fig = plot_cdf(name,
               'IMT_CDF_of_DL_interference-to-noise_ratio',
               passo_xticks=5,
               xaxis_title='INR (dB)',
               legends=legends,
               subfolders=subfolders,
               save_file=False,
               show_plot=False
               )
inr_crit_db = np.array(np.repeat([-6], 4))
inr_crit_y = np.array([0, 0.25, 0.5, 1.0])
fig.add_trace(go.Scatter(x=inr_crit_db, y=inr_crit_y, mode='lines',
              marker=dict(color='black'), name=f'I/N criteria'))
# Graph configurations
fig.update_layout(
    title=f'INR [dB] - Satellite altitude {
        sat_altitude}km - beam cell radius {beam_cell_radius}km',
    xaxis_title='INR (dB)',
    yaxis_title='Prob of INR < X%',
    # yaxis=dict(tickmode='array', tickvals=[0, 0.25, 0.5, 0.75, 1]),
    # xaxis=dict(tickmode='linear', tick0=global_min, dtick=passo_xticks),
    legend_title="Labels"
)
fig.show()

fig = plot_cdf(
    name,
    'SYS_CDF_of_IMT_to_system_path_loss',
    passo_xticks=5,
    xaxis_title='Path Loss (dB)',
    legends=legends,
    subfolders=subfolders,
    save_file=False,
    show_plot=False
)
fig.update_layout(
    title=f'NTN-BS to IMT-TN Path Loss [dB] - - Satellite altitude {
        sat_altitude}km - beam cell radius {beam_cell_radius}km',
    xaxis_title='PL (dB)',
    yaxis_title='Prob of PL < X%',
    # yaxis=dict(tickmode='array', tickvals=[0, 0.25, 0.5, 0.75, 1]),
    # xaxis=dict(tickmode='linear', tick0=global_min, dtick=passo_xticks),
    legend_title="Labels"
)
# fspl = np.array([160.74, 160.76, 160.78, 160.82, 160.96, 161.15, 161.38, 161.65, 161.95, 162.27])
# for i, pl in enumerate(fspl):
#     yval = np.array([0, .25, .5, 1.])
#     xval = np.repeat(pl, yval.shape)
#     # fig.plot(yval, xval)
#     fig.add_trace(go.Scatter(x=xval, y=yval, mode='lines', name=f'FSPL'))


fig.show()

fig = plot_cdf(
    name,
    'IMT_CDF_of_system_PFD_to_IMT_DL',
    passo_xticks=5,
    xaxis_title='PFD (dB/m^2)',
    legends=legends,
    subfolders=subfolders,
    save_file=False,
    show_plot=False
)
fig.update_layout(
    title=f'NTN-BS to IMT-TN PFD (dB/m^2) - Satellite altitude {
        sat_altitude}km - beam cell radius {beam_cell_radius}km',
    xaxis_title='PFD (dB/m^2)',
    yaxis_title='Prob of PFD < X%',
    # yaxis=dict(tickmode='array', tickvals=[0, 0.25, 0.5, 0.75, 1]),
    # xaxis=dict(tickmode='linear', tick0=global_min, dtick=passo_xticks),
    legend_title="Labels"
)

fig.show()
# Example with all subfolders and no specific legends
# This will include all subfolders that start with "output_imt_hibs_ras_2600_MHz_" in the base directory
# and generate legends automatically based on the folder names

# Define legends and subfolders as None to include all automatically
# legends = None
# subpastas = None

# Run the function with all subfolders and auto-generated legends
# all_plots(name, legends=legends, subpastas=subpastas, save_file=True, show_plot=False)
