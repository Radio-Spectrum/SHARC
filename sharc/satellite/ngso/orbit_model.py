"""Implements a Space Station Orbit model as described in Rec. ITU-R S.1325-3
"""

import numpy as np

from sharc.satellite.ngso.custom_functions import wrap2pi, eccentric_anomaly, keplerian2eci, eci2ecef, plot_ground_tracks
from sharc.satellite.utils.sat_utils import ecef2lla
from sharc.satellite.ngso.constants import EARTH_RADIUS_KM, KEPLER_CONST, EARTH_ROTATION_RATE


class OrbitModel():
    """Orbit Model for satellite positions."""

    def __init__(self,
                 Nsp: int,
                 Np: int,
                 phasing: float,
                 long_asc: float,
                 omega: float,
                 delta: float,
                 hp: float,
                 ha: float,
                 Mo: float):
        """Instantiates and OrbitModel object from the Orbit parameters as specified in S.1529.

        Parameters
        ----------
        Nsp : int
            number of satellites in the orbital plane (A.4.b.4.b)
        Np : int
            number of orbital planes (A.4.b.2)
        phasing : float
            satellite phasing between planes, in degrees
        long_asc : float
            initial longitude of ascending node of the first plane, in degrees
        omega : float
            argument of perigee, in degrees
        delta : float
            orbital plane inclination, in degrees
        perigee_alt_km : float
            altitude of perigee in km
        ha : float
            altitude of apogee in km
        Mo : float
            initial mean anomaly for first satellite of first plane, in degrees
        """
        self.Nsp = Nsp
        self.Np = Np
        self.phasing = phasing
        self.long_asc = long_asc
        self.omega = omega
        self.delta = delta
        self.perigee_alt_km = hp
        self.apogee_alt_km = ha
        self.Mo = Mo

        # Derive other orbit parameters
        self.semi_major_axis = (hp + ha + 2 * EARTH_RADIUS_KM) / 2  # semi-major axis, in km
        self.eccentricity = (ha + EARTH_RADIUS_KM - self.semi_major_axis) / self.semi_major_axis  # orbital eccentricity (e)
        self.orbital_period_sec = 2 * np.pi * np.sqrt(self.semi_major_axis ** 3 / KEPLER_CONST)  # orbital period, in seconds
        self.sat_sep_angle_deg = 360 / self.Nsp  # satellite separation angle in the plane (degrees)
        self.orbital_plane_inclination = 360 / self.Np  # angle between plane intersections with the equatorial plane (degrees)

        # Initial mean anomalies for all the satellites
        # shape (Np, Nsp)
        self.initial_mean_anomalies = (Mo + np.arange(Nsp) * self.sat_sep_angle_deg + np.arange(self.Np)[:, None] *
                                       self.phasing) % 360
        self._initial_mean_anomalies_flat = np.radians(self.initial_mean_anomalies.flatten())  # shape (Np*Nsp,)

        # Initial longitudes of ascending node for all the planes
        # shape (Np, Nsp)
        self.Omega_o = (self.long_asc + np.arange(self.Nsp) * 0 + np.arange(self.Np)[:, None] *
                        self.orbital_plane_inclination) % 360
        self.Omega0 = np.radians(self.Omega_o.flatten())  # shape (Np*Nsp,)

    def get_satellite_positions_time_interval(self, initial_time_secs=0, interval_secs=5, n_periods=4) -> dict:
        """
        Return the orbit positions vector.

        Parameters
        ----------
        initial_time_secs : int, optional
            initial time instant in seconds, by default 0
        interval_secs : int, optional
            time interval between points, by default 5
        n_periods : int, optional
            number of orbital peridos, by default 4

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ecef coordinates.
                lat, lon, sx, sy, sz
        """
        t = np.arange(initial_time_secs, n_periods * self.orbital_period_sec + interval_secs, interval_secs)
        return self.__get_satellite_positions(t)

    def get_orbit_positions_time_instant(self, time_instant_secs=0) -> dict:
        """Returns satellite positions in a determined time instant in seconds"""
        t = np.array([time_instant_secs])
        return self.__get_satellite_positions(t)

    def get_orbit_positions_random_time(self, rng: np.random.RandomState) -> dict:
        """Returns satellite positions in a random time instant in seconds"""
        return self.__get_satellite_positions(rng.random_sample(1) * 1000 * self.orbital_period_sec)

    def __get_satellite_positions(self, t: np.array) -> dict:
        """Returns satellite positions (lat, lon, ecef) at given time instants.

        Parameters
        ----------
        t : np.array
            Time instants inside the orbit period in seconds.

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ECEF coordinates:
            - 'lat': Latitude in degrees
            - 'lon': Longitude in degrees
            - 'sx', 'sy', 'sz': ECEF coordinates (meters)
        """

        # 1. Compute Mean Anomaly (M)
        mean_anomaly = (self._initial_mean_anomalies_flat[:, None] +
                        (2 * np.pi / self.orbital_period_sec) * t) % (2 * np.pi)

        # 2. Compute Eccentric Anomaly (E)
        eccentric_anom = eccentric_anomaly(self.eccentricity, mean_anomaly)

        # 3. Compute True Anomaly (v)
        v = 2 * np.arctan(np.sqrt((1 + self.eccentricity) / (1 - self.eccentricity)) * np.tan(eccentric_anom / 2))
        v = np.mod(v, 2 * np.pi)  # Keep within 0 to 2π

        # 4. Compute Distance from Earth's Center (r)
        r = self.semi_major_axis * (1 - self.eccentricity ** 2) / (1 + self.eccentricity * np.cos(v))

        # 5. Longitude of the Ascending Node (`OmegaG`) Evolution
        OmegaG = wrap2pi(self.Omega0[:, None] + EARTH_ROTATION_RATE * t)

        # 6. Compute Latitude (theta)
        lat = np.degrees(np.arcsin(np.sin(v) * np.sin(np.radians(self.delta))))

        # 7. Compute Longitude (phi)
        lon = np.degrees(OmegaG + np.arctan2(np.sin(v), np.cos(v)))

        # 8. Convert to ECEF Coordinates (ITU-R S.1503)
        r_eci = keplerian2eci(self.semi_major_axis,
                            self.eccentricity,
                            self.delta,
                            np.degrees(self.Omega0),
                            self.omega,
                            np.degrees(v))

        r_ecef = eci2ecef(t, r_eci)

        # 9. Extract ECEF coordinates
        sx, sy, sz = r_ecef[0], r_ecef[1], r_ecef[2]

        # 10. Return Position Data
        return {
            'lat': lat,
            'lon': lon,
            'sx': sx,
            'sy': sy,
            'sz': sz
        }



import plotly.graph_objects as go


if __name__ == "__main__":
    # Create an OrbitModel instance
    orbit = OrbitModel(
        Nsp=6,
        Np=8,
        phasing=7.5,
        long_asc=0,
        omega=0,
        delta=52,
        hp=1414,
        ha=1414,
        Mo=0
    )

    # Get satellite positions at time t = 0
    #positions = orbit.get_orbit_positions_time_instant(time_instant_secs=4)
    positions = orbit.get_orbit_positions_random_time(rng=np.random.RandomState(seed=6)
                                                      )
    # Extract longitudes and reshape them into (Np, Nsp) for proper plane grouping
    longitudes = np.sort(positions['lon']).reshape(orbit.Np, orbit.Nsp)

    # Compute satellite spacing within each orbital plane (row-wise differences)
    intra_plane_spacing = (np.diff(longitudes, axis=1)) % 360 # Differences within each plane

    # Compute phasing between planes using the first satellite in each plane
    first_sat_longitudes = longitudes[:, 0]  # First satellite in each plane
    inter_plane_phasing = np.diff(first_sat_longitudes)  # Compute differences

    # Ensure angles are wrapped within [-180, 180]
    inter_plane_phasing = (inter_plane_phasing) % 360

    # Print results
    print("\n--- Satellite Spacing in Orbital Plane ---")
    print(f"Expected: {360/orbit.Nsp:.2f}°")
    print(f"Computed: {intra_plane_spacing}")

    print("\n--- Phasing Between Orbital Planes ---")
    print(f"Expected: {orbit.phasing}°")
    print(f"Computed: {inter_plane_phasing}")

    # Prepare Plotly figure
    fig = go.Figure()

    # Plot intra-plane spacing (satellite spacing in the same plane)
    fig.add_trace(go.Scatter(
        x=list(range(intra_plane_spacing.size)),
        y=intra_plane_spacing.flatten(),
        mode='markers+lines',
        marker=dict(color='red', size=8),
        name="Intra-plane spacing"
    ))

    # Expected intra-plane spacing as reference line
    fig.add_trace(go.Scatter(
        x=list(range(intra_plane_spacing.size)),
        y=[360/orbit.Nsp] * intra_plane_spacing.size,
        mode='lines',
        line=dict(color='red', dash='dash'),
        name="Expected intra-plane spacing"
    ))

    # Plot inter-plane phasing (spacing between orbital planes)
    fig.add_trace(go.Scatter(
        x=list(range(len(inter_plane_phasing))),
        y=inter_plane_phasing,
        mode='markers+lines',
        marker=dict(color='blue', size=8),
        name="Inter-plane phasing"
    ))

    # Expected phasing reference line
    fig.add_trace(go.Scatter(
        x=list(range(len(inter_plane_phasing))),
        y=[orbit.phasing] * len(inter_plane_phasing),
        mode='lines',
        line=dict(color='blue', dash='dash'),
        name="Expected inter-plane phasing"
    ))

    # Customize the layout
    fig.update_layout(
        title="Satellite Angle Differences",
        xaxis_title="Satellite Index",
        yaxis_title="Angle (degrees)",
        legend=dict(x=0.1, y=1.1),
        template="plotly_white"
    )

    # Show interactive plot
    fig.show()


    plot_ground_tracks(positions['lat'], positions['lon'], planes=[1, 2, 3, 4, 5, 6, 7, 8], satellites=[1])


