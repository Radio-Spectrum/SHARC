# -*- coding: utf-8 -*-

from sharc.antenna.antenna import Antenna

import numpy as np
import math


class AntennaF1336(Antenna):
    """
    Implements reference radiation patterns for system antennas for use
    in coordination studies and interference assessment (ITU-R F.1336-5)
    """

    def __init__(self, param):
        super().__init__()
        self.gain = getattr(param, 'gain', 12.0)
        self.k = getattr(param, 'k', 0.7)
        self.cable_loss = getattr(param, 'cable_loss', 2.0)

        self.theta_3 = 107.6 * math.pow(10, -0.1 * self.gain)
        self.theta_4 = self.theta_3 * math.sqrt(1 - (1 / 1.2) * math.log10(self.k + 1))

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculate the antenna gain for the given off-axis angles.

        Parameters
        ----------
        *args : tuple
            Positional arguments (not used).
        **kwargs : dict
            Keyword arguments, expects 'off_axis_angle_vec'.

        Returns
        -------
        np.array
            Calculated antenna gain values subtracted by the cable loss.
        """
        theta = np.absolute(kwargs["off_axis_angle_vec"])
        pattern = np.zeros(theta.shape)

        idx_0 = np.where(theta < self.theta_4)[0]
        pattern[idx_0] = self.gain - 12 * np.power(theta[idx_0] / self.theta_3, 2)

        idx_1 = np.where((self.theta_4 <= theta) & (theta < self.theta_3))[0]
        pattern[idx_1] = self.gain - 12 + 10 * math.log10(self.k + 1)

        idx_2 = np.where((self.theta_3 <= theta) & (theta <= 90))[0]
        pattern[idx_2] = self.gain - 12 + 10 * np.log10(np.power(theta[idx_2] / self.theta_3, -1.5) + self.k)

        # Se houver valores acima de 90 passados para a função (caso ocorra fora do escopo)
        # não haverá cálculo de ganho e ficarão em 0. Como o SHARC restringe 
        # a elevação de -90 a 90, o módulo |theta| será sempre <= 90.

        # Aplica a atenuação do cabo (cable_loss)
        pattern -= self.cable_loss

        return pattern


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    class ParametersF1336Mock:
        pass

    param_mock = ParametersF1336Mock()
    param_mock.gain = 12.0
    param_mock.k = 0.7
    param_mock.cable_loss = 2.0

    antenna = AntennaF1336(param_mock)

    theta_vec = np.linspace(-90, 90, num=100000)
    
    gain_vec = antenna.calculate_gain(off_axis_angle_vec=theta_vec)

    fig = plt.figure(figsize=(8, 7), facecolor='w', edgecolor='k')

    plt.plot(theta_vec, gain_vec, "-b", label=f"$G_0={param_mock.gain}$ dBi, $k={param_mock.k}$, Perda={param_mock.cable_loss} dB")

    plt.title("ITU-R F.1336-5 antenna radiation pattern")
    plt.xlabel(r"Elevation angle $\theta$ [deg]")
    plt.ylabel("Gain [dBi]")
    plt.legend(loc="lower center")
    plt.xlim((theta_vec[0], theta_vec[-1]))
    plt.grid(True)
    plt.show()
