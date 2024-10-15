import os
import pandas as pd
import plotly.graph_objects as go
import re
from sharc.plot import Plot
import numpy as np

class PlotGenerator:

    def __init__(self, name: str, save_file=False, show_plot=True, subfolders=None):
        
        self.name = name

        # Define the base directory dynamically based on user input
        self.workfolder = os.path.dirname(os.path.abspath(__file__))
        self.csv_folder = os.path.abspath(os.path.join(self.workfolder, '..', "campaigns", name, "output",))
        self.figs_folder = os.path.abspath(os.path.join(self.workfolder, '..', "campaigns", name, "output", "figs"))


        self.save_file = save_file
        self.show_plot = show_plot

        # Ensure at least one of save_file or show_plot is true
        if not self.save_file and not self.show_plot:
            raise ValueError("Either save_file or show_plot must be True.")

        self.subfolders = subfolders
        self.plot_list = []

        # Check if the figs output folder exists, if not, create it
        if not os.path.exists(self.figs_folder):
            os.makedirs(self.figs_folder)

        self.decide_simulated_variables()

        self.plot_configurations = {
            'system_imt_antenna_gain': {
                'x_label': 'Antenna gain [dBi]',
                'y_label_cdf': 'Probability of antenna gain < $X$',
                'title': '[SYS] system antenna gain towards IMT stations',
            },
            'imt_system_antenna_gain': {
                'x_label': 'Antenna gain [dBi]',
                'y_label_cdf': 'Probability of antenna gain < $X$',
                'title': '[IMT] IMT station antenna gain towards system',
            },
            'imt_system_path_loss': {
                'x_label': 'Path Loss [dB]',
                'y_label_cdf': 'Probability of path loss < $X$',
                'title': '[SYS] IMT to system path loss',
            },
            'imt_system_build_entry_loss': {
                'x_label': 'Building entry loss [dB]',
                'y_label_cdf': 'Probability of loss < $X$',
                'title': '[SYS] IMT to system building entry loss',
            },
            'imt_system_diffraction_loss': {
                'x_label': 'Building entry loss [dB]',
                'y_label_cdf': 'Probability of loss < $X$',
                'title': '[SYS] IMT to system diffraction loss',
            },
            'imt_bs_antenna_gain': {
                'x_label': 'Antenna gain [dBi]',
                'y_label_cdf': 'Probability of antenna gain < $X$',
                'title': '[IMT] BS antenna gain towards the UE',
            },
            'imt_ue_antenna_gain': {
                'x_label': 'Antenna gain [dBi]',
                'y_label_cdf': 'Probability of antenna gain < $X$',
                'title': '[IMT] UE antenna gain towards the BS',
            },
            'imt_ul_tx_power_density': {
                'x_label': 'Transmit power density [dBm/Hz]',
                'y_label_cdf': 'Probability of transmit power density < $X$',
                'title': '[IMT] UE transmit power density',
            },
            'imt_ul_tx_power': {
                'x_label': 'Transmit power [dBm]',
                'y_label_cdf': 'Probability of transmit power < $X$',
                'title': '[IMT] UE transmit power',
            },
            'imt_ul_sinr_ext': {
                'x_label': 'SINR [dB]',
                'y_label_cdf': 'Probability of SINR < $X$',
                'title': '[IMT] UL SINR with external interference',
            },
            'imt_ul_sinr': {
                'x_label': 'SINR [dB]',
                'y_label_cdf': 'Probability of SINR < $X$',
                'title': '[IMT] UL SINR',
            },
            'imt_ul_snr': {
                'x_label': 'SNR [dB]',
                'y_label_cdf': 'Probability of SNR < $X$',
                'title': '[IMT] UL SNR',
            },
            'imt_ul_inr': {
                'x_label': '$I/N$ [dB]',
                'y_label_cdf': 'Probability of $I/N$ < $X$',
                'title': '[IMT] UL interference-to-noise ratio',
            },
            'imt_ul_tput_ext': {
                'x_label': 'Throughput [bits/s/Hz]',
                'y_label_cdf': 'Probability of UL throughput < $X$',
                'title': '[IMT] UL throughput with external interference',
            },
            'imt_ul_tput': {
                'x_label': 'Throughput [bits/s/Hz]',
                'y_label_cdf': 'Probability of UL throughput < $X$',
                'title': '[IMT] UL throughput',
            },
            'imt_path_loss': {
                'x_label': 'Path loss [dB]',
                'y_label_cdf': 'Probability of path loss < $X$',
                'title': '[IMT] path loss',
            },
            'imt_coupling_loss': {
                'x_label': 'Coupling loss [dB]',
                'y_label_cdf': 'Probability of coupling loss < $X$',
                'title': '[IMT] coupling loss',
            },
            'imt_dl_tx_power': {
                'x_label': 'Transmit power [dBm]',
                'y_label_cdf': 'Probability of transmit power < $X$',
                'title': '[IMT] DL transmit power',
            },
            'imt_dl_sinr_ext': {
                'x_label': 'SINR [dB]',
                'y_label_cdf': 'Probability of SINR < $X$',
                'title': '[IMT] DL SINR with external interference',
            },
            'imt_dl_sinr': {
                'x_label': 'SINR [dB]',
                'y_label_cdf': 'Probability of SINR < $X$',
                'title': '[IMT] DL SINR',
            },
            'imt_dl_snr': {
                'x_label': 'SNR [dB]',
                'y_label_cdf': 'Probability of SNR < $X$',
                'title': '[IMT] DL SNR',
            },
            'imt_dl_inr': {
                'x_label': '$I/N$ [dB]',
                'y_label_cdf': 'Probability of $I/N$ < $X$',
                'title': '[IMT] DL interference-to-noise ratio',
            },
            'imt_dl_tput_ext': {
                'x_label': 'Throughput [bits/s/Hz]',
                'y_label_cdf': 'Probability of throughput < $X$',
                'title': '[IMT] DL throughput with external interference',
            },
            'imt_dl_tput': {
                'x_label': 'Throughput [bits/s/Hz]',
                'y_label_cdf': 'Probability of throughput < $X$',
                'title': '[IMT] DL throughput',
            },
            'system_inr': {
                'x_label': 'INR [dB]',
                'y_label_cdf': 'Probability of INR < $X$',
                'title': '[SYS] system INR',
            },
            'system_pfd': {
                'x_label': 'PFD [dBm/m^2]',
                'y_label_cdf': 'Probability of INR < $X$',
                'title': '[SYS] system PFD',
            },
            'system_ul_interf_power': {
                'x_label': 'Interference Power [dBm]',
                'y_label_cdf': 'Probability of Power < $X$',
                'title': '[SYS] system interference power from IMT UL',
            },
            'system_dl_interf_power': {
                'x_label': 'Interference Power [dBm/MHz]',
                'y_label_cdf': 'Probability of Power < $X$',
                'title': '[SYS] system interference power from IMT DL',
            }
        }


    def plot_title_to_filename(self, title: str):
        """
        Creates the file name from the graph titles by removing spaces and brackets.
        """
        return re.sub(r'[\[\]]', "", title).replace(" ", "_")
    
    def cdf(self, data, file_name, bins=1000):
        """
        Compute the CDF of a given data.
        """
        values, base = np.histogram(data, bins=bins)
        cumulative = np.cumsum(values)
        x = base[:-1]
        y = cumulative / cumulative[-1]
        x_label = self.plot_configurations[file_name]['x_label']
        y_label = self.plot_configurations[file_name]['y_label_cdf']
        title = "CDF of " + self.plot_configurations[file_name]['title']
        f_name = self.plot_title_to_filename(title)
        return Plot(x, y, x_label, y_label, title, f_name)
    
    def hist(self, data, file_name, bins=50):
        """
        Compute the histogram of a given data.
        """
        values, base = np.histogram(data, bins=bins, density=True)
        x = base[:-1]
        y = values
        x_label = self.plot_configurations[file_name]['x_label']
        y_label = '$n^o$'
        title = "Histogram of " + self.plot_configurations[file_name]['title']
        f_name = self.plot_title_to_filename(title)
        return Plot(x, y, x_label, y_label, title, f_name)
    
    def decide_simulated_variables(self):
        """
        List all csv files found for simulated variables.
        """
        if self.subfolders:
            self.subdirs = [os.path.join(self.csv_folder, d) for d in self.subfolders if os.path.isdir(os.path.join(self.csv_folder, d))]
        else:
            self.subdirs = [os.path.join(self.csv_folder, d) for d in os.listdir(self.csv_folder) 
                    if os.path.isdir(os.path.join(self.csv_folder, d)) and d.startswith(f"output_{self.name}_")]
            

    def generate_fig(self, plot_data: Plot):
        """
        Generate the figure based on the plot configurations.
        """
        fig = go.Figure()
        try:
            fig.add_trace(go.Scatter(x=plot_data.x, y=plot_data.y, mode='lines', name=plot_data.title))
        except Exception as e:
            print(f"Error adding the trace to the figure: {e}")
            raise e

        # Graph configurations
        fig.update_layout(
            title=f"Plot for {plot_data.title}",
            xaxis_title=plot_data.x_label,
            yaxis_title=plot_data.y_label,
            yaxis=dict(tickmode='array', tickvals=[0, 0.25, 0.5, 0.75, 1]),
            xaxis=dict(tickmode='linear', tick0=plot_data.x.min(), dtick=5),
            legend_title="Labels"
        )

        # Show the figure if requested
        if self.show_plot:
            fig.show()

        # Save the figure if requested
        if self.save_file:
            fig_file_path = os.path.join(self.figs_folder, f"Plot_{plot_data.file_name}.png")
            fig.write_image(fig_file_path)
            print(f"Figure saved: {fig_file_path}")
    
    def plot_cdf(self):
        """
        Compute the CDF of a given simulation variable.
        """
        for subdir in self.subdirs:
            subdir = os.path.join(subdir, 'raw_data_dir')
            all_files = [f for f in os.listdir(subdir) if f.endswith('.csv')]

            for file_name in all_files:
                file_path = os.path.join(subdir, file_name)
                if os.path.exists(file_path):
                    try:
                        # Try reading the .csv file using pandas with different delimiters
                        try:
                            data = pd.read_csv(file_path, delimiter=',')
                        except:
                            data = pd.read_csv(file_path, delimiter=';')
                        
                        # Plot the CDF
                        plot_data = self.cdf(data, file_name.split('.')[0])
                        self.plot_list.append(plot_data)
                    except Exception as e:
                        print(f"Error processing the file {file_name}: {e}")

    def plot_hist(self):
        """
        Compute the PDF of a given simulation variable.
        """
        for subdir in self.subdirs:
            subdir = os.path.join(subdir, 'raw_data_dir')
            all_files = [f for f in os.listdir(subdir) if f.endswith('.csv')]

            for file_name in all_files:
                file_path = os.path.join(subdir, file_name)
                if os.path.exists(file_path):
                    try:
                        # Try reading the .csv file using pandas with different delimiters
                        try:
                            data = pd.read_csv(file_path, delimiter=',')
                        except:
                            data = pd.read_csv(file_path, delimiter=';')
                        
                        # Plot the PDF
                        plot_data = self.hist(data, file_name.split('.')[0])
                        self.plot_list.append(plot_data)
                    except Exception as e:
                        print(f"Error processing the file {file_name}: {e}")


    def generate_plots(self):
        """
        Generate the plots based on the plot list.
        """

        # Plot the graphs adjusting the axes
        for plot_data in self.plot_list:
            self.generate_fig(plot_data)

if __name__ == "__main__":
    # Example usage
    name = "imt_hibs_ras_2600_MHz"
    plot = PlotGenerator(name)
    plot.plot_cdf()
    plot.plot_hist()
    plot.generate_plots()


