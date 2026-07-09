# -*- coding: utf-8 -*-
"""
Propagation models for the TopologyIndoorBuilding scenario, where Wi-Fi
APs (and, optionally, Wi-Fi stations) are indoor and the IMT network
(BS and/or UE) is outdoor.

Three distinct physical situations are handled by
PropagationIndoorBuilding, based on the indoor flag, building_id and
floor of both stations:

    1) Indoor <-> Indoor, SAME building (e.g. AP <-> STA inside the
       same building): no exterior wall is crossed, so Building Entry
       Loss (BEL) does NOT apply. The site-general indoor model of
       Recommendation ITU-R P.1238-13 (Annex, Section 3.1, eq. 1) is
       used as the base loss, PLUS a floor penetration loss term
       Lf(n) (Annex, Section 3.2, eq. 2 / Table 5) whenever the two
       stations are on different floors of that building.

    2) Indoor <-> Indoor, DIFFERENT buildings (e.g. AP in building A
       <-> AP in building B): the link leaves building A (1x BEL),
       travels outdoors, and enters building B (1x BEL) -> outdoor
       basic path loss + TWO Building Entry Losses. No floor
       penetration term is applied here (floor loss only applies
       within the same building, per eq. 2).

    3) Indoor <-> Outdoor (e.g. outdoor IMT BS/UE <-> indoor Wi-Fi AP):
       the link crosses exactly one exterior wall -> outdoor basic
       path loss + ONE Building Entry Loss (as before).

The outdoor portion of cases (2) and (3) uses PropagationUMa (3GPP
TR 38.901 Urban Macro) by default, since it is the outdoor macro model
already used elsewhere for the IMT system -- this is a better match for
realistic outdoor propagation than plain free space, which is kept
only as a lightweight fallback option.

Requires the Wi-Fi StationManager to expose `building_id` and `floor`
arrays (added to TopologyIndoorBuilding / generate_indoor_coordinates),
identifying, respectively, which building each indoor station belongs
to and which floor it is on. Outdoor (IMT) stations don't need
meaningful values for these; placeholders work since they are excluded
from cases (1)/(2) by the indoor flag alone.
"""

from multipledispatch import dispatch
import sys
import numpy as np

from sharc.station_manager import StationManager
from sharc.parameters.parameters import Parameters
from sharc.parameters.wifi.parameters_indoor_building import ParametersIndoorBuilding
from sharc.propagation.propagation import Propagation
from sharc.propagation.propagation_free_space import PropagationFreeSpace
from sharc.propagation.propagation_uma import PropagationUMa
from sharc.propagation.propagation_building_entry_loss import PropagationBuildingEntryLoss


class PropagationP1238(Propagation):
    """
    Site-general indoor propagation model according to Recommendation
    ITU-R P.1238-13, Annex, Section 3.1, eq. (1):

        Lb(d, f) = 10 * alpha * log10(d) + beta + 10 * gamma * log10(f)
                   + N(0, sigma)

    Coefficients are taken from Table 2, "Office" environment (chosen
    as the closest match to an indoor building / Wi-Fi deployment).

    NOTE: Recommendation ITU-R P.1238 does not define its own LOS
    probability model. This implementation reuses the 3GPP TR 38.901
    InH-Office LOS probability curve as a reasonable approximation for
    office-type indoor environments. Replace get_los_probability if a
    different LOS criterion is preferred.
    """

    # Table 2, Rec. ITU-R P.1238-13 -- "Office" environment
    # valid for f in [0.3, 294] GHz (LoS) / [0.3, 255] GHz (NLoS)
    # and d in [2, 27] m (LoS) / [4, 30] m (NLoS)
    COEFFICIENTS = {
        "LOS": {"alpha": 1.47, "beta": 34.17, "gamma": 2.08, "sigma": 3.68},
        "NLOS": {"alpha": 2.39, "beta": 30.13, "gamma": 2.40, "sigma": 5.01},
    }

    def get_loss(
        self,
        distance_3D: np.ndarray,
        frequency_MHz: np.ndarray,
        los_condition: np.ndarray,
        shadowing: bool,
    ) -> np.array:
        """
        Parameters
        ----------
            distance_3D : 3D distance between stations [m]
            frequency_MHz : center frequency [MHz]
            los_condition : bool array, True where the link is LoS
            shadowing : whether to add the log-normal shadowing term
                        (built into sigma per Table 2)

        Returns
        -------
            array with path loss values, dimensions of distance_3D
        """
        frequency_GHz = frequency_MHz / 1000
        loss = np.zeros(distance_3D.shape)

        for cond, mask in (("LOS", los_condition), ("NLOS", ~los_condition)):
            if not np.any(mask):
                continue
            c = self.COEFFICIENTS[cond]
            loss[mask] = (
                10 * c["alpha"] * np.log10(distance_3D[mask]) + c["beta"] +
                10 * c["gamma"] * np.log10(frequency_GHz[mask])
            )
            if shadowing:
                loss[mask] += self.random_number_gen.normal(
                    0, c["sigma"], np.count_nonzero(mask),
                )

        return loss

    def get_los_probability(self, distance_2D: np.array) -> np.array:
        """LOS probability curve reused from 3GPP TR 38.901 InH-Office."""
        p_los = np.ones(distance_2D.shape)
        id1 = np.where((distance_2D > 1.2) & (distance_2D < 6.5))
        p_los[id1] = np.exp(-(distance_2D[id1] - 1.2) / 4.7)
        id2 = np.where(distance_2D >= 6.5)
        p_los[id2] = np.exp(-(distance_2D[id2] - 6.5) / 32.6) * 0.32
        return p_los

    def get_los_condition(self, distance_2D: np.array) -> np.array:
        p_los = self.get_los_probability(distance_2D)
        return self.random_number_gen.random_sample(p_los.shape) < p_los


class FloorPenetrationLoss:
    """
    Floor penetration loss factor Lf(n), Recommendation ITU-R P.1238-13,
    Annex, Section 3.2, Table 5. n = number of floors penetrated
    (n >= 1); Lf = 0 dB for n = 0 (same floor).

    Table 5 only gives discrete values for a handful of (frequency,
    n_floors) combinations per environment, plus explicit linear
    formulas for the 1.8-2 GHz (office/commercial) and 5.8 GHz
    (office) bands. Values beyond the tabulated n_floors, for bands
    without an explicit formula, are extrapolated linearly using the
    slope (dB/floor) observed between the last two tabulated points
    (or a default slope, when only one point is available). This
    extrapolation is an engineering approximation, not something the
    Recommendation defines explicitly.
    """

    # freq_GHz -> {n_floors: Lf_dB}
    TABLES = {
        "OFFICE": {
            2.0: {1: 15, 2: 19, 3: 23},           # 15 + 4*(n-1), Table 5 formula
            3.5: {1: 18, 2: 26},
            5.2: {1: 16},
            5.8: {n: 22 + 6 * (n - 1) for n in range(1, 11)},  # 22 + 6*(n-1)
        },
        "RESIDENTIAL": {
            0.9: {1: 9, 2: 19, 3: 24},
            2.4: {1: 10},
            5.2: {1: 13},
        },
        "COMMERCIAL": {
            2.0: {1: 6, 2: 9, 3: 12},             # 6 + 3*(n-1), Table 5 formula
        },
    }

    # fallback slope (dB/floor) when only one tabulated point exists
    # for the nearest frequency, taken as a typical value across bands
    # for that environment
    DEFAULT_SLOPE = {
        "OFFICE": 7.0,
        "RESIDENTIAL": 5.0,
        "COMMERCIAL": 3.0,
    }

    @classmethod
    def _loss_scalar(cls, frequency_MHz: float, n_floors: int, environment: str) -> float:
        if n_floors <= 0:
            return 0.0

        table = cls.TABLES[environment]
        freq_GHz = frequency_MHz / 1000
        nearest_freq = min(table.keys(), key=lambda f: abs(f - freq_GHz))
        floor_map = table[nearest_freq]
        max_n = max(floor_map.keys())

        if n_floors in floor_map:
            return float(floor_map[n_floors])

        if n_floors < max_n:
            # gap in the middle of tabulated range: linear interpolation
            lower_n = max(k for k in floor_map if k < n_floors)
            upper_n = min(k for k in floor_map if k > n_floors)
            lo, hi = floor_map[lower_n], floor_map[upper_n]
            frac = (n_floors - lower_n) / (upper_n - lower_n)
            return lo + frac * (hi - lo)

        # extrapolate beyond the last tabulated point
        if max_n >= 2:
            slope = floor_map[max_n] - floor_map[max_n - 1]
        else:
            slope = cls.DEFAULT_SLOPE[environment]

        return float(floor_map[max_n] + slope * (n_floors - max_n))

    @classmethod
    def get_loss(
        cls,
        frequency_MHz: np.ndarray,
        n_floors: np.ndarray,
        environment: str = "OFFICE",
    ) -> np.array:
        """
        Vectorized floor penetration loss.

        Parameters
        ----------
            frequency_MHz : center frequency [MHz], array
            n_floors : number of floors penetrated (>= 0), array,
                       same shape as frequency_MHz
            environment : "OFFICE", "RESIDENTIAL" or "COMMERCIAL"

        Returns
        -------
            array with Lf values [dB], same shape as inputs
        """
        environment = environment.upper()
        vec_loss = np.vectorize(
            lambda f, n: cls._loss_scalar(f, int(n), environment),
        )
        return vec_loss(frequency_MHz, n_floors)


class PropagationIndoorBuilding(Propagation):
    """
    Wrapper propagation class for the TopologyIndoorBuilding scenario.
    Routes each station_a <-> station_b link to the model appropriate
    for its indoor/outdoor, same-building/different-building and
    same-floor/different-floor condition (see module docstring).
    """

    def __init__(
        self,
        random_number_gen: np.random.RandomState,
        param: ParametersIndoorBuilding,
    ):
        super().__init__(random_number_gen)

        # basic_path_loss: model used for the outdoor portion of any
        # link that crosses at least one exterior wall (indoor<->
        # outdoor, or indoor<->indoor across different buildings).
        # UMa (3GPP TR 38.901 Urban Macro) is the recommended choice,
        # matching the outdoor macro model already used for the IMT
        # system elsewhere. FSPL is kept as a lightweight fallback.
        if param.basic_path_loss == "FSPL":
            self.bpl = PropagationFreeSpace(random_number_gen)
        elif param.basic_path_loss == "UMa":
            self.bpl = PropagationUMa(random_number_gen)
        else:
            sys.stderr.write(
                "ERROR\nInvalid indoor building basic path loss model: " +
                param.basic_path_loss,
            )
            sys.exit(1)

        self.bel = PropagationBuildingEntryLoss(random_number_gen)
        self.p1238 = PropagationP1238(random_number_gen)
        self.building_class = param.building_class
        # environment used for floor penetration loss lookup (Table 5)
        self.floor_loss_environment = getattr(param, "floor_loss_environment", "OFFICE")

    @dispatch(
        Parameters, float, StationManager,
        StationManager, np.ndarray, np.ndarray,
    )
    def get_loss(
        self,
        params: Parameters,
        frequency: float,
        station_a: StationManager,
        station_b: StationManager,
        station_a_gains=None,
        station_b_gains=None,
    ) -> np.array:
        """
        Wrapper function to fit the Propagation ABC class interface.
        """
        wrap_around_enabled = False
        if params.imt.topology.type == "MACROCELL":
            wrap_around_enabled = params.imt.topology.macrocell.wrap_around \
                and params.imt.topology.macrocell.num_clusters == 1
        if params.imt.topology.type == "HOTSPOT":
            wrap_around_enabled = params.imt.topology.hotspot.wrap_around \
                and params.imt.topology.hotspot.num_clusters == 1

        if wrap_around_enabled:
            dist_2d, dist_3d, _, _ = station_a.get_dist_angles_wrap_around(station_b)
        else:
            dist_2d = station_a.get_distance_to(station_b)
            dist_3d = station_a.get_3d_distance_to(station_b)

        frequency_array = frequency * np.ones(dist_2d.shape)
        elevation = station_a.get_elevation(station_b)

        indoor_a = np.tile(
            station_a.indoor[:, np.newaxis], (1, station_b.num_stations),
        )
        indoor_b = np.tile(
            station_b.indoor[np.newaxis, :], (station_a.num_stations, 1),
        )

        bid_a_1d = getattr(station_a, "building_id", -np.ones(station_a.num_stations, dtype=int))
        bid_b_1d = getattr(station_b, "building_id", -np.ones(station_b.num_stations, dtype=int))
        building_id_a = np.tile(bid_a_1d[:, np.newaxis], (1, station_b.num_stations))
        building_id_b = np.tile(bid_b_1d[np.newaxis, :], (station_a.num_stations, 1))

        floor_a_1d = getattr(station_a, "floor", np.zeros(station_a.num_stations, dtype=int))
        floor_b_1d = getattr(station_b, "floor", np.zeros(station_b.num_stations, dtype=int))
        floor_a = np.tile(floor_a_1d[:, np.newaxis], (1, station_b.num_stations))
        floor_b = np.tile(floor_b_1d[np.newaxis, :], (station_a.num_stations, 1))

        # antenna heights, kept as 1D arrays (station_a.num_stations,)
        # and (station_b.num_stations,) -- PropagationUMa broadcasts
        # them internally against the 2D distance arrays, following the
        # same "ue_height = station_a.height, bs_height = station_b.height"
        # convention used in PropagationUMa's own Parameters wrapper
        height_a = station_a.height
        height_b = station_b.height

        return self.get_loss(
            dist_3d,
            dist_2d,
            frequency_array,
            elevation,
            indoor_a,
            indoor_b,
            building_id_a,
            building_id_b,
            floor_a,
            floor_b,
            height_a,
            height_b,
            params.imt.shadowing,
        )

    # pylint: disable=function-redefined
    # pylint: disable=arguments-renamed
    @dispatch(
        np.ndarray, np.ndarray, np.ndarray, np.ndarray,
        np.ndarray, np.ndarray, np.ndarray, np.ndarray,
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool,
    )
    def get_loss(
        self,
        distance_3D: np.ndarray,
        distance_2D: np.ndarray,
        frequency: np.ndarray,
        elevation: np.ndarray,
        indoor_a: np.ndarray,
        indoor_b: np.ndarray,
        building_id_a: np.ndarray,
        building_id_b: np.ndarray,
        floor_a: np.ndarray,
        floor_b: np.ndarray,
        height_a: np.ndarray,
        height_b: np.ndarray,
        shadowing_flag: bool,
    ) -> np.array:
        """
        Calculates path loss for each station_a <-> station_b link,
        picking the model based on the indoor condition, building and
        floor of both ends.

        height_a / height_b : 1D antenna height arrays, shapes
        (distance_2D.shape[0],) and (distance_2D.shape[1],)
        respectively -- only used when the outdoor model is UMa.
        """
        loss = np.zeros(distance_2D.shape)

        both_indoor = indoor_a & indoor_b
        same_building = both_indoor & (building_id_a == building_id_b)
        diff_building = both_indoor & (building_id_a != building_id_b)
        one_indoor = indoor_a ^ indoor_b
        both_outdoor = (~indoor_a) & (~indoor_b)

        # ---- (1) Indoor <-> Indoor, SAME building: ITU-R P.1238 base
        # loss + floor penetration loss (Table 5) if floors differ ----
        if np.any(same_building):
            los_condition = self.p1238.get_los_condition(distance_2D)
            base_loss = self.p1238.get_loss(
                distance_3D, frequency, los_condition, shadowing_flag,
            )
            n_floors = np.abs(floor_a - floor_b)
            floor_loss = FloorPenetrationLoss.get_loss(
                frequency, n_floors, self.floor_loss_environment,
            )
            loss[same_building] = (base_loss + floor_loss)[same_building]

        # ---- (2) Indoor <-> Indoor, DIFFERENT buildings: outdoor path
        # (UMa) + TWO Building Entry Losses ----
        if np.any(diff_building):
            outdoor_loss = self._get_outdoor_loss(
                distance_3D, distance_2D, frequency, height_a, height_b, shadowing_flag,
            )
            bel_loss = self.bel.get_loss(
                frequency, elevation, "RANDOM", self.building_class,
            )
            loss[diff_building] = (outdoor_loss + 2 * bel_loss)[diff_building]

        # ---- (3) Indoor <-> Outdoor: outdoor path (UMa) + ONE Building
        # Entry Loss ----
        if np.any(one_indoor):
            outdoor_loss = self._get_outdoor_loss(
                distance_3D, distance_2D, frequency, height_a, height_b, shadowing_flag,
            )
            bel_loss = self.bel.get_loss(
                frequency, elevation, "RANDOM", self.building_class,
            )
            loss[one_indoor] = (outdoor_loss + bel_loss)[one_indoor]

        # ---- Outdoor <-> Outdoor: not expected in this scenario, but
        # fall back to the same outdoor model so the array is fully
        # populated ----
        if np.any(both_outdoor):
            outdoor_loss = self._get_outdoor_loss(
                distance_3D, distance_2D, frequency, height_a, height_b, shadowing_flag,
            )
            loss[both_outdoor] = outdoor_loss[both_outdoor]

        return loss

    def _get_outdoor_loss(self, distance_3D, distance_2D, frequency, height_a, height_b, shadowing_flag):
        """
        Basic path loss for the outdoor portion of a link that crosses
        at least one exterior wall (or the fully-outdoor fallback).
        """
        if isinstance(self.bpl, PropagationUMa):
            # PropagationUMa.get_loss(distance_3d, distance_2d, frequency,
            #                          bs_height, ue_height, shadowing)
            # bs_height/ue_height are 1D and broadcast internally;
            # following PropagationUMa's own convention: bs_height comes
            # from the "b" side (columns), ue_height from the "a" side
            # (rows) of the distance matrix.
            return self.bpl.get_loss(
                distance_3D, distance_2D, frequency,
                height_b, height_a, shadowing_flag,
            )
        return self.bpl.get_loss(distance_3D=distance_3D, frequency=frequency)


if __name__ == '__main__':
    class _FakeParam:
        basic_path_loss = "UMa"
        building_class = "TRADITIONAL"
        floor_loss_environment = "OFFICE"

    prop = PropagationIndoorBuilding(np.random.RandomState(), _FakeParam())

    # --- case A: outdoor IMT <-> indoor Wi-Fi AP, using UMa outdoors ---
    num_bs, num_ap = 3, 10
    distance_2D = 300 * np.random.random((num_bs, num_ap)) + 20
    h_bs = 25 * np.ones(num_bs)
    h_ap = 1.5 * np.ones(num_ap)
    distance_3D = np.sqrt(distance_2D ** 2 + (h_bs[:, np.newaxis] - h_ap) ** 2)
    frequency = 3500 * np.ones(distance_2D.shape)
    elevation = np.degrees(np.arctan2(h_bs[:, np.newaxis] - h_ap, distance_2D))
    indoor_a = np.zeros((num_bs, num_ap), dtype=bool)
    indoor_b = np.ones((num_bs, num_ap), dtype=bool)
    bid_a = -np.ones((num_bs, num_ap), dtype=int)
    bid_b = np.zeros((num_bs, num_ap), dtype=int)
    floor_a = np.zeros((num_bs, num_ap), dtype=int)
    floor_b = np.zeros((num_bs, num_ap), dtype=int)
    height_a = h_bs      # station_a = IMT BS
    height_b = h_ap       # station_b = Wi-Fi AP

    loss_imt_wifi = prop.get_loss(
        distance_3D, distance_2D, frequency, elevation,
        indoor_a, indoor_b, bid_a, bid_b, floor_a, floor_b,
        height_a, height_b, False,
    )
    print("IMT outdoor (UMa) <-> Wi-Fi AP indoor (+BEL):\n", loss_imt_wifi)

    # --- case B: Wi-Fi AP (building 0) <-> Wi-Fi AP (building 1), UMa outdoors ---
    num_ap_a, num_ap_b = 3, 5
    distance_2D = 200 * np.random.random((num_ap_a, num_ap_b)) + 10
    h_ap_a = 3 * np.ones(num_ap_a)
    h_ap_b = 3 * np.ones(num_ap_b)
    distance_3D = np.sqrt(distance_2D ** 2 + (h_ap_a[:, np.newaxis] - h_ap_b) ** 2)
    frequency = 5800 * np.ones(distance_2D.shape)
    elevation = np.degrees(np.arctan2(h_ap_a[:, np.newaxis] - h_ap_b, distance_2D))
    indoor_a = np.ones((num_ap_a, num_ap_b), dtype=bool)
    indoor_b = np.ones((num_ap_a, num_ap_b), dtype=bool)
    bid_a = np.zeros((num_ap_a, num_ap_b), dtype=int)
    bid_b = np.ones((num_ap_a, num_ap_b), dtype=int)
    floor_a = np.zeros((num_ap_a, num_ap_b), dtype=int)
    floor_b = np.zeros((num_ap_a, num_ap_b), dtype=int)

    loss_diff_building = prop.get_loss(
        distance_3D, distance_2D, frequency, elevation,
        indoor_a, indoor_b, bid_a, bid_b, floor_a, floor_b,
        h_ap_a, h_ap_b, False,
    )
    print("Wi-Fi AP <-> Wi-Fi AP (different buildings, UMa + 2xBEL):\n", loss_diff_building)