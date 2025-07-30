import numpy as np
import math
import unittest
import numpy.testing as npt

from sharc.simulation import Simulation
from sharc.results import Results
from sharc.parameters.parameters import Parameters
from sharc.parameters.parameters_base import ParametersBase

from sharc.simulation_downlink import SimulationDownlink
from sharc.simulation_uplink import SimulationUplink
from sharc.parameters.parameters import Parameters
from sharc.antenna.antenna_omni import AntennaOmni
from sharc.station_factory import StationFactory
from sharc.propagation.propagation_factory import PropagationFactory
from sharc.parameters.imt.parameters_imt_topology import ParametersImtTopology
from sharc.parameters.imt.parameters_single_bs import ParametersSingleBS
from sharc.propagation.propagation_free_space import PropagationFreeSpace


class SimulationE2EAdjacentTest(unittest.TestCase):
    """
    This is not an unit test, but also isn't that E2E.
    It doesn't test modules, but that the input and output of
    simulator is unchanged considering adjacent channel coupling loss and interference.
    """
    def setUp(self):
        """Set up the test environment and initialize simulation parameters."""
        self.fspl = PropagationFreeSpace(np.random.RandomState())

        self.param = Parameters()

        self.param.general.enable_cochannel = False
        self.param.general.enable_adjacent_channel = True
        self.param.general.seed = 101

        self.param.imt.interfered_with = False
        self.param.imt.guard_band_ratio = 0.1
        self.param.general.system = "SINGLE_EARTH_STATION"

        self.param.imt.frequency = 25e3
        self.param.imt.bandwidth = 100
        self.param.imt.spectral_mask = "IMT-2020"
        self.param.imt.spurious_emissions = -13
        self.param.imt.adjacent_ch_emissions = "SPECTRAL_MASK"
        self.param.imt.topology.type = "SINGLE_BS"
        self.param.imt.topology.single_bs.intersite_distance = 200 * 3 / 2
        self.param.imt.topology.single_bs.cell_radius = 200
        self.param.imt.topology.single_bs.num_clusters = 2
        self.param.imt.adjacent_antenna_model = "SINGLE_ELEMENT"

        self.param.imt.bs.load_probability = 1
        self.param.imt.bs.antenna.array.downtilt = 0
        self.param.imt.bs.antenna.array.element_max_g = -3
        self.param.imt.bs.antenna.array.n_columns = 4
        self.param.imt.bs.antenna.array.n_rows = 4
        self.param.imt.bs.conducted_power = 2
        self.param.imt.bs.height = 6
        self.param.imt.bs.ohmic_loss = 0.0
        self.param.imt.bs.body_loss = 0.0

        self.param.imt.ue.k = 1
        self.param.imt.ue.k_m = 1
        self.param.imt.ue.tx_power_control = "OFF"
        self.param.imt.ue.p_cmax = 13

        self.param.imt.ue.conducted_power = 10
        self.param.imt.ue.height = 1.5
        self.param.imt.ue.aclr = 6
        self.param.imt.ue.acs = 7
        self.param.imt.ue.noise_figure = 9

        self.param.imt.ue.antenna.array.element_max_g = -2
        self.param.imt.ue.antenna.array.element_pattern = "FIXED"

        self.param.imt.ue.ohmic_loss = 0.0
        self.param.imt.ue.body_loss = 0.0

        self.param.imt.noise_temperature = 290
        self.param.imt.channel_model = "FSPL"

        self.param.single_earth_station.channel_model = "FSPL"

        self.param.single_earth_station.adjacent_ch_reception = "OFF"
        self.param.single_earth_station.tx_power_density = 0.0
        self.param.single_earth_station.antenna.gain = 1.0
        self.param.single_earth_station.antenna.pattern = "OMNI"
        self.param.single_earth_station.frequency = 1e3
        self.param.single_earth_station.bandwidth = 100
        self.param.single_earth_station.geometry.height = 6
        self.param.single_earth_station.geometry.azimuth.type = "FIXED"
        self.param.single_earth_station.geometry.azimuth.fixed = 180
        self.param.single_earth_station.geometry.elevation.type = "FIXED"
        self.param.single_earth_station.geometry.elevation.fixed = 0
        self.param.single_earth_station.geometry.location.type = "FIXED"
        self.param.single_earth_station.geometry.location.fixed.x = 200
        self.param.single_earth_station.geometry.location.fixed.y = 0
        self.param.single_earth_station.polarization_loss = 0
        self.param.single_earth_station.noise_temperature = 290

        # replacing load parameters to be able to use parameters load validations
        # own load paarameters usage
        ParametersBase.load_parameters_from_file = lambda x, y: None
        self.param.imt.load_parameters_from_file("")
        self.param.imt.validate("imt")
        self.param.single_earth_station.load_parameters_from_file("")
        self.param.single_earth_station.validate("single_earth_station")

    def lin(self, dB):
        """Convert decibel (dB) values to linear scale."""
        return 10 ** (0.1 * dB)

    def dB(self, lin):
        """Convert linear scale values to decibel (dB)."""
        return 10 * np.log10(lin)

    def assert_imt_dl_to_sys_results_attr(
        self,
        res: Results,
        k: int, n_bs: int,
    ):
        """
        This is a common method that tests whether the provided results
        contain the correct number of values for each attribute in Results.
        It works for IMT DL, system victim.

        It checks for common attributes, some more may be tested depending
        on the test case.
        """
        n_sys = 1
        n_beams = k * n_bs

        # testing attributes that should be per beams
        self.assertEqual(len(res.imt_dl_tx_power), n_beams)

        # testing attributes that should be per beam towards system
        self.assertEqual(len(res.imt_system_antenna_gain_adjacent), n_beams * n_sys)
        self.assertEqual(len(res.imt_system_path_loss), n_beams * n_sys)
        # NOTE: it may not have co-channel since this test is for adjacent
        # self.assertEqual(len(res.imt_system_antenna_gain), n_beams * n_sys)

        # testing attributes that should be per system
        self.assertEqual(len(res.system_dl_interf_power), n_sys)
        self.assertEqual(len(res.system_dl_interf_power_per_mhz), n_sys)
        self.assertEqual(len(res.system_inr), n_sys)

        # testing attributes that should be per system towards imt
        self.assertEqual(len(res.system_imt_antenna_gain), n_sys * n_beams)

    def assert_imt_ul_to_sys_results_attr(
        self,
        res: Results,
        k: int, n_bs: int,
    ):
        """
        This is a common method that tests whether the provided results
        contain the correct number of values for each attribute in Results.
        It works for IMT UL, system victim.

        It checks for common attributes, some more may be tested depending
        on the test case.
        """
        n_sys = 1
        n_ue = k * n_bs

        # testing attributes that should be per ue
        self.assertEqual(len(res.imt_ul_tx_power), n_ue)
        self.assertEqual(len(res.imt_ul_tx_power_density), n_ue)

        # testing attributes that should be per ue towards system
        self.assertEqual(len(res.imt_system_antenna_gain_adjacent), n_ue * n_sys)
        self.assertEqual(len(res.imt_system_path_loss), n_ue * n_sys)
        # NOTE: it may not have co-channel since this test is for adjacent
        # self.assertEqual(len(res.imt_system_antenna_gain), n_ue * n_sys)

        # testing attributes that should be per system
        self.assertEqual(len(res.system_ul_interf_power), n_sys)
        self.assertEqual(len(res.system_ul_interf_power_per_mhz), n_sys)
        self.assertEqual(len(res.system_inr), n_sys)

        # testing attributes that should be per system towards imt
        self.assertEqual(len(res.system_imt_antenna_gain), n_sys * n_ue)

    def test_2bs_to_es_mask(self):
        """
        Testing BS spectral mask interference
        This simplifies spectral mask calculation by only getting the spurious emissions
        """
        self.param.general.imt_link = "DOWNLINK"
        self.param.imt.interfered_with = False

        self.param.imt.ue.k = 1
        simulation_1k = SimulationDownlink(self.param, "")
        simulation_1k.initialize()

        self.assertFalse(simulation_1k.co_channel)

        simulation_1k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=14,
        )

        """
        We also check that spectral mask emissions don't depend on ue.k
        """
        self.param.imt.ue.k = 3
        simulation_3k = SimulationDownlink(self.param, "")
        simulation_3k.initialize()

        simulation_3k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=13,
        )

        self.assertEqual(
            simulation_1k.coupling_loss_imt_system_adjacent.shape,
            (2, 1)
        )
        self.assertEqual(
            simulation_3k.coupling_loss_imt_system_adjacent.shape,
            (6, 1)
        )

        p_loss = self.fspl.get_loss(
            simulation_1k.bs.get_3d_distance_to(simulation_1k.system),
            # TODO: maybe should change this?
            np.array([self.param.imt.frequency])
        )
        npt.assert_array_equal(
            p_loss.flatten(),
            simulation_1k.results.imt_system_path_loss
        )

        g1 = self.param.imt.bs.antenna.array.element_max_g
        g2 = self.param.single_earth_station.antenna.gain
        coupling = p_loss - g1 - g2
        npt.assert_allclose(
            coupling,
            simulation_1k.coupling_loss_imt_system_adjacent
        )
        npt.assert_allclose(
            simulation_1k.coupling_loss_imt_system_adjacent.repeat(3),
            np.ravel(simulation_3k.coupling_loss_imt_system_adjacent)
        )

        mask_power = self.param.imt.spurious_emissions + self.dB(self.param.single_earth_station.bandwidth)
        rx_power = self.dB(self.lin(mask_power - coupling).sum())
        self.assertEqual(
            len(simulation_1k.results.system_dl_interf_power),
            1
        )
        npt.assert_almost_equal(
            simulation_1k.results.system_dl_interf_power,
            rx_power
        )

        npt.assert_allclose(
            simulation_3k.coupling_loss_imt_system_adjacent,
            simulation_1k.coupling_loss_imt_system_adjacent[0][0],
        )
        npt.assert_almost_equal(
            simulation_3k.results.system_dl_interf_power,
            simulation_1k.results.system_dl_interf_power,
        )

        self.assert_imt_dl_to_sys_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_imt_dl_to_sys_results_attr(
            simulation_3k.results,
            3, 2
        )

    def test_2bs_to_es_aclr_and_acs_partial_overlap(self):
        """
        Testing BS acs and aclr with partial co-channel
        """
        self.param.general.imt_link = "DOWNLINK"
        self.param.imt.interfered_with = False

        self.param.imt.adjacent_ch_emissions = "ACLR"
        self.param.single_earth_station.adjacent_ch_reception = "ACS"

        self.param.imt.bs.adjacent_ch_leak_ratio = 10.
        self.param.single_earth_station.adjacent_ch_selectivity = 5.

        self.param.imt.frequency = 800.
        self.param.imt.bandwidth = 100.
        overlap = 50.
        self.param.single_earth_station.frequency = 800 + 75. / 2
        self.param.single_earth_station.bandwidth = 75.

        self.param.imt.ue.k = 1
        simulation_1k = SimulationDownlink(self.param, "")
        simulation_1k.initialize()

        self.assertFalse(simulation_1k.co_channel)

        simulation_1k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=14,
        )

        """
        We also check that system rx interference doesn't depend on ue.k
        """
        self.param.imt.ue.k = 3
        simulation_3k = SimulationDownlink(self.param, "")
        simulation_3k.initialize()

        simulation_3k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=13,
        )

        self.assertEqual(
            simulation_1k.coupling_loss_imt_system_adjacent.shape,
            (2, 1)
        )
        self.assertEqual(
            simulation_3k.coupling_loss_imt_system_adjacent.shape,
            (6, 1)
        )

        p_loss = self.fspl.get_loss(
            simulation_1k.bs.get_3d_distance_to(simulation_1k.system),
            # TODO: maybe should change this?
            np.array([self.param.imt.frequency])
        )
        npt.assert_array_equal(
            p_loss.flat[0],
            simulation_3k.results.imt_system_path_loss
        )
        npt.assert_array_equal(
            p_loss.flat[0],
            simulation_1k.results.imt_system_path_loss
        )

        g1_adj = self.param.imt.bs.antenna.array.element_max_g
        g1_co_1k = np.zeros((1, 2))

        for i in range(2):
            phi = 0. if i == 0 else 180.
            g1_co_1k[0][i] = simulation_1k.bs.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([90.]),
                beams_l=np.array([0]),
                co_channel=True,
            )
        npt.assert_allclose(
            simulation_1k.results.imt_system_antenna_gain,
            g1_co_1k.flatten()
        )

        g1_co_3k = np.zeros((3, 2))
        for k in range(3):
            for i in range(2):
                phi = 0. if i == 0 else 180.
                g1_co_3k[k][i] = simulation_3k.bs.antenna[i].calculate_gain(
                    phi_vec=np.array([phi]),
                    theta_vec=np.array([90.]),
                    beams_l=np.array([k]),
                    co_channel=True,
                )
        g1_co_3k = np.reshape(np.transpose(g1_co_3k), (1, 6))
        npt.assert_allclose(
            # the order may not be the same, so we sort
            sorted(simulation_3k.results.imt_system_antenna_gain),
            sorted(g1_co_3k.flatten())
        )

        g2 = self.param.single_earth_station.antenna.gain

        adj_coupling = p_loss - np.transpose(g1_adj) - g2
        coc_coupling_1k = p_loss - np.transpose(g1_co_1k) - g2
        coc_coupling_3k = np.reshape(p_loss.repeat(3), (6, 1)) - np.transpose(g1_co_3k) - g2

        npt.assert_allclose(
            simulation_1k.coupling_loss_imt_system_adjacent,
            adj_coupling,
        )
        npt.assert_allclose(
            np.ravel(simulation_3k.coupling_loss_imt_system_adjacent),
            np.ravel(adj_coupling.repeat(3)),
        )

        npt.assert_allclose(
            coc_coupling_1k,
            simulation_1k.coupling_loss_imt_system
        )
        npt.assert_allclose(
            coc_coupling_3k,
            simulation_3k.coupling_loss_imt_system
        )
        imt_non_overlap = self.param.imt.bandwidth - overlap
        sys_non_overlap = self.param.single_earth_station.bandwidth - overlap

        imt_measurement_bw = self.param.imt.bandwidth

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            PSD = tx_pow_lin / tx_bw
            tx_pow_adj_lin = PSD * non_overlap_imt_bw
            rx_oob = tx_pow_adj_lin / acs
        """
        tx_lin_1k = self.lin(np.array(list(simulation_1k.bs.tx_power.values())))
        tx_lin_3k = self.lin(np.array(list(simulation_3k.bs.tx_power.values())))

        tx_bw = self.param.imt.bandwidth

        rx_oob_lin_1k = (tx_lin_1k / tx_bw) * imt_non_overlap / self.lin(
            self.param.single_earth_station.adjacent_ch_selectivity
        )
        rx_oob_lin_3k = (tx_lin_3k / tx_bw) * imt_non_overlap / self.lin(
            self.param.single_earth_station.adjacent_ch_selectivity
        )

        rx_oob_1k = self.dB(rx_oob_lin_1k)
        rx_oob_3k = self.dB(rx_oob_lin_3k)

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            tx_oob_in_measurement = (tx_pow_lin / aclr)
            => PSD = (tx_pow_lin / aclr) / measurement_bw
            => received tx_oob = PSD * non_overlap_sys_bw
        """
        psd_1k = (tx_lin_1k / self.lin(
            self.param.imt.bs.adjacent_ch_leak_ratio
        )) / imt_measurement_bw
        psd_3k = (tx_lin_3k / self.lin(
            self.param.imt.bs.adjacent_ch_leak_ratio
        )) / imt_measurement_bw

        tx_oob_1k = self.dB(psd_1k * sys_non_overlap)
        tx_oob_3k = self.dB(psd_3k * sys_non_overlap)

        rx_power_1k = self.dB(
            self.lin(rx_oob_1k - coc_coupling_1k).sum() + \
            self.lin(tx_oob_1k - adj_coupling).sum()
        )
        rx_power_3k = self.dB(
            self.lin(rx_oob_3k.reshape(coc_coupling_3k.shape) - coc_coupling_3k).sum() + \
            self.lin(tx_oob_3k - adj_coupling).sum()
        )

        self.assertEqual(
            len(simulation_1k.results.system_dl_interf_power),
            1
        )
        self.assertEqual(
            len(simulation_3k.results.system_dl_interf_power),
            1
        )

        npt.assert_almost_equal(
            simulation_1k.results.system_dl_interf_power,
            rx_power_1k
        )
        npt.assert_almost_equal(
            simulation_3k.results.system_dl_interf_power,
            rx_power_3k,
        )

        self.assert_imt_dl_to_sys_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_imt_dl_to_sys_results_attr(
            simulation_3k.results,
            3, 2
        )

    def test_ue_to_es_mask(self):
        """
        Testing UE spectral mask interference
        This simplifies spectral mask calculation by only getting the spurious emissions
        """
        self.param.general.imt_link = "UPLINK"
        self.param.imt.interfered_with = False

        self.param.imt.ue.k = 1
        simulation_1k = SimulationUplink(self.param, "")
        simulation_1k.initialize()

        self.assertFalse(simulation_1k.co_channel)

        simulation_1k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=14,
        )

        """
        We also check for ue.k = 3
        """
        self.param.imt.ue.k = 3
        simulation_3k = SimulationUplink(self.param, "")
        simulation_3k.initialize()

        simulation_3k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=13,
        )

        self.assertEqual(
            simulation_1k.coupling_loss_imt_system_adjacent.shape,
            (2, 1)
        )
        self.assertEqual(
            simulation_3k.coupling_loss_imt_system_adjacent.shape,
            (6, 1)
        )

        p_loss_1k = self.fspl.get_loss(
            simulation_1k.ue.get_3d_distance_to(simulation_1k.system),
            # TODO: maybe should change this?
            np.array([self.param.imt.frequency])
        )
        npt.assert_array_equal(
            p_loss_1k.flatten(),
            simulation_1k.results.imt_system_path_loss
        )
        p_loss_3k = self.fspl.get_loss(
            simulation_3k.ue.get_3d_distance_to(simulation_3k.system),
            # TODO: maybe should change this?
            np.array([self.param.imt.frequency])
        )
        npt.assert_array_equal(
            sorted(p_loss_3k.flatten()),
            sorted(simulation_3k.results.imt_system_path_loss)
        )

        g1 = self.param.imt.ue.antenna.array.element_max_g
        g2 = self.param.single_earth_station.antenna.gain
        coupling_1k = p_loss_1k - g1 - g2
        coupling_3k = p_loss_3k - g1 - g2
        npt.assert_allclose(
            coupling_1k,
            simulation_1k.coupling_loss_imt_system_adjacent
        )
        npt.assert_allclose(
            coupling_3k.flatten(),
            simulation_3k.coupling_loss_imt_system_adjacent.flatten()
        )

        mask_power = self.param.imt.spurious_emissions + self.dB(self.param.single_earth_station.bandwidth)
        rx_power = self.dB(self.lin(mask_power - coupling_1k).sum())
        self.assertEqual(
            len(simulation_1k.results.system_ul_interf_power),
            1
        )
        npt.assert_almost_equal(
            simulation_1k.results.system_ul_interf_power,
            rx_power
        )
        # checking if interf from 3k is next to 3 * higher
        npt.assert_allclose(
            simulation_3k.results.system_ul_interf_power,
            simulation_1k.results.system_ul_interf_power + self.dB(3),
            atol=0.8
        )

        self.assert_imt_ul_to_sys_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_imt_ul_to_sys_results_attr(
            simulation_3k.results,
            3, 2
        )

    def test_ue_to_es_aclr_and_acs_partial_overlap(self):
        """
        Testing ue acs and aclr with partial co-channel
        """
        self.param.imt.ue.antenna.array.element_pattern = "M2101"
        self.param.imt.ue.antenna.array.element_max_g = -2
        self.param.imt.ue.antenna.array.n_columns = 2
        self.param.imt.ue.antenna.array.n_rows = 2

        self.param.general.imt_link = "UPLINK"
        self.param.imt.interfered_with = False

        self.param.imt.adjacent_ch_emissions = "ACLR"
        self.param.single_earth_station.adjacent_ch_reception = "ACS"

        self.param.imt.ue.adjacent_ch_leak_ratio = 10.
        self.param.single_earth_station.adjacent_ch_selectivity = 5.

        self.param.imt.frequency = 800.
        self.param.imt.bandwidth = 100.
        overlap = 50.
        self.param.single_earth_station.frequency = 800 + 75. / 2
        self.param.single_earth_station.bandwidth = 75.

        self.param.imt.ue.k = 1
        simulation_1k = SimulationUplink(self.param, "")
        simulation_1k.initialize()

        self.assertFalse(simulation_1k.co_channel)
        self.assertEqual(simulation_1k.overlapping_bandwidth, overlap)

        simulation_1k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=14,
        )

        """
        We also check that system rx interference does depend on ue.k
        """
        self.param.imt.ue.k = 3
        simulation_3k = SimulationUplink(self.param, "")
        simulation_3k.initialize()

        simulation_3k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=13,
        )

        self.assertEqual(
            simulation_1k.coupling_loss_imt_system_adjacent.shape,
            (2, 1)
        )
        self.assertEqual(
            simulation_3k.coupling_loss_imt_system_adjacent.shape,
            (6, 1)
        )

        p_loss_1k = self.fspl.get_loss(
            simulation_1k.ue.get_3d_distance_to(simulation_1k.system),
            # TODO: maybe should change this?
            np.array([self.param.imt.frequency])
        )
        npt.assert_array_equal(
            p_loss_1k.flatten(),
            simulation_1k.results.imt_system_path_loss
        )
        p_loss_3k = self.fspl.get_loss(
            simulation_3k.ue.get_3d_distance_to(simulation_3k.system),
            # TODO: maybe should change this?
            np.array([self.param.imt.frequency])
        )
        npt.assert_array_equal(
            sorted(p_loss_3k.flatten()),
            sorted(simulation_3k.results.imt_system_path_loss)
        )

        g1_co_1k = np.zeros((1, 2))
        g1_adj_1k = np.zeros((1, 2))
        phis, thetas = simulation_1k.ue.get_pointing_vector_to(simulation_1k.system)

        for i, phi, theta in zip(range(2), phis, thetas):
            g1_co_1k[0][i] = simulation_1k.ue.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([theta]),
                beams_l=np.array([0]),
                co_channel=True,
            )
            g1_adj_1k[0][i] = simulation_1k.ue.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([theta]),
                beams_l=np.array([0]),
                co_channel=False,
            )

        npt.assert_allclose(
            simulation_1k.results.imt_system_antenna_gain,
            g1_co_1k.flatten()
        )

        g1_co_3k = np.zeros((1, 6))
        g1_adj_3k = np.zeros((1, 6))
        phis, thetas = simulation_3k.ue.get_pointing_vector_to(simulation_1k.system)

        for i, phi, theta in zip(range(6), phis, thetas):
            g1_co_3k[0][i] = simulation_3k.ue.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([theta]),
                beams_l=np.array([0]),
                co_channel=True,
            )
            g1_adj_3k[0][i] = simulation_3k.ue.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([theta]),
                beams_l=np.array([0]),
                co_channel=False,
            )

        g1_co_3k = np.reshape(np.transpose(g1_co_3k), (1, 6))
        npt.assert_allclose(
            # the order may not be the same, so we sort
            sorted(simulation_3k.results.imt_system_antenna_gain),
            sorted(g1_co_3k.flatten())
        )

        g2 = self.param.single_earth_station.antenna.gain

        adj_coupling_1k = p_loss_1k - np.transpose(g1_adj_1k) - g2

        adj_coupling_3k = p_loss_3k - np.transpose(g1_adj_3k) - g2
        coc_coupling_1k = p_loss_1k - np.transpose(g1_co_1k) - g2
        coc_coupling_3k = p_loss_3k - np.transpose(g1_co_3k) - g2

        npt.assert_allclose(
            simulation_1k.coupling_loss_imt_system_adjacent,
            adj_coupling_1k,
        )
        npt.assert_allclose(
            simulation_3k.coupling_loss_imt_system_adjacent,
            adj_coupling_3k,
        )

        npt.assert_allclose(
            coc_coupling_1k,
            simulation_1k.coupling_loss_imt_system
        )
        npt.assert_allclose(
            coc_coupling_3k,
            simulation_3k.coupling_loss_imt_system
        )
        imt_non_overlap = self.param.imt.bandwidth - overlap
        sys_non_overlap = self.param.single_earth_station.bandwidth - overlap

        imt_measurement_bw = self.param.imt.bandwidth

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            PSD = tx_pow_lin / tx_bw
            tx_pow_adj_lin = PSD * non_overlap_imt_bw
            rx_oob = tx_pow_adj_lin / acs
        """
        tx_lin_1k = self.lin(simulation_1k.ue.tx_power)
        tx_lin_3k = self.lin(simulation_3k.ue.tx_power)

        tx_bw = self.param.imt.bandwidth

        rx_oob_lin_1k = (tx_lin_1k / tx_bw) * imt_non_overlap / self.lin(
            self.param.single_earth_station.adjacent_ch_selectivity
        )
        rx_oob_lin_3k = (tx_lin_3k / tx_bw) * imt_non_overlap / self.lin(
            self.param.single_earth_station.adjacent_ch_selectivity
        )

        rx_oob_1k = self.dB(rx_oob_lin_1k)
        rx_oob_3k = self.dB(rx_oob_lin_3k)

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            tx_oob_in_measurement = (tx_pow_lin / aclr)
            => PSD = (tx_pow_lin / aclr) / measurement_bw
            => received tx_oob = PSD * non_overlap_sys_bw
        """
        psd_1k = (tx_lin_1k / self.lin(
            self.param.imt.ue.adjacent_ch_leak_ratio
        )) / imt_measurement_bw
        psd_3k = (tx_lin_3k / self.lin(
            self.param.imt.ue.adjacent_ch_leak_ratio
        )) / imt_measurement_bw

        tx_oob_1k = self.dB(psd_1k * sys_non_overlap)
        tx_oob_3k = self.dB(psd_3k * sys_non_overlap)

        rx_power_1k = self.dB(
            self.lin(rx_oob_1k.flatten() - coc_coupling_1k.flatten()).sum() + \
            self.lin(tx_oob_1k.flatten() - adj_coupling_1k.flatten()).sum()
        )

        rx_power_3k = self.dB(
            self.lin(rx_oob_3k.flatten() - coc_coupling_3k.flatten()).sum() + \
            self.lin(tx_oob_3k.flatten() - adj_coupling_3k.flatten()).sum()
        )

        self.assertEqual(
            len(simulation_1k.results.system_ul_interf_power),
            1
        )
        self.assertEqual(
            len(simulation_3k.results.system_ul_interf_power),
            1
        )

        npt.assert_almost_equal(
            simulation_1k.results.system_ul_interf_power,
            rx_power_1k
        )
        npt.assert_almost_equal(
            simulation_3k.results.system_ul_interf_power,
            rx_power_3k,
        )

        self.assert_imt_ul_to_sys_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_imt_ul_to_sys_results_attr(
            simulation_3k.results,
            3, 2
        )


if __name__ == "__main__":
    unittest.main()
