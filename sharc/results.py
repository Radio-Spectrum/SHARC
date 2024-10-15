# -*- coding: utf-8 -*-
"""
Created on Thu Mar 23 08:47:46 2017

@author: edgar
"""

import numpy as np
import os
import csv
import datetime
import pathlib
import pandas as pd
from scipy import stats
from shutil import copy

class Results(object):
    """Handle the output of the simulator
    """
    def __init__(self, parameters_filename: str,
                 overwrite_output: bool,
                 output_dir='output',
                 output_dir_prefix='output',):
        
        self.data_buffer = {
            "imt_ul_tx_power_density": [],
            "imt_ul_tx_power": [],
            "imt_ul_sinr_ext": [],
            "imt_ul_sinr": [],
            "imt_ul_snr": [],
            "imt_ul_inr": [],
            "imt_ul_tput_ext": [],
            "imt_ul_tput": [],
            "imt_path_loss": [],
            "imt_coupling_loss": [],
            "imt_bs_antenna_gain": [],
            "imt_ue_antenna_gain": [],
            "system_imt_antenna_gain": [],
            "imt_system_antenna_gain": [],
            "imt_system_path_loss": [],
            "imt_system_build_entry_loss": [],
            "imt_system_diffraction_loss": [],
            "imt_dl_tx_power_density": [],
            "imt_dl_tx_power": [],
            "imt_dl_sinr_ext": [],
            "imt_dl_sinr": [],
            "imt_dl_snr": [],
            "imt_dl_inr": [],
            "imt_dl_tput_ext": [],
            "imt_dl_tput": [],
            "system_ul_coupling_loss": [],
            "system_ul_interf_power": [],
            "system_dl_coupling_loss": [],
            "system_dl_interf_power": [],
            "system_inr": [],
            "system_pfd": [],
            "system_rx_interf": []
        }


        self.statistics = {} # To store the computed statistics
        self.__sharc_dir = pathlib.Path(__file__).parent.resolve()
        self.output_dir_parent = output_dir
        if not overwrite_output:
            today = datetime.date.today()
            results_number = 1
            results_dir_head = output_dir_prefix + '_' + today.isoformat() + '_{:02n}'
            self.create_dir(results_number, results_dir_head)
            copy(parameters_filename, self.output_directory)
        else:
            self.output_directory = self.__sharc_dir / self.output_dir_parent
            
    def create_dir(self, results_number: int, dir_head: str):
        """Creates the output directory if it doesn't exist.
        Uses the results_number to format the directory name.
        
        Parameters:
        - results_number : int
            Increment used in directory name.
        - dir_head : str
            Directory name prefix, which includes a placeholder for formatting.
        
        Returns:
        - str
            The path of the created output directory.
        """
        # Apply the results_number to format the directory name
        dir_head_complete = self.__sharc_dir / self.output_dir_parent / dir_head.format(results_number)

        try:
            os.makedirs(dir_head_complete)
            self.output_directory = dir_head_complete
        except FileExistsError:
            # Increment the number and retry directory creation if it already exists
            self.create_dir(results_number + 1, dir_head)

    def add_result(self, key: str, values: list):
        """Stores simulation samples in the data buffer and collects a list of what data is being simulated.
        
        Parameters:
        - key : str
            Name of the type of sample being stored.
        - values : list
            List of sample data values.
        """
        if key in self.data_buffer:
            self.data_buffer[key].extend(values)
        else:
            raise KeyError(f"Key '{key}' not found in the results dictionary.")

    def calculate_statistics(self):
        """Calculate mean, variance, standard deviation, and 95% confidence interval for each dataset."""
                
        # Assuming each file contains a column 'data' to analyze
        for file in os.listdir(self.raw_data_dir):
            if file.endswith('.csv'):
                file_path = os.path.join(self.raw_data_dir, file)
                data = pd.read_csv(file_path, header=None)
                
                # Access the first column assuming data values are there
                data_array = data[0].to_numpy()
                mean = np.mean(data_array)
                variance = np.var(data_array, ddof=1)  # Sample variance
                std_dev = np.std(data_array, ddof=1)
                
                # Calculate the 2.5th and 97.5th percentiles for the 95% confidence interval
                ci_lower = np.percentile(data_array, 2.5)
                ci_upper = np.percentile(data_array, 97.5)
                ci = (ci_lower, ci_upper) 

                self.statistics[file] = {
                    'mean': mean,
                    'variance': variance,
                    'std_dev': std_dev,
                    '95%_ci': ci
                }

    def write_statistics(self):
        """Write computed statistics to a separate file with columns for each value."""
        output_file = os.path.join(self.output_directory, "statistics.csv")
        
        with open(output_file, 'w', newline='') as file:
            writer = csv.writer(file)
            # Write the header row
            writer.writerow(['Key', 'Mean', 'Variance', 'Std Dev', '95% CI'])
            
            # Write the statistics rows
            for key, stats in self.statistics.items():
                writer.writerow([key, stats['mean'], stats['variance'], stats['std_dev'], stats['95%_ci']])

    def write_files(self):
        """Write raw data to files."""
        # Create raw data directory if it does not exist
        self.raw_data_dir = os.path.join(self.output_directory, "raw_data_dir/")
        os.makedirs(self.raw_data_dir, exist_ok=True)  # This creates the directory if it doesn't exist

        # Write data files only if there are values
        for key, values in self.data_buffer.items():
            if values:  # Check if values is not empty
                file_path = os.path.join(self.raw_data_dir, f"{key}.csv")
                with open(file_path, 'w') as file:
                    for value in values:
                        file.write(f"{value}\n")
    
    def empty_buffer(self):
        """Empties the data_buffer."""
        for key in self.data_buffer:
            self.data_buffer[key] = []
