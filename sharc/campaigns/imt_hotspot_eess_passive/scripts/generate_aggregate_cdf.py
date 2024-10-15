# we have to get the interference samples by using de INR samples
# because currently only INR samples are collected on the result
# since noise temperature is constant eq. to 500, as seen in `sharc/station_factory.py:L766`, in `StationFactory.generate_space_station`
# thermal_noise is calculated as seen in `sharc/simulation_downlink.py:L226`
# or `sharc/simulation_uplink.py:L226`

from sharc.parameters.constants import BOLTZMANN_CONSTANT

import os
import pandas as pd
import numpy as np
import math


workfolder = os.path.dirname(os.path.abspath(__file__))
csv_folder = os.path.abspath(os.path.join(workfolder, '..', "output"))

comparison_folder = os.path.abspath(os.path.join(workfolder, '..', "comparison"))
comparison_file = "luciano-contrib21-figure8-eess.csv"

# do judson:
# 1 amostra aggr = ( 0.25 (1UL) + 0.75 (1DL) ) * SF

# do outro jeito:
# cada 1 amostra aggr = sum(SF amostras, onde 25% das SF amostras vem de UL)
# Se SF = 3
# cada 1 amostra aggr = 1DL + 1DL + 1DL
# 1DL + 1DL + 1UL
# 1DL + 1UL + 1DL
# 1UL + 1DL + 1DL
# 1DL + 1DL + 1DL


# TODO: get latest
DL_folder = "output_imt_hotspot_eess_passive_1_cluster_DL_2024-09-27_03"
UL_folder = "output_imt_hotspot_eess_passive_1_cluster_UL_2024-09-27_02"

DL_csv_name = "SYS_INR_samples.csv"
UL_csv_name = "SYS_INR_samples.csv"

UL_inr_csv = pd.read_csv(
    os.path.join(csv_folder, UL_folder, UL_csv_name),
    delimiter=',', skiprows=1
)

UL_inr = UL_inr_csv.iloc[:, 1]
bandwidth = 100
# used fixed noise_temperature = 500 on simulation
thermal_noise = \
    10*math.log10(BOLTZMANN_CONSTANT * 500 * 1e3) + \
    10*math.log10(bandwidth * 1e6)

# need to do this because we only have inr sample
UL_interference = UL_inr + thermal_noise

DL_inr_csv = pd.read_csv(
    os.path.join(csv_folder, DL_folder, DL_csv_name),
    delimiter=',', skiprows=1
)

DL_inr = DL_inr_csv.iloc[:, 1]

# need to do this because we only have inr sample
DL_interference = DL_inr + thermal_noise


segment_factor = 2.8

TDD_UL_factor = 0.25

random_number_gen = np.random.RandomState(101)

choose_from_ul_perc = 0

aggregate_samples = np.empty(10000, dtype=float)

# # method of summing N samples. It provides a smaller variance than the next method. segment_factor needs to be an integer
# segment_factor = math.ceil(segment_factor)

# for i in range(len(aggregate_samples)):
#     indexes = np.floor(random_number_gen.random(size=2) * len(UL_interference))
#     sample = 0.0

#     for j in indexes: # 3 random samples
#         choose_from_ul = False
#         # 1/4 of the time it will choose sample from UL
#         choose_from_ul_perc += TDD_UL_factor # 0.25, 0.5, 0.75, [1.0]
#         if choose_from_ul_perc >= 1: # [1.0]
#             choose_from_ul_perc -= 1
#             choose_from_ul = True

#         if choose_from_ul:
#             sample += np.power(10, (UL_interference[int(j)])/10)
#         else:
#             sample += np.power(10, (DL_interference[int(j)])/10)
#         aggregate_samples[i] = 10 * np.log10(sample) - 30


# judson's method
for i in range(len(aggregate_samples)):
    indexes = np.floor(random_number_gen.random(size=2) * len(UL_interference))
    sample = 0.0

    aggregate_samples[i] = 10 * np.log10(
        (
            np.power(10, (UL_interference[int(indexes[0])])/10) +
            3*np.power(10, (DL_interference[int(indexes[1])])/10)
        ) * segment_factor / 4
    ) - 30

# the -30 is needed to transform dBm into dB

values, base = np.histogram(aggregate_samples, bins=200)
cumulative = np.cumsum(values)
x = base[:-1]
y = cumulative / cumulative[-1]
title = "aggregate-interference-1-cluster-0.25-TDD"
y_limits = (0, 1)

file_path = os.path.join(comparison_folder, title + ".csv")
df = pd.DataFrame({'x': x, 'y': y})
# Writing header text as comment
with open(file_path, 'w') as f:
    f.write(f"# {title}\n")
df.to_csv(file_path, mode='a', index=False)
