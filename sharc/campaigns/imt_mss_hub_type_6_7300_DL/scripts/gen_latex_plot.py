import os
import re
from pathlib import Path

import pandas as pd

# Base directory for simulation results
campaign_base_dir = Path(__file__).resolve().parent.parent / "output"
latex_dir = campaign_base_dir / "latex"

# Create the 'latex' folder if it does not exist
latex_dir.mkdir(exist_ok=True)

# Prefix for simulation output directories
prefix = "output_imt_mss_hub_type_6_DL_7300"

# Regex pattern to extract distance (y) and load probability values
pattern = re.compile(rf"{prefix}_y_(\d+)_load_probability_(\d+)")

# Dictionary to store simulation data
data_dict = {}

# Iterate through all subdirectories in 'output'
for subdir in campaign_base_dir.iterdir():
    if subdir.is_dir():
        match = pattern.search(subdir.name)
        if match:
            y_value, load_probability = match.groups()

            # Expected path of the data file
            original_file = subdir / "system_inr.csv"

            # Check if the file exists before processing
            if original_file.exists():
                # Read CSV, assuming it contains a single column of INR values
                df = pd.read_csv(original_file, names=["INR [dB]"])

                # Column name for this simulation
                column_name = f"Dist_{y_value}m_Load_{load_probability}"

                # Add data to the dictionary
                data_dict[column_name] = df["INR [dB]"]

                print(f"Processed: {original_file}")
            else:
                print(f"File not found: {original_file}")

# Create a final DataFrame combining all data
if data_dict:
    combined_df = pd.DataFrame(dict(sorted(data_dict.items())))

    # Save the combined CSV file
    output_csv_path = latex_dir / "combined_system_inr.csv"
    combined_df.to_csv(output_csv_path, index=False)

    print(f"Combined file saved at: {output_csv_path}")
else:
    print("No CSV files found to combine.")
