"""
Simple YAML-like serializer used by the GUI.
This is intentionally minimal (not a full YAML implementation).
"""

from typing import Any, Dict, List


def _yaml_bool(v: bool) -> str:
    return "true" if v else "false"


def dump_yaml_block(data: Any, indent: int = 0) -> List[str]:
    lines: List[str] = []
    sp = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{sp}{key}:")
                lines.extend(dump_yaml_block(value, indent + 1))
            elif isinstance(value, (list, tuple)):
                lines.append(f"{sp}{key}:")
                for item in value:
                    if isinstance(item, (dict, list, tuple)):
                        lines.append(f"{sp}-")
                        lines.extend(dump_yaml_block(item, indent + 1))
                    elif isinstance(item, bool):
                        lines.append(f"{sp}- {_yaml_bool(item)}")
                    elif item is None:
                        lines.append(f"{sp}- null")
                    else:
                        lines.append(f"{sp}- {item}")
            elif isinstance(value, bool):
                lines.append(f"{sp}{key}: {_yaml_bool(value)}")
            elif value is None:
                lines.append(f"{sp}{key}: null")
            else:
                lines.append(f"{sp}{key}: {value}")
    else:
        # scalar or simple list item
        lines.append(f"{sp}{data}")

    return lines


def build_yaml_text(root: Dict[str, Any]) -> str:
    """
    Build a YAML-like string from a Python dictionary.
    Use this for preview/export in the GUI.
    """
    return "\n".join(dump_yaml_block(root)) + "\n"
