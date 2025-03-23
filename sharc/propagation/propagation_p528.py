# -*- coding: utf-8 -*-
import math
import numpy as np
from multipledispatch import dispatch
from dataclasses import dataclass, field
from typing import List, Union
from sharc.propagation.propagation import Propagation
from dataclasses import dataclass
from typing import List
import numpy as np
from sharc.station_manager import StationManager
from sharc.parameters.parameters import Parameters

# Constants
a_0__km = 6371.0
a_e__km = 9257.0
N_s = 341
epsilon_r = 15.0
sigma = 0.005
LOS_EPSILON = 0.00001
THIRD = 1.0 / 3.0

# Consts
CONST_MODE__SEARCH = 0
CONST_MODE__DIFFRACTION = 1
CONST_MODE__SCATTERING = 2

CASE_1 = 1
CASE_2 = 2

PROP_MODE__NOT_SET = 0
PROP_MODE__LOS = 1
PROP_MODE__DIFFRACTION = 2
PROP_MODE__SCATTERING = 3

# List of valid polarizations
POLARIZATION__HORIZONTAL = 0
POLARIZATION__VERTICAL = 1

Y_pi_99_INDEX = 16

# Return Codes
SUCCESS = 0
ERROR_VALIDATION__D_KM = 1
ERROR_VALIDATION__H_1 = 2
ERROR_VALIDATION__H_2 = 3
ERROR_VALIDATION__TERM_GEO = 4
ERROR_VALIDATION__F_MHZ_LOW = 5
ERROR_VALIDATION__F_MHZ_HIGH = 6
ERROR_VALIDATION__PERCENT_LOW = 7
ERROR_VALIDATION__PERCENT_HIGH = 8
ERROR_VALIDATION__POLARIZATION = 9
ERROR_HEIGHT_AND_DISTANCE = 10
WARNING__DFRAC_TROPO_REGION = 20


class PropagationP528(Propagation):
    """
    Implements the propagation model from ITU-R P.528-5.
    """

    def __init__(
        self,
        random_number_gen: np.random.RandomState,
        time_percentage: Union[str, float] = "RANDOM",
        polarization: Union[str, int] = "RANDOM",
    ):
        """Initialize the P528 propagation model."""
        super().__init__(random_number_gen)
        # Create helper objects once and reuse them
        self.terminal_1 = Terminal()
        self.terminal_2 = Terminal()
        self.tropo = TroposcatterParams()
        self.path = Path()
        self.los_params = LineOfSightParams()
        self.result = Result()
        self.default_time_percentage = time_percentage
        self.default_polarization = polarization

    @dispatch(Parameters, float, StationManager, StationManager, np.ndarray, np.ndarray)
    def get_loss(
        self,
        params: Parameters,
        frequency: float,
        station_a: StationManager,
        station_b: StationManager,
        station_a_gains=None,
        station_b_gains=None,
    ) -> np.array:
        """Calculate path loss using P528 model with SHARC framework interface."""
        # Get distances between stations
        distance_3d = station_a.get_3d_distance_to(station_b)

        # Convert distance from meters to km
        d__km = distance_3d / 1000.0

        # Create frequency array matching distance dimensions
        f__mhz = frequency * np.ones(d__km.shape)

        # Get station heights
        h_1__meter = station_a.height
        h_2__meter = station_b.height

        return self.get_loss(d__km, h_1__meter, h_2__meter, f__mhz)

    @dispatch(np.ndarray, float, float, np.ndarray)
    def get_loss(
        self,
        distance_km: np.array,
        h_1__meter: float,
        h_2__meter: float,
        frequency_mhz: np.array,
        time_percentage: Union[str, float, np.ndarray] = None,
        polarization: Union[str, int, np.ndarray] = None,
    ) -> np.array:
        """Calculate path loss using P528 model.

        Args:
            distance_km: Array of distances in km
            h_1__meter: Height of first terminal in meters
            h_2__meter: Height of second terminal in meters
            frequency_mhz: Array of frequencies in MHz
            time_percentage: Optional override for time percentage
            polarization: Optional override for polarization
        """
        results = np.zeros(distance_km.shape)

        # Use provided values or defaults
        use_time_percentage = time_percentage if time_percentage is not None else self.default_time_percentage
        use_polarization = polarization if polarization is not None else self.default_polarization

        # Generate time percentage values
        if isinstance(use_time_percentage, str) and use_time_percentage.upper() == "RANDOM":
            p_values = 1 + 98 * self.random_number_gen.random_sample(distance_km.shape)
        else:
            p_values = use_time_percentage * np.ones(distance_km.shape)

        # Generate polarization values
        if isinstance(use_polarization, str) and use_polarization.upper() == "RANDOM":
            t_values = self.random_number_gen.randint(0, 2, distance_km.shape)
        else:
            t_values = use_polarization * np.ones(distance_km.shape, dtype=int)

        # Iterate through the distance array
        for idx in np.ndindex(distance_km.shape):

            # Print progress bar
            print(idx[0])

            # Clear helper objects
            self.terminal_1.clear()
            self.terminal_2.clear()
            self.tropo.clear()
            self.path.clear()
            self.los_params.clear()
            self.result.clear()

            # Calculate path loss using P528_Ex
            result = P528_Ex(
                float(distance_km[idx]),
                float(h_1__meter),
                float(h_2__meter),
                float(frequency_mhz[idx]),
                int(t_values[idx]),
                float(p_values[idx]),
                self.result,
                self.terminal_1,
                self.terminal_2,
                self.tropo,
                self.path,
                self.los_params,
            )

            results[idx] = result.A__db

        return results


@dataclass
class Path:

    d_ML__km: float = 0.0
    d_0__km: float = 0.0
    d_d__km: float = 0.0

    def __init__(self):
        print("Creating Path Object")
        self.clear()

    def clear(self):
        self.d_ML__km: float = 0.0
        self.d_0__km: float = 0.0
        self.d_d__km: float = 0.0


@dataclass
class Terminal:
    h_r__km: float = 0.0
    h_e__km: float = 0.0
    delta_h__km: float = 0.0
    d_r__km: float = 0.0
    a__km: float = 0.0
    phi__rad: float = 0.0
    theta__rad: float = 0.0
    A_a__db: float = 0.0

    def __init__(self):
        print("Creating Terminal Object")
        self.clear()

    def clear(self):
        self.h_r__km: float = 0.0
        self.h_e__km: float = 0.0
        self.delta_h__km: float = 0.0
        self.d_r__km: float = 0.0
        self.a__km: float = 0.0
        self.phi__rad: float = 0.0
        self.theta__rad: float = 0.0
        self.A_a__db: float = 0.0


@dataclass
class LineOfSightParams:
    z__km: List[float] = field(default_factory=lambda: [0.0, 0.0])
    d__km: float = 0.0
    r_0__km: float = 0.0
    r_12__km: float = 0.0
    D__km: List[float] = field(default_factory=lambda: [0.0, 0.0])
    theta_h1__rad: float = 0.0
    theta_h2__rad: float = 0.0
    theta: List[float] = field(default_factory=lambda: [0.0, 0.0])
    a_a__km: float = 0.0
    delta_r__km: float = 0.0
    A_LOS__db: float = 0.0

    def __init__(self):
        print("Creating LineOfSighParams Object")
        self.clear()

    def clear(self):
        self.z__km: List[float] = [0.0, 0.0]
        self.d__km: float = 0.0
        self.r_0__km: float = 0.0
        self.r_12__km: float = 0.0
        self.D__km: List[float] = [0.0, 0.0]
        self.theta_h1__rad: float = 0.0
        self.theta_h2__rad: float = 0.0
        self.theta: List[float] = [0.0, 0.0]
        self.a_a__km: float = 0.0
        self.delta_r__km: float = 0.0
        self.A_LOS__db: float = 0.0


print("Creating Global LineOfSightParams")
_GLOBAL_LOS_PARAMS = LineOfSightParams()


@dataclass
class TroposcatterParams:
    d_s__km: float = 0.0
    d_z__km: float = 0.0
    h_v__km: float = 0.0
    theta_s: float = 0.0
    theta_A: float = 0.0
    A_s__db: float = 0.0
    A_s_prev__db: float = 0.0
    M_s: float = 0.0

    def __init__(self):
        print("Creating TroposcatterParams Object")
        self.clear()

    def clear(self):
        self.d_s__km: float = 0.0
        self.d_z__km: float = 0.0
        self.h_v__km: float = 0.0
        self.theta_s: float = 0.0
        self.theta_A: float = 0.0
        self.A_s__db: float = 0.0
        self.A_s_prev__db: float = 0.0
        self.M_s: float = 0.0


print("Creating Global TroposcatterParams")
_GLOBAL_TROPO_PARAMS = TroposcatterParams()


@dataclass
class Result:
    propagation_mode: int = 0
    d__km: float = 0.0
    A__db: float = 0.0
    A_fs__db: float = 0.0
    A_a__db: float = 0.0
    theta_h1__rad: float = 0.0
    result: str = ""

    def __init__(self):
        print("Creating Result Object")
        self.clear()

    def clear(self):
        self.propagation_mode: int = 0
        self.d__km: float = 0.0
        self.A__db: float = 0.0
        self.A_fs__db: float = 0.0
        self.A_a__db: float = 0.0
        self.theta_h1__rad: float = 0.0
        self.result: str = ""


@dataclass
class SlantPathAttenuationResult:
    A_gas__db: float = 0.0  # Median gaseous absorption, in dB
    bending__rad: float = 0.0  # Bending angle, in rad
    a__km: float = 0.0  # Ray length, in km
    angle__rad: float = 0.0  # Incident angle, in rad
    delta_L__km: float = 0.0  # Excess atmospheric path length, in km

    def __init__(self):
        print("Creating SlantPathAttenuationResult Object")
        self.clear()

    def clear(self):
        self.A_gas__db = 0.0
        self.bending__rad = 0.0
        self.a__km = 0.0
        self.angle__rad = 0.0
        self.delta_L__km = 0.0


print("Creating Global SlantPathAttenuationResult")
_GLOBAL_SLANT_RESULT = SlantPathAttenuationResult()

# P835.h

# Constants
RHO_0__M_KG = 7.5

# Error Codes
ERROR_HEIGHT_TOO_SMALL = -1
ERROR_HEIGHT_TOO_LARGE = -2

# P528.cpp

# Constants
PROP_MODE__NOT_SET = 0
PROP_MODE__LOS = 1
PROP_MODE__DIFFRACTION = 2
PROP_MODE__SCATTERING = 3

SUCCESS = 0
ERROR_HEIGHT_AND_DISTANCE = -1
CASE_1 = 1
CASE_2 = 2


def P528_Ex(
    d__km: float,
    h_1__meter: float,
    h_2__meter: float,
    f__mhz: float,
    T_pol: int,
    p: float,
    result: Result,
    terminal_1: Terminal,
    terminal_2: Terminal,
    tropo: TroposcatterParams,
    path: Path,
    los_params: LineOfSightParams,
):

    # reset Results struct
    result.clear()

    err = ValidateInputs(d__km, h_1__meter, h_2__meter, f__mhz, T_pol, p)

    result.result = err

    if err != "SUCCESS":
        if err == "ERROR_HEIGHT_AND_DISTANCE":
            result.A_fs__db = 0
            result.A_a__db = 0
            result.A__db = 0
            result.d__km = 0
            return result
        else:
            result.result = err
            raise ValueError(err)
            return result

    # Compute terminal geometries

    # Step 1 for low terminal
    terminal_1.h_r__km = h_1__meter / 1000
    TerminalGeometry(f__mhz, terminal_1)

    # Step 1 for high terminal
    terminal_2.h_r__km = h_2__meter / 1000
    TerminalGeometry(f__mhz, terminal_2)

    # Step 2

    path.d_ML__km = terminal_1.d_r__km + terminal_2.d_r__km  # [Eqn 3-1]

    # Smooth earth diffraction line calculations

    # Step 3.1
    d_3__km = path.d_ML__km + 0.5 * pow(pow(a_e__km, 2) / f__mhz, THIRD)  # [Eqn 3-2]
    d_4__km = path.d_ML__km + 1.5 * pow(pow(a_e__km, 2) / f__mhz, THIRD)  # [Eqn 3-3]

    # Step 3.2
    A_3__db = SmoothEarthDiffraction(terminal_1.d_r__km, terminal_2.d_r__km, f__mhz, d_3__km, T_pol)
    A_4__db = SmoothEarthDiffraction(terminal_1.d_r__km, terminal_2.d_r__km, f__mhz, d_4__km, T_pol)

    # Step 3.3
    M_d = (A_4__db - A_3__db) / (d_4__km - d_3__km)  # [Eqn 3-4]
    A_d0 = A_4__db - M_d * d_4__km  # [Eqn 3-5]

    # Step 3.4
    A_dML__db = (M_d * path.d_ML__km) + A_d0  # [Eqn 3-6]
    path.d_d__km = -(A_d0 / M_d)  # [Eqn 3-7]

    K_LOS = 0

    # Step 4. If the path is in the Line-of-Sight range, call LOS and then exit
    if path.d_ML__km - d__km > 0.001:

        result.propagation_mode = PROP_MODE__LOS
        K_LOS = LineOfSight(
            path,
            terminal_1,
            terminal_2,
            los_params,
            f__mhz,
            -A_dML__db,
            p,
            d__km,
            T_pol,
            result,
            K_LOS,
        )
        return result

    else:

        K_LOS = LineOfSight(
            path,
            terminal_1,
            terminal_2,
            los_params,
            f__mhz,
            -A_dML__db,
            p,
            path.d_ML__km - 1,
            T_pol,
            result,
            K_LOS,
        )

        # Step 6. Search past horizon to find crossover point between Diffraction and Troposcatter models
        # TranshorizonSearch(path, terminal_1, terminal_2, f__mhz, A_dML__db, M_d, A_d0,Const)
        M_d, A_d0, d_crx__km, CASE = TranshorizonSearch(path, terminal_1, terminal_2, f__mhz, A_dML__db, M_d, A_d0)
        # [rtn, M_d, A_d0, d_crx__km, CASE]

        # Compute terrain attenuation, A_T__db

        # Step 7.1
        A_d__db = M_d * d__km + A_d0  # [Eqn 3-14]

        # Step 7.2
        troposcatter(path, terminal_1, terminal_2, d__km, f__mhz, tropo)

        # Step 7.3
        if d__km < d_crx__km:
            # always in diffraction if less than d_crx
            A_T__db = A_d__db
            result.propagation_mode = PROP_MODE__DIFFRACTION
        else:
            if CASE == CASE_1:
                # select the lower loss mode of propagation
                if tropo.A_s__db <= A_d__db:
                    A_T__db = tropo.A_s__db
                    result.propagation_mode = PROP_MODE__SCATTERING
                else:
                    A_T__db = A_d__db
                    result.propagation_mode = PROP_MODE__DIFFRACTION
            else:  # CASE_2
                A_T__db = tropo.A_s__db
                result.propagation_mode = PROP_MODE__SCATTERING

        # Compute variability

        # f_theta_h is unity for transhorizon paths
        f_theta_h = 1

        # compute the 50% and p% of the long-term variability distribution
        Y_e__db, _ = LongTermVariability(
            terminal_1.d_r__km,
            terminal_2.d_r__km,
            d__km,
            f__mhz,
            p,
            f_theta_h,
            -A_T__db,
        )
        Y_e_50__db, _ = LongTermVariability(
            terminal_1.d_r__km,
            terminal_2.d_r__km,
            d__km,
            f__mhz,
            50,
            f_theta_h,
            -A_T__db,
        )

        # compute the 50% and p% of the Nakagami-Rice distribution
        ANGLE = 0.02617993878  # 1.5 deg
        if tropo.theta_s >= ANGLE:  # theta_s > 1.5 deg
            K_t__db = 20
        elif tropo.theta_s <= 0.0:
            K_t__db = K_LOS
        else:
            K_t__db = (tropo.theta_s * (20.0 - K_LOS) / ANGLE) + K_LOS

        Y_pi_50__db = 0.0  # zero mean
        Y_pi__db = NakagamiRice(K_t__db, p)

        # combine the long-term and Nakagami-Rice distributions
        Y_total__db = CombineDistributions(Y_e_50__db, Y_e__db, Y_pi_50__db, Y_pi__db, p)

        # Atmospheric absorption for transhorizon path

        result_v = SlantPathAttenuation(f__mhz / 1000, 0, tropo.h_v__km, math.pi / 2)

        result.A_a__db = terminal_1.A_a__db + terminal_2.A_a__db + 2 * result_v.A_gas__db  # [Eqn 3-17]

        # Compute free-space loss

        r_fs__km = terminal_1.a__km + terminal_2.a__km + 2 * result_v.a__km  # [Eqn 3-18]
        result.A_fs__db = 20.0 * math.log10(f__mhz) + 20.0 * math.log10(r_fs__km) + 32.45  # [Eqn 3-19]

        result.d__km = d__km
        result.A__db = result.A_fs__db + result.A_a__db + A_T__db - Y_total__db  # [Eqn 3-20]
        result.theta_h1__rad = -terminal_1.theta__rad

        return result


def ValidateInputs(d_km, h_1_meter, h_2_meter, f_mhz, t_pol, p):

    if d_km < 0:
        return "ERROR_VALIDATION__D_KM", ERROR_VALIDATION__D_KM

    if h_1_meter < 1.5 or h_1_meter > 20000:
        return "ERROR_VALIDATION__H_1", ERROR_VALIDATION__H_1

    if h_2_meter < 1.5 or h_2_meter > 20000:
        return "ERROR_VALIDATION__H_2", ERROR_VALIDATION__H_2

    if h_1_meter > h_2_meter:
        return "ERROR_VALIDATION__TERM_GEO", ERROR_VALIDATION__TERM_GEO

    if f_mhz < 100:
        return "ERROR_VALIDATION__F_MHZ_LOW", ERROR_VALIDATION__F_MHZ_LOW

    if f_mhz > 30000:
        return "ERROR_VALIDATION__F_MHZ_HIGH", ERROR_VALIDATION__F_MHZ_HIGH

    if t_pol != POLARIZATION__HORIZONTAL and t_pol != POLARIZATION__VERTICAL:
        return "ERROR_VALIDATION__POLARIZATION", ERROR_VALIDATION__POLARIZATION

    if p < 1:
        return "ERROR_VALIDATION__PERCENT_LOW", ERROR_VALIDATION__PERCENT_LOW

    if p > 99:
        return "ERROR_VALIDATION__PERCENT_HIGH", ERROR_VALIDATION__PERCENT_HIGH

    if h_1_meter == h_2_meter and d_km == 0:
        return "ERROR_HEIGHT_AND_DISTANCE"

    return "SUCCESS"


def TerminalGeometry(f__mhz: float, terminal: Terminal):
    theta_tx__rad = 0
    result = SlantPathAttenuation(f__mhz / 1000, 0, terminal.h_r__km, math.pi / 2 - theta_tx__rad)

    terminal.theta__rad = math.pi / 2 - result.angle__rad
    terminal.A_a__db = result.A_gas__db
    terminal.a__km = result.a__km

    # compute arc distance
    central_angle = (math.pi / 2 - result.angle__rad) - theta_tx__rad + result.bending__rad
    terminal.d_r__km = a_0__km * central_angle
    terminal.phi__rad = terminal.d_r__km / a_e__km
    terminal.h_e__km = (a_e__km / math.cos(terminal.phi__rad)) - a_e__km
    terminal.delta_h__km = terminal.h_r__km - terminal.h_e__km


# p835 MeanAnnualGlobalReferenceAtmosphere


def GlobalTemperature(h__km: float):
    if h__km < 0:
        raise ValueError(ERROR_HEIGHT_TOO_SMALL)
    if h__km > 100:
        raise ValueError(ERROR_HEIGHT_TOO_LARGE)
    if h__km < 86:
        h_prime__km = ConvertToGeopotentialHeight(h__km)
        return GlobalTemperature_Regime1(h_prime__km)
    else:
        return GlobalTemperature_Regime2(h__km)


def GlobalTemperature_Regime1(h_prime__km: float):
    if h_prime__km < 0:
        raise ValueError(ERROR_HEIGHT_TOO_SMALL)
    elif h_prime__km <= 11:
        return 288.15 - 6.5 * h_prime__km
    elif h_prime__km <= 20:
        return 216.65
    elif h_prime__km <= 32:
        return 216.65 + (h_prime__km - 20)
    elif h_prime__km <= 47:
        return 228.65 + 2.8 * (h_prime__km - 32)
    elif h_prime__km <= 51:
        return 270.65
    elif h_prime__km <= 71:
        return 270.65 - 2.8 * (h_prime__km - 51)
    elif h_prime__km <= 84.852:
        return 214.65 - 2.0 * (h_prime__km - 71)
    else:
        raise ValueError(ERROR_HEIGHT_TOO_LARGE)


def GlobalTemperature_Regime2(h__km: float):
    if h__km < 86:
        return ERROR_HEIGHT_TOO_SMALL
    elif h__km <= 91:
        return 186.8673
    elif h__km <= 100:
        return 263.1905 - 76.3232 * math.sqrt(1 - pow((h__km - 91) / 19.9429, 2))
    else:
        return ERROR_HEIGHT_TOO_LARGE


def GlobalPressure(h__km: float):
    if h__km < 0:
        return ERROR_HEIGHT_TOO_SMALL
    if h__km > 100:
        return ERROR_HEIGHT_TOO_LARGE

    if h__km < 86:
        h_prime__km = ConvertToGeopotentialHeight(h__km)
        return GlobalPressure_Regime1(h_prime__km)
    else:
        return GlobalPressure_Regime2(h__km)


def GlobalPressure_Regime1(h_prime__km: float):
    if h_prime__km < 0:
        return ERROR_HEIGHT_TOO_SMALL
    elif h_prime__km <= 11:
        return 1013.25 * pow(288.15 / (288.15 - 6.5 * h_prime__km), -34.1632 / 6.5)
    elif h_prime__km <= 20:
        return 226.3226 * math.exp(-34.1632 * (h_prime__km - 11) / 216.65)
    elif h_prime__km <= 32:
        return 54.74980 * pow(216.65 / (216.65 + (h_prime__km - 20)), 34.1632)
    elif h_prime__km <= 47:
        return 8.680422 * pow(228.65 / (228.65 + 2.8 * (h_prime__km - 32)), 34.1632 / 2.8)
    elif h_prime__km <= 51:
        return 1.109106 * math.exp(-34.1632 * (h_prime__km - 47) / 270.65)
    elif h_prime__km <= 71:
        return 0.6694167 * pow(270.65 / (270.65 - 2.8 * (h_prime__km - 51)), -34.1632 / 2.8)
    elif h_prime__km <= 84.852:
        return 0.03956649 * pow(214.65 / (214.65 - 2.0 * (h_prime__km - 71)), -34.1632 / 2.0)
    else:
        return ERROR_HEIGHT_TOO_LARGE


def GlobalPressure_Regime2(h__km: float):
    if h__km < 86:
        return ERROR_HEIGHT_TOO_SMALL
    if h__km > 100:
        return ERROR_HEIGHT_TOO_LARGE

    a_0 = 95.571899
    a_1 = -4.011801
    a_2 = 6.424731e-2
    a_3 = -4.789660e-4
    a_4 = 1.340543e-6

    return math.exp(a_0 + a_1 * h__km + a_2 * pow(h__km, 2) + a_3 * pow(h__km, 3) + a_4 * pow(h__km, 4))


def GlobalWaterVapourDensity(h__km: float, rho_0: float):
    if h__km < 0:
        return ERROR_HEIGHT_TOO_SMALL
    if h__km > 100:
        return ERROR_HEIGHT_TOO_LARGE

    h_0__km = 2  # scale height

    return rho_0 * math.exp(-h__km / h_0__km)


def GlobalWaterVapourPressure(h__km: float, rho_0: float):
    if h__km < 0:
        return ERROR_HEIGHT_TOO_SMALL
    if h__km > 100:
        return ERROR_HEIGHT_TOO_LARGE

    rho = GlobalWaterVapourDensity(h__km, rho_0)

    if h__km < 86:
        # convert to geopotential height
        h_prime__km = ConvertToGeopotentialHeight(h__km)
        T__kelvin = GlobalTemperature_Regime1(h_prime__km)
    else:
        T__kelvin = GlobalTemperature_Regime2(h__km)

    return WaterVapourDensityToPressure(rho, T__kelvin)


def SlantPathAttenuation(f__ghz: float, h_1__km: float, h_2__km: float, beta_1__rad: float):

    result = _GLOBAL_SLANT_RESULT
    result.clear()

    if beta_1__rad > math.pi / 2:
        # negative elevation angle
        # find h_G and then trace in each direction
        # see Section 2.2.2

        # compute refractive index at h_1
        # p__hPa = config.dry_pressure(h_1__km)
        # T__kelvin = config.temperature(h_1__km)
        # e__hPa = config.wet_pressure(h_1__km, rho_0)  # Note: rho_0 needs to be defined or passed as a parameter

        p__hPa = GlobalPressure(h_1__km)
        T__kelvin = GlobalTemperature(h_1__km)
        e__hPa = GlobalWetPressure(h_1__km)

        n_1 = RefractiveIndex(p__hPa, T__kelvin, e__hPa)

        # set initial h_G at mid-point between h_1 and surface of the earth
        # then binary search to converge
        h_G__km = h_1__km
        delta = h_1__km / 2
        diff = 100

        while abs(diff) > 0.001:
            if diff > 0:
                h_G__km -= delta
            else:
                h_G__km += delta
            delta /= 2

            # p__hPa = config.dry_pressure(h_G__km)
            # T__kelvin = config.temperature(h_G__km)
            # e__hPa = config.wet_pressure(h_G__km, rho_0)  # Note: rho_0 needs to be defined or passed as a parameter

            p__hPa = GlobalPressure(h_G__km)
            T__kelvin = GlobalTemperature(h_G__km)
            e__hPa = GlobalWetPressure(h_G__km)

            n_G = RefractiveIndex(p__hPa, T__kelvin, e__hPa)

            grazing_term = n_G * (a_0__km + h_G__km)
            start_term = n_1 * (a_0__km + h_1__km) * math.sin(beta_1__rad)

            diff = grazing_term - start_term

        # converged on h_G.  Now call RayTrace in both directions with grazing angle
        beta_graze__rad = math.pi / 2
        result_1 = RayTrace(f__ghz, h_G__km, h_1__km, beta_graze__rad)
        result_2 = RayTrace(f__ghz, h_G__km, h_2__km, beta_graze__rad)

        result.angle__rad = result_2.angle__rad

        result.A_gas__db = result_1.A_gas__db + result_2.A_gas__db
        result.a__km = result_1.a__km + result_2.a__km
        result.bending__rad = result_1.bending__rad + result_2.bending__rad
        result.delta_L__km = result_1.delta_L__km + result_2.delta_L__km
    else:
        result = RayTrace(f__ghz, h_1__km, h_2__km, beta_1__rad)
        # result = RayTrace(f__ghz, h_1__km, h_2__km, beta_1__rad, config)

    return result


def LayerThickness(m: float, i: int):
    # Equation 14
    delta_i__km = m * math.exp((i - 1) / 100.0)
    return delta_i__km


def RayTrace(f__ghz: float, h_1__km: float, h_2__km: float, beta_1__rad: float):
    # Equations 16(a)-(c)
    i_lower = math.floor(100 * math.log(1e4 * h_1__km * (math.exp(1.0 / 100.0) - 1) + 1) + 1)
    i_upper = math.ceil(100 * math.log(1e4 * h_2__km * (math.exp(1.0 / 100.0) - 1) + 1) + 1)
    m = ((math.exp(2.0 / 100.0) - math.exp(1.0 / 100.0)) / (math.exp(i_upper / 100.0) - math.exp(i_lower / 100.0))) * (
        h_2__km - h_1__km
    )

    result = _GLOBAL_SLANT_RESULT
    result.clear()

    # initialize starting layer
    delta_i__km = LayerThickness(m, i_lower)
    h_i__km = h_1__km + m * ((math.exp((i_lower - 1) / 100.0) - math.exp((i_lower - 1) / 100.0)) / (math.exp(1 / 100.0) - 1))
    n_i, gamma_i = GetLayerProperties(f__ghz, h_i__km + delta_i__km / 2)
    r_i__km = a_0__km + h_i__km

    # record bottom layer properties for alpha and beta calculations
    r_1__km = r_i__km
    n_1 = n_i

    # summation from Equation 13
    for i in range(i_lower, i_upper):
        delta_ii__km = LayerThickness(m, i + 1)
        h_ii__km = h_1__km + m * ((math.exp(i / 100.0) - math.exp((i_lower - 1) / 100.0)) / (math.exp(1 / 100.0) - 1))

        n_ii, gamma_ii = GetLayerProperties(f__ghz, h_ii__km + delta_ii__km / 2)

        r_ii__km = a_0__km + h_ii__km

        delta_i__km = LayerThickness(m, i)

        # Equation 19b
        beta_i__rad = math.asin(min(1, (n_1 * r_1__km) / (n_i * r_i__km) * math.sin(beta_1__rad)))

        # entry angle into the layer interface, Equation 18a
        alpha_i__rad = math.asin(min(1, (n_1 * r_1__km) / (n_i * r_ii__km) * math.sin(beta_1__rad)))

        # path length through ith layer, Equation 17
        a_i__km = -r_i__km * math.cos(beta_i__rad) + math.sqrt(
            r_i__km**2 * math.cos(beta_i__rad) ** 2 + 2 * r_i__km * delta_i__km + delta_i__km**2
        )

        result.a__km += a_i__km
        result.A_gas__db += a_i__km * gamma_i
        result.delta_L__km += a_i__km * (n_i - 1)  # summation, Equation 23

        beta_ii__rad = math.asin(n_i / n_ii * math.sin(alpha_i__rad))

        # summation of the bending angle, Equation 22a
        # the summation only goes to i_max - 1
        if i != i_upper - 1:
            result.bending__rad += beta_ii__rad - alpha_i__rad

        # shift for next loop
        h_i__km = h_ii__km
        n_i = n_ii
        gamma_i = gamma_ii
        r_i__km = r_ii__km

    result.angle__rad = alpha_i__rad
    return result


def GlobalWetPressure(h__km: float):
    """
    Calculate the global wet pressure at a given height.

    Args:
    h__km (float): Height in kilometers

    Returns:
    float: Wet pressure in hPa
    """
    T__kelvin = GlobalTemperature(h__km)
    P__hPa = GlobalPressure(h__km)
    rho__g_m3 = max(
        GlobalWaterVapourDensity(h__km, RHO_0__M_KG),
        2 * pow(10, -6) * 216.7 * P__hPa / T__kelvin,
    )
    e__hPa = WaterVapourDensityToPressure(rho__g_m3, T__kelvin)

    return e__hPa


def RefractiveIndex(p__hPa: float, T__kelvin: float, e__hPa: float):
    """
    Calculate the refractive index based on pressure, temperature, and water vapor pressure.

    Args:
    p__hPa (float): Pressure in hectopascals (hPa)
    T__kelvin (float): Temperature in Kelvin
    e__hPa (float): Water vapor pressure in hectopascals (hPa)

    Returns:
    float: Refractive index
    """
    # dry term of refractivity
    N_dry = 77.6 * p__hPa / T__kelvin

    # wet term of refractivity
    N_wet = 72 * e__hPa / T__kelvin + 3.75e5 * e__hPa / pow(T__kelvin, 2)

    N = N_dry + N_wet

    n = 1 + N * pow(10, -6)

    return n


def SpecificAttenuation(f__ghz: float, T__kelvin: float, e__hPa: float, p__hPa: float):
    """
    Calculate the specific attenuation due to atmospheric gases.

    Args:
    f__ghz (float): Frequency in GHz
    T__kelvin (float): Temperature in Kelvin
    e__hPa (float): Water vapor pressure in hectopascals (hPa)
    p__hPa (float): Total atmospheric pressure in hectopascals (hPa)

    Returns:
    float: Specific attenuation in dB/km
    """
    gamma_o = OxygenSpecificAttenuation(f__ghz, T__kelvin, e__hPa, p__hPa)

    gamma_w = WaterVapourSpecificAttenuation(f__ghz, T__kelvin, e__hPa, p__hPa)

    gamma = gamma_o + gamma_w  # [Eqn 1]

    return gamma


OxygenData = {
    "f_0": [
        50.474214,
        50.987745,
        51.503360,
        52.021429,
        52.542418,
        53.066934,
        53.595775,
        54.130025,
        54.671180,
        55.221384,
        55.783815,
        56.264774,
        56.363399,
        56.968211,
        57.612486,
        58.323877,
        58.446588,
        59.164204,
        59.590983,
        60.306056,
        60.434778,
        61.150562,
        61.800158,
        62.411220,
        62.486253,
        62.997984,
        63.568526,
        64.127775,
        64.678910,
        65.224078,
        65.764779,
        66.302096,
        66.836834,
        67.369601,
        67.900868,
        68.431006,
        68.960312,
        118.750334,
        368.498246,
        424.763020,
        487.249273,
        715.392902,
        773.839490,
        834.145546,
    ],
    "a_1": [
        0.975,
        2.529,
        6.193,
        14.320,
        31.240,
        64.290,
        124.600,
        227.300,
        389.700,
        627.100,
        945.300,
        543.400,
        1331.800,
        1746.600,
        2120.100,
        2363.700,
        1442.100,
        2379.900,
        2090.700,
        2103.400,
        2438.000,
        2479.500,
        2275.900,
        1915.400,
        1503.000,
        1490.200,
        1078.000,
        728.700,
        461.300,
        274.000,
        153.000,
        80.400,
        39.800,
        18.560,
        8.172,
        3.397,
        1.334,
        940.300,
        67.400,
        637.700,
        237.400,
        98.100,
        572.300,
        183.100,
    ],
    "a_2": [
        9.651,
        8.653,
        7.709,
        6.819,
        5.983,
        5.201,
        4.474,
        3.800,
        3.182,
        2.618,
        2.109,
        0.014,
        1.654,
        1.255,
        0.910,
        0.621,
        0.083,
        0.387,
        0.207,
        0.207,
        0.386,
        0.621,
        0.910,
        1.255,
        0.083,
        1.654,
        2.108,
        2.617,
        3.181,
        3.800,
        4.473,
        5.200,
        5.982,
        6.818,
        7.708,
        8.652,
        9.650,
        0.010,
        0.048,
        0.044,
        0.049,
        0.145,
        0.141,
        0.145,
    ],
    "a_3": [
        6.690,
        7.170,
        7.640,
        8.110,
        8.580,
        9.060,
        9.550,
        9.960,
        10.370,
        10.890,
        11.340,
        17.030,
        11.890,
        12.230,
        12.620,
        12.950,
        14.910,
        13.530,
        14.080,
        14.150,
        13.390,
        12.920,
        12.630,
        12.170,
        15.130,
        11.740,
        11.340,
        10.880,
        10.380,
        9.960,
        9.550,
        9.060,
        8.580,
        8.110,
        7.640,
        7.170,
        6.690,
        16.640,
        16.400,
        16.400,
        16.000,
        16.000,
        16.200,
        14.700,
    ],
    "a_4": [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ],
    "a_5": [
        2.566,
        2.246,
        1.947,
        1.667,
        1.388,
        1.349,
        2.227,
        3.170,
        3.558,
        2.560,
        -1.172,
        3.525,
        -2.378,
        -3.545,
        -5.416,
        -1.932,
        6.768,
        -6.561,
        6.957,
        -6.395,
        6.342,
        1.014,
        5.014,
        3.029,
        -4.499,
        1.856,
        0.658,
        -3.036,
        -3.968,
        -3.528,
        -2.548,
        -1.660,
        -1.680,
        -1.956,
        -2.216,
        -2.492,
        -2.773,
        -0.439,
        0.000,
        0.000,
        0.000,
        0.000,
        0.000,
        0.000,
    ],
    "a_6": [
        6.850,
        6.800,
        6.729,
        6.640,
        6.526,
        6.206,
        5.085,
        3.750,
        2.654,
        2.952,
        6.135,
        -0.978,
        6.547,
        6.451,
        6.056,
        0.436,
        -1.273,
        2.309,
        -0.776,
        0.699,
        -2.825,
        -0.584,
        -6.619,
        -6.759,
        0.844,
        -6.675,
        -6.139,
        -2.895,
        -2.590,
        -3.680,
        -5.002,
        -6.091,
        -6.393,
        -6.475,
        -6.545,
        -6.600,
        -6.650,
        0.079,
        0.000,
        0.000,
        0.000,
        0.000,
        0.000,
        0.000,
    ],
}


def OxygenRefractivity(f__ghz: float, T__kelvin: float, e__hPa: float, p__hPa: float):
    """
    Calculate the imaginary part of the frequency-dependent complex refractivity due to oxygen.

    Args:
    f__ghz (float): Frequency in GHz
    T__kelvin (float): Temperature in Kelvin
    e__hPa (float): Water vapour partial pressure in hectopascals (hPa)
    p__hPa (float): Dry air pressure in hectopascals (hPa)

    Returns:
    float: Refractivity in N-Units
    """
    theta = 300 / T__kelvin

    N = 0

    for i in range(len(OxygenData["f_0"])):
        # Equation 3, for oxygen
        S_i = OxygenData["a_1"][i] * 1e-7 * p__hPa * math.pow(theta, 3) * math.exp(OxygenData["a_2"][i] * (1 - theta))

        # compute the width of the line, Equation 6a, for oxygen
        delta_f__ghz = (
            OxygenData["a_3"][i] * 1e-4 * (p__hPa * math.pow(theta, (0.8 - OxygenData["a_4"][i])) + 1.1 * e__hPa * theta)
        )

        # modify the line width to account for Zeeman splitting of the oxygen lines
        # Equation 6b, for oxygen
        delta_f__ghz = math.sqrt(math.pow(delta_f__ghz, 2) + 2.25e-6)

        # correction factor due to interference effects in oxygen lines
        # Equation 7, for oxygen
        delta = (OxygenData["a_5"][i] + OxygenData["a_6"][i] * theta) * 1e-4 * (p__hPa + e__hPa) * math.pow(theta, 0.8)

        F_i = LineShapeFactor(f__ghz, OxygenData["f_0"][i], delta_f__ghz, delta)

        # summation of terms...from Equation 2a, for oxygen
        N += S_i * F_i

    N_D = NonresonantDebyeAttenuation(f__ghz, e__hPa, p__hPa, theta)

    N_o = N + N_D

    return N_o


def NonresonantDebyeAttenuation(f__ghz: float, e__hPa: float, p__hPa: float, theta: float):
    """
    Calculate the Non-resonant Debye component of frequency-dependent complex refractivity.

    Args:
    f__ghz (float): Frequency in GHz
    e__hPa (float): Water vapour partial pressure in hectopascals (hPa)
    p__hPa (float): Dry air pressure in hectopascals (hPa)
    theta (float): From Equation 3

    Returns:
    float: Non-resonant Debye component
    """
    # width parameter for the Debye spectrum, Equation 9
    d = 5.6e-4 * (p__hPa + e__hPa) * math.pow(theta, 0.8)

    # Equation 8
    frac_1 = 6.14e-5 / (d * (1 + math.pow(f__ghz / d, 2)))
    frac_2 = (1.4e-12 * p__hPa * math.pow(theta, 1.5)) / (1 + 1.9e-5 * math.pow(f__ghz, 1.5))
    N_D = f__ghz * p__hPa * math.pow(theta, 2) * (frac_1 + frac_2)

    return N_D


WaterVapourData = {
    "f_0": [
        22.235080,
        67.803960,
        119.995940,
        183.310087,
        321.225630,
        325.152888,
        336.227764,
        380.197353,
        390.134508,
        437.346667,
        439.150807,
        443.018343,
        448.001085,
        470.888999,
        474.689092,
        488.490108,
        503.568532,
        504.482692,
        547.676440,
        552.020960,
        556.935985,
        620.700807,
        645.766085,
        658.005280,
        752.033113,
        841.051732,
        859.965698,
        899.303175,
        902.611085,
        906.205957,
        916.171582,
        923.112692,
        970.315022,
        987.926764,
        1780.000000,
    ],
    "b_1": [
        0.1079,
        0.0011,
        0.0007,
        2.273,
        0.0470,
        1.514,
        0.0010,
        11.67,
        0.0045,
        0.0632,
        0.9098,
        0.1920,
        10.41,
        0.3254,
        1.260,
        0.2529,
        0.0372,
        0.0124,
        0.9785,
        0.1840,
        497.0,
        5.015,
        0.0067,
        0.2732,
        243.4,
        0.0134,
        0.1325,
        0.0547,
        0.0386,
        0.1836,
        8.400,
        0.0079,
        9.009,
        134.6,
        17506.0,
    ],
    "b_2": [
        2.144,
        8.732,
        8.353,
        0.668,
        6.179,
        1.541,
        9.825,
        1.048,
        7.347,
        5.048,
        3.595,
        5.048,
        1.405,
        3.597,
        2.379,
        2.852,
        6.731,
        6.731,
        0.158,
        0.158,
        0.159,
        2.391,
        8.633,
        7.816,
        0.396,
        8.177,
        8.055,
        7.914,
        8.429,
        5.110,
        1.441,
        10.293,
        1.919,
        0.257,
        0.952,
    ],
    "b_3": [
        26.38,
        28.58,
        29.48,
        29.06,
        24.04,
        28.23,
        26.93,
        28.11,
        21.52,
        18.45,
        20.07,
        15.55,
        25.64,
        21.34,
        23.20,
        25.86,
        16.12,
        16.12,
        26.00,
        26.00,
        30.86,
        24.38,
        18.00,
        32.10,
        30.86,
        15.90,
        30.60,
        29.85,
        28.65,
        24.08,
        26.73,
        29.00,
        25.50,
        29.85,
        196.3,
    ],
    "b_4": [
        0.76,
        0.69,
        0.70,
        0.77,
        0.67,
        0.64,
        0.69,
        0.54,
        0.63,
        0.60,
        0.63,
        0.60,
        0.66,
        0.66,
        0.65,
        0.69,
        0.61,
        0.61,
        0.70,
        0.70,
        0.69,
        0.71,
        0.60,
        0.69,
        0.68,
        0.33,
        0.68,
        0.68,
        0.70,
        0.70,
        0.70,
        0.70,
        0.64,
        0.68,
        2.00,
    ],
    "b_5": [
        5.087,
        4.930,
        4.780,
        5.022,
        4.398,
        4.893,
        4.740,
        5.063,
        4.810,
        4.230,
        4.483,
        5.083,
        5.028,
        4.506,
        4.804,
        5.201,
        3.980,
        4.010,
        4.500,
        4.500,
        4.552,
        4.856,
        4.000,
        4.140,
        4.352,
        5.760,
        4.090,
        4.530,
        5.100,
        4.700,
        5.150,
        5.000,
        4.940,
        4.550,
        24.15,
    ],
    "b_6": [
        1.00,
        0.82,
        0.79,
        0.85,
        0.54,
        0.74,
        0.61,
        0.89,
        0.55,
        0.48,
        0.52,
        0.50,
        0.67,
        0.65,
        0.64,
        0.72,
        0.43,
        0.45,
        1.00,
        1.00,
        1.00,
        0.68,
        0.50,
        1.00,
        0.84,
        0.45,
        0.84,
        0.90,
        0.95,
        0.53,
        0.78,
        0.80,
        0.67,
        0.90,
        5.00,
    ],
}


def LineShapeFactor(f__ghz, f_i__ghz, delta_f__ghz, delta):
    term1 = f__ghz / f_i__ghz
    term2 = (delta_f__ghz - delta * (f_i__ghz - f__ghz)) / ((f_i__ghz - f__ghz) ** 2 + delta_f__ghz**2)
    term3 = (delta_f__ghz - delta * (f_i__ghz + f__ghz)) / ((f_i__ghz + f__ghz) ** 2 + delta_f__ghz**2)

    F_i = term1 * (term2 + term3)

    return F_i


def WaterVapourRefractivity(f__ghz: float, T__kelvin: float, e__hPa: float, P__hPa: float):
    """
    Calculate the imaginary part of the frequency-dependent complex refractivity due to water vapour.

    Args:
    f__ghz (float): Frequency in GHz
    T__kelvin (float): Temperature in Kelvin
    e__hPa (float): Water vapour partial pressure in hectopascals (hPa)
    P__hPa (float): Dry air pressure in hectopascals (hPa)

    Returns:
    float: Refractivity in N-Units
    """
    theta = 300 / T__kelvin

    N_w = 0

    for i in range(len(WaterVapourData["f_0"])):
        # Equation 3, for water vapour
        S_i = 0.1 * WaterVapourData["b_1"][i] * e__hPa * theta**3.5 * math.exp(WaterVapourData["b_2"][i] * (1 - theta))

        # compute the width of the line, Equation 6a, for water vapour
        delta_f__ghz = (
            1e-4
            * WaterVapourData["b_3"][i]
            * (
                P__hPa * theta ** WaterVapourData["b_4"][i]
                + WaterVapourData["b_5"][i] * e__hPa * theta ** WaterVapourData["b_6"][i]
            )
        )

        # modify the line width to account for Doppler broadening of water vapour lines
        # Equation 6b, for water vapour
        term1 = 0.217 * delta_f__ghz**2 + (2.1316e-12 * WaterVapourData["f_0"][i] ** 2 / theta)
        delta_f__ghz = 0.535 * delta_f__ghz + math.sqrt(term1)

        # Equation 7, for water vapour
        delta = 0

        F_i = LineShapeFactor(f__ghz, WaterVapourData["f_0"][i], delta_f__ghz, delta)

        # summation of terms...from Equation 2b, for water vapour
        N_w += S_i * F_i

    return N_w


def OxygenSpecificAttenuation(f__ghz: float, T__kelvin: float, e__hPa: float, p__hPa: float):
    """
    Calculate the specific attenuation due to oxygen.

    Args:
    f__ghz (float): Frequency in GHz
    T__kelvin (float): Temperature in Kelvin
    e__hPa (float): Water vapor partial pressure in hectopascals (hPa)
    p__hPa (float): Dry air pressure in hectopascals (hPa)

    Returns:
    float: Specific attenuation due to oxygen in dB/km
    """
    # partial Eqn 1
    N_o = OxygenRefractivity(f__ghz, T__kelvin, e__hPa, p__hPa)

    gamma_o = 0.1820 * f__ghz * N_o

    return gamma_o


def WaterVapourSpecificAttenuation(f__ghz: float, T__kelvin: float, e__hPa: float, p__hPa: float):
    """
    Calculate the specific attenuation due to water vapour.

    Args:
    f__ghz (float): Frequency in GHz
    T__kelvin (float): Temperature in Kelvin
    e__hPa (float): Water vapor partial pressure in hectopascals (hPa)
    p__hPa (float): Dry air pressure in hectopascals (hPa)

    Returns:
    float: Specific attenuation due to water vapour in dB/km
    """
    # partial Eqn 1
    N_w = WaterVapourRefractivity(f__ghz, T__kelvin, e__hPa, p__hPa)
    gamma_w = 0.1820 * f__ghz * N_w

    return gamma_w


def GetLayerProperties(f__ghz: float, h_i__km: float):
    # use function pointers to get atmospheric parameters

    # T__kelvin = config.temperature(h_i__km)
    # p__hPa = config.dry_pressure(h_i__km)
    # e__hPa = config.wet_pressure(h_i__km)
    """na original é assim, mas o certo em python seria:"""
    T__kelvin = GlobalTemperature(h_i__km)
    p__hPa = GlobalPressure(h_i__km)
    e__hPa = GlobalWetPressure(h_i__km)

    # compute the refractive index for the current layer
    n = RefractiveIndex(p__hPa, T__kelvin, e__hPa)

    # specific attenuation of layer
    gamma = SpecificAttenuation(f__ghz, T__kelvin, e__hPa, p__hPa)

    return n, gamma


# Conversion


def ConvertToGeopotentialHeight(h__km: float):
    """
    Converts from geometric height, in km, to geopotential height, in km'.
    See Equation (1a).

    Args:
    h__km (float): Geometric height, in km

    Returns:
    float: Geopotential height, in km'
    """
    return (6356.766 * h__km) / (6356.766 + h__km)


def ConvertToGeometricHeight(h_prime__km: float):
    """
    Converts from geopotential height, in km', to geometric height, in km.
    See Equation (1b).

    Args:
    h_prime__km (float): Geopotential height, in km'

    Returns:
    float: Geometric height, in km
    """
    return (6356.766 * h_prime__km) / (6356.766 - h_prime__km)


def WaterVapourDensityToPressure(rho: float, T__kelvin: float):
    """
    Converts water vapour density, in g/m^3, to water vapour pressure, in hPa.
    See Equation (8).

    Args:
    rho (float): Water vapour density, rho(h), in g/m^3
    T__kelvin (float): Temperature, T(h), in Kelvin

    Returns:
    float: Water vapour pressure, e(h), in hPa
    """
    return (rho * T__kelvin) / 216.7


def DistanceFunction(x__km: float):
    """
    Calculate the distance function G(x).

    Args:
    x__km (float): Distance in km

    Returns:
    float: Distance function value in dB
    """
    # [Vogler 1964, Equ 13]
    G_x__db = 0.05751 * x__km - 10.0 * math.log10(x__km)
    return G_x__db


def HeightFunction(x__km: float, K: float):
    """
    Calculate the height function F(x).

    Args:
    x__km (float): Distance in km
    K (float): Coefficient K

    Returns:
    float: Height function value in dB
    """
    # [FAA-ES-83-3, Equ 73]
    y__db = 40.0 * math.log10(x__km) - 117.0

    # [Vogler 1964, Equ 13]
    G_x__db = DistanceFunction(x__km)

    if x__km <= 200.0:
        x_t__km = 450 / -math.pow(math.log10(K), 3)  # [Eqn 109]

        # [Eqn 110]
        if x__km >= x_t__km:
            if abs(y__db) < 117:
                F_x__db = y__db
            else:
                F_x__db = -117
        else:
            F_x__db = 20 * math.log10(K) - 15 + (0.000025 * math.pow(x__km, 2) / K)
    elif x__km > 2000.0:
        # [Vogler 1964] F_x ~= G_x for large x (see Figure 7)
        F_x__db = G_x__db
    else:  # Blend y__db with G_x__db for 200 < x__km < 2000
        # [FAA-ES-83-3, Equ 72] weighting variable
        W = 0.0134 * x__km * math.exp(-0.005 * x__km)

        # [FAA-ES-83-3, Equ 75]
        F_x__db = W * y__db + (1.0 - W) * G_x__db

    return F_x__db


def SmoothEarthDiffraction(d_1__km: float, d_2__km: float, f__mhz: float, d_0__km: float, T_pol: int):
    """
    Calculate the smooth earth diffraction loss.

    Args:
    d_1__km (float): Horizon distance of terminal 1, in km
    d_2__km (float): Horizon distance of terminal 2, in km
    f__mhz (float): Frequency, in MHz
    d_0__km (float): Path length of interest, in km
    T_pol (int): Polarization code (0 for horizontal, 1 for vertical)

    Returns:
    float: Diffraction loss in dB
    """
    THIRD = 1 / 3
    s = 18000 * sigma / f__mhz

    if T_pol == POLARIZATION__HORIZONTAL:
        K = 0.01778 * math.pow(f__mhz, -THIRD) * math.pow(math.pow(epsilon_r - 1, 2) + math.pow(s, 2), -0.25)
    else:
        K = (
            0.01778
            * math.pow(f__mhz, -THIRD)
            * math.pow(
                (math.pow(epsilon_r, 2) + math.pow(s, 2)) / math.pow(math.pow(epsilon_r - 1, 2) + math.pow(s, 2), 0.5),
                0.5,
            )
        )

    B_0 = 1.607

    # [Vogler 1964, Equ 2] with C_0 = 1 due to "4/3" Earth assumption
    x_0__km = (B_0 - K) * math.pow(f__mhz, THIRD) * d_0__km
    x_1__km = (B_0 - K) * math.pow(f__mhz, THIRD) * d_1__km
    x_2__km = (B_0 - K) * math.pow(f__mhz, THIRD) * d_2__km

    # Compute the distance function for the path
    G_x__db = DistanceFunction(x_0__km)

    # Compute the height functions for the two terminals
    F_x1__db = HeightFunction(x_1__km, K)
    F_x2__db = HeightFunction(x_2__km, K)

    # [Vogler 1964, Equ 1] with C_1(K, b^0) = 20, which is the approximate value for all K (see Figure 5)
    return G_x__db - F_x1__db - F_x2__db - 20.0


def FindPsiAtDistance(d__km: float, path: Path, terminal_1: Terminal, terminal_2: Terminal):
    if d__km == 0:
        return math.pi / 2

    # initialize to start at mid-point
    psi = math.pi / 2
    delta_psi = -math.pi / 4

    while True:
        psi += delta_psi  # new psi

        params_temp = _GLOBAL_LOS_PARAMS
        params_temp.clear()
        RayOptics(terminal_1, terminal_2, psi, params_temp)

        d_psi__km = params_temp.d__km

        # compute delta
        if d_psi__km > d__km:
            delta_psi = abs(delta_psi) / 2
        else:
            delta_psi = -abs(delta_psi) / 2

        if abs(d__km - d_psi__km) <= 1e-3 or abs(delta_psi) <= 1e-12:
            break

    return psi


def FindPsiAtDeltaR(
    delta_r__km: float,
    path: Path,
    terminal_1: Terminal,
    terminal_2: Terminal,
    terminate: float,
):
    psi = math.pi / 2
    delta_psi = -math.pi / 4

    while True:
        psi += delta_psi

        params_temp = _GLOBAL_LOS_PARAMS
        params_temp.clear()
        RayOptics(terminal_1, terminal_2, psi, params_temp)

        if params_temp.delta_r__km > delta_r__km:
            delta_psi = -abs(delta_psi) / 2
        else:
            delta_psi = abs(delta_psi) / 2

        if abs(params_temp.delta_r__km - delta_r__km) <= terminate:
            break

    return psi


def FindDistanceAtDeltaR(
    delta_r__km: float,
    path: Path,
    terminal_1: Terminal,
    terminal_2: Terminal,
    terminate: float,
):
    psi = math.pi / 2
    delta_psi = -math.pi / 4

    while True:
        psi += delta_psi

        params_temp = _GLOBAL_LOS_PARAMS
        params_temp.clear()
        RayOptics(terminal_1, terminal_2, psi, params_temp)

        if params_temp.delta_r__km > delta_r__km:
            delta_psi = -abs(delta_psi) / 2
        else:
            delta_psi = abs(delta_psi) / 2

        if abs(params_temp.delta_r__km - delta_r__km) <= terminate:
            break

    return params_temp.d__km


def LineOfSight(
    path: Path,
    terminal_1: Terminal,
    terminal_2: Terminal,
    los_params: LineOfSightParams,
    f__mhz: float,
    A_dML__db: float,
    p: float,
    d__km: float,
    T_pol: int,
    result: Result,
    K_LOS: float,
):

    # 0.2997925 = speed of light, gigameters per sec
    lambda__km = 0.2997925 / f__mhz  # [Eqn 6-1]
    terminate = lambda__km / 1e6

    # determine psi_limit, where you switch from free space to 2-ray model
    # lambda / 2 is the start of the lobe closest to d_ML
    psi_limit = FindPsiAtDeltaR(lambda__km / 2, path, terminal_1, terminal_2, terminate)

    # "[d_y6__km] is the largest distance at which a free-space value is obtained in a two-ray model
    #   of reflection from a smooth earth with a reflection coefficient of -1" [ES-83-3, page 44]
    d_y6__km = FindDistanceAtDeltaR(lambda__km / 6, path, terminal_1, terminal_2, terminate)

    # Determine d_0__km distance
    if terminal_1.d_r__km >= path.d_d__km or path.d_d__km >= path.d_ML__km:
        if terminal_1.d_r__km > d_y6__km or d_y6__km > path.d_ML__km:
            path.d_0__km = terminal_1.d_r__km
        else:
            path.d_0__km = d_y6__km
    elif path.d_d__km < d_y6__km and d_y6__km < path.d_ML__km:
        path.d_0__km = d_y6__km
    else:
        path.d_0__km = path.d_d__km

    # Tune d_0__km distance
    d_temp__km = path.d_0__km

    los_result = _GLOBAL_LOS_PARAMS
    los_result.clear()

    while True:
        psi = FindPsiAtDistance(d_temp__km, path, terminal_1, terminal_2)

        los_result = RayOptics(terminal_1, terminal_2, psi, los_result)

        if los_result.d__km >= path.d_0__km or (d_temp__km + 0.001) >= path.d_ML__km:
            path.d_0__km = los_result.d__km
            break

        d_temp__km += 0.001

    # Compute loss at d_0__km
    psi_d0 = FindPsiAtDistance(path.d_0__km, path, terminal_1, terminal_2)
    RayOptics(terminal_1, terminal_2, psi_d0, los_params)
    R_Tg = GetPathLoss(psi_d0, path, f__mhz, psi_limit, A_dML__db, 0, T_pol, los_params)

    # tune psi for the desired distance
    psi = FindPsiAtDistance(d__km, path, terminal_1, terminal_2)
    RayOptics(terminal_1, terminal_2, psi, los_params)
    R_Tg = GetPathLoss(
        psi,
        path,
        f__mhz,
        psi_limit,
        A_dML__db,
        los_params.A_LOS__db,
        T_pol,
        los_params,
    )

    # Compute atmospheric absorption
    result_slant = SlantPathAttenuation(
        f__mhz / 1000,
        terminal_1.h_r__km,
        terminal_2.h_r__km,
        math.pi / 2 - los_params.theta_h1__rad,
    )
    result.A_a__db = result_slant.A_gas__db

    # Compute free-space loss
    result.A_fs__db = 20.0 * math.log10(los_params.r_0__km) + 20.0 * math.log10(f__mhz) + 32.45  # [Eqn 6-4]

    # Compute variability
    f_theta_h = (
        1.0
        if los_params.theta_h1__rad <= 0.0
        else (
            0.0
            if los_params.theta_h1__rad >= 1.0
            else max(
                0.5 - (1 / math.pi) * (math.atan(20.0 * math.log10(32.0 * los_params.theta_h1__rad))),
                0,
            )
        )
    )

    Y_e__db, A_Y = LongTermVariability(
        terminal_1.d_r__km,
        terminal_2.d_r__km,
        d__km,
        f__mhz,
        p,
        f_theta_h,
        los_params.A_LOS__db,
    )
    Y_e_50__db, _ = LongTermVariability(
        terminal_1.d_r__km,
        terminal_2.d_r__km,
        d__km,
        f__mhz,
        50,
        f_theta_h,
        los_params.A_LOS__db,
    )

    F_AY = 1.0 if A_Y <= 0.0 else (0.1 if A_Y >= 9.0 else (1.1 + (0.9 * math.cos((A_Y / 9.0) * math.pi))) / 2.0)

    F_delta_r = (
        1.0
        if los_params.delta_r__km >= (lambda__km / 2.0)
        else (
            0.1
            if los_params.delta_r__km <= lambda__km / 6.0
            else 0.5 * (1.1 - (0.9 * math.cos(((3.0 * math.pi) / lambda__km) * (los_params.delta_r__km - (lambda__km / 6.0)))))
        )
    )

    R_s = R_Tg * F_delta_r * F_AY  # [Eqn 13-4]

    Y_pi_99__db = 10.0 * math.log10(f__mhz * pow(result_slant.a__km, 3)) - 84.26  # [Eqn 13-5]
    K_t = FindKForYpiAt99Percent(Y_pi_99__db)

    W_a = pow(10.0, K_t / 10.0)  # [Eqn 13-6]
    W_R = pow(R_s, 2) + pow(0.01, 2)  # [Eqn 13-7]
    W = W_R + W_a  # [Eqn 13-8]

    K_LOS = -40.0 if W <= 0.0 else max(10.0 * math.log10(W), -40.0)

    Y_pi_50__db = 0.0  # zero mean
    Y_pi__db = NakagamiRice(K_LOS, p)

    Y_total__db = -CombineDistributions(Y_e_50__db, Y_e__db, Y_pi_50__db, Y_pi__db, p)

    result.d__km = los_params.d__km
    result.A__db = result.A_fs__db + result.A_a__db - los_params.A_LOS__db + Y_total__db
    result.theta_h1__rad = los_params.theta_h1__rad

    return K_LOS


def RayOptics(
    terminal_1: Terminal,
    terminal_2: Terminal,
    psi: float,
    params: LineOfSightParams,
):

    z = (a_0__km / a_e__km) - 1  # [Eqn 7-1]
    k_a = 1 / (1 + z * math.cos(psi))  # [Eqn 7-2]
    params.a_a__km = a_0__km * k_a  # [Eqn 7-3]

    delta_h_a1__km = terminal_1.delta_h__km * (params.a_a__km - a_0__km) / (a_e__km - a_0__km)  # [Eqn 7-4]
    delta_h_a2__km = terminal_2.delta_h__km * (params.a_a__km - a_0__km) / (a_e__km - a_0__km)  # [Eqn 7-4]

    H__km = [0, 0]
    H__km[0] = terminal_1.h_r__km - delta_h_a1__km  # [Eqn 7-5]
    H__km[1] = terminal_2.h_r__km - delta_h_a2__km  # [Eqn 7-5]

    Hprime__km = [0, 0]
    for i in range(2):
        params.z__km[i] = params.a_a__km + H__km[i]  # [Eqn 7-6]
        params.theta[i] = math.acos(params.a_a__km * math.cos(psi) / params.z__km[i]) - psi  # [Eqn 7-7]
        params.D__km[i] = params.z__km[i] * math.sin(params.theta[i])  # [Eqn 7-8]

        # [Eqn 7-9]
        if psi > 1.56:
            Hprime__km[i] = H__km[i]
        else:
            Hprime__km[i] = params.D__km[i] * math.tan(psi)

    delta_z = abs(params.z__km[0] - params.z__km[1])  # [Eqn 7-10]

    params.d__km = max(params.a_a__km * (params.theta[0] + params.theta[1]), 0)  # [Eqn 7-11]

    if (params.D__km[0] + params.D__km[1]) != 0:
        alpha = math.atan((Hprime__km[1] - Hprime__km[0]) / (params.D__km[0] + params.D__km[1]))  # [Eqn 7-12]
    else:
        alpha = math.atan(math.inf)  # [Eqn 7-12]

    params.r_0__km = max(delta_z, (params.D__km[0] + params.D__km[1]) / math.cos(alpha))  # [Eqn 7-13]
    params.r_12__km = (params.D__km[0] + params.D__km[1]) / math.cos(psi)  # [Eqn 7-14]

    params.delta_r__km = 4.0 * Hprime__km[0] * Hprime__km[1] / (params.r_0__km + params.r_12__km)  # [Eqn 7-15]

    params.theta_h1__rad = alpha - params.theta[0]  # [Eqn 7-16]
    params.theta_h2__rad = -(alpha + params.theta[1])  # [Eqn 7-17]

    return params


def GetPathLoss(
    psi__rad: float,
    path: Path,
    f__mhz: float,
    psi_limit: float,
    A_dML__db: float,
    A_d_0__db: float,
    T_pol: int,
    params: LineOfSightParams,
):
    R_g, phi_g = ReflectionCoefficients(psi__rad, f__mhz, T_pol)

    if math.tan(psi__rad) >= 0.1:
        D_v = 1.0
    else:
        r_1 = params.D__km[0] / math.cos(psi__rad)  # [Eqn 8-3]
        r_2 = params.D__km[1] / math.cos(psi__rad)  # [Eqn 8-3]
        R_r = (r_1 * r_2) / params.r_12__km  # [Eqn 8-4]

        term_1 = (2 * R_r * (1 + math.sin(psi__rad) ** 2)) / (params.a_a__km * math.sin(psi__rad))
        term_2 = (2 * R_r / params.a_a__km) ** 2
        D_v = (1.0 + term_1 + term_2) ** (-0.5)  # [Eqn 8-5]

    # Ray-length factor, [Eqn 8-6]
    if params.r_12__km != 0:
        F_r = min(params.r_0__km / params.r_12__km, 1)
    else:
        F_r = min(math.inf, 1)

    R_Tg = R_g * D_v * F_r  # [Eqn 8-7]

    if params.d__km > path.d_0__km:
        # [Eqn 8-1]
        params.A_LOS__db = (
            (params.d__km - path.d_0__km) * (A_dML__db - A_d_0__db) / (path.d_ML__km - path.d_0__km)
        ) + A_d_0__db
    else:
        lambda__km = 0.2997925 / f__mhz  # [Eqn 8-2]

        if psi__rad > psi_limit:
            # ignore the phase lag; Step 8-2
            params.A_LOS__db = 0
        else:
            # Total phase lag of the ground reflected ray relative to the direct ray

            # [Eqn 8-8]
            phi_Tg = (2 * math.pi * params.delta_r__km / lambda__km) + phi_g

            # [Eqn 8-9]
            cplx = complex(R_Tg * math.cos(phi_Tg), -R_Tg * math.sin(phi_Tg))

            # [Eqn 8-10]
            W_RL = min(abs(1.0 + cplx), 1.0)

            # [Eqn 8-11]
            W_R0 = W_RL**2

            # [Eqn 8-12]
            params.A_LOS__db = 10.0 * math.log10(W_R0)

    return R_Tg


def ReflectionCoefficients(psi__rad: float, f__mhz: float, T_pol: int):
    if psi__rad <= 0.0:
        psi__rad = 0.0
        sin_psi = 0.0
        cos_psi = 1.0
    elif psi__rad >= math.pi / 2:
        psi__rad = math.pi / 2
        sin_psi = 1.0
        cos_psi = 0.0
    else:
        sin_psi = math.sin(psi__rad)
        cos_psi = math.cos(psi__rad)

    X = (18000.0 * sigma) / f__mhz  # [Eqn 9-1]
    Y = epsilon_r - cos_psi**2  # [Eqn 9-2]
    T = math.sqrt(Y**2 + X**2) + Y  # [Eqn 9-3]
    P = math.sqrt(T * 0.5)  # [Eqn 9-4]
    Q = X / (2.0 * P)  # [Eqn 9-5]

    # [Eqn 9-6]
    if T_pol == POLARIZATION__HORIZONTAL:
        B = 1.0 / (P**2 + Q**2)
    else:
        B = (epsilon_r**2 + X**2) / (P**2 + Q**2)

    # [Eqn 9-7]
    if T_pol == POLARIZATION__HORIZONTAL:
        A = (2.0 * P) / (P**2 + Q**2)
    else:
        A = (2.0 * (P * epsilon_r + Q * X)) / (P**2 + Q**2)

    # [Eqn 9-8]
    R_g = math.sqrt((1.0 + (B * sin_psi**2) - (A * sin_psi)) / (1.0 + (B * sin_psi**2) + (A * sin_psi)))

    # [Eqn 9-9]
    if T_pol == POLARIZATION__HORIZONTAL:
        alpha = math.atan2(-Q, sin_psi - P)
    else:
        alpha = math.atan2((epsilon_r * sin_psi) - Q, epsilon_r * sin_psi - P)

    # [Eqn 9-10]
    if T_pol == POLARIZATION__HORIZONTAL:
        beta = math.atan2(Q, sin_psi + P)
    else:
        beta = math.atan2((X * sin_psi) + Q, epsilon_r * sin_psi + P)

    # [Eqn 9-11]
    phi_g = alpha - beta

    return R_g, phi_g


def linear_interpolation(x, x1, y1, x2, y2):
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)


def LongTermVariability(
    d_r1__km: float,
    d_r2__km: float,
    d__km: float,
    f__mhz: float,
    p: float,
    f_theta_h: float,
    A_T: float,
):
    """
    Compute the long term variability as described in Annex 2, Section 14 of
    Recommendation ITU-R P.528-5, "Propagation curves for aeronautical mobile
    and radionavigation services using the VHF, UHF and SHF bands"

    Args:
    d_r1__km (float): Actual height of low terminal, in km
    d_r2__km (float): Actual height of high terminal, in km
    d__km (float): Path distance, in km
    f__mhz (float): Frequency, in MHz
    p (float): Time percentage
    f_theta_h (float): Angular distance factor
    A_T (float): Total loss

    Returns:
    tuple[float, float]: (Y_e__db, A_Y)
        Y_e__db: Variability, in dB
        A_Y: Conditional adjustment factor, in dB
    """
    THIRD = 1 / 3
    d_qs__km = 65.0 * pow((100.0 / f__mhz), THIRD)  # [Eqn 14-1]
    d_Lq__km = d_r1__km + d_r2__km  # [Eqn 14-2]
    d_q__km = d_Lq__km + d_qs__km  # [Eqn 14-3]

    # [Eqn 14-4]
    if d__km <= d_q__km:
        d_e__km = (130.0 * d__km) / d_q__km
    else:
        d_e__km = 130.0 + d__km - d_q__km

    # [Eqns 14-5 and 14-6]
    if f__mhz > 1600.0:
        g_10 = g_90 = 1.05
    else:
        g_10 = (0.21 * math.sin(5.22 * math.log10(f__mhz / 200.0))) + 1.28
        g_90 = (0.18 * math.sin(5.22 * math.log10(f__mhz / 200.0))) + 1.23

    # Data Source for Below Consts: Tech Note 101, Vol 2
    # Column 1: Table III.4, Row A* (Page III-50)
    # Column 2: Table III.3, Row A* (Page III-49)
    # Column 3: Table III.5, Row Continental Temperate (Page III-51)

    c_1 = [2.93e-4, 5.25e-4, 1.59e-5]
    c_2 = [3.78e-8, 1.57e-6, 1.56e-11]
    c_3 = [1.02e-7, 4.70e-7, 2.77e-8]

    n_1 = [2.00, 1.97, 2.32]
    n_2 = [2.88, 2.31, 4.08]
    n_3 = [3.15, 2.90, 3.25]

    f_inf = [3.2, 5.4, 0.0]
    f_m = [8.2, 10.0, 3.9]

    Z__db = [0, 0, 0]  # = [Y_0(90) Y_0(10) V(50)]
    for i in range(3):
        f_2 = f_inf[i] + ((f_m[i] - f_inf[i]) * math.exp(-c_2[i] * pow(d_e__km, n_2[i])))
        Z__db[i] = (c_1[i] * pow(d_e__km, n_1[i]) - f_2) * math.exp(-c_3[i] * pow(d_e__km, n_3[i])) + f_2

    if p == 50:
        Y_p__db = Z__db[2]
    elif p > 50:
        z_90 = InverseComplementaryCumulativeDistributionFunction(90.0 / 100.0)
        z_p = InverseComplementaryCumulativeDistributionFunction(p / 100.0)
        c_p = z_p / z_90

        Y = c_p * (-Z__db[0] * g_90)
        Y_p__db = Y + Z__db[2]
    else:
        if p >= 10:
            z_10 = InverseComplementaryCumulativeDistributionFunction(10.0 / 100.0)
            z_p = InverseComplementaryCumulativeDistributionFunction(p / 100.0)
            c_p = z_p / z_10
        else:
            # Source for values p < 10: [15], Table 10, Page 34, Climate 6
            ps = [1, 2, 5, 10]
            c_ps = [1.9507, 1.7166, 1.3265, 1.0000]

            # Simplified interpolation
            for i in range(len(ps) - 1):
                if ps[i] <= p < ps[i + 1]:
                    c_p = c_ps[i] + (c_ps[i + 1] - c_ps[i]) * (p - ps[i]) / (ps[i + 1] - ps[i])
                    break
            else:
                c_p = c_ps[-1]

        Y = c_p * (Z__db[1] * g_10)
        Y_p__db = Y + Z__db[2]

    Y_10__db = (Z__db[1] * g_10) + Z__db[2]  # [Eqn 14-20]
    Y_eI__db = f_theta_h * Y_p__db  # [Eqn 14-21]
    Y_eI_10__db = f_theta_h * Y_10__db  # [Eqn 14-22]

    # A_Y "is used to prevent available signal powers from exceeding levels expected for free-space propagation by an unrealistic
    #      amount when the variability about L_b(50) is large and L_b(50) is near its free-space level" [ES-83-3, p3-4]

    A_YI = (A_T + Y_eI_10__db) - 3.0  # [Eqn 14-23]
    A_Y = max(A_YI, 0)  # [Eqn 14-24]
    Y_e__db = Y_eI__db - A_Y  # [Eqn 14-25]

    # For percentages less than 10%, do a correction check to,
    #    "prevent available signal powers from exceeding levels expected from free-space levels
    #     by unrealistic amounts" [Gierhart 1970]
    if p < 10:
        c_Y = [-5.0, -4.5, -3.7, 0.0]
        P = [1, 2, 5, 10]  # Assuming this is data::P

        # Simplified interpolation
        for i in range(len(P) - 1):
            if P[i] <= p < P[i + 1]:
                c_Yi = c_Y[i] + (c_Y[i + 1] - c_Y[i]) * (p - P[i]) / (P[i + 1] - P[i])
                break
        else:
            c_Yi = c_Y[-1]

        Y_e__db += A_T

        if Y_e__db > -c_Yi:
            Y_e__db = -c_Yi

        Y_e__db -= A_T

    return Y_e__db, A_Y


def FindKForYpiAt99Percent(Y_pi_99__db: float):
    """
    Find K value for Y_pi at 99 percent.

    Args:
    Y_pi_99__db (float): Y_pi value at 99 percent

    Returns:
    float: Corresponding K value
    """
    # Is Y_pi_99__db smaller than the smallest value in the distribution data
    if Y_pi_99__db < NakagamiRiceCurves[0][Y_pi_99_INDEX]:
        return K[0]

    # Search the distribution data and interpolate to find K (dependent variable)
    for i in range(1, len(K)):
        if Y_pi_99__db - NakagamiRiceCurves[i][Y_pi_99_INDEX] < 0:
            return (
                K[i] * (Y_pi_99__db - NakagamiRiceCurves[i - 1][Y_pi_99_INDEX])
                - K[i - 1] * (Y_pi_99__db - NakagamiRiceCurves[i][Y_pi_99_INDEX])
            ) / (NakagamiRiceCurves[i][Y_pi_99_INDEX] - NakagamiRiceCurves[i - 1][Y_pi_99_INDEX])

    # No match. Y_pi_99__db is greater than the data contains. Return largest K
    return K[-1]


# Data curves corresponding Nakagami-Rice distributions
NakagamiRiceCurves = [
    # K = -40 distribution
    [
        -0.1417,
        -0.1252,
        -0.1004,
        -0.0784,
        -0.0634,
        -0.0515,
        -0.0321,
        -0.0155,
        0.0000,
        0.0156,
        0.0323,
        0.0518,
        0.0639,
        0.0791,
        0.1016,
        0.1271,
        0.1441,
    ],
    [
        -0.7676,
        -0.6811,
        -0.5497,
        -0.4312,
        -0.3504,
        -0.2856,
        -0.1790,
        -0.0870,
        0.0000,
        0.0878,
        0.1828,
        0.2953,
        0.3651,
        0.4537,
        0.5868,
        0.7390,
        0.8420,
    ],
    [
        -1.3183,
        -1.1738,
        -0.9524,
        -0.7508,
        -0.6121,
        -0.5003,
        -0.3151,
        -0.1537,
        0.0000,
        0.1564,
        0.3269,
        0.5308,
        0.6585,
        0.8218,
        1.0696,
        1.3572,
        1.5544,
    ],
    [
        -1.6263,
        -1.4507,
        -1.1805,
        -0.9332,
        -0.7623,
        -0.6240,
        -0.3940,
        -0.1926,
        0.0000,
        0.1969,
        0.4127,
        0.6722,
        0.8355,
        1.0453,
        1.3660,
        1.7417,
        2.0014,
    ],
    [
        -1.9963,
        -1.7847,
        -1.4573,
        -1.1557,
        -0.9462,
        -0.7760,
        -0.4916,
        -0.2410,
        0.0000,
        0.2478,
        0.5209,
        0.8519,
        1.0615,
        1.3326,
        1.7506,
        2.2463,
        2.5931,
    ],
    [
        -2.4355,
        -2.1829,
        -1.7896,
        -1.4247,
        -1.1695,
        -0.9613,
        -0.6113,
        -0.3007,
        0.0000,
        0.3114,
        0.6573,
        1.0802,
        1.3505,
        1.7028,
        2.2526,
        2.9156,
        3.3872,
    ],
    [
        -2.9491,
        -2.6507,
        -2.1831,
        -1.7455,
        -1.4375,
        -1.1846,
        -0.7567,
        -0.3737,
        0.0000,
        0.3903,
        0.8281,
        1.3698,
        1.7198,
        2.1808,
        2.9119,
        3.8143,
        4.4714,
    ],
    [
        -3.5384,
        -3.1902,
        -2.6407,
        -2.1218,
        -1.7535,
        -1.4495,
        -0.9307,
        -0.4619,
        0.0000,
        0.4874,
        1.0404,
        1.7348,
        2.1898,
        2.7975,
        3.7820,
        5.0373,
        5.9833,
    ],
    [
        -4.1980,
        -3.7974,
        -3.1602,
        -2.5528,
        -2.1180,
        -1.7565,
        -1.1345,
        -0.5662,
        0.0000,
        0.6045,
        1.2999,
        2.1887,
        2.7814,
        3.5868,
        4.9288,
        6.7171,
        8.1319,
    ],
    [
        -4.9132,
        -4.4591,
        -3.7313,
        -3.0306,
        -2.5247,
        -2.1011,
        -1.3655,
        -0.6855,
        0.0000,
        0.7415,
        1.6078,
        2.7374,
        3.5059,
        4.5714,
        6.4060,
        8.9732,
        11.0973,
    ],
    [
        -5.6559,
        -5.1494,
        -4.3315,
        -3.5366,
        -2.9578,
        -2.4699,
        -1.6150,
        -0.8154,
        0.0000,
        0.8935,
        1.9530,
        3.3611,
        4.3363,
        5.7101,
        8.1216,
        11.5185,
        14.2546,
    ],
    [
        -6.3810,
        -5.8252,
        -4.9219,
        -4.0366,
        -3.3871,
        -2.8364,
        -1.8638,
        -0.9455,
        0.0000,
        1.0458,
        2.2979,
        3.9771,
        5.1450,
        6.7874,
        9.6276,
        13.4690,
        16.4251,
    ],
    [
        -7.0247,
        -6.4249,
        -5.4449,
        -4.4782,
        -3.7652,
        -3.1580,
        -2.0804,
        -1.0574,
        0.0000,
        1.1723,
        2.5755,
        4.4471,
        5.7363,
        7.5266,
        10.5553,
        14.5401,
        17.5511,
    ],
    [
        -7.5229,
        -6.8862,
        -5.8424,
        -4.8090,
        -4.0446,
        -3.3927,
        -2.2344,
        -1.1347,
        0.0000,
        1.2535,
        2.7446,
        4.7144,
        6.0581,
        7.9073,
        11.0003,
        15.0270,
        18.0526,
    ],
    [
        -7.8532,
        -7.1880,
        -6.0963,
        -5.0145,
        -4.2145,
        -3.5325,
        -2.3227,
        -1.1774,
        0.0000,
        1.2948,
        2.8268,
        4.8377,
        6.2021,
        8.0724,
        11.1869,
        15.2265,
        18.2566,
    ],
    [
        -8.0435,
        -7.3588,
        -6.2354,
        -5.1234,
        -4.3022,
        -3.6032,
        -2.3656,
        -1.1975,
        0.0000,
        1.3130,
        2.8619,
        4.8888,
        6.2610,
        8.1388,
        11.2607,
        15.3047,
        18.3361,
    ],
    [
        -8.2238,
        -7.5154,
        -6.3565,
        -5.2137,
        -4.3726,
        -3.6584,
        -2.3979,
        -1.2121,
        0.0000,
        1.3255,
        2.8855,
        4.9224,
        6.2992,
        8.1814,
        11.3076,
        15.3541,
        18.3864,
    ],
]

K = [-40, -25, -20, -18, -16, -14, -12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 20]

# Percentages for interpolation and data tables
P = [1, 2, 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 85, 90, 95, 98, 99]

import bisect


def NakagamiRice(K_value, p_value):

    d_K = bisect.bisect_left(K, K_value)
    d_p = bisect.bisect_left(P, p_value)

    if d_K == 0:  # K_value <= smallest K
        if d_p == 0:
            return NakagamiRiceCurves[0][0]
        else:
            return linear_interpolation(
                p_value,
                P[d_p - 1],
                NakagamiRiceCurves[0][d_p - 1],
                P[d_p],
                NakagamiRiceCurves[0][d_p],
            )
    elif d_K == len(K):  # K_value > largest K
        if d_p == 0:
            return NakagamiRiceCurves[d_K - 1][0]
        else:
            return linear_interpolation(
                p_value,
                P[d_p - 1],
                NakagamiRiceCurves[d_K - 1][d_p - 1],
                P[d_p],
                NakagamiRiceCurves[d_K - 1][d_p],
            )
    else:
        if d_p == 0:
            return linear_interpolation(
                K_value,
                K[d_K - 1],
                NakagamiRiceCurves[d_K - 1][0],
                K[d_K],
                NakagamiRiceCurves[d_K][0],
            )
        else:
            v1 = linear_interpolation(
                K_value,
                K[d_K - 1],
                NakagamiRiceCurves[d_K - 1][d_p],
                K[d_K],
                NakagamiRiceCurves[d_K][d_p],
            )
            v2 = linear_interpolation(
                K_value,
                K[d_K - 1],
                NakagamiRiceCurves[d_K - 1][d_p - 1],
                K[d_K],
                NakagamiRiceCurves[d_K][d_p - 1],
            )
            return linear_interpolation(p_value, P[d_p - 1], v2, P[d_p], v1)


def CombineDistributions(A_M, A_p, B_M, B_p, p):
    C_M = A_M + B_M

    Y_1 = A_p - A_M
    Y_2 = B_p - B_M

    Y_3 = math.sqrt(Y_1**2 + Y_2**2)

    if p < 50:
        return C_M + Y_3
    else:
        return C_M - Y_3


def InverseComplementaryCumulativeDistributionFunction(q):
    C_0 = 2.515516
    C_1 = 0.802853
    C_2 = 0.010328
    D_1 = 1.432788
    D_2 = 0.189269
    D_3 = 0.001308

    x = q
    if q > 0.5:
        x = 1.0 - x

    T_x = math.sqrt(-2.0 * math.log(x))

    zeta_x = ((C_2 * T_x + C_1) * T_x + C_0) / (((D_3 * T_x + D_2) * T_x + D_1) * T_x + 1.0)

    Q_q = T_x - zeta_x

    if q > 0.5:
        Q_q = -Q_q

    return Q_q


# TranshorizonSearch(path, terminal_1, terminal_2, f__mhz, A_dML__db, M_d, A_d0,Const)
def TranshorizonSearch(path, terminal_1, terminal_2, f_mhz, A_dML_db, M_d, A_d0):
    """
    Implements Step 6 of Annex 2, Section 3 of Recommendation ITU-R P.528-5.

    Args:
        path: Structure containing propagation path parameters.
        terminal_1: Structure containing low terminal geometry parameters.
        terminal_2: Structure containing high terminal geometry parameters.
        f_mhz: Frequency in MHz.
        A_dML_db: Diffraction loss at d_ML in dB.

    Returns:
        M_d: Slope of the diffraction line.
        A_d0: Intercept of the diffraction line.
        d_crx_km: Final search distance in km.
        CASE: Case as defined in Step 6.5.
    """

    CASE = CONST_MODE__SEARCH
    k = 0

    tropo = _GLOBAL_TROPO_PARAMS  # tropo is the global of TroposcatterParams
    tropo.clear()

    # Step 6.1. Initialize search parameters
    d_search_km = np.array([path.d_ML__km + 3, path.d_ML__km + 2])
    A_s_db = np.zeros(2)
    M_s = 0

    SEARCH_LIMIT = 100

    for i_search in range(SEARCH_LIMIT):
        A_s_db[1] = A_s_db[0]

        # Step 6.2
        troposcatter(path, terminal_1, terminal_2, d_search_km[0], f_mhz, tropo)
        A_s_db[0] = tropo.A_s__db

        # if loss is less than 20 dB, the result is not within valid part of model
        if tropo.A_s__db < 20.0:
            d_search_km[1] = d_search_km[0]
            d_search_km[0] += 1
            continue

        k += 1
        if k <= 1:  # need two points to draw a line and we don't have them both yet
            d_search_km[1] = d_search_km[0]
            d_search_km[0] += 1
            continue

        # Step 6.3
        M_s = (A_s_db[0] - A_s_db[1]) / (d_search_km[0] - d_search_km[1])  # [Eqn 3-10]

        if M_s <= M_d:
            d_crx_km = d_search_km[0]

            # Step 6.6
            A_d__db = M_d * d_search_km[1] + A_d0  # [Eqn 3-11]

            if A_s_db[1] >= A_d__db:
                CASE = 1  # CASE_1
            else:
                # Adjust the diffraction line to the troposcatter model
                M_d = (A_s_db[1] - A_dML_db) / (d_search_km[1] - path.d_ML__km)  # [Eqn 3-12]
                A_d0 = A_s_db[1] - (M_d * d_search_km[1])  # [Eqn 3-13]

                CASE = 2  # CASE_2

            return M_d, A_d0, d_crx_km, CASE

        d_search_km[1] = d_search_km[0]
        d_search_km[0] += 1

    # M_s was always greater than M_d. Default to diffraction-only transhorizon model
    CASE = 1  # CONST_MODE__DIFFRACTION
    d_crx_km = d_search_km[1]

    return M_d, A_d0, d_crx_km, WARNING__DFRAC_TROPO_REGION


def troposcatter(path, terminal_1, terminal_2, d_km, f_mhz, tropo):

    tropo.d_s__km = d_km - terminal_1.d_r__km - terminal_2.d_r__km

    if tropo.d_s__km <= 0.0:
        tropo.d_z__km = 0.0
        tropo.A_s__db = 0.0
        tropo.d_s__km = 0.0
        tropo.h_v__km = 0.0
        tropo.theta_s = 0.0
        tropo.theta_A = 0.0
    else:
        # Compute the geometric parameters
        tropo.d_z__km = 0.5 * tropo.d_s__km

        A_m = 1 / a_0__km
        dN = A_m - (1.0 / a_e__km)
        gamma_e__km = (N_s * 1e-6) / dN

        z_a__km = 1.0 / (2 * a_e__km) * (tropo.d_z__km / 2) ** 2
        z_b__km = 1.0 / (2 * a_e__km) * tropo.d_z__km**2

        Q_o = A_m - dN
        Q_a = A_m - dN / math.exp(min(35.0, z_a__km / gamma_e__km))
        Q_b = A_m - dN / math.exp(min(35.0, z_b__km / gamma_e__km))

        Z_a__km = (7.0 * Q_o + 6.0 * Q_a - Q_b) * (tropo.d_z__km**2 / 96.0)
        Z_b__km = (Q_o + 2.0 * Q_a) * (tropo.d_z__km**2 / 6.0)

        Q_A = A_m - dN / math.exp(min(35.0, Z_a__km / gamma_e__km))
        Q_B = A_m - dN / math.exp(min(35.0, Z_b__km / gamma_e__km))

        tropo.h_v__km = (Q_o + 2.0 * Q_A) * (tropo.d_z__km**2 / 6.0)
        tropo.theta_A = (Q_o + 4.0 * Q_A + Q_B) * tropo.d_z__km / 6.0
        tropo.theta_s = 2 * tropo.theta_A

        # Compute the scattering efficiency term
        epsilon_1 = 5.67e-6 * N_s**2 - 0.00232 * N_s + 0.031
        epsilon_2 = 0.0002 * N_s**2 - 0.06 * N_s + 6.6

        gamma = 0.1424 * (1.0 + epsilon_1 / math.exp(min(35.0, (tropo.h_v__km / 4.0) ** 6)))
        S_e__db = (
            83.1
            - epsilon_2 / (1.0 + 0.07716 * tropo.h_v__km**2)
            + 20 * math.log10((0.1424 / gamma) ** 2 * math.exp(gamma * tropo.h_v__km))
        )

        # Compute the scattering volume term
        X_A1__km2 = (terminal_1.h_e__km**2) + 4.0 * (a_e__km + terminal_1.h_e__km) * a_e__km * math.sin(
            terminal_1.d_r__km / (2 * a_e__km)
        ) ** 2
        X_A2__km2 = (terminal_2.h_e__km**2) + 4.0 * (a_e__km + terminal_2.h_e__km) * a_e__km * math.sin(
            terminal_2.d_r__km / (2 * a_e__km)
        ) ** 2

        ell_1__km = math.sqrt(X_A1__km2) + tropo.d_z__km
        ell_2__km = math.sqrt(X_A2__km2) + tropo.d_z__km
        ell__km = ell_1__km + ell_2__km

        s = (ell_1__km - ell_2__km) / ell__km
        eta = gamma * tropo.theta_s * ell__km / 2

        kappa = f_mhz / 0.0477

        rho_1__km = 2.0 * kappa * tropo.theta_s * terminal_1.h_e__km
        rho_2__km = 2.0 * kappa * tropo.theta_s * terminal_2.h_e__km

        SQRT2 = math.sqrt(2)

        A = (1 - s**2) ** 2

        X_v1 = (1 + s) ** 2 * eta
        X_v2 = (1 - s) ** 2 * eta

        q_1 = X_v1**2 + rho_1__km**2
        q_2 = X_v2**2 + rho_2__km**2

        B_s = (
            6
            + 8 * s**2
            + 8 * (1.0 - s) * X_v1**2 * rho_1__km**2 / q_1**2
            + 8 * (1.0 + s) * X_v2**2 * rho_2__km**2 / q_2**2
            + 2 * (1.0 - s**2) * (1 + 2 * X_v1**2 / q_1) * (1 + 2 * X_v2**2 / q_2)
        )

        C_s = (
            12
            * ((rho_1__km + SQRT2) / rho_1__km) ** 2
            * ((rho_2__km + SQRT2) / rho_2__km) ** 2
            * (rho_1__km + rho_2__km)
            / (rho_1__km + rho_2__km + 2 * SQRT2)
        )

        temp = (A * eta**2 + B_s * eta) * q_1 * q_2 / (rho_1__km**2 * rho_2__km**2)

        S_v__db = 10 * math.log10(temp + C_s)

        tropo.A_s__db = S_e__db + S_v__db + 10.0 * math.log10(kappa * tropo.theta_s**3 / ell__km)


def test_propagation_p528():
    """Test the P528 propagation model implementation."""
    random_number_gen = np.random.RandomState(101)
    p528 = PropagationP528(random_number_gen)

    # Test parameters
    distances_km = np.linspace(1, 1000, 100)
    h_1__meter = 40.0
    h_2__meter = 20000.0
    frequency_mhz = 4000.0 * np.ones(distances_km.shape)

    # Test with defaults (random)
    print(distances_km)

    results_default = p528.get_loss(distances_km, h_1__meter, h_2__meter, frequency_mhz)

    # Test with specific values
    results_specific = p528.get_loss(distances_km, h_1__meter, h_2__meter, frequency_mhz, time_percentage=80, polarization=1)

    # Print the results and distances side by side
    for d, loss_default, loss_specific in zip(distances_km, results_default, results_specific):
        print(f"Distance: {d:.2f} km, Default Loss: {loss_default:.2f} dB, Specific Loss: {loss_specific:.2f} dB")

    return distances_km, results_default, results_specific


if __name__ == "__main__":
    distances, losses_default, losses_specific = test_propagation_p528()

    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 6))
    plt.plot(distances, losses_default, label="Default (Random)")
    plt.plot(distances, losses_specific, label="Specific (p=80%, vertical pol.)")
    plt.grid(True)
    plt.xlabel("Distance (km)")
    plt.ylabel("Path Loss (dB)")
    plt.title("P528 Path Loss vs Distance - Different Configurations")
    plt.legend()
    plt.savefig("p528_pathloss_comparison.png")
    plt.close()
