# -*- coding: utf-8 -*-
# Object that loads the parameters for the P.528 propagation model.
"""Parameters definitions for ITU-R P.528 (air-ground / aeronautical)
"""
from dataclasses import dataclass
import typing

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP528(ParametersBase):
    """
    Dataclass containing the P.528 propagation model parameters.

    Notes
    -----
    - P.528 é focada em enlaces ar-superfície (aeronautical/air-ground).
      Alturas dos terminais devem vir dos objetos StationManager.
    - Aqui expomos parâmetros “globais” que afetam reflexão, variabilidade e
      correções opcionais — úteis para o seu PropagationP528.
    """

    # ---- Variabilidade / disponibilidade (tempo e local) ----
    # Percentual de tempo (p%) para o qual a perda NÃO será excedida (ex.: 50, 90, 95)
    reliability_time_pct: float = 50.0
    # Percentual de localização (opcional; manter 50 se não usar distribuição espacial)
    reliability_location_pct: float = 50.0

    # ---- Superfície terrestre para coeficiente de reflexão (≈ P.528 §2) ----
    # Permissividade relativa efetiva do solo
    surface_permittivity: float = 15.0
    # Condutividade elétrica do solo (S/m)
    surface_conductivity_S_per_m: float = 0.005
    # Polarização do campo (“H” ou “V”) – pode ser usada no cálculo de Fresnel
    polarization: typing.Literal["H", "V"] = "H"

    # ---- Terra efetiva (fator-k) ----
    # Raio efetivo da Terra [km]; 4/3 * 6371 ≈ 8494 km (alguns usam ~ 8500–9257 conforme aproximação)
    effective_earth_radius_km: float = 8494.0

    # ---- Atmosfera / clima (para futura integração P.676/P.835) ----
    # Ativar cálculo de absorção atmosférica (P.676) no pipeline (se implementado no modelo)
    include_atmospheric_absorption: bool = False
    # Perfil atmosférico para P.835 (opcional): "SUMMER", "WINTER", "STANDARD", etc.
    atmosphere_profile: str = "STANDARD"

    # ---- Variabilidade de longo prazo (Y(p)) – se implementada no modelo ----
    include_long_term_variability: bool = False

    # ---- Debug / traçados auxiliares ----
    # Usado para exportar pontos chave (d3, d4, dd, etc.) se o modelo suportar
    export_breakpoints: bool = False

    def load_from_paramters(self, param: ParametersBase):
        """
        Load P.528 parameters from a broader system ParametersBase, if available.

        Parameters
        ----------
        param : ParametersBase
            System parameters carrying optional nested configs.
        """
        # Copiar, se existirem no objeto raiz:
        # (Mantém a mesma convenção do P.619: param.param_p528.*)
        if hasattr(param, "param_p528"):
            p = param.param_p528

            self.reliability_time_pct = getattr(p, "reliability_time_pct", self.reliability_time_pct)
            self.reliability_location_pct = getattr(p, "reliability_location_pct", self.reliability_location_pct)

            self.surface_permittivity = getattr(p, "surface_permittivity", self.surface_permittivity)
            self.surface_conductivity_S_per_m = getattr(p, "surface_conductivity_S_per_m", self.surface_conductivity_S_per_m)
            self.polarization = getattr(p, "polarization", self.polarization)

            self.effective_earth_radius_km = getattr(p, "effective_earth_radius_km", self.effective_earth_radius_km)

            self.include_atmospheric_absorption = getattr(p, "include_atmospheric_absorption", self.include_atmospheric_absorption)
            self.atmosphere_profile = getattr(p, "atmosphere_profile", self.atmosphere_profile)

            self.include_long_term_variability = getattr(p, "include_long_term_variability", self.include_long_term_variability)
            self.export_breakpoints = getattr(p, "export_breakpoints", self.export_breakpoints)

        # Sanitização básica
        self._validate()

    def set_external_parameters(self,
                                *,
                                reliability_time_pct: float | None = None,
                                reliability_location_pct: float | None = None,
                                surface_permittivity: float | None = None,
                                surface_conductivity_S_per_m: float | None = None,
                                polarization: typing.Literal["H", "V"] | None = None,
                                effective_earth_radius_km: float | None = None,
                                include_atmospheric_absorption: bool | None = None,
                                atmosphere_profile: str | None = None,
                                include_long_term_variability: bool | None = None,
                                export_breakpoints: bool | None = None):
        """
        Set external parameters for P.528 propagation calculations.
        """
        if reliability_time_pct is not None:
            self.reliability_time_pct = reliability_time_pct
        if reliability_location_pct is not None:
            self.reliability_location_pct = reliability_location_pct

        if surface_permittivity is not None:
            self.surface_permittivity = surface_permittivity
        if surface_conductivity_S_per_m is not None:
            self.surface_conductivity_S_per_m = surface_conductivity_S_per_m
        if polarization is not None:
            self.polarization = polarization

        if effective_earth_radius_km is not None:
            self.effective_earth_radius_km = effective_earth_radius_km

        if include_atmospheric_absorption is not None:
            self.include_atmospheric_absorption = include_atmospheric_absorption
        if atmosphere_profile is not None:
            self.atmosphere_profile = atmosphere_profile

        if include_long_term_variability is not None:
            self.include_long_term_variability = include_long_term_variability
        if export_breakpoints is not None:
            self.export_breakpoints = export_breakpoints

        self._validate()

    # -----------------------
    # Helpers
    # -----------------------
    def _validate(self):
        # time/location percent in (0,100]
        for name, val in [
            ("reliability_time_pct", self.reliability_time_pct),
            ("reliability_location_pct", self.reliability_location_pct),
        ]:
            if not (0.0 < float(val) <= 100.0):
                raise ValueError(f"{self.__class__.__name__}: {name} must be in (0, 100].")

        if self.polarization not in ("H", "V"):
            raise ValueError(f"{self.__class__.__name__}: polarization must be 'H' or 'V'.")

        if self.surface_permittivity <= 0.0:
            raise ValueError(f"{self.__class__.__name__}: surface_permittivity must be > 0.")

        if self.surface_conductivity_S_per_m < 0.0:
            raise ValueError(f"{self.__class__.__name__}: surface_conductivity_S_per_m must be >= 0.")

        if self.effective_earth_radius_km <= 0.0:
            raise ValueError(f"{self.__class__.__name__}: effective_earth_radius_km must be > 0.")
