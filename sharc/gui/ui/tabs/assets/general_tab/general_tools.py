import ast
import math


def parse_list_safe(s: str, default: list) -> list:
    """Safely parses a string representation of a list."""
    s = (s or "").strip()
    if not s:
        return default
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return list(obj)
    except (ValueError, SyntaxError):
        pass
    return default


def generate_sequence(start: float, end: float, param: float, mode: str) -> list[float]:
    """
    Generates a numeric sequence based on the mode.

    Args:
        start: Start value.
        end: End value.
        param: Step size (if mode='STEP') or N points (if mode='NPTS').
        mode: 'STEP' or 'NPTS'.
    """
    vals = []
    if mode == "STEP":
        step = param
        if step == 0:
            return []

        # Avoid infinite loops with a safety counter
        curr = start
        count = 0
        if step > 0:
            while curr <= end + 1e-9 and count < 10000:
                vals.append(curr)
                curr += step
                count += 1
        else:
            while curr >= end - 1e-9 and count < 10000:
                vals.append(curr)
                curr += step
                count += 1
    else:
        # NPTS mode
        n_pts = int(param)
        if n_pts <= 1:
            vals = [start]
        else:
            vals = [start + (end - start) * i / (n_pts - 1)
                    for i in range(n_pts)]

    return vals


def format_number(n: float) -> str:
    """Formats a number as integer if it's close to one, else 4 sig figs."""
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n:.4g}"
