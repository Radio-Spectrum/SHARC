
"""Antenna factory module for creating antenna instances based on parameters."""
from sharc.parameters.parameters_antenna import ParametersAntenna

from sharc.antenna.antenna_mss_adjacent import AntennaMSSAdjacent
from sharc.antenna.antenna_omni import AntennaOmni
from sharc.antenna.antenna_f699 import AntennaF699
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.antenna.antenna_rra7_3 import AntennaReg_RR_A7_3
from sharc.antenna.antenna_s580 import AntennaS580
from sharc.antenna.antenna_s1528 import AntennaS1528
from sharc.antenna.antenna_s1855 import AntennaS1855
from sharc.antenna.antenna_s672 import AntennaS672
from sharc.antenna.antenna_s1528 import AntennaS1528, AntennaS1528Leo, AntennaS1528Taylor
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt


class AntennaFactory():
    """Factory class for creating antenna instances based on pattern parameters."""

    @staticmethod
    def create_antenna(
        antenna_params: ParametersAntenna,
        azimuth: float,
        elevation: float,
    ):
        """Create and return an antenna instance based on the provided parameters, azimuth, and elevation."""
        match antenna_params.pattern:
            case "OMNI":
                return AntennaOmni(antenna_params.gain)
            case "ITU-R F.699":
                return AntennaF699(antenna_params.itu_r_f_699)
            case "ITU-R-S.1528-Taylor":
                return AntennaS1528Taylor(antenna_params.itu_r_s_1528)
            case "ITU-R-S.1528-LEO":
                return AntennaS1528Leo(antenna_params.itu_r_s_1528)
            case "ITU-R-S.1528-Section1.2":
                return AntennaS1528(antenna_params.itu_r_s_1528)
            case "ITU-R S.672":
                return AntennaS672(antenna_params.itu_r_s_672)
            case "ITU-R S.465":
                return AntennaS465(antenna_params.itu_r_s_465)
            case "ITU-R S.580":
                return AntennaS580(antenna_params.itu_r_s_580)
            case "MODIFIED ITU-R S.465":
                return AntennaS465(antenna_params.itu_r_s_465_modified)
            case "ITU-R S.1855":
                return AntennaS1855(antenna_params.itu_r_s_1855)
            case "ITU-R Reg. RR. Appendice 7 Annex 3":
                return AntennaReg_RR_A7_3(antenna_params.itu_reg_rr_a7_3)
            case "MSS Adjacent":
                return AntennaMSSAdjacent(
                    antenna_params.mss_adjacent.frequency)
            case "ARRAY":
                return AntennaBeamformingImt(
                    antenna_params.array.get_antenna_parameters(),
                    azimuth,
                    elevation
                )
            case _:
                raise ValueError(
                    f"Antenna factory does not support pattern {
                        antenna_params.pattern}")
