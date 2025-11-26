
# -*- coding: utf-8 -*-
"""Antenna model for Cosine Antenna channel systems."""
from sharc.antenna.antenna import Antenna

import numpy as np


class AntennaElementCosine(Antenna):
    """
    Implements antenna part of EIRP mask for MSS-DC systems
    as defined in the WP4C Working Document 4C/356-E.
    """

    def __init__(self,):
        """
        Initialize the AntennaElementCosine class.

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
        theta_rad = np.minimum(theta_rad, np.pi / 2 - 1e-5)
        return np.log10(np.cos(theta_rad))


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    theta = np.linspace(0.01, 90, num=1000)
    antenna = AntennaElementCosine()
    gain = antenna.calculate_gain(off_axis_angle_vec=theta)
    fig = plt.figure(facecolor='w', edgecolor='k')
    ax = fig.add_subplot()
    ax.plot(theta, gain)
    ax.grid(True)
    ax.set_title("Antenna Element Cosine Pattern")
    ax.set_xlabel(r"Off-axis angle $\theta$ [deg]")
    ax.set_ylabel("Antenna Gain [dBi]")
    ax.set_xlim((theta[0], theta[-1]))
    ax.set_ylim((-80, 10))
    plt.show()
