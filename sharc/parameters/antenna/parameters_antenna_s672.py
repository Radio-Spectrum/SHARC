# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaS672(ParametersBase):
    """Dataclass containing the Antenna Pattern S.672 parameters for the simulator.
    """
    section_name: str = "ITU-R-S.678"
    # Peak antenna gain [dBi]
    antenna_gain: float | None = None
    # The required near-in-side-lobe level (dB) relative to peak gain
    # according to ITU-R S.672-4
    antenna_l_s: float | None = None
    # 3 dB beamwidth angle (3 dB below maximum gain) [degrees]
    antenna_3_dB_bw: float | None = None

    def load_parameters_from_file(self, config_file: str):
        """Load the parameters from file an run a sanity check.

        Parameters
        ----------
        file_name : str
            the path to the configuration file

        Raises
        ------
        ValueError
            if a parameter is not valid
        """
        super().load_parameters_from_file(config_file)

        self.validate("antenna_s678")

    def load_from_parameters(self, param: ParametersBase):
        """Load from another parameter object

        Parameters
        ----------
        param : ParametersBase
            Parameters object containing ParametersAntennaS1528
        """
        self.antenna_l_s = param.antenna_l_s
        self.antenna_3_dB_bw = param.antenna_3_dB_bw
        return self

    def set_external_parameters(self, **kwargs):
        """
        This method is used to "propagate" parameters from external context
        to the values required by antenna S1528.
        """
        attr_list = [a for a in dir(self) if not a.startswith('__')]

        for k, v in kwargs.items():
            if k in attr_list:
                setattr(self, k, v)
            else:
                raise ValueError(
                    f"Parameter {k} is not a valid attribute of {
                        self.__class__.__name__}")

        self.validate("S.1528")

    def validate(self, ctx: str):
        """
        Validate the parameters for the S.1528 antenna configuration.

        Checks that required attributes are set and that the antenna pattern is valid.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        # Now do the sanity check for some parameters
        if None in [self.antenna_l_s, self.antenna_3_dB_bw]:
            raise ValueError(
                f"{ctx}.[antenna_l_s, antenna_3_dB_bw] = {[self.antenna_l_s, self.antenna_3_dB_bw]}.\
                They need to all be set!")
