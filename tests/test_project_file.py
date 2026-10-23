"""The .sharc project file format: round trip, safety checks, versions, atomic write and the CLI extraction."""
import json
import os
import sys
import zipfile

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "sharc", "gui"))

from core import project_file as pf  # noqa: E402


def _project(**kw):
    base = dict(name="Ceara test", scenario_yaml="general:\n  num_snapshots: 10\n", gui_state={"app": {"seed": 157}},
                notes="hello", summary={"system": "SINGLE_SPACE_STATION"}, sharc_version="1.2.3")
    base.update(kw)
    return pf.Project(**base)


def test_round_trip_keeps_everything(tmp_path):
    p = _project(contour_config={"site": {"lat": -3.87}}, contour_results_csv="az,d\n0,100\n")
    path = pf.save(str(tmp_path / "a"), p)                       # the extension is added
    assert path.endswith(".sharc") and os.path.isfile(path)
    q = pf.load(path)
    assert (q.name, q.scenario_yaml, q.gui_state, q.notes) == (p.name, p.scenario_yaml, p.gui_state, "hello")
    assert q.contour_config == {"site": {"lat": -3.87}} and q.contour_results_csv == "az,d\n0,100\n"
    assert q.summary == {"system": "SINGLE_SPACE_STATION"} and q.sharc_version == "1.2.3"
    assert q.format_version == pf.FORMAT_VERSION and q.modified >= q.created


def test_optional_parts_are_optional(tmp_path):
    q = pf.load(pf.save(str(tmp_path / "b.sharc"), _project(notes="")))
    assert q.contour_config is None and q.contour_results_csv == "" and q.notes == ""
    with zipfile.ZipFile(tmp_path / "b.sharc") as z:
        assert sorted(z.namelist()) == ["gui_state.json", "manifest.json", "scenario.yaml"]


def test_it_is_a_zip_and_the_yaml_is_plain_for_the_cli(tmp_path):
    path = pf.save(str(tmp_path / "c.sharc"), _project())
    out = pf.extract_scenario(path, str(tmp_path / "sub" / "scenario.yaml"))
    assert open(out, encoding="utf-8").read() == "general:\n  num_snapshots: 10\n"


def test_non_projects_are_refused_with_a_clear_message(tmp_path):
    missing = str(tmp_path / "nope.sharc")
    with pytest.raises(pf.ProjectError, match="not found"):
        pf.load(missing)
    junk = tmp_path / "junk.sharc"
    junk.write_bytes(b"not a zip at all")
    with pytest.raises(pf.ProjectError, match="not a SHARC project"):
        pf.load(str(junk))
    other = tmp_path / "other.sharc"
    with zipfile.ZipFile(other, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "something-else", "format_version": 1}))
    with pytest.raises(pf.ProjectError, match="not a SHARC project"):
        pf.load(str(other))


def test_newer_format_is_refused_not_half_read(tmp_path):
    path = pf.save(str(tmp_path / "d.sharc"), _project())
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    m = json.loads(members["manifest.json"])
    m["format_version"] = pf.FORMAT_VERSION + 1
    members["manifest.json"] = json.dumps(m).encode()
    with zipfile.ZipFile(path, "w") as z:
        for n, b in members.items():
            z.writestr(n, b)
    with pytest.raises(pf.ProjectError, match="newer SHARC"):
        pf.load(path)
    with pytest.raises(pf.ProjectError, match="newer SHARC"):
        pf.read_manifest(path)


def test_edited_scenario_fails_the_checksum(tmp_path):
    path = pf.save(str(tmp_path / "e.sharc"), _project())
    with zipfile.ZipFile(path) as z:
        members = {n: z.read(n) for n in z.namelist()}
    members["scenario.yaml"] = b"general:\n  num_snapshots: 99999999\n"
    with zipfile.ZipFile(path, "w") as z:
        for n, b in members.items():
            z.writestr(n, b)
    with pytest.raises(pf.ProjectError, match="checksum"):
        pf.load(path)


def test_incomplete_and_unknown_members(tmp_path):
    path = tmp_path / "f.sharc"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": pf.FORMAT, "format_version": 1}))
    with pytest.raises(pf.ProjectError, match="incomplete"):
        pf.load(str(path))
    # a path-traversal member is never read, never written to disk
    good = pf.save(str(tmp_path / "g.sharc"), _project())
    with zipfile.ZipFile(good, "a") as z:
        z.writestr("../evil.txt", "x")
        z.writestr("contour/../../evil2.txt", "x")
    pf.load(good)
    assert not (tmp_path.parent / "evil.txt").exists() and not (tmp_path / "evil2.txt").exists()


def test_a_huge_member_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "MAX_MEMBER_BYTES", 100)
    path = pf.save(str(tmp_path / "h.sharc"), _project(scenario_yaml="x: " + "1" * 500))
    with pytest.raises(pf.ProjectError, match="too large"):
        pf.load(path)


def test_save_is_atomic_when_the_write_fails(tmp_path, monkeypatch):
    path = pf.save(str(tmp_path / "i.sharc"), _project(name="first"))

    def boom(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(pf.ProjectError, match="disk full"):
        pf.save(path, _project(name="second"))
    monkeypatch.undo()
    assert pf.load(path).name == "first"                                 # the old file is intact
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []   # and no temp file is left behind


def test_unicode_survives(tmp_path):
    q = pf.load(pf.save(str(tmp_path / "j.sharc"), _project(name="Eusébio – CE", notes="órgão")))
    assert q.name == "Eusébio – CE" and q.notes == "órgão"
