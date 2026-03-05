import unittest

import numpy as np
import numpy.testing as npt
from scipy.spatial.transform import Rotation

from sharc.antenna.antenna_array_pool import AntennaArrayPool
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.support.geometry import RigidTransform


class TestAntennaArrayShared(unittest.TestCase):
    def _make_par(self):
        param = ParametersAntennaImt()
        param.adjacent_antenna_model = "SINGLE_ELEMENT"
        param.normalization = False
        param.minimum_array_gain = -200

        param.element_pattern = "M2101"
        param.element_max_g = 6.5
        param.element_phi_3db = 65
        param.element_theta_3db = 90
        param.element_am = 30
        param.element_sla_v = 30
        param.n_rows = 8
        param.n_columns = 8
        param.element_horiz_spacing = 0.5
        param.element_vert_spacing = 0.5
        param.multiplication_factor = 12

        return param.get_antenna_parameters()

    def _make_transform(self, idx: int):
        return RigidTransform(
            rot=Rotation.from_euler("z", [float(idx)], degrees=True),
            t=np.array([[float(idx), 0.0, 0.0]]),
        )

    def test_wrapper_matches_base_for_multiple_beam_counts(self):
        par = self._make_par()

        phi = np.linspace(-180.0, 180.0, 180)
        theta = np.linspace(0.0, 180.0, 180)

        for n_beams in [1, 2, 3, 7]:
            pool = AntennaArrayPool()
            pool.reset_pool(1)

            wrappers = []
            azimuths = np.linspace(-25.0, 25.0, n_beams)
            elevations = np.linspace(-5.0, 5.0, n_beams)

            for azim, elev in zip(azimuths, elevations):
                wrappers.append(
                    pool.append_antenna(
                        par,
                        azimuth=float(azim),
                        elevation=float(elev),
                        global2local_transform=self._make_transform(0),
                    )
                )

            base = wrappers[0].array

            for beam_idx, wrapper in enumerate(wrappers):
                gain_wrapper = wrapper.calculate_gain(phi_vec=phi, theta_vec=theta)
                expected = base.calculate_gain(
                    phi_vec=phi,
                    theta_vec=theta,
                    beams_l=np.full(len(phi), beam_idx, dtype=int),
                )
                npt.assert_allclose(gain_wrapper, expected)

    def test_results_are_memoized_for_shared_array(self):
        par = self._make_par()

        pool = AntennaArrayPool()
        pool.reset_pool(1)
        tf = self._make_transform(0)
        ant_0 = pool.append_antenna(
            par,
            azimuth=0.0,
            elevation=0.0,
            global2local_transform=tf,
        )
        ant_1 = pool.append_antenna(
            par,
            azimuth=10.0,
            elevation=0.0,
            global2local_transform=tf,
        )

        base = ant_0.array
        original_calculate_gain = base.calculate_gain
        n_calls = {"value": 0}

        def counted_calculate_gain(*args, **kwargs):
            n_calls["value"] += 1
            return original_calculate_gain(*args, **kwargs)

        base.calculate_gain = counted_calculate_gain

        phi = np.linspace(-20.0, 20.0, 8)
        theta = np.zeros_like(phi) + 90.0

        _ = ant_0.calculate_gain(phi_vec=phi, theta_vec=theta)
        calls_after_first_compute = n_calls["value"]
        _ = ant_1.calculate_gain(phi_vec=phi, theta_vec=theta)

        self.assertEqual(calls_after_first_compute, 1)
        self.assertEqual(n_calls["value"], calls_after_first_compute)

    def test_cache_is_split_by_co_channel(self):
        par = self._make_par()

        pool = AntennaArrayPool()
        pool.reset_pool(1)
        tf = self._make_transform(0)
        ant_0 = pool.append_antenna(
            par,
            azimuth=0.0,
            elevation=0.0,
            global2local_transform=tf,
        )
        ant_1 = pool.append_antenna(
            par,
            azimuth=10.0,
            elevation=0.0,
            global2local_transform=tf,
        )

        base = ant_0.array
        original_calculate_gain = base.calculate_gain
        n_calls = {"value": 0}

        def counted_calculate_gain(*args, **kwargs):
            n_calls["value"] += 1
            return original_calculate_gain(*args, **kwargs)

        base.calculate_gain = counted_calculate_gain

        phi = np.linspace(-20.0, 20.0, 8)
        theta = np.zeros_like(phi) + 90.0

        gain_true_0 = ant_0.calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            co_channel=True,
        )
        self.assertEqual(n_calls["value"], 1)

        gain_false_0 = ant_0.calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            co_channel=False,
        )
        self.assertEqual(n_calls["value"], 2)

        gain_true_1 = ant_1.calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            co_channel=True,
        )
        gain_false_1 = ant_1.calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            co_channel=False,
        )
        self.assertEqual(n_calls["value"], 2)

        expected_true_0 = original_calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.zeros(len(phi), dtype=int),
            co_channel=True,
        )
        expected_true_1 = original_calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.ones(len(phi), dtype=int),
            co_channel=True,
        )
        expected_false_0 = original_calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.zeros(len(phi), dtype=int),
            co_channel=False,
        )
        expected_false_1 = original_calculate_gain(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.ones(len(phi), dtype=int),
            co_channel=False,
        )

        npt.assert_allclose(gain_true_0, expected_true_0)
        npt.assert_allclose(gain_true_1, expected_true_1)
        npt.assert_allclose(gain_false_0, expected_false_0)
        npt.assert_allclose(gain_false_1, expected_false_1)

    def test_multiple_pools_are_independent_and_correct(self):
        par = self._make_par()

        pool = AntennaArrayPool()
        pool.reset_pool(2)

        tf_a = self._make_transform(0)
        tf_b = self._make_transform(1)

        ant_a0 = pool.append_antenna(
            par,
            azimuth=-10.0,
            elevation=-2.0,
            global2local_transform=tf_a,
        )
        ant_a1 = pool.append_antenna(
            par,
            azimuth=15.0,
            elevation=3.0,
            global2local_transform=tf_a,
        )

        ant_b0 = pool.append_antenna(
            par,
            azimuth=-30.0,
            elevation=1.0,
            global2local_transform=tf_b,
        )
        ant_b1 = pool.append_antenna(
            par,
            azimuth=0.0,
            elevation=5.0,
            global2local_transform=tf_b,
        )
        ant_b2 = pool.append_antenna(
            par,
            azimuth=35.0,
            elevation=-4.0,
            global2local_transform=tf_b,
        )

        base_a = ant_a0.array
        base_b = ant_b0.array

        count_a = {"value": 0}
        count_b = {"value": 0}

        original_a = base_a.calculate_gain
        original_b = base_b.calculate_gain

        def counted_a(*args, **kwargs):
            count_a["value"] += 1
            return original_a(*args, **kwargs)

        def counted_b(*args, **kwargs):
            count_b["value"] += 1
            return original_b(*args, **kwargs)

        base_a.calculate_gain = counted_a
        base_b.calculate_gain = counted_b

        phi = np.linspace(-60.0, 60.0, 31)
        theta = np.linspace(50.0, 130.0, 31)

        gain_a0 = ant_a0.calculate_gain(phi_vec=phi, theta_vec=theta)
        gain_a1 = ant_a1.calculate_gain(phi_vec=phi, theta_vec=theta)
        gain_b0 = ant_b0.calculate_gain(phi_vec=phi, theta_vec=theta)
        gain_b1 = ant_b1.calculate_gain(phi_vec=phi, theta_vec=theta)
        gain_b2 = ant_b2.calculate_gain(phi_vec=phi, theta_vec=theta)

        expected_a0 = original_a(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.zeros(len(phi), dtype=int),
        )
        expected_a1 = original_a(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.ones(len(phi), dtype=int),
        )

        expected_b0 = original_b(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.zeros(len(phi), dtype=int),
        )
        expected_b1 = original_b(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.ones(len(phi), dtype=int),
        )
        expected_b2 = original_b(
            phi_vec=phi,
            theta_vec=theta,
            beams_l=np.full(len(phi), 2, dtype=int),
        )

        npt.assert_allclose(gain_a0, expected_a0)
        npt.assert_allclose(gain_a1, expected_a1)
        npt.assert_allclose(gain_b0, expected_b0)
        npt.assert_allclose(gain_b1, expected_b1)
        npt.assert_allclose(gain_b2, expected_b2)
        npt.assert_allclose(gain_b2, expected_b2)

        self.assertEqual(count_a["value"], 1)
        self.assertEqual(count_b["value"], 1)


if __name__ == "__main__":
    unittest.main()
