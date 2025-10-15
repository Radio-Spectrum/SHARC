# -*- coding: utf-8 -*-
"""
Lightweight ITU-R P.528 aeronautical/air-ground propagation model
Compatible wrapper with PropagationP619.get_loss(...)

NOTE:
- This is a practical, modular starter that mirrors the step-by-step flow
  of P.528 Annex 2. It’s structured so you can later swap in the exact
  ray-tracing (P.676/P.835), LOS-diffraction blending, troposcatter, and
  variability blocks with high-fidelity versions.

Refs:
- ITU-R P.528-5 (09/2021): A propagation prediction method for aeronautical mobile
  and radionavigation services using the VHF, UHF and SHF bands (Annex 2).
"""

from __future__ import annotations

from multipledispatch import dispatch
import numpy as np

from sharc.propagation.propagation import Propagation
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.parameters.parameters import Parameters
from sharc.station_manager import StationManager
#from sharc.parameters.parameters_p528 import ParametersP528

# ------------------------------------------------------------
# Constants / Quick-start approximations
# ------------------------------------------------------------
AEFF_KM: float = 9257.0   # 4/3 Earth effective radius (km)
A0_KM: float   = 6371.0   # mean Earth radius (km)
EPSR_GROUND: float = 15.0
SIGMA_GROUND: float = 0.005  # S/m

# Polarization flags (align with your ParametersP528 encoding if applicable)
POL_H = 0  # horizontal
POL_V = 1  # vertical


def _db10(x: np.ndarray) -> np.ndarray:
    return 10.0 * np.log10(x)


def _fspl_dB(f_MHz: np.ndarray, r_km: np.ndarray) -> np.ndarray:
    """Free-space path loss (dB): 32.45 + 20log10(f_MHz) + 20log10(r_km)."""
    f = np.maximum(np.asarray(f_MHz, dtype=float), 1e-12)
    r = np.maximum(np.asarray(r_km, dtype=float), 1e-12)
    return 32.45 + 20.0 * np.log10(f) + 20.0 * np.log10(r)


class PropagationP528(Propagation):
    """
    Starter implementation of ITU-R P.528 (air-ground / aeronautical links)
    Public methods:
        - get_loss (Parameters, float, StationManager, StationManager, ...)
        - get_loss (np.ndarray overload; fully vectorized; Annex 2 with step markers)
    """

    def __init__(self, random_number_gen: np.random.RandomState):
        super().__init__(random_number_gen)
        self.free_space = PropagationFreeSpace(self.random_number_gen)
        # Default surface refractivity Ns (N-units) for §11; can be overridden via kwargs or ParametersP528
        self.Ns_default = 301.0

    # ------------------------------------------------------------------
    # Public wrapper compatible with PropagationP619.get_loss(...)
    # ------------------------------------------------------------------
    @dispatch(Parameters, float, StationManager, StationManager, np.ndarray, np.ndarray)
    def get_loss(self,
                 params: Parameters,
                 frequency: float,
                 station_a: StationManager,
                 station_b: StationManager,
                 station_a_gains=None,
                 station_b_gains=None) -> np.ndarray:
        """
        Wrapper compatível com PropagationP619.get_loss(...).
        Decide quem é “alto/baixo” (aeronave vs base/solo), calcula distâncias e chama o kernel.
        """
        # Distância 3D entre todos os pares (matriz N_a x N_b)
        distance = station_a.get_3d_distance_to(station_b)  # [m]
        f_arr = float(frequency) * np.ones_like(distance, dtype=float)

        # Alturas geométricas [km]
        hA_km = (np.asarray(station_a.height, dtype=float) / 1e3) * np.ones_like(distance, dtype=float)
        hB_km = (np.asarray(station_b.height, dtype=float) / 1e3) * np.ones_like(distance, dtype=float)

        # Indoor (P.528 não cobre indoor/clutter — manter 0)
        indoor = np.zeros_like(distance, dtype=bool)

        # Polarização e tempo (se vierem de ParametersP528)
        Tpol = params.single_space_station.param_p528.Tpol
        p_time = params.single_space_station.param_p528.p_time

        return self.get_loss(
            distance, f_arr, hA_km, hB_km, indoor,
            int(Tpol), float(p_time)
        )

    # ------------------------------------------------------------------
    # Core vectorized kernel (Annex 2, with explicit step markers 3-1..3-12)
    # ------------------------------------------------------------------
    @dispatch(np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, float)
    def get_loss(self,
            distance: np.ndarray,
            frequency: np.ndarray,
            h1_km: np.ndarray,
            h2_km: np.ndarray,
            indoor_stations: np.ndarray,
            Tpol: int,
            p_time: float
        ) -> np.ndarray:
        """
        Fully vectorized Annex 2 flow (no explicit Python loops), with step markers 3-1..3-12.

        Kwargs:
            polarization: int (0 = H, 1 = V)
            time_percentage: float in [1, 99]
        """
        # --- (Pre) Step 2: Input, defaults, validation ----------------------------------
        if Tpol not in (1, 0):
            raise ValueError("polarization must be 0 (H) or 1 (V)")
        if not (1.0 <= p_time <= 99.0):
            raise ValueError("time_percentage must be in [1, 99]")

        d_km  = np.maximum(distance.astype(float) / 1e3, 1e-6)
        f_MHz = np.maximum(frequency.astype(float), 1e-6)

        # Determine low/high terminals by height (broadcast-safe)
        hr1 = np.minimum(h1_km, h2_km)
        hr2 = np.maximum(h1_km, h2_km)

        # --- Step 3-1: Compute terminal parameters for BOTH terminals (use §4) -----------
        dr1, theta_r1, he1, dH1, Aa1, r1 = self._terminal_params(hr1, f_MHz)
        dr2, theta_r2, he2, dH2, Aa2, r2 = self._terminal_params(hr2, f_MHz)

        # --- Step 3-2: Determine maximum LOS distance dML --------------------------------
        dML = dr1 + dr2

        # --- Step 3-3: Construct the smooth-Earth diffraction line (Md, Ad0, AdML, dd0) --
        f_safe = np.maximum(f_MHz, 1e-9)
        d3 = dML + 0.5 * (AEFF_KM**2 / f_safe) ** (1.0 / 3.0)
        d4 = dML + 1.5 * (AEFF_KM**2 / f_safe) ** (1.0 / 3.0)
        Ad3 = self._smooth_earth_diffraction(f_MHz, d3, dr1, dr2, Tpol)
        Ad4 = self._smooth_earth_diffraction(f_MHz, d4, dr1, dr2, Tpol)
        Md  = (Ad4 - Ad3) / np.maximum(d4 - d3, 1e-9)
        Ad0 = Ad4 - Md * d4
        AdML = Md * dML + Ad0
        dd0 = -Ad0 / np.maximum(Md, 1e-9)

        # --- Step 3-4: Region decision (LOS vs Trans-horizon) ----------------------------
        los_mask = d_km < dML

        # Prepare output
        Lb = np.empty_like(d_km)

        # ========================= LOS REGION (Sections 6, 7, 8, 9, 12) =================
        if np.any(los_mask):
            # --- Step 3-5: Two-ray LOS terms (§6) + near-grazing smoothing (§8) ----------
            A_los_total = self._los_region_loss(
                d_km[los_mask], f_MHz[los_mask],
                hr1[los_mask], hr2[los_mask], dH1[los_mask], dH2[los_mask],
                dr1[los_mask], dr2[los_mask], dML[los_mask], dd0[los_mask], AdML[los_mask],
                Md[los_mask], Ad0[los_mask], Tpol,
                p_time
            )
            # Steps 3-6..3-9 handled inside _los_region_loss in this starter
            Lb[los_mask] = A_los_total

        # ============ TRANS-HORIZON REGION (Sections 10, 11, 12, 14) =====================
        if np.any(~los_mask):
            dk   = d_km[~los_mask]
            fm   = f_MHz[~los_mask]
            dr1m = dr1[~los_mask]
            dr2m = dr2[~los_mask]
            he1m = he1[~los_mask]
            he2m = he2[~los_mask]
            Md_m = Md[~los_mask]
            Ad0m = Ad0[~los_mask]
            r1m  = r1[~los_mask]
            r2m  = r2[~los_mask]
            Aa_m = Aa1[~los_mask] + Aa2[~los_mask]

            # --- Step 3-10: Diffraction at d ---------------------------------------------
            Ad = Md_m * dk + Ad0m

            # --- Step 3-11: Troposcatter loss (basic placeholder) -----------------------
            As, hv, theta_s = self._troposcatter_section11(dk, dr1m, dr2m, he1m, he2m, fm, Ns=kwargs.get('Ns', getattr(self, 'Ns_default', 301.0)))

            # Select the smaller mechanism
            AT = np.minimum(Ad, As)

            # --- Step 3-12: Combine with absorption, FSPL and variability ----------------
            r_fsl = r1m + r2m + 2.0 * np.maximum(dk - (dr1m + dr2m), 0.0)
            Afs   = _fspl_dB(fm, np.maximum(r_fsl, dk))
            Yp    = self._variability_long_term(p_time, dk, fm)
            Lb[~los_mask] = Afs + Aa_m + AT + Yp

        # --- (Post) Finalization ---------------------------------------------------------
        Lb = np.where(np.isfinite(Lb), Lb, 0.0)
        return Lb

    # ------------------------------------------------------------------
    # §4 — Terminal parameters (fully vectorized)
    # ------------------------------------------------------------------
    def _terminal_params(self, hr_km: np.ndarray, f_MHz: np.ndarray):
        """§4 Terminal parameters (fully vectorized)
        Inputs broadcast to a common shape. Returns arrays with the same shape:
            dr      : horizon distance [km] per (approx) 4/3-Earth model
            theta_r : horizon incidence angle [rad] (small-angle proxy)
            he      : effective terminal height [km]
            dH      : terrain/effective-height delta (starter: 0)
            Aa      : atmospheric absorption along terminal arc [dB] (starter: 0)
            r       : ray length terminal→horizon [km]
        """
        hr = np.maximum(np.asarray(hr_km, dtype=float), 0.0)
        _f  = np.broadcast_to(np.asarray(f_MHz, dtype=float), hr.shape)  # kept for API parity

        # Horizon distance using 4/3 Earth: d ≈ sqrt(2 * ae * h)  [vectorized]
        dr = np.sqrt(2.0 * AEFF_KM * hr)

        # Incidence angle proxy (very small angles near the radio-horizon)
        theta_r = np.sqrt(np.divide(hr, AEFF_KM, out=np.zeros_like(hr), where=hr > 0.0))

        # Effective height ~ geometric for this starter
        he = hr.copy()
        dH = hr - he
        Aa = np.zeros_like(hr)
        r = dr.copy()
        return dr, theta_r, he, dH, Aa, r

    # ------------------------------------------------------------------
    # §§6–9/§8 — LOS region loss with near-grazing blend (vectorized)
    # ------------------------------------------------------------------
    def _los_region_loss(self,
                         d_km, f_MHz,
                         hr1, hr2, dH1, dH2,
                         dr1, dr2, dML, dd0, AdML,
                         Md, Ad0, Tpol,
                         p_time):
        """LOS region loss (vectorized), covering §§6–9 and blending of §8.
        Returns A_total (already FSPL + blend + variability stub), matching input shape.
        """
        d_km  = np.asarray(d_km, dtype=float)
        f_MHz = np.asarray(f_MHz, dtype=float)
        hr1   = np.asarray(hr1, dtype=float)
        hr2   = np.asarray(hr2, dtype=float)
        dML   = np.asarray(dML, dtype=float)
        dd0   = np.asarray(dd0, dtype=float)
        AdML  = np.asarray(AdML, dtype=float)
        Md    = np.asarray(Md, dtype=float)
        Ad0   = np.asarray(Ad0, dtype=float)

        # §6: two-ray geometry ------------------------------------------------------------
        lam_km = 0.2997925 / np.maximum(f_MHz, 1e-9)
        d0 = np.minimum(np.maximum(dd0, 0.0), dML)

        # Grazing angle proxy ψ ≈ (h1+h2)/d  (clip to avoid singularities)
        psi = np.clip((hr1 + hr2) / np.maximum(d_km, 1e-6), 1e-4, np.deg2rad(89.0))

        # Excess path difference Δr ≈ 2*h1*h2/d
        delta_r = (2.0 * np.maximum(hr1, 0.0) * np.maximum(hr2, 0.0)) / np.maximum(d_km, 1e-6)
        delta_r_limit = lam_km / 2.0
        psi_limit_mask = delta_r <= delta_r_limit

        # §9: ground reflection coefficient -----------------------------------------------
        Rg, phi_g = self._ground_reflection_coeff(psi, f_MHz, Tpol)

        # §8: divergence / fringing factors (starter approximations) ----------------------
        aa = A0_KM * (1.0 / (1.0 + ((A0_KM / AEFF_KM) - 1.0) * np.cos(psi)))
        D1 = D2 = 0.5 * d_km
        r1_geo = D1 / np.cos(psi)
        r2_geo = D2 / np.cos(psi)
        Rr = (r1_geo * r2_geo) / np.maximum(D1, 1e-9)
        Dv = (1.0 + (2.0 * Rr * (1.0 + np.sin(psi)**2) / (aa * np.sin(psi))) + (2.0 * Rr / np.maximum(aa, 1e-6))**2) ** (-0.5)
        Fr = np.minimum(1.0, (D1 + D2) / np.maximum((D1 + D2) / np.cos(psi), 1e-9))

        RTg = Rg * Dv * Fr
        phi_Tg = (2.0 * np.pi * delta_r / np.maximum(lam_km, 1e-12)) + phi_g

        # Interference magnitude |1 + R e^{jphi}|^2
        Re_part = RTg * np.cos(phi_Tg)
        Im_part = RTg * np.sin(phi_Tg)
        WR0 = (1.0 + Re_part)**2 + (Im_part)**2
        WR0 = np.clip(WR0, 1e-9, None)
        A_LOS = 10.0 * np.log10(WR0)

        # Disable two-ray very close in where ψ > ψ_limit
        A_LOS = np.where(psi_limit_mask, A_LOS, 0.0)

        # Blend to diffraction near horizon (§8, eq. 55 proxy)
        Ad_at_d0 = Md * d0 + Ad0
        blend = ((d_km - d0) * (AdML - Ad_at_d0)) / np.maximum(dML - d0, 1e-6) + Ad_at_d0
        A_los_path = np.where(d_km > d0, blend, A_LOS)

        # Atmospheric absorption along direct ray ~ 0 dB (starter). For realism, plug P.676.
        Aa = 0.0
        # Free-space distance ~ straight-line between terminals (≈ d for small heights)
        Afs = _fspl_dB(f_MHz, np.maximum(d_km, 1e-6))

        # Variability (LOS, starter = 0 dB)
        Yp = self._variability_long_term(p_time, d_km, f_MHz)

        return Afs + Aa + A_los_path + Yp

    # ------------------------------------------------------------------
    # §10 — Smooth-Earth diffraction (vectorized + broadcasting safe)
    # ------------------------------------------------------------------
    def _smooth_earth_diffraction(self, f_MHz, d0_km, dr1_km, dr2_km, Tpol):
        """
        §10 Smooth-Earth diffraction, vectorized.
        Uses the piecewise F(x) / G(x) structure with safe broadcasting.
        """
        f   = np.asarray(f_MHz, dtype=float)
        d0  = np.asarray(d0_km, dtype=float)
        xdr1 = np.asarray(dr1_km, dtype=float)
        xdr2 = np.asarray(dr2_km, dtype=float)

        # Broadcast all to common shape
        f, d0, xdr1, xdr2 = np.broadcast_arrays(f, d0, xdr1, xdr2)

        # (79) surface admittance term
        s = 18000.0 * SIGMA_GROUND / np.maximum(f, 1e-12)

        # Effective K per polarization (kept consistent with earlier form)
        if Tpol == POL_H:
            K = 0.01778 * np.power(np.maximum(f, 1e-12), -1.0/3.0) * np.power(((EPSR_GROUND - 1.0)**2 + s**2), -0.25)
        else:
            K = 0.01778 * np.power(np.maximum(f, 1e-12), -1.0/3.0) * np.sqrt(
                (EPSR_GROUND**2 + s**2) / np.sqrt((EPSR_GROUND - 1.0)**2 + s**2)
            )

        def G_of_x(x):
            return 0.05751 * x - 10.0 * np.log10(np.maximum(x, 1e-12))

        # (81) normalization
        cbrt_f = np.cbrt(np.maximum(f, 1e-12))
        x0 = (1.607 - K) * cbrt_f * np.maximum(d0, 0.0)
        x1 = (1.607 - K) * cbrt_f * np.maximum(xdr1, 0.0)
        x2 = (1.607 - K) * cbrt_f * np.maximum(xdr2, 0.0)

        # (82–88) F(x) piecewise
        def F_of_x(x):
            y = 40.0 * np.log10(np.maximum(x, 1e-12)) - 117.0  # (83)
            out = np.empty_like(x)

            mask_hi = x >= 2000.0
            out[mask_hi] = G_of_x(x[mask_hi])                   # (84)

            mask_mid = (~mask_hi) & (x > 200.0)
            if np.any(mask_mid):
                W = 0.0134 * x[mask_mid] * np.exp(-0.005 * x[mask_mid])   # (85)
                out[mask_mid] = W * y[mask_mid] + (1.0 - W) * G_of_x(x[mask_mid])  # (86)

            mask_lo = ~mask_hi & ~mask_mid
            if np.any(mask_lo):
                # (87) threshold depends on K
                Kloc = np.broadcast_to(K, x.shape)[mask_lo]
                xt = 450.0 - (np.log10(np.maximum(Kloc, 1e-12)))**3
                yz = y[mask_lo]
                branch_hi = np.where(np.abs(yz) < 117.0, yz, -117.0)       # (88) top branch
                part_lo = 20.0 * np.log10(np.maximum(Kloc, 1e-12)) - 15.0 + (0.000025 * (x[mask_lo]**2) / np.maximum(Kloc, 1e-12))
                out[mask_lo] = np.where(x[mask_lo] >= xt, branch_hi, part_lo)
            return out

        G0 = G_of_x(x0)
        F1 = F_of_x(x1)
        F2 = F_of_x(x2)

        # (78) diffraction loss
        Ad = G0 - F1 - F2 - 20.0
        return Ad

    # ------------------------------------------------------------------
    # §9 — Ground reflection coefficients (vectorized)
    # ------------------------------------------------------------------
    def _ground_reflection_coeff(self, psi_rad, f_MHz, Tpol):
        psi = np.asarray(psi_rad, dtype=float)
        f   = np.asarray(f_MHz, dtype=float)
        psi, f = np.broadcast_arrays(psi, f)

        X = 18000.0 * SIGMA_GROUND / np.maximum(f, 1e-12)  # (67)
        Y = EPSR_GROUND - np.cos(psi)**2                    # (68)
        T = np.sqrt(Y**2 + X**2) + Y                        # (69)
        P = np.sqrt(0.5 * T)                                # (70)
        Q = X / np.maximum(2.0 * P, 1e-12)                  # (71)

        if Tpol == POL_H:
            denom = np.maximum(P**2 + Q**2, 1e-12)
            B = 1.0 / denom
            A = 2.0 * P / denom
            alpha = np.arctan2(-Q, np.sin(psi) - P)
            beta  = np.arctan2(Q,  np.sin(psi) + P)
        else:
            denom = np.maximum(P**2 + Q**2, 1e-12)
            B = (EPSR_GROUND**2 + X**2) / denom
            A = (2.0 * (P * EPSR_GROUND + Q * X)) / denom
            alpha = np.arctan2((EPSR_GROUND * np.sin(psi)) - Q, EPSR_GROUND * np.sin(psi) - P)
            beta  = np.arctan2((X * np.sin(psi)) + Q, EPSR_GROUND * np.sin(psi) + P)

        # Magnitude per eqs. (72–77) condensed
        num = (1.0 + B * (np.sin(psi)**2)) - A * np.sin(psi)
        den = (1.0 + B * (np.sin(psi)**2)) + A * np.sin(psi)
        Rg = np.sqrt(np.clip(num / np.maximum(den, 1e-12), 1e-12, None))
        phi_g = alpha - beta
        return Rg, phi_g

    # ------------------------------------------------------------------
    # §11 — Troposcatter (full Section 11 implementation, vectorized)
    # ------------------------------------------------------------------
    def _troposcatter_section11(self, d_km, dr1, dr2, he1, he2, f_MHz, Ns=None):
        """Implements §11 Troposcatter per P.528-5 equations (89)–(126).
        Returns (As [dB], hv [km], theta_s [rad]).
        """
        # Inputs
        d_km = np.asarray(d_km, dtype=float)
        dr1  = np.asarray(dr1, dtype=float)
        dr2  = np.asarray(dr2, dtype=float)
        he1  = np.asarray(he1, dtype=float)
        he2  = np.asarray(he2, dtype=float)
        f    = np.asarray(f_MHz, dtype=float)
        d_km, dr1, dr2, he1, he2, f = np.broadcast_arrays(d_km, dr1, dr2, he1, he2, f)

        # Ns (surface refractivity) default
        if Ns is None:
            Ns = getattr(self, 'Ns_default', 301.0)
        Ns = float(Ns)

        # Step 11-1: scatter distance ds (90)
        ds = d_km - (dr1 + dr2)
        # Step 11-2: if ds<=0, no common volume → As=0, hv=0, theta_s=0 (91–93)
        no_cv = ds <= 0.0

        # Step 11-3: dz = 0.5*ds (94)
        dz = 0.5 * np.maximum(ds, 0.0)

        # Step 11-4: atmospheric gradient parameters (95–97)
        Am = 1.0 / A0_KM
        dN = Am - 1.0 / AEFF_KM
        Ge = Ns * 1e-6 / dN  # Γ_e

        # Step 11-5: geometry yielding hv and theta_A (98–107)
        za = ( (dz/2.0)**2 ) / (2.0 * AEFF_KM)   # (98)
        zb = ( dz**2 ) / (2.0 * AEFF_KM)         # (99)
        Qo = Am - dN                              # (100)
        Qa = Am - dN * np.exp(-za / Ge)          # (101)
        Qb = Am - dN * np.exp(-zb / Ge)          # (101)
        zap = (7.0*Qo + 6.0*Qa - Qb) * (dz**2) / 96.0  # (102)
        zbp = (Qo + 2.0*Qa) * (dz**2) / 6.0            # (103)
        QA = Am - dN * np.exp(-zap / Ge)               # (104)
        QB = Am - dN * np.exp(-zbp / Ge)               # (104)
        hv = (Qo + 2.0*QA) * (dz**2) / 6.0             # (105)
        theta_A = (Qo + 4.0*QA + QB) * dz / 6.0        # (106)
        theta_s = 2.0 * theta_A                        # (107)

        # Step 11-6: scattering efficiency Se (108–111)
        eps1 = (5.67e-6) * (Ns**2) - 0.00232 * Ns + 0.031  # (108)
        eps2 = 0.0002 * (Ns**2) - 0.06 * Ns + 6.6          # (109)
        gamma = 0.1424 * (1.0 + eps1 / np.exp((hv/4.0)**6))  # (110)
        Se = 83.1 - (eps2 / (1.0 + 0.07716 * (hv**2))) + 20.0 * np.log10(((0.1424/gamma)**2) * np.exp(gamma*hv))  # (111)

        # Step 11-7: scattering volume term SV (112–126)
        # d1,d2: distance from terminals to CV center along smooth-Earth
        d1 = dr1 + dz
        d2 = dr2 + dz
        # (112)
        XA1 = he1**2 + 4.0 * (AEFF_KM + he1) * AEFF_KM * (np.sin(d1 / (2.0 * AEFF_KM))**2)
        XA2 = he2**2 + 4.0 * (AEFF_KM + he2) * AEFF_KM * (np.sin(d2 / (2.0 * AEFF_KM))**2)
        # (113–114)
        l1 = np.sqrt(XA1 + dz)
        l2 = np.sqrt(XA2 + dz)
        ell = l1 + l2
        # (115)
        s = (l1 - l2) / np.maximum(ell, 1e-12)
        # (116)
        eta = gamma * theta_s * ell / 2.0
        # (117)
        kappa = f / 0.0477
        # (118)
        rho1 = 2.0 * kappa * theta_s * he1
        rho2 = 2.0 * kappa * theta_s * he2
        # (120–123)
        Xv1 = ((1.0 + s)**2) * eta
        Xv2 = ((1.0 - s)**2) * eta
        q1 = Xv1**2 + rho1**2
        q2 = Xv2**2 + rho2**2
        # (124)
        A = (1.0 - s**2)**2
        # (125)
        BS = (6.0 + 8.0*s**2
              + (8.0*(1.0 - s) * (Xv1**2) / np.maximum(rho1**2, 1e-12)) * (1.0/np.maximum(q1,1e-12))
              + (8.0*(1.0 + s) * (Xv2**2) / np.maximum(rho2**2, 1e-12)) * (1.0/np.maximum(q2,1e-12))
              + 2.0*(1.0 - s**2) * (1.0 + 2.0*(Xv1**2)/np.maximum(q1,1e-12)) * (1.0 + 2.0*(Xv2**2)/np.maximum(q2,1e-12)))
        # (126)
        CS = 12.0 * ((rho1 + np.sqrt(2.0)*rho1)**2) * ((rho2 + np.sqrt(2.0)*rho2)**2) * ((rho1 + rho2) / np.maximum(rho1 + rho2 + 2.0*np.sqrt(2.0), 1e-12))
        # (119)
        SV = 10.0 * np.log10( (A * (eta**2) + BS * eta) * q1 * q2 / np.maximum(rho1**2 * rho2**2 + CS, 1e-24) )

        # Step 11-8: Troposcatter loss (89)
        As = Se + SV + 10.0 * np.log10(np.maximum(kappa * (theta_s**3) / np.maximum(ell,1e-12), 1e-24))

        # Enforce Step 11-2 conditions for ds<=0
        As = np.where(no_cv, 0.0, As)
        hv = np.where(no_cv, 0.0, hv)
        theta_s = np.where(no_cv, 0.0, theta_s)
        return As, hv, theta_s

    # ------------------------------------------------------------------
    # §§12/14 — Variability model (vectorized; replaces stub)
    # ------------------------------------------------------------------
    def _variability_long_term(self, p_time, d_km, f_MHz,
                               sigma_e_base: float = 3.0,
                               sigma_t_base: float = 2.0,
                               sigma_e_slope: float = 0.002,
                               sigma_t_slope: float = 0.001):
        """
        Combined long-term (location/climate) + short-term (time) variability per §§12/14.
        This implementation provides a pragmatic, vectorized approximation:
        L_b(p) = L_b(50%) + Y_p,  with  Y_p = z(p) * sqrt( sigma_e^2 + sigma_t^2 )
        where z(p) is the standard normal deviate for probability p.

        Parameters
        ----------
        p_time : float in [1,99]
            Requested time percentage (same p used for aggregation here).
        d_km : array_like
            Path length (km).
        f_MHz : array_like
            Frequency (MHz).
        sigma_e_base, sigma_t_base : float
            Baseline standard deviations (dB) for long-term and time variability.
        sigma_e_slope, sigma_t_slope : float
            Distance dependence (per km) contributing to standard deviations.

        Notes
        -----
        - This is a calibrated scaffold. For strict P.528 equations, replace the
          sigma_e/t parameterizations with the exact §12/§14 expressions from the
          Recommendation.
        - Returns Y_p in dB (can be added directly to median L_b).
        """
        d = np.asarray(d_km, dtype=float)
        f = np.asarray(f_MHz, dtype=float)
        d, f = np.broadcast_arrays(d, f)

        # Clamp p and compute signed z-score (p<50 -> negative; p>50 -> positive)
        p = float(np.clip(p_time, 1.0, 99.0)) / 100.0
        z = self._inv_norm_cdf(p)  # ~N(0,1)

        # Simple frequency scalings (mild): more variability at higher f for scintillation;
        # long-term weakly depends on f. Tune/replace per §12/§14 if desired.
        fe = 1.0 + 0.02 * np.log10(np.maximum(f, 1.0))
        ft = 1.0 + 0.05 * np.log10(np.maximum(f, 1.0))

        sigma_e = fe * (sigma_e_base + sigma_e_slope * d)
        sigma_t = ft * (sigma_t_base + sigma_t_slope * d)

        sigma_tot = np.sqrt(np.maximum(sigma_e**2 + sigma_t**2, 1e-12))
        Yp = z * sigma_tot
        return Yp

    # Inverse normal CDF (Acklam's approximation) for 0<p<1
    def _inv_norm_cdf(self, p: float) -> float:
        # Coefficients for Acklam's approximation
        a = [-3.969683028665376e+01,  2.209460984245205e+02,
             -2.759285104469687e+02,  1.383577518672690e+02,
             -3.066479806614716e+01,  2.506628277459239e+00]
        b = [-5.447609879822406e+01,  1.615858368580409e+02,
             -1.556989798598866e+02,  6.680131188771972e+01,
             -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01,
             -2.400758277161838e+00, -2.549732539343734e+00,
              4.374664141464968e+00,  2.938163982698783e+00]
        d = [ 7.784695709041462e-03,  3.224671290700398e-01,
              2.445134137142996e+00,  3.754408661907416e+00]
        plow  = 0.02425
        phigh = 1 - plow
        if p <= 0.0:
            return -np.inf
        if p >= 1.0:
            return np.inf
        if p < plow:
            q = np.sqrt(-2*np.log(p))
            num = (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5])
            den = ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
            return num/den
        if p > phigh:
            q = np.sqrt(-2*np.log(1-p))
            num = -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5])
            den = ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
            return num/den
        q = p - 0.5
        r = q*q
        num = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q
        den = (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
        return num/den

# --------------------------------------------------------------------------------------
# Optional quick test
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    f_MHz     = 3500.0
    h1_km     = 0.050   # 50 m
    h2_km     = 1.0    # 10 km aircraft
    d_km      = np.linspace(1.0, 100.0, 800)
    d_m       = np.sqrt(1**2 + d_km**2) * 1000.0
    f_vec     = np.full_like(d_m, f_MHz, dtype=float)
    h1_v      = np.full_like(d_km, h1_km, dtype=float)
    h2_v      = np.full_like(d_km, h2_km, dtype=float)
    indoor    = np.zeros_like(d_km, dtype=bool)

    rng = np.random.RandomState(42)
    model = PropagationP528(rng)

    Lb = model.get_loss(d_m, f_vec, h1_v, h2_v, indoor,
                        polarization=POL_V, time_percentage=10.0)

    print(f"\nP.528 test: f={f_MHz:.0f} MHz, h1={h1_km*1000:.0f} m, h2={h2_km:.1f} km, pol=V, p=10%")
    for km in [1, 7.13, 13.27, 25.53, 37.80, 50.0]:
        i = np.argmin(np.abs(d_km - km))
        print(f"d = {d_km[i]:8.2f} km  ->  Lb = {Lb[i]:.2f} dB")

    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8,5))
        plt.plot(d_km, Lb, label="P.528 (pol=V, p=10%)")
        plt.xlabel("Distance (km)")
        plt.ylabel("Basic transmission loss Lb (dB)")
        plt.title(f"ITU-R P.528 – Lb vs Distance | f={f_MHz:.0f} MHz")
        plt.grid(True, which="both", ls="--", alpha=0.4)
        plt.legend()
        plt.tight_layout()
        plt.show()
    except Exception:
        pass
