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

from multipledispatch import dispatch
import numpy as np

from sharc.propagation.propagation import Propagation
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.parameters.parameters import Parameters
from sharc.station_manager import StationManager
from sharc.parameters.parameters_p528 import ParametersP528


# Se você tiver utilitários comuns no seu projeto (constantes etc.), importe-os aqui
AEFF_KM = 9257.0   # effective Earth radius (4/3 Earth) usado como aproximação inicial
A0_KM   = 6371.0   # mean Earth radius


class PropagationP528(Propagation):
    """
    Starter implementation of ITU-R P.528 (air-ground / aeronautical links)
    Public method:
        get_loss: Calculates path loss (LOS or trans-horizon) per Annex-2 flow.
    """

    def __init__(self, random_number_gen: np.random.RandomState):
        super().__init__(random_number_gen)
        self.free_space = PropagationFreeSpace(self.random_number_gen)

        # Parâmetros "médios" de solo (P.528 §2): εr≈15, σ≈0.005 S/m.
        # Aqui mantemos apenas placeholders para a reflexão; ajuste conforme necessário.
        self.eps_r = 15.0
        self.sigma = 0.005

        # Flags simples
        self.include_variability = False  # TODO: implementar Y(p) (§§12–13 da P.528)
        self.include_atm_abs = False      # TODO: implementar Aa via P.676/P.835

    # ---------------------------
    # Helpers (estrutura P.528)
    # ---------------------------

    @staticmethod
    def _wavelength_km(f_MHz: float) -> float:
        # λ[km] = 0.2997925 / f[MHz]
        return 0.2997925 / f_MHz

    @staticmethod
    def _terminal_horizon_distance_km(h_km: float, aeff_km: float = AEFF_KM) -> float:
        """
        d_r ≈ sqrt(2 * a_eff * h) — aproximação padrão 4/3 Earth para horizonte liso.
        (P.528 Step 3-1 precisa de dr1, dr2; aqui usamos aproximação sem ray-tracing.)
        """
        h_km = max(h_km, 0.0)
        return np.sqrt(2.0 * aeff_km * h_km)

    @staticmethod
    def _max_los_distance_km(h1_km: float, h2_km: float) -> float:
        return (PropagationP528._terminal_horizon_distance_km(h1_km) +
                PropagationP528._terminal_horizon_distance_km(h2_km))

    @staticmethod
    def _two_ray_los_delta_r_km(h1_km: float, h2_km: float, d_km: float) -> float:
        """
        Diferença de caminho LOS de 2 raios com superfície plana (aprox. simples).
        Δr ≈ (2 * h1 * h2) / d    (versão plana; boa como starter)
        """
        d_km = max(d_km, 1e-6)
        return 2.0 * h1_km * h2_km / d_km

    def _los_loss_excess_dB(self, f_MHz: float, h1_km: float, h2_km: float, d_km: float) -> float:
        """
        Excesso de perda relativo ao espaço livre para LOS com 2-ray “smoothed”.
        Aplica limitação para ângulos muito rasantes (ψ > ψ_limit) conforme espírito do §8.
        Aqui: modelo leve, estável, sem oscilação severa.
        """
        lam_km = self._wavelength_km(f_MHz)
        delta_r = self._two_ray_los_delta_r_km(h1_km, h2_km, d_km)

        # Fase relativa (φ = 2π Δr / λ)
        phi = 2.0 * np.pi * (delta_r / lam_km)

        # Coef. de reflexão efetivo (magnitude reduzida para suavizar lóbulos)
        # Para vertical/horizontal verdadeiros, use Fresnel com εr, σ, ψ — TODO.
        R_eff = 0.3

        # Ganho/atenuação relativa: |1 + R e^{jφ}|^2 limitado (evita >0 dB)
        W = (1.0 + R_eff * np.cos(phi))**2 + (R_eff * np.sin(phi))**2
        W = min(W, 1.0)
        return 10.0 * np.log10(W)

    def _smooth_earth_diffraction_line(self, f_MHz: float, dML_km: float):
        """
        Constrói a linha de difração “suavizada” (Step 3-3) por dois pontos (d3,d4).
        Aqui usamos um modelo de difração simples baseado em knife-edge efetivo.
        Você pode substituir por rotinas ITU “smooth Earth diffraction” depois.
        """
        # P.528 sugere: d3 = dML + 0.5*(ae^2/f)^(1/3), d4 = dML + 1.5*(...) (Eqs. 8–9)
        incr = (AEFF_KM**2 / f_MHz)**(1.0/3.0)
        d3 = dML_km + 0.5 * incr
        d4 = dML_km + 1.5 * incr

        def A_diff_ke(d_km: float) -> float:
            # Difração tipo knife-edge “leve”: A_d ≈ 6.9 + 20 log10(√((v-0.1)^2 + 1) + v - 0.1)
            # com v ~ (d - dML)/dF — escala empírica para suavizar transição.
            # Isto é apenas um placeholder estável (não oficial ITU).
            dF = max(incr, 1e-3)
            v = max((d_km - dML_km) / dF, 0.0)
            return 6.9 + 20.0 * np.log10(np.hypot(v - 0.1, 1.0) + v - 0.1)

        Ad3 = A_diff_ke(d3)
        Ad4 = A_diff_ke(d4)
        Md = (Ad4 - Ad3) / (d4 - d3)     # Eq. (10)
        Ad0 = Ad4 - Md * d4              # Eq. (11)
        AdML = Md * dML_km + Ad0         # Eq. (12)
        dd   = -Ad0 / Md                 # Eq. (13)

        return (Md, Ad0, AdML, dd, d3, d4)

    def _troposcatter_loss_dB(self, f_MHz: float, d_km: float) -> float:
        """
        Troposcatter starter (placeholder suave, monótono).
        Substitua por §11 completo (ângulo de espalhamento, volume comum, etc.).
        """
        # Atenuação cresce ~ linearmente (dB) com distância além de dML; inclina 0.05–0.15 dB/km
        slope = 0.08
        base = 20.0  # P.528 pede que As >= 20 dB válido; usamos mínimo 20 dB
        return base + slope * max(d_km, 0.0)

    def _variability_Yp_dB(self, p_time: float, d_km: float, f_MHz: float) -> float:
        """
        Variabilidade de longo prazo Y(p) (§§12–13).
        TODO: implementar curva ITU. Aqui retornamos 0 dB por padrão.
        """
        return 0.0

    # ---------------------------
    # API compatível com P619
    # ---------------------------

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
        distance = station_a.get_3d_distance_to(station_b)  # [m]
        f_arr = frequency * np.ones(distance.shape)

        # Alturas geométricas [km]
        # (Para aeronave, use height do StationManager; para solo, idem.)
        hA_km = (station_a.height / 1e3) * np.ones(distance.shape)
        hB_km = (station_b.height / 1e3) * np.ones(distance.shape)

        # Indoor (não usado aqui; P.528 não cobre clutter/indoor — mantenha 0)
        indoor = np.zeros_like(distance, dtype=bool)

        return self.get_loss(distance=distance,
                             frequency=f_arr,
                             h1_km=hA_km,
                             h2_km=hB_km,
                             indoor_stations=indoor)

    @dispatch(np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    def get_loss(self,
                 distance: np.ndarray,      # [m]
                 frequency: np.ndarray,     # [MHz]
                 h1_km: np.ndarray,
                 h2_km: np.ndarray,
                 indoor_stations: np.ndarray) -> np.ndarray:
        """
        Kernel escalar/vetorial. Implementa o fluxo do Annex-2:
        - Determina LOS vs Trans-horizonte
        - LOS: Lfs + (excesso 2-ray suavizado) + Aa + Y(p)
        - Trans: Lfs + Aa + A_T(d) (min(diffraction, troposcatter)) + Y(p)
        Retorna Lb [dB].
        """
        # Espaço livre
        Lfs = self.free_space.get_free_space_loss(distance=distance, frequency=frequency)

        # Comprimento de caminho aproximado para Aa (TODO: trocar por ray-tracing §5/P.676)
        # Aqui mantemos Aa = 0 dB (placeholder coerente).
        Aa = np.zeros_like(Lfs)

        # Distâncias em km
        d_km = np.maximum(distance / 1000.0, 1e-6)
        f_MHz = frequency

        # Parâmetros LOS/trans
        dML = self._max_los_distance_km(h1_km, h2_km)  # km
        is_los = d_km < dML

        # --- LOS branch ---
        A_los_excess = np.zeros_like(Lfs)
        los_mask = is_los
        if np.any(los_mask):
            # Excesso LOS (2-ray suavizado)
            A_los_excess[los_mask] = np.vectorize(self._los_loss_excess_dB)(
                float(f_MHz.flat[0]),
                float(h1_km.flat[0]),
                float(h2_km.flat[0]),
                d_km[los_mask]
            )

        # --- Trans-horizonte branch ---
        A_T = np.zeros_like(Lfs)
        trans_mask = ~is_los
        if np.any(trans_mask):
            # Linha de difração “smooth Earth” (Step 3-3)
            Md, Ad0, AdML, dd, d3, d4 = self._smooth_earth_diffraction_line(
                float(f_MHz.flat[0]), float(dML.flat[0])
            )
            # Difração linear: Ad = Md * d + Ad0
            A_diff = Md * d_km + Ad0

            # Troposcatter (placeholder)
            A_scatt = np.vectorize(self._troposcatter_loss_dB)(
                float(f_MHz.flat[0]), d_km
            )

            # Seleção/consistência (Step 3-7/22): min(Ad, As)
            A_T[trans_mask] = np.minimum(A_diff[trans_mask], A_scatt[trans_mask])

        # Variabilidade (desligada por padrão)
        Yp = 0.0  # TODO: self._variability_Yp_dB(p_time, ...)

        # Lb total
        Lb = Lfs + Aa + np.where(is_los, A_los_excess, A_T) + Yp
        return Lb
    
    
