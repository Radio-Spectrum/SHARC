# -*- coding: utf-8 -*-
"""The 30-site installation test of branch_database2, run on this branch.

The parameter file is the one of branch_database2 converted with
campaigns/IMT_TO_SES_Database/Script/convert_from_branch_database2.py, and the
reference INR samples are the ones that branch produced. The victim (the ROEN
radio-astronomy station, omnidirectional) receives the spurious emissions of
30 base stations, read from the database in two subsets.
"""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import numpy.testing as npt
import pandas as pd

from sharc.model import Model

CAMPAIGN = Path(__file__).resolve().parents[2] / "sharc" / "campaigns" / "IMT_TO_SES_Database"


def load_converter():
    """Import the campaign's conversion script."""
    path = CAMPAIGN / "Script" / "convert_from_branch_database2.py"
    spec = importlib.util.spec_from_file_location("convert_from_branch_database2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BranchDatabase2CaseTest(unittest.TestCase):
    """Run teste_instalacao and compare it with the branch_database2 reference."""

    def setUp(self):
        """Point the parameter file at the campaign database and a temporary output."""
        self.tmp = Path(tempfile.mkdtemp())
        text = (CAMPAIGN / "input" / "teste_instalacao.yaml").read_text(encoding="utf-8")
        converter = load_converter()
        text = converter.convert_text(
            text,
            database=str(CAMPAIGN / "database" / "db_teste_30bs.csv"),
            output_dir=str(self.tmp / "out"),
        )
        self.param_file = self.tmp / "teste_instalacao.yaml"
        self.param_file.write_text(text, encoding="utf-8")

    def tearDown(self):
        """Remove the temporary folder."""
        shutil.rmtree(self.tmp)

    def test_matches_reference(self):
        """Every snapshot is within 0.1 dB of branch_database2."""
        model = Model()
        model.set_param_file(str(self.param_file))
        model.initialize()
        sim = model.simulation
        inr = []
        while not model.is_finished():
            model.snapshot()
            inr.append(float(sim.system.inr[0]))
        model.finalize()

        reference = pd.read_csv(CAMPAIGN / "reference" / "branch_database2_system_inr.csv")["samples"]
        self.assertEqual(len(inr), len(reference))
        # the victim antenna stands 15 m higher here (fixed_geo.altitude plus
        # its height above ground); the rest is the same model
        npt.assert_allclose(inr, reference, atol=0.1)

        # the subset of every sample is written next to the INR
        output = next((self.tmp / "out").glob("teste_instalacao_*"))
        subsets = pd.read_csv(output / "system_database_subset.csv")["samples"].to_numpy()
        npt.assert_array_equal(subsets, np.repeat([0, 1], 5))


if __name__ == "__main__":
    unittest.main()
