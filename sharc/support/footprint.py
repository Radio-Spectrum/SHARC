
from mpl_toolkits.mplot3d import Axes3D, art3d
import geopandas as gpd
from area import area as earthArea
from numpy import cos, sin, tan, arctan, deg2rad, rad2deg, arccos, pi, linspace, arcsin, vstack, arctan2, where, zeros_like
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from sharc.parameters.constants import EARTH_RADIUS
from shapely.geometry import Polygon, MultiPolygon
import math
 
 
class Footprint(object):
    """
    Defines a satellite footprint region and calculates its area.
    Method for generating footprints (Siocos,1973) is found in the book
    "Satellite Communication Systems" by M. Richharia ISBN 0-07-134208-7
 
    Construction:
        FootprintArea(bore_lat_deg, bore_subsat_long_deg, beam)
            beam_deg (float): half of beam width in degrees
            elevation_deg (float): optional. Satellite elevation at
            boresight bore_lat_deg (float): optional, default = 0.
                Latitude of boresight point. If elevation is given this
                parameter is not used. Default = 0
            bore_subsat_long_deg (float): longitude of boresight with respect
                to sub-satellite point, taken positive when to the west of the
                sub-satellite point. If elevation is given this
                parameter is not used. Default = 0
            sat_height (int): optional, Default = 3578600.
                Height of satellite in meters. If none are given, it is assumed that it is a geostationary satellite.
    """
 
    def __init__(self, beam_deg: float, **kwargs):
        # Initialize attributes
        self.sat_height = 35786000
        if 'sat_height' in kwargs.keys():
            self.sat_height = kwargs['sat_height']
 
        if 'elevation_deg' in kwargs.keys():
            self.elevation_deg = kwargs['elevation_deg']
            self.bore_lat_deg = 0.0
            self.sigma = EARTH_RADIUS / (EARTH_RADIUS + self.sat_height)
            self.bore_subsat_long_deg = self.calc_beta(self.elevation_deg)
        else:
            self.sigma = EARTH_RADIUS / (EARTH_RADIUS + self.sat_height)
            self.bore_lat_deg = 0.0
            self.bore_subsat_long_deg = 0.0
            if 'bore_lat_deg' in kwargs.keys():
                self.bore_lat_deg = kwargs['bore_lat_deg']
            if 'bore_subsat_long_deg' in kwargs.keys():
                self.bore_subsat_long_deg = kwargs['bore_subsat_long_deg']
            self.elevation_deg = \
                self.calc_elevation(
                    self.bore_lat_deg,
                    self.bore_subsat_long_deg,
                )
 
        self.beam_width_deg = beam_deg
 
        # sigma is the relation bewtween earth radius and satellite height
        # print(self.sigma)
 
        # Convert to radians
        self.elevation_rad = deg2rad(self.elevation_deg)
        self.bore_lat_rad = deg2rad(self.bore_lat_deg)
        self.bore_subsat_long_rad = deg2rad(self.bore_subsat_long_deg)
        self.beam_width_rad = deg2rad(self.beam_width_deg)
 
        # Calculate tilt
        self.beta = arccos(
            cos(self.bore_lat_rad) *
            cos(self.bore_subsat_long_rad),
        )
        self.bore_tilt = arctan2(
            sin(self.beta), ((1 / self.sigma) - cos(self.beta)),
        )
 
        # Maximum tilt and latitute coverage
        self.max_beta_rad = arccos(self.sigma)
        self.max_gamma_rad = pi / 2 - self.max_beta_rad
 
    def calc_beta(self, elev_deg: float):
        """
        Calculates elevation angle based on given elevation. Beta is the
        subpoint to earth station great-circle distance
 
        Input:
            elev_deg (float): elevation in degrees
 
        Output:
            beta (float): beta angle in degrees
        """
        elev_rad = deg2rad(elev_deg)
        beta = 90 - elev_deg - rad2deg(arcsin(cos(elev_rad) * self.sigma))
        return beta
 
    def calc_elevation(self, lat_deg: float, long_deg: float):
        """
        Calculates elevation for given latitude of boresight point and
        longitude of boresight with respect to sub-satellite point.
 
        Inputs:
            lat_deg (float): latitude of boresight point in degrees
            long_deg (float): longitude of boresight with respect
                to sub-satellite point, taken positive when to the west of the
                sub-satellite point, in degrees
 
        Output:
            elev (float): elevation in degrees
        """
        lat_rad = deg2rad(lat_deg)
        long_rad = deg2rad(long_deg)
        beta = arccos(cos(lat_rad) * cos(long_rad))
        elev = arctan2((cos(beta) - self.sigma), sin(beta))
 
        return rad2deg(elev)
 
    def set_elevation(self, elev: float):
        """
        Resets elevation angle to given value
        """
        self.elevation_deg = elev
        self.bore_lat_deg = 0.0
        self.bore_subsat_long_deg = self.calc_beta(self.elevation_deg)
 
        # Convert to radians
        self.elevation_rad = deg2rad(self.elevation_deg)
        self.bore_lat_rad = deg2rad(self.bore_lat_deg)
        self.bore_subsat_long_rad = deg2rad(self.bore_subsat_long_deg)
 
        # Calculate tilt
        self.beta = arccos(
            cos(self.bore_lat_rad) *
            cos(self.bore_subsat_long_rad),
        )
        self.bore_tilt = arctan2(
            sin(self.beta), (1 / self.sigma - cos(self.beta)),
        )
 
    def calc_footprint(self, n: int):
        """
        Defines footprint polygonal approximation
 
        Input:
            n (int): number of vertices on polygonal
 
        Outputs:
            pt_long (np.array): longitude of vertices in deg
            pt_lat (np.array): latiture of vertices in deg
        """
        # Projection angles
        phi = linspace(0, 2 * pi, num=n)
 
        cos_gamma_n = cos(self.bore_tilt) * cos(self.beam_width_rad) + \
            sin(self.bore_tilt) * sin(self.beam_width_rad) *\
            cos(phi)
 
        gamma_n = arccos(cos_gamma_n)
        phi_n = arctan2(
            sin(phi), (
                sin(self.bore_tilt) * self.cot(self.beam_width_rad) -
                cos(self.bore_tilt) * cos(phi)
            ),
        )
 
        eps_n = arctan2(sin(self.bore_subsat_long_rad), tan(self.bore_lat_rad)) + \
            phi_n
 
        beta_n = arcsin((1 / self.sigma) * sin(gamma_n)) - gamma_n
        beta_n[where(gamma_n > self.max_gamma_rad)] = self.max_beta_rad
 
        pt_lat = arcsin(sin(beta_n) * cos(eps_n))
        pt_long = arctan(tan(beta_n) * sin(eps_n))
 
        return rad2deg(pt_long), rad2deg(pt_lat)
 
    def calc_area(self, n: int):
        """
        Returns footprint area in km^2
 
        Input:
            n (int): number of vertices on polygonal approximation
        Output:
            a (float): footprint area in km^2
        """
 
        long, lat = self.calc_footprint(n)
 
        long_lat = vstack((long, lat)).T
 
        obj = {
            'type': 'Polygon',
            'coordinates': [long_lat.tolist()],
        }
 
        return earthArea(obj) * 1e-6
 
    def cot(self, angle):
        return tan(pi / 2 - angle)
 
    def arccot(self, x):
        return pi / 2 - arctan(x)
 
 
if __name__ == '__main__':
 
    import plotly.graph_objects as go
    # axis = fig.add_subplot(111, projection='', computed_zorder=False)
 
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = (EARTH_RADIUS) * np.outer(np.cos(u), np.sin(v))
    y = (EARTH_RADIUS) * np.outer(np.sin(u), np.sin(v))
    z = (EARTH_RADIUS) * np.outer(np.ones(np.size(u)), np.cos(v))
    cmap = plt.get_cmap("tab10")
    make_int = np.vectorize(int)
    mycolors_a = make_int(256*np.array(cmap(1)[0:3])).reshape((1, 1,-1)).repeat(21, axis = 0).repeat(21, axis =1)
    fig = go.Figure(data=[
              #       go.Surface(x=x,y=y, surfacecolor=np.zeros(shape=x.shape) * -EARTH_RADIUS,colorscale=[[0, 'rgb(255,255,255)'], 
              # [1, 'rgb(255,255,255)']])
                ])
 
    brazils = gpd.read_file(
        "sharc/topology/countries/ne_110m_admin_0_countries.shp",
    )
 
    # Plot the surface
    # axis.plot_surface(x, y, z, color='b', zorder=0)
 
    # Coordinates of the Federal District (Brasília)
    federal_district_coords = (-47.9292, -15.7801)
 
    # Approximate conversion factors (1 degree latitude = 111 km, 1 degree longitude = 111 km)
    lat_to_km = 111
    lon_to_km = 111
 
    def convert_to_xyz(long, lat, altitude=0):
        # python
        if hasattr(lat, "shape"):
            altitude = altitude*np.ones(lat.shape)
        return (long, lat, altitude)
        rho = EARTH_RADIUS + altitude
        x = np.cos(np.deg2rad(lat)) * np.cos(np.deg2rad(long)) * rho
        y = np.cos(np.deg2rad(lat)) * np.sin(np.deg2rad(long)) * rho
        z = np.sin(np.deg2rad(lat)) * rho # z is 'up'
        return (x,y,z)
 
    def add_points(ax,xs,ys,zs, *rest):
        for x,y,z in zip(xs, ys, zs):
            # print(x,y,z)
            add_point(ax,x,y,z,*rest)
    
    def add_point(ax, x, y, z, fc = None, ec = None, radius = 0.005):
       xy_len, z_len = ax.get_figure().get_size_inches()
       axis_length = [x[1] - x[0] for x in [ax.get_xbound(), ax.get_ybound(), ax.get_zbound()]]
       axis_rotation =  {'z': ((x, y, z), axis_length[1]/axis_length[0]),
                         'y': ((x, z, y), axis_length[2]/axis_length[0]*xy_len/z_len),
                         'x': ((y, z, x), axis_length[2]/axis_length[1]*xy_len/z_len)}
       for a, ((x0, y0, z0), ratio) in axis_rotation.items():
           p = matplotlib.patches.Ellipse((x0, y0), width = radius, height = radius*ratio, fc=fc, ec=ec)
           ax.add_patch(p)
           art.pathpatch_2d_to_(p,  zdir=a)
 
    # Convert Federal District coordinates to kilometers
    federal_district_coords_km = (
        federal_district_coords[0], federal_district_coords[1],
    )
 
    # Calculate the shift required to move the Federal District to (0, 0)
    x_shift = federal_district_coords_km[0]
    y_shift = federal_district_coords_km[1]
    x_shift = 0
    y_shift = 0
 
    # Manually plot the map of Brazil on the xy-plane
    for m in brazils['NAME']:
        brazil = brazils[brazils['NAME'] == m]
        for geom in brazil.geometry:
            if isinstance(geom, Polygon):
                lon, lat = geom.exterior.xy
                x = np.array(lon)
                y = np.array(lat)
                x,y,z = convert_to_xyz(x,y)
                # print(x,y,z)
                # add_points(axis,x,y,z,'lightgray')
                fig.add_scatter(x=x,y=y, mode="lines", showlegend=False, line_color="gray")
            elif isinstance(geom, MultiPolygon):
                for poly in geom.geoms:
                    lon, lat = poly.exterior.xy
                    x = np.array(lon)
                    y = np.array(lat)
                    x,y,z = convert_to_xyz(x,y)
                    # add_points(axis,x,y,z,'lightgray')
                    # axis.plot(x,y,z, color='lightgray', zorder=0)
                    fig.add_scatter(x=x,y=y, mode="lines", showlegend=False, line_color="gray")
 
    # Add the Federal District location to the plot
    x_shift = federal_district_coords_km[0]
    y_shift = federal_district_coords_km[1]
    # axis.scatter(x_shift, y_shift, 0, color='red', zorder=5)
    # axis.text(x_shift, y_shift, 0, 'Federal District', fontsize=12, ha='right')
 
    # x = np.array([0, 1000])
    # y = np.array([0, 1000])
    # r = 450
 
    # # Plot each sector
    # for x, y in zip(x / 1000, y / 1000):  # Convert to kilometers
    #     hexagon = []
    #     for a in range(6):
    #         angle_rad = math.radians(a * 60)
    #         hexagon.append([
    #             x + r * math.cos(angle_rad),
    #             y + r * math.sin(angle_rad),
    #         ])
    #     hexagon.append(hexagon[0])  # Close the hexagon
    #     hexagon = np.array(hexagon)
 
    # #  hexagon
    # axis.plot(
    #     hexagon[:, 0], hexagon[:, 1],
    #     np.zeros_like(hexagon[:, 0]), 'k-',
    # )
 
    # # Plot base stations
    # axis.scatter(
    #     x / 1000, y / 1000, np.zeros_like(x), s=75, marker='v', c='k', edgecolor='k',
    #     linewidth=1, alpha=1,
    #     label="Anchor Points",
    # )
 
    space_station_x = -14.5
    space_station_y = 0
    space_station_z = 35786000
    # Create 20km footprints
    fprint90 = Footprint(9, elevation_deg=90)
    fprint45 = Footprint(8.5, elevation_deg=90)
    fprint30 = Footprint(8, elevation_deg=90)
    fprint20 = Footprint(10, elevation_deg=90)
    # fprint05 = Footprint(10, elevation_deg=5)
 
    import plotly.express as px
    # # Plot coordinates
    n = 100
    long, lat = fprint20.calc_footprint(n)
    x,y,z = convert_to_xyz(long+space_station_x, lat)
    fig.add_scatter(
        x=x,y=y,
        connectgaps=False,
        mode="lines",
        name="$20^o beam$"
    )
    fig.data[-1].line.width=3

    # long, lat = fprint90.calc_footprint(n)
    # x,y,z = convert_to_xyz(long+space_station_x, lat)
    # fig.add_scatter(
    #     x=x,y=y,
    #     connectgaps=False,
    #     mode="lines",
    #     name="$18^o beam$"
    # )
    # fig.data[-1].line.width=3
    # fig.(, lat, 'k', label='')
    long, lat = fprint45.calc_footprint(n)
    x,y,z = convert_to_xyz(long+space_station_x, lat)
    fig.add_scatter(
        x=x,y=y,
        connectgaps=False,
        mode="lines",
        name="$17^o beam$"
    )
    fig.data[-1].line.width=3
    long, lat = fprint30.calc_footprint(n)
    x,y,z = convert_to_xyz(long+space_station_x, lat)
    
    fig.add_scatter(
        x=x,y=y,
        connectgaps=False,
        mode="lines",
        name="$16^o beam$"
    )
    fig.data[-1].line.width=3
 
    # long, lat = fprint20.calc_footprint(n)
    # plt.plot(long, lat, 'g', label='$20^o$')
    # long, lat = fprint05.calc_footprint(n)
    # plt.plot(long, lat, 'y', label='$5^o$')
 
    # plt.title("Footprints at 35786km (GEO)")
    # plt.legend(loc='upper right')
    # plt.xlabel('Longitude [deg]')
    # plt.ylabel('Latitude [deg]')
    # plt.xlim([-5, 90])
    # bs_radius = 2000
    bs_azimuth = 90
    bs_elevation = 5
    # # Plot the satellite
    # axis.scatter(
    #     space_station_x, space_station_y, space_station_z, s=75, c='r',
    #     marker='^', edgecolor='k', linewidth=1, alpha=1,
    #     # label=f"Satellite (φ={np.degrees(bs_azimuth):.1f}°, θ={np.degrees(bs_elevation):.1f}°)",
    #     label="Satellite",
    # )
    x,y,z = convert_to_xyz(space_station_x, space_station_y, space_station_z )
    # fig.add_scatter(x=(x,), y=(y,), z=(z,), mode="markers", name="Satellite", marker_color="red")
 
    # # Plot the height line
    # axis.plot(
    #     [space_station_x, space_station_x],
    #     [space_station_y, space_station_y],
    #     [-10000, space_station_z], 'b-', label=f'Height = {space_station_z:.1f} km',
    # )
 
    # # Plot the slant range line
    # axis.plot(
    #     [x_shift, space_station_x],
    #     [y_shift, space_station_y],
    #     [0, space_station_z], 'g--', label='Slant',
    #     # [0, space_station_z], 'g--', label=f'Slant range = {bs_radius:.1f} km',
    # )
 
    # Add labels and title
    # axis.set_xlabel("long [deg]")
    # axis.set_ylabel("lat [deg]")
    # axis.set_zlabel("z-coordinate [km]")
    # axis.set_title("Footprint")
    # axis.legend()
    # axis.axes.set_zlim(bottom=0, top=space_station_z)
    # axis.set_box_aspect(aspect=(1,1,1))
    # plt.tight_layout()
    fig.update_layout(
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
        ),
        yaxis_title="Latitude (deg)",
        xaxis_title="Longitude (deg)",
    )
    fig.show()
