import typing
from dataclasses import field, dataclass
import numpy as np

from sharc.parameters.parameters_base import ParametersBase

@dataclass
class ParametersImtTopology(ParametersBase):
    type: typing.Literal[
        "MACROCELL", "HOTSPOT", "INDOOR", "SINGLE_BS", "NTN"
    ] = "MACROCELL"
    __AVAILABLE_TYPES = [
        "MACROCELL", "HOTSPOT", "INDOOR", "SINGLE_BS", "NTN"
    ]

    @dataclass
    class ParametersImtTopologyMacrocell(ParametersBase):
        intersite_distance: int = None
        wrap_around: bool = False
        num_clusters: int = 1

        def validate(self, ctx):
            if not isinstance(self.intersite_distance, int) and not isinstance(self.intersite_distance, float):
                raise ValueError(f"{ctx}.intersite_distance should be a number")

            if self.num_clusters not in [1, 7]:
                raise ValueError(f"{ctx}.num_clusters should be either 1 or 7")

    @dataclass
    class ParametersImtTopologyHotspot(ParametersBase):
        intersite_distance: int = None
        # Enable wrap around
        wrap_around: bool = False
        # Number of clusters topology
        num_clusters: int = 1
        # Number of hotspots per macro cell (sector)
        num_hotspots_per_cell: float =  1.0
        # Maximum 2D distance between hotspot and UE [m]
        # This is the hotspot radius
        max_dist_hotspot_ue: float = 100.0
        # Minimum 2D distance between macro cell base station and hotspot [m]
        min_dist_bs_hotspot: float = 0.0

        def validate(self, ctx):
            if not isinstance(self.intersite_distance, int) or not isinstance(self.intersite_distance, float):
                raise ValueError(f"{ctx}.intersite_distance should be a number")

            if self.num_clusters not in [1, 7]:
                raise ValueError(f"{ctx}.num_clusters should be either 1 or 7")

            if not isinstance(self.num_hotspots_per_cell, int) or self.num_hotspots_per_cell < 0:
                raise ValueError("num_hotspots_per_cell must be non-negative")

            if not isinstance(self.max_dist_hotspot_ue, float) or not isinstance(self.max_dist_hotspot_ue, int) or self.max_dist_hotspot_ue < 0:
                raise ValueError("max_dist_hotspot_ue must be non-negative")

            if not isinstance(self.min_dist_bs_hotspot, float) or not isinstance(self.min_dist_bs_hotspot, int) or self.min_dist_bs_hotspot < 0:
                raise ValueError("min_dist_bs_hotspot must be non-negative")

    @dataclass
    class ParametersImtTopologyIndoor(ParametersBase):
        # Basic path loss model for indoor topology. Possible values:
        #       "FSPL" (free-space path loss),
        #       "INH_OFFICE" (3GPP Indoor Hotspot - Office)
        basic_path_loss: typing.Literal["INH_OFFICE", "FSPL"] = "INH_OFFICE"
        # Number of rows of buildings in the simulation scenario
        n_rows: int = 3
        # Number of colums of buildings in the simulation scenario
        n_colums: int = 2
        # Number of buildings containing IMT stations. Options:
        # 'ALL': all buildings contain IMT stations.
        # An integer representing the number of buildings.
        num_imt_buildings: typing.Union[typing.Literal["ALL"], int] = "ALL"
        # Street width (building separation) [m]
        street_width: int = 30
        # Intersite distance [m]
        intersite_distance: int = 40
        # Number of cells per floor
        num_cells: int = 3
        # Number of floors per building
        num_floors: int = 1
        # Percentage of indoor UE's [0, 1]
        ue_indoor_percent: int = .95
        # Building class: "TRADITIONAL" or "THERMALLY_EFFICIENT"
        building_class: typing.Literal[
            "TRADITIONAL", "THERMALLY_EFFICIENT"
        ] = "TRADITIONAL"

    @dataclass
    class ParametersImtTopologySingleBS(ParametersBase):
        intersite_distance: int = None
        cell_radius: int = None
        num_clusters: int = 1

        def load_subparameters(self, ctx: str, params: dict, quiet=True):
            super().load_subparameters(ctx, params, quiet)

            if self.intersite_distance is not None and self.cell_radius is not None:
                raise ValueError(f"{ctx}.intersite_distance and {ctx}.cell_radius should not be set at the same time")

            if self.intersite_distance is not None:
                self.cell_radius = self.intersite_distance * 2 / 3
            if self.cell_radius is not None:
                self.intersite_distance = self.cell_radius * 3 / 2

        def validate(self, ctx):
            if None in [self.intersite_distance, self.cell_radius]:
                raise ValueError(f"{ctx}.intersite_distance and cell_radius should be set.\
                                 One of them through the parameters, the other inferred")

            if self.num_clusters not in [1, 2]:
                raise ValueError(f"{ctx}.num_clusters should either be 1 or 2")



    @dataclass
    class ParametersImtTopologyNTN(ParametersBase):
        # NTN Airborne Platform height (m)
        bs_height: float = None

        # NTN cell radius in network topology [m]
        cell_radius: float = 90000

        # NTN Intersite Distance (m). Intersite distance = Cell Radius * sqrt(3)
        # @important: for NTN, intersite distance means something different than normally,
        # since the BS's are placed at center of hexagons
        intersite_distance: float = None

        # BS azimuth
        # TODO: Put this elsewhere (in a bs.geometry for example) if needed by another model
        bs_azimuth: float = 45
        # BS elevation
        bs_elevation: float = 90

        # Number of sectors
        num_sectors: int = 7

        # TODO: implement the below parameters in the simulator. They are currently not used
        # Backoff Power [Layer 2] [dB]. Allowed: 7 sector topology - Layer 2
        bs_backoff_power: int = 3

        # NTN Antenna configuration
        bs_n_rows_layer1: int = 2
        bs_n_columns_layer1: int = 2
        bs_n_rows_layer2: int = 4
        bs_n_columns_layer2: int = 2

        def load_subparameters(self, ctx: str, params: dict, quiet=True):
            super().load_subparameters(ctx, params, quiet)

            if self.cell_radius is not None and self.intersite_distance is not None:
                raise ValueError(f"You cannot set both {ctx}.intersite_distance and {ctx}.cell_radius.")

            if self.cell_radius is not None:
                self.intersite_distance = self.cell_radius * np.sqrt(3)

            if self.intersite_distance is not None:
                self.cell_radius = self.intersite_distance / np.sqrt(3)

        def set_external_parameters(self, *, bs_height: float):
            """
                This method is used to "propagate" parameters from external context
                to the values required by ntn topology. It's not ideal, but it's done
                this way until we decide on a better way to model context.
            """
            self.bs_height = bs_height

        def validate(self, ctx: str):
            # Now do the sanity check for some parameters
            if self.num_sectors not in [1, 7, 19]:
                raise ValueError(
                    f"ParametersNTN: Invalid number of sectors {self.num_sectors}",
                )

            if self.bs_height <= 0:
                raise ValueError(
                    f"ParametersNTN: bs_height must be greater than 0, but is {self.bs_height}",
                )

            if self.cell_radius <= 0:
                raise ValueError(
                    f"ParametersNTN: cell_radius must be greater than 0, but is {self.cell_radius}",
                )

            if self.intersite_distance <= 0:
                raise ValueError(
                    f"ParametersNTN: intersite_distance must be greater than 0, but is {self.intersite_distance}",
                )

            if not isinstance(self.bs_conducted_power, int) or self.bs_conducted_power <= 0:
                raise ValueError(
                    f"ParametersNTN: bs_conducted_power must be a positive integer, but is {self.bs_conducted_power}",
                )

            if not isinstance(self.bs_backoff_power, int) or self.bs_backoff_power < 0:
                raise ValueError(
                    f"ParametersNTN: bs_backoff_power must be a non-negative integer, but is {self.bs_backoff_power}",
                )

            if not np.all((0 <= self.bs_azimuth) & (self.bs_azimuth <= 360)):
                raise ValueError(
                    "ParametersNTN: bs_azimuth values must be between 0 and 360 degrees",
                )

            if not np.all((0 <= self.bs_elevation) & (self.bs_elevation <= 90)):
                raise ValueError(
                    "ParametersNTN: bs_elevation values must be between 0 and 90 degrees",
                )



    macrocell: ParametersImtTopologyMacrocell = field(default_factory=ParametersImtTopologyMacrocell)
    hotspot: ParametersImtTopologyHotspot = field(default_factory=ParametersImtTopologyHotspot)
    indoor: ParametersImtTopologyIndoor = field(default_factory=ParametersImtTopologyIndoor)
    single_bs: ParametersImtTopologySingleBS = field(default_factory=ParametersImtTopologySingleBS)
    ntn: ParametersImtTopologyNTN = field(default_factory=ParametersImtTopologyNTN)

    def validate(self, ctx):
        match self.type:
            case "MACROCELL":
                self.macrocell.validate(ctx)
            case "HOTSPOT":
                self.hotspot.validate(ctx)
            case "INDOOR":
                self.indoor.validate(ctx)
            case "SINGLE_BS":
                self.single_bs.validate(ctx)
            case "NTN":
                self.ntn.validate(ctx)
            case _:
                raise NotImplementedError(f"{ctx}.type == '{self.type}' may not be implemented")
