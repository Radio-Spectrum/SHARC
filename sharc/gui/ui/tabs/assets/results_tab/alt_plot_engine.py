import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.transforms import Bbox
import matplotlib.ticker as ticker
import numpy as np
import os

# MUDANÇA CRÍTICA: Renderizador nativo para PySide6/Qt
matplotlib.use("QtAgg")


class EcdfCurve:
    """
    One empirical CDF/CCDF curve, drawn with only the points the screen can show.

    A campaign has hundreds of thousands of samples per curve; sending all of them to Matplotlib makes every
    draw, and above all the automatic legend placement, take seconds. The curve is monotonic, so the points
    left out between two kept ones lie inside the rectangle those two span: keeping points at a fixed step of
    probability (and, on a logarithmic probability axis, at a fixed ratio near the tail) bounds the error by
    a fraction of a pixel. The points are chosen again from the full data whenever the axes limits change, so
    zooming in still shows every sample.
    """

    # points per curve at a fixed probability step, across the visible part of the curve
    LINEAR_POINTS = 8192
    # on a log probability axis: every sample of the first TAIL_DENSE ranks, then ranks growing by TAIL_RATIO
    TAIL_DENSE = 512
    TAIL_RATIO = 1.003

    def __init__(self, sorted_x, ccdf, x_shift, x_log, y_log):
        self.ccdf = ccdf
        self.y_log = y_log
        self.n = int(sorted_x.size)
        # same operations, in the same order, as plotting every sample
        self.x = sorted_x + x_shift
        # Samples [first, last) are drawn. Infinite samples (e.g. "no interference") sit at the two ends of
        # the sorted data and are never drawn by Matplotlib, so the curve starts and ends at the finite ones.
        first = int(np.searchsorted(self.x, -np.inf, side="right"))
        last = int(np.searchsorted(self.x, np.inf, side="left"))
        if x_log:                                   # x > 0: a suffix, the data is sorted
            first = max(first, int(np.searchsorted(self.x, 0, side="right")))
        if y_log and ccdf:                          # y > 0: only the last sample has CCDF = 0
            last = min(last, self.n - 1)
        self.first, self.last = first, max(first, last)
        # what a line holding every sample would contain: only the log-axis filters applied
        self._plain_first = int(np.searchsorted(self.x, 0, side="right")) if x_log else 0
        self._plain_last = max(self._plain_first, self.n - 1 if (y_log and ccdf) else self.n)
        self.empty = self._plain_last == self._plain_first
        self.line = None

    def __len__(self):
        return self.last - self.first

    def _y(self, idx):
        y = (idx + 1) / self.n
        return 1.0 - y if self.ccdf else y

    def _visible_range(self, xlim, ylim):
        """Indices [lo, hi] of the samples inside the view, plus one neighbour on each side."""
        lo, hi = self.first, self.last - 1
        if xlim is not None and np.all(np.isfinite(xlim)):
            x0, x1 = min(xlim), max(xlim)
            lo = max(lo, int(np.searchsorted(self.x, x0, side="left")) - 1)
            hi = min(hi, int(np.searchsorted(self.x, x1, side="right")))
        if ylim is not None and np.all(np.isfinite(ylim)):
            y0, y1 = min(ylim), max(ylim)
            p0, p1 = (1.0 - y1, 1.0 - y0) if self.ccdf else (y0, y1)     # ranks/n inside the view
            lo = max(lo, int(np.floor(p0 * self.n)) - 2)
            hi = min(hi, int(np.ceil(p1 * self.n)) + 1)
        lo, hi = min(lo, hi), max(lo, hi)           # empty view: keep the two samples around it
        return max(self.first, lo), min(self.last - 1, hi)

    def points(self, xlim=None, ylim=None):
        """(x, y) to draw for the given view (None = whole curve)."""
        if len(self) == 0:
            return self.x[:0], np.empty(0)
        lo, hi = self._visible_range(xlim, ylim)
        span = hi - lo + 1
        if span <= self.LINEAR_POINTS:
            idx = np.arange(lo, hi + 1)
        else:
            parts = [np.linspace(lo, hi, self.LINEAR_POINTS).astype(np.int64)]
            if self.y_log:
                # ranks counted from the small-probability end: 0, 1, 2, ... then geometric
                steps = np.arange(min(span, self.TAIL_DENSE), dtype=np.int64)
                if span > self.TAIL_DENSE:
                    n_geo = int(np.log(span / self.TAIL_DENSE) / np.log(self.TAIL_RATIO)) + 1
                    geo = (self.TAIL_DENSE * self.TAIL_RATIO ** np.arange(1, n_geo + 1)).astype(np.int64)
                    steps = np.concatenate([steps, geo[geo < span]])
                parts.append(hi - steps if self.ccdf else lo + steps)
            idx = np.unique(np.concatenate(parts))
        return self.x[idx], self._y(idx)

    def refresh(self, xlim, ylim):
        if self.line is not None:
            self.line.set_data(*self.points(xlim, ylim))

    # ---- questions about ALL the samples (what a full-resolution line would answer), without visiting them ----
    def _plain_range(self):
        """Samples [first, last) a full-resolution line would hold (log-axis filters only)."""
        return self._plain_first, self._plain_last

    def _ranks_between(self, y0, y1):
        """Indices [lo, hi) of the samples whose probability is strictly between y0 and y1."""
        n = self.n
        if self.ccdf:                                   # y decreases with the index
            lo = min(max(int(np.floor((1.0 - y1) * n)) - 1, 0), n)
            while lo > 0 and self._y(lo - 1) < y1: lo -= 1
            while lo < n and not self._y(lo) < y1: lo += 1
            hi = min(max(int(np.ceil((1.0 - y0) * n)), 0), n)
            while hi < n and self._y(hi) > y0: hi += 1
            while hi > 0 and not self._y(hi - 1) > y0: hi -= 1
        else:                                           # y increases with the index
            lo = min(max(int(np.floor(y0 * n)) - 1, 0), n)
            while lo > 0 and self._y(lo - 1) > y0: lo -= 1
            while lo < n and not self._y(lo) > y0: lo += 1
            hi = min(max(int(np.ceil(y1 * n)), 0), n)
            while hi < n and self._y(hi) < y1: hi += 1
            while hi > 0 and not self._y(hi - 1) < y1: hi -= 1
        return lo, hi

    def inside(self, x0, x1, y0, y1):
        """Indices [lo, hi) of the samples strictly inside the data rectangle (lo >= hi: none)."""
        first, last = self._plain_range()
        lo_y, hi_y = self._ranks_between(y0, y1)
        lo = max(first, int(np.searchsorted(self.x, x0, side="right")), lo_y)
        hi = min(last, int(np.searchsorted(self.x, x1, side="left")), hi_y)
        return lo, hi

    def vertices(self, lo, hi):
        """Data coordinates of samples [lo, hi), clipped to the samples of the line."""
        first, last = self._plain_range()
        idx = np.arange(max(first, lo), min(last, hi))
        return np.column_stack([self.x[idx], self._y(idx)])


class _CurveLegend(Legend):
    """
    Legend of an axes with EcdfCurve lines whose automatic placement (loc="best") is decided with all the
    samples of the curves, as when every sample was a vertex of the line.

    Matplotlib chooses the corner where the legend covers the fewest line vertices. Counting only the drawn
    (reduced) vertices could choose another corner; visiting every sample for each candidate corner is what
    made a draw take seconds. The curves are sorted, so the samples inside a rectangle are found by bisection.
    """
    curves = ()

    def _find_best_position(self, width, height, renderer, *args, **kwargs):
        try:
            return self._best_position_with_all_samples(width, height, renderer)
        except Exception:      # unexpected Matplotlib internals: fall back to its own placement
            return super()._find_best_position(width, height, renderer, *args, **kwargs)

    def _best_position_with_all_samples(self, width, height, renderer):
        by_line = {id(c.line): c for c in self.curves}
        to_display = self.parent.transData
        to_data = to_display.inverted()
        # as Legend._auto_legend_data, with the curves kept apart
        bboxes, lines, offsets, curves = [], [], [], []
        for artist in self.parent._children:
            if id(artist) in by_line:
                curves.append(by_line[id(artist)])
            elif isinstance(artist, Line2D):
                lines.append(artist.get_transform().transform_path(artist.get_path()))
            elif isinstance(artist, Rectangle):
                bboxes.append(artist.get_bbox().transformed(artist.get_data_transform()))
            elif isinstance(artist, Patch):
                lines.append(artist.get_transform().transform_path(artist.get_path()))
            else:
                # collections etc.: none in these figures; let Matplotlib handle anything unexpected
                raise NotImplementedError(type(artist).__name__)

        def curve_badness(curve, box):
            (xa, ya), (xb, yb) = to_data.transform([box.min, box.max])
            lo, hi = curve.inside(min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb))
            count = max(0, hi - lo)
            # does the curve touch the box? Only the samples next to the box can tell.
            if count > 0:
                near = curve.vertices(lo - 1, lo + 2)
            else:
                near = curve.vertices(min(lo, hi) - 2, max(lo, hi) + 2)
            touches = len(near) >= 2 and MplPath(to_display.transform(near)).intersects_bbox(box, filled=False)
            if count > 0 and not touches and len(curve.vertices(lo - 1, hi + 1)) >= 2:
                touches = True                           # samples inside the box: some segment is inside too
            return count + int(touches)

        bbox = Bbox.from_bounds(0, 0, width, height)
        candidates = []
        for idx, code in enumerate(range(1, len(self.codes))):
            l, b = self._get_anchored_bbox(code, bbox, self.get_bbox_to_anchor(), renderer)
            box = Bbox.from_bounds(l, b, width, height)
            badness = (sum(box.count_contains(line.vertices) for line in lines)
                       + box.count_contains(offsets)
                       + box.count_overlaps(bboxes)
                       + sum(line.intersects_bbox(box, filled=False) for line in lines)
                       + sum(curve_badness(curve, box) for curve in curves))
            if badness == 0:
                return l, b
            candidates.append((badness, idx, (l, b)))      # the index favours lower codes in a tie
        _, _, (l, b) = min(candidates)
        return l, b


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

    def create_figure(self, data_getter_func, plot_selected_only=False, selected_indices=None, data_is_sorted=False):
        """Build the figure. ``data_getter_func(folder, field)`` returns the samples of a field; pass
        ``data_is_sorted=True`` when it already returns them in ascending order."""
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
            curves = []
            for dir_idx, folder in enumerate(self.res_dirs):
                if plot_selected_only and (selected_indices is not None) and (dir_idx not in selected_indices):
                    continue

                data = data_getter_func(folder, field)
                if data is None or len(data) == 0:
                    continue

                curve = EcdfCurve(
                    data if data_is_sorted else np.sort(data),
                    ccdf=(cfg["mode"] == "CCDF"), x_shift=cfg.get("x_shift", 0.0),
                    x_log=cfg["x_log"], y_log=cfg["y_log"],
                )
                if curve.empty: continue      # nothing left by the log-axis filters: not plotted, no legend entry
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

                x, y = curve.points()
                curve.line, = ax.plot(x, y, label=label_text, color=color, linestyle=linestyle, linewidth=linewidth)
                curves.append(curve)

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
            except (ValueError, TypeError): pass

            try:
                ymin, ymax = cfg.get("y_min", ""), cfg.get("y_max", "")
                if ymin != "" and ymax != "": ax.set_ylim(bottom=float(ymin), top=float(ymax))
                elif ymin != "": ax.set_ylim(bottom=float(ymin))
                elif ymax != "": ax.set_ylim(top=float(ymax))
            except (ValueError, TypeError): pass

            try:
                xstep = float(cfg.get("x_step", ""))
                if xstep > 0:
                    ax.xaxis.set_major_locator(ticker.MultipleLocator(xstep))
                    if not cfg.get("x_log") and xstep < 1.0:
                         ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
            except (ValueError, TypeError): pass

            try:
                ystep = float(cfg.get("y_step", ""))
                if ystep > 0:
                    ax.yaxis.set_major_locator(ticker.MultipleLocator(ystep))
                    if not cfg.get("y_log") and ystep < 1.0:
                        ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
            except (ValueError, TypeError): pass

            if has_data and i == 0:
                legend = ax.legend(fontsize=8, loc='best')
                legend.__class__ = _CurveLegend        # same legend; "best" is decided with every sample
                legend.curves = curves

            self._follow_view(ax, curves)

        return fig

    @staticmethod
    def _follow_view(ax, curves):
        """Choose the drawn points of each curve again whenever the limits of the axes change (limits typed
        in the tab, zoom, pan, home), from the full data."""
        if not curves:
            return

        def refresh(_ax=None):
            xlim, ylim = ax.get_xlim(), ax.get_ylim()
            for curve in curves:
                curve.refresh(xlim, ylim)

        if not (ax.get_autoscalex_on() and ax.get_autoscaley_on()):
            refresh()                       # limits were typed in the tab: draw that part in full detail
        ax.callbacks.connect("xlim_changed", refresh)
        ax.callbacks.connect("ylim_changed", refresh)
