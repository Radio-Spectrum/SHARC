"""Terrain profiles and the P.452 path loss between the protected station and a base station on a ray.

Same functions and order of operations as the SHARC campaigns (``ParametersDatabase``: profile from the reference
point to the site, reversed so that index 0 is the base station, ``Hte`` = base-station height,
``PropagationClearAir.get_loss``), but with the rasters loaded once per link instead of once per call.
"""
from __future__ import annotations

import copy
from typing import Optional, Tuple

import numpy as np

from sharc.parameters.parameters_p452 import ParametersP452
from sharc.propagation.propagation_clear_air_452 import PropagationClearAir
from sharc.propagation.real_terrain.grade_raster import GridRaster, height_lut

from sharc.contour.region import Region
from sharc.contour.site import RasSite

EARTH_RADIUS_KM = 6371.0
CLUTTER_EXCLUSION_KM = 0.05          # P.452-18 eq. 6e: no clutter within 50 m of either terminal


def _great_circle_km(lat1, lon1, lat2, lon2):
    la1, lo1, la2, lo2 = map(np.radians, (lat1, lon1, lat2, lon2))
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h))


class Profiles:
    """Profiles from the station (index 0) to a point, sampled from the region rasters."""

    def __init__(self, region: Region):
        region.check()
        self.step_m = float(region.step_m)
        self.terrain = GridRaster(region.terrain)
        self.cover = GridRaster(region.clutter) if region.clutter else None
        self.heights = height_lut(region.clutter_heights) if self.cover is not None else None
        self.zones = GridRaster(region.zones) if region.zones else None

    def profile(self, ref_lat, ref_lon, lat, lon):
        """(dist_km, elev_m, elev_with_clutter_m or None, zone or None); raises ValueError over points without data."""
        length_km = float(_great_circle_km(ref_lat, ref_lon, lat, lon))
        n = max(5, int(np.ceil(length_km * 1000.0 / self.step_m)) + 1)
        lats, lons = np.linspace(ref_lat, lat, n), np.linspace(ref_lon, lon, n)
        elev = self.terrain.sample(lats, lons, "bilinear")
        dist_km = np.concatenate([[0.0], np.cumsum(_great_circle_km(lats[:-1], lons[:-1], lats[1:], lons[1:]))])
        if np.isnan(elev).any():
            raise ValueError(f"terrain profile to ({lat}, {lon}) has {int(np.isnan(elev).sum())} points without data")
        with_clutter = None
        if self.cover is not None:
            classes = np.clip(self.cover.sample(lats, lons, "nearest", fill=0).astype(int), 0, 255)
            far = (dist_km >= CLUTTER_EXCLUSION_KM) & (dist_km <= dist_km[-1] - CLUTTER_EXCLUSION_KM)
            far[0] = far[-1] = False
            with_clutter = elev + np.where(far, self.heights[classes], 0.0)
        zone = None
        if self.zones is not None:
            zone = self.zones.sample(lats, lons, "nearest", fill=2).astype(float)
            zone[(zone < 1) | (zone > 3)] = 2
        return dist_km, elev, with_clutter, zone

    def ground_m(self, lat, lon) -> float:
        """Terrain elevation [m] at a point (bilinear)."""
        return float(self.terrain.sample(np.array([lat]), np.array([lon]), "bilinear")[0])


class P452Link:
    """P.452 loss from the base station on a ray to the protected station.

    `p452` holds the climate and path options (percentage_p, delta_N, N0, polarization, clutter_loss...), exactly the
    names of ``ParametersP452``; ``Hre`` (the station height) and ``Hte`` (the base-station height) are set here."""

    def __init__(self, site: RasSite, region: Region, p452: Optional[dict] = None, frequency_mhz: float = 3500.0):
        self.site = site
        self.f_ghz = float(frequency_mhz) / 1000.0
        self.params = ParametersP452()
        for key, value in (p452 or {}).items():
            if key in ("Hre", "Hte", "hte_from_db"):
                raise KeyError(f"p452.{key} is set by the link: Hre = the site height, Hte = the base-station height")
            if not hasattr(self.params, key):
                raise KeyError(f"unknown P.452 parameter: {key}")
            setattr(self.params, key, value)
        self.params.Hre = float(site.height_m)
        self.params.hte_from_db = True
        self.profiles = Profiles(region)
        self.rng = np.random.RandomState(42)                      # not drawn when percentage_p is a number
        self.ground_m = self.profiles.ground_m(site.lat_deg, site.lon_deg)

    def loss_db(self, lat, lon, bs_height_m: float) -> Tuple[float, float]:
        """(P.452 loss [dB], base-station ground elevation [m]) for a base station at (lat, lon)."""
        dist_km, elev, with_clutter, zone = self.profiles.profile(self.site.lat_deg, self.site.lon_deg, lat, lon)
        return self.loss_from_profile(dist_km, elev, with_clutter, zone, bs_height_m)

    def loss_from_profile(self, dist_km, elev, with_clutter, zone, bs_height_m: float) -> Tuple[float, float]:
        """Same, for a profile already sampled (see `Profiles.profile`)."""
        p = copy.copy(self.params)
        p.terrain_d = dist_km[-1] - dist_km[::-1]
        p.terrain_h = elev[::-1].copy()
        p.Hte = float(bs_height_m)
        if with_clutter is not None:
            p.terrain_g = with_clutter[::-1].copy()
        if zone is not None:
            p.terrain_zone = zone[::-1].copy()
            p.Dct, p.Dcr = PropagationClearAir.coast_distances(p.terrain_d, p.terrain_zone)
        prop = PropagationClearAir(self.rng, p)
        loss = prop.get_loss(np.array([[dist_km[-1]]]), np.array([[self.f_ghz]]), np.array([[False]]),
                             np.array([[0.0]]), np.array([[0.0]]), np.array([[0.0]]))[0, 0]
        return float(loss), float(elev[-1])
