# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP1812(ParametersBase):
    """Dataclass containing the ITU-R P.1812-6 propagation model parameters."""
    # Total air pressure in hPa
    atmospheric_pressure: float = 935.0
    # Temperature in Kelvin
    air_temperature: float = 300.0
    # Sea-level surface refractivity (use the map)
    N0: float = 352.58
    # Average radio-refractivity lapse-rate through the lowest 1 km (use the map)
    delta_N: float = 43.127
    # Percentage of time p. Float (0 to 50) or RANDOM
    percentage_p: float = 0.2
    # Distance over land from the transmit antenna to the coast (km)
    Dct: float = 70.0
    # Distance over land from the receive antenna to the coast (km)
    Dcr: float = 70.0
    # Effective height of interfering antenna (m)
    Hte: float = 20.0
    # Effective height of interfered-with antenna (m)
    Hre: float = 3.0
    # Latitude of transmitter
    tx_lat: float = -23.55028
    # Latitude of receiver
    rx_lat: float = -23.17889
    # Antenna polarization ("horizontal" or "vertical")
    polarization: str = "horizontal"
    # Percentage of locations pL (0 to 100). pL = 50 -> median-location loss.
    location_percentage: float = 50.0
    # Standard deviation of the location variability sigma_L (dB), Section 4.8.
    # 0.0 disables the location-variability correction.
    location_variability_sigma: float = 0.0
    # Clutter handling mode. One of:
    #   "p2108"   - statistical clutter at each end following ITU-R P.2108
    #   "terrain" - path-specific representative-clutter height-gain model
    #               (P.1812 Section 4.7), applied at the terminals
    #   "none"    - no clutter loss
    clutter_mode: str = "p2108"
    # (P.2108 mode) determine if clutter is applied to "one_end" or "both_ends"
    clutter_type: str = "one_end"
    # Kept for backward compatibility; superseded by clutter_mode for P.1812.
    clutter_loss: bool = True

    # --- Representative clutter for the "terrain" clutter mode ----------
    # Representative clutter height around the transmitter / receiver (m).
    # Set to 0 to disable clutter at that terminal.
    repr_clutter_height_tx: float = 15.0
    repr_clutter_height_rx: float = 15.0
    # Nominal distance from the terminal to the clutter (km).
    clutter_nominal_dist_tx: float = 0.1
    clutter_nominal_dist_rx: float = 0.1

    # --- Terrain profile configuration ---------------------------------
    # Terrain profile source used by the diffraction model:
    #   "flat"        - smooth Earth (no terrain database), default
    #   "srtm"        - real terrain sampled from SRTM .hgt tiles (path-specific)
    #   "statistical" - synthetic terrain drawn per snapshot from fitted
    #                   distributions (Monte-Carlo friendly; 5D/1059 approach)
    terrain_profile: str = "flat"
    # Directory containing SRTM .hgt tiles (used when terrain_profile == "srtm")
    srtm_directory: str = ""
    # Number of points sampled along each path profile (>= 4)
    profile_resolution: int = 100
    # If True, missing SRTM tiles/voids are treated as 0 m (sea level) with a
    # warning; if False, a missing tile raises an error.
    srtm_missing_tile_as_zero: bool = True
    # If True, tiles missing from srtm_directory are downloaded on demand and
    # cached there. Requires network access. Default False (offline).
    srtm_auto_download: bool = False
    # URL template for tile download; {tile} is replaced by the tile base name
    # (e.g. "S24W047"). Empty string uses the default ESA STEP SRTMGL1 mirror.
    srtm_download_url_template: str = ""
    # Per-tile download timeout in seconds.
    srtm_download_timeout: float = 60.0
    # How station coordinates are interpreted to obtain lat/long for SRTM:
    #   "local"      - stations are placed in a local x(east)/y(north) plane in
    #                  metres; the geographic anchor below maps the origin.
    #   "geographic" - use the stations' own latitude/longitude attributes.
    terrain_coordinate_mode: str = "local"
    # Geographic anchor (degrees) of the local x/y origin, used when
    # terrain_coordinate_mode == "local".
    topology_central_latitude: float = 0.0
    topology_central_longitude: float = 0.0

    # --- Statistical terrain model (terrain_profile == "statistical") ---
    # Student's t-distribution of peak/valley height deviations (m, location 0)
    # and lognormal distribution of distance (km) between consecutive extrema.
    # Defaults: values fitted from 20x50 km radials around Campinas-SP.
    stat_height_sigma_m: float = 36.27
    stat_height_nu: float = 2.93
    stat_dist_mu: float = -0.652
    stat_dist_sigma: float = 0.720
    # Constant elevation added to the synthetic profile (m amsl); does not
    # affect diffraction.
    stat_baseline_m: float = 0.0
    # Moving-average length (km) applied to the synthetic profile to emulate
    # the roundness of real terrain (calibrated against real Campinas profiles).
    stat_smoothing_km: float = 1.6

    # --- Statistical clutter-over-terrain (used in clutter_mode "terrain") ---
    # If True, the representative clutter heights at the terminals are drawn per
    # link from the distance-dependent model instead of the fixed
    # repr_clutter_height_*.
    clutter_statistical: bool = False
    # Distance-dependent clutter: deterministic exponential-with-floor trend
    # f(d) = C + (A - C)*exp(-d/d0) times a multiplicative lognormal spread,
    # where d (km) is the terminal's distance from the IMT cluster centre.
    # Defaults fitted from REAL land use (ESA WorldCover) over Campinas-SP
    # (trend fitted to the MEAN, R^2=0.98): mean 22.7 m at the centre decaying
    # to a ~7.9 m rural floor. stat_clutter_target = "mean" or "median".
    stat_clutter_trend_A: float = 22.68
    stat_clutter_trend_C: float = 7.90
    stat_clutter_trend_d0_km: float = 5.97
    stat_clutter_sigma: float = 1.238
    stat_clutter_target: str = "mean"

    def load_from_paramters(self, param: ParametersBase):
        """Load the P.1812 parameters from an IMT or system parameters object.

        Parameters
        ----------
        param : ParametersBase
            IMT or system parameters that carry the P.1812 attributes.
        """
        self.atmospheric_pressure = param.atmospheric_pressure
        self.air_temperature = param.air_temperature
        self.N0 = param.N0
        self.delta_N = param.delta_N
        self.percentage_p = param.percentage_p
        self.Dct = param.Dct
        self.Dcr = param.Dcr
        self.Hte = param.Hte
        self.Hre = param.Hre
        self.tx_lat = param.tx_lat
        self.rx_lat = param.rx_lat
        self.polarization = param.polarization
        self.location_percentage = param.location_percentage
        self.location_variability_sigma = param.location_variability_sigma
        self.clutter_mode = param.clutter_mode
        self.clutter_type = param.clutter_type
        self.clutter_loss = param.clutter_loss
        self.repr_clutter_height_tx = param.repr_clutter_height_tx
        self.repr_clutter_height_rx = param.repr_clutter_height_rx
        self.clutter_nominal_dist_tx = param.clutter_nominal_dist_tx
        self.clutter_nominal_dist_rx = param.clutter_nominal_dist_rx
        self.terrain_profile = param.terrain_profile
        self.srtm_directory = param.srtm_directory
        self.profile_resolution = param.profile_resolution
        self.srtm_missing_tile_as_zero = param.srtm_missing_tile_as_zero
        self.srtm_auto_download = param.srtm_auto_download
        self.srtm_download_url_template = param.srtm_download_url_template
        self.srtm_download_timeout = param.srtm_download_timeout
        self.terrain_coordinate_mode = param.terrain_coordinate_mode
        self.topology_central_latitude = param.topology_central_latitude
        self.topology_central_longitude = param.topology_central_longitude
        self.stat_height_sigma_m = param.stat_height_sigma_m
        self.stat_height_nu = param.stat_height_nu
        self.stat_dist_mu = param.stat_dist_mu
        self.stat_dist_sigma = param.stat_dist_sigma
        self.stat_baseline_m = param.stat_baseline_m
        self.stat_smoothing_km = param.stat_smoothing_km
        self.clutter_statistical = param.clutter_statistical
        self.stat_clutter_trend_A = param.stat_clutter_trend_A
        self.stat_clutter_trend_C = param.stat_clutter_trend_C
        self.stat_clutter_trend_d0_km = param.stat_clutter_trend_d0_km
        self.stat_clutter_sigma = param.stat_clutter_sigma
        self.stat_clutter_target = param.stat_clutter_target
