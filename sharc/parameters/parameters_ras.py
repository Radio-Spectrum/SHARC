# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.support.sharc_utils import is_float
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersRas(ParametersBase):
    """
    Simulation parameters for Radio Astronomy Service
    """

    section_name: str = "RAS"
    # x-y coordinates [m]
    x: float = 81000.0
    y: float = 0.0
    # antenna height [m]
    height: float = 15.0
    # Elevation angle [deg]
    elevation: float = 45.0
    # Azimuth angle [deg]
    azimuth: float = -90.0
    # center frequency [MHz]
    frequency: float = 43000.0
    # bandwidth [MHz]
    bandwidth: float = 1000.0
    # Antenna noise temperature [K]
    antenna_noise_temperature: float = 25.0
    # Receiver noise temperature [K]
    receiver_noise_temperature: float = 65.0
    # adjacent channel selectivity (dB)
    adjacent_ch_selectivity: float = 20.0
    # Antenna efficiency
    antenna_efficiency: float = 1.0
    # Antenna pattern of the FSS Earth station
    # Possible values: "ITU-R SA.509", "OMNI"
    antenna_pattern: str = "ITU-R SA.509"
    # Antenna gain for "OMNI" pattern
    antenna_gain: float = 0.0
    # Diameter of antenna [m]
    diameter: float = 15.0
    # Channel parameters
    # channel model, possible values are "FSPL" (free-space path loss),
    #                                    "TerrestrialSimple" (FSPL + clutter loss)
    #                                    "P452"
    channel_model: str = "P452"

    # P452 parameters
    # Total air pressure in hPa
    atmospheric_pressure: float = 935.0
    # Temperature in Kelvin
    air_temperature: float = 300.0
    # Sea-level surface refractivity (use the map)
    N0: float = 352.58
    # Average radio-refractive (use the map)
    delta_N: float = 43.127
    # Percentage p. Float (0 to 100) or RANDOM
    percentage_p: str = "RANDOM"
    # Distance over land from the transmit and receive antennas to the coast (km)
    Dct: float = 70.0
    # Distance over land from the transmit and receive antennas to the coast (km)
    Dcr: float = 70.0
    # Effective height of interfering antenna (m)
    Hte: float = 20.0
    # Effective height of interfered-with antenna (m)
    Hre: float = 3.0
    # Latitude of transmitter
    tx_lat: float = -23.55028
    # Latitude of receiver
    rx_lat: float = -23.17889
    # Antenna polarization
    polarization: str = "horizontal"
    # Determine whether clutter loss following ITU-R P.2108 is added (TRUE/FALSE)
    clutter_loss: bool = True

    def load_parameters_from_file(self, config_file: str):
        """Load the parameters from file an run a sanity check

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
        if self.channel_model.upper() not in ["FSPL", "TERRESTRIALSIMPLE", "P452"]:
            raise ValueError(f'ParametersRas: \
                             Invalid value for parameter channel_model - {self.channel_model}. \
                             Allowed values are: "FSPL", "TerrestrialSimple", "P452"')
        if self.antenna_pattern.upper() not in ["ITU-R SA.509", "OMNI"]:
            raise ValueError(f'ParametersRas: \
                             Invalid value for parameter antenna_pattern - {self.antenna_pattern}. \
                             Allowed values are: "ITU-R SA.509", "OMNI"')
        if self.polarization.lower() not in ["horizontal", "vertical"]:
            raise ValueError(f'ParametersRas: \
                             Invalid value for parameter polarization - {self.polarization}. \
                             Allowed values are: "horizontal", "vertical"')
        if is_float(self.percentage_p):
            self.percentage_p = float(self.percentage_p)
        elif self.percentage_p.upper() != "RANDOM":
            raise ValueError(f"""ParametersRas:
                            Invalid value for parameter percentage_p - {self.percentage_p}.
                            Allowed values are \"RANDOM\" or a percentage ]0,1]""")
