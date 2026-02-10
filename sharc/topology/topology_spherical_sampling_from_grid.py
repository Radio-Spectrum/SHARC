from sharc.topology.topology import Topology
import numpy as np
from sharc.support.sharc_geom import CoordinateSystem
from sharc.support.geometry import SimulatorGeometry, ENUReferenceFrame
from sharc.parameters.imt.parameters_grid import ParametersTerrestrialGrid
# from sharc.satellite.utils.sat_utils import lla2ecef
# import math
# import matplotlib.pyplot as plt
# import matplotlib.axes
# import geopandas as gpd
# from shapely.geometry import Polygon, MultiPolygon
# from pathlib import Path


class TopologySamplingFromSphericalGrid(Topology):
    """
    Class to generate and manage terrestrial networks distributed on a
    grid situated on a spherical Earth.
    This IMT topology is not meant for IMT TN as victim studies, since distributed
    IMT will not have intra-IMT interference from close BS.
    """

    def __init__(
        self,
        max_ue_distance: float,
        num_base_stations: int,
        global_sim_lla_reference: tuple[float, float, float],
        grid: ParametersTerrestrialGrid | np.ndarray,
    ):
        """
        Initializes a spherical topology with specific network settings.

        Parameters:
        max_ue_distance: Radius of the coverage area for each site in meters.
        num_base_stations: Number of base stations to sample
        global_sim_lla_reference: (3,) tuple for lla of global coordinate system
        grid: ParametersTerrestrialGrid for determining grid
        """
        # intersite distance is needed for UE distribution, so we calculate it
        intersite_dist = max_ue_distance * 3 / 2
        super().__init__(intersite_dist, max_ue_distance)

        self.determines_local_geometry = True

        self.num_base_stations = num_base_stations
        self.is_space_station = False

        self.grid = grid

        # sistema de coord global
        self.global_cs = global_sim_lla_reference
        self.bs_geometry: SimulatorGeometry = None

        self.calculate_coordinates()

    def calculate_coordinates(self, random_number_gen=np.random.RandomState()):
        """Compute and set the coordinates and angles for each base station.

        Parameters
        ----------
        random_number_gen : np.random.RandomState, optional
            Random number generator (not used in this implementation).
        """
        if not isinstance(self.grid, np.ndarray):
            self.grid.reset_grid(
                "calculate_coords",
                random_number_gen,
                True
            )
            lla_grid_to_sample = self.grid.lon_lat_grid[::-1]
        else:
            lla_grid_to_sample = self.grid

        # print("self.grid.lon_lat_grid.shape", self.grid.lon_lat_grid.shape)
        # print("self.grid.lon_lat_grid.shape", self.grid.lon_lat_grid.shape)
        # print("self.num_base_stations", self.num_base_stations)
        if lla_grid_to_sample.shape[0] == 2:
            default_alts = np.zeros((1, lla_grid_to_sample.shape[1]))
            lla_grid_to_sample = np.concatenate((lla_grid_to_sample, default_alts))

        # print("np.arange(lla_grid_to_sample.shape[0]).shape", np.arange(lla_grid_to_sample.shape[0]).shape)
        chosen_idxs = random_number_gen.choice(
            np.arange(lla_grid_to_sample.shape[1]),
            size=self.num_base_stations,
            replace=False
        )

        # (3, N)
        chosen_llas = lla_grid_to_sample.T[chosen_idxs].T

        geom = SimulatorGeometry(
            self.num_base_stations,
            self.num_base_stations,
            ENUReferenceFrame(
                lat=self.global_cs[0],
                lon=self.global_cs[1],
                alt=self.global_cs[2],
            ),
        )
        lat, lon, alt = chosen_llas
        self.chosen_lat, self.chosen_lon, self.chosen_alt = lat, lon, alt
        # coords locais para determinar
        # transformação global <> local
        geom.set_local_reference_frame(
            ENUReferenceFrame(
                lat=lat,
                lon=lon,
                alt=alt,
            )
        )
        self.x = np.zeros(self.num_base_stations)
        self.y = np.zeros(self.num_base_stations)
        self.z = np.zeros(self.num_base_stations)
        self.azimuth = random_number_gen.uniform(-180., 180., size=self.num_base_stations)
        geom.set_local_coords(
            self.x,
            self.y,
            self.z,
            self.azimuth,
        )

        # local x,y,z
        # self.x = None
        # self.y = None
        # self.z = None
        self.bs_geometry = geom

    def get_bs_geometry(self) -> SimulatorGeometry:
        """Returns BS pre-built SimulatorGeometry if implemented
        """
        return self.bs_geometry

    def get_ue_geometry(self, ue_k: int) -> SimulatorGeometry:
        """Returns UE pre-built SimulatorGeometry if implemented
        """
        ue_geom = SimulatorGeometry(
            self.num_base_stations * ue_k,
            self.num_base_stations * ue_k,
            self.bs_geometry.global_reference_frame,
        )
        ue_geom.set_local_reference_frame(
            ENUReferenceFrame(
                lat=np.repeat(self.chosen_lat, ue_k),
                lon=np.repeat(self.chosen_lon, ue_k),
                alt=np.repeat(self.chosen_alt, ue_k),
            )
        )
        return ue_geom

    def transform_ue_xyz(self, bs, x, y, z):
        """Do not make any changes to ue position, let SimulatorGeometry take care of it"""
        return x, y, z


# Example usage
if __name__ == '__main__':
    global_lla = (-14, -45, 1200)
    topology = TopologySamplingFromSphericalGrid(
        0, 3,
        global_lla,
        np.array([
            # [-1, -47, 400],
            # [-3, -47, 400],
            # [-5, -47, 400],
            # [-7, -47, 400],
            # [-9, -47, 400],
            [11, -47, 400],
            [22, -47, 400],
            [-14, -45, 1200]
        ]).T,
    )

    topology.calculate_coordinates()

    from sharc.satellite.scripts.plot_globe import plot_globe_with_borders
    from sharc.support.sharc_geom import CoordinateSystem

    global_cs = CoordinateSystem()
    global_cs.set_reference(
        *global_lla
    )
    fig = plot_globe_with_borders(
        False, global_cs, False
    )

    import plotly.graph_objects as go

    fig.add_trace(go.Scatter3d(
        x=topology.bs_geometry.x_global,
        y=topology.bs_geometry.y_global,
        z=topology.bs_geometry.z_global,
        mode='markers',
        marker=dict(
            size=2,
            color='blue',
            opacity=1.0
        ),
        name='Reference'
    ))

    fig.show()
