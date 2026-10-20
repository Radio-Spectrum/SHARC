"""In-app updater: build identity, update detection, changelog and download integrity."""
import hashlib
import json

import pytest

from core import updater

CUR = updater.BuildInfo(repo="o/r", branch="b", tag="v1-b", commit="a" * 40)


def _api(monkeypatch, tag_sha, assets=None):
    def fake(url):
        if "/git/ref/tags/" in url:
            return {"object": {"type": "commit", "sha": tag_sha}}
        if "/releases/tags/" in url:
            return {"html_url": "u", "published_at": "t", "body": "notes", "assets": assets if assets is not None else [{
                "name": "SHARC-1-Setup-x64.exe", "browser_download_url": "http://x/s.exe",
                "size": 3, "digest": "sha256:" + hashlib.sha256(b"abc").hexdigest()}]}
        if "/compare/" in url:
            return {"commits": [{"commit": {"message": "feat: one\n\nbody"}},
                                {"commit": {"message": "fix: two"}}]}
        raise AssertionError(url)
    monkeypatch.setattr(updater, "_get_json", fake)


def test_load_build_info_reads_bom_json(tmp_path):
    f = tmp_path / "build_info.json"
    f.write_text(json.dumps({"repo": "o/r", "branch": "b", "tag": "t", "commit": "c"}), encoding="utf-8-sig")
    assert updater.load_build_info(str(f)).branch == "b"


def test_load_build_info_missing_or_broken(tmp_path):
    assert updater.load_build_info(str(tmp_path / "none.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert updater.load_build_info(str(bad)) is None


def test_no_update_when_tag_matches(monkeypatch):
    _api(monkeypatch, "a" * 40)
    assert updater.check_for_update(CUR) is None


def test_update_found_lists_changes_oldest_first(monkeypatch):
    _api(monkeypatch, "b" * 40)
    info = updater.check_for_update(CUR)
    assert info.latest_commit == "b" * 40
    assert info.changes == ["fix: two", "feat: one"]
    assert info.asset_sha256 == hashlib.sha256(b"abc").hexdigest()


def test_release_without_installer_is_an_error(monkeypatch):
    _api(monkeypatch, "b" * 40, assets=[])
    with pytest.raises(updater.UpdateError):
        updater.check_for_update(CUR)


class _Resp:
    headers = {"Content-Length": "3"}

    def __init__(self):
        self._data = [b"abc", b""]

    def read(self, _n):
        return self._data.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _info(sha):
    return updater.UpdateInfo(current=CUR, latest_commit="b" * 40, tag="t", release_url="", published_at="",
                              notes="", asset_name="t-Setup-x64.exe", asset_url="http://x", asset_sha256=sha)


def test_download_verifies_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: _Resp())
    path = updater.download_installer(_info(hashlib.sha256(b"abc").hexdigest()))
    assert open(path, "rb").read() == b"abc"


def test_download_rejects_corrupted_file(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(updater.UpdateError):
        updater.download_installer(_info("0" * 64))
    assert not list((tmp_path / "SHARC-update").glob("*"))
