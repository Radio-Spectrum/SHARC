# -*- coding: utf-8 -*-
"""
Created on Tue Dec  5 11:06:56 2017

@author: Calil
"""

from sharc.support.enumerations import StationType
from sharc.mask.spectral_mask import SpectralMask

import numpy as np
import sys


class SpectralMaskImt2030(SpectralMask):

    def __init__(
        self,
        sta_type: StationType,
        freq_mhz: float,
        band_mhz: float,
        spurious_emissions: float,
        scenario: str = "OUTDOOR",
        category: str = "CatA",
    ):
        """
        Implements spectral emission mask:
            For Base Station
                CatA: Impements spectral emission mask from Document 5D/TEMP/275(Rev.1)
                    Table A 6 (AAS - ΔfOBUE = 100 MHz and from 7125 to 8400 MHz with 100MHz of channel bandwidth)
                CatB: Impements spectral emission mask from 3GPP TS 38.104 version 18.6.0 Release 18
                    Table 6.6.4.2.2.1-2b  (AAS - ΔfOBUE = 100 MHz - rom 7125 to 8400 MHz with 100MHz of channel bandwidth)
            For UE:
                Impements spectral emission mask from Document 3GPP TS 38.101-1 version 16.7.0 Release 16
                Table 6.5.2.2-1 (Pág. 201)
        to adjust the input parameter that defines the spurious emission level:
            Cat-A: -13 dBm/MHz
            Cat-B: -30 dBm/MHz
        """
        if sta_type is not StationType.IMT_BS and sta_type is not StationType.IMT_UE:
            message = "ERROR\nInvalid station type: " + str(sta_type)
            sys.stderr.write(message)
            sys.exit(1)

        if band_mhz not in [5, 10, 15, 20, 100]:
            message = "ERROR\nInvalid bandwidth for 3GPP mask: " + band_mhz
            sys.stderr.write(message)

        # Attributes
        self.spurious_emissions = spurious_emissions
        self.sta_type = sta_type
        self.scenario = scenario
        self.band_mhz = band_mhz
        self.freq_mhz = freq_mhz
        self.BScategory = category

        delta_f_lim = self.get_frequency_limits(self.sta_type, self.band_mhz)
        # delta_f_lim_flipped = np.flip(self.delta_f_lim,0)
        delta_f_lim_flipped = delta_f_lim[::-1]

        self.freq_lim = np.concatenate((
            (self.freq_mhz - self.band_mhz / 2) - delta_f_lim_flipped,
            (self.freq_mhz + self.band_mhz / 2) + delta_f_lim,
        ))

    def get_frequency_limits(
        self,
        sta_type: StationType,
        bandwidth: float,
    ) -> np.array:
        """
        Calculates the frequency limits of the spectrum emission masks. This
        implementation is valid only for bandwidths equal to 5, 10, 15 or 20 MHz.
        """

        if sta_type is StationType.IMT_BS:
            # Mask delta f breaking limits [MHz]
            delta_f_lim = np.arange(0, 50, .1)
            delta_f_lim = np.append(delta_f_lim, 100)
        else:
            delta_f_lim = np.array([0, 1, 5])
            if bandwidth == 5:
                delta_f_lim = np.append(delta_f_lim, np.array([6, 10]))
            if bandwidth == 10:
                delta_f_lim = np.append(delta_f_lim, np.array([10, 15]))
            if bandwidth == 15:
                delta_f_lim = np.append(delta_f_lim, np.array([15, 20]))
            if bandwidth == 20:
                delta_f_lim = np.append(delta_f_lim, np.array([20, 25]))
            else:
                delta_f_lim = np.append(delta_f_lim, np.array([100, 105]))
        return delta_f_lim

    def set_mask(self, p_tx=0):
        emission_limits = self.get_emission_limits(
            self.sta_type,
            self.band_mhz,
            self.spurious_emissions,
            self.BScategory
        )
        self.p_tx = p_tx - 10 * np.log10(self.band_mhz)
        # emission_limits = np.flip(emission_limits, 0)
        emission_limits_flipped = emission_limits[::-1]
        self.mask_dbm = np.concatenate((
            emission_limits_flipped,
            np.array([self.p_tx]),
            emission_limits,
        ))

    def get_emission_limits(
        self,
        sta_type: StationType,
        bandwidth: float,
        spurious_emissions: float,
        category: float
    ) -> np.array:
        if sta_type is StationType.IMT_BS:
            if category == "CatA":
                # emission limits in dBm/MHz
                emission_limits = 3 - 7 / 20 * (np.arange(.05, 50, .1) - .05)
                emission_limits = np.append(
                    emission_limits, np.array([-4, -13]),
                )
            else:
                emission_limits = 3 - 7 / 50 * (np.arange(.05, 50, .1) - .05)
                emission_limits = np.append(
                    emission_limits, np.array([-4, -15]),
                )
        else:
            if bandwidth >= 50:
                if bandwidth == 5:
                    limit_r1 = np.array([-13])
                elif bandwidth == 10:
                    limit_r1 = np.array([-13])
                elif bandwidth == 15:
                    limit_r1 = np.array([-13])
                elif bandwidth == 20:
                    limit_r1 = np.array([-13])
                emission_limits = np.append(
                    limit_r1 + 10 * np.log10(1 / (0.01 * bandwidth)),
                    np.array([-10, -13, -25, spurious_emissions]),
                )
            else:
                limit_r1 = np.array([-24])
                emission_limits = np.append(
                    limit_r1 + 10 * np.log10(1 / 0.03),
                    np.array([-10, -13, -25, spurious_emissions]),
                )
        return emission_limits
