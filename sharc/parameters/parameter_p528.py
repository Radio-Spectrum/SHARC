# -*- coding: utf-8 -*-
"""Parameters definitions for P528 propagation model
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union, Optional
import numpy as np

from sharc.parameters.parameters_base import ParametersBase

POL_H = 0  # horizontal
POL_V = 1  # vertical


@dataclass
class ParametersP528(ParametersBase):
    """Dataclass containing the P.528 propagation model parameters.

    Fields:
        time_percentage : float in [1,99] or "RANDOM"
        polarization    : 0 (horizontal), 1 (vertical) or "RANDOM"
        channel_model   : always "P528"
        Ns              : optional surface refractivity (N-units) used in §11 troposcatter
                          (leave None to use model default, e.g., 301.0)
    """

    time_percentage: Union[float, str] = "RANDOM"
    polarization: Union[int, str] = "RANDOM"
    channel_model: str = "P528"
    Ns: Optional[float] = None  # if None, the model uses the internal default (e.g. 301.0)

    # -------------------------
    # Compat layer to PropagationP528:
    # .p_time and .Tpol are the names the kernel expects.
    # -------------------------
    @property
    def p_time(self) -> float:
        """Numeric time percentage for the model (if 'RANDOM', returns 50.0 by default)."""
        if self.time_percentage == "RANDOM":
            # Deterministic fallback value for compatibility when 'RANDOM' is not resolved yet.
            return 50.0
        return float(self.time_percentage)

    @property
    def Tpol(self) -> int:
        """Numeric polarization flag for the model (if 'RANDOM', returns vertical by default)."""
        if self.polarization == "RANDOM":
            # Deterministic fallback choice when 'RANDOM' is not resolved yet.
            return POL_V
        val = int(self.polarization)
        if val not in (POL_H, POL_V):
            raise ValueError("ParametersP528.Tpol must be 0 (H) or 1 (V).")
        return val

    # -------------------------
    # Randomization helper (optional)
    # -------------------------
    def resolve(self,
                rng: Optional[np.random.RandomState] = None,
                time_rng: tuple[float, float] = (1.0, 99.0)) -> "ParametersP528":
        """Materializes 'RANDOM' fields into numeric values and returns a new instance.

        This avoids in-place modification so that if called per iteration,
        the original 'RANDOM' configuration is preserved.

        Args:
            rng: np.random.RandomState for reproducibility; if None, uses RandomState().
            time_rng: interval (min, max) to draw time_percentage when 'RANDOM'.

        Returns:
            A new ParametersP528 instance with time_percentage/polarization resolved.
        """
        import copy
        resolved = copy.copy(self)

        if rng is None:
            rng = np.random.RandomState()

        # time_percentage
        if resolved.time_percentage == "RANDOM":
            lo, hi = float(time_rng[0]), float(time_rng[1])
            lo = max(1.0, lo)
            hi = min(99.0, hi)
            if lo > hi:
                lo, hi = hi, lo
            resolved.time_percentage = float(rng.uniform(lo, hi))

        # polarization
        if resolved.polarization == "RANDOM":
            resolved.polarization = int(rng.choice([POL_H, POL_V]))

        # sanity
        resolved.validate("ParametersP528")
        return resolved

    # -------------------------
    # Validation
    # -------------------------
    def validate(self, ctx: str):
        super().validate(ctx)
        # channel_model
        if self.channel_model != "P528":
            raise ValueError(
                f"{ctx}: Invalid channel_model '{self.channel_model}'. Must be 'P528'."
            )

        # time_percentage
        if isinstance(self.time_percentage, str):
            if self.time_percentage != "RANDOM":
                raise ValueError(
                    f"{ctx}: Invalid time_percentage {self.time_percentage}. "
                    "Must be between 1-99 or 'RANDOM'"
                )
        else:
            try:
                time_pct = float(self.time_percentage)
                if not (1.0 <= time_pct <= 99.0):
                    raise ValueError(
                        f"{ctx}: Invalid time_percentage {time_pct}. "
                        "Must be between 1-99 or 'RANDOM'"
                    )
            except (ValueError, TypeError):
                raise ValueError(
                    f"{ctx}: Invalid time_percentage {self.time_percentage}. "
                    "Must be between 1-99 or 'RANDOM'"
                )

        # polarization
        if isinstance(self.polarization, str):
            if self.polarization != "RANDOM":
                raise ValueError(
                    f"{ctx}: Invalid polarization {self.polarization}. "
                    "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                )
        else:
            try:
                pol = int(self.polarization)
                if pol not in (POL_H, POL_V):
                    raise ValueError(
                        f"{ctx}: Invalid polarization {pol}. "
                        "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                    )
            except (ValueError, TypeError):
                raise ValueError(
                    f"{ctx}: Invalid polarization {self.polarization}. "
                    "Must be 0 (horizontal), 1 (vertical) or 'RANDOM'"
                )

        # Ns (if provided)
        if self.Ns is not None:
            try:
                Ns_val = float(self.Ns)
                if not (100.0 <= Ns_val <= 450.0):
                    # typical Ns range; adjust according to your climate database
                    raise ValueError(
                        f"{ctx}: Ns={Ns_val} out of expected range [100, 450]."
                    )
            except (ValueError, TypeError):
                raise ValueError(
                    f"{ctx}: Invalid Ns {self.Ns}. Must be float or None."
                )
