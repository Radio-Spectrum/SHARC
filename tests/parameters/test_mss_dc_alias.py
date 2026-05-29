from pathlib import Path
import tempfile
import unittest

import numpy as np

from sharc.parameters.parameters import Parameters
from sharc.station_factory import StationFactory
from sharc.support.sharc_geom import CoordinateSystem


class ParametersMssDcAliasTest(unittest.TestCase):
    def _load_alias_parameters(self):
        yaml_text = """
general:
    system: MSS_DC
imt:
    topology:
        type: SINGLE_BS
        single_bs:
            cell_radius: 1000
mss_dc:
    name: AliasSystem
    antenna_pattern: ITU-R-S.1528-LEO
    frequency: 2190.0
    bandwidth: 10.0
    cell_radius: 21000
    num_sectors: 7
    noise_temperature: 290.0
"""

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_text)
            tmp_path = Path(tmp.name)

        try:
            params = Parameters()
            params.set_file_name(tmp_path)
            params.read_params()
            return params
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_mss_dc_alias_section_is_loaded(self):
        params = self._load_alias_parameters()

        self.assertEqual(params.general.system, "MSS_DC")
        self.assertEqual(params.mss_dc.section_name, "mss_dc")
        self.assertEqual(params.mss_dc.name, "AliasSystem")
        self.assertEqual(params.mss_dc.frequency, 2190.0)
        self.assertEqual(params.mss_dc.bandwidth, 10.0)
        self.assertEqual(params.mss_dc.cell_radius, 21000)
        self.assertEqual(params.mss_dc.num_sectors, 7)

    def test_station_factory_accepts_mss_dc_system(self):
        params = self._load_alias_parameters()
        rng = np.random.RandomState(42)
        coord = CoordinateSystem()
        coord.set_reference(0.0, 0.0, 0.0)

        manager = StationFactory.generate_system(
            params,
            topology=None,
            random_number_gen=rng,
            coordinate_system=coord,
        )

        self.assertEqual(manager.station_type.name, "MSS_D2D")
        self.assertGreater(manager.num_stations, 0)


if __name__ == "__main__":
    unittest.main()
