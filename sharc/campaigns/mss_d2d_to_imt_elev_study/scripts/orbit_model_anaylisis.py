# Description: This script is used to analyze the orbit model of the Global Star constellation.
# The script calculates the number of visible satellites from a ground station and the elevation angles of the satellites.
# The script uses the OrbitModel class from the sharc.satellite.ngso.orbit_model module to calculate the satellite positions.
import numpy as np
import plotly.graph_objects as go

from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.satellite.utils.sat_utils import calc_elevation

if __name__ == "__main__":

    # Plot SystemA orbit using OrbitModel object
    orbit = OrbitModel(
        Nsp=32,  # number of sats per plane
        Np=20,  # number of planes
        phasing=3.9,  # phasing in degrees
        long_asc=18.0,  # longitude of the ascending node in degrees
        omega=0,  # argument of perigee in degrees
        delta=54.5,  # inclination in degrees
        hp=525.0,  # perigee altitude in km
        ha=525.0,  # apogee altitude in km
        Mo=0  # mean anomaly in degrees
    )

    # Show visible satellites from ground-station
    GROUND_STA_LAT = -15.7801
    GROUND_STA_LON = -42.9292
    MIN_ELEV_ANGLE_DEG = 5.0
    pos_vec = orbit.get_satellite_positions_time_interval(initial_time_secs=0, interval_secs=5, n_periods=10)
    sat_altitude_km = orbit.apogee_alt_km  # altitude of the satellites in kilometers
    num_of_visible_sats_per_drop = []
    elevation_angles_per_drop = np.empty(0)
    NUM_DROPS = 1
    rng = np.random.RandomState(seed=6)
    acc_pos = {'x': list(), 'y': list(), 'z': list(), 'lat': list(), 'lon': list()}
    n_samples = pos_vec['sx'].shape[1]
    for i in range(n_samples):
        # pos_vec = orbit.get_orbit_positions_random_time(rng=rng)
        acc_pos['x'].extend(pos_vec['sx'][:, i])
        acc_pos['y'].extend(pos_vec['sy'][:, i])
        acc_pos['z'].extend(pos_vec['sz'][:, i])
        acc_pos['lat'].extend(pos_vec['lat'][:, i])
        acc_pos['lon'].extend(pos_vec['lon'][:, i])
        elev_angles = calc_elevation(GROUND_STA_LAT, pos_vec['lat'][:, i], GROUND_STA_LON,
                                     pos_vec['lon'][:, i], sat_altitude_km)
        elevation_angles_per_drop = np.append(elevation_angles_per_drop,
                                              elev_angles[np.where(np.array(elev_angles) > MIN_ELEV_ANGLE_DEG)])
        vis_sats = np.where(np.array(elev_angles) > MIN_ELEV_ANGLE_DEG)[0]
        num_of_visible_sats_per_drop.append(len(vis_sats))

    # Show visible satellites from ground-station - random
    GROUND_STA_LAT = -15.7801
    GROUND_STA_LON = -42.9292
    MIN_ELEV_ANGLE_DEG = 80.0
    MAX_ELEV_ANGLE_DEG = 90.0
    num_of_visible_sats_per_drop_rand = []
    elevation_angles_per_drop_rand = []
    NUM_DROPS = 1000
    rng = np.random.RandomState(seed=6)
    acc_pos = {'x': list(), 'y': list(), 'z': list(), 'lat': list(), 'lon': list()}
    for i in range(n_samples):
        pos_vec = orbit.get_orbit_positions_random_time(rng=rng)
        acc_pos['x'].extend(pos_vec['sx'].flatten())
        acc_pos['y'].extend(pos_vec['sy'].flatten())
        acc_pos['z'].extend(pos_vec['sz'].flatten())
        acc_pos['lat'].extend(pos_vec['lat'].flatten())
        acc_pos['lon'].extend(pos_vec['lon'].flatten())
        elev_angles = calc_elevation(GROUND_STA_LAT, pos_vec['lat'].flatten(), GROUND_STA_LON,
                                     pos_vec['lon'].flatten(), sat_altitude_km)
        valid_elevs = np.array(elev_angles)
        mask = (valid_elevs >= MIN_ELEV_ANGLE_DEG) & (valid_elevs <= MAX_ELEV_ANGLE_DEG)
        elevation_angles_per_drop = np.append(elevation_angles_per_drop, valid_elevs[mask])
        vis_sats = np.where(mask)[0]

        
        num_of_visible_sats_per_drop_rand.append(len(vis_sats))

    # plot histogram of visible satellites
    fig = go.Figure(data=[go.Histogram(x=num_of_visible_sats_per_drop,
                                       histnorm='probability', xbins=dict(start=-0.5, size=1))])
    fig.update_layout(
        title_text='Visible satellites per drop',
        xaxis_title_text='Num of visible satellites',
        yaxis_title_text='Probability',
        bargap=0.2,
        bargroupgap=0.1,
        xaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=1
        )
    )
    fig.show()

    # plot histogram of visible satellites in random drops
    fig = go.Figure(data=[go.Histogram(x=num_of_visible_sats_per_drop_rand,
                                       histnorm='probability', xbins=dict(start=-0.5, size=1))])
    fig.update_layout(
        title_text='Visible satellites per drop - random',
        xaxis_title_text='Num of visible satellites',
        yaxis_title_text='Probability',
        bargap=0.2,
        bargroupgap=0.1,
        xaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=1
        )
    )
    fig.show()

    # plot histogram of elevation angles
    fig = go.Figure(data=[go.Histogram(x=np.array(elevation_angles_per_drop).flatten(),
                                       histnorm='probability', xbins=dict(start=0, size=5))])
    fig.update_layout(
        title_text='Elevation angles',
        xaxis_title_text='Elevation angle [deg]',
        yaxis_title_text='Probability',
        bargap=0.2,
        bargroupgap=0.1
    )
    fig.show()
