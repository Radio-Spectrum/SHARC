"""Contour campaign rows <-> CSV text (the `contour/results.csv` of a project)."""
from __future__ import annotations

import csv
import io
from typing import Dict, List, Sequence

from sharc.contour.campaign import COLUMNS

_TEXT = {"marker", "ray_end_reason"}
_INT = {"evaluations"}


def rows_to_csv(rows: Sequence[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in COLUMNS})
    return out.getvalue()


def rows_from_csv(text: str) -> List[Dict[str, object]]:
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        row: Dict[str, object] = {}
        for key in COLUMNS:
            value = raw.get(key, "")
            if key in _TEXT:
                row[key] = value
            elif key in _INT:
                row[key] = int(float(value)) if value not in ("", None) else 0
            else:
                row[key] = float(value) if value not in ("", None) else float("nan")
        rows.append(row)
    return rows
