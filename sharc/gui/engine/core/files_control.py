import os
from tkinter import filedialog, messagebox


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


def _save_yaml_to_yamldir(self):
    combos = self._collect_var_combos()
    if combos is None:
        return
    root = self._current_yaml()
    outdir = self.var_yaml_dir.get() or "."
    os.makedirs(outdir, exist_ok=True)
    self._write_yaml_combos(root, outdir, combos)
    messagebox.showinfo("OK", f"YAML(s) gerado(s) em:\n{outdir}")