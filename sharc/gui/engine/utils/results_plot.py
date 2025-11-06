import numpy as np
from pathlib import Path

from core.utils import _load_plot_info

RESULT_FIELDNAME_TO_PLOT_INFO = _load_plot_info()

def _draw_results_plots(root):
    """
    Desenha os subplots de resultados (CDF/CCDF), com Y linear/log,
    linhas de referência e comparação entre múltiplas pastas.
    """
    # Se auto-update foi desligado, cancele job pendente
    if root._plot_auto_job is not None and not root.var_auto_update.get():
        try:
            root.after_cancel(root._plot_auto_job)
        except Exception:
            pass
        root._plot_auto_job = None

    
    # Layout
    rows = max(1, int(root.var_rows.get()))
    cols = max(1, int(root.var_cols.get()))
    n_axes = min(rows * cols, root._max_axes)

    # Recria grade
    root.fig_res.clf()
    axes = root.fig_res.subplots(rows, cols)
    if isinstance(axes, np.ndarray):
        axes_flat = axes.ravel()
    else:
        axes_flat = [axes]

    # Pastas selecionadas (fallback: output_dir atual)
    dirs = list(root.res_dirs)
    if not dirs:
        od = str(Path(root.var_outdir.get()))
        if od:
            dirs = [od]

    # Desenho por subfigura
    for i in range(n_axes):
        ax = axes_flat[i]
        cfg = root._axes_cfg[i]
        field = cfg.get("field", "")
        mode = (cfg.get("mode") or "CDF").strip().upper()

        # Y-scale (parsing robusto)
        ytxt = (cfg.get("yscale") or "").strip().lower()
        if ytxt in {"log", "log10", "logarítmica", "logaritmica", "log-scale", "logscale"}:
            ysc = "Log"
        else:
            ysc = "Linear"

        ccdf = (mode == "CCDF")
        eps = 1e-4 if ysc == "Log" else 0.0  # evita log(0)

        ax.cla()
        plotted_any = False

        for folder in dirs:
            s = root._collect_series_from_folder(folder, field)
            if s is None or s.size == 0:
                continue

            xs, ys = root._compute_ecdf(s, ccdf=ccdf)
            if xs is None:
                continue

            yplot = np.clip(ys, eps, 1.0) if ysc == "Log" else ys
            (line,) = ax.plot(xs, yplot, label=Path(folder).name)
            plotted_any = True

            # ----- Linhas de referência -----
            refs_txt = (cfg.get("refs") or "").strip()
            # fallback para referência global (opcional)
            if not refs_txt and hasattr(root, "var_global_refs"):
                refs_txt = (root.var_global_refs.get() or "").strip()

            if refs_txt:
                # "5, 10, 50" -> [0.05, 0.10, 0.50]
                refs = []
                for tok in refs_txt.replace(";", ",").split(","):
                    tok = tok.strip()
                    if not tok:
                        continue
                    try:
                        val = float(tok)
                        if val > 1.0:
                            val = val / 100.0
                        if 0.0 < val < 1.0:
                            refs.append(val)
                    except Exception:
                        pass

                color = line.get_color()
                finite = s[np.isfinite(s)]
                for r in refs:
                    # r é a referência em CCDF; o quantil na CDF correspondente é q = 1 - r
                    try:
                        x_ref = np.quantile(finite, 1.0 - r)
                    except Exception:
                        continue

                    if ccdf:
                        y0, y1 = (1.0, r)  # de 100% até a referência (CCDF)
                    else:
                        y0, y1 = (0.0, 1.0 - r)  # de 0% até (1 - referência) (CDF)

                    if ysc == "Log":
                        y0 = max(eps, y0)
                        y1 = max(eps, y1)

                    ax.vlines(x_ref, y0, y1, colors=color, linestyles="dashed", linewidth=1.2, alpha=0.85)
                    ax.text(x_ref, y1, f"{int(round(r*100))}%", rotation=90, va="bottom", ha="center",
                            fontsize=8, color=color, alpha=0.8)

        # Títulos/labels
        info = RESULT_FIELDNAME_TO_PLOT_INFO.get(field, {})
        ax.set_title(info.get("title", field))
        ax.set_xlabel(info.get("x_label", field))
        ax.set_ylabel("CCDF" if ccdf else "CDF")

        # Y-scale
        try:
            ax.set_yscale("log" if ysc == "Log" else "linear")
        except Exception:
            pass

        # Grade/legenda
        ax.grid(True, which="both", alpha=0.3)
        if plotted_any:
            ax.legend()
        else:
            ax.text(0.5, 0.5, "sem dados", ha="center", va="center",
                    transform=ax.transAxes, alpha=0.6)

        # Limites Y seguros para log
        if ysc == "Log":
            ax.set_ylim(max(eps, 1e-6), 1.0)

    # Remove eixos além de n_axes
    for j in range(n_axes, len(axes_flat)):
        try:
            root.fig_res.delaxes(axes_flat[j])
        except Exception:
            pass

    root.fig_res.tight_layout()
    root.canvas_res.draw_idle()

    # (re)agenda auto-update se ligado
    if root.var_auto_update.get():
        period = max(200, int(root.var_update_period_ms.get()))
        def _tick():
            root._draw_results_plots()
        if root._plot_auto_job is not None:
            try:
                root.after_cancel(root._plot_auto_job)
            except Exception:
                pass
        root._plot_auto_job = root.after(period, _tick)