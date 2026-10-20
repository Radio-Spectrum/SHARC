"""Procedural 3D models (glTF binary) for the preview: satellite, base-station tower, earth-station dish.

The models are built here from simple solids, so the preview needs no external 3D assets and
stays crisp at any zoom. Coordinates follow glTF: +Y is up and +Z is the "front" of the model
(the dish / antenna boresight). Units are metres at scale 1.
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

Vec = Tuple[float, float, float]


@dataclass
class Material:
    color: Tuple[float, float, float, float]
    metallic: float = 0.2
    roughness: float = 0.6
    emissive: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    double_sided: bool = False


@dataclass
class Part:
    positions: np.ndarray            # (N, 3) float32
    normals: np.ndarray              # (N, 3) float32
    indices: np.ndarray              # (M,) uint32
    material: int
    colors: np.ndarray | None = None  # optional (N, 4) float32 per-vertex RGBA (glTF COLOR_0)


@dataclass
class Model:
    materials: List[Material] = field(default_factory=list)
    parts: List[Part] = field(default_factory=list)

    def material(self, *args, **kwargs) -> int:
        self.materials.append(Material(*args, **kwargs))
        return len(self.materials) - 1

    def add(self, mesh: Tuple[np.ndarray, np.ndarray, np.ndarray], material: int) -> None:
        self.parts.append(Part(*mesh, material))


# ----------------------------------------------------------------------------- primitives
def _rot(axis: str, deg: float) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def transform(mesh, rot: np.ndarray | None = None, move: Vec = (0, 0, 0)):
    p, n, i = mesh
    if rot is not None:
        p, n = p @ rot.T, n @ rot.T
    return (p + np.asarray(move, dtype=np.float32)).astype(np.float32), n.astype(np.float32), i


def box(size: Vec) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    sx, sy, sz = (v / 2.0 for v in size)
    faces = [((1, 0, 0), [(sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz), (sx, -sy, sz)]),
             ((-1, 0, 0), [(-sx, -sy, sz), (-sx, sy, sz), (-sx, sy, -sz), (-sx, -sy, -sz)]),
             ((0, 1, 0), [(-sx, sy, -sz), (-sx, sy, sz), (sx, sy, sz), (sx, sy, -sz)]),
             ((0, -1, 0), [(-sx, -sy, sz), (-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz)]),
             ((0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
             ((0, 0, -1), [(sx, -sy, -sz), (-sx, -sy, -sz), (-sx, sy, -sz), (sx, sy, -sz)])]
    pos, nor, idx = [], [], []
    for normal, corners in faces:
        base = len(pos)
        pos += corners
        nor += [normal] * 4
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    return np.array(pos, np.float32), np.array(nor, np.float32), np.array(idx, np.uint32)


def cylinder(radius: float, height: float, segments: int = 24, radius_top: float | None = None):
    """Cylinder/cone along Y, centred on the origin."""
    rt = radius if radius_top is None else radius_top
    h = height / 2.0
    pos, nor, idx = [], [], []
    slope = (radius - rt) / height
    for k in range(segments + 1):
        a = 2 * math.pi * k / segments
        c, s = math.cos(a), math.sin(a)
        n = np.array([c, slope, s])
        n = n / np.linalg.norm(n)
        pos += [(radius * c, -h, radius * s), (rt * c, h, rt * s)]
        nor += [tuple(n), tuple(n)]
    for k in range(segments):
        b = 2 * k
        idx += [b, b + 2, b + 1, b + 1, b + 2, b + 3]
    for y, ny, r, flip in ((h, 1.0, rt, False), (-h, -1.0, radius, True)):
        if r <= 1e-9:
            continue
        base = len(pos)
        pos.append((0, y, 0))
        nor.append((0, ny, 0))
        for k in range(segments + 1):
            a = 2 * math.pi * k / segments
            pos.append((r * math.cos(a), y, r * math.sin(a)))
            nor.append((0, ny, 0))
        for k in range(segments):
            tri = [base, base + 1 + k, base + 2 + k]
            idx += tri[::-1] if flip else tri
    return np.array(pos, np.float32), np.array(nor, np.float32), np.array(idx, np.uint32)


def dish(radius: float, depth: float, rings: int = 10, segments: int = 36):
    """Paraboloid reflector opening towards +Z (apex at the origin)."""
    pos, nor, idx = [(0.0, 0.0, 0.0)], [(0.0, 0.0, 1.0)], []
    for r in range(1, rings + 1):
        rr = radius * r / rings
        z = depth * (rr / radius) ** 2
        slope = 2 * depth * rr / radius ** 2
        for k in range(segments):
            a = 2 * math.pi * k / segments
            c, s = math.cos(a), math.sin(a)
            n = np.array([-slope * c, -slope * s, 1.0])
            pos.append((rr * c, rr * s, z))
            nor.append(tuple(n / np.linalg.norm(n)))
    for k in range(segments):
        idx += [0, 1 + k, 1 + (k + 1) % segments]
    for r in range(1, rings):
        for k in range(segments):
            a = 1 + (r - 1) * segments + k
            b = 1 + (r - 1) * segments + (k + 1) % segments
            c = 1 + r * segments + k
            d = 1 + r * segments + (k + 1) % segments
            idx += [a, c, d, a, d, b]
    return np.array(pos, np.float32), np.array(nor, np.float32), np.array(idx, np.uint32)


# ----------------------------------------------------------------------------- GLB writer
def to_glb(model: Model) -> bytes:
    buf = bytearray()
    views, accessors, prims = [], [], []

    def add_view(arr: np.ndarray, target: int) -> int:
        data = arr.tobytes()
        while len(buf) % 4:
            buf.append(0)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(data), "target": target})
        buf.extend(data)
        return len(views) - 1

    for part in model.parts:
        vp = add_view(part.positions.astype("<f4"), 34962)
        vn = add_view(part.normals.astype("<f4"), 34962)
        vi = add_view(part.indices.astype("<u4"), 34963)
        a0 = len(accessors)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(part.positions), "type": "VEC3",
                          "min": part.positions.min(axis=0).tolist(), "max": part.positions.max(axis=0).tolist()})
        accessors.append({"bufferView": vn, "componentType": 5126, "count": len(part.normals), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(part.indices), "type": "SCALAR"})
        attrs = {"POSITION": a0, "NORMAL": a0 + 1}
        if part.colors is not None:
            vc = add_view(part.colors.astype("<f4"), 34962)
            accessors.append({"bufferView": vc, "componentType": 5126, "count": len(part.colors), "type": "VEC4"})
            attrs["COLOR_0"] = len(accessors) - 1
        prims.append({"attributes": attrs, "indices": a0 + 2, "material": part.material})
    materials = []
    for m in model.materials:
        mat = {"pbrMetallicRoughness": {"baseColorFactor": list(m.color), "metallicFactor": m.metallic,
                                        "roughnessFactor": m.roughness}, "doubleSided": m.double_sided}
        if any(m.emissive):
            mat["emissiveFactor"] = list(m.emissive)
        if m.color[3] < 1.0:
            mat["alphaMode"] = "BLEND"
        materials.append(mat)
    doc = {"asset": {"version": "2.0", "generator": "SHARC model_factory"}, "scene": 0,
           "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}], "meshes": [{"primitives": prims}],
           "materials": materials, "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": len(buf)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bn = bytes(buf) + b"\0" * (-len(buf) % 4)
    total = 12 + 8 + len(js) + 8 + len(bn)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js
            + struct.pack("<I4s", len(bn), b"BIN\0") + bn)


# ----------------------------------------------------------------------------- the models
def satellite() -> Model:
    """Bus with gold foil, two solar wings and a nadir-pointing dish (+Z = boresight)."""
    m = Model()
    gold = m.material((0.85, 0.65, 0.25, 1), metallic=0.8, roughness=0.35)
    solar = m.material((0.08, 0.14, 0.45, 1), metallic=0.6, roughness=0.25)
    white = m.material((0.9, 0.9, 0.92, 1), metallic=0.3, roughness=0.4, double_sided=True)
    grey = m.material((0.55, 0.57, 0.6, 1), metallic=0.7, roughness=0.4)
    m.add(box((2.0, 2.0, 3.0)), gold)
    for sign in (-1, 1):
        m.add(transform(box((0.25, 0.1, 0.25)), move=(sign * 1.2, 0, 0)), grey)
        m.add(transform(box((7.0, 0.06, 2.6)), move=(sign * 4.9, 0, 0)), solar)
    m.add(transform(cylinder(0.08, 1.2), rot=_rot("x", 90), move=(0, 0, 2.1)), grey)
    m.add(transform(dish(1.3, 0.35), move=(0, 0, 2.7)), white)
    m.add(transform(cylinder(0.05, 0.9), move=(0, 1.4, 0)), grey)
    return m


def tower() -> Model:
    """Lattice-like mast with three sector panels (front of panel 0 = +Z, then every 120 degrees)."""
    m = Model()
    steel = m.material((0.62, 0.64, 0.67, 1), metallic=0.7, roughness=0.45)
    panel = m.material((0.93, 0.93, 0.95, 1), metallic=0.1, roughness=0.5)
    red = m.material((0.9, 0.15, 0.12, 1), metallic=0.1, roughness=0.5, emissive=(0.4, 0.0, 0.0))
    m.add(transform(cylinder(0.45, 30.0, 16, 0.2), move=(0, 15.0, 0)), steel)
    m.add(transform(box((4.2, 0.25, 0.25)), move=(0, 29.0, 0)), steel)
    for k in range(3):
        r = _rot("y", 120 * k)
        m.add(transform(box((0.45, 2.4, 0.18)), rot=r, move=tuple(r @ np.array([0, 28.2, 0.9]))), panel)
        m.add(transform(box((0.3, 0.5, 0.2)), rot=r, move=tuple(r @ np.array([0, 26.6, 0.35]))), steel)
    m.add(transform(cylinder(0.12, 0.5), move=(0, 30.3, 0)), red)
    return m


def earth_station() -> Model:
    """Parabolic dish on a pedestal; the dish points along +Z and tilts around the X axis (hinge at y = 3)."""
    m = Model()
    white = m.material((0.92, 0.93, 0.95, 1), metallic=0.25, roughness=0.4, double_sided=True)
    grey = m.material((0.5, 0.52, 0.55, 1), metallic=0.7, roughness=0.45)
    m.add(transform(cylinder(0.45, 3.0, 20), move=(0, 1.5, 0)), grey)
    m.add(transform(box((1.4, 0.5, 0.9)), move=(0, 3.0, 0)), grey)
    m.add(transform(dish(2.4, 0.75), move=(0, 3.4, 0.2)), white)
    m.add(transform(cylinder(0.05, 2.2), rot=_rot("x", 90), move=(0, 3.4, 1.35)), grey)
    m.add(transform(box((0.25, 0.25, 0.3)), move=(0, 3.4, 2.5)), grey)
    return m


MODELS = {"satellite": satellite, "tower": tower, "earth_station": earth_station}
_cache: Dict[str, bytes] = {}


_dynamic: Dict[str, bytes] = {}


def register(name: str, data: bytes, limit: int = 64) -> None:
    """Serve extra, scene-dependent models (e.g. antenna gain lobes) under /models/<name>.glb."""
    if len(_dynamic) >= limit:
        _dynamic.pop(next(iter(_dynamic)))
    _dynamic[name] = data


def glb(name: str) -> bytes:
    """GLB bytes for one of MODELS (built once, then cached) or a registered dynamic model."""
    if name in _dynamic:
        return _dynamic[name]
    if name not in MODELS:
        raise KeyError(name)
    if name not in _cache:
        _cache[name] = to_glb(MODELS[name]())
    return _cache[name]
