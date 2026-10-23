"""Link budget of one base station into the protected station, except the propagation loss.

    I [dBm] = P - L + G_station + G_bs - L_pol - L_shield - L_bs          margin = I - threshold   (> 0: not met)

P is the base-station power in the observation band: only the spurious-domain floor of the 3GPP mask (the victim band
lies entirely outside the IMT carrier by more than 10 MHz), P = E + 10 log10(B_obs) with E the spurious emission density.
The station antenna is SA.509 and the base station is one M.2101 element in its own local frame, as in the engine.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Tuple

import numpy as np

from sharc.antenna.antenna_element_imt_m2101 import AntennaElementImtM2101
from sharc.antenna.antenna_sa509 import AntennaSA509
from sharc.contour.criterion import Criterion
from sharc.contour.site import RasSite
from sharc.support.geodesy import lla_to_ecef
from sharc.support.sharc_utils import wrap2_180


def _enu_direction(lat_deg, lon_deg, v_ecef):
    """(phi, theta) [deg] of ECEF vectors `v_ecef` (n, 3) in the local ENU frame at (lat, lon): phi counter-clockwise
    from east, theta from the local vertical (zenith angle)."""
    lat, lon = np.radians(np.asarray(lat_deg, float)), np.radians(np.asarray(lon_deg, float))
    v = np.asarray(v_ecef, float).reshape(-1, 3)
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    east = -np.sin(lon) * x + np.cos(lon) * y
    north = -np.sin(lat) * np.cos(lon) * x - np.sin(lat) * np.sin(lon) * y + np.cos(lat) * z
    up = np.cos(lat) * np.cos(lon) * x + np.cos(lat) * np.sin(lon) * y + np.sin(lat) * z
    return np.degrees(np.arctan2(north, east)), np.degrees(np.arccos(np.clip(up / np.linalg.norm(v, axis=1), -1.0, 1.0)))


@dataclass(frozen=True)
class ReferenceBs:
    """The (reference) base station placed along every ray."""
    frequency_mhz: float = 3500.0                 # IMT carrier; NOT the frequency of the loss calculation
    bandwidth_mhz: float = 100.0                  # IMT carrier bandwidth (per operator)
    spurious_dbm_mhz: float = -30.0               # spurious emission density per operator
    n_operators: int = 4
    downtilt_deg: float = 6.0
    losses_db: float = 0.0
    element_max_g: float = 3.65
    element_phi_3db: float = 90.0
    element_theta_3db: float = 65.0
    element_am: float = 30.0
    element_sla_v: float = 30.0
    multiplication_factor: float = 12.0
    min_gain_dbi: float = -200.0


@dataclass
class Budget:
    site: RasSite
    bs: ReferenceBs = field(default_factory=ReferenceBs)
    criterion: Criterion = field(default_factory=Criterion)

    def __post_init__(self):
        s, b = self.site, self.bs
        self.station_antenna = AntennaSA509(SimpleNamespace(
            diameter=float(s.diameter_m), antenna_efficiency=float(s.efficiency), frequency=float(s.frequency_mhz)))
        self.element = AntennaElementImtM2101(SimpleNamespace(
            multiplication_factor=b.multiplication_factor, element_max_g=b.element_max_g,
            element_phi_3db=b.element_phi_3db, element_theta_3db=b.element_theta_3db,
            element_am=b.element_am, element_sla_v=b.element_sla_v))
        lo, hi = s.frequency_mhz - s.bandwidth_mhz / 2, s.frequency_mhz + s.bandwidth_mhz / 2
        if not (lo > b.frequency_mhz + b.bandwidth_mhz / 2 + 10 or hi < b.frequency_mhz - b.bandwidth_mhz / 2 - 10):
            raise ValueError(f"the station band ({lo:.0f}-{hi:.0f} MHz) is not entirely in the spurious domain of the "
                             "base station (more than 10 MHz outside the IMT carrier)")
        spurious = b.spurious_dbm_mhz + 10 * math.log10(b.n_operators)
        self.power_dbm = 10 * math.log10(s.bandwidth_mhz * 10 ** (spurious / 10))
        self.total_losses_db = float(b.losses_db) + float(s.polarization_loss_db) + float(s.shielding_db)
        self.threshold_dbm = self.criterion.threshold_dbw(s.temperature_k, s.bandwidth_mhz) + 30.0

    # ------------------------------------------------------------ geometry
    def directions(self, lat, lon, bs_height_m, bs_ground_m, station_ground_m) -> Tuple[np.ndarray, ...]:
        """(phi_r, theta_r, phi_b, theta_b): direction of the base station seen from the station (ENU azimuth at the
        station, counter-clockwise from east; theta = zenith angle) and of the station seen from the base station
        (ENU at the base station). Both on the WGS-84 ellipsoid, antennas at ground elevation + height."""
        lat, lon = np.atleast_1d(np.asarray(lat, float)), np.atleast_1d(np.asarray(lon, float))
        s = self.site
        station = np.array(lla_to_ecef(s.lat_deg, s.lon_deg, station_ground_m + s.height_m), float)
        bs = np.stack(lla_to_ecef(lat, lon, np.asarray(bs_height_m) + np.asarray(bs_ground_m)), axis=-1)
        phi_r, theta_r = _enu_direction(s.lat_deg, s.lon_deg, bs - station)
        phi_b, theta_b = _enu_direction(lat, lon, station - bs)
        return phi_r, theta_r, phi_b, theta_b

    # --------------------------------------------------------------- gains
    def station_gain(self, theta_r, elevation_deg=None, azimuth_offset_deg=None):
        """(G_station [dBi], off-axis angle [deg]): SA.509 toward a direction with zenith angle `theta_r`. The dish
        points at the base station in azimuth (offset 0) and at `elevation_deg` (default the site elevation)."""
        el = self.site.elevation_deg if elevation_deg is None else float(elevation_deg)
        a = 90 - el
        b = np.asarray(theta_r, float)
        c = np.zeros_like(b) if azimuth_offset_deg is None else np.asarray(azimuth_offset_deg, float)
        cos_phi = np.cos(np.radians(a)) * np.cos(np.radians(b)) + np.sin(np.radians(a)) * np.sin(np.radians(b)) * np.cos(np.radians(c))
        psi = np.degrees(np.arccos(np.clip(cos_phi, -1.0, 1.0)))
        return self.station_antenna.calculate_gain(off_axis_angle_vec=psi), psi

    def bs_gain(self, phi_b, theta_b, off_axis_deg):
        """M.2101 element toward the station; antenna azimuth = bearing of the station + `off_axis_deg`, elevation
        -downtilt. Off-axis 0 points the sector at the station, 180 points it away."""
        alpha = np.deg2rad(wrap2_180(np.asarray(phi_b, float) + off_axis_deg))
        beta = np.deg2rad(-self.bs.downtilt_deg)
        ph, th = np.deg2rad(phi_b), np.deg2rad(theta_b)
        p0, p1, p2 = np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)
        u0 = np.cos(alpha) * p0 + np.sin(alpha) * p1               # Rz(alpha)^T
        u1 = -np.sin(alpha) * p0 + np.cos(alpha) * p1
        q0 = np.cos(beta) * u0 + np.sin(beta) * p2                 # Ry(beta)
        q2 = -np.sin(beta) * u0 + np.cos(beta) * p2
        lo_phi, lo_theta = np.rad2deg(np.arctan2(u1, q0)), np.rad2deg(np.arccos(q2))
        return np.maximum(self.element.element_pattern(lo_phi, lo_theta) + 0.0, self.bs.min_gain_dbi)

    def margin_db(self, loss_db, g_station, g_bs):
        """I - threshold [dB]; > 0 means the criterion is not met."""
        return (self.power_dbm - np.asarray(loss_db) + np.asarray(g_station) + np.asarray(g_bs)
                - self.total_losses_db - self.threshold_dbm)
