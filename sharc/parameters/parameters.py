# -*- coding: utf-8 -*-
"""
Created on Wed Aug  9 19:35:52 2017

@author: edgar
"""

import sys
import os
import yaml

from sharc.parameters.parameters_general import ParametersGeneral
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.parameters.parameters_eess_ss import ParametersEessSS
from sharc.parameters.parameters_fs import ParametersFs
from sharc.parameters.parameters_metsat_ss import ParametersMetSatSS
from sharc.parameters.parameters_fss_ss import ParametersFssSs
from sharc.parameters.parameters_fss_es import ParametersFssEs
from sharc.parameters.parameters_haps import ParametersHaps
from sharc.parameters.parameters_rns import ParametersRns
from sharc.parameters.parameters_ras import ParametersRas
from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation

# Register a tuple constructor with PyYAML
def tuple_constructor(loader, node):
    """Load the sequence of values from the YAML node and returns a tuple constructed from the sequence."""
    values = loader.construct_sequence(node)
    return tuple(values)


yaml.SafeLoader.add_constructor('tag:yaml.org,2002:python/tuple', tuple_constructor)


class Parameters(object):
    """
    Reads parameters from input file.
    """

    def __init__(self):
        self.file_name = None
        self.overwritten_parameters = []

        self.general = ParametersGeneral()
        self.imt = ParametersImt()
        self.eess_ss = ParametersEessSS()
        self.fs = ParametersFs()
        self.fss_ss = ParametersFssSs()
        self.fss_es = ParametersFssEs()
        self.haps = ParametersHaps()
        self.rns = ParametersRns()
        self.ras = ParametersRas()
        self.single_earth_station = ParametersSingleEarthStation()
        self.metsat_ss = ParametersMetSatSS()

    def set_overwritten_parameters(self, overwritten_parameters: list[(str, str)]):
        """sets the configuration file name

        Parameters
        ----------
        file_name : str
            configuration file path
        """
        self.overwritten_parameters = overwritten_parameters

    def set_file_name(self, file_name: str):
        """sets the configuration file name

        Parameters
        ----------
        file_name : str
            configuration file path
        """
        self.file_name = file_name

    def read_params(self):
        """Read the parameters from the config file
        """
        if not os.path.isfile(self.file_name):
            err_msg = f"PARAMETER ERROR [{self.__class__.__name__}]: \
                Could not find the configuration file {self.file_name}"
            sys.stderr.write(err_msg)
            sys.exit(1)

        with open(self.file_name, 'r') as file:
            config = yaml.safe_load(file)

        for ov_param in self.overwritten_parameters:
            path = ov_param[0].split(".")
            path.reverse()
            update_value_to = ov_param[1]

            parameter = config
            while len(path) > 1:
                k = path.pop()
                if k not in parameter:
                    parameter[k] = {}
                parameter = parameter[k]

            parameter[path[0]] = update_value_to

        #######################################################################
        # GENERAL
        #######################################################################
        # TODO: change typing of every method called below
        self.general.load_parameters_from_file(config)

        #######################################################################
        # IMT
        #######################################################################
        self.imt.load_parameters_from_file(config)

        #######################################################################
        # FSS space station
        #######################################################################
        self.fss_ss.load_parameters_from_file(config)

        #######################################################################
        # FSS earth station
        #######################################################################
        self.fss_es.load_parameters_from_file(config)

        #######################################################################
        # Fixed wireless service
        #######################################################################
        self.fs.load_parameters_from_file(config)

        #######################################################################
        # HAPS (airbone) station
        #######################################################################
        self.haps.load_parameters_from_file(config)

        #######################################################################
        # RNS
        #######################################################################
        self.rns.load_parameters_from_file(config)

        #######################################################################
        # RAS station
        #######################################################################
        self.ras.load_parameters_from_file(config)

        #######################################################################
        # EESS passive
        #######################################################################
        self.eess_ss.load_parameters_from_file(config)

        self.single_earth_station.load_parameters_from_file(config)


if __name__ == "__main__":
    from pprint import pprint
    parameters = Parameters()
    param_sections = [
        a for a in dir(parameters) if not a.startswith('__') and not
        callable(getattr(parameters, a))
    ]
    print("\n#### Dumping default parameters:")
    for p in param_sections:
        print("\n")
        pprint(getattr(parameters, p))
