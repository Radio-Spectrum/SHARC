import numpy as np
import plotly.graph_objects as go

from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.satellite.utils.sat_utils import calc_elevation, lla2ecef
from sharc.satellite.scripts.plot_globe import plot_globe_with_borders
from sharc.satellite.ngso.constants import EARTH_RADIUS_KM


def plot_orbit_trace(orbit):
    """
    Traces the orbit satellite paths from t_min to t_max
    """
    # Plot satellite traces from a time interval
    fig = plot_globe_with_borders(True, None, True)
    step = 5
    pos_vec = orbit.get_orbit_positions_time_instant(
        np.linspace(orbit.t_min, orbit.t_max, int((orbit.t_max - orbit.t_min) / step))
    )
    fig.add_trace(go.Scatter3d(x=pos_vec['sx'].flatten(),
                               y=pos_vec['sy'].flatten(),
                               z=pos_vec['sz'].flatten(),
                               mode='lines',
                               showlegend=False))

    fig.update_layout(
        title_text='Satellite Traces',
        scene=dict(
            xaxis_title='X [km]',
            yaxis_title='Y [km]',
            zaxis_title='Z [km]',
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0)
    )

    return fig


def plot_sampling(
    orbit,
    ground_sta_lat,
    ground_sta_lon,
    ground_sta_alt,
    min_elev_angle_deg,
    num_drops=1000
):
    """
    Gets num_drops random snapshots from orbit model and plots the result
    """
    # Show visible satellites from ground-station
    fig = plot_globe_with_borders(True, None, True)
    rng = np.random.RandomState(seed=6)
    pos_vec = orbit.get_orbit_positions_random(rng=rng, n_samples=num_drops)
    look_angles = calc_elevation(
        ground_sta_lat,
        pos_vec['lat'],
        ground_sta_lon,
        pos_vec['lon'],
        sat_height=orbit.apogee_alt_km * 1e3,
        es_height=ground_sta_alt)

    # plot all satellites in drops
    fig.add_trace(go.Scatter3d(x=pos_vec['sx'].flatten(),
                               y=pos_vec['sy'].flatten(),
                               z=pos_vec['sz'].flatten(),
                               mode='markers',
                               marker=dict(size=2,
                                           color='red',
                                           opacity=0.8),
                               showlegend=False))

    # plot visible satellites
    fig.add_trace(go.Scatter3d(
        x=pos_vec['sx'][np.where(look_angles > min_elev_angle_deg)].flatten(),
        y=pos_vec['sy'][np.where(look_angles > min_elev_angle_deg)].flatten(),
        z=pos_vec['sz'][np.where(look_angles > min_elev_angle_deg)].flatten(),
        mode='markers',
        marker=dict(size=2,
                    color='green',
                    opacity=0.8),
        showlegend=False))

    # plot ground station
    groud_sta_pos = lla2ecef(ground_sta_lat, ground_sta_lon, ground_sta_alt)
    fig.add_trace(go.Scatter3d(
        x=np.array(groud_sta_pos[0] / 1e3),
        y=np.array(groud_sta_pos[1] / 1e3),
        z=np.array(groud_sta_pos[2] / 1e3),
        mode='markers',
        marker=dict(size=4,
                    color='blue',
                    opacity=1.0),
        showlegend=False))

    return fig


def get_times_for_sat_in_correct_latitude(
    earth_station_lat: np.ndarray,
    orbit: OrbitModel,
):
    """
    Returns time: nd.array
        A time array for the times where a satellite is at the given latitude
        in the [0, orbit_period_sec) range.
        Since every satellite passes through that lat twice,
        ascending and descending, time.shape == (Np * Nsp * 2,)
    """
    inclin = np.abs(orbit.delta)

    if np.abs(earth_station_lat) > inclin:
        # return None
        raise ValueError(
            "It is impossible to find a time where the satellite "
            f"passes ahead of a point lat={earth_station_lat} if "
            f"its inclination is {inclin}"
        )
    # considering plane geometry, latitude of the satellite follows
    # is the argument of latitude u
    # u(t) = v(t) + omega(t)
    # simplifying argument of perigee omega(t) = omega can be done for circular orbits
    # or when ideal keplerian model is considered (since there is no precession)
    # so u(t) = v(t) + omega

    # also, sin(inclin) * sin(u) = sin(lat)
    # so, to get wanted time t_w,
    # u = arcsin(sin(lat) / sin(inclin))
    u1 = np.arcsin(
        np.sin(np.deg2rad(earth_station_lat)) / np.sin(np.deg2rad(orbit.delta))
    )
    u2 = np.pi - u1
    u = np.array([u1, u2])
    # true anomaly:
    # NOTE: this would not be correct when considering J2 perigee argument precession
    # on non-circular orbits. In that case, numerical methods are needed
    v = u - np.deg2rad(orbit.omega_0)

    # eccentric anomaly
    E = 2 * np.arctan2(
        np.sqrt(1 - orbit.eccentricity) * np.sin(v / 2),
        np.sqrt(1 + orbit.eccentricity) * np.cos(v / 2)
    )

    # mean anomaly wanted, to get desired latitude
    M_w = E - orbit.eccentricity * np.sin(E)

    # time wanted for desired latitude is t_w (mod orbit_period)
    t_w = (
        (M_w[None, :] - orbit.initial_mean_anomalies_rad[:, None]) /
        orbit.mean_motion
    ) % orbit.orbital_period_sec

    return t_w.flatten()


def min_and_max_t_from(
    selected_t: float,
    selected_sat_i: float,
    orbit: OrbitModel,
    ground_lat: float,
    ground_lon: float,
    ground_alt: float,
    min_elevation,
    step: float = 5
):
    """
    Searches and returns min and max time for which satellite is still visible.
    selected_t is the midpoint of the search domain
    """
    # check if it is in bounding box
    low = selected_t - orbit.orbital_period_sec / 4
    high = selected_t + orbit.orbital_period_sec / 4
    ts = np.arange(low, high, step)
    all_pos = orbit.get_orbit_positions_time_instant(ts)
    sat_lats = all_pos["lat"][selected_sat_i]
    sat_lons = all_pos["lon"][selected_sat_i]
    sat_alts = all_pos["alt"][selected_sat_i]

    elev = calc_elevation(
        ground_lat, sat_lats,
        ground_lon, sat_lons,
        sat_height=sat_alts * 1e3,
        es_height=ground_alt
    )
    mask = elev >= min_elevation
    ts_within = np.where(mask)[0]

    t_min_i = ts_within[0] - 1
    t_max_i = ts_within[-1] + 1

    return ts[t_min_i], ts[t_max_i]


if __name__ == "__main__":
    orbit = OrbitModel(
        Nsp=120,  # number of sats per plane
        Np=28,  # number of planes
        phasing=1.5,  # phasing in degrees
        long_asc=0,  # longitude of the ascending node in degrees
        omega=0,  # argument of perigee in degrees
        delta=52,  # inclination in degrees
        hp=525,  # perigee altitude in km
        ha=525,  # apogee altitude in km
        Mo=0,  # mean anomaly in degrees
        model_time_as_random_variable=True,
        t_min=0.0,
        t_max=None
    )

    # Set parameters for ground station
    GROUND_STA_LAT = -15.7801
    GROUND_STA_LON = -42.9292
    GROUND_STA_ALT = 1200

    MIN_ELEV_ANGLE_DEG = 5.0

    possible_ts = get_times_for_sat_in_correct_latitude(
        GROUND_STA_LAT,
        orbit,
    )
    n_samples = 1e3
    arange_len = int(np.ceil(n_samples / (orbit.Np * orbit.Nsp)))
    candidate_times = (possible_ts[None, :] + np.arange(0, arange_len)[:, None] * orbit.orbital_period_sec).flatten()

    pos_vec = orbit.get_orbit_positions_time_instant(
        candidate_times
    )
    all_lats = pos_vec["lat"]
    all_lons = pos_vec["lon"]
    lat_err = np.abs(all_lats - GROUND_STA_LAT)
    lon_err = np.abs(all_lons - GROUND_STA_LON)
    # do not let us choose a satellite with lat_err > 0.1
    lon_err[lat_err > 0.1] = 100
    # you may choose other parameters, such as choosing a specific sat
    # my_sat_i = 2 * orbit.Nsp + 1
    # my_sat_err = lon_err[my_sat_i].copy()
    # lon_err[::] = 100
    # lon_err[my_sat_i] = my_sat_err
    flat_selected_i = np.argmin(lon_err)

    selected_sat_i = flat_selected_i // len(candidate_times)
    selected_t_i = flat_selected_i % len(candidate_times)

    sat_lat = all_lats[selected_sat_i][selected_t_i]
    sat_lon = all_lons[selected_sat_i][selected_t_i]
    selected_t = candidate_times[selected_t_i]

    print(f"Selected satellite {selected_sat_i} at time {selected_t}")
    print(f"\tPositioned at (lat, lon) = ({sat_lat}, {sat_lon})")
    print(
        "\tAt an error of (dlat, dlon) =",
        f"({np.abs(sat_lat - GROUND_STA_LAT)}, {np.abs(sat_lon - GROUND_STA_LON)})"
    )
    # range = 20
    # range = orbit.orbital_period_sec
    # t_start, t_end = selected_t - range, selected_t + range
    t_start, t_end = min_and_max_t_from(
        selected_t,
        selected_sat_i,
        orbit,
        GROUND_STA_LAT,
        GROUND_STA_LON,
        GROUND_STA_ALT,
        MIN_ELEV_ANGLE_DEG,
    )
    print(f"Can simulate with t in [{t_start}, {t_end}]")

    orbit.t_min = t_start
    orbit.t_max = t_end

    plot_orbit_trace(orbit).show()
    plot_sampling(
        orbit,
        GROUND_STA_LAT,
        GROUND_STA_LON,
        GROUND_STA_ALT,
        MIN_ELEV_ANGLE_DEG,
        num_drops=1
    ).show()

    print("Orbit additional params:")
    for k in [
        "Mo", "model_time_as_random_variable", "t_min", "t_max",
    ]:
        print(4 * " " + f"{k}:", getattr(orbit, k))
