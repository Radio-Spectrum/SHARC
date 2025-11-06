import os
import tkinter as tk
import pyaml
from tkinter import filedialog, messagebox


def dump_yaml_block(d, indent=0):
    lines = []
    sp = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.extend(dump_yaml_block(v, indent + 1))
            elif isinstance(v, (list, tuple)):
                lines.append(f"{sp}{k}:")
                for it in v:
                    if isinstance(it, (dict, list, tuple)):
                        lines.append(f"{sp}-")
                        lines.extend(dump_yaml_block(it, indent + 1))
                    elif isinstance(it, bool):
                        lines.append(f"{sp}- {_yaml_bool(it)}")
                    elif it is None:
                        lines.append(f"{sp}- null")
                    else:
                        lines.append(f"{sp}- {it}")
            elif isinstance(v, bool):
                lines.append(f"{sp}{k}: {_yaml_bool(v)}")
            elif v is None:
                lines.append(f"{sp}{k}: null")
            else:
                lines.append(f"{sp}{k}: {v}")
    else:
        lines.append(f"{sp}{d}")
    return lines


def build_yaml_text(root_dict: dict) -> str:
    return "\n".join(dump_yaml_block(root_dict)) + "\n"


def _update_yaml_preview(self):
    root = self._current_yaml()
    text = build_yaml_text(root)
    self.txt_yaml.delete("1.0", tk.END)
    self.txt_yaml.insert(tk.END, text)


def _save_yaml_dialog_multicombos(self):
    combos = self._collect_var_combos()
    if combos is None:
        return
    root = self._current_yaml()
    initdir = self.var_yaml_dir.get() or os.getcwd()
    os.makedirs(initdir, exist_ok=True)
    path = filedialog.asksaveasfilename(
        title="Escolha um nome (usaremos apenas a pasta selecionada)",
        defaultextension=".yaml",
        initialdir=initdir,
        initialfile=(self.var_prefix.get() or "scenario") + ".yaml",
        filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
    )
    if not path:
        return
    outdir = os.path.dirname(path)
    os.makedirs(outdir, exist_ok=True)
    self._write_yaml_combos(root, outdir, combos)
    self.var_yaml_dir.set(outdir)
    messagebox.showinfo("OK", f"YAML(s) salvo(s) em:\n{outdir}")

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
