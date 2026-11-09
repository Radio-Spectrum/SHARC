# -*- coding: utf-8 -*-
"""
Created on Thu May  4 16:09:17 2017

@author: Calil
"""

from abc import ABC, abstractmethod
import numpy as np

from sharc.support.sharc_utils import wrap2_180, clip_angle


class Antenna(ABC):
    """
    Abstract antenna class. All antenna classes must inherit from it.

    Methods
    -------
    calculate_gain: calculates the antenna gain in the given directions
    """

    def __init__(self):
        self.beams_list = []
        self.w_vec_list = []

    @abstractmethod
    def calculate_gain(self, *args, **kwargs) -> np.array:
        """
        Calculates the antenan gain.
        """

    def add_beam(self, phi_etilt: float, theta_etilt: float):
        """
        Add new beam to antenna.
        Does not receive angles in local coordinate system.
        Theta taken with z axis as reference.

        Parameters
        ----------
            phi_etilt (float): azimuth electrical tilt angle [degrees]
            theta_etilt (float): elevation electrical tilt angle [degrees]
        """
        self.beams_list.append((0, 0))

    def clip_beam_direction(
        self, phi, theta, h_range, v_range, boresight_azimuth,
    ) -> tuple:
        """
        Limits a beam direction to the antenna steering ranges.

        Parameters
        ----------
            phi (float): beam azimuth [degrees], global coordinates
            theta (float): beam angle from the z axis [degrees], global coordinates
            h_range (tuple): horizontal steering range, relative to boresight
            v_range (tuple): vertical steering range, as theta angles
            boresight_azimuth (float): boresight azimuth [degrees], global coordinates

        Returns
        -------
            phi, theta of the limited beam [degrees], global coordinates
        """
        h_min, h_max = wrap2_180(np.asarray(h_range) + boresight_azimuth)
        return clip_angle(phi, h_min, h_max), np.clip(theta, *v_range)
