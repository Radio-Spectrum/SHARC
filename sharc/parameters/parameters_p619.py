# -*- coding: utf-8 -*-
# Object that loads the parameters for the P.619 propagation model.
"""Parameters definitions for IMT systems
"""
from dataclasses import dataclass
import typing

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP619(ParametersBase):
    """Dataclass containing the P.619 propagation model parameters
    """
    # Parameters for the P.619 propagation model
    # For IMT NTN the model is used for calculating the coupling loss between
    # the BS space station and the UEs on Earth's surface.
    # For now, the NTN footprint is centered over the BS nadir point, therefore
    # the paramters imt_lag_deg and imt_long_diff_deg SHALL be zero.
    #    earth_station_alt_m - altitude of IMT system (in meters)
    #    earth_station_lat_deg - latitude of IMT system (in degrees)
    #    earth_station_long_diff_deg - difference between longitudes of IMT and satellite system
    #      (positive if space-station is to the East of earth-station)
    #    season - season of the year.
    earth_station_alt_m: float = 0.0
    earth_station_lat_deg: float = 0.0
    season: str = "SUMMER"
    shadowing: bool = True
    noise_temperature: float = 290.0
    # Average height of clutter. According to 2018 it can be "Low", "Mid" or "High"
    mean_clutter_height: str = "high"
    below_rooftop: float = 100

    def load_from_paramters(self, param: ParametersBase):
        """Used to load parameters of P.619 from IMT or system parameters

        Parameters
        ----------
        param : ParametersBase
            IMT or system parameters
        """
        self.earth_station_alt_m = param.earth_station_alt_m
        self.earth_station_lat_deg = param.earth_station_lat_deg
        self.season = param.season
        self.mean_clutter_height = param.param_p619.mean_clutter_height

        if self.season.upper() not in ["SUMMER", "WINTER"]:
            raise ValueError(f"{self.__class__.__name__}: \
                             Invalid value for parameter season - {self.season}. \
                             Possible values are \"SUMMER\", \"WINTER\".")

        allowed = {"low", "mid", "high"}
        if str(self.mean_clutter_height).lower() not in allowed:
            raise ValueError("Invalid type of mean_clutter_height. mean_clutter_height must be 'Low', 'Mid', or 'High'")

    def set_external_parameters(self, *,
                                earth_station_alt_m: float,
                                earth_station_lat_deg: float,
                                season: typing.Literal["SUMMER", "WINTER"]):
        """
        Set external parameters for P619 propagation calculations.
        """
        self.earth_station_alt_m = earth_station_alt_m
        self.earth_station_lat_deg = earth_station_lat_deg
        self.season = season
