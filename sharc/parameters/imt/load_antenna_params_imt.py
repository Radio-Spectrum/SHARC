# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 16:29:36 2017

@author: Calil
"""

import pandas as pd
from dataclasses import dataclass
from dataclasses import fields
from collections import namedtuple

AntennaParGen = namedtuple(
    "AntennaParGen",
    "adjacent_antenna_model normalization normalization_data element_pattern \
                        element_max_g element_phi_3db element_theta_3db element_am element_sla_v n_rows \
                        n_columns element_horiz_spacing element_vert_spacing multiplication_factor \
                        minimum_array_gain downtilt tx_power",
)

@dataclass
class AntennaParamsFromFile:
    """
    Definition of antenna parameters read from a .csv or .xlsx database.
    """

    # BS number of rows and columns in antenna array.
    num_rows: int
    num_columns: int

    # Beamforming gain [dB].
    beamforming_gain: float

    # BS/UE maximum transmit/receive element gain [dBi].
    element_max_g: float

    # Total transmit power [dBm].
    tx_power: float

    # Sub-array number of rows
    sub_num_rows: int

    # Downtilt
    downtilt: float

    def __post_init__(self):
        """
        Validates fields after initialization.
        """
        self.validate_rows_cols()
        self.validate_bf_gain()
        self.validate_tx_power()
        self.validate_el_gain()

    def validate_rows_cols(self):
        """
        Validate the number of rows and columns.
        """
        if not isinstance(self.num_rows, int) or self.num_rows <= 0:
            raise ValueError("num_rows must be a positive integer")
        if not isinstance(self.num_columns, int) or self.num_columns <= 0:
            print(self.num_columns)
            raise ValueError("num_columns must be a positive integer")
        if not isinstance(self.sub_num_rows, int) or self.sub_num_rows <= 0:
            raise ValueError("sub_num_rows must be a positive integer")
        
    def validate_bf_gain(self):
        """
        Validate the beamforming gain.
        """
        if not isinstance(self.beamforming_gain, (int, float)) or self.beamforming_gain < 0:
            raise ValueError("Value must be a positive number")

    def validate_tx_power(self):
        """
        Validate the transmit power.
        """
        if not isinstance(self.tx_power, (int, float)):
            raise ValueError("Value must be a number")

    def validate_el_gain(self):
        """
        Validate the element gain.
        """
        if not isinstance(self.element_max_g, (int, float)):
            raise ValueError("Value must be a number")

def load_antenna_params_from_file(file_path: str, delimiter: str = ',') -> list[ AntennaParamsFromFile ]:
                
    # Get the field names of the AntennaParamsFromFile class
    col_labels_types = {f.name.lower(): f.type for f in fields(AntennaParamsFromFile)}

    # Read file
    ant_params_df = None
    if file_path.endswith('.csv'):
                
        ant_params_df = pd.read_csv( file_path,
                                     delimiter=delimiter.encode().decode("unicode_escape"),
                                     usecols=col_labels_types.keys(),
                                     dtype=col_labels_types )

    elif file_path.endswith('.xlsx'):
                
        ant_params_df = pd.read_excel( file_path,
                                     usecols=col_labels_types.keys(),
                                     dtype=col_labels_types )

    else:
        raise ValueError( 'File format must be .csv or .xlsx' )

    
    # Check if all required columns exist in the DataFrame
    missing_columns = [ f for f in col_labels_types.keys()
                       if f not in ant_params_df ]
    if missing_columns:
        raise ValueError(
            f"Missing columns in the file: {missing_columns}. "
            f"Expected columns: {missing_columns}"
        )
    
    # Filter only columns that exist in the class
    ant_params_df = ant_params_df[col_labels_types.keys()]
    
    # Convert each line to a AntennaParamsFromFile object
    ant_params_list = [AntennaParamsFromFile(**row) for row in ant_params_df.to_dict('records')]
    
    return ant_params_list