from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersHemisphericAntenna(ParametersBase):
    """
    Defines the parameter structure for a generic hemispheric antenna gain model.
    
    Attributes
    ----------
    gain_upper : float
        Gain (in dBi) in the upper hemisphere, typically when off-axis angle <= cutoff_angle.
        
    gain_lower : float
        Gain (in dBi) in the lower hemisphere, when off-axis angle > cutoff_angle.
        
    cutoff_angle : float
        Threshold off-axis angle (in degrees) between upper and lower hemispheres.
        Default is 80 degrees, which corresponds to 10 degrees elevation.
    """
    gain_upper: float = None
    gain_lower: float = None
    cutoff_angle: float = 80.0  # default used for GNSS-type antennas

    def validate(self, ctx):
        """
        Manually validates parameter values, since this is not done automatically by the loader.

        Parameters
        ----------
        ctx : str
            Context string to identify the parameter object in error messages.
        """
        if self.gain_upper is None or self.gain_lower is None:
            raise ValueError(f"{ctx} requires both gain_upper and gain_lower to be set")

        if not isinstance(self.gain_upper, (int, float)):
            raise ValueError(f"{ctx}.gain_upper must be a number")

        if not isinstance(self.gain_lower, (int, float)):
            raise ValueError(f"{ctx}.gain_lower must be a number")

        if not isinstance(self.cutoff_angle, (int, float)):
            raise ValueError(f"{ctx}.cutoff_angle must be a number")

        if not (0.0 <= self.cutoff_angle <= 180.0):
            raise ValueError(f"{ctx}.cutoff_angle must be between 0 and 180 degrees")
