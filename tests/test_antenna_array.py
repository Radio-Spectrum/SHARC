# -*- coding: utf-8 -*-
"""
Created on Sat Apr 15 15:36:22 2017

@author: Calil
"""

import unittest
import numpy as np
import numpy.testing as npt

from sharc.antenna.antenna_array import AntennaArray
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt


class AntennaArrayTest(unittest.TestCase):
    """Unit tests for the AntennaArray class."""

    def setUp(self):
        """Set up test fixtures for AntennaArray tests."""
        # Array parameters
        self.bs_param = ParametersAntennaImt()
        self.ue_param = ParametersAntennaImt()

        # NOTE: not implemented:
        self.bs_param.adjacent_antenna_model = "SINGLE_ELEMENT"
        self.bs_param.normalization = False
        self.bs_param.normalization_file = None
        self.ue_param.adjacent_antenna_model = "SINGLE_ELEMENT"
        self.ue_param.normalization = False
        self.ue_param.normalization_file = None

        self.bs_param.element_pattern = "M2101"
        self.bs_param.minimum_array_gain = -200
        self.bs_param.downtilt = 0
        self.bs_param.element_max_g = 5
        self.bs_param.element_phi_3db = 80
        self.bs_param.element_theta_3db = 60
        self.bs_param.element_am = 30
        self.bs_param.element_sla_v = 30
        self.bs_param.n_rows = 16
        self.bs_param.n_columns = 16
        self.bs_param.element_horiz_spacing = 1
        self.bs_param.element_vert_spacing = 1
        self.bs_param.multiplication_factor = 12

        self.ue_param.element_pattern = "M2101"
        self.ue_param.minimum_array_gain = -200
        self.ue_param.element_max_g = 10
        self.ue_param.element_phi_3db = 75
        self.ue_param.element_theta_3db = 65
        self.ue_param.element_am = 25
        self.ue_param.element_sla_v = 35
        self.ue_param.n_rows = 2
        self.ue_param.n_columns = 2
        self.ue_param.element_horiz_spacing = 0.5
        self.ue_param.element_vert_spacing = 0.5
        self.ue_param.multiplication_factor = 12
        # Create antenna objects
        par = self.bs_param.get_antenna_parameters()
        self.antenna1 = AntennaArray(par)
        par = self.ue_param.get_antenna_parameters()
        self.antenna2 = AntennaArray(par)

    def test_element_gain(self):
        """Testing element gain calculations"""

        """Test M.2101 horizontal pattern calculation for various phi values."""
        # phi = 0 results in zero gain
        phi = np.array([0., 120., 150.])
        theta = np.zeros_like(phi) + 90.
        h_att = self.antenna1._element_gain(phi, theta)
        npt.assert_equal(
            h_att,
            self.antenna1.par.element_max_g - np.array([0.0, 27.0, 30.0])
        )

        """Test M.2101 vertical pattern calculation for various theta values."""
        theta = np.array([90, 180, 210])
        phi = np.zeros_like(theta)
        v_att = self.antenna1._element_gain(phi, theta)
        npt.assert_equal(
            v_att,
            self.antenna1.par.element_max_g - np.array([0.0, 27.0, 30.0])
        )

        """Test element pattern calculation for various phi/theta values."""
        phi = np.array([0, 80, 150])
        theta = np.array([90, 150, 210])
        e_gain = self.antenna1._element_gain(phi, theta)
        npt.assert_equal(
            e_gain,
            np.array([5.0, -19.0, -25.0])
        )

    def test_weight_vector(self):
        """Test calculation of the weight vector for beamforming."""
        # Error margin
        eps = 1e-5

        acc_phi_scan = []
        acc_theta_tilt = []
        acc_w_vec = []
        # Test 1
        phi_scan = 0
        theta_tilt = 0
        w_vec = self.antenna2._weight_vector(
            phi_scan, theta_tilt,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi_scan.append(phi_scan)
        acc_theta_tilt.append(theta_tilt)
        acc_w_vec.append(w_vec)
        expected_w_vec = np.array([[[0.5, 0.5], [0.5, 0.5]]])
        npt.assert_allclose(
            w_vec,
            expected_w_vec, rtol=eps,
        )

        # Test 2
        phi_scan = 90
        theta_tilt = 90
        w_vec = self.antenna2._weight_vector(
            phi_scan, theta_tilt,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi_scan.append(phi_scan)
        acc_theta_tilt.append(theta_tilt)
        acc_w_vec.append(w_vec)
        expected_w_vec = np.array([[[0.5, 0.5], [-0.5, -0.5]]])
        npt.assert_allclose(
            w_vec,
            expected_w_vec, rtol=eps,
        )

        # Test 3
        phi_scan = 45
        theta_tilt = 45
        w_vec = self.antenna2._weight_vector(
            phi_scan, theta_tilt,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi_scan.append(phi_scan)
        acc_theta_tilt.append(theta_tilt)
        acc_w_vec.append(w_vec)
        expected_w_vec = np.array([[
            [0.5 + 0.0j, 0.0 - 0.5j],
            [-0.3028499 + 0.3978466j, 0.3978466 + 0.3028499j],
        ]])
        npt.assert_allclose(
            w_vec,
            expected_w_vec, rtol=eps,
        )

        # Test 4
        phi_scan = 0
        theta_tilt = 90
        w_vec = self.antenna2._weight_vector(
            phi_scan, theta_tilt,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi_scan.append(phi_scan)
        acc_theta_tilt.append(theta_tilt)
        acc_w_vec.append(w_vec)
        expected_w_vec = np.array([[[0.5, 0.5], [-0.5, -0.5]]])
        npt.assert_allclose(
            w_vec,
            expected_w_vec, rtol=eps,
        )

        # Test 5
        phi_scan = 45
        theta_tilt = 30
        w_vec = self.antenna2._weight_vector(
            phi_scan, theta_tilt,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi_scan.append(phi_scan)
        acc_theta_tilt.append(theta_tilt)
        acc_w_vec.append(w_vec)
        expected_w_vec = np.array([[
            [0.5 + 0.0j, -0.172870 - 0.469169j],
            [0.0 + 0.5j, 0.469165 - 0.172870j],
        ]])
        npt.assert_allclose(
            w_vec,
            expected_w_vec, rtol=eps,
        )

        acc_phi_scan = np.array(acc_phi_scan)
        acc_theta_tilt = np.array(acc_theta_tilt)
        acc_w_vec = np.array(acc_w_vec)
        w_vec = self.antenna2._weight_vector(
            acc_phi_scan, acc_theta_tilt,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        expected_w_vec = np.squeeze(acc_w_vec, axis=1)
        npt.assert_allclose(
            w_vec,
            expected_w_vec, rtol=eps,
        )

    def test_super_position_vector(self):
        """Test calculation of the superposition vector."""
        # Error margin
        eps = 1e-5

        acc_phi = []
        acc_theta = []
        acc_v_vec = []

        # Test 1
        phi = 0
        theta = 0
        v_vec = self.antenna2._super_position_vector(
            phi, theta,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi.append(phi)
        acc_theta.append(theta)
        acc_v_vec.append(v_vec)
        expected_v_vec = np.array([[[1.0, 1.0], [-1.0, -1.0]]])
        npt.assert_allclose(
            v_vec,
            expected_v_vec, rtol=eps,
        )

        # Test 2
        phi = 90
        theta = 90
        v_vec = self.antenna2._super_position_vector(
            phi, theta,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi.append(phi)
        acc_theta.append(theta)
        acc_v_vec.append(v_vec)
        expected_v_vec = np.array([[[1.0, -1.0], [1.0, -1.0]]])
        npt.assert_allclose(
            v_vec,
            expected_v_vec, rtol=eps,
        )

        # Test 3
        phi = 45
        theta = 45
        v_vec = self.antenna2._super_position_vector(
            phi, theta,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi.append(phi)
        acc_theta.append(theta)
        acc_v_vec.append(v_vec)
        expected_v_vec = np.array([[
            [1.0 + 0.0j, 0.0 + 1.0j],
            [-0.6056998 + 0.7956932j, -0.7956932 - 0.6056998j],
        ]])
        npt.assert_allclose(
            v_vec,
            expected_v_vec, rtol=eps,
        )

        # Test 4
        phi = 60
        theta = 90
        v_vec = self.antenna2._super_position_vector(
            phi, theta,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        acc_phi.append(phi)
        acc_theta.append(theta)
        acc_v_vec.append(v_vec)
        expected_v_vec = np.array([[
            [1.0 + 0.0j, -0.912724 + 0.408576j],
            [1.0 + 0.0j, -0.912724 + 0.408576j],
        ]])
        npt.assert_allclose(
            v_vec,
            expected_v_vec, rtol=eps,
        )

        acc_phi = np.array(acc_phi)
        acc_theta = np.array(acc_theta)
        expected_v_vec = np.squeeze(acc_v_vec, axis=1)
        v_vec = self.antenna2._super_position_vector(
            acc_phi, acc_theta,
            self.antenna2.par.n_rows, self.antenna2.par.n_columns,
            self.antenna2.par.element_vert_spacing,
            self.antenna2.par.element_horiz_spacing,
        )
        npt.assert_allclose(
            v_vec,
            expected_v_vec, rtol=eps,
        )

    def test_calculate_gain(self):
        """Test calculation of antenna gain for given phi/theta vectors."""
        # Error margin and antenna
        eps = 1e-4
        par = self.bs_param.get_antenna_parameters()
        self.antenna1 = AntennaArray(par)
        par = self.ue_param.get_antenna_parameters()
        self.antenna2 = AntennaArray(par)

        # Test 1
        phi_vec = np.array([45.0, 32.5])
        theta_vec = np.array([45.0, 115.2])
        gains = self.antenna2.calculate_gain(
            phi_vec=phi_vec, theta_vec=theta_vec,
        )
        npt.assert_allclose(gains, np.array([5.9491, 11.9636]), atol=eps)

        # Test 2
        phi = 0.0
        theta = 60.0
        phi_scan = 45
        theta_tilt = 180
        self.antenna2.add_beam(phi_scan, theta_tilt)
        beams_l = np.zeros_like(phi, dtype=int)
        gains = self.antenna2.calculate_gain(
            phi_vec=phi, theta_vec=theta,
            beams_l=beams_l,
        )
        npt.assert_allclose(gains, np.array([10.454087]), atol=eps)

        # Test 3
        phi = 40
        theta = 100
        gains = self.antenna1.calculate_gain(
            phi_vec=phi, theta_vec=theta,
            co_channel=False,
        )
        npt.assert_allclose(gains, np.array([1.6667]), atol=eps)


if __name__ == '__main__':
    unittest.main()
