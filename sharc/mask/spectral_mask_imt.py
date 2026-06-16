# -*- coding: utf-8 -*-
"""
Created on Tue Dec  5 11:06:56 2017

@author: Calil
"""

from sharc.support.enumerations import StationType
from sharc.mask.spectral_mask import SpectralMask

from warnings import warn
import numpy as np
import matplotlib.pyplot as plt


class SpectralMaskImt(SpectralMask):
    """
    Implements spectral masks for IMT-2020 according to Document 5-1/36-E
        (the masks are in the document's tables 1 to 8), plus the NR
        bands-below-1-GHz Wide Area BS mask from 3GPP TS 38.104
        Table 6.6.4.2.2.1-1 (Category A and B), selected automatically for
        outdoor IMT BS with center frequency below 1 GHz.

    Attributes:
        spurious_emissions (float): level of power emissions at spurious
            domain [dBm/MHz].
        category (str): "A" or "B" emission limit category for the NR <1 GHz
            Wide Area BS mask (only the 10 MHz..delta_f_max region differs).
        delta_f_max (float): end of the OOB domain for the <1 GHz mask [MHz].
        delta_f_lin (np.array): mask delta f breaking limits in MHz. Delta f
            values for which the spectral mask changes value. In this context, delta f is the frequency distance to
            the transmission's edge frequencies
        freq_lim (no.array): frequency values for which the spectral mask
            changes emission value
        sta_type (StationType): type of station to which consider the spectral
            mask. Possible values are StationType.IMT_BS and StationType.IMT_UE
        freq_mhz (float): center frequency of station in MHz
        band_mhs (float): transmitting bandwidth of station in MHz
        scenario (str): INDOOR or OUTDOOR scenario
        p_tx (float): station's transmit power in dBm/MHz
        mask_dbm (np.array): spectral mask emission values in dBm
    """
    # Fixed end of the OOB domain (10 MHz..DELTA_F_MAX region) for the <1 GHz
    # mask, in MHz.
    DELTA_F_MAX_MHZ = 15.0

    def __init__(
        self,
        sta_type: StationType,
        freq_mhz: float,
        band_mhz: float,
        spurious_emissions: float,
        scenario="OUTDOOR",
        category="A",
    ):
        """
        Class constructor.

        Parameters:
            sta_type (StationType): type of station to which consider the spectral
                mask. Possible values are StationType.IMT_BS and StationType.
                IMT_UE
            freq_mhz (float): center frequency of station in MHz
            band_mhs (float): transmitting bandwidth of station in MHz
            spurious_emissions (float): level of spurious emissions [dBm/MHz].
                NOTE: for the NR <1 GHz Wide Area BS mask this is overridden by
                the category-dependent spurious limit (Table 6.6.5.2.1-1/-2).
            scenario (str): INDOOR or OUTDOOR scenario
            category (str): emission limit category for the NR <1 GHz Wide Area
                BS mask, "A" or "B". Sets both the 10 MHz..15 MHz OOB region
                (-13 vs -16 dBm/100kHz) and the 30 MHz-1 GHz spurious limit
                (-13 vs -36 dBm/100kHz). Ignored for other bands.
        """
        # Spurious domain limits [dBm/MHz]
        self.spurious_emissions = spurious_emissions

        # Attributes
        self.sta_type = sta_type
        self.scenario = scenario
        self.band_mhz = band_mhz
        self.freq_mhz = freq_mhz
        self.category = str(category).upper()

        # The NR <1 GHz Wide Area BS mask (3GPP TS 38.104 Table 6.6.4.2.2.1-1)
        # has its own break points; every other case keeps the 5-1/36-E points.
        if self.sta_type is StationType.IMT_BS and self.scenario != "INDOOR" \
                and self.freq_mhz < 1000.0:
            self._build_sub1ghz_mask()
        else:
            self._mask_segments = None
            # Mask delta f breaking limits [MHz] (value from 5-1/36-E)
            self.delta_f_lim = np.array([0, 20, 400])

        self.freq_lim = np.concatenate((
            (freq_mhz - band_mhz / 2) - self.delta_f_lim[::-1],
            (freq_mhz + band_mhz / 2) + self.delta_f_lim,
        ))

    def _build_sub1ghz_mask(self):
        """
        Build delta_f_lim and the per-segment emission limits for the NR
        bands-below-1-GHz Wide Area BS spectrum emission mask
        (3GPP TS 38.104 Table 6.6.4.2.2.1-1, Category A and B).

        Regions (Delta f from the channel edge):
            0 <= df < 5 MHz   : ramp  -7 - (7/5)*df          [dBm/100kHz]
            5 <= df < 10 MHz  : -14                          [dBm/100kHz]
            10 <= df <= 15 MHz: -13 (Cat A) / -16 (Cat B)    [dBm/100kHz]
            df > 15 MHz       : spurious (30 MHz-1 GHz limit, Table 6.6.5.2.1):
                                -13 (Cat A) / -36 (Cat B)    [dBm/100kHz]

        The spec limits are referenced to a 100 kHz measurement bandwidth; we
        add +10 dB to express them as dBm/MHz, matching the dBm/MHz convention
        used by power_calc (which integrates level*bandwidth_in_MHz).
        """
        BW_CORR_DB = 10.0  # dBm/100kHz -> dBm/MHz

        # Spurious limit for the 30 MHz - 1 GHz range (Table 6.6.5.2.1-1/-2),
        # category-dependent. Overrides the user-supplied spurious_emissions.
        spurious_cat = (-36.0 if self.category == "B" else -13.0) + BW_CORR_DB
        self.spurious_emissions = spurious_cat

        # Region 1 (ramp) as a piecewise-constant staircase at 1-MHz steps,
        # using the value at the lower edge of each step (upper bound).
        ramp_df = np.arange(0.0, 5.0, 1.0)                  # 0,1,2,3,4 MHz
        ramp_lim = (-7.0 - (7.0 / 5.0) * ramp_df) + BW_CORR_DB
        # Region 2 (flat)
        flat_lim = -14.0 + BW_CORR_DB
        # Region 3 (category-dependent OOB limit)
        cat_lim = (-16.0 if self.category == "B" else -13.0) + BW_CORR_DB

        delta_f = list(ramp_df) + [5.0, 10.0, self.DELTA_F_MAX_MHZ]
        segments = list(ramp_lim) + [flat_lim, cat_lim, spurious_cat]

        self.delta_f_lim = np.array(delta_f, dtype=float)
        self._mask_segments = np.array(segments, dtype=float)

    def set_mask(self, p_tx=0):
        """
        Sets the spectral mask (mask_dbm attribute) based on station type,
        operating frequency and transmit power.

        Parameters:
            p_tx (float): station transmit power. Default = 0
        """
        self.p_tx = p_tx - 10 * np.log10(self.band_mhz)

        # NR bands below 1 GHz, Wide Area BS (Cat A/B): segments precomputed in
        # __init__ (independent of p_tx).
        if self._mask_segments is not None:
            mask_dbm = self._mask_segments

        # Set new transmit power value
        elif self.sta_type is StationType.IMT_UE:
            # Table 8
            mask_dbm = np.array([-5, -13, self.spurious_emissions])

        elif self.sta_type is StationType.IMT_BS and self.scenario == "INDOOR":
            # Table 1
            mask_dbm = np.array([-5, -13, self.spurious_emissions])

        else:

            if (self.freq_mhz > 24250 and self.freq_mhz < 33400):
                if p_tx >= 34.5:
                    # Table 2
                    mask_dbm = np.array([-5, -13, self.spurious_emissions])
                else:
                    # Table 3
                    mask_dbm = np.array([
                        -5, np.max((p_tx - 47.5, -20)),
                        self.spurious_emissions,
                    ])
            elif (self.freq_mhz > 37000 and self.freq_mhz < 52600):
                if p_tx >= 32.5:
                    # Table 4
                    mask_dbm = np.array([-5, -13, self.spurious_emissions])
                else:
                    # Table 5
                    mask_dbm = np.array([
                        -5, np.max((p_tx - 45.5, -20)),
                        self.spurious_emissions,
                    ])
            elif (self.freq_mhz > 66000 and self.freq_mhz < 86000):
                if p_tx >= 30.5:
                    # Table 6
                    mask_dbm = np.array([-5, -13, self.spurious_emissions])
                else:
                    # Table 7
                    mask_dbm = np.array([
                        -5, np.max((p_tx - 43.5, -20)),
                        self.spurious_emissions,
                    ])
            else:
                mask_dbm = None
                # this will only be reached when spurious emission has been manually set to something invalid and
                warn(
                    "\nSpectralMaskIMT cannot be used with current parameters.\n"
                    "\tYou may:\n\t\t- Have set spurious emission to a value not in [-13,-30]"
                    "\n\t\t- Be trying to use the mask for IMT BS outdoor but freq not in (24.25, 86) GHz range"
                )

        if mask_dbm is not None:
            self.mask_dbm = np.concatenate((
                mask_dbm[::-1], np.array([self.p_tx]),
                mask_dbm,
            ))


if __name__ == '__main__':
    # Demo: NR Wide Area BS mask below 1 GHz, Category A vs B.
    sta_type = StationType.IMT_BS
    p_tx = 43.0
    freq = 700          # MHz (< 1 GHz -> uses Table 6.6.4.2.2.1-1)
    band = 10           # MHz
    spurious_emissions_dbm_mhz = -30  # overridden by the category spurious limit

    freqs = np.linspace(-30, 30, num=4000) + freq

    for category in ("A", "B"):
        msk = SpectralMaskImt(
            sta_type, freq, band, spurious_emissions_dbm_mhz,
            category=category,
        )
        msk.set_mask(p_tx)

        mask_val = np.ones_like(freqs) * msk.mask_dbm[0]
        for k in range(len(msk.freq_lim) - 1, -1, -1):
            mask_val[np.where(freqs < msk.freq_lim[k])] = msk.mask_dbm[k]

        plt.plot(freqs, mask_val, label=f"Category {category}")

    plt.xlim([freqs[0], freqs[-1]])
    plt.xlabel(r"f [MHz]")
    plt.ylabel("Spectral Mask [dBm/MHz]")
    plt.title(f"NR <1 GHz Wide Area BS mask (f={freq} MHz, BW={band} MHz)")
    plt.legend()
    plt.grid()
    plt.show()
