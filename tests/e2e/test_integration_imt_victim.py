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


class SimulationE2EIMTVictim(unittest.TestCase):
    """
    This is not an unit test, but also isn't that E2E.
    It doesn't test modules, but that the input and output of
    simulator is unchanged considering adjacent channel coupling loss and interference.
    """
    def setUp(self):
        """Set up test parameters and simulation objects for each test."""
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
        """Convert dB value to linear scale."""
        return 10 ** (0.1 * dB)

    def dB(self, lin):
        """
        Convert linear scale value to dB.
        """
        return 10 * np.log10(lin)

    def assert_sys_to_imt_dl_results_attr(
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
        # NOTE: as seen, only linked ue to linked bs are kept
        # otherwise there would be n_bs * n_ue as results
        self.assertEqual(len(res.imt_path_loss), n_ue)
        self.assertEqual(len(res.imt_coupling_loss), n_ue)
        self.assertEqual(len(res.imt_bs_antenna_gain), n_ue)
        self.assertEqual(len(res.imt_ue_antenna_gain), n_ue)

        self.assertEqual(len(res.imt_dl_pfd_external), n_ue)
        self.assertEqual(len(res.imt_dl_pfd_external_aggregated), n_ue)
        self.assertEqual(len(res.imt_dl_sinr_ext), n_ue)
        self.assertEqual(len(res.imt_dl_sinr), n_ue)
        self.assertEqual(len(res.imt_dl_snr), n_ue)
        self.assertEqual(len(res.imt_dl_inr), n_ue)
        self.assertEqual(len(res.imt_dl_tput_ext), n_ue)
        self.assertEqual(len(res.imt_dl_tput), n_ue)

        # testing attributes that should be per ue towards system
        self.assertEqual(len(res.imt_system_antenna_gain_adjacent), n_ue * n_sys)
        self.assertEqual(len(res.imt_system_path_loss), n_ue * n_sys)
        # NOTE: it may not have co-channel since this test is for adjacent
        # self.assertEqual(len(res.imt_system_antenna_gain), n_ue * n_sys)

        # testing attributes that should be per system towards imt
        self.assertEqual(len(res.system_imt_antenna_gain), n_sys * n_ue)
        # FIXME: why is this attr only on system -> IMT DL??
        self.assertEqual(len(res.sys_to_imt_coupling_loss), n_sys * n_ue)

    def assert_sys_to_imt_ul_results_attr(
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
        # n_ue == n_links
        n_ue = k * n_bs

        # testing attributes that should be per ue
        # NOTE: as seen, only linked ue to linked bs are kept
        # otherwise there would be n_bs * n_ue as results
        self.assertEqual(len(res.imt_path_loss), n_ue)
        self.assertEqual(len(res.imt_coupling_loss), n_ue)
        self.assertEqual(len(res.imt_bs_antenna_gain), n_ue)
        self.assertEqual(len(res.imt_ue_antenna_gain), n_ue)

        # self.assertEqual(len(res.imt_ul_pfd_external), n_ue)
        # self.assertEqual(len(res.imt_ul_pfd_external_aggregated), n_ue)
        self.assertEqual(len(res.imt_ul_sinr_ext), n_ue)
        self.assertEqual(len(res.imt_ul_sinr), n_ue)
        self.assertEqual(len(res.imt_ul_snr), n_ue)
        self.assertEqual(len(res.imt_ul_inr), n_ue)
        self.assertEqual(len(res.imt_ul_tput_ext), n_ue)
        self.assertEqual(len(res.imt_ul_tput), n_ue)

        # testing attributes that should be per ue towards system
        self.assertEqual(len(res.imt_system_antenna_gain_adjacent), n_ue * n_sys)
        self.assertEqual(len(res.imt_system_path_loss), n_ue * n_sys)
        # NOTE: it may not have co-channel since this test is for adjacent,
        # so if need be, remove this from here and put it elsewhere
        self.assertEqual(len(res.imt_system_antenna_gain), n_ue * n_sys)

        # testing attributes that should be per system towards imt
        self.assertEqual(len(res.system_imt_antenna_gain), n_sys * n_ue)

    def test_es_to_ue_aclr_and_acs_partial_overlap(self):
        """
        Testing Earth Station to UE acs and aclr with partial overlap
        """
        self.param.imt.ue.antenna.array.element_max_g = -2
        self.param.imt.ue.antenna.array.n_columns = 2
        self.param.imt.ue.antenna.array.n_rows = 2

        self.param.general.imt_link = "DOWNLINK"
        self.param.general.enable_cochannel = True
        self.param.imt.interfered_with = True

        self.param.imt.adjacent_ch_reception = "ACS"
        self.param.single_earth_station.adjacent_ch_emissions = "ACLR"
        self.param.single_earth_station.adjacent_ch_leak_ratio = 10.

        self.param.imt.ue.adjacent_ch_selectivity = 9.

        self.param.imt.frequency = 800.
        self.param.imt.bandwidth = 100.
        self.param.single_earth_station.bandwidth = 75.
        self.param.single_earth_station.frequency = 800. + 75 / 2
        overlap = 50.0

        self.param.imt.ue.k = 1
        simulation_1k = SimulationDownlink(self.param, "")
        simulation_1k.initialize()

        self.assertTrue(simulation_1k.co_channel)
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
        simulation_3k = SimulationDownlink(self.param, "")
        simulation_3k.initialize()

        simulation_3k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=13,
        )

        self.assertEqual(
            np.sum(simulation_3k.ue.center_freq == self.param.imt.frequency),
            2
        )
        self.assertEqual(
            np.sum(simulation_3k.ue.center_freq > self.param.imt.frequency),
            2
        )
        self.assertEqual(
            np.sum(simulation_3k.ue.center_freq < self.param.imt.frequency),
            2
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
            simulation_1k.system.get_3d_distance_to(simulation_1k.ue),
            # TODO: maybe should change this?
            np.array([self.param.single_earth_station.frequency])
        )
        npt.assert_array_equal(
            p_loss_1k.flatten(),
            simulation_1k.results.imt_system_path_loss
        )
        p_loss_3k = self.fspl.get_loss(
            simulation_3k.system.get_3d_distance_to(simulation_3k.ue),
            # TODO: maybe should change this?
            np.array([self.param.single_earth_station.frequency])
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

        adj_coupling_1k = np.transpose(p_loss_1k - g1_adj_1k - g2)
        adj_coupling_3k = np.transpose(p_loss_3k - g1_adj_3k - g2)
        coc_coupling_1k = np.transpose(p_loss_1k - g1_co_1k - g2)
        coc_coupling_3k = np.transpose(p_loss_3k - g1_co_3k - g2)

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
        imt_overlap_1k = simulation_1k.calculate_bw_weights(
            simulation_1k.ue.bandwidth,
            simulation_1k.ue.center_freq,
            self.param.single_earth_station.bandwidth,
            self.param.single_earth_station.frequency,
        ) * simulation_1k.ue.bandwidth
        imt_non_overlap_1k = simulation_1k.ue.bandwidth - imt_overlap_1k

        imt_overlap_3k = simulation_3k.calculate_bw_weights(
            simulation_3k.ue.bandwidth,
            simulation_3k.ue.center_freq,
            self.param.single_earth_station.bandwidth,
            self.param.single_earth_station.frequency,
        ) * simulation_3k.ue.bandwidth
        imt_non_overlap_3k = simulation_3k.ue.bandwidth - imt_overlap_3k

        sys_non_overlap = self.param.single_earth_station.bandwidth - overlap

        """
        Calculating received power from filter imperfections,
        the oob for IMT and co-channel for System
        ==============================================
            tx_pow_adj_lin = PSD * non_overlap_imt_bw
            rx_oob = tx_pow_adj_lin / acs
        """
        psd = self.lin(self.param.single_earth_station.tx_power_density)
        rx_oob_lin = psd * sys_non_overlap * 1e6 / self.lin(
            self.param.imt.ue.adjacent_ch_selectivity
        )

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            tx_oob_in_measurement = (tx_pow_lin / aclr)
            => PSD = (tx_pow_lin / aclr) / measurement_bw
            if measurement_bw == tx_bw, PSD_oob = PSD_coc / aclr
            => received tx_oob = PSD * non_overlap_sys_bw
        """
        psd_adj = psd / self.lin(
            self.param.single_earth_station.adjacent_ch_leak_ratio
        )

        tx_oob_lin_1k = psd_adj * imt_non_overlap_1k * 1e6
        tx_oob_lin_3k = psd_adj * imt_non_overlap_3k * 1e6

        """
        Calculating per RB co-channel interference
        """
        cochn_lin_1k = self.lin(
            self.param.single_earth_station.tx_power_density
        ) * imt_overlap_1k * 1e6
        cochn_1k = self.dB(cochn_lin_1k).reshape(coc_coupling_1k.shape) - coc_coupling_1k

        cochn_lin_3k = self.lin(
            self.param.single_earth_station.tx_power_density
        ) * imt_overlap_3k * 1e6
        cochn_3k = self.dB(cochn_lin_3k).reshape(coc_coupling_3k.shape) - coc_coupling_3k

        rx_oob_1k = self.dB(rx_oob_lin) - adj_coupling_1k
        tx_oob_1k = self.dB(tx_oob_lin_1k).reshape(coc_coupling_1k.shape) - coc_coupling_1k

        rx_oob_3k = self.dB(rx_oob_lin) - adj_coupling_3k
        tx_oob_3k = self.dB(tx_oob_lin_3k).reshape(coc_coupling_3k.shape) - coc_coupling_3k

        rx_power_1k = self.dB(
            self.lin(rx_oob_1k).sum(axis=1) + \
            self.lin(tx_oob_1k).sum(axis=1) + \
            self.lin(cochn_1k).sum(axis=1)
        )
        rx_power_3k = self.dB(
            self.lin(rx_oob_3k).sum(axis=1) + \
            self.lin(tx_oob_3k).sum(axis=1) + \
            self.lin(cochn_3k).sum(axis=1)
        )

        npt.assert_allclose(
            simulation_1k.ue.ext_interference.flatten(),
            rx_power_1k + 30,
        )
        npt.assert_allclose(
            simulation_3k.ue.ext_interference.flatten(),
            rx_power_3k + 30,
            atol=0.007
        )

        # TODO: test IMT KPIs (sinr, etc)

        self.assert_sys_to_imt_dl_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_sys_to_imt_dl_results_attr(
            simulation_3k.results,
            3, 2
        )

    def test_es_to_bs_aclr_and_acs_partial_overlap(self):
        """
        Testing system to BS acs and aclr with partial co-channel
        """
        self.param.general.imt_link = "UPLINK"
        self.param.general.enable_cochannel = True
        self.param.imt.interfered_with = True

        self.param.single_earth_station.adjacent_ch_emissions = "ACLR"
        self.param.imt.adjacent_ch_reception = "ACS"

        self.param.imt.bs.adjacent_ch_selectivity = 3.3
        self.param.single_earth_station.adjacent_ch_leak_ratio = 2.9

        self.param.imt.frequency = 800.
        self.param.imt.bandwidth = 100.
        overlap = 50.
        self.param.single_earth_station.frequency = 800 + 75. / 2
        self.param.single_earth_station.bandwidth = 75.

        self.param.imt.ue.k = 1
        simulation_1k = SimulationUplink(self.param, "")
        simulation_1k.initialize()

        self.assertTrue(simulation_1k.co_channel)
        self.assertTrue(simulation_1k.adjacent_channel)

        simulation_1k.snapshot(
            write_to_file=False,
            snapshot_number=0,
            seed=14,
        )

        """
        We also check that system rx interference doesn't depend on ue.k
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

        p_loss = self.fspl.get_loss(
            simulation_1k.bs.get_3d_distance_to(simulation_1k.system),
            # TODO: maybe should change this?
            np.array([self.param.single_earth_station.frequency])
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
        imt_overlap_1k = simulation_1k.calculate_bw_weights(
            simulation_1k.bs.bandwidth[:, np.newaxis],
            simulation_1k.bs.center_freq,
            self.param.single_earth_station.bandwidth,
            self.param.single_earth_station.frequency,
        ) * simulation_1k.bs.bandwidth[:, np.newaxis]

        imt_non_overlap_1k = simulation_1k.bs.bandwidth[:, np.newaxis] - imt_overlap_1k

        npt.assert_allclose(
            imt_non_overlap_1k,
            overlap - (self.param.imt.guard_band_ratio) * self.param.imt.bandwidth / 2
        )

        imt_overlap_3k = simulation_3k.calculate_bw_weights(
            simulation_3k.bs.bandwidth[:, np.newaxis],
            simulation_3k.bs.center_freq,
            self.param.single_earth_station.bandwidth,
            self.param.single_earth_station.frequency,
        ) * simulation_3k.bs.bandwidth[:, np.newaxis]

        imt_non_overlap_3k = simulation_3k.bs.bandwidth[:, np.newaxis] - imt_overlap_3k

        # fully co-channel
        npt.assert_allclose(
            imt_non_overlap_3k[simulation_3k.bs.center_freq > self.param.imt.frequency],
            0,
            atol=1e-12
        )

        # half bw is adjacent
        npt.assert_allclose(
            imt_non_overlap_3k[simulation_3k.bs.center_freq == self.param.imt.frequency],
            # N RBs * RB_bw / 2
            np.floor(90 / 3 / self.param.imt.rb_bandwidth) * self.param.imt.rb_bandwidth / 2,
            atol=1e-12
        )
        # fully adjacent
        npt.assert_allclose(
            imt_non_overlap_3k[simulation_3k.bs.center_freq < self.param.imt.frequency],
            # N RBs * RB_bw
            np.floor(90 / 3 / self.param.imt.rb_bandwidth) * self.param.imt.rb_bandwidth,
            atol=1e-12
        )

        sys_non_overlap = self.param.single_earth_station.bandwidth - overlap

        sys_measurement_bw = self.param.single_earth_station.bandwidth

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            PSD = tx_pow_lin / tx_bw
            tx_pow_adj_lin = PSD * non_overlap_imt_bw
            rx_oob = tx_pow_adj_lin / acs
        """
        tx_lin = self.lin(
            self.param.single_earth_station.tx_power_density
        ) * self.param.single_earth_station.bandwidth * 1e6

        tx_bw = self.param.single_earth_station.bandwidth

        rx_oob_lin = (tx_lin / tx_bw) * sys_non_overlap / self.lin(
            self.param.imt.bs.adjacent_ch_selectivity
        )

        rx_oob = self.dB(rx_oob_lin)

        """
        Calculating received power from filter imperfections,
        the oob for system and co-channel for IMT
        ==============================================
            tx_oob_in_measurement = (tx_pow_lin / aclr)
            => PSD = (tx_pow_lin / aclr) / measurement_bw
            => received tx_oob = PSD * non_overlap_sys_bw
        """
        psd = (tx_lin / self.lin(
            self.param.single_earth_station.adjacent_ch_leak_ratio
        )) / sys_measurement_bw

        tx_oob_1k = self.dB(psd * imt_non_overlap_1k)
        tx_oob_3k = self.dB(psd * imt_non_overlap_3k)

        rx_oob -= adj_coupling
        tx_oob_1k -= coc_coupling_1k

        tx_oob_3k = tx_oob_3k.reshape(coc_coupling_3k.shape) - coc_coupling_3k

        """
        Calculating per RB co-channel interference
        """
        cochn_lin_1k = self.lin(
            self.param.single_earth_station.tx_power_density
        ) * imt_overlap_1k * 1e6
        cochn_1k = self.dB(cochn_lin_1k) - coc_coupling_1k

        cochn_lin_3k = self.lin(
            self.param.single_earth_station.tx_power_density
        ) * imt_overlap_3k * 1e6
        cochn_3k = self.dB(cochn_lin_3k).reshape(coc_coupling_3k.shape) - coc_coupling_3k

        rx_power_1k = self.dB(
            self.lin(rx_oob).sum(axis=1) + \
            self.lin(tx_oob_1k).sum(axis=1) + \
            self.lin(cochn_1k).sum(axis=1)
        )
        rx_power_3k = self.dB(
            self.lin(np.tile(rx_oob, (3, 1))).sum(axis=1) + \
            self.lin(tx_oob_3k).sum(axis=1) + \
            self.lin(cochn_3k).sum(axis=1)
        )

        npt.assert_almost_equal(
            np.ravel(list(simulation_1k.bs.ext_interference.values())),
            rx_power_1k + 30
        )
        npt.assert_almost_equal(
            np.ravel(list(simulation_3k.bs.ext_interference.values())),
            rx_power_3k + 30,
        )

        self.assert_sys_to_imt_ul_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_sys_to_imt_ul_results_attr(
            simulation_3k.results,
            3, 2
        )

    def test_es_to_ue_mask(self):
        """
        Testing ES spectral mask interference into UE
        This simplifies spectral mask calculation by only getting the spurious emissions
        """
        self.param.general.imt_link = "DOWNLINK"
        self.param.imt.interfered_with = True
        self.param.single_earth_station.adjacent_ch_emissions = "SPECTRAL_MASK"
        self.param.single_earth_station.spectral_mask = "MSS"
        self.param.single_earth_station.spurious_emissions = -13.

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
        We also check that received spectral mask power
        is per UE allocated RBs
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

        p_loss_1k = self.fspl.get_loss(
            simulation_1k.system.get_3d_distance_to(simulation_1k.ue),
            # TODO: maybe should change this?
            np.array([self.param.single_earth_station.frequency])
        )
        npt.assert_array_equal(
            p_loss_1k.flatten(),
            simulation_1k.results.imt_system_path_loss
        )

        p_loss_3k = self.fspl.get_loss(
            simulation_3k.system.get_3d_distance_to(simulation_3k.ue),
            # TODO: maybe should change this?
            np.array([self.param.single_earth_station.frequency])
        )
        npt.assert_array_equal(
            sorted(p_loss_3k.flatten()),
            sorted(simulation_3k.results.imt_system_path_loss)
        )

        g1_co_1k = np.zeros((1, 2))
        phis, thetas = simulation_1k.ue.get_pointing_vector_to(simulation_1k.system)

        for i, phi, theta in zip(range(2), phis, thetas):
            g1_co_1k[0][i] = simulation_1k.ue.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([theta]),
                beams_l=np.array([0]),
                co_channel=True,
            )

        npt.assert_allclose(
            simulation_1k.results.imt_system_antenna_gain,
            g1_co_1k.flatten()
        )

        g1_co_3k = np.zeros((1, 6))
        phis, thetas = simulation_3k.ue.get_pointing_vector_to(simulation_1k.system)

        for i, phi, theta in zip(range(6), phis, thetas):
            g1_co_3k[0][i] = simulation_3k.ue.antenna[i].calculate_gain(
                phi_vec=np.array([phi]),
                theta_vec=np.array([theta]),
                beams_l=np.array([0]),
                co_channel=True,
            )

        g1_co_3k = np.reshape(np.transpose(g1_co_3k), (1, 6))
        npt.assert_allclose(
            # the order may not be the same, so we sort
            sorted(simulation_3k.results.imt_system_antenna_gain),
            sorted(g1_co_3k.flatten())
        )

        g2 = self.param.single_earth_station.antenna.gain

        coc_coupling_1k = np.transpose(p_loss_1k - g1_co_1k - g2)
        coc_coupling_3k = np.transpose(p_loss_3k - g1_co_3k - g2)

        npt.assert_allclose(
            coc_coupling_1k,
            simulation_1k.coupling_loss_imt_system
        )
        npt.assert_allclose(
            coc_coupling_3k,
            simulation_3k.coupling_loss_imt_system
        )

        mask_power_1k = self.param.single_earth_station.spurious_emissions + \
            self.dB(simulation_1k.ue.bandwidth)
        mask_power_3k = self.param.single_earth_station.spurious_emissions + \
            self.dB(simulation_3k.ue.bandwidth)

        rx_power_1k = mask_power_1k - coc_coupling_1k.reshape(mask_power_1k.shape)
        rx_power_3k = mask_power_3k - coc_coupling_3k.reshape(mask_power_3k.shape)

        npt.assert_almost_equal(
            simulation_1k.ue.ext_interference,
            rx_power_1k
        )

        npt.assert_allclose(
            simulation_3k.ue.ext_interference,
            rx_power_3k,
        )
        npt.assert_almost_equal(
            simulation_3k.results.system_dl_interf_power,
            simulation_1k.results.system_dl_interf_power,
        )

        self.assert_sys_to_imt_dl_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_sys_to_imt_dl_results_attr(
            simulation_3k.results,
            3, 2
        )

    def test_es_to_bs_mask(self):
        """
        Testing ES spectral mask interference into BS
        This simplifies spectral mask calculation by only getting the spurious emissions
        """
        self.param.general.imt_link = "UPLINK"
        self.param.imt.interfered_with = True
        self.param.single_earth_station.adjacent_ch_emissions = "SPECTRAL_MASK"
        self.param.single_earth_station.spectral_mask = "MSS"
        self.param.single_earth_station.spurious_emissions = -13.

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
        We also check that received spectral mask power
        is per UE allocated RBs
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
            simulation_1k.system.get_3d_distance_to(simulation_1k.bs),
            # TODO: maybe should change this?
            np.array([self.param.single_earth_station.frequency])
        )
        npt.assert_array_equal(
            p_loss_1k.flatten(),
            simulation_1k.results.imt_system_path_loss
        )

        p_loss_3k = p_loss_1k.repeat(3)
        npt.assert_array_equal(
            p_loss_3k.flatten(),
            simulation_3k.results.imt_system_path_loss
        )

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

        coc_coupling_1k = np.transpose(p_loss_1k - g1_co_1k - g2)
        coc_coupling_3k = np.transpose(p_loss_3k - g1_co_3k - g2)

        npt.assert_allclose(
            coc_coupling_1k,
            simulation_1k.coupling_loss_imt_system
        )
        npt.assert_allclose(
            coc_coupling_3k,
            simulation_3k.coupling_loss_imt_system
        )

        mask_power_1k = self.param.single_earth_station.spurious_emissions + \
            self.dB(simulation_1k.bs.bandwidth)
        mask_power_3k = np.repeat(
            self.param.single_earth_station.spurious_emissions + \
            self.dB(simulation_3k.bs.bandwidth),
            3
        )

        # mask power for BS with 3 times more RB should be 3 times bigger
        self.assertAlmostEqual(
            mask_power_1k.flat[0],
            mask_power_3k.flat[0] + self.dB(3),
            1
        )

        rx_power_1k = mask_power_1k - coc_coupling_1k.reshape(mask_power_1k.shape)
        rx_power_3k = mask_power_3k - coc_coupling_3k.reshape(mask_power_3k.shape)

        npt.assert_almost_equal(
            np.ravel(list(simulation_1k.bs.ext_interference.values())),
            rx_power_1k
        )

        npt.assert_allclose(
            np.ravel(list(simulation_3k.bs.ext_interference.values())),
            rx_power_3k,
        )
        npt.assert_almost_equal(
            simulation_3k.results.system_dl_interf_power,
            simulation_1k.results.system_dl_interf_power,
        )

        self.assert_sys_to_imt_ul_results_attr(
            simulation_1k.results,
            1, 2
        )
        self.assert_sys_to_imt_ul_results_attr(
            simulation_3k.results,
            3, 2
        )


if __name__ == "__main__":
    unittest.main()
