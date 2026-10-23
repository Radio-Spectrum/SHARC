"""The `.sharc` project file: one portable file holding a whole SHARC project.

A `.sharc` is a ZIP with fixed member names (never extracted to disk: members are read by name):

    manifest.json        format, format_version, name, SHARC version, created / modified, a summary, md5 of the scenario
    scenario.yaml        the engine YAML, exactly what `main_cli` reads (`python -m sharc.main_cli -p file.yaml`)
    gui_state.json       every GUI value (all pages), the parameter-sweep table and the heat-map style
    notes.md             free text of the user (optional)
    contour/config.json  the Protection Contour page (optional)
    contour/results.csv  its results (optional)

Large data (terrain rasters, databases) is NOT embedded: `gui_state.json` keeps their paths. Projects are versioned
(`format_version`), so older files can be migrated when the format changes, and a file from a newer SHARC is refused with
a clear message instead of being half-read.

This module has no Qt and no engine imports: it is the file format only.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

FORMAT = "sharc-project"
FORMAT_VERSION = 1
EXTENSION = ".sharc"
MEMBERS = ("manifest.json", "scenario.yaml", "gui_state.json", "notes.md", "contour/config.json", "contour/results.csv")
MAX_MEMBER_BYTES = 200 * 1024 * 1024          # one member (a results CSV can be big)
MAX_TOTAL_BYTES = 400 * 1024 * 1024


class ProjectError(Exception):
    """A project file that cannot be saved or opened; the message is meant for the user."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Project:
    name: str = "Untitled"
    scenario_yaml: str = ""
    gui_state: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    contour_config: Optional[Dict[str, Any]] = None
    contour_results_csv: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)         # e.g. system, topology: shown by the project manager
    created: str = field(default_factory=_now)
    modified: str = field(default_factory=_now)
    sharc_version: str = ""
    format_version: int = FORMAT_VERSION


def _manifest(p: Project) -> Dict[str, Any]:
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "name": p.name, "sharc_version": p.sharc_version,
            "created": p.created, "modified": p.modified, "summary": p.summary,
            "scenario_md5": hashlib.md5(p.scenario_yaml.encode("utf-8")).hexdigest(),
            "has_contour": p.contour_config is not None}


def save(path: str, project: Project) -> str:
    """Write the project; the file is replaced atomically (an interrupted save never leaves a broken project)."""
    if not str(path).lower().endswith(EXTENSION):
        path = str(path) + EXTENSION
    project.modified = _now()
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(_manifest(project), indent=2, ensure_ascii=False))
        z.writestr("scenario.yaml", project.scenario_yaml)
        z.writestr("gui_state.json", json.dumps(project.gui_state, indent=1, ensure_ascii=False, default=str))
        if project.notes:
            z.writestr("notes.md", project.notes)
        if project.contour_config is not None:
            z.writestr("contour/config.json", json.dumps(project.contour_config, indent=1, ensure_ascii=False, default=str))
            z.writestr("contour/results.csv", project.contour_results_csv)
    fd, tmp = tempfile.mkstemp(prefix=".sharc_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(buffer.getvalue())
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise ProjectError(f"Could not write {path}: {exc}") from exc
    return path


def _read_zip(path: str) -> Dict[str, bytes]:
    if not os.path.isfile(path):
        raise ProjectError(f"File not found: {path}")
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ProjectError(f"{os.path.basename(path)} is not a SHARC project (not a valid archive).") from exc
    out: Dict[str, bytes] = {}
    total = 0
    with z:
        infos = {i.filename: i for i in z.infolist()}
        for name in MEMBERS:                                       # only the known names, never extracted to disk
            info = infos.get(name)
            if info is None:
                continue
            total += info.file_size
            if info.file_size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                raise ProjectError(f"{os.path.basename(path)} is too large to be a SHARC project.")
            out[name] = z.read(name)
    return out


def read_manifest(path: str) -> Dict[str, Any]:
    """Only the manifest (cheap: the project manager lists many files)."""
    members = _read_zip_manifest(path)
    return members


def _read_zip_manifest(path: str) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as z:
            raw = z.read("manifest.json")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ProjectError(f"{os.path.basename(path)} is not a SHARC project.") from exc
    return _check_manifest(raw, path)


def _check_manifest(raw: bytes, path: str) -> Dict[str, Any]:
    try:
        m = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProjectError(f"{os.path.basename(path)}: the manifest is damaged.") from exc
    if not isinstance(m, dict) or m.get("format") != FORMAT:
        raise ProjectError(f"{os.path.basename(path)} is not a SHARC project.")
    version = m.get("format_version")
    if not isinstance(version, int) or version < 1:
        raise ProjectError(f"{os.path.basename(path)}: unknown format version {version!r}.")
    if version > FORMAT_VERSION:
        raise ProjectError(f"{os.path.basename(path)} was saved by a newer SHARC (project format {version}; this one "
                           f"reads up to {FORMAT_VERSION}). Update SHARC to open it.")
    return m


def _migrate(manifest: Dict[str, Any], gui_state: Dict[str, Any]):
    """Bring an older project to the current format. Version 1 is the first one: nothing to do yet; new versions add
    their steps here (`if version < 2: ...`)."""
    return manifest, gui_state


def load(path: str) -> Project:
    members = _read_zip(path)
    if "manifest.json" not in members:
        raise ProjectError(f"{os.path.basename(path)} is not a SHARC project (no manifest).")
    manifest = _check_manifest(members["manifest.json"], path)
    if "scenario.yaml" not in members or "gui_state.json" not in members:
        raise ProjectError(f"{os.path.basename(path)} is incomplete: the scenario or the GUI state is missing.")
    try:
        gui_state = json.loads(members["gui_state.json"].decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProjectError(f"{os.path.basename(path)}: the GUI state is damaged.") from exc
    manifest, gui_state = _migrate(manifest, gui_state)
    scenario = members["scenario.yaml"].decode("utf-8")
    md5 = manifest.get("scenario_md5")
    if md5 and md5 != hashlib.md5(scenario.encode("utf-8")).hexdigest():
        raise ProjectError(f"{os.path.basename(path)}: the scenario does not match its checksum (file damaged or edited).")
    contour_config = None
    if "contour/config.json" in members:
        try:
            contour_config = json.loads(members["contour/config.json"].decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProjectError(f"{os.path.basename(path)}: the contour configuration is damaged.") from exc
    return Project(name=str(manifest.get("name", "Untitled")), scenario_yaml=scenario, gui_state=gui_state,
                   notes=members.get("notes.md", b"").decode("utf-8"), contour_config=contour_config,
                   contour_results_csv=members.get("contour/results.csv", b"").decode("utf-8"),
                   summary=dict(manifest.get("summary") or {}), created=str(manifest.get("created", "")),
                   modified=str(manifest.get("modified", "")), sharc_version=str(manifest.get("sharc_version", "")),
                   format_version=int(manifest["format_version"]))


def extract_scenario(path: str, dest: str) -> str:
    """Write the engine YAML of a project to `dest` (for `main_cli`) and return the path."""
    members = _read_zip(path)
    if "manifest.json" not in members or "scenario.yaml" not in members:
        raise ProjectError(f"{os.path.basename(path)} is not a SHARC project.")
    _check_manifest(members["manifest.json"], path)
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(members["scenario.yaml"])
    return dest
