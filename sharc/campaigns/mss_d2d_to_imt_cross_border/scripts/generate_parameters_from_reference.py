"""Generates scenarios based on main parameters
"""
import numpy as np
import yaml
import os

from sharc.parameters.parameters_base import tuple_constructor

yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/tuple', tuple_constructor)

local_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(local_dir, "../input")
parameter_file_name = os.path.join(input_dir, "./parameters_mss_d2d_to_imt_cross_border_base.yaml")

# load the base parameters from the yaml file
with open(parameter_file_name, 'r') as file:
    parameters = yaml.safe_load(file)

output_pattern = parameters['general']['output_dir_prefix'].replace("_base", "_<specific>")


parameters['mss_d2d']['num_sectors'] = 19
# 1 out of 19 beams are active
parameters['mss_d2d']['beams_load_factor'] = 0.05263157894

specific = "activate_random_beam_5p"
parameters['general']['output_dir_prefix'] = output_pattern.replace("<specific>", specific)

with open(
    os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{specific}.yaml"),
    'w'
) as file:
    yaml.dump(parameters, file, default_flow_style=False)


parameters['mss_d2d']['num_sectors'] = 1
parameters['mss_d2d']['beams_load_factor'] = 1

parameters['mss_d2d']['center_beam_positioning'] = {}

parameters['mss_d2d']['center_beam_positioning']['type'] = "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE"

# for uniform area distribution
parameters['mss_d2d']['center_beam_positioning']['angle_from_subsatellite_phi'] = {
    'type': "~U(MIN,MAX)",
    'distribution': {
        'min': -180.,
        'max': 180.,
    }
}
parameters['mss_d2d']['center_beam_positioning']['distance_from_subsatellite'] = {
    'type': "~SQRT(U(0,1))*MAX",
    'distribution': {
        'min': 0,
        'max': parameters['mss_d2d']["cell_radius"] * 4,
    }
}

specific = "random_pointing_1beam"
parameters['general']['output_dir_prefix'] = output_pattern.replace("<specific>", specific)

with open(
    os.path.join(input_dir, f"./parameters_mss_d2d_to_imt_cross_border_{specific}.yaml"),
    'w'
) as file:
    yaml.dump(parameters, file, default_flow_style=False)

print(f'Generated parameters for random selected sectors.')
