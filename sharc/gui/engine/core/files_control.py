import os
from tkinter import filedialog, messagebox


def _pick_outdir(root):
    cur = root.var_outdir.get() or os.getcwd()
    if not os.path.isdir(cur): cur = os.getcwd()
    path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta de saída (dentro do YAML)")
    if path:
        if not path.endswith(("/", "\\")):
            path = path + os.sep
        root.var_outdir.set(path.replace("\\","/"))


def _pick_yamldir(root):
    p = filedialog.askdirectory(title="Selecionar pasta para salvar os .yaml", initialdir=root.var_yaml_dir.get() or os.getcwd())
    if p:
        root.var_yaml_dir.set(p)

def _save_yaml_to_yamldir(root):
    combos = root._collect_var_combos()
    if combos is None:
        return
    root = root._current_yaml()
    outdir = root.var_yaml_dir.get() or "."
    os.makedirs(outdir, exist_ok=True)
    root._write_yaml_combos(root, outdir, combos)
    messagebox.showinfo("OK", f"YAML(s) gerado(s) em:\n{outdir}")

def _pick_folder(self, var):
    cur = var.get() or os.getcwd()
    if not os.path.isdir(cur):
        cur = os.getcwd()
    path = filedialog.askdirectory(initialdir=cur, title="Selecione a pasta")
    if path:
        var.set(path)
        self._scan_yaml_files()
