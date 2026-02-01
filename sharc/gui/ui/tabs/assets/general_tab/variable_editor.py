import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import ast

# Import logic from the new utils file
from ui.tabs.assets.general_tab.general_tools import parse_list_safe, generate_sequence, format_number


class VariableEditor(tk.Toplevel):
    """
    A dialog window to edit Tag <-> Value mappings for a simulation variable.
    """

    def __init__(self, parent, var_key, tags_raw, vals_raw, on_save_callback):
        super().__init__(parent)
        self.title(f"Edit Variable: {var_key}")
        self.geometry("700x600")
        self.transient(parent)  # Keep on top of parent

        self.on_save = on_save_callback
        self.rows = []  # Stores (Entry_Tag, Entry_Value) tuples

        # Initial Data
        self.tags_list = parse_list_safe(tags_raw, [])
        self.vals_list = parse_list_safe(vals_raw, [])

        self._build_ui(var_key)
        self._populate_initial_rows()

    def _build_ui(self, var_key):
        # --- Header ---
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))

        ttk.Label(top, text="Variable Name:").pack(side="left")
        self.e_var = ttk.Entry(top, width=24)
        self.e_var.insert(0, str(var_key))
        self.e_var.pack(side="left", padx=(6, 0))

        ttk.Label(top, text="(use {name} in paths)",
                  foreground="gray").pack(side="left", padx=10)

        # --- Scrollable List Area ---
        frm_list = ttk.LabelFrame(self, text="Mapping (Tag -> Value)")
        frm_list.pack(fill="both", expand=True, padx=10, pady=6)

        canvas = tk.Canvas(frm_list)
        scrollbar = ttk.Scrollbar(
            frm_list, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas = canvas  # Keep reference to update scrollregion

        # Column Headers
        ttk.Label(self.scroll_frame, text="Tag (Filename)").grid(
            row=0, column=0, sticky="w", padx=5)
        ttk.Label(self.scroll_frame, text="Value (Number or Path)").grid(
            row=0, column=1, sticky="w", padx=5)

        # --- Action Buttons ---
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=10, pady=(0, 6))

        ttk.Button(actions, text="Add Row",
                   command=lambda: self._add_row_ui("", "")).pack(side="left")
        ttk.Button(actions, text="Remove Last",
                   command=self._remove_last_row).pack(side="left", padx=5)
        ttk.Button(actions, text="Select Files...",
                   command=self._pick_files).pack(side="left", padx=5)

        # --- Auto-Generation Section ---
        self._build_auto_gen_ui()

        # --- Bottom Buttons ---
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="OK", command=self._on_ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(
            side="left", padx=10)

    def _build_auto_gen_ui(self):
        auto = ttk.LabelFrame(
            self, text="Generate Values Automatically (Numeric)")
        auto.pack(fill="x", padx=10, pady=(6, 0))

        self.gen_mode = tk.StringVar(value="STEP")

        rowm = ttk.Frame(auto)
        rowm.pack(fill="x", pady=2)
        ttk.Radiobutton(rowm, text="Start/End/Step", variable=self.gen_mode,
                        value="STEP", command=self._update_gen_labels).pack(side="left")
        ttk.Radiobutton(rowm, text="Start/End/N Points", variable=self.gen_mode,
                        value="NPTS", command=self._update_gen_labels).pack(side="left", padx=15)

        rowa = ttk.Frame(auto)
        rowa.pack(fill="x", pady=4)

        ttk.Label(rowa, text="Start:").pack(side="left")
        self.e_start = ttk.Entry(rowa, width=8)
        self.e_start.pack(side="left", padx=2)

        ttk.Label(rowa, text="End:").pack(side="left", padx=(10, 0))
        self.e_end = ttk.Entry(rowa, width=8)
        self.e_end.pack(side="left", padx=2)

        self.lbl_param = ttk.Label(rowa, text="Step:")
        self.lbl_param.pack(side="left", padx=(10, 0))
        self.e_param = ttk.Entry(rowa, width=8)
        self.e_param.pack(side="left", padx=2)

        ttk.Label(rowa, text="Base Tag:").pack(side="left", padx=(15, 0))
        self.e_tagbase = ttk.Entry(rowa, width=8)
        self.e_tagbase.pack(side="left", padx=2)
        self.e_tagbase.insert(0, "V")

        ttk.Button(auto, text="Generate and Replace",
                   command=self._generate_values).pack(anchor="e", padx=5, pady=2)

    def _populate_initial_rows(self):
        n = max(len(self.tags_list), len(self.vals_list), 1)
        # Pad lists
        t_list = self.tags_list + [""] * (n - len(self.tags_list))
        v_list = self.vals_list + [""] * (n - len(self.vals_list))

        for t, v in zip(t_list, v_list):
            self._add_row_ui(t, v)

    def _add_row_ui(self, t="", v=""):
        r = len(self.rows) + 1
        e1 = ttk.Entry(self.scroll_frame, width=25)
        e1.insert(0, str(t))
        e2 = ttk.Entry(self.scroll_frame, width=55)
        e2.insert(0, str(v))

        e1.grid(row=r, column=0, sticky="we", pady=2, padx=5)
        e2.grid(row=r, column=1, sticky="we", pady=2, padx=5)
        self.rows.append((e1, e2))

        # Force update scroll if needed
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _remove_last_row(self):
        if not self.rows:
            return
        e1, e2 = self.rows.pop()
        e1.destroy()
        e2.destroy()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _clear_rows(self):
        while self.rows:
            self._remove_last_row()

    def _pick_files(self):
        files = filedialog.askopenfilenames(title=f"Select files", parent=self)
        if not files:
            return
        self._clear_rows()
        for f in files:
            f_path = Path(f)
            self._add_row_ui(f_path.stem, f_path.as_posix())

    def _update_gen_labels(self):
        self.lbl_param.config(
            text="Step:" if self.gen_mode.get() == "STEP" else "N Points:")

    def _generate_values(self):
        try:
            s = float(self.e_start.get())
            e = float(self.e_end.get())
            p = float(self.e_param.get())
        except ValueError:
            messagebox.showerror(
                "Error", "Please fill Start, End and Step/N with numbers.", parent=self)
            return

        vals = generate_sequence(s, e, p, self.gen_mode.get())
        tag_base = self.e_tagbase.get()

        self._clear_rows()
        for i, v in enumerate(vals, 1):
            self._add_row_ui(f"{tag_base}{i}", format_number(v))

    def _on_ok(self):
        tags_out = []
        vals_out = []

        for e1, e2 in self.rows:
            t_val = e1.get().strip()
            v_val = e2.get().strip()
            if not t_val and not v_val:
                continue

            tags_out.append(t_val)
            # Try to store as number if possible
            try:
                num = ast.literal_eval(v_val)
                vals_out.append(num)
            except (ValueError, SyntaxError):
                vals_out.append(v_val)

        if not tags_out:
            messagebox.showwarning(
                "Warning", "The list cannot be empty.", parent=self)
            return

        if len(tags_out) != len(vals_out):
            messagebox.showwarning(
                "Error", "Tags and Values must have the same length.", parent=self)
            return

        new_name = self.e_var.get().strip()
        if not new_name:
            messagebox.showwarning(
                "Error", "Variable name is required.", parent=self)
            return

        # Trigger the callback
        self.on_save(new_name, tags_out, vals_out)
        self.destroy()
