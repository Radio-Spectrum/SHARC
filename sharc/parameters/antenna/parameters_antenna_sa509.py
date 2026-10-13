from sharc.parameters.parameters_base import ParametersBase

from dataclasses import dataclass


@dataclass
class ParametersAntennaSA509(ParametersBase):
    """
    Parameters for the ITU-R SA.509-3 radio astronomy antenna pattern.

    The peak gain is NOT read from the yaml: it is derived from the aperture,
    G_0 = 10*log10(eta * (pi*D/lambda)^2), as prescribed by the recommendation.
    Hence only the diameter and the aperture efficiency are needed here;
    "frequency" is injected by ParametersAntenna.set_external_parameters from
    the system's own centre frequency.
    """
    # Antenna diameter [m]
    diameter: float = None

    # Aperture efficiency [0-1]
    antenna_efficiency: float = None

    # Centre frequency [MHz] -- set externally, not by the user
    frequency: float = None

    def validate(self, ctx):
        """
        Validate the SA.509 antenna parameters.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        Raises
        ------
        ValueError
            If any parameter is invalid.
        """
        if None in [self.diameter, self.antenna_efficiency, self.frequency]:
            raise ValueError(f"{ctx} needs to have all its parameters set")

        if not isinstance(self.diameter, (int, float)) or self.diameter <= 0:
            raise ValueError(f"{ctx}.diameter needs to be a positive number")

        if not isinstance(self.antenna_efficiency, (int, float)) or \
                not 0 < self.antenna_efficiency <= 1:
            raise ValueError(
                f"{ctx}.antenna_efficiency needs to be a number in (0, 1]",
            )

        if not isinstance(self.frequency, (int, float)):
            raise ValueError(f"{ctx}.frequency needs to be a number")
