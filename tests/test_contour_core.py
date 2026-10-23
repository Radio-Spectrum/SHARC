"""Generalized protection-contour core: geometry, ray search and the P.452 link, checked against the Ceara reference."""
import math
import os
import unittest

import numpy as np

from sharc.contour import geometry, search
from sharc.contour.region import Region
from sharc.contour.site import PRESETS, RasSite

# Reference data of the original Ceara tool (rays already computed by it). Set SHARC_CONTOUR_REF to the folder that
# holds `camp/` (parametros_usados.yaml + raios/*.npz) and `D/.../CE_*_50m.tif`; the checks are skipped without it.
REF = os.environ.get("SHARC_CONTOUR_REF", "")


class GeometryTest(unittest.TestCase):
    def test_azimuth_conventions_round_trip(self):
        az = np.array([0.0, 45.0, 90.0, 180.0, 270.0, 359.0])
        np.testing.assert_allclose(geometry.north_to_enu(geometry.enu_to_north(az)), az)
        self.assertAlmostEqual(float(geometry.enu_to_north(0.0)), 90.0)         # ENU east = 90 degrees from North

    def test_point_on_ray_is_at_the_requested_distance_and_direction(self):
        lat, lon = geometry.points_on_ray(-3.8735, -38.42216, 0.0, [1000.0, 5000.0])        # due east
        np.testing.assert_allclose(geometry.distance_m(-3.8735, -38.42216, lat, lon), [1000.0, 5000.0], atol=1e-3)
        self.assertTrue((lon > -38.42216).all() and np.allclose(lat, -3.8735, atol=2e-4))
        north = geometry.bearing_north(-3.8735, -38.42216, lat[-1], lon[-1])
        self.assertAlmostEqual(north, 90.0, places=1)

    def test_works_anywhere_on_earth(self):
        for lat0, lon0 in ((50.52, 6.88), (-33.0, 151.2), (0.0, 0.0)):                 # not only Brazil
            lat, lon = geometry.points_on_ray(lat0, lon0, 123.0, 20000.0)
            self.assertAlmostEqual(float(geometry.distance_m(lat0, lon0, lat, lon)[0]), 20000.0, places=2)

    def test_ray_azimuths(self):
        az = geometry.ray_azimuths(1.0)
        self.assertEqual((az.size, az[0], az[-1]), (360, 0.0, 359.0))
        self.assertEqual(geometry.ray_azimuths(0.5, 0.0, 90.0).size, 180)


class SearchTest(unittest.TestCase):
    def test_finds_the_boundary_of_a_monotonic_margin(self):
        d, marker, n = search.search_ray(lambda d: 3000.0 - d, d_start=10000.0, d_min=100.0, step=50.0, tol=1.0)
        self.assertEqual(marker, search.OK)
        self.assertAlmostEqual(d, 3000.0, delta=1.0)
        self.assertLess(n, 200)

    def test_nonmonotonic_margin_takes_the_farthest_violation(self):
        """A shadow near the station that meets the criterion must not hide a violation further out."""
        def margin(d):
            return 1.0 if (2000.0 <= d <= 4000.0 or d < 500.0) else -1.0
        d, marker, _ = search.search_ray(margin, 10000.0, 100.0, 50.0, 1.0)
        self.assertEqual(marker, search.OK)
        self.assertAlmostEqual(d, 4000.0, delta=51.0)

    def test_markers_at_the_two_ends(self):
        self.assertEqual(search.search_ray(lambda d: 1.0, 5000.0, 100.0, 50.0, 1.0)[1], search.NOT_MET_AT_END)
        d, marker, _ = search.search_ray(lambda d: -1.0, 5000.0, 100.0, 50.0, 1.0)
        self.assertEqual((d, marker), (100.0, search.MET_EVERYWHERE))
        self.assertEqual(search.search_ray(lambda d: -1.0, 50.0, 100.0, 50.0, 1.0), (100.0, search.MET_EVERYWHERE, 1))


class SiteTest(unittest.TestCase):
    def test_threshold_follows_the_noise_floor(self):
        site = RasSite("x", 0.0, 0.0, bandwidth_mhz=100.0, temperature_k=100.0)
        n_dbw = 10 * math.log10(1.380649e-23 * 100.0 * 100e6)
        self.assertAlmostEqual(site.threshold_dbw(-6.0), n_dbw - 6.0, places=9)
        self.assertGreater(site.with_(temperature_k=200.0).threshold_dbw(), site.threshold_dbw())

    def test_the_preset_is_a_value_not_a_global(self):
        self.assertEqual(PRESETS["ROEN"].frequency_mhz, 4895.0)
        self.assertEqual(PRESETS["ROEN"].with_(name="other").name, "other")
        self.assertIn("Eusebio", PRESETS["ROEN"].name)


class RegionTest(unittest.TestCase):
    def test_missing_file_is_reported_with_its_role(self):
        with self.assertRaisesRegex(FileNotFoundError, "Region.terrain"):
            Region("no_such_dem.tif").check()
        with self.assertRaises(ValueError):
            Region("").check()


@unittest.skipUnless(REF and os.path.isdir(os.path.join(REF, "camp")), "SHARC_CONTOUR_REF not set")
class CearaReferenceTest(unittest.TestCase):
    """The generalized link reproduces the losses the original tool stored in its rays."""

    @classmethod
    def setUpClass(cls):
        import yaml
        from sharc.contour.link import P452Link
        cls.camp = os.path.join(REF, "camp")
        y = yaml.safe_load(open(os.path.join(cls.camp, "parametros_usados.yaml"), encoding="utf-8"))
        base = os.path.join(REF, "D", "Simulacao Database - Restart", "topografia_morfologia_CE", "base_processada")
        region = Region(os.path.join(base, "CE_MDT_50m.tif"), os.path.join(base, "CE_morf_50m.tif"),
                        os.path.join(base, "CE_zonas_50m.tif"), "celplan", y["varredura"]["passo_m"])
        r, ras = y["raios"], y["ras"]
        site = RasSite("ROEN", r["lat"], r["lon"], r["altura_ras_m"], ras["diametro_m"], ras["eficiencia"],
                       ras["frequencia_mhz"], ras["banda_mhz"], ras["elevacao_graus"], ras["temperatura_k"])
        p452 = {k: v for k, v in y["propagacao"]["param_p452"].items()
                if k not in ("profile_source", "profile_raster", "profile_step_m", "clutter_raster", "clutter_heights",
                             "zone_raster")}
        cls.link = P452Link(site, region, p452, y["propagacao"]["frequencia_mhz"])
        cls.rays = sorted(f for f in os.listdir(os.path.join(cls.camp, "raios")) if f.endswith(".npz"))

    def test_ground_elevation_and_ray_points_match(self):
        ray = np.load(os.path.join(self.camp, "raios", self.rays[1]), allow_pickle=True)
        az = float(ray["az_enu"])
        lat, lon = geometry.points_on_ray(self.link.site.lat_deg, self.link.site.lon_deg, az, ray["d_m"])
        np.testing.assert_allclose(lat, ray["lat"], atol=1e-9)
        np.testing.assert_allclose(lon, ray["lon"], atol=1e-9)

    def test_p452_loss_matches_the_stored_losses(self):
        worst, count = 0.0, 0
        for name in self.rays[:: max(1, len(self.rays) // 6)]:
            ray = np.load(os.path.join(self.camp, "raios", name), allow_pickle=True)
            n = ray["d_m"].size
            for i in sorted({0, n // 4, n // 2, 3 * n // 4, n - 1}):
                loss, ground = self.link.loss_db(float(ray["lat"][i]), float(ray["lon"][i]), float(ray["altura_m"][i]))
                worst = max(worst, abs(loss - float(ray["perda_db"][i])))
                self.assertAlmostEqual(ground, float(ray["cota_bs_m"][i]), places=3)
                count += 1
        self.assertGreater(count, 20)
        self.assertLess(worst, 1e-6, f"worst loss difference {worst} dB over {count} points")


@unittest.skipUnless(REF and os.path.isdir(os.path.join(REF, "camp")), "SHARC_CONTOUR_REF not set")
class CearaBudgetReferenceTest(unittest.TestCase):
    """Directions, gains and margin of the generalized budget reproduce the original tool's stored rays."""

    @classmethod
    def setUpClass(cls):
        import yaml
        from sharc.contour.budget import Budget, ReferenceBs
        from sharc.contour.criterion import Criterion
        cls.camp = os.path.join(REF, "camp")
        y = yaml.safe_load(open(os.path.join(cls.camp, "parametros_usados.yaml"), encoding="utf-8"))
        r, ras, bs, crit = y["raios"], y["ras"], y["bs_referencia"], y["criterio"]
        a = bs["antena"]
        cls.site = RasSite("ROEN", r["lat"], r["lon"], r["altura_ras_m"], ras["diametro_m"], ras["eficiencia"],
                           ras["frequencia_mhz"], ras["banda_mhz"], ras["elevacao_graus"], ras["temperatura_k"],
                           ras["perda_polarizacao_db"], ras["blindagem_db"])
        cls.budget = Budget(
            cls.site,
            ReferenceBs(bs["frequencia_mhz"], bs["banda_por_operadora_mhz"], bs["espuria_por_operadora_dbm_mhz"],
                        bs["n_operadoras"], bs["downtilt_graus"], bs["perdas_db"], a["element_max_g"],
                        a["element_phi_3db"], a["element_theta_3db"], a["element_am"], a["element_sla_v"],
                        a["multiplication_factor"], a["ganho_minimo_dbi"]),
            Criterion(crit["caso"], 1.0, 1.0, crit["tempo_integracao_s"], crit["margem_rateio_db"]))
        cls.offs = bs["off_axis_graus"]
        cls.rays = sorted(f for f in os.listdir(os.path.join(cls.camp, "raios")) if f.endswith(".npz"))

    def test_the_threshold_and_power_are_the_ones_of_the_campaign(self):
        ray = np.load(os.path.join(self.camp, "raios", self.rays[1]), allow_pickle=True)
        # I = P - L + G_station + G_bs  and  margin = I - threshold, from the stored arrays of any point
        i0 = np.asarray(ray["i_dbm_0"]) - (np.asarray(ray["margem_db_0"]))
        self.assertAlmostEqual(float(i0[0]), self.budget.threshold_dbm, places=6)
        implied_power = (np.asarray(ray["i_dbm_0"]) + np.asarray(ray["perda_db"]) - np.asarray(ray["g_ras_dbi"])
                         - np.asarray(ray["g_bs_dbi_0"]))
        self.assertAlmostEqual(float(implied_power[0]), self.budget.power_dbm - self.budget.total_losses_db, places=6)

    def test_directions_gains_and_margin_match_the_stored_rays(self):
        worst = {"phi_r": 0, "theta_r": 0, "phi_b": 0, "theta_b": 0, "g_ras": 0, "g_bs": 0, "margin": 0}
        for name in self.rays[:: max(1, len(self.rays) // 8)]:
            ray = np.load(os.path.join(self.camp, "raios", name), allow_pickle=True)
            lat, lon, h, ground = ray["lat"], ray["lon"], ray["altura_m"], ray["cota_bs_m"]
            station_ground = float(ground[0] - 0)                      # replaced below by the profile ground of the site
            phi_r, theta_r, phi_b, theta_b = self.budget.directions(lat, lon, h, ground, self._station_ground())
            for key, mine, ref in (("phi_r", phi_r, "phi_r_graus"), ("theta_r", theta_r, "theta_r_graus"),
                                   ("phi_b", phi_b, "phi_b_graus"), ("theta_b", theta_b, "theta_b_graus")):
                worst[key] = max(worst[key], float(np.max(np.abs(mine - ray[ref]))))
            g_ras, psi = self.budget.station_gain(theta_r)
            worst["g_ras"] = max(worst["g_ras"], float(np.max(np.abs(g_ras - ray["g_ras_dbi"]))))
            for off in self.offs:
                g_bs = self.budget.bs_gain(phi_b, theta_b, off)
                worst["g_bs"] = max(worst["g_bs"], float(np.max(np.abs(g_bs - ray["g_bs_dbi_%g" % off]))))
                margin = self.budget.margin_db(ray["perda_db"], g_ras, g_bs)
                worst["margin"] = max(worst["margin"], float(np.max(np.abs(margin - ray["margem_db_%g" % off]))))
        for key, value in worst.items():
            self.assertLess(value, 1e-5, f"{key}: worst difference {value}")

    def _station_ground(self):
        from sharc.contour.link import Profiles
        base = os.path.join(REF, "D", "Simulacao Database - Restart", "topografia_morfologia_CE", "base_processada")
        return Profiles(Region(os.path.join(base, "CE_MDT_50m.tif"))).ground_m(self.site.lat_deg, self.site.lon_deg)


@unittest.skipUnless(REF and os.path.isdir(os.path.join(REF, "camp")), "SHARC_CONTOUR_REF not set")
class CearaCalculatorReferenceTest(CearaBudgetReferenceTest):
    """End to end: the calculator re-evaluates stored rays and ends them where the original tool did."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import yaml
        from sharc.contour.calculator import ContourCalculator, Sweep
        from sharc.contour.domain import Domain
        from sharc.contour.heights import constant_height
        y = yaml.safe_load(open(os.path.join(cls.camp, "parametros_usados.yaml"), encoding="utf-8"))
        base = os.path.join(REF, "D", "Simulacao Database - Restart", "topografia_morfologia_CE", "base_processada")
        region = Region(os.path.join(base, "CE_MDT_50m.tif"), os.path.join(base, "CE_morf_50m.tif"),
                        os.path.join(base, "CE_zonas_50m.tif"), "celplan", 50.0)
        p452 = {k: v for k, v in y["propagacao"]["param_p452"].items()
                if k not in ("profile_source", "profile_raster", "profile_step_m", "clutter_raster", "clutter_heights",
                             "zone_raster")}
        v = y["varredura"]
        cls.calc = ContourCalculator(cls.budget, region, p452, constant_height(45.0), y["propagacao"]["frequencia_mhz"],
                                     Domain(region.terrain, region.zones), Sweep(v["passo_m"], v["d_min_m"], v["d_max_m"]))

    def test_evaluate_reproduces_the_stored_margins(self):
        worst = 0.0
        for name in self.rays[:: max(1, len(self.rays) // 5)]:
            ray = np.load(os.path.join(self.camp, "raios", name), allow_pickle=True)
            sel = slice(0, ray["d_m"].size, 7)                              # a subset of the points keeps it fast
            out = self.calc.evaluate(float(ray["az_enu"]), ray["d_m"][sel], ray["altura_m"][sel], self.offs)
            for off in self.offs:
                worst = max(worst, float(np.max(np.abs(out["margin_db_%g" % off] - ray["margem_db_%g" % off][sel]))))
            self.assertIn("horizon_margin_db_0", out)
        self.assertLess(worst, 1e-5, f"worst margin difference {worst} dB")

    def test_rays_end_where_the_original_tool_ended_them(self):
        checked = 0
        for name in self.rays:
            ray = np.load(os.path.join(self.camp, "raios", name), allow_pickle=True)
            reason = str(ray["motivo_fim"])
            if reason != "mar":                                              # the state polygon is not part of this check
                continue
            d_end, why = self.calc.ray_end(float(ray["az_enu"]))
            self.assertEqual(why, "sea")
            self.assertAlmostEqual(d_end, float(ray["d_fim_m"]), places=6)
            checked += 1
        self.assertGreater(checked, 3)

    def test_contour_search_agrees_with_the_stored_margins_within_a_grid_step(self):
        ray = np.load(os.path.join(self.camp, "raios", self.rays[1]), allow_pickle=True)
        from_margins = self.calc.contour_from_margins(ray["d_m"], ray["margem_db_90"])
        found = self.calc.contour_distance(float(ray["az_enu"]), 90.0, float(ray["d_fim_m"]))
        if from_margins["marker"] == "ok" and found["marker"] == "ok":
            # constant height 45 m is what the stored ray used, so both see the same margins
            self.assertLessEqual(abs(found["contour_m"] - from_margins["contour_m"]), 50.0 + 1.0)


class AnotherSiteTest(unittest.TestCase):
    """The same code at a site on another continent, with synthetic data: no file or constant of Ceara is involved."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path

        import rasterio
        from rasterio.transform import from_origin
        cls.tmp = Path(tempfile.mkdtemp())
        n, step = 400, 0.005                                    # 2 x 2 degrees, about 550 m cells
        kw = dict(driver="GTiff", height=n, width=n, count=1, crs="EPSG:4326",
                  transform=from_origin(5.88, 51.52, step, step))
        ys, xs = np.mgrid[0:n, 0:n]
        dem = (300.0 + 150.0 * np.exp(-(((xs - 200) / 40.0) ** 2 + ((ys - 200) / 40.0) ** 2))).astype(np.float32)
        cls.dem = str(cls.tmp / "dem.tif")
        with rasterio.open(cls.dem, "w", dtype="float32", **kw) as ds:
            ds.write(dem, 1)
        cls.cover = str(cls.tmp / "cover.tif")
        with rasterio.open(cls.cover, "w", dtype="uint8", **kw) as ds:
            ds.write(np.full((n, n), 10, dtype=np.uint8), 1)             # tree cover everywhere (WorldCover class 10)
        cls.zones = str(cls.tmp / "zones.tif")
        with rasterio.open(cls.zones, "w", dtype="uint8", **kw) as ds:
            ds.write(np.full((n, n), 2, dtype=np.uint8), 1)              # inland everywhere

    def _calc(self, spurious_dbm_mhz=-30.0, bs_height=30.0, d_max=60000.0):
        from sharc.contour.budget import Budget, ReferenceBs
        from sharc.contour.calculator import ContourCalculator, Sweep
        from sharc.contour.heights import constant_height
        site = RasSite("Effelsberg-like", 50.5249, 6.8836, 10.0, 100.0, 0.6, 4900.0, 100.0, 30.0, 40.0)
        region = Region(self.dem, self.cover, self.zones, "worldcover", 100.0)
        return ContourCalculator(Budget(site, ReferenceBs(spurious_dbm_mhz=spurious_dbm_mhz)), region,
                                 {"percentage_p": 2.0, "delta_N": 45.0, "N0": 330.0, "air_temperature": 283.15,
                                  "atmospheric_pressure": 1013.0, "polarization": "horizontal", "clutter_loss": False,
                                  "clutter_type": "both_ends", "is_terrain": True, "Dct": 500.0, "Dcr": 500.0},
                                 constant_height(bs_height), 3500.0, sweep=Sweep(200.0, 400.0, d_max, 5.0))

    def test_ray_ends_at_the_terrain_edge_not_at_a_state_border(self):
        calc = self._calc(d_max=500000.0)
        d_end, reason = calc.ray_end(0.0)                                    # east
        self.assertEqual(reason, "terrain_edge")
        self.assertGreater(d_end, 40000.0)
        self.assertLess(d_end, 80000.0)                                      # the raster ends about 1 degree east

    def test_margin_falls_with_distance_and_the_contour_follows_the_emission(self):
        quiet, loud = self._calc(-20.0), self._calc(0.0)
        d = np.array([1000.0, 5000.0, 20000.0])
        m = quiet.evaluate(30.0, d, [30.0] * 3, [0.0])["margin_db_0"]
        self.assertTrue(m[0] > m[1] > m[2])
        far = []
        for calc in (quiet, loud):
            found = calc.contour_distance(30.0, 0.0, 50000.0)
            far.append(found["contour_m"])
        self.assertGreater(far[0], quiet.sweep.d_min_m)                      # both are inside the search range
        self.assertGreater(far[1], 2.0 * far[0])                             # 20 dB more emission moves the contour out a lot

    def test_horizon_angles_are_reported_and_finite(self):
        out = self._calc().evaluate(120.0, [2000.0, 8000.0], [30.0, 30.0], [0.0, 90.0])
        for key in ("el_station_horizon_deg", "el_bs_horizon_deg", "horizon_margin_db_0", "horizon_margin_db_90"):
            self.assertTrue(np.isfinite(out[key]).all(), key)

    def test_margin_at_is_the_same_number_as_evaluate(self):
        calc = self._calc()
        d = 7300.0
        full = calc.evaluate(75.0, [d], [30.0], [0.0, 90.0, 135.0])
        for off in (0.0, 90.0, 135.0):
            self.assertAlmostEqual(calc.margin_at(75.0, d, off), float(full["margin_db_%g" % off][0]), places=9)

    def test_the_search_of_every_off_axis_reuses_the_loss_of_the_same_point(self):
        calc = self._calc()
        calls = []
        original = calc.link.loss_from_profile
        calc.link.loss_from_profile = lambda *a, **k: (calls.append(1), original(*a, **k))[1]
        found = [calc.contour_distance(30.0, off, 20000.0) for off in (0.0, 90.0, 135.0)]
        evaluations = sum(f["evaluations"] for f in found)
        self.assertLess(len(calls), evaluations)                  # fewer losses than margin evaluations: shared points
        self.assertLessEqual(len(calls), max(f["evaluations"] for f in found) * 2)

    def test_a_profile_over_empty_pixels_cuts_the_ray_instead_of_failing_the_campaign(self):
        from sharc.contour.calculator import NoTerrainData
        calc = self._calc()
        reference = calc.contour_distance(30.0, 0.0, 20000.0)
        real_profile = calc.link.profiles.profile

        def patchy(lat0, lon0, lat, lon):
            from sharc.contour import geometry as g
            if g.distance_m(lat0, lon0, lat, lon)[0] > 6000.0:
                raise ValueError("terrain profile to (x, y) has 3 points without data")
            return real_profile(lat0, lon0, lat, lon)
        calc.link.profiles.profile = patchy
        calc._terms_cache.clear()
        cut = calc.contour_distance(30.0, 0.0, 20000.0)
        self.assertLessEqual(cut["cut_at_m"], 6000.0)
        self.assertGreater(cut["cut_at_m"], 5000.0)                          # cut one step before the first empty point
        self.assertLessEqual(cut["contour_m"], cut["cut_at_m"] + 1e-9)
        self.assertTrue(np.isfinite(cut["contour_m"]))
        self.assertNotIn("cut_at_m", reference)
        with self.assertRaises(NoTerrainData):                           # the low-level call still says what happened
            calc.margin_at(30.0, 8000.0, 0.0)
        calc.link.profiles.profile = lambda *a: (_ for _ in ()).throw(ValueError("terrain profile has 2 points without data"))
        calc._terms_cache.clear()
        self.assertEqual(calc.contour_distance(30.0, 0.0, 20000.0)["marker"], "no_points")   # nothing usable at all

    def test_other_errors_are_not_swallowed(self):
        calc = self._calc()
        calc.link.profiles.profile = lambda *a: (_ for _ in ()).throw(ValueError("something else"))
        with self.assertRaisesRegex(ValueError, "something else"):
            calc.contour_distance(30.0, 0.0, 20000.0)


class HeightTableTest(unittest.TestCase):
    def _csv(self, rows):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "db.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("latitude,longitude,altura\n" + "".join(f"{a},{b},{c}\n" for a, b, c in rows))
        return path

    def test_rows_with_missing_or_invalid_heights_are_ignored_not_fatal(self):
        from sharc.contour.heights import HeightTable
        rows = [(50.55, 6.9, 30), (50.56, 6.9, ""), (50.57, 6.9, "abc"), (50.58, 6.9, -5), (50.59, 6.9, 50), ("x", 6.9, 20)]
        table = HeightTable(self._csv(rows), 50.5249, 6.8836, window=1.0, n_min=2)
        self.assertEqual(table.dropped, 4)
        h = table(5000.0)
        self.assertTrue(np.isfinite(h) and 30.0 <= h <= 50.0)

    def test_a_database_without_usable_rows_is_an_error_with_the_file_name(self):
        from sharc.contour.heights import HeightTable
        with self.assertRaisesRegex(ValueError, "no usable row"):
            HeightTable(self._csv([(50.5, 6.9, "")]), 50.5249, 6.8836)

    def test_missing_column_is_reported(self):
        import tempfile
        from sharc.contour.heights import HeightTable
        path = os.path.join(tempfile.mkdtemp(), "x.csv")
        open(path, "w").write("latitude,longitude\n1,2\n")
        with self.assertRaisesRegex(KeyError, "altura"):
            HeightTable(path, 0.0, 0.0)

    def test_a_sparse_ring_is_widened_to_n_min(self):
        from sharc.contour.heights import HeightTable
        rows = [(50.5249 + 0.01 * i, 6.8836, 10 + i) for i in range(1, 30)]
        table = HeightTable(self._csv(rows), 50.5249, 6.8836, window=0.01, n_min=5)
        _, used, width = table.height(5000.0)
        self.assertGreaterEqual(used, 5)
        self.assertGreater(width, 0.01)


class CriterionTest(unittest.TestCase):
    def test_ra769_cases(self):
        from sharc.contour.criterion import Criterion
        k = 1.380649e-23
        vlbi = Criterion("VLBI", p_vlbi_percent=1.0).threshold_dbw(50.0, 190.0)
        self.assertAlmostEqual(vlbi, 10 * math.log10(0.01 * k * 50.0 * 190e6), places=9)
        cont = Criterion("CONTINUUM", p_continuum_percent=1.0, integration_time_s=2000.0).threshold_dbw(50.0, 190.0)
        self.assertAlmostEqual(cont, 10 * math.log10(0.01 * k * 50.0 * math.sqrt(190e6 / 2000.0)), places=9)
        self.assertAlmostEqual(Criterion("VLBI", allocation_margin_db=3.0).threshold_dbw(50.0, 190.0), vlbi - 3.0, places=9)
        with self.assertRaises(ValueError):
            Criterion("other").threshold_dbw(50.0, 190.0)

    def test_station_band_must_be_outside_the_imt_carrier(self):
        from sharc.contour.budget import Budget, ReferenceBs
        with self.assertRaisesRegex(ValueError, "spurious domain"):
            Budget(RasSite("x", 0.0, 0.0, frequency_mhz=3500.0, bandwidth_mhz=50.0), ReferenceBs(frequency_mhz=3500.0))


class HorizonTest(unittest.TestCase):
    def test_flat_path_is_line_of_sight_with_the_usual_small_negative_angles(self):
        from sharc.contour import horizon
        d = np.linspace(0.0, 10.0, 101)
        el_station, el_bs = horizon.path_angles_deg(d, np.zeros_like(d), 15.0, 45.0, horizon.effective_earth_radius_km(60.0))
        self.assertLess(abs(el_station), 1.0)
        self.assertLess(abs(el_bs), 1.0)

    def test_a_ridge_raises_the_horizon_angle_seen_from_the_station(self):
        from sharc.contour import horizon
        d = np.linspace(0.0, 10.0, 101)
        h = np.zeros_like(d)
        base, _ = horizon.path_angles_deg(d, h, 15.0, 45.0, 8500.0)
        h[30] = 300.0                                               # a ridge 3 km from the station
        ridge, _ = horizon.path_angles_deg(d, h, 15.0, 45.0, 8500.0)
        self.assertGreater(ridge, base + 3.0)

    def test_effective_radius(self):
        from sharc.contour import horizon
        self.assertAlmostEqual(horizon.effective_earth_radius_km(60.0), 6371.0 * 157.0 / 97.0, places=6)


if __name__ == "__main__":
    unittest.main()
