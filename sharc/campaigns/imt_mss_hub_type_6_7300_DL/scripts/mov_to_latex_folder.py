import os
import re
from pathlib import Path

import pandas as pd

# Base directory for the simulation results
campaign_base_dir = Path(__file__).resolve().parent.parent / "output"
latex_dir = campaign_base_dir / "latex"

# Create the 'latex' folder if it does not exist
latex_dir.mkdir(exist_ok=True)

# Output prefix pattern (Adjust this based on your real prefix)
output_prefix = "output_imt_mss_hub_type_6_DL_7300"

# Dictionary to store data from all CSV files
data_dict = {}

# Regular expression to extract y-value and load probability
pattern = re.compile(r"y_(\d+)_load_probability_(\d+)")

# Iterate over all subdirectories in the output directory
for subdir in campaign_base_dir.iterdir():
    if subdir.is_dir() and subdir.name.startswith(output_prefix):
        match = pattern.search(subdir.name)
        if match:
            y_value, load_probability = map(int, match.groups())

            # Expected path of the system_inr.csv file
            original_file = subdir / "system_inr.csv"

            # Check if the file exists before processing
            if original_file.exists():
                # Load the CSV file
                df = pd.read_csv(original_file, names=["INR [dB]"])

                # Define column name based on Distance and Load Probability
                col_name = f"INR_y_{y_value}_load_{load_probability}"
                data_dict[col_name] = df["INR [dB]"]

            else:
                print(f"File not found: {original_file}")

# Convert dictionary to DataFrame and save
if data_dict:
    combined_df = pd.DataFrame(data_dict)

    # Save the combined CSV file
    output_csv_path = latex_dir / "combined_system_inr.csv"
    combined_df.to_csv(output_csv_path, index=False)
    print(f"Combined CSV saved: {output_csv_path}")
else:
    print("No CSV files were found to combine.")
