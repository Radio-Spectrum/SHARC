from utils.results_plot import _draw_results_plots

def _schedule_auto_update(root):
    
    def draw_results_plots():
        return _draw_results_plots(root)

    if root._plot_auto_job is not None:
        try:
            root.after_cancel(root._plot_auto_job)
        except Exception:
            pass
        root._plot_auto_job = None

    if not root.var_auto_update.get():
        return

    period = max(200, int(root.var_update_period_ms.get()))

    def _tick():
        draw_results_plots()
        root._plot_auto_job = root.after(period, _tick)
    root._plot_auto_job = root.after(period, _tick)
