
# -*- coding: utf-8 -*-
"""Antenna model for MSS adjacent channel systems."""
from sharc.antenna.antenna import Antenna

import numpy as np


class AntennaMSSAdjacent(Antenna):
    """
    Implements part of EIRP mask for MSS-DC systems given in document WPGC
    as defined in the WP4C Working Document 4C/356-E
    You can choose the adjacent channel by choosing the tx power
    You need to also make sure ACLR_db = 0, otherwise SHARC's implementation will
    mess the EIRP up.
    """

    def __init__(self,):
        """
        Initialize the AntennaMSSAdjacent class.

        """
        super().__init__()

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculate the antenna gain for the given off-axis angles.

        Parameters
        ----------
        *args : tuple
            Positional arguments (not used).
        **kwargs : dict
            Keyword arguments, expects 'off_axis_angle_vec' as input.

        Returns
        -------
        np.array
            Calculated antenna gain values.
        """
        theta_rad = np.deg2rad(np.absolute(kwargs["off_axis_angle_vec"]))
        return 10 * np.log10(np.cos(theta_rad) + 1e-5)


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    frequency = 2170
    theta = np.linspace(0.01, 90, num=100000)
    antenna = AntennaMSSAdjacent(frequency)
    gain = antenna.calculate_gain(off_axis_angle_vec=theta)
    fig = plt.figure(facecolor='w', edgecolor='k')
    ax = fig.add_subplot()
    ax.plot(theta, gain)
    ax.grid(True)
    ax.set_xlabel(r"Off-axis angle $\theta$ [deg]")
    ax.set_ylabel("Antenna Gain [dBi]")
    ax.set_xlim((theta[0], theta[-1]))
    ax.set_ylim((-80, 10))
    plt.show()