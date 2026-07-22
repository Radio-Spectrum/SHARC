# -*- coding: utf-8 -*-
"""
Tests for sharc.topology.topology_countries module (TopologyCountries).

Tests the static helper methods with synthetic/analytical inputs.
Integration tests (calculate_coordinates) require shapefiles to be present
in sharc/topology/map/.
"""

import unittest
import numpy as np
import numpy.testing as npt
from shapely.geometry import box, Polygon, MultiPolygon

from sharc.topology.topology_countries import TopologyCountries, _WGS84_A, _WGS84_E2, _WGS84_F
from sharc.parameters.imt.parameters_countries_imt import ParametersCountries
from sharc.support.sharc_geom import CoordinateSystem


class TestLlaToEcef(unittest.TestCase):
    """Tests for TopologyCountries._lla_to_ecef (static)."""

    def test_equator_greenwich(self):
        """(0°, 0°, 0m) should give X ≈ semi-major-axis, Y ≈ 0, Z ≈ 0."""
        X, Y, Z = TopologyCountries._lla_to_ecef(0.0, 0.0, 0.0)
        npt.assert_allclose(X, _WGS84_A, rtol=1e-8)
        npt.assert_allclose(Y, 0.0, atol=1e-4)
        npt.assert_allclose(Z, 0.0, atol=1e-4)

    def test_equator_90_east(self):
        """(0°, 90°, 0m) should give X ≈ 0, Y ≈ semi-major-axis, Z ≈ 0."""
        X, Y, Z = TopologyCountries._lla_to_ecef(0.0, 90.0, 0.0)
        npt.assert_allclose(X, 0.0, atol=1e-4)
        npt.assert_allclose(Y, _WGS84_A, rtol=1e-8)
        npt.assert_allclose(Z, 0.0, atol=1e-4)

    def test_north_pole(self):
        """(90°, 0°, 0m) should give X ≈ 0, Y ≈ 0, Z ≈ semi-minor-axis."""
        X, Y, Z = TopologyCountries._lla_to_ecef(90.0, 0.0, 0.0)
        b = _WGS84_A * (1.0 - _WGS84_F)
        npt.assert_allclose(X, 0.0, atol=1e-4)
        npt.assert_allclose(Y, 0.0, atol=1e-4)
        npt.assert_allclose(Z, b, rtol=1e-6)

    def test_south_pole(self):
        """(−90°, 0°, 0m) should give Z ≈ −semi-minor-axis."""
        X, Y, Z = TopologyCountries._lla_to_ecef(-90.0, 0.0, 0.0)
        b = _WGS84_A * (1.0 - _WGS84_F)
        npt.assert_allclose(Z, -b, rtol=1e-6)

    def test_with_height(self):
        """Height adds to the radial distance."""
        h = 1000.0  # 1 km
        X0, Y0, Z0 = TopologyCountries._lla_to_ecef(0.0, 0.0, 0.0)
        Xh, Yh, Zh = TopologyCountries._lla_to_ecef(0.0, 0.0, h)
        self.assertGreater(float(Xh), float(X0))
        npt.assert_allclose(float(Xh) - float(X0), h, rtol=1e-3)

    def test_vectorized(self):
        """Array inputs produce array outputs with correct shape."""
        lat = np.array([0.0, 45.0, -23.5])
        lon = np.array([0.0, 90.0, -46.6])
        h = np.array([0.0, 100.0, 800.0])
        X, Y, Z = TopologyCountries._lla_to_ecef(lat, lon, h)
        self.assertEqual(X.shape, (3,))
        self.assertEqual(Y.shape, (3,))
        self.assertEqual(Z.shape, (3,))

    def test_magnitude_is_earth_radius(self):
        """At sea level, |ECEF| should be close to Earth radius."""
        lat = np.array([0.0, 30.0, 60.0, -45.0])
        lon = np.array([0.0, 45.0, -120.0, 170.0])
        h = np.zeros(4)
        X, Y, Z = TopologyCountries._lla_to_ecef(lat, lon, h)
        mag = np.sqrt(X**2 + Y**2 + Z**2)
        for m in mag:
            self.assertAlmostEqual(m, _WGS84_A, delta=25000)  # within ~25km of semi-major


class TestGetDensityRange(unittest.TestCase):
    """Tests for TopologyCountries._get_density_range."""

    def _make_topology(self, dist_type=None, dist_density_min=None, dist_density_max=None):
        params = ParametersCountries(
            country_names=["Brazil"],
            dist_type=dist_type,
            dist_density_min=dist_density_min,
            dist_density_max=dist_density_max,
        )
        cs = CoordinateSystem()
        cs.set_reference(0, 0, 0)
        return TopologyCountries(params, cs)

    def test_urban(self):
        """dist_type='Urban' returns (1500, 10000)."""
        t = self._make_topology(dist_type="Urban")
        self.assertEqual(t._get_density_range(), (1500.0, 10000.0))

    def test_suburban(self):
        """dist_type='Suburban' returns (300, 1500)."""
        t = self._make_topology(dist_type="Suburban")
        self.assertEqual(t._get_density_range(), (300.0, 1500.0))

    def test_rural(self):
        """dist_type='Rural' returns (0, 300)."""
        t = self._make_topology(dist_type="Rural")
        self.assertEqual(t._get_density_range(), (0.0, 300.0))

    def test_none(self):
        """dist_type=None returns None."""
        t = self._make_topology()
        self.assertIsNone(t._get_density_range())

    def test_explicit_density_range(self):
        """Explicit min/max overrides dist_type."""
        t = self._make_topology(dist_density_min=100, dist_density_max=500)
        self.assertEqual(t._get_density_range(), (100.0, 500.0))

    def test_invalid_density_range(self):
        """dist_density_max <= dist_density_min should raise ValueError."""
        t = self._make_topology(dist_density_min=500, dist_density_max=100)
        with self.assertRaises(ValueError):
            t._get_density_range()


class TestRowAreasKm2(unittest.TestCase):
    """Tests for TopologyCountries._row_areas_km2 (static)."""

    def test_method_none(self):
        """method='none' returns array of ones."""
        lats = np.array([0, 30, 60])
        result = TopologyCountries._row_areas_km2(lats, 1.0, 1.0, "none")
        npt.assert_allclose(result, [1.0, 1.0, 1.0])

    def test_equator_area_larger(self):
        """Pixel area at equator should be larger than at 60°."""
        lats = np.array([0.0, 60.0])
        result = TopologyCountries._row_areas_km2(lats, 1.0, 1.0, "spherical")
        self.assertGreater(result[0], result[1])

    def test_coslat_equator(self):
        """coslat method at equator: area ≈ 111.32² ≈ 12392."""
        lats = np.array([0.0])
        result = TopologyCountries._row_areas_km2(lats, 1.0, 1.0, "coslat")
        npt.assert_allclose(result, [111.32**2], rtol=0.01)

    def test_spherical_positive(self):
        """Spherical method should always produce positive areas."""
        lats = np.linspace(-60, 60, 20)
        result = TopologyCountries._row_areas_km2(lats, 0.5, 0.5, "spherical")
        self.assertTrue(np.all(result > 0))


class TestIndexToDensity(unittest.TestCase):
    """Tests for TopologyCountries._index_to_density (static)."""

    def test_log_mapping_midpoint(self):
        """Log mapping: index 127 → density near geometric mean of vmin/vmax."""
        idx = np.array([127])
        result = TopologyCountries._index_to_density(idx, "log", 1.0, 1e4)
        # bin midpoint: x = (127+0.5)/256 ≈ 0.498
        expected = 10.0**(0 + 0.498 * 4)  # 10^1.992 ≈ 98.1
        npt.assert_allclose(result, [expected], rtol=0.05)

    def test_linear_mapping(self):
        """Linear mapping: index 0 → near vmin, index 255 → near vmax."""
        idx = np.array([0, 255])
        result = TopologyCountries._index_to_density(idx, "linear", 0.0, 1000.0)
        # bin midpoints: (0.5/256)*1000 and (255.5/256)*1000
        npt.assert_allclose(result[0], 0.5 / 256 * 1000, rtol=0.01)
        npt.assert_allclose(result[1], 255.5 / 256 * 1000, rtol=0.01)

    def test_log_invalid_vmin_raises(self):
        """vmin <= 0 for log mode should raise ValueError."""
        with self.assertRaises(ValueError):
            TopologyCountries._index_to_density(np.array([128]), "log", 0.0, 100.0)


class TestRandomPointsInPolygon(unittest.TestCase):
    """Tests for TopologyCountries._random_points_in_polygon."""

    def setUp(self):
        """Create a TopologyCountries instance for Brazil."""
        params = ParametersCountries(country_names=["Brazil"])
        cs = CoordinateSystem()
        cs.set_reference(0, 0, 0)
        self.topo = TopologyCountries(params, cs, np.random.RandomState(42))

    def test_correct_count(self):
        """Should generate exactly n points."""
        poly = box(-50, -25, -40, -15)
        lons, lats = self.topo._random_points_in_polygon(poly, 100)
        self.assertEqual(len(lons), 100)
        self.assertEqual(len(lats), 100)

    def test_points_inside_polygon(self):
        """All generated points should be inside the polygon."""
        poly = box(-50, -25, -40, -15)
        lons, lats = self.topo._random_points_in_polygon(poly, 200)
        from shapely.geometry import Point
        buffered = poly.buffer(0.01)  # tiny buffer for floating-point
        for lon, lat in zip(lons, lats):
            self.assertTrue(
                buffered.contains(Point(lon, lat)),
                f"Point ({lon}, {lat}) outside polygon",
            )

    def test_multipolygon(self):
        """Should work with MultiPolygon input."""
        mp = MultiPolygon([box(-50, -25, -45, -20), box(-40, -15, -35, -10)])
        lons, lats = self.topo._random_points_in_polygon(mp, 50)
        self.assertEqual(len(lons), 50)

    def test_reproducibility(self):
        """Same seed should produce same points."""
        poly = box(-50, -25, -40, -15)
        params = ParametersCountries(country_names=["Brazil"])
        cs = CoordinateSystem()
        cs.set_reference(0, 0, 0)
        t1 = TopologyCountries(params, cs, np.random.RandomState(42))
        t2 = TopologyCountries(params, cs, np.random.RandomState(42))
        lons1, lats1 = t1._random_points_in_polygon(poly, 20)
        lons2, lats2 = t2._random_points_in_polygon(poly, 20)
        npt.assert_array_equal(lons1, lons2)
        npt.assert_array_equal(lats1, lats2)


class TestTransformUeXyz(unittest.TestCase):
    """Tests for TopologyCountries.transform_ue_xyz."""

    def test_zero_offset(self):
        """Zero local offset should return BS position."""
        params = ParametersCountries(country_names=["Brazil"])
        cs = CoordinateSystem()
        cs.set_reference(0, 0, 0)
        topo = TopologyCountries(params, cs)
        topo.x = np.array([1000.0, 2000.0])
        topo.y = np.array([3000.0, 4000.0])
        topo.z = np.array([5000.0, 6000.0])

        x, y, z = topo.transform_ue_xyz(0, 0.0, 0.0, 0.0)
        self.assertEqual(x, 1000.0)
        self.assertEqual(y, 3000.0)
        self.assertEqual(z, 5000.0)

    def test_nonzero_offset(self):
        """Non-zero offset should be added to BS position."""
        params = ParametersCountries(country_names=["Brazil"])
        cs = CoordinateSystem()
        cs.set_reference(0, 0, 0)
        topo = TopologyCountries(params, cs)
        topo.x = np.array([1000.0])
        topo.y = np.array([2000.0])
        topo.z = np.array([3000.0])

        x, y, z = topo.transform_ue_xyz(0, 10.0, 20.0, 30.0)
        self.assertEqual(x, 1010.0)
        self.assertEqual(y, 2020.0)
        self.assertEqual(z, 3030.0)


class TestResolveAsset(unittest.TestCase):
    """Tests for TopologyCountries._resolve_asset."""

    def test_absolute_path(self):
        """An absolute path should be returned unchanged."""
        from pathlib import Path
        p = Path("/tmp/test_file.shp")
        result = TopologyCountries._resolve_asset(p)
        self.assertEqual(result, p)

    def test_none_path(self):
        """A None path should resolve to None."""
        self.assertIsNone(TopologyCountries._resolve_asset(None))

    def test_relative_path(self):
        """A relative path should resolve to an existing absolute path."""
        from pathlib import Path
        rel_path = "sharc/topology/map/ne_110m_admin_0_countries.shp"
        result = TopologyCountries._resolve_asset(rel_path)
        self.assertTrue(result.is_absolute())
        self.assertTrue(result.exists())

    def test_relative_path_sharc_file_none(self):
        """A relative path should still resolve when sharc.__file__ is None."""
        from pathlib import Path
        import sharc
        from unittest.mock import patch

        rel_path = "sharc/topology/map/ne_110m_admin_0_countries.shp"
        with patch.object(sharc, "__file__", None):
            result = TopologyCountries._resolve_asset(rel_path)
            self.assertTrue(result.is_absolute())
            self.assertTrue(result.exists())


if __name__ == "__main__":
    unittest.main()
