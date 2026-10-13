# -*- coding: utf-8 -*-
"""P.452 over real terrain profiles and the losses precomputed per database BS."""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import numpy.testing as npt
import rasterio
from rasterio.transform import from_origin

from sharc.parameters.database.parameters_database import ParametersDatabase
from sharc.parameters.parameters_p452 import ParametersP452
from sharc.propagation.propagation_clear_air_452 import PropagationClearAir

# DEM: 0.2 deg x 0.2 deg at 0.001 deg; 50 m of ground with a 250 m ridge
# along the meridian -38.50 (west of it the BS on the far side).
LON0, LAT0, STEP, N_PIX = -38.60, -3.70, 0.001, 200
REF = (-3.80, -38.45)                       # victim, east of the ridge
SITES = [
    # latitude, longitude, azimute, altura
    (-3.80, -38.56, 90.0, 30.0),            # behind the ridge
    (-3.80, -38.47, 270.0, 30.0),           # same side as the victim
]


def p452_params() -> ParametersP452:
    """P.452 parameters for the tests (no clutter loss, fixed time percentage)."""
    params = ParametersP452()
    params.percentage_p = 2.0
    params.clutter_loss = False
    params.Hte = 30.0
    params.Hre = 15.0
    params.tx_lat = -3.8
    params.rx_lat = -3.8
    return params


def loss(params, distance_km, frequency_ghz=3.5):
    """P.452 loss of one link."""
    prop = PropagationClearAir(np.random.RandomState(1), params)
    return float(np.ravel(prop.get_loss(
        np.array([distance_km]), np.array([frequency_ghz]), np.array([False]),
        np.array([0.0]), np.array([0.0]), np.array([0.0]),
    ))[0])


class P452ProfileTest(unittest.TestCase):
    """PropagationClearAir with a terrain profile on its parameters."""

    def setUp(self):
        """A 20 km link and its flat profile."""
        self.distance = 20.0
        self.d = np.linspace(0, self.distance, 101)

    def test_flat_profile_matches_default(self):
        """An explicit flat profile gives the loss of the default flat path."""
        params = p452_params()
        flat = loss(params, self.distance)
        params.terrain_d = self.d
        params.terrain_h = np.zeros_like(self.d)
        self.assertAlmostEqual(loss(params, self.distance), flat, places=6)

    def test_ridge_and_clutter_add_loss(self):
        """A ridge between the terminals, and clutter on it, add diffraction loss."""
        params = p452_params()
        params.terrain_d = self.d
        params.terrain_h = np.zeros_like(self.d)
        flat = loss(params, self.distance)
        params.terrain_h = 200.0 * np.exp(-((self.d - 10.0) / 1.0) ** 2)
        ridge = loss(params, self.distance)
        self.assertGreater(ridge, flat + 10.0)
        params.terrain_g = params.terrain_h + np.where((self.d > 0.05) & (self.d < 19.95), 15.0, 0.0)
        self.assertGreater(loss(params, self.distance), ridge)

    def test_zone_helpers(self):
        """Fraction over sea and distances to the coast from a zone profile."""
        d = np.arange(5.0)
        zone = np.array([2, 2, 3, 3, 2])
        self.assertAlmostEqual(PropagationClearAir.path_fraction_v2(d, zone, 3), 0.5)
        self.assertEqual(PropagationClearAir.coast_distances(d, zone), (1.5, 0.5))
        self.assertEqual(PropagationClearAir.coast_distances(d, np.full(5, 2)), (4.0, 4.0))
        # all over sea: omega = 1 changes the loss
        params = p452_params()
        params.terrain_d = np.linspace(0, 20.0, 101)
        params.terrain_h = np.zeros(101)
        land = loss(params, 20.0)
        params.terrain_zone = np.full(101, 3.0)
        self.assertNotAlmostEqual(loss(params, 20.0), land, places=3)


class DatabaseTerrainTest(unittest.TestCase):
    """compute_terrain over a DEM read as a grid raster."""

    def setUp(self):
        """Write the DEM and the database."""
        self.tmp = Path(tempfile.mkdtemp())
        lons = LON0 + (np.arange(N_PIX) + 0.5) * STEP
        dem = 50.0 + 250.0 * np.exp(-((lons + 38.50) / 0.004) ** 2)
        dem = np.tile(dem, (N_PIX, 1)).astype(np.float32)
        self.dem = self.tmp / "dem.tif"
        with rasterio.open(
            self.dem, "w", driver="GTiff", height=N_PIX, width=N_PIX, count=1, dtype="float32",
            crs="EPSG:4326", transform=from_origin(LON0, LAT0, STEP, STEP),
        ) as ds:
            ds.write(dem, 1)
        csv = self.tmp / "db.csv"
        csv.write_text("latitude,longitude,azimute,altura\n"
                       + "".join(f"{a},{b},{c},{h}\n" for a, b, c, h in SITES))
        self.database = ParametersDatabase(from_db_topology_countries=True, use_real_terrain=True)
        self.database.load_database(csv)
        self.params = p452_params()
        self.params.profile_source = "grid"
        self.params.profile_raster = str(self.dem)
        self.params.profile_step_m = 100.0

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def test_ground_altitudes(self):
        """Every site and the reference point get the terrain altitude."""
        self.database.compute_terrain(*REF, self.params)
        npt.assert_allclose(self.database.data_full["cota_terreno"], 50.0, atol=0.5)
        self.assertAlmostEqual(self.database.reference_ground, 50.0, delta=0.5)
        self.assertNotIn("path_loss_p452", self.database.data_full.columns)
        npt.assert_allclose(self.database.data_full["distancekm_to_ref"], [12.2, 2.2], rtol=0.01)

    def test_losses(self):
        """Losses per BS: the BS is the transmitter, the ridge adds loss."""
        self.database.compute_terrain(*REF, self.params, frequency_ghz=3.5)
        losses = self.database.data_full["path_loss_p452"].to_numpy()
        profiles = self.database.terrain_profiles(*REF, self.params)

        # same as P.452 on the profile reversed to start at the BS
        for i, prof in enumerate(profiles):
            params = copy.copy(self.params)
            params.terrain_d = prof["dist_km"][-1] - prof["dist_km"][::-1]
            params.terrain_h = prof["height_m"][::-1]
            self.assertAlmostEqual(losses[i], loss(params, prof["dist_km"][-1]), places=6)

        # the BS behind the ridge loses more than free space over the same distance
        flat = copy.copy(self.params)
        flat.terrain_d = np.linspace(0, profiles[0]["dist_km"][-1], 101)
        flat.terrain_h = np.full(101, 50.0)
        self.assertGreater(losses[0], loss(flat, profiles[0]["dist_km"][-1]) + 10.0)

        # a taller BS antenna clears more of the ridge
        self.params.hte_from_db = True
        self.database.data_full.loc[0, "altura"] = 200.0
        self.database.compute_terrain(*REF, self.params, frequency_ghz=3.5)
        self.assertLess(self.database.data_full["path_loss_p452"].iloc[0], losses[0])

    def write_raster(self, name, values, dtype):
        """Write a raster on the DEM grid."""
        path = self.tmp / name
        with rasterio.open(
            path, "w", driver="GTiff", height=N_PIX, width=N_PIX, count=1, dtype=dtype,
            crs="EPSG:4326", transform=from_origin(LON0, LAT0, STEP, STEP),
        ) as ds:
            ds.write(values.astype(dtype), 1)
        return str(path)

    def test_clutter_and_zones(self):
        """Land-cover heights add loss; a sea zone sets Dct/Dcr and the profile zones."""
        self.database.compute_terrain(*REF, self.params, frequency_ghz=3.5)
        bare = self.database.data_full["path_loss_p452"].to_numpy()

        # CelPlan class 1 (30 m of clutter) everywhere
        self.params.clutter_raster = self.write_raster("lc.tif", np.ones((N_PIX, N_PIX)), "uint8")
        profiles = self.database.terrain_profiles(*REF, self.params)
        prof = profiles[0]
        inner = (prof["dist_km"] >= 0.05) & (prof["dist_km"] <= prof["dist_km"][-1] - 0.05)
        npt.assert_allclose(prof["clutter_m"][inner], prof["height_m"][inner] + 30.0)
        npt.assert_allclose(prof["clutter_m"][~inner], prof["height_m"][~inner])
        self.database.compute_terrain(*REF, self.params, frequency_ghz=3.5)
        with_clutter = self.database.data_full["path_loss_p452"].to_numpy()
        self.assertTrue(np.all(with_clutter >= bare - 1e-9))
        self.assertGreater(with_clutter[1], bare[1])

        # sea (zone 3) between -38.465 and -38.455, inland elsewhere
        lons = LON0 + (np.arange(N_PIX) + 0.5) * STEP
        zones = np.tile(np.where(np.abs(lons + 38.46) < 0.005, 3, 2), (N_PIX, 1))
        self.params.clutter_raster = ""
        self.params.zone_raster = self.write_raster("zones.tif", zones, "uint8")
        prof = self.database.terrain_profiles(*REF, self.params)[1]
        self.assertTrue(np.any(prof["zone"] == 3))
        d = prof["dist_km"][-1] - prof["dist_km"][::-1]
        dct, dcr = PropagationClearAir.coast_distances(d, prof["zone"][::-1])
        self.assertGreater(dct, 0.0)
        self.assertGreater(dcr, 0.0)
        self.assertLess(dct + dcr, d[-1])
        self.database.compute_terrain(*REF, self.params, frequency_ghz=3.5)
        self.assertTrue(np.all(np.isfinite(self.database.data_full["path_loss_p452"])))

    def test_missing_terrain(self):
        """A profile leaving the raster is reported."""
        self.database.data_full.loc[0, "longitude"] = -39.0
        with self.assertRaises(ValueError):
            self.database.compute_terrain(*REF, self.params)

    def test_validation(self):
        """Profile options are checked."""
        params = p452_params()
        params.profile_source = "grid"
        with self.assertRaises(ValueError):
            params.validate("param_p452")
        params.profile_source = "dem"
        with self.assertRaises(ValueError):
            params.validate("param_p452")
        params = p452_params()
        params.is_terrain = True
        with self.assertRaises(NotImplementedError):
            params.validate("param_p452")
        params.override_from_db = True
        params.validate("param_p452")


if __name__ == "__main__":
    unittest.main()
