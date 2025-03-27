
"""
This module implements an IMT Mobile Satellite Service (MSS) for Direct Connectivity (D2D) topology.

It consists of a group of NGSO satellites that provide direct connectivity to user equipment (UE) on the ground.
The Space Stations positions are generated from the Keplerian elements of the orbits in the OrbitModel class.
Only a subset of Space Stations are used, which are the ones that are visible to the UE.
After satellite visibility is calculated, the ECEF coordinates are transformed to a new cartesian coordinate system
centered at the reference point defined in the GeometryConverter object.
The azimuth and elevation angles are also rotated to the new coordinate system.
The visible Space Stations are then used to generate the IMT Base Stations.
"""

import numpy as np

from sharc.topology.topology import Topology
from sharc.parameters.imt.parameters_imt_mss_dc import ParametersImtMssDc
from sharc.parameters.parameters_orbit import ParametersOrbit
from sharc.satellite.ngso.orbit_model import OrbitModel
from sharc.support.sharc_geom import GeometryConverter, rotate_angles_based_on_new_nadir
from sharc.topology.topology_ntn import TopologyNTN
from sharc.satellite.utils.sat_utils import calc_elevation
from sharc.support.sharc_geom import lla2ecef, cartesian_to_polar, polar_to_cartesian


class TopologyImtMssDc(Topology):
    def __init__(self, params: ParametersImtMssDc, geometry_converter: GeometryConverter):
        """Implements a IMT Mobile Satellite Service (MSS) for Direct Connectivity (D2D) topology.

        Parameters
        ----------
        params : ParametersImtMssDc
            Input parameters for the IMT MSS-DC topology
        geometry_converter : GeometryConverter
            GeometryConverter object that converts the ECEF coordintate system to one
            centered at GeometryConverter.reference.
        """
        # That means the we need to pass the groud reference points to the base stations generator
        self.is_space_station = True
        self.num_sectors = params.num_beams

        # Specific attributes
        self.geometry_converter = geometry_converter
        self.orbit_params = params
        self.space_station_x = None
        self.space_station_y = None
        self.space_station_z = None

        self.cell_radius = params.beam_radius
        # TODO: check this:
        self.intersite_distance = self.cell_radius * np.sqrt(3)

        self.lat = None
        self.lon = None
        self.min_elev_angle = params.min_elev_angle  # Minimum elevation angle for satellite visibility
        self.orbits = []

        # Iterate through each orbit defined in the parameters
        # print("self.orbit_params.orbits", self.orbit_params.orbits)
        # exit()
        for param in self.orbit_params.orbits:
            # Instantiate an OrbitModel for the current orbit
            orbit = OrbitModel(
                Nsp=param.sats_per_plane,  # Satellites per plane
                Np=param.n_planes,  # Number of orbital planes
                phasing=param.phasing_deg,  # Phasing angle in degrees
                long_asc=param.long_asc_deg,  # Longitude of ascending node in degrees
                omega=param.omega_deg,  # Argument of perigee in degrees
                delta=param.inclination_deg,  # Orbital inclination in degrees
                hp=param.perigee_alt_km,  # Perigee altitude in kilometers
                ha=param.apogee_alt_km,  # Apogee altitude in kilometers
                Mo=param.initial_mean_anomaly  # Initial mean anomaly in degrees
            )
            self.orbits.append(orbit)

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """
        Computes the coordintates of the visible space stations
        """
        self.geometry_converter.validate()

        # Calculate the total number of satellites across all orbits
        total_satellites = sum(orbit.n_planes * orbit.sats_per_plane for orbit in self.orbit_params.orbits)

        idx_orbit = np.zeros(total_satellites, dtype=int)  # Add orbit index array

        # Initialize arrays to store satellite positions, angles and distance from center of earth
        all_positions = {"R": [], "lat": [], "lon": [], "sx": [], "sy": [], "sz": []}
        all_elevations = []  # Store satellite elevations
        all_azimuths = []  # Store satellite azimuths

        # List to store indices of active satellites
        active_satellite_idxs = []
        current_sat_idx = 0  # Index tracker for satellites across all orbits

        MAX_ITER = 100  # Maximum iterations to find at least one visible satellite
        i = 0  # Iteration counter for ensuring satellite visibility
        while len(active_satellite_idxs) == 0:
            # Iterate through each orbit defined in the parameters
            for orbit_idx, orbit in enumerate(self.orbits):
                # Generate random positions for satellites in this orbit
                pos_vec = orbit.get_orbit_positions_random_time(rng=random_number_gen)

                # Determine the number of satellites in this orbit
                num_satellites = len(pos_vec["sx"])

                # Assign orbit index to satellites
                idx_orbit[current_sat_idx:current_sat_idx + num_satellites] = orbit_idx

                # Extract satellite positions and calculate distances
                sx, sy, sz = pos_vec['sx'], pos_vec['sy'], pos_vec['sz']
                r = np.sqrt(sx**2 + sy**2 + sz**2)  # Distance from Earth's center

                # When getting azimuth and elevation, we need to consider sx, sy and sz points
                # from the center of earth to the satellite, and we need to point the satellite
                # towards the center of earth
                elevations = np.degrees(np.arcsin(-sz / r))  # Calculate elevation angles
                azimuths = np.degrees(np.arctan2(-sy, -sx))  # Calculate azimuth angles

                # Append satellite positions and angles to global lists
                all_positions['lat'].extend(pos_vec['lat'])  # Latitudes
                all_positions['lon'].extend(pos_vec['lon'])  # Longitudes
                all_positions['sx'].extend(sx)  # X-coordinates
                all_positions['sy'].extend(sy)  # Y-coordinates
                all_positions['sz'].extend(sz)  # Z-coordinates
                all_positions["R"].extend(r)
                all_elevations.extend(elevations)  # Elevation angles
                all_azimuths.extend(azimuths)  # Azimuth angles

                # Calculate satellite visibility from base stations
                elev_from_bs = calc_elevation(
                    self.geometry_converter.ref_lat,  # Latitude of base station
                    pos_vec['lat'],  # Latitude of satellites
                    self.geometry_converter.ref_long,  # Longitude of base station
                    pos_vec['lon'],  # Longitude of satellites
                    orbit.perigee_alt_km  # Perigee altitude in kilometers
                )

                # Determine visible satellites based on minimum elevation angle
                visible_sat_idxs = [
                    current_sat_idx + idx for idx, elevation in enumerate(elev_from_bs)
                    if elevation >= self.min_elev_angle
                ]
                active_satellite_idxs.extend(visible_sat_idxs)

                # Update the index tracker for the next orbit
                current_sat_idx += len(sx)

            i += 1  # Increment iteration counter
            if i >= MAX_ITER:  # Check if maximum iterations reached
                raise RuntimeError(
                    "Maximum iterations reached, and no satellite was selected within the minimum elevation criteria."
                )
        # We have the list of visible satellites, now create a Topolgy of this subset and move the coordinate system
        # reference.
        total_active_satellites = len(active_satellite_idxs)
        self.space_station_x = np.squeeze(np.array(all_positions['sx']))[active_satellite_idxs] * 1e3  # Convert X-coordinates to meters
        self.space_station_y = np.squeeze(np.array(all_positions['sy']))[active_satellite_idxs] * 1e3  # Convert Y-coordinates to meters
        self.space_station_z = np.squeeze(np.array(all_positions['sz']))[active_satellite_idxs] * 1e3  # Convert Z-coordinates to meters
        self.elevation = np.squeeze(np.array(all_elevations))[active_satellite_idxs]  # Elevation angles
        self.azimuth = np.squeeze(np.array(all_azimuths))[active_satellite_idxs]  # Azimuth angles

        # Store the latitude and longitude of the visible satellites for later use
        self.lat = np.squeeze(np.array(all_positions['lat']))[active_satellite_idxs]
        self.lon = np.squeeze(np.array(all_positions['lon']))[active_satellite_idxs]

        # Convert the ECEF coordinates to the transformed cartesian coordinates and set the Space Station positions
        # used to generetate the IMT Base Stations
        self.space_station_x, self.space_station_y, self.space_station_z = \
            self.geometry_converter.convert_cartesian_to_transformed_cartesian(self.space_station_x, self.space_station_y, self.space_station_z)

        # Rotate the azimuth and elevation angles off the center beam the new transformed cartesian coordinates
        r = 1
        # transform pointing vectors, without considering geodesical earth coord system
        pointing_vec_x, pointing_vec_y, pointing_vec_z = polar_to_cartesian(r, self.azimuth, self.elevation)
        pointing_vec_x, pointing_vec_y, pointing_vec_z = \
            self.geometry_converter.convert_cartesian_to_transformed_cartesian(
                pointing_vec_x, pointing_vec_y, pointing_vec_z, translate=0)
        _, self.azimuth, self.elevation = cartesian_to_polar(pointing_vec_x, pointing_vec_y, pointing_vec_z)

        # Create the other beams and rotate the azimuth and elevation angles

        # Calculate the average altitude of the visible satellites
        rx, ry, rz = lla2ecef(
            np.squeeze(np.array(all_positions['lat'])),
            np.squeeze(np.array(all_positions['lon'])),
            0
        )
        earth_radius = np.sqrt(rx * rx + ry * ry + rz * rz)
        all_r = np.squeeze(np.array(all_positions['R'])) * 1e3
        sat_altitude = np.array(all_r - earth_radius)[active_satellite_idxs]

        # We borrow the TopologyNTN method to calculate the sectors azimuth and elevation angles from their
        # respective x and y boresight coordinates
        sx, sy = TopologyNTN.get_sectors_xy(
            intersite_distance=self.orbit_params.beam_radius * np.sqrt(3),
            num_sectors=self.orbit_params.num_beams
        )

        assert(len(sx) == self.orbit_params.num_beams)
        assert(len(sy) == self.orbit_params.num_beams)

        # we give num_beams sectors to each satellite
        sx = np.resize(sx, self.orbit_params.num_beams * total_active_satellites)
        sy = np.resize(sy, self.orbit_params.num_beams * total_active_satellites)

        # Calculate the azimuth and elevation angles for each beam
        # as though their nadir is at (0,0)
        # before rotating them
        beams_azim = np.rad2deg(np.arctan2(sy, sx))
        beams_elev = np.rad2deg(np.arctan2(np.sqrt(sy * sy + sx * sx),
                                           np.repeat(sat_altitude, self.orbit_params.num_beams))
                            ) - 90

        beams_azim = beams_azim.reshape(
            (total_active_satellites, self.orbit_params.num_beams)
        )

        beams_elev = beams_elev.reshape(
            (total_active_satellites, self.orbit_params.num_beams)
        )

        # Rotate and set the each beam azimuth and elevation angles - only for the visible satellites
        assert(self.elevation.shape, (total_active_satellites,))
        assert(self.azimuth.shape, (total_active_satellites,))
        for i in range(total_active_satellites):
            # Rotate the azimuth and elevation angles based on the new nadir point
            beams_elev[i], beams_azim[i] = rotate_angles_based_on_new_nadir(
                beams_elev[i],
                beams_azim[i],
                self.elevation[i],
                self.azimuth[i]
            )
        
        # In SHARC each sector is treated as a separate base station, so we need to repeat the satellite positions
        # for each sector.
        self.space_station_x = np.repeat(self.space_station_x, self.orbit_params.num_beams)
        self.space_station_y = np.repeat(self.space_station_y, self.orbit_params.num_beams)
        self.space_station_z = np.repeat(self.space_station_z, self.orbit_params.num_beams)
        # the offset of the beams boresight from the satellite position
        offset_x = np.repeat(
            sat_altitude * np.cos(np.radians(self.elevation)) * np.cos(np.radians(self.azimuth)),
            self.orbit_params.num_beams
        )
        offset_y = np.repeat(
            sat_altitude * np.cos(np.radians(self.elevation)) * np.sin(np.radians(self.azimuth)),
            self.orbit_params.num_beams
        )
        offset_z = np.repeat(
            sat_altitude * np.sin(np.radians(self.elevation)),
            self.orbit_params.num_beams
        )
        self.num_base_stations = self.orbit_params.num_beams * total_active_satellites
        self.x = sx
        self.y = sy
        self.z = np.zeros_like(self.y)
        self.elevation = beams_elev.flatten()  # only valid at active satellites indices
        self.azimuth = beams_azim.flatten()  # only valid at active satellites indices
        self.indoor = np.zeros(self.num_base_stations, dtype=bool)  # ofcourse, all are outdoor
        self.height = np.ones(self.num_base_stations) * np.repeat(sat_altitude, self.orbit_params.num_beams)  # all are at the same height
        # Store the latitude and longitude of the visible satellites for later use
        self.lat = np.repeat(self.lat, self.orbit_params.num_beams)
        self.lon = np.repeat(self.lon, self.orbit_params.num_beams)

        assert(self.lat.shape == (self.num_base_stations,))
        assert(self.lon.shape == (self.num_base_stations,))
        assert(self.x.shape == (self.num_base_stations,))
        assert(self.y.shape == (self.num_base_stations,))
        assert(self.z.shape == (self.num_base_stations,))
        assert(self.elevation.shape == (self.num_base_stations,))
        assert(self.azimuth.shape == (self.num_base_stations,))
        assert(self.indoor.shape == (self.num_base_stations,))
        assert(self.height.shape == (self.num_base_stations,))
        assert(self.height.shape == (self.num_base_stations,))

    # We can factor this out if another topology also ends up needing this
    def transform_ue_xyz(self, bs_i, x, y, z):
        x, y, z = super().transform_ue_xyz(bs_i, x, y, z)

        # translate by earth radius on the lat long passed
        # this way we mantain the center of topology on surface of earth
        # considering a geodesic earth
        # since we expect the area to be small, we can just consider
        # the center of the topology for this translation
        rx, ry, rz = lla2ecef(self.lat[bs_i], self.lon[bs_i], 0)
        earth_radius_at_sat_nadir = np.sqrt(rx*rx + ry*ry + rz*rz)
        z += earth_radius_at_sat_nadir

        # get angle around y axis
        around_y = np.arctan2(
                np.sqrt(
                    self.space_station_x[bs_i] ** 2 +
                    self.space_station_y[bs_i] ** 2
                ),
                self.space_station_z[bs_i] + self.geometry_converter.get_translation()
            )

        # get around z axis
        around_z = np.arctan2(self.space_station_y[bs_i], self.space_station_x[bs_i])

        # rotating around y
        nx = x * np.cos(around_y) + z * np.sin(around_y)
        nz = x * -np.sin(around_y) + z * np.cos(around_y)
        x = nx
        z = nz

        # now we have (x,y) = (A, 0)
        # rotating around z
        nx = x * np.cos(around_z) + y * -np.sin(around_z)
        ny = x * np.sin(around_z) + y * np.cos(around_z)
        x = nx
        y = ny

        # translate ue back so other system is in (0,0,0)
        z -= self.geometry_converter.get_translation()

        return (x, y, z)


# Example usage
if __name__ == '__main__':
    from sharc.parameters.imt.parameters_imt_mss_dc import ParametersImtMssDc
    from sharc.support.sharc_geom import GeometryConverter

    # Define the parameters for the IMT MSS-DC topology
    # SystemA Orbit parameters
    orbit = ParametersOrbit(
        n_planes=20,
        sats_per_plane=32,
        phasing_deg=3.9,
        long_asc_deg=18.0,
        inclination_deg=54.5,
        perigee_alt_km=525,
        apogee_alt_km=525
    )
    params = ParametersImtMssDc(
        beam_radius=36516.0,
        num_beams=7,
        orbits=[orbit]
    )

    # Define the geometry converter
    geometry_converter = GeometryConverter()
    geometry_converter.set_reference(-15.0, -42.0, 1200)

    # Instantiate the IMT MSS-DC topology
    imt_mss_dc_topology = TopologyImtMssDc(params, geometry_converter)

    # Calculate the coordinates of the space stations
    rng = np.random.RandomState(101)
    imt_mss_dc_topology.calculate_coordinates(random_number_gen=rng)

    # Plot the IMT MSS-DC space stations after selecting the visible ones and transforming the coordinate system
    import plotly.graph_objects as go

    # Create a 3D scatter plot using Plotly
    fig = go.Figure(data=[go.Scatter3d(
        x=imt_mss_dc_topology.space_station_x / 1e3,
        y=imt_mss_dc_topology.space_station_y / 1e3,
        z=imt_mss_dc_topology.space_station_z / 1e3,
        mode='markers',
        marker=dict(
            size=4,
            color='red',
            opacity=0.8
        )
    )])

    # Set plot title and axis labels
    fig.update_layout(
        title='IMT MSS-DC Topology',
        scene=dict(
            xaxis_title='X [m]',
            yaxis_title='Y [m]',
            zaxis_title='Z [m]'
        )
    )

    # Add a point at the origin
    fig.add_trace(go.Scatter3d(
        x=[0],
        y=[0],
        z=[0],
        mode='markers',
        marker=dict(
            size=6,
            color='blue',
            opacity=1.0
        ),
        name='Reference'
    ))
    # Calculate the elevation with respect to the x-y plane
    elevation_xy_plane = np.degrees(
        np.arctan2(
            imt_mss_dc_topology.space_station_z,
            np.sqrt(imt_mss_dc_topology.space_station_x**2 + imt_mss_dc_topology.space_station_y**2)
        )
    )

    # Add the elevation with respect to the x-y plane to the plot
    fig.add_trace(go.Scatter3d(
        x=imt_mss_dc_topology.space_station_x / 1e3,
        y=imt_mss_dc_topology.space_station_y / 1e3,
        z=imt_mss_dc_topology.space_station_z / 1e3,
        mode='markers',
        marker=dict(
            size=4,
            color=elevation_xy_plane,
            colorscale='Viridis',
            colorbar=dict(title='Elevation (degrees)', x=-0.1),
            opacity=0.8
        ),
        name='Space Stations Positions'
    ))

    # Add lines between the origin and the IMT space stations
    for x, y, z in zip(imt_mss_dc_topology.space_station_x / 1e3, imt_mss_dc_topology.space_station_y / 1e3, imt_mss_dc_topology.space_station_z / 1e3):
        fig.add_trace(go.Scatter3d(
            x=[0, x],
            y=[0, y],
            z=[0, z],
            mode='lines',
            line=dict(color='green', width=2, dash='dash'),
            name='Elevation Line'
        ))
    # Suppress the legend for the elevation plot
    fig.update_traces(showlegend=False, selector=dict(name='Elevation Line'))

    # Plot beam boresight vectors
    boresight_length = 100  # Length of the boresight vectors for visualization
    boresight_x, boresight_y, boresight_z = polar_to_cartesian(
        boresight_length,
        imt_mss_dc_topology.azimuth,
        imt_mss_dc_topology.elevation
    )
    # Add arrow heads to the end of the boresight vectors
    for x, y, z, bx, by, bz in zip(imt_mss_dc_topology.space_station_x / 1e3,
                                   imt_mss_dc_topology.space_station_y / 1e3,
                                   imt_mss_dc_topology.space_station_z / 1e3,
                                   boresight_x,
                                   boresight_y,
                                   boresight_z):
        fig.add_trace(go.Cone(
            x=[x + bx],
            y=[y + by],
            z=[z + bz],
            u=[bx],
            v=[by],
            w=[bz],
            colorscale=[[0, 'orange'], [1, 'orange']],
            sizemode='absolute',
            sizeref=40,
            showscale=False
        ))
    for x, y, z, bx, by, bz in zip(imt_mss_dc_topology.space_station_x / 1e3,
                                   imt_mss_dc_topology.space_station_y / 1e3,
                                   imt_mss_dc_topology.space_station_z / 1e3,
                                   boresight_x,
                                   boresight_y,
                                   boresight_z):
        fig.add_trace(go.Scatter3d(
            x=[x, x + bx],
            y=[y, y + by],
            z=[z, z + bz],
            mode='lines',
            line=dict(color='orange', width=2),
            name='Boresight'
        ))
    # Suppress the legend for the boresight plot
    fig.update_traces(showlegend=False, selector=dict(name='Boresight'))

    # Maintain axis proportions
    fig.update_layout(scene_aspectmode='data')

    fig.show()

    # Plot the IMT MSS-DC space stations in a 2D plane
    fig_2d = go.Figure()

    # Add circles centered at the (x, y) coordinates of the space stations
    for x, y in zip(imt_mss_dc_topology.x, imt_mss_dc_topology.y):
        circle = go.Scatter(
            x=[x + imt_mss_dc_topology.orbit_params.beam_radius * np.cos(theta) for theta in np.linspace(0, 2 * np.pi, 100)],
            y=[y + imt_mss_dc_topology.orbit_params.beam_radius * np.sin(theta) for theta in np.linspace(0, 2 * np.pi, 100)],
            mode='lines',
            line=dict(color='blue')
        )
        fig_2d.add_trace(circle)

    # Set plot title and axis labels
    fig_2d.update_layout(
        title='IMT MSS-DC Topology in x-y Plane',
        xaxis_title='X [m]',
        yaxis_title='Y [m]',
        showlegend=False
    )

    # Maintain axis proportions
    fig_2d.update_yaxes(scaleanchor="x", scaleratio=1)

    # Show the plot
    fig_2d.show()

    # Print the elevation angles
    print('Elevation angles:', imt_mss_dc_topology.elevation)
    # Print the azimuth angles
    print('Azimuth angles:', imt_mss_dc_topology.azimuth)
    # Print the elevation w.r.t. the x-y plane
    print('Elevation w.r.t. XY plane:', elevation_xy_plane)
    # Print the slant range
    idxs = np.arange(imt_mss_dc_topology.num_base_stations // imt_mss_dc_topology.num_sectors) * \
        imt_mss_dc_topology.num_sectors
    print('Slant range:', np.sqrt(imt_mss_dc_topology.space_station_x[idxs]**2 +
                                  imt_mss_dc_topology.space_station_y[idxs]**2 +
                                  imt_mss_dc_topology.space_station_z[idxs]**2) / 1e3)
