"""Problems dock: validation issues of the current scenario; double-click jumps to the page."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from core.validation import ERROR, Issue


class ProblemsPanel(QTableWidget):
    jump_requested = Signal(str, str)        # page key, field label

    COLUMNS = ("Severity", "Page", "Field", "Message")

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setObjectName("ProblemsPanel")
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        hdr = self.horizontalHeader()
        for col in range(3):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        self._issues: List[Issue] = []
        self.cellDoubleClicked.connect(self._on_double_click)

    def set_issues(self, issues: List[Issue]) -> None:
        # errors first, then warnings, each keeping the order the rules produced them
        self._issues = sorted(issues, key=lambda i: i.severity != ERROR)
        self.setRowCount(0)
        for issue in self._issues:
            row = self.rowCount()
            self.insertRow(row)
            for col, text in enumerate((issue.severity.capitalize(), issue.page, issue.field, issue.message)):
                item = QTableWidgetItem(text)
                item.setToolTip(issue.message)
                self.setItem(row, col, item)

    def counts(self) -> tuple:
        """(errors, warnings)"""
        errors = sum(1 for i in self._issues if i.severity == ERROR)
        return errors, len(self._issues) - errors

    def _on_double_click(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._issues):
            issue = self._issues[row]
            self.jump_requested.emit(issue.page, issue.field)
