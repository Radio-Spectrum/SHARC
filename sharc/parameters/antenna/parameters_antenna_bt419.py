from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaBT419(ParametersBase):
    """Dataclass containing the Antenna Pattern BT.419 parameters for the simulator.
    """
    antenna_gain: float | None = None
    bs_system_band: str | None = None

    def validate(self, ctx: str):
        """
        Validate the parameters for the BT.419 antenna configuration.
        """
        if self.antenna_gain is None:
            raise ValueError(f"{ctx}.antenna_gain must be set for BT.419 antenna configuration.")

        if self.bs_system_band not in ["BAND_I", "BAND_II", "BAND_III", "BAND_IV", "BAND_V"]:
            raise ValueError(f"Band {self.bs_system_band} is not supported in BT.419 antenna discrimination pattern")
            if self.bs_system_band not in ["BAND_IV", "BAND_V"]:
                raise NotImplementedError(f"Band {self.bs_system_band} is not implemented in BT.419 antenna discrimination pattern, only Bands IV and V are implemented for now.")