"""Implements a Space Station Orbit model as described in Rec. ITU-R S.1325-3
"""

import numpy as np

from sharc.satellite.ngso.custom_functions import wrap2pi, eccentric_anomaly, keplerian2eci, eci2ecef
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
                 Mo: float,
                 *,
                 model_time_as_random_variable: bool,
                 t_min: float,
                 t_max: float | None
             ):
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
        model_time_as_random_variable: bool
            whether get_orbit_positions_random will use only time as random variable
        t_min: float
            if model_time_as_random_variable == True,
            defines the lower bound of the time distribution
        t_max: float
            if model_time_as_random_variable == True,
            defines the upper bound of the time distribution
        """
        self.Nsp = Nsp
        self.Np = Np
        self.phasing = phasing
        self.long_asc = long_asc
        self.omega_0 = omega
        self.omega = omega
        self.delta = delta
        self.perigee_alt_km = hp
        self.apogee_alt_km = ha
        self.Mo = Mo

        # Derive other orbit parameters
        self.semi_major_axis = (
            hp + ha + 2 * EARTH_RADIUS_KM) / 2  # semi-major axis, in km
        self.eccentricity = (ha + EARTH_RADIUS_KM - self.semi_major_axis) / \
            self.semi_major_axis  # orbital eccentricity (e)
        # TODO: consider J2 perturbations for mean motion and orbital period
        self.mean_motion = np.sqrt(KEPLER_CONST / self.semi_major_axis ** 3)
        # orbital period, in seconds
        self.orbital_period_sec = 2 * np.pi / self.mean_motion
        # satellite separation angle in the plane (degrees)
        self.sat_sep_angle_deg = 360 / self.Nsp
        # angle between plane intersections with the equatorial plane (degrees)
        self.orbital_plane_spacing = 360 / self.Np

        # Initial mean anomalies for all the satellites
        initial_mean_anomalies_deg = (
            Mo + np.arange(Nsp) * self.sat_sep_angle_deg + np.arange(
                self.Np)[
                :,
                np.newaxis] * self.phasing) % 360
        self.initial_mean_anomalies_rad = np.radians(
            initial_mean_anomalies_deg.flatten())

        # Initial longitudes of ascending node for all the planes
        inital_raan = (self.long_asc * np.ones(self.Nsp) + np.arange(self.Np)
                       [:, np.newaxis] * self.orbital_plane_spacing) % 360
        self.inital_raan_rad = np.radians(inital_raan.flatten())

        self.model_time_as_random_variable = model_time_as_random_variable
        self.t_min = t_min

        if t_max is not None:
            self.t_max = t_max
        else:
            # sane default
            self.t_max = t_min + self.orbital_period_sec * 1e3
            # TODO: implement 1503 secular drift to enable correct higher time ceiling
            # self.t_max = t_min + 365 * 24 * 60 * 60
            # self.t_max = sys.float_info.max

        # Calculated variables
        self.mean_anomaly = None  # computed mean anomalies
        self.raan_rad = None  # computed longitudes of the ascending node
        self.eccentric_anomaly = None  # computed eccentric anomalies
        self.true_anomaly = None  # computed true anomalies
        self.distance = None  # computed distance to Earth's center
        # computed true anomaly relative to the line of nodes
        self.true_anomaly_rel_line_nodes = None

    def get_satellite_positions_time_interval(
            self,
            initial_time_secs=0,
            interval_secs=5,
            n_periods=4) -> dict:
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
        t = np.arange(
            initial_time_secs,
            n_periods *
            self.orbital_period_sec +
            interval_secs,
            interval_secs)
        return self.get_orbit_positions_time_instant(t)

    def get_orbit_positions_time_instant(self, time_instant_secs=0) -> dict:
        """Returns the Satellite positins for a given time vector within the orbit period.

        Parameters
        ----------
        time_instant_secs: np.array
            time instants inside the orbit period in seconds

        Returns
        -------
        dict
            A dictionary with satellite positions in spherical and ecef coordinates.
                lat, lon, alt, sx, sy, sz
        """
        t = np.atleast_1d(time_instant_secs)

        assert t.ndim == 1, "Input must be scalar or 1D array"

        # TODO: add J2 perturbations based on 1503
        # Mean anomaly (M)
        self.mean_anomaly = (
            self.initial_mean_anomalies_rad[:, None] + self.mean_motion * t
        ) % (2 * np.pi)

        # TODO: add J2 perturbations based on 1503
        # Longitudes of the ascending node (OmegaG)
        # shape (Np*Nsp, len(t))
        self.raan_rad = self.inital_raan_rad[:, None]

        # TODO: add J2 perturbations based on 1503
        # perigee argument
        self.omega = self.omega_0

        self.omega_rad = np.deg2rad(self.omega)

        # The time to be used for calculation of Earth's rotation angle
        earth_rotated_t = t

        return self.__get_satellite_positions_from_angles(
            self.mean_anomaly,
            self.raan_rad,
            self.omega_rad,
            earth_rotated_t,
        )

    def get_orbit_positions_random(
            self,
            rng: np.random.RandomState,
            n_samples=1) -> dict:
        """Returns satellite positions in a random time instant in seconds.
                Parameters
                ----------
                rng : np.random.RandomState
                    Random number generator for reproducibility
                n_samples : int
                    Number of random samples to generate, by default 1
                Returns
                -------
                dict
                    A dictionary with satellite positions in spherical and ecef coordinates.
                        lat, lon, sx, sy, sz
        """
        if self.model_time_as_random_variable:
            return self.get_orbit_positions_time_instant(
                self.t_min + (self.t_max - self.t_min) * rng.random_sample(n_samples)
            )
        # Mean anomaly (M)
        self.mean_anomaly = (self.initial_mean_anomalies_rad[:, None] +
                             2 * np.pi * rng.random_sample(n_samples)) % (2 * np.pi)

        # just selecting a random earth rotation for later coordinate transformation
        earth_rotated_t = 2 * np.pi * rng.random_sample(n_samples) / EARTH_ROTATION_RATE

        # Longitudes of the ascending node (OmegaG)
        # shape (Np*Nsp, len(t))
        # FIXME: previous implementation, due to unexpected behavior, did not
        # use the drawn random samples. Choose whether to maintain behavior
        # self.raan_rad = (self.inital_raan_rad[:, None] +
        #             2 * np.pi * rng.random_sample(n_samples))
        self.raan_rad = self.inital_raan_rad[:, None]

        # perigee argument
        # NOTE: using fixed perigee argument for circular orbits always make sense
        self.omega = self.omega_0

        self.omega_rad = np.deg2rad(self.omega)

        return self.__get_satellite_positions_from_angles(
            self.mean_anomaly,
            self.raan_rad,
            self.omega_rad,
            earth_rotated_t,
        )

    def __get_satellite_positions_from_angles(
        self,
        mean_anomaly: np.ndarray,
        raan_rad: np.ndarray,
        omega_rad: np.array,
        earth_rotated_t: np.ndarray,
    ):
        """
        mean_anomaly:
            Mean anomaly (M)
        raan_rad: np.ndarray
            Longitudes of the ascending node (OmegaG)
        omega_rad: np.ndarray
            Perigee argument
            NOTE: doesn't matter for circular orbits
        earth_rotated_t:
            The time to be used for calculation of Earth's rotation angle
        """
        assert (raan_rad.shape == (self.Np * self.Nsp, len(earth_rotated_t))) or (
            raan_rad.shape == (self.Np * self.Nsp, 1)
        )

        # Eccentric anomaly (E)
        self.eccentric_anom = eccentric_anomaly(
            self.eccentricity, mean_anomaly)

        # True anomaly (v)
        self.true_anomaly = 2 * np.arctan(np.sqrt((1 + self.eccentricity) / (
            1 - self.eccentricity)) * np.tan(self.eccentric_anom / 2))

        self.true_anomaly = np.mod(self.true_anomaly, 2 * np.pi)

        # Distance of the satellite to Earth's center (r)
        r = self.semi_major_axis * \
            (1 - self.eccentricity ** 2) / (1 + self.eccentricity * np.cos(self.true_anomaly))

        # True anomaly relative to the line of nodes (gamma)
        self.true_anomaly_rel_line_nodes = wrap2pi(
            self.true_anomaly +
            omega_rad)  # gamma in the interval [-pi, pi]

        # Latitudes of the satellites, in radians (theta)
        # theta = np.arcsin(np.sin(gamma) * np.sin(np.radians(self.delta)))

        # Longitude variation due to angular displacement, in radians (phiS)
        # phiS = np.arccos(np.cos(gamma) / np.cos(theta)) * np.sign(gamma)

        raan_rad = wrap2pi(raan_rad)

        # POSITION CALCULATION IN ECEF COORDINATES - ITU-R S.1503
        r_eci = keplerian2eci(self.semi_major_axis,
                              self.eccentricity,
                              self.delta,
                              np.degrees(raan_rad),
                              np.degrees(omega_rad),
                              np.degrees(self.true_anomaly))

        r_ecef = eci2ecef(earth_rotated_t, r_eci)
        sx, sy, sz = r_ecef[0], r_ecef[1], r_ecef[2]
        lat = np.degrees(np.arcsin(sz / r))
        lon = np.degrees(np.arctan2(sy, sx))
        # (lat, lon, _) = ecef2lla(sx, sy, sz)

        pos_vector = {
            'lat': lat,
            'lon': lon,
            'alt': r - EARTH_RADIUS_KM,
            'sx': sx,
            'sy': sy,
            'sz': sz
        }
        return pos_vector


def main():
    """Main function to test the OrbitModel class and plot ground tracks.

    This function creates an instance of the OrbitModel class with specified parameters,
    retrieves satellite positions over a specified time interval, and plots the ground tracks
    of the satellites using Plotly.
    """
    import plotly.graph_objects as go

    orbit_params = {
        "Nsp": 1,
        "Np": 28,
        "phasing": 1.5,
        "long_asc": 0,
        "omega": 0,
        "delta": 53,
        "hp": 525,
        "ha": 525,
        "Mo": 0,
        "model_time_as_random_variable": False,
        "t_min": 0.0,
        "t_max": None
    }

    print("Orbit parameters:")
    print(orbit_params)

    # Instantiate the OrbitModel
    orbit_model = OrbitModel(**orbit_params)

    # Get satellite positions over time
    positions = orbit_model.get_satellite_positions_time_interval(n_periods=1)

    # Extract latitude and longitude
    latitudes = positions['lat']
    longitudes = positions['lon']

    # Create a plotly figure
    fig = go.Figure()

    # Add traces for each satellite
    for i in range(latitudes.shape[0]):
        # for i in range(10, 20):
        fig.add_trace(go.Scattergeo(
            lon=longitudes[i],
            lat=latitudes[i],
            mode='lines',
            name=f'Satellite {i + 1}'
        ))

    # Update layout for better visualization
    fig.update_layout(
        title="Satellite Ground Tracks",
        showlegend=False,
        geo=dict(
            projection_type="equirectangular",
            showland=True,
            landcolor="rgb(243, 243, 243)",
            countrycolor="rgb(204, 204, 204)"
        )
    )

    # Show the plot
    fig.show()


if __name__ == "__main__":
    main()
