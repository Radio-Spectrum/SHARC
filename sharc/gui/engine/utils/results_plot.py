"""
Results plotting module.

Move the original plotting logic from the monolithic sharc_gui.py into here.
This file should provide functions that accept:
 - a Matplotlib Figure / Axes (or create them)
 - plotting configuration (which fields to plot, CDF/CCDF, refs)
 - a list of result directories to read data from

Currently this module provides a placeholder API; implementers should port
the plotting functions and file readers here.
"""

from typing import List, Dict, Any


def draw_results_figure(fig: Any, axes_cfg: List[Dict[str, Any]], res_dirs: List[str]) -> None:
    """
    Draw results into 'fig' according to axes_cfg and res_dirs.
    - fig: Matplotlib Figure instance (or None to create a new one)
    - axes_cfg: list of dicts, example:
        [{"field":"SINR", "mode":"CDF", "yscale":"Linear", "refs": "5,10"}]
    - res_dirs: list of folder paths with result data
    """
    # TODO: Move the plotting implementation (CDF/CCDF, reading CSVs, etc.) from the old monolith.
    raise NotImplementedError("Please implement plotting logic here by porting from the original sharc_gui.py.")
