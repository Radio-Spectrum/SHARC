from sharc.parameters.parameters_base import ParametersBase
import numpy as np
from dataclasses import dataclass


@dataclass
class ParametersAntennaCosecantSquared(ParametersBase):
    elevation_beamwidth_3db: float = None
    azim_beamwidth_3db: float = None
    antenna_gain: float = None
    theta_end: float = None

    floor_gain_db: float = -55  # dBi

    def validate(self, ctx):
        if None in [
            self.elevation_beamwidth_3db,
            self.azim_beamwidth_3db,
            self.theta_end,
            self.floor_gain_db
        ]:
            raise ValueError(f"You must set all attributes for {ctx}")

        if np.any(np.array([
            self.elevation_beamwidth_3db,
            self.azim_beamwidth_3db,
            self.theta_end,]) <= 0.
        ):
            raise ValueError(
                f"You must set valid values for attributes of {ctx}"
            )

    def theta_null(self, theta_tilt_deg: float):
        return theta_tilt_deg - self.elevation_beamwidth_3db / 0.88

    def theta_start(self, theta_tilt_deg):
        """Theta start could be set manually, but we never
        have parameters, so this is a sane implementation
        according to the document
        """
        return theta_tilt_deg + self.elevation_beamwidth_3db / 2.
