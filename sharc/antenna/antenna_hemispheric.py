import numpy as np

from sharc.antenna.antenna import Antenna
from sharc.parameters.antenna.parameters_antenna_hemispheric import \
    ParametersHemisphericAntenna


class HemisphericAntennaPattern(Antenna):
    """
    Implements a simple hemispheric antenna pattern model.

    The antenna gain is constant in the upper and lower hemispheres,
    based on a cutoff off-axis angle.
    """

    def __init__(self, param: ParametersHemisphericAntenna):
        """
        Initializes the hemispheric antenna with provided parameters.

        Parameters
        ----------
        param : ParametersHemisphericAntenna
            Parameters for the hemispheric gain model.
        """
        super().__init__()
        self.gain_upper = param.gain_upper
        self.gain_lower = param.gain_lower
        self.cutoff_angle = param.cutoff_angle

    def calculate_gain(self, *args, **kwargs) -> np.ndarray:
        """
        Calculates gain based on elevation angle interpreted as off_axis_angle_vec.

        Parameters
        ----------
        off_axis_angle_vec : np.ndarray
            Array of elevation angles in degrees (0° = horizon, 90° = zenith).

        Returns
        -------
        gain : np.ndarray
            Gain values corresponding to elevation angle threshold.
        """
        elevation = np.abs(kwargs["off_axis_angle_vec"])
        gain = np.full(elevation.shape, self.gain_lower)
        gain[elevation >= self.cutoff_angle] = self.gain_upper
        return gain


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Angle vector interpreted as elevation angles from 0° to 90°
    phi = np.linspace(0, 90, 1000)

    # GNSS-like antenna: higher gain above cutoff angle (e.g., >10°)
    param = ParametersHemisphericAntenna(gain_upper=3.0, gain_lower=-5.0, cutoff_angle=10.0)
    antenna = HemisphericAntennaPattern(param)
    gain = antenna.calculate_gain(off_axis_angle_vec=phi)

    plt.plot(phi, gain, label="Elevation cutoff = 10°")
    plt.title("Elevation-Based Hemispheric Antenna Pattern")
    plt.xlabel("Elevation angle [°] (0° = horizon)")
    plt.ylabel("Gain [dBi]")
    plt.grid()
    plt.legend()
    plt.ylim([-15, 5])
    plt.show()
