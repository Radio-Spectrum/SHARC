# Parameters for the IMT MSS-DC topology.
from dataclasses import dataclass, field
import numpy as np
import typing
from pathlib import Path
import geopandas as gpd
import shapely as shp

from sharc.support.sharc_utils import load_epsg4326_gdf
from sharc.support.sharc_geom import shrink_countries_by_km, generate_grid_in_multipolygon
from sharc.satellite.utils.sat_utils import lla2ecef
from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_orbit import ParametersOrbit

SHARC_ROOT_DIR = (Path(__file__) / ".." / ".." / ".." / "..").resolve()


@dataclass
class ParametersSectorPositioning(ParametersBase):
    """Dataclass for sector positioning parameters in the IMT MSS-DC topology."""

    @dataclass
    class ParametersSectorValue(ParametersBase):
        @dataclass
        class ParametersSectorValueDistribution(ParametersBase):
            min: float = None
            max: float = None

        __ALLOWED_TYPES = [
            "FIXED",
            "~U(MIN,MAX)",
            "~SQRT(U(0,1))*MAX",
        ]
        # # this distribution can be used when you wish to have a uniform area distribution
        # # over the area of a cone base (circle)
        # # uniform dist over area of circle is sqrt(U(0,1))*max_radius for radius dist
        # "~ATAN(SQRT(U(0,1))*TAN(MAX))",
        type: typing.Literal[
            "FIXED",
            "~U(MIN,MAX)",
            "~SQRT(U(0,1))*MAX",
        ] = "FIXED"

        MIN_VALUE: float = None
        MAX_VALUE: float = None

        fixed: float = 0.0
        distribution: ParametersSectorValueDistribution = field(default_factory=ParametersSectorValueDistribution)

        def validate(self, ctx):
            if self.type not in self.__ALLOWED_TYPES:
                raise ValueError(
                    f"{ctx}.type = {self.type} is not one of the accepted values:\n{self.__ALLOWED_TYPES}"
                )
            match self.type:
                case "FIXED":
                    if not (isinstance(self.fixed, float) or isinstance(self.fixed, int)):
                        raise ValueError(f"{ctx}.fixed must be a number")
                    if self.MIN_VALUE is not None:
                        if self.fixed < self.MIN_VALUE:
                            raise ValueError(f"{ctx}.fixed must be at least {self.MIN_VALUE}")
                    if self.MAX_VALUE is not None:
                        if self.fixed > self.MAX_VALUE:
                            raise ValueError(f"{ctx}.fixed must be at least {self.MAX_VALUE}")
                case "~U(MIN,MAX)":
                    if not (isinstance(self.distribution.min, float) or isinstance(self.distribution.max, int)):
                        raise ValueError(f"{ctx}.distribution.min must be a number")

                    if not (isinstance(self.distribution.max, float) or isinstance(self.distribution.max, int)):
                        raise ValueError(f"{ctx}.distribution.max must be a number")

                    if self.distribution.max <= self.distribution.min:
                        raise ValueError(f"{ctx}.distribution.max must be bigger than {ctx}.distribution.max")

                    if self.MIN_VALUE is not None:
                        if self.distribution.min < self.MIN_VALUE:
                            raise ValueError(f"{ctx}.distribution.min must be at least {self.MIN_VALUE}")
                        if self.distribution.max < self.MIN_VALUE:
                            raise ValueError(f"{ctx}.distribution.max must be at least {self.MIN_VALUE}")

                    if self.MAX_VALUE is not None:
                        if self.distribution.min > self.MAX_VALUE:
                            raise ValueError(f"{ctx}.distribution.min must be at least {self.MAX_VALUE}")
                        if self.distribution.max > self.MAX_VALUE:
                            raise ValueError(f"{ctx}.distribution.max must be at least {self.MAX_VALUE}")
                case _:
                    raise NotImplementedError(
                        f"No validation implemented for {ctx}.type = {self.type}"
                    )

    @dataclass
    class ParametersServiceGrid(ParametersBase):
        country_shapes_filename: Path = SHARC_ROOT_DIR / "sharc" / "data" / "countries" / "ne_110m_admin_0_countries.shp"

        country_names: list[str] = field(default_factory=lambda: list([""]))

        # margin from inside of border [km]
        # if positive, makes border smaller by x km
        # if negative, makes border bigger by x km
        grid_margin_from_border: float = None

        # margin from inside of border [km]
        # if positive, makes border smaller by x km
        # if negative, makes border bigger by x km
        eligible_sats_margin_from_border: float = None

        beam_radius: float = None

        # 2xN, ([lon], [lat])
        lon_lat_grid = None

        eligibility_polygon: typing.Union[shp.MultiPolygon, shp.Polygon] = None

        def validate(self, ctx: str):
            # conditional is weird due to suboptimal way of working with nested array parameters
            if len(self.country_names) == 0 or (len(self.country_names) == 1 and self.country_names[0] == ""):
                raise ValueError(f"You need to pass at least one country name to {ctx}.country_names")

            # NOTE: prefer this to be set by a parent/composition
            if not isinstance(self.beam_radius, float) and not isinstance(self.beam_radius, int):
                raise ValueError(f"{ctx}.beam_radius needs to be a number")

            if self.grid_margin_from_border is None:
                self.grid_margin_from_border = self.beam_radius / 1e3
            if not isinstance(self.grid_margin_from_border, float) and not isinstance(self.grid_margin_from_border, int):
                raise ValueError(f"{ctx}.grid_margin_from_border needs to be a number")

            if not isinstance(self.eligible_sats_margin_from_border, float) and not isinstance(self.eligible_sats_margin_from_border, int):
                raise ValueError(f"{ctx}.eligible_sats_margin_from_border needs to be a number")

            self.reset_grid(ctx)

            super().validate(ctx)

        def load_from_active_sat_conditions(
            self,
            sat_is_active_if: "ParametersSelectActiveSatellite",
        ):
            if len(self.country_names) == 0 or self.country_names[0] == "":
                self.country_names = sat_is_active_if.lat_long_inside_country.country_names
            if self.eligible_sats_margin_from_border is None:
                self.eligible_sats_margin_from_border = sat_is_active_if.lat_long_inside_country.margin_from_border

        def reset_grid(self, ctx: str, force_update=False):
            """
            After creating grid, there are some features that can only be implemented
            with knowledge of other parts of the simulator. This method's purpose is
            to run only once at the start of the simulation
            """
            if self.lon_lat_grid is not None and not force_update:
                return
            filtered_gdf = load_epsg4326_gdf(
                self.country_shapes_filename,
                {
                    "NAME": self.country_names
                },
                ctx,
            )

            # shrink countries and unite
            # them into a single MultiPolygon
            shrinked = shrink_countries_by_km(
                filtered_gdf.geometry.values, self.grid_margin_from_border
            )
            polygon = shp.ops.unary_union(shrinked)
            assert polygon.is_valid, shp.validation.explain_validity(polygon)
            assert not polygon.is_empty, "Can't have a empty polygon as filter"

            self.lon_lat_grid = generate_grid_in_multipolygon(
                polygon,
                self.beam_radius
            )

            self.ecef_grid = lla2ecef(self.lon_lat_grid[1], self.lon_lat_grid[0], 0)

            self.eligibility_polygon = shp.ops.unary_union(shrink_countries_by_km(
                filtered_gdf.geometry.values, self.eligible_sats_margin_from_border
            ))

    __ALLOWED_TYPES = [
        "ANGLE_FROM_SUBSATELLITE",
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
        "SERVICE_GRID",
    ]

    type: typing.Literal[
        "ANGLE_FROM_SUBSATELLITE",
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
        "SERVICE_GRID",
    ] = "ANGLE_FROM_SUBSATELLITE"

    # theta is the off axis angle from satellite nadir
    angle_from_subsatellite_theta: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue()
    )

    # phi completes polar coordinates
    # equivalent to "azimuth" from subsatellite in earth plane
    angle_from_subsatellite_phi: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue(MIN_VALUE=-180.0, MAX_VALUE=180.0)
    )

    # distance from subsatellite. Substitutes theta
    distance_from_subsatellite: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue(MIN_VALUE=0.0)
    )

    service_grid: ParametersServiceGrid = field(default_factory=ParametersServiceGrid)

    def validate(self, ctx):
        if self.type not in self.__ALLOWED_TYPES:
            raise ValueError(
                f"{ctx}.type = {self.type} is not one of the accepted values:\n{self.__ALLOWED_TYPES}"
            )
        match self.type:
            case "ANGLE_FROM_SUBSATELLITE":
                self.angle_from_subsatellite_theta.validate(f"{ctx}.angle_from_subsatellite_theta")
                self.angle_from_subsatellite_phi.validate(f"{ctx}.angle_from_subsatellite_phi")
            case "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE":
                self.angle_from_subsatellite_theta.validate(f"{ctx}.angle_from_subsatellite_theta")
            case "SERVICE_GRID":
                self.service_grid.validate(f"{ctx}.service_grid")
            case _:
                raise NotImplementedError(
                    f"No validation implemented for {ctx}.type = {self.type}"
                )


@dataclass
class ParametersSelectActiveSatellite(ParametersBase):
    @dataclass
    class ParametersLatLongInsideCountry(ParametersBase):
        country_shapes_filename: Path = \
            SHARC_ROOT_DIR / "sharc" / "data" / "countries" / "ne_110m_admin_0_countries.shp"

        country_names: list[str] = field(default_factory=lambda: list([""]))

        # margin from inside of border [km]
        # if positive, makes border smaller by x km
        # if negative, makes border bigger by x km
        margin_from_border: float = 0.0

        # geometry after file processing
        filter_polygon: typing.Union[shp.MultiPolygon, shp.Polygon] = None

        def validate(self, ctx: str):
            # conditional is weird due to suboptimal way of working with nested array parameters
            if len(self.country_names) == 0 or (len(self.country_names) == 1 and self.country_names[0] == ""):
                raise ValueError(f"You need to pass at least one country name to {ctx}.country_names")

            self.reset_filter_polygon(ctx)

        def reset_filter_polygon(self, ctx: str, force_update=False):
            if self.filter_polygon is not None and not force_update:
                return

            filtered_gdf = load_epsg4326_gdf(
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

            assert self.filter_polygon.is_valid, shp.validation.explain_validity(self.filter_polygon)

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

    lat_long_inside_country: ParametersLatLongInsideCountry = field(default_factory=ParametersLatLongInsideCountry)

    def validate(self, ctx):
        if "LAT_LONG_INSIDE_COUNTRY" in self.conditions:
            self.lat_long_inside_country.validate(f"{ctx}.lat_long_inside_country")

        if "MINIMUM_ELEVATION_FROM_ES" in self.conditions:
            if not isinstance(self.minimum_elevation_from_es, float) and not isinstance(self.minimum_elevation_from_es, int):
                raise ValueError(
                    f"{ctx}.minimum_elevation_from_es is not a number!"
                )
            if not (self.minimum_elevation_from_es >= 0 and self.minimum_elevation_from_es < 90):
                raise ValueError(
                    f"{ctx}.minimum_elevation_from_es needs to be a number in interval [0, 90]"
                )

        if "MAXIMUM_ELEVATION_FROM_ES" in self.conditions:
            if not isinstance(self.maximum_elevation_from_es, float) and not isinstance(self.maximum_elevation_from_es, int):
                raise ValueError(
                    f"{ctx}.maximum_elevation_from_es is not a number!"
                )
            if not (self.maximum_elevation_from_es >= 0 and self.maximum_elevation_from_es < 90):
                raise ValueError(
                    f"{ctx}.maximum_elevation_from_es needs to be a number in interval [0, 90]"
                )
            if "MINIMUM_ELEVATION_FROM_ES" in self.conditions:
                if self.maximum_elevation_from_es < self.minimum_elevation_from_es:
                    raise ValueError(
                        f"{ctx}.maximum_elevation_from_es needs to be >= {ctx}.minimum_elevation_from_es"
                    )

        if len(self.conditions) == 1 and self.conditions[0] == "":
            self.conditions.pop()

        if any(cond not in self.__ALLOWED_CONDITIONS for cond in self.conditions):
            raise ValueError(
                f"{ctx}.conditions = {self.conditions}\n"
                f"However, only the following are allowed: {self.__ALLOWED_CONDITIONS}"
            )

        if len(set(self.conditions)) != len(self.conditions):
            raise ValueError(
                f"{ctx}.conditions = {self.conditions}\n"
                "And it contains duplicate values!"
            )


@dataclass
class ParametersImtMssDc(ParametersBase):
    """Dataclass for the IMT MSS-DC topology parameters."""
    section_name: str = "imt_mss_dc"

    nested_parameters_enabled = True

    # MSS_D2D system name
    name: str = "SystemA"

    # Orbit parameters
    orbits: list[ParametersOrbit] = field(default_factory=lambda: [ParametersOrbit()])

    # Number of beams
    num_beams: int = 19

    # Beam radius in meters
    # The beam radius should be calculated based on the Antenna Pattern used for IMT Space Stations
    beam_radius: float = 36516.0

    sat_is_active_if: ParametersSelectActiveSatellite = field(default_factory=ParametersSelectActiveSatellite)

    beam_positioning: ParametersSectorPositioning = field(default_factory=ParametersSectorPositioning)

    def propagate_parameters(self):
        if self.beam_positioning.service_grid.beam_radius is None:
            self.beam_positioning.service_grid.beam_radius = self.beam_radius

        self.beam_positioning.service_grid.load_from_active_sat_conditions(
            self.sat_is_active_if,
        )

    def validate(self, ctx: str):
        """
        Raises
        ------
        ValueError
            If a parameter is not valid.
        """
        # Now do the sanity check for some parameters
        if self.num_beams not in [1, 7, 19]:
            raise ValueError(f"{ctx}.num_beams: Invalid number of sectors {self.num_sectors}")

        if self.beam_radius <= 0:
            raise ValueError(f"{ctx}.beam_radius: cell_radius must be greater than 0, but is {self.cell_radius}")
        else:
            self.cell_radius = self.beam_radius
            self.intersite_distance = np.sqrt(3) * self.cell_radius

        self.propagate_parameters()

        super().validate(ctx)
