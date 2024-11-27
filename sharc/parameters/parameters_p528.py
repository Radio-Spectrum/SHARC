# -*- coding: utf-8 -*-
"""Parameters definitions for P528 propagation model
"""
from dataclasses import dataclass
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP528(ParametersBase):
    """Dataclass containing the P.528 propagation model parameters"""

    # Time percentage between 1-99 or "RANDOM"
    time_percentage: str = "RANDOM"
    # 0 (horizontal), 1 (vertical) polarization or "RANDOM"
    polarization: str = "RANDOM"
    # Channel model, possible values are "P528"
    channel_mode: str = "P528"

    def load_parameters_from_file(self, config_file: str):
        """Load the parameters from file and run validation

        Parameters
        ----------
        config_file : str
            Path to the configuration file

        Raises
        ------
        ValueError
            If a parameter is not valid
        """
        super().load_parameters_from_file(config_file)

        # Validate time percentage
        if self.time_percentage != "RANDOM":
            try:
                time_pct = float(self.time_percentage)
                if time_pct < 1 or time_pct > 99:
                    raise ValueError(
                        f"ParametersP528: Invalid time_percentage {time_pct}. " "Must be between 1-99 or 'RANDOM'"
                    )
            except ValueError:
                raise ValueError(
                    f"ParametersP528: Invalid time_percentage {self.time_percentage}. " "Must be between 1-99 or 'RANDOM'"
                )

        # Validate polarization
        if self.polarization != "RANDOM":
            try:
                pol = int(self.polarization)
                if pol not in [0, 1]:
                    raise ValueError(
                        f"ParametersP528: Invalid polarization {pol}. " "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                    )
            except ValueError:
                raise ValueError(
                    f"ParametersP528: Invalid polarization {self.polarization}. "
                    "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                )
