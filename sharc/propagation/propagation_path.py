from sharc.station_manager import StationManager
import typing
import numpy as np

from sharc.parameters.parameters import Parameters
from sharc.propagation.propagation import Propagation


class PropagationPath():
    # either
    # - (sta_a == IMT UE) and (sta_b == IMT BS)
    # OR
    # - (sta_a == System) and (sta_b == IMT BS)
    # OR
    # - (sta_a == System) and (sta_b == IMT UE)
    sta_a: StationManager
    sta_b: StationManager

    # mask to know what paths are valid paths
    _mask: np.ndarray  # shape (sys_a.num_station, sys_b.num_station)

    # mask to remove duplicated calculations
    _deduplicated_mask: np.ndarray  # shape (sys_a.num_station, sys_b.num_station)

    # how to remove useless calculations
    _mask_strategies: list[typing.Callable] = []

    _orig_shape: tuple[int, int]

    _propagation: Propagation

    def __init__(
        self,
        sta_a: StationManager,
        sta_b: StationManager,
        mask_strategies: list[typing.Callable] = []
    ):
        """Initializes PropagationPath between station_a and station_b
        considering masking functions passed. By default stations at the same place
        may or may not be masked, since some propagation models depend on more than
        just station position.
        """
        self.sta_a = sta_a
        self.sta_b = sta_b
        self._orig_shape = (self.sta_a.num_stations, self.sta_b.num_stations)
        self._mask_strategies = mask_strategies

    def get_path_loss(
        self,
        propagation: Propagation,
        parameters: Parameters,
        frequency: float,
        *,
        sta_a_gains=None,
        sta_b_gains=None,
    ):
        """Calculates mask depending on propagation, then calls the propagation
        get_path_loss methods that may or may not consider the given paths.
        """
        if propagation.needs_antenna_gains:
            # NOTE: currently implemented propagation models that require gain
            # DIFFERENTIATE between stations at the same position
            # so we can't deduplicate solely based on (position, indoor, ...)
            self.calc_mask(deduplicate=False)
        else:
            # NOTE: making sure the propagation has set needs_antenna_gains
            # if it needs the gains
            sta_a_gains = None
            sta_b_gains = None
            # NOTE: only propagation models that require gain
            # differentiate between stations at the same position
            self.calc_mask(deduplicate=True)

        return propagation.get_path_loss(
            parameters,
            frequency,
            self,
            sta_a_gains,
            sta_b_gains,
        )

    def calc_mask(self, *, deduplicate: bool):
        mask = np.ones(self._orig_shape, dtype=bool)
        for mask_fn in self._mask_strategies:
            mask = mask_fn(self.sta_a, self.sta_b, mask)

        if deduplicate:
            self._set_mask_and_deduplicate(mask)
        else:
            self._set_mask(mask)
            self._set_deduplication_info(
                mask,
                np.arange(len(self._paths_from_to))
            )

    def mtx_to_masked(self, mtx: np.ndarray):
        """Receives matrix occurring from operations of sta_a to sta_b
        and returns 1d vector filtering only active paths
        """
        assert mtx.shape[:2] == self._orig_shape
        return mtx[self._deduplicated_mask]

    def sta_a_to_masked(self, vec: np.ndarray):
        """Receives vector occurring from operations of sta_a
        and returns elements for all active paths
        """
        assert vec.shape[0] == self._orig_shape[0]
        return vec[self._deduped_paths_from_to[:, 0]]

    def sta_b_to_masked(self, vec: np.ndarray):
        """Receives vector occurring from operations of sta_b
        and returns elements for all active paths
        """
        assert vec.shape[0] == self._orig_shape[1]
        return vec[self._deduped_paths_from_to[:, 1]]

    def from_masked_mtx(self, vec: np.ndarray):
        """Receives 1d vector filtering that only contains active paths
        and returns original matrix occurring from operations of sta_a to sta_b
        """
        assert vec.shape == (self._n_deduped_paths,)

        mtx = np.full(self._orig_shape, np.nan)
        expanded_vec = vec[self._deduped_paths_representative_node]
        mtx[self._mask] = expanded_vec

        return mtx

    def _set_mask_and_deduplicate(self, mask):
        self._mask = mask
        self._paths_from_to = np.stack(np.where(mask), axis=-1)
        self._n_paths = len(self._paths_from_to)

        dedupe_mask, representative_nodes = self._deduplicate(
            self.sta_a, self.sta_b, self._paths_from_to
        )
        self._set_deduplication_info(dedupe_mask, representative_nodes)

    def _set_mask(self, mask):
        self._mask = mask
        self._paths_from_to = np.stack(np.where(mask), axis=-1)
        self._n_paths = len(self._paths_from_to)

    def _set_deduplication_info(self, deduplicated_mask, representative_nodes):
        self._deduplicated_mask = deduplicated_mask
        self._deduped_paths_from_to = np.stack(np.where(deduplicated_mask), axis=-1)
        self._deduped_paths_representative_node = representative_nodes
        self._n_deduped_paths = np.sum(deduplicated_mask)

    def _deduplicate(
            self, sta_a, sta_b, paths_from_to,
        ):
        """Maps duplicated stations and new mask.
        """
        duplicated_sta_a = self._get_representative_nodes(sta_a)
        duplicated_sta_b = self._get_representative_nodes(sta_b)

        deduped_paths_from_to = np.copy(paths_from_to)

        deduped_paths_from_to[:, 0] = duplicated_sta_a[
            paths_from_to[:, 0]
        ]
        deduped_paths_from_to[:, 1] = duplicated_sta_b[
            paths_from_to[:, 1]
        ]

        # since deduped_paths_from_to is already ordered
        # np.unique's unstable sort doesn't eff it up
        uniq_deduped_paths_from_to, adjacency_vec = np.unique(
            deduped_paths_from_to,
            axis=0,
            return_inverse=True
        )

        deduplicated_mask = np.zeros((sta_a.num_stations, sta_b.num_stations), dtype=bool)
        deduplicated_mask[
            uniq_deduped_paths_from_to[:, 0], uniq_deduped_paths_from_to[:, 1]
        ] = True

        return deduplicated_mask, adjacency_vec

    @staticmethod
    def _get_representative_nodes(sta: StationManager):
        # tuples for what needs to be considered for differentiating
        # stations for deduplication
        representative_tuples = np.stack([
                sta.geom.x_global,
                sta.geom.y_global,
                sta.geom.z_global,
                sta.indoor,
            ], axis=-1)

        # like an adjacency matrix, but for tree-like struct
        # e.g. graph where each node points to itself or its representative
        adjacency_vec = np.zeros((len(representative_tuples),))
        repr_nodes = {}

        # NOTE: tried using numpy but np.unique unstable sorts
        # and makes the code really ugly
        for i in range(len(representative_tuples)):
            tup = tuple(representative_tuples[i])
            if tup not in repr_nodes:
                repr_nodes[tup] = i
            adjacency_vec[i] = repr_nodes[tup]

        return adjacency_vec

    @staticmethod
    def create_default(
        sta_a,
        sta_b,
    ) -> "PropagationPath":
        """Creates a PropagationPath between stations considering
        which ones should exist.
        Check default behavior to understand what paths "should exist"
        by default
        """
        mask_fns = [
            path_mask_inactive_stations,
        ]

        if sta_a.is_space_station or sta_b.is_space_station:
            # care for through earth interference
            mask_fns.append(
                create_path_mask_low_elevation_sat_from_es(0.0)
            )

        # if one of the stations considers a maximum earth path distance
        # for interference, we remove those paths
        max_interf_dist = np.inf
        if sta_a.max_earth_sta_interf_distance is not None:
            max_interf_dist = min(
                max_interf_dist,
                sta_a.max_earth_sta_interf_distance,
            )
        if sta_b.max_earth_sta_interf_distance is not None:
            max_interf_dist = min(
                max_interf_dist,
                sta_b.max_earth_sta_interf_distance,
            )

        if max_interf_dist < np.inf:
            mask_fns.append(
                create_path_mask_distant_earth_stations(max_interf_dist),
            )

        return PropagationPath(sta_a, sta_b, mask_fns)

def create_path_mask_distant_earth_stations(distance_m: float):
    """Receives a distance in meters and returns a function
    deactivate paths between distant earth stations
    """
    def path_mask_distant_earth_stations(
        sta_a: StationManager,
        sta_b: StationManager,
        acc_mask: np.ndarray[np.ndarray[bool]]
    ):
        if sta_a.is_space_station or sta_b.is_space_station:
            return acc_mask

        dists = sta_a.geom.get_3d_distance_to(sta_b.geom)
        acc_mask[dists > distance_m] = False

        return acc_mask

    return path_mask_distant_earth_stations


def create_path_mask_low_elevation_sat_from_es(min_elev_deg: float = 0.0):
    """Receives a distance in meters and returns a function
    deactivate paths between distant earth stations
    """
    def path_mask_low_elevation_sat_from_es(
        sta_a: StationManager,
        sta_b: StationManager,
        acc_mask: np.ndarray[np.ndarray[bool]]
    ):
        es: StationManager = None
        ss: StationManager = None
        if sta_a.is_space_station and not sta_b.is_space_station:
            transpose = True
            es = sta_b
            ss = sta_a
        elif not sta_a.is_space_station and sta_b.is_space_station:
            transpose = False
            es = sta_a
            ss = sta_b
        else:
            return acc_mask

        elevs = es.geom.get_local_elevation(ss.geom)
        if transpose:
            elevs = elevs.T
        acc_mask[elevs < min_elev_deg] = False

        return acc_mask

    return path_mask_low_elevation_sat_from_es


def path_mask_inactive_stations(
    sta_a: StationManager,
    sta_b: StationManager,
    acc_mask: np.ndarray[np.ndarray[bool]]
):
    acc_mask[~sta_a.active, :] = False
    acc_mask[:, ~sta_b.active] = False

    return acc_mask


if __name__ == "__main__":
    bs = StationManager(2)
    ue = StationManager(6)
    bs.geom.set_global_coords(
        np.repeat(0., 2),
        np.repeat(0., 2),
        np.repeat(1.5, 2),
    )

    ue.geom.set_global_coords(
        np.linspace(10., 60., 6),
        np.linspace(10., 60., 6),
        np.repeat(1.5, 6),
    )
    path = PropagationPath(bs, ue)
    path._set_mask_and_deduplicate(
        np.array([
             [
                 True, True, True, False, False, False
             ],
             [
                 False, False, False, True, True, True
             ],
        ])
    )

    # print("path.deduplicated_mask", path.deduplicated_mask)
    # print("path.mask", path.mask)
    print("path._paths_from_to", path._paths_from_to)
    print("path.deduplicated_mask", path._deduplicated_mask)
    dist2d = bs.geom.get_local_distance_to(ue.geom)
    print("dist2d", dist2d)
    masked_dist2d = path.to_masked(dist2d)
    print("masked_dist2d", masked_dist2d)
    unmasked_dist2d = path.from_masked(masked_dist2d)
    print("unmasked_dist2d", unmasked_dist2d)

    print()
    print()
    print("#####################3")
    print()

    # bs.active[0] = False
    ue.active[2] = False
    path = PropagationPath.create_default(bs, ue)
    path.calc_mask(deduplicate=True)
    print("path._paths_from_to", path._paths_from_to)
    print("path.deduplicated_mask", path._deduplicated_mask)
    dist2d = path.sta_a.geom.get_local_distance_to(path.sta_b.geom)
    print("dist2d", dist2d)
    masked_dist2d = path.to_masked(dist2d)
    print("masked_dist2d", masked_dist2d)
    unmasked_dist2d = path.from_masked(masked_dist2d)
    print("unmasked_dist2d", unmasked_dist2d)

    print()
    print()
    print("#####################3")
    print()

    path = PropagationPath.create_default(bs, ue)
    path.calc_mask(deduplicate=False)
    print("path._paths_from_to", path._paths_from_to)
    print("path.deduplicated_mask", path._deduplicated_mask)
    dist2d = path.sta_a.geom.get_local_distance_to(path.sta_b.geom)
    print("dist2d", dist2d)
    masked_dist2d = path.to_masked(dist2d)
    print("masked_dist2d", masked_dist2d)
    unmasked_dist2d = path.from_masked(masked_dist2d)
    print("unmasked_dist2d", unmasked_dist2d)
