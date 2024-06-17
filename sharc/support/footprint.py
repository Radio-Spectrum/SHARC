# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 08:52:28 2017

@author: Calil
"""

from area import area as earthArea
from numpy import cos, sin, tan, arctan, deg2rad, rad2deg, arccos, pi, linspace, arcsin, vstack, arctan2, where, zeros_like
import matplotlib.pyplot as plt

earth_radius = 6371000

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
            altitude (float): optional, default = 3578600 (GEO satellite).
                Altitude of the satellite in meters.
    """
    def __init__(self, beam_deg: float, altitude: float = 35786000, **kwargs):
        # Initialize attributes
        self.altitude = altitude
        self.elevation_deg = kwargs.get('elevation_deg')
        self.bore_lat_deg = kwargs.get('bore_lat_deg', 0.0)
        self.bore_subsat_long_deg = kwargs.get('bore_subsat_long_deg', 0.0)
        
        if self.elevation_deg is not None:
            self.bore_subsat_long_deg = self.calc_beta(self.elevation_deg, self.altitude)
        else:
            self.elevation_deg = self.calc_elevation(self.bore_lat_deg, self.bore_subsat_long_deg)
        
        self.beam_width_deg = beam_deg
        
        # Convert to radians
        self.elevation_rad = deg2rad(self.elevation_deg)
        self.bore_lat_rad = deg2rad(self.bore_lat_deg)
        self.bore_subsat_long_rad = deg2rad(self.bore_subsat_long_deg)
        self.beam_width_rad = deg2rad(self.beam_width_deg)
        
        # Calculate tilt
        self.beta = arccos(cos(self.bore_lat_rad) * cos(self.bore_subsat_long_rad))
        self.bore_tilt = arctan2(sin(self.beta), (6.6235 - cos(self.beta)))
        
        # Maximum tilt and latitude coverage
        self.max_gamma_rad = deg2rad(8.6833)
        self.max_beta_rad = deg2rad(81.3164)
        
    def calc_beta(self,elev_deg: float, altitude : float):
        """
        Calculates elevation angle based on given elevation. Beta is the 
        subpoint to earth station great-circle distance
        
        Input:
            elev_deg (float): elevation in degrees
            altitude (float): altitude of the satellite in meters.
            
        Output:
            beta (float): beta angle in degrees  
        """
        elev_rad = deg2rad(elev_deg)
        beta = 90 - elev_deg - rad2deg(arcsin(cos(elev_rad)/((altitude + earth_radius)/earth_radius)))
        return beta
    
    def calc_elevation(self,lat_deg: float, long_deg: float):
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
        beta = arccos(cos(lat_rad)*cos(long_rad))
        elev = arctan2((cos(beta) - 0.1510),sin(beta))
        
        return rad2deg(elev)
    
    def set_elevation(self,elev: float):
        """
        Resets elevation angle to given value
        """
        self.elevation_deg = elev
        self.bore_lat_deg = 0.0
        self.bore_subsat_long_deg = self.calc_beta(self.elevation_deg, self.altitude)
        
        # Convert to radians
        self.elevation_rad = deg2rad(self.elevation_deg)
        self.bore_lat_rad = deg2rad(self.bore_lat_deg)
        self.bore_subsat_long_rad = deg2rad(self.bore_subsat_long_deg)
        
        # Calculate tilt
        self.beta = arccos(cos(self.bore_lat_rad)*cos(self.bore_subsat_long_rad))
        self.bore_tilt = arctan2(sin(self.beta),(6.6235 - cos(self.beta)))
        
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
        phi = linspace(0,2*pi,num = n)
        
        cos_gamma_n = cos(self.bore_tilt)*cos(self.beam_width_rad) + sin(self.bore_tilt)*sin(self.beam_width_rad)*cos(phi)
        
        gamma_n = arccos(cos_gamma_n) 
        phi_n = arctan2(sin(phi),(sin(self.bore_tilt)*self.cot(self.beam_width_rad) - cos(self.bore_tilt)*cos(phi))) 
        
        eps_n = arctan2(sin(self.bore_subsat_long_rad),tan(self.bore_lat_rad)) + phi_n
                
        beta_n = arcsin(6.6235*sin(gamma_n)) - gamma_n
        beta_n[where(gamma_n >  self.max_gamma_rad)] = self.max_beta_rad
        
        pt_lat  = arcsin(sin(beta_n)*cos(eps_n))
        pt_long = arctan(tan(beta_n)*sin(eps_n))
        
        return rad2deg(pt_long), rad2deg(pt_lat)
    
    def calc_area(self, n:int):
        """
        Returns footprint area in km^2
        
        Input:
            n (int): number of vertices on polygonal approximation
        Output:
            a (float): footprint area in km^2
        """
        long, lat = self.calc_footprint(n)
        
        long_lat = vstack((long, lat)).T
        
        obj = {'type':'Polygon',
               'coordinates':[long_lat.tolist()]}
        
        return earthArea(obj)*1e-6
        
    def cot(self,angle):
        return tan(pi/2 - angle)
    
    def arccot(self,x):
        return pi/2 - arctan(x)
        
if __name__ == '__main__':
    # Earth  [km]
    R = 6371
    
    # Create object
    fprint90_20km = Footprint(0.325,elevation_deg=90,altitude=20000)
    fprint45_20km = Footprint(0.325,elevation_deg=45,altitude=20000)
    fprint30_20km = Footprint(0.325,elevation_deg=30,altitude=20000)
    fprint20_20km = Footprint(0.325,elevation_deg=20,altitude=20000)
    fprint05_20km = Footprint(0.325,elevation_deg=5,altitude=20000)
    
    fprint90_500km = Footprint(0.325,elevation_deg=90,altitude=500000)
    fprint45_500km = Footprint(0.325,elevation_deg=45,altitude=500000)
    fprint30_500km = Footprint(0.325,elevation_deg=30,altitude=500000)
    fprint20_500km = Footprint(0.325,elevation_deg=20,altitude=500000)
    fprint05_500km = Footprint(0.325,elevation_deg=5,altitude=500000)
    
    fprint90_geo = Footprint(0.325,elevation_deg=90)
    fprint45_geo = Footprint(0.325,elevation_deg=45)
    fprint30_geo = Footprint(0.325,elevation_deg=30)
    fprint20_geo = Footprint(0.325,elevation_deg=20)
    fprint05_geo = Footprint(0.325,elevation_deg=5)

    n = 100
    # Plot coordinates for the 20km
    plt.figure(figsize=(15,2))
    long, lat = fprint90_20km.calc_footprint(n)
    plt.plot(long,lat,'k',label='$90^o$')
    long, lat = fprint45_20km.calc_footprint(n)
    plt.plot(long,lat,'b',label='$45^o$')
    long, lat = fprint30_20km.calc_footprint(n)
    plt.plot(long,lat,'r',label='$30^o$')
    long, lat = fprint20_20km.calc_footprint(n)
    plt.plot(long,lat,'g',label='$20^o$')
    long, lat = fprint05_20km.calc_footprint(n)
    plt.plot(long,lat,'y',label='$5^o$')
    plt.legend(loc='upper right')
    plt.xlabel('Longitude [deg]')
    plt.ylabel('Latitude [deg]')
    plt.xlim([-5, 8])
    plt.grid()
    plt.show()

    # Plot coordinates for the 500km
    plt.figure(figsize=(15,2))
    long, lat = fprint90_500km.calc_footprint(n)
    plt.plot(long,lat,'k',label='$90^o$')
    long, lat = fprint45_500km.calc_footprint(n)
    plt.plot(long,lat,'b',label='$45^o$')
    long, lat = fprint30_500km.calc_footprint(n)
    plt.plot(long,lat,'r',label='$30^o$')
    long, lat = fprint20_500km.calc_footprint(n)
    plt.plot(long,lat,'g',label='$20^o$')
    long, lat = fprint05_500km.calc_footprint(n)
    plt.plot(long,lat,'y',label='$5^o$')
    plt.legend(loc='upper right')
    plt.xlabel('Longitude [deg]')
    plt.ylabel('Latitude [deg]')
    plt.xlim([-5, 25])
    plt.grid()
    plt.show()

    # Plot coordinates for the 500km
    plt.figure(figsize=(15,2))
    long, lat = fprint90_geo.calc_footprint(n)
    plt.plot(long,lat,'k',label='$90^o$')
    long, lat = fprint45_geo.calc_footprint(n)
    plt.plot(long,lat,'b',label='$45^o$')
    long, lat = fprint30_geo.calc_footprint(n)
    plt.plot(long,lat,'r',label='$30^o$')
    long, lat = fprint20_geo.calc_footprint(n)
    plt.plot(long,lat,'g',label='$20^o$')
    long, lat = fprint05_geo.calc_footprint(n)
    plt.plot(long,lat,'y',label='$5^o$')
    plt.legend(loc='upper right')
    plt.xlabel('Longitude [deg]')
    plt.ylabel('Latitude [deg]')
    plt.xlim([-5, 90])
    plt.grid()
    plt.show()



    n = 1000
    # Print areas for the 20km
    print()
    print("Sat elevation 90 deg with an altitude of 20 km: area = {}".format(fprint90_20km.calc_area(n)))
    print("Sat elevation 45 deg with an altitude of 20 km: area = {}".format(fprint45_20km.calc_area(n)))
    print("Sat elevation 30 deg with an altitude of 20 km: area = {}".format(fprint30_20km.calc_area(n)))
    print("Sat elevation 20 deg with an altitude of 20 km: area = {}".format(fprint20_20km.calc_area(n)))
    print("Sat elevation 05 deg with an altitude of 20 km: area = {}".format(fprint05_20km.calc_area(n)))

    # Print areas for the 500km
    print()
    print("Sat elevation 90 deg with an altitude of 500 km: area = {}".format(fprint90_500km.calc_area(n)))
    print("Sat elevation 45 deg with an altitude of 500 km: area = {}".format(fprint45_500km.calc_area(n)))
    print("Sat elevation 30 deg with an altitude of 500 km: area = {}".format(fprint30_500km.calc_area(n)))
    print("Sat elevation 20 deg with an altitude of 500 km: area = {}".format(fprint20_500km.calc_area(n)))
    print("Sat elevation 05 deg with an altitude of 500 km: area = {}".format(fprint05_500km.calc_area(n)))

    # Print areas for the geo
    print()
    print("GEO Sat elevation 90 deg: area = {}".format(fprint90_geo.calc_area(n)))
    print("GEO Sat elevation 45 deg: area = {}".format(fprint45_geo.calc_area(n)))
    print("GEO Sat elevation 30 deg: area = {}".format(fprint30_geo.calc_area(n)))
    print("GEO Sat elevation 20 deg: area = {}".format(fprint20_geo.calc_area(n)))
    print("GEO Sat elevation 05 deg: area = {}".format(fprint05_geo.calc_area(n)))
    print()

    n_el = 100
    n_poly = 1000
    elevation = linspace(0,90,num=n_el)
    area = zeros_like(elevation)
    # Plot area vs elevation for the 20km
    fprint = Footprint(0.320,elevation_deg=0, altitude=20000)
    
    for k in range(len(elevation)):
        fprint.set_elevation(elevation[k])
        area[k] = fprint.calc_area(n_poly)
        
    plt.plot(elevation,area,label='20km')
    plt.xlabel('Elevation [deg]')
    plt.ylabel('Footprint area [$km^2$]')
    plt.legend(loc='upper center')
    plt.xlim([0, 90])
    plt.grid()
    plt.show()

    # Plot area vs elevation for the 500km
    fprint = Footprint(0.320,elevation_deg=0, altitude=500000)
    
    for k in range(len(elevation)):
        fprint.set_elevation(elevation[k])
        area[k] = fprint.calc_area(n_poly)
        
    plt.plot(elevation,area,label='500km')
    plt.xlabel('Elevation [deg]')
    plt.ylabel('Footprint area [$km^2$]')
    plt.legend(loc='upper center')
    plt.xlim([0, 90])
    plt.grid()
    plt.show()

    # Plot area vs elevation for the geo
    fprint = Footprint(0.320,elevation_deg=0, altitude=500000)
    
    for k in range(len(elevation)):
        fprint.set_elevation(elevation[k])
        area[k] = fprint.calc_area(n_poly)
        
    plt.plot(elevation,area,label='GEO')
    plt.xlabel('Elevation [deg]')
    plt.ylabel('Footprint area [$km^2$]')
    plt.legend(loc='upper center')
    plt.xlim([0, 90])
    plt.grid()
    plt.show()