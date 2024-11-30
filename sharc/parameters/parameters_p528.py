# -*- coding: utf-8 -*-
"""Parameters definitions for P528 propagation model
"""
from dataclasses import dataclass
from typing import Union
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP528(ParametersBase):
    """Dataclass containing the P.528 propagation model parameters"""

    # Time percentage between 1-99 or "RANDOM"
    time_percentage: Union[float, str] = "RANDOM"
    # 0 (horizontal), 1 (vertical) polarization or "RANDOM"
    polarization: Union[int, str] = "RANDOM"
    # Channel model, possible values are "P528"
    channel_model: str = "P528"
@dataclass
class ParametersP528(ParametersBase):
    """Dataclass containing the P.528 propagation model parameters"""

    # Time percentage between 1-99 or "RANDOM"
    time_percentage: Union[float, str] = "RANDOM"
    # 0 (horizontal), 1 (vertical) polarization or "RANDOM"
    polarization: Union[int, str] = "RANDOM"
    # Channel model, possible values are "P528"
    channel_model: str = "P528"

    def load_from_parameters(self, param: ParametersBase):
        """Used to load parameters of P.528 from parent parameters

        Parameters
        ----------
        param : ParametersBase
            Parent parameters object containing P.528 values in param_p528
        """
        # Get values from the param_p528 section of parent parameters
        if hasattr(param, 'param_p528'):
            config = getattr(param, 'param_p528')
            if hasattr(config, 'time_percentage'):
                self.time_percentage = config.time_percentage
            if hasattr(config, 'polarization'):
                self.polarization = config.polarization
            if hasattr(config, 'channel_model'):
                self.channel_model = config.channel_model

        # Validate time percentage
        if isinstance(self.time_percentage, str):
            if self.time_percentage != "RANDOM":
                raise ValueError(
                    f"ParametersP528: Invalid time_percentage {self.time_percentage}. "
                    "Must be between 1-99 or 'RANDOM'"
                )
        else:
            try:
                time_pct = float(self.time_percentage)
                if time_pct < 1 or time_pct > 99:
                    raise ValueError(
                        f"ParametersP528: Invalid time_percentage {time_pct}. "
                        "Must be between 1-99 or 'RANDOM'"
                    )
            except (ValueError, TypeError):
                raise ValueError(
                    f"ParametersP528: Invalid time_percentage {self.time_percentage}. "
                    "Must be between 1-99 or 'RANDOM'"
                )

        # Validate polarization
        if isinstance(self.polarization, str):
            if self.polarization != "RANDOM":
                raise ValueError(
                    f"ParametersP528: Invalid polarization {self.polarization}. "
                    "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                )
        else:
            try:
                pol = int(self.polarization)
                if pol not in [0, 1]:
                    raise ValueError(
                        f"ParametersP528: Invalid polarization {pol}. "
                        "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                    )
            except (ValueError, TypeError):
                raise ValueError(
                    f"ParametersP528: Invalid polarization {self.polarization}. "
                    "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                )
