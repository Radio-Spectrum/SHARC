# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from dataclasses import fields, field
import pandas as pd
from typing import List, Dict, Type, Any, Optional, Tuple
import numpy as np
import math

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_p452 import ParametersP452
from sharc.parameters.database.parameters_database_imt_antenna import AntennaParamsFromFile
from sharc.parameters.database.parameters_database_topology_countries import TopologyCountriesParamsFromFile
from sharc.propagation.real_terrain import download_terrain, download_clutter
from sharc.propagation.real_terrain import build_adaptive_mesh, RealAdaptiveMesh

ALLOWED_FORMATS = ['.csv', '.xlsx']
ALLOWED_DELIMITERS = ['\t',',','|']

from dataclasses import dataclass
from typing import Optional
from sharc.parameters.parameters_base import ParametersBase

@dataclass
class TerrainParams(ParametersBase):
    """Parameters related to real terrain and adaptive mesh."""
    ref_gpkg: Optional[str] = None
    mesh_resolution_m: float = 100.0
    mesh_urban_res_m: int = 30
    mesh_suburban_res_m: int = 150
    mesh_rural_res_m: int = 500
    mesh_water: str = "coarse"
    mesh_output_dir: str = "data"

    def validate(self, ctx: str = "terrain_params"):
        super().validate(ctx)

        # 1. mesh_resolution_m (must be a positive number)
        if not isinstance(self.mesh_resolution_m, (int, float)):
            raise ValueError(f"{ctx}.mesh_resolution_m must be a number")
        if self.mesh_resolution_m <= 0:
            raise ValueError(
                f"{ctx}.mesh_resolution_m must be positive (got {self.mesh_resolution_m})"
            )

        # 2. Urban, suburban, rural resolutions (must be positive integers)
        for res_name, res_val in [
            ("mesh_urban_res_m", self.mesh_urban_res_m),
            ("mesh_suburban_res_m", self.mesh_suburban_res_m),
            ("mesh_rural_res_m", self.mesh_rural_res_m),
        ]:
            if not isinstance(res_val, int):
                raise ValueError(
                    f"{ctx}.{res_name} must be an integer (got {type(res_val).__name__})"
                )
            if res_val <= 0:
                raise ValueError(
                    f"{ctx}.{res_name} must be positive (got {res_val})"
                )

        # 4. mesh_water must be one of the allowed values
        allowed_water = ["coarse", "exclude"]  # from adaptive_mesh documentation
        if self.mesh_water not in allowed_water:
            raise ValueError(
                f"{ctx}.mesh_water must be one of {allowed_water} (got {self.mesh_water})"
            )

        # 5. mesh_output_dir must be a non-empty string
        if not isinstance(self.mesh_output_dir, str):
            raise ValueError(f"{ctx}.mesh_output_dir must be a string")
        if not self.mesh_output_dir.strip():
            raise ValueError(f"{ctx}.mesh_output_dir cannot be empty")

        # 6. ref_gpkg can be None or a string (no further validation)
        if self.ref_gpkg is not None and not isinstance(self.ref_gpkg, str):
            raise ValueError(f"{ctx}.ref_gpkg must be a string or None")

@dataclass
class Database:
    """Database loader and holder for simulation parameters."""

    database_file_name: str = "./database.csv"
    delimiter: str = ","
    expected_columns: Optional[Dict[str, Type]] = None

    # DataFrames: full database and current subset
    database_df_full: pd.DataFrame = field(default_factory=pd.DataFrame, init=False)
    database_df: pd.DataFrame = field(default_factory=pd.DataFrame, init=False)


    def __post_init__(self) -> None:
        """Initialize empty DataFrames."""
        self.database_df_full = pd.DataFrame()
        self.database_df = pd.DataFrame()

    def load_parameters_from_database(self) -> "Database":
        """Load parameters from the database file (CSV or Excel) and validate columns.

        Returns
        -------
        Database
            Self instance for method chaining.

        Raises
        ------
        ValueError
            If file format is not supported, file is missing, or required columns are absent.
        FileNotFoundError
            If the database file does not exist.
        """
        self._validate_file_exists()
        self._read_file_based_on_extension()
        self._normalize_column_names()
        self._validate_required_columns()
        self._filter_to_expected_columns()
        return self

    # ----------------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------------
    def _validate_file_exists(self) -> None:
        """Check if the database file exists."""
        path = Path(self.database_file_name).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Database file not found: {path}")
        self.database_file_name = str(path)

    def _read_file_based_on_extension(self) -> None:
        """Read CSV or Excel file based on file extension."""
        file_path = self.database_file_name
        if file_path.lower().endswith('.csv'):
            self.database_df_full = pd.read_csv(file_path, delimiter=self.delimiter)
        elif file_path.lower().endswith('.xlsx'):
            self.database_df_full = pd.read_excel(file_path)
        else:
            raise ValueError(
                f"Unsupported file format: {file_path}. Must be .csv or .xlsx"
            )

    def _normalize_column_names(self) -> None:
        """Convert all column names to lowercase for consistency."""
        self.database_df_full.columns = self.database_df_full.columns.str.lower()

    def _validate_required_columns(self) -> None:
        """Raise an error if any expected column is missing from the DataFrame."""
        expected_cols = set(self.expected_columns.keys())
        actual_cols = set(self.database_df_full.columns)
        missing = expected_cols - actual_cols
        if missing:
            raise ValueError(
                f"Missing required columns in database file: {sorted(missing)}"
            )

    def _filter_to_expected_columns(self) -> None:
        """Keep only the columns that are expected (defined in the parameter classes)."""
        expected_cols = list(self.expected_columns.keys())
        self.database_df_full = self.database_df_full[expected_cols]

@dataclass
class ParametersDatabase(ParametersBase):
    """Dataclass containing the parameters for database loading."""

    section_name: str = "database"

    # Database file name
    database_file_name: Optional[str] = None

    # Database load flag
    database_loaded: bool = False

    # Database instance
    database: Database = field(init=False)

    # Database delimiter (only for CSV)
    delimiter: str = ","

    # Number of parts into which the base is divided
    num_subsets: int = 1

    # Chunk size (automatically computed)
    chunks_size: int = 100

    # Full IMT antenna parameters list
    db_imt_antenna_params_full: List[AntennaParamsFromFile] = field(init=False)

    # Current subset IMT antenna parameters
    db_imt_antenna_params: List[AntennaParamsFromFile] = field(init=False)

    # Flags for topology/antenna data sources
    from_db_topology_countries: bool = False
    from_db_antenna_params: bool = False

    # Bounding box (min_lat, max_lat, min_lon, max_lon)
    bounding_box: Optional[tuple] = field(init=False, default=None)

    # Flag to enable real terrain (adaptive mesh)
    use_real_terrain: bool = False

    # Parameters related to real terrain and adaptive mesh
    terrain: TerrainParams = field(default_factory=TerrainParams)

    # Internal cached mesh object
    _adaptive_mesh: Optional[Any] = field(init=False, default=None)

    def load_parameters_from_file(self, config_file: str) -> None:
        """Load parameters from a configuration file and run sanity checks.

        Parameters
        ----------
        config_file : str
            Path to the configuration file.

        Raises
        ------
        ValueError
            If any parameter is invalid.
        """
        super().load_parameters_from_file(config_file)
        if self.database_file_name:
            self._load_database_from_file()
        else:
            raise ValueError(
                f"ParametersDatabase: Database file name not defined."
            )

    @classmethod
    def from_direct_params(cls, database_file_name: str, delimiter: str = ",", **kwargs):
        """Cria instância diretamente a partir de parâmetros, sem YAML."""
        instance = cls(**kwargs)
        instance.database_file_name = database_file_name
        instance.delimiter = delimiter
        instance._load_database_from_file()
        return instance

    # ----------------------------------------------------------------------
    # Private helper methods
    # ----------------------------------------------------------------------
    def _load_database_from_file(self):

        self._validate_and_prepare_database_file()
        expected = self._get_expected_columns()
        self._load_database(expected)
        self._prepare_antenna_parameters()
        self._compute_bounding_box()
        self.get_adaptive_mesh()
        self._setup_chunking_and_first_subset()
        
    def _validate_and_prepare_database_file(self) -> None:
        """Resolve the database file path and validate its existence and format."""
        self.database_file_name = str(Path(self.database_file_name).expanduser().resolve(strict=False))
        self.delimiter = self.delimiter.encode().decode("unicode_escape")

        db_path = Path(self.database_file_name)

        if not db_path.is_file():
            raise ValueError(
                f"ParametersDatabase: Could not find the database file {self.database_file_name}"
            )

        if db_path.suffix.lower() not in ALLOWED_FORMATS:
            raise ValueError(
                f"ParametersDatabase: The database format must be one of {ALLOWED_FORMATS}."
            )

        if self.delimiter.upper() not in ALLOWED_DELIMITERS:
            raise ValueError(f"ParametersGeneral: Invalid database delimiter '{self.delimiter}'")

    def _load_database(self, expected: Dict[str, Type]) -> None:
        """Instantiate and load the database from the file."""
        self.database = Database(self.database_file_name, self.delimiter, expected_columns=expected).load_parameters_from_database()
        self.database_loaded = True

    def _prepare_antenna_parameters(self) -> None:
        """Build the full list of IMT antenna parameters from the database."""
        if self.from_db_antenna_params:
            col_labels_types_imt_ant = {f.name.lower(): f.type for f in fields(AntennaParamsFromFile)}
            # Keep only columns that exist in the AntennaParamsFromFile class
            ant_params_df = self.database.database_df_full[col_labels_types_imt_ant.keys()]
            self.db_imt_antenna_params_full = [
                AntennaParamsFromFile(**row) for row in ant_params_df.to_dict("records")
            ]

    def _setup_chunking_and_first_subset(self) -> None:
        """Compute chunk size and point to the first subset."""
        total_rows = len(self.database.database_df_full)
        self.chunks_size = math.ceil(total_rows / self.num_subsets)
        self.point_to_ith_subset(0)

    def _get_expected_columns(self) -> Dict[str, Type]:
        """Return a mapping of expected column names to their required types,
        based on the active flags."""
        col_sets = []
        if self.from_db_antenna_params:
            col_sets.append({f.name.lower(): f.type for f in fields(AntennaParamsFromFile)})
        if self.from_db_topology_countries:
            col_sets.append({f.name.lower(): f.type for f in fields(TopologyCountriesParamsFromFile)})

        expected = {}
        for cs in col_sets:
            expected.update(cs)
        return expected

    def _compute_bounding_box(self) -> None:
        """Calculate the minimum bounding box (lat/lon) from the full database."""
        if self.database_loaded and not self.database.database_df_full.empty:
            df = self.database.database_df_full
            if 'latitude' in df.columns and 'longitude' in df.columns:
                min_lat = df['latitude'].min()
                max_lat = df['latitude'].max()
                min_lon = df['longitude'].min()
                max_lon = df['longitude'].max()
                self.bounding_box = (min_lat, max_lat, min_lon, max_lon)
            else:
                self.bounding_box = None
        else:
            self.bounding_box = None

    def __repr__(self) -> str:
        """Technical representation for debugging."""
        attrs = [
            f"database_file_name={self.database_file_name!r}",
            f"delimiter={self.delimiter!r}",
            f"num_subsets={self.num_subsets}",
            f"chunks_size={self.chunks_size}",
            f"from_db_topology_countries={self.from_db_topology_countries}",
            f"from_db_antenna_params={self.from_db_antenna_params}",
            f"database_loaded={self.database_loaded}",
        ]
        if self.database_loaded:
            df_full = self.database.database_df_full
            attrs.append(f"database_full_shape={df_full.shape}")
            attrs.append(f"database_current_shape={self.database.database_df.shape}")
            if hasattr(self, 'db_imt_antenna_params_full'):
                attrs.append(f"num_antenna_params_full={len(self.db_imt_antenna_params_full)}")
            if hasattr(self, 'db_imt_antenna_params'):
                attrs.append(f"num_antenna_params_current={len(self.db_imt_antenna_params)}")
        if self.bounding_box is not None:
            attrs.append(f"bounding_box={self.bounding_box}")

        attrs.append(f"use_real_terrain={self.use_real_terrain}")
        attrs.append(f"terrain={self.terrain}")
        if self._adaptive_mesh is not None:
            attrs.append("adaptive_mesh_loaded=True")

        return f"{self.__class__.__name__}({', '.join(attrs)})"

    def __str__(self) -> str:
        """User-friendly representation."""
        lines = [
            "ParametersDatabase:",
            f"  Database file: {self.database_file_name}",
            f"  Delimiter: {self.delimiter}",
            f"  Number of subsets: {self.num_subsets}",
            f"  Chunk size: {self.chunks_size}",
            "  Flags:",
            f"    from_db_topology_countries: {self.from_db_topology_countries}",
            f"    from_db_antenna_params: {self.from_db_antenna_params}",
        ]
        if self.database_loaded:
            df_full = self.database.database_df_full
            lines.append(f"  Database loaded: Yes")
            lines.append(f"    Total rows: {len(df_full)}")
            lines.append(f"    Total columns: {len(df_full.columns)}")
            lines.append(f"    Current subset rows: {len(self.database.database_df)}")
            if self.database.expected_columns:
                lines.append(f"    Expected columns: {list(self.database.expected_columns.keys())}")
            if hasattr(self, 'db_imt_antenna_params_full'):
                lines.append(f"    Antenna parameters (full): {len(self.db_imt_antenna_params_full)}")
            if hasattr(self, 'db_imt_antenna_params'):
                lines.append(f"    Antenna parameters (current): {len(self.db_imt_antenna_params)}")
        else:
            lines.append("  Database loaded: No")

        lines.append(f"  Use real terrain: {self.use_real_terrain}")
        if self.use_real_terrain:
            lines.append(f"  Reference GPKG: {self.terrain.ref_gpkg or 'Not set (will be built)'}")
            if self._adaptive_mesh is not None:
                lines.append("  Adaptive mesh: loaded")
            else:
                lines.append("  Adaptive mesh: not loaded yet")
            lines.append("  Mesh resolution settings:")
            lines.append(f"    Base resolution: {self.terrain.mesh_resolution_m} m")
            lines.append(f"    Urban: {self.terrain.mesh_urban_res_m} m")
            lines.append(f"    Suburban: {self.terrain.mesh_suburban_res_m} m")
            lines.append(f"    Rural: {self.terrain.mesh_rural_res_m} m")
        else:
            lines.append("  Adaptive mesh: disabled")

        if self.bounding_box is not None:
            min_lat, max_lat, min_lon, max_lon = self.bounding_box
            lines.append("  Bounding box:")
            lines.append(f"    Latitude : [{min_lat:.6f}, {max_lat:.6f}]")
            lines.append(f"    Longitude: [{min_lon:.6f}, {max_lon:.6f}]")
        else:
            lines.append("  Bounding box: Not available")

        return "\n".join(lines)

    # ----------------------------------------------------------------------
    # Public subset selection
    # ----------------------------------------------------------------------
    def point_to_ith_subset(self, blk_i: int) -> None:
        """Select the i-th subset of the database and antenna parameters.

        Parameters
        ----------
        blk_i : int
            Subset index (0-based).
        """
        start = blk_i * self.chunks_size
        end = (blk_i + 1) * self.chunks_size
        self.database.database_df = self.database.database_df_full.iloc[start:end]
        if self.from_db_antenna_params:
            self.db_imt_antenna_params = self.db_imt_antenna_params_full[start:end]

    def get_adaptive_mesh(self) -> Optional[Any]:
        """
        Get the adaptive mesh object.

        If use_real_terrain is False, returns None.
        If ref_gpkg is set, loads the existing GeoPackage.
        Otherwise, builds a new adaptive mesh from terrain and clutter data,
        stores the gpkg path in ref_gpkg, and caches the mesh object.

        Returns
        -------
        RealAdaptiveMesh or None
            The mesh object, or None if real terrain is disabled.
        """
        if not self.use_real_terrain:
            return None

        if self._adaptive_mesh is not None:
            return self._adaptive_mesh

        # If ref_gpkg is provided, load it
        if self.terrain.ref_gpkg:
            gpkg_path = Path(self.terrain.ref_gpkg).expanduser().resolve()
            if not gpkg_path.is_file():
                raise FileNotFoundError(f"Reference GeoPackage not found: {gpkg_path}")
            self._adaptive_mesh = RealAdaptiveMesh(str(gpkg_path))
            return self._adaptive_mesh

        # Otherwise, build a new mesh
        if self.bounding_box is None:
            raise ValueError("Cannot build mesh without bounding_box (latitude/longitude columns missing).")

        min_lat, max_lat, min_lon, max_lon = self.bounding_box
        output_dir = Path(self.terrain.mesh_output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filenames based on bbox and resolution
        bbox_str = f"{min_lon:.4f}_{min_lat:.4f}_{max_lon:.4f}_{max_lat:.4f}"
        res_int = int(self.terrain.mesh_resolution_m)
        terrain_path = output_dir / f"terrain_{bbox_str}_{res_int}m.tif"
        clutter_path = output_dir / f"clutter_{bbox_str}_{res_int}m.tif"
        mesh_path = output_dir / f"mesh_{bbox_str}.gpkg"

        # Download terrain if needed
        if not terrain_path.is_file():
            print(f"Downloading terrain for bbox {self.bounding_box} at {self.terrain.mesh_resolution_m}m ...")
            download_terrain(
                bbox=(min_lon, min_lat, max_lon, max_lat),
                resolution_m=self.terrain.mesh_resolution_m,
                out_path=str(terrain_path),
                verbose=True
            )
        else:
            print(f"Terrain already exists: {terrain_path}")

        # Download clutter if needed
        if not clutter_path.is_file():
            print(f"Downloading clutter for bbox {self.bounding_box} at {self.terrain.mesh_resolution_m}m ...")
            download_clutter(
                bbox=(min_lon, min_lat, max_lon, max_lat),
                resolution_m=self.terrain.mesh_resolution_m,
                out_path=str(clutter_path),
                like_path=str(terrain_path),
                verbose=True
            )
        else:
            print(f"Clutter already exists: {clutter_path}")

        # Build adaptive mesh if needed
        if not mesh_path.is_file():
            print(f"Building adaptive mesh with urban={self.terrain.mesh_urban_res_m}m, "
                  f"suburban={self.terrain.mesh_suburban_res_m}m, rural={self.terrain.mesh_rural_res_m}m ...")
            build_adaptive_mesh(
                terrain_path=str(terrain_path),
                clutter_path=str(clutter_path),
                out_path=str(mesh_path),
                mesh_res_m={
                    "urban": self.terrain.mesh_urban_res_m,
                    "suburban": self.terrain.mesh_suburban_res_m,
                    "rural": self.terrain.mesh_rural_res_m
                }
            )
        else:
            print(f"Mesh already exists: {mesh_path}")

        # Store the gpkg path for future use
        self.terrain.ref_gpkg = str(mesh_path)

        # Load and cache the mesh
        self._adaptive_mesh = RealAdaptiveMesh(str(mesh_path))
        return self._adaptive_mesh
    
    def expand_bounding_box_to_point(self, lat: float, lon: float) -> None:
        """
        Extend the bounding box to include a new point (lat, lon).
        If the point is already inside the bounding box, nothing happens.
        Otherwise, the bounding box is expanded and the adaptive mesh is rebuilt.

        Parameters
        ----------
        lat : float
            Latitude of the new point (degrees).
        lon : float
            Longitude of the new point (degrees).

        Raises
        ------
        ValueError
            If the bounding box is not initialized (database not loaded).
        """
        if lat is None or lon is None:
            raise ValueError("Latitude and longitude must be provided (got lat={}, lon={}).".format(lat, lon))

        if self.bounding_box is None:
            raise ValueError("Bounding box is not initialized. Load database first.")

        min_lat, max_lat, min_lon, max_lon = self.bounding_box

        new_min_lat = min(min_lat, lat)
        new_max_lat = max(max_lat, lat)
        new_min_lon = min(min_lon, lon)
        new_max_lon = max(max_lon, lon)

        # Check if bounding box actually changed
        if (new_min_lat == min_lat and new_max_lat == max_lat and
            new_min_lon == min_lon and new_max_lon == max_lon):
            return  # point is already inside

        # Update bounding box
        self.bounding_box = (new_min_lat, new_max_lat, new_min_lon, new_max_lon)

        # Reset mesh-related cached data to force rebuild
        self._adaptive_mesh = None
        self.terrain.ref_gpkg = None

        # Rebuild mesh with the expanded bounding box (if real terrain is enabled)
        if self.use_real_terrain:
            self.get_adaptive_mesh()

    def compute_profiles_to_reference(
        self,
        ref_lat: float,
        ref_lon: float,
        n: int = 301,
        method: str = "nearest"
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Compute elevation profiles from a reference point to all database points.

        Parameters
        ----------
        ref_lat : float
            Latitude of the reference point (degrees).
        ref_lon : float
            Longitude of the reference point (degrees).
        n : int, default=301
            Number of sample points along each profile.
        method : str, default="nearest"
            Interpolation method for elevation sampling: "nearest" or "linear".

        Returns
        -------
        List[Tuple[np.ndarray, np.ndarray]]
            List of (distance_km, elevation_m) tuples, one per database point.
            Distance arrays are 1D (n,) in km, elevation arrays are 1D (n,) in metres.
            If a point is outside the mesh or over nodata, the profile may contain NaNs.

        Raises
        ------
        ValueError
            If real terrain is disabled, mesh not loaded, database lacks lat/lon,
            or reference point is outside the database bounding box.
        """
        if not self.use_real_terrain:
            raise ValueError("Real terrain is disabled (use_real_terrain=False). Cannot compute profiles.")

        mesh = self.get_adaptive_mesh()
        if mesh is None:
            raise ValueError("Adaptive mesh could not be loaded or built.")

        # Ensure database is loaded and has lat/lon
        if not self.database_loaded:
            raise ValueError("Database not loaded. Call _load_database_from_file() first.")

        df = self.database.database_df_full
        if 'latitude' not in df.columns or 'longitude' not in df.columns:
            raise ValueError("Database missing 'latitude' and/or 'longitude' columns.")

        # Check if reference point is within the database bounding box
        if self.bounding_box is not None:
            min_lat, max_lat, min_lon, max_lon = self.bounding_box
            if not (min_lat <= ref_lat <= max_lat and min_lon <= ref_lon <= max_lon):
                raise ValueError(
                    f"Reference point ({ref_lat}, {ref_lon}) is outside the database bounding box "
                    f"[{min_lat:.4f}, {max_lat:.4f}] x [{min_lon:.4f}, {max_lon:.4f}]"
                )
        else:
            pass

        # Extract coordinates as numpy arrays
        lats = df['latitude'].to_numpy()
        lons = df['longitude'].to_numpy()

        profiles = []
        for lat, lon in zip(lats, lons):
            dist_km, elev_m = mesh.elevation_profile(ref_lat, ref_lon, lat, lon, n=n, method=method)
            profiles.append((dist_km, elev_m))

        return profiles

    def compute_path_losses_p452(
        self,
        ref_lat: float,
        ref_lon: float,
        frequency_ghz: float,
        p452_params: ParametersP452,
        n_profile_points: int = 301,
        profile_method: str = "nearest",
    ) -> np.ndarray:
        """
        Compute ITU-R P.452 path losses from a reference point to all database points.

        Parameters
        ----------
        ref_lat, ref_lon : float
            Coordinates of the reference point (degrees).
        p452_params : ParametersP452
            Fully configured P.452 parameters object (frequency, gains, polarization, etc.).
        n_profile_points : int, default 301
            Number of sample points per elevation profile.
        profile_method : str, default "nearest"
            Interpolation method for elevation profiles ("nearest" or "linear").
        add_to_df : bool, default True
            If True, adds the losses as a new column to the main database DataFrame.
        loss_column_name : str, default "path_loss_p452"
            Name of the column to add to the DataFrame.

        Returns
        -------
        np.ndarray
            1D array of path losses (dB) for each database point, in the same order
            as the database rows.

        Raises
        ------
        ValueError
            If real terrain is disabled, mesh not loaded, or database lacks coordinates.
        """
        if ref_lat is None or ref_lon is None:
            raise ValueError("Latitude and longitude must be provided (got lat={}, lon={}).".format(ref_lat, ref_lon))

        # 1. Get elevation profiles
        profiles = self.compute_profiles_to_reference(
            ref_lat, ref_lon, n=n_profile_points, method=profile_method
        )

        # 2. Prepare a random number generator for PropagationClearAir
        rng = np.random.RandomState(42)

        losses = []
        distancekm_to_ref = []
        for dist_km, elev_m in profiles:
            # Create a copy of the parameters to set terrain_d/h without modifying original
            import copy

            model_params = copy.copy(p452_params)
            model_params.terrain_d = dist_km
            model_params.terrain_h = elev_m
            
            # Instantiate the propagation model
            from sharc.propagation.propagation_clear_air_452 import PropagationClearAir
            prop = PropagationClearAir(rng, model_params)

            # Prepare input arrays for a single link
            total_dist_km = dist_km[-1]
            distance = np.array([[total_dist_km]])
            frequency = np.array([[frequency_ghz]])
            indoor = np.array([[False]])
            elevation_arr = np.array([[0.0]])
            tx_gain_arr = np.array([[0.0]])
            rx_gain_arr = np.array([[0.0]])

            loss_matrix = prop.get_loss(
                distance, frequency, indoor, elevation_arr,
                tx_gain_arr, rx_gain_arr
            )
            losses.append(float(loss_matrix[0, 0]))
            distancekm_to_ref.append(total_dist_km)

        losses = np.array(losses)
        distancekm_to_ref = np.array(distancekm_to_ref)

        if not self.database_loaded:
            raise ValueError("Database not loaded. Cannot add column.")
        # Add column to full DataFrame
        self.database.database_df_full['path_loss_p452'] = losses
        self.database.database_df_full['distancekm_to_ref'] = distancekm_to_ref
        self._setup_chunking_and_first_subset()

        return losses, distancekm_to_ref
