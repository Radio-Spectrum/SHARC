# -*- coding: utf-8 -*-
"""End-to-end runs of a MACRO_COUNTRIES network read from a base-station database."""
import copy
import math
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import numpy.testing as npt
import yaml

import sharc.parameters.parameters_base  # noqa: F401  (registers the tuple constructor)
from sharc.model import Model

yaml.SafeDumper.add_representer(
    tuple, lambda dumper, value: dumper.represent_sequence("tag:yaml.org,2002:python/tuple", value),
)

# Six sites around (-3.8, -38.5); the victim sits at the simulator reference point.
SITES = [
    # latitude, longitude, azimute, altura
    (-3.8641, -38.4429, 110.0, 50.0),
    (-3.8641, -38.4429, 230.0, 50.0),
    (-3.8969, -38.4233, 10.0, 45.0),
    (-3.8202, -38.5011, 95.0, 30.0),
    (-3.7905, -38.5317, 200.0, 25.0),
    (-3.8350, -38.4800, 330.0, 35.0),
]

ARRAY = {
    "normalization": False,
    "element_pattern": "M2101",
    "minimum_array_gain": -200,
    "horizontal_beamsteering_range": (-60.0, 60.0),
    "vertical_beamsteering_range": (90.0, 100.0),
    "downtilt": 6,
    "element_max_g": 3.65,
    "element_phi_3db": 90,
    "element_theta_3db": 65,
    "n_rows": 8,
    "n_columns": 8,
    "element_horiz_spacing": 0.5,
    "element_vert_spacing": 4.2,
    "element_am": 30,
    "element_sla_v": 30,
    "multiplication_factor": 12,
    "subarray": {"is_enabled": True, "n_rows": 6, "element_vert_spacing": 0.7, "eletrical_downtilt": 3.0},
}

PARAMETERS = {
    "general": {
        "num_snapshots": 3, "imt_link": "DOWNLINK", "system": "SINGLE_EARTH_STATION",
        "enable_cochannel": True, "enable_adjacent_channel": False, "seed": 75,
        "overwrite_output": False, "output_dir": "", "output_dir_prefix": "db",
    },
    "database": {
        "database_file_name": "db.csv", "num_subsets": 2, "from_db_topology_countries": True,
    },
    "imt": {
        "minimum_separation_distance_bs_ue": 35, "interfered_with": False,
        "imt_dl_intra_sinr_calculation_disabled": True,
        "frequency": 3500, "bandwidth": 20, "rb_bandwidth": 0.18,
        "spectral_mask": "3GPP E-UTRA", "spurious_emissions": -30,
        "adjacent_ch_emissions": "SPECTRAL_MASK", "adjacent_antenna_model": "SINGLE_ELEMENT",
        "guard_band_ratio": 0.1,
        "topology": {
            "central_latitude": -3.8, "central_longitude": -38.5, "central_altitude": 0,
            "type": "MACRO_COUNTRIES",
            "macrocell_countries": {"country_names": ["Brazil"], "cell_radius": 400.0},
        },
        "bs": {
            "load_probability": 1.0, "conducted_power": 28.0, "height": 20.0,
            "noise_figure": 11, "ohmic_loss": 0, "antenna": {"array": ARRAY},
        },
        "ue": {
            "k": 2, "k_m": 1, "indoor_percent": 0, "distribution_type": "ANGLE_AND_DISTANCE",
            "tx_power_control": True, "height": 1.5, "noise_figure": 9, "ohmic_loss": 0,
            "body_loss": 4,
            "antenna": {"array": {"element_pattern": "FIXED", "element_max_g": -4,
                                  "n_rows": 1, "n_columns": 1}},
        },
        "channel_model": "UMa", "shadowing": False,
    },
    "single_earth_station": {
        "antenna": {"gain": 0.0, "pattern": "OMNI"},
        "bandwidth": 20.0, "channel_model": "FSPL", "frequency": 3500, "polarization_loss": 0,
        "geometry": {
            "azimuth": {"type": "FIXED", "fixed": 0.0},
            "elevation": {"type": "FIXED", "fixed": 0.0},
            "height": 15.0,
            "location": {"type": "FIXED", "fixed": {"x": 0.0, "y": 0.0}},
        },
        "noise_temperature": 50, "tx_power_density": -200,
    },
}


class DatabaseE2ETest(unittest.TestCase):
    """Run the simulator on a small database and check its outputs."""

    def setUp(self):
        """Create a temporary folder for the inputs and outputs."""
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def run_case(self, name: str, parameters: dict, columns: dict | None = None):
        """Write the database and the parameter file, run every snapshot.

        Returns the system INR and the per-BS power of each snapshot.
        """
        header = ["latitude", "longitude", "azimute", "altura"]
        rows = [list(site) for site in SITES]
        if columns:
            header += list(columns)
            for i, row in enumerate(rows):
                row += [values[i] for values in columns.values()]
        csv = self.tmp / f"{name}.csv"
        lines = [",".join(header)] + [",".join(repr(v) for v in r) for r in rows]
        csv.write_text("\n".join(lines) + "\n")

        parameters = copy.deepcopy(parameters)
        parameters["database"]["database_file_name"] = csv.name
        parameters["general"]["output_dir"] = str(self.tmp / "out")
        parameters["general"]["output_dir_prefix"] = name
        param_file = self.tmp / f"{name}.yaml"
        param_file.write_text(yaml.safe_dump(parameters, sort_keys=False))

        model = Model()
        model.set_param_file(str(param_file))
        model.initialize()
        sim = model.simulation
        inr, powers, subsets = [], [], []
        while not model.is_finished():
            model.snapshot()
            inr.append(float(sim.system.inr[0]))
            powers.append({bs: p.copy() for bs, p in sim.bs.tx_power.items()})
            subsets.append(sim.parameters.database.subset_index)
        return np.array(inr), powers, subsets, sim

    def test_subsets_in_order(self):
        """Every subset gets num_snapshots snapshots, in order."""
        _, _, subsets, sim = self.run_case("order", PARAMETERS)
        self.assertEqual(sim.parameters.general.num_snapshots, 6)
        self.assertEqual(subsets, [0, 0, 0, 1, 1, 1])
        self.assertEqual(sim.topology.num_base_stations, 3)

    def test_antenna_params_equal_to_parameter_file(self):
        """A database repeating the parameter-file array and power changes nothing."""
        reference, _, _, _ = self.run_case("yaml", PARAMETERS)

        parameters = copy.deepcopy(PARAMETERS)
        parameters["database"]["from_db_antenna_params"] = True
        n = len(SITES)
        total_power = 28.0 + 10 * math.log10(8 * 8)
        columns = {
            "n_rows": [8] * n, "n_columns": [8] * n,
            "beamforming_gain": [10 * np.log10(8 * 8)] * n,
            "element_max_g": [3.65] * n, "tx_power": [total_power] * n,
            "sub_num_rows": [6] * n, "downtilt": [6.0] * n,
        }
        from_db, _, _, _ = self.run_case("db_same", parameters, columns)
        npt.assert_allclose(from_db, reference, atol=1e-9)

        # +3 dB on every BS: co-channel interference goes up by 3 dB
        columns["tx_power"] = [total_power + 3.0] * n
        louder, powers, _, _ = self.run_case("db_louder", parameters, columns)
        npt.assert_allclose(louder, reference + 3.0, atol=1e-9)
        for snapshot_powers in powers:
            for p in snapshot_powers.values():
                npt.assert_allclose(p, total_power + 3.0 - 10 * math.log10(2))

    def test_victim_at_geographic_location(self):
        """A FIXED_GEO victim pointing at the IMT center, with a directional antenna."""
        parameters = copy.deepcopy(PARAMETERS)
        ses = parameters["single_earth_station"]
        ses["geometry"]["location"] = {
            "type": "FIXED_GEO",
            "fixed_geo": {"latitude": -3.87350, "longitude": -38.42216, "altitude": 30.0},
        }
        ses["geometry"]["azimuth"] = {"type": "POINTING_AT_IMT_CENTER"}
        ses["geometry"]["elevation"] = {"type": "FIXED", "fixed": 0.0}
        ses["antenna"] = {"pattern": "ITU-R F.699", "gain": 30.0,
                          "itu_r_f_699": {"diameter": 2.0, "frequency": 3500.0}}
        inr, _, _, sim = self.run_case("geo", parameters)
        self.assertTrue(np.all(np.isfinite(inr)))
        # 30 m of ground plus 15 m of antenna
        npt.assert_allclose(sim.system.geom.z_local, 15.0)
        # boresight through the simulator reference point, horizontally
        azim_to_center = np.degrees(np.arctan2(-3.8 + 3.8735, -38.5 + 38.42216))
        npt.assert_allclose(sim.system.geom.pointn_azim_local, azim_to_center, atol=0.1)

    def test_antenna_params_per_bs(self):
        """Each BS gets its own array, downtilt and power."""
        parameters = copy.deepcopy(PARAMETERS)
        parameters["database"]["from_db_antenna_params"] = True
        columns = {
            "n_rows": [8, 8, 4, 8, 4, 8], "n_columns": [8, 8, 4, 8, 4, 8],
            "beamforming_gain": [18.0, 18.0, 12.0, 18.0, 12.0, 18.0],
            "element_max_g": [5.0] * 6, "tx_power": [46.0, 46.0, 40.0, 43.0, 40.0, 46.0],
            "sub_num_rows": [3] * 6, "downtilt": [3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        }
        inr, powers, _, sim = self.run_case("db_per_bs", parameters, columns)
        self.assertTrue(np.all(np.isfinite(inr)))
        # last subset: rows 3, 4, 5
        npt.assert_allclose(sim.bs.geom.pointn_elev_local, [-6.0, -7.0, -8.0])
        self.assertEqual([a.n_rows for a in sim.bs.antenna], [8, 4, 8])
        # BS with equal arrays share their parameters (keeps the batched path)
        self.assertIs(sim.bs.antenna[0].param, sim.bs.antenna[2].param)
        for bs, p in powers[-1].items():
            npt.assert_allclose(p, columns["tx_power"][3 + bs] - 10 * math.log10(2))
        # element gain compensated by the beamforming efficiency
        npt.assert_allclose(
            sim.bs.antenna[0].param.element_max_g, 5.0 - (10 * np.log10(64) - 18.0),
        )


if __name__ == "__main__":
    unittest.main()
