# Parameters for the IMT MSS-DC topology.
from dataclasses import dataclass, field
import numpy as np
import typing
from pathlib import Path
import geopandas as gpd

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_orbit import ParametersOrbit

SHARC_ROOT_DIR = (Path(__file__) / ".." / ".." / ".." / "..").resolve()

@dataclass
class ParametersSectorPositioning(ParametersBase):
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

    __ALLOWED_TYPES = [
        "ANGLE_FROM_SUBSATELLITE",
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
    ]

    type: typing.Literal[
        "ANGLE_FROM_SUBSATELLITE",
        "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE",
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
            case _:
                raise NotImplementedError(
                    f"No validation implemented for {ctx}.type = {self.type}"
                )

@dataclass
class ParametersSelectActiveSatellite(ParametersBase):
    @dataclass
    class ParametersLatLongInsideCountry(ParametersBase):
        country_shapes_filename: Path = SHARC_ROOT_DIR / "sharc"/"topology"/"countries"/"ne_110m_admin_0_countries.shp"

        # may load automatically for different shapefiles
        __ALLOWED_COUNTRY_NAMES = []

        __ALLOWED_COORDINATE_REFERENCES = [
            # it is a WGS84 based coordinate system that only contains (lat, long) information
            # which should be more than enough to describe any country borders or desired shape
            "EPSG:4326"
        ]

        country_name: str = None
        # margin from inside of border [km]
        # if positive, makes border smaller by x km
        # if negative, makes border bigger by x km
        margin_from_border: float = 0.0

        # geometry after file processing
        country_geometry = None

        already_validated = False

        def validate(self, ctx):
            if self.already_validated:
                return
            self.already_validated = True

            if self.country_name is None:
                raise ValueError(
                    f"{ctx}.country_name was not set, but is needed!"
                )

            f = gpd.read_file(self.country_shapes_filename, columns=["NAME"])
            if f.geometry.crs not in self.__ALLOWED_COORDINATE_REFERENCES:
                raise ValueError(
                    f"Shapefile at {ctx}.country_shapes_filename = {self.country_shapes_filename}\n"
                    f"does not use one of the allowed formats {self.__ALLOWED_COORDINATE_REFERENCES},"
                    "with points as (lat, long).\n"
                    "If for some reason you really want to use another projection for this parameter\n"
                    "Add the projection so that this error isn't triggered"
                )
            if "NAME" not in f:
                raise ValueError(
                    f"Shapefile at {ctx}.country_shapes_filename = {self.country_shapes_filename}\n"
                    "does not contains a 'NAME' column, so it cannot be read"
                )
            self.__ALLOWED_COUNTRY_NAMES = list(f["NAME"])

            # preload country projection
            country_proj = f[f["NAME"] == self.country_name]

            # NOTE: if country_proj is a GeoDataFrame instead of a polygon undesired behaviour will follow
            # for that reason we can use union_all()
            self.country_geometry = country_proj["geometry"].geometry.union_all()

            if self.country_name not in self.__ALLOWED_COUNTRY_NAMES:
                raise ValueError(
                    f"{ctx}.country_name == {self.country_name} but shapefile only contains data on\n"
                    f"{self.__ALLOWED_COUNTRY_NAMES}"
                )

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

    center_beam_positioning: ParametersSectorPositioning = field(default_factory=ParametersSectorPositioning)

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

        super().validate(ctx)

