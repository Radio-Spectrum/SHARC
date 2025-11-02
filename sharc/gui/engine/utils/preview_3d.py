"""
3D preview drawing helpers. This module draws a simple Earth sphere and
example satellite markers. It is intentionally lightweight and purely
visual — the real application should feed satellite/topology data.
"""

from typing import Any
import numpy as np
import matplotlib.pyplot as plt


def setup_3d_figure():
    """Create a Matplotlib figure and 3D axis for embedding in Tk."""
    fig = plt.figure(figsize=(6.6, 6.6))
    ax = fig.add_subplot(111, projection="3d")
    return fig, ax


def draw_preview(ax: Any, show_gainmap: bool = False, vmin: str = "auto", vmax: str = "auto", **kwargs) -> Any:
    """
    Draw a simple Earth sphere and placeholder satellite points.
    - 'ax' is a Matplotlib 3D axis.
    - 'show_gainmap' left as a flag for future implementation.
    """
    ax.clear()
    ax.set_title("Satellite Preview")
    ax.set_xlabel("X (km)")
    ax.set_ylabel("Y (km)")
    ax.set_zlabel("Z (km)")

    # Earth sphere (low resolution, scaled in km)
    u = np.linspace(0, 2 * np.pi, 36)
    v = np.linspace(0, np.pi, 18)
    R = 6371.0  # Earth radius in kilometers (visual scale)
    x = R * np.outer(np.cos(u), np.sin(v))
    y = R * np.outer(np.sin(u), np.sin(v))
    z = R * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, rstride=4, cstride=4, alpha=0.2)

    # Example satellite markers (placeholder)
    ax.scatter([R * 1.2], [0], [0], s=60, label="Example satellite")
    ax.legend(loc="upper right")
    return ax
