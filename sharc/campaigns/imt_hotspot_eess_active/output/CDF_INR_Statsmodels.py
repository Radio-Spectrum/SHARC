import csv
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.distributions.empirical_distribution import ECDF

# Define paths to your CSV files (replace with actual file paths)
csv_file_DL_SM = 'path_to_INR_DL_SM.csv'
csv_file_DL_LG = 'path_to_INR_DL_LG.csv'
csv_file_UL_SM = 'path_to_INR_UL_SM.csv'
csv_file_UL_LG = 'path_to_INR_UL_LG.csv'

def load_data_from_csv(file_path):
    """
    Load data from a CSV file, skipping the first two rows.

    Args:
        file_path (str): Path to the CSV file.

    Returns:
        np.array: Array containing the loaded data from the CSV.
    """
    try:
        with open(file_path, mode='r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip the first row (snapshots info)
            next(reader)  # Skip the second row (axis labels)
            data = [float(row[0]) for row in reader]
            return np.array(data)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return np.array([])

# Load data from the CSV files
INR_DL_SM = load_data_from_csv(csv_file_DL_SM)
INR_DL_LG = load_data_from_csv(csv_file_DL_LG)
INR_UL_SM = load_data_from_csv(csv_file_UL_SM)
INR_UL_LG = load_data_from_csv(csv_file_UL_LG)

# Ensure that all data arrays were successfully loaded before proceeding
if not all([INR_DL_SM.size, INR_DL_LG.size, INR_UL_SM.size, INR_UL_LG.size]):
    raise ValueError("Error: One or more datasets failed to load. Please check the CSV file paths.")

# Convert INR values from dB to linear scale
INR_DL_SM_lin = 10 ** (INR_DL_SM / 10)
INR_DL_LG_lin = 10 ** (INR_DL_LG / 10)
INR_UL_SM_lin = 10 ** (INR_UL_SM / 10)
INR_UL_LG_lin = 10 ** (INR_UL_LG / 10)

# Aggregate INR values for DL and UL in linear scale
INR_DL = INR_DL_SM_lin + INR_DL_LG_lin
INR_UL = INR_UL_SM_lin + INR_UL_LG_lin

# Generate random indices for aggregating different combinations of DL and UL
Ind1 = np.random.randint(0, len(INR_DL), len(INR_DL))
Ind2 = np.random.randint(0, len(INR_DL), len(INR_DL))
Ind3 = np.random.randint(0, len(INR_DL), len(INR_DL))
Ind4 = np.random.randint(0, len(INR_DL), len(INR_DL))
Ind5 = np.random.randint(0, len(INR_DL), len(INR_DL))
Ind6 = np.random.randint(0, len(INR_DL), len(INR_DL))

# Calculate aggregate INR values using a weighted combination of DL and UL
INR_Agg_1 = 10 * np.log10(0.75 * (INR_DL_SM_lin[Ind3] + INR_DL_LG_lin[Ind4]) + 0.25 * (INR_UL_SM_lin[Ind5] + INR_UL_LG_lin[Ind6]))
INR_Agg_2 = 10 * np.log10(0.75 * INR_DL[Ind1] + 0.25 * INR_UL[Ind2])

# Function to calculate the empirical CDF using statsmodels
def compute_cdf(data):
    """
    Compute the empirical CDF using the statsmodels ECDF function.
    
    Args:
        data (np.array): Input data for which the CDF is to be calculated.
    
    Returns:
        tuple: x values (sorted data), y values (CDF).
    """
    ecdf = ECDF(data)
    return ecdf.x, ecdf.y

# Compute empirical CDFs for the loaded INR data
x_INR_DL_LG, y_INR_DL_LG = compute_cdf(INR_DL_LG)
x_INR_DL_SM, y_INR_DL_SM = compute_cdf(INR_DL_SM)
x_INR_UL_LG, y_INR_UL_LG = compute_cdf(INR_UL_LG)
x_INR_UL_SM, y_INR_UL_SM = compute_cdf(INR_UL_SM)
x_INR_Agg_1, y_INR_Agg_1 = compute_cdf(INR_Agg_1)
x_INR_Agg_2, y_INR_Agg_2 = compute_cdf(INR_Agg_2)

# Set x-axis limits based on percentiles for better observability
def get_x_limits(*datasets):
    """
    Get x-axis limits based on the 1st and 99th percentiles of the data.
    
    Args:
        datasets: Multiple arrays of data (e.g., INR_DL, INR_UL) for which we want to set limits.
    
    Returns:
        tuple: (min_limit, max_limit) for the x-axis.
    """
    combined_data = np.concatenate(datasets)
    lower_limit = np.percentile(combined_data, 1)  # 1st percentile
    upper_limit = np.percentile(combined_data, 99)  # 99th percentile
    return lower_limit, upper_limit

# Get dynamic x-axis limits for better visualization
x_min, x_max = get_x_limits(INR_DL_SM, INR_DL_LG, INR_UL_SM, INR_UL_LG, INR_Agg_1, INR_Agg_2)

# Plotting the CDFs for different INR data sets with dynamic x-limits
plt.figure()

# Convert the CDF values to percentages
plt.plot(x_INR_DL_LG, y_INR_DL_LG, linewidth=2, label='DL - large beam')
plt.plot(x_INR_UL_LG, y_INR_UL_LG, linewidth=2, label='UL - large beam')
plt.plot(x_INR_DL_SM, y_INR_DL_SM, linewidth=2, label='DL - 3dB spotbeam')
plt.plot(x_INR_UL_SM, y_INR_UL_SM, linewidth=2, label='UL - 3dB spotbeam')
plt.plot(x_INR_Agg_1, y_INR_Agg_1, linewidth=2, label='Aggregate CDF 1')
plt.plot(x_INR_Agg_2, y_INR_Agg_2, linewidth=2, label='Aggregate CDF 2')

# Customize plot labels, title, and grid
plt.legend()
plt.xlabel('Interference to Noise Ratio [dB]')
plt.ylabel('CDF [%]')
plt.title('CDF of Interference to Noise Ratio for 18° Nadir - EESS Active')
plt.grid(True)

# Set dynamic limits for x-axis based on data percentiles
plt.xlim([x_min, x_max])
plt.ylim([0, 2])   # CDF in percentage

# Show the plot
plt.show()
