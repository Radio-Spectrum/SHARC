# -*- coding: utf-8 -*-
"""
ITU-R P.528 (Annex 2) – Python port with LOS smoothing per Steps 6–8

Notes
-----
- Maintains class name, imports, public `get_loss` overloads, and the method
  that reads the distance between stations via `station_a.get_3d_distance_to(station_b)`.
- Adds `polarization` (0=H, 1=V) and `time_percentage` (1..99) as optional kwargs
  to both get_loss overloads. If omitted, class defaults are used.
- Hardened against NaNs (safe logs/divisions and clipping of power factors).
"""

from multipledispatch import dispatch
import numpy as np

from sharc.propagation.propagation import Propagation
from sharc.parameters.parameters import Parameters
from sharc.station_manager import StationManager


# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------
A0_KM   = 6371.0      # mean Earth radius
AEFF_KM = 9257.0      # effective Earth radius (4/3 Earth)
EPS_R   = 15.0        # average ground relative permittivity
SIGMA   = 0.005       # ground conductivity [S/m]
THIRD   = 1.0 / 3.0
EPS     = 1e-12       # numeric epsilon

POL_H = 0
POL_V = 1

# Nakagami-Rice tables (K rows × P cols)
_YPI_99_IDX = 16
_K_TABLE = np.array([-40, -25, -20, -18, -16, -14, -12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 20], dtype=float)
_P_TABLE = np.array([1, 2, 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 85, 90, 95, 98, 99], dtype=float)
_NKR = np.array([
 [-0.1417,-0.1252,-0.1004,-0.0784,-0.0634,-0.0515,-0.0321,-0.0155,0.0000,0.0156,0.0323,0.0518,0.0639,0.0791,0.1016,0.1271,0.1441],
 [-0.7676,-0.6811,-0.5497,-0.4312,-0.3504,-0.2856,-0.1790,-0.0870,0.0000,0.0878,0.1828,0.2953,0.3651,0.4537,0.5868,0.7390,0.8420],
 [-1.3183,-1.1738,-0.9524,-0.7508,-0.6121,-0.5003,-0.3151,-0.1537,0.0000,0.1564,0.3269,0.5308,0.6585,0.8218,1.0696,1.3572,1.5544],
 [-1.6263,-1.4507,-1.1805,-0.9332,-0.7623,-0.6240,-0.3940,-0.1926,0.0000,0.1969,0.4127,0.6722,0.8355,1.0453,1.3660,1.7417,2.0014],
 [-1.9963,-1.7847,-1.4573,-1.1557,-0.9462,-0.7760,-0.4916,-0.2410,0.0000,0.2478,0.5209,0.8519,1.0615,1.3326,1.7506,2.2463,2.5931],
 [-2.4355,-2.1829,-1.7896,-1.4247,-1.1695,-0.9613,-0.6113,-0.3007,0.0000,0.3114,0.6573,1.0802,1.3505,1.7028,2.2526,2.9156,3.3872],
 [-2.9491,-2.6507,-2.1831,-1.7455,-1.4375,-1.1846,-0.7567,-0.3737,0.0000,0.3903,0.8281,1.3698,1.7198,2.1808,2.9119,3.8143,4.4714],
 [-3.5384,-3.1902,-2.6407,-2.1218,-1.7535,-1.4495,-0.9307,-0.4619,0.0000,0.4874,1.0404,1.7348,2.1898,2.7975,3.7820,5.0373,5.9833],
 [-4.1980,-3.7974,-3.1602,-2.5528,-2.1180,-1.7565,-1.1345,-0.5662,0.0000,0.6045,1.2999,2.1887,2.7814,3.5868,4.9288,6.7171,8.1319],
 [-4.9132,-4.4591,-3.7313,-3.0306,-2.5247,-2.1011,-1.3655,-0.6855,0.0000,0.7415,1.6078,2.7374,3.5059,4.5714,6.4060,8.9732,11.0973],
 [-5.6559,-5.1494,-4.3315,-3.5366,-2.9578,-2.4699,-1.6150,-0.8154,0.0000,0.8935,1.9530,3.3611,4.3363,5.7101,8.1216,11.5185,14.2546],
 [-6.3810,-5.8252,-4.9219,-4.0366,-3.3871,-2.8364,-1.8638,-0.9455,0.0000,1.0458,2.2979,3.9771,5.1450,6.7874,9.6276,13.4690,16.4251],
 [-7.0247,-6.4249,-5.4449,-4.4782,-3.7652,-3.1580,-2.0804,-1.0574,0.0000,1.1723,2.5755,4.4471,5.7363,7.5266,10.5553,14.5401,17.5511],
 [-7.5229,-6.8862,-5.8424,-4.8090,-4.0446,-3.3927,-2.2344,-1.1347,0.0000,1.2535,2.7446,4.7144,6.0581,7.9073,11.0003,15.0270,18.0526],
 [-7.8532,-7.1880,-6.0963,-5.0145,-4.2145,-3.5325,-2.3227,-1.1774,0.0000,1.2948,2.8268,4.8377,6.2021,8.0724,11.1869,15.2265,18.2566],
 [-8.0435,-7.3588,-6.2354,-5.1234,-4.3022,-3.6032,-2.3656,-1.1975,0.0000,1.3130,2.8619,4.8888,6.2610,8.1388,11.2607,15.3047,18.3361],
 [-8.2238,-7.5154,-6.3565,-5.2137,-4.3726,-3.6584,-2.3979,-1.2121,0.0000,1.3255,2.8855,4.9224,6.2992,8.1814,11.3076,15.3541,18.3864]
], dtype=float)


# --------------------------------------------------------------------------------------
# Numeric helpers
# --------------------------------------------------------------------------------------
def _clamp_pos(x):
    return np.maximum(x, EPS)

def _lin_interp(x1, y1, x2, y2, x):
    denom = (x2 - x1)
    if abs(denom) < EPS:
        return 0.5 * (y1 + y2)
    return (y1 * (x2 - x) + y2 * (x - x1)) / denom

def _inv_Qccdf(q):
    """Inverse complementary CDF approximation (P.1057 / A&S 26.2.23)."""
    C0, C1, C2 = 2.515516, 0.802853, 0.010328
    D1, D2, D3 = 1.432788, 0.189269, 0.001308
    x = q if q <= 0.5 else 1.0 - q
    T = np.sqrt(-2.0 * np.log(_clamp_pos(x)))
    zeta = ((C2 * T + C1) * T + C0) / (((D3 * T + D2) * T + D1) * T + 1.0)
    Q = T - zeta
    return -Q if q > 0.5 else Q

def _find_K_for_Ypi99(y99_db):
    col = _YPI_99_IDX
    if y99_db < _NKR[0, col]:
        return _K_TABLE[0]
    for i in range(1, len(_K_TABLE)):
        if y99_db < _NKR[i, col]:
            return _lin_interp(_NKR[i-1, col], _K_TABLE[i-1],
                               _NKR[i, col], _K_TABLE[i], y99_db)
    return _K_TABLE[-1]

def _nakagami_rice(K_db, p):
    """Bilinear interpolation of Nakagami-Rice table."""
    k_idx = int(np.searchsorted(_K_TABLE, K_db, side="left"))
    k_idx = int(np.clip(k_idx, 0, len(_K_TABLE)))
    if k_idx == 0:
        row_low = row_high = 0
    elif k_idx == len(_K_TABLE):
        row_low = row_high = len(_K_TABLE) - 1
    else:
        row_low, row_high = k_idx - 1, k_idx
    p_idx = int(np.searchsorted(_P_TABLE, p, side="left"))
    p_idx = int(np.clip(p_idx, 0, len(_P_TABLE)))
    if p_idx == 0:
        col_low = col_high = 0
    elif p_idx == len(_P_TABLE):
        col_low = col_high = len(_P_TABLE) - 1
    else:
        if abs(_P_TABLE[p_idx] - p) < EPS:
            col_low = col_high = p_idx
        else:
            col_low, col_high = p_idx - 1, p_idx
    v_high = _lin_interp(_K_TABLE[row_low], _NKR[row_low, col_high],
                         _K_TABLE[row_high], _NKR[row_high, col_high], K_db)
    v_low  = _lin_interp(_K_TABLE[row_low], _NKR[row_low,  col_low],
                         _K_TABLE[row_high], _NKR[row_high, col_low], K_db)
    if col_low == col_high:
        return v_low
    return _lin_interp(_P_TABLE[col_low], v_low, _P_TABLE[col_high], v_high, p)


# --------------------------------------------------------------------------------------
# Core model
# --------------------------------------------------------------------------------------
class PropagationP528(Propagation):
    """
    ITU-R P.528 with LOS (FS/2-ray with Step-8 smoothing), smooth-earth diffraction,
    trans-horizon troposcatter selection, and variability combiner.

    Public method:
        get_loss(...): overloads preserved; accept
                       polarization=0|1 and time_percentage=1..99 as kwargs.
    """

    def __init__(self, random_number_gen: np.random.RandomState):
        super().__init__(random_number_gen)
        self.eps_r = EPS_R
        self.sigma = SIGMA
        self.default_polarization = POL_V          # 0=H, 1=V
        self.default_time_percentage = 50.0        # %
        self.include_variability = True
        self.include_atm_abs = False               # Aa = 0 dB (placeholder)

    # ---------------------------
    # Geometry helpers
    # ---------------------------
    @staticmethod
    def _wavelength_km(f_MHz: float) -> float:
        return 0.2997925 / _clamp_pos(f_MHz)

    @staticmethod
    def _terminal_horizon_distance_km(h_km) -> np.ndarray:
        h_km = np.maximum(h_km, 0.0)
        return np.sqrt(2.0 * AEFF_KM * h_km)

    @staticmethod
    def _max_los_distance_km(h1_km, h2_km) -> np.ndarray:
        return PropagationP528._terminal_horizon_distance_km(h1_km) + \
               PropagationP528._terminal_horizon_distance_km(h2_km)

    # ---------------------------
    # Smooth-Earth diffraction (Vogler distance/height functions)
    # ---------------------------
    @staticmethod
    def _distance_function(x_km):
        x_km = _clamp_pos(x_km)
        return 0.05751 * x_km - 10.0 * np.log10(x_km)

    @staticmethod
    def _height_function(x_km, K):
        x_km = _clamp_pos(x_km)
        K = max(K, EPS)
        y_db = 40.0 * np.log10(x_km) - 117.0
        Gx = PropagationP528._distance_function(x_km)
        if x_km <= 200.0:
            xt = 450.0 / (-(np.log10(K))**3 + EPS)
            if x_km >= xt:
                return np.clip(y_db, -117.0, 117.0)
            return 20.0 * np.log10(K) - 15.0 + (0.000025 * (x_km**2) / K)
        if x_km > 2000.0:
            return Gx
        W = 0.0134 * x_km * np.exp(-0.005 * x_km)
        return W * y_db + (1.0 - W) * Gx

    def _smooth_earth_diffraction(self, d1_km, d2_km, f_MHz, d0_km, pol):
        s = 18000.0 * self.sigma / _clamp_pos(f_MHz)
        if pol == POL_H:
            K = 0.01778 * f_MHz**(-THIRD) * (((self.eps_r - 1.0)**2 + s**2) ** -0.25)
        else:
            K = 0.01778 * f_MHz**(-THIRD) * (((self.eps_r**2 + s**2) /
                                              (((self.eps_r - 1.0)**2 + s**2) ** 0.5 + EPS)) ** 0.5)
        B0 = 1.607
        fac = (B0 - K) * (f_MHz**THIRD)
        x0 = max(fac * d0_km, EPS)
        x1 = max(fac * d1_km, EPS)
        x2 = max(fac * d2_km, EPS)
        Gx = self._distance_function(x0)
        Fx1 = self._height_function(x1, K)
        Fx2 = self._height_function(x2, K)
        return Gx - Fx1 - Fx2 - 20.0

    def _build_diffraction_line(self, f_MHz, dML_km, d1_km, d2_km, pol):
        incr = (AEFF_KM**2 / _clamp_pos(f_MHz))**(1.0/3.0)
        d3 = dML_km + 0.5 * incr
        d4 = dML_km + 1.5 * incr
        A3 = self._smooth_earth_diffraction(d1_km, d2_km, f_MHz, d3, pol)
        A4 = self._smooth_earth_diffraction(d1_km, d2_km, f_MHz, d4, pol)
        denom = (d4 - d3)
        Md = 0.0 if abs(denom) < EPS else (A4 - A3) / denom
        Ad0 = A4 - Md * d4
        AdML = Md * dML_km + Ad0
        dd = -Ad0 / (Md + EPS)
        return Md, Ad0, AdML, dd

    # ---------------------------
    # Reflection coefficient (Section 9)
    # ---------------------------
    def _reflection_coeff(self, psi_rad, f_MHz, pol):
        psi = np.clip(psi_rad, 0.0, np.pi/2)
        spsi = np.sin(psi)
        cpsi = np.cos(psi)
        X = (18000.0 * self.sigma) / _clamp_pos(f_MHz)
        Y = self.eps_r - cpsi**2
        T = np.sqrt(np.maximum(Y**2 + X**2, 0.0)) + Y
        P = np.sqrt(np.maximum(0.5 * T, EPS))
        Q = X / (2.0 * P)
        if pol == POL_H:
            B = 1.0 / (P**2 + Q**2)
            A = (2.0 * P) / (P**2 + Q**2)
            alpha = np.arctan2(-Q, spsi - P)
            beta  = np.arctan2(Q,  spsi + P)
        else:
            B = ((self.eps_r**2 + X**2) / (P**2 + Q**2))
            A = (2.0 * (P*self.eps_r + Q*X)) / (P**2 + Q**2)
            alpha = np.arctan2(self.eps_r*spsi - Q, self.eps_r*spsi - P)
            beta  = np.arctan2(X*spsi + Q,        self.eps_r*spsi + P)
        num = (1.0 + (B * spsi**2) - (A * spsi))
        den = (1.0 + (B * spsi**2) + (A * spsi))
        ratio = num / (den + EPS)
        Rg = np.sqrt(np.maximum(ratio, 0.0))
        phi_g = alpha - beta
        return Rg, phi_g

    # ---------------------------
    # LOS excess loss with Step-8 smoothing (FS/2-ray + linear ramp to A_dML)
    # ---------------------------
    @staticmethod
    def _two_ray_delta_r_km(h1_km, h2_km, d_km):
        return 2.0 * h1_km * h2_km / _clamp_pos(d_km)

    def _los_excess_loss_smooth(self, f_MHz, h1_km, h2_km, d_km, pol,
                                dML_km, d_r1_km, d_r2_km, Md, Ad0, AdML, dd):
        lam_km = self._wavelength_km(f_MHz)

        # d_y6 from Δr = λ/6 using the flat-earth Δr ≈ 2 h1 h2 / d
        d_y6 = (12.0 * h1_km * h2_km) / max(lam_km, EPS)

        # choose d0 (Step 8, same logic as MATLAB code)
        if (d_r1_km >= dd) or (dd >= dML_km):
            d0 = d_r1_km if (d_r1_km > d_y6 or d_y6 > dML_km) else d_y6
        elif (dd < d_y6) and (d_y6 < dML_km):
            d0 = d_y6
        else:
            d0 = dd
        d0 = np.clip(d0, 0.0, dML_km - 1e-6)

        def two_ray_excess(dkm):
            delta_r = 2.0 * h1_km * h2_km / max(dkm, EPS)
            # If beyond the first-lobe region, use free-space (0 dB excess)
            if delta_r > lam_km / 2.0:
                return 0.0
            psi = np.deg2rad(1.5)
            Rg, phi_g = self._reflection_coeff(psi, f_MHz, pol)
            phi_Tg = 2.0 * np.pi * (delta_r / lam_km) + phi_g
            W = np.abs(1.0 + Rg * np.exp(1j * phi_Tg))**2
            W = float(np.clip(W, EPS, 1.0))  # clip to avoid log(0) and >1
            return 10.0 * np.log10(W)

        # value at d0 (may be FS=0 dB or 2-ray)
        A_d0 = two_ray_excess(d0)

        if d_km > d0:
            # Eq. (8-1) – linear ramp from d0..dML to the diffraction loss at dML
            if dML_km > d0 + 1e-9:
                return ((d_km - d0) * (AdML - A_d0) / (dML_km - d0)) + A_d0
            return AdML
        else:
            return two_ray_excess(d_km)

    # ---------------------------
    # Simple Troposcatter stand-in (>=20 dB where valid)
    # ---------------------------
    @staticmethod
    def _troposcatter_simple(f_MHz, d_km):
        return 20.0 + 0.08 * d_km

    # ---------------------------
    # Variability combiner
    # ---------------------------
    @staticmethod
    def _combine_dists(A_M, A_p, B_M, B_p, p):
        C_M = A_M + B_M
        Y1 = A_p - A_M
        Y2 = B_p - B_M
        Y3 = np.sqrt(np.maximum(Y1**2 + Y2**2, 0.0))
        return C_M + (Y3 if p < 50.0 else -Y3)

    def _long_term_variability(self, d_r1_km, d_r2_km, d_km, f_MHz, p, f_theta_h, A_T_db):
        # Compact Section 14 with guards
        d_qs = 65.0 * (100.0 / _clamp_pos(f_MHz))**THIRD
        d_Lq = d_r1_km + d_r2_km
        d_q = d_Lq + d_qs
        d_e = (130.0 * d_km / _clamp_pos(d_q)) if d_km <= d_q else (130.0 + d_km - d_q)

        if f_MHz > 1600.0:
            g10 = 1.05
            g90 = 1.05
        else:
            g10 = (0.21 * np.sin(5.22 * np.log10(_clamp_pos(f_MHz) / 200.0))) + 1.28
            g90 = (0.18 * np.sin(5.22 * np.log10(_clamp_pos(f_MHz) / 200.0))) + 1.23

        c1 = np.array([2.93e-4, 5.25e-4, 1.59e-5])
        c2 = np.array([3.78e-8, 1.57e-6, 1.56e-11])
        c3 = np.array([1.02e-7, 4.70e-7, 2.77e-8])
        n1 = np.array([2.00, 1.97, 2.32])
        n2 = np.array([2.88, 2.31, 4.08])
        n3 = np.array([3.15, 2.90, 3.25])
        finf = np.array([3.2, 5.4, 0.0])
        fm   = np.array([8.2, 10.0, 3.9])

        Z = np.zeros(3)
        for i in range(3):
            f2 = finf[i] + ((fm[i] - finf[i]) * np.exp(-c2[i] * (d_e**n2[i])))
            Z[i] = (c1[i]*(d_e**n1[i]) - f2) * np.exp(-c3[i]*(d_e**n3[i])) + f2

        if p == 50:
            Yp = Z[2]
        elif p > 50:
            z90 = _inv_Qccdf(0.90)
            z_p = _inv_Qccdf(p/100.0)
            cp = z_p / (z90 + EPS)
            Yp = cp * (-Z[0] * g90) + Z[2]
        else:
            if p >= 10:
                z10 = _inv_Qccdf(0.10)
                z_p = _inv_Qccdf(p/100.0)
                cp = z_p / (z10 + EPS)
            else:
                ps  = np.array([1, 2, 5, 10], dtype=float)
                cps = np.array([1.9507, 1.7166, 1.3265, 1.0000], dtype=float)
                idx = int(np.searchsorted(ps, p, side="right"))
                idx = int(np.clip(idx, 1, len(ps)-1))
                cp = _lin_interp(ps[idx-1], cps[idx-1], ps[idx], cps[idx], p)
            Yp = cp * (Z[1] * g10) + Z[2]

        Y10   = (Z[1] * g10) + Z[2]
        YeI   = f_theta_h * Yp
        YeI10 = f_theta_h * Y10
        AYI   = (A_T_db + YeI10) - 3.0
        AY    = max(AYI, 0.0)
        Ye    = YeI - AY

        if p < 10:
            cY = np.array([-5.0, -4.5, -3.7, 0.0])
            ps = np.array([1, 2, 5, 10], dtype=float)
            idx = int(np.searchsorted(ps, p, side="right"))
            idx = int(np.clip(idx, 1, len(ps)-1))
            cYi = _lin_interp(ps[idx-1], cY[idx-1], ps[idx], cY[idx], p)
            Ye = Ye + A_T_db
            Ye = min(Ye, -cYi)
            Ye = Ye - A_T_db
        return Ye, AY

    # ----------------------------------------------------------------------------------
    # Public API — overloads preserved; accept polarization & time_percentage
    # ----------------------------------------------------------------------------------
    @dispatch(Parameters, float, StationManager, StationManager, np.ndarray, np.ndarray)
    def get_loss(self,
                 params: Parameters,
                 frequency: float,
                 station_a: StationManager,
                 station_b: StationManager,
                 station_a_gains=None,
                 station_b_gains=None,
                 **kwargs) -> np.ndarray:
        """
        Station-based overload (kept). New kwargs:
            polarization: int (0=H, 1=V)
            time_percentage: float in [1, 99]
        """
        distance = station_a.get_3d_distance_to(station_b)  # [m]
        f_arr = float(frequency) * np.ones(distance.shape)

        hA_km = (float(station_a.height) / 1e3) * np.ones(distance.shape)
        hB_km = (float(station_b.height) / 1e3) * np.ones(distance.shape)
        indoor = np.zeros_like(distance, dtype=bool)

        pol = getattr(params, "polarization", None)
        p   = getattr(params, "time_percentage", None)

        pol = kwargs.get("polarization", pol)
        p   = kwargs.get("time_percentage", p)

        if pol is None:
            pol = self.default_polarization
        if p is None:
            p = self.default_time_percentage

        return self.get_loss(distance=distance,
                             frequency=f_arr,
                             h1_km=hA_km,
                             h2_km=hB_km,
                             indoor_stations=indoor,
                             polarization=int(pol),
                             time_percentage=float(p))

    @dispatch(np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    def get_loss(self,
                 distance: np.ndarray,      # [m]
                 frequency: np.ndarray,     # [MHz]
                 h1_km: np.ndarray,
                 h2_km: np.ndarray,
                 indoor_stations: np.ndarray,
                 **kwargs) -> np.ndarray:
        """
        Vectorized overload (kept). New kwargs:
            polarization: int (0=H, 1=V)
            time_percentage: float in [1, 99]
        """
        pol = int(kwargs.get("polarization", self.default_polarization))
        p   = float(kwargs.get("time_percentage", self.default_time_percentage))
        if pol not in (0, 1):
            raise ValueError("polarization must be 0 (H) or 1 (V)")
        if not (1.0 <= p <= 99.0):
            raise ValueError("time_percentage must be in [1, 99]")

        d_km  = np.maximum(distance.astype(float) / 1000.0, EPS)
        f_MHz = np.maximum(frequency.astype(float), EPS)
        Lfs = 20.0 * np.log10(f_MHz) + 20.0 * np.log10(d_km) + 32.45

        dML = self._max_los_distance_km(h1_km, h2_km)
        Aa = np.zeros_like(Lfs)
        A_excess = np.zeros_like(Lfs)

        it = np.nditer(Lfs, flags=['multi_index'])
        while not it.finished:
            idx = it.multi_index
            dk  = float(d_km[idx])
            fm  = float(f_MHz[idx])
            h1  = float(h1_km[idx])
            h2  = float(h2_km[idx])
            dml = float(dML[idx])

            # Build diffraction line once (needed for both branches)
            dr1 = float(self._terminal_horizon_distance_km(h1))
            dr2 = float(self._terminal_horizon_distance_km(h2))
            Md, Ad0, AdML, dd = self._build_diffraction_line(fm, dml, dr1, dr2, pol)

            if dk < dml - 1e-3:
                # LOS with P.528 Step-8 smoothing
                A_los = self._los_excess_loss_smooth(fm, h1, h2, dk, pol,
                                                     dml, dr1, dr2, Md, Ad0, AdML, dd)

                # LOS variability – simple proxy for f_theta_h
                theta_h1 = 0.0
                if theta_h1 <= 0.0:
                    f_theta_h = 1.0
                elif theta_h1 >= 1.0:
                    f_theta_h = 0.0
                else:
                    f_theta_h = max(0.5 - (1/np.pi) * np.arctan(20.0 * np.log10(32.0 * theta_h1)), 0.0)

                if self.include_variability:
                    Ye, AY = self._long_term_variability(dr1, dr2, dk, fm, p, f_theta_h, A_los)
                    a_km = dk  # slant proxy
                    Ypi99 = 10.0 * np.log10(fm * (a_km**3) + EPS) - 84.26
                    Kt = _find_K_for_Ypi99(Ypi99)
                    Ypi = _nakagami_rice(Kt, p)
                    Ytot = self._combine_dists(Ye, Ye, 0.0, Ypi, p)
                else:
                    Ytot = 0.0

                A_excess[idx] = A_los + Ytot

            else:
                # Trans-horizon: pick min(diffraction, troposcatter)
                A_diff  = Md * dk + Ad0
                A_scatt = self._troposcatter_simple(fm, dk)
                A_T = min(A_diff, A_scatt)

                if self.include_variability:
                    Ye, _ = self._long_term_variability(dr1, dr2, dk, fm, p, 1.0, -A_T)
                else:
                    Ye = 0.0
                A_excess[idx] = A_T - Ye

            it.iternext()

        Lb = Lfs + Aa + A_excess
        Lb = np.where(np.isfinite(Lb), Lb, 0.0)
        return Lb


# --------------------------------------------------------------------------------------
# Optional quick test
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    f_MHz     = 3500.0
    h1_km     = 0.050   # 50 m
    h2_km     = 10.0    # 10 km aircraft
    d_km      = np.linspace(1.0, 50.0, 800)
    d_m       = np.sqrt(10**2 + d_km**2) * 1000.0
    f_vec     = np.full_like(d_m, f_MHz, dtype=float)
    h1_v      = np.full_like(d_km, h1_km, dtype=float)
    h2_v      = np.full_like(d_km, h2_km, dtype=float)
    indoor    = np.zeros_like(d_km, dtype=bool)

    rng = np.random.RandomState(42)
    model = PropagationP528(rng)

    Lb = model.get_loss(d_m, f_vec, h1_v, h2_v, indoor,
                        polarization=POL_H, time_percentage=80.0)

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
