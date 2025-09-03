import unittest
import numpy as np
import numpy.testing as npt
import shapely as shp
import shapely.vectorized
from pathlib import Path

from sharc.support.sharc_geom import generate_grid_in_multipolygon
from sharc.support.sharc_utils import load_gdf
from sharc.satellite.utils.sat_utils import haversine


class TestSharcGeom(unittest.TestCase):
    """Unit tests for geometric utilities in SHARC (e.g., grid generation in polygons)."""

    def setUp(self):
        """Set up test fixtures for SHARC geometry tests."""
        root = (Path(__file__) / ".." / "..").resolve()
        self.countries_shapefile = root / "sharc" / "data" / \
            "countries" / "ne_110m_admin_0_countries.shp"

    def test_generate_grid(self):
        """Test the generate_grid_in_multipolygon function."""
        # approx a square
        # good only for small (lon, lat) values
        rng = np.random.RandomState(seed=0xCAFEBABE)
        mx = 0.001
        border = np.linspace(-mx / 2, mx / 2, 100)
        poly = shp.Polygon(
            [(-mx / 2, x) for x in border] +
            [(x, mx / 2) for x in border] +
            [(mx / 2, x) for x in border[::-1]] +
            [(x, -mx / 2) for x in border[::-1]]
        )
        # when passing too large values, the grid will have no points
        grid = generate_grid_in_multipolygon(
            poly, 1.01 * mx * 111e3 * 2 / np.sqrt(3))
        self.assertEqual(len(grid[0]), 0)

        # doing some packing inside the square
        # based on
        # hx A = 3 * sqrt(3) * r**2 / 2
        # N_max = hx A / pol A
        pol_A = mx * mx * 111e3 * 111e3
        for hx_r in np.arange(100, 12801, 5e2):
            hx_A = 3 * np.sqrt(3) * hx_r**2 / 2
            grid = generate_grid_in_multipolygon(poly, hx_r, True, rng)
            npt.assert_allclose(len(grid[0]), pol_A / hx_A, rtol=0.05, atol=10)
            lons, lats = grid
            self.assertTrue(
                shp.vectorized.contains(poly, lons, lats).all()
            )

        gdf = load_gdf(
            self.countries_shapefile,
            {"NAME": ["Brazil", "Chile"]}
        )
        poly = gdf[gdf["NAME"] == "Brazil"]["geometry"].values[0]

        # 10km hexagon radius
        hx_r = 10e3
        grid = generate_grid_in_multipolygon(poly, hx_r, True, rng)
        pol_A = 851e4 * 1e6
        hx_A = 3 * np.sqrt(3) * hx_r**2 / 2

        br_grid_len = len(grid[0])
        npt.assert_allclose(br_grid_len, pol_A / hx_A, rtol=0.007, atol=190)
        lons, lats = grid
        self.assertTrue(
            shp.vectorized.contains(poly, lons, lats).all()
        )

        poly = gdf[gdf["NAME"] == "Chile"]["geometry"].values[0]

        grid = generate_grid_in_multipolygon(poly, hx_r, True, rng)
        pol_A = 756626 * 1e6
        hx_A = 3 * np.sqrt(3) * hx_r ** 2 / 2

        # NOTE: as expected, with "thin" countries, lamberts equal area projection
        # causes noticeable distortion and differing results...
        cl_grid_len = len(grid[0])
        npt.assert_allclose(cl_grid_len, pol_A / hx_A, rtol=0.08, atol=230)
        lons, lats = grid
        self.assertTrue(
            shp.vectorized.contains(poly, lons, lats).all()
        )

        # generating grid for both Chile and Brazil at the same time
        poly = shp.ops.unary_union(gdf["geometry"].values)
        grid = generate_grid_in_multipolygon(poly, hx_r, True, rng)

        npt.assert_allclose(len(grid[0]), cl_grid_len + br_grid_len, rtol=0.0011)
        lons, lats = grid
        self.assertTrue(
            shp.vectorized.contains(poly, lons, lats).all()
        )

        from scipy.spatial import cKDTree

        lons, lats = grid
        pts = np.column_stack([lons, lats])  # shape (N, 2)
        tree = cKDTree(pts)
        dists, idxs = tree.query(pts, k=2)
        # idxs[:,0] are the points themselves
        # idxs[:,1] are the nearest neighbor
        near_idxs = idxs[:, 1]
        nn_dists = haversine(lons, lats, lons[near_idxs], lats[near_idxs])

        expected_dist = np.sqrt((np.sqrt(3) / 2 * hx_r)**2 + (3 / 2 * hx_r)**2)
        npt.assert_allclose(nn_dists, expected_dist, rtol=0.02)


if __name__ == '__main__':
    unittest.main()
