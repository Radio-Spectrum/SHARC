# -*- coding: utf-8 -*-
"""Parameters definitions for IMT systems
"""
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase

@dataclass
class ParametersIndoor(ParametersBase):
    """
    Simulation parameters for indoor network topology.
    """
    section_name: str = "INDOOR"
    
    # Basic path loss model for indoor topology.
    # Possible values: "FSPL" (free-space path loss), "INH_OFFICE" (3GPP Indoor Hotspot - Office)
    basic_path_loss: str = "INH_OFFICE"
    
    # Number of rows of buildings in the simulation scenario
    n_rows: int = 3
    
    # Number of columns of buildings in the simulation scenario
    n_colums: int = 2
    
    # Number of buildings containing IMT stations. Options: 'ALL' (all buildings contain IMT stations),
    # or a specific number of buildings.
    num_imt_buildings: str = "ALL"
    
    # Street width (building separation) [m]
    street_width: float = 30.0
    
    # Intersite distance [m]
    intersite_distance: float = 40.0
    
    # Number of cells per floor
    num_cells: int = 3
    
    # Number of floors per building
    num_floors: int = 1
    
    # Percentage of indoor UEs [0, 1]
    ue_indoor_percent: float = .95
    
    # Building class. Options: "TRADITIONAL" or "THERMALLY_EFFICIENT"
    building_class: str = "TRADITIONAL"
    
    
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

        # Now do the sanity check for some parameters
        if self.basic_path_loss.upper() not in ["FSPL", "INH_OFFICE"]:
            raise ValueError(f"ParamtersIndoor: Invalid topology name {self.basic_path_loss}")
        
        if self.num_imt_buildings.upper() != "ALL":
            if self.num_imt_buildings.isnumeric():
                self.num_imt_buildings = int(self.num_imt_buildings)
            else:
                raise ValueError(f"ParamtersIndoor: Invalid topology name {self.num_imt_buildings}")
     
        if self.building_class.upper() not in ["TRADITIONAL" , "THERMALLY_EFFICIENT"]:
            raise ValueError(f"ParametersIndoor: Inavlid Spectral Mask Name {self.building_class}")
        
        if not (0 <= self.ue_indoor_percent or  self.ue_indoor_percent <= 1):
            raise ValueError(f"ParametersIndoor: ue_indoor_percent must be between 0 and 1, but is {self.ue_indoor_percent}")
        
        # Ensure the number of rows is greater than zero
        if self.n_rows <= 0:
            raise ValueError(f"ParametersIndoor: n_rows must be greater than 0, but is {self.n_rows}")

        # Ensure the number of columns is greater than zero
        if self.n_colums <= 0:
            raise ValueError(f"ParametersIndoor: n_colums must be greater than 0, but is {self.n_colums}")
