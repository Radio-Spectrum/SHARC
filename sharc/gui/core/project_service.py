"""The current project of the GUI: new, open, save, recent list and unsaved-changes detection.

State lives in a `.sharc` file (see `project_file`); the recent list lives in the GUI settings. "Unsaved changes" compares a
fingerprint of everything the project would save with the one taken at the last open / save.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional

from core import project_file, project_state
from core.project_file import EXTENSION, ProjectError

MAX_RECENT = 12
RECENT_KEY = "projects/recent"
UNTITLED = "Untitled"


def _default_settings():
    from PySide6.QtCore import QSettings
    return QSettings("SHARC", "GUI")


class ProjectService:
    def __init__(self, app, settings_factory: Callable[[], Any] = _default_settings):
        self.app = app
        self._settings = settings_factory
        self.path: Optional[str] = None
        self.name = UNTITLED
        self.notes = ""
        self.created: Optional[str] = None
        self._saved_fingerprint = ""
        self._defaults: Optional[Dict[str, Any]] = None
        self._contour_defaults: Optional[Dict[str, Any]] = None

    # ---------------------------------------------------------------- state
    def snapshot_defaults(self) -> None:
        """Remember the values the GUI starts with: "New Project" goes back to them."""
        self._defaults = project_state.capture(self.app)
        contour = getattr(self.app, "tab_contour", None)
        self._contour_defaults = project_state.widget_values(contour.w) if contour is not None else None
        self._saved_fingerprint = self.fingerprint()

    def fingerprint(self) -> str:
        """Hash of everything a save would write (scenario, GUI state, contour page, notes, name)."""
        contour = getattr(self.app, "tab_contour", None)
        data = {"state": project_state.capture(self.app), "notes": self.notes, "name": self.name,
                "contour": project_state.widget_values(contour.w) if contour is not None else None,
                "rows": len(getattr(contour, "rows", []) or [])}
        return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def is_dirty(self) -> bool:
        return self.fingerprint() != self._saved_fingerprint

    def title(self) -> str:
        return f"{self.name}{'*' if self.is_dirty() else ''}"

    # ---------------------------------------------------------------- actions
    def new_project(self) -> None:
        """Back to the starting values, with no file."""
        if self._defaults is not None:
            project_state.apply(self.app, self._defaults)
        contour = getattr(self.app, "tab_contour", None)
        if contour is not None:
            contour.rows = []
            if self._contour_defaults:
                project_state.apply_widget_values(contour.w, self._contour_defaults)
            contour._show([])
            contour._set_buttons(False)
        self.path, self.name, self.notes, self.created = None, UNTITLED, "", None
        self._saved_fingerprint = self.fingerprint()

    def save(self, path: Optional[str] = None) -> str:
        """Save to `path` (or to the current file). Raises ProjectError when there is no path or the write fails."""
        target = path or self.path
        if not target:
            raise ProjectError("This project has no file yet: use Save Project As.")
        if not target.lower().endswith(EXTENSION):
            target += EXTENSION
        if path and path != self.path and self.name == UNTITLED:
            self.name = os.path.splitext(os.path.basename(target))[0]
        project = project_state.build_project(self.app, self.name, self.notes, self.created)
        saved = project_file.save(target, project)
        self.path, self.created = saved, project.created
        self._saved_fingerprint = self.fingerprint()
        self._remember(saved, self.name)
        return saved

    def open(self, path: str) -> Dict[str, Any]:
        """Open a project: returns the report of `project_state.apply_project` (what was applied / skipped)."""
        project = project_file.load(path)
        report = project_state.apply_project(self.app, project)
        self.path, self.name, self.notes, self.created = path, project.name, project.notes, project.created
        self._saved_fingerprint = self.fingerprint()
        self._remember(path, project.name)
        return report

    # ---------------------------------------------------------------- recent
    def recent(self) -> List[Dict[str, Any]]:
        raw = self._settings().value(RECENT_KEY, "[]")
        try:
            items = json.loads(raw) if isinstance(raw, str) else list(raw)
        except (ValueError, TypeError):
            return []
        return [i for i in items if isinstance(i, dict) and i.get("path")]

    def _store(self, items: List[Dict[str, Any]]) -> None:
        self._settings().setValue(RECENT_KEY, json.dumps(items[:MAX_RECENT]))

    def _remember(self, path: str, name: str) -> None:
        path = os.path.abspath(path)
        items = [i for i in self.recent() if os.path.normcase(i["path"]) != os.path.normcase(path)]
        items.insert(0, {"path": path, "name": name})
        self._store(items)

    def forget(self, path: str) -> None:
        self._store([i for i in self.recent() if os.path.normcase(i["path"]) != os.path.normcase(os.path.abspath(path))])
