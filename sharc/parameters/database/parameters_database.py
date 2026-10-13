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
from sharc.parameters.database.parameters_database_imt_antenna import (
    ANTENNA_COLUMNS, AntennaParamsFromFile,
)

ALLOWED_FORMATS = (".csv", ".xlsx")
ALLOWED_DELIMITERS = ("\t", ",", "|")

# Columns a MACRO_COUNTRIES topology needs when it takes its sites from the
# database. The names are the ones used by the existing database files.
TOPOLOGY_COUNTRIES_COLUMNS = ("latitude", "longitude", "azimute", "altura")

# Mean Earth radius used for the great-circle lengths of the profiles [km].
EARTH_RADIUS_KM = 6371.0


def _great_circle_km(lat0, lon0, lat1, lon1):
    """Haversine distance [km] between points given in degrees."""
    la0, lo0, la1, lo1 = map(np.radians, (lat0, lon0, lat1, lon1))
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(
        np.sin((la1 - la0) / 2) ** 2 + np.cos(la0) * np.cos(la1) * np.sin((lo1 - lo0) / 2) ** 2))


@dataclass
class TerrainParams(ParametersBase):
    """Real terrain: terrain/land-cover download and the adaptive mesh."""

    # Adaptive mesh (GeoPackage) to read. Empty: download the terrain and
    # land cover around the database and build the mesh in mesh_output_dir.
    ref_gpkg: Optional[str] = None
    # Resolution of the downloaded terrain and land-cover grids [m].
    mesh_resolution_m: float = 100.0
    # Mesh resolution in urban, suburban and rural areas [m].
    mesh_urban_res_m: int = 30
    mesh_suburban_res_m: int = 150
    mesh_rural_res_m: int = 500
    # Water in the mesh: "exclude" or "coarse".
    mesh_water: str = "exclude"
    # Folder of the downloaded grids and of the mesh built from them.
    mesh_output_dir: str = "data"

    def validate(self, ctx: str):
        """Check the terrain parameters.

        Parameters
        ----------
        ctx : str
            Context used in the error messages.
        """
        super().validate(ctx)
        if isinstance(self.mesh_resolution_m, bool) or not isinstance(self.mesh_resolution_m, (int, float)) \
                or self.mesh_resolution_m <= 0:
            raise ValueError(f"{ctx}.mesh_resolution_m must be a positive number")
        for name in ("mesh_urban_res_m", "mesh_suburban_res_m", "mesh_rural_res_m"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{ctx}.{name} must be a positive integer")
        if self.mesh_water not in ("exclude", "coarse"):
            raise ValueError(f"{ctx}.mesh_water must be 'exclude' or 'coarse'")
        if not isinstance(self.mesh_output_dir, str) or not self.mesh_output_dir.strip():
            raise ValueError(f"{ctx}.mesh_output_dir must be a non-empty string")
        if self.ref_gpkg is not None and not isinstance(self.ref_gpkg, str):
            raise ValueError(f"{ctx}.ref_gpkg must be a string")


@dataclass
class ParametersDatabase(ParametersBase):
    """Parameters of the base-station database and its runtime state."""

    section_name: str = "database"

    # needed to parse the nested terrain block
    nested_parameters_enabled: bool = True

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

    # Take the array antenna, downtilt and total power of each BS from the
    # database (columns in ANTENNA_COLUMNS). Needs from_db_topology_countries.
    from_db_antenna_params: bool = False

    # Real terrain between each BS and the victim station: the ground
    # altitude of every site (both ends of each link) and, for the P452
    # channel model, the P.452 loss of each BS, computed once per run over the
    # terrain profile (see compute_terrain and param_p452.override_from_db).
    use_real_terrain: bool = False
    terrain: TerrainParams = field(default_factory=TerrainParams)

    # Runtime state, filled when the database is loaded.
    _config_dir: Optional[Path] = field(default=None, init=False, repr=False)
    _adaptive_mesh: Optional[object] = field(default=None, init=False, repr=False)
    _reference_ground: Optional[float] = field(default=None, init=False, repr=False)
    _data_full: Optional[pd.DataFrame] = field(default=None, init=False, repr=False)
    _antenna_params_full: Optional[list] = field(default=None, init=False, repr=False)
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
        self._config_dir = Path(config_file).resolve().parent
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
        if self.from_db_antenna_params and not self.from_db_topology_countries:
            raise ValueError(
                f"{ctx}.from_db_antenna_params needs {ctx}.from_db_topology_countries: "
                "the antenna rows must be the sites of the topology",
            )
        if self.use_real_terrain and not self.from_db_topology_countries:
            raise ValueError(
                f"{ctx}.use_real_terrain needs {ctx}.from_db_topology_countries",
            )
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
        if self.from_db_antenna_params:
            missing = [c for c in ANTENNA_COLUMNS if c not in data.columns]
            if missing:
                raise ValueError(f"ParametersDatabase: missing columns {missing}")
            self._antenna_params_full = [
                AntennaParamsFromFile.from_row(row)
                for row in data[list(ANTENNA_COLUMNS)].to_dict("records")
            ]

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

    @property
    def antenna_params(self) -> Optional[list]:
        """AntennaParamsFromFile of the current subset (None without from_db_antenna_params)."""
        if self._antenna_params_full is None:
            return None
        start, end = self.subset_rows(self._subset_index)
        return self._antenna_params_full[start:end]

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

    # ------------------------------------------------------------------
    # Real terrain
    # ------------------------------------------------------------------
    @property
    def reference_ground(self) -> Optional[float]:
        """Ground altitude [m] at the reference point of compute_terrain."""
        return self._reference_ground

    def resolve_input(self, file_name: str) -> Path:
        """Resolve an input file: as given, next to the parameter file, or in the cwd."""
        path = Path(file_name).expanduser()
        if path.is_absolute():
            candidates = [path]
        else:
            candidates = [Path.cwd() / path]
            if self._config_dir is not None:
                candidates.insert(0, self._config_dir / path)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(f"ParametersDatabase: file not found: {file_name}")

    def _resolve_output_dir(self, dir_name: str) -> Path:
        """Resolve an output folder: as given, or next to the parameter file."""
        path = Path(dir_name).expanduser()
        if not path.is_absolute():
            path = (self._config_dir or Path.cwd()) / path
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def get_adaptive_mesh(self, bounding_box: tuple):
        """Load, or download and build, the adaptive terrain mesh.

        Parameters
        ----------
        bounding_box : tuple
            (min_lat, max_lat, min_lon, max_lon) the mesh must cover, used
            only when terrain.ref_gpkg is empty.

        Returns
        -------
        RealAdaptiveMesh
            The mesh, cached for the rest of the run.
        """
        if self._adaptive_mesh is not None:
            return self._adaptive_mesh
        from sharc.propagation.real_terrain import (
            RealAdaptiveMesh, build_adaptive_mesh, download_clutter, download_terrain,
        )

        if self.terrain.ref_gpkg:
            self._adaptive_mesh = RealAdaptiveMesh(str(self.resolve_input(self.terrain.ref_gpkg)))
            return self._adaptive_mesh

        min_lat, max_lat, min_lon, max_lon = bounding_box
        output_dir = self._resolve_output_dir(self.terrain.mesh_output_dir)
        bbox_str = f"{min_lon:.4f}_{min_lat:.4f}_{max_lon:.4f}_{max_lat:.4f}"
        res = int(self.terrain.mesh_resolution_m)
        terrain_path = output_dir / f"terrain_{bbox_str}_{res}m.tif"
        clutter_path = output_dir / f"clutter_{bbox_str}_{res}m.tif"
        # the name carries every setting the mesh depends on, so that a run
        # with other settings never reuses it
        mesh_path = output_dir / (
            f"mesh_{bbox_str}_{res}m_u{self.terrain.mesh_urban_res_m}"
            f"_s{self.terrain.mesh_suburban_res_m}_r{self.terrain.mesh_rural_res_m}"
            f"_{self.terrain.mesh_water}.gpkg"
        )
        bbox = (min_lon, min_lat, max_lon, max_lat)
        if not terrain_path.is_file():
            download_terrain(bbox=bbox, resolution_m=self.terrain.mesh_resolution_m,
                             out_path=str(terrain_path), verbose=True)
        if not clutter_path.is_file():
            download_clutter(bbox=bbox, resolution_m=self.terrain.mesh_resolution_m,
                             out_path=str(clutter_path), like_path=str(terrain_path), verbose=True)
        if not mesh_path.is_file():
            build_adaptive_mesh(
                terrain_path=str(terrain_path), clutter_path=str(clutter_path),
                out_path=str(mesh_path),
                mesh_res_m={
                    "urban": self.terrain.mesh_urban_res_m,
                    "suburban": self.terrain.mesh_suburban_res_m,
                    "rural": self.terrain.mesh_rural_res_m,
                },
                mesh_water=self.terrain.mesh_water,
            )
        self._adaptive_mesh = RealAdaptiveMesh(str(mesh_path))
        return self._adaptive_mesh

    def terrain_profiles(self, ref_lat: float, ref_lon: float, p452_params) -> list:
        """Terrain profiles from a reference point to every database site.

        The profile source and the optional land-cover and zone profiles are
        the options of p452_params (profile_source, profile_raster,
        profile_step_m, clutter_raster, clutter_heights, zone_raster).

        Parameters
        ----------
        ref_lat, ref_lon : float
            Reference point (the victim station) [deg].
        p452_params : ParametersP452
            Profile options.

        Returns
        -------
        list of dict
            One per database row, from the reference point to the site:
            dist_km, height_m (bare terrain), clutter_m (terrain plus
            representative clutter height on the intermediate points, P.452-18
            eq. 6e; None without clutter_raster) and zone (radio-climatic zone
            per point, 1 = A1, 2 = A2, 3 = B; None without zone_raster).
        """
        from sharc.propagation.real_terrain.grade_raster import GridRaster, height_lut

        lats_db = self._data_full["latitude"].to_numpy(dtype=float)
        lons_db = self._data_full["longitude"].to_numpy(dtype=float)
        step_m = float(p452_params.profile_step_m or 0)

        grid = mesh = None
        if p452_params.profile_source == "grid":
            if not p452_params.profile_raster:
                raise ValueError("param_p452.profile_source 'grid' needs param_p452.profile_raster")
            grid = GridRaster(self.resolve_input(p452_params.profile_raster))
        elif p452_params.profile_source == "mesh":
            mesh = self.get_adaptive_mesh((
                min(lats_db.min(), ref_lat), max(lats_db.max(), ref_lat),
                min(lons_db.min(), ref_lon), max(lons_db.max(), ref_lon),
            ))
        else:
            raise ValueError("param_p452.profile_source must be 'mesh' or 'grid'")
        land_cover = GridRaster(self.resolve_input(p452_params.clutter_raster)) \
            if p452_params.clutter_raster else None
        clutter_lut = height_lut(p452_params.clutter_heights) if land_cover is not None else None
        zones = GridRaster(self.resolve_input(p452_params.zone_raster)) \
            if p452_params.zone_raster else None

        profiles = []
        for lat, lon in zip(lats_db, lons_db):
            if step_m > 0:
                length_km = _great_circle_km(ref_lat, ref_lon, lat, lon)
                n = max(5, int(np.ceil(length_km * 1000.0 / step_m)) + 1)
            else:
                n = 301
            lats = np.linspace(ref_lat, lat, n)
            lons = np.linspace(ref_lon, lon, n)
            if grid is None:
                dist_km, height_m = mesh.elevation_profile(ref_lat, ref_lon, lat, lon, n=n, method="nearest")
                dist_km = np.asarray(dist_km, dtype=float)
                height_m = np.asarray(height_m, dtype=float)
            else:
                height_m = grid.sample(lats, lons, "bilinear")
                dist_km = np.concatenate([
                    [0.0], np.cumsum(_great_circle_km(lats[:-1], lons[:-1], lats[1:], lons[1:])),
                ])
            if np.isnan(height_m).any():
                raise ValueError(
                    f"ParametersDatabase: the terrain profile to ({lat}, {lon}) has "
                    f"{int(np.isnan(height_m).sum())} points without data")

            clutter_m = None
            if land_cover is not None:
                classes = np.clip(land_cover.sample(lats, lons, "nearest", fill=0).astype(int), 0, 255)
                # no clutter within 50 m of either terminal (P.452-18 eq. 6e)
                away = (dist_km >= 0.05) & (dist_km <= dist_km[-1] - 0.05)
                away[0] = away[-1] = False
                clutter_m = height_m + np.where(away, clutter_lut[classes], 0.0)
            zone = None
            if zones is not None:
                zone = zones.sample(lats, lons, "nearest", fill=2).astype(float)
                zone[(zone < 1) | (zone > 3)] = 2
            profiles.append({"dist_km": dist_km, "height_m": height_m, "clutter_m": clutter_m, "zone": zone})
        return profiles

    def compute_terrain(
        self, ref_lat: float, ref_lon: float, p452_params,
        frequency_ghz: Optional[float] = None,
    ):
        """Ground altitudes and, optionally, P.452 losses over the real terrain.

        Adds to the database the columns cota_terreno (ground altitude of each
        site, m), distancekm_to_ref and, when frequency_ghz is given,
        path_loss_p452 (dB), and keeps the ground altitude at the reference
        point (reference_ground). All of them come from the same bare-terrain
        profiles.

        The P.452 loss of each BS is computed with the BS as the transmitter:
        the profile is reversed so that it starts at the BS, whose antenna
        height is param_p452.Hte, or the altura column with hte_from_db. It is
        computed once, without antenna gains and with a single draw of any
        random component of the model (percentage_p RANDOM, P.2108 clutter).

        Parameters
        ----------
        ref_lat, ref_lon : float
            Reference point (the victim station) [deg].
        p452_params : ParametersP452
            P.452 parameters and profile options.
        frequency_ghz : float, optional
            Frequency of the P.452 losses [GHz]; None computes only the
            ground altitudes.
        """
        profiles = self.terrain_profiles(ref_lat, ref_lon, p452_params)
        self._data_full["cota_terreno"] = np.array([p["height_m"][-1] for p in profiles])
        self._data_full["distancekm_to_ref"] = np.array([p["dist_km"][-1] for p in profiles])
        self._reference_ground = float(profiles[0]["height_m"][0])
        if frequency_ghz is None:
            return

        import copy
        from sharc.propagation.propagation_clear_air_452 import PropagationClearAir

        heights = self._data_full["altura"].to_numpy(dtype=float) if p452_params.hte_from_db else None
        rng = np.random.RandomState(42)
        losses = np.empty(len(profiles))
        for i, prof in enumerate(profiles):
            params = copy.copy(p452_params)
            # reversed: index 0 is the BS (the transmitter "t" of P.452)
            dist_km = prof["dist_km"]
            params.terrain_d = dist_km[-1] - dist_km[::-1]
            params.terrain_h = prof["height_m"][::-1].copy()
            if prof["clutter_m"] is not None:
                params.terrain_g = prof["clutter_m"][::-1].copy()
            if prof["zone"] is not None:
                params.terrain_zone = prof["zone"][::-1].copy()
                params.Dct, params.Dcr = PropagationClearAir.coast_distances(
                    params.terrain_d, params.terrain_zone)
            if heights is not None:
                params.Hte = float(heights[i])
            loss = PropagationClearAir(rng, params).get_loss(
                np.array([dist_km[-1]]), np.array([frequency_ghz]), np.array([False]),
                np.array([0.0]), np.array([0.0]), np.array([0.0]),
            )
            losses[i] = float(np.ravel(loss)[0])
        self._data_full["path_loss_p452"] = losses
