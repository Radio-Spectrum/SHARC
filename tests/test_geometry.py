import unittest
import numpy as np
import numpy.testing as npt

from sharc.support.geometry import (
    SimulatorGeometry, DWNReferenceFrame, ENUReferenceFrame, RigidTransform
)
from sharc.satellite.ngso.constants import EARTH_RADIUS_M
from copy import deepcopy
from scipy.spatial.transform import Rotation
from itertools import product


def random_rigid_transform(rng, N):
    """
    Generate a random RigidTransform with batch size N.
    Rotations are orthonormal matrices generated via QR.
    """
    A = rng.normal(size=(N, 3, 3))
    Q, _ = np.linalg.qr(A)

    # ensure right-handed (det = +1)
    det = np.linalg.det(Q)
    Q[det < 0, :, 0] *= -1

    t = rng.normal(size=(N, 3))

    return RigidTransform(Rotation.from_matrix(Q), t)


def rot_identity(n=1):
    """Returns identity rotation of batch size n."""
    return Rotation.from_rotvec(np.zeros((n, 3)))


def rot_z(angle_deg, n=1):
    """Returns rotation about Z axis by angle_deg degrees, batch size n."""
    return Rotation.from_rotvec(
        np.tile([0.0, 0.0, angle_deg], (n, 1)),
        degrees=True
    )


def rot_x(angle_deg, n=1):
    """Returns rotation about X axis by angle_deg degrees, batch size n."""
    return Rotation.from_rotvec(
        np.tile([angle_deg, 0.0, 0.0], (n, 1)),
        degrees=True
    )


def rot_y(angle_deg, n=1):
    """Returns rotation about Y axis by angle_deg degrees, batch size n."""
    return Rotation.from_rotvec(
        np.tile([0.0, angle_deg, 0.0], (n, 1)),
        degrees=True
    )


class TestRigidTransform(unittest.TestCase):
    """Unit tests for RigidTransform class."""

    def setUp(self):
        """Set up test fixtures for RigidTransform tests."""
        pass

    def test_init_and_broadcasting(self):
        """Test RigidTransform initialization and broadcasting behavior."""
        for rot_shp, t_shp in product(
            [(1, 3), (4, 3)],
            [(1, 3), (4, 3)],
        ):
            Nrot = rot_shp[0]
            Nt = t_shp[0]
            N = max(Nrot, Nt)

            rot = rot_identity(rot_shp[0])
            t = np.zeros(t_shp)

            with self.assertRaises(ValueError):
                RigidTransform(rot, np.zeros((3,)))

            if Nt > 1:
                with self.assertRaises(ValueError):
                    RigidTransform(rot_identity(N + 1), t)

            if Nrot > 1:
                with self.assertRaises(ValueError):
                    RigidTransform(rot, np.zeros((N + 1, 3)))

            # should not throw:
            tr = RigidTransform(rot, t)
            RigidTransform(rot, np.zeros((1, 3)))
            RigidTransform(rot_identity(1), t)

            # test broadcasting contracts:
            for fn in [tr.apply_points, tr.apply_vectors]:
                if N > 1:
                    with self.assertRaises(AssertionError):
                        fn(np.zeros((N + 1, 3)))

                for in_shp in [(1, 3), (N, 3)]:
                    res = fn(np.zeros(in_shp))
                    npt.assert_equal(
                        res.shape, (N, 3)
                    )

            for fn, in_shp in product(
                [tr.apply_points_permutation, tr.apply_vectors_permutation],
                [(1, 3), (N, 3), (N + 1, 3)]
            ):
                Nin = in_shp[0]
                res = fn(np.zeros(in_shp))
                npt.assert_equal(
                    res.shape, (N, Nin, 3)
                )

    def test_simple_transformations(self):
        """Test RigidTransform simple transformations and their combinations."""
        eps = 1e-4

        ux = np.array([1., 0., 0.])
        uy = np.array([0., 1., 0.])
        uz = np.array([0., 0., 1.])
        u = np.array([ux, uy, uz, ux + uy + uz])

        #######################################################################
        # Identity transform
        id_tr = RigidTransform(rot_identity(4), np.zeros((1, 3)))
        out = id_tr.apply_points(u)
        npt.assert_equal(out, u)

        out = id_tr.apply_vectors(u)
        npt.assert_equal(out, u)

        out = id_tr.apply_points_permutation(u)
        npt.assert_equal(out, np.stack((u, u, u, u)))

        out = id_tr.apply_vectors_permutation(u)
        npt.assert_equal(out, np.stack((u, u, u, u)))

        #######################################################################
        # Translation only transform
        t1_tr = RigidTransform(rot_identity(4), np.ones((1, 3)))
        out = t1_tr.apply_points(u)
        npt.assert_equal(out, u + 1.)
        out = t1_tr.inv().apply_points(out)
        npt.assert_equal(out, u)

        out = t1_tr.apply_vectors(u)
        npt.assert_equal(out, u)

        out = t1_tr.apply_points_permutation(u)
        npt.assert_equal(out, np.stack((u, u, u, u)) + 1.)
        out = t1_tr.inv().apply_points(out[0])
        npt.assert_equal(out, u)

        out = t1_tr.apply_vectors_permutation(u)
        npt.assert_equal(out, np.stack((u, u, u, u)))

        #######################################################################
        # Rotation Z only transform
        rot_z90_tr = RigidTransform(
            rot_z(-90.), np.zeros((1, 3))
        )
        out_rot_z90 = rot_z90_tr.apply_points(u)
        npt.assert_allclose(
            out_rot_z90,
            np.array([
                -uy, ux, uz, ux - uy + uz
            ]),
            atol=eps
        )
        out = rot_z90_tr.inv().apply_points(out_rot_z90)
        npt.assert_allclose(
            out,
            u,
            atol=eps
        )

        #######################################################################
        # Rotation X only transform
        rot_x90_tr = RigidTransform(
            rot_x(-90., 4), np.zeros((1, 3))
        )

        out_rot_z90_x90 = rot_x90_tr.apply_points(out_rot_z90)
        expected_out_rot_z90_x90 = np.array([
            uz, ux, uy, ux + uy + uz
        ])
        npt.assert_allclose(
            out_rot_z90_x90,
            expected_out_rot_z90_x90,
            atol=eps
        )
        out = rot_x90_tr.inv().apply_points(expected_out_rot_z90_x90)
        npt.assert_allclose(
            out,
            out_rot_z90,
            atol=eps
        )

        #######################################################################
        # Rotation Z and then Rotation X transform
        npt.assert_allclose(
            rot_z90_tr.and_then(rot_x90_tr).apply_points(u),
            expected_out_rot_z90_x90,
            atol=eps,
        )
        npt.assert_allclose(
            (rot_z90_tr.and_then(rot_x90_tr).inv()
                .apply_points(expected_out_rot_z90_x90)),
            u,
            atol=eps,
        )
        npt.assert_allclose(
            (rot_x90_tr.inv().and_then(rot_z90_tr.inv())
                .apply_points(expected_out_rot_z90_x90)),
            u,
            atol=eps,
        )

        #######################################################################
        # Rotation Z and then Rotation X and then Translation transform
        npt.assert_allclose(
            rot_z90_tr.and_then(rot_x90_tr).and_then(t1_tr).apply_points(u),
            expected_out_rot_z90_x90 + 1.,
            atol=eps,
        )
        npt.assert_allclose(
            (rot_z90_tr.and_then(rot_x90_tr).and_then(t1_tr).inv()
                .apply_points(expected_out_rot_z90_x90 + 1.)),
            u,
            atol=eps,
        )
        npt.assert_allclose(
            (t1_tr.inv().and_then(rot_x90_tr.inv().and_then(rot_z90_tr.inv()))
                .apply_points(expected_out_rot_z90_x90 + 1.)),
            u,
            atol=eps,
        )
        # considering that VECTOR calculation should NOT translate
        npt.assert_allclose(
            rot_z90_tr.and_then(rot_x90_tr).and_then(t1_tr).apply_vectors(u),
            expected_out_rot_z90_x90,
            atol=eps,
        )
        npt.assert_allclose(
            (rot_z90_tr.and_then(rot_x90_tr).and_then(t1_tr).inv()
                .apply_vectors(expected_out_rot_z90_x90)),
            u,
            atol=eps,
        )
        npt.assert_allclose(
            (t1_tr.inv().and_then(rot_x90_tr.inv().and_then(rot_z90_tr.inv()))
                .apply_vectors(expected_out_rot_z90_x90)),
            u,
            atol=eps,
        )

    def test_permutation_points_equivalence(self):
        """Test equivalence of permutation and non-permutation point applications."""
        rng = np.random.default_rng(0)

        for n in range(1, 10):
            tr = random_rigid_transform(rng, n)

            x = rng.normal(size=(n, 3))

            y = tr.apply_points(x)
            y_permutation = tr.apply_points_permutation(x)

            # diagonal of permutation must equal non-permutation
            npt.assert_allclose(
                y,
                y_permutation.diagonal().T,
                atol=1e-12,
            )

    def test_permutation_vectors_equivalence(self):
        """Test equivalence of permutation and non-permutation vector applications."""
        rng = np.random.default_rng(0)

        for n in range(1, 10):
            tr = random_rigid_transform(rng, n)

            x = rng.normal(size=(n, 3))

            y = tr.apply_vectors(x)
            y_permutation = tr.apply_vectors_permutation(x)

            # diagonal of permutation must equal non-permutation
            npt.assert_allclose(
                y,
                y_permutation.diagonal().T,
                atol=1e-12,
            )

    def test_take_commutes_with_apply_points(self):
        """Test that 'take' method commutes with apply_points."""
        rng = np.random.default_rng(0)

        for n in range(1, 10):
            tr = random_rigid_transform(rng, n)
            x = rng.normal(size=(n, 3))

            y_full = tr.apply_points(x)

            for i in range(n):
                y_take = tr.take(i).apply_points(x)
                npt.assert_allclose(
                    y_take[i],
                    y_full[i],
                    atol=1e-12,
                )

    def test_take_matches_permutation_points(self):
        """Test that 'take' method matches permutation point applications."""
        rng = np.random.default_rng(1)

        for n in [2, 5]:
            tr = random_rigid_transform(rng, n)
            x = rng.normal(size=(n, 3))

            Y = tr.apply_points_permutation(x)

            for i in range(n):
                tr_i = tr.take(i)
                yi = tr_i.apply_points(x)

                npt.assert_allclose(
                    yi,
                    Y[i],
                    rtol=1e-12,
                    atol=1e-12,
                )

    def test_take_matches_permutation_vectors(self):
        """Test that 'take' method matches permutation vector applications."""
        rng = np.random.default_rng(1)

        for n in [2, 5]:
            tr = random_rigid_transform(rng, n)
            x = rng.normal(size=(n, 3))

            Y = tr.apply_vectors_permutation(x)

            for i in range(n):
                tr_i = tr.take(i)
                yi = tr_i.apply_vectors(x)

                npt.assert_allclose(
                    yi,
                    Y[i],
                    rtol=1e-12,
                    atol=1e-12,
                )


class TestDWNReferenceFrame(unittest.TestCase):
    """Unit tests for DWNReferenceFrame class."""

    def setUp(self):
        """Set up test fixtures for DWNReferenceFrame tests."""
        self.lat = np.array([0.0])
        self.lon = np.array([0.0])
        self.alt = np.array([0.0])

        self.enu = ENUReferenceFrame(
            lat=self.lat, lon=self.lon, alt=self.alt
        )
        self.dwn = DWNReferenceFrame(
            lat=self.lat, lon=self.lon, alt=self.alt
        )

    def test_enu_to_dwn_basis(self):
        """Test transformation of basis vectors from ENU to DWN."""
        # ENU basis vectors
        e = np.array([1.0, 0.0, 0.0])  # East
        n = np.array([0.0, 1.0, 0.0])  # North
        u = np.array([0.0, 0.0, 1.0])  # Up

        # Transform ENU -> ECEF -> DWN
        e_dwn = self.dwn.from_ecef.apply_vectors(
            self.enu.to_ecef.apply_vectors(e)
        )[0]
        n_dwn = self.dwn.from_ecef.apply_vectors(
            self.enu.to_ecef.apply_vectors(n)
        )[0]
        u_dwn = self.dwn.from_ecef.apply_vectors(
            self.enu.to_ecef.apply_vectors(u)
        )[0]

        npt.assert_allclose(e_dwn, np.array([0.0, -1.0, 0.0]), atol=1e-4)
        npt.assert_allclose(n_dwn, np.array([0.0, 0.0, 1.0]), atol=1e-4)
        npt.assert_allclose(u_dwn, np.array([-1.0, 0.0, 0.0]), atol=1e-4)
        npt.assert_allclose(
            np.linalg.norm(e_dwn),
            np.linalg.norm(e),
        )
        npt.assert_allclose(
            np.linalg.norm(n_dwn),
            np.linalg.norm(n),
        )
        npt.assert_allclose(
            np.linalg.norm(u_dwn),
            np.linalg.norm(u),
        )


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
        npt.assert_allclose(
            np.stack((geom.x_local, geom.y_local, geom.z_local)),
            np.stack((expect_local["x"], expect_local["y"], expect_local["z"])),
            atol=0.001
        )
        # npt.assert_allclose(geom.x_local, expect_local["x"], atol=0.001)
        # npt.assert_allclose(geom.y_local, expect_local["y"], atol=0.001)
        # npt.assert_allclose(geom.z_local, expect_local["z"], atol=0.001)
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

        npt.assert_allclose(
            np.stack((geom.x_global, geom.y_global, geom.z_global)),
            np.stack((expect_global["x"], expect_global["y"], expect_global["z"])),
            atol=0.001
        )
        # npt.assert_allclose(geom.x_global, expect_global["x"], atol=0.001)
        # npt.assert_allclose(geom.y_global, expect_global["y"], atol=0.001)
        # npt.assert_allclose(geom.z_global, expect_global["z"], atol=0.001)
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
        ref_lla = (10, -5, 1200)
        ref_frame = ENUReferenceFrame(
            lat=ref_lla[0], lon=ref_lla[1], alt=ref_lla[2],
        )
        no_local = SimulatorGeometry(3, False, ref_frame)
        local_eq_global = SimulatorGeometry(3, True, ref_frame)
        local_eq_global.set_local_reference_frame(
            ENUReferenceFrame(
                lat=np.repeat([ref_lla[0]], 3),
                lon=np.repeat([ref_lla[1]], 3),
                alt=np.repeat([ref_lla[2]], 3),
            )
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
        ref_lla = (-45.0, 90, 30.)
        ref_frame = ENUReferenceFrame(
            lat=ref_lla[0], lon=ref_lla[1], alt=ref_lla[2],
        )

        alt_vals = np.array([500., 800., 1200., 1800.])

        def init_diff_alt():
            geom = SimulatorGeometry(4, True, ref_frame)
            geom.set_local_reference_frame(
                ENUReferenceFrame(
                    lat=np.repeat([ref_lla[0]], 4),
                    lon=np.repeat([ref_lla[1]], 4),
                    alt=alt_vals,
                )
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
        alt_vals_diff = ref_lla[2] - alt_vals
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
        ref_lla = (0.0, 0.0, 0.0)
        ref_frame = ENUReferenceFrame(
            lat=ref_lla[0], lon=ref_lla[1], alt=ref_lla[2],
        )

        llas = np.array([
            [-90., 0., 0.],
            [90., 0., 0.],
            [0., 90., 0.],
            [0., -90., 0.],
        ]).T

        def init_diff_llas():
            geom = SimulatorGeometry(4, True, ref_frame)
            geom.set_local_reference_frame(
                ENUReferenceFrame(
                    lat=llas[0],
                    lon=llas[1],
                    alt=llas[2],
                )
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
        ref_lla = (90., 0., 0.)
        ref_frame = ENUReferenceFrame(
            lat=ref_lla[0], lon=ref_lla[1], alt=ref_lla[2],
        )
        local_llas = np.array([
            [0., 0., 0.],
            [0., 1., 0.],
            [0., -1., 0.],
            [1., 0., 0.],
            [-1., 0., 0.],
        ]).T

        def init_geom():
            geom = SimulatorGeometry(5, True, ref_frame)
            geom.set_local_reference_frame(
                ENUReferenceFrame(
                    lat=local_llas[0],
                    lon=local_llas[1],
                    alt=local_llas[2],
                )
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
            atol=1e-8,  # tolerance for == 0.
            rtol=0.3 / 100,  # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[1], np.array([111e3, 0., 2 * 111e3, np.sqrt(2) * 111e3, np.sqrt(2) * 111e3]),
            atol=1e-8,  # tolerance for == 0.
            rtol=0.3 / 100,  # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[2], np.array([111e3, 2 * 111e3, 0., np.sqrt(2) * 111e3, np.sqrt(2) * 111e3]),
            atol=1e-8,  # tolerance for == 0.
            rtol=0.3 / 100,  # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[3], np.array([111e3, np.sqrt(2) * 111e3, np.sqrt(2) * 111e3, 0., 2 * 111e3]),
            atol=1e-8,  # tolerance for == 0.
            rtol=0.3 / 100,  # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[4], np.array([111e3, np.sqrt(2) * 111e3, np.sqrt(2) * 111e3, 2 * 111e3, 0.]),
            atol=1e-8,  # tolerance for == 0.
            rtol=0.3 / 100,  # tolerance for all others
        )

    def test_get_local_distance_to_same_ref(self):
        """Tests getting local distance from a station to another when
        they have same local references
        """
        ref_lla = (90., 0., 0.)
        ref_frame = ENUReferenceFrame(
            lat=ref_lla[0], lon=ref_lla[1], alt=ref_lla[2],
        )
        local_llas = np.array([
            [0., 0., 0.],
            [0., 0., 0.],
            [0., -1., 0.],
            [0., -1., 0.],
        ]).T

        def init_geom():
            geom = SimulatorGeometry(4, True, ref_frame)
            geom.set_local_reference_frame(
                ENUReferenceFrame(
                    lat=local_llas[0],
                    lon=local_llas[1],
                    alt=local_llas[2],
                )
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
            rtol=0.4 / 100,  # tolerance for all others
        )
        npt.assert_allclose(
            dists2d[2:, :2], 111e3,
            rtol=0.4 / 100,  # tolerance for all others
        )

    def test_get_local_elevation(self):
        """Tests getting local elevation from a station to another.
        """
        ref_lla = (90., 0., 0.)
        ref_frame = ENUReferenceFrame(
            lat=ref_lla[0], lon=ref_lla[1], alt=ref_lla[2],
        )
        local_llas = np.array([
            [0., 0., 0.],
            [0., 0., 0.],
            [0., -1., 0.],
            [0., -1., 0.],
        ]).T

        def init_geom():
            geom = SimulatorGeometry(4, True, ref_frame)
            geom.set_local_reference_frame(
                ENUReferenceFrame(
                    lat=local_llas[0],
                    lon=local_llas[1],
                    alt=local_llas[2],
                )
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
