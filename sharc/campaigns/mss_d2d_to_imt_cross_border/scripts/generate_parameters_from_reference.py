"""Generates scenarios based on main parameters
"""
import yaml
import os
from copy import deepcopy
import math

from sharc.parameters.parameters_base import tuple_constructor

import argparse

parser = argparse.ArgumentParser(
    description="You may create or overwrite the parameters with different channel configs"
)

parser.add_argument(
    '--channel', type=str, required=True, choices=["co", "adj"],
    help='Set the channel to generate the parameters ("co" for cochannel or "adj" for adjacent channel)'
)

parser.add_argument(
    '--freq', type=str, required=True, choices=["0.8G", "2.1G"],
    help='Set the frequency to generate the parameters ("0.8G" or "2.1G")'
)

parser.add_argument(
    '--coverage', type=str, required=True, choices=["service_grid", "fixed_sectors"],
    help='Set the frequency to generate the parameters ("0.8G" or "2.1G")',
)

args = parser.parse_args()

yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/tuple', tuple_constructor)

local_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(local_dir, "../input")

ul_parameter_file_name = os.path.join(local_dir, "./base_input.yaml")

# load the base parameters from the yaml file
with open(ul_parameter_file_name, 'r') as file:
    ul_parameters = yaml.safe_load(file)

IMT_CENTER_FREQ_2GHZ = 2140  # center of B1 band
IMT_CENTER_FREQ_850MHZ = 881.5  # center of A1 band

# Set parameters based on cli config
if args.freq == "2.1G":
    # Update IMT params for 2.1 GHz
    # 5D/716 table 4.1
    # The base input is already set for 2.1 GHz
    imt_freq = IMT_CENTER_FREQ_2GHZ
    imt_bw = 20  # MHz
    n_rb_per_bw = 100  # number of resource blocks per 20 MHz bandwidth
    ul_parameters["imt"]["frequency"] = imt_freq
    ul_parameters["imt"]["bandwidth"] = imt_bw
    max_pfd_margin_km = 67.71  # -109 dBW/mˆ2/MHz limit at 2.1GHz

elif args.freq == "0.8G":
    # Update IMT params for 850 MHz
    # 5D/716 table 4.1
    imt_freq = IMT_CENTER_FREQ_850MHZ
    imt_bw = 10
    n_rb_per_bw = 50  # number of resource blocks per 20 MHz bandwidth
    ul_parameters["imt"]["frequency"] = imt_freq
    ul_parameters["imt"]["bandwidth"] = imt_bw

    # BS for f < 1GHz needs non-AAS
    # so we change it here
    ul_parameters["imt"]["topology"]["single_bs"]["cell_radius"] = 1500
    ul_parameters["imt"]["bs"]["conducted_power"] = 58

    ul_parameters["imt"]["bs"]["height"] = 30
    # while ohmic loss is included in AAS gain,
    # feeder loss = 3 dB is not included in non-AAS gain
    ul_parameters["imt"]["bs"]["ohmic_loss"] = 3

    # Set Non-AAS antenna parameters
    ul_parameters["imt"]["bs"]["antenna"]["array"]["n_rows"] = 1
    ul_parameters["imt"]["bs"]["antenna"]["array"]["n_columns"] = 1
    ul_parameters["imt"]["bs"]["antenna"]["array"]["subarray"]["is_enabled"] = False

    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_pattern"] = "F1336"
    ul_parameters["imt"]["bs"]["antenna"]["array"]["downtilt"] = 3.0

    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_max_g"] = 15
    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_phi_3db"] = 65
    # NOTE: to calculate automatically:
    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_theta_3db"] = 0

    # update mss params
    ul_parameters["mss_d2d"]["tx_power_density"] = -28.1 - 34.1
    ul_parameters["mss_d2d"]["cell_radius"] = 113630  # meters
    max_pfd_margin_km = 149.07  # -109 dBW/mˆ2/MHz limit at 850MHz

else:
    raise ValueError("Should be impossible to fall here")

if args.channel == "co":
    ul_parameters["general"]["enable_cochannel"] = True
    ul_parameters["general"]["enable_adjacent_channel"] = True
    ul_parameters["mss_d2d"]["frequency"] = imt_freq
elif args.channel == "adj":
    ul_parameters["general"]["enable_cochannel"] = False
    ul_parameters["general"]["enable_adjacent_channel"] = True
    ul_parameters["imt"]["adjacent_ch_reception"] = "ACS"
    ul_parameters["imt"]["bs"]["adjacent_ch_selectivity"] = 45.0  # dB
    ul_parameters["imt"]["ue"]["adjacent_ch_selectivity"] = 35.0  # dB
    ul_parameters["mss_d2d"]["frequency"] = imt_freq + imt_bw / 2 + ul_parameters["mss_d2d"]["bandwidth"] / 2
else:
    raise ValueError("Should be impossible to fall here")

ul_parameters['general']['output_dir'] = \
    ul_parameters['general']['output_dir'].replace("output_base", f"output_{args.freq}_{args.channel}")

#################################################################
# Create the base IMT-DL parameters based on the UL parameters.
dl_parameters = deepcopy(ul_parameters)
dl_parameters['general']['output_dir'] = ul_parameters['general']['output_dir'].replace(
    "_ul", "_dl")
dl_parameters['general']['output_dir_prefix'] = ul_parameters['general']['output_dir_prefix'].replace(
    "_ul", "_dl")
dl_parameters['general']['imt_link'] = "DOWNLINK"

# We try to analyze the interferce into a single UE in the DL, so we set the number of UEs to 1 and the IMT
# band equal to the RBG bandwidth of a single UE.
ue_tx_bw_mhz = math.trunc(n_rb_per_bw / ul_parameters["imt"]["ue"]["k"]) * ul_parameters["imt"]["rb_bandwidth"]
dl_parameters["imt"]["bandwidth"] = imt_bw
# round(ue_tx_bw_mhz / (1 - ul_parameters["imt"]["guard_band_ratio"]), 2)
dl_parameters["imt"]["guard_band_ratio"] = ue_tx_bw_mhz / imt_bw

cell_radius_km = ul_parameters["mss_d2d"]["cell_radius"] / 1e3

# doesn't matter from which, both will give same result
output_dir_pattern = ul_parameters['general']['output_dir'].replace("_base_ul", "_<specific>")
output_prefix_pattern = ul_parameters['general']['output_dir_prefix'].replace("_base_ul", "_<specific>")


def w_param(parameters, specific):
    """Set output directory and write parameter file to input directory."""
    parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace("<specific>", specific)

    with open(
        os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{specific}.yaml"),
        'w'
    ) as file:
        yaml.dump(parameters, file, default_flow_style=False)


if args.coverage == "fixed_sectors":
    # set parameters for fixed sectors with different loads
    # and single sector with random pointing
    country_border_km = 4 * cell_radius_km  # distance from subsatellite to border
    for dist in [
        0,
        country_border_km,
        country_border_km + max_pfd_margin_km - cell_radius_km,  # -109 dBW/mˆ2/MHz limit
    ]:
        # setting border for all parameter files on this loop
        ul_parameters["mss_d2d"]["sat_is_active_if"]["lat_long_inside_country"]["margin_from_border"] = dist
        dl_parameters["mss_d2d"]["sat_is_active_if"]["lat_long_inside_country"]["margin_from_border"] = dist

        w_param(ul_parameters, f"{dist}km_base_ul")
        w_param(dl_parameters, f"{dist}km_base_dl")

        for link in ["ul", "dl"]:
            if link == "ul":
                parameters = deepcopy(ul_parameters)
            if link == "dl":
                parameters = deepcopy(dl_parameters)

            ####################################################
            # make fixed positioned sectors with different loads
            print("Generating parameters for sectors at subsatellite with different loads")
            parameters['mss_d2d']['num_sectors'] = 19

            # 1 out of 19 beams are active
            parameters['mss_d2d']['beams_load_factor'] = 0.05263157894
            w_param(parameters, f"{dist}km_activate_random_beam_5p_{link}")

            parameters['mss_d2d']['beams_load_factor'] = 0.3
            w_param(parameters, f"{dist}km_activate_random_beam_30p_{link}")

            ####################################################
            # make single sector with random pointing
            print(
                "Generating parameters for single sector at random"
                " (uniform) circle area around subsatellite"
            )
            parameters['mss_d2d']['num_sectors'] = 1
            parameters['mss_d2d']['beams_load_factor'] = 1
            # for uniform area distribution in a circle of radius 4 * beam_radius
            parameters['mss_d2d']['beam_positioning'] = {
                'type': "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
                'angle_from_subsatellite_phi': {
                    'type': "~U(MIN,MAX)",
                    'distribution': {
                        'min': -180.,
                        'max': 180.,
                    },
                },
                'distance_from_subsatellite': {
                    'type': "~SQRT(U(0,1))*MAX",
                    'distribution': {
                        'min': 0,
                        'max': parameters['mss_d2d']["cell_radius"] * 4,
                    }
                }
            }
            w_param(parameters, f"{dist}km_random_pointing_1beam_{link}")

elif args.coverage == "service_grid":
    for dist in [
        0,
        cell_radius_km,
        max_pfd_margin_km,  # -109 dBW/mˆ2/MHz limit
    ]:
        for link in ["ul", "dl"]:
            if link == "ul":
                parameters = deepcopy(ul_parameters)
            if link == "dl":
                parameters = deepcopy(dl_parameters)

            print(f"Generating parameters for service grid with {dist}km margin from border for {link} link")

            ####################################################
            # entire service grid is covered
            # 731 km of border
            parameters["mss_d2d"]["sat_is_active_if"]["lat_long_inside_country"]["margin_from_border"] = -731
            parameters['mss_d2d']['beam_positioning'] = {
                "service_grid": {
                    "grid_margin_from_border": dist,
                    "eligible_sats_margin_from_border": -731
                }
            }
            parameters['mss_d2d']['beams_load_factor'] = 1
            # just select service grid, let defaults come from
            # country polygon limit definitions
            parameters['mss_d2d']['beam_positioning']['type'] = "SERVICE_GRID"
            w_param(parameters, f"{dist}km_service_grid_padded_100p_{link}")

            parameters['mss_d2d']['beams_load_factor'] = 0.5
            w_param(parameters, f"{dist}km_service_grid_padded_50p_{link}")

            parameters['mss_d2d']['beams_load_factor'] = 0.2
            w_param(parameters, f"{dist}km_service_grid_padded_20p_{link}")

            # There's no satellies outside the country polygon. Set for comparison.
            parameters["mss_d2d"]["sat_is_active_if"]["lat_long_inside_country"]["margin_from_border"] = 0
            parameters["mss_d2d"]["beam_positioning"]["service_grid"]["eligible_sats_margin_from_border"] = 0
            parameters['mss_d2d']['beams_load_factor'] = 1
            w_param(parameters, f"{dist}km_service_grid_100p_{link}")

            parameters['mss_d2d']['beams_load_factor'] = 0.5
            w_param(parameters, f"{dist}km_service_grid_50p_{link}")

            parameters['mss_d2d']['beams_load_factor'] = 0.2
            w_param(parameters, f"{dist}km_service_grid_20p_{link}")
else:
    raise ValueError("Should be impossible to fall here")
