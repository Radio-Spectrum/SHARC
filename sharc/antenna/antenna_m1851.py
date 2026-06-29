# -*- coding: utf-8 -*-

from sharc.antenna.antenna import Antenna

import numpy as np
import math


class AntennaM1851(Antenna):
    """
    Implementa o diagrama de ganho de potência normalizada CSC² para 
    radares terrestres (ITU-R M.1851-12).
    """

    def __init__(self, param):
        super().__init__()
        # Parâmetros fornecidos
        self.gain = getattr(param, 'gain', 30.0)         # Ganho máximo a ser somado
        self.theta_3 = getattr(param, 'theta_3', 2.0)
        self.theta_start = getattr(param, 'theta_start', 1.0)
        self.theta_end = getattr(param, 'theta_end', 45.0)
        self.g_0 = getattr(param, 'g_0', -30.0)          # Nível de floor (G_0)

        # Cálculo de theta_tilt
        self.theta_tilt = self.theta_start - (self.theta_3 / 2.0)

        # Cálculo de theta_null
        self.theta_null = self.theta_tilt - (self.theta_3 / 0.88)

    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calcula o ganho da antena para os ângulos de elevação dados (off-axis).

        Parameters
        ----------
        *args : tuple
            Argumentos posicionais (não utilizados).
        **kwargs : dict
            Argumentos de palavra-chave, espera 'off_axis_angle_vec'.

        Returns
        -------
        np.array
            Valores calculados de ganho da antena (Ganho normalizado + Ganho máximo).
        """
        # Utiliza-se os ângulos originais para manter a coerência de direção (sem np.absolute)
        theta = kwargs["off_axis_angle_vec"]
        
        # Inicializa todo o array com o nível G_0 (Região 3 ou "otherwise")
        pattern = np.full(theta.shape, self.g_0, dtype=float)

        # -------------------------------------------------------------
        # Região 1: theta_null <= theta <= theta_start
        # -------------------------------------------------------------
        idx_1 = np.where((theta >= self.theta_null) & (theta <= self.theta_start))[0]
        if len(idx_1) > 0:
            mu = (np.pi * 50.8 * np.sin(np.deg2rad(theta[idx_1] - self.theta_tilt))) / self.theta_3
            
            # np.sinc(x) do numpy equivale a sin(pi * x) / (pi * x). 
            # Portanto, passamos mu / np.pi para obtermos sin(mu) / mu sem risco de div/0
            sinc_val = np.sinc(mu / np.pi)
            
            # Clip para evitar log10(0)
            sinc_val = np.clip(np.abs(sinc_val), 1e-12, None)
            pattern[idx_1] = 20 * np.log10(sinc_val)

        # -------------------------------------------------------------
        # Região 2: theta_start < theta <= theta_end
        # -------------------------------------------------------------
        idx_2 = np.where((theta > self.theta_start) & (theta <= self.theta_end))[0]
        if len(idx_2) > 0:
            # csc(x) = 1 / sin(x)
            csc_theta = 1.0 / np.sin(np.deg2rad(theta[idx_2]))
            csc_start = 1.0 / np.sin(np.deg2rad(self.theta_start))
            
            # Cálculo de G_unif(theta_start) - a constante que é somada na região 2
            mu_start = (np.pi * 50.8 * np.sin(np.deg2rad(self.theta_start - self.theta_tilt))) / self.theta_3
            sinc_start = np.sinc(mu_start / np.pi)
            sinc_start = max(abs(sinc_start), 1e-12)
            
            term1 = 20 * np.log10(np.abs(csc_theta / csc_start))
            term2 = 20 * np.log10(sinc_start)
            
            pattern[idx_2] = term1 + term2

        # -------------------------------------------------------------
        # Soma final do Ganho do usuário
        # -------------------------------------------------------------
        pattern += self.gain

        return pattern


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    class ParametersM1851Mock:
        pass

    # Exemplo com parâmetros típicos
    param_mock = ParametersM1851Mock()
    param_mock.gain = 34.0
    param_mock.theta_3 = 4.8
    param_mock.theta_start = 6
    param_mock.theta_end = 30.0
    param_mock.g_0 = -55

    antenna = AntennaM1851(param_mock)

    # Varredura de elevação (ex: 0 a 60 graus para ver o lóbulo principal e o floor)
    theta_vec = np.linspace(-10, 60, num=10000)
    
    gain_vec = antenna.calculate_gain(off_axis_angle_vec=theta_vec)

    fig = plt.figure(figsize=(9, 6), facecolor='w', edgecolor='k')

    plt.plot(theta_vec, gain_vec, "-r", label=f"$Gain={param_mock.gain}$ dBi, $G_0={param_mock.g_0}$ dB, $\\theta_3={param_mock.theta_3}^\\circ$")

    plt.title("Diagrama Normalizado CSC² ITU-R M.1851-12")
    plt.xlabel(r"Ângulo de elevação $\theta$ [deg]")
    plt.ylabel("Ganho [dBi]")
    
    # Linhas auxiliares para identificar as transições
    plt.axvline(antenna.theta_null, color='gray', linestyle='--', linewidth=0.8, label=f'$\\theta_{{Null}} = {antenna.theta_null:.2f}^\\circ$')
    plt.axvline(antenna.theta_tilt, color='lightblue', linestyle='--', linewidth=0.8, label=f'$\\theta_{{Tilt}} = {antenna.theta_tilt:.2f}^\\circ$')
    plt.axvline(antenna.theta_start, color='blue', linestyle='--', linewidth=0.8, label=f'$\\theta_{{Start}} = {antenna.theta_start:.2f}^\\circ$')
    plt.axvline(antenna.theta_end, color='green', linestyle='--', linewidth=0.8, label=f'$\\theta_{{End}} = {antenna.theta_end:.2f}^\\circ$')

    plt.legend(loc="upper right")
    plt.xlim((theta_vec[0], theta_vec[-1]))
    plt.grid(True)
    plt.show()