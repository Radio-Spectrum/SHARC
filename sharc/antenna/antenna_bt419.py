"""
Implementation of the Broadcast System Antenna discriminations as described in Rec. ITU-R  BT.419-3.

Note that this is not an actual antenna pattern, but a discrimination pattern to be applied to the interference power 
received by the victim antenna. The pattern is defined as a function of the off-axis angle between the victim 
and the interfering antennas.

The antenna is *always* assumed to be pointing to the local horizon, so make sure that the elevation parameter
is set to 0.
"""

from sharc.antenna.antenna import Antenna
from sharc.parameters.antenna.parameters_antenna_bt419 import ParametersAntennaBT419

import numpy as np
import sys


class AntennaBt419(Antenna):
    """
    Implementation of the Broadcast System Antenna based on a fixed gain plus the
    discriminations as described in Rec. ITU-R  BT.419-3.
    according to Recommendation ITU-R S.672-4 Annex 1

    Note that this is not an actual antenna pattern, but a discrimination pattern to be applied to the interference power 
    received by the victim antenna. The pattern is defined as a function of the off-axis angle between the victim 
    and the interfering antennas.

    The antenna is *always* assumed to be pointing to the local horizon, so make sure that the elevation parameter
    is set to 0.

    For now, only Bands IV and V is implemented.

    """

    def __init__(self, param: ParametersAntennaBT419):
        super().__init__()

        self.max_gain = param.antenna_gain

        # TODO: Implement bands I to III.
        self.bs_system_band = param.bs_system_band

        if self.bs_system_band not in ["BAND_I", "BAND_II", "BAND_III", "BAND_IV", "BAND_V"]:
            raise ValueError(f"Band {self.bs_system_band} is not supported in BT.419 antenna discrimination pattern")

        if self.bs_system_band not in ["BAND_IV", "BAND_V"]:
            raise NotImplementedError(f"Band {self.bs_system_band} is not implemented in BT.419 antenna discrimination pattern, only Bands IV and V are implemented for now.")


    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculate the antenna gain for given off-axis angles based on a fixed gain plus BT.419 antenna discrimination.

        The BT.419 specifies only the azimuth angle on a 0 deg elevation plane (pointing to the local horizon).
        However the off-axis from the antenna boresight is considered as input, so the antenna is assumumed to be
        symmetric in the elevation plane.

        Parameters
        ----------
        *args : tuple
            Positional arguments (unused).
        **kwargs : dict
            Keyword arguments containing:
                - off_axis_angle_vec: off-axis angles (degrees) in the range [0, 180].

        Returns
        -------
        np.array
            Calculated gain values for the given angles.
        """
        theta_deg = np.abs(np.asarray(kwargs["off_axis_angle_vec"]))

        gain = np.zeros(theta_deg.shape)

        if self.bs_system_band in ["BAND_IV", "BAND_V"]:
            gain[np.where(theta_deg <= 20.0)[0]] = self.max_gain
            gain[np.where((theta_deg > 20.0) & (theta_deg <= 60.0))[0]] = \
                self.max_gain - 0.4 * (theta_deg[(theta_deg > 20.0) & (theta_deg <= 60.0)] - 20.0)
            gain[np.where(theta_deg > 60.0)[0]] = self.max_gain - 16.0
        else:
            raise NotImplementedError(f"Band {self.bs_system_band} is not implemented in BT.419 antenna discrimination pattern")

        return np.asarray(gain)


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    # initialize antenna parameters
    param = ParametersAntennaBT419()
    param.max_gain = 0.0
    param.bs_system_band = "V"

    fig = plt.figure(
        figsize=(12, 7), facecolor='w',
        edgecolor='k',
    )  # create a figure object

    plt.plot(
        np.linspace(0, 90, 100),
        AntennaBt419(param).calculate_gain(off_axis_angle_vec=np.linspace(0, 90, 100)),
        label="BT.419-3"
    )

    plt.title("ITU-R BT.419-3 Antenna Discrimination Pattern - Band V")
    plt.xlabel(r"Off-axis angle, $\theta$")
    plt.ylabel("Discrimination [dB]")
    plt.legend(loc="upper right")

    ax = plt.gca()
    ax.set_xticks(np.arange(0, 91, 10))

    plt.grid()

    # Plot considereing the gain of the antenna as well
    fig = plt.figure(
        figsize=(12, 7), facecolor='w',
        edgecolor='k',
    )

    param.max_gain = 14.14
    plt.plot(
        np.linspace(0, 180, 100),
        AntennaBt419(param).calculate_gain(off_axis_angle_vec=np.linspace(0, 180, 100)),
        label="BT.419-3 with gain"
    )
    plt.title("ITU-R BT.419-3 Discrimination + Gain - ISDB-T Fixed Reception - Band V")
    plt.xlabel(r"Off-axis angle, $\theta$")
    plt.ylabel("Antenna Gain [dB]")
    plt.legend(loc="upper right")
    plt.grid()

    plt.show()
