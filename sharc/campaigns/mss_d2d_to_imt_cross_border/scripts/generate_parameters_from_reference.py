"""Generates scenarios based on main parameters
"""
import numpy as np
import yaml
import os
from copy import deepcopy

from sharc.parameters.parameters_base import tuple_constructor

import argparse

parser = argparse.ArgumentParser(
    description="You may create or overwrite the parameters with different channel configs"
)

parser.add_argument('--channel', type=str, required=True, choices=["co", "adj"],
    help='Set the channel to generate the parameters ("co" for cochannel or "adj" for adjacent channel)'
)

parser.add_argument('--freq', type=str, required=True, choices=["~0.8G", "~2.1G"],
    help='Set the frequency to generate the parameters ("~0.8G" or "~2.1G")'
)

args = parser.parse_args()

yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/tuple', tuple_constructor)

local_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(local_dir, "../input")

ul_parameter_file_name = os.path.join(local_dir, "./base_input.yaml")

# load the base parameters from the yaml file
with open(ul_parameter_file_name, 'r') as file:
    ul_parameters = yaml.safe_load(file)

# Set parameters based on cli config
if args.freq == "~2.1G":
    # default parameters already made for this case
    imt_freq = ul_parameters["imt"]["frequency"]
    imt_bw = ul_parameters["imt"]["bandwidth"]
elif args.freq == "~0.8G":
    # update mss params
    ul_parameters["mss_d2d"]["tx_power_density"] = -28.1 - 34.1

    # update immt params
    imt_bw = 10.0
    imt_freq = 698 + imt_bw / 2
    ul_parameters["imt"]["frequency"] = imt_freq
    ul_parameters["imt"]["bandwidth"] = imt_bw

    # # same as defalt for mss d2d bw
    # # ul_parameters["mss_d2d"]["bandwidth"] = 5.0

    ul_parameters["imt"]["topology"]["single_bs"]["cell_radius"] = 1500
    # BS for f < 1GHz needs non-AAS
    # so we change it here
    ul_parameters["imt"]["bs"]["conducted_power"] = 58

    ul_parameters["imt"]["bs"]["height"] = 30
    # while ohmic loss is included in AAS gain,
    # feeder loss = 3 dB is not included in non-AAS gain
    ul_parameters["imt"]["bs"]["ohmic_loss"] = 3

    # Non aas
    ul_parameters["imt"]["bs"]["antenna"]["array"]["n_rows"] = 1
    ul_parameters["imt"]["bs"]["antenna"]["array"]["n_columns"] = 1
    ul_parameters["imt"]["bs"]["antenna"]["array"]["subarray"]["is_enabled"] = False

    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_pattern"] = "F1336"
    ul_parameters["imt"]["bs"]["antenna"]["array"]["downtilt"] = 3.0

    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_max_g"] = 15
    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_phi_3db"] = 65
    # NOTE: to calculate automatically:
    ul_parameters["imt"]["bs"]["antenna"]["array"]["element_theta_3db"] = 0
else:
    raise ValueError("Should be impossible to fall here")

if args.channel == "co":
    ul_parameters["general"]["enable_cochannel"] = True
    ul_parameters["general"]["enable_adjacent_channel"] = False

    ul_parameters["mss_d2d"]["frequency"] = imt_freq
elif args.channel == "adj":
    ul_parameters["general"]["enable_cochannel"] = False
    ul_parameters["general"]["enable_adjacent_channel"] = True

    ul_parameters["mss_d2d"]["frequency"] = imt_freq + imt_bw / 2 + ul_parameters["mss_d2d"]["bandwidth"] / 2
else:
    raise ValueError("Should be impossible to fall here")

ul_parameters['general']['output_dir'] = \
    ul_parameters['general']['output_dir'].replace("output_base", f"output_{args.freq}_{args.channel}")


dl_parameters = deepcopy(ul_parameters)
dl_parameters['general']['output_dir'] = ul_parameters['general']['output_dir'].replace("_ul", "_dl")
dl_parameters['general']['output_dir_prefix'] = ul_parameters['general']['output_dir_prefix'].replace("_ul", "_dl")
dl_parameters['general']['imt_link'] = "DOWNLINK"

country_border = 4 * ul_parameters["mss_d2d"]["cell_radius"] / 1e3
print("country_border", country_border)

# doesn't matter from which, both will give same result
output_dir_pattern = ul_parameters['general']['output_dir'].replace("_base_ul", "_<specific>")
output_prefix_pattern = ul_parameters['general']['output_dir_prefix'].replace("_base_ul", "_<specific>")

for dist in [
    0,
    country_border,
    country_border + 111 / 2,
    country_border + 111,
    country_border + 3 * 111 / 2,
    country_border + 2 * 111
]:
    ul_parameters["mss_d2d"]["sat_is_active_if"]["lat_long_inside_country"]["margin_from_border"] = dist
    specific = f"{dist}km_base_ul"
    ul_parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace("<specific>", specific)

    dl_parameters["mss_d2d"]["sat_is_active_if"]["lat_long_inside_country"]["margin_from_border"] = dist
    specific = f"{dist}km_base_dl"
    dl_parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace("<specific>", specific)

    ul_parameter_file_name = os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{dist}km_base_ul.yaml")
    dl_parameter_file_name = os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{dist}km_base_dl.yaml")

    with open(
        dl_parameter_file_name,
        'w'
    ) as file:
        yaml.dump(dl_parameters, file, default_flow_style=False)
    with open(
        ul_parameter_file_name,
        'w'
    ) as file:
        yaml.dump(ul_parameters, file, default_flow_style=False)

    for link in ["ul", "dl"]:
        if link == "ul":
            parameters = deepcopy(ul_parameters)
        if link == "dl":
            parameters = deepcopy(dl_parameters)

        parameters['mss_d2d']['num_sectors'] = 19
        # 1 out of 19 beams are active
        parameters['mss_d2d']['beams_load_factor'] = 0.05263157894

        specific = f"{dist}km_activate_random_beam_5p_{link}"
        parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace("<specific>", specific)

        with open(
            os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{specific}.yaml"),
            'w'
        ) as file:
            yaml.dump(parameters, file, default_flow_style=False)

        parameters['mss_d2d']['num_sectors'] = 19
        parameters['mss_d2d']['beams_load_factor'] = 0.3

        specific = f"{dist}km_activate_random_beam_30p_{link}"
        parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace("<specific>", specific)

        with open(
            os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{specific}.yaml"),
            'w'
        ) as file:
            yaml.dump(parameters, file, default_flow_style=False)

        parameters['mss_d2d']['num_sectors'] = 1
        parameters['mss_d2d']['beams_load_factor'] = 1

        parameters['mss_d2d']['beam_positioning'] = {}

        parameters['mss_d2d']['beam_positioning']['type'] = "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE"

        # for uniform area distribution
        parameters['mss_d2d']['beam_positioning']['angle_from_subsatellite_phi'] = {
            'type': "~U(MIN,MAX)",
            'distribution': {
                'min': -180.,
                'max': 180.,
            }
        }
        parameters['mss_d2d']['beam_positioning']['distance_from_subsatellite'] = {
            'type': "~SQRT(U(0,1))*MAX",
            'distribution': {
                'min': 0,
                'max': parameters['mss_d2d']["cell_radius"] * 4,
            }
        }

        specific = f"{dist}km_random_pointing_1beam_{link}"
        parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace("<specific>", specific)

        with open(
            os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{specific}.yaml"),
            'w'
        ) as file:
            yaml.dump(parameters, file, default_flow_style=False)
