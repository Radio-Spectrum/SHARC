# -*- coding: utf-8 -*-
"""Real-terrain path profiles from SRTM ``.hgt`` tiles for the ITU-R P.1812 model.

This module reads standard SRTM elevation tiles (``.hgt``, big-endian 16-bit
signed integers, square grids of 1201x1201 for SRTM3 / 3 arc-second or
3601x3601 for SRTM1 / 1 arc-second) directly with NumPy, and samples terrain
height profiles along the great-circle path between two geographic points.

Tile naming follows the usual SRTM convention based on the south-west corner of
the 1-degree cell, e.g. ``S24W047.hgt`` covers latitudes -24..-23 and
longitudes -47..-46.

No external SRTM library is required. ``pyproj`` (already a project dependency)
is used to place equally-spaced points along the WGS84 geodesic.
"""
import io
import os
import warnings
import zipfile
import urllib.request

import numpy as np

# SRTM void / no-data marker
_SRTM_VOID = -32768

# Default no-authentication source for SRTMGL1 (1 arc-second, ~30 m) tiles.
# The ``{tile}`` placeholder is replaced by the tile base name, e.g. "S24W047".
_DEFAULT_DOWNLOAD_URL = "https://step.esa.int/auxdata/dem/SRTMGL1/{tile}.SRTMGL1.hgt.zip"


class SRTMReader:
    """Read SRTM ``.hgt`` tiles and build terrain height profiles.

    Parameters
    ----------
    srtm_directory : str
        Directory containing the ``.hgt`` tiles.
    missing_tile_as_zero : bool, optional
        If ``True`` (default), elevation queries that fall on a missing tile or
        on a void sample return 0 m (sea level) and a one-time warning is
        emitted. If ``False``, a missing tile raises ``FileNotFoundError``.
    auto_download : bool, optional
        If ``True``, tiles missing from ``srtm_directory`` are downloaded on
        demand from ``download_url_template`` and cached locally. Default
        ``False`` (offline / read-only).
    download_url_template : str, optional
        URL template for downloading a tile; ``{tile}`` is replaced by the tile
        base name (e.g. ``"S24W047"``). Defaults to the ESA STEP SRTMGL1 mirror,
        which serves zipped ``.hgt`` tiles without authentication.
    download_timeout : float, optional
        Per-request timeout in seconds for downloads (default 60).
    """

    def __init__(
        self,
        srtm_directory: str,
        missing_tile_as_zero: bool = True,
        auto_download: bool = False,
        download_url_template: str = "",
        download_timeout: float = 60.0,
    ):
        self.srtm_directory = srtm_directory
        self.missing_tile_as_zero = missing_tile_as_zero
        self.auto_download = auto_download
        self.download_url_template = download_url_template or _DEFAULT_DOWNLOAD_URL
        self.download_timeout = download_timeout
        # Cache of loaded tiles: (lat_floor, lon_floor) -> (np.ndarray NxN, N) or None
        self._tiles = {}
        self._warned_tiles = set()
        # Tiles for which a download was already attempted and failed
        self._failed_downloads = set()

        if srtm_directory and not os.path.isdir(srtm_directory):
            if auto_download:
                os.makedirs(srtm_directory, exist_ok=True)
            else:
                warnings.warn(
                    f"SRTMReader: directory '{srtm_directory}' does not exist; "
                    "all elevations will be treated as 0 m (sea level).",
                )

    @staticmethod
    def _tile_base(lat_floor: int, lon_floor: int) -> str:
        """Build the SRTM tile base name (no extension) for the cell's SW corner."""
        ns = "N" if lat_floor >= 0 else "S"
        ew = "E" if lon_floor >= 0 else "W"
        return f"{ns}{abs(lat_floor):02d}{ew}{abs(lon_floor):03d}"

    @classmethod
    def _tile_name(cls, lat_floor: int, lon_floor: int) -> str:
        """Build the SRTM ``.hgt`` filename for the cell with the given SW corner."""
        return cls._tile_base(lat_floor, lon_floor) + ".hgt"

    def _download_tile(self, lat_floor: int, lon_floor: int) -> bool:
        """Download a missing tile into ``srtm_directory``; return True on success.

        Supports both zipped (``.zip`` containing a ``.hgt``) and raw ``.hgt``
        download URLs. Network or extraction failures are reported as warnings
        and never raise.
        """
        key = (lat_floor, lon_floor)
        if key in self._failed_downloads:
            return False

        tile = self._tile_base(lat_floor, lon_floor)
        url = self.download_url_template.format(tile=tile)
        dest = os.path.join(self.srtm_directory, tile + ".hgt")

        try:
            os.makedirs(self.srtm_directory, exist_ok=True)
            request = urllib.request.Request(
                url, headers={"User-Agent": "SHARC-P1812/1.0"},
            )
            with urllib.request.urlopen(request, timeout=self.download_timeout) as resp:
                payload = resp.read()
        except Exception as exc:  # noqa: BLE001 - network errors are non-fatal
            self._failed_downloads.add(key)
            warnings.warn(
                f"SRTMReader: failed to download tile {tile} from '{url}': {exc}. "
                "Using 0 m (sea level) for points in this cell.",
            )
            return False

        try:
            is_zip = url.lower().endswith(".zip") or payload[:2] == b"PK"
            if is_zip:
                with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                    members = [n for n in zf.namelist() if n.lower().endswith(".hgt")]
                    if not members:
                        raise ValueError("no .hgt member found in downloaded archive")
                    with zf.open(members[0]) as src, open(dest, "wb") as out:
                        out.write(src.read())
            else:
                with open(dest, "wb") as out:
                    out.write(payload)
        except Exception as exc:  # noqa: BLE001
            self._failed_downloads.add(key)
            warnings.warn(
                f"SRTMReader: failed to extract downloaded tile {tile}: {exc}.",
            )
            return False

        return os.path.isfile(dest)

    def _load_tile(self, lat_floor: int, lon_floor: int):
        """Load (and cache) the tile covering the given 1-degree cell.

        Returns
        -------
        tuple or None
            ``(data, N)`` where ``data`` is an NxN int array of elevations and
            ``N`` is the grid size, or ``None`` if the tile is unavailable.
        """
        key = (lat_floor, lon_floor)
        if key in self._tiles:
            return self._tiles[key]

        path = os.path.join(self.srtm_directory, self._tile_name(lat_floor, lon_floor))
        if not os.path.isfile(path) and self.srtm_directory and self.auto_download:
            self._download_tile(lat_floor, lon_floor)
        if not self.srtm_directory or not os.path.isfile(path):
            self._tiles[key] = None
            return None

        raw = np.fromfile(path, dtype=">i2")
        n = int(round(np.sqrt(raw.size)))
        if n * n != raw.size:
            warnings.warn(
                f"SRTMReader: tile '{path}' has unexpected size {raw.size}; ignoring.",
            )
            self._tiles[key] = None
            return None

        data = raw.reshape((n, n)).astype(np.float64)
        self._tiles[key] = (data, n)
        return self._tiles[key]

    def _warn_missing(self, lat_floor: int, lon_floor: int):
        """Emit a one-time warning for a missing tile."""
        key = (lat_floor, lon_floor)
        if key not in self._warned_tiles:
            self._warned_tiles.add(key)
            warnings.warn(
                f"SRTMReader: tile {self._tile_name(lat_floor, lon_floor)} not found in "
                f"'{self.srtm_directory}'; using 0 m (sea level) for points in this cell.",
            )

    def elevation(self, lat: float, lon: float) -> float:
        """Return the bilinearly-interpolated terrain elevation (m) at a point.

        Parameters
        ----------
        lat, lon : float
            Geographic coordinates in degrees (WGS84).

        Returns
        -------
        float
            Elevation above mean sea level in metres (0 m where data is missing).
        """
        lat_floor = int(np.floor(lat))
        lon_floor = int(np.floor(lon))

        tile = self._load_tile(lat_floor, lon_floor)
        if tile is None:
            if not self.missing_tile_as_zero:
                raise FileNotFoundError(
                    f"SRTM tile {self._tile_name(lat_floor, lon_floor)} not found in "
                    f"'{self.srtm_directory}'.",
                )
            self._warn_missing(lat_floor, lon_floor)
            return 0.0

        data, n = tile

        # Fractional grid position. Row 0 is the northernmost line (lat_floor + 1).
        row_f = (1.0 - (lat - lat_floor)) * (n - 1)
        col_f = (lon - lon_floor) * (n - 1)

        row_f = min(max(row_f, 0.0), n - 1)
        col_f = min(max(col_f, 0.0), n - 1)

        r0 = int(np.floor(row_f))
        c0 = int(np.floor(col_f))
        r1 = min(r0 + 1, n - 1)
        c1 = min(c0 + 1, n - 1)

        fr = row_f - r0
        fc = col_f - c0

        v00 = data[r0, c0]
        v01 = data[r0, c1]
        v10 = data[r1, c0]
        v11 = data[r1, c1]

        # Replace voids with 0 m before interpolating
        vals = np.array([v00, v01, v10, v11])
        vals[vals <= _SRTM_VOID] = 0.0
        v00, v01, v10, v11 = vals

        top = v00 * (1 - fc) + v01 * fc
        bottom = v10 * (1 - fc) + v11 * fc
        return float(top * (1 - fr) + bottom * fr)

    def path_profile(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        n_points: int,
    ):
        """Build a terrain profile along the great-circle path between two points.

        Parameters
        ----------
        lat1, lon1 : float
            Transmitter coordinates (degrees).
        lat2, lon2 : float
            Receiver coordinates (degrees).
        n_points : int
            Number of profile points (>= 4 as required by the P.1812 model).

        Returns
        -------
        tuple
            ``(d_km, h_m)`` with the cumulative distance (km) and terrain
            elevation (m) at each of the ``n_points`` samples.
        """
        from pyproj import Geod

        n_points = max(int(n_points), 4)
        geod = Geod(ellps="WGS84")

        _, _, dist_m = geod.inv(lon1, lat1, lon2, lat2)

        if dist_m <= 0.0:
            # Degenerate (coincident) endpoints: build a minimal flat profile.
            h0 = self.elevation(lat1, lon1)
            d_km = np.linspace(0.0, 1e-3, n_points)
            return d_km, np.full(n_points, h0)

        # Equally-spaced intermediate points along the geodesic
        inter = geod.npts(lon1, lat1, lon2, lat2, n_points - 2)
        lons = np.array([lon1] + [p[0] for p in inter] + [lon2])
        lats = np.array([lat1] + [p[1] for p in inter] + [lat2])

        d_km = np.linspace(0.0, dist_m / 1000.0, n_points)
        h_m = np.array([self.elevation(la, lo) for la, lo in zip(lats, lons)])

        return d_km, h_m
