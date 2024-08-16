from dataclasses import dataclass
from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersEessPassive(ParametersBase):
    """
    Defines parameters for passive Earth Exploration Satellite Service (EESS) sensors
    and their interaction with other services based on ITU recommendations.
    """

    section_name: str = "EESS_PASSIVE"

    # Sensor center frequency [MHz]
    frequency: float = 23900.0  # Center frequency of the sensor in MHz

    # Sensor bandwidth [MHz]
    bandwidth: float = 200.0  # Bandwidth of the sensor in MHz

    # Off-nadir pointing angle [deg]
    nadir_angle: float = 46.6  # Angle in degrees away from the nadir point

    # Sensor altitude [m]
    altitude: float = (
        828000.0  # Altitude of the sensor above the Earth's surface in meters
    )

    # Antenna pattern of the sensor
    # Possible values: "ITU-R RS.1813", "ITU-R RS.1861 9a", "ITU-R RS.1861 9b", "ITU-R RS.1861 9c", "OMNI"
    antenna_pattern: str = "ITU-R RS.1813"  # Antenna radiation pattern

    # Antenna efficiency for pattern described in ITU-R RS.1813 [0-1]
    antenna_efficiency: float = (
        0.6  # Efficiency factor for the antenna, range from 0 to 1
    )

    # Antenna diameter for ITU-R RS.1813 [m]
    antenna_diameter: float = 2.2  # Diameter of the antenna in meters

    # Receive antenna gain - applicable for 9a, 9b and OMNI [dBi]
    antenna_gain: float = 52.0  # Gain of the antenna in dBi

    # Channel model, possible values are "FSPL" (free-space path loss), "P619"
    channel_model: str = "FSPL"  # Channel model to be used

    # Relevant IMT parameters which apply for ITU-R P.619
    imt_altitude: float = 20.0  # Altitude of IMT system (in meters)
    imt_lat_deg: float = -22.9  # Latitude of IMT system (in degrees)
    season: str = "SUMMER"  # Season of the year

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

        # Implement additional sanity checks for EESS specific parameters
        if not (0 <= self.antenna_efficiency or self.antenna_efficiency <= 1):
            raise ValueError("antenna_efficiency must be between 0 and 1")

        if self.antenna_pattern not in [
            "ITU-R RS.1813",
            "ITU-R RS.1861 9a",
            "ITU-R RS.1861 9b",
            "ITU-R RS.1861 9c",
            "OMNI",
        ]:
            raise ValueError(f"Invalid antenna_pattern: {self.antenna_pattern}")

        # Check channel model
        if self.channel_model not in ["FSPL", "P619"]:
            raise ValueError("Invalid channel_model, must be either 'FSPL' or 'P619'")

        # Check season
        if self.season not in ["SUMMER", "WINTER"]:
            raise ValueError("Invalid season, must be either 'SUMMER' or 'WINTER'")
