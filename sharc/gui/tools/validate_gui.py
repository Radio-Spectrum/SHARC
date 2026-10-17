"""Valida a GUI de ponta a ponta. Rode sempre depois de mudar a GUI:

    python sharc/gui/tools/validate_gui.py [pasta_de_capturas]

1. pytest tests/gui  (fumaça, fidelidade do preview, Run ponta a ponta)
2. tour de capturas das páginas (falha se algum traceback ou 'falhou' aparecer)
3. confere que cada captura existe e não está em branco
Sai com código 0 só se tudo passar.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
GUI = os.path.join(REPO, "sharc", "gui")
ENV = {**os.environ, "SHARC_GUI_NO_RESTORE": "1", "PYTHONPATH": REPO}


def step(name, cmd, env=None, cwd=REPO):
    print(f"\n=== {name} ===", flush=True)
    r = subprocess.run(cmd, cwd=cwd, env=env or ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def main() -> int:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="sharc_gui_tour_")
    failures = []

    rc, out = step("pytest tests/gui", [sys.executable, "-m", "pytest", "tests/gui", "-q", "-p", "no:cacheprovider"],
                   env={**ENV, "QT_QPA_PLATFORM": "offscreen"})
    print("\n".join(out.strip().splitlines()[-6:]))
    if rc != 0:
        failures.append("pytest tests/gui")

    rc, out = step("tour de capturas", [sys.executable, os.path.join(GUI, "tools", "screenshot_tour.py"), out_dir], cwd=GUI)
    bad = [l for l in out.splitlines() if "Traceback" in l or "falhou" in l or "Error:" in l]
    print(f"capturas em {out_dir}; problemas: {len(bad)}")
    for l in bad[:10]:
        print("  ", l)
    if rc != 0 or bad:
        failures.append("tour de capturas")

    try:
        from PIL import Image  # noqa
        for name in sorted(os.listdir(out_dir)):
            if name.endswith(".png"):
                im = Image.open(os.path.join(out_dir, name)).convert("L")
                lo, hi = im.getextrema()
                if hi - lo < 10:
                    failures.append(f"captura em branco: {name}")
    except ImportError:
        pass

    print("\nRESULTADO:", "OK" if not failures else "FALHOU -> " + "; ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
