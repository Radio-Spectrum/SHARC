def _schedule_auto_update(root):
    # cancela anterior
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
        root._draw_results_plots()
        root._plot_auto_job = root.after(period, _tick)
    root._plot_auto_job = root.after(period, _tick)
