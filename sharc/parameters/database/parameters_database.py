# -*- coding: utf-8 -*-
"""Base-station database.

A CSV (or XLSX) file whose rows describe real IMT sites. It is read once,
split into ``num_subsets`` consecutive subsets, and the snapshots go through
the subsets in order: with ``general.num_snapshots = N`` every subset gets N
snapshots, so the run has ``N * num_subsets`` snapshots in total.

The section is optional. Without a ``database`` section (or without
``database_file_name``) nothing is loaded and the simulation is unchanged.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from sharc.parameters.parameters_base import ParametersBase

ALLOWED_FORMATS = (".csv", ".xlsx")
ALLOWED_DELIMITERS = ("\t", ",", "|")

# Columns a MACRO_COUNTRIES topology needs when it takes its sites from the
# database. The names are the ones used by the existing database files.
TOPOLOGY_COUNTRIES_COLUMNS = ("latitude", "longitude", "azimute", "altura")


@dataclass
class ParametersDatabase(ParametersBase):
    """Parameters of the base-station database and its runtime state."""

    section_name: str = "database"

    # Path to the database file (.csv or .xlsx). A relative path is looked up
    # next to the parameter file first and then in the working directory.
    database_file_name: Optional[str] = None

    # Column delimiter (only for .csv files)
    delimiter: str = ","

    # Number of consecutive subsets the database is split into. Each snapshot
    # simulates a single subset.
    num_subsets: int = 1

    # Take the MACRO_COUNTRIES sites (latitude, longitude, azimute, altura)
    # from the database instead of sampling them.
    from_db_topology_countries: bool = False

    # Kept so that parameter files written for the GEN_MACROCELL topology are
    # rejected with a clear message: that topology is not available here.
    from_db_topology_gen_macrocell: bool = False

    # Runtime state, filled when the database is loaded.
    _data_full: Optional[pd.DataFrame] = field(default=None, init=False, repr=False)
    _subset_bounds: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _subset_index: int = field(default=0, init=False, repr=False)
    _snapshots_per_subset: int = field(default=1, init=False, repr=False)

    def load_parameters_from_file(self, config_file: str, quiet=True):
        """Load the section and, when a database file is set, the database.

        Parameters
        ----------
        config_file : str
            Path to the parameter file.
        quiet : bool
            If True the parser does not warn about unset parameters.
        """
        super().load_parameters_from_file(config_file, quiet)
        self.validate(self.section_name)
        if self.database_file_name is None:
            return
        self.load_database(self._resolve_path(self.database_file_name, config_file))

    def validate(self, ctx: str):
        """Check the parameters of the section.

        Parameters
        ----------
        ctx : str
            Context used in the error messages.
        """
        super().validate(ctx)
        if self.database_file_name is None:
            if self.from_db_topology_countries:
                raise ValueError(
                    f"{ctx}.from_db_topology_countries needs {ctx}.database_file_name",
                )
            return
        if not isinstance(self.database_file_name, str) or not self.database_file_name.strip():
            raise ValueError(f"{ctx}.database_file_name must be a non-empty string")
        if Path(self.database_file_name).suffix.lower() not in ALLOWED_FORMATS:
            raise ValueError(f"{ctx}.database_file_name must be one of {ALLOWED_FORMATS}")
        delimiter = self.delimiter.encode().decode("unicode_escape")
        if delimiter not in ALLOWED_DELIMITERS:
            raise ValueError(f"{ctx}.delimiter must be one of {ALLOWED_DELIMITERS}")
        if isinstance(self.num_subsets, bool) or not isinstance(self.num_subsets, int) \
                or self.num_subsets < 1:
            raise ValueError(f"{ctx}.num_subsets must be a positive integer")
        if self.from_db_topology_gen_macrocell:
            raise NotImplementedError(
                f"{ctx}.from_db_topology_gen_macrocell: the GEN_MACROCELL topology is not available",
            )

    @staticmethod
    def _resolve_path(file_name: str, config_file: str) -> Path:
        """Resolve the database path: as given, next to the parameter file, or in the cwd."""
        path = Path(file_name).expanduser()
        if path.is_absolute():
            return path
        candidates = [Path(config_file).resolve().parent / path, Path.cwd() / path]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return candidates[0]

    def load_database(self, path: Path | str):
        """Read the database file, check its columns and select the first subset.

        Parameters
        ----------
        path : Path | str
            Path to the .csv or .xlsx file.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"ParametersDatabase: database file not found: {path}")
        self.database_file_name = str(path)

        if path.suffix.lower() == ".csv":
            delimiter = self.delimiter.encode().decode("unicode_escape")
            data = pd.read_csv(path, delimiter=delimiter)
        else:
            data = pd.read_excel(path)
        data.columns = data.columns.str.strip().str.lower()

        if len(data) == 0:
            raise ValueError(f"ParametersDatabase: {path} has no rows")
        if self.num_subsets > len(data):
            raise ValueError(
                f"ParametersDatabase: num_subsets ({self.num_subsets}) is larger than "
                f"the number of rows ({len(data)})",
            )
        if self.from_db_topology_countries:
            self._check_topology_columns(data)

        self._data_full = data.reset_index(drop=True)
        # Consecutive subsets whose sizes differ by at most one row, so that
        # none of them is empty.
        self._subset_bounds = np.array([
            len(chunk) for chunk in np.array_split(np.arange(len(data)), self.num_subsets)
        ]).cumsum()
        self._subset_bounds = np.concatenate([[0], self._subset_bounds])
        self.select_subset(0)

    @staticmethod
    def _check_topology_columns(data: pd.DataFrame):
        """Check the columns MACRO_COUNTRIES reads from the database."""
        missing = [c for c in TOPOLOGY_COUNTRIES_COLUMNS if c not in data.columns]
        if missing:
            raise ValueError(f"ParametersDatabase: missing columns {missing}")
        for column in TOPOLOGY_COUNTRIES_COLUMNS:
            values = pd.to_numeric(data[column], errors="coerce").to_numpy()
            if not np.all(np.isfinite(values)):
                raise ValueError(f"ParametersDatabase: column '{column}' must be numeric and finite")
        if np.any(np.abs(data["latitude"]) > 90.0):
            raise ValueError("ParametersDatabase: latitude must be in [-90, 90]")
        if np.any(np.abs(data["longitude"]) > 180.0):
            raise ValueError("ParametersDatabase: longitude must be in [-180, 180]")
        if np.any(data["altura"] <= 0.0):
            raise ValueError("ParametersDatabase: altura must be greater than zero")

    @property
    def is_loaded(self) -> bool:
        """Whether a database file was loaded."""
        return self._data_full is not None

    @property
    def data_full(self) -> pd.DataFrame:
        """All the rows of the database."""
        return self._data_full

    @property
    def data(self) -> Optional[pd.DataFrame]:
        """The rows of the current subset (None while nothing is loaded)."""
        if self._data_full is None:
            return None
        start, end = self.subset_rows(self._subset_index)
        return self._data_full.iloc[start:end]

    @property
    def subset_index(self) -> int:
        """Index of the current subset."""
        return self._subset_index

    def subset_rows(self, index: int) -> tuple[int, int]:
        """Return the [start, end) row range of a subset."""
        return int(self._subset_bounds[index]), int(self._subset_bounds[index + 1])

    def select_subset(self, index: int):
        """Make subset ``index`` the current one."""
        if not 0 <= index < self.num_subsets:
            raise IndexError(f"ParametersDatabase: subset {index} out of range [0, {self.num_subsets})")
        self._subset_index = int(index)

    def set_snapshots_per_subset(self, snapshots_per_subset: int):
        """Set how many consecutive snapshots each subset gets."""
        if snapshots_per_subset < 1:
            raise ValueError("ParametersDatabase: snapshots_per_subset must be positive")
        self._snapshots_per_subset = int(snapshots_per_subset)

    def subset_for_snapshot(self, snapshot_number: int) -> int:
        """Return the subset a snapshot simulates (snapshot_number is 1-indexed)."""
        index = (int(snapshot_number) - 1) // self._snapshots_per_subset
        return min(max(index, 0), self.num_subsets - 1)
