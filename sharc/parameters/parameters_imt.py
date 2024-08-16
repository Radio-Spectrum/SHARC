# -*- coding: utf-8 -*-
"""Parameters definitions for IMT systems"""

import configparser
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersImt(ParametersBase):
    """Dataclass containing the IMT system parameters"""

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
    bs_load_probability: float = 0.2
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
    channel_model: str = "UMi"
    los_adjustment_factor: float = 18.0
    shadowing: bool = True
    noise_temperature: float = 290.0

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
        if self.topology.upper() not in ["MACROCELL", "HOTSPOT", "SINGLE_BS", "INDOOR"]:
            raise ValueError(f"ParamtersImt: Invalid topology name {self.topology}")

        if self.spectral_mask.upper() not in ["IMT-2020", "3GPP E-UTRA"]:
            raise ValueError(
                f"ParametersImt: Inavlid Spectral Mask Name {self.spectral_mask}"
            )
