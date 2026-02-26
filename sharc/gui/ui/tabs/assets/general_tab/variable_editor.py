import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from pathlib import Path
import ast
import csv
import os

# Ajuste os imports conforme a estrutura do seu projeto
from ui.tabs.assets.general_tab.general_tools import parse_list_safe, generate_sequence, format_number


class VariableEditor(tk.Toplevel):
    """
    A dialog window to edit Tag <-> Value mappings.
    Features:
    - Toggle between 'Logical Value' and 'File Path' modes.
    - Hides Numeric Generator when in File Mode.
    - Real-time validation.
    - CSV Import/Export.
    """

    def __init__(self, parent, var_key, tags_raw, vals_raw, on_save_callback):
        super().__init__(parent)
        self.title(f"Edit Variable: {var_key}")
        self.geometry("800x650")
        self.transient(parent)

        self.on_save = on_save_callback
        self.rows = []  # Stores (Entry_Tag, Entry_Value, Button_Browse) tuples

        # Initial Data
        self.tags_list = parse_list_safe(tags_raw, [])
        self.vals_list = parse_list_safe(vals_raw, [])

        # Detect initial mode
        initial_mode = "VALUE"
        for v in self.vals_list:
            if isinstance(v, str) and ("/" in v or "\\" in v):
                initial_mode = "FILE"
                break

        self.var_mode = tk.StringVar(value=initial_mode)  # "VALUE" or "FILE"

        # UI Components placeholders
        self.frm_auto = None
        self.btns_frame = None

        self._build_ui(var_key)
        self._populate_initial_rows()

        # Apply initial visibility and validation
        self._toggle_mode_ui()

    def _build_ui(self, var_key):
        # --- Header ---
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))

        # Row 1: Name
        r1 = ttk.Frame(top)
        r1.pack(fill="x")
        ttk.Label(r1, text="Variable Name:").pack(side="left")
        self.e_var = ttk.Entry(r1, width=24)
        self.e_var.insert(0, str(var_key))
        self.e_var.pack(side="left", padx=(6, 0))
        ttk.Label(r1, text="(use {name} in paths)",
                  foreground="gray").pack(side="left", padx=10)

        # Row 2: Type Selection (Mode)
        r2 = ttk.Labelframe(top, text="Variable Type / Validation Mode")
        r2.pack(fill="x", pady=(10, 0))

        ttk.Radiobutton(r2, text="Logical Value (Numeric Check)", variable=self.var_mode,
                        value="VALUE", command=self._toggle_mode_ui).pack(side="left", padx=10, pady=5)

        ttk.Radiobutton(r2, text="File Path (Existence Check)", variable=self.var_mode,
                        value="FILE", command=self._toggle_mode_ui).pack(side="left", padx=10, pady=5)

        # --- Scrollable List Area ---
        frm_list = ttk.Labelframe(self, text="Mapping (Tag -> Value)")
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
        self.canvas = canvas

        # Column Headers
        self.lbl_col_tag = ttk.Label(self.scroll_frame, text="Tag (Key)")
        self.lbl_col_tag.grid(row=0, column=0, sticky="w", padx=5)

        self.lbl_col_val = ttk.Label(self.scroll_frame, text="Value")
        self.lbl_col_val.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(self.scroll_frame, text="").grid(
            row=0, column=2, sticky="w", padx=0)

        # --- Action Buttons ---
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=10, pady=(0, 6))

        # Left side: Manipulation
        ttk.Button(actions, text="+ Add Row",
                   command=lambda: self._add_row_ui("", "")).pack(side="left")
        ttk.Button(actions, text="- Remove Last",
                   command=self._remove_last_row).pack(side="left", padx=5)

        ttk.Separator(actions, orient="vertical").pack(
            side="left", fill="y", padx=10)

        # Middle: Files & CSV
        self.btn_bulk = ttk.Button(
            actions, text="Import Files...", command=self._pick_files_bulk)
        self.btn_bulk.pack(side="left", padx=2)

        ttk.Button(actions, text="Import CSV",
                   command=self._import_csv).pack(side="left", padx=2)
        ttk.Button(actions, text="Export CSV",
                   command=self._export_csv).pack(side="left", padx=2)

        # --- Auto-Generation Section (Built but visibility controlled later) ---
        self._build_auto_gen_ui()

        # --- Bottom Buttons (Saved to reference for ordering) ---
        self.btns_frame = ttk.Frame(self)
        self.btns_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(self.btns_frame, text="OK",
                   command=self._on_ok).pack(side="left")
        ttk.Button(self.btns_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=10)

        # Legend for validation
        ttk.Label(self.btns_frame, text="* Red text indicates invalid value/path",
                  foreground="red", font=("Arial", 8)).pack(side="right")

    def _build_auto_gen_ui(self):
        """Constructs the Auto-Generation frame."""
        self.frm_auto = ttk.Labelframe(
            self, text="Generate Values Automatically (Numeric)")
        # We don't pack it here immediately to avoid order issues,
        # it will be packed in _toggle_mode_ui

        self.gen_mode = tk.StringVar(value="STEP")

        rowm = ttk.Frame(self.frm_auto)
        rowm.pack(fill="x", pady=2)
        ttk.Radiobutton(rowm, text="Start/End/Step", variable=self.gen_mode,
                        value="STEP", command=self._update_gen_labels).pack(side="left")
        ttk.Radiobutton(rowm, text="Start/End/N Points", variable=self.gen_mode,
                        value="NPTS", command=self._update_gen_labels).pack(side="left", padx=15)

        rowa = ttk.Frame(self.frm_auto)
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

        ttk.Button(self.frm_auto, text="Generate and Replace",
                   command=self._generate_values).pack(anchor="e", padx=5, pady=2)

    # --- UI Logic Methods ---

    def _toggle_mode_ui(self):
        """Updates the UI, re-validates rows, and Hides/Shows generator based on mode."""
        mode = self.var_mode.get()

        # 1. Update Headers & Validation
        if mode == "FILE":
            self.lbl_col_val.config(text="File Path (Must exist)")
            # Hide the numeric generator
            self.frm_auto.pack_forget()
        else:
            self.lbl_col_val.config(text="Value (Numeric)")
            # Show the numeric generator (before the buttons)
            self.frm_auto.pack(fill="x", padx=10, pady=(
                6, 0), before=self.btns_frame)

        # 2. Update Rows visibility
        for _, e_val, btn_browse in self.rows:
            if mode == "FILE":
                btn_browse.grid()
            else:
                btn_browse.grid_remove()

            # Re-validate current value with new mode
            self._validate_entry(e_val)

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _add_row_ui(self, t="", v=""):
        r = len(self.rows) + 1

        e1 = ttk.Entry(self.scroll_frame, width=20)
        e1.insert(0, str(t))

        e2 = ttk.Entry(self.scroll_frame, width=55)
        e2.insert(0, str(v))

        # Bind validation event (KeyRelease triggers on every keystroke)
        e2.bind('<KeyRelease>', lambda event,
                entry=e2: self._validate_entry(entry))

        # Browse Button
        btn_browse = ttk.Button(self.scroll_frame, text="...", width=3,
                                command=lambda entry=e2: self._browse_single_file(entry))

        # Grid Layout
        e1.grid(row=r, column=0, sticky="we", pady=2, padx=5)
        e2.grid(row=r, column=1, sticky="we", pady=2, padx=5)
        btn_browse.grid(row=r, column=2, sticky="w", pady=2, padx=(0, 5))

        # Initial validation state
        if self.var_mode.get() != "FILE":
            btn_browse.grid_remove()

        self.rows.append((e1, e2, btn_browse))
        self._validate_entry(e2)  # Validate initial value

        # Force update scroll
        self.scroll_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # --- Validation Logic ---
    def _validate_entry(self, entry_widget):
        """Checks if value is valid based on mode. Changes text color."""
        val = entry_widget.get().strip()
        mode = self.var_mode.get()
        is_valid = True

        if not val:
            entry_widget.config(foreground="black")
            return

        if mode == "VALUE":
            try:
                float(val)
                is_valid = True
            except ValueError:
                is_valid = False

        elif mode == "FILE":
            # Allow placeholders like {var} or check file existence
            if "{" in val and "}" in val:
                is_valid = True
            else:
                # Check path (removing quotes if user pasted them)
                clean_path = val.strip('"').strip("'")
                is_valid = os.path.exists(clean_path)

        color = "black" if is_valid else "red"
        entry_widget.config(foreground=color)

    # --- CSV Import / Export ---
    # (Existing CSV methods unchanged - kept for brevity unless requested)
    def _export_csv(self):
        f_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export to CSV", parent=self
        )
        if not f_path:
            return
        try:
            with open(f_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Tag", "Value"])
                for e1, e2, _ in self.rows:
                    if e1.get().strip() or e2.get().strip():
                        writer.writerow([e1.get().strip(), e2.get().strip()])
            messagebox.showinfo(
                "Success", "CSV exported successfully.", parent=self)
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to export CSV:\n{e}", parent=self)

    def _import_csv(self):
        f_path = filedialog.askopenfilename(
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Import CSV", parent=self
        )
        if not f_path:
            return
        if messagebox.askyesno("Confirm", "Replace current rows?", parent=self):
            try:
                with open(f_path, mode='r', newline='', encoding='utf-8') as f:
                    data = list(csv.reader(
                        f, csv.Sniffer().sniff(f.read(1024))))
                    f.seek(0)
                self._clear_rows()
                for row in data:
                    if len(row) >= 2:
                        self._add_row_ui(row[0], row[1])
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to import:\n{e}", parent=self)

    # --- File Picking Logic (UPDATED) ---

    def _browse_single_file(self, entry_widget):
        f = filedialog.askopenfilename(title="Select File", parent=self)
        if f:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, f)
            self._validate_entry(entry_widget)

    def _pick_files_bulk(self):
        """
        Allows selecting multiple parameter files (JSON/YAML) or standard files.
        Auto-populates Tag with filename and Value with path.
        """
        # Improved filters to find presets easily
        file_types = [
            ("Parameter Files", "*.json *.yaml *.yml"),
            ("JSON Configuration", "*.json"),
            ("YAML Configuration", "*.yaml *.yml"),
            ("All Files", "*.*")
        ]

        files = filedialog.askopenfilenames(
            title="Select Parameter Files",
            filetypes=file_types,
            parent=self
        )
        if not files:
            return

        # 1. Force FILE mode
        self.var_mode.set("FILE")
        self._toggle_mode_ui()

        # 2. Clear existing (optional, usually better for bulk import)
        if not self.rows:
            self._clear_rows()

        # 3. Populate
        for f in files:
            f_path = Path(f)
            # Tag = filename without extension (e.g., 'imt_urban')
            tag_name = f_path.stem
            # Value = Absolute path
            val_path = f_path.as_posix()

            self._add_row_ui(tag_name, val_path)

    def _remove_last_row(self):
        if not self.rows:
            return
        e1, e2, btn = self.rows.pop()
        e1.destroy()
        e2.destroy()
        btn.destroy()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _clear_rows(self):
        while self.rows:
            self._remove_last_row()

    def _populate_initial_rows(self):
        n = max(len(self.tags_list), len(self.vals_list), 1)
        t_list = self.tags_list + [""] * (n - len(self.tags_list))
        v_list = self.vals_list + [""] * (n - len(self.vals_list))
        for t, v in zip(t_list, v_list):
            self._add_row_ui(t, v)

    # --- Auto Gen Logic ---

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

        self.var_mode.set("VALUE")
        self._toggle_mode_ui()

        self._clear_rows()
        for i, v in enumerate(vals, 1):
            self._add_row_ui(f"{tag_base}{i}", format_number(v))

    def _on_ok(self):
        tags_out = []
        vals_out = []
        is_file_mode = (self.var_mode.get() == "FILE")
        has_invalid = False

        for e1, e2, _ in self.rows:
            t_val = e1.get().strip()
            v_val = e2.get().strip()
            if not t_val and not v_val:
                continue

            if e2.cget("foreground") == "red":
                has_invalid = True

            tags_out.append(t_val)
            if is_file_mode:
                vals_out.append(v_val)
            else:
                try:
                    num = ast.literal_eval(v_val)
                    vals_out.append(num)
                except (ValueError, SyntaxError):
                    vals_out.append(v_val)

        if has_invalid:
            if not messagebox.askyesno("Warning", "Some values appear invalid (red). Save anyway?", parent=self):
                return

        if not tags_out:
            messagebox.showwarning(
                "Warning", "List cannot be empty.", parent=self)
            return

        new_name = self.e_var.get().strip()
        if not new_name:
            messagebox.showwarning(
                "Error", "Variable name is required.", parent=self)
            return

        self.on_save(new_name, tags_out, vals_out)
        self.destroy()
