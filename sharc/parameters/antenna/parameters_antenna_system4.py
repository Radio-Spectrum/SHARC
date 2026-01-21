# Implementation of ParametersAntennaSystem4 class
# The System 4 antenna was defined in WP4C Working Document 4C/356 from October 2025
# The antenna is based on S.1528 recommends 1.2
# It defines two sets of parameters for high elevation and low elevation beams
from dataclasses import dataclass, field

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528


@dataclass
class ParametersAntennaSystem4(ParametersBase):
    """Dataclass containing the Antenna System 4 parameters for the simulator.
    """
    section_name: str = "Antenna System 4"

    # Parameters for high elevation beams
    antenna_parameters_high: ParametersAntennaS1528 = field(
        # we don't care about frequency and bandwidth here. Just to make validation work.
        default_factory=lambda: ParametersAntennaS1528(
            frequency=-1,
            bandwidth=-1
        )
    )

    # Parameters for low elevation beams
    antenna_parameters_low: ParametersAntennaS1528 = field(
        # we don't care about frequency and bandwidth here. Just to make validation work.
        default_factory=lambda: ParametersAntennaS1528(
            frequency=-1,
            bandwidth=-1
        )
    )

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
