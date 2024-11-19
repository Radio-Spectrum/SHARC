# -*- coding: utf-8 -*-
"""Parameters definitions for P528 propagation model
"""
from dataclasses import dataclass
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP528(ParametersBase):
    """Dataclass containing the P.528 propagation model parameters
    """
    # Parameters for the P.528 propagation model
    time_percentage: str = "RANDOM"  # Time percentage between 1-99 or "RANDOM"
    polarization: str = "RANDOM"    # 0 (horizontal), 1 (vertical) or "RANDOM"

    def load_from_parameters(self, param: ParametersBase):
        """Used to load parameters of P.528 from IMT or system parameters

        Parameters
        ----------
        param : ParametersBase
            IMT or system parameters
        """
        if hasattr(param, 'time_percentage'):
            self.time_percentage = param.time_percentage
        if hasattr(param, 'polarization'):
            self.polarization = param.polarization
