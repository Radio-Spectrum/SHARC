# Generates a 3D plot of the Earth with the satellites positions
"""
Script to generate a 3D plot of the Earth with satellite positions for the MSS D2D to IMT cross-border scenario.
"""
# https://geopandas.org/en/stable/docs/user_guide/io.html
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

from sharc.support.sharc_geom import GeometryConverter
from sharc.parameters.parameters import Parameters
from sharc.topology.topology_factory import TopologyFactory
from sharc.station_factory import StationFactory
from sharc.satellite.scripts.plot_globe import plot_globe_with_borders, plot_mult_polygon


if __name__ == "__main__":
    geoconv = GeometryConverter()
    SELECTED_SNAPSHOT_NUMBER = 0
    OPAQUE_GLOBE = True
    print(f"Plotting drop {SELECTED_SNAPSHOT_NUMBER}")
    # even when using the same drop number as in a simulation,
    # since the random generators are not in the same state, there isn't
    # a direct relationship between a drop in this plot and a drop in the
    # simulation loop
    # NOTE: if you want to plot the actual simulation scenarios for debugging,
    # you should do so inside the simulation loop
    print("  (not the same drop number as in simulation)")

    script_dir = Path(__file__).parent
    param_file = script_dir / "base_input.yaml"
    # param_file = script_dir / "../input/parameters_mss_d2d_to_imt_cross_border_0km_random_pointing_1beam_dl.yaml"
    param_file = param_file.resolve()
    print("File at:")
    print(f"  '{param_file}'")

    parameters = Parameters()
    parameters.set_file_name(param_file)
    parameters.read_params()

    geoconv.set_reference(
        parameters.imt.topology.central_latitude,
        parameters.imt.topology.central_longitude,
        parameters.imt.topology.central_altitude,
    )
    print(
        "imt at (lat, lon, alt) = ",
        (geoconv.ref_lat, geoconv.ref_long, geoconv.ref_alt),
    )

    import random
    random.seed(parameters.general.seed)

    secondary_seeds = [None] * parameters.general.num_snapshots

    max_seed = 2**32 - 1

    for index in range(parameters.general.num_snapshots):
        secondary_seeds[index] = random.randint(1, max_seed)

    seed = secondary_seeds[SELECTED_SNAPSHOT_NUMBER]

    topology = TopologyFactory.createTopology(parameters, geoconv)

    random_number_gen = np.random.RandomState(seed)

    # In case of hotspots, base stations coordinates have to be calculated
    # on every snapshot. Anyway, let topology decide whether to calculate
    # or not
    topology.calculate_coordinates(random_number_gen)

    # Create the base stations (remember that it takes into account the
    # network load factor)
    bs = StationFactory.generate_imt_base_stations(
        parameters.imt,
        parameters.imt.bs.antenna.array,
        topology, random_number_gen,
    )

    # Create the other system (FSS, HAPS, etc...)
    system = StationFactory.generate_system(
        parameters, topology, random_number_gen,
        geoconv
    )

    # Create IMT user equipments
    ue = StationFactory.generate_imt_ue(
        parameters.imt,
        parameters.imt.ue.antenna.array,
        topology, random_number_gen,
    )

    # Plot the globe with satellite positions
    fig = plot_globe_with_borders(OPAQUE_GLOBE, geoconv, False)

    polygons_lim = plot_mult_polygon(
        parameters.mss_d2d.sat_is_active_if.lat_long_inside_country.filter_polygon,
        geoconv,
        False)
    from functools import reduce

    lim_x, lim_y, lim_z = reduce(lambda acc, it: (list(it[0]) + [None] + acc[0], list(
        it[1]) + [None] + acc[1], list(it[2]) + [None] + acc[2]), polygons_lim, ([], [], []))

    fig.add_trace(go.Scatter3d(
        x=lim_x,
        y=lim_y,
        z=lim_z,
        mode='lines',
        line=dict(color='rgb(0, 0, 255)'),
        showlegend=False
    ))

    # Plot all satellites (red markers)
    fig.add_trace(go.Scatter3d(
        x=system.x,
        y=system.y,
        z=system.z,
        mode='markers',
        marker=dict(size=2, color='red', opacity=0.5),
        showlegend=False
    ))

    # Plot visible satellites (green markers)
    # print(visible_positions['x'][visible_positions['x'] > 0])
    # print("vis_elevation", vis_elevation)
    fig.add_trace(go.Scatter3d(
        x=system.x[system.active],
        y=system.y[system.active],
        z=system.z[system.active],
        mode='markers',
        marker=dict(size=3, color='green', opacity=0.8),
        showlegend=False
    ))

    fig.add_trace(go.Scatter3d(
        x=ue.x,
        y=ue.y,
        z=ue.z,
        mode='markers',
        marker=dict(size=4, color='blue', opacity=1.0),
        showlegend=False
    ))

    fig.add_trace(go.Scatter3d(
        x=bs.x,
        y=bs.y,
        z=bs.z,
        mode='markers',
        marker=dict(size=4, color='black', opacity=1.0),
        showlegend=False
    ))

    # Display the plot
    range = 3e6
    fig.update_layout(
        scene=dict(
            zaxis=dict(
                range=(-range, range)
            ),
            yaxis=dict(
                range=(-range, range)
            ),
            xaxis=dict(
                range=(-range, range)
            ),
            camera=dict(
                center=dict(x=0, y=0, z=-geoconv.get_translation() /
                            (2 * range)),  # Look at Earth's center
                # eye=eye,   # Camera position
                # center=dict(x=0, y=0, z=0),  # Look at Earth's center
                # up=dict(x=0, y=0, z=1)  # Ensure the up direction is correct
            )
        )
    )

    fig.show()
