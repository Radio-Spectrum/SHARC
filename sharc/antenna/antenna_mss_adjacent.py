
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

    def __init__(self, frequency_MHz: float):
        """
        Initialize the AntennaMSSAdjacent class.

        Parameters
        ----------
        frequency_MHz : float
            Frequency in MHz for the antenna model.
        """
        super().__init__()
        self.frequency = frequency_MHz

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
        theta_rad = np.minimum(theta_rad, np.pi / 2 - 1e-4)
        return 20 * np.log10(self.frequency / 2e3) + 10 * \
            np.log10(np.cos(theta_rad))


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    frequency = 2170
    theta = np.linspace(0.01, 90, num=100000)

    antenna = AntennaMSSAdjacent(frequency)
    gain = antenna.calculate_gain(off_axis_angle_vec=theta)

    def create_plot_adj_channel(frequency, theta, chn, ax=None):
        """
        Create a plot for the adjacent channel mask for MSS antennas.

        Parameters
        ----------
        frequency : float
            Frequency in MHz.
        theta : np.array
            Array of off-axis angles in degrees.
        chn : int
            Channel number (-1 or 1).
        ax : matplotlib.axes.Axes, optional
            Matplotlib axis to plot on. If None, a new figure and axis are created.

        Returns
        -------
        matplotlib.axes.Axes
            The axis with the plot.
        """
        tranls = {
            -1: 0,
            1: -55.6,
            2: -73.6,
            3: -83.6,
        }
        if chn == -1:
            ylabel = "Gain [dB]"
        else:
            ylabel = f"EIRP_{chn}"

        if ax is None:
            fig = plt.figure(facecolor='w', edgecolor='k')
            ax1 = fig.add_subplot()
        else:
            ax1 = ax

        ax1.plot(theta, gain + tranls[chn])
        ax1.grid(True)
        ax1.set_xlabel(r"Off-axis angle $\theta$ [deg]")
        ax1.set_ylabel(ylabel)

        label = f"$f = {frequency / 1e3: .3f}$ GHz"
        if chn != -1:
            label += f", channel {chn}"
        # ax1.semilogx(
        ax1.plot(
            theta, gain,
            label=label,
        )
        ax1.legend(loc="lower left")
        ax1.set_xlim((theta[0], theta[-1]))
        ax1.set_ylim((-80, 10))

        return ax1

    create_plot_adj_channel(frequency, theta, -1)
    plt.show()
    ax = create_plot_adj_channel(frequency, theta, 1)
    create_plot_adj_channel(frequency, theta, 2, ax)
    create_plot_adj_channel(frequency, theta, 3, ax)
    plt.show()
