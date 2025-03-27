# Generates a 3D plot of the Earth with the satellites positions
# https://geopandas.org/en/stable/docs/user_guide/io.html
import os
import geopandas as gpd
import numpy as np
import plotly.graph_objects as go

from sharc.support.sharc_geom import GeometryConverter
from sharc.station_manager import StationManager
from sharc.parameters.parameters import Parameters
from sharc.topology.topology_factory import TopologyFactory
from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.satellite.utils.sat_utils import calc_elevation, lla2ecef
from sharc.satellite.ngso.constants import EARTH_RADIUS_KM
from sharc.parameters.parameters_mss_d2d import ParametersOrbit, ParametersMssD2d
from sharc.station_factory import StationFactory


def plot_back(fig, geoconv):
    """back half of sphere"""
    clor = 'rgb(220, 220, 220)'
    # Create a mesh grid for latitude and longitude.
    # For the "front" half, we can use longitudes from -180 to 0 degrees.
    lat_vals = np.linspace(-90, 90, 50)       # 50 latitude points from -90 to 90 degrees.
    lon_vals = np.linspace(0, 180, 50)         # 50 longitude points for the front half.
    lon, lat = np.meshgrid(lon_vals, lat_vals)  # lon and lat will be 2D arrays.

    # Flatten the mesh to pass to the converter function.
    lat_flat = lat.flatten()
    lon_flat = lon.flatten()

    # Convert the lat/lon grid to transformed Cartesian coordinates.
    # Ensure your converter function can handle vectorized (numpy array) inputs.
    x_flat, y_flat, z_flat = geoconv.convert_lla_to_transformed_cartesian(lat_flat, lon_flat, 0)

    # Reshape the converted coordinates back to the 2D grid shape.
    x = x_flat.reshape(lat.shape)
    y = y_flat.reshape(lat.shape)
    z = z_flat.reshape(lat.shape)

    # Add the surface to the Plotly figure.
    fig.add_surface(
        x=x, y=y, z=z,
        colorscale=[[0, clor], [1, clor]],  # Uniform color scale for a solid color.
        opacity=1.0,
        showlegend=False,
        lighting=dict(diffuse=0.1)
    )


def plot_front(fig, geoconv):
    """front half of sphere"""
    clor = 'rgb(220, 220, 220)'

    # Create a mesh grid for latitude and longitude.
    # For the "front" half, we can use longitudes from -180 to 0 degrees.
    lat_vals = np.linspace(-90, 90, 50)       # 50 latitude points from -90 to 90 degrees.
    lon_vals = np.linspace(-180, 0, 50)         # 50 longitude points for the front half.
    lon, lat = np.meshgrid(lon_vals, lat_vals)  # lon and lat will be 2D arrays.

    # Flatten the mesh to pass to the converter function.
    lat_flat = lat.flatten()
    lon_flat = lon.flatten()

    # Convert the lat/lon grid to transformed Cartesian coordinates.
    # Ensure your converter function can handle vectorized (numpy array) inputs.
    x_flat, y_flat, z_flat = geoconv.convert_lla_to_transformed_cartesian(lat_flat, lon_flat, 0)

    # Reshape the converted coordinates back to the 2D grid shape.
    x = x_flat.reshape(lat.shape)
    y = y_flat.reshape(lat.shape)
    z = z_flat.reshape(lat.shape)

    # Add the surface to the Plotly figure.
    fig.add_surface(
        x=x, y=y, z=z,
        colorscale=[[0, clor], [1, clor]],  # Uniform color scale for a solid color.
        opacity=1.0,
        showlegend=False,
        lighting=dict(diffuse=0.1)
    )

def plot_polygon(poly, geoconv):

    xy_coords = poly.exterior.coords.xy
    lon = np.array(xy_coords[0])
    lat = np.array(xy_coords[1])

    # lon = lon * np.pi / 180
    # lat = lat * np.pi / 180

    # R = EARTH_RADIUS_KM
    x, y, z = geoconv.convert_lla_to_transformed_cartesian(lat, lon, 0)

    return x, y, z


def plot_globe_with_borders(opaque_globe: bool, geoconv):
    # Read the shapefile.  Creates a DataFrame object
    countries_borders_shp_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "../data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")
    gdf = gpd.read_file(countries_borders_shp_file)
    fig = go.Figure()
    # fig.update_layout(
    #     scene=dict(
    #         aspectmode="data",
    #         xaxis=dict(showbackground=False),
    #         yaxis=dict(showbackground=False),
    #         zaxis=dict(showbackground=False)
    #     ),
    #     margin=dict(l=0, r=0, b=0, t=0)
    # )
    if opaque_globe:
        plot_front(fig, geoconv)
        plot_back(fig, geoconv)
    x_all, y_all, z_all = [], [], []

    for i in gdf.index:
        # print(gdf.loc[i].NAME)            # Call a specific attribute

        polys = gdf.loc[i].geometry         # Polygons or MultiPolygons

        if polys.geom_type == 'Polygon':
            x, y, z = plot_polygon(polys, geoconv)
            x_all.extend(x)
            x_all.extend([None])  # None separates different polygons
            y_all.extend(y)
            y_all.extend([None])
            z_all.extend(z)
            z_all.extend([None])

        elif polys.geom_type == 'MultiPolygon':

            for poly in polys.geoms:
                x, y, z = plot_polygon(poly, geoconv)
                x_all.extend(x)
                x_all.extend([None])  # None separates different polygons
                y_all.extend(y)
                y_all.extend([None])
                z_all.extend(z)
                z_all.extend([None])

    fig.add_trace(go.Scatter3d(x=x_all, y=y_all, z=z_all, mode='lines',
                               line=dict(color='rgb(0, 0, 0)'), showlegend=False))

    return fig

if __name__ == "__main__":
    geoconv = GeometryConverter()
    SELECTED_SNAPSHOT_NUMBER = 0
    OPAQUE_GLOBE = True

    param_file = "sharc/campaigns/mss_d2d_to_imt/input/parameters_mss_d2d_to_imt_co_channel_system_A.yaml"
    parameters = Parameters()
    parameters.set_file_name(param_file)
    parameters.read_params()

    geoconv.set_reference(
        parameters.imt.topology.central_latitude,
        parameters.imt.topology.central_longitude,
        parameters.imt.topology.central_altitude,
    )

    import random
    random.seed(parameters.general.seed)

    secondary_seeds = [None] * parameters.general.num_snapshots

    max_seed = 2**32 - 1

    for index in range(parameters.general.num_snapshots):
        secondary_seeds[index] = random.randint(1, max_seed)

    seed = secondary_seeds[SELECTED_SNAPSHOT_NUMBER]

    topology = TopologyFactory.createTopology(parameters)

    random_number_gen = np.random.RandomState(seed)

    # In case of hotspots, base stations coordinates have to be calculated
    # on every snapshot. Anyway, let topology decide whether to calculate
    # or not
    topology.calculate_coordinates(random_number_gen)

    # Create the base stations (remember that it takes into account the
    # network load factor)
    bs = StationFactory.generate_imt_base_stations(
        parameters.imt,
        parameters.imt.bs.antenna,
        topology, random_number_gen,
    )

    # Create the other system (FSS, HAPS, etc...)
    system = StationFactory.generate_system(
        parameters, topology, random_number_gen,
    )

    # Create IMT user equipments
    ue = StationFactory.generate_imt_ue(
        parameters.imt,
        parameters.imt.ue.antenna,
        topology, random_number_gen,
    )

    # Plot the globe with satellite positions
    fig = plot_globe_with_borders(OPAQUE_GLOBE, geoconv)

    # Plot all satellites (red markers)
    fig.add_trace(go.Scatter3d(
        x=system.x ,
        y=system.y ,
        z=system.z ,
        mode='markers',
        marker=dict(size=2, color='red', opacity=0.5),
        showlegend=False
    ))

    # Plot visible satellites (green markers)
    # print(visible_positions['x'][visible_positions['x'] > 0])
    # print("vis_elevation", vis_elevation)
    fig.add_trace(go.Scatter3d(
        x=system.x[system.active] ,
        y=system.y[system.active] ,
        z=system.z[system.active] ,
        mode='markers',
        marker=dict(size=3, color='green', opacity=0.8),
        showlegend=False
    ))

    
    fig.add_trace(go.Scatter3d(
        x=ue.x ,
        y=ue.y ,
        z=ue.z ,
        mode='markers',
        marker=dict(size=4, color='blue', opacity=1.0),
        showlegend=False
    ))

    fig.add_trace(go.Scatter3d(
        x=bs.x ,
        y=bs.y ,
        z=bs.z ,
        mode='markers',
        marker=dict(size=4, color='black', opacity=1.0),
        showlegend=False
    ))

    # Display the plot
    fig.update_layout(
        scene=dict(
            zaxis=dict(
                range=(-1e3*5000, 1e3*5000)
            ),
            yaxis=dict(
                range=(-1e3*5000, 1e3*5000)
            ),
            xaxis=dict(
                range=(-1e3*5000, 1e3*5000)
            ),
            # camera=dict(
            #     eye=eye,   # Camera position
            #     center=dict(x=0, y=0, z=center_of_earth.z[0]/1e3/10000),  # Look at Earth's center
            #     # center=dict(x=0, y=0, z=0),  # Look at Earth's center
            #     # up=dict(x=0, y=0, z=1)  # Ensure the up direction is correct
            # )
        )
    )
    print(
        "system.x[system.active]", system.x[system.active] ,
    )
    print(
        "system.y[system.active]", system.y[system.active] ,
    )
    print(
        "system.z[system.active]", system.z[system.active] ,
    )
    fig.show()




