from dataclasses import dataclass, field

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.imt.parameters_grid import ParametersTerrestrialGrid


@dataclass
class ParametersSamplingFromSphericalGrid(ParametersBase):
    """
    Data class for spherical sampling from grid topology parameters.
    """
    num_bs: int = None

    # It is necessary to decouple coverage radius and grid cell radius
    # so that grid point calculation and ue positioning are decoupled
    # This parameter determines max ue position
    max_ue_distance: float = None

    grid: ParametersTerrestrialGrid = field(default_factory=ParametersTerrestrialGrid)

    def validate(self, ctx):
        """
        Validate the topology parameters.

        Ensures that all attributes are set to valid values and types.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        if not isinstance(
                self.num_bs,
                int) or self.num_bs < 0:
            raise ValueError(f"{ctx}.num_bs must be non-negative")

        if self.max_ue_distance <= 0.0:
            raise ValueError(f"{ctx}.max_ue_distance must be positive")

        super().validate(ctx)
