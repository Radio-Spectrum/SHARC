import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import re
import queue
import yaml
import time
import datetime
import threading
import subprocess
from pathlib import Path

def _tab_runner(self, root):
    top = ttk.Frame(root);
top.pack(fill="x")
    self.run_folder = tk.StringVar(value=os.path.join(Path.cwd(), "/sharc/campaigns"))
    ttk.Label(top, text="Pasta com arquivos .yaml").pack(side="left")
    e = ttk.Entry(top, textvariable=self.run_folder)
    e.pack(side="left", fill="x", expand=True, padx=6)
    ttk.Button(top, text="Escolher...", command=lambda: self._pick_folder(self.run_folder)).pack(side="left")
    ttk.Button(top, text="Atualizar lista", command=self._scan_yaml_files).pack(side="left", padx=(6,0))
    ttk.Label(top, text="Paralelo (máx execuções):").pack(side="left", padx=(14,4))
    tk.Spinbox(top, from_=1, to=32, width=4, textvariable=self.var_max_workers).pack(side="left")

    
# Tree for files + progress
    mid = ttk.Frame(root);
mid.pack(fill="both", expand=True, pady=(8,0))
    self.tree = ttk.Treeview(mid, columns=("yaml","status","snap","pct","eta"), show="headings", height=12)
    self.tree.heading("yaml", text="YAML")
    self.tree.heading("status", text="Status")
    self.tree.heading("snap", text="Snapshots (done/total)")
    self.tree.heading("pct", text="%")
    self.tree.heading("eta", text="ETA")
    self.tree.column("yaml", width=380)
    self.tree.column("status", width=220)
    self.tree.column("snap", width=180)
    self.tree.column("pct", width=60, anchor="e")

      self.tree.column("eta", width=120)
    self.tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview);
sb.pack(side="left", fill="y")
    self.tree.configure(yscroll=sb.set)

    right = ttk.Frame(root);
right.pack(fill="x", pady=(8,0))
    self.main_cli_path = tk.StringVar(value=os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_cli.py"))
    ttk.Label(right, text="main_cli.py:").pack(side="left")
    ttk.Entry(right, textvariable=self.main_cli_path, width=44).pack(side="left", padx=6, fill="x", expand=True)
    ttk.Button(right, text="Parar selecionados", command=self._stop_selected).pack(side="right", padx=(6,0))
    ttk.Button(right, text="Executar selecionados", command=self._run_selected_yaml_parallel).pack(side="right")

    logf = ttk.LabelFrame(root, text="Log")
    logf.pack(fill="both", expand=True, pady=(8,0))
    self.txt_log = tk.Text(logf, height=10, wrap="none")
    self.txt_log.pack(fill="both", expand=True)

 
       self._scan_yaml_files()
    self.after(150, self._drain_log_queue)
    self.after(250, self._runner_scheduler_tick)

# ---------------- Runner helpers (parallel) ----------------
def _pick_outdir(self):
    cur = self.var_outdir.get() or os.getcwd()
    if not os.path.isdir(cur): cur = os.getcwd()
    path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta de saída (dentro do YAML)")
    if path:
        if not path.endswith(("/", "\\")):
  
          path = path + os.sep
        self.var_outdir.set(path.replace("\\","/"))

def _pick_yamldir(self):
    p = filedialog.askdirectory(title="Selecionar pasta para salvar os .yaml", initialdir=self.var_yaml_dir.get() or os.getcwd())
    if p:
        self.var_yaml_dir.set(p)

def _pick_folder(self, var):
    cur = var.get() or os.getcwd()
    if not os.path.isdir(cur):

          cur = os.getcwd()
    path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta")
    if path:
        var.set(path)
        self._scan_yaml_files()

def _scan_yaml_files(self):
    if not hasattr(self, "tree"):
        return
    self.tree.delete(*self.tree.get_children())
  
  folder = getattr(self, "run_folder", tk.StringVar(value=os.getcwd())).get()
    if not os.path.isdir(folder):
        return
    files = [f for f in os.listdir(folder) if f.lower().endswith((".yaml",".yml"))]
    files.sort()
    for f in files:
        path = os.path.join(folder, f)
        total = self._yaml_num_snapshots(path) or int(self.var_snaps.get())
  
      self.tree.insert("", "end", iid=path, values=(os.path.basename(path), "Pronto", f"0/{total}", "0", "--"))

def _yaml_num_snapshots(self, ypath):
    try:
        with open(ypath, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            if "general" in data and isinstance(data["general"], dict) and 
"num_snapshots" in data["general"]:
                return int(data["general"]["num_snapshots"])
            if "num_snapshots" in data:
                return int(data["num_snapshots"])
    except Exception:
        pass
    return None

def _run_selected_yaml_parallel(self):

      sel = self.tree.selection()
    if not sel:
        messagebox.showwarning("Runner", "Selecione pelo menos um arquivo YAML.")
        return
    for iid in sel:
        if iid in self.proc_threads and self.proc_threads[iid].is_alive():
            continue
    
    self.jobs_q.put(iid)
        self._update_row(iid, status="Na fila", snap=None, pct=None, eta="--")

def _stop_selected(self):
    sel = self.tree.selection()
    if not sel:
        messagebox.showwarning("Runner", "Selecione pelo menos um YAML.")
        return
    for iid in sel:
        p = 
self.procs.get(iid)
        if p and (p.poll() is None):
            try:
                p.terminate()
                try:
                    p.wait(timeout=2.0)
   
                 except Exception:
                    p.kill()
                self._update_row(iid, status="Parado pelo usuário", eta="--")
            except Exception as e:
           
     self._update_row(iid, status=f"Erro ao parar: {e}")
        else:
            self._update_row(iid, status="Não está rodando")

def _runner_scheduler_tick(self):
    # inicia até max_workers simultâneos
    maxw = max(1, int(self.var_max_workers.get()))
    while len(self.running) < maxw and not self.jobs_q.empty():
        iid = self.jobs_q.get()

        if iid in self.running:
            continue
        if iid in self.proc_threads and self.proc_threads[iid].is_alive():
            continue
        t = threading.Thread(target=self._run_one_yaml, args=(iid,), daemon=True)
        self.proc_threads[iid] = t
      
  self.running.add(iid)
        t.start()
    # reaplicar em loop
    self.after(300, self._runner_scheduler_tick)

def _run_one_yaml(self, ypath):
    declared_total = self._yaml_num_snapshots(ypath) or int(self.var_snaps.get())
    self.runtime[ypath] = {"status":"Rodando", "done":0, "total":declared_total, "declared_total":declared_total, "t0":time.time(), "last_snap_time":None}
    self._update_row(ypath, status="Rodando", snap=f"0/{declared_total}", pct="0", eta="--")

    try:
        cmd 
= [sys.executable, self.main_cli_path.get(), "-p", ypath]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, text=True)
        self.procs[ypath] = proc

        pat_xy = re.compile(r"(?:snapshot|snap)\s*:?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
        pat_hash = re.compile(r"Snapshot\s*#\s*(\d+)", re.IGNORECASE)

        total = declared_total
        for line in proc.stdout:
 
           self.line_q.put(f"[{os.path.basename(ypath)}] {line}")
            m1 = pat_xy.search(line)
            m2 = pat_hash.search(line)

            if m1:
                done = int(m1.group(1));
total_in_line = int(m1.group(2))
                if total_in_line:
                    total = max(total, total_in_line)
                self.runtime[ypath]["done"] = done
                self.runtime[ypath]["total"] = total
  
          elif m2:
                done = int(m2.group(1))
                self.runtime[ypath]["done"] = done
                total = max(total, self.runtime[ypath]["total"])
            else:
  
              continue

            now = time.time()
            self.runtime[ypath]["last_snap_time"] = now
            pct = f"{(100.0*self.runtime[ypath]['done']/max(total,1)):.1f}"
            eta = self._eta_string(self.runtime[ypath]["t0"], now, self.runtime[ypath]["done"], total)
       
     self._update_row(ypath, status="Rodando", snap=f"{self.runtime[ypath]['done']}/{total}", pct=pct, eta=eta)

        proc.wait()
        rc = proc.returncode
        done = self.runtime[ypath]["done"]
        pct = "100" if rc == 0 else f"{(100.0*done/max(total,1)):.1f}"
        self._update_row(ypath, status=("OK" if rc==0 else f"Erro {rc}"), snap=f"{done}/{total}", pct=pct, eta="00:00")
    except Exception 
as e:
        self._update_row(ypath, status=f"Falha: {e}", snap=f"--/--", pct="--", eta="--")
    finally:
        if ypath in self.running:
            self.running.remove(ypath)
        if ypath in self.procs:
            self.procs.pop(ypath, None)

def _eta_string(self, t0, now, done, total):

      if done <= 0 or total <= 0:
        return "--"
    elapsed = now - t0
    rate = elapsed / max(done, 1)  # seg/snapshot
    remain = max(total - done, 0) * rate
    return str(datetime.timedelta(seconds=int(remain)))

def _update_row(self, iid, status=None, snap=None, pct=None, eta=None):
    try:

        cur = list(self.tree.item(iid, "values"))
        if not cur:
            return
        if status is not None: cur[1] = status
        if snap   is not None: cur[2] = snap
        if pct    is not 
None: cur[3] = pct
        if eta    is not None: cur[4] = eta
        self.tree.item(iid, values=cur)
    except Exception:
        pass

def _drain_log_queue(self):
    try:
        while True:
           
 line = self.line_q.get_nowait()
            self.txt_log.insert("end", line)
            if not line.endswith("\n"):
                self.txt_log.insert("end", "\n")
            self.txt_log.see("end")
    except queue.Empty:
        pass

    self.after(150, self._drain_log_queue)