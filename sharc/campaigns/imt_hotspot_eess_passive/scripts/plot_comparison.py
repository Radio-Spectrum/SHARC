# TODO: refactor this with new post processing script

import os
import pandas as pd
import plotly.graph_objects as go

# Define the base directory
name = "imt_hotspot_eess_passive"

# code adapted from import: from sharc.plots.plot_cdf import plot_cdf
def plot_comparison(base_dir, file_prefix, passo_xticks=5, xaxis_title='Value', legends=None, subfolders=None, save_file=True, show_plot=False):
    
    label='CDF'
    # Ensure at least one of save_file or show_plot is true
    if not save_file and not show_plot:
        raise ValueError("Either save_file or show_plot must be True.")

    workfolder = os.path.dirname(os.path.abspath(__file__))
    csv_folder = os.path.abspath(os.path.join(workfolder, '..', "output"))
    figs_folder = os.path.abspath(os.path.join(workfolder, '..', "output", "figs"))

    # Check if the figs output folder exists, if not, create it
    if not os.path.exists(figs_folder):
        os.makedirs(figs_folder)
    
    comparison_folder = os.path.abspath(os.path.join(workfolder, '..', "comparison"))
    subdirs = [comparison_folder]
    # legends = []
    # List all subfolders in the base directory or only those specified by the user
    if subfolders:
        subdirs += [os.path.join(csv_folder, d) for d in subfolders if os.path.isdir(os.path.join(csv_folder, d))]
    else:
        subdirs += [os.path.join(csv_folder, d) for d in os.listdir(csv_folder) 
                   if os.path.isdir(os.path.join(csv_folder, d)) and d.startswith(f"output_{base_dir}_")]
    
    # Validate the number of legends
    # if legends and len(legends) != len(subdirs):
    #     raise ValueError("The number of provided legends does not match the number of found subfolders.")

    # Initialize global min and max values
    global_min = float('inf')
    global_max = float('-inf')


    # First, calculate the global min and max values
    for subdir in subdirs:
        all_files = [f for f in os.listdir(subdir) if f.endswith('.csv') and label in f and file_prefix in f]
        if subdir == comparison_folder:
            all_files = ["Fig. 8 EESS (Passive) Sensor.csv","Fig. 15 (IMT Uplink) EESS (Passive) Sensor", "aggregate-interference-1-cluster-0.25-TDD.csv"]

        for file_name in all_files:
            file_path = os.path.join(subdir, file_name)
            if os.path.exists(file_path):
                try:
                    # Try reading the .csv file using pandas with different delimiters
                    try:
                        data = pd.read_csv(file_path, delimiter=',', skiprows=1)
                    except:
                        data = pd.read_csv(file_path, delimiter=';', skiprows=1)
                    
                    # Ensure the data has at least two columns
                    if data.shape[1] < 2:
                        print(f"The file {file_name} does not have enough columns to plot.")
                        continue

                    # Remove rows that do not contain valid numeric values
                    data = data.apply(pd.to_numeric, errors='coerce').dropna()
                    
                    if not data.empty:
                        global_min = min(global_min, data.iloc[:, 0].min())
                        global_max = max(global_max, data.iloc[:, 0].max())
                except Exception as e:
                    print(f"Error processing the file {file_name}: {e}")

    # If no valid data was found, set reasonable defaults for global_min and global_max
    if global_min == float('inf') or global_max == float('-inf'):
        global_min, global_max = 0, 1
    # print(subdirs)
    # Plot the graphs adjusting the axes
    fig = go.Figure()
    for idx, subdir in enumerate(subdirs):
        all_files = [f for f in os.listdir(subdir) if f.endswith('.csv') and label in f and file_prefix in f]
        if subdir == comparison_folder:
            all_files = ["Fig. 8 EESS (Passive) Sensor.csv", "Fig. 15 (IMT Uplink) EESS (Passive) Sensor.csv", "aggregate-interference-1-cluster-0.25-TDD.csv"]
        legenda = legends[idx] if legends and len(legends) > idx else os.path.basename(subdir)
        for file_name in all_files:
            if file_name == "Fig. 8 EESS (Passive) Sensor.csv":
                legenda = "Fig. 8 EESS (Passive) Sensor"
            elif "aggregate-interference-1-cluster-0.25-TDD" in file_name:
                legenda = "Aggregate Interference"
            elif "Fig. 15 (IMT Uplink) EESS (Passive) Sensor" in file_name:
                legenda = "Fig. 15 (IMT Uplink) EESS (Passive) Sensor"
            else:
                # print(file_name)
                legenda = legends[idx] if legends and len(legends) > idx else os.path.basename(subdir)

            file_path = os.path.join(subdir, file_name)
            if os.path.exists(file_path):
                try:
                    # Try reading the .csv file using pandas with different delimiters
                    try:
                        data = pd.read_csv(file_path, delimiter=',', skiprows=1)
                    except:
                        data = pd.read_csv(file_path, delimiter=';', skiprows=1)
                    
                    # Ensure the data has at least two columns
                    if data.shape[1] < 2:
                        print(f"The file {file_name} does not have enough columns to plot.")
                        continue

                    # Remove rows that do not contain valid numeric values
                    data = data.apply(pd.to_numeric, errors='coerce').dropna()
                    
                    # Check if there are enough data points to plot
                    if data.empty or data.shape[0] < 2:
                        print(f"The file {file_name} does not have enough data to plot.")
                        continue
                    if legenda.startswith("Fig. 8 EESS (Passive) Sensor") or legenda.startswith("Fig. 15 (IMT Uplink) EESS (Passive) Sensor"):
                        # invert (1 - CDF) y axis used on fig 8 and 15:
                        data.iloc[:, 1] = (1 - data.iloc[:, 1])
                    elif legenda.startswith("Aggregate Interference"):
                        pass
                    else:
                        # transform dBm to dB:
                        data.iloc[:, 0] = data.iloc[:, 0] - 30
                    # data.iloc[:, 1] = (1 - data.iloc[:, 1])
                        
                    # Plot the CDF
                    fig.add_trace(go.Scatter(x=data.iloc[:, 0], y=data.iloc[:, 1], mode='lines', name=f'{legenda}'))
                except Exception as e:
                    print(f"Error processing the file {file_name}: {e}")
            else:
                print(f"WTF: {file_path}")
    
    # Graph configurations
    fig.update_layout(
        title=f'CDF Plot for {file_prefix}',
        xaxis_title='dBW/MHz',
        yaxis_title='CDF',
        yaxis=dict(tickmode='array', tick0=0, dtick=0.25),
        xaxis=dict(tickmode='linear', tick0=global_min, dtick=passo_xticks),
        legend_title="Labels"
    )
    
    # Show the figure if requested
    if show_plot:
        fig.show()
    
    # Save the figure if requested
    if save_file:
        fig_file_path = os.path.join(figs_folder, f"CDF_Plot_{file_prefix}.png")
        fig.write_image(fig_file_path)
        print(f"Figure saved: {fig_file_path}")


plot_comparison(name, 'SYS_CDF_of_system_interference_power_from_IMT_DL', 5, xaxis_title='Interference Power (dB/MHz)', legends=None, subfolders=None, save_file=False, show_plot=True)

plot_comparison(name, 'SYS_CDF_of_system_interference_power_from_IMT_UL', 5, xaxis_title='Interference Power (dB/MHz)', legends=None, subfolders=None, save_file=False, show_plot=True)
