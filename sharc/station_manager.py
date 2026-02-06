# -*- coding: utf-8 -*-
"""
Created on Fri Feb  3 15:29:48 2017

@author: edgar
"""

import numpy as np

from sharc.support.enumerations import StationType
from sharc.station import Station
from sharc.antenna.antenna import Antenna
from sharc.mask.spectral_mask import SpectralMask
from sharc.support.geometry import SimulatorGeometry


class StationManager(object):
    """
    This is the base class that manages an array of stations that will be
    used during a simulation. It acts like a container that vectorizes the
    station properties to speed up calculations.
    """

    def __init__(self, n):
        self.num_stations = n  # Number of stations managed
        self.idx_orbit = np.empty(n)  # Index of the orbit for space stations
        self.indoor = np.zeros(n, dtype=bool)  # Whether the station is indoor
        self.active = np.ones(n, dtype=bool)  # Whether the station is active in the simulation
        self.tx_power = np.zeros(n)  # Station transmit power - dBm for IMT
        self.tx_power_density = np.empty(n)  # Transmit power density in dB/Hz
        self.rx_power = np.empty(n)  # Received power
        self.rx_interference = np.empty(n)  # Rx interferece
        self.ext_interference = np.empty(n)  # External interferece
        self.antenna = np.empty(n, dtype=Antenna)  # antenna objects, one for each station
        self.bandwidth = np.empty(n)  # Bandwidth in MHz

        self.noise_figure = np.empty(n)  # Noise figure in dB
        self.noise_temperature = np.empty(n)  # Noise temperature in K
        self.thermal_noise = np.empty(n)  # Thermal noise in dBm/MHz
        self.total_interference = np.empty(n)  # Total received interference
        self.snr = np.empty(n)  # SNR in dB
        self.sinr = np.empty(n)  # SINR in dB
        self.sinr_ext = np.empty(n)  # Used to store IMT SINR with external interference in dB
        self.inr = np.empty(n)  # INR in dB
        self.pfd = np.empty(n)  # Power flux density in dBm/m^2/MHz
        self.pfd_external_aggregated = np.empty(n)  # External aggregated PFD in dBm/m^2
        self.spectral_mask = np.empty(n, dtype=SpectralMask)  # Spectral mask objects, one for each station
        self.center_freq = np.empty(n)  # Center frequency in MHz
        self.station_type = StationType.NONE  # Station type
        self.is_space_station = False  # Whether the station is a space station - used for path loss calculations
        self.geom = SimulatorGeometry(n)  # Geometry object to manage station coordinates
        self.max_earth_sta_interf_distance = np.inf  # Max distance for earth station interference calculations

    def get_station_list(self, id=None) -> list:
        """Return a list of Station objects for the given indices.

        Parameters
        ----------
        id : iterable or None, optional
            Indices of stations to retrieve. If None, returns all stations.

        Returns
        -------
        list
            List of Station objects.
        """
        if (id is None):
            id = range(self.num_stations)
        station_list = list()
        for i in id:
            station_list.append(self.get_station(i))
        return station_list

    def get_station(self, id) -> Station:
        """Return a Station object for the given index.

        Parameters
        ----------
        id : int
            Index of the station to retrieve.

        Returns
        -------
        Station
            Station object with properties set from the manager.
        """
        station = Station()
        station.id = id
        station.x = self.geom.x_global[id]
        station.y = self.geom.y_global[id]
        station.z = self.geom.z_global[id]
        station.azimuth = self.geom.pointn_azim_global[id]
        station.elevation = self.geom.pointn_elev_global[id]
        station.indoor = self.indoor[id]
        station.active = self.active[id]
        station.tx_power = self.tx_power[id]
        station.rx_power = self.rx_power[id]
        station.rx_interference = self.rx_interference[id]
        station.ext_interference = self.ext_interference[id]
        station.antenna = self.antenna[id]
        station.bandwidth = self.bandwidth[id]
        station.noise_figure = self.noise_figure[id]
        station.noise_temperature = self.noise_temperature[id]
        station.thermal_noise = self.thermal_noise[id]
        station.total_interference = self.total_interference[id]
        station.snr = self.snr[id]
        station.sinr = self.sinr[id]
        station.sinr_ext = self.sinr_ext[id]
        station.inr = self.inr[id]
        station.station_type = self.station_type
        return station

    def is_imt_station(self) -> bool:
        """Return whether this station manager represents IMT stations.

        Returns
        -------
        bool
            True if this station manager is IMT (IMT_BS or IMT_UE), False otherwise.
        """
        if self.station_type is StationType.IMT_BS or self.station_type is StationType.IMT_UE:
            return True
        else:
            return False


def copy_active_stations(stations: StationManager) -> StationManager:
    """Return a new StationManager object containing only the active stations.

    Parameters
    ----------
    stations : StationManager
        StationManager object to copy from.

    Returns
    -------
    StationManager
        A new StationManager object with only the active stations.
    """
    act_sta = StationManager(np.sum(stations.active))
    for idx, active_idx in enumerate(np.where(stations.active)[0]):
        act_sta.x[idx] = stations.x[active_idx]
        act_sta.y[idx] = stations.y[active_idx]
        act_sta.z[idx] = stations.z[active_idx]
        act_sta.azimuth[idx] = stations.azimuth[active_idx]
        act_sta.elevation[idx] = stations.elevation[active_idx]
        act_sta.indoor[idx] = stations.indoor[active_idx]
        act_sta.active[idx] = stations.active[active_idx]
        act_sta.tx_power[idx] = stations.tx_power[active_idx]
        act_sta.rx_power[idx] = stations.rx_power[active_idx]
        act_sta.rx_interference[idx] = stations.rx_interference[active_idx]
        act_sta.ext_interference[idx] = stations.ext_interference[active_idx]
        act_sta.antenna[idx] = stations.antenna[active_idx]
        act_sta.bandwidth[idx] = stations.bandwidth[active_idx]
        act_sta.noise_figure[idx] = stations.noise_figure[active_idx]
        act_sta.noise_temperature[idx] = stations.noise_temperature[active_idx]
        act_sta.thermal_noise[idx] = stations.thermal_noise[active_idx]
        act_sta.total_interference[idx] = stations.total_interference[active_idx]
        act_sta.snr[idx] = stations.snr[active_idx]
        act_sta.sinr[idx] = stations.sinr[active_idx]
        act_sta.sinr_ext[idx] = stations.sinr_ext[active_idx]
        act_sta.inr[idx] = stations.inr[active_idx]
        act_sta.pfd[idx] = stations.pfd[active_idx]
        act_sta.spectral_mask = stations.spectral_mask
        act_sta.center_freq[idx] = stations.center_freq[active_idx]
        act_sta.station_type = stations.station_type
        act_sta.is_space_station = stations.is_space_station
        act_sta.intersite_dist = stations.geom.intersite_dist
    return act_sta
