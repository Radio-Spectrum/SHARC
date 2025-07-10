"""Generates scenarios based on main parameters
"""
from dataclasses import dataclass
import typing
import numpy as np
import yaml
import os
from copy import deepcopy

from sharc.parameters.parameters_base import tuple_constructor


@dataclass
class ESParams():
    """
    Data class representing Earth Station parameters for scenario generation.

    Attributes:
        name (str): Name of the earth station system.
        antenna_gain (float): Antenna gain in dBi.
        receive_temperature (float): Receiver noise temperature in K.
        frequency (float): Operating frequency in MHz.
        bandwidth (float): Bandwidth in MHz.
        antenna_diameter (float, optional): Antenna diameter in meters.
        antenna_pattern (Literal): Antenna pattern type.
    """
    name: str
    # [dBi]
    antenna_gain: float
    # [K]
    receive_temperature: float
    # [MHz]
    frequency: float
    # [MHz]
    bandwidth: float
    # [m]
    antenna_diameter: float = None
    # TODO: add "ITU RR. Appendix 8, annex III" antenna pattern
    antenna_pattern: typing.Literal[
        "ITU-R S.465", "ITU RR. Appendix 8, annex III"
    ] = "ITU-R S.465"

    def __post_init__(self):
        if self.antenna_diameter is None:
            # antenna efficiency:
            n = 0.5
            lmbda = 3e8 / (self.frequency * 1e6)
            G = 10**(self.antenna_gain / 10)
            self.antenna_diameter = float(np.round(
                lmbda * np.sqrt(G / n) / np.pi, decimals=2
            ))
            print(
                f"Earth station {
                    self.name} antenna diameter of {
                    self.antenna_diameter} " f"has been assumed for an efficiency of {n}.")


yaml.SafeLoader.add_constructor(
    'tag:yaml.org,2002:python/tuple',
    tuple_constructor)

local_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(local_dir, "../input")

parameter_file_name = os.path.join(local_dir, "./base_input.yaml")

# load the base parameters from the yaml file
with open(parameter_file_name, 'r') as file:
    gen_parameters = yaml.safe_load(file)

# doesn't matter from which, both will give same result
output_prefix_pattern = gen_parameters['general']['output_dir_prefix'].replace(
    "_base", "_<specific>")

freq = 2200

system_B = ESParams(
    name="system_b",
    antenna_gain=45.8,
    receive_temperature=190,
    frequency=freq,
    bandwidth=4,  # MHz
)

system_D = ESParams(
    name="system_d",
    antenna_gain=39,
    receive_temperature=120,
    frequency=freq,
    bandwidth=6,  # MHz
)

for sys in [
    system_B,
    system_D,
]:
    sys_parameters = deepcopy(gen_parameters)

    sys_parameters['single_earth_station']['frequency'] = sys.frequency
    sys_parameters['single_earth_station']['bandwidth'] = sys.bandwidth

    sys_parameters['single_earth_station']['antenna']['gain'] = sys.antenna_gain
    sys_parameters['single_earth_station']['antenna']['pattern'] = sys.antenna_pattern
    sys_parameters['single_earth_station']['antenna']['itu_r_s_465']['diameter'] = sys.antenna_diameter

    sys_parameters['single_earth_station']['noise_temperature'] = sys.receive_temperature

    for eess_elev in [
        5, 30, 60, 90
    ]:
        parameters = deepcopy(sys_parameters)

        parameters['single_earth_station']['geometry']['elevation']['type'] = "FIXED"
        parameters['single_earth_station']['geometry']['elevation']['fixed'] = eess_elev

        specific = f"{eess_elev}elev_{sys.name}"
        parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace(
            "<specific>", specific)

        with open(
            os.path.join(input_dir, f"./parameters_mss_d2d_to_eess_{specific}.yaml"),
            'w'
        ) as file:
            yaml.dump(parameters, file, default_flow_style=False)

    # also do uniform dist of elevation angles
    parameters = deepcopy(sys_parameters)
    parameters['single_earth_station']['geometry']['elevation']['type'] = "UNIFORM_DIST"
    parameters['single_earth_station']['geometry']['elevation']['uniform_dist'] = {
        'min': 5, 'max': 90, }

    specific = f"uniform_elev_{sys.name}"
    parameters['general']['output_dir_prefix'] = output_prefix_pattern.replace(
        "<specific>", specific)

    with open(
        os.path.join(input_dir, f"./parameters_mss_d2d_to_eess_{specific}.yaml"),
        'w'
    ) as file:
        yaml.dump(parameters, file, default_flow_style=False)
