
# -*- coding: utf-8 -*-
"""
Created on Thu May 11 15:34:31 2017.

@author: edgar
"""


class Plot(object):
    """Class for handling and storing plot data and metadata."""

    def __init__(self, x, y, x_label, y_label, title, file_name, **kwargs):
        """Initialize the plot with data, labels, title, file name, and optional axis limits."""
        self.x = x
        self.y = y
        self.x_label = x_label
        self.y_label = y_label
        self.title = title
        self.file_name = file_name

        if "x_lim" in kwargs:
            self.x_lim = kwargs["x_lim"]
        else:
            self.x_lim = None

        if "y_lim" in kwargs:
            self.y_lim = kwargs["y_lim"]
        else:
            self.y_lim = None
