import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.ticker as ticker
import numpy as np
import os

# MUDANÇA CRÍTICA: Renderizador nativo para PySide6/Qt
matplotlib.use("QtAgg")

class MatplotlibPlotter:
    """
    Module responsible for generating figures using Matplotlib.
    """

    def __init__(self, axes_cfg, res_dirs, res_styles, rows, cols, max_axes):
        self.axes_cfg = axes_cfg
        self.res_dirs = res_dirs
        self.res_styles = res_styles
        self.rows = rows
        self.cols = cols
        self.max_axes = max_axes
        
        self.dash_map = {
            "solid": "-", "-": "-", 
            "dash": "--", "--": "--", 
            "dashdot": "-.", "-.": "-.", 
            "dot": ":", ":": ":", 
            "Auto": "-"
        }

    def create_figure(self, data_getter_func, plot_selected_only=False, selected_indices=None):
        fig = Figure(figsize=(5, 4), dpi=100)
        fig.set_tight_layout(True)
        
        n_plots = min(self.rows * self.cols, self.max_axes)
        
        for i in range(n_plots):
            cfg = self.axes_cfg[i]
            ax = fig.add_subplot(self.rows, self.cols, i + 1)
            field = cfg["field"]
            
            title = cfg.get("title", "")
            if not title:
                title = field
            ax.set_title(title, fontsize=10)
            
            xlabel = cfg.get("x_label") or field
            ylabel = cfg.get("y_label") or f"Prob ({cfg['mode']})"
            ax.set_xlabel(xlabel, fontsize=9)
            ax.set_ylabel(ylabel, fontsize=9)
            
            if cfg.get("x_log"): ax.set_xscale("log")
            if cfg.get("y_log"): ax.set_yscale("log")
                
            ax.grid(True, which="both", linestyle='--', linewidth=0.5, alpha=0.7)

            has_data = False
            for dir_idx, folder in enumerate(self.res_dirs):
                if plot_selected_only and (selected_indices is not None) and (dir_idx not in selected_indices):
                    continue

                data = data_getter_func(folder, field)
                if data is None or len(data) == 0:
                    continue

                x = np.sort(data)
                n = x.size
                y = np.arange(1, n+1) / n
                if cfg["mode"] == "CCDF":
                    y = 1.0 - y

                x = x + cfg.get("x_shift", 0.0)

                if cfg["x_log"]:
                    mask = x > 0
                    x, y = x[mask], y[mask]
                if cfg["y_log"]:
                    mask = y > 0
                    x, y = x[mask], y[mask]
                
                if len(x) == 0: continue
                has_data = True

                style = self.res_styles.get(folder, {})
                custom_label = style.get("label", "")
                folder_name = os.path.basename(folder) if "ssh://" not in folder else f"[SSH] {os.path.basename(folder)}"
                suffix = cfg.get('legend_suffix', '')
                label_text = (custom_label if custom_label else folder_name) + suffix

                color = style.get("color", "Auto")
                if color == "Auto": color = None 
                
                ls_raw = style.get("linestyle", "Auto")
                linestyle = self.dash_map.get(ls_raw, "-")
                linewidth = style.get("linewidth", 1.5)

                ax.plot(x, y, label=label_text, color=color, linestyle=linestyle, linewidth=linewidth)

            for crit in cfg.get("criteria", []):
                if not crit.get("enabled", True): continue
                try:
                    val = float(crit["val"])
                    c_color = crit.get("color", "red")
                    c_label = crit.get("label", "")
                    
                    if "Vertical" in crit["type"]:
                        ax.axvline(x=val, color=c_color, linestyle="--", linewidth=1.2, label="_nolegend_")
                        trans = ax.get_xaxis_transform()
                        ax.text(val, 1.01, c_label, color=c_color, transform=trans, ha='center', va='bottom', fontsize=8, rotation=90)
                    else:
                        ax.axhline(y=val, color=c_color, linestyle="--", linewidth=1.2, label="_nolegend_")
                        ax.text(ax.get_xlim()[0], val, c_label, color=c_color, va='bottom', ha='left', fontsize=8)
                except Exception as e:
                    print(f"Error plotting criteria: {e}")

            try:
                xmin, xmax = cfg.get("x_min", ""), cfg.get("x_max", "")
                if xmin != "" and xmax != "": ax.set_xlim(left=float(xmin), right=float(xmax))
                elif xmin != "": ax.set_xlim(left=float(xmin))
                elif xmax != "": ax.set_xlim(right=float(xmax))
            except: pass

            try:
                ymin, ymax = cfg.get("y_min", ""), cfg.get("y_max", "")
                if ymin != "" and ymax != "": ax.set_ylim(bottom=float(ymin), top=float(ymax))
                elif ymin != "": ax.set_ylim(bottom=float(ymin))
                elif ymax != "": ax.set_ylim(top=float(ymax))
            except: pass

            try:
                xstep = float(cfg.get("x_step", ""))
                if xstep > 0:
                    ax.xaxis.set_major_locator(ticker.MultipleLocator(xstep))
                    if not cfg.get("x_log") and xstep < 1.0:
                         ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
            except: pass

            try:
                ystep = float(cfg.get("y_step", ""))
                if ystep > 0:
                    ax.yaxis.set_major_locator(ticker.MultipleLocator(ystep))
                    if not cfg.get("y_log") and ystep < 1.0:
                        ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
            except: pass

            if has_data and i == 0:
                ax.legend(fontsize=8, loc='best')

        return fig