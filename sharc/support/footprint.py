# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 08:52:28 2017

@author: Calil
"""

from area import area as earthArea
import numpy as np
from numpy import cos, sin, tan, arctan, deg2rad, rad2deg, arccos, pi, linspace, arcsin, vstack, arctan2, where, zeros_like
import matplotlib.pyplot as plt
from sharc.parameters.constants import EARTH_RADIUS

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
    def __init__(self,beam_deg:float,**kwargs):
        # Initialize attributes
        if 'elevation_deg' in kwargs.keys() and 'sat_height' in kwargs.keys():
            self.elevation_deg = kwargs['elevation_deg']
            self.sat_height = kwargs['sat_height']
            self.sigma = EARTH_RADIUS / (EARTH_RADIUS + self.sat_height)
            self.bore_lat_deg = 0.0
            self.bore_subsat_long_deg = self.calc_beta(self.elevation_deg)
        elif 'elevation_deg' in kwargs.keys() and 'sat_height' not in kwargs.keys():
            self.elevation_deg = kwargs['elevation_deg']
            self.bore_lat_deg = 0.0
            self.sat_height = 35786000
            self.sigma = EARTH_RADIUS / (EARTH_RADIUS + self.sat_height)
            self.bore_subsat_long_deg = self.calc_beta(self.elevation_deg)
        else:
            self.sat_height = 35786000
            self.sigma = EARTH_RADIUS / (EARTH_RADIUS + self.sat_height)
            self.bore_lat_deg = 0.0
            self.bore_subsat_long_deg = 0.0
            if 'bore_lat_deg' in kwargs.keys():
                self.bore_lat_deg = kwargs['bore_lat_deg']
            if 'bore_subsat_long_deg' in kwargs.keys():
                self.bore_subsat_long_deg = kwargs['bore_subsat_long_deg']
            self.elevation_deg = \
                self.calc_elevation(self.bore_lat_deg,self.bore_subsat_long_deg)
            
        
        self.beam_width_deg = beam_deg
        
        # sigma is the relation bewtween earth radius and satellite height
        # print(self.sigma) 
        
        # Convert to radians
        self.elevation_rad = deg2rad(self.elevation_deg)
        self.bore_lat_rad = deg2rad(self.bore_lat_deg)
        self.bore_subsat_long_rad = deg2rad(self.bore_subsat_long_deg)
        self.beam_width_rad = deg2rad(self.beam_width_deg)
        
        # Calculate tilt
        self.beta = arccos(cos(self.bore_lat_rad)*\
                           cos(self.bore_subsat_long_rad))
        self.bore_tilt = arctan2(sin(self.beta),((1/self.sigma) - cos(self.beta)))
        
        # Maximum tilt and latitute coverage
        self.max_beta_rad = arccos(self.sigma) 
        self.max_gamma_rad = pi/2 - self.max_beta_rad
        
        
    def calc_beta(self,elev_deg: float):
        """
        Calculates elevation angle based on given elevation. Beta is the 
        subpoint to earth station great-circle distance
        
        Input:
            elev_deg (float): elevation in degrees
            
        Output:
            beta (float): beta angle in degrees  
        """
        elev_rad = deg2rad(elev_deg)
        beta = 90 - elev_deg - rad2deg(arcsin(cos(elev_rad)*self.sigma))
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
        elev = arctan2((cos(beta) - self.sigma),sin(beta))
        
        return rad2deg(elev)
    
    def set_elevation(self,elev: float):
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
        self.beta = arccos(cos(self.bore_lat_rad)*\
                           cos(self.bore_subsat_long_rad))
        self.bore_tilt = arctan2(sin(self.beta),(1/self.sigma - cos(self.beta)))
        
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
        
        cos_gamma_n = cos(self.bore_tilt)*cos(self.beam_width_rad) + \
                      sin(self.bore_tilt)*sin(self.beam_width_rad)*\
                      cos(phi)
        
        gamma_n = arccos(cos_gamma_n) 
        phi_n = arctan2(sin(phi),(sin(self.bore_tilt)*self.cot(self.beam_width_rad) - \
                     cos(self.bore_tilt)*cos(phi))) 
        
        eps_n = arctan2(sin(self.bore_subsat_long_rad),tan(self.bore_lat_rad)) + \
                phi_n
                
        beta_n = arcsin((1/self.sigma)*sin(gamma_n)) - gamma_n
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

def monte_carlo_simulation(num_samples, beam_deg, sat_height, elevation_range):
    areas = []
    elevations = np.random.uniform(elevation_range[0], elevation_range[1], num_samples)
    
    for elevation in elevations:
        footprint = Footprint(beam_deg, sat_height=sat_height, elevation_deg=elevation)
        area = footprint.calc_area(5000)
        areas.append(area)
    
    max_area = max(areas)
    best_elevation = elevations[areas.index(max_area)]
    
    return best_elevation, max_area, elevations, areas    

if __name__ == '__main__':
    
    #Create 20km footprints
    footprint_20km_10deg = Footprint(5, elevation_deg=10, sat_height=20000)
    footprint_20km_20deg = Footprint(5, elevation_deg=20, sat_height=20000)
    footprint_20km_30deg = Footprint(5, elevation_deg=30, sat_height=20000)
    footprint_20km_45deg = Footprint(5, elevation_deg=45, sat_height=20000)
    footprint_20km_90deg = Footprint(5, elevation_deg=90, sat_height=20000)
    
    plt.figure(figsize=(15,2))
    n = 100
    lng,lat = footprint_20km_90deg.calc_footprint(n)
    plt.plot(lng,lat,label='20 km Footprint with Elevation 90 deg')
    lng,lat = footprint_20km_45deg.calc_footprint(n)
    plt.plot(lng,lat,label='20 km Footprint with Elevation 45 deg')
    lng,lat = footprint_20km_30deg.calc_footprint(n)
    plt.plot(lng,lat,label='20 km Footprint with Elevation 30 deg')
    lng,lat = footprint_20km_20deg.calc_footprint(n)
    plt.plot(lng,lat,label='20 km Footprint with Elevation 20 deg')
    lng,lat = footprint_20km_10deg.calc_footprint(n)
    plt.plot(lng,lat,label='20 km Footprint with Elevation 10 deg')
    plt.xlabel('Longitude (deg)')
    plt.ylabel('Latitude (deg)')
    plt.legend()
    plt.show()

    print("Areas for 20km footprints:")
    print(f"Elevation 10 deg: {footprint_20km_10deg.calc_area(n)} km^2")
    print(f"Elevation 20 deg: {footprint_20km_20deg.calc_area(n)} km^2")
    print(f"Elevation 30 deg: {footprint_20km_30deg.calc_area(n)} km^2")
    print(f"Elevation 45 deg: {footprint_20km_45deg.calc_area(n)} km^2")
    print(f"Elevation 90 deg: {footprint_20km_90deg.calc_area(n)} km^2")
    
    # Create 35786km footprints
    footprint_35786km_10deg = Footprint(5, elevation_deg=10, sat_height=35786000)
    footprint_35786km_20deg = Footprint(5, elevation_deg=20, sat_height=35786000)
    footprint_35786km_30deg = Footprint(5, elevation_deg=30, sat_height=35786000)
    footprint_35786km_45deg = Footprint(5, elevation_deg=45, sat_height=35786000)
    footprint_35786km_90deg = Footprint(5, elevation_deg=90, sat_height=35786000)
    
    plt.figure(figsize=(15,2))
    n = 100
    lng,lat = footprint_35786km_90deg.calc_footprint(n)
    plt.plot(lng,lat,label='35786 km Footprint with Elevation 90 deg')
    lng,lat = footprint_35786km_45deg.calc_footprint(n)
    plt.plot(lng,lat,label='35786 km Footprint with Elevation 45 deg')
    lng,lat = footprint_35786km_30deg.calc_footprint(n)
    plt.plot(lng,lat,label='35786 km Footprint with Elevation 30 deg')
    lng,lat = footprint_35786km_20deg.calc_footprint(n)
    plt.plot(lng,lat,label='35786 km Footprint with Elevation 20 deg')
    lng,lat = footprint_35786km_10deg.calc_footprint(n)
    plt.plot(lng,lat,label='35786 km Footprint with Elevation 10 deg')
    plt.xlabel('Longitude (deg)')
    plt.ylabel('Latitude (deg)')
    plt.legend()
    plt.show()
    
    print("Areas for 35786km footprints:")
    print(f"Elevation 10 deg: {footprint_35786km_10deg.calc_area(n)} km^2")
    print(f"Elevation 20 deg: {footprint_35786km_20deg.calc_area(n)} km^2")
    print(f"Elevation 30 deg: {footprint_35786km_30deg.calc_area(n)} km^2")
    print(f"Elevation 45 deg: {footprint_35786km_45deg.calc_area(n)} km^2")
    print(f"Elevation 90 deg: {footprint_35786km_90deg.calc_area(n)} km^2")
    
    # Create 1200km footprints
    footprint_1200km_10deg = Footprint(5, elevation_deg=10, sat_height=1200000)
    footprint_1200km_20deg = Footprint(5, elevation_deg=20, sat_height=1200000)
    footprint_1200km_30deg = Footprint(5, elevation_deg=30, sat_height=1200000)
    footprint_1200km_45deg = Footprint(5, elevation_deg=45, sat_height=1200000)
    footprint_1200km_90deg = Footprint(5, elevation_deg=90, sat_height=1200000)
    
    plt.figure(figsize=(15,2))
    n = 100
    lng,lat = footprint_1200km_90deg.calc_footprint(n)
    plt.plot(lng,lat,label='1200 km Footprint with Elevation 90 deg')
    lng,lat = footprint_1200km_45deg.calc_footprint(n)
    plt.plot(lng,lat,label='1200 km Footprint with Elevation 45 deg')
    lng,lat = footprint_1200km_30deg.calc_footprint(n)
    plt.plot(lng,lat,label='1200 km Footprint with Elevation 30 deg')
    lng,lat = footprint_1200km_20deg.calc_footprint(n)
    plt.plot(lng,lat,label='1200 km Footprint with Elevation 20 deg')
    lng,lat = footprint_1200km_10deg.calc_footprint(n)
    plt.plot(lng,lat,label='1200 km Footprint with Elevation 10 deg')
    plt.xlabel('Longitude (deg)')
    plt.ylabel('Latitude (deg)')
    plt.legend()
    plt.show()

    print("Areas for 1200km footprints:")
    print(f"Elevation 10 deg: {footprint_1200km_10deg.calc_area(n)} km^2")
    print(f"Elevation 20 deg: {footprint_1200km_20deg.calc_area(n)} km^2")
    print(f"Elevation 30 deg: {footprint_1200km_30deg.calc_area(n)} km^2")
    print(f"Elevation 45 deg: {footprint_1200km_45deg.calc_area(n)} km^2")
    print(f"Elevation 90 deg: {footprint_1200km_90deg.calc_area(n)} km^2")

    # Create 600km footprints
    footprint_600km_10deg = Footprint(5, elevation_deg=10, sat_height=600000)
    footprint_600km_20deg = Footprint(5, elevation_deg=20, sat_height=600000)
    footprint_600km_30deg = Footprint(5, elevation_deg=30, sat_height=600000)
    footprint_600km_45deg = Footprint(5, elevation_deg=45, sat_height=600000)
    footprint_600km_90deg = Footprint(5, elevation_deg=90, sat_height=600000)
    
    plt.figure(figsize=(15,2))
    n = 100
    lng,lat = footprint_600km_90deg.calc_footprint(n)
    plt.plot(lng,lat,label='600 km Footprint with Elevation 90 deg')
    lng,lat = footprint_600km_45deg.calc_footprint(n)
    plt.plot(lng,lat,label='600 km Footprint with Elevation 45 deg')
    lng,lat = footprint_600km_30deg.calc_footprint(n)
    plt.plot(lng,lat,label='600 km Footprint with Elevation 30 deg')
    lng,lat = footprint_600km_20deg.calc_footprint(n)
    plt.plot(lng,lat,label='600 km Footprint with Elevation 20 deg')
    lng,lat = footprint_600km_10deg.calc_footprint(n)
    plt.plot(lng,lat,label='600 km Footprint with Elevation 10 deg')
    plt.xlabel('Longitude (deg)')
    plt.ylabel('Latitude (deg)')
    plt.legend()
    plt.show()

    print("Areas for 600km footprints:")
    print(f"Elevation 10 deg: {footprint_600km_10deg.calc_area(n)} km^2")
    print(f"Elevation 20 deg: {footprint_600km_20deg.calc_area(n)} km^2")
    print(f"Elevation 30 deg: {footprint_600km_30deg.calc_area(n)} km^2")
    print(f"Elevation 45 deg: {footprint_600km_45deg.calc_area(n)} km^2")
    print(f"Elevation 90 deg: {footprint_600km_90deg.calc_area(n)} km^2")






# Parâmetros
num_samples = 1000
beam_deg = 5
sat_height = 1200000
elevation_range = [5, 85]  # Faixa de elevação em graus

# Executar a simulação de Monte Carlo
best_elevation, max_area, elevations, areas = monte_carlo_simulation(num_samples, beam_deg, sat_height, elevation_range)

# Plotar os resultados
plt.scatter(elevations, areas, s=1)
plt.xlabel('Elevation (degrees)')
plt.ylabel('Area (km^2)')
plt.title('Monte Carlo Simulation for Satellite Elevation')
plt.show()

print(f'Melhor elevação: {best_elevation} graus')
print(f'Maior área de cobertura: {max_area} km^2')

 """
O código simula a cobertura de um satélite na Terra,
 calculando a área da região coberta para diferentes ângulos de elevação.
A simulação de Monte Carlo é utilizada para encontrar o ângulo ideal que maximiza a cobertura.
 Os resultados são visualizados graficamente, permitindo uma análise detalhada

Funcionalidades Principais:

Cálculo da Área: A classe calcula a área da região de cobertura com base em
 parâmetros como a largura do feixe, a altura do satélite e o ângulo de elevação.

Visualização: O código gera gráficos para visualizar as diferentes formas da 
cobertura do satélite em diferentes altitudes e ângulos de elevação.

Simulação de Monte Carlo: A principal modificação introduzida é a simulação de
Monte Carlo. Essa técnica permite encontrar o ângulo de elevação ideal para maximizar a área de cobertura, simulando aleatoriamente diferentes ângulos e calculando a área correspondente.


 """
