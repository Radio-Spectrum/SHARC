import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ast
import os
import math
import random
from pathlib import Path

from utils import add_row_three


class GeneralTab:
    """
    Manages the 'General' tab of the application, handling global simulation parameters,
    file paths, and the setup of variable combinations for batch processing.
    """

    def __init__(self, app, parent_frame):
        """
        Initializes the GeneralTab.

        Args:
            app: Instance of the main App class (main.py) to access shared variables.
            parent_frame: The parent widget where this tab will be rendered.
        """
        self.app = app
        self.frame = parent_frame

        self.var_use_random_seed = tk.BooleanVar(value=False)

        self._build_ui()
        self._setup_traces()

    def _build_ui(self):
        """Constructs the user interface elements for the tab."""
        vcmd = (self.frame.register(self._validate_int), '%P')

        frm = ttk.LabelFrame(self.frame, text="General Parameters")
        frm.pack(fill="x", pady=(0, 6))

        # --- Row 1 ---
        f_seed_cont = ttk.Frame(frm)

        self.e_seed = ttk.Entry(
            f_seed_cont,
            textvariable=self.app.var_seed,
            width=8,
            validate='key',
            validatecommand=vcmd
        )
        self.e_seed.pack(side="left")

        cb_rnd = ttk.Checkbutton(
            f_seed_cont,
            text="Random",
            variable=self.var_use_random_seed,
            command=self._toggle_random_seed
        )
        cb_rnd.pack(side="left", padx=(5, 0))

        e_snaps = ttk.Entry(
            frm,
            textvariable=self.app.var_snaps,
            width=12,
            validate='key',
            validatecommand=vcmd
        )

        cb_sys = ttk.Combobox(
            frm,
            textvariable=self.app.var_system,
            values=["SINGLE_EARTH_STATION", "SINGLE_SPACE_STATION"],
            state="readonly",
            width=26
        )

        add_row_three(frm, 0, [
            ("seed", f_seed_cont),
            ("num_snapshots", e_snaps),
            ("system", cb_sys)
        ])

        # --- Row 2 ---
        row2 = ttk.Frame(frm)
        row2.grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2, text="output_dir (written to YAML)").pack(side="left")

        self.e_outdir = ttk.Entry(row2, textvariable=self.app.var_outdir)
        self.e_outdir.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row2, text="Select...",
                   command=self._pick_outdir).pack(side="left")

        # --- Row 3 ---
        row2b = ttk.Frame(frm)
        row2b.grid(row=2, column=0, columnspan=6, sticky="we", pady=2)
        ttk.Label(row2b, text="yaml_dir (where to save .yaml files)").pack(
            side="left")

        self.e_yamldir = ttk.Entry(row2b, textvariable=self.app.var_yaml_dir)
        self.e_yamldir.pack(side="left", fill="x", expand=True, padx=(6, 6))

        ttk.Button(row2b, text="Select...",
                   command=self._pick_yamldir).pack(side="left")

        # --- Row 4 ---
        e_prefix = ttk.Entry(frm, textvariable=self.app.var_prefix)
        cb_link = ttk.Combobox(
            frm,
            textvariable=self.app.var_imt_link,
            values=["DOWNLINK", "UPLINK"],
            state="readonly",
            width=18
        )

        add_row_three(frm, 3, [
            ("output_dir_prefix (uses {variable})", e_prefix),
            ("imt_link", cb_link),
            ("overwrite_output", ttk.Checkbutton(
                frm, variable=self.app.var_overwrite, text="true/false"))
        ])

        # --- Extra Row ---
        self.lbl_preview = ttk.Label(
            frm, text="Preview: ...", foreground="gray")
        self.lbl_preview.grid(row=4, column=0, columnspan=6,
                              sticky="w", padx=5, pady=(0, 5))

        # --- Row 5 ---
        add_row_three(frm, 5, [
            ("enable_adjacent_channel", ttk.Checkbutton(
                frm, variable=self.app.var_adj, text="true/false")),
            ("enable_cochannel", ttk.Checkbutton(
                frm, variable=self.app.var_coch, text="true/false")),
            ("", ttk.Label(frm, text=""))
        ])

        # --- Combination Variables ---
        box = ttk.LabelFrame(
            self.frame,
            text="Combination Variables (Tags in filename -> Values in YAML)"
        )
        box.pack(fill="both", expand=True, pady=(8, 0))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="Add Variable",
                   command=self._var_add).pack(side="left")
        ttk.Button(toolbar, text="Edit Selected", command=self._var_edit).pack(
            side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Remove Selected",
                   command=self._var_remove).pack(side="left", padx=(6, 0))

        self.var_table = ttk.Treeview(
            box,
            columns=("var", "tags", "values"),
            show="headings",
            height=6
        )

        self.var_table.heading("var", text="Variable (placeholder)")
        self.var_table.heading("tags", text="Tags (names e.g., ['D1','D2'])")
        self.var_table.heading(
            "values", text="Values (e.g., [100, 200] or paths)")

        self.var_table.column("var", width=150)
        self.var_table.column("tags", width=250)
        self.var_table.column("values", width=450)

        self.var_table.pack(fill="both", expand=True, pady=(4, 6))

        self.var_table.bind("<Double-1>", lambda e: self._var_edit())

        if not self.var_table.get_children():
            self.var_table.insert("", "end", values=(
                "dist", "['D1','D2']", "[1000,2000]"))

        row_gen = ttk.Frame(self.frame)
        row_gen.pack(fill="x", pady=(8, 0))
        ttk.Button(
            row_gen,
            text="Generate YAML(s) in yaml_dir (all combinations)",
            command=self.app.save_yaml_to_yamldir
        ).pack(side="left")

    def _toggle_random_seed(self):
        """Enables or disables random seed generation."""
        if self.var_use_random_seed.get():
            rnd_val = random.randint(1, 9999)
            self.app.var_seed.set(str(rnd_val))
            self.e_seed.configure(state='disabled')
        else:
            self.e_seed.configure(state='normal')

    def _setup_traces(self):
        """Sets up variable observers for visual feedback and preview updates."""
        self.app.var_outdir.trace_add(
            "write", lambda *a: self._check_path(
                self.e_outdir, self.app.var_outdir)
        )
        self.app.var_yaml_dir.trace_add(
            "write", lambda *a: self._check_path(
                self.e_yamldir, self.app.var_yaml_dir)
        )

        self.app.var_prefix.trace_add("write", self._update_preview)

        self._check_path(self.e_outdir, self.app.var_outdir)
        self._check_path(self.e_yamldir, self.app.var_yaml_dir)
        self._update_preview()

    def _validate_int(self, P):
        """Entry validator: allows only digits, empty string, or a single minus sign."""
        if P == "" or P == "-":
            return True
        return P.isdigit() or (P.startswith("-") and P[1:].isdigit())

    def _check_path(self, entry_widget, string_var):
        """Highlights the entry text in red if the path does not exist."""
        path = string_var.get()
        if path and os.path.isdir(path):
            entry_widget.configure(foreground="black")
        else:
            entry_widget.configure(foreground="red")

    def _update_preview(self, *args):
        """Updates the preview label by simulating the substitution of the first variable."""
        text = self.app.var_prefix.get()
        children = self.var_table.get_children()

        if not children:
            self.lbl_preview.config(text=f"Preview (no variables): {text}")
            return

        try:
            item = self.var_table.item(children[0])
            name, tags_str, vals_str = item['values']

            tags_list = self._parse_list_safe(tags_str, [])
            first_tag = tags_list[0] if len(tags_list) > 0 else "?"

            simulated = text.replace(f"{{{name}}}", str(first_tag))

            if len(children) > 1:
                self.lbl_preview.config(
                    text=f"Example (1st var): {simulated} (varying others...)"
                )
            else:
                self.lbl_preview.config(text=f"Example: {simulated}")

        except Exception:
            self.lbl_preview.config(
                text="Error generating preview (check variable syntax)"
            )

    def _pick_outdir(self):
        """Opens a directory picker for the output directory."""
        cur = self.app.var_outdir.get() or os.getcwd()
        if not os.path.isdir(cur):
            cur = os.getcwd()

        path = filedialog.askdirectory(
            initialdir=cur, title="Select Output Directory"
        )
        if path:
            if not path.endswith(("/", "\\")):
                path += os.sep
            self.app.var_outdir.set(path.replace("\\", "/"))

    def _pick_yamldir(self):
        """Opens a directory picker for the YAML save directory."""
        cur = self.app.var_yaml_dir.get() or os.getcwd()
        path = filedialog.askdirectory(
            title="Select folder to save YAMLs", initialdir=cur
        )
        if path:
            self.app.var_yaml_dir.set(path)

    def _var_add(self):
        """Adds a new placeholder row and opens the editor."""
        iid = self.var_table.insert("", "end", values=("new_var", "[]", "[]"))
        self.var_table.selection_set(iid)
        self.var_table.focus(iid)
        self._open_var_editor(iid, "new_var", "[]", "[]")

    def _var_remove(self):
        """Removes selected variables from the table."""
        sel = self.var_table.selection()
        for iid in sel:
            self.var_table.delete(iid)
        self._update_preview()

    def _var_edit(self):
        """Opens the editor for the currently selected variable."""
        sel = self.var_table.selection()
        if not sel:
            messagebox.showwarning(
                "Variables", "Please select a variable to edit.")
            return
        iid = sel[0]
        var_key, tags_raw, vals_raw = self.var_table.item(iid, "values")
        self._open_var_editor(iid, var_key, tags_raw, vals_raw)

    def _parse_list_safe(self, s, default):
        """Safely parses a string representation of a list."""
        s = (s or "").strip()
        if not s:
            return default
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, (list, tuple)):
                return list(obj)
        except Exception:
            pass
        return default

    def _open_var_editor(self, iid, var_key, tags_raw, vals_raw):
        """
        Opens an advanced popup window to edit Tag <-> Value mappings.

        Args:
            iid: Treeview item ID.
            var_key: Current variable name.
            tags_raw: String representation of the tags list.
            vals_raw: String representation of the values list.
        """
        dlg = tk.Toplevel(self.frame)
        dlg.title(f"Edit Variable: {var_key}")
        dlg.geometry("700x600")

        # --- Header ---
        top = ttk.Frame(dlg)
        top.pack(fill="x", padx=10, pady=(10, 6))

        ttk.Label(top, text="Variable (YAML placeholder):").pack(side="left")
        e_var = ttk.Entry(top, width=24)
        e_var.insert(0, str(var_key))
        e_var.pack(side="left", padx=(6, 0))

        ttk.Label(top, text="(use {var} in output_dir_prefix)", foreground="gray").pack(
            side="left", padx=10
        )

        # --- List Frame ---
        frm_list = ttk.LabelFrame(dlg, text="Mapping (Tag -> Value)")
        frm_list.pack(fill="both", expand=True, padx=10, pady=6)

        canvas = tk.Canvas(frm_list)
        scrollbar = ttk.Scrollbar(
            frm_list, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(scrollable_frame, text="Tag (Filename)").grid(
            row=0, column=0, sticky="w", padx=5
        )
        ttk.Label(scrollable_frame, text="Value (Number or Path)").grid(
            row=0, column=1, sticky="w", padx=5
        )

        rows = []

        tags_list = self._parse_list_safe(tags_raw, [])
        vals_list = self._parse_list_safe(vals_raw, [])

        n = max(len(tags_list), len(vals_list), 1)

        while len(tags_list) < n:
            tags_list.append("")
        while len(vals_list) < n:
            vals_list.append("")

        def _add_row_ui(t="", v=""):
            r = len(rows) + 1
            e1 = ttk.Entry(scrollable_frame, width=25)
            e1.insert(0, str(t))
            e2 = ttk.Entry(scrollable_frame, width=55)
            e2.insert(0, str(v))

            e1.grid(row=r, column=0, sticky="we", pady=2, padx=5)
            e2.grid(row=r, column=1, sticky="we", pady=2, padx=5)
            rows.append((e1, e2))

        for t, v in zip(tags_list, vals_list):
            _add_row_ui(t, v)

        # --- Action Buttons ---
        actions = ttk.Frame(dlg)
        actions.pack(fill="x", padx=10, pady=(0, 6))

        def add_line():
            _add_row_ui("", "")

        def remove_last():
            if not rows:
                return
            e1, e2 = rows.pop()
            e1.destroy()
            e2.destroy()
            canvas.configure(scrollregion=canvas.bbox("all"))

        def pick_files():
            files = filedialog.askopenfilenames(
                title=f"Select files for {e_var.get()}",
                parent=dlg
            )
            if not files:
                return
            while rows:
                remove_last()

            for f in files:
                f = f.replace("\\", "/")
                tag = Path(f).stem
                _add_row_ui(tag, f)

        ttk.Button(actions, text="Add Row", command=add_line).pack(side="left")
        ttk.Button(actions, text="Remove Last",
                   command=remove_last).pack(side="left", padx=5)
        ttk.Button(actions, text="Select Files...",
                   command=pick_files).pack(side="left", padx=5)

        # --- Automatic Generation ---
        auto = ttk.LabelFrame(
            dlg, text="Generate Values Automatically (Numeric)")
        auto.pack(fill="x", padx=10, pady=(6, 0))

        mode = tk.StringVar(value="STEP")

        rowm = ttk.Frame(auto)
        rowm.pack(fill="x", pady=2)
        ttk.Radiobutton(
            rowm, text="Start/End/Step", variable=mode, value="STEP"
        ).pack(side="left")
        ttk.Radiobutton(
            rowm, text="Start/End/N Points", variable=mode, value="NPTS"
        ).pack(side="left", padx=15)

        rowa = ttk.Frame(auto)
        rowa.pack(fill="x", pady=4)

        ttk.Label(rowa, text="Start:").pack(side="left")
        e_start = ttk.Entry(rowa, width=8)
        e_start.pack(side="left", padx=2)

        ttk.Label(rowa, text="End:").pack(side="left", padx=(10, 0))
        e_end = ttk.Entry(rowa, width=8)
        e_end.pack(side="left", padx=2)

        lbl3 = ttk.Label(rowa, text="Step:")
        lbl3.pack(side="left", padx=(10, 0))
        e_third = ttk.Entry(rowa, width=8)
        e_third.pack(side="left", padx=2)

        ttk.Label(rowa, text="Base Tag (e.g., 'V'):").pack(
            side="left", padx=(15, 0))
        e_tagbase = ttk.Entry(rowa, width=8)
        e_tagbase.pack(side="left", padx=2)
        e_tagbase.insert(0, "V")

        def _update_mode(*_):
            lbl3.config(text="Step:" if mode.get() == "STEP" else "N Points:")
        mode.trace_add("write", _update_mode)

        def _generate_values():
            try:
                s = float(e_start.get())
                e = float(e_end.get())
                t = float(e_third.get())
            except ValueError:
                messagebox.showerror(
                    "Error", "Please fill Start, End and Step/N with numbers.", parent=dlg
                )
                return

            vals = []
            if mode.get() == "STEP":
                step = t
                if step == 0:
                    return
                curr = s
                count = 0
                if step > 0:
                    while curr <= e + 1e-9 and count < 10000:
                        vals.append(curr)
                        curr += step
                        count += 1
                else:
                    while curr >= e - 1e-9 and count < 10000:
                        vals.append(curr)
                        curr += step
                        count += 1
            else:
                n_pts = int(t)
                if n_pts <= 1:
                    vals = [s]
                else:
                    vals = [s + (e - s) * i / (n_pts - 1)
                            for i in range(n_pts)]

            tag_b = e_tagbase.get()

            while rows:
                remove_last()

            for i, v in enumerate(vals, 1):
                v_str = f"{int(v)}" if abs(v - round(v)) < 1e-9 else f"{v:.4g}"
                _add_row_ui(f"{tag_b}{i}", v_str)

        ttk.Button(auto, text="Generate and Replace", command=_generate_values).pack(
            anchor="e", padx=5, pady=2
        )

        # --- Final Buttons ---
        btns = ttk.Frame(dlg)
        btns.pack(fill="x", padx=10, pady=10)

        def ok():
            tags_out = []
            vals_out = []
            for e1, e2 in rows:
                t_val = e1.get().strip()
                v_val = e2.get().strip()
                if not t_val and not v_val:
                    continue

                tags_out.append(t_val)
                try:
                    num = ast.literal_eval(v_val)
                    vals_out.append(num)
                except:
                    vals_out.append(v_val)

            if not tags_out:
                messagebox.showwarning(
                    "Warning", "The list cannot be empty.", parent=dlg)
                return

            if len(tags_out) != len(vals_out):
                messagebox.showwarning(
                    "Error", "Tags and Values must have the same length.", parent=dlg)
                return

            new_name = e_var.get().strip()
            if not new_name:
                messagebox.showwarning(
                    "Error", "Variable name is required.", parent=dlg)
                return

            self.var_table.item(iid, values=(
                new_name, str(tags_out), str(vals_out)))
            self._update_preview()
            dlg.destroy()

        ttk.Button(btns, text="OK", command=ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(
            side="left", padx=10)
