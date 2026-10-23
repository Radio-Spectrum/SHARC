"""The protected station (a radio-astronomy dish, or any fixed receiver) and its observation band."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict

K_B = 1.380649e-23


@dataclass(frozen=True)
class RasSite:
    """Location, dish and observation band of the protected station. Heights are above ground level."""
    name: str
    lat_deg: float
    lon_deg: float
    height_m: float = 15.0
    diameter_m: float = 12.0
    efficiency: float = 0.7
    frequency_mhz: float = 4895.0
    bandwidth_mhz: float = 190.0
    elevation_deg: float = 8.1                 # pointing elevation of the dish
    temperature_k: float = 50.0                # system noise temperature used by the protection criterion
    polarization_loss_db: float = 0.0
    shielding_db: float = 0.0

    def with_(self, **changes) -> "RasSite":
        return replace(self, **changes)

    def threshold_dbw(self, i_over_n_db: float = -6.0) -> float:
        """Interference threshold [dBW] in the observation band for a given I/N: N = k T B, I_max = N + I/N."""
        import math
        return 10.0 * math.log10(K_B * self.temperature_k * self.bandwidth_mhz * 1e6) + i_over_n_db


# Sites that were studied with the original tool; any other station is built with RasSite(...) directly.
PRESETS: Dict[str, RasSite] = {
    "ROEN": RasSite("ROEN (Eusebio, CE, Brazil)", -3.87350, -38.42216, height_m=15.0, diameter_m=12.0, efficiency=0.71,
                    frequency_mhz=4895.0, bandwidth_mhz=190.0, elevation_deg=8.1, temperature_k=50.0),
}
