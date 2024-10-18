import os
import pandas as pd
import numpy as np

workfolder = os.path.dirname(os.path.abspath(__file__))
csv_folder = os.path.abspath(os.path.join(workfolder, '..', "output"))

comparison_folder = os.path.abspath(os.path.join(workfolder, '..', "comparison"))

# TODO: get latest

DL_folder = "output_imt_hotspot_eess_active_beam_small_dl_2024-09-30_03"
UL_folder = "output_imt_hotspot_eess_active_beam_small_ul_2024-09-30_01"

DL_csv_name = "SYS_INR_samples.csv"
UL_csv_name = "SYS_INR_samples.csv"

UL_inr_csv = pd.read_csv(
    os.path.join(csv_folder, UL_folder, UL_csv_name),
    delimiter=',', skiprows=1
)

UL_inr = UL_inr_csv.iloc[:, 1]

DL_inr_csv = pd.read_csv(
    os.path.join(csv_folder, DL_folder, DL_csv_name),
    delimiter=',', skiprows=1
)

DL_inr = DL_inr_csv.iloc[:, 1]

segment_factor = 1.0526

TDD_UL_factor = 0.25
TDD_samples = 4

random_number_gen = np.random.RandomState(101)

choose_from_ul_perc = 0

aggregate_samples = np.empty(min(len(DL_inr), len(UL_inr)), dtype=float)

for i in range(len(aggregate_samples)):
    indexes = np.floor(random_number_gen.random(size=TDD_samples) * min(len(DL_inr), len(UL_inr)))
    sample = 0.0

    for j in indexes: # random samples
        choose_from_ul = False
        # 1/4 of the time it will choose sample from UL
        choose_from_ul_perc += TDD_UL_factor # 0.25, 0.5, 0.75, [1.0]
        if choose_from_ul_perc >= 1: # [1.0]
            choose_from_ul_perc -= 1
            choose_from_ul = True

        if choose_from_ul:
            # print("UL")
            sample += np.power(10, (UL_inr[int(j)])/10)
        else:
            # print("DL")
            sample += np.power(10, (DL_inr[int(j)])/10)
    aggregate_samples[i] = 10 * np.log10(sample * segment_factor / TDD_samples)

values, base = np.histogram(aggregate_samples, bins=200)
cumulative = np.cumsum(values)
x = base[:-1]
y = cumulative / cumulative[-1]
title = "aggregate-inr-0.25-TDD"
y_limits = (0, 1)
filename = "SYS_CDF_of_system_INR.csv"
output_prefix = "output_imt_hotspot_eess_active_"
aggregate_dir = os.path.join(csv_folder, output_prefix + title)
aggregate_inr_file = os.path.join(aggregate_dir, filename)

df = pd.DataFrame({'x': x, 'y': y})
# Writing header text as comment

try:
    os.makedirs(aggregate_dir)
except:
    pass

with open(aggregate_inr_file, 'w') as f:
    f.write(f"# {title}\n")
df.to_csv(aggregate_inr_file, mode='a', index=False)

# also create comparison files:
import shutil

comparison_inr_cdf_files = [f[0:-len(".csv")] for f in os.listdir(comparison_folder) if f.endswith(".csv")]

for comparison_inr_cdf_file in comparison_inr_cdf_files:
    folder_to_create = os.path.join(csv_folder, output_prefix + comparison_inr_cdf_file)
    reference_file = os.path.join(comparison_folder, comparison_inr_cdf_file + ".csv")
    file_to_create = os.path.join(folder_to_create, "SYS_CDF_of_system_INR.csv")
    try:
        print(folder_to_create)
        os.makedirs(folder_to_create)
    except:
        pass

    shutil.copyfile(reference_file, file_to_create)
    
