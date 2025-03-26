# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersAntennaS1528(ParametersBase):
    """Dataclass containing the Antenna Pattern S.1528 parameters for the simulator.
    """
    section_name: str = "S1528"
    # satellite center frequency [MHz]
    frequency: float = None
    # channel bandwidth - used for Taylor antenna
    bandwidth: float = None
    # Peak antenna gain [dBi]
    antenna_gain: float = None
    # Antenna pattern from ITU-R S.1528
    # Possible values: "ITU-R-S.1528-Section1.2", "ITU-R-S.1528-LEO", "ITU-R-S.1528-Taylor"
    antenna_pattern: str = "ITU-R-S.1528-LEO"
    # The required near-in-side-lobe level (dB) relative to peak gain
    # according to ITU-R S.672-4
    antenna_l_s: float = -20.0
    # 3 dB beamwidth angle (3 dB below maximum gain) [degrees]
    antenna_3_dB_bw: float = 0.65

    # The following parameters are used for S.1528-Taylor antenna pattern

    # SLR is the side-lobe ratio of the pattern (dB), the difference in gain between the maximum
    # gain and the gain at the peak of the first side lobe.
    slr: float = 20.0

    # half-radial axis distance of the illuminated beam (degrees) (subtended at the satellite)
    a_deg: float = 0.4

    # half-transverse axis distance of the illuminated beam (degrees) (subtended at the satellite)
    b_deg: float = 0.4

    # Number of secondary lobes considered in the diagram (coincide with the roots of the Bessel function)
    n_side_lobes: int = 4

    # Radial (l_r) and transverse (l_t) sizes of the effective radiating area of the satellite transmitt antenna (m)
    l_r: float = 1.6
    l_t: float = 1.6

    # beam roll-off (difference between the maximum gain and the gain at the edge of the illuminated beam)
    # Possible values are 0, 3, 5 and 7. The value 0 (zero) means that the first J1 root of the bessel function 
    # sits at the edge of the beam
    roll_off: int = 7

    def load_parameters_from_file(self, config_file: str):
        """Load the parameters from file an run a sanity check.

        Parameters
        ----------
        file_name : str
            the path to the configuration file

        Raises
        ------
        ValueError
            if a parameter is not valid
        """
        super().load_parameters_from_file(config_file)

        self.validate("antenna_s1528")

    def set_external_parameters(self, **kwargs):
        """
        This method is used to "propagate" parameters from external context
        to the values required by antenna S1528.
        """
        attr_list = [a for a in dir(self) if not a.startswith('__')]

        for k, v in kwargs.items():
            if k in attr_list:
                setattr(self, k, v)
            else:
                raise ValueError(f"Parameter {k} is not a valid attribute of {self.__class__.__name__}")

        self.validate("S.1528")

    def validate(self, ctx: str):
        # Now do the sanity check for some parameters

        if None in [self.frequency, self.bandwidth, self.antenna_gain]:
            raise ValueError(
                f"AntennaS1528Taylor: [frequency, bandwidth, antenna_gain] = {[self.frequency, self.bandwidth, self.antenna_gain]}.\
                They need to all be set!")

        if self.antenna_pattern not in ["ITU-R-S.1528-Section1.2", "ITU-R-S.1528-LEO", "ITU-R-S.1528-Taylor"]:
            raise ValueError(f"ParametersAntennaS1528: \
                             invalid value for parameter antenna_pattern - {self.antenna_pattern}. \
                             Possible values \
                             are \"ITU-R-S.1528-Section1.2\", \"ITU-R-S.1528-LEO\", \"ITU-R-S.1528-Taylor\"")

        if int(self.roll_off) not in [0, 3, 5, 7]:
            raise ValueError(
                f"AntennaS1528Taylor: Invalid value for roll_off factor {self.roll_off}")
