# -*- coding: utf-8 -*-
"""
Created on Wed Aug  9 19:35:52 2017

@author: edgar
"""

import sys
import os
import yaml

from sharc.parameters.parameters_general import ParametersGeneral
from sharc.parameters.parameters_imt import ParametersImt
from sharc.parameters.parameters_hotspot import ParametersHotspot
from sharc.parameters.parameters_indoor import ParametersIndoor
from sharc.parameters.parameters_antenna_imt import ParametersAntennaImt
from sharc.parameters.parameters_eess_passive import ParametersEessPassive
from sharc.parameters.parameters_fs import ParametersFs
from sharc.parameters.parameters_fss_ss import ParametersFssSs
from sharc.parameters.parameters_fss_es import ParametersFssEs
from sharc.parameters.parameters_haps import ParametersHaps
from sharc.parameters.parameters_rns import ParametersRns
from sharc.parameters.parameters_ras import ParametersRas
from sharc.parameters.parameters_ntn import ParametersNTN


class Parameters(object):
    """
    Reads parameters from input file.
    """

    def __init__(self):
        self.file_name = None

        self.general = ParametersGeneral()
        self.imt = ParametersImt()
        self.antenna_imt = ParametersAntennaImt()
        self.hotspot = ParametersHotspot()
        self.indoor = ParametersIndoor()
        self.ntn = ParametersNTN()
        self.eess_passive = ParametersEessPassive()
        self.fs = ParametersFs()
        self.fss_ss = ParametersFssSs()
        self.fss_es = ParametersFssEs()
        self.haps = ParametersHaps()
        self.rns = ParametersRns()
        self.ras = ParametersRas()


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
            
        with open(self.file_name, 'r') as yaml_file:
            # yaml_config = yaml.safe_load(yaml_file)

            #######################################################################
            # GENERAL
            #######################################################################
            self.general.load_parameters_from_file(self.file_name)

            #######################################################################
            # IMT
            #######################################################################
            self.imt.load_parameters_from_file(self.file_name)
            # self.imt.topology                = config.get("IMT", "topology")
            # self.imt.wrap_around             = config.getboolean("IMT", "wrap_around")
            # self.imt.num_clusters            = config.getint("IMT", "num_clusters")
            # self.imt.intersite_distance      = config.getfloat("IMT", "intersite_distance")
            # self.imt.minimum_separation_distance_bs_ue = config.getfloat("IMT", "minimum_separation_distance_bs_ue")
            # self.imt.interfered_with         = config.getboolean("IMT", "interfered_with")
            # self.imt.frequency               = config.getfloat("IMT", "frequency")
            # self.imt.bandwidth               = config.getfloat("IMT", "bandwidth")
            # self.imt.rb_bandwidth            = config.getfloat("IMT", "rb_bandwidth")
            # self.imt.spectral_mask           = config.get("IMT", "spectral_mask")
            # self.imt.spurious_emissions      = config.getfloat("IMT", "spurious_emissions")
            # self.imt.guard_band_ratio        = config.getfloat("IMT", "guard_band_ratio")
            # self.imt.bs_load_probability     = config.getfloat("IMT", "bs_load_probability")
            # self.imt.bs_conducted_power      = config.getfloat("IMT", "bs_conducted_power")
            # self.imt.bs_height               = config.getfloat("IMT", "bs_height")
            # self.imt.bs_noise_figure         = config.getfloat("IMT", "bs_noise_figure")
            # self.imt.bs_noise_temperature    = config.getfloat("IMT", "bs_noise_temperature")
            # self.imt.bs_ohmic_loss           = config.getfloat("IMT", "bs_ohmic_loss")
            # self.imt.ul_attenuation_factor   = config.getfloat("IMT", "ul_attenuation_factor")
            # self.imt.ul_sinr_min             = config.getfloat("IMT", "ul_sinr_min")
            # self.imt.ul_sinr_max             = config.getfloat("IMT", "ul_sinr_max")
            # self.imt.ue_k                    = config.getint("IMT", "ue_k")
            # self.imt.ue_k_m                  = config.getint("IMT", "ue_k_m")
            # self.imt.ue_indoor_percent       = config.getfloat("IMT", "ue_indoor_percent")
            # self.imt.ue_distribution_type    = config.get("IMT", "ue_distribution_type")
            # self.imt.ue_distribution_distance = config.get("IMT", "ue_distribution_distance")
            # self.imt.ue_distribution_azimuth = config.get("IMT", "ue_distribution_azimuth")
            # self.imt.ue_tx_power_control     = config.get("IMT", "ue_tx_power_control")
            # self.imt.ue_p_o_pusch            = config.getfloat("IMT", "ue_p_o_pusch")
            # self.imt.ue_alpha                 = config.getfloat("IMT", "ue_alpha")
            # self.imt.ue_p_cmax               = config.getfloat("IMT", "ue_p_cmax")
            # self.imt.ue_power_dynamic_range  = config.getfloat("IMT", "ue_power_dynamic_range")
            # self.imt.ue_height               = config.getfloat("IMT", "ue_height")
            # self.imt.ue_noise_figure         = config.getfloat("IMT", "ue_noise_figure")
            # self.imt.ue_ohmic_loss            = config.getfloat("IMT", "ue_ohmic_loss")
            # self.imt.ue_body_loss            = config.getfloat("IMT", "ue_body_loss")
            # self.imt.dl_attenuation_factor   = config.getfloat("IMT", "dl_attenuation_factor")
            # self.imt.dl_sinr_min             = config.getfloat("IMT", "dl_sinr_min")
            # self.imt.dl_sinr_max             = config.getfloat("IMT", "dl_sinr_max")
            # self.imt.channel_model           = config.get("IMT", "channel_model")
            # self.imt.los_adjustment_factor   = config.getfloat("IMT", "los_adjustment_factor")
            # self.imt.shadowing               = config.getboolean("IMT", "shadowing")
            # self.imt.noise_temperature       = config.getfloat("IMT", "noise_temperature")
            # self.imt.BOLTZMANN_CONSTANT      = config.getfloat("IMT", "BOLTZMANN_CONSTANT")

            #######################################################################
            # IMT ANTENNA
            #######################################################################
            self.antenna_imt.load_parameters_from_file(self.file_name)

            #######################################################################
            # HOTSPOT
            #######################################################################
            self.hotspot.load_parameters_from_file(self.file_name)

            #######################################################################
            # INDOOR
            #######################################################################
            self.indoor.load_parameters_from_file(self.file_name)

            #######################################################################
            # FSS space station
            #######################################################################
            self.fss_ss.load_parameters_from_file(self.file_name)

            #######################################################################
            # FSS earth station
            #######################################################################
            self.fss_es.load_parameters_from_file(self.file_name)

            #######################################################################
            # Fixed wireless service
            #######################################################################
            self.fs.load_parameters_from_file(self.file_name)

            #######################################################################
            # HAPS (airbone) station
            #######################################################################
            self.haps.load_parameters_from_file(self.file_name)

            #######################################################################
            # RNS
            #######################################################################
            self.rns.load_parameters_from_file(self.file_name)

            #######################################################################
            # RAS station
            #######################################################################
            self.ras.load_parameters_from_file(self.file_name)

            #######################################################################
            # EESS passive
            #######################################################################
            self.eess_passive.load_parameters_from_file(self.file_name)

        #######################################################################
        # NTN
        #######################################################################
        self.ntn.load_parameters_from_file(self.file_name)

if __name__ == "__main__":
    from pprint import pprint
    parameters = Parameters()
    param_sections = [a for a in dir(parameters) if not a.startswith('__') and not
                callable(getattr(parameters, a))]
    print("\n#### Dumping default parameters:")
    for p in param_sections:
        print("\n")
        pprint(getattr(parameters, p))
