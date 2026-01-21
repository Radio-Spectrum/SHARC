import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ast
import os
import random  # <--- Import necessário

# Importa a função auxiliar definida em utils.py
from utils import add_row_three

class GeneralTab:
    def __init__(self, app, parent_frame):
        """
        :param app: Instância da classe App (main.py) para acessar variáveis compartilhadas.
        :param parent_frame: O widget onde esta aba será desenhada.
        """
        self.app = app
        self.frame = parent_frame

        # Variável local para controlar o Checkbox de Random
        self.var_use_random_seed = tk.BooleanVar(value=False)

        # Constrói a interface
        self._build_ui()

        # Configura os traces (monitores) para feedback visual e preview
        self._setup_traces()

    def _build_ui(self):
        # --- Configuração de Validação (Apenas Números) ---
        vcmd = (self.frame.register(self._validate_int), '%P')

        # Cria um LabelFrame principal
        frm = ttk.LabelFrame(self.frame, text="Parâmetros gerais")
        frm.pack(fill="x")

        # --- Linha 1: Seed, Snaps, System ---
        
        # [MODIFICAÇÃO] Container para Seed + Checkbox Random
        f_seed_cont = ttk.Frame(frm)
        
        self.e_seed = ttk.Entry(f_seed_cont, textvariable=self.app.var_seed, width=8,
                           validate='key', validatecommand=vcmd)
        self.e_seed.pack(side="left")

        # Checkbutton para ativar modo aleatório
        cb_rnd = ttk.Checkbutton(f_seed_cont, text="Random SEED", variable=self.var_use_random_seed,
                                 command=self._toggle_random_seed)
        cb_rnd.pack(side="left", padx=(5, 0))

        # Demais campos da linha 1
        e_snaps = ttk.Entry(frm, textvariable=self.app.var_snaps, width=12,
                            validate='key', validatecommand=vcmd)

        cb_sys = ttk.Combobox(frm, textvariable=self.app.var_system,
                              values=["SINGLE_EARTH_STATION",
                                      "SINGLE_SPACE_STATION"],
                              state="readonly", width=26)

        # Adiciona à grade usando o container do seed
        add_row_three(frm, 0, [
            ("seed", f_seed_cont),
            ("num_snapshots", e_snaps),
            ("system", cb_sys)
        ])

        # --- Linha 2: Output Dir ---
        row2 = ttk.Frame(frm)
        row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2, text="output_dir (vai dentro do YAML)").pack(side="left")

        self.e_outdir = ttk.Entry(row2, textvariable=self.app.var_outdir)
        self.e_outdir.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row2, text="Selecionar...",
                   command=self._pick_outdir).pack(side="left")

        # --- Linha 3: YAML Dir ---
        row2b = ttk.Frame(frm)
        row2b.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2b, text="yaml_dir (onde salvar os .yaml)").pack(side="left")

        self.e_yamldir = ttk.Entry(row2b, textvariable=self.app.var_yaml_dir)
        self.e_yamldir.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row2b, text="Selecionar...",
                   command=self._pick_yamldir).pack(side="left")

        # --- Linha 4: Prefix, Link, Overwrite ---
        e_prefix = ttk.Entry(frm, textvariable=self.app.var_prefix)
        cb_link = ttk.Combobox(frm, textvariable=self.app.var_imt_link,
                               values=["DOWNLINK", "UPLINK"], state="readonly", width=18)

        add_row_three(frm, 3, [
            ("output_dir_prefix (usa {variavel})", e_prefix),
            ("imt_link", cb_link),
            ("overwrite_output", ttk.Checkbutton(
                frm, variable=self.app.var_overwrite, text="true/false"))
        ])

        # --- Linha Extra: Preview do Prefixo ---
        self.lbl_preview = ttk.Label(
            frm, text="Preview: ...", foreground="gray")
        self.lbl_preview.grid(row=4, column=0, columnspan=6,
                              sticky="w", padx=5, pady=(0, 5))

        # --- Linha 5: Adjacent / Cochannel ---
        add_row_three(frm, 5, [
            ("enable_adjacent_channel", ttk.Checkbutton(
                frm, variable=self.app.var_adj, text="true/false")),
            ("enable_cochannel", ttk.Checkbutton(
                frm, variable=self.app.var_coch, text="true/false")),
            ("", ttk.Label(frm, text=""))
        ])

        # ---- Seção: Variáveis para combinações ----
        box = ttk.LabelFrame(
            self.frame, text="Variáveis para combinações (Double-click para editar)")
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
        self.var_table.heading("name", text="Nome ({nome})")
        self.var_table.heading(
            "values", text="Valores (lista: [10,20] ou [\"LOW\",\"MID\"])")
        self.var_table.column("name", width=180)
        self.var_table.column("values", width=640)
        self.var_table.pack(fill="both", expand=True, pady=(6, 6))

        # Evento de duplo clique para editar
        self.var_table.bind("<Double-1>", self._on_double_click)

        # Insere valor padrão se estiver vazio
        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=(
                "long", "[-10, -20, -30, -40, -50]"))

        # Botão Gerar
        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(8, 0))
        ttk.Button(row_gen, text="Gerar YAML(s) no yaml_dir (todas combinações)",
                   command=self.app.save_yaml_to_yamldir).pack(side="left")

    # ---------------- Lógica Nova (Random Seed) ----------------
    def _toggle_random_seed(self):
        """Ativa ou desativa a geração de seed aleatória."""
        if self.var_use_random_seed.get():
            # Gera número entre 1 e 9999
            rnd_val = random.randint(1, 9999)
            self.app.var_seed.set(str(rnd_val))
            # Desabilita edição manual para garantir consistência
            self.e_seed.configure(state='disabled')
        else:
            # Habilita edição manual novamente
            self.e_seed.configure(state='normal')

    # ---------------- Setup de Traces e Validadores ----------------

    def _setup_traces(self):
        """Configura observadores nas variáveis para feedback visual."""
        # Monitora caminhos para verificar existência
        self.app.var_outdir.trace_add(
            "write", lambda *a: self._check_path(self.e_outdir, self.app.var_outdir))
        self.app.var_yaml_dir.trace_add(
            "write", lambda *a: self._check_path(self.e_yamldir, self.app.var_yaml_dir))

        # Monitora prefixo para atualizar o preview
        self.app.var_prefix.trace_add("write", self._update_preview)

        # Chama uma vez para estado inicial
        self._check_path(self.e_outdir, self.app.var_outdir)
        self._check_path(self.e_yamldir, self.app.var_yaml_dir)
        self._update_preview()

    def _validate_int(self, P):
        """Validador para Entry: permite apenas dígitos ou vazio (e sinal negativo)."""
        if P == "" or P == "-":
            return True
        return P.isdigit() or (P.startswith("-") and P[1:].isdigit())

    def _check_path(self, entry_widget, string_var):
        """Coloca texto em vermelho se o caminho não existir."""
        path = string_var.get()
        if path and os.path.isdir(path):
            entry_widget.configure(foreground="black")
        else:
            entry_widget.configure(foreground="red")

    def _update_preview(self, *args):
        """Atualiza o Label de preview simulando a substituição da primeira variável."""
        text = self.app.var_prefix.get()
        children = self.var_table.get_children()

        if not children:
            self.lbl_preview.config(text=f"Preview (sem variáveis): {text}")
            return

        # Pega a primeira variável da tabela para simular
        try:
            item = self.var_table.item(children[0])
            name, vals_str = item['values']
            val_list = ast.literal_eval(vals_str)

            first_val = val_list[0] if len(val_list) > 0 else "?"

            # Tenta substituir {nome} pelo primeiro valor
            simulated = text.replace(f"{{{name}}}", str(first_val))

            # Se houver mais variáveis, indicamos com ...
            if len(children) > 1:
                self.lbl_preview.config(
                    text=f"Exemplo (1ª var): {simulated} (variando outros...)")
            else:
                self.lbl_preview.config(text=f"Exemplo: {simulated}")

        except Exception:
            self.lbl_preview.config(
                text="Erro ao gerar preview (verifique sintaxe das variáveis)")

    # ---------------- Lógica Local (Pickers e Tabela) ----------------

    def _pick_outdir(self):
        cur = self.app.var_outdir.get() or os.getcwd()
        if not os.path.isdir(cur):
            cur = os.getcwd()

        path = filedialog.askdirectory(
            initialdir=cur, title="Selecione a pasta de saída")
        if path:
            if not path.endswith(("/", "\\")):
                path += os.sep
            self.app.var_outdir.set(path.replace("\\", "/"))

    def _pick_yamldir(self):
        cur = self.app.var_yaml_dir.get() or os.getcwd()
        p = filedialog.askdirectory(
            title="Selecionar pasta para salvar YAMLs", initialdir=cur)
        if p:
            self.app.var_yaml_dir.set(p)

    def _on_double_click(self, event):
        """Detecta clique duplo na Treeview para editar."""
        region = self.var_table.identify("region", event.x, event.y)
        if region == "cell":
            self._var_edit()

    def _var_edit(self):
        """Abre diálogo para editar a variável selecionada."""
        sel = self.var_table.selection()
        if not sel:
            return

        item = self.var_table.item(sel[0])
        old_name, old_vals = item['values']

        self._open_var_dialog(old_name, old_vals, item_id=sel[0])

    def _var_add(self):
        """Abre diálogo para adicionar nova variável."""
        self._open_var_dialog("", "")

    def _open_var_dialog(self, default_name, default_vals, item_id=None):
        """
        Cria o popup de formulário para Adicionar ou Editar.
        :param item_id: Se fornecido, estamos editando essa linha da Treeview.
        """
        is_edit = (item_id is not None)
        title = "Editar variável" if is_edit else "Adicionar variável"

        dlg = tk.Toplevel(self.frame)
        dlg.title(title)

        ttk.Label(dlg, text="Nome da variável (ex: 'lat', 'power'):").pack(
            anchor="w", padx=10, pady=(10, 2))
        e_name = ttk.Entry(dlg)
        e_name.pack(fill="x", padx=10)
        e_name.insert(0, default_name)

        ttk.Label(dlg, text="Valores (lista Python, ex: [1, 2, 3]):").pack(
            anchor="w", padx=10, pady=(10, 2))
        e_vals = ttk.Entry(dlg)
        e_vals.pack(fill="x", padx=10)
        e_vals.insert(0, default_vals)

        btns = ttk.Frame(dlg)
        btns.pack(fill="x", pady=10)

        def _ok():
            name = e_name.get().strip()
            vals = e_vals.get().strip()

            if not name:
                messagebox.showwarning("Aviso", "Informe um nome.", parent=dlg)
                return

            # Validação da lista
            try:
                lst = ast.literal_eval(vals)
                if not isinstance(lst, (list, tuple)):
                    raise ValueError()
            except Exception:
                messagebox.showwarning(
                    "Erro", "Os valores devem ser uma lista válida (ex: [10, 20]).", parent=dlg)
                return

            if is_edit:
                self.var_table.item(item_id, values=(name, vals))
            else:
                self.var_table.insert("", "end", values=(name, vals))

            # Atualiza preview e fecha
            self._update_preview()
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
        self._update_preview()