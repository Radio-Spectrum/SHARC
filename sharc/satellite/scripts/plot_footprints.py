# Generates a 3D plot of the Earth with the satellites positions
# https://geopandas.org/en/stable/docs/user_guide/io.html
import os
import geopandas as gpd
import numpy as np
import plotly.graph_objects as go

from sharc.station_factory import StationFactory
from sharc.parameters.parameters_mss_d2d import ParametersOrbit, ParametersMssD2d
from sharc.support.sharc_geom import GeometryConverter
from sharc.satellite.utils.sat_utils import ecef2lla
from sharc.station_manager import StationManager
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528


geoconv = GeometryConverter()

sys_lat = -14.5
sys_long = -45
sys_alt = 1200

geoconv.set_reference(
    sys_lat, sys_long, sys_alt
)


def plot_back(fig):
    """back half of sphere"""
    clor = 'rgb(220, 220, 220)'
    # Create a mesh grid for latitude and longitude.
    # For the "front" half, we can use longitudes from -180 to 0 degrees.
    # 50 latitude points from -90 to 90 degrees.
    lat_vals = np.linspace(-90, 90, 50)
    # 50 longitude points for the front half.
    lon_vals = np.linspace(0, 180, 50)
    # lon and lat will be 2D arrays.
    lon, lat = np.meshgrid(lon_vals, lat_vals)

    # Flatten the mesh to pass to the converter function.
    lat_flat = lat.flatten()
    lon_flat = lon.flatten()

    # Convert the lat/lon grid to transformed Cartesian coordinates.
    # Ensure your converter function can handle vectorized (numpy array) inputs.
    x_flat, y_flat, z_flat = geoconv.convert_lla_to_transformed_cartesian(
        lat_flat, lon_flat, 0)

    # Reshape the converted coordinates back to the 2D grid shape.
    x = x_flat.reshape(lat.shape)
    y = y_flat.reshape(lat.shape)
    z = z_flat.reshape(lat.shape)

    # Add the surface to the Plotly figure.
    fig.add_surface(
        x=x / 1e3, y=y / 1e3, z=z / 1e3,
        # Uniform color scale for a solid color.
        colorscale=[[0, clor], [1, clor]],
        opacity=1.0,
        showlegend=False,
        lighting=dict(diffuse=0.1)
    )


def plot_front(fig):
    """front half of sphere"""
    clor = 'rgb(220, 220, 220)'

    # Create a mesh grid for latitude and longitude.
    # For the "front" half, we can use longitudes from -180 to 0 degrees.
    # 50 latitude points from -90 to 90 degrees.
    lat_vals = np.linspace(-90, 90, 50)
    # 50 longitude points for the front half.
    lon_vals = np.linspace(-180, 0, 50)
    # lon and lat will be 2D arrays.
    lon, lat = np.meshgrid(lon_vals, lat_vals)

    # Flatten the mesh to pass to the converter function.
    lat_flat = lat.flatten()
    lon_flat = lon.flatten()

    # Convert the lat/lon grid to transformed Cartesian coordinates.
    # Ensure your converter function can handle vectorized (numpy array) inputs.
    x_flat, y_flat, z_flat = geoconv.convert_lla_to_transformed_cartesian(
        lat_flat, lon_flat, 0)

    # Reshape the converted coordinates back to the 2D grid shape.
    x = x_flat.reshape(lat.shape)
    y = y_flat.reshape(lat.shape)
    z = z_flat.reshape(lat.shape)

    # Add the surface to the Plotly figure.
    fig.add_surface(
        x=x / 1e3, y=y / 1e3, z=z / 1e3,
        # Uniform color scale for a solid color.
        colorscale=[[0, clor], [1, clor]],
        opacity=1.0,
        showlegend=False,
        lighting=dict(diffuse=0.1)
    )


def plot_polygon(poly):

    xy_coords = poly.exterior.coords.xy
    lon = np.array(xy_coords[0])
    lat = np.array(xy_coords[1])

    # lon = lon * np.pi / 180
    # lat = lat * np.pi / 180

    # R = EARTH_RADIUS_KM
    x, y, z = geoconv.convert_lla_to_transformed_cartesian(lat, lon, 0)

    return x, y, z


def plot_globe_with_borders():
    # Read the shapefile.  Creates a DataFrame object
    countries_borders_shp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "../data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")
    gdf = gpd.read_file(countries_borders_shp_file)
    fig = go.Figure()
    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis=dict(showbackground=False),
            yaxis=dict(showbackground=False),
            zaxis=dict(showbackground=False)
        ),
        margin=dict(l=0, r=0, b=0, t=0)
    )
    # return fig
    plot_front(fig)
    plot_back(fig)
    x_all, y_all, z_all = [], [], []

    for i in gdf.index:
        # print(gdf.loc[i].NAME)            # Call a specific attribute

        polys = gdf.loc[i].geometry         # Polygons or MultiPolygons

        if polys.geom_type == 'Polygon':
            x, y, z = plot_polygon(polys)
            x_all.extend(x/1e3)
            x_all.extend([None])  # None separates different polygons
            y_all.extend(y/1e3)
            y_all.extend([None])
            z_all.extend(z/1e3)
            z_all.extend([None])

        elif polys.geom_type == 'MultiPolygon':

            for poly in polys.geoms:
                x, y, z = plot_polygon(poly)
                x_all.extend(x/1e3)
                x_all.extend([None])  # None separates different polygons
                y_all.extend(y/1e3)
                y_all.extend([None])
                z_all.extend(z/1e3)
                z_all.extend([None])

    fig.add_trace(go.Scatter3d(x=x_all, y=y_all, z=z_all, mode='lines',
                               line=dict(color='rgb(0, 0, 0)'), showlegend=False))

    return fig


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

    # Antenna parameters
    g_max = 34.1  # dBi
    l_r = l_t = 1.6  # meters
    slr = 20  # dB
    n_side_lobes = 2  # number of side lobes
    freq = 2e3  # MHz

    antenna_params = ParametersAntennaS1528(
        antenna_gain=g_max,
        frequency=freq,  # in MHz
        bandwidth=5,  # in MHz
        slr=slr,
        n_side_lobes=n_side_lobes,
        l_r=l_r,
        l_t=l_t,
        roll_off=None
    )

    spotbeam_radius = 98.12 * 1e3  # meters

    # Configure the MSS D2D system parameters
    params = ParametersMssD2d(
        name="Example-MSS-D2D",
        antenna_pattern="ITU-R-S.1528-Taylor",
        num_sectors=19,
        antenna_gain=g_max,
        antenna_s1528=antenna_params,
        intersite_distance=np.sqrt(3) * spotbeam_radius,
        orbits=[orbit_1, orbit_2]
    )

    # Create a topology with a single base station
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation
    imt_topology = TopologySingleBaseStation(
        cell_radius=500, num_clusters=1
    )

    # Create a random number generator
    rng = np.random.RandomState(seed=42)

    # Number of iterations (drops)
    NUM_DROPS = 128

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
    managers = []
    options = []
    for drop in range(NUM_DROPS):
        # Generate satellite positions using the StationFactory
        mss_d2d_manager = StationFactory.generate_mss_d2d(params, rng, geoconv)
        managers.append(mss_d2d_manager)

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

        options.extend([(drop, i, len(visible_positions['x'])+i)
                       for i, idx in enumerate(vis_sat_idxs)])

        # should be pointing at nadir
        off_axis = mss_d2d_manager.get_off_axis_angle(center_of_earth)
        if len(np.where(off_axis > 0.01)[0]):
            print("AOPA, off axis parece estar errado")
            print("onde?: ", np.where(off_axis > 0.01))

        visible_positions['x'].extend(x_vec[vis_sat_idxs])
        visible_positions['y'].extend(y_vec[vis_sat_idxs])
        visible_positions['z'].extend(z_vec[vis_sat_idxs])
        vis_elevation.extend(mss_d2d_manager.elevation[vis_sat_idxs])
    print("options", options)
    print("len(options)", len(options))
    select_i = 656
    station_1 = managers[options[select_i][0]]
    mss_active = np.where(station_1.active)[0]
    # consider satellite footprint
    mss_to_consider = mss_active[options[select_i][1]]

    # Flatten arrays
    # print(all_positions['x'])
    all_positions['x'] = np.concatenate([all_positions['x']])
    all_positions['y'] = np.concatenate([all_positions['y']])
    all_positions['z'] = np.concatenate([all_positions['z']])

    visible_positions['x'] = np.concatenate([visible_positions['x']])
    visible_positions['y'] = np.concatenate([visible_positions['y']])
    visible_positions['z'] = np.concatenate([visible_positions['z']])

    orx, ory, orz = geoconv.revert_transformed_cartesian_to_cartesian(
        station_1.x[mss_to_consider],
        station_1.y[mss_to_consider],
        station_1.z[mss_to_consider],
    )
    sat_lat, sat_long, sat_alt = ecef2lla(orx, ory, orz)
    # Plot the globe with satellite positions
    fig = plot_globe_with_borders()

    scale = 0.5 / np.sqrt(visible_positions['x'][options[select_i][2]]**2 +
                          visible_positions['y'][options[select_i][2]]**2 +
                          visible_positions['z'][options[select_i][2]]**2)
    eye = dict(
        # x=0,
        # y=0,
        # z=0
        x=visible_positions['x'][options[select_i][2]] * scale,
        y=visible_positions['y'][options[select_i][2]] * scale,
        z=visible_positions['z'][options[select_i][2]] * scale
    )
    print("eye", eye)

    # Set the camera position in Plotly
    # print(center_of_earth.z[0])
    # fig.update_layout(
    #     scene=dict(
    #         zaxis=dict(
    #             range=(-1400, 10000-1400)
    #         ),
    #         yaxis=dict(
    #             range=(-5000, 5000)
    #         ),
    #         xaxis=dict(
    #             range=(-5000, 5000)
    #         ),
    #         camera=dict(
    #             eye=eye,   # Camera position
    #             center=dict(x=0, y=0, z=center_of_earth.z[0]/1e3/10000),  # Look at Earth's center
    #             # center=dict(x=0, y=0, z=0),  # Look at Earth's center
    #             # up=dict(x=0, y=0, z=1)  # Ensure the up direction is correct
    #         )
    #     )
    # )

    # 50 latitude points from -90 to 90 degrees.
    lat_vals = np.linspace(sat_lat - 5.0, sat_lat + 5.0, 50)
    # 50 longitude points for the front half.
    lon_vals = np.linspace(sat_long - 5.0, sat_long + 5.0, 50)
    # lon and lat will be 2D arrays.
    lon, lat = np.meshgrid(lon_vals, lat_vals)

    # Flatten the mesh to pass to the converter function.
    lat_flat = lat.flatten()
    lon_flat = lon.flatten()

    # Convert the lat/lon grid to transformed Cartesian coordinates.
    # Ensure your converter function can handle vectorized (numpy array) inputs.
    x_flat, y_flat, z_flat = geoconv.convert_lla_to_transformed_cartesian(lat_flat, lon_flat, 0)

    surf_manager = StationManager(len(x_flat))
    surf_manager.x = x_flat
    surf_manager.y = y_flat
    surf_manager.z = z_flat
    surf_manager.height = z_flat

    station_2 = surf_manager
    station_2_active = np.where(station_2.active)[0]

    # Calculate vector and apointment off_axis
    phi, theta = station_1.get_pointing_vector_to(station_2)
    off_axis_angle = station_1.get_off_axis_angle(station_2)

    world_surf_x = x_flat.reshape(lat.shape)
    world_surf_y = y_flat.reshape(lat.shape)
    world_surf_z = z_flat.reshape(lat.shape)

    clor = 'rgb(220, 220, 220)'

    for k in mss_active:
        gain_k = station_1.antenna[k].calculate_gain(
            off_axis_angle_vec=off_axis_angle[k, station_2_active],
            theta_vec=theta[k, station_2_active],
            phi_vec=phi[k, station_2_active],
        )

        lin_gain_k = 10 ** (gain_k / 10)
        reshaped_gain_k = lin_gain_k.reshape(lat.shape)
        # lin_gains = gains
        # print("lin_gains")
        # print(lin_gains)
        # print(mss_active)
        # print("considering ", mss_to_consider)
        # print("considering z", station_1.z[mss_to_consider])


        fig.add_surface(
            x=world_surf_x / 1e3,
            y=world_surf_y / 1e3,
            z=world_surf_z / 1e3,
            surfacecolor=reshaped_gain_k,
            colorscale=[[0, clor], [0.1, "blue"], [1, "red"]],
            opacity=0.6, 
            showlegend=False,
            lighting=dict(diffuse=0.1),
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