# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 16:29:36 2017

@author: Calil
"""

import sys

from sharc.support.named_tuples import AntennaPar
from sharc.support.enumerations import StationType
from numpy import load

from dataclasses import dataclass
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaImt(ParametersBase):
    """
    Defines the antenna model and related parameters to be used in compatibility
    studies between IMT and other services in adjacent bands.
    """

    section_name: str = "IMT_ANTENNA"
    # Antenna model for adjacent band studies.
    adjacent_antenna_model: str = "SINGLE_ELEMENT"

    # Normalization application flags for base station (BS) and user equipment (UE).
    bs_normalization: bool = False
    ue_normalization: bool = False

    # Normalization files for BS and UE beamforming.
    bs_normalization_file: str = "antenna/beamforming_normalization/bs_norm.npz"
    ue_normalization_file: str = "antenna/beamforming_normalization/ue_norm.npz"

    # Radiation pattern of each antenna element.
    bs_element_pattern: str = "M2101"
    ue_element_pattern: str = "M2101"

    # Minimum array gain for the beamforming antenna [dBi].
    bs_minimum_array_gain: float = -200.0
    ue_minimum_array_gain: float = -200.0

    # Mechanical downtilt [degrees].
    bs_downtilt: float = 6.0
    #   ue_downtilt:float = 6  # Assuming you need this attribute as well

    # BS/UE maximum transmit/receive element gain [dBi].
    bs_element_max_g: float = 5.0
    ue_element_max_g: float = 5.0

    # BS/UE horizontal 3dB beamwidth of single element [degrees].
    bs_element_phi_3db: float = 65.0
    ue_element_phi_3db: float = 90.0

    # BS/UE vertical 3dB beamwidth of single element [degrees].
    bs_element_theta_3db: float = 65.0
    ue_element_theta_3db: float = 90.0

    # BS/UE number of rows and columns in antenna array.
    bs_n_rows: int = 8
    ue_n_rows: int = 4
    bs_n_columns: int = 8
    ue_n_columns: int = 4

    # BS/UE array element spacing (d/lambda).
    bs_element_horiz_spacing: float = 0.5
    ue_element_horiz_spacing: float = 0.5
    bs_element_vert_spacing: float = 0.5
    ue_element_vert_spacing: float = 0.5

    # BS/UE front to back ratio and single element vertical sidelobe attenuation [dB].
    bs_element_am: int = 30
    ue_element_am: int = 25
    bs_element_sla_v: int = 30
    ue_element_sla_v: int = 25

    # Multiplication factor k used to adjust the single-element pattern.
    bs_multiplication_factor: int = 12
    ue_multiplication_factor: int = 12

    def load_parameters_from_file(self, config_file: str):
        """
        Load the parameters from a file and run a sanity check.

        Parameters
        ----------
        config_file : str
            The path to the configuration file.

        Raises
        ------
        ValueError
            If a parameter is not valid.
        """
        super().load_parameters_from_file(config_file)

        # Additional sanity checks specific to antenna parameters can be implemented here

        # Sanity check for adjacent_antenna_model
        if self.adjacent_antenna_model not in ["SINGLE_ELEMENT", "BEAMFORMING"]:
            raise ValueError("adjacent_antenna_model must be 'SINGLE_ELEMENT'")

        # Sanity checks for normalization flags
        if not isinstance(self.bs_normalization, bool):
            raise ValueError("bs_normalization must be a boolean value")

        if not isinstance(self.ue_normalization, bool):
            raise ValueError("ue_normalization must be a boolean value")

        # Sanity checks for element patterns
        if self.bs_element_pattern.upper() not in ["M2101", "F1336", "FIXED"]:
            raise ValueError(
                f"Invalid bs_element_pattern value {self.bs_element_pattern}"
            )

        if self.ue_element_pattern.upper() not in ["M2101", "F1336", "FIXED"]:
            raise ValueError(
                f"Invalid ue_element_pattern value {self.ue_element_pattern}"
            )

    ###########################################################################
    # Named tuples which contain antenna types

    def get_antenna_parameters(self, sta_type: StationType) -> AntennaPar:
        if sta_type is StationType.IMT_BS:
            if self.bs_normalization:
                # Load data, save it in dict and close it
                data = load(self.bs_normalization_file)
                data_dict = {key: data[key] for key in data}
                self.bs_normalization_data = data_dict
                data.close()
            else:
                self.bs_normalization_data = None
            tpl = AntennaPar(
                self.adjacent_antenna_model,
                self.bs_normalization,
                self.bs_normalization_data,
                self.bs_element_pattern,
                self.bs_element_max_g,
                self.bs_element_phi_3db,
                self.bs_element_theta_3db,
                self.bs_element_am,
                self.bs_element_sla_v,
                self.bs_n_rows,
                self.bs_n_columns,
                self.bs_element_horiz_spacing,
                self.bs_element_vert_spacing,
                self.bs_multiplication_factor,
                self.bs_minimum_array_gain,
                self.bs_downtilt,
            )
        elif sta_type is StationType.IMT_UE:
            if self.ue_normalization:
                # Load data, save it in dict and close it
                data = load(self.ue_normalization_file)
                data_dict = {key: data[key] for key in data}
                self.ue_normalization_data = data_dict
                data.close()
            else:
                self.ue_normalization_data = None
            tpl = AntennaPar(
                self.adjacent_antenna_model,
                self.ue_normalization,
                self.ue_normalization_data,
                self.ue_element_pattern,
                self.ue_element_max_g,
                self.ue_element_phi_3db,
                self.ue_element_theta_3db,
                self.ue_element_am,
                self.ue_element_sla_v,
                self.ue_n_rows,
                self.ue_n_columns,
                self.ue_element_horiz_spacing,
                self.ue_element_vert_spacing,
                self.ue_multiplication_factor,
                self.ue_minimum_array_gain,
                0,
            )
        else:
            sys.stderr.write("ERROR\nInvalid station type: " + sta_type)
            sys.exit(1)

        return tpl
