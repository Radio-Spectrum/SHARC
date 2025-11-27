import unittest
import numpy as np
import numpy.testing as npt

from sharc.parameters.parameters import Parameters
from sharc.propagation.propagation_path import PropagationPath
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.propagation.propagation_factory import PropagationFactory
from sharc.station_manager import StationManager
from sharc.support.enumerations import StationType


def assert_array_not_equal(x, y):
    """Asserts that two arrays are not equal."""
    npt.assert_raises(AssertionError, npt.assert_array_equal, x, y)


def create_mock_function(ret):
    """Creates function that returns the argument
    """
    def mock_function(*args, **kwargs):
        return ret
    return mock_function


class PropagationPathTest(unittest.TestCase):
    """This is more of an integration test since it depends on the parts
    it joins.
    """
    def setUp(self):
        """setUp that runs before each test"""
        pass

    def test_undeduped_masking_operations(self):
        """Testing masking operations when not deduplicating
        """
        bs = StationManager(4)
        bs.geom.set_global_coords(
            np.array([5., 15., 25., 35.]),
            np.array([0., 0., 0., 0.]),
            np.repeat(10., 4),
        )
        ue = StationManager(3)
        ue.geom.set_global_coords(
            np.array([-5., -5., -25.]),
            np.array([0., 0., 0.]),
            np.repeat(10., 3),
        )

        path = PropagationPath.create_default(ue, bs)
        path.calc_mask(deduplicate=False)

        mtx = np.array([
            [1., 2., 3., 4.],
            [5., 6., 7., 8.],
            [9., 10., 11., 12.],
        ])
        mskd_mtx = path.mtx_to_masked(mtx)

        npt.assert_equal(np.ravel(mtx), mskd_mtx)

        unmskd_mtx = path.from_masked_mtx(mskd_mtx)
        npt.assert_equal(mtx, unmskd_mtx)

        vec = np.array([10., 20., 30.])
        vec_cast = path.sta_a_to_masked(vec)
        # since paths are ordered by sta_a,
        # they are iterated for (0, ...), (1, ...)
        # as such it repeats the i-th indice n sta_b times
        expected = np.array([
            10., 10., 10., 10.,
            20., 20., 20., 20.,
            30., 30., 30., 30.,
        ])
        npt.assert_array_equal(expected, vec_cast)

        # since paths are ordered by sta_a,
        # they are iterated for (0, ...j), (1, ...)
        # as such it goes through entire j sequence
        # sta_a times
        vec = np.array([10., 20., 30., 40.])
        vec_cast = path.sta_b_to_masked(vec)
        expected = np.array([
            10., 20., 30., 40.,
            10., 20., 30., 40.,
            10., 20., 30., 40.,
        ])
        npt.assert_array_equal(expected, vec_cast)

        ue.active[0] = False
        path.calc_mask(deduplicate=False)

        mskd_mtx = path.mtx_to_masked(mtx)

        npt.assert_equal(np.ravel(mtx[1:]), mskd_mtx)

        unmskd_mtx = path.from_masked_mtx(mskd_mtx)
        # first row of mtx should be np.nan
        expected = np.copy(mtx)
        expected[0, :] = np.nan

        npt.assert_equal(expected, unmskd_mtx)

        vec = np.array([10., 20., 30.])
        vec_cast = path.sta_a_to_masked(vec)
        expected = np.array([
            20., 20., 20., 20.,
            30., 30., 30., 30.,
        ])
        npt.assert_array_equal(expected, vec_cast)

        vec = np.array([10., 20., 30., 40.])
        vec_cast = path.sta_b_to_masked(vec)
        expected = np.array([
            10., 20., 30., 40.,
            10., 20., 30., 40.,
        ])
        npt.assert_array_equal(expected, vec_cast)

    def test_deduped_mask_operations(self):
        """Testing masking operations when deduplicating
        """
        bs = StationManager(4)
        bs.geom.set_global_coords(
            np.array([5., 15., 25., 35.]),
            np.array([0., 0., 0., 0.]),
            np.repeat(10., 4),
        )
        ue = StationManager(3)
        ue.geom.set_global_coords(
            np.array([-5., -5., -25.]),
            np.array([0., 0., 0.]),
            np.repeat(10., 3),
        )

        """Since zeroth row it represents 1, it should be used for both 0 and 1"""
        path = PropagationPath.create_default(ue, bs)
        path.calc_mask(deduplicate=True)

        mtx = np.array([
            [1., 2., 3., 4.],
            [5., 6., 7., 8.],
            [9., 10., 11., 12.],
        ])
        mskd_mtx = path.mtx_to_masked(mtx)
        expected = np.concatenate((mtx[0], mtx[2]))
        # expect reduction in values for path loss calc
        npt.assert_equal(expected, mskd_mtx)

        unmskd_mtx = path.from_masked_mtx(mskd_mtx)
        # and reverse mapping for deduped values (0) and the rows that need
        # those values (0 and 1)
        expected = np.concatenate(([mtx[0]], [mtx[0]], [mtx[2]]))
        npt.assert_equal(expected, unmskd_mtx)

        vec = np.array([10., 20., 30.])
        vec_cast = path.sta_a_to_masked(vec)
        # since paths are ordered by sta_a,
        # they are iterated for (0, ...), (1, ...)
        # as such it repeats the i-th indice n sta_b times
        expected = np.array([
            10., 10., 10., 10.,
            30., 30., 30., 30.,
        ])
        npt.assert_array_equal(expected, vec_cast)

        # since paths are ordered by sta_a,
        # they are iterated for (0, ...j), (1, ...)
        # as such it goes through entire j sequence
        # sta_a times
        vec = np.array([10., 20., 30., 40.])
        vec_cast = path.sta_b_to_masked(vec)
        expected = np.array([
            10., 20., 30., 40.,
            10., 20., 30., 40.,
        ])
        npt.assert_array_equal(expected, vec_cast)

        """Even if 0 is not active, since it represents 1, it should be calc'd"""
        ue.active[0] = False
        path.calc_mask(deduplicate=True)

        mskd_mtx = path.mtx_to_masked(mtx)
        # so its value should be masked
        expected = np.concatenate((mtx[0], mtx[2]))
        npt.assert_equal(expected, mskd_mtx)

        unmskd_mtx = path.from_masked_mtx(mskd_mtx)
        # zeroth row of mtx should be np.nan
        expected = np.copy(mtx)
        expected[0, :] = np.nan
        # and second should come from the masked zeroth
        expected[1, :] = mtx[0, :]

        npt.assert_equal(expected, unmskd_mtx)

    def test_get_path_loss_fspl(self):
        """Test get_path_loss with different shapes on fspl
        """
        bs = StationManager(3)
        bs.geom.set_global_coords(
            np.array([5., 15., 25.]),
            np.array([0., 0., 0.]),
            np.repeat(10., 3),
        )
        ue = StationManager(3)
        ue.geom.set_global_coords(
            np.array([-5., -15., -25.]),
            np.array([0., 0., 0.]),
            np.repeat(10., 3),
        )

        path = PropagationPath.create_default(ue, bs)

        fspl = path.get_path_loss(
            PropagationFreeSpace(None),
            None,
            1e3,  # [MHz]
        )

        expected_fspl = PropagationFreeSpace(None).get_free_space_loss(
            1e3,
            ue.geom.get_3d_distance_to(bs.geom),
        )

        self.assertEqual(fspl.shape, expected_fspl.shape)
        npt.assert_array_equal(fspl, expected_fspl)

    def test_get_path_loss_in_propagations(self):
        """Test get_path_loss method with all propagations
        """
        bs = StationManager(12)
        bs.geom.set_global_coords(
            np.arange(0., 12., 1.0) * 10,
            np.repeat(0., 12),
            np.repeat(10., 12),
        )
        ue = StationManager(36)
        bs.station_type = StationType.IMT_UE
        ue.geom.set_global_coords(
            np.repeat(np.arange(0., 18., 1.0) * 10, 2),
            np.repeat(5., 36),
            np.repeat(1.5, 36),
        )
        bs.is_space_station = False
        for i in range(5, 11):
            ue.active[i] = False

        for i in range(20, 23):
            ue.active[i] = False

        for i in range(0, 3):
            bs.active[i] = False

        path = PropagationPath.create_default(ue, bs)
        parameters = Parameters()
        parameters.imt.topology.type = "MSS_DC"
        parameters.imt.interfered_with = True
        gains0 = np.zeros(path._orig_shape)

        bs_w_beams_gains = np.zeros([*path._orig_shape, 3])
        ue.is_space_station = True
        for ch_model in [
            "FSPL",
            "ABG",
            "UMa",
            "UMi",
            # "SatelliteSimple",
            "TerrestrialSimple",
            "P619",
            "P452",
            "TVRO-URBAN",
            "TVRO-SUBURBAN",
            "HDFSS",
            "INDOOR",
        ]:
            rng = np.random.RandomState(1)
            propagation = PropagationFactory.create_propagation(
                ch_model, parameters,
                parameters.single_earth_station,
                rng,
            )
            if hasattr(propagation, "_get_atmospheric_gasses_loss"):
                # since P619 takes too long calculating this
                propagation._get_atmospheric_gasses_loss = create_mock_function(0.0)

            ploss = path.get_path_loss(
                propagation,
                parameters,
                1e3,  # [MHz]
                # sta_a_gains=gains0,
                sta_a_gains=bs_w_beams_gains,
                sta_b_gains=gains0.T,
            )

            if ch_model == "HDFSS":
                ploss = ploss[0]

            expected_shape = (ue.num_stations, bs.num_stations)
            expected_filled = np.stack(np.where(path._mask), axis=0)
            expected_nans = np.stack(np.where(~path._mask), axis=0)

            if ch_model == "INDOOR":
                # NOTE: current Indoor channel model implementaiton
                # depends on the matrix structure so it does not consider
                # the only active paths for path loss calculation
                # TODO: update indoor implementation to let that happen
                expected_filled = np.stack(np.where(np.ones(expected_shape)), axis=0)
                expected_nans = np.stack(np.where(np.zeros(expected_shape)), axis=0)
            else:
                # checking if the _paths_from_to is representative
                npt.assert_array_equal(expected_filled, path._paths_from_to.T)

            self.assertEqual(ploss.shape, expected_shape)
            npt.assert_array_equal(ploss[tuple(expected_nans)], np.nan)
            assert_array_not_equal(ploss[tuple(expected_filled)], np.nan)

    def test_get_path_loss_single_ss_vs_bs_in_propagations(self):
        """Test for the case when a single other station is vs base station
        important for code coverage in P.619 (single entry interference)
        """
        single_sta = StationManager(1)
        single_sta.geom.set_global_coords(
            np.array([0.]),
            np.array([5.]),
            np.array([30.]),
        )
        single_sta.is_space_station = True
        single_sta.active[0] = True

        bs = StationManager(12)
        bs.geom.set_global_coords(
            np.arange(0., 12., 1.0) * 10,
            np.repeat(0., 12),
            np.repeat(10., 12),
        )
        bs.station_type = StationType.IMT_UE
        bs.is_space_station = False

        for i in range(0, 3):
            bs.active[i] = False

        path = PropagationPath.create_default(single_sta, bs)
        parameters = Parameters()
        parameters.imt.topology.type = "MSS_DC"
        parameters.imt.interfered_with = True
        gains0 = np.zeros(path._orig_shape)

        bs_w_beams_gains = np.zeros([path._orig_shape[1], path._orig_shape[0], 3])
        for ch_model in [
            "FSPL",
            "ABG",
            "UMa",
            "UMi",
            # "SatelliteSimple",
            "TerrestrialSimple",
            "P619",
            "P452",
            "TVRO-URBAN",
            "TVRO-SUBURBAN",
            "HDFSS",
            "INDOOR",
        ]:
            rng = np.random.RandomState(1)
            propagation = PropagationFactory.create_propagation(
                ch_model, parameters,
                parameters.single_earth_station,
                rng,
            )
            if hasattr(propagation, "_get_atmospheric_gasses_loss"):
                # since P619 takes too long calculating this
                propagation._get_atmospheric_gasses_loss = create_mock_function(0.0)

            ploss = path.get_path_loss(
                propagation,
                parameters,
                1e3,  # [MHz]
                sta_a_gains=gains0,
                # sta_b_gains=gains0.T,
                sta_b_gains=bs_w_beams_gains,
            )

            if ch_model == "HDFSS":
                ploss = ploss[0]

            expected_shape = (single_sta.num_stations, bs.num_stations)
            expected_filled = np.stack(np.where(path._mask), axis=0)
            expected_nans = np.stack(np.where(~path._mask), axis=0)

            if ch_model == "INDOOR":
                # NOTE: current Indoor channel model implementaiton
                # depends on the matrix structure so it does not consider
                # the only active paths for path loss calculation
                # TODO: update indoor implementation to let that happen
                expected_filled = np.stack(np.where(np.ones(expected_shape)), axis=0)
                expected_nans = np.stack(np.where(np.zeros(expected_shape)), axis=0)
            else:
                # checking if the _paths_from_to is representative
                npt.assert_array_equal(expected_filled, path._paths_from_to.T)

            self.assertEqual(ploss.shape, expected_shape)
            npt.assert_array_equal(ploss[tuple(expected_nans)], np.nan)
            assert_array_not_equal(ploss[tuple(expected_filled)], np.nan)


if __name__ == '__main__':
    # unittest.main(module="tests.test_propagation_path")
    unittest.main()
