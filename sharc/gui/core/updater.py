"""Self-update of the installed SHARC build, tied to the branch it was built from.

The installer ships ``build_info.json`` (written by installer/build.ps1) with the repo, the
branch, the release tag of that branch and the commit the build came from. Each branch keeps one
GitHub release (``v<version>-<branch>``) whose tag always points at the newest build; an update
exists when the tag moved away from the installed commit. Qt-free, so it can be unit tested.
"""
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, List, Optional

API = "https://api.github.com"
TIMEOUT = 15
MAX_CHANGELOG_COMMITS = 60


class UpdateError(Exception):
    """Network, API or integrity failure; the message is safe to show to the user."""


@dataclass(frozen=True)
class BuildInfo:
    repo: str
    branch: str
    tag: str
    commit: str
    version: str = ""
    built_at: str = ""

    @property
    def short_commit(self) -> str:
        return self.commit[:8]


@dataclass
class UpdateInfo:
    current: BuildInfo
    latest_commit: str
    tag: str
    release_url: str
    published_at: str
    notes: str                      # release body (hand-written summary)
    changes: List[str] = field(default_factory=list)   # commit subjects since the installed build
    asset_name: str = ""
    asset_url: str = ""
    asset_size: int = 0
    asset_sha256: str = ""

    @property
    def short_commit(self) -> str:
        return self.latest_commit[:8]


def build_info_path() -> Optional[str]:
    """Where the frozen build keeps build_info.json (None when running from source)."""
    base = getattr(sys, "_MEIPASS", None)
    return os.path.join(base, "sharc", "build_info.json") if base else None


def load_build_info(path: Optional[str] = None) -> Optional[BuildInfo]:
    """The installed build's identity, or None for a source checkout / unreadable file."""
    path = path or build_info_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8-sig") as fh:  # PowerShell writes a BOM
            data = json.load(fh)
        return BuildInfo(
            repo=data["repo"], branch=data["branch"], tag=data["tag"], commit=data["commit"],
            version=data.get("version", ""), built_at=data.get("built_at", ""),
        )
    except (OSError, ValueError, KeyError):
        return None


def _get_json(url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "SHARC-updater",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub answered HTTP {exc.code} for {url}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"Could not reach GitHub: {exc}") from exc


def _tag_commit(repo: str, tag: str) -> str:
    ref = _get_json(f"{API}/repos/{repo}/git/ref/tags/{tag}")["object"]
    if ref["type"] == "tag":  # annotated tag: one more hop to the commit
        ref = _get_json(ref["url"])["object"]
    return ref["sha"]


def _changes_since(repo: str, base: str, head: str) -> List[str]:
    """Commit subjects (newest first) between two commits; empty if the history is unrelated."""
    try:
        cmp = _get_json(f"{API}/repos/{repo}/compare/{base}...{head}")
    except UpdateError:
        return []
    subjects = [c["commit"]["message"].splitlines()[0] for c in cmp.get("commits", [])]
    return list(reversed(subjects))[:MAX_CHANGELOG_COMMITS]


def check_for_update(current: BuildInfo) -> Optional[UpdateInfo]:
    """UpdateInfo when the branch release moved past the installed commit, else None."""
    latest = _tag_commit(current.repo, current.tag)
    if latest == current.commit:
        return None
    release = _get_json(f"{API}/repos/{current.repo}/releases/tags/{current.tag}")
    setup = next((a for a in release.get("assets", []) if a["name"].lower().endswith("-setup-x64.exe")), None)
    if setup is None:
        raise UpdateError("The release has no installer attached yet.")
    digest = setup.get("digest") or ""
    return UpdateInfo(
        current=current, latest_commit=latest, tag=current.tag,
        release_url=release.get("html_url", ""), published_at=release.get("published_at", ""),
        notes=(release.get("body") or "").strip(),
        changes=_changes_since(current.repo, current.commit, latest),
        asset_name=setup["name"], asset_url=setup["browser_download_url"],
        asset_size=int(setup.get("size", 0)),
        asset_sha256=digest.split(":", 1)[1] if digest.startswith("sha256:") else "",
    )


def download_installer(
    info: UpdateInfo,
    progress: Optional[Callable[[int, int], None]] = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> str:
    """Download the installer to a temp folder, verify its SHA-256 and return its path."""
    folder = os.path.join(tempfile.gettempdir(), "SHARC-update")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, info.asset_name)
    part = dest + ".part"
    sha = hashlib.sha256()
    done = 0
    req = urllib.request.Request(info.asset_url, headers={"User-Agent": "SHARC-updater"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or info.asset_size)
            while True:
                if cancelled():
                    raise UpdateError("Download cancelled.")
                block = resp.read(1 << 20)
                if not block:
                    break
                out.write(block)
                sha.update(block)
                done += len(block)
                if progress:
                    progress(done, total)
    except (urllib.error.URLError, OSError) as exc:
        _remove(part)
        raise UpdateError(f"Download failed: {exc}") from exc
    except UpdateError:
        _remove(part)
        raise
    if info.asset_sha256 and sha.hexdigest() != info.asset_sha256:
        _remove(part)
        raise UpdateError("Downloaded installer is corrupted (checksum mismatch).")
    os.replace(part, dest)
    return dest


def launch_installer(path: str) -> None:
    """Start the installer through the shell, so Windows can raise the UAC prompt."""
    os.startfile(path)  # noqa: S606 - installer we just verified; Windows-only app


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
