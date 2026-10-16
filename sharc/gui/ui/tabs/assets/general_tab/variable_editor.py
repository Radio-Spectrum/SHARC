import os
import ast
import csv
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QLineEdit, QPushButton, QRadioButton, QScrollArea, 
    QWidget, QFileDialog, QMessageBox, QButtonGroup, QFrame
)
from PySide6.QtCore import Qt, Slot

# Ajuste os imports conforme a estrutura do seu projeto
from ui.tabs.assets.general_tab.general_tools import parse_list_safe, generate_sequence, format_number


class VariableEditor(QDialog):
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
        self.setWindowTitle(f"Edit Variable: {var_key}")
        self.resize(800, 650)
        self.setModal(True)

        self.on_save = on_save_callback
        self.rows = []  # Stores (QLineEdit_Tag, QLineEdit_Value, QPushButton_Browse) tuples

        # Initial Data
        self.tags_list = parse_list_safe(tags_raw, [])
        self.vals_list = parse_list_safe(vals_raw, [])

        # Detect initial mode
        initial_mode = "VALUE"
        for v in self.vals_list:
            if isinstance(v, str) and ("/" in v or "\\" in v):
                initial_mode = "FILE"
                break

        self._build_ui(var_key, initial_mode)
        self._populate_initial_rows()
        self._toggle_mode_ui()

    def _build_ui(self, var_key, initial_mode):
        main_layout = QVBoxLayout(self)

        # --- Header ---
        top_frame = QWidget()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Row 1: Name
        r1_layout = QHBoxLayout()
        r1_layout.addWidget(QLabel("Variable Name:"))
        self.e_var = QLineEdit(str(var_key))
        r1_layout.addWidget(self.e_var)
        lbl_hint = QLabel("(use {name} in paths)")
        lbl_hint.setStyleSheet("color: gray;")
        r1_layout.addWidget(lbl_hint)
        r1_layout.addStretch()
        top_layout.addLayout(r1_layout)

        # Row 2: Type Selection (Mode)
        r2_group = QGroupBox("Variable Type / Validation Mode")
        r2_layout = QHBoxLayout(r2_group)
        
        self.mode_group = QButtonGroup(self)
        self.rb_value = QRadioButton("Logical Value (Numeric Check)")
        self.rb_file = QRadioButton("File Path (Existence Check)")
        
        self.mode_group.addButton(self.rb_value, 0)
        self.mode_group.addButton(self.rb_file, 1)
        
        if initial_mode == "FILE":
            self.rb_file.setChecked(True)
        else:
            self.rb_value.setChecked(True)
            
        self.mode_group.buttonClicked.connect(self._toggle_mode_ui)
        
        r2_layout.addWidget(self.rb_value)
        r2_layout.addWidget(self.rb_file)
        r2_layout.addStretch()
        top_layout.addWidget(r2_group)

        main_layout.addWidget(top_frame)

        # --- Scrollable List Area ---
        list_group = QGroupBox("Mapping (Tag -> Value)")
        list_layout = QVBoxLayout(list_group)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        # Headers
        self.lbl_col_tag = QLabel("Tag (Key)")
        self.lbl_col_val = QLabel("Value")
        self.scroll_layout.addWidget(self.lbl_col_tag, 0, 0)
        self.scroll_layout.addWidget(self.lbl_col_val, 0, 1)
        
        self.scroll_area.setWidget(self.scroll_widget)
        list_layout.addWidget(self.scroll_area)
        
        main_layout.addWidget(list_group, 1) # Expandible

        # --- Action Buttons ---
        actions_layout = QHBoxLayout()
        
        btn_add = QPushButton("+ Add Row")
        btn_add.clicked.connect(lambda: self._add_row_ui("", ""))
        btn_remove = QPushButton("- Remove Last")
        btn_remove.clicked.connect(self._remove_last_row)
        
        actions_layout.addWidget(btn_add)
        actions_layout.addWidget(btn_remove)
        
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        actions_layout.addWidget(line)
        
        btn_bulk = QPushButton("Import Files...")
        btn_bulk.clicked.connect(self._pick_files_bulk)
        btn_import = QPushButton("Import CSV")
        btn_import.clicked.connect(self._import_csv)
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self._export_csv)
        
        actions_layout.addWidget(btn_bulk)
        actions_layout.addWidget(btn_import)
        actions_layout.addWidget(btn_export)
        actions_layout.addStretch()
        
        main_layout.addLayout(actions_layout)

        # --- Auto-Generation Section ---
        self._build_auto_gen_ui(main_layout)

        # --- Bottom Buttons ---
        btns_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        lbl_legend = QLabel("* Red text indicates invalid value/path")
        lbl_legend.setStyleSheet("color: red; font-size: 11px;")
        
        btns_layout.addWidget(btn_ok)
        btns_layout.addWidget(btn_cancel)
        btns_layout.addStretch()
        btns_layout.addWidget(lbl_legend)
        
        main_layout.addLayout(btns_layout)

    def _build_auto_gen_ui(self, main_layout):
        self.frm_auto = QGroupBox("Generate Values Automatically (Numeric)")
        auto_layout = QVBoxLayout(self.frm_auto)
        
        row_mode = QHBoxLayout()
        self.gen_group = QButtonGroup(self)
        self.rb_step = QRadioButton("Start/End/Step")
        self.rb_npts = QRadioButton("Start/End/N Points")
        self.rb_step.setChecked(True)
        self.gen_group.addButton(self.rb_step, 0)
        self.gen_group.addButton(self.rb_npts, 1)
        self.gen_group.buttonClicked.connect(self._update_gen_labels)
        
        row_mode.addWidget(self.rb_step)
        row_mode.addWidget(self.rb_npts)
        row_mode.addStretch()
        auto_layout.addLayout(row_mode)
        
        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Start:"))
        self.e_start = QLineEdit()
        self.e_start.setFixedWidth(80)
        row_params.addWidget(self.e_start)
        
        row_params.addWidget(QLabel("End:"))
        self.e_end = QLineEdit()
        self.e_end.setFixedWidth(80)
        row_params.addWidget(self.e_end)
        
        self.lbl_param = QLabel("Step:")
        row_params.addWidget(self.lbl_param)
        self.e_param = QLineEdit()
        self.e_param.setFixedWidth(80)
        row_params.addWidget(self.e_param)
        
        row_params.addWidget(QLabel("Base Tag:"))
        self.e_tagbase = QLineEdit("V")
        self.e_tagbase.setFixedWidth(80)
        row_params.addWidget(self.e_tagbase)
        
        row_params.addStretch()
        btn_gen = QPushButton("Generate and Replace")
        btn_gen.clicked.connect(self._generate_values)
        row_params.addWidget(btn_gen)
        
        auto_layout.addLayout(row_params)
        main_layout.addWidget(self.frm_auto)

    @Slot()
    def _toggle_mode_ui(self):
        is_file = self.rb_file.isChecked()
        
        if is_file:
            self.lbl_col_val.setText("File Path (Must exist)")
            self.frm_auto.hide()
        else:
            self.lbl_col_val.setText("Value (Numeric)")
            self.frm_auto.show()

        for _, e_val, btn_browse in self.rows:
            btn_browse.setVisible(is_file)
            self._validate_entry(e_val)

    def _add_row_ui(self, t="", v=""):
        row_idx = len(self.rows) + 1 # +1 accounts for header

        e1 = QLineEdit(str(t))
        e2 = QLineEdit(str(v))
        
        e2.textChanged.connect(lambda text, entry=e2: self._validate_entry(entry))
        
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(lambda _, entry=e2: self._browse_single_file(entry))
        
        self.scroll_layout.addWidget(e1, row_idx, 0)
        self.scroll_layout.addWidget(e2, row_idx, 1)
        self.scroll_layout.addWidget(btn_browse, row_idx, 2)
        
        btn_browse.setVisible(self.rb_file.isChecked())
        
        self.rows.append((e1, e2, btn_browse))
        self._validate_entry(e2)

    def _validate_entry(self, entry_widget):
        val = entry_widget.text().strip()
        is_file = self.rb_file.isChecked()
        is_valid = True

        if not val:
            entry_widget.setStyleSheet("")
            return

        if not is_file:
            try:
                float(val)
            except ValueError:
                is_valid = False
        else:
            if "{" not in val or "}" not in val:
                clean_path = val.strip('"').strip("'")
                is_valid = os.path.exists(clean_path)

        color = "" if is_valid else "color: red;"
        entry_widget.setStyleSheet(color)

    def _browse_single_file(self, entry_widget):
        f, _ = QFileDialog.getOpenFileName(self, "Select File")
        if f:
            entry_widget.setText(f)
            self._validate_entry(entry_widget)

    def _pick_files_bulk(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Parameter Files", "", 
            "Parameter Files (*.json *.yaml *.yml);;All Files (*.*)"
        )
        if not files:
            return

        self.rb_file.setChecked(True)
        self._toggle_mode_ui()
        self._clear_rows()

        for f in files:
            f_path = Path(f)
            self._add_row_ui(f_path.stem, f_path.as_posix())

    def _remove_last_row(self):
        if not self.rows:
            return
        e1, e2, btn = self.rows.pop()
        self.scroll_layout.removeWidget(e1)
        self.scroll_layout.removeWidget(e2)
        self.scroll_layout.removeWidget(btn)
        e1.deleteLater()
        e2.deleteLater()
        btn.deleteLater()

    def _clear_rows(self):
        while self.rows:
            self._remove_last_row()

    def _populate_initial_rows(self):
        n = max(len(self.tags_list), len(self.vals_list), 1)
        t_list = self.tags_list + [""] * (n - len(self.tags_list))
        v_list = self.vals_list + [""] * (n - len(self.vals_list))
        for t, v in zip(t_list, v_list):
            self._add_row_ui(t, v)

    @Slot()
    def _update_gen_labels(self):
        self.lbl_param.setText("Step:" if self.rb_step.isChecked() else "N Points:")

    def _generate_values(self):
        try:
            s = float(self.e_start.text())
            e = float(self.e_end.text())
            p = float(self.e_param.text())
        except ValueError:
            QMessageBox.critical(self, "Error", "Please fill Start, End and Step/N with numbers.")
            return

        mode = "STEP" if self.rb_step.isChecked() else "NPTS"
        vals = generate_sequence(s, e, p, mode)
        tag_base = self.e_tagbase.text()

        self.rb_value.setChecked(True)
        self._toggle_mode_ui()
        self._clear_rows()
        for i, v in enumerate(vals, 1):
            self._add_row_ui(f"{tag_base}{i}", format_number(v))

    def _export_csv(self):
        f_path, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv);;All Files (*.*)")
        if not f_path:
            return
        try:
            with open(f_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Tag", "Value"])
                for e1, e2, _ in self.rows:
                    if e1.text().strip() or e2.text().strip():
                        writer.writerow([e1.text().strip(), e2.text().strip()])
            QMessageBox.information(self, "Success", "CSV exported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV:\n{e}")

    def _import_csv(self):
        f_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv);;All Files (*.*)")
        if not f_path:
            return
        if QMessageBox.question(self, "Confirm", "Replace current rows?") == QMessageBox.Yes:
            try:
                with open(f_path, mode='r', newline='', encoding='utf-8') as f:
                    data = list(csv.reader(f, csv.Sniffer().sniff(f.read(1024))))
                self._clear_rows()
                for row in data:
                    if len(row) >= 2:
                        self._add_row_ui(row[0], row[1])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import:\n{e}")

    def _on_ok(self):
        tags_out = []
        vals_out = []
        is_file_mode = self.rb_file.isChecked()
        has_invalid = False

        for e1, e2, _ in self.rows:
            t_val = e1.text().strip()
            v_val = e2.text().strip()
            if not t_val and not v_val:
                continue

            if "color: red" in e2.styleSheet():
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
            if QMessageBox.question(self, "Warning", "Some values appear invalid (red). Save anyway?") != QMessageBox.Yes:
                return

        if not tags_out:
            QMessageBox.warning(self, "Warning", "List cannot be empty.")
            return

        new_name = self.e_var.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Variable name is required.")
            return

        self.on_save(new_name, tags_out, vals_out)
        self.accept()