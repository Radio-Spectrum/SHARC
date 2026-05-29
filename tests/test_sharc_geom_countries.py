# -*- coding: utf-8 -*-
"""
Tests for sharc.support.sharc_geom_countries module.

Covers:
  - cartesian_to_polar / polar_to_cartesian conversions
  - get_rotation_matrix for identity and 90° rotations
  - rotate_angles_based_on_new_nadir
  - GeometryConverter: set_reference, roundtrip, station transforms
  - generate_grid_in_polygon / generate_grid_in_multipolygon
  - shrink_country_polygon_by_km / shrink_countries_by_km
  - get_lambert_equal_area_crs
"""

import unittest
import numpy as np
import numpy.testing as npt
from shapely.geometry import box, Polygon, MultiPolygon, Point

from sharc.support.sharc_geom_countries import (
    cartesian_to_polar,
    polar_to_cartesian,
    get_rotation_matrix,
    rotate_angles_based_on_new_nadir,
    GeometryConverter,
    get_lambert_equal_area_crs,
    shrink_country_polygon_by_km,
    shrink_countries_by_km,
    generate_grid_in_polygon,
    generate_grid_in_multipolygon,
)

# WGS-84 constants
_WGS84_A = 6378137.0
_WGS84_F = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)


class TestCartesianPolar(unittest.TestCase):
    """Tests for cartesian <-> polar coordinate conversions."""

    def test_cartesian_to_polar_x_axis(self):
        """Point on +X axis: range=1, az=0°, el=0°."""
        r, az, el = cartesian_to_polar(
            np.array([1.0]), np.array([0.0]), np.array([0.0])
        )
        npt.assert_allclose(r, [1.0], atol=1e-12)
        npt.assert_allclose(az, [0.0], atol=1e-12)
        npt.assert_allclose(el, [0.0], atol=1e-12)

    def test_cartesian_to_polar_y_axis(self):
        """Point on +Y axis: range=1, az=90°, el=0°."""
        r, az, el = cartesian_to_polar(
            np.array([0.0]), np.array([1.0]), np.array([0.0])
        )
        npt.assert_allclose(r, [1.0], atol=1e-12)
        npt.assert_allclose(az, [90.0], atol=1e-12)
        npt.assert_allclose(el, [0.0], atol=1e-12)

    def test_cartesian_to_polar_z_axis(self):
        """Point on +Z axis: range=1, el=90°."""
        r, az, el = cartesian_to_polar(
            np.array([0.0]), np.array([0.0]), np.array([1.0])
        )
        npt.assert_allclose(r, [1.0], atol=1e-12)
        npt.assert_allclose(el, [90.0], atol=1e-12)

    def test_cartesian_to_polar_negative_z(self):
        """Point on -Z axis: el=-90°."""
        r, az, el = cartesian_to_polar(
            np.array([0.0]), np.array([0.0]), np.array([-1.0])
        )
        npt.assert_allclose(el, [-90.0], atol=1e-12)

    def test_polar_to_cartesian_roundtrip(self):
        """Convert polar->cartesian->polar and check recovery."""
        r_in = np.array([5.0, 10.0, 1.0])
        az_in = np.array([30.0, -45.0, 120.0])
        el_in = np.array([15.0, -30.0, 60.0])

        x, y, z = polar_to_cartesian(r_in, az_in, el_in)
        r_out, az_out, el_out = cartesian_to_polar(x, y, z)

        npt.assert_allclose(r_out, r_in, atol=1e-10)
        npt.assert_allclose(az_out, az_in, atol=1e-10)
        npt.assert_allclose(el_out, el_in, atol=1e-10)

    def test_cartesian_to_polar_vectorized(self):
        """Array inputs produce correct output shapes."""
        x = np.array([1.0, 0.0, 0.0])
        y = np.array([0.0, 1.0, 0.0])
        z = np.array([0.0, 0.0, 1.0])
        r, az, el = cartesian_to_polar(x, y, z)
        self.assertEqual(r.shape, (3,))
        self.assertEqual(az.shape, (3,))
        self.assertEqual(el.shape, (3,))


class TestRotationMatrix(unittest.TestCase):
    """Tests for get_rotation_matrix."""

    def test_identity(self):
        """Zero rotation gives identity matrix."""
        R = get_rotation_matrix(0, 0)
        npt.assert_allclose(np.array(R), np.eye(3), atol=1e-12)

    def test_90deg_around_z(self):
        """90° around Z maps (1,0,0) -> (0,1,0)."""
        R = get_rotation_matrix(90, 0)
        result = np.array(R @ np.array([[1], [0], [0]])).flatten()
        npt.assert_allclose(result, [0, 1, 0], atol=1e-12)

    def test_90deg_around_y(self):
        """90° around Y maps (1,0,0) -> (0,0,-1)."""
        R = get_rotation_matrix(0, 90)
        result = np.array(R @ np.array([[1], [0], [0]])).flatten()
        npt.assert_allclose(result, [0, 0, -1], atol=1e-12)

    def test_rotation_is_orthogonal(self):
        """Any rotation matrix should satisfy R^T * R = I."""
        R = np.array(get_rotation_matrix(37.5, 62.3))
        npt.assert_allclose(R.T @ R, np.eye(3), atol=1e-12)


class TestRotateAnglesNadir(unittest.TestCase):
    """Tests for rotate_angles_based_on_new_nadir."""

    def test_nadir_maps_to_minus90_elevation(self):
        """Nadir point rotated so that (elev=0, azim=0) maps to -90° elevation."""
        # When we rotate so that the nadir (el=-90, az=0) goes to (0,0),
        # the actual nadir point should end up at el=-90
        res_elev, res_azim = rotate_angles_based_on_new_nadir(
            np.array([-90.0]),
            np.array([0.0]),
            -90.0,
            0.0,
        )
        npt.assert_allclose(res_elev, [-90.0], atol=1e-6)

    def test_identity_nadir(self):
        """If nadir is at (elev=-90, azim=0) the rotation should be near identity."""
        elev = np.array([0.0, 45.0, -90.0])
        azim = np.array([0.0, 90.0, 0.0])
        res_elev, res_azim = rotate_angles_based_on_new_nadir(
            elev, azim, -90.0, 0.0
        )
        # The nadir point should remain at -90°
        npt.assert_allclose(res_elev[2], -90.0, atol=1e-8)


class TestGeometryConverter(unittest.TestCase):
    """Tests for the GeometryConverter class."""

    def test_validate_unset_raises(self):
        """validate() should raise ValueError if reference not set."""
        gc = GeometryConverter()
        with self.assertRaises(ValueError):
            gc.validate()

    def test_set_reference_equator_greenwich(self):
        """Setting reference at equator/Greenwich produces expected ECEF."""
        gc = GeometryConverter()
        gc.set_reference(0.0, 0.0, 0.0)
        # lla2ecef uses spherical Earth with R=6378145
        from sharc.satellite.ngso.constants import EARTH_RADIUS_M
        npt.assert_allclose(gc.ref_x, EARTH_RADIUS_M, rtol=1e-4)
        npt.assert_allclose(gc.ref_y, 0.0, atol=1.0)
        npt.assert_allclose(gc.ref_z, 0.0, atol=1.0)

    def test_set_reference_north_pole(self):
        """Setting reference at North Pole produces expected ECEF."""
        gc = GeometryConverter()
        gc.set_reference(90.0, 0.0, 0.0)
        from sharc.satellite.ngso.constants import EARTH_RADIUS_M
        npt.assert_allclose(gc.ref_x, 0.0, atol=1.0)
        npt.assert_allclose(gc.ref_y, 0.0, atol=1.0)
        npt.assert_allclose(gc.ref_z, EARTH_RADIUS_M, rtol=1e-4)

    def test_roundtrip_transform(self):
        """convert + revert should recover original ECEF coordinates."""
        gc = GeometryConverter()
        gc.set_reference(-15.0, -47.0, 100.0)

        # Some ECEF points (approximate surface of Earth)
        x_orig = np.array([4000000.0, 4100000.0, 3900000.0])
        y_orig = np.array([-4500000.0, -4400000.0, -4600000.0])
        z_orig = np.array([-1700000.0, -1600000.0, -1800000.0])

        x2, y2, z2 = gc.convert_cartesian_to_transformed_cartesian(
            x_orig, y_orig, z_orig
        )
        x_rev, y_rev, z_rev = gc.revert_transformed_cartesian_to_cartesian(
            x2, y2, z2
        )

        npt.assert_allclose(x_rev, x_orig, atol=1e-4)
        npt.assert_allclose(y_rev, y_orig, atol=1e-4)
        npt.assert_allclose(z_rev, z_orig, atol=1e-4)

    def test_reference_point_transforms_to_origin(self):
        """The reference point should transform to approximately (0,0,0)."""
        gc = GeometryConverter()
        gc.set_reference(-23.5, -46.6, 800.0)

        x2, y2, z2 = gc.convert_cartesian_to_transformed_cartesian(
            np.array([gc.ref_x]),
            np.array([gc.ref_y]),
            np.array([gc.ref_z]),
        )
        npt.assert_allclose(x2, [0.0], atol=1e-4)
        npt.assert_allclose(y2, [0.0], atol=1e-4)
        npt.assert_allclose(z2, [0.0], atol=1e-4)

    def test_rotation_only(self):
        """Using translate=0 should only rotate, not translate."""
        gc = GeometryConverter()
        gc.set_reference(0.0, 0.0, 0.0)

        v = np.array([1.0])
        zeros = np.array([0.0])

        # Rotate unit-X vector — should still have magnitude 1
        x2, y2, z2 = gc.convert_cartesian_to_transformed_cartesian(
            v, zeros, zeros, translate=0
        )
        magnitude = np.sqrt(x2**2 + y2**2 + z2**2)
        npt.assert_allclose(magnitude, [1.0], atol=1e-12)


class TestLambertEqualAreaCRS(unittest.TestCase):
    """Tests for get_lambert_equal_area_crs."""

    def test_crs_centered_on_polygon(self):
        """CRS should be LAEA centered on polygon centroid."""
        poly = box(-48, -24, -46, -22)
        crs = get_lambert_equal_area_crs(poly)
        self.assertIsNotNone(crs)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            crs_str = crs.to_proj4()
        self.assertIn("+proj=laea", crs_str)

    def test_crs_contains_centroid_coords(self):
        """CRS proj4 should contain lat_0 and lon_0 near centroid."""
        poly = box(10, 40, 20, 50)
        crs = get_lambert_equal_area_crs(poly)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            crs_str = crs.to_proj4()
        self.assertIn("lat_0=45", crs_str)
        self.assertIn("lon_0=15", crs_str)


class TestShrinkPolygon(unittest.TestCase):
    """Tests for polygon shrinking functions."""

    def test_shrink_reduces_area(self):
        """Shrinking a polygon should produce a smaller polygon."""
        poly = box(-50, -25, -40, -15)  # ~10°×10° box
        shrunk = shrink_country_polygon_by_km(poly, 50)  # 50 km inward
        self.assertLess(shrunk.area, poly.area)
        self.assertTrue(shrunk.is_valid)
        self.assertFalse(shrunk.is_empty)

    def test_shrink_polygon_still_contained(self):
        """Shrunk polygon should be contained within original."""
        poly = box(-50, -25, -40, -15)
        shrunk = shrink_country_polygon_by_km(poly, 10)
        # The shrunk polygon should be within the original (approximately)
        self.assertTrue(poly.contains(shrunk) or poly.buffer(0.1).contains(shrunk))

    def test_shrink_countries_by_km(self):
        """Shrinking a list of polygons should produce valid results."""
        polys = [
            box(-50, -25, -40, -15),
            MultiPolygon([box(10, 40, 20, 50), box(25, 40, 35, 50)]),
        ]
        result = shrink_countries_by_km(polys, 10)
        self.assertTrue(len(result) > 0)
        for p in result:
            self.assertTrue(p.is_valid)
            self.assertFalse(p.is_empty)


class TestGenerateGrid(unittest.TestCase):
    """Tests for hexagonal grid generation."""

    def test_grid_in_polygon_points_inside(self):
        """All generated grid points should be inside the polygon."""
        poly = box(-48, -24, -46, -22)  # ~2°×2° box
        result = generate_grid_in_polygon(poly, hexagon_radius=50000)  # 50km
        self.assertEqual(result.shape[0], 2)
        n_points = result.shape[1]
        self.assertGreater(n_points, 0)

        # Check all points are inside the polygon (with tiny buffer for floating-point)
        buffered = poly.buffer(0.01)
        for i in range(n_points):
            pt = Point(result[0, i], result[1, i])
            self.assertTrue(
                buffered.contains(pt),
                f"Point ({result[0, i]}, {result[1, i]}) outside polygon",
            )

    def test_grid_point_count_scales_with_radius(self):
        """Smaller hexagons should produce more grid points."""
        poly = box(-48, -24, -46, -22)
        result_large = generate_grid_in_polygon(poly, hexagon_radius=100000)
        result_small = generate_grid_in_polygon(poly, hexagon_radius=50000)
        self.assertGreater(result_small.shape[1], result_large.shape[1])

    def test_grid_negative_radius_raises(self):
        """Negative hexagon radius should raise ValueError."""
        poly = box(-48, -24, -46, -22)
        with self.assertRaises(ValueError):
            generate_grid_in_polygon(poly, hexagon_radius=-1000)

    def test_grid_in_multipolygon(self):
        """Grid in MultiPolygon should produce points in all sub-polygons."""
        mp = MultiPolygon([box(-50, -25, -48, -23), box(-45, -20, -43, -18)])
        result = generate_grid_in_multipolygon(mp, km=50000)
        self.assertEqual(result.shape[0], 2)
        self.assertGreater(result.shape[1], 0)

    def test_grid_with_rotation(self):
        """Grid with rotation should still produce valid points."""
        poly = box(-48, -24, -46, -22)
        result = generate_grid_in_polygon(
            poly, hexagon_radius=50000, rotation_deg=45.0
        )
        self.assertGreater(result.shape[1], 0)

    def test_grid_with_random_transform(self):
        """Grid with random transform (via multipolygon) should work."""
        poly = box(-48, -24, -46, -22)
        rng = np.random.RandomState(42)
        result = generate_grid_in_multipolygon(
            poly, km=50000, random_transform_on_grid=True, rng=rng
        )
        self.assertGreater(result.shape[1], 0)


if __name__ == "__main__":
    unittest.main()
