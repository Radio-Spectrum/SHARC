
# -*- coding: utf-8 -*-
"""Antenna model for Cosine Antenna channel systems."""
from sharc.antenna.antenna import Antenna

import numpy as np

import numpy as np

def angle_from_az_el(phi_v, theta_v, phi_n, theta_n):
    """
    Angle between two 3D directions.

    phi   : azimuth (rad), from +X in the XY-plane
    theta : polar angle (rad), from +Z

    Inputs may be scalars or array-like (NumPy broadcasting supported).
    """
    phi_v = np.asarray(phi_v)
    theta_v = np.asarray(theta_v)
    phi_n = np.asarray(phi_n)
    theta_n = np.asarray(theta_n)

    cos_angle = (
        np.cos(theta_v) * np.cos(theta_n) + np.sin(theta_v) * np.sin(theta_n) * np.cos(phi_v - phi_n)
    )

    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    angle = np.degrees(np.arccos(cos_angle))

    return angle.item() if angle.ndim == 0 else angle


class AntennaSystem3Oob(Antenna):
    """
    Implements the antenna for the System3 OOBE mask model.
    This is very similar to the Cosine Antenna pattern but with hacks specific to System3 OOBE.
    """

    def __init__(self, gain=0.0, azimuth_to_nadir=0.0, elevation_to_nadir=90.0):
        """
        Initialize the AntennaSystem3Oob class.

        Parameters
        ----------
        gain : float
            The fixed gain value for the antenna in dBi.
        azimuth_to_nadir : float
            The azimuth angle to nadir in degrees.
        elevation_to_nadir : float
            The elevation angle to nadir in degrees.
        """
        super().__init__()
        self.gain_dbi = gain
        self.azimuth_to_nadir = azimuth_to_nadir
        self.elevation_to_nadir = elevation_to_nadir

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
        # phi and theta in the global coordinate system of the simulation.
        phi_vec = np.asarray(kwargs["phi_vec"])
        theta_vec = np.asarray(kwargs["theta_vec"])
        off_axis_to_nadir = angle_from_az_el(phi_vec, theta_vec, self.azimuth_to_nadir, self.elevation_to_nadir)
        off_axis_rad = np.minimum(
            np.deg2rad(np.minimum(off_axis_to_nadir, 180 - off_axis_to_nadir)),
            np.pi / 2 - 1e-5
        )
        return 10 * np.log10(np.cos(off_axis_rad)) + self.gain_dbi

    def set_gain(self, gain: float):
        """
        Set the antenna gain.

        Parameters
        ----------
        gain : float
            The gain value to set in dBi.
        """
        self.gain_dbi = gain


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    theta = np.linspace(0.01, 90.01, num=1000)
    antenna = AntennaSystem3Oob(gain=0.0)
    gain = antenna.calculate_gain(off_axis_angle_vec=theta)
    fig = plt.figure(facecolor='w', edgecolor='k')
    ax = fig.add_subplot()
    ax.plot(theta, gain)
    ax.grid(True)
    ax.set_title("Antenna System3 OOBE Pattern")
    ax.set_xlabel(r"Off-axis angle $\theta$ [deg]")
    ax.set_ylabel("Antenna Gain [dBi]")
    ax.set_xlim((theta[0], theta[-1]))
    ax.set_ylim((-40, 10))
    plt.show()
