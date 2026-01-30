# Parameters for the IMT MSS-DC topology.
from dataclasses import dataclass, field
import numpy as np
import typing
from pathlib import Path

from sharc.parameters.parameters_base import ParametersBase
from sharc.parameters.parameters_orbit import ParametersOrbit
from sharc.parameters.imt.parameters_grid import (
    ParametersSatelliteWithServiceGrid,
    ParametersSelectActiveSatellite,
    ParametersZone,
)

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
        distribution: ParametersSectorValueDistribution = field(
            default_factory=ParametersSectorValueDistribution)

        def validate(self, ctx):
            """
            Validate the sector value parameters.

            Ensures that the type and value constraints are satisfied for the sector value.

            Parameters
            ----------
            ctx : str
                Context string for error messages.
            """
            if self.type not in self.__ALLOWED_TYPES:
                raise ValueError(
                    f"{ctx}.type = {
                        self.type} is not one of the accepted values:\n{
                        self.__ALLOWED_TYPES}")
            match self.type:
                case "FIXED":
                    if not (
                        isinstance(
                            self.fixed,
                            float) or isinstance(
                            self.fixed,
                            int)):
                        raise ValueError(f"{ctx}.fixed must be a number")
                    if self.MIN_VALUE is not None:
                        if self.fixed < self.MIN_VALUE:
                            raise ValueError(
                                f"{ctx}.fixed must be at least {
                                    self.MIN_VALUE}")
                    if self.MAX_VALUE is not None:
                        if self.fixed > self.MAX_VALUE:
                            raise ValueError(
                                f"{ctx}.fixed must be at least {
                                    self.MAX_VALUE}")
                case "~U(MIN,MAX)":
                    if not (
                        isinstance(
                            self.distribution.min,
                            float) or isinstance(
                            self.distribution.max,
                            int)):
                        raise ValueError(
                            f"{ctx}.distribution.min must be a number")

                    if not (
                        isinstance(
                            self.distribution.max,
                            float) or isinstance(
                            self.distribution.max,
                            int)):
                        raise ValueError(
                            f"{ctx}.distribution.max must be a number")

                    if self.distribution.max <= self.distribution.min:
                        raise ValueError(
                            f"{ctx}.distribution.max must be bigger than {ctx}.distribution.max")

                    if self.MIN_VALUE is not None:
                        if self.distribution.min < self.MIN_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.min must be at least {
                                    self.MIN_VALUE}")
                        if self.distribution.max < self.MIN_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.max must be at least {
                                    self.MIN_VALUE}")

                    if self.MAX_VALUE is not None:
                        if self.distribution.min > self.MAX_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.min must be at least {
                                    self.MAX_VALUE}")
                        if self.distribution.max > self.MAX_VALUE:
                            raise ValueError(
                                f"{ctx}.distribution.max must be at least {
                                    self.MAX_VALUE}")
                case _:
                    raise NotImplementedError(
                        f"No validation implemented for {ctx}.type = {
                            self.type}")

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
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue())

    # phi completes polar coordinates
    # equivalent to "azimuth" from subsatellite in earth plane
    angle_from_subsatellite_phi: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue(
            MIN_VALUE=-180.0, MAX_VALUE=180.0))

    # distance from subsatellite. Substitutes theta
    distance_from_subsatellite: ParametersSectorValue = field(
        default_factory=lambda: ParametersSectorPositioning.ParametersSectorValue(
            MIN_VALUE=0.0))

    service_grid: ParametersSatelliteWithServiceGrid = field(
        default_factory=ParametersSatelliteWithServiceGrid)

    def validate(self, ctx):
        """
        Validate the sector positioning parameters.

        Ensures that the type and nested parameters are valid for the sector positioning configuration.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        """
        if self.type not in self.__ALLOWED_TYPES:
            raise ValueError(
                f"{ctx}.type = {
                    self.type} is not one of the accepted values:\n{
                    self.__ALLOWED_TYPES}")
        match self.type:
            case "ANGLE_FROM_SUBSATELLITE":
                self.angle_from_subsatellite_theta.validate(
                    f"{ctx}.angle_from_subsatellite_theta")
                self.angle_from_subsatellite_phi.validate(
                    f"{ctx}.angle_from_subsatellite_phi")
            case "ANGLE_AND_DISTANCE_FROM_SUBSATELLITE":
                self.angle_from_subsatellite_theta.validate(
                    f"{ctx}.angle_from_subsatellite_theta")
            case "SERVICE_GRID":
                self.service_grid.validate(f"{ctx}.service_grid")
            case _:
                raise NotImplementedError(
                    f"No validation implemented for {ctx}.type = {self.type}"
                )


@dataclass
class ParametersPowerControlZone(ParametersBase):
    """Dataclass for a power control zone in the IMT MSS-DC topology."""
    geometry: ParametersZone = field(default_factory=ParametersZone)
    power_backoff_db: float = None


@dataclass
class ParametersPowerControl(ParametersBase):
    """Dataclass for power control parameters in the IMT MSS-DC topology."""
    zones: list[ParametersPowerControlZone] = field(
        default_factory=lambda: [ParametersPowerControlZone()])

    def validate(self, ctx):
        """
        Validate the power control parameters.
        """
        super().validate(ctx)
        for i in range(len(self.zones)):
            self.zones[i].geometry.validate(ctx + f"zones.{i}.geometry")
            if not isinstance(self.zones[i].power_backoff_db, float):
                raise ValueError("power_backoff_db is not properly defined.")


@dataclass
class ParametersImtMssDc(ParametersBase):
    """Dataclass for the IMT MSS-DC topology parameters."""
    section_name: str = "imt_mss_dc"

    nested_parameters_enabled = True

    # MSS_D2D system name
    name: str = "SystemA"

    # Orbit parameters
    orbits: list[ParametersOrbit] = field(
        default_factory=lambda: [ParametersOrbit()])

    # Number of beams
    num_beams: int = 19

    # Beam radius in meters
    # The beam radius should be calculated based on the Antenna Pattern used
    # for IMT Space Stations
    beam_radius: float = 36516.0

    power_control_zones: ParametersPowerControl = field(
        default_factory=ParametersPowerControl)

    sat_is_active_if: ParametersSelectActiveSatellite = field(
        default_factory=ParametersSelectActiveSatellite)

    beam_positioning: ParametersSectorPositioning = field(
        default_factory=ParametersSectorPositioning)

    def propagate_parameters(self):
        """
        Propagate relevant parameters from the top-level configuration to nested parameter objects.

        Ensures that the service grid's beam radius and country-related parameters are set based on the main configuration.
        """
        if self.beam_positioning.service_grid.beam_radius is None:
            self.beam_positioning.service_grid.beam_radius = self.beam_radius

        self.beam_positioning.service_grid.load_from_active_sat_conditions(
            self.sat_is_active_if,
        )

    def validate(self, ctx: str):
        """
        Validate the IMT MSS DC parameters for correctness.

        Parameters
        ----------
        ctx : str
            Context string for error messages.

        Raises
        ------
        ValueError
            If a parameter is not valid.
        """
        # Now do the sanity check for some parameters
        if self.num_beams not in [1, 7, 19]:
            raise ValueError(
                f"{ctx}.num_beams: Invalid number of sectors {
                    self.num_sectors}")

        if self.beam_radius <= 0:
            raise ValueError(
                f"{ctx}.beam_radius: cell_radius must be greater than 0, but is {
                    self.cell_radius}")
        else:
            self.cell_radius = self.beam_radius
            self.intersite_distance = np.sqrt(3) * self.cell_radius

        self.propagate_parameters()

        super().validate(ctx)
