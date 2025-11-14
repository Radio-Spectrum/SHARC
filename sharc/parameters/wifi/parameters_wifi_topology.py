import typing
from dataclasses import dataclass, field

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.wifi.parameters_hotspot import ParametersHotspot
from sharc.parameters.wifi.parameters_indoor import ParametersIndoor


@dataclass
class ParametersWifiTopology(ParametersBase):
    type: typing.Literal["HOTSPOT", "INDOOR"
    ] = "HOTSPOT"

    #macrocell: ParametersMacrocell = field(default_factory=ParametersMacrocell)
    hotspot: ParametersHotspot = field(default_factory=ParametersHotspot)
    indoor: ParametersIndoor = field(default_factory=ParametersIndoor)
    #single_bs: ParametersSingleBS = field(default_factory=ParametersSingleBS)
    #ntn: ParametersNTN = field(default_factory=ParametersNTN)

    def validate(self, ctx):
        match self.type:

            case "HOTSPOT":
                self.hotspot.validate(f"{ctx}.hotspot")
            case "INDOOR":
                self.indoor.validate(f"{ctx}.indoor")
            case _:
                raise NotImplementedError(f"{ctx}.type == '{self.type}' may not be implemented")
