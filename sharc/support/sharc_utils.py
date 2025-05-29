import numpy as np


def is_float(s: str) -> bool:
    """Check if string represents a float value

    Parameters
    ----------
    s : str
        input string

    Returns
    -------
    bool
        whether the string is a float value or not
    """
    try:
        float(s)
        return True
    except ValueError:
        return False


def to_scalar(x):
    if isinstance(x, np.ndarray):
        return x.item()  # Works for 0-D or 1-element arrays
    return x
