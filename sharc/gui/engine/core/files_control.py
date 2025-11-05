import os
from tkinter import filedialog


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
            if "general" in data and isinstance(data["general"], dict) and "num_snapshots" in data["general"]:
                return int(data["general"]["num_snapshots"])
            if "num_snapshots" in data:
                return int(data["num_snapshots"])
    except Exception:
        pass
    return None