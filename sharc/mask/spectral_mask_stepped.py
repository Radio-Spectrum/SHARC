# -*- coding: utf-8 -*-

from sharc.mask.spectral_mask import SpectralMask

import numpy as np
import matplotlib.pyplot as plt


class SpectralMaskStepped(SpectralMask):
    """
    Implements a stepped spectral mask defined by user-provided steps.
    """
    def __init__(
            self,
            freq_mhz: float,
            band_mhz: float,
            mask_steps_dBm_mhz: list):
        """
        Class constructor.
        Parameters:
            freq_mhz (float): center frequency of station in MHz
            band_mhs (float): transmitting bandwidth of station in MHz
            mask_steps_dBm_mhz (list): list of spectral mask step values in dBm/MHz. Each step corresponds to a
            multiple of the bandwidth away from the band edge.
            The last step is considered to the spurious domain.
        """

        self.mask_steps_dBm_mhz = mask_steps_dBm_mhz
        self.freq_mhz = freq_mhz
        self.band_mhz = band_mhz

        self.delta_f_lim = np.array(
            [self.band_mhz * i for i in range(len(self.mask_steps_dBm_mhz))]
        )

        self.freq_lim = np.concatenate((
            (freq_mhz - band_mhz / 2) - self.delta_f_lim[::-1],
            (freq_mhz + band_mhz / 2) + self.delta_f_lim,
        ))

    def set_mask(self, p_tx=0):
        """
        Set the spectral mask values based on the defined steps.

        Parameters:
            p_tx (float): Transmit power in dBm/MHz.
        """
        self.p_tx = p_tx - 10 * np.log10(self.band_mhz)
        self.mask_dbm = np.concatenate([self.mask_steps_dBm_mhz[::-1], [self.p_tx], self.mask_steps_dBm_mhz])


if __name__ == '__main__':

    freq = 2100  # MHz
    band = 5  # MHz
    p_tx = 0.0 + 10 * np.log10(band)  # dBm
    spourious_emissions = -30.0  # dBm/MHz

    mask_steps = [-10, -15, -20]  # dBm/MHz
    mask_steps = np.concatenate([mask_steps, [-30]])  # dBm/MHz

    # Create mask
    msk = SpectralMaskStepped(freq, band, mask_steps)
    msk.set_mask(p_tx)

    # Frequencies
    freqs = np.linspace(-60, 60, num=1000) + freq

    # Mask values
    mask_val = np.ones_like(freqs) * msk.mask_dbm[0]
    for k in range(len(msk.freq_lim) - 1, -1, -1):
        mask_val[np.where(freqs < msk.freq_lim[k])] = msk.mask_dbm[k]

    # Plot
    plt.plot(freqs, mask_val)
    plt.title("Stepped Spectral Mask")
    plt.xlim([freqs[0], freqs[-1]])
    plt.xlabel(r"$\Delta$f [MHz]")
    plt.ylabel("Spectral Mask [dBc]")
    plt.grid()
    plt.show()

    print(msk.power_calc(center_f=freq + 1 * band, band=band))
    print(msk.power_calc(center_f=freq + 2 * band, band=band))
    print(msk.power_calc(center_f=freq + 3 * band, band=band))
