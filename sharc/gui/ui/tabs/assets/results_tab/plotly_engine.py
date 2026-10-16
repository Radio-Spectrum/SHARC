import os
import math
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import RESULT_FIELDNAME_TO_PLOT_INFO

class PlotlyPlotter:
    """
    Module responsible for generating figures using Plotly,
    replicating the dynamic style and configurations of the ResultsTab.
    """

    def __init__(self, axes_cfg, res_dirs, res_styles, rows, cols, max_axes):
        self.axes_cfg = axes_cfg
        self.res_dirs = res_dirs
        self.res_styles = res_styles
        self.rows = rows
        self.cols = cols
        self.max_axes = max_axes
        
        # Mapping Plotly/Tkinter line styles to Plotly syntax
        self.dash_map = {
            "-": "solid", 
            "--": "dash",
            "-.": "dashdot", 
            ":": "dot", 
            "Auto": None
        }
        
        self.color_map = {
            "tab:blue": "#1f77b4", 
            "tab:orange": "#ff7f0e", 
            "tab:green": "#2ca02c", 
            "tab:red": "#d62728", 
            "tab:purple": "#9467bd",
            "tab:brown": "#8c564b", 
            "tab:pink": "#e377c2", 
            "tab:gray": "#7f7f7f", 
            "tab:olive": "#bcbd22", 
            "tab:cyan": "#17becf"
        }

    def create_figure(self, data_getter_func, ecdf_func, plot_selected_only=False, selected_indices=None, progress_callback=None, is_preview=False, force_refresh=False):
        """
        Creates the Plotly figure.
        
        Args:
            data_getter_func: Callback function to retrieve data.
            ecdf_func: Callback function to calculate ECDF.
            plot_selected_only (bool): Whether to plot selected items only.
            selected_indices (list): List of selected indices from the GUI.
            progress_callback: Callback function to report UI progress.
            is_preview (bool): If true, limits number of points.
            force_refresh (bool): Bypasses cached data.
        """
        rows = max(1, self.rows)
        cols = max(1, self.cols)
        n_plots = min(rows * cols, self.max_axes)
        total_steps = n_plots * max(1, len(self.res_dirs))
        current_step = 0
        last_progress_time = 0

        titles = []
        for i in range(n_plots):
            cfg = self.axes_cfg[i]
            t = cfg.get("title")
            if not t:
                t = RESULT_FIELDNAME_TO_PLOT_INFO.get(cfg["field"], {}).get("title", cfg["field"])
            titles.append(t)

        fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles,
                            vertical_spacing=0.12, horizontal_spacing=0.08)

        # Iterate over subplots
        for i in range(n_plots):
            cfg = self.axes_cfg[i]
            r, c = (i // cols) + 1, (i % cols) + 1
            field = cfg["field"]

            for dir_idx, folder in enumerate(self.res_dirs):
                current_step += 1
                now = time.time()
                
                # Report Progress via callback
                if progress_callback and total_steps > 0 and (now - last_progress_time > 0.1):
                    pct = (current_step / total_steps) * 80.0
                    progress_callback(pct)
                    last_progress_time = now

                # Selection Filter
                if plot_selected_only and (selected_indices is not None) and (dir_idx not in selected_indices):
                    continue

                # Callback Data Fetch
                data = data_getter_func(folder, field, force_refresh=force_refresh)
                if data is None or len(data) == 0:
                    continue

                # ECDF Limit 
                limit_points = 2000 if is_preview else 0
                x, y = ecdf_func(data, ccdf=(cfg["mode"] == "CCDF"), downsample_to=limit_points)

                x = x + cfg.get("x_shift", 0.0)
                
                # Math filters 
                if cfg["x_log"]:
                    mask = x > 0
                    x, y = x[mask], y[mask]
                if cfg["y_log"]:
                    mask = y > 0
                    x, y = x[mask], y[mask]

                if len(x) == 0:
                    continue

                # Styling
                style = self.res_styles.get(folder, {})
                custom_label = style.get("label", "")
                if custom_label:
                    name = custom_label
                else:
                    name = os.path.basename(folder) if "ssh://" not in folder else f"[SSH] {os.path.basename(folder)}"
                name += cfg.get('legend_suffix', '')

                line_props = dict(width=style.get("linewidth", 1.5))
                ls_val = style.get("linestyle", "Auto")
                if ls_val in self.dash_map and self.dash_map[ls_val]:
                    line_props["dash"] = self.dash_map[ls_val]
                
                c_val = style.get("color", "Auto")
                if c_val != "Auto":
                    line_props["color"] = self.color_map.get(c_val, c_val)

                # Render fallback / engine choice
                if is_preview:
                    trace_type = go.Scatter
                else:
                    trace_type = go.Scattergl if len(x) > 10000 else go.Scatter

                fig.add_trace(trace_type(x=x, y=y, mode='lines', name=name, line=line_props,
                              legendgroup=folder, showlegend=(i == 0)), row=r, col=c)

            # Draw Criteria Lines
            for crit in cfg.get("criteria", []):
                if not crit.get("enabled", True):
                    continue
                try:
                    val = float(crit["val"])
                    color = crit.get("color", "red")
                    if "Vertical" in crit["type"]:
                        fig.add_vline(x=val, line_dash="dash", line_color=color,
                                      annotation_text=crit.get("label"), row=r, col=c)
                    else:
                        fig.add_hline(y=val, line_dash="dash", line_color=color,
                                      annotation_text=crit.get("label"), row=r, col=c)
                except (ValueError, TypeError):
                    pass

            # Axes and Ticks Logic
            xlab = cfg.get("x_label") or field
            ylab = cfg.get("y_label") or f"Prob ({cfg['mode']})"
            xaxis_params = dict(title_text=xlab, type="log" if cfg["x_log"] else "linear", showgrid=True)
            yaxis_params = dict(title_text=ylab, type="log" if cfg["y_log"] else "linear", showgrid=True)
            
            # --- X Params Config ---
            try:
                xmin = float(cfg.get("x_min", ""))
                xmax = float(cfg.get("x_max", ""))
                if cfg["x_log"]:
                    xmin_log = math.log10(xmin) if xmin > 0 else 0
                    xmax_log = math.log10(xmax) if xmax > 0 else 1
                    xaxis_params["range"] = [xmin_log, xmax_log]
                else:
                    xaxis_params["range"] = [xmin, xmax]
            except ValueError:
                pass
            
            # --- Y Params Config ---
            try:
                ymin = float(cfg.get("y_min", ""))
                ymax = float(cfg.get("y_max", ""))
                if cfg["y_log"]:
                    ymin_log = math.log10(ymin) if ymin > 0 else 0
                    ymax_log = math.log10(ymax) if ymax > 0 else 1
                    yaxis_params["range"] = [ymin_log, ymax_log]
                else:
                    yaxis_params["range"] = [ymin, ymax]
            except ValueError:
                pass

            # --- Layout Steps ---
            try:
                xstep = float(cfg.get("x_step", ""))
                if xstep > 0 and not cfg["x_log"]:
                    xaxis_params["dtick"] = xstep
                    if xstep < 1.0:
                        decimals = max(0, int(math.ceil(-math.log10(xstep)) - 2))
                        xaxis_params["tickformat"] = f".{decimals}%"
            except ValueError:
                pass

            try:
                ystep = float(cfg.get("y_step", ""))
                if ystep > 0 and not cfg["y_log"]:
                    yaxis_params["dtick"] = ystep
                    if ystep < 1.0:
                        decimals = max(0, int(math.ceil(-math.log10(ystep)) - 2))
                        yaxis_params["tickformat"] = f".{decimals}%"
            except ValueError:
                pass

            fig.update_xaxes(xaxis_params, row=r, col=c)
            fig.update_yaxes(yaxis_params, row=r, col=c)

        fig.update_layout(template="plotly_white", margin=dict(l=50, r=20, t=50, b=50), 
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        return fig
