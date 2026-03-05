"""Shared-computation wrapper for :class:`AntennaArray` instances."""

import typing

import numpy as np

from sharc.antenna.antenna import Antenna
from sharc.antenna.antenna_array import AntennaArray
from sharc.parameters.imt.parameters_antenna_imt import ParametersAntennaImt
from sharc.support.geometry import RigidTransform


class AntennaArrayPool:
    """Creates antenna wrappers that share the same underlying array object."""

    def __init__(self):
        self.reset_pool(0)

    def reset_pool(self, max_antennas: int):
        self.antenna_pool: list[AntennaArray | None] = [None] * max_antennas
        self.shared_results_pool: list[dict | None] = [None] * max_antennas
        self._pool_idx = -1
        self._last_global2local_transform: RigidTransform | None = None

    @staticmethod
    def _same_transform(
        lhs: RigidTransform | None,
        rhs: RigidTransform | None,
    ) -> bool:
        if lhs is None and rhs is None:
            return True
        if lhs is None or rhs is None:
            return False
        return (
            np.array_equal(lhs.t, rhs.t)
            and np.array_equal(lhs.rot.as_quat(), rhs.rot.as_quat())
        )

    def append_antenna(
        self,
        par: ParametersAntennaImt,
        azimuth: float,
        elevation: float,
        global2local_transform: RigidTransform = None,
        *,
        per_element_taper_fn: typing.Callable = None,
    ):
        is_same_as_previous = self._same_transform(
            self._last_global2local_transform,
            global2local_transform,
        )

        if self._pool_idx < 0 or not is_same_as_previous:
            self._pool_idx += 1
            if self._pool_idx >= len(self.antenna_pool):
                raise ValueError(
                    "AntennaArrayPool capacity exceeded. Increase max_antennas"
                )

        pool_idx = self._pool_idx

        if self.antenna_pool[pool_idx] is None:
            self.antenna_pool[pool_idx] = AntennaArray(
                par,
                global2local_transform,
                per_element_taper_fn=per_element_taper_fn,
            )
            self.shared_results_pool[pool_idx] = {
                "all_beam_gains_by_co_channel": {},
            }

        base_ant = self.antenna_pool[pool_idx]
        shared_results = self.shared_results_pool[pool_idx]

        base_ant.add_beam(
            azimuth,
            90. - elevation,
        )
        beam_idx = len(base_ant.beams_list) - 1
        self._last_global2local_transform = global2local_transform

        return AntennaArrayShared(
            base_ant,
            shared_results,
            beam_idx=beam_idx,
        )


class AntennaArrayShared(Antenna):
    """Wraps one beam of a shared :class:`AntennaArray` instance."""

    def __init__(
        self,
        array: AntennaArray,
        shared_results: dict,
        beam_idx: int,
    ):
        super().__init__()
        self.array = array
        self.shared_results = shared_results
        self.beam_idx = beam_idx
        self.beams_list = self.array.beams_list

    def _calculate_all_beam_gains(
        self,
        phi_vec: np.ndarray,
        theta_vec: np.ndarray,
        co_channel: bool,
    ) -> np.ndarray:
        n_beams = len(self.array.beams_list)
        n_angles = len(phi_vec)

        phi_all = phi_vec.repeat(n_beams)
        theta_all = theta_vec.repeat(n_beams)
        beams_l = np.tile(np.arange(n_beams, dtype=int), n_angles)

        gain_all = self.array.calculate_gain(
            phi_vec=phi_all,
            theta_vec=theta_all,
            beams_l=beams_l,
            co_channel=co_channel,
        )

        return gain_all.reshape(n_angles, n_beams).T

    def calculate_gain(self, *args, **kwargs) -> np.array:
        phi_vec = np.atleast_1d(kwargs["phi_vec"])
        theta_vec = np.atleast_1d(kwargs["theta_vec"])
        co_channel = bool(kwargs.get("co_channel", True))

        cache = self.shared_results["all_beam_gains_by_co_channel"]

        if co_channel not in cache:
            cache[co_channel] = (
                self._calculate_all_beam_gains(
                    phi_vec,
                    theta_vec,
                    co_channel,
                )
            )

        return cache[co_channel][self.beam_idx]
