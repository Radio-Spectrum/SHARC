# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaF1245FS(ParametersBase):
    """Dataclass containing the ITU-R F.1245 (fixed service) antenna pattern parameters.

    The section is written as::

        antenna:
          pattern: ITU-R F.1245_fs
          gain: 38
          itu_r_f_1245_fs:
            gain: 38     # optional, defaults to the antenna's gain
            diameter: 4

    ``frequency`` is not read from the configuration file: it is set by the
    parent system through ``ParametersAntenna.set_external_parameters()``.
    """
    section_name: str = "ITU-R-F.1245_fs"

    # Peak antenna gain [dBi]
    gain: float | None = None

    # Antenna diameter [meters]
    diameter: float | None = None

    # Center frequency [MHz]. Set by the parent system, not by the .yaml file
    frequency: float | None = None

    def validate(self, ctx: str):
        """
        Validate the ITU-R F.1245 fixed service antenna parameters.

        Parameters
        ----------
        ctx : str
            Context string for error messages.

        Raises
        ------
        ValueError
            If any parameter is invalid.
        """
        if None in [self.gain, self.diameter, self.frequency]:
            raise ValueError(
                f"{ctx}.[gain, diameter, frequency] = "
                f"{[self.gain, self.diameter, self.frequency]}. They need to all be set!",
            )

        if not isinstance(self.gain, (int, float)):
            raise ValueError(f"{ctx}.gain needs to be a number")

        if not isinstance(self.diameter, (int, float)) or self.diameter <= 0:
            raise ValueError(f"{ctx}.diameter needs to be a positive number")

        if not isinstance(self.frequency, (int, float)):
            raise ValueError(f"{ctx}.frequency needs to be a number")
