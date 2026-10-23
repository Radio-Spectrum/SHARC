"""Protection criterion of a radio-astronomy station (Recommendation ITU-R RA.769): the interference threshold."""
from __future__ import annotations

import math
from dataclasses import dataclass

K_B = 1.380649e-23
VLBI = "VLBI"
CONTINUUM = "CONTINUUM"


@dataclass(frozen=True)
class Criterion:
    """Which RA.769 case applies and its percentages.

    ``VLBI``: threshold = p_vlbi % of the noise power kTB. ``CONTINUUM``: p_continuum % of kT sqrt(B / tau), tau being
    the integration time. ``allocation_margin_db`` is subtracted from the threshold (share among several systems)."""
    case: str = VLBI
    p_vlbi_percent: float = 1.0
    p_continuum_percent: float = 1.0
    integration_time_s: float = 2000.0
    allocation_margin_db: float = 0.0

    def threshold_dbw(self, temperature_k: float, bandwidth_mhz: float) -> float:
        """Threshold [dBW] for the system temperature [K] and the observation bandwidth [MHz]."""
        df = float(bandwidth_mhz) * 1e6
        case = self.case.upper()
        if case == VLBI:
            value = 10 * math.log10(self.p_vlbi_percent / 100.0 * K_B * temperature_k * df)
        elif case in (CONTINUUM, "CONTINUO"):
            value = 10 * math.log10(self.p_continuum_percent / 100.0 * K_B * temperature_k
                                    * math.sqrt(df / self.integration_time_s))
        else:
            raise ValueError(f"Criterion.case must be VLBI or CONTINUUM, not {self.case!r}")
        return value - self.allocation_margin_db
