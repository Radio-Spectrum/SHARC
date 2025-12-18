import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ast
from pathlib import Path
import os

# Importa a função auxiliar definida em utils.py
from utils import add_row_three


class GeneralTab:
    def __init__(self, app, parent_frame):
        """
        :param app: Instância da classe App (main.py) para acessar variáveis compartilhadas.
        :param parent_frame: O widget onde esta aba será desenhada (dentro do Notebook).
        """
        self.app = app
        self.frame = parent_frame

        # Constrói a interface
        self._build_ui()

    def _build_ui(self):
        # Cria um LabelFrame principal
        frm = ttk.LabelFrame(self.frame, text="Parâmetros gerais")
        frm.pack(fill="x")

        # Linha 1: Seed, Snaps, System
        # Note o uso de self.app.var_... para acessar as variáveis
        e_seed = ttk.Entry(frm, textvariable=self.app.var_seed, width=12)
        e_snaps = ttk.Entry(frm, textvariable=self.app.var_snaps, width=12)
        cb_sys = ttk.Combobox(frm, textvariable=self.app.var_system,
                              values=["SINGLE_EARTH_STATION",
                                      "SINGLE_SPACE_STATION"],
                              state="readonly", width=26)

        add_row_three(frm, 0, [
            ("seed", e_seed),
            ("num_snapshots", e_snaps),
            ("system", cb_sys)
        ])

        # Linha 2: Output Dir
        row2 = ttk.Frame(frm)
        row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2, text="output_dir (vai dentro do YAML)").pack(
            side="left")

        e_outdir = ttk.Entry(row2, textvariable=self.app.var_outdir)
        e_outdir.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row2, text="Selecionar...",
                   command=self._pick_outdir).pack(side="left")

        # Linha 3: YAML Dir
        row2b = ttk.Frame(frm)
        row2b.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2b, text="yaml_dir (onde salvar os .yaml)").pack(
            side="left")

        e_yamldir = ttk.Entry(row2b, textvariable=self.app.var_yaml_dir)
        e_yamldir.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row2b, text="Selecionar...",
                   command=self._pick_yamldir).pack(side="left")

        # Linha 4: Prefix, Link, Overwrite
        e_prefix = ttk.Entry(frm, textvariable=self.app.var_prefix)
        cb_link = ttk.Combobox(frm, textvariable=self.app.var_imt_link,
                               values=["DOWNLINK", "UPLINK"], state="readonly", width=18)

        add_row_three(frm, 3, [
            ("output_dir_prefix (usa {variavel})", e_prefix),
            ("imt_link", cb_link),
            ("overwrite_output", ttk.Checkbutton(
                frm, variable=self.app.var_overwrite, text="true/false"))
        ])

        # Linha 5: Adjacent / Cochannel
        add_row_three(frm, 4, [
            ("enable_adjacent_channel", ttk.Checkbutton(
                frm, variable=self.app.var_adj, text="true/false")),
            ("enable_cochannel", ttk.Checkbutton(
                frm, variable=self.app.var_coch, text="true/false")),
            ("", ttk.Label(frm, text=""))
        ])

        # ---- Seção: Variáveis para combinações ----
        box = ttk.LabelFrame(
            self.frame, text="Variáveis para combinações (use {nome} no output_dir_prefix e no YAML)")
        box.pack(fill="both", expand=True, pady=(8, 0))

        # Toolbar da tabela
        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Adicionar variável",
                   command=self._var_add).pack(side="left")
        ttk.Button(toolbar, text="Remover selecionadas",
                   command=self._var_remove).pack(side="left", padx=(6, 0))

        # Tabela Treeview
        self.var_table = ttk.Treeview(box, columns=(
            "name", "values"), show="headings", height=5)
        self.var_table.heading("name", text="nome")
        self.var_table.heading(
            "values", text="valores (lista: [10,20] ou [\"LOW\",\"MID\"])")
        self.var_table.column("name", width=180)
        self.var_table.column("values", width=640)
        self.var_table.pack(fill="both", expand=True, pady=(6, 6))

        # Insere valor padrão se estiver vazio
        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=(
                "long", "[-10, -20, -30, -40, -50]"))

        # Botão Gerar (chama método no App principal)
        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(8, 0))
        ttk.Button(row_gen, text="Gerar YAML(s) no yaml_dir (todas combinações)",
                   command=self.app.save_yaml_to_yamldir).pack(side="left")

    # ---------------- Lógica Local (Pickers e Tabela) ----------------

    def _pick_outdir(self):
        cur = self.app.var_outdir.get() or os.getcwd()
        if not os.path.isdir(cur):
            cur = os.getcwd()
        path = filedialog.askdirectory(
            initialdir=cur, title="Selecione a pasta de saída (dentro do YAML)")
        if path:
            # Normaliza barras para evitar problemas no Windows/Linux misturados
            if not path.endswith(("/", "\\")):
                path = path + os.sep
            self.app.var_outdir.set(path.replace("\\", "/"))

    def _pick_yamldir(self):
        cur = self.app.var_yaml_dir.get() or os.getcwd()
        p = filedialog.askdirectory(
            title="Selecionar pasta para salvar os .yaml", initialdir=cur)
        if p:
            self.app.var_yaml_dir.set(p)

    def _var_add(self):
        # Diálogo local para adicionar variável
        dlg = tk.Toplevel(self.frame)
        dlg.title("Adicionar variável")

        ttk.Label(dlg, text="Nome da variável (use {nome} no prefix/YAML):").pack(
            anchor="w", padx=10, pady=(10, 2))
        e_name = ttk.Entry(dlg)
        e_name.pack(fill="x", padx=10)

        ttk.Label(dlg, text="Valores (lista):").pack(
            anchor="w", padx=10, pady=(10, 2))
        e_vals = ttk.Entry(dlg)
        e_vals.pack(fill="x", padx=10)

        btns = ttk.Frame(dlg)
        btns.pack(fill="x", pady=10)

        def _ok():
            name = e_name.get().strip()
            vals = e_vals.get().strip()
            if not name:
                messagebox.showwarning(
                    "Variáveis", "Informe um nome.", parent=dlg)
                return
            if not vals:
                messagebox.showwarning(
                    "Variáveis", "Informe valores em lista.", parent=dlg)
                return
            try:
                lst = ast.literal_eval(vals)
                if not isinstance(lst, (list, tuple)):
                    raise ValueError()
            except Exception:
                messagebox.showwarning(
                    "Variáveis", "Valores devem ser uma lista Python válida.", parent=dlg)
                return

            self.var_table.insert("", "end", values=(name, vals))
            dlg.destroy()

        ttk.Button(btns, text="OK", command=_ok).pack(
            side="left", padx=(10, 4))
        ttk.Button(btns, text="Cancelar",
                   command=dlg.destroy).pack(side="left")
        e_name.focus_set()

    def _var_remove(self):
        sel = self.var_table.selection()
        for iid in sel:
            self.var_table.delete(iid)
