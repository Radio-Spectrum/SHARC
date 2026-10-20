# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the SHARC desktop build (onedir, windowed).

Build: python -m PyInstaller installer/sharc.spec --noconfirm --distpath installer/build/dist --workpath installer/build/work
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
PKG = os.path.join(ROOT, "sharc")
GUI = os.path.join(PKG, "gui")

SKIP_DIRS = {"__pycache__", "campaigns", "graphify-out", ".legacy", ".pytest_cache", "output"}


def _tree(src_root, dest_root):
    """All files of a source tree (minus caches, campaigns and run outputs) as PyInstaller datas."""
    items = []
    for cur, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(("output_", "."))]
        rel = os.path.relpath(cur, src_root)
        dest = dest_root if rel == "." else os.path.join(dest_root, rel)
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            items.append((os.path.join(cur, name), dest))
    return items


datas = _tree(PKG, "sharc")
binaries = []
hiddenimports = ["sharc.gui.main", "config", "utils"]
for pkg in ("ui", "core", "managers"):
    hiddenimports += collect_submodules(pkg)  # resolved through pathex=GUI

for name in ("cartopy", "pyproj", "rasterio", "geopandas", "pyogrio", "shapely", "qtawesome"):
    d, b, h = collect_all(name)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(SPECPATH, "sharc_launcher.py")],
    pathex=[GUI, PKG, ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "_pytest", "IPython", "notebook", "sphinx", "setuptools", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SHARC",
    console=False,
    icon=os.path.join(SPECPATH, "assets", "sharc.ico"),
    version=os.path.join(SPECPATH, "version_info.txt"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SHARC")
