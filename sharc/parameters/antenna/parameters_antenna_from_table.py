from sharc.parameters.parameters_base import ParametersBase

from dataclasses import dataclass, field
import os
import numpy as np


@dataclass
class ParametersAntennaFromTable(ParametersBase):
    """Parameters for a table-based antenna pattern loaded from a CSV file.

    The CSV is read once when validate() is called and cached in
    _elevation/_gain so that AntennaFromTable.__init__ never touches
    disk again, even across 10 000 snapshots.
    """

    table_file: str = None

    # Cached arrays — populated by validate(), read-only afterwards
    _elevation: np.ndarray = field(default=None, init=False, repr=False, compare=False)
    _gain:      np.ndarray = field(default=None, init=False, repr=False, compare=False)

    def validate(self, ctx):
        if self.table_file is None:
            raise ValueError(f"{ctx}.table_file must be set")
        if not os.path.isfile(self.table_file):
            raise ValueError(f"{ctx}.table_file not found: {self.table_file}")

        # Load once and cache
        data = np.loadtxt(self.table_file, delimiter=",", skiprows=1, usecols=(0, 1))
        self._elevation = data[:, 0]
        self._gain      = data[:, 1]
