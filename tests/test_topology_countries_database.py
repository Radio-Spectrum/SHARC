# -*- coding: utf-8 -*-
"""MACRO_COUNTRIES with its sites read from a base-station database."""
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import numpy.testing as npt

from sharc.parameters.database.parameters_database import ParametersDatabase
from sharc.parameters.imt.parameters_countries_imt import ParametersCountries
from sharc.parameters.imt.parameters_imt import ParametersImt
from sharc.station_factory import StationFactory
from sharc.support.sharc_geom import CoordinateSystem
from sharc.topology.topology_countries import TopologyCountries

ROWS = [
    # latitude, longitude, azimute, altura, cota_terreno
    (-3.8641, -38.4429, 110.0, 50.0, 10.0),
    (-3.8641, -38.4429, 230.0, 50.0, 110.0),
    (-3.8969, -38.4233, 10.0, 45.0, 20.0),
    (-3.7700, -38.5500, -60.0, 30.0, 5.0),
    (-3.7000, -38.6000, 0.0, 25.0, 0.0),
]


def make_database(folder: Path, num_subsets: int, with_ground: bool) -> ParametersDatabase:
    """Write ROWS to a CSV in folder and load it."""
    header = "latitude,longitude,azimute,altura" + (",cota_terreno" if with_ground else "")
    lines = [header]
    for row in ROWS:
        values = row if with_ground else row[:4]
        lines.append(",".join(str(v) for v in values))
    path = folder / "db.csv"
    path.write_text("\n".join(lines) + "\n")
    database = ParametersDatabase(num_subsets=num_subsets, from_db_topology_countries=True)
    database.load_database(path)
    return database


class TopologyCountriesDatabaseTest(unittest.TestCase):
    """Sites, subsets, heights and ground altitude taken from the database."""

    def setUp(self):
        """Create a temporary folder and the simulator reference point."""
        self.tmp = Path(tempfile.mkdtemp())
        self.cs = CoordinateSystem()
        self.cs.set_reference(-3.77, -38.55, 30.0)

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def topology(self, database: ParametersDatabase, **kwargs) -> TopologyCountries:
        """Build a MACRO_COUNTRIES topology fed by the database."""
        params = ParametersCountries(country_names=["Brazil"], **kwargs)
        return TopologyCountries(params, self.cs, database=database)

    def test_sites_follow_the_subset(self):
        """The BS are the rows of the current subset."""
        database = make_database(self.tmp, num_subsets=2, with_ground=False)
        topology = self.topology(database)

        topology.calculate_coordinates()
        self.assertEqual(topology.num_base_stations, 3)
        npt.assert_array_equal(topology.lats, [r[0] for r in ROWS[:3]])
        npt.assert_array_equal(topology.lons, [r[1] for r in ROWS[:3]])
        npt.assert_array_equal(topology.azimuth, [r[2] for r in ROWS[:3]])
        npt.assert_array_equal(topology.site_heights, [r[3] for r in ROWS[:3]])
        npt.assert_array_equal(topology.ground_altitude, 0.0)

        database.select_subset(1)
        topology.calculate_coordinates()
        self.assertEqual(topology.num_base_stations, 2)
        npt.assert_array_equal(topology.lats, [r[0] for r in ROWS[3:]])

    def test_fixed_azimuth_overrides_column(self):
        """macrocell_countries.fixed_azimuth still wins over the column."""
        database = make_database(self.tmp, num_subsets=1, with_ground=False)
        topology = self.topology(database, fixed_azimuth=45.0)
        topology.calculate_coordinates()
        npt.assert_array_equal(topology.azimuth, 45.0)

    def test_base_stations_heights_and_ground(self):
        """Antenna at ground altitude (cota_terreno) plus height above ground."""
        database = make_database(self.tmp, num_subsets=1, with_ground=True)
        topology = self.topology(database)
        topology.calculate_coordinates()
        npt.assert_array_equal(topology.ground_altitude, [r[4] for r in ROWS])

        param_imt = ParametersImt()
        param_imt.topology.type = "MACRO_COUNTRIES"
        bs = StationFactory.generate_imt_base_stations(
            param_imt, param_imt.bs.antenna.array, topology, np.random.RandomState(1),
        )
        # height above ground stays the local z (used by UMa and others)
        npt.assert_array_equal(bs.geom.z_local, [r[3] for r in ROWS])
        # the first two sites share latitude/longitude: their antennas are
        # apart only by the 100 m difference in ground altitude
        distance = bs.geom.get_3d_distance_to(bs.geom)
        self.assertAlmostEqual(distance[0, 1], 100.0, delta=1e-3)
        # BS pointing is set in each site's own frame (wrapped to [-180, 180))
        npt.assert_allclose(
            bs.geom.pointn_azim_local, [(r[2] + 180.0) % 360.0 - 180.0 for r in ROWS],
        )

        ue = StationFactory.generate_imt_ue(
            param_imt, param_imt.ue.antenna.array, topology, np.random.RandomState(2),
        )
        # UE height above the ground of its own site, whatever the BS height
        npt.assert_allclose(ue.geom.z_local, param_imt.ue.height)

    def test_unloaded_database_is_rejected(self):
        """Passing a database that was never loaded is an error."""
        with self.assertRaises(ValueError):
            self.topology(ParametersDatabase(from_db_topology_countries=True))


if __name__ == "__main__":
    unittest.main()
