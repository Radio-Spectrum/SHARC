# -*- coding: utf-8 -*-
"""Parameters definitions for NTN systems
"""
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase
import numpy as np


@dataclass
class ParametersNTN(ParametersBase):
    """
    Simulation parameters for NTN network topology.
    """
    section_name: str = "NTN"

    # NTN Airborne Platform height (m)
    bs_height: float = 20000

    # NTN cell radius in network topology [m]
    cell_radius: float = 90000

    # NTN Intersite Distance (m). Intersite distance = Cell Radius * sqrt(3)
    intersite_distance: float = np.sqrt(3)*cell_radius

    # BS Distance from earth
    # bs_height: float = 20000

    # BS azimuth
    bs_azimuth: float = 45.0

    # BS elevation
    bs_elevation: float = 90.0

    # Number of sectors
    num_sectors: int = 7

    # Conducted power per element [dBm/bandwidth]
    bs_conducted_power: int = 37

    # Backoff Power [Layer 2] [dB]. Allowed: 7 sector topology - Layer 2
    bs_backoff_power: int = 3

    # NTN Antenna configuration
    bs_n_rows_layer1: int = 2
    bs_n_columns_layer1: int = 2
    bs_n_rows_layer2: int = 4
    bs_n_columns_layer2: int = 2

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

        # Now do the sanity check for some parameters
        if self.num_sectors not in [1, 7, 19]:
            raise ValueError(f"ParametersNTN: Invalid number of sectors {
                             self.num_sectors}")

        if self.bs_height <= 0:
            raise ValueError(f"ParametersNTN: bs_height must be greater than 0, but is {
                             self.bs_height}")

        if self.cell_radius <= 0:
            raise ValueError(f"ParametersNTN: cell_radius must be greater than 0, but is {
                             self.cell_radius}")

        if self.intersite_distance <= 0:
            raise ValueError(f"ParametersNTN: intersite_distance must be greater than 0, but is {
                             self.intersite_distance}")

        if not isinstance(self.bs_conducted_power, int) or self.bs_conducted_power <= 0:
            raise ValueError(f"ParametersNTN: bs_conducted_power must be a positive integer, but is {
                             self.bs_conducted_power}")

        if not isinstance(self.bs_backoff_power, int) or self.bs_backoff_power < 0:
            raise ValueError(
                f"ParametersNTN: bs_backoff_power must be a non-negative integer, but is {self.bs_backoff_power}")

        if not np.all((0 <= self.bs_azimuth) & (self.bs_azimuth <= 360)):
            raise ValueError(
                "ParametersNTN: bs_azimuth values must be between 0 and 360 degrees")

        if not np.all((0 <= self.bs_elevation) & (self.bs_elevation <= 90)):
            raise ValueError(
                "ParametersNTN: bs_elevation values must be between 0 and 90 degrees")
