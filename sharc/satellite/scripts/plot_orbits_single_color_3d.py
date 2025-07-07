# Generates a 3D plot of the Earth with the satellites positions
# https://geopandas.org/en/stable/docs/user_guide/io.html
from sharc.satellite.scripts.plot_globe import plot_globe_with_borders
from sharc.station_factory import StationFactory
from sharc.parameters.parameters_mss_d2d import ParametersOrbit, ParametersMssD2d
import numpy as np
import plotly.graph_objects as go

from sharc.support.sharc_geom import GeometryConverter
from sharc.station_manager import StationManager
geoconv = GeometryConverter()

sys_lat = -14.5
sys_long = -45
sys_alt = 1200

geoconv.set_reference(
    sys_lat, sys_long, sys_alt
)


if __name__ == "__main__":
    # Define the orbit parameters for two satellite constellations
    orbit_1 = ParametersOrbit(
        n_planes=6, sats_per_plane=8, phasing_deg=7.5, long_asc_deg=0,
        inclination_deg=52, perigee_alt_km=1414, apogee_alt_km=1414
    )

    orbit_2 = ParametersOrbit(
        n_planes=4, sats_per_plane=10, phasing_deg=5.0, long_asc_deg=90,
        inclination_deg=60, perigee_alt_km=1200, apogee_alt_km=1200
    )

    # Configure the MSS D2D system parameters
    params = ParametersMssD2d(
        name="Example-MSS-D2D",
        antenna_pattern="ITU-R-S.1528-Taylor",
        orbits=[orbit_1, orbit_2],
        frequency=2100,
        bandwidth=5
    )

    params.antenna_s1528.antenna_gain = 30.0

    params.sat_is_active_if.conditions = [
        "LAT_LONG_INSIDE_COUNTRY",
        "MINIMUM_ELEVATION_FROM_ES",
    ]
    params.sat_is_active_if.minimum_elevation_from_es = 5
    # params.sat_is_active_if.lat_long_inside_country.country_name = "Colombia"
    params.sat_is_active_if.lat_long_inside_country.margin_from_border = 0
    # params.sat_is_active_if.lat_long_inside_country.margin_from_border = 0
    params.sat_is_active_if.lat_long_inside_country.country_names = ["Brazil"]

    params.propagate_parameters()

    # Create a topology with a single base station
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation
    imt_topology = TopologySingleBaseStation(
        cell_radius=500, num_clusters=1
    )

    # Create a random number generator
    rng = np.random.RandomState(seed=42)

    # Number of iterations (drops)
    NUM_DROPS = 100

    # Lists to store satellite positions (all and visible)
    all_positions = {'x': [], 'y': [], 'z': []}
    visible_positions = {'x': [], 'y': [], 'z': []}

    # Plot the ground station (blue marker)
    # ground_sta_pos = lla2ecef(sys_lat, sys_long, sys_alt)
    ground_sta_pos = geoconv.convert_lla_to_transformed_cartesian(
        sys_lat, sys_long, 1200.0)

    center_of_earth = StationManager(1)
    # rotated and then translated center of earth
    center_of_earth.x = np.array([0.0])
    center_of_earth.y = np.array([0.0])
    center_of_earth.z = np.array([-geoconv.get_translation()])

    vis_elevation = []
    for _ in range(NUM_DROPS):
        # Generate satellite positions using the StationFactory
        mss_d2d_manager = StationFactory.generate_mss_d2d(params, rng, geoconv)

        # Extract satellite positions
        x_vec = mss_d2d_manager.x / 1e3  # (Km)
        y_vec = mss_d2d_manager.y / 1e3  # (Km)
        z_vec = mss_d2d_manager.z / 1e3  # (Km)
        # Store all positions
        all_positions['x'].extend(x_vec)
        all_positions['y'].extend(y_vec)
        all_positions['z'].extend(z_vec)

        # Identify visible satellites
        vis_sat_idxs = np.where(mss_d2d_manager.active)[0]

        # should be pointing at nadir
        off_axis = mss_d2d_manager.get_off_axis_angle(center_of_earth)

        visible_positions['x'].extend(x_vec[vis_sat_idxs])
        visible_positions['y'].extend(y_vec[vis_sat_idxs])
        visible_positions['z'].extend(z_vec[vis_sat_idxs])
        vis_elevation.extend(mss_d2d_manager.elevation[vis_sat_idxs])

    # Flatten arrays
    all_positions['x'] = np.concatenate([all_positions['x']])
    all_positions['y'] = np.concatenate([all_positions['y']])
    all_positions['z'] = np.concatenate([all_positions['z']])

    visible_positions['x'] = np.concatenate([visible_positions['x']])
    visible_positions['y'] = np.concatenate([visible_positions['y']])
    visible_positions['z'] = np.concatenate([visible_positions['z']])

    # Plot the globe with satellite positions
    fig = plot_globe_with_borders(
        True, geoconv, True
    )

    # Plot all satellites (red markers)
    print("adding sats")
    fig.add_trace(go.Scatter3d(
        x=all_positions['x'],
        y=all_positions['y'],
        z=all_positions['z'],
        mode='markers',
        marker=dict(size=2, color='red', opacity=0.5),
        showlegend=False
    ))

    # Plot visible satellites (green markers)
    # print(visible_positions['x'][visible_positions['x'] > 0])
    # print("vis_elevation", vis_elevation)
    fig.add_trace(go.Scatter3d(
        x=visible_positions['x'],
        y=visible_positions['y'],
        z=visible_positions['z'],
        mode='markers',
        marker=dict(size=3, color='green', opacity=0.8),
        showlegend=False
    ))

    fig.add_trace(go.Scatter3d(
        x=[ground_sta_pos[0] / 1e3],
        y=[ground_sta_pos[1] / 1e3],
        z=[ground_sta_pos[2] / 1e3],
        mode='markers',
        marker=dict(size=5, color='blue', opacity=1.0),
        showlegend=False
    ))

    # fig.add_trace(go.Scatter3d(
    #     x=center_of_earth.x / 1e3,
    #     y=center_of_earth.y / 1e3,
    #     z=center_of_earth.z / 1e3,
    #     mode='markers',
    #     marker=dict(size=5, color='black', opacity=1.0),
    #     showlegend=False
    # ))

    # Display the plot
    print(len(fig.data))
    fig.show()
