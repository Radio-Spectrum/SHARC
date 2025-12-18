import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pathlib import Path

# Importa configurações globais
from config import RESULT_FIELDNAME_TO_PLOT_INFO


class ResultsTab:
    def __init__(self, app, parent_frame):
        """
        :param app: Instância da classe App (main.py)
        :param parent_frame: O widget onde esta aba será desenhada
        """
        self.app = app
        self.frame = parent_frame

        # --- Estado Local da Aba ---
        self.res_dirs = []  # Lista de diretórios para comparar
        self.ref_lines = []  # Linhas de referência globais
        self._plot_auto_job = None

        # Configuração dos Subplots
        self.result_fields = sorted(list(RESULT_FIELDNAME_TO_PLOT_INFO.keys()))
        self._max_axes = 9
        # Default config per axis
        self._axes_cfg = [{
            "field": self.result_fields[0] if self.result_fields else "",
            "mode": "CDF",
            "yscale": "Linear",
            "refs": ""
        } for _ in range(self._max_axes)]

        self._build_ui()

        # Inicia loop de atualização (se ativado)
        self._schedule_auto_update()

    def _build_ui(self):
        # Layout dividido: Esquerda (Controles) | Direita (Gráfico)
        left = ttk.Frame(self.frame)
        right = ttk.Frame(self.frame)
        left.pack(side="left", fill="y")
        right.pack(side="right", fill="both", expand=True)

        # ==================== CONTROLES (ESQUERDA) ====================

        # ---- Lista de Pastas ----
        ttk.Label(left, text="Pastas de resultados (comparação):").pack(
            anchor="w", pady=(6, 2))
        frm_dirs = ttk.Frame(left)
        frm_dirs.pack(fill="x")

        self.lb_dirs = tk.Listbox(frm_dirs, height=6, selectmode="extended")
        self.lb_dirs.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frm_dirs, orient="vertical",
                           command=self.lb_dirs.yview)
        sb.pack(side="right", fill="y")
        self.lb_dirs.config(yscrollcommand=sb.set)

        frm_btn = ttk.Frame(left)
        frm_btn.pack(fill="x", pady=(4, 8))
        ttk.Button(frm_btn, text="Adicionar pasta…",
                   command=self._add_dir).pack(side="left", padx=(0, 4))
        ttk.Button(frm_btn, text="Usar output_dir atual",
                   command=self._add_current_outdir).pack(side="left", padx=(0, 4))
        ttk.Button(frm_btn, text="Remover",
                   command=self._remove_dir).pack(side="left")

        # ---- Grid Layout ----
        frm_grid = ttk.LabelFrame(left, text="Layout de subfiguras")
        frm_grid.pack(fill="x", pady=(6, 6))
        ttk.Label(frm_grid, text="Linhas").grid(
            row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.app.var_rows, width=5,
                    command=self._draw_results_plots).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frm_grid, text="Colunas").grid(
            row=0, column=2, padx=4, pady=4, sticky="w")
        ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.app.var_cols, width=5,
                    command=self._draw_results_plots).grid(row=0, column=3, padx=4, pady=4)

        # ---- Configuração individual dos eixos ----
        frm_cfg = ttk.LabelFrame(left, text="Configuração de cada subfigura")
        frm_cfg.pack(fill="x", pady=(6, 8))

        for i in range(self._max_axes):
            r = ttk.Frame(frm_cfg)
            r.pack(fill="x", pady=2)
            ttk.Label(r, text=f"{i+1:02d}").pack(side="left", padx=(2, 6))

            # Métrica
            cb_field = ttk.Combobox(
                r, values=self.result_fields, width=28)  # width reduzido
            cb_field.set(self._axes_cfg[i]["field"])
            cb_field.pack(side="left", padx=(0, 2))

            # CDF/CCDF
            cb_mode = ttk.Combobox(r, values=["CDF", "CCDF"], width=5)
            cb_mode.set(self._axes_cfg[i]["mode"])
            cb_mode.pack(side="left", padx=(0, 2))

            # Escala Y
            cb_ys = ttk.Combobox(r, values=["Linear", "Log"], width=6)
            cb_ys.set(self._axes_cfg[i]["yscale"])
            cb_ys.pack(side="left", padx=(0, 2))

            # Refs
            # ttk.Label(r, text="%").pack(side="left")
            ent_refs = ttk.Entry(r, width=8)
            ent_refs.insert(0, self._axes_cfg[i]["refs"])
            ent_refs.pack(side="left", padx=(2, 2))

            # Callback Factory (Closure fix)
            def _mk_upd(idx, c_f, c_m, c_y, e_r):
                def _upd(*_):
                    self._axes_cfg[idx]["field"] = c_f.get()
                    self._axes_cfg[idx]["mode"] = c_m.get()
                    self._axes_cfg[idx]["yscale"] = c_y.get()
                    self._axes_cfg[idx]["refs"] = e_r.get()
                    self._draw_results_plots()
                return _upd

            upd = _mk_upd(i, cb_field, cb_mode, cb_ys, ent_refs)
            cb_field.bind("<<ComboboxSelected>>", upd)
            cb_mode.bind("<<ComboboxSelected>>", upd)
            cb_ys.bind("<<ComboboxSelected>>", upd)
            ent_refs.bind("<FocusOut>", upd)
            ent_refs.bind("<Return>", upd)

        # ---- Auto Update ----
        frm_auto = ttk.LabelFrame(left, text="Atualização")
        frm_auto.pack(fill="x", pady=(6, 8))
        ttk.Checkbutton(frm_auto, text="Auto", variable=self.app.var_auto_update,
                        command=self._schedule_auto_update).pack(side="left", padx=(4, 4))
        ttk.Label(frm_auto, text="ms:").pack(side="left")
        ttk.Spinbox(frm_auto, from_=500, to=10000, increment=500, textvariable=self.app.var_update_period_ms,
                    width=6, command=self._schedule_auto_update).pack(side="left", padx=(0, 4))
        ttk.Button(frm_auto, text="Atualizar agora",
                   command=self._draw_results_plots).pack(side="left")

        # ---- Escala Global X e Export ----
        frm_extras = ttk.LabelFrame(left, text="Opções Globais")
        frm_extras.pack(fill="x", pady=(6, 8))

        ttk.Checkbutton(frm_extras, text="Eixo X Logarítmico", variable=self.app.var_xlog,
                        command=self._draw_results_plots).pack(fill="x", padx=4, pady=2)

        # Linhas de Ref Global
        ref_row = ttk.Frame(frm_extras)
        ref_row.pack(fill="x", pady=2)
        ttk.Label(ref_row, text="Ref x=").pack(side="left")
        self._ref_x_entry = ttk.Entry(ref_row, width=6)
        self._ref_x_entry.pack(side="left", padx=2)
        ttk.Button(ref_row, text="+", width=3,
                   command=self._ref_add).pack(side="left")
        ttk.Button(ref_row, text="Limpar Refs",
                   command=self._ref_clear).pack(side="left", padx=2)

        # Export
        exp_row = ttk.Frame(frm_extras)
        exp_row.pack(fill="x", pady=4)
        ttk.Label(exp_row, text="DPI:").pack(side="left")
        ttk.Spinbox(exp_row, from_=72, to=600,
                    textvariable=self.app.var_export_dpi, width=5).pack(side="left")
        ttk.Button(exp_row, text="Exportar", command=self._export_results_fig).pack(
            side="left", padx=4)

        # ==================== PLOT (DIREITA) ====================
        self.fig_res = plt.figure(figsize=(7.8, 6.2))
        self.canvas_res = FigureCanvasTkAgg(self.fig_res, master=right)
        self.canvas_res.get_tk_widget().pack(fill="both", expand=True)

        # Desenho inicial
        self._draw_results_plots()

    # ---------------- Manipulação de Diretórios ----------------

    def _add_dir(self):
        init = str(Path(self.app.var_outdir.get() or Path.cwd()))
        path = filedialog.askdirectory(
            initialdir=init, title="Selecionar pasta de resultados")
        if path and path not in self.res_dirs:
            self.res_dirs.append(path)
            self.lb_dirs.insert("end", path)
            self._draw_results_plots()

    def _add_current_outdir(self):
        path = str(Path(self.app.var_outdir.get()))
        if path and path not in self.res_dirs:
            self.res_dirs.append(path)
            self.lb_dirs.insert("end", path)
            self._draw_results_plots()

    def _remove_dir(self):
        sel = list(self.lb_dirs.curselection())[::-1]
        for idx in sel:
            path = self.lb_dirs.get(idx)
            if path in self.res_dirs:
                self.res_dirs.remove(path)
            self.lb_dirs.delete(idx)
        self._draw_results_plots()

    # ---------------- Lógica de Dados ----------------

    def _collect_series_from_folder(self, folder: str, field: str):
        """
        Tenta ler <folder>/<field>.csv ou procura nos CSVs da pasta.
        Retorna np.ndarray ou None.
        """
        def _read_csv_1col(path):
            try:
                df = pd.read_csv(path)
                if field in df.columns:
                    return df[field].dropna().values.astype(float)
                elif df.shape[1] == 1:
                    return df.iloc[:, 0].dropna().values.astype(float)
                elif "value" in df.columns:
                    return df["value"].dropna().values.astype(float)
            except Exception:
                return None
            return None

        # 1. Nome exato
        cand = os.path.join(folder, f"{field}.csv")
        if os.path.exists(cand):
            s = _read_csv_1col(cand)
            if s is not None and s.size > 0:
                return s

        # 2. Varredura
        for path in glob.glob(os.path.join(folder, "*.csv")):
            s = _read_csv_1col(path)
            if s is not None and s.size > 0:
                return s
        return None

    def _compute_ecdf(self, x: np.ndarray, ccdf: bool = False):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        if x.size == 0:
            return None, None
        x_sorted = np.sort(x)
        y = np.arange(1, x_sorted.size + 1) / x_sorted.size
        if ccdf:
            y = 1.0 - y
        return x_sorted, y

    # ---------------- Plotagem ----------------

    def _draw_results_plots(self):
        # Gerenciamento do Auto-Update
        if self._plot_auto_job is not None and not self.app.var_auto_update.get():
            try:
                self.app.after_cancel(self._plot_auto_job)
            except:
                pass
            self._plot_auto_job = None

        # Configuração da Grade
        rows = max(1, int(self.app.var_rows.get()))
        cols = max(1, int(self.app.var_cols.get()))
        n_axes = min(rows * cols, self._max_axes)

        self.fig_res.clf()
        axes = self.fig_res.subplots(rows, cols)
        if isinstance(axes, np.ndarray):
            axes_flat = axes.ravel()
        else:
            axes_flat = [axes]

        # Diretórios (Fallback para output atual se vazio)
        dirs = list(self.res_dirs)
        if not dirs:
            od = str(Path(self.app.var_outdir.get()))
            if od and os.path.isdir(od):
                dirs = [od]

        # Iterar subplots
        for i in range(n_axes):
            ax = axes_flat[i]
            cfg = self._axes_cfg[i]
            field = cfg.get("field", "")
            mode = (cfg.get("mode") or "CDF").strip().upper()
            ytxt = (cfg.get("yscale") or "").strip().lower()
            ysc = "Log" if "log" in ytxt else "Linear"
            ccdf = (mode == "CCDF")
            eps = 1e-4 if ysc == "Log" else 0.0

            ax.cla()
            plotted_any = False

            for folder in dirs:
                s = self._collect_series_from_folder(folder, field)
                if s is None or s.size == 0:
                    continue

                xs, ys = self._compute_ecdf(s, ccdf=ccdf)
                if xs is None:
                    continue

                yplot = np.clip(ys, eps, 1.0) if ysc == "Log" else ys
                (line,) = ax.plot(xs, yplot, label=Path(folder).name)
                plotted_any = True

                # Linhas de referência percentuais (inputadas na grid)
                refs_txt = (cfg.get("refs") or "").strip()
                if refs_txt:
                    self._draw_percentiles(
                        ax, s, refs_txt, ccdf, ysc, line.get_color(), eps)

            # Estilo
            info = RESULT_FIELDNAME_TO_PLOT_INFO.get(field, {})
            ax.set_title(info.get("title", field), fontsize=9)
            ax.set_xlabel(info.get("x_label", field), fontsize=8)
            ax.set_ylabel("CCDF" if ccdf else "CDF", fontsize=8)

            try:
                ax.set_yscale("log" if ysc == "Log" else "linear")
            except:
                pass

            if self.app.var_xlog.get():
                try:
                    ax.set_xscale("log")
                except:
                    pass

            ax.grid(True, which="both", alpha=0.3)

            # Linhas Globais (Verticais X=...)
            for ref in self.ref_lines:
                ax.axvline(x=ref["x"], color="r", linestyle=":", alpha=0.6)
                # Opcional: texto ref["label"]

            if plotted_any:
                ax.legend(fontsize=7)
            else:
                ax.text(0.5, 0.5, "sem dados", ha="center",
                        va="center", transform=ax.transAxes, alpha=0.5)

            if ysc == "Log":
                ax.set_ylim(max(eps, 1e-6), 1.0)

        # Limpar eixos excedentes
        for j in range(n_axes, len(axes_flat)):
            try:
                self.fig_res.delaxes(axes_flat[j])
            except:
                pass

        self.fig_res.tight_layout()
        self.canvas_res.draw_idle()

        # Reagendar se necessário
        if self.app.var_auto_update.get():
            period = max(200, int(self.app.var_update_period_ms.get()))

            def _tick():
                self._draw_results_plots()

            if self._plot_auto_job:
                try:
                    self.app.after_cancel(self._plot_auto_job)
                except:
                    pass
            self._plot_auto_job = self.app.after(period, _tick)

    def _draw_percentiles(self, ax, data, refs_txt, ccdf, ysc, color, eps):
        finite = data[np.isfinite(data)]
        for tok in refs_txt.replace(";", ",").split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                val = float(tok)
                if val > 1.0:
                    val /= 100.0
                if 0.0 < val < 1.0:
                    # Val é a probabilidade da cauda (CCDF) ou evento (CDF)
                    x_ref = np.quantile(finite, 1.0 - val)

                    # Se modo CDF, e user pede 95%, quantile é 0.95.
                    # Se user pede 5% em CCDF (cauda), quantile é 0.95.
                    # Ajustando lógica simples: input é sempre % do eixo Y

                    # Desenhar linha
                    y_level = val  # Assumindo input como valor alvo de Y

                    # Inverso: Calcular X para dado Y
                    # Simples quantile:
                    # Se CDF e Y=0.9 -> x_ref = quantile(0.9)
                    # Se CCDF e Y=0.1 -> x_ref = quantile(0.9)
                    q = 1.0 - val if ccdf else val
                    x_pos = np.quantile(finite, q)

                    y0, y1 = (1.0, val) if ccdf else (0.0, val)
                    if ysc == "Log":
                        y0, y1 = max(eps, y0), max(eps, y1)

                    ax.vlines(x_pos, y0, y1, colors=color,
                              linestyles="dashed", linewidth=1, alpha=0.7)
                    ax.text(x_pos, y1, f"{int(val*100)}%", rotation=90,
                            va="bottom", ha="center", fontsize=7, color=color)

            except:
                pass

    # ---------------- Helpers de Linha Ref & Update ----------------

    def _ref_add(self):
        try:
            x = float(self._ref_x_entry.get().strip())
            self.ref_lines.append({"x": x, "label": ""})
            self._draw_results_plots()
            self._ref_x_entry.delete(0, "end")
        except:
            messagebox.showwarning("Erro", "Valor inválido")

    def _ref_clear(self):
        self.ref_lines.clear()
        self._draw_results_plots()

    def _schedule_auto_update(self):
        if self._plot_auto_job:
            try:
                self.app.after_cancel(self._plot_auto_job)
            except:
                pass
            self._plot_auto_job = None

        if self.app.var_auto_update.get():
            self._draw_results_plots()

    def _export_results_fig(self):
        path = filedialog.asksaveasfilename(
            title="Exportar figura",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf")]
        )
        if path:
            dpi = max(72, int(self.app.var_export_dpi.get()))
            try:
                self.fig_res.savefig(path, dpi=dpi, bbox_inches="tight")
                messagebox.showinfo("Sucesso", f"Salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", str(e))
