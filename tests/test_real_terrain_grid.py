# -*- coding: utf-8 -*-
"""Raster sampling of the real-terrain grid (GridRaster) and clutter height tables."""
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import numpy.testing as npt
import rasterio
from rasterio.transform import from_origin

from sharc.propagation.real_terrain.grade_raster import GridRaster, height_lut

LON0, LAT0, STEP = -38.60, -3.70, 0.01   # upper-left corner and pixel size [deg]


def pixel_centre(row, col):
    """Latitude and longitude of a pixel centre."""
    return LAT0 - (row + 0.5) * STEP, LON0 + (col + 0.5) * STEP


class GridRasterTest(unittest.TestCase):
    """GridRaster on a 4 x 5 raster whose value is 10 * row + col."""

    def setUp(self):
        """Write the raster, with one nodata pixel at (3, 4)."""
        self.tmp = Path(tempfile.mkdtemp())
        data = (10 * np.arange(4)[:, None] + np.arange(5)[None, :]).astype(np.float32)
        data[3, 4] = -9999
        self.path = self.tmp / "grid.tif"
        with rasterio.open(
            self.path, "w", driver="GTiff", height=4, width=5, count=1, dtype="float32",
            crs="EPSG:4326", transform=from_origin(LON0, LAT0, STEP, STEP), nodata=-9999,
        ) as ds:
            ds.write(data, 1)
        self.grid = GridRaster(self.path)

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def test_pixel_centres(self):
        """At pixel centres both methods return the pixel value."""
        lat, lon = pixel_centre(np.array([0, 1, 2]), np.array([0, 3, 1]))
        npt.assert_allclose(self.grid.sample(lat, lon, "bilinear"), [0, 13, 21])
        npt.assert_array_equal(self.grid.sample(lat, lon, "nearest"), [0, 13, 21])

    def test_bilinear_between_centres(self):
        """Halfway between pixel centres the bilinear value is the mean."""
        lat0, lon0 = pixel_centre(1, 1)
        lat1, lon1 = pixel_centre(2, 2)
        npt.assert_allclose(
            self.grid.sample([(lat0 + lat1) / 2], [(lon0 + lon1) / 2], "bilinear"),
            [(11 + 12 + 21 + 22) / 4],
        )

    def test_outside_and_nodata(self):
        """Outside the raster or on nodata: NaN (bilinear) or fill (nearest)."""
        lat, lon = pixel_centre(np.array([-3, 3]), np.array([0, 4]))
        self.assertTrue(np.all(np.isnan(self.grid.sample(lat, lon, "bilinear"))))
        npt.assert_array_equal(self.grid.sample(lat, lon, "nearest", fill=7), [7, 7])
        with self.assertRaises(ValueError):
            self.grid.sample(lat, lon, "cubic")

    def test_missing_file(self):
        """A missing raster is reported."""
        with self.assertRaises(FileNotFoundError):
            GridRaster(self.tmp / "missing.tif")


class HeightTableTest(unittest.TestCase):
    """Clutter height lookup tables."""

    def test_tables(self):
        """Known classes get their height, others get zero."""
        celplan = height_lut("celplan")
        self.assertEqual(celplan[1], 30)
        self.assertEqual(celplan[19], 45)
        self.assertEqual(celplan[200], 0)
        self.assertEqual(height_lut("p452_tab3")[4], 10)
        worldcover = height_lut("worldcover")
        self.assertEqual(worldcover[50], 15)        # built-up
        self.assertEqual(worldcover[10], 15)        # tree cover
        self.assertEqual(worldcover[80], 0)         # water
        self.assertEqual(worldcover[30], 0)         # grassland
        with self.assertRaises(ValueError):
            height_lut("unknown")


if __name__ == "__main__":
    unittest.main()
