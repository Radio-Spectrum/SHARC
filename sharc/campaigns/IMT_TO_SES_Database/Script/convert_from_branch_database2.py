# -*- coding: utf-8 -*-
"""Convert parameter files written for branch_database2 to this branch.

The edits are made on the text, so comments and layout are kept:

* ``imt.topology.type: Macro_countries`` becomes ``MACRO_COUNTRIES``;
* ``imt.ue.distribution_type: Macro_Countries`` becomes
  ``ANGLE_AND_DISTANCE`` with ``distribution_distance: SQRT(UNIFORM)`` and
  ``distribution_azimuth: UNIFORM``, which is how branch_database2 placed the
  UEs: radius uniform in area between minimum_separation_distance_bs_ue and
  the cell radius, angle uniform within azimuth_range around the BS azimuth;
* the ``gain`` of an ``itu_r_f_1245_fs`` block is removed: here the F.1245
  peak gain is ``antenna.gain`` (the two must be equal, or the file is
  rejected);
* optionally, ``database.database_file_name`` and ``general.output_dir`` are
  replaced.

Usage::

    python convert_from_branch_database2.py SRC OUT_DIR [--database PATH]
        [--output-dir DIR] [--check]

SRC is a parameter file or a folder of them. --check loads every converted
file with this branch's Parameters (with use_real_terrain switched off, so
that nothing is downloaded or precomputed).
"""
import argparse
import re
import sys
from pathlib import Path

import yaml


def _tuple_constructor(loader, node):
    return tuple(loader.construct_sequence(node))


yaml.SafeLoader.add_constructor("tag:yaml.org,2002:python/tuple", _tuple_constructor)


def convert_text(text: str, database: str | None = None, output_dir: str | None = None) -> str:
    """Return the converted text of one parameter file."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"(?m)^(\s*type:\s*)Macro_countries\b", r"\1MACRO_COUNTRIES", text)

    def ue_distribution(match):
        indent = match.group(1)
        lines = [f"{indent}distribution_type: ANGLE_AND_DISTANCE"]
        lines.append(f"{indent}distribution_distance: SQRT(UNIFORM)")
        lines.append(f"{indent}distribution_azimuth: UNIFORM")
        return "\n".join(lines)

    package_ue = re.compile(r"(?m)^(\s*)distribution_type:\s*Macro_Countries\b[^\n]*")
    if package_ue.search(text):
        if re.search(r"(?m)^\s*distribution_(distance|azimuth):", text):
            raise ValueError("the file already sets distribution_distance/distribution_azimuth")
        text = package_ue.sub(ue_distribution, text)

    block = re.search(r"(?m)^(\s*)itu_r_f_1245_fs:\s*\n((?:\1\s+\S[^\n]*\n)+)", text)
    if block:
        params = yaml.safe_load(text)
        antennas = [
            section["antenna"] for section in params.values()
            if isinstance(section, dict) and isinstance(section.get("antenna"), dict)
            and "itu_r_f_1245_fs" in section["antenna"]
        ]
        for antenna in antennas:
            block_gain = antenna["itu_r_f_1245_fs"].get("gain")
            if block_gain is not None and float(block_gain) != float(antenna.get("gain")):
                raise ValueError(
                    f"itu_r_f_1245_fs.gain ({block_gain}) differs from antenna.gain "
                    f"({antenna.get('gain')}): set antenna.gain to the F.1245 peak gain")
        body = re.sub(r"(?m)^\s+gain:[^\n]*\n", "", block.group(2))
        text = text[:block.start(2)] + body + text[block.end(2):]

    if database is not None:
        text, n = re.subn(r"(?m)^(\s*database_file_name:\s*).*$", lambda m: m.group(1) + repr(database), text)
        if n != 1:
            raise ValueError("database.database_file_name not found")
    if output_dir is not None:
        text, n = re.subn(r"(?m)^(\s*output_dir:\s*).*$", lambda m: m.group(1) + repr(output_dir), text)
        if n != 1:
            raise ValueError("general.output_dir not found")
    return text


def check(path: Path):
    """Load a converted file with this branch's Parameters, without real terrain."""
    from sharc.parameters.parameters import Parameters

    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^(\s*use_real_terrain:\s*)true\b", r"\1false", text)
    text = re.sub(r"(?m)^(\s*override_from_db:\s*)true\b", r"\1false", text)
    text = re.sub(r"(?m)^(\s*is_terrain:\s*)true\b", r"\1false", text)
    # next to the original, so that relative paths resolve the same way
    probe = path.parent / f".check_{path.name}"
    probe.write_text(text, encoding="utf-8", newline="")
    try:
        parameters = Parameters()
        parameters.set_file_name(str(probe))
        parameters.read_params()
    finally:
        probe.unlink()


def main(argv=None):
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--database", help="new database.database_file_name")
    parser.add_argument("--output-dir", help="new general.output_dir")
    parser.add_argument("--check", action="store_true", help="load every converted file")
    args = parser.parse_args(argv)

    files = sorted(args.src.glob("*.yaml")) if args.src.is_dir() else [args.src]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for src in files:
        out = args.out_dir / src.name
        out.write_text(convert_text(src.read_text(encoding="utf-8"), args.database, args.output_dir),
                       encoding="utf-8", newline="")
        if args.check:
            check(out)
        print(f"{src.name} -> {out}")


if __name__ == "__main__":
    sys.exit(main())
