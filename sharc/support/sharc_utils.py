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
    if s.replace(".", "").isnumeric():
        return True
    else:
        return False
