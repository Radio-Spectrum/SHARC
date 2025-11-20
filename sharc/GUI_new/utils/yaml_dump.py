def _yaml_bool(v: bool) -> str:
    return "true" if v else "false"

def dump_yaml_block(d, indent=0):
    lines = []
    sp = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.extend(dump_yaml_block(v, indent + 1))
            elif isinstance(v, (list, tuple)):
                lines.append(f"{sp}{k}:")
                for it in v:
                    if isinstance(it, (dict, list, tuple)):
                        lines.append(f"{sp}-")
                        lines.extend(dump_yaml_block(it, indent + 1))
                    elif isinstance(it, bool):
                        lines.append(f"{sp}- {_yaml_bool(it)}")
                    elif it is None:
                        lines.append(f"{sp}- null")
                    else:
                        lines.append(f"{sp}- {it}")
            elif isinstance(v, bool):
                lines.append(f"{sp}{k}: {_yaml_bool(v)}")
            elif v is None:
                lines.append(f"{sp}{k}: null")
            else:
                lines.append(f"{sp}{k}: {v}")
    else:
        lines.append(f"{sp}{d}")
    return lines

def build_yaml_text(root_dict: dict) -> str:
    return "\n".join(dump_yaml_block(root_dict)) + "\n"
