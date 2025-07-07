"""
Script to generate a 3D plot of the Earth with satellite positions and footprints.

This module uses plotly to visualize satellite footprints and related data for SHARC simulations.
"""
import numpy as np
import plotly.graph_objects as go
from dataclasses import dataclass, field

from sharc.station_factory import StationFactory
from sharc.parameters.parameters_mss_d2d import ParametersOrbit, ParametersMssD2d
from sharc.support.sharc_geom import GeometryConverter
from sharc.satellite.utils.sat_utils import ecef2lla
from sharc.station_manager import StationManager
from sharc.parameters.antenna.parameters_antenna_s1528 import ParametersAntennaS1528
from sharc.satellite.scripts.plot_globe import plot_globe_with_borders, plot_mult_polygon


@dataclass
class FootPrintOpts:
    """
    Options for configuring the satellite footprint plotting, including color, resolution, and gain calculation settings.
    """
    # choose a seed to use for getting the satellites
    # if seed is different, different random numbers are taken
    seed: int

    # steps from previous section
    # e.g. [3, 3, x] means that 1st clr will be for 0 to -3 dB, 2nd for -3 to -6dB and 3rd for < -6dB
    # from normalized gains
    # FIXME: at the moment the last step is ignored
    step: list[float] = field(default_factory=lambda: [3, 4, 14])  # dB

    # colors to be used for each step
    colors: list[str] = field(default_factory=lambda: ['#fff7ec', '#fee8c8', '#fdd49e', '#fdbb84', '#fc8d59', '#7f0000'])

    # choose if colors appear continuously or in discrete steps
    discretize: bool = True

    # choose if a surface point received gain should be all sat gains summed
    # or if only max gain will be considered
    sum_gains: bool = False

    # if using service grid, you may choose for it to appear on the plot
    show_service_grid_if_possible: bool = False

    # number of horizontal and vertical divisions for footprint
    resolution: int = 100


def plot_fp(
    params,
    geoconv,
    opts=FootPrintOpts(seed=32)
):
    """
    Generate a 3D plot of the Earth with satellite positions and their footprints.

    Args:
        params: Parameters for the MSS D2D system.
        geoconv: GeometryConverter instance for coordinate transformations.
        opts: FootPrintOpts instance with plotting options.

    Returns:
        plotly.graph_objects.Figure: The generated 3D plot.
    """
    colors = opts.colors
    step = opts.step
    seed = opts.seed
    discretize = opts.discretize
    sum_gains = opts.sum_gains
    show_service_grid_if_possible = opts.show_service_grid_if_possible
    resolution = opts.resolution

    print("instantiating stations")
    # Create a topology with a single base station
    from sharc.topology.topology_single_base_station import TopologySingleBaseStation

    # Create a random number generator
    rng = np.random.RandomState(seed=seed)

    center_of_earth = StationManager(1)
    # rotated and then translated center of earth
    center_of_earth.x = np.array([0.0])
    center_of_earth.y = np.array([0.0])
    center_of_earth.z = np.array([-geoconv.get_translation()])

    mss_d2d_manager = StationFactory.generate_mss_d2d(params, rng, geoconv)

    # Plot the globe with satellite positions
    fig = plot_globe_with_borders(
        True, geoconv, True
    )

    # Set the camera position in Plotly
    show_range = 1e4
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        scene=dict(
            zaxis=dict(
                range=(-show_range / 2, show_range / 2)
            ),
            yaxis=dict(
                range=(-show_range / 2, show_range / 2)
            ),
            xaxis=dict(
                range=(-show_range / 2, show_range / 2)
            ),
            camera=dict(
                center=dict(x=0, y=0, z=center_of_earth.z[0] / show_range / 1e3),
                eye=dict(x=0, y=0, z=0.7),  # Eye position (above the center)
                up=dict(x=0, y=1, z=0)      # "Up" is along +y (default is usually +z)
            )
        ),
        legend=dict(
            x=0.02,        # Move to left
            y=0.02,        # Near top
            bgcolor='rgba(255,255,255,1)',  # Optional: semi-transparent background
            bordercolor='black',
            borderwidth=1
        ),
        # width=700,
        # height=700,
    )

    station_1 = mss_d2d_manager
    # Satellite as fp center
    center_fp_at_sat = 0
    # get original sat xyz
    orx, ory, orz = geoconv.revert_transformed_cartesian_to_cartesian(
        station_1.x[center_fp_at_sat],
        station_1.y[center_fp_at_sat],
        station_1.z[center_fp_at_sat],
    )
    sat_lat, sat_long, sat_alt = ecef2lla(orx, ory, orz)

    # lat_vals = np.linspace(sat_lat - 10.0, sat_lat + 10.0, resolution)
    # lon_vals = np.linspace(sat_long - 10.0, sat_long + 10.0, resolution)

    # # Ground station as fp center
    # lat_vals = np.linspace(geoconv.ref_lat, geoconv.ref_lat + 10.0, resolution)
    # lon_vals = np.linspace(geoconv.ref_long - 5.0, geoconv.ref_long + 5.0, resolution)

    # Arbitrary range for fp calulation
    lat_vals = np.linspace(-33.69111, 4, resolution)
    lon_vals = np.linspace(-74, -34.80861, resolution)

    # lon and lat will be 2D arrays.
    lon, lat = np.meshgrid(lon_vals, lat_vals)

    # Flatten the mesh to pass to the converter function.
    lat_flat = lat.flatten()
    lon_flat = lon.flatten()

    # Convert the lat/lon grid to transformed Cartesian coordinates.
    # Ensure your converter function can handle vectorized (numpy array) inputs.
    x_flat, y_flat, z_flat = geoconv.convert_lla_to_transformed_cartesian(lat_flat, lon_flat, 0)

    # creates a StationManager to calculate the gains on
    surf_manager = StationManager(len(x_flat))
    surf_manager.x = x_flat
    surf_manager.y = y_flat
    surf_manager.z = z_flat
    surf_manager.height = z_flat

    station_1 = mss_d2d_manager
    mss_active = np.where(station_1.active)[0]
    station_2 = surf_manager
    station_2_active = np.where(station_2.active)[0]

    print("Calculating gains (memory intensive)")
    # Calculate vector and apointment off_axis
    gains = np.zeros((len(mss_active), len(station_2_active)))
    off_axis_angle = station_1.get_off_axis_angle(station_2)
    phi, theta = station_1.get_pointing_vector_to(station_2)
    for k in range(len(mss_active)):
        gains[k, :] = \
            station_1.antenna[k].calculate_gain(
                off_axis_angle_vec=off_axis_angle[k, station_2_active],
                theta_vec=theta[k, station_2_active],
                phi_vec=phi[k, station_2_active],
        )

    if sum_gains:
        gains = 10 ** (gains / 10)
        gains = 10 * np.log10(np.sum(gains, axis=0))
    else:
        gains = np.max(gains, axis=0)

    world_surf_x = x_flat.reshape(lat.shape)
    world_surf_y = y_flat.reshape(lat.shape)
    world_surf_z = z_flat.reshape(lat.shape)
    reshaped_gain = gains.reshape(lat.shape)

    mx_gain = np.max(reshaped_gain)
    mn_gain = np.min(reshaped_gain)
    rnge = mx_gain - mn_gain
    n_steps = len(step) - 1
    colorscale = []
    bins = []
    at = 0
    offset = len(colors) - len(step)

    for i in range(0, n_steps + 1):
        ci = offset + i

        bins.append(mx_gain - at * rnge)
        at += step[i] / rnge

        if discretize and i / n_steps - 1 / n_steps / 2 > 0:
            colorscale.append([i / n_steps - 1 / n_steps / 2, "rgb(100,100,100)"])
            colorscale.append([i / n_steps - 1 / n_steps / 2 + 0.001, colors[ci]])
        colorscale.append([i / n_steps, colors[ci]])
        if discretize and i / n_steps + 1 / n_steps / 2 < 1.0:
            colorscale.append([i / n_steps + 1 / n_steps / 2 - 0.001, colors[ci]])
    # bins.append(mn_gain)
    bins.reverse()

    if discretize:
        # cumul_steps = np.cumsum(steps)
        surfacecolor = np.digitize(reshaped_gain, bins, right=True)
        colorbar = dict(
            tickmode='array',
            tickvals=np.arange(0, len(bins)),
            ticktext=[f"< {bins[0]:.2f} dB"] + [f"{bins[i]:.2f} to {bins[i + 1]:.2f} dB" for i in range(len(bins) - 1)],
            title="Gain (dB)"
        )
    else:
        surfacecolor = reshaped_gain
        colorbar = None

    fig.add_surface(
        x=world_surf_x / 1e3, y=world_surf_y / 1e3, z=world_surf_z / 1e3,
        surfacecolor=surfacecolor,
        # Uniform color scale for a solid color.
        colorscale=colorscale,
        opacity=1.0,
        showlegend=False,
        # lighting=dict(diffuse=0)
        colorbar=colorbar,
    )

    # Plot all satellites (red markers)
    print("adding sats")
    fig.add_trace(go.Scatter3d(
        x=mss_d2d_manager.x / 1e3,
        y=mss_d2d_manager.y / 1e3,
        z=mss_d2d_manager.z / 1e3,
        mode='markers',
        marker=dict(size=2, color='red', opacity=0.5),
        showlegend=False
    ))

    # Plot visible satellites (green markers)
    # print(visible_positions['x'][visible_positions['x'] > 0])
    fig.add_trace(go.Scatter3d(
        x=mss_d2d_manager.x[mss_d2d_manager.active] / 1e3,
        y=mss_d2d_manager.y[mss_d2d_manager.active] / 1e3,
        z=mss_d2d_manager.z[mss_d2d_manager.active] / 1e3,
        mode='markers',
        marker=dict(size=3, color='green', opacity=0.8),
        name="MSS D2D sat",
    ))

    fig.add_trace(go.Scatter3d(
        x=[0],
        y=[0],
        z=[10],
        mode='markers',
        marker=dict(size=5, color='red', opacity=1.0),
        name="Victim IMT TN",
    ))

    polygons_lim = plot_mult_polygon(
        params.sat_is_active_if.lat_long_inside_country.filter_polygon,
        geoconv,
        True,
        2
    )
    from functools import reduce

    lim_x, lim_y, lim_z = reduce(
        lambda acc, it: (list(it[0]) + [None] + acc[0], list(it[1]) + [None] + acc[1], list(it[2]) + [None] + acc[2]),
        polygons_lim,
        ([], [], [])
    )

    fig.add_trace(go.Scatter3d(
        x=lim_x,
        y=lim_y,
        z=lim_z,
        mode='lines',
        line=dict(color='rgb(0, 255, 0)'),
        name="Sat. active limits"
    ))

    if params.beam_positioning.type == "SERVICE_GRID" and show_service_grid_if_possible:
        print("adding service grid")
        print("N = ", len(params.beam_positioning.service_grid.lon_lat_grid[0]))
        xy_coords = params.beam_positioning.service_grid.lon_lat_grid
        lon = np.array(xy_coords[0])
        lat = np.array(xy_coords[1])

        x, y, z = geoconv.convert_lla_to_transformed_cartesian(lat, lon, 1e3)

        fig.add_trace(go.Scatter3d(
            x=x / 1e3,
            y=y / 1e3,
            z=z / 1e3,
            mode='markers',
            marker=dict(size=1, color='blue', opacity=1.0),
            name="Service Point"
        ))
    # fig.add_trace(go.Scatter3d(
    #     x=center_of_earth.x / 1e3,
    #     y=center_of_earth.y / 1e3,
    #     z=center_of_earth.z / 1e3,
    #     mode='markers',
    #     marker=dict(size=5, color='black', opacity=1.0),
    #     showlegend=False
    # ))

    return fig


if __name__ == "__main__":
    # Define the orbit parameters for two satellite constellations
    orbit_1 = ParametersOrbit(
        n_planes=28, sats_per_plane=120, phasing_deg=1.5, long_asc_deg=0,
        inclination_deg=53.0, perigee_alt_km=525.0, apogee_alt_km=525.0
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
        l_t=l_t
    )

    spotbeam_radius = 39475  # meters

    # Configure the MSS D2D system parameters
    params = ParametersMssD2d(
        name="Example-MSS-D2D",
        antenna_pattern="ITU-R-S.1528-Taylor",
        num_sectors=19,
        antenna_s1528=antenna_params,
        intersite_distance=np.sqrt(3) * spotbeam_radius,
        cell_radius=spotbeam_radius,
        orbits=[orbit_1]
    )
    params.sat_is_active_if.conditions = [
        # "MINIMUM_ELEVATION_FROM_ES",
        "LAT_LONG_INSIDE_COUNTRY",
    ]
    params.sat_is_active_if.minimum_elevation_from_es = 5.0
    params.sat_is_active_if.lat_long_inside_country.country_names = ["Brazil"]
    # params.beams_load_factor = 0.1
    params.beam_positioning.type = "SERVICE_GRID"
    # params.beam_positioning.type = "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE"
    # params.beam_positioning.angle_from_subsatellite_phi.type = "~U(MIN,MAX)"
    # params.beam_positioning.angle_from_subsatellite_phi.distribution.min = -60.0
    # params.beam_positioning.angle_from_subsatellite_phi.distribution.max = 60.0
    # params.beam_positioning.distance_from_subsatellite.type = "~SQRT(U(0,1))*MAX"
    # params.beam_positioning.distance_from_subsatellite.distribution.max = 1111000.0
    params.propagate_parameters()
    params.validate("opa")

    geoconv = GeometryConverter()

    sys_lat = -14.5
    sys_long = -52
    sys_alt = 1200

    geoconv.set_reference(
        sys_lat, sys_long, sys_alt
    )

    opts = [
        FootPrintOpts(
            seed=20,
        ),
        FootPrintOpts(
            seed=22,
        )
    ]

    for opt in opts:
        fig = plot_fp(params, geoconv, opt)
        # fig.write_image(f"fp.png")
        fig.show()
