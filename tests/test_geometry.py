import unittest
import numpy as np
import numpy.testing as npt
from sharc.support.geometry import SimulatorGeometry
from sharc.satellite.ngso.constants import EARTH_RADIUS_M
from copy import deepcopy


class TestGeometry(unittest.TestCase):
    """Unit tests for the CoordinateSystem class and related coordinate transformations."""

    def _test_expected_geom(
        self,
        geom,
        expect_local,
        expect_global,
        *,
        only_global_azim=None,
        only_local_azim=None
    ):
        npt.assert_allclose(geom.x_local, expect_local["x"], atol=0.001)
        npt.assert_allclose(geom.y_local, expect_local["y"], atol=0.001)
        npt.assert_allclose(geom.z_local, expect_local["z"], atol=0.001)
        npt.assert_allclose(geom.pointn_elev_local, expect_local["elev"], atol=0.001)
        if only_local_azim is None:
            npt.assert_allclose(geom.pointn_azim_local, expect_local["azim"], atol=0.001)
        else:
            self.assertEqual(expect_local["azim"].shape, geom.pointn_azim_local.shape)
            npt.assert_allclose(
                geom.pointn_azim_local[only_local_azim],
                expect_local["azim"][only_local_azim],
                atol=0.001
            )

        npt.assert_allclose(geom.x_global, expect_global["x"], atol=0.001)
        npt.assert_allclose(geom.y_global, expect_global["y"], atol=0.001)
        npt.assert_allclose(geom.z_global, expect_global["z"], atol=0.001)
        npt.assert_allclose(geom.pointn_elev_global, expect_global["elev"], atol=0.001)
        if only_global_azim is None:
            npt.assert_allclose(
                geom.pointn_azim_global,
                expect_global["azim"],
                atol=0.001
            )
        else:
            self.assertEqual(expect_local["azim"].shape, geom.pointn_azim_local.shape)
            npt.assert_allclose(
                geom.pointn_azim_global[only_global_azim],
                expect_global["azim"][only_global_azim],
                atol=0.001
            )

    def setUp(self):
        """Set up test fixtures for CoordinateSystem tests."""
        pass

    def test_set_coords_when_local_eq_global(self):
        """Test setting coordinates when local should eq global
        """
        ref = (10, -5, 1200)

        no_local = SimulatorGeometry(3, False, ref)
        local_eq_global = SimulatorGeometry(3, True, ref)
        local_eq_global.set_local_coord_sys(
            np.repeat([ref[0]], 3),
            np.repeat([ref[1]], 3),
            np.repeat([ref[2]], 3),
        )

        """Test setting global coordinates
        """
        expect = {
            "x": np.array([10., 11., 21.]), "y": np.array([15., 19., 211]),
            "z": np.array([20., 30., 50.]),
            "azim": np.array([90., 70., 170.]), "elev": np.array([12., 15., 19.]),
        }
        no_local.set_global_coords(**expect)
        local_eq_global.set_global_coords(**expect)

        """Verify that when local reference is not set or is set to global ref,
        local and global are set to the expected, equal, value
        """
        self._test_expected_geom(no_local, expect, expect)
        self._test_expected_geom(local_eq_global, expect, expect)

        """Test setting local coordinates
        """
        expect = {
            "x": np.array([1235., 1241., 12341.]), "y": np.array([12413., 89012., 767.]),
            "z": np.array([91238., 481., 123980.]),
            "azim": np.array([-10., -12., -98.]), "elev": np.array([-70., -1., 0.]),
        }
        no_local.set_local_coords(**expect)
        local_eq_global.set_local_coords(**expect)

        """Verify that when local reference is not set or is the same as global
        local and global are set to the expected, equal, value
        """
        self._test_expected_geom(no_local, expect, expect)
        self._test_expected_geom(local_eq_global, expect, expect)

    def test_setting_different_alts(self):
        """Test setting coordinates when local should eq global
        """
        ref = (-45.0, 90, 30.)

        alt_vals = np.array([500., 800., 1200., 1800.])
        def init_diff_alt():
            geom = SimulatorGeometry(4, True, ref)
            geom.set_local_coord_sys(
                np.repeat([ref[0]], 4),
                np.repeat([ref[1]], 4),
                alt_vals,
            )
            return geom
        diff_alt = init_diff_alt()

        """Test setting global coordinates
        """
        expect_local = {
            "x": np.array([10., 11., 12., 985.]), "y": np.array([15., 31., 41341., 10.]),
            "z": np.array([-5., 100., 1e4, -1e3]),
            "azim": np.array([90., 10., -179., 180.]), "elev": np.array([89., -89., -1., 12.]),
        }
        expect_global = deepcopy(expect_local)
        alt_vals_diff = ref[2] - alt_vals
        expect_global["z"] -= alt_vals_diff

        diff_alt.set_global_coords(**expect_global)

        """Verify that when local reference is not set, local and global
        are set to the expected, equal, value
        """
        self._test_expected_geom(diff_alt, expect_local, expect_global)

        """Test setting local coordinates
        """
        diff_alt = init_diff_alt()
        diff_alt.set_local_coords(**expect_local)

        """Verify that when local reference is set to be the same as global,
        local and global are set to the expected, value
        """
        self._test_expected_geom(diff_alt, expect_local, expect_global)

    def test_setting_different_llas(self):
        """Test setting coordinates when local should eq global
        """
        ref = (0.0, 0.0, 0.0)

        llas = np.array([
            [-90., 0., 0.],
            [90., 0., 0.],
            [0., 90., 0.],
            [0., -90., 0.],
        ]).T
        def init_diff_llas():
            geom = SimulatorGeometry(4, True, ref)
            geom.set_local_coord_sys(
                llas[0],
                llas[1],
                llas[2],
            )
            return geom

        """Test setting global coordinates
        """
        expect_local = {
            "x": np.zeros(4), "y": np.zeros(4),
            "z": np.zeros(4),
            # point to north
            "azim": np.zeros(4) + 90., "elev": np.zeros(4) - 10,
        }
        expect_global = {
            "x": np.array([0., 0., 1., -1.]) * EARTH_RADIUS_M,
            "y": np.array([-1., 1., 0., 0.]) * EARTH_RADIUS_M,
            "z": np.zeros(4) - EARTH_RADIUS_M,
            "azim": np.array([90., -90., 100., 80.]),
            "elev": np.array([80., -80., 0., 0.]),
        }

        diff_llas = init_diff_llas()
        diff_llas.set_local_coords(**expect_local)

        self._test_expected_geom(
            diff_llas, expect_local, expect_global,
            # only_global_azim=np.where(abs(expect_global["elev"]) != 90.),
            # only_local_azim=np.where(abs(expect_local["elev"]) != 90.),
        )

        diff_llas = init_diff_llas()
        diff_llas.set_global_coords(**expect_global)

        self._test_expected_geom(
            diff_llas, expect_local, expect_global,
            # only_global_azim=np.where(abs(expect_global["elev"]) != 90.),
            # only_local_azim=np.where(abs(expect_local["elev"]) != 90.),
        )

    def test_get_local_distance_to_diff_ref(self):
        """Tests getting local distance from a station to another when
        they have different local references
        """
        ref = (90., 0., 0.)
        local_llas = np.array([
            [0., 0., 0.],
            [0., 1., 0.],
            [0., -1., 0.],
            [1., 0., 0.],
            [-1., 0., 0.],
        ]).T
        def init_geom():
            geom = SimulatorGeometry(5, True, ref)
            geom.set_local_coord_sys(
                local_llas[0],
                local_llas[1],
                local_llas[2],
            )
            geom.set_local_coords(
                np.repeat(0., 5),
                np.repeat(0., 5),
                np.repeat(0., 5),
                np.repeat(0., 5),
                np.repeat(0., 5),
            )
            return geom

        geom = init_geom()

        dists2d = geom.get_local_distance_to(geom)

        self.assertEqual(dists2d.shape, (5, 5))

        # distance of any coord to itself
        npt.assert_allclose(np.diagonal(dists2d), 0., atol=1e-8)

        # assuming 1deg difference should be ~ 111km at lat,lon = (0, 0)
        npt.assert_allclose(
            dists2d[0], np.array([0., 111e3, 111e3, 111e3, 111e3]),
            atol=1e-8, # tolerance for == 0.
            rtol=0.3/100, # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[1], np.array([111e3, 0., 2 * 111e3, np.sqrt(2) * 111e3, np.sqrt(2) * 111e3]),
            atol=1e-8, # tolerance for == 0.
            rtol=0.3/100, # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[2], np.array([111e3, 2 * 111e3, 0.,  np.sqrt(2) * 111e3, np.sqrt(2) * 111e3]),
            atol=1e-8, # tolerance for == 0.
            rtol=0.3/100, # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[3], np.array([111e3, np.sqrt(2) * 111e3, np.sqrt(2) * 111e3,  0., 2 * 111e3]),
            atol=1e-8, # tolerance for == 0.
            rtol=0.3/100, # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[4], np.array([111e3, np.sqrt(2) * 111e3, np.sqrt(2) * 111e3,  2 * 111e3, 0.]),
            atol=1e-8, # tolerance for == 0.
            rtol=0.3/100, # tolerance for all others
        )

    def test_get_local_distance_to_same_ref(self):
        """Tests getting local distance from a station to another when
        they have same local references
        """
        ref = (90., 0., 0.)
        local_llas = np.array([
            [0., 0., 0.],
            [0., 0., 0.],
            [0., -1., 0.],
            [0., -1., 0.],
        ]).T

        def init_geom():
            geom = SimulatorGeometry(4, True, ref)
            geom.set_local_coord_sys(
                local_llas[0],
                local_llas[1],
                local_llas[2],
            )
            geom.set_local_coords(
                np.tile([0., 20.], 2),
                np.tile([0., 20.], 2),
                np.tile([0., 10.], 2),
                np.repeat(0., 4),
                np.repeat(0., 4),
            )
            return geom

        geom = init_geom()

        dists2d, z_dist = geom.get_local_distance_to(geom, return_z_dist=True)

        self.assertEqual(dists2d.shape, (4, 4))
        self.assertEqual(z_dist.shape, (4, 4))

        # distance of any coord to itself
        npt.assert_allclose(np.diagonal(dists2d), 0., atol=1e-8)
        npt.assert_allclose(np.diagonal(z_dist), 0., atol=1e-8)

        # and that square diagonal is sqrt(2) * side_len
        npt.assert_allclose(
            dists2d[0, :2], np.array([0., 20 * np.sqrt(2)]),
            atol=1e-8,
        )
        npt.assert_allclose(
            z_dist[0, :2], np.array([0., 10]),
            atol=1e-8,
        )

        npt.assert_allclose(
            dists2d[1, :2], np.array([20 * np.sqrt(2), 0.]),
            atol=1e-8,
        )
        npt.assert_allclose(
            z_dist[1, :2], np.array([-10, 0.]),
            atol=1e-8,
        )

        npt.assert_allclose(
            dists2d[2, 2:], np.array([0., 20 * np.sqrt(2)]),
            atol=1e-8,
        )
        npt.assert_allclose(
            z_dist[2, 2:], np.array([0, 10.]),
            atol=1e-8,
        )

        npt.assert_allclose(
            dists2d[3, 2:], np.array([20 * np.sqrt(2), 0.]),
            atol=1e-8,
        )
        npt.assert_allclose(
            z_dist[3, 2:], np.array([-10., 0.]),
            atol=1e-8,
        )

        # assuming 1deg difference should be ~ 111km at lat,lon = (0, 0)
        npt.assert_allclose(
            dists2d[:2, 2:], 111e3,
            rtol=0.4/100, # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[2:, :2], 111e3,
            rtol=0.4/100, # tolerance for all others
        )

    def test_get_local_elevation(self):
        """Tests getting local elevation from a station to another.
        """
        ref = (90., 0., 0.)
        local_llas = np.array([
            [0., 0., 0.],
            [0., 0., 0.],
            [0., -1., 0.],
            [0., -1., 0.],
        ]).T

        def init_geom():
            geom = SimulatorGeometry(4, True, ref)
            geom.set_local_coord_sys(
                local_llas[0],
                local_llas[1],
                local_llas[2],
            )
            geom.set_local_coords(
                np.tile([0., 20.], 2),
                np.tile([0., 0.], 2),
                np.tile([0., 20.], 2),
                np.repeat(0., 4),
                np.repeat(0., 4),
            )
            return geom

        geom = init_geom()

        elev = geom.get_local_elevation(geom)

        self.assertEqual(elev.shape, (4, 4))

        npt.assert_allclose(elev[0, 1], 45.)
        npt.assert_allclose(elev[1, 0], -45.)

        npt.assert_allclose(elev[2, 3], 45.)
        npt.assert_allclose(elev[3, 2], -45.)

        # obviously below horizon for each other
        npt.assert_array_less(elev[:2, 2:], 0.)
        npt.assert_array_less(elev[2:, :2], 0.)


if __name__ == '__main__':
    unittest.main()
