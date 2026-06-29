
"""Antenna factory module for creating antenna instances based on parameters."""
from sharc.parameters.parameters_antenna import ParametersAntenna
from sharc.antenna.antenna import Antenna

from sharc.antenna.antenna_element_cosine import AntennaElementCosine
from sharc.antenna.antenna_omni import AntennaOmni
from sharc.antenna.antenna_mss_hibleo_x_ue import AntennaMssHibleoXUe
from sharc.antenna.antenna_f699 import AntennaF699
from sharc.antenna.antenna_s465 import AntennaS465
from sharc.antenna.antenna_rra7_3 import AntennaReg_RR_A7_3
from sharc.antenna.antenna_s580 import AntennaS580
from sharc.antenna.antenna_s1528 import AntennaS1528
from sharc.antenna.antenna_s1855 import AntennaS1855
from sharc.antenna.antenna_f1245_fs import Antenna_f1245_fs
from sharc.antenna.antenna_s1528 import AntennaS1528, AntennaS1528Leo, AntennaS1528Taylor
from sharc.antenna.antenna_beamforming_imt import AntennaBeamformingImt
from sharc.antenna.antenna_array import AntennaArray
from sharc.support.geometry import SimulatorGeometry, RigidTransform
from sharc.antenna.system_4_constants import taper_fn as sys4_taper_fn
from sharc.antenna.antenna_from_table import AntennaFromTable
from sharc.antenna.antenna_f1336 import AntennaF1336
from sharc.antenna.antenna_m1851 import AntennaM1851

import numpy as np


class AntennaFactory():
    """Factory class for creating antenna instances based on pattern parameters."""

    @staticmethod
    def create_antenna(
        antenna_params: ParametersAntenna,
        azimuth: float,
        elevation: float,
        *,
        global2local_ref_frame: RigidTransform = None
    ):
        """Create and return an antenna instance based on the provided parameters, azimuth, and elevation.

        Args:
            antenna_params (ParametersAntenna): The parameters defining the antenna configuration.
            azimuth (float): The azimuth angle for the antenna.
            elevation (float): The elevation angle for the antenna.
            oob_pattern (str, optional): Out-of-band pattern to use instead of the main pattern.
        Returns:
            Antenna: An instance of the appropriate Antenna subclass.
        """
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
            case "ITU-R F.1245_fs":
                return Antenna_f1245_fs(antenna_params.itu_r_f_1245_fs)
            case "ITU-R Reg. RR. Appendice 7 Annex 3":
                return AntennaReg_RR_A7_3(antenna_params.itu_reg_rr_a7_3)
            case "Cosine Antenna":
                return AntennaElementCosine()
            case "ARRAY":
                return AntennaBeamformingImt(
                    antenna_params.array.get_antenna_parameters(),
                    azimuth,
                    elevation
                )
            case "ARRAY Satellite" | "ARRAY System 4":
                taper_fn = None
                if antenna_params.pattern == "ARRAY System 4":
                    taper_fn = sys4_taper_fn

                arr = AntennaArray(
                    antenna_params.array.get_antenna_parameters(),
                    global2local_ref_frame,
                    per_element_taper_fn=taper_fn
                )
                arr.add_beam(
                    azimuth,
                    90. - elevation,
                )
                arr.set_always_first_beam()
                return arr
            case "Antenna System 4":
                # Handled in station_factory.py since it requires two antennas
                raise NotImplementedError(
                    "Antenna System 4 requires two antenna instances and "
                    "should be created in station_factory.py"
                )
            case "FROM TABLE":
                return AntennaFromTable(antenna_params.from_table)
            case "ITU-R F.1336":
                return AntennaF1336(antenna_params.itu_r_f_1336)
            case "ITU-R M.1851":
                return AntennaM1851(antenna_params.itu_r_m_1851)
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
        *,
        geom: SimulatorGeometry = None
    ):
        """
        Create many antennas based on passed parameters.

        If antenna does not require each object to have different state,
        only a single antenna object will be created, and every position
        in the array will point to it.
        This is much more performant.
        Args:
            antenna_params (ParametersAntenna): The parameters defining the antenna configuration.
            azimuth (np.ndarray | float): The azimuth angles for the antennas.
            elevation (np.ndarray | float): The elevation angles for the antennas.
            n_stations (int): Number of antennas to create.
        Returns:
            np.ndarray: An array of Antenna instances.
        """
        antennas = np.empty((n_stations,), dtype=Antenna)
        assert n_stations == len(azimuth)
        assert n_stations == len(elevation)

        if antenna_params.pattern in [
            "ARRAY", "ARRAY Satellite", "ARRAY System 4"
        ]:
            for i in range(n_stations):
                global2local_reference_frame = None
                if hasattr(geom, "global2local") and geom.global2local is not None:
                    global2local_reference_frame = geom.global2local.take(i)
                antennas[i] = AntennaFactory.create_antenna(
                    antenna_params, azimuth[i], elevation[i],
                    global2local_ref_frame=global2local_reference_frame
                )

            if antenna_params.pattern in ["ARRAY Satellite", "ARRAY System 4"]:
                geom.set_local_coords(
                    azim=np.zeros_like(geom.pointn_azim_global),
                    elev=np.zeros_like(geom.pointn_elev_global),
                )

        elif antenna_params.pattern == "Antenna System 4":
            antenna_pattern_high = AntennaS1528(antenna_params.antenna_system_4.antenna_parameters_high)
            antenna_pattern_low = AntennaS1528(antenna_params.antenna_system_4.antenna_parameters_low)
            for i in range(n_stations):
                if antenna_params.antenna_system_4.beam_ground_elev_angles[i] >= 50:
                    antennas[i] = antenna_pattern_high
                else:
                    antennas[i] = antenna_pattern_low
        else:
            # some antennas don't need azimuth and elevation at all
            # this makes it much faster
            antennas[:] = AntennaFactory.create_antenna(
                antenna_params, None, None,
            )

        return antennas
