from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
    QLabel, QLineEdit, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt

class IMTUIHelper:
    """Helper class for standardized grid/form layouts in the IMT tab (PySide6)."""

    @staticmethod
    def bind_var(widget, sharc_var):
        """Conecta um SharcVar a um QWidget bidirecionalmente."""
        if isinstance(widget, QLineEdit):
            sharc_var.value_changed.connect(lambda v: widget.setText(str(v)))
            widget.textChanged.connect(lambda t: sharc_var.set(t))
            widget.setText(str(sharc_var.get()))
        
        elif isinstance(widget, QComboBox):
            widget.setEditable(True)
            sharc_var.value_changed.connect(lambda v: widget.setCurrentText(str(v)))
            widget.currentTextChanged.connect(lambda t: sharc_var.set(t))
            widget.setCurrentText(str(sharc_var.get()))
            
        elif isinstance(widget, QCheckBox):
            sharc_var.value_changed.connect(lambda v: widget.setChecked(str(v).lower() in ("true", "1")))
            widget.toggled.connect(lambda c: sharc_var.set(c))
            widget.setChecked(str(sharc_var.get()).lower() in ("true", "1"))

    @staticmethod
    def create_field(sharc_var, widget_type=QLineEdit, values=None):
        """Cria o widget, preenche valores (se combo) e faz o binding automático."""
        w = widget_type()
        if values and widget_type == QComboBox:
            w.addItems([str(v) for v in values])
        IMTUIHelper.bind_var(w, sharc_var)
        return w

    @staticmethod
    def add_grid_row(layout, row_idx, items):
        """Imita o antigo add_row_three, mas nativo para QGridLayout."""
        col = 0
        for label_text, widget in items:
            if label_text:
                layout.addWidget(QLabel(label_text), row_idx, col)
            if widget:
                layout.addWidget(widget, row_idx, col + 1)
            col += 2

    @staticmethod
    def create_sub_column(parent_layout, title):
        """Cria um QGroupBox com um QFormLayout interno limpo."""
        group = QGroupBox(title)
        layout = QFormLayout(group)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        parent_layout.addWidget(group)
        return layout

    @staticmethod
    def pair_entries(var1, var2, width=60):
        """Cria um composite widget para dois valores lado a lado (ex: Min/Max)."""
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        e1 = QLineEdit()
        e2 = QLineEdit()
        e1.setFixedWidth(width)
        e2.setFixedWidth(width)
        IMTUIHelper.bind_var(e1, var1)
        IMTUIHelper.bind_var(e2, var2)
        l.addWidget(e1)
        l.addWidget(QLabel(" / "))
        l.addWidget(e2)
        l.addStretch()
        return w

    @staticmethod
    def add_range(form_layout, label_text, var1, var2):
        w = IMTUIHelper.pair_entries(var1, var2)
        form_layout.addRow(label_text, w)