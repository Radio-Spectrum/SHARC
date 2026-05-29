# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaF1245Fs(ParametersBase):
    """
    Parameters for the ITU-R F.1245 Fixed-Service antenna pattern.

    Attributes
    ----------
    gain : float
        Peak antenna gain [dBi]. Defaults to -25.
    diameter : float
        Antenna diameter [m].
    frequency : float
        Carrier frequency [MHz].
    """
    gain: float = -25
    diameter: float = None
    frequency: float = None

    def validate(self, ctx: str):
        if None in [self.gain, self.diameter, self.frequency]:
            raise ValueError(f"{ctx}.antenna_3_dB should be set to a number")
