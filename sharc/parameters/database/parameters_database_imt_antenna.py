# -*- coding: utf-8 -*-
"""IMT base-station antenna parameters read from the base-station database."""
from dataclasses import dataclass

import numpy as np

# Database columns, one per field of AntennaParamsFromFile.
ANTENNA_COLUMNS = (
    "n_rows", "n_columns", "beamforming_gain", "element_max_g",
    "tx_power", "sub_num_rows", "downtilt",
)


@dataclass
class AntennaParamsFromFile:
    """Array antenna and power of one base station, from a database row."""

    # Number of rows and columns of the array.
    n_rows: int
    n_columns: int

    # Beamforming gain actually achieved by the array [dB]. It may be lower
    # than the theoretical 10*log10(n_rows * n_columns); the difference is
    # taken off the element gain (see __post_init__).
    beamforming_gain: float

    # Maximum element gain [dBi].
    element_max_g: float

    # Total transmit power of the BS [dBm], over all array elements: the
    # equivalent of imt.bs.conducted_power (per element) plus
    # 10*log10(n_rows * n_columns).
    tx_power: float

    # Number of rows of the subarray.
    sub_num_rows: int

    # Mechanical downtilt [deg].
    downtilt: float

    def __post_init__(self):
        """Validate the row and compensate the element gain."""
        self.validate()
        # Element gain compensated by the beamforming efficiency, so that the
        # main-beam gain of the array is element_max_g + beamforming_gain.
        theoretical_bf_gain = 10 * np.log10(self.n_columns * self.n_rows)
        self.element_max_g = self.element_max_g - (theoretical_bf_gain - self.beamforming_gain)

    def validate(self):
        """Check the values of the row."""
        for name in ("n_rows", "n_columns", "sub_num_rows"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
                raise ValueError(f"AntennaParamsFromFile: {name} must be a positive integer, got {value}")
        for name in ("beamforming_gain", "element_max_g", "tx_power", "downtilt"):
            value = getattr(self, name)
            if not isinstance(value, (int, float, np.integer, np.floating)) or not np.isfinite(value):
                raise ValueError(f"AntennaParamsFromFile: {name} must be a finite number, got {value}")
        if self.beamforming_gain < 0:
            raise ValueError("AntennaParamsFromFile: beamforming_gain must not be negative")

    @staticmethod
    def from_row(row) -> "AntennaParamsFromFile":
        """Build from a database row (a mapping with the ANTENNA_COLUMNS keys)."""
        def as_int(value):
            as_float = float(value)
            if not as_float.is_integer():
                raise ValueError(f"AntennaParamsFromFile: expected an integer, got {value}")
            return int(as_float)

        return AntennaParamsFromFile(
            n_rows=as_int(row["n_rows"]),
            n_columns=as_int(row["n_columns"]),
            beamforming_gain=float(row["beamforming_gain"]),
            element_max_g=float(row["element_max_g"]),
            tx_power=float(row["tx_power"]),
            sub_num_rows=as_int(row["sub_num_rows"]),
            downtilt=float(row["downtilt"]),
        )
