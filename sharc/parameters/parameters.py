# -*- coding: utf-8 -*-
"""
Created on Wed Aug  9 19:35:52 2017

@author: edgar
"""

import sys
import os

from sharc.parameters.parameters_general import ParametersGeneral
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.parameters.parameters_eess_ss import ParametersEessSS
from sharc.parameters.parameters_fs import ParametersFs
from sharc.parameters.parameters_metsat_ss import ParametersMetSatSS
from sharc.parameters.parameters_fss_ss import ParametersFssSs
from sharc.parameters.parameters_fss_es import ParametersFssEs
from sharc.parameters.parameters_haps import ParametersHaps
from sharc.parameters.parameters_rns import ParametersRns
from sharc.parameters.parameters_ras import ParametersRas
from sharc.parameters.parameters_single_earth_station import ParametersSingleEarthStation
from sharc.parameters.parameters_mss_ss import ParametersMssSs
from sharc.parameters.parameters_mss_d2d import ParametersMssD2d
from sharc.parameters.parameters_single_space_station import ParametersSingleSpaceStation
from sharc.parameters.database.parameters_database import ParametersDatabase


class Parameters(object):
    """
    Reads parameters from input file.
    """

    def __init__(self):
        self.file_name = None

        self.general = ParametersGeneral()
        self.imt = ParametersImt()
        self.eess_ss = ParametersEessSS()
        self.fs = ParametersFs()
        self.fss_ss = ParametersFssSs()
        self.fss_es = ParametersFssEs()
        self.haps = ParametersHaps()
        self.rns = ParametersRns()
        self.ras = ParametersRas()
        self.single_earth_station = ParametersSingleEarthStation()
        self.single_space_station = ParametersSingleSpaceStation()
        self.metsat_ss = ParametersMetSatSS()
        self.mss_ss = ParametersMssSs()
        self.mss_d2d = ParametersMssD2d()
        self.database = ParametersDatabase()

    def set_file_name(self, file_name: str):
        """sets the configuration file name

        Parameters
        ----------
        file_name : str
            configuration file path
        """
        self.file_name = file_name

    def read_params(self):
        """Read the parameters from the config file
        """
        if not os.path.isfile(self.file_name):
            err_msg = f"PARAMETER ERROR [{self.__class__.__name__}]: \
                Could not find the configuration file {self.file_name}"
            sys.stderr.write(err_msg)
            sys.exit(1)

        #######################################################################
        # GENERAL
        #######################################################################
        self.general.load_parameters_from_file(self.file_name)

        #######################################################################
        # IMT
        #######################################################################
        self.imt.load_parameters_from_file(self.file_name)

        #######################################################################
        # FSS space station
        #######################################################################
        self.fss_ss.load_parameters_from_file(self.file_name)

        #######################################################################
        # FSS earth station
        #######################################################################
        self.fss_es.load_parameters_from_file(self.file_name)

        #######################################################################
        # Fixed wireless service
        #######################################################################
        self.fs.load_parameters_from_file(self.file_name)

        #######################################################################
        # HAPS (airbone) station
        #######################################################################
        self.haps.load_parameters_from_file(self.file_name)

        #######################################################################
        # RNS
        #######################################################################
        self.rns.load_parameters_from_file(self.file_name)

        #######################################################################
        # RAS station
        #######################################################################
        self.ras.load_parameters_from_file(self.file_name)

        #######################################################################
        # EESS passive
        #######################################################################
        self.eess_ss.load_parameters_from_file(self.file_name)

        #######################################################################
        # Single Earth Station
        #######################################################################
        self.single_earth_station.load_parameters_from_file(self.file_name)

        #######################################################################
        # MSS_SS
        #######################################################################
        self.mss_ss.load_parameters_from_file(self.file_name)

        #######################################################################
        # MSS_D2d
        #######################################################################
        self.mss_d2d.load_parameters_from_file(self.file_name)

        self.single_space_station.load_parameters_from_file(self.file_name)

        #######################################################################
        # Base-station database (optional)
        #######################################################################
        self.database.load_parameters_from_file(self.file_name)
        if self.database.is_loaded:
            # general.num_snapshots counts the snapshots of ONE subset: the
            # subsets are simulated in order, each one that many times.
            self.database.set_snapshots_per_subset(self.general.num_snapshots)
            self.general.num_snapshots *= self.database.num_subsets
            if self.database.use_real_terrain:
                self._compute_database_terrain()
        uses_p452_from_db = self.general.system == "SINGLE_EARTH_STATION" \
            and self.single_earth_station.channel_model == "P452" \
            and self.single_earth_station.param_p452.override_from_db
        if uses_p452_from_db and not (self.database.is_loaded and self.database.use_real_terrain):
            raise ValueError(
                "single_earth_station.param_p452.override_from_db needs a database "
                "with use_real_terrain")

    def _compute_database_terrain(self):
        """Terrain between the database sites and the victim, once per run.

        Gives every site its ground altitude and, with the P452 channel model
        and override_from_db, the P.452 loss of every BS. The victim station
        is placed on the ground altitude of the same profiles, instead of the
        altitude of its fixed_geo location.
        """
        ses = self.single_earth_station
        if self.general.system != "SINGLE_EARTH_STATION" or ses.geometry.location.type != "FIXED_GEO":
            raise ValueError(
                "database.use_real_terrain needs general.system SINGLE_EARTH_STATION "
                "with a FIXED_GEO location: the terrain profiles go from it to each BS")
        fixed_geo = ses.geometry.location.fixed_geo
        frequency_ghz = None
        if ses.channel_model == "P452" and ses.param_p452.override_from_db:
            frequency_ghz = self.imt.frequency / 1000.0
        self.database.compute_terrain(
            fixed_geo.latitude, fixed_geo.longitude, ses.param_p452, frequency_ghz,
        )
        ground = self.database.data_full["cota_terreno"]
        print(
            f"[terrain] victim ground {self.database.reference_ground:.2f} m "
            f"(fixed_geo.altitude {fixed_geo.altitude:.2f} m not used), "
            f"BS ground {ground.min():.1f} to {ground.max():.1f} m"
            + ("" if frequency_ghz is None else ", P.452 losses precomputed")
        )
        fixed_geo.altitude = self.database.reference_ground


if __name__ == "__main__":
    from pprint import pprint
    parameters = Parameters()
    param_sections = [
        a for a in dir(parameters) if not a.startswith('__') and not
        callable(getattr(parameters, a))
    ]
    print("\n#### Dumping default parameters:")
    for p in param_sections:
        print("\n")
        pprint(getattr(parameters, p))
