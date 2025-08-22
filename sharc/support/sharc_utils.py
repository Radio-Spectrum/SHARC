import numpy as np
import typing
from pathlib import Path
import geopandas as gpd

from sharc.satellite.ngso.constants import EARTH_DEFAULT_CRS


def is_float(s: str) -> bool:
    """Check if string represents a float value

    Parameters
    ----------
    s : str
        input string

    Returns
    -------
    bool
        whether the string is a float value or not
    """
    try:
        float(s)
        return True
    except ValueError:
        return False


def wrap2_180(a):
    """
    Wraps angles to the [-180, 180) range
    """
    return (a + 180) % 360 - 180


def angular_dist(a1, a2):
    """
    Returns smallest angular distance between 2 angles
    in the [0, 180] range
    """
    return np.abs(wrap2_180(a1 - a2))


def clip_angle(a, a_min, a_max):
    """
    Returns `a` if it is inside the angle range defined by [`a_min`, `a_max`]
        otherwise returns the closest bound, be it `a_min` or `a_max`
    It is assumed all angles passes are already in [-180, 180] range
    """
    outside_rng = False
    # NOTE: angle limits such as -180 + [-60, 60]
    # should be passed as wrapped around [120, -120]
    # So it is important to check for this case
    if a_min > a_max:
        if a > a_max and a < a_min:
            outside_rng = True
    else:
        # Normal interval
        if a < a_min or a > a_max:
            outside_rng = True

    # always clip to the closest bound
    if outside_rng:
        if angular_dist(a, a_min) < angular_dist(a, a_max):
            return a_min
        else:
            return a_max

    return a


def to_scalar(x):
    """Convert a numpy scalar or array to a Python scalar if possible."""
    if isinstance(x, np.ndarray):
        return x.item()  # Works for 0-D or 1-element arrays
    return x


def load_gdf(
    country_shapes_filename: typing.Union[Path, str],
    filters: dict[str, list[str]],
    err_ctx: str = "load_gdf",
) -> gpd.GeoDataFrame:
    """
    It is assumed that the shapefile is in EPSG:4326
        containing polygons specified by (lon, lat) points
        and the results are returned considering the default earth used
    Parameters:
        country_shapes_filename: path to shapefile to be read
        country_names: list of names to filter by and return
        err_ctx: error string to be used as context
    Raises ValueError using `err_ctx` as part of the error message
    """
    ALLOWED_COORDINATE_REFERENCES = [
        # it is a WGS84 based coordinate system that only contains (lon, lat) information
        # which should be more than enough to describe any country borders or desired shape
        "EPSG:4326"
    ]
    filter_names = list(filters.keys())

    f = gpd.read_file(country_shapes_filename, columns=filter_names)
    if f.geometry.crs not in ALLOWED_COORDINATE_REFERENCES:
        raise ValueError(
            f"Shapefile at {err_ctx}.country_shapes_filename = {country_shapes_filename}\n"
            f"does not use one of the allowed formats {ALLOWED_COORDINATE_REFERENCES},"
            "with points as (lat, long).\n"
            "If for some reason you really want to use another projection for this parameter\n"
            "Add the projection so that this error isn't triggered"
        )

    filtered_gdf = f
    for filter_name in filters.keys():
        if filter_name not in f:
            raise ValueError(
                f"Shapefile at {err_ctx}.country_shapes_filename = {country_shapes_filename}\n"
                f"does not contains a '{filter_name}' column, so it cannot be read"
            )
        allowed_filter_vals = list(f[filter_name])
        filter_vals = filters[filter_name]

        for filter_val in filter_vals:
            if filter_val not in allowed_filter_vals:
                raise ValueError(
                    f"{err_ctx} tries to filter polygons by '{filter_name}' == '{filter_val}',\n"
                    "but shapefile only contains data on\n"
                    f"{allowed_filter_vals}"
                )

        filtered_gdf = filtered_gdf[filtered_gdf[filter_name].isin(
            filter_vals)]

    return filtered_gdf.to_crs(EARTH_DEFAULT_CRS)
