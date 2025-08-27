from dataclasses import dataclass
from sharc.parameters.parameters_base import ParametersBase
from warnings import warn


@dataclass
class ParametersOrbit(ParametersBase):
    """
    Parameters for satellite orbit configuration, including planes, satellites per plane, and orbital elements.
    """
    n_planes: int = 8
    sats_per_plane: int = 6
    phasing_deg: float = 7.5
    long_asc_deg: float = 0.0
    omega_deg: float = 0.0
    inclination_deg: float = 52.0
    perigee_alt_km: float = 1414.0
    apogee_alt_km: float = 1414.0
    initial_mean_anomaly: float = 0.0

    # by default, three time dependant angles are set to be
    # independent random variables.
    # You can model time as the only random variable instead
    # by setting this parameter to True
    model_time_as_random_variable: bool = False

    # You may specify a time range lower bound [s]
    t_min: float = 0.0

    # You may specify a time range upper bound [s]
    # or let a default be chosen where needed
    t_max: float = None

    def load_parameters_from_file(self, config_file: str):
        """Load parameters from file and validate."""
        super().load_parameters_from_file(config_file)

        self.validate("ParametersOrbit")

    def validate(self, ctx: str):
        """
        Validate the orbit parameters for correctness.

        Parameters
        ----------
        ctx : str
            Context string for error messages.
        Raises
        ------
        ValueError
            If any parameter is invalid.
        """
        if not (0 <= self.inclination_deg <= 180):
            raise ValueError(
                f"Invalid {ctx}.inclination_deg = {
                    self.inclination_deg}. \
                             Must be in the range [0, 180] degrees.")
        if self.perigee_alt_km < 0:
            raise ValueError(
                f"Invalid {ctx}.perigee_alt_km = {
                    self.perigee_alt_km}. \
                             Altitude must be non-negative.")
        if self.apogee_alt_km < self.perigee_alt_km:
            raise ValueError(
                f"Invalid {ctx}.apogee_alt_km = {
                    self.apogee_alt_km}. \
                             Must be greater than or equal to perigee_alt_km.")
        if not (0 <= self.phasing_deg <= 360):
            raise ValueError(
                f"Invalid {ctx}.phasing_deg = {
                    self.phasing_deg}. \
                             Must be in the range [0, 360] degrees.")

        if self.enable_time_as_only_random_variable:
            if self.t_max is None:
                warn(
                    f"{ctx}.t_max was not set. Default values will be used when needed"
                )
            else:
                if self.t_max < self.t_min:
                    raise ValueError(f"{ctx}.t_max should be >= {ctx}.t_min")
            if self.t_min < 0:
                raise ValueError(f"{ctx}.t_min should be >= 0")

        if not self.enable_time_as_only_random_variable:
            # check that defaults haven't been changed
            if self.t_max != ParametersOrbit.t_max:
                raise ValueError(
                    f"You should only set {ctx}.t_max "
                    f"if {ctx}.enable_time_as_only_random_variable is set to True"
                )
            if self.t_min != ParametersOrbit.t_min:
                raise ValueError(
                    f"You should only set {ctx}.t_min "
                    f"if {ctx}.enable_time_as_only_random_variable is set to True"
                )
