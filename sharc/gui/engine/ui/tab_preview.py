"""
3D preview tab: embeds a Matplotlib 3D figure and provides simple export controls.
Drawing logic is delegated to plotting/preview_3d.py.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
matplotlib.use("TkAgg")

from utils.preview_3d import setup_3d_figure, draw_preview


def build_preview_tab(app: tk.Tk, root: tk.Widget) -> None:
    left = ttk.Frame(root)
    right = ttk.Frame(root)
    left.pack(side="left", fill="both", expand=True)
    right.pack(side="right", fill="y")

    # Create figure and canvas
    fig, ax = setup_3d_figure()
    canvas = FigureCanvasTkAgg(fig, master=left)
    canvas.get_tk_widget().pack(fill="both", expand=True)
    app._preview_fig = fig
    app._preview_ax = ax
    app._preview_canvas = canvas

    # Controls on the right-hand column
    ttk.Checkbutton(
        right,
        text="Show antenna gain map (S.672)",
        variable=app.var_show_gainmap,
        command=lambda: _draw_preview(app),
    ).pack(fill="x", pady=(0, 8))

    frm_gain = ttk.Frame(right)
    frm_gain.pack(fill="x", pady=(0, 8))
    ttk.Label(frm_gain, text="vmin (dBi):").pack(side="left")
    ttk.Entry(frm_gain, textvariable=app.var_gain_vmin, width=7).pack(side="left", padx=(4, 8))
    ttk.Label(frm_gain, text="vmax (dBi):").pack(side="left")
    ttk.Entry(frm_gain, textvariable=app.var_gain_vmax, width=7).pack(side="left", padx=(4, 0))

    ttk.Button(right, text="Generate 3D preview", command=lambda: _draw_preview(app)).pack(fill="x", pady=(4, 4))
    ttk.Button(right, text="Save image...", command=lambda: _save_image(app)).pack(fill="x", pady=(4, 4))

    # Initial draw
    _draw_preview(app)


def _draw_preview(app: tk.Tk) -> None:
    """Re-draw the 3D preview using the plotting helper."""
    draw_preview(
        app._preview_ax,
        show_gainmap=app.var_show_gainmap.get(),
        vmin=app.var_gain_vmin.get(),
        vmax=app.var_gain_vmax.get(),
    )
    app._preview_canvas.draw()


def _save_image(app: tk.Tk) -> None:
    """Ask for a file path and save the preview figure as PNG."""
    path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("All files", "*.*")])
    if path:
        app._preview_fig.savefig(path, dpi=200)
