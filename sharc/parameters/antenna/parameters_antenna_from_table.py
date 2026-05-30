from sharc.parameters.parameters_base import ParametersBase

from dataclasses import dataclass
import os


@dataclass
class ParametersAntennaFromTable(ParametersBase):
    """Parameters for a table-based antenna pattern loaded from a CSV file."""

    table_file: str = None

    def validate(self, ctx):
        if self.table_file is None:
            raise ValueError(f"{ctx}.table_file must be set")
        if not os.path.isfile(self.table_file):
            raise ValueError(f"{ctx}.table_file not found: {self.table_file}")
