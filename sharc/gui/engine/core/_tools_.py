"""
Minor tools for specific actions
"""

def _num_or_str(root, s):
    """Converte para float se possível; senão retorna string (p/ placeholders)."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s2 = str(s).strip()
    try:
        return float(s2)
    except Exception:
        return s2