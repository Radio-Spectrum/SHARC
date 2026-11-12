"""Checkpoint / resume: an interrupted run, once resumed, gives the same samples as an uninterrupted one."""
import os
from pathlib import Path

import pandas as pd
import pytest
import yaml

from sharc.model import Model
from sharc.results import Results
from sharc.support import checkpoint

yaml.SafeDumper.add_representer(
    tuple, lambda dumper, value: dumper.represent_sequence("tag:yaml.org,2002:python/tuple", value),
)

# Small macrocell scenario; shadowing on, so the generator shared across snapshots matters.
PARAMETERS = {
    "general": {
        "num_snapshots": 35, "imt_link": "DOWNLINK", "system": "SINGLE_EARTH_STATION",
        "enable_cochannel": True, "enable_adjacent_channel": False, "seed": 75,
        "overwrite_output": False,
    },
    "imt": {
        "minimum_separation_distance_bs_ue": 35, "interfered_with": False,
        "frequency": 3500, "bandwidth": 20, "rb_bandwidth": 0.18,
        "spectral_mask": "3GPP E-UTRA", "spurious_emissions": -30,
        "guard_band_ratio": 0.1,
        "topology": {
            "type": "MACROCELL",
            "macrocell": {"intersite_distance": 500, "num_clusters": 1, "wrap_around": False},
        },
        "bs": {"load_probability": 0.5, "conducted_power": 28.0, "height": 20.0,
               "noise_figure": 11, "ohmic_loss": 0},
        "ue": {"k": 2, "k_m": 1, "indoor_percent": 0, "distribution_type": "ANGLE_AND_DISTANCE",
               "tx_power_control": True, "height": 1.5, "noise_figure": 9, "ohmic_loss": 0,
               "body_loss": 4},
        "channel_model": "UMa", "shadowing": True,
    },
    "single_earth_station": {
        "antenna": {"gain": 0.0, "pattern": "OMNI"},
        "bandwidth": 20.0, "channel_model": "FSPL", "frequency": 3500, "polarization_loss": 0,
        "geometry": {
            "azimuth": {"type": "FIXED", "fixed": 0.0},
            "elevation": {"type": "FIXED", "fixed": 0.0},
            "height": 15.0,
            "location": {"type": "FIXED", "fixed": {"x": 100.0, "y": 50.0}},
        },
        "noise_temperature": 50, "tx_power_density": -200,
    },
}


def _yaml(tmp_path, name, num_snapshots=35):
    import copy
    params = copy.deepcopy(PARAMETERS)
    params["general"].update(num_snapshots=num_snapshots, output_dir=str(tmp_path / "out"),
                             output_dir_prefix=f"output_{name}")
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(params, sort_keys=False), encoding="utf-8")
    return str(path)


def _run(param_file, resume=False, crash_after=None):
    Results.overwrite_sample_files = True
    model = Model()
    model.set_param_file(param_file)
    model.initialize(resume=resume)
    while not model.is_finished():
        model.snapshot()
        if crash_after is not None and model.current_snapshot >= crash_after:
            return model                      # "crash": no finalize, unflushed samples are lost
    model.finalize()
    return model


def _samples(folder):
    out = {}
    for p in sorted(Path(folder).glob("*.csv")):
        out[p.name] = pd.read_csv(p)["samples"].to_numpy()
    return out


def test_resume_matches_uninterrupted_run(tmp_path):
    full = _run(_yaml(tmp_path, "full"))
    ref = _samples(full.simulation.results.output_directory)
    assert ref

    pfile = _yaml(tmp_path, "cut")
    crashed = _run(pfile, crash_after=24)            # last checkpoint at snapshot 20
    out_dir = Path(crashed.simulation.results.output_directory)
    ckpt = checkpoint.find(pfile)
    assert ckpt.snapshot == 20 and ckpt.resumable and Path(ckpt.output_dir) == out_dir
    # a flush cut in half by the crash: garbage after the checkpoint must be dropped
    victim = next(out_dir.glob("*.csv"))
    with open(victim, "a") as fh:
        fh.write("123.4\n567.8\n9")

    resumed = _run(pfile, resume=True)
    assert Path(resumed.simulation.results.output_directory) == out_dir
    got = _samples(out_dir)
    assert got.keys() == ref.keys()
    for name in ref:
        assert len(got[name]) == len(ref[name]), name
        assert (got[name] == pytest.approx(ref[name])), name
    assert checkpoint.find(pfile).completed


def test_resume_refused_when_yaml_changed(tmp_path):
    pfile = _yaml(tmp_path, "chg", num_snapshots=20)
    _run(pfile, crash_after=12)
    with open(pfile, "a") as fh:
        fh.write("\n# edited\n")
    ckpt, reason = checkpoint.find_valid(pfile)
    assert ckpt is None and "changed" in reason


def test_find_interrupted_skips_finished_runs(tmp_path, monkeypatch):
    a = _yaml(tmp_path, "a", num_snapshots=20)
    b = _yaml(tmp_path, "b", num_snapshots=20)
    _run(a, crash_after=12)
    _run(b)
    assert checkpoint.find_interrupted(str(tmp_path)) == []          # this process is still "running" it
    monkeypatch.setattr(checkpoint, "pid_alive", lambda pid: False)
    found = [os.path.basename(c.param_file) for c in checkpoint.find_interrupted(str(tmp_path))]
    assert found == ["a.yaml"]
