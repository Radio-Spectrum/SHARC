"""P.452 radio-climatic zones derived from land cover and the DEM."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from sharc.propagation.real_terrain.zones import A1, A2, B, build_zone_raster, zones_from_land_cover

CELL = (1000.0, 1000.0)          # 1 km cells: 100 x 100 km


def _coast(cols_water=20, size=100):
    """Water on the west (columns < cols_water), land on the east."""
    land = np.full((size, size), 10, dtype=np.uint8)
    land[:, :cols_water] = 80
    return land


class ZonesTest(unittest.TestCase):
    def test_sea_coast_and_inland(self):
        """Large water is B, land within 50 km of it is A1, further land is A2."""
        z = zones_from_land_cover(_coast(), CELL, min_sea_km2=100.0)
        self.assertTrue((z[:, :20] == B).all())
        self.assertTrue((z[:, 20:70] == A1).all())          # 1..50 km from the shore
        self.assertTrue((z[:, 71:] == A2).all())

    def test_high_land_near_the_coast_is_inland(self):
        """P.452 coastal land stops above 100 m."""
        dem = np.full((100, 100), 20.0)
        dem[:, 30:] = 300.0
        z = zones_from_land_cover(_coast(), CELL, dem, min_sea_km2=100.0)
        self.assertTrue((z[:, 20:30] == A1).all())
        self.assertTrue((z[:, 30:] == A2).all())

    def test_small_lake_is_land(self):
        """A lake far below the sea threshold, away from the border, does not create zone B or A1."""
        land = np.full((100, 100), 10, dtype=np.uint8)
        land[40:45, 40:45] = 80                              # 25 km2
        z = zones_from_land_cover(land, CELL)
        self.assertTrue((z == A2).all())

    def test_big_inland_water_body_is_b(self):
        land = np.full((200, 200), 10, dtype=np.uint8)
        land[50:150, 50:150] = 80                            # 10 000 km2 >= 7 800
        z = zones_from_land_cover(land, CELL)
        self.assertTrue((z[50:150, 50:150] == B).all())
        self.assertEqual(z[100, 140 + 5], B)
        self.assertEqual(z[100, 155], A1)                    # 5 km from the shore

    def test_no_water_is_all_inland(self):
        z = zones_from_land_cover(np.full((30, 30), 50, dtype=np.uint8), CELL)
        self.assertTrue((z == A2).all())

    def test_raster_round_trip_keeps_the_grid(self):
        """The zone GeoTIFF has the clutter grid; the DEM is resampled onto it."""
        tmp = Path(tempfile.mkdtemp())
        tr = from_origin(-40.0, -3.0, 0.009, 0.009)          # about 1 km cells near the equator
        kw = dict(driver="GTiff", height=100, width=100, count=1, crs="EPSG:4326", transform=tr)
        with rasterio.open(tmp / "c.tif", "w", dtype="uint8", **kw) as ds:
            ds.write(_coast(), 1)
        with rasterio.open(tmp / "t.tif", "w", dtype="float32", **kw) as ds:
            ds.write(np.full((100, 100), 10.0, dtype=np.float32), 1)
        out = build_zone_raster(str(tmp / "c.tif"), str(tmp / "z.tif"), str(tmp / "t.tif"), min_sea_km2=100.0)
        with rasterio.open(out) as z, rasterio.open(tmp / "c.tif") as c:
            self.assertEqual((z.width, z.height, z.transform), (c.width, c.height, c.transform))
            arr = z.read(1)
        self.assertEqual(set(np.unique(arr)), {A1, A2, B})
        self.assertTrue((arr[:, :20] == B).all())
        self.assertTrue((arr[:, 25:60] == A1).all())


if __name__ == "__main__":
    unittest.main()
