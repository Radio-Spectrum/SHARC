# -*- coding: utf-8 -*-
"""Implements the ITU-R P.1812-6 propagation model.

ITU-R P.1812 is a path-specific propagation prediction method for point-to-area
terrestrial services in the frequency range 30 MHz to 6 GHz. It predicts the
basic transmission loss not exceeded for a given percentage of time (p%) and a
given percentage of locations (pL%).

The recommendation shares most of its sub-models with ITU-R P.452 (diffraction
via the delta-Bullington construction, anomalous/ducting propagation,
tropospheric scatter and gaseous absorption following ITU-R P.676). This
implementation therefore mirrors :class:`sharc.propagation.propagation_clear_air_452.PropagationClearAir`,
re-using the same auxiliary routines, and adds the P.1812-specific pieces:

* the free-space term constant of 92.4 dB (eq. 8) instead of P.452's 92.5 dB;
* the assembly of the basic transmission loss for p% time (Sections 4.1-4.6);
* the location-variability correction for pL% of locations (Section 4.8).

As with the existing P.452 implementation in SHARC, a smooth (flat) terrain
profile is assumed, i.e. no terrain height database is consulted. The model
consequently reduces to its smooth-Earth behaviour, which is the regime SHARC
sharing studies operate in.
"""
import numpy as np
from multipledispatch import dispatch

from sharc.propagation.propagation import Propagation
from sharc.station_manager import StationManager
from sharc.parameters.parameters import Parameters
from sharc.parameters.parameters_p1812 import ParametersP1812
from sharc.propagation.clear_air_452_aux import p676_ga
from sharc.propagation.clear_air_452_aux import inv_cum_norm
from sharc.support.enumerations import StationType
from sharc.propagation.propagation_clutter_loss import PropagationClutterLoss
from sharc.propagation.propagation_building_entry_loss import PropagationBuildingEntryLoss
from sharc.propagation.terrain_srtm import SRTMReader
from sharc.propagation.terrain_statistical import (
    StatisticalTerrainModel,
    StatisticalClutterModel,
)

# Mean Earth radius (m) used for the local x/y -> lat/long conversion
_EARTH_RADIUS_M = 6371000.0


class PropagationP1812(Propagation):
    """ITU-R P.1812-6 basic transmission loss for point-to-area terrestrial paths."""

    def __init__(
            self,
            random_number_gen: np.random.RandomState,
            model_params: ParametersP1812):
        """Initialize PropagationP1812 with a random number generator and model parameters."""
        super().__init__(random_number_gen)

        self.clutter = PropagationClutterLoss(random_number_gen)
        self.building_entry = PropagationBuildingEntryLoss(
            self.random_number_gen,
        )
        self.building_loss = 20
        self.model_params = model_params

        terrain_mode = str(getattr(model_params, "terrain_profile", "flat")).lower()

        # Real-terrain provider (SRTM). ``None`` keeps the smooth-Earth behaviour.
        self.terrain = None
        if terrain_mode == "srtm":
            self.terrain = SRTMReader(
                model_params.srtm_directory,
                missing_tile_as_zero=model_params.srtm_missing_tile_as_zero,
                auto_download=model_params.srtm_auto_download,
                download_url_template=model_params.srtm_download_url_template,
                download_timeout=model_params.srtm_download_timeout,
            )

        # Statistical (synthetic) terrain model for Monte-Carlo simulations.
        self.stat_terrain = None
        if terrain_mode == "statistical":
            self.stat_terrain = StatisticalTerrainModel(
                height_sigma_m=model_params.stat_height_sigma_m,
                height_nu=model_params.stat_height_nu,
                dist_mu=model_params.stat_dist_mu,
                dist_sigma=model_params.stat_dist_sigma,
                baseline_m=model_params.stat_baseline_m,
                smoothing_km=model_params.stat_smoothing_km,
            )

        # Statistical clutter model (representative clutter heights at terminals).
        self.stat_clutter = None
        if getattr(model_params, "clutter_statistical", False):
            self.stat_clutter = StatisticalClutterModel(
                clutter_mu=model_params.stat_clutter_mu,
                clutter_sigma=model_params.stat_clutter_sigma,
            )

        # Per-link terrain profiles stashed by the high-level get_loss wrapper
        # so the low-level (multipledispatch-bound) method can consume them.
        self._terrain_profiles = None

    def _station_lat_lon(self, station: StationManager):
        """Return per-station (latitude, longitude) arrays in degrees for SRTM sampling.

        Depending on ``terrain_coordinate_mode`` the stations are either taken to
        carry their own geographic coordinates, or to be placed in a local
        x(east)/y(north) plane in metres anchored at the configured central
        latitude/longitude.
        """
        if str(self.model_params.terrain_coordinate_mode).lower() == "geographic":
            return (
                np.atleast_1d(np.asarray(station.latitude, dtype=float)),
                np.atleast_1d(np.asarray(station.longitude, dtype=float)),
            )

        lat0 = float(self.model_params.topology_central_latitude)
        lon0 = float(self.model_params.topology_central_longitude)
        x = np.atleast_1d(np.asarray(station.x, dtype=float))  # east (m)
        y = np.atleast_1d(np.asarray(station.y, dtype=float))  # north (m)

        lat = lat0 + np.degrees(y / _EARTH_RADIUS_M)
        lon = lon0 + np.degrees(
            x / (_EARTH_RADIUS_M * np.cos(np.radians(lat0))),
        )
        return lat, lon

    # ------------------------------------------------------------------
    # Inverse standard-normal CDF valid over the whole (0, 1) range.
    # ``inv_cum_norm`` (Attachment to P.452/P.1812) is only defined for
    # arguments <= 0.5, so we use the symmetry of the normal distribution
    # to cover percentages of locations above 50%.
    # ------------------------------------------------------------------
    @staticmethod
    def norm_inv(q):
        """Inverse of the standard normal cumulative distribution, valid for 0 < q < 1."""
        if q <= 0.5:
            return inv_cum_norm(q)
        return -inv_cum_norm(1.0 - q)

    @staticmethod
    def longest_cont_dist(d, zone, zone_r):
        """Return the longest continuous distance (km) within a given radio-climatic zone."""
        dm = 0

        if zone_r == 12:
            aux = (zone == 1) + (zone == 2)
        else:
            aux = zone == zone_r

        aux = np.append(0, np.append(aux, 0))
        aux = np.diff(aux)
        start = np.where(aux == 1)[0]
        stop = np.where(aux == -1)[0] - 1

        start = np.atleast_1d(start)
        stop = np.atleast_1d(stop)
        n = start.size

        for i in range(n):
            delta = 0
            if (d[stop[i]] < d[-1]):
                delta = delta + (d[stop[i] + 1] - d[stop[i]]) / 2.0

            if (d[start[i]] > 0):
                delta = delta + (d[stop[i]] - d[stop[i] - 1]) / 2.0

            dm = max(d[stop[i]] - d[start[i]] + delta, dm)

        return dm

    @staticmethod
    def beta0(phi, dtm, dlm):
        """Calculate the time percentage beta0 for anomalous propagation (P.1812 Att. 1).

        Parameters
        ----------
        phi : float
            Path-centre latitude (degrees).
        dtm : float
            Longest continuous land (inland + coastal) section of the path (km).
        dlm : float
            Longest continuous inland section of the path (km).

        Returns
        -------
        float
            Time percentage beta0 for which refractivity lapse-rates exceeding
            100 N-units/km can be expected.
        """
        tau = 1 - np.exp(-(4.12 * 1e-4 * dlm ** 2.41))  # (3a)

        mu1 = (
            10 ** (-dtm / (16 - 6.6 * tau)) + 10 **
            (-5 * (0.496 + 0.354 * tau))
        ) ** 0.2

        indices = np.nonzero(mu1 > 1)
        mu1[indices] = 1

        if abs(phi) <= 70:
            mu4 = 10 ** ((-0.935 + 0.0176 * abs(phi)) * np.log10(mu1))
            b0 = 10 ** (-0.015 * abs(phi) + 1.67) * mu1 * mu4
        else:
            mu4 = 10 ** (0.3 * np.log10(mu1))
            b0 = 4.17 * mu1 * mu4

        return b0

    @staticmethod
    def earth_rad_eff(DN):
        """Calculate the median (ae) and beta0 (ab) effective Earth radii from lapse-rate DN."""
        k50 = 157 / (157 - DN)
        ae = 6371 * k50

        kbeta = 3
        ab = 6371 * kbeta

        return ae, ab

    @staticmethod
    def smooth_earth_heights(d, h, htg, hrg, ae, f):
        """Compute smooth-Earth heights and horizon geometry for the path profile.

        Mirrors ITU-R P.1812 Attachment 1 (identical construction to P.452
        Attachment 2). Returns the smoothed terminal heights, effective heights,
        terrain roughness, horizon distances and elevation angles, the angular
        distance and the path type (1 = LoS, 2 = trans-horizon).
        """
        n = d.size
        dtot = d[-1]

        # Tx and Rx antenna heights above mean sea level amsl (m)
        hts = h[0] + htg
        hrs = h[-1] + hrg

        # Section 5.6.1 - Smoothed terrain heights
        v1 = 0
        for ii in range(1, n):
            v1 = v1 + (d[ii] - d[ii - 1]) * (h[ii] + h[ii - 1])

        v2 = 0
        for ii in range(2, n):
            v2 = v2 + (d[ii] - d[ii - 1]) * (
                h[ii] * (2 * d[ii] + d[ii - 1]) +
                h[ii - 1] * (d[ii] + 2 * d[ii - 1])
            )

        hst = (2 * v1 * dtot - v2) / dtot ** 2
        hsr = (v2 - v1 * dtot) / dtot ** 2

        # Section 5.6.2 - Heights for the diffraction model
        HH = h - (hts * (dtot - d) + hrs * d) / dtot
        hobs = max(HH[1:n - 1])

        alpha_obt = max(HH[1:n - 1] / d[1:n - 1])
        alpha_obr = max(HH[1:n - 1] / (dtot - d[1:n - 1]))

        gt = alpha_obt / (alpha_obt + alpha_obr)
        gr = alpha_obr / (alpha_obt + alpha_obr)

        if hobs <= 0:
            hstp = hst
            hsrp = hsr
        else:
            hstp = hst - hobs * gt
            hsrp = hsr - hobs * gr

        if hstp >= h[0]:
            hstd = h[0]
        else:
            hstd = hstp

        if hsrp > h[-1]:
            hsrd = h[-1]
        else:
            hsrd = hsrp

        # Interfering antenna horizon elevation angle and distance
        ii = np.arange(1, n - 1)

        theta = 1000 * np.arctan((h[ii] - hts) /
                                 (1000 * d[ii]) - d[ii] / (2 * ae))
        theta_t = max(theta)

        theta_td = 1000 * np.arctan((hrs - hts) /
                                    (1000 * dtot) - dtot / (2 * ae))
        theta_rd = 1000 * np.arctan((hts - hrs) /
                                    (1000 * dtot) - dtot / (2 * ae))

        if theta_t > theta_td:
            pathtype = 2  # trans-horizon
        else:
            pathtype = 1  # line-of-sight

        kindex = np.nonzero(theta == theta_t)
        lt = kindex[0] + 1
        dlt = d[lt]

        # Interfered-with antenna horizon elevation angle and distance
        theta = 1000 * \
            np.arctan((h[ii] - hrs) / (1000 * (dtot - d[ii])) -
                      (dtot - d[ii]) / (2 * ae))
        theta_r = max(theta)

        kindex = np.nonzero(np.ravel(theta) == theta_r)
        lr = kindex[-1] + 1
        dlr = dtot - d[lr]

        if pathtype == 1:
            theta_t = theta_td
            theta_r = theta_rd

            ii = np.arange(1, n - 1)

            lamb = 0.3 / f
            Ce = 1 / ae

            nu = (h[ii] + 500 * Ce * d[ii] * (dtot - d[ii]) - (hts * (dtot - d[ii]) +
                  hrs * d[ii]) / dtot) * np.sqrt(0.002 * dtot / (lamb * d[ii] * (dtot - d[ii])))
            numax = max(nu)

            kindex = np.nonzero(nu == numax)
            lt = kindex[-1] + 1
            dlt = d[lt]
            dlr = dtot - dlt
            kindex = np.nonzero(dlr <= dtot - d[ii])
            lr = kindex[0][-1] + 1

        # Angular distance
        theta_tot = 1e3 * dtot / ae + theta_t + theta_r

        # Smooth-Earth heights for the roughness factor (ducting model)
        hst = min(hst, h[0])
        hsr = min(hsr, h[-1])

        m = (hsr - hst) / dtot

        hte = htg + h[0] - hst
        hre = hrg + h[-1] - hsr

        ii = np.arange(lt, lr + 1)
        hm = max(h[ii] - (hst + m * d[ii]))

        return hst, hsr, hstd, hsrd, hte, hre, hm, dlt, dlr, theta_t, theta_r, theta_tot, pathtype

    @staticmethod
    def path_fraction(d, zone, zone_r):
        """Calculate the fraction of the path within a given radio-climatic zone."""
        dm = 0

        aux = np.nonzero(zone == zone_r)
        start = aux[0]
        stop = aux[-1]
        start = np.atleast_1d(start)
        stop = np.atleast_1d(stop)

        n = start.size

        for i in range(n):
            delta = 0
            if (d(stop[1]) < d[-1]):
                delta = delta + (d(stop[i] + 1) - d(stop[i])) / 2.0

            if (d(start[i]) > 0):
                delta = delta + (d(stop[i]) - d(stop[i] - 1)) / 2.0

            dm = dm + d(stop[i]) - d(start[i]) + delta

        omega = dm / (d[-1] - d[0])

        return omega

    @staticmethod
    def pl_los(d, f, p, b0, w, T, press, dlt, dlr):
        """Line-of-sight basic transmission loss including gases (P.1812 Section 4.1).

        Parameters
        ----------
        d : float
            Great-circle path length (km).
        f : float
            Frequency (GHz).
        p : float
            Percentage of time (%).
        b0 : float
            Time percentage beta0 (%).
        w : float
            Fraction of the path over water.
        T : float
            Air temperature (K).
        press : float
            Atmospheric pressure (hPa).
        dlt, dlr : float
            Tx/Rx horizon distances (km).

        Returns
        -------
        tuple
            (Lbfsg, Lb0p, Lb0b): free-space-plus-gas loss and the LoS losses not
            exceeded for p% and beta0% of time.
        """
        # Water-vapour density (g/m^3)
        rho = 7.5 + 2.5 * w

        # Specific attenuation due to dry air and water vapour (P.676)
        [g_0, g_w] = p676_ga(f, press, rho, T, True)

        Ag = (g_0 + g_w) * d

        # Free-space basic transmission loss including gaseous attenuation.
        # P.1812 eq. (8) uses 92.4 dB (vs. 92.5 dB in P.452).
        Lbfsg = 92.4 + 20.0 * np.log10(f) + 20.0 * np.log10(d) + Ag

        # Corrections for multipath and focusing effects at p and b0 (eq. 9, 10)
        Esp = 2.6 * (1 - np.exp(-0.1 * (dlt + dlr))) * np.log10(p / 50)
        Esb = 2.6 * (1 - np.exp(-0.1 * (dlt + dlr))) * np.log10(b0 / 50)

        # LoS loss not exceeded for p% time (eq. 11) and beta0% time (eq. 12)
        Lb0p = Lbfsg + Esp
        Lb0b = Lbfsg + Esb

        return Lbfsg, Lb0p, Lb0b

    @staticmethod
    def tl_tropo(dtot, theta, f, p, T, press, N0, Gt, Gr):
        """Tropospheric-scatter basic transmission loss (P.1812 Section 4.4)."""
        # Frequency-dependent loss
        Lf = 25 * np.log10(f) - 2.5 * (np.log10(f / 2)) ** 2

        # Aperture-to-medium coupling loss (dB)
        Lc = 0.051 * np.exp(0.055 * (Gt + Gr))

        # Gaseous absorption using rho = 3 g/m^3 over the whole path
        rho = 3
        [g_0, g_w] = p676_ga(f, press, rho, T, True)
        Ag = (g_0 + g_w) * dtot

        Lbs = 190 + Lf + 20 * np.log10(dtot) + 0.573 * theta - \
            0.15 * N0 + Lc + Ag - 10.1 * (-np.log10(p / 50)) ** (0.7)
        return Lbs

    @staticmethod
    def tl_anomalous(
        dtot, dlt, dlr, dct, dcr, dlm, hts, hrs, hte, hre, hm,
        theta_t, theta_r, f, p, T, press, omega, ae, b0,
    ):
        """Anomalous (ducting / layer-reflection) basic transmission loss (P.1812 Section 4.5)."""
        Alf = 0
        if f < 0.5:
            Alf = 45.375 - 137.0 * f + 92.5 * f * f

        # Site-shielding diffraction losses for the Tx and Rx
        theta_t1 = theta_t - 0.1 * dlt
        theta_r1 = theta_r - 0.1 * dlr

        Ast = 0
        Asr = 0
        if theta_t1 > 0:
            Ast = 20 * np.log10(
                1 + 0.361 * theta_t1 * np.sqrt(f * dlt),
            ) + 0.264 * theta_t1 * f ** (1 / 3)

        if theta_r1 > 0:
            Asr = 20 * np.log10(
                1 + 0.361 * theta_r1 * np.sqrt(f * dlr),
            ) + 0.264 * theta_r1 * f ** (1 / 3)

        # Over-sea surface duct coupling corrections
        Act = 0
        Acr = 0
        if dct <= 5:
            if dct <= dlt:
                if omega >= 0.75:
                    Act = -3 * np.exp(-0.25 * dct * dct) * \
                        (1 + np.tanh(0.07 * (50 - hts)))

        if dcr <= 5:
            if dcr <= dlr:
                if omega >= 0.75:
                    Acr = -3 * np.exp(-0.25 * dcr * dcr) * \
                        (1 + np.tanh(0.07 * (50 - hrs)))

        # Specific attenuation
        gamma_d = 5e-5 * ae * f ** (1 / 3)

        # Angular distance (corrected where appropriate)
        theta_t1 = theta_t
        theta_r1 = theta_r
        if theta_t > 0.1 * dlt:
            theta_t1 = 0.1 * dlt
        if theta_r > 0.1 * dlr:
            theta_r1 = 0.1 * dlr

        theta1 = 1e3 * dtot / ae + theta_t1 + theta_r1

        dI = min(dtot - dlt - dlr, 40)

        mu3 = 1
        if hm > 10:
            mu3 = np.exp(-4.6e-5 * (hm - 10) * (43 + 6 * dI))

        tau = 1 - np.exp(-(4.12e-4 * dlm ** 2.41))
        epsilon = 3.5
        alpha = -0.6 - epsilon * 1e-9 * dtot ** (3.1) * tau
        if alpha < -3.4:
            alpha = -3.4

        mu2 = (500 / ae * dtot ** 2 / (np.sqrt(hte) + np.sqrt(hre)) ** 2) ** alpha
        if mu2 > 1:
            mu2 = 1

        beta = b0 * mu2 * mu3

        Gamma = 1.076 / (2.0058 - np.log10(beta)) ** 1.012 * np.exp(-(9.51 - 4.8 *
                         np.log10(beta) + 0.198 * (np.log10(beta)) ** 2) * 1e-6 * dtot ** (1.13),)

        Ap = -12 + (1.2 + 3.7e-3 * dtot) * \
            np.log10(p / beta) + 12 * (p / beta) ** Gamma

        Adp = gamma_d * theta1 + Ap

        # Gaseous absorption
        rho = 7.5 + 2.5 * omega
        [g_0, g_w] = p676_ga(f, press, rho, T, True)
        Ag = (g_0 + g_w) * dtot

        # Fixed coupling losses between the antennas and the anomalous structure
        Af = 102.45 + 20 * \
            np.log10(f) + 20 * np.log10(dlt + dlr) + \
            Alf + Ast + Asr + Act + Acr

        Lba = Af + Adp + Ag

        return Lba

    @staticmethod
    def dl_bull(d, h, hts, hrs, ap, f):
        """Bullington part of the diffraction loss for a path profile (P.1812 Att. 4)."""
        Ce = 1 / ap
        lamb = 0.3 / f
        dtot = d[-1] - d[0]

        di = d[1: -1]
        hi = h[1:- 1]

        Stim = np.max((hi + 500 * Ce * di * (dtot - di) - hts) / di)
        Str = (hrs - hts) / dtot

        if Stim < Str:  # Case 1, path is LoS
            numax = np.max(
                (
                    hi + 500 * Ce * di * (dtot - di) -
                    (hts * (dtot - di) + hrs * di) / dtot
                ) *
                np.sqrt(0.002 * dtot / (lamb * di * (dtot - di))),
            )

            Luc = 0
            if numax > -0.78:
                Luc = 6.9 + 20 * \
                    np.log10(np.sqrt((numax - 0.1) ** 2 + 1) + numax - 0.1)
        else:  # Path is trans-horizon
            Srim = np.max(
                (hi + 500 * Ce * di * (dtot - di) - hrs) / (dtot - di),
            )
            dbp = (hrs - hts + Srim * dtot) / (Stim + Srim)
            nub = (hts + Stim * dbp - (hts * (dtot - dbp) + hrs * dbp) /
                   dtot) * np.sqrt(0.002 * dtot / (lamb * dbp * (dtot - dbp)))

            Luc = 0
            if nub > -0.78:
                Luc = 6.9 + 20 * \
                    np.log10(np.sqrt((nub - 0.1) ** 2 + 1) + nub - 0.1)

        Lbull = Luc + (1 - np.exp(-Luc / 6.0)) * (10 + 0.02 * dtot)
        return Lbull

    @staticmethod
    def dl_se_ft_inner(epsr, sigma, d, hte, hre, adft, f):
        """First-term spherical-Earth diffraction loss for one ground type/polarization."""
        K = np.empty(2)
        K[0] = 0.036 * (adft * f) ** (-1 / 3) * (
            (epsr - 1) ** 2 + (18 * sigma / f) ** 2
        ) ** (-1 / 4)
        K[1] = K[0] * (epsr ** 2 + (18 * sigma / f) ** 2) ** (1 / 2)

        beta_dft = (1 + 1.6 * K ** 2 + 0.67 * K**4) / \
            (1 + 4.5 * K ** 2 + 1.53 * K ** 4)

        X = 21.88 * beta_dft * (f / adft ** 2) ** (1 / 3) * d

        Yt = 0.9575 * beta_dft * (f ** 2 / adft) ** (1 / 3) * hte
        Yr = 0.9575 * beta_dft * (f ** 2 / adft) ** (1 / 3) * hre

        Fx = np.empty(2)
        for ii in range(2):
            if X[ii] >= 1.6:
                Fx[ii] = 11 + 10 * np.log10(X[ii]) - 17.6 * X[ii]
            else:
                Fx[ii] = -20 * np.log10(X[ii]) - 5.6488 * (X[ii]) ** 1.425

        Bt = beta_dft * Yt
        Br = beta_dft * Yr

        GYt = np.empty(2)
        GYr = np.empty(2)
        for ii in range(2):
            if Bt[ii] > 2:
                GYt[ii] = 17.6 * (Bt[ii] - 1.1) ** 0.5 - 5 * \
                    np.log10(Bt[ii] - 1.1) - 8
            else:
                GYt[ii] = 20 * np.log10(Bt[ii] + 0.1 * Bt[ii] ** 3)

            if Br[ii] > 2:
                GYr[ii] = 17.6 * (Br[ii] - 1.1) ** 0.5 - 5 * \
                    np.log10(Br[ii] - 1.1) - 8
            else:
                GYr[ii] = 20 * np.log10(Br[ii] + 0.1 * Br[ii] ** 3)

            if GYr[ii] < 2 + 20 * np.log10(K[ii]):
                GYr[ii] = 2 + 20 * np.log10(K[ii])
            if GYt[ii] < 2 + 20 * np.log10(K[ii]):
                GYt[ii] = 2 + 20 * np.log10(K[ii])

        Ldft = -Fx - GYt - GYr
        return Ldft

    @staticmethod
    def dl_se_ft(d, hte, hre, adft, f, omega):
        """First-term spherical-Earth diffraction loss combining land and sea."""
        # Over land
        epsr = 22
        sigma = 0.003
        Ldft_land = PropagationP1812.dl_se_ft_inner(
            epsr, sigma, d, hte, hre, adft, f,
        )

        # Over sea
        epsr = 80
        sigma = 5
        Ldft_sea = PropagationP1812.dl_se_ft_inner(
            epsr, sigma, d, hte, hre, adft, f,
        )

        Ldft = omega * Ldft_sea + (1 - omega) * Ldft_land
        return Ldft

    @staticmethod
    def dl_se(d, hte, hre, ap, f, omega):
        """Spherical-Earth diffraction loss (P.1812 Att. 4)."""
        lamb = 0.3 / f
        dlos = np.sqrt(2 * ap) * (np.sqrt(0.001 * hte) + np.sqrt(0.001 * hre))

        if d >= dlos:
            Ldsph = PropagationP1812.dl_se_ft(d, hte, hre, ap, f, omega)
        else:
            c = (hte - hre) / (hte + hre)
            m = 250 * d * d / (ap * (hte + hre))

            b = 2 * np.sqrt((m + 1) / (3 * m)) * np.cos(
                np.pi / 3 +
                1 / 3 * np.arccos(3 * c / 2 * np.sqrt(3 * m / (m + 1) ** 3)),
            )

            dse1 = d / 2 * (1 + b)
            dse2 = d - dse1

            hse = (hte - 500 * dse1 * dse1 / ap) * dse2 + \
                (hre - 500 * dse2 * dse2 / ap) * dse1
            hse = hse / d

            hreq = 17.456 * np.sqrt(dse1 * dse2 * lamb / d)

            if hse > hreq:
                Ldsph = np.array([0, 0])
            else:
                aem = 500 * (d / (np.sqrt(hte) + np.sqrt(hre)))**2
                Ldft = PropagationP1812.dl_se_ft(d, hte, hre, aem, f, omega)

                if (Ldft < 0).any():
                    Ldsph = np.array([0, 0])
                else:
                    Ldsph = (1 - hse / hreq) * Ldft

        return Ldsph

    @staticmethod
    def dl_delta_bull(d, h, hts, hrs, hstd, hsrd, ap, f, omega):
        """Delta-Bullington diffraction loss combining actual and smooth paths."""
        Lbulla = PropagationP1812.dl_bull(d, h, hts, hrs, ap, f)

        hts1 = hts - hstd
        hrs1 = hrs - hsrd
        h1 = np.zeros(h.size)

        Lbulls = PropagationP1812.dl_bull(d, h1, hts1, hrs1, ap, f)

        hte = hts1
        hre = hrs1
        dtot = d[-1] - d[0]

        Ldsph = PropagationP1812.dl_se(dtot, hte, hre, ap, f, omega)

        Ld = np.empty(2)
        Ld[0] = Lbulla + max(Ldsph[0] - Lbulls, 0)
        Ld[1] = Lbulla + max(Ldsph[1] - Lbulls, 0)

        return Ld

    @staticmethod
    def dl_p(d, h, hts, hrs, hstd, hsrd, f, omega, p, b0, DN):
        """Diffraction loss not exceeded for p% time and for 50% time (P.1812 Section 4.3)."""
        [ae, ab] = PropagationP1812.earth_rad_eff(DN)

        ap = ae
        Ld50 = PropagationP1812.dl_delta_bull(
            d, h, hts, hrs, hstd, hsrd, ap, f, omega,
        )

        if p == 50:
            Ldp = Ld50
        elif p < 50:
            ap = ab
            Ldb = PropagationP1812.dl_delta_bull(
                d, h, hts, hrs, hstd, hsrd, ap, f, omega,
            )

            if p > b0:
                Fi = inv_cum_norm(p / 100) / inv_cum_norm(b0 / 100)
            else:
                Fi = 1

            Ldp = Ld50 + Fi * (Ldb - Ld50)

        return Ldp, Ld50

    @staticmethod
    def clutter_correction(f, d, h, htg, hrg, ha_t, ha_r, dk_t, dk_r):
        """Path-specific terminal clutter correction (ITU-R P.1812-6 Section 4.7).

        Applies the representative-clutter height-gain model: when a terminal
        sits below the representative clutter height ``ha`` of its surroundings,
        an additional loss is introduced and the diffraction path is shortened
        to start/end at the clutter edge (a nominal distance ``dk`` from the
        terminal), with the effective terminal ground height raised to the
        clutter top. This is the same correction used by ITU-R P.452-16 (eq. 57).

        Parameters
        ----------
        f : float
            Frequency (GHz).
        d : np.ndarray
            Distance profile (km).
        h : np.ndarray
            Terrain height profile (m amsl).
        htg, hrg : float
            Tx/Rx antenna heights above ground (m).
        ha_t, ha_r : float
            Representative clutter heights at Tx/Rx (m). 0 disables that end.
        dk_t, dk_r : float
            Nominal clutter distances at Tx/Rx (km).

        Returns
        -------
        tuple
            (dc, hc, htgc, hrgc, Aht, Ahr): clipped distance/height profile,
            adjusted terminal ground heights and the additional clutter losses
            (dB) at the Tx and Rx ends.
        """
        n = d.size
        index1 = 0
        index2 = n - 1
        htgc = htg
        hrgc = hrg
        Aht = 0.0
        Ahr = 0.0

        # Frequency-dependent factor (eq. 57a)
        Ffc = 0.25 + 0.375 * (1 + np.tanh(7.5 * (f - 0.5)))

        if ha_t and ha_t > htg:
            Aht = 10.25 * Ffc * np.exp(-dk_t) * \
                (1 - np.tanh(6 * (htg / ha_t - 0.625))) - 0.33  # (eq. 57)
            kk = np.where(d >= dk_t)[0]
            index1 = kk[0] if kk.size else n - 1
            htgc = ha_t

        if ha_r and ha_r > hrg:
            Ahr = 10.25 * Ffc * np.exp(-dk_r) * \
                (1 - np.tanh(6 * (hrg / ha_r - 0.625))) - 0.33  # (eq. 57)
            kk = np.where(d <= d[-1] - dk_r)[0]
            index2 = kk[-1] if kk.size else 0
            hrgc = ha_r

        # At least two points must remain between the clutter at both ends
        if index2 - index1 < 3:
            error_message = (
                "tl_p1812: clutter_correction: the sum of clutter nominal "
                "distances is larger than the path length."
            )
            raise ValueError(error_message)

        dc = d[index1:index2 + 1] - d[index1]
        hc = h[index1:index2 + 1]
        return dc, hc, htgc, hrgc, Aht, Ahr

    @dispatch(Parameters, float, StationManager,
              StationManager, np.ndarray, np.ndarray)
    def get_loss(
        self,
        params: Parameters,
        frequency: float,
        station_a: StationManager,
        station_b: StationManager,
        station_a_gains=None,
        station_b_gains=None,
    ) -> np.array:
        """Wrapper fitting the Propagation ABC interface; computes loss between station_a and station_b.

        Parameters
        ----------
        params : Parameters
            Simulation parameters needed for the propagation class.
        frequency : float
            Centre frequency (MHz).
        station_a : StationManager
            StationManager container representing the system station.
        station_b : StationManager
            StationManager container representing the IMT station.
        station_a_gains : np.ndarray, optional
            System antenna gains.
        station_b_gains : np.ndarray, optional
            IMT antenna gains.

        Returns
        -------
        np.array
            Array (station_a.num_stations x station_b.num_stations) of path losses.
        """
        distance = station_a.get_3d_distance_to(
            station_b,
        ) * (1e-3)  # P.1812 expects km
        frequency_array = frequency * \
            np.ones(distance.shape) * (1e-3)  # P.1812 expects GHz
        indoor_stations = np.tile(
            station_b.indoor, (station_a.num_stations, 1),
        )
        elevation = station_b.get_elevation(station_a)
        if params.imt.interfered_with:
            tx_gain = station_a_gains
            rx_gain = station_b_gains
        else:
            tx_gain = station_b_gains
            rx_gain = station_a_gains

        # Build real-terrain profiles for each link when SRTM is enabled.
        # Link ii connects station_a[0] to station_b[ii], mirroring the
        # smooth-Earth path that indexes distance[0][ii].
        if self.terrain is not None:
            lat_a, lon_a = self._station_lat_lon(station_a)
            lat_b, lon_b = self._station_lat_lon(station_b)
            n_points = self.model_params.profile_resolution
            self._terrain_profiles = [
                self.terrain.path_profile(
                    lat_a[0], lon_a[0], lat_b[ii], lon_b[ii], n_points,
                )
                for ii in range(station_b.num_stations)
            ]

        try:
            return self.get_loss(
                distance,
                frequency_array,
                indoor_stations,
                elevation,
                tx_gain,
                rx_gain,
            )
        finally:
            self._terrain_profiles = None

    # pylint: disable=function-redefined
    # pylint: disable=arguments-differ
    @dispatch(np.ndarray, np.ndarray, np.ndarray,
              np.ndarray, np.ndarray, np.ndarray)
    def get_loss(
        self, distance: np.ndarray, frequency: np.ndarray,
        indoor_stations: np.ndarray, elevation: np.ndarray,
        tx_gain: np.ndarray, rx_gain: np.ndarray,
    ) -> np.array:
        """Calculate the basic transmission loss according to ITU-R P.1812-6.

        Parameters
        ----------
        distance : np.ndarray
            Distance array between stations in km.
        frequency : np.ndarray
            Frequency array for the links in GHz.
        indoor_stations : np.ndarray
            Whether the rx stations are indoors.
        elevation : np.ndarray
            Elevation angle between stations.
        tx_gain, rx_gain : np.ndarray
            Transmitter/receiver antenna gains.

        Returns
        -------
        np.array
            Array of path losses.
        """
        frequency = np.unique(frequency)
        if len(frequency) > 1:
            error_message = "different frequencies not supported in P.1812"
            raise ValueError(error_message)

        Ph = np.asarray(self.model_params.atmospheric_pressure)
        T = np.asarray(self.model_params.air_temperature)
        Dct = np.asarray(self.model_params.Dct)
        Dcr = np.asarray(self.model_params.Dcr)
        Hte = np.asarray(self.model_params.Hte)
        Hre = np.asarray(self.model_params.Hre)
        N0 = np.asarray(self.model_params.N0)
        deltaN = np.asarray(self.model_params.delta_N)

        if self.model_params.percentage_p == 'RANDOM':
            p = 50 * self.random_number_gen.rand(distance.size)
        else:
            p = float(self.model_params.percentage_p) * np.ones(distance.size)

        # Percentage of locations and location variability standard deviation
        # (P.1812 Section 4.8). pL = 50 reproduces the median-location loss.
        pL = float(self.model_params.location_percentage)
        sigma_loc = float(self.model_params.location_variability_sigma)
        # Location-variability correction (eq. 64): higher pL -> lower loss.
        Lloc = -self.norm_inv(pL / 100.0) * sigma_loc

        tx_lat = self.model_params.tx_lat
        rx_lat = self.model_params.rx_lat

        tx_gain = np.ravel(tx_gain)
        rx_gain = np.ravel(rx_gain)

        # Clutter handling mode (Section 4.7 / P.2108):
        #   "p2108"  - statistical clutter at each end (ITU-R P.2108)
        #   "terrain" - path-specific representative-clutter height-gain model
        #   "none"   - no clutter loss
        clutter_mode = str(self.model_params.clutter_mode).lower()
        if clutter_mode not in ("p2108", "terrain", "none"):
            raise ValueError(
                f"tl_p1812: invalid clutter_mode '{self.model_params.clutter_mode}'. "
                "Allowed values are 'p2108', 'terrain', 'none'.",
            )
        # Representative clutter heights/distances for the "terrain" mode
        ha_t = float(self.model_params.repr_clutter_height_tx)
        ha_r = float(self.model_params.repr_clutter_height_rx)
        dk_t = float(self.model_params.clutter_nominal_dist_tx)
        dk_r = float(self.model_params.clutter_nominal_dist_rx)

        num_dists = distance.size

        # Path profile, in priority order:
        #   1. real terrain (SRTM) stashed by the wrapper,
        #   2. synthetic statistical terrain (one realization per link),
        #   3. smooth (flat) profile, as done for P.452 in SHARC.
        profiles = self._terrain_profiles
        if profiles is not None:
            if len(profiles) != num_dists:
                error_message = (
                    "tl_p1812: number of terrain profiles "
                    f"({len(profiles)}) does not match number of links ({num_dists}). "
                    "P.1812 assumes a single station_a (system) against N station_b."
                )
                raise ValueError(error_message)
            profile_length = profiles[0][0].size
            d = np.empty([num_dists, profile_length])
            h = np.empty([num_dists, profile_length])
            for ii in range(num_dists):
                d[ii, :] = profiles[ii][0]
                h[ii, :] = profiles[ii][1]
        elif self.stat_terrain is not None:
            profile_length = int(self.model_params.profile_resolution)
            d = np.empty([num_dists, profile_length])
            h = np.empty([num_dists, profile_length])
            for ii in range(num_dists):
                d_ii, h_ii = self.stat_terrain.synthesize(
                    distance[0][ii], profile_length, self.random_number_gen,
                )
                d[ii, :] = d_ii
                h[ii, :] = h_ii
        else:
            profile_length = 100
            d = np.empty([num_dists, profile_length])
            for ii in range(num_dists):
                d[ii, :] = np.linspace(0, distance[0][ii], profile_length)
            h = np.zeros(d.shape)

        # Path-centre latitude
        phi_path = (tx_lat + rx_lat) / 2

        # dtm: longest continuous land section; dlm: longest continuous inland section
        dtm = np.empty(num_dists)
        dlm = np.empty(num_dists)

        zone = np.ones(profile_length) * 2
        for index in range(num_dists):
            zone_r = 12
            dtm[index] = self.longest_cont_dist(d[index, :], zone, zone_r)
            zone_r = 2
            dlm[index] = self.longest_cont_dist(d[index, :], zone, zone_r)

        b0 = self.beta0(phi_path, dtm, dlm)
        [ae, ab] = self.earth_rad_eff(deltaN)

        # Path fraction over water
        omega = self.path_fraction(d.transpose(), zone, 3)

        Lb = np.empty([1, num_dists])

        Ce = 1 / ae

        # Interpolation factors (P.1812 Section 4.6)
        THETA = 0.3
        KSI = 0.8

        htg = Hte
        hrg = Hre

        for ii in range(num_dists):
            # Working profile for this link; clipped/raised by the terrain
            # clutter model when enabled.
            d_i = d[ii, :]
            h_i = h[ii, :]
            htg_i = htg
            hrg_i = hrg
            Aht = 0.0
            Ahr = 0.0

            if clutter_mode == "terrain":
                # Representative clutter heights: drawn per link from the
                # statistical clutter model, or fixed from parameters.
                if self.stat_clutter is not None:
                    ha_t_i = float(self.stat_clutter.sample(self.random_number_gen))
                    ha_r_i = float(self.stat_clutter.sample(self.random_number_gen))
                else:
                    ha_t_i = ha_t
                    ha_r_i = ha_r
                d_i, h_i, htg_i, hrg_i, Aht, Ahr = self.clutter_correction(
                    frequency, d[ii, :], h[ii, :], htg, hrg,
                    ha_t_i, ha_r_i, dk_t, dk_r,
                )

            [
                hst, hsr, hstd, hsrd, hte, hre, hm, dlt,
                dlr, theta_t, theta_r, theta, pathtype,
            ] = self.smooth_earth_heights(d_i, h_i, htg_i, hrg_i, ae, frequency)

            dtot = d_i[-1] - d_i[0]

            hts = h_i[0] + htg_i
            hrs = h_i[-1] + hrg_i

            if len(d_i) < 4:
                error_message = "tl_p1812: path profile requires at least 4 points."
                raise ValueError(error_message)

            di = d_i[1: -1]
            hi = h_i[1: -1]

            Stim = max((hi + 500 * Ce * di * (dtot - di) - hts) / di)
            Str = (hrs - hts) / dtot

            # Interpolation factor for the path angular distance (eq. 58)
            Fj = 1.0 - 0.5 * (1.0 + np.tanh(3.0 * KSI * (Stim - Str) / THETA))

            # Interpolation factor for the great-circle path distance
            dsw = 20
            kappa = 0.5
            Fk = 1.0 - 0.5 * (1.0 + np.tanh(3.0 * kappa * (dtot - dsw) / dsw))

            [Lbfsg, Lb0p, Lb0b] = self.pl_los(
                dtot, frequency, p[ii], b0[ii], omega[ii], T, Ph, dlt, dlr,
            )

            [Ldp, Ld50] = self.dl_p(
                d_i, h_i, hts, hrs, hstd, hsrd,
                frequency, omega[ii], p[ii], b0[ii], deltaN,
            )

            # Median basic transmission loss associated with diffraction
            Lbd50 = Lbfsg + Ld50
            # Diffraction loss not exceeded for p% time
            Lbd = Lb0p + Ldp

            # Notional minimum loss associated with LoS and over-sea diffraction
            Lminb0p = Lb0p + (1 - omega[ii]) * Ldp
            if p[ii] >= b0[ii]:
                Fi = inv_cum_norm(p[ii] / 100) / inv_cum_norm(b0[ii] / 100)
                Lminb0p = Lbd50 + (Lb0b + (1 - omega[ii]) * Ldp - Lbd50) * Fi

            # Notional minimum loss associated with LoS and transhorizon enhancements
            eta = 2.5
            Lba = self.tl_anomalous(
                dtot, dlt, dlr, Dct, Dcr, dlm[ii], hts, hrs, hte, hre, hm,
                theta_t, theta_r, frequency, p[ii], T, Ph, omega[ii], ae, b0[ii],
            )

            Lminbap = eta * np.log(np.exp(Lba / eta) + np.exp(Lb0p / eta))

            # Notional loss associated with diffraction and LoS/ducting enhancements
            Lbda = Lbd
            if (Lbd >= Lminbap).any():
                Lbda = Lminbap + (Lbd - Lminbap) * Fk

            # Modified loss accounting for diffraction and LoS/ducting enhancements
            Lbam = Lbda + (Lminb0p - Lbda) * Fj

            # Troposcatter loss
            Lbs = self.tl_tropo(
                dtot, theta, frequency,
                p[ii], T, Ph, N0, tx_gain[ii], rx_gain[ii],
            )

            # Basic transmission loss not exceeded for p% time and 50% locations (eq. 60)
            Lbc_pol = -5 * np.log10(
                10 ** (-0.2 * Lbs) +
                10 ** (-0.2 * Lbam),
            )

            # Location variability for pL% of locations (Section 4.8) and
            # path-specific terminal clutter losses (Aht, Ahr; 0 unless the
            # "terrain" clutter mode is active).
            Lb_pol = Lbc_pol + Lloc + Aht + Ahr

            if (self.model_params.polarization).lower() == "horizontal":
                Lb[0, ii] = Lb_pol[0]
            elif (self.model_params.polarization).lower() == "vertical":
                Lb[0, ii] = Lb_pol[1]
            else:
                error_message = "invalid polarization"
                raise ValueError(error_message)

        if clutter_mode == "p2108":
            # Statistical clutter at each end following ITU-R P.2108
            clutter_loss = self.clutter.get_loss(
                frequency=frequency * 1000,
                distance=distance * 1000,
                clutter_scenario="terrestrial",  # Always terrestrial for P.1812
                clutter_type=self.model_params.clutter_type,
            )
        else:
            # "terrain": already added to Lb via Aht/Ahr in the loop.
            # "none": no clutter loss.
            clutter_loss = np.zeros(distance.shape)

        b_loss = np.transpose(
            self.building_entry.get_loss(frequency, elevation),
        )
        building_loss = b_loss * indoor_stations
        lb_new = Lb + clutter_loss + building_loss

        return lb_new
