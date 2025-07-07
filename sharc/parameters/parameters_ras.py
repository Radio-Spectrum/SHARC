# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation


@dataclass
class ParametersRas(ParametersSingleEarthStation):
    """
    Simulation parameters for Radio Astronomy Service
    """
    section_name: str = "ras"
    polarization_loss: float | None = None
