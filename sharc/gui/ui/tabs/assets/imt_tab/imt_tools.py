import tkinter as tk
from tkinter import ttk


class IMTUIHelper:
    """
    Helper class for standardized grid layouts in the IMT tab.
    """
    PAD_X = (6, 4)
    PAD_Y = 2

    @staticmethod
    def create_sub_column(parent, col_idx, title, weights=(0, 1, 0, 1)):
        """Creates a labelled frame acting as a column within a section."""
        frame = ttk.LabelFrame(parent, text=title)
        frame.grid(row=0, column=col_idx, sticky="nsew", padx=3, pady=6)
        for c, w in enumerate(weights):
            frame.columnconfigure(c, weight=w)
        return frame

    @staticmethod
    def add_field(parent, row, label_text, widget, col=0, col_span=2):
        """Adds a standard Label + Widget pair."""
        ttk.Label(parent, text=label_text).grid(
            row=row, column=col, sticky="w", padx=IMTUIHelper.PAD_X, pady=IMTUIHelper.PAD_Y
        )
        widget.grid(
            row=row, column=col + 1, columnspan=col_span - 1,
            sticky="we", padx=(0, 6), pady=IMTUIHelper.PAD_Y
        )

    @staticmethod
    def add_range(parent, row, label_text, wmin, wmax, sep_text="to"):
        """Adds a Min/Max range input."""
        ttk.Label(parent, text=label_text).grid(
            row=row, column=0, sticky="w", padx=IMTUIHelper.PAD_X, pady=IMTUIHelper.PAD_Y
        )
        wmin.grid(row=row, column=1, sticky="we",
                  padx=(0, 4), pady=IMTUIHelper.PAD_Y)
        ttk.Label(parent, text=f" {sep_text} ").grid(
            row=row, column=2, padx=(0, 4))
        wmax.grid(row=row, column=3, sticky="we",
                  padx=(0, 6), pady=IMTUIHelper.PAD_Y)

    @staticmethod
    def pair_entries(parent, var1, var2, width=6):
        """Creates a composite widget for two side-by-side values (e.g., Min/Max)."""
        f = ttk.Frame(parent)
        e1 = ttk.Entry(f, textvariable=var1, width=width)
        e1.pack(side="left")
        ttk.Label(f, text=" / ").pack(side="left")
        e2 = ttk.Entry(f, textvariable=var2, width=width)
        e2.pack(side="left")
        return f
