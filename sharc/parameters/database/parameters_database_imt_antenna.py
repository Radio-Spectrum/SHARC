# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 16:29:36 2017

@author: Calil
"""
import numpy as np
from dataclasses import dataclass

@dataclass
class AntennaParamsFromFile:
    """
    Definition of antenna parameters read from a .csv or .xlsx database.
    """

    # BS number of rows and columns in antenna array.
    n_rows: int
    n_columns: int

    # Beamforming gain [dB].
    beamforming_gain: float

    # BS/UE maximum transmit/receive element gain [dBi].
    element_max_g: float

    # Total transmit power [dBm].
    tx_power: float

    # Sub-array number of rows
    sub_num_rows: int

    # Downtilt
    downtilt: float

    def __post_init__(self):
        """
        Validates fields after initialization.
        """
        self.validate()

        # Theoretical beamforming gain
        th_bf_gain = 10 * np.log10( self.n_columns * self.n_rows )
        # Desired beamforming gain
        pt_bf_gain = self.beamforming_gain
        # Beamforming efficiency reduction (dB)
        bf_gain_eff = th_bf_gain - pt_bf_gain

        # Gain per element compensated by beamforming efficiency
        self.element_max_g = self.element_max_g - bf_gain_eff

    def validate(self):
        """
        Validate inputs.
        """
        if not isinstance(self.n_rows, int) or self.n_rows <= 0:
            raise ValueError("n_rows must be a positive integer")
        if not isinstance(self.n_columns, int) or self.n_columns <= 0:
            print(self.n_columns)
            raise ValueError("n_columns must be a positive integer")
        if not isinstance(self.sub_num_rows, int) or self.sub_num_rows <= 0:
            raise ValueError("sub_num_rows must be a positive integer")
        if not isinstance(self.beamforming_gain, (int, float)) or self.beamforming_gain < 0:
            raise ValueError("Value must be a positive number")
        if not isinstance(self.tx_power, (int, float)):
            raise ValueError("Value must be a number")
        if not isinstance(self.element_max_g, (int, float)):
            raise ValueError("Value must be a number")