# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersHaps(ParametersBase):
    """Dataclass containing the IMT system parameters
    """
    # HAPS center frequency [MHz]
    frequency: float = 27250
    # HAPS bandwidth [MHz]
    bandwidth: float = 200
    # HAPS peak antenna gain [dBi]
    antenna_gain: float = 28.1
    # EIRP spectral density [dBW/MHz]
    eirp_density: float = 4.4
    # tx antenna power density [dBW/MHz]
    tx_power_density: float = eirp_density - antenna_gain - 60
    # HAPS altitude [m] and latitude [deg]
    altitude: float = 20000
    lat_deg: float = 0
    # Elevation angle [deg]
    elevation: float = 270
    # Azimuth angle [deg]
    azimuth: float = 0
    # Antenna pattern of the HAPS (airbone) station
    # Possible values: "ITU-R F.1891", "OMNI"
    antenna_pattern: str = "ITU-R F.1891"
    # IMT parameters relevant to the HAPS system
    #    altitude of IMT system (in meters)
    #    latitude of IMT system (in degrees)
    #    difference between longitudes of IMT and satellite system
    #      (positive if space-station is to the East of earth-station)
    imt_altitude: float = 0
    imt_lat_deg: float = 0
    imt_long_diff_deg: float = 0
    # Season of the year for the channel model
    season: str = "SUMMER"
    # Adjacent channel selectivity [dB]
    acs: float = 30
    # Channel parameters
    # channel model, possible values are "FSPL" (free-space path loss),
    #                                    "SatelliteSimple" (FSPL + 4 + clutter loss)
    #                                    "P619"
    channel_model: str = "P619"
    # Near side-lobe level (dB) relative to the peak gain required by the system
    # design, and has a maximum value of −25 dB
    antenna_l_n: float = -25

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
        if self.antenna_pattern not in ["ITU-R F.1891", "OMNI"]:
            raise ValueError(f"ParametersHaps: \
                             Invalid value for parameter {self.antenna_pattern}. \
                             Allowed values are \"ITU-R F.1891\", \"OMNI\".")
        if self.channel_model.upper() not in ["FSPL", "SatelliteSimple", "P619"]:
            raise ValueError(f"ParametersHaps: \
                             Invalid value for paramter channel_model = {self.channel_model}. \
                             Possible values are \"FSPL\", \"SatelliteSimple\", \"P619\".")
        if self.season.upper() not in ["SUMMER", "WINTER"]:
            raise ValueError(f"ParametersHaps: \
                             Invalid value for parameter season - {self.season}. \
                             Possible values are \"SUMMER\", \"WINTER\".")
