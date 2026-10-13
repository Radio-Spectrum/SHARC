
"""Antenna factory module for creating antenna instances based on parameters."""
import copy

from sharc.parameters.parameters_antenna import ParametersAntenna
from sharc.antenna.antenna import Antenna

from sharc.antenna.antenna_mss_adjacent import AntennaMSSAdjacent
from sharc.antenna.antenna_omni import AntennaOmni
from sharc.antenna.antenna_mss_hibleo_x_ue import AntennaMssHibleoXUe
from sharc.antenna.antenna_f699 import AntennaF699
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.antenna.antenna_rra7_3 import AntennaReg_RR_A7_3
from sharc.antenna.antenna_s580 import AntennaS580
from sharc.antenna.antenna_s1528 import AntennaS1528
from sharc.antenna.antenna_s672 import AntennaS672
from sharc.antenna.antenna_s1855 import AntennaS1855
from sharc.antenna.antenna_f1245_fs import Antenna_f1245_fs
from sharc.antenna.antenna_s1528 import AntennaS1528, AntennaS1528Leo, AntennaS1528Taylor
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt
from sharc.antenna.antenna_sa509 import AntennaSA509

import numpy as np


class AntennaFactory():
    """Factory class for creating antenna instances based on pattern parameters."""

    @staticmethod
    def create_antenna(
        antenna_params: ParametersAntenna,
        azimuth: float,
        elevation: float,
    ):
        """Create and return an antenna instance based on the provided parameters, azimuth, and elevation."""
        match antenna_params.pattern:
            case "OMNI":
                return AntennaOmni(antenna_params.gain)
            case "HibleoX":
                return AntennaMssHibleoXUe(antenna_params.hibleo_x.frequency)
            case "ITU-R F.699":
                return AntennaF699(antenna_params.itu_r_f_699)
            case "ITU-R-S.1528-Taylor":
                return AntennaS1528Taylor(antenna_params.itu_r_s_1528)
            case "ITU-R-S.1528-LEO":
                return AntennaS1528Leo(antenna_params.itu_r_s_1528)
            case "ITU-R-S.1528-Section1.2":
                return AntennaS1528(antenna_params.itu_r_s_1528)
            case "ITU-R S.465":
                return AntennaS465(antenna_params.itu_r_s_465)
            case "ITU-R S.580":
                return AntennaS580(antenna_params.itu_r_s_580)
            case "MODIFIED ITU-R S.465":
                return AntennaS465(antenna_params.itu_r_s_465_modified)
            case "ITU-R S.1855":
                return AntennaS1855(antenna_params.itu_r_s_1855)
            case "ITU-R S.672":
                return AntennaS672(antenna_params.itu_r_s_672)
            case "ITU-R F.1245_fs":
                return Antenna_f1245_fs(antenna_params.itu_r_f_1245_fs)
            case "ITU-R Reg. RR. Appendice 7 Annex 3":
                return AntennaReg_RR_A7_3(antenna_params.itu_reg_rr_a7_3)
            case "ITU-R SA.509":
                return AntennaSA509(antenna_params.itu_r_sa_509)
            case "MSS Adjacent":
                return AntennaMSSAdjacent(
                    antenna_params.mss_adjacent.frequency)
            case "ARRAY":
                return AntennaBeamformingImt(
                    antenna_params.array.get_antenna_parameters(),
                    azimuth,
                    elevation
                )
            case _:
                raise ValueError(
                    f"Antenna factory does not support pattern {
                        antenna_params.pattern}")

    @staticmethod
    def create_n_antennas(
        antenna_params: ParametersAntenna,
        azimuth: np.ndarray | float,
        elevation: np.ndarray | float,
        n_stations: int,
    ):
        """
        Creates many antennas based on passed parameters.
        If antenna does not require each object to have different state,
        only a single antenna object will be created, and every position
        in the array will point to it.
        This is much more performant.
        """
        antennas = np.empty((n_stations,), dtype=Antenna)
        assert n_stations == len(azimuth)
        assert n_stations == len(elevation)

        if n_stations == 0:
            return antennas

        if antenna_params.pattern == "ARRAY":
            first = AntennaFactory.create_antenna(
                antenna_params, azimuth[0], elevation[0],
            )
            if getattr(first, "constant_gain", False):
                # 1x1 constant-gain "array" (e.g. a -4 dBi UE): the gain does
                # not depend on orientation or beams, share a single object.
                antennas[:] = first
            else:
                antennas[0] = first
                for i in range(1, n_stations):
                    antennas[i] = AntennaFactory.create_antenna(
                        antenna_params, azimuth[i], elevation[i],
                    )
        else:
            # some antennas don't need azimuth and elevation at all
            # this makes it much faster
            antennas[:] = AntennaFactory.create_antenna(
                antenna_params, None, None,
            )

        return antennas

    @staticmethod
    def create_n_antennas_from_db(
        antenna_params: ParametersAntenna,
        db_antenna_params: list,
        azimuth: np.ndarray,
        elevation: np.ndarray,
        n_stations: int,
    ):
        """Create one array antenna per station, with per-station database values.

        Every station starts from antenna_params.array; n_rows, n_columns,
        element_max_g and the subarray rows are replaced by the values of its
        AntennaParamsFromFile. Stations with the same values share one
        parameter object, so the batched beam and gain computations still
        apply when the whole network uses the same array.

        Parameters
        ----------
        antenna_params : ParametersAntenna
            Antenna parameters from the parameter file (pattern ARRAY).
        db_antenna_params : list of AntennaParamsFromFile
            One entry per station.
        azimuth, elevation : np.ndarray
            Pointing of each station, in its local frame [deg].
        n_stations : int
            Number of stations.

        Returns
        -------
        np.ndarray
            Array of AntennaBeamformingImt, one per station.
        """
        if antenna_params.pattern != "ARRAY":
            raise ValueError(
                "Antenna parameters from the database need the ARRAY pattern, "
                f"not {antenna_params.pattern}")
        assert n_stations == len(azimuth)
        assert n_stations == len(elevation)
        assert n_stations == len(db_antenna_params)

        base = antenna_params.array.get_antenna_parameters()
        if base.normalization:
            raise ValueError(
                "Beamforming normalization is not supported with antenna "
                "parameters from the database: the normalization data is "
                "computed for the array of the parameter file")

        shared = {}
        antennas = np.empty((n_stations,), dtype=Antenna)
        for i, db in enumerate(db_antenna_params):
            key = (db.n_rows, db.n_columns, db.element_max_g, db.sub_num_rows)
            par = shared.get(key)
            if par is None:
                # shallow copies keep the attributes set outside the
                # dataclass fields (e.g. adjacent_antenna_model)
                par = copy.copy(base)
                par.n_rows = db.n_rows
                par.n_columns = db.n_columns
                par.element_max_g = db.element_max_g
                par.subarray = copy.copy(base.subarray)
                par.subarray.n_rows = db.sub_num_rows
                shared[key] = par
            antennas[i] = AntennaBeamformingImt(par, azimuth[i], elevation[i])

        return antennas
