import typing
from dataclasses import field, dataclass

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.imt.parameters_hotspot import ParametersHotspot
from sharc.parameters.imt.parameters_indoor import ParametersIndoor
from sharc.parameters.imt.parameters_macrocell import ParametersMacrocell
from sharc.parameters.imt.parameters_ntn import ParametersNTN
from sharc.parameters.imt.parameters_single_bs import ParametersSingleBS


@dataclass
class ParametersImtTopology(ParametersBase):
    type: typing.Literal[
        "MACROCELL", "HOTSPOT", "INDOOR", "SINGLE_BS", "NTN"
    ] = "MACROCELL"

    macrocell: ParametersMacrocell = field(default_factory=ParametersMacrocell)
    hotspot: ParametersHotspot = field(default_factory=ParametersHotspot)
    indoor: ParametersIndoor = field(default_factory=ParametersIndoor)
    single_bs: ParametersSingleBS = field(default_factory=ParametersSingleBS)
    ntn: ParametersNTN = field(default_factory=ParametersNTN)

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
