import queue
import threading
from tkinter import messagebox


def _update_row(self, iid, status=None, snap=None, pct=None, eta=None):
    try:
        cur = list(self.tree.item(iid, "values"))
        if not cur:
            return
        if status is not None: cur[1] = status
        if snap   is not None: cur[2] = snap
        if pct    is not None: cur[3] = pct
        if eta    is not None: cur[4] = eta
        self.tree.item(iid, values=cur)
    except Exception:
        pass

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
        p = self.procs.get(iid)
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