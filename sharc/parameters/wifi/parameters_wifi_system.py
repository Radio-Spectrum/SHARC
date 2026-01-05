# -*- coding: utf-8 -*-
"""Parameters definitions for WiFi systems
"""
from dataclasses import dataclass, field
import typing

from sharc.parameters.wifi.parameters_antenna_wifi import ParametersAntennaWifi
from sharc.parameters.parameters_antenna import ParametersAntenna
from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_p619 import ParametersP619
from sharc.parameters.wifi.parameters_antenna_wifi import ParametersAntennaWifi
from sharc.parameters.wifi.parameters_wifi_topology import ParametersWifiTopology


@dataclass
class ParametersWifiSystem(ParametersBase):
    """Dataclass containing the WiFi system parameters
    """
    section_name: str = "wifi"

    nested_parameters_enabled: bool = True

    minimum_separation_distance_ap_sta: float = 0.0
    interfered_with: bool = False
    frequency: float = 7000.0
    bandwidth: float = 80.0
    rb_bandwidth: float = 0.180
    spectral_mask: str = "WIFI-2020"
    spurious_emissions: float = -13.0
    guard_band_ratio: float = 0.1
    antenna_pattern: str = "Modified ITU-R S.465"
    max_dist_hotspot_ue: float = 70
    adjacent_ch_reception: str = "ACS"
    polarization_loss: float = 0.0
    adjacent_ch_selectivity: float = 20.0
    tx_power_density: float = -65

    # Adjacent channel emissions type
    # Possible values are "ACLR", "SPECTRAL_MASK" and "OFF"
    adjacent_ch_emissions: str = "OFF"

    # Spectral mask used for the IMT system when adjacent_ch_emissions is set to "SPECTRAL_MASK"
    spectral_mask: str = "WIFI-2020"

    @dataclass
    class ParametersAP(ParametersBase):
        load_probability = 0.5
        conducted_power = 22
        height: float = 6.0
        noise_figure: float = 10.0
        ohmic_loss: float = 3.0
        # Adjacent Channel Selectivity in dB
        adjacent_ch_selectivity: float = None
        # Adjacent channel leakage ratio in dB used if adjacent_ch_emissions is set to "ACLR"
        adjacent_ch_leak_ratio: float = 45.0
        antenna: ParametersAntenna = field(
            default_factory=lambda: ParametersAntenna(
                pattern="ARRAY", array=ParametersAntennaWifi(
                    downtilt=0.0)))

    ap: ParametersAP = field(default_factory=ParametersAP)

    topology: ParametersWifiTopology = field(default_factory=ParametersWifiTopology)

    @dataclass
    class ParametersUL(ParametersBase):
        attenuation_factor: float = 0.4
        sinr_min: float = -10.0
        sinr_max: float = 22.0
    uplink: ParametersUL = field(default_factory=ParametersUL)

     # Antenna model for adjacent band studies.
    adjacent_antenna_model: typing.Literal["SINGLE_ELEMENT", "BEAMFORMING"] = "SINGLE_ELEMENT"

    @dataclass
    class ParametersSTA(ParametersBase):
        load_probability = 0.5
        conducted_power = 12
        k: int = 1
        k_m: int = 1
        indoor_percent: int = 0.0
        distribution_type: str = "ANGLE_AND_DISTANCE"
        distribution_distance: str = "SQRT(UNIFORM)"
        distribution_azimuth: str = "UNIFORM"
        azimuth_range: tuple = (-180, 180)
        tx_power_control: bool = True
        p_o_pusch: float = -95.0
        alpha: float = 1.0
        p_cmax: float = 22.0
        power_dynamic_range: float = 63.0
        height: float = 1.5
        noise_figure: float = 10.0
        ohmic_loss: float = 3.0
        body_loss: float = 4.0
        adjacent_ch_selectivity: float = 33  # Adjacent Channel Selectivity in dB
        # Adjacent channel leakage ratio in dB used if adjacent_ch_emissions is set to "ACLR"
        adjacent_ch_leak_ratio: float = 45.0
        antenna: ParametersAntenna = field(
            default_factory=lambda: ParametersAntenna(
                pattern="ARRAY"))

    sta: ParametersSTA = field(default_factory=ParametersSTA)

    @dataclass
    class ParamatersDL(ParametersBase):
        attenuation_factor: float = 0.6
        sinr_min: float = -10.0
        sinr_max: float = 30.0

    downlink: ParamatersDL = field(default_factory=ParamatersDL)

    noise_temperature: float = 290.0
    # Channel parameters
    # channel model, possible values are "FSPL" (free-space path loss),
    #                                    "CI" (close-in FS reference distance)
    #                                    "UMa" (Urban Macro - 3GPP)
    #                                    "UMi" (Urban Micro - 3GPP)
    #                                    "TVRO-URBAN"
    #                                    "TVRO-SUBURBAN"
    #                                    "ABG" (Alpha-Beta-Gamma)
    # TODO: check if we wanna separate the channel model definition in its own nested attributes
    channel_model: str = "UMi"
    season: str = "SUMMER"

    # TODO: create parameters for where this is needed
    los_adjustment_factor: float = 18.0
    shadowing: bool = True


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
        
        if self.channel_model not in ["FSPL", "CI", "UMa", "UMi", "TVRO-URBAN", "TVRO-SUBURBAN", "ABG", "P619"]:
            raise ValueError(f"ParamtersImt: \
                             Invalid value for parameter channel_model - {self.channel_model}. \
                             Possible values are \"FSPL\",\"CI\", \"UMa\", \"UMi\", \"TVRO-URBAN\", \"TVRO-SUBURBAN\", \
                             \"ABG\", \"P619\".")


        if self.season not in ["SUMMER", "WINTER"]:
            raise ValueError(f"ParamtersImt: \
                             Invalid value for parameter season - {self.season}. \
                             Possible values are \"SUMMER\", \"WINTER\".")


        self.frequency = float(self.frequency)

        self.ap.antenna.set_external_parameters(
            adjacent_antenna_model=self.adjacent_antenna_model,
            frequency=self.frequency,
            bandwidth=self.bandwidth,
        )

        self.sta.antenna.set_external_parameters(
            adjacent_antenna_model=self.adjacent_antenna_model,
            frequency=self.frequency,
            bandwidth=self.bandwidth,
        )

    

    