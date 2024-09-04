from dataclasses import dataclass
from sharc.parameters.parameters_base import ParametersBase

@dataclass
class ParametersHotspot(ParametersBase):
    """
    Parameters definitions for Hotspot systems.
    """
    section_name: str = "hotspot"
    # Number of hotspots per macro cell (sector).
    num_hotspots_per_cell:int = 1

    # Maximum 2D distance between hotspot and UE [m].
    # This is the hotspot radius.
    max_dist_hotspot_ue:float = 100.0

    # Minimum 2D distance between macro cell base station and hotspot [m].
    min_dist_bs_hotspot:float = 0.0

    def load_parameters_from_file(self, config_file: str):
        """
        Load the parameters from a file and run a sanity check.

        Parameters
        ----------
        config_file : str
            The path to the configuration file.

        Raises
        ------
        ValueError
            If a parameter is not valid.
        """
        super().load_parameters_from_file(config_file)

        # Implement sanity checks for non-negative values
        if self.num_hotspots_per_cell < 0:
            raise ValueError("num_hotspots_per_cell must be non-negative")

        if self.max_dist_hotspot_ue < 0:
            raise ValueError("max_dist_hotspot_ue must be non-negative")

        if self.min_dist_bs_hotspot < 0:
            raise ValueError("min_dist_bs_hotspot must be non-negative")
