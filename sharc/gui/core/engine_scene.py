"""Cena do Preview montada pelo próprio motor do SHARC.

O Preview deve mostrar o que o simulador fará, não uma aproximação. Este módulo
pega o YAML que a GUI gera (a mesma estrutura enviada ao simulador), lê os
parâmetros com a classe `Parameters` do motor e gera topologia, estações-base e
UEs com as mesmas fábricas usadas em `Simulation` (mesma semente). Erros de
parâmetro viram mensagens legíveis em vez de um desenho enganoso.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import yaml


class EngineSceneError(Exception):
    """Parâmetros inválidos para o motor (mensagem já pronta para exibir)."""


@dataclass
class EngineScene:
    params: Any
    topology: Any
    bs: Any
    ue: Any
    reference: Dict[str, float]
    system: Any = None          # StationManager do sistema vítima (antena real do motor)
    system_error: str = ""
    coordinate_system: Any = None


_CACHE: Dict[str, EngineScene] = {}
_CACHE_MAX = 8


def _yaml_key(data: Dict[str, Any]) -> str:
    return hashlib.sha1(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def build_engine_scene(data: Dict[str, Any]) -> EngineScene:
    """Constrói (e guarda em cache) a cena do motor para o YAML `data`."""
    from sharc.parameters.parameters import Parameters
    from sharc.station_factory import StationFactory
    from sharc.support.sharc_geom import CoordinateSystem
    from sharc.topology.topology_factory import TopologyFactory

    data = copy.deepcopy(data)
    gen = data.setdefault("general", {})
    if str(gen.get("seed", "")).upper() == "RANDOM":
        gen["seed"] = 42  # preview only; the simulation draws its own

    key = _yaml_key(data)
    if key in _CACHE:
        return _CACHE[key]

    path = os.path.join(tempfile.mkdtemp(prefix="sharc_preview_"), "preview.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh)

    # The engine sometimes reports errors with sys.exit() after writing to stderr; a GUI must
    # never die because of that, so capture the text and turn it into a readable error.
    err_buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(err_buf), contextlib.redirect_stdout(io.StringIO()):
            params = Parameters()
            params.set_file_name(path)
            params.read_params()
            topo_p = params.imt.topology
            cs = CoordinateSystem()
            if topo_p.central_latitude is not None:
                cs.set_reference(topo_p.central_latitude, topo_p.central_longitude, topo_p.central_altitude)
            else:
                cs.set_reference(0.0, 0.0, 0.0)
            database = getattr(params, "database", None)
            if database is not None and database.is_loaded:
                # same as Simulation.select_database_subset for the first snapshot
                database.select_subset(database.subset_for_snapshot(1))
            topology = TopologyFactory.createTopology(params, cs)
            rng = np.random.RandomState(params.general.seed)
            topology.calculate_coordinates(rng)
            bs = StationFactory.generate_imt_base_stations(
                params.imt, params.imt.bs.antenna.array, topology, rng)
            ue = StationFactory.generate_imt_ue(
                params.imt, params.imt.ue.antenna.array, topology, rng)
    except SystemExit as exc:
        text = " ".join(err_buf.getvalue().split()) or f"engine exited ({exc.code})"
        raise EngineSceneError(text) from None
    except Exception as exc:  # noqa: BLE001 - any parameter failure
        raise EngineSceneError(f"{type(exc).__name__}: {exc}") from exc

    system, system_error = None, ""
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            system = StationFactory.generate_system(params, topology, rng, cs)
    except SystemExit:
        system_error = "the victim system could not be created"
    except Exception as exc:  # noqa: BLE001 - the system may not be drawable; the IMT still is
        system_error = f"{type(exc).__name__}: {exc}"

    scene = EngineScene(
        params=params, topology=topology, bs=bs, ue=ue, system=system, system_error=system_error,
        coordinate_system=cs,
        reference={
            "lat_deg": float(cs.ref_lat) if hasattr(cs, "ref_lat") else float(topo_p.central_latitude or 0.0),
            "lon_deg": float(cs.ref_long) if hasattr(cs, "ref_long") else float(topo_p.central_longitude or 0.0),
            "alt_m": float(cs.ref_alt) if hasattr(cs, "ref_alt") else float(topo_p.central_altitude or 0.0),
        },
    )
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = scene
    return scene


def hex_radius_m(es: EngineScene) -> float:
    """Raio (centro-vértice) da célula, a partir dos parâmetros do motor."""
    t = es.params.imt.topology
    kind = str(t.type).upper()
    if kind == "MACROCELL":
        return float(t.macrocell.intersite_distance) / math.sqrt(3.0)
    if kind == "HOTSPOT":
        return float(t.hotspot.intersite_distance) / math.sqrt(3.0)
    if kind == "SINGLE_BS":
        return float(t.single_bs.cell_radius)
    return 0.0


def apply_to_local(local, es: EngineScene) -> None:
    """Sobrescreve em `local` os valores que vinham de estados desatualizados."""
    g_bs, g_ue = es.bs.geom, es.ue.geom
    local.reference_lat_deg = es.reference["lat_deg"]
    local.reference_lon_deg = es.reference["lon_deg"]
    local.reference_alt_m = es.reference["alt_m"]
    local.bs_height_m = float(np.mean(g_bs.z_global))
    local.ue_height_m = float(np.mean(g_ue.z_global)) if len(g_ue.z_global) else local.ue_height_m
    local.downtilt_deg = float(-np.mean(g_bs.pointn_elev_global))
    local.ue_k = int(es.params.imt.ue.k)
    kind = str(es.params.imt.topology.type).upper()
    topo = es.topology
    local.xs = [float(v) for v in topo.x]
    local.ys = [float(v) for v in topo.y]
    if hasattr(topo, "azimuth") and len(topo.azimuth) == len(local.xs):
        local.azimuths = [float(v) for v in topo.azimuth]
    if kind == "INDOOR":
        local.indoor_topo = topo
    elif kind == "NTN":
        local.ntn_topo = topo


def hex_sector_scene(topo_type: str, es: EngineScene) -> Dict[str, Any]:
    """Cena de BSs setorizadas (MACROCELL/HOTSPOT/SINGLE_BS) com dados do motor."""
    g_bs, g_ue = es.bs.geom, es.ue.geom
    xs, ys = np.asarray(g_bs.x_global, float), np.asarray(g_bs.y_global, float)
    zs = np.asarray(g_bs.z_global, float)
    az = np.asarray(g_bs.pointn_azim_global, float)
    el = np.asarray(g_bs.pointn_elev_global, float)

    base_stations = [
        {"x": float(x), "y": float(y), "z": float(z), "azimuth_deg": float(a), "downtilt_deg": float(-e)}
        for x, y, z, a, e in zip(xs, ys, zs, az, el)
    ]
    centers = sorted({(round(float(x), 3), round(float(y), 3)) for x, y in zip(xs, ys)})

    return {
        "topology_type": topo_type,
        "reference": dict(es.reference),
        "hex_radius_m": hex_radius_m(es) or 50.0,
        "bs_height_m": float(np.mean(zs)),
        "ue_height_m": float(np.mean(g_ue.z_global)) if g_ue.num_geometries else 1.5,
        "downtilt_deg": float(-np.mean(el)),
        "base_stations": base_stations,
        "hex_centers": [{"x": x, "y": y} for x, y in centers],
        "ue_positions": [
            {"x": float(x), "y": float(y)}
            for x, y in zip(g_ue.x_global, g_ue.y_global)
        ],
        "source": "engine",
    }


def station_lat_lon(es: EngineScene, geom=None):
    """Latitude/longitude [deg] of IMT stations (default: the base stations).

    The engine converts with a spherical Earth, so the inverse must be spherical too;
    that reproduces the latitude/longitude of the database rows exactly."""
    g = geom if geom is not None else es.bs.geom
    x, y, z = es.coordinate_system.enu2ecef(
        np.asarray(g.x_global, float), np.asarray(g.y_global, float), np.asarray(g.z_global, float))
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    lat = np.degrees(np.arcsin(z / np.sqrt(x * x + y * y + z * z)))
    lon = np.degrees(np.arctan2(y, x))
    return lat, lon
