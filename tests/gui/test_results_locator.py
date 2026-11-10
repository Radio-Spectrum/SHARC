"""Result folders are found without the user pointing at them."""
import os
import sys
import time
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "sharc", "gui"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import results_locator as rl  # noqa: E402


def _job_yaml(tmp_path, **gen):
    p = tmp_path / "runs" / "job_a.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    p.write_text(yaml.safe_dump({"general": gen}), encoding="utf-8")
    return str(p)


def _result_dir(path: Path, with_yaml=None):
    path.mkdir(parents=True)
    (path / "imt_coupling_loss.csv").write_text("x\n1\n", encoding="utf-8")
    if with_yaml:
        (path / with_yaml).write_text("general: {}\n", encoding="utf-8")
    return path


def test_overwrite_mode_uses_output_dir_itself(tmp_path):
    sharc = tmp_path / "sharc"
    y = _job_yaml(tmp_path, output_dir="out", output_dir_prefix="p", overwrite_output=True)
    assert rl.find_job_results(y, sharc) is None                      # nothing written yet
    out = _result_dir(sharc / "out")
    assert rl.find_job_results(y, sharc) == out


def test_numbered_mode_picks_the_folder_holding_this_jobs_yaml(tmp_path):
    sharc = tmp_path / "sharc"
    y = _job_yaml(tmp_path, output_dir="out", output_dir_prefix="p", overwrite_output=False)
    mine = _result_dir(sharc / "out" / "p_2026-01-01_01", with_yaml="job_a.yaml")
    other = _result_dir(sharc / "out" / "p_2026-01-01_02", with_yaml="job_b.yaml")
    now = time.time()
    os.utime(mine, (now - 100, now - 100))
    os.utime(other, (now, now))                                       # newer, but not this job's
    assert rl.find_job_results(y, sharc) == mine


def test_numbered_mode_falls_back_to_newest_with_prefix(tmp_path):
    sharc = tmp_path / "sharc"
    y = _job_yaml(tmp_path, output_dir="out", output_dir_prefix="p", overwrite_output=False)
    old = _result_dir(sharc / "out" / "p_2026-01-01_01")
    new = _result_dir(sharc / "out" / "p_2026-01-01_02")
    _result_dir(sharc / "out" / "unrelated_2026-01-01_01")           # other prefix is ignored
    now = time.time()
    os.utime(old, (now - 50, now - 50))
    os.utime(new, (now, now))
    assert rl.find_job_results(y, sharc) == new


def test_unreadable_yaml_does_not_raise(tmp_path):
    assert rl.find_job_results(str(tmp_path / "missing.yaml"), tmp_path / "sharc") is None


def test_discover_lists_result_folders_newest_first_and_skips_noise(tmp_path):
    a = _result_dir(tmp_path / "r" / "a")
    b = _result_dir(tmp_path / "r" / "b")
    _result_dir(tmp_path / "r" / "_deprecated" / "old")
    _result_dir(tmp_path / "r" / ".hidden")
    (tmp_path / "r" / "empty").mkdir()
    now = time.time()
    os.utime(a, (now - 10, now - 10))
    os.utime(b, (now, now))
    got = rl.discover([tmp_path / "r", tmp_path / "does_not_exist"])
    assert got == [b.resolve(), a.resolve()]


def test_discover_respects_depth_limit(tmp_path):
    _result_dir(tmp_path / "r" / "l1" / "l2" / "l3")
    assert rl.discover([tmp_path / "r"], max_depth=2) == []
    assert len(rl.discover([tmp_path / "r"], max_depth=4)) == 1
