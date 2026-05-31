from warnings import warn
from dataclasses import dataclass, field
import numpy as np
import typing
from pathlib import Path
import shapely as shp
from collections.abc import Iterable

from sharc.support.sharc_utils import load_gdf
from sharc.support.sharc_geom import (
    shrink_countries_by_km,
    generate_grid_in_multipolygon,
    shrink_lonlat_polygon_by_km,
)
from sharc.satellite.utils.sat_utils import lla2ecef
from sharc.parameters.parameters_base import ParametersBase

SHARC_ROOT_DIR = (Path(__file__) / ".." / ".." / ".." / "..").resolve()


@dataclass
class ParametersZone(ParametersBase):
    """Defines parameters for the creation of a 'zone' polygon.
    """
    @dataclass
    class ParametersCircle(ParametersBase):
        center_lat: typing.Optional[float] = None
        center_lon: typing.Optional[float] = None
        radius_km: typing.Optional[float] = None

        _polygon: shp.Polygon = None

        def validate(self, ctx):
            """
            Validates instance parameters.

            Ensures attributes make sense

            Parameters
            ----------
            ctx : str
                Context string for error messages.

            Raises
            ------
            ValueError
                If a parameter is not valid.
            """
            if None in [
                self.center_lat,
                self.center_lon,
                self.radius_km,
            ]:
                raise ValueError(
                    f"{ctx}.(center_lat|center_lon|radius_km) need to be set"
                )

            if self.radius_km <= 0:
                raise ValueError(f"{ctx}.radius_km needs to be positive")

            if not (-180. <= self.center_lon <= 180.):
                raise ValueError(f"{ctx}.center_lon needs to be in [-180, 180]")

            if not (-90. <= self.center_lat <= 90.):
                raise ValueError(f"{ctx}.center_lat needs to be in [-90, 90]")

            super().validate(ctx)

            self._calculate_polygon()

        def _calculate_polygon(self):
            """
            Calculates circle lon,lat polygon according to its attributes
            """
            self._polygon = shrink_lonlat_polygon_by_km(
                shp.geometry.Point(self.center_lon, self.center_lat),
                -self.radius_km
            )

    @dataclass
    class ParametersFromCountries(ParametersBase):
        country_shapes_filename: Path = SHARC_ROOT_DIR / "sharc" / \
            "data" / "countries" / "ne_110m_admin_0_countries.shp"

        country_names: list[str] = field(default_factory=lambda: list([""]))
        # margin from inside of border [km]
        # if positive, makes border smaller by x km
        # if negative, makes border bigger by x km
        margin_from_border: float = None

        _polygon: shp.Polygon = None
        _unprocessed_polygon: shp.Polygon = None

        def validate(self, ctx):
            """
            Validates instance parameters.
            Raises ValueError
                If a parameter is not valid.
            """
            # conditional is weird due to suboptimal way of working with nested
            # array parameters
            if len(self.country_names) == 0 or (
                    len(self.country_names) == 1 and self.country_names[0] == ""):
                raise ValueError(
                    f"You need to pass at least one country name to {ctx}.country_names")

            if not isinstance(
                    self.margin_from_border,
                    float) and not isinstance(
                    self.margin_from_border,
                    int):
                raise ValueError(
                    f"{ctx}.margin_from_border needs to be a number")

            self._calculate_polygon()

        def _calculate_polygon(self):
            filtered_gdf = load_gdf(
                self.country_shapes_filename,
                {
                    "NAME": self.country_names
                },
                "from_countries",
            )

            # shrink countries and unite
            # them into a single MultiPolygon
            self._unprocessed_polygon = filtered_gdf.geometry.values

            shrinked = shrink_countries_by_km(
                filtered_gdf.geometry.values, self.margin_from_border
            )
            self._polygon = shp.ops.unary_union(shrinked)

            assert self._polygon.is_valid, \
                shp.validation.explain_validity(self._polygon)

            assert not self._polygon.is_empty, \
                "Can't have a empty grid_borders_polygon as filter"

    __ALLOWED_TYPES = [None, "CIRCLE", "FROM_COUNTRIES"]
    _ACCEPT_NONE_TYPE: bool = False

    type: typing.Literal[None, "CIRCLE", "FROM_COUNTRIES"] = None

    circle: ParametersCircle = field(default_factory=ParametersCircle)

    from_countries: ParametersFromCountries = field(default_factory=ParametersFromCountries)

    _polygon: shp.geometry.Polygon = None
    _unprocessed_polygon: shp.geometry.Polygon = None

    def _set_chosen_pol(self):
        self.chosen_pol = None
        if self.type is None:
            return

        if self.type == "CIRCLE":
            self.chosen_pol = self.circle
        elif self.type == "FROM_COUNTRIES":
            self.chosen_pol = self.from_countries
        else:
            raise NotImplementedError(
                f"Cannot set chosen_pol for type == '{self.type}'"
            )

        self._polygon = self.chosen_pol._polygon
        if hasattr(self.chosen_pol, "_unprocessed_polygon"):
            self._unprocessed_polygon = self.chosen_pol._unprocessed_polygon
        else:
            self._unprocessed_polygon = self.chosen_pol._polygon

    def validate(self, ctx):
        """
        Validates instance parameters.

        Ensures attributes make sense

        Parameters
        ----------
        ctx : str
            Context string for error messages.

        Raises
        ------
        ValueError
            If a parameter is not valid.
        """
        if self.type not in self.__ALLOWED_TYPES:
            raise ValueError(f"{ctx}.type should be in {self.__ALLOWED_TYPES}")

        if self.type is None:
            return

        if self.type == "CIRCLE":
            self.circle.validate(f"{ctx}.circle")
        elif self.type == "FROM_COUNTRIES":
            self.from_countries.validate(f"{ctx}.from_countries")
        else:
            raise NotImplementedError(
                "No validation implemented for\n"
                f"\t{ctx}.type == {self.type}"
            )

        self._set_chosen_pol()
        self._calculate_polygon()

        if (not self._polygon.is_valid
            or self._polygon.is_empty
            or self._polygon.area <= 0
        ):
            raise Exception(f"Bad {ctx}._polygon was generated")

    def _calculate_polygon(self):
        self._set_chosen_pol()

        if self.chosen_pol is None:
            if self._ACCEPT_NONE_TYPE:
                return
            raise ValueError("No polygon type has been set for zone")

        self.chosen_pol._calculate_polygon()
        self._polygon = self.chosen_pol._polygon
        if hasattr(self.chosen_pol, "_unprocessed_polygon"):
            self._unprocessed_polygon = self.chosen_pol._unprocessed_polygon
        else:
            self._unprocessed_polygon = self.chosen_pol._polygon

    def apply_exclusion_zone(self, lon, lat):
        """
        Returns coordinates that are not contained in polygon
        """
        if self.type is None:
            return np.stack((lon, lat))

        msk = ~shp.vectorized.contains(
            self._polygon,
            lon,
            lat,
        )

        return np.stack((lon[msk], lat[msk]))


@dataclass
class ParametersTerrestrialGrid(ParametersBase):
    """Defines parameters for the creation of a (lon, lat) grid considering
    spherical Earth.
    """
    cell_radius: float = None

    transform_grid_randomly: bool = False

    grid_exclusion_zone: ParametersZone = field(
        default_factory=lambda: ParametersZone(_ACCEPT_NONE_TYPE=True)
    )

    grid_in_zone: ParametersZone = field(
        default_factory=lambda: ParametersZone(type="FROM_COUNTRIES")
    )

    # 2xN, ([lon], [lat])
    lon_lat_grid = None

    def validate(self, ctx: str):
        """
        Validate the service grid parameters.

        Ensures that country names and beam radius are set and valid, and sets grid margin if needed.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        # NOTE: prefer this to be set by a parent/composition
        if not isinstance(
                self.cell_radius,
                float) and not isinstance(
                self.cell_radius,
                int):
            raise ValueError(f"{ctx}.cell_radius needs to be a number")

        if self.grid_in_zone.from_countries.margin_from_border is None:
            self.grid_in_zone.from_countries.margin_from_border = self.cell_radius / 1e3
        if self.grid_exclusion_zone.from_countries.margin_from_border is None:
            self.grid_exclusion_zone.from_countries.margin_from_border = self.cell_radius / 1e3

        super().validate(ctx)

        self._recalculate_grid_polygon_if_needed(ctx)

    def reset_grid(
        self,
        ctx: str,
        rng: np.random.RandomState,
        force_update=False,
    ):
        """
        After creating grid, there are some features that can only be implemented
        with knowledge of other parts of the simulator.
        """
        needed = self._recalculate_grid_polygon_if_needed(ctx, force_update)

        if needed or force_update:
            lon, lat = generate_grid_in_multipolygon(
                self.grid_in_zone._polygon,
                self.cell_radius,
                self.transform_grid_randomly,
                rng
            )

            self.lon_lat_grid = self.grid_exclusion_zone.apply_exclusion_zone(
                lon, lat
            )

            self.ecef_grid = lla2ecef(
                self.lon_lat_grid[1], self.lon_lat_grid[0], 0)

    def _recalculate_grid_polygon_if_needed(self, ctx: str, force_update=False) -> bool:
        if self.grid_in_zone._polygon is not None and not force_update:
            return False
        self.grid_in_zone._calculate_polygon()
        self.grid_exclusion_zone._calculate_polygon()
        return True


@dataclass
class ParametersSatelliteWithServiceGrid(ParametersTerrestrialGrid):
    """
    Adds parameters for satellite that uses terrestrial service grid for positioning
    """
    # margin from inside of border [km]
    # if positive, makes border smaller by x km
    # if negative, makes border bigger by x km
    eligible_sats_margin_from_border: float = None

    eligibility_polygon: typing.Union[shp.MultiPolygon, shp.Polygon] = None

    beam_radius: float = None

    # [deg]
    minimum_service_angle: float = 5.0

    def validate(self, ctx):
        """Validates instance parameters.
        Parameters
            ctx : str
                Context string for error messages.
        Raises ValueError
            If a parameter is not valid.
        """
        if self.cell_radius is not None:
            warn(
                f"{ctx}.cell_radius should be set through beam_radius parameter"
            )
        self.cell_radius = self.beam_radius

        if self.minimum_service_angle < 0. or self.minimum_service_angle > 90:
            raise ValueError(f"{ctx}.minimum_service_angle should be in [0, 90]")

        if not isinstance(
                self.eligible_sats_margin_from_border,
                float) and not isinstance(
                self.eligible_sats_margin_from_border,
                int):
            raise ValueError(
                f"{ctx}.eligible_sats_margin_from_border needs to be a number")

        super().validate(ctx)

    def load_from_active_sat_conditions(
        self,
        sat_is_active_if: "ParametersSelectActiveSatellite",
    ):
        """
        Load grid parameters from active satellite selection conditions.

        Parameters
        ----------
        sat_is_active_if : ParametersSelectActiveSatellite
            The object containing satellite selection and country information.
        """
        if (
            len(self.grid_in_zone.from_countries.country_names) == 0
            or self.grid_in_zone.from_countries.country_names[0] == ""
        ):
            self.grid_in_zone.from_countries.country_names = sat_is_active_if.lat_long_inside_country.country_names
        if self.eligible_sats_margin_from_border is None:
            self.eligible_sats_margin_from_border = sat_is_active_if.lat_long_inside_country.margin_from_border

    def _recalculate_grid_polygon_if_needed(self, ctx: str, force_update=False):
        if self.eligibility_polygon is not None and not force_update:
            return False
        self.grid_in_zone._calculate_polygon()
        self.grid_exclusion_zone._calculate_polygon()

        # For creating selectable satellite zone
        # we consider polygon before shrinking country borders or other
        # geometry processing
        pols = self.grid_in_zone._unprocessed_polygon

        if not isinstance(pols, Iterable):
            pols = [pols]

        self.eligibility_polygon = shp.ops.unary_union(shrink_countries_by_km(
            pols,
            self.eligible_sats_margin_from_border,
        ))

        assert self.eligibility_polygon.is_valid, \
            shp.validation.explain_validity(self.eligibility_polygon)

        assert not self.eligibility_polygon.is_empty, \
            "Can't have a empty eligibility_polygon as filter"

        return True


@dataclass
class ParametersSelectActiveSatellite(ParametersBase):
    """
    Parameters for selecting active satellites based on geographic and elevation criteria.
    """
    @dataclass
    class ParametersLatLongInsideCountry(ParametersBase):
        """
        Parameters for checking if a location is inside a given country.
        """
        country_shapes_filename: Path = SHARC_ROOT_DIR / "sharc" / \
            "data" / "countries" / "ne_110m_admin_0_countries.shp"

        country_names: list[str] = field(default_factory=lambda: list([""]))

        # margin from inside of border [km]
        # if positive, makes border smaller by x km
        # if negative, makes border bigger by x km
        margin_from_border: float = 0.0

        # geometry after file processing
        filter_polygon: typing.Union[shp.MultiPolygon, shp.Polygon] = None

        def validate(self, ctx: str):
            """
            Validate the country names and filter polygon for the location check.

            Parameters
            ----------
            ctx : str
                Context string for error messages.
            """
            # conditional is weird due to suboptimal way of working with nested
            # array parameters
            if len(self.country_names) == 0 or (
                    len(self.country_names) == 1 and self.country_names[0] == ""):
                raise ValueError(
                    f"You need to pass at least one country name to {ctx}.country_names")

            self.reset_filter_polygon(ctx)

        def reset_filter_polygon(self, ctx: str, force_update=False):
            """
            Reset the filter polygon for country boundaries, optionally forcing update.

            Parameters
            ----------
            ctx : str
                Context string for error messages.
            force_update : bool, optional
                If True, force update even if already set (default is False).
            """
            if self.filter_polygon is not None and not force_update:
                return

            filtered_gdf = load_gdf(
                self.country_shapes_filename,
                {
                    "NAME": self.country_names
                },
                ctx,
            )

            # shrink countries and unite
            # them into a single MultiPolygon
            self.filter_polygon = shp.ops.unary_union(shrink_countries_by_km(
                filtered_gdf.geometry.values, self.margin_from_border
            ))

            assert self.filter_polygon.is_valid, shp.validation.explain_validity(
                self.filter_polygon)

    __ALLOWED_CONDITIONS = [
        "LAT_LONG_INSIDE_COUNTRY",
        "MINIMUM_ELEVATION_FROM_ES",
        "MAXIMUM_ELEVATION_FROM_ES",
    ]

    conditions: list[typing.Literal[
        "LAT_LONG_INSIDE_COUNTRY",
        "MINIMUM_ELEVATION_FROM_ES",
        "MAXIMUM_ELEVATION_FROM_ES",
    ]] = field(default_factory=lambda: list([""]))

    minimum_elevation_from_es: float = None

    maximum_elevation_from_es: float = None

    lat_long_inside_country: ParametersLatLongInsideCountry = field(
        default_factory=ParametersLatLongInsideCountry)

    def validate(self, ctx):
        """
        Validate the satellite selection conditions and their parameters.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        if "LAT_LONG_INSIDE_COUNTRY" in self.conditions:
            self.lat_long_inside_country.validate(
                f"{ctx}.lat_long_inside_country")

        if "MINIMUM_ELEVATION_FROM_ES" in self.conditions:
            if not isinstance(
                    self.minimum_elevation_from_es,
                    float) and not isinstance(
                    self.minimum_elevation_from_es,
                    int):
                raise ValueError(
                    f"{ctx}.minimum_elevation_from_es is not a number!"
                )
            if not (-90 <= self.minimum_elevation_from_es < 90):
                raise ValueError(
                    f"{ctx}.minimum_elevation_from_es needs to be a number in interval [-90, 90)")

        if "MAXIMUM_ELEVATION_FROM_ES" in self.conditions:
            if not isinstance(
                    self.maximum_elevation_from_es,
                    float) and not isinstance(
                    self.maximum_elevation_from_es,
                    int):
                raise ValueError(
                    f"{ctx}.maximum_elevation_from_es is not a number!"
                )
            if not (-90 <= self.maximum_elevation_from_es < 90):
                raise ValueError(
                    f"{ctx}.maximum_elevation_from_es needs to be a number in interval [-90, 90)")
            if "MINIMUM_ELEVATION_FROM_ES" in self.conditions:
                if self.maximum_elevation_from_es < self.minimum_elevation_from_es:
                    raise ValueError(
                        f"{ctx}.maximum_elevation_from_es needs to be >= {ctx}.minimum_elevation_from_es")

        if len(self.conditions) == 1 and self.conditions[0] == "":
            self.conditions.pop()

        if any(cond not in self.__ALLOWED_CONDITIONS for cond in self.conditions):
            raise ValueError(
                f"{ctx}.conditions = {
                    self.conditions}\n" f"However, only the following are allowed: {
                    self.__ALLOWED_CONDITIONS}")

        if len(set(self.conditions)) != len(self.conditions):
            raise ValueError(
                f"{ctx}.conditions = {self.conditions}\n"
                "And it contains duplicate values!"
            )
