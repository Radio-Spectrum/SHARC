# -*- coding: utf-8 -*-
"""Tests for the optional base-station database section."""
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import numpy.testing as npt

from sharc.parameters.parameters import Parameters
from sharc.parameters.database.parameters_database import ParametersDatabase

CSV_HEADER = "Latitude,Longitude,Azimute,Altura,Operadora\n"


def write_csv(path: Path, n_rows: int):
    """Write a database with n_rows valid sites to path."""
    lines = [CSV_HEADER]
    for i in range(n_rows):
        lines.append(f"{-3.8 - 0.01 * i},{-38.5 + 0.01 * i},{(30.0 * i) % 360},{20.0 + i},op{i % 3}\n")
    path.write_text("".join(lines))


class ParametersDatabaseTest(unittest.TestCase):
    """Loading, validation and subsets of ParametersDatabase."""

    def setUp(self):
        """Create a temporary folder with a 10-row database."""
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "db.csv"
        write_csv(self.csv, 10)

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def write_yaml(self, body: str) -> Path:
        """Write a parameter file holding only the given text."""
        path = self.tmp / "params.yaml"
        path.write_text(body)
        return path

    def load(self, body: str) -> ParametersDatabase:
        """Load a ParametersDatabase from a parameter file with the given text."""
        params = ParametersDatabase()
        params.load_parameters_from_file(self.write_yaml(body))
        return params

    def test_no_section(self):
        """Without a database section nothing is loaded."""
        params = self.load("general:\n  num_snapshots: 3\n")
        self.assertFalse(params.is_loaded)
        self.assertIsNone(params.data)
        self.assertIsNone(params.data_full)

    def test_load_relative_to_parameter_file(self):
        """A relative file name is resolved next to the parameter file."""
        params = self.load(
            "database:\n  database_file_name: db.csv\n  num_subsets: 3\n"
            "  from_db_topology_countries: true\n",
        )
        self.assertTrue(params.is_loaded)
        self.assertEqual(Path(params.database_file_name), self.csv.resolve())
        # column names are normalised to lower case
        self.assertIn("latitude", params.data_full.columns)
        self.assertIn("operadora", params.data_full.columns)
        self.assertEqual(len(params.data_full), 10)

    def test_subsets(self):
        """Subsets are consecutive, never empty and cover every row once."""
        params = self.load("database:\n  database_file_name: db.csv\n  num_subsets: 4\n")
        sizes = []
        rows = []
        for i in range(4):
            params.select_subset(i)
            self.assertEqual(params.subset_index, i)
            sizes.append(len(params.data))
            rows.extend(params.data.index.tolist())
        self.assertEqual(sizes, [3, 3, 2, 2])
        self.assertEqual(rows, list(range(10)))
        with self.assertRaises(IndexError):
            params.select_subset(4)

    def test_subset_for_snapshot(self):
        """Each subset gets snapshots_per_subset consecutive snapshots."""
        params = self.load("database:\n  database_file_name: db.csv\n  num_subsets: 2\n")
        params.set_snapshots_per_subset(5)
        subsets = [params.subset_for_snapshot(s) for s in range(1, 11)]
        self.assertEqual(subsets, [0] * 5 + [1] * 5)

    def test_validation(self):
        """Invalid sections and files are rejected."""
        with self.assertRaises(ValueError):
            self.load("database:\n  from_db_topology_countries: true\n")
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.txt\n")
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.csv\n  num_subsets: 0\n")
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.csv\n  num_subsets: 11\n")
        with self.assertRaises(FileNotFoundError):
            self.load("database:\n  database_file_name: missing.csv\n")
        with self.assertRaises(NotImplementedError):
            self.load(
                "database:\n  database_file_name: db.csv\n"
                "  from_db_topology_gen_macrocell: true\n",
            )
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.csv\n  unknown_key: 1\n")

    def test_antenna_params(self):
        """from_db_antenna_params needs the topology flag and its columns."""
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.csv\n  from_db_antenna_params: true\n")
        flags = "  from_db_topology_countries: true\n  from_db_antenna_params: true\n"
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.csv\n" + flags)

        lines = (self.csv.read_text().splitlines())
        lines[0] += ",n_rows,n_columns,beamforming_gain,element_max_g,tx_power,sub_num_rows,downtilt"
        for i in range(1, len(lines)):
            lines[i] += f",8,8,15.0,5.0,{40.0 + i},3,6.0"
        self.csv.write_text("\n".join(lines) + "\n")
        params = self.load("database:\n  database_file_name: db.csv\n  num_subsets: 2\n" + flags)
        params.select_subset(1)
        antennas = params.antenna_params
        self.assertEqual(len(antennas), 5)
        self.assertEqual(antennas[0].n_rows, 8)
        self.assertAlmostEqual(antennas[0].tx_power, 46.0)
        self.assertAlmostEqual(antennas[0].element_max_g, 5.0 - (10 * np.log10(64) - 15.0))

        lines[1] = lines[1].replace(",8,8,", ",8.5,8,")
        self.csv.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ValueError):
            self.load("database:\n  database_file_name: db.csv\n" + flags)

    def test_topology_columns(self):
        """MACRO_COUNTRIES from the database needs valid site columns."""
        (self.tmp / "bad.csv").write_text("latitude,longitude,azimute\n-3.8,-38.5,10\n")
        with self.assertRaises(ValueError):
            self.load(
                "database:\n  database_file_name: bad.csv\n"
                "  from_db_topology_countries: true\n",
            )
        (self.tmp / "bad.csv").write_text("latitude,longitude,azimute,altura\n-3.8,-38.5,10,0\n")
        with self.assertRaises(ValueError):
            self.load(
                "database:\n  database_file_name: bad.csv\n"
                "  from_db_topology_countries: true\n",
            )


class ParametersWithDatabaseTest(unittest.TestCase):
    """The database section inside a full parameter file."""

    def setUp(self):
        """Copy the testing parameter file next to a database."""
        self.tmp = Path(tempfile.mkdtemp())
        write_csv(self.tmp / "db.csv", 10)
        self.base_yaml = Path(__file__).parent.resolve() / "parameters_for_testing.yaml"

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def read(self, extra: str) -> Parameters:
        """Read the testing parameter file with extra text appended."""
        path = self.tmp / "params.yaml"
        path.write_text(self.base_yaml.read_text() + "\n" + extra)
        parameters = Parameters()
        parameters.set_file_name(path)
        parameters.read_params()
        return parameters

    def test_without_database(self):
        """The usual parameter file loads no database and keeps num_snapshots."""
        parameters = self.read("")
        self.assertFalse(parameters.database.is_loaded)
        self.assertEqual(parameters.general.num_snapshots, 100)

    def test_with_database(self):
        """num_snapshots counts the snapshots of one subset."""
        parameters = self.read("database:\n  database_file_name: db.csv\n  num_subsets: 2\n")
        self.assertTrue(parameters.database.is_loaded)
        self.assertEqual(parameters.general.num_snapshots, 200)
        npt.assert_array_equal(
            [parameters.database.subset_for_snapshot(s) for s in (1, 100, 101, 200)],
            [0, 0, 1, 1],
        )


if __name__ == "__main__":
    unittest.main()
