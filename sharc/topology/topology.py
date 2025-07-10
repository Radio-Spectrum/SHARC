# -*- coding: utf-8 -*-
"""
Created on Tue Feb 14 12:48:58 2017

@author: edgar
"""

from abc import ABCMeta, abstractmethod
import numpy as np
import matplotlib.axes


class Topology(object):
    """Abstract base class for network topology representations."""

    __metaclass__ = ABCMeta

    def __init__(
        self,
        intersite_distance: float,
        cell_radius: float,
    ):
        """Initialize a Topology instance with intersite distance and cell radius."""
        self.intersite_distance = intersite_distance
        self.cell_radius = cell_radius

        # Coordinates of the base stations. In this context, each base station
        # is equivalent to a sector (hexagon) in the macrocell topology
        self.x = np.empty(0)
        self.y = np.empty(0)
        self.z = np.empty(0)
        self.azimuth = np.empty(0)
        self.indoor = np.empty(0)
        self.is_space_station = False
        self.num_base_stations = -1
        self.static_base_stations = False

    @abstractmethod
    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """Calculate the coordinates of the stations according to class attributes."""

    # by default, a sharc topology will translate the UE distribution by the
    # BS position
    def transform_ue_xyz(
            self,
            bs_i: int,
            x: np.array,
            y: np.array,
            z: np.array):
        """Translate UE coordinates by the position of the specified base station."""
        return (
            x + self.x[bs_i],
            y + self.y[bs_i],
            z + self.z[bs_i],
        )

    @abstractmethod
    def plot(self, ax: matplotlib.axes.Axes):
        """Plot the topology on the given axis."""
