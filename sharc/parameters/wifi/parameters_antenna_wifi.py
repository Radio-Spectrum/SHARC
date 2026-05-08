# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 16:29:36 2017

@author: Calil
"""

from numpy import load
import typing

from dataclasses import dataclass, field
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaSubarrayWifi(ParametersBase):
    """
    Parameters for subarray as defined in R23-WP5D-C-0413, Annex 4.2
    """
    # to use subarray, set this to true
    is_enabled: bool = False

    # Number of rows in subarray
    n_rows: int = 3

    # BS array element vertical spacing (d/lambda).
    element_vert_spacing: float = 0.5
    # element_vert_spacing: float = 0.5

    # notice that electrical tilt == -1 * downtilt
    # Sub array eletrical downtilt [deg]
    eletrical_downtilt: float = 3.0


@dataclass
class ParametersAntennaWifi(ParametersBase):
    """
    Defines the antenna model and related parameters to be used in compatibility
    studies between IMT and other services in adjacent bands.
    """
    section_name: str = "wifi_antenna"

    downtilt: float = 6.0

    n_rows: int = 8
    n_columns: int = 8


    def __post_init__(self):
        self.normalization_data = None

    def load_subparameters(self, ctx: str, params: dict, quiet=True):
        """
        Load parameters when this class is used as a subparameter.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        params : dict
            Dictionary of parameters to load.
        quiet : bool, optional
            If True, suppress output (default is True).
        """
        super().load_subparameters(ctx, params, quiet)

    def set_external_parameters(
            self, *, adjacent_antenna_model: typing.Literal["BEAMFORMING", "SINGLE_ELEMENT"]):
        """
        Set the adjacent antenna model parameter.

        Parameters
        ----------
        adjacent_antenna_model : Literal["BEAMFORMING", "SINGLE_ELEMENT"]
            The adjacent antenna model to use.
        """
        self.adjacent_antenna_model = adjacent_antenna_model

    def validate(self, ctx: str):
        """
        Validate the antenna parameters for correctness.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        Raises
        ------
        ValueError
            If any parameter is invalid.
        """
        # Additional sanity checks specific to antenna parameters can be
        # implemented here
        pass

    def get_normalization_data_if_needed(self):
        """
        This loads normalization data if normalization should be applied
        """
        if self.normalization:
            # Load data, save it in dict and close it
            data = load(self.normalization_file)
            data_dict = {key: data[key] for key in data}
            self.normalization_data = data_dict
            data.close()
        else:
            self.normalization_data = None

    def get_antenna_parameters(self) -> "ParametersAntennaWifi":
        """
        Get the antenna parameters loadind normalization values if needed.

        Returns
        -------
        ParametersAntennaImt
            The antenna parameters object constructed from the current configuration.
        """
        self.get_normalization_data_if_needed()

        return self
