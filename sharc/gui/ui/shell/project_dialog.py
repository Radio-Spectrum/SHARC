"""Project manager: the recent projects (name, system, topology, modified), open / new / browse / remove, and the notes
of the current project."""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core import project_file
from core.project_file import EXTENSION, ProjectError

COLUMNS = ["Name", "System", "Topology", "Modified", "Path"]


class ProjectDialog(QDialog):
    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.win = window
        self.service = window.projects
        self.setWindowTitle("Project Manager")
        self.resize(900, 520)
        root = QVBoxLayout(self)

        cur = QGroupBox("Current project")
        cl = QVBoxLayout(cur)
        row = QHBoxLayout()
        row.addWidget(QLabel("Name"))
        self.name = QLineEdit(self.service.name)
        row.addWidget(self.name, 1)
        self.lbl_file = QLabel(self.service.path or "Not saved yet")
        self.lbl_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.lbl_file, 2)
        cl.addLayout(row)
        cl.addWidget(QLabel("Notes"))
        self.notes = QPlainTextEdit(self.service.notes)
        self.notes.setMaximumHeight(90)
        cl.addWidget(self.notes)
        bar = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._save)
        self.btn_save_as = QPushButton("Save as...")
        self.btn_save_as.clicked.connect(self._save_as)
        self.btn_new = QPushButton("New project")
        self.btn_new.clicked.connect(self._new)
        for b in (self.btn_save, self.btn_save_as, self.btn_new):
            bar.addWidget(b)
        bar.addStretch(1)
        cl.addLayout(bar)
        root.addWidget(cur)

        root.addWidget(QLabel("Recent projects (double-click to open)"))
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda *_: self._open_selected())
        root.addWidget(self.table, 1)

        bar = QHBoxLayout()
        self.btn_open = QPushButton("Open")
        self.btn_open.clicked.connect(self._open_selected)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse)
        self.btn_remove = QPushButton("Remove from list")
        self.btn_remove.clicked.connect(self._remove)
        self.btn_folder = QPushButton("Show in folder")
        self.btn_folder.clicked.connect(self._show_folder)
        for b in (self.btn_open, self.btn_browse, self.btn_remove, self.btn_folder):
            bar.addWidget(b)
        bar.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bar.addWidget(close)
        root.addLayout(bar)
        self.refresh()

    # ----------------------------------------------------------------- list
    def refresh(self) -> None:
        items = self.service.recent()
        self.table.setRowCount(len(items))
        for r, item in enumerate(items):
            path = item["path"]
            try:
                m = project_file.read_manifest(path)
                s = m.get("summary") or {}
                cells = [m.get("name", item.get("name", "")), s.get("system", ""), s.get("topology", ""),
                         str(m.get("modified", "")).replace("T", " ").rstrip("Z"), path]
            except ProjectError as exc:
                cells = [item.get("name", ""), "", "", f"unavailable: {exc}", path]
            for c, text in enumerate(cells):
                cell = QTableWidgetItem(str(text))
                cell.setData(Qt.UserRole, path)
                self.table.setItem(r, c, cell)
        self.table.resizeColumnsToContents()

    def _selected(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.UserRole) if item is not None else None

    # --------------------------------------------------------------- actions
    def _apply_fields(self) -> None:
        self.service.name = self.name.text().strip() or "Untitled"
        self.service.notes = self.notes.toPlainText()

    def _save(self) -> None:
        self._apply_fields()
        self.win.save_project()
        self._sync()

    def _save_as(self) -> None:
        self._apply_fields()
        self.win.save_project_as()
        self._sync()

    def _new(self) -> None:
        if self.win.new_project():
            self._sync()

    def _open_selected(self) -> None:
        path = self._selected()
        if path and self.win.open_project(path):
            self._sync()
            self.accept()

    def _browse(self) -> None:
        if self.win.open_project_dialog():
            self.accept()

    def _remove(self) -> None:
        path = self._selected()
        if path:
            self.service.forget(path)
            self.refresh()

    def _show_folder(self) -> None:
        path = self._selected()
        if not path or not os.path.exists(path):
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def _sync(self) -> None:
        self.name.setText(self.service.name)
        self.notes.setPlainText(self.service.notes)
        self.lbl_file.setText(self.service.path or "Not saved yet")
        self.refresh()
