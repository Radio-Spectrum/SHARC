import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
import glob
import os
from pathlib import Path

# (Imports from other project files would go here)
# from ..utils.results_plot import RESULT_FIELDNAME_TO_PLOT_INFO

def _tab_results(self, root):
    # Lado esquerdo: controles / Lado direito: figura
    left = ttk.Frame(root);
right = ttk.Frame(root)
    left.pack(side="left", fill="y");
right.pack(side="right", fill="both", expand=True)

    # ---- Seleção de pastas ----
    ttk.Label(left, text="Pastas de resultados (comparação):").pack(anchor="w", pady=(6,2))
    frm_dirs = ttk.Frame(left);
frm_dirs.pack(fill="x")
    self.lb_dirs = tk.Listbox(frm_dirs, height=6, selectmode="extended")
    self.lb_dirs.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(frm_dirs, orient="vertical", command=self.lb_dirs.yview)
    sb.pack(side="right", fill="y");
self.lb_dirs.config(yscrollcommand=sb.set)

    def _add_dir():
        init = str(Path(self.var_outdir.get() or Path.cwd()))
        path = filedialog.askdirectory(initialdir=init, title="Selecionar pasta de resultados")
        if path and path not in self.res_dirs:
            self.res_dirs.append(path)
            self.lb_dirs.insert("end", path)
  
          self._draw_results_plots()

    def _add_current_outdir():
        path = str(Path(self.var_outdir.get()))
        if path and path not in self.res_dirs:
            self.res_dirs.append(path)
            self.lb_dirs.insert("end", path)
            
self._draw_results_plots()

    def _remove_dir():
        sel = list(self.lb_dirs.curselection())[::-1]
        for idx in sel:
            path = self.lb_dirs.get(idx)
            self.res_dirs.remove(path)
            self.lb_dirs.delete(idx)
        
self._draw_results_plots()

    frm_btn = ttk.Frame(left);
frm_btn.pack(fill="x", pady=(4,8))
    ttk.Button(frm_btn, text="Adicionar pasta…", command=_add_dir).pack(side="left", padx=(0,4))
    ttk.Button(frm_btn, text="Usar output_dir atual", command=_add_current_outdir).pack(side="left", padx=(0,4))
    ttk.Button(frm_btn, text="Remover selecionadas", command=_remove_dir).pack(side="left")

    # ---- Grid de subplots ----
    frm_grid = ttk.LabelFrame(left, text="Layout de subfiguras")
    frm_grid.pack(fill="x", pady=(6,6))
    ttk.Label(frm_grid, text="Linhas").grid(row=0, column=0, padx=4, pady=4, sticky="w")
    ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.var_rows, width=5, command=self._draw_results_plots).grid(row=0, column=1, 
padx=4, pady=4)
    ttk.Label(frm_grid, text="Colunas").grid(row=0, column=2, padx=4, pady=4, sticky="w")
    ttk.Spinbox(frm_grid, from_=1, to=3, textvariable=self.var_cols, width=5, command=self._draw_results_plots).grid(row=0, column=3, padx=4, pady=4)

    # ---- Configuração por subfigura (até _max_axes)
    frm_cfg = ttk.LabelFrame(left, text="Configuração de cada subfigura")
    frm_cfg.pack(fill="x", pady=(6,8))
    self._subplot_cfg_rows = []
    for i in range(self._max_axes):
        
r = ttk.Frame(frm_cfg); r.pack(fill="x", pady=2)
        ttk.Label(r, text=f"{i+1:02d}").pack(side="left", padx=(2,6))

        # MÉTRICA
        cb_field = ttk.Combobox(r, values=self.result_fields, width=34)
        cb_field.set(self._axes_cfg[i]["field"])
        cb_field.pack(side="left", padx=(0,6))

        # CDF/CCDF
        cb_mode = ttk.Combobox(r, 
values=["CDF","CCDF"], width=6)
        cb_mode.set(self._axes_cfg[i]["mode"])
        cb_mode.pack(side="left", padx=(0,6))

        # Y-SCALE (Linear/Log)
        cb_ys = ttk.Combobox(r, values=["Linear","Log"], width=7)
        cb_ys.set(self._axes_cfg[i]["yscale"])
        cb_ys.pack(side="left", padx=(0,6))

        # REFERÊNCIAS (%, ex.: 5,10,50)
   
         ttk.Label(r, text="Refs(%)").pack(side="left")
        ent_refs = ttk.Entry(r, width=10)
        ent_refs.insert(0, self._axes_cfg[i]["refs"])
        ent_refs.pack(side="left", padx=(4,6))

        def _mk_upd(idx, combof, combom, comboys, entryrefs):
            def _upd(*_):
           
     self._axes_cfg[idx]["field"]  = combof.get()
                self._axes_cfg[idx]["mode"]   = combom.get()
                self._axes_cfg[idx]["yscale"] = comboys.get()
                self._axes_cfg[idx]["refs"]   = entryrefs.get()
                self._draw_results_plots()
  
              return _upd

        upd = _mk_upd(i, cb_field, cb_mode, cb_ys, ent_refs)
        cb_field.bind("<<ComboboxSelected>>", upd)
        cb_mode.bind("<<ComboboxSelected>>", upd)
        cb_ys.bind("<<ComboboxSelected>>", upd)
        ent_refs.bind("<FocusOut>", upd)
        ent_refs.bind("<Return>", upd)

  
          self._subplot_cfg_rows.append((cb_field, cb_mode, cb_ys, ent_refs))

    # ---- Atualização automática ----
    frm_auto = ttk.LabelFrame(left, text="Atualização")
    frm_auto.pack(fill="x", pady=(6,8))
    ttk.Checkbutton(frm_auto, text="Atualização automática", variable=self.var_auto_update,
                    command=self._schedule_auto_update).pack(side="left", padx=(4,8))
    ttk.Label(frm_auto, text="Período (ms):").pack(side="left")
    ttk.Spinbox(frm_auto, 
from_=500, to=10000, increment=500, textvariable=self.var_update_period_ms, width=8,
                command=self._schedule_auto_update).pack(side="left", padx=(4,8))
    ttk.Button(frm_auto, text="Atualizar agora", command=self._draw_results_plots).pack(side="left")

    # ---- Exportar figura ----
    frm_export = ttk.LabelFrame(left, text="Exportar")
    frm_export.pack(fill="x", pady=(6,8))
    ttk.Label(frm_export, text="DPI:").pack(side="left", padx=(6,4))
    self.var_export_dpi = tk.IntVar(value=200)
    ttk.Spinbox(frm_export, from_=100, to=600, increment=50, 
textvariable=self.var_export_dpi, width=6).pack(side="left", padx=(0,8))
    ttk.Button(frm_export, text="Exportar figura…", command=self._export_results_fig).pack(side="left")
    # ---- Escala / Exportar ----
    frm_extras = ttk.LabelFrame(left, text="Escala e Exportação")
    frm_extras.pack(fill="x", pady=(6,8))

    # Escala log no X
    ttk.Checkbutton(
        frm_extras, text="Escala log no eixo X",
        variable=self.var_xlog,

         command=self._draw_results_plots
    ).pack(fill="x", padx=4, pady=(2,6))

    # Exportar figura
    fexp = ttk.Frame(frm_extras);
fexp.pack(fill="x", pady=(2,4))
    ttk.Label(fexp, text="Formato:").pack(side="left")
    ttk.Combobox(
        fexp, textvariable=self.var_export_fmt,
        values=["PNG","SVG","PDF"], width=6, state="readonly"
    ).pack(side="left", padx=(4,8))
    ttk.Label(fexp, text="DPI:").pack(side="left")
    ttk.Spinbox(
        fexp, from_=72, to=600, increment=10, width=6,
        textvariable=self.var_export_dpi
 
       ).pack(side="left", padx=(4,8))
    #ttk.Button(fexp, text="Exportar figura…", command=self._export_results_figure).pack(side="left")

    # ---- Linhas de referência (globais) ----
    frm_refs = ttk.LabelFrame(left, text="Linhas de referência (todas as subfiguras)")
    frm_refs.pack(fill="x", pady=(6,8))

    ref_row = ttk.Frame(frm_refs);
ref_row.pack(fill="x", pady=(2,4))
    ttk.Label(ref_row, text="x=").pack(side="left")
    self._ref_x_entry = ttk.Entry(ref_row, width=10)
    self._ref_x_entry.pack(side="left", padx=(4,8))
    ttk.Label(ref_row, text="rótulo:").pack(side="left")
    self._ref_label_entry = ttk.Entry(ref_row, width=18)
    self._ref_label_entry.pack(side="left", padx=(4,8))
    ttk.Button(ref_row, text="Adicionar", command=self._ref_add).pack(side="left")

    # lista de linhas
    list_frame = ttk.Frame(frm_refs);
list_frame.pack(fill="x", pady=(2,4))
    self.lb_refs = tk.Listbox(list_frame, height=5, selectmode="extended")
    self.lb_refs.pack(side="left", fill="both", expand=True)
    sb2 = ttk.Scrollbar(list_frame, orient="vertical", command=self.lb_refs.yview)
    sb2.pack(side="right", fill="y")
    self.lb_refs.config(yscrollcommand=sb2.set)

    btns = ttk.Frame(frm_refs);
btns.pack(fill="x")
    ttk.Button(btns, text="Remover selecionadas", command=self._ref_remove).pack(side="left")
    ttk.Button(btns, text="Aplicar (redesenhar)", command=self._draw_results_plots).pack(side="left", padx=(6,0))

    # ---- Figura de resultados (matplotlib)
    self.fig_res = plt.figure(figsize=(7.8, 6.2))
    self.canvas_res = FigureCanvasTkAgg(self.fig_res, master=right)
    self.canvas_res.get_tk_widget().pack(fill="both", expand=True)

    self._draw_results_plots()
    self._schedule_auto_update()

# ---------------- Plot_results ----------------
def _collect_series_from_folder(self, folder: str, field: str):
    """
    Estratégia:
    1) Tenta ler <folder>/<field>.csv (coluna única ou coluna 'value').
    2) Se não existir, globa *.csv e tenta encontrar uma coluna chamada <field>.
    Retorna np.ndarray ou None.
    
"""
    import os
    import numpy as np

    def _read_csv_1col(path):
        try:
            df = pd.read_csv(path)
            # coluna com mesmo nome do field?
if field in df.columns:
                s = df[field].dropna().values
            else:
                # se só houver 1 coluna, usa ela
                if df.shape[1] == 1:
     
               s = df.iloc[:,0].dropna().values
                elif "value" in df.columns:
                    s = df["value"].dropna().values
                else:
          
          return None
            return s.astype(float)
        except Exception:
            return None

    # 1) nome exato
    cand = os.path.join(folder, f"{field}.csv")
    if os.path.exists(cand):
       
 s = _read_csv_1col(cand)
        if s is not None and s.size > 0:
            return s

    # 2) varrer outros csvs
    for path in glob.glob(os.path.join(folder, "*.csv")):
        s = _read_csv_1col(path)
        if s is not None and s.size > 0:

              return s

    return None


def _compute_ecdf(self, x: np.ndarray, ccdf: bool = False):
    import numpy as np
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None, None
    
x_sorted = np.sort(x)
    y = np.arange(1, x_sorted.size+1) / x_sorted.size
    if ccdf:
        y = 1.0 - y
    return x_sorted, y

def _draw_results_plots(self):
    """
    Desenha os subplots de resultados (CDF/CCDF), com Y linear/log,
    linhas de referência e comparação entre múltiplas pastas.
"""
    # Se auto-update foi desligado, cancele job pendente
    if self._plot_auto_job is not None and not self.var_auto_update.get():
        try:
            self.after_cancel(self._plot_auto_job)
        except Exception:
            pass
        self._plot_auto_job 
= None

    import numpy as np
    from pathlib import Path

    # Layout
    rows = max(1, int(self.var_rows.get()))
    cols = max(1, int(self.var_cols.get()))
    n_axes = min(rows * cols, self._max_axes)

    # Recria grade
    self.fig_res.clf()
    axes = self.fig_res.subplots(rows, cols)

    if isinstance(axes, np.ndarray):
        axes_flat = axes.ravel()
    else:
        axes_flat = [axes]

    # Pastas selecionadas (fallback: output_dir atual)
    dirs = list(self.res_dirs)
    if not dirs:
        od = str(Path(self.var_outdir.get()))
       
 if od:
            dirs = [od]

    # Desenho por subfigura
    for i in range(n_axes):
        ax   = axes_flat[i]
        cfg  = self._axes_cfg[i]
        field = cfg.get("field", "")
        
mode  = (cfg.get("mode") or "CDF").strip().upper()

        # Y-scale (parsing robusto)
        ytxt = (cfg.get("yscale") or "").strip().lower()
        if ytxt in {"log", "log10", "logarítmica", "logaritmica", "log-scale", "logscale"}:
            ysc = "Log"
        else:
          
  ysc = "Linear"

        ccdf = (mode == "CCDF")
        eps  = 1e-4 if ysc == "Log" else 0.0  # evita log(0)

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

            # ----- Linhas de referência -----
    
        refs_txt = (cfg.get("refs") or "").strip()
            # fallback para referência global (opcional)
            if not refs_txt and hasattr(self, "var_global_refs"):
                refs_txt = (self.var_global_refs.get() or "").strip()

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
                        if 0.0 < 
val < 1.0:
                            refs.append(val)
                    except Exception:
                        pass

         
       color = line.get_color()
                finite = s[np.isfinite(s)]
                for r in refs:
                    # r é a referência em CCDF;
o quantil na CDF correspondente é q = 1 - r
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
                    ax.text(x_ref, y1, f"{int(round(r*100))}%", rotation=90, va="bottom", 
ha="center",
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
            self.fig_res.delaxes(axes_flat[j])
   
         except Exception:
            pass

    self.fig_res.tight_layout()
    self.canvas_res.draw_idle()

    # (re)agenda auto-update se ligado
    if self.var_auto_update.get():
        period = max(200, int(self.var_update_period_ms.get()))
        def _tick():
     
       self._draw_results_plots()
        if self._plot_auto_job is not None:
            try:
                self.after_cancel(self._plot_auto_job)
            except Exception:
                pass

        self._plot_auto_job = self.after(period, _tick)


def _ref_add(self):
    try:
        x = float(self._ref_x_entry.get().strip())
    except Exception:
        messagebox.showwarning("Linha de referência", "Valor de x inválido.")
        return
    label = self._ref_label_entry.get().strip()
    self.ref_lines.append({"x": x, "label": label})

      self.lb_refs.insert("end", f"{x:g}  —  {label or '(sem rótulo)'}")
    self._ref_x_entry.delete(0, "end");
self._ref_label_entry.delete(0, "end")
    self._draw_results_plots()

def _ref_remove(self):
    sel = list(self.lb_refs.curselection())[::-1]
    for idx in sel:
        self.lb_refs.delete(idx)
        del self.ref_lines[idx]
    self._draw_results_plots()

def _schedule_auto_update(self):
    # cancela anterior
    if self._plot_auto_job is not None:
 
       try:
            self.after_cancel(self._plot_auto_job)
        except Exception:
            pass
        self._plot_auto_job = None

    if not self.var_auto_update.get():
        return

    period = max(200, int(self.var_update_period_ms.get()))

 
       def _tick():
        self._draw_results_plots()
        self._plot_auto_job = self.after(period, _tick)
    self._plot_auto_job = self.after(period, _tick)

def _export_results_fig(self):
    path = filedialog.asksaveasfilename(
        title="Exportar figura",
        defaultextension=".png",
        filetypes=[("PNG", "*.png"), 
("SVG", "*.svg"), ("PDF", "*.pdf"), ("All files", "*.*")]
    )
    if not path:
        return
    dpi = max(72, int(self.var_export_dpi.get()))
    try:
        self.fig_res.savefig(path, dpi=dpi, bbox_inches="tight")
        messagebox.showinfo("Exportar figura", f"Figura salva em:\n{path}")
    except Exception as e:

        messagebox.showerror("Exportar figura", f"Falha ao exportar:\n{e}")