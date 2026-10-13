# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sharc.parameters.parameters_base import ParametersBase


@dataclass
class ParametersP452(ParametersBase):
    """Dataclass containing the P.452 propagation model parameters
    """
    # Total air pressure in hPa
    atmospheric_pressure: float = 935.0
    # Temperature in Kelvin
    air_temperature: float = 300.0
    # Sea-level surface refractivity (use the map)
    N0: float = 352.58
    # Average radio-refractive (use the map)
    delta_N: float = 43.127
    # percentage p. Float (0 to 100) or RANDOM
    percentage_p: float = 0.2
    # Distance over land from the transmit and receive antennas to the coast
    # (km)
    Dct: float = 70.0
    # Distance over land from the transmit and receive antennas to the coast
    # (km)
    Dcr: float = 70.0
    # Effective height of interfering antenna (m)
    Hte: float = 20.0
    # Effective height of interfered-with antenna (m)
    Hre: float = 3.0
    # Latitude of transmitter
    tx_lat: float = -23.55028
    # Latitude of receiver
    rx_lat: float = -23.17889
    # Antenna polarization
    polarization: str = "horizontal"
    # determine whether clutter loss following ITU-R P.2108 is added
    # (TRUE/FALSE)
    clutter_loss: bool = True
    # Determine if clutter is applied to "one_end" or "both_ends"
    clutter_type: str = "one_end"

    # --- Losses precomputed per base station over the real terrain ---
    # (database.use_real_terrain with database.from_db_topology_countries)
    # Use the precomputed losses instead of computing P.452 on every snapshot.
    override_from_db: bool = False
    # Take Hte of each BS from the database column altura instead of Hte.
    hte_from_db: bool = False
    # Where the terrain profiles come from: "mesh" (the adaptive mesh of
    # database.terrain) or "grid" (profile_raster, bilinear at pixel centres).
    profile_source: str = "mesh"
    # Terrain GeoTIFF (geographic degrees) for profile_source "grid".
    profile_raster: str = ""
    # Spacing of the profile points [m]; 0 keeps 301 points per profile.
    profile_step_m: float = 0.0
    # Land-cover GeoTIFF (CelPlan classes). When set, representative clutter
    # heights are added to the intermediate profile points (P.452-18 eq. 6e)
    # and used only in the Bullington part of the diffraction model.
    clutter_raster: str = ""
    # Height table for clutter_raster: "celplan" or "p452_tab3".
    clutter_heights: str = "celplan"
    # Radio-climatic zone GeoTIFF (1 = A1 coastal land, 2 = A2 inland,
    # 3 = B sea). When set, the zones, the fraction over sea and Dct/Dcr come
    # from the profile; otherwise the path is A2 and Dct/Dcr are used.
    zone_raster: str = ""
    # Synthetic terrain profiles of RadiAlti_simulation, not available here.
    # Accepted so that those parameter files load; only allowed (and then
    # unused) together with override_from_db.
    is_terrain: bool = False

    def validate(self, ctx: str):
        """Check the P.452 options for profiles precomputed from the database.

        Parameters
        ----------
        ctx : str
            Context used in the error messages.
        """
        super().validate(ctx)
        if self.profile_source not in ("mesh", "grid"):
            raise ValueError(f"{ctx}.profile_source must be 'mesh' or 'grid'")
        if self.profile_source == "grid" and not self.profile_raster:
            raise ValueError(f"{ctx}.profile_source 'grid' needs {ctx}.profile_raster")
        if self.clutter_heights not in ("celplan", "p452_tab3"):
            raise ValueError(f"{ctx}.clutter_heights must be 'celplan' or 'p452_tab3'")
        if isinstance(self.profile_step_m, bool) or not isinstance(self.profile_step_m, (int, float)) \
                or self.profile_step_m < 0:
            raise ValueError(f"{ctx}.profile_step_m must be a non-negative number")
        if self.is_terrain and not self.override_from_db:
            raise NotImplementedError(
                f"{ctx}.is_terrain: the synthetic terrain profiles of RadiAlti_simulation are not "
                "available; use the real terrain of the database (override_from_db)")

    def load_from_paramters(self, param: ParametersBase):
        """Used to load parameters of P.452 from IMT or system parameters

        Parameters
        ----------
        param : ParametersBase
            IMT or system parameters
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
        self.clutter_loss = param.clutter_loss
        self.clutter_type = param.clutter_type
