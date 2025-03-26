# Generates a 3D plot of the Earth with the satellites positions
# https://geopandas.org/en/stable/docs/user_guide/io.html
import os
import geopandas as gpd
import numpy as np
import plotly.graph_objects as go

from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.satellite.utils.sat_utils import calc_elevation, lla2ecef
from sharc.satellite.ngso.constants import EARTH_RADIUS_KM


def plot_back(fig):
    """back half of sphere"""
    clor = 'rgb(220, 220, 220)'
    R = np.sqrt(EARTH_RADIUS_KM)
    u_angle = np.linspace(0, np.pi, 25)
    v_angle = np.linspace(0, np.pi, 25)
    x_dir = np.outer(R * np.cos(u_angle), R * np.sin(v_angle))
    y_dir = np.outer(R * np.sin(u_angle), R * np.sin(v_angle))
    z_dir = np.outer(R * np.ones(u_angle.shape[0]), R * np.cos(v_angle))
    fig.add_surface(z=z_dir, x=x_dir, y=y_dir, colorscale=[[0, clor], [1, clor]],
                    opacity=1.0, showlegend=False, lighting=dict(
                    # opacity=fig.sphere_alpha, colorscale=[[0, fig.sphere_color], [1, fig.sphere_color]])
                    diffuse=0.1))


def plot_front(fig):
    """front half of sphere"""
    clor = 'rgb(220, 220, 220)'
    R = np.sqrt(EARTH_RADIUS_KM)
    u_angle = np.linspace(-np.pi, 0, 25)
    v_angle = np.linspace(0, np.pi, 25)
    x_dir = np.outer(R * np.cos(u_angle), R * np.sin(v_angle))
    y_dir = np.outer(R * np.sin(u_angle), R * np.sin(v_angle))
    z_dir = np.outer(R * np.ones(u_angle.shape[0]), R * np.cos(v_angle))
    fig.add_surface(z=z_dir, x=x_dir, y=y_dir, colorscale=[[0, clor], [1, clor]], opacity=1.0, showlegend=False,
                    lighting=dict(
                        # opacity=fig.sphere_alpha, colorscale=[[0, fig.sphere_color], [1, fig.sphere_color]])
                        diffuse=0.1))


def plot_polygon(poly):

    xy_coords = poly.exterior.coords.xy
    lon = np.array(xy_coords[0])
    lat = np.array(xy_coords[1])

    lon = lon * np.pi / 180
    lat = lat * np.pi / 180

    R = EARTH_RADIUS_KM
    x = R * np.cos(lat) * np.cos(lon)
    y = R * np.cos(lat) * np.sin(lon)
    z = R * np.sin(lat)

    return x, y, z


def plot_globe_with_borders():
    # Read the shapefile.  Creates a DataFrame object
    countries_borders_shp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "../data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")
    gdf = gpd.read_file(countries_borders_shp_file)
    fig = go.Figure()
    plot_front(fig)
    plot_back(fig)

    for i in gdf.index:
        # print(gdf.loc[i].NAME)            # Call a specific attribute

        polys = gdf.loc[i].geometry         # Polygons or MultiPolygons

        if polys.geom_type == 'Polygon':
            x, y, z = plot_polygon(polys)
            fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode='lines',
                                       line=dict(color='rgb(0, 0,0)'), showlegend=False))

        elif polys.geom_type == 'MultiPolygon':

            for poly in polys.geoms:
                x, y, z = plot_polygon(poly)
                fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode='lines',
                                           line=dict(color='rgb(0, 0,0)'), showlegend=False))
    return fig


if __name__ == "__main__":

    # Plot Global Star orbit using OrbitModel object
    orbit = OrbitModel(
        Nsp=6,  # number of sats per plane
        Np=8,  # number of planes
        phasing=7.5,  # phasing in degrees
        long_asc=0,  # longitude of the ascending node in degrees
        omega=0,  # argument of perigee in degrees
        delta=52,  # inclination in degrees
        hp=1414,  # perigee altitude in km
        ha=1414,  # apogee altitude in km
        Mo=0  # mean anomaly in degrees
    )

    # Plot satellite traces from a time interval
    fig = plot_globe_with_borders()
    pos_vec = orbit.get_satellite_positions_time_interval(initial_time_secs=0, interval_secs=5, n_periods=1)
    # pos_vec = orbit.get_orbit_positions_time_instant()
    fig.add_trace(go.Scatter3d(x=pos_vec['sx'].flatten(),
                               y=pos_vec['sy'].flatten(),
                               z=pos_vec['sz'].flatten(),
                               mode='lines',
                               showlegend=False))

    fig.show()

    # Plot satellites positions taken randomly
    fig = plot_globe_with_borders()
    NUM_DROPS = 100
    rng = np.random.RandomState(seed=6)
    acc_pos = {'x': list(), 'y': list(), 'z': list()}
    for i in range(NUM_DROPS):
        pos_vec = orbit.get_orbit_positions_random_time(rng=rng)
        acc_pos['x'].extend(pos_vec['sx'].flatten())
        acc_pos['y'].extend(pos_vec['sy'].flatten())
        acc_pos['z'].extend(pos_vec['sz'].flatten())

    fig.add_trace(go.Scatter3d(x=acc_pos['x'],
                               y=acc_pos['y'],
                               z=acc_pos['z'],
                               mode='markers',
                               marker=dict(size=2,
                                           color='red',
                                           opacity=0.8),
                               showlegend=False))
    fig.show()

    # Show visible satellites from ground-station
    GROUND_STA_LAT = -15.7801
    GROUND_STA_LON = -42.9292
    MIN_ELEV_ANGLE_DEG = 5.0
    fig = plot_globe_with_borders()
    pos_vec = orbit.get_satellite_positions_time_interval()
    num_of_visible_sats_per_drop = []
    elevation_angles_per_drop = []
    NUM_DROPS = 1000
    rng = np.random.RandomState(seed=6)
    acc_pos = {'x': list(), 'y': list(), 'z': list(), 'lat': list(), 'lon': list()}
    for i in range(NUM_DROPS):
        pos_vec = orbit.get_orbit_positions_random_time(rng=rng)
        acc_pos['x'].extend(pos_vec['sx'].flatten())
        acc_pos['y'].extend(pos_vec['sy'].flatten())
        acc_pos['z'].extend(pos_vec['sz'].flatten())
        acc_pos['lat'].extend(pos_vec['lat'].flatten())
        acc_pos['lon'].extend(pos_vec['lon'].flatten())
        elev_angles = calc_elevation(GROUND_STA_LAT, pos_vec['lat'].flatten(), GROUND_STA_LON,
                                     pos_vec['lon'].flatten(), 1414.0)
        elevation_angles_per_drop.append(elev_angles[np.where(np.array(elev_angles) > 0)])
        vis_sats = np.where(np.array(elev_angles) > MIN_ELEV_ANGLE_DEG)[0]
        num_of_visible_sats_per_drop.append(len(vis_sats))

    # plot all satellites in drops
    fig.add_trace(go.Scatter3d(x=acc_pos['x'],
                               y=acc_pos['y'],
                               z=acc_pos['z'],
                               mode='markers',
                               marker=dict(size=2,
                                           color='red',
                                           opacity=0.8),
                               showlegend=False))

    lookangles = calc_elevation(GROUND_STA_LAT, acc_pos['lat'], GROUND_STA_LON, acc_pos['lon'], 1414.0)
    vis_sat_idxs = np.where(lookangles > MIN_ELEV_ANGLE_DEG)[0]

    # plot visible satellites
    fig.add_trace(go.Scatter3d(
        x=np.array(acc_pos['x'])[vis_sat_idxs],
        y=np.array(acc_pos['y'])[vis_sat_idxs],
        z=np.array(acc_pos['z'])[vis_sat_idxs],
        mode='markers',
        marker=dict(size=2,
                    color='green',
                    opacity=0.8),
        showlegend=False))

    # plot ground station
    groud_sta_pos = lla2ecef(GROUND_STA_LAT, GROUND_STA_LON, 0.0)
    fig.add_trace(go.Scatter3d(
        x=np.array(groud_sta_pos[0] / 1),
        y=np.array(groud_sta_pos[1] / 1),
        z=np.array(groud_sta_pos[2] / 1),
        mode='markers',
        marker=dict(size=4,
                    color='blue',
                    opacity=1.0),
        showlegend=False))

    fig.show()

    # plot histogram of visible satellites
    fig = go.Figure(data=[go.Histogram(x=num_of_visible_sats_per_drop,
                                       histnorm='probability', xbins=dict(start=-0.5, size=1))])
    fig.update_layout(
        title_text='Visible satellites per drop',
        xaxis_title_text='Num of visible satellites',
        yaxis_title_text='Percentage',
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
        yaxis_title_text='Percentage',
        bargap=0.2,
        bargroupgap=0.1,
        # xaxis=dict(
        #     tickmode='linear',
        #     tick0=0,
        #     dtick=5
        # )
    )
    fig.show()
