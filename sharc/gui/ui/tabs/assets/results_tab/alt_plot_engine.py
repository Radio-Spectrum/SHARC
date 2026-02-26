import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker as ticker
import numpy as np
import os

# Ensure Matplotlib uses the correct backend for Tkinter integration
matplotlib.use("TkAgg")

class MatplotlibPlotter:
    """
    Module responsible for generating figures using Matplotlib,
    replicating the style and configurations of the ResultsTab.
    """

    def __init__(self, axes_cfg, res_dirs, res_styles, rows, cols, max_axes):
        self.axes_cfg = axes_cfg
        self.res_dirs = res_dirs
        self.res_styles = res_styles
        self.rows = rows
        self.cols = cols
        self.max_axes = max_axes
        
        # Mapping Plotly/Tkinter line styles to Matplotlib
        self.dash_map = {
            "solid": "-", 
            "-": "-", 
            "dash": "--", 
            "--": "--", 
            "dashdot": "-.", 
            "-.": "-.", 
            "dot": ":", 
            ":": ":", 
            "Auto": "-"
        }

    def create_figure(self, data_getter_func, plot_selected_only=False, selected_indices=None):
        """
        Creates the Matplotlib figure.
        
        Args:
            data_getter_func: Callback function to retrieve data (self._get_data).
            plot_selected_only (bool): Whether to plot only selected items.
            selected_indices (list): List of selected indices from the Listbox.
        """
        # Figure Configuration
        fig = Figure(figsize=(5, 4), dpi=100)
        # Tight_layout prevents labels from being cut off
        fig.set_tight_layout(True)
        
        n_plots = min(self.rows * self.cols, self.max_axes)
        
        # Iterate over subplots
        for i in range(n_plots):
            cfg = self.axes_cfg[i]
            # Add subplot (rows, cols, index) - Matplotlib index starts at 1
            ax = fig.add_subplot(self.rows, self.cols, i + 1)
            
            field = cfg["field"]
            
            # --- Axis and Title Configuration ---
            title = cfg.get("title", "")
            if not title:
                title = field
            ax.set_title(title, fontsize=10)
            
            xlabel = cfg.get("x_label") or field
            ylabel = cfg.get("y_label") or f"Prob ({cfg['mode']})"
            ax.set_xlabel(xlabel, fontsize=9)
            ax.set_ylabel(ylabel, fontsize=9)
            
            if cfg.get("x_log"):
                ax.set_xscale("log")
            if cfg.get("y_log"):
                ax.set_yscale("log")
                
            ax.grid(True, which="both", linestyle='--', linewidth=0.5, alpha=0.7)

            # --- Data Plotting ---
            has_data = False
            
            for dir_idx, folder in enumerate(self.res_dirs):
                # Selection Filter
                if plot_selected_only and (selected_indices is not None) and (dir_idx not in selected_indices):
                    continue

                # Callback to get data (reuses the original script logic)
                data = data_getter_func(folder, field)
                
                if data is None or len(data) == 0:
                    continue

                # ECDF Processing
                x = np.sort(data)
                n = x.size
                y = np.arange(1, n+1) / n
                if cfg["mode"] == "CCDF":
                    y = 1.0 - y

                # Apply Shift
                x = x + cfg.get("x_shift", 0.0)

                # Log Filter (prevent math errors)
                if cfg["x_log"]:
                    mask = x > 0
                    x, y = x[mask], y[mask]
                if cfg["y_log"]:
                    mask = y > 0
                    x, y = x[mask], y[mask]
                
                if len(x) == 0:
                    continue
                
                has_data = True

                # Styling
                style = self.res_styles.get(folder, {})
                
                # Label
                custom_label = style.get("label", "")
                folder_name = os.path.basename(folder) if "ssh://" not in folder else f"[SSH] {os.path.basename(folder)}"
                suffix = cfg.get('legend_suffix', '')
                label_text = (custom_label if custom_label else folder_name) + suffix

                # Color and Line
                color = style.get("color", "Auto")
                if color == "Auto":
                    color = None # Let Matplotlib decide
                
                ls_raw = style.get("linestyle", "Auto")
                linestyle = self.dash_map.get(ls_raw, "-")
                linewidth = style.get("linewidth", 1.5)

                ax.plot(x, y, label=label_text, color=color, linestyle=linestyle, linewidth=linewidth)

            # --- Protection Criteria ---
            for crit in cfg.get("criteria", []):
                if not crit.get("enabled", True):
                    continue
                try:
                    val = float(crit["val"])
                    c_color = crit.get("color", "red")
                    c_label = crit.get("label", "")
                    
                    if "Vertical" in crit["type"]:
                        ax.axvline(x=val, color=c_color, linestyle="--", linewidth=1.2, label=f"_nolegend_")
                        # Simple text near the line
                        trans = ax.get_xaxis_transform()
                        ax.text(val, 1.01, c_label, color=c_color, transform=trans, ha='center', va='bottom', fontsize=8, rotation=90)
                    else:
                        ax.axhline(y=val, color=c_color, linestyle="--", linewidth=1.2, label=f"_nolegend_")
                        trans = ax.get_yaxis_transform()
                        ax.text(ax.get_xlim()[0], val, c_label, color=c_color, va='bottom', ha='left', fontsize=8)

                except Exception as e:
                    print(f"Error plotting criteria: {e}")

            # --- Manual Limits ---
            try:
                xmin = cfg.get("x_min", "")
                xmax = cfg.get("x_max", "")
                if xmin != "" and xmax != "":
                    ax.set_xlim(left=float(xmin), right=float(xmax))
                elif xmin != "":
                    ax.set_xlim(left=float(xmin))
                elif xmax != "":
                    ax.set_xlim(right=float(xmax))
            except: pass

            try:
                ymin = cfg.get("y_min", "")
                ymax = cfg.get("y_max", "")
                if ymin != "" and ymax != "":
                    ax.set_ylim(bottom=float(ymin), top=float(ymax))
                elif ymin != "":
                    ax.set_ylim(bottom=float(ymin))
                elif ymax != "":
                    ax.set_ylim(top=float(ymax))
            except: pass

            # --- Step Logic and Formatter ---
            # X Axis Step
            try:
                xstep = float(cfg.get("x_step", ""))
                if xstep > 0:
                    ax.xaxis.set_major_locator(ticker.MultipleLocator(xstep))
                    # If not Log and step is small, assume percentage
                    if not cfg.get("x_log") and xstep < 1.0:
                         ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
            except: pass

            # Y Axis Step
            try:
                ystep = float(cfg.get("y_step", ""))
                if ystep > 0:
                    ax.yaxis.set_major_locator(ticker.MultipleLocator(ystep))
                    if not cfg.get("y_log") and ystep < 1.0:
                        ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
            except: pass

            # Legend (only on the first plot to avoid clutter)
            if has_data and i == 0:
                ax.legend(fontsize=8, loc='best')

        return fig