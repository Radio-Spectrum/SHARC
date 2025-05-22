"""Generates scenarios based on main parameters
"""
import numpy as np
import yaml
import os
from copy import deepcopy

from sharc.parameters.parameters_base import tuple_constructor
from sharc.parameters.constants import EARTH_RADIUS


EARTH_RADIUS_KM = EARTH_RADIUS / 1e3
"""Generates the parameters for the MSS D2D to IMT with varying latitude campaign.
"""
import numpy as np
import yaml
import os

from sharc.parameters.parameters_base import tuple_constructor

yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/tuple', tuple_constructor)

local_dir = os.path.dirname(os.path.abspath(__file__))
parameter_file_name = os.path.join(local_dir, "../input/parameters_template.yaml")

# load the base parameters from the yaml file
with open(parameter_file_name, 'r') as file:
    parameters = yaml.safe_load(file)

# beware were using the perigee altitude and only one orbit
sat_alt_km = parameters['mss_d2d']['orbits'][0]['perigee_alt_km']
distances_km = [10, 20, 30, 40, 50]
for direction in [('dl', 'DOWNLINK'), ('ul', 'UPLINK')]:
    for dist in distances_km:
        # Create a copy of the base parameters
        params = parameters.copy()

        # set the link direction
        params['general']['imt_link'] = direction[1]

        # Update the parameters with the new exclusion angle calculated from the exclusion distance
        # The distance is assumed be the arc distance on the surface of the Earth
        central_angle_rad = dist / EARTH_RADIUS_KM

        # Use cosine law to calculate the slant range
        slant_range = np.sqrt(EARTH_RADIUS_KM**2 + (EARTH_RADIUS_KM + sat_alt_km)**2 -
                              2 * EARTH_RADIUS_KM * (EARTH_RADIUS_KM + sat_alt_km) * np.cos(central_angle_rad))

        # Calculate the exclusion angle
        alfa_rad = np.arcsin(((EARTH_RADIUS_KM + sat_alt_km) / slant_range) * np.sin(central_angle_rad))
        exclusion_angle_deg = 90 - np.degrees(alfa_rad)

        print(f'Exclusion angle for distance {dist} km: {exclusion_angle_deg:.2f} degrees')

        params['mss_d2d']['sat_is_active_if']['maximum_elevation_from_es'] = float(exclusion_angle_deg)

        # Set the right campaign prefix
        params['general']['output_dir_prefix'] = 'output_mss_d2d_to_imt_excl_dist_' + str(dist) + \
            '_km_' + direction[0]
        # Save the parameters to a new yaml file
        parameter_file_name = "../input/parameters_mss_d2d_to_imt_excl_angle_" + str(dist) + \
            '_km_' + direction[0] + ".yaml"
        parameter_file_name = os.path.join(local_dir, parameter_file_name)
        with open(parameter_file_name, 'w') as file:
            yaml.dump(params, file, default_flow_style=False)

        del params
        print(f'Generated parameters for exclusion angle {exclusion_angle_deg} degrees.')
