import os
import sys
import re
import ast
import json
import time
import queue
import yaml
import itertools
import datetime
import threading
import subprocess
import paramiko
from tkinter import simpledialog
import shlex
from pathlib import Path
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from sharc.antenna.antenna_s672 import AntennaS672
from sharc.parameters.antenna.parameters_antenna_s672 import ParametersAntennaS672
from matplotlib import cm, colors
import pandas as pd
import glob
from tkinter import filedialog
import traceback
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ====== Optional: Countries topology (for 3D preview) ======
HAS_TOPO = True
try:
    from sharc.topology.topology_countries import TopologyCountries, ParametersCountries
    from sharc.support.sharc_geom_countries import GeometryConverter
except Exception:
    HAS_TOPO = False
    TopologyCountries = None
    ParametersCountries = None
    GeometryConverter = None

# ====== Optional: shapefile borders (pyshp) ======
try:
    import shapefile as pyshp  # pip install pyshp
    HAS_PYSHP = True
except Exception:
    HAS_PYSHP = False

# ===================== Simple YAML dumper =====================
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

# ===================== Geodesy helpers =====================
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563

def lla_to_ecef(lat_deg, lon_deg, h_m, a=WGS84_A, f=WGS84_F):
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    s, c = np.sin(lat), np.cos(lat)
    sl, cl = np.sin(lon), np.cos(lon)
    e2 = f * (2.0 - f)
    N = a / np.sqrt(1.0 - e2 * s * s)
    X = (N + h_m) * c * cl
    Y = (N + h_m) * c * sl
    Z = (N * (1.0 - e2) + h_m) * s
    return X, Y, Z

# ===================== UI Helpers =====================
def add_row_three(parent, r, items):
    col = 0
    for (txt, w) in items:
        lbl = ttk.Label(parent, text=txt)
        lbl.grid(row=r, column=col, sticky="e", padx=(0,6), pady=2)
        w.grid(row=r, column=col+1, sticky="we", pady=2)
        parent.grid_columnconfigure(col+1, weight=1)
        col += 2
    while col < 6:
        parent.grid_columnconfigure(col, weight=1)
        col += 1


# ===================== GUI =====================
