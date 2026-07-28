# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 16:29:36 2017

@author: Calil
"""

import pandas as pd
from dataclasses import dataclass

@dataclass
class TopologyCountriesParamsFromFile:
    """
    Definition of TopologyCountries parameters read from a .csv or .xlsx database.
    """

    # Latitude and longitude coordinates [decimal degrees].
    latitude: float
    longitude: float

    # Azimuth angles [°]
    azimute: float

    # Antenna heights [m]
    altura: float

    def __post_init__(self):
        """
        Validates fields after initialization.
        """
        self.validate()


    def validate(self):
        """
        Validate latitude and longitude coordinates.
        """     
        if not isinstance( self.latitude, float ) or not ( -90.0 <= self.latitude <= 90.0 ):
            raise ValueError(f"Latitude must be between -90° and 90°")
                    
        if not isinstance( self.longitude, float ) or not ( -180.0 <= self.longitude <= 180.0 ):
            raise ValueError(f"Longitude must be between -180° and 180°")
        
        if not isinstance( self.azimute, float ) or not ( 0.0 <= self.azimute <= 360.0 ):
                raise ValueError(f"Azimuth must be between 0° and 360°")
        
        if not isinstance( self.altura, float ) or not ( self.altura > 0.0 ):
            raise ValueError(f"Height must a value greater than zero.")