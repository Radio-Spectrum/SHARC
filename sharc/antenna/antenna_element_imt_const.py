# -*- coding: utf-8 -*-
"""
Created on Fri Apr 14 14:13:58 2017

@author: Calil
"""


from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
import numpy as np


class AntennaElementImtConst(object):
    """
    Implements a single element of an IMT antenna array with constant gain

    Attributes
    ----------
        g_max (float): maximum gain of element

    """

    def __init__(self, par: ParametersAntennaImt):
        """
        Constructs an AntennaElementImt object.

        Parameters
        ---------
            param (ParametersAntennaImt): antenna IMT parameters
        """
        self.g_max = par.element_max_g

    def element_pattern(self, phi: np.array, theta: np.array) -> np.array:
        """
        Calculates the element radiation pattern gain.

        Parameters
        ----------
            theta (np.array): elevation angle [degrees]
            phi (np.array): azimuth angle [degrees]

        Returns
        -------
            gain (np.array): element radiation pattern gain value
        """
        gain = np.ones(np.shape(phi)) * self.g_max

        return gain
