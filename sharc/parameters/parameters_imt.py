# -*- coding: utf-8 -*-
"""Parameters definitions for IMT systems
"""
import configparser
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_p619 import ParametersP619


@dataclass
class ParametersImt(ParametersBase):
    """Dataclass containing the IMT system parameters
    """
    section_name: str = "IMT"
    topology: str = "MACROCELL"
    wrap_around: bool = False
    num_clusters: int = 1
    intersite_distance: float = 500.0
    minimum_separation_distance_bs_ue: float = 0.0
    interfered_with: bool = False
    frequency: float = 24350.0
    bandwidth: float = 200.0
    rb_bandwidth: float = 0.180
    spectral_mask: str = "IMT-2020"
    spurious_emissions: float = -13.0
    guard_band_ratio: float = 0.1
    bs_load_probability: float = .2
    bs_conducted_power: float = 10.0
    bs_height: float = 6.0
    bs_noise_figure: float = 10.0
    bs_noise_temperature: float = 290.0
    bs_ohmic_loss: float = 3.0
    ul_attenuation_factor: float = 0.4
    ul_sinr_min: float = -10.0
    ul_sinr_max: float = 22.0
    ue_k: int = 3
    ue_k_m: int = 1
    ue_indoor_percent: int = 5.0
    ue_distribution_type: str = "ANGLE_AND_DISTANCE"
    ue_distribution_distance: str = "RAYLEIGH"
    ue_distribution_azimuth: str = "NORMAL"
    ue_tx_power_control: bool = True
    ue_p_o_pusch: float = -95.0
    ue_alpha: float = 1.0
    ue_p_cmax: float = 22.0
    ue_power_dynamic_range: float = 63.0
    ue_height: float = 1.5
    ue_noise_figure: float = 10.0
    ue_ohmic_loss: float = 3.0
    ue_body_loss: float = 4.0
    dl_attenuation_factor: float = 0.6
    dl_sinr_min: float = -10.0
    dl_sinr_max: float = 30.0
    noise_temperature: float = 290.0
    channel_model: str = "UMi"
    shadowing: bool = True
    # Parameters for the P.619 propagation model
    # For IMT NTN the model is used for calculating the coupling loss between
    # the BS space station and the UEs on Earth's surface.
    # For now, the NTN footprint is centered over the BS nadir point, therefore
    # the paramters imt_lag_deg and imt_long_diff_deg SHALL be zero.
    #    space_station_alt_m - altitude of IMT space station (meters)
    #    earth_station_alt_m - altitude of IMT earth stations (UEs) (in meters)
    #    earth_station_lat_deg - latitude of IMT earth stations (UEs) (in degrees)
    #    earth_station_long_diff_deg - difference between longitudes of IMT space and earth stations
    #      (positive if space-station is to the East of earth-station)
    #    season - season of the year.
    param_p619 = ParametersP619()
    space_station_alt_m: float = 20000.0
    earth_station_alt_m: float = 1000.0
    earth_station_lat_deg: float = -15.7801
    earth_station_long_diff_deg: float = 0.0
    season: str = "SUMMER"
    los_adjustment_factor: float = 18.0


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

        # Now do the sanity check for some parameters
        if self.topology.upper() not in ["MACROCELL", "HOTSPOT", "SINGLE_BS", "INDOOR", "NTN"]:
            raise ValueError(
                f"ParamtersImt: Invalid topology name {self.topology}")

        if self.spectral_mask.upper() not in ["IMT-2020", "3GPP E-UTRA"]:
            raise ValueError(f"""ParametersImt: Inavlid Spectral Mask Name {self.spectral_mask}""")

        if self.channel_model.upper() not in ["FSPL", "CI", "UMA", "UMI", "TVRO-URBAN", "TVRO-SUBURBAN", "ABG", "P619"]:
            raise ValueError(f"ParamtersImt: \
                             Invalid value for parameter channel_model - {self.channel_model}. \
                             Possible values are \"FSPL\",\"CI\", \"UMA\", \"UMI\", \"TVRO-URBAN\", \"TVRO-SUBURBAN\", \"ABG\", \"P619\".")
  
        if self.topology == "NTN" and self.channel_model not in ["FSPL", "P619"]:
            raise ValueError(f"ParametersImt: Invalid channel model {self.channel_model} for topology NTN")

        if self.season.upper() not in ["SUMMER", "WINTER"]:
            raise ValueError(f"ParamtersImt: \
                             Invalid value for parameter season - {self.season}. \
                             Possible values are \"SUMMER\", \"WINTER\".")
        
        if self.topology == "NTN":
            self.is_space_to_earth = True
            self.param_p619.load_from_paramters(self)
