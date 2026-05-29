# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaRA(ParametersBase):
    """
    Parameter holder for the Radio Altimeter antenna (ITU-R M.2319, Eq. A-3.6).

    Attributes
    ----------
    gain_isotropic_dbi : float
        G_RA,dBi — isotropic gain offset, in dBi.
    phi_3db_deg : float
        φ_3dB — 3 dB beamwidth, in degrees.
    inband : bool
        If True, use the in-band quadratic pattern; otherwise use the
        out-of-band pattern.
    """
    gain_isotropic_dbi: float = 5
    phi_3db_deg: float = 20
    inband: bool = True

    def validate(self, ctx: str):
        super().validate(ctx)
        if self.phi_3db_deg <= 0:
            raise ValueError(f"{ctx}.phi_3db_deg must be > 0 (in degrees).")
