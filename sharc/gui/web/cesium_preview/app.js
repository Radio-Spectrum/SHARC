// SHARC Preview — CesiumJS spike (Fase 2/3 of CESIUMJS_MIGRATION_PLAN.md).
//
// Proves that CesiumJS can render fully offline (no Cesium Ion, no CDN, no
// network) inside a Qt QWebEngineView, that a QWebChannel Python<->JS round
// trip works, and (Fase 3, first step) that real SHARC engine geometry
// (TopologyMacrocell, via demo_scene.py) can be rendered — not just
// hand-picked demo coordinates.

const statusEl = document.getElementById("status");
const isEmbedded = new URLSearchParams(window.location.search).get("embedded") === "1";

if (isEmbedded) {
  // Embedded in the real Preview tab: Python drives what's rendered
  // (PreviewTab._refresh_cesium calls requestScene() directly), so the
  // manual topology dropdown would just be confusing/redundant here.
  document.getElementById("topoPicker").style.display = "none";
}

function setStatus(text) {
  statusEl.textContent = text;
  console.log("[cesium_spike]", text);
}

window.addEventListener("error", function (event) {
  setStatus("JS ERROR: " + event.message);
});

setStatus("creating viewer (offline mode: no Ion, no imagery CDN)…");

// Offline world basemap: a plain equirectangular JPEG rasterized from the
// Natural Earth 110m countries shapefile already bundled with SHARC
// (sharc/topology/map/, public domain) — see
// tools/run_cesium_spike.py's sibling generator. No Ion, no network.
//
// NOTE: passing a provider via the Viewer's `imageryProvider` option is a
// no-op in this Cesium version (it only suppresses the default Ion layer) —
// the provider must be wrapped in an ImageryLayer and passed as `baseLayer`.
const worldBasemap = new Cesium.SingleTileImageryProvider({
  url: "./assets/world_basemap.jpg",
  tileWidth: 2048,
  tileHeight: 1024,
  rectangle: Cesium.Rectangle.MAX_VALUE,
});

let viewer;
try {
  viewer = new Cesium.Viewer("cesiumContainer", {
    // No Ion services of any kind: no world terrain, no geocoder/
    // base-layer-picker (both are Ion/Bing-backed by default).
    baseLayer: new Cesium.ImageryLayer(worldBasemap),
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: true,
    sceneModePicker: true,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    infoBox: true,
    selectionIndicator: true,
    shouldAnimate: false,
  });
} catch (e) {
  setStatus("FAILED to construct Cesium.Viewer: " + e);
  throw e;
}

// Flat, evenly-lit globe for now (no day/night shading) so the sphere is
// unambiguously visible regardless of the current real-world date/time —
// lighting can come back once real data makes it useful.
viewer.scene.globe.enableLighting = false;
viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#4a90d9");
viewer.scene.skyAtmosphere.show = true;
viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#0b0e1a");

// setView (synchronous, immediate) instead of flyTo(duration: 0) — flyTo
// expects a real animation duration and can no-op or behave oddly at 0.
// This is just the fallback view before (or if) real scene data arrives.
viewer.camera.setView({
  destination: Cesium.Cartesian3.fromDegrees(-47.0, -15.0, 25000000),
});

// --- Fase 3: render a SceneGraph that came from the real SHARC engine
// (TopologyMacrocell/Hotspot/SingleBaseStation/Indoor, via
// PyBridge.get_scene(topology_type) — see demo_scene.py), instead of
// hand-picked demo coordinates. Positions are in a local ENU frame
// (meters); `reference` anchors that frame to a real lat/lon so Cesium's
// own eastNorthUpToFixedFrame can place it on the globe — no coordinate
// math is re-implemented here. ---

function makeEnuHelpers(reference) {
  const origin = Cesium.Cartesian3.fromDegrees(reference.lon_deg, reference.lat_deg, reference.alt_m);
  const enuToFixed = Cesium.Transforms.eastNorthUpToFixedFrame(origin);
  const orientation = Cesium.Quaternion.fromRotationMatrix(Cesium.Matrix4.getMatrix3(enuToFixed, new Cesium.Matrix3()));
  return {
    toWorld(x, y, z) {
      return Cesium.Matrix4.multiplyByPoint(enuToFixed, new Cesium.Cartesian3(x, y, z), new Cesium.Cartesian3());
    },
    orientation,
  };
}

// --- Scenario-modeling helpers (Fase 5: melhor fidelidade geométrica) ---
//
// Same "direction vector + two perpendicular basis vectors" technique
// core/cesium_bridge.py's _footprint_boundary_lla / demo_scene.py's
// _footprint_boundary_lla already use for the satellite footprint circle —
// applied here in the local ENU (east/north/up) frame instead of ECEF, to
// draw a real 3D antenna beam cone instead of a single pointing line.

function unit3(v) {
  const n = Math.hypot(v[0], v[1], v[2]);
  return n > 0 ? [v[0] / n, v[1] / n, v[2] / n] : v;
}

function cross3(a, b) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

// Filled polygon for one sector's horizontal coverage wedge (ground-
// projected), matching PlotEnginesMixin._add_wedge_outline3d_mpl's
// half-beamwidth convention (30 deg either side of the azimuth).
function sectorWedgePositions(toWorld, bx, by, z, azDeg, radius, halfBwDeg = 30, segments = 16) {
  const positions = [toWorld(bx, by, z)];
  const az0 = Cesium.Math.toRadians(azDeg - halfBwDeg);
  const az1 = Cesium.Math.toRadians(azDeg + halfBwDeg);
  for (let i = 0; i <= segments; i++) {
    const a = az0 + ((az1 - az0) * i) / segments;
    positions.push(toWorld(bx + radius * Math.cos(a), by + radius * Math.sin(a), z));
  }
  positions.push(toWorld(bx, by, z));
  return positions;
}

// 3D antenna beam cone (apex at the BS/antenna, pointing along azimuth +
// downtilt) — a wireframe of radial lines plus a translucent base cap, so
// the antenna's real pointing direction and beamwidth are visible in 3D,
// not just a flat line.
function beamConePositions(bx, by, bz, azDeg, downtiltDeg, length, halfAngleDeg = 12, segments = 24) {
  const az = Cesium.Math.toRadians(azDeg);
  const dt = Cesium.Math.toRadians(downtiltDeg);
  const u = [Math.cos(dt) * Math.cos(az), Math.cos(dt) * Math.sin(az), -Math.sin(dt)];

  let ref = [0, 0, 1];
  if (Math.abs(u[2]) > 0.9) ref = [0, 1, 0];
  const e1 = unit3(cross3(u, ref));
  const e2 = cross3(u, e1);

  const halfAngle = Cesium.Math.toRadians(halfAngleDeg);
  const baseRadius = length * Math.tan(halfAngle);
  const apex = [bx, by, bz];
  const base = [];
  for (let i = 0; i <= segments; i++) {
    const phi = (2 * Math.PI * i) / segments;
    base.push([
      apex[0] + length * u[0] + baseRadius * (Math.cos(phi) * e1[0] + Math.sin(phi) * e2[0]),
      apex[1] + length * u[1] + baseRadius * (Math.cos(phi) * e1[1] + Math.sin(phi) * e2[1]),
      apex[2] + length * u[2] + baseRadius * (Math.cos(phi) * e1[2] + Math.sin(phi) * e2[2]),
    ]);
  }
  return { apex, base };
}

function addBeamCone(toWorld, entities, bx, by, bz, azDeg, downtiltDeg, length, color, halfAngleDeg = 12) {
  const { apex, base } = beamConePositions(bx, by, bz, azDeg, downtiltDeg, length, halfAngleDeg);
  const apexWorld = toWorld(apex[0], apex[1], apex[2]);
  const baseWorld = base.map((p) => toWorld(p[0], p[1], p[2]));

  // Translucent cap (the "flashlight beam" silhouette).
  entities.add({
    polygon: {
      hierarchy: baseWorld,
      material: color.withAlpha(0.18),
      outline: false,
      perPositionHeight: true,
    },
  });
  // A handful of radial lines from apex to the base circle, so the cone
  // shape reads clearly even from angles where the cap is edge-on.
  const radialStep = Math.max(1, Math.floor(base.length / 8));
  for (let i = 0; i < base.length; i += radialStep) {
    entities.add({
      polyline: { positions: [apexWorld, baseWorld[i]], width: 1, material: color.withAlpha(0.5) },
    });
  }
}

function renderHexSectorScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  const bsHeightM = scene.bs_height_m;
  const ueHeightM = scene.ue_height_m;
  const arrowLenM = scene.hex_radius_m * 0.6;

  // Hex cell outlines — one 6-vertex loop per site, matching
  // PlotEnginesMixin._hexagon_points (radius = hex_radius_m, 30 deg
  // rotation) so the honeycomb layout matches the legacy renderers.
  for (const hc of scene.hex_centers) {
    const positions = [];
    for (let i = 0; i <= 6; i++) {
      const angle = Cesium.Math.toRadians(30 + i * 60);
      positions.push(
        toWorld(
          hc.x + scene.hex_radius_m * Math.cos(angle),
          hc.y + scene.hex_radius_m * Math.sin(angle),
          0
        )
      );
    }
    viewer.entities.add({
      polyline: { positions, width: 1, material: Cesium.Color.SLATEBLUE.withAlpha(0.6) },
    });
  }

  // Base stations: mast (ground -> antenna height), sector coverage wedge
  // (filled, horizontal) and a real 3D antenna beam cone (azimuth +
  // downtilt + beamwidth) instead of a single pointing line.
  const sectorRadius = Math.max(scene.hex_radius_m * 0.85, arrowLenM);
  for (const bs of scene.base_stations) {
    const groundPos = toWorld(bs.x, bs.y, 0);
    const worldPos = toWorld(bs.x, bs.y, bsHeightM);

    viewer.entities.add({
      polyline: { positions: [groundPos, worldPos], width: 2, material: Cesium.Color.fromCssColorString("#8a94a8") },
    });
    viewer.entities.add({
      position: worldPos,
      point: { pixelSize: 6, color: Cesium.Color.CYAN, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
    });

    viewer.entities.add({
      polygon: {
        hierarchy: sectorWedgePositions(toWorld, bs.x, bs.y, bsHeightM, bs.azimuth_deg, sectorRadius),
        material: Cesium.Color.CYAN.withAlpha(0.12),
        outline: true,
        outlineColor: Cesium.Color.CYAN.withAlpha(0.5),
        perPositionHeight: true,
      },
    });

    addBeamCone(
      toWorld, viewer.entities, bs.x, bs.y, bsHeightM,
      bs.azimuth_deg, scene.downtilt_deg, arrowLenM, Cesium.Color.ORANGE
    );
  }

  // UE (illustrative scatter, deterministically seeded — see
  // demo_scene.py).
  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, ueHeightM),
      point: { pixelSize: 3, color: Cesium.Color.fromCssColorString("#ff6b6b").withAlpha(0.85) },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(
    `rendered real ${scene.topology_type} scene from SHARC engine: ` +
      `${scene.base_stations.length} BS/sectors, ${scene.hex_centers.length} cells, ` +
      `${scene.ue_positions.length} UE`
  );
}

function renderIndoorScene(scene) {
  const { toWorld, orientation } = makeEnuHelpers(scene.reference);

  // Buildings as extruded boxes. Box dimensions are in the entity's own
  // local frame, so giving every building the same ENU orientation
  // (derived from the single scene reference point) is a fine
  // approximation at this scale (a handful of buildings within a few
  // hundred meters of each other).
  for (const b of scene.buildings) {
    const totalHeight = b.floor_height * b.num_floors;
    const centerWorld = toWorld(b.x0 + b.width / 2, b.y0 + b.depth / 2, totalHeight / 2);
    viewer.entities.add({
      position: centerWorld,
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(b.width, b.depth, totalHeight),
        material: Cesium.Color.fromCssColorString("#d4a574").withAlpha(0.55),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#8a6d3b"),
      },
    });
  }

  for (const bs of scene.base_stations) {
    viewer.entities.add({
      position: toWorld(bs.x, bs.y, bs.z),
      point: { pixelSize: 6, color: Cesium.Color.BLUE, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
    });
  }

  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, ue.z),
      point: { pixelSize: 3, color: Cesium.Color.fromCssColorString("#ff6b6b").withAlpha(0.85) },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(
    `rendered real ${scene.topology_type} scene from SHARC engine: ` +
      `${scene.buildings.length} buildings, ${scene.base_stations.length} BS, ` +
      `${scene.ue_positions.length} UE`
  );
}

function renderSingleSpaceStationScene(scene) {
  // Genuinely global coordinates — no local ENU anchor here. Cesium places
  // lat/lon/alt directly; this is the scene type Cesium is actually built
  // for (versus the ENU-anchor trick used for terrestrial topologies,
  // which don't have real-world coordinates of their own).
  const sat = scene.satellite;
  const es = scene.earth_station;
  const satWorld = Cesium.Cartesian3.fromDegrees(sat.lon_deg, sat.lat_deg, sat.alt_m);
  const esWorld = Cesium.Cartesian3.fromDegrees(es.lon_deg, es.lat_deg, es.alt_m);

  viewer.entities.add({
    name: "Satellite",
    position: satWorld,
    point: { pixelSize: 10, color: Cesium.Color.RED, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
  });
  viewer.entities.add({
    name: "Earth station",
    position: esWorld,
    point: { pixelSize: 8, color: Cesium.Color.CYAN, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
  });
  viewer.entities.add({
    polyline: { positions: [satWorld, esWorld], width: 2, material: Cesium.Color.ORANGE.withAlpha(0.8) },
  });

  if (scene.footprint && scene.footprint.length > 1) {
    const footprintPositions = Cesium.Cartesian3.fromDegreesArray(
      scene.footprint.flatMap((p) => [p.lon_deg, p.lat_deg])
    );
    viewer.entities.add({
      polyline: { positions: footprintPositions, width: 3, material: Cesium.Color.MAGENTA },
    });
    // Filled illuminated area (not just the boundary outline) — the actual
    // patch of Earth the antenna's beamwidth covers.
    viewer.entities.add({
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(footprintPositions),
        material: Cesium.Color.MAGENTA.withAlpha(0.12),
        outline: false,
      },
    });
    // Beam volume: a handful of lines from the satellite down to its own
    // footprint boundary, so the cone connecting satellite -> illuminated
    // area is visible (not just an outline floating on the globe).
    const beamStep = Math.max(1, Math.floor(footprintPositions.length / 12));
    for (let i = 0; i < footprintPositions.length; i += beamStep) {
      viewer.entities.add({
        polyline: {
          positions: [satWorld, footprintPositions[i]],
          width: 1,
          material: Cesium.Color.MAGENTA.withAlpha(0.25),
        },
      });
    }
  }

  // Country borders (Natural Earth 110m, same shapefile the Matplotlib
  // renderer uses — see core/cesium_bridge.py: _borders_dict). Only present
  // when "Show country borders" is checked.
  if (scene.borders && scene.borders.length > 0) {
    for (const b of scene.borders) {
      if (b.lat_deg.length < 2) continue;
      const positions = Cesium.Cartesian3.fromDegreesArray(
        b.lat_deg.flatMap((lat, i) => [b.lon_deg[i], lat])
      );
      viewer.entities.add({
        polyline: {
          positions,
          width: b.selected ? 2.5 : 1,
          material: b.selected ? Cesium.Color.LIME : Cesium.Color.WHITE.withAlpha(0.6),
        },
      });
    }
  }

  // Macro_countries also comes through here (same global scene shape as
  // SINGLE_SPACE_STATION — satellite/earth_station/footprint — plus this).
  if (scene.country_bs && scene.country_bs.length > 0) {
    for (const bs of scene.country_bs) {
      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(bs.lon_deg, bs.lat_deg),
        point: { pixelSize: 4, color: Cesium.Color.fromCssColorString("#4fc3f7").withAlpha(0.9) },
      });
    }
  }

  viewer.zoomTo(viewer.entities);
  let statusMsg =
    `rendered real ${scene.topology_type} scene from SHARC engine: ` +
    `satellite at (${sat.lat_deg.toFixed(1)}, ${sat.lon_deg.toFixed(1)}), ` +
    `footprint with ${scene.footprint.length} pts`;
  if (scene.country_bs) {
    statusMsg += `, ${scene.country_bs.length} country BS`;
  }
  if (scene.borders) {
    statusMsg += `, ${scene.borders.length} border rings`;
  }
  setStatus(statusMsg);
}

function renderD2DScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  const z = scene.ue_height_m;
  const devices = scene.devices;

  const colors = [Cesium.Color.fromCssColorString("#66bb6a"), Cesium.Color.fromCssColorString("#ab47bc")];
  const worldPositions = devices.map((d) => toWorld(d.x, d.y, z));

  worldPositions.forEach((pos, i) => {
    viewer.entities.add({
      name: `Device ${i + 1}`,
      position: pos,
      point: { pixelSize: 9, color: colors[i % colors.length], outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
    });
  });

  if (worldPositions.length > 1) {
    viewer.entities.add({
      polyline: {
        positions: worldPositions,
        width: 3,
        material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.ORANGE }),
      },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(`rendered real MSS_D2D scene from SHARC engine: ${devices.length} devices`);
}

function renderSingleStationScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  const s = scene.station;
  const worldPos = toWorld(s.x, s.y, s.z);

  viewer.entities.add({
    name: "Single Earth Station",
    position: worldPos,
    point: { pixelSize: 10, color: Cesium.Color.RED, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
  });

  viewer.zoomTo(viewer.entities);
  setStatus(
    `rendered real ${scene.topology_type} scene from SHARC engine: ` +
      `station at local (${s.x.toFixed(0)}, ${s.y.toFixed(0)}) m`
  );
}

function renderNtnScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);

  // Hex cell outline around each anchor point (same tessellation as
  // renderHexSectorScene, radius = cell_radius) — matches the legacy
  // Matplotlib/Plotly NTN renderer's "Sector Cells" hexagons.
  for (const ap of scene.anchor_points) {
    const positions = [];
    for (let i = 0; i <= 6; i++) {
      const angle = Cesium.Math.toRadians(30 + i * 60);
      positions.push(
        toWorld(ap.x + scene.hex_radius_m * Math.cos(angle), ap.y + scene.hex_radius_m * Math.sin(angle), 0)
      );
    }
    viewer.entities.add({
      polyline: { positions, width: 1, material: Cesium.Color.SLATEBLUE.withAlpha(0.6) },
    });
    viewer.entities.add({
      position: toWorld(ap.x, ap.y, 0),
      point: { pixelSize: 5, color: Cesium.Color.LIGHTGRAY, outlineColor: Cesium.Color.BLACK, outlineWidth: 1 },
    });
  }

  const satLocal = scene.satellite;
  const satWorld = toWorld(satLocal.x, satLocal.y, satLocal.z);
  const groundBelowSat = toWorld(satLocal.x, satLocal.y, 0);
  const originWorld = toWorld(0, 0, 0);

  viewer.entities.add({
    name: `Satellite (el=${scene.elevation_deg.toFixed(0)}°)`,
    position: satWorld,
    point: { pixelSize: 10, color: Cesium.Color.fromCssColorString("#ff5252"), outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
  });
  viewer.entities.add({
    polyline: { positions: [groundBelowSat, satWorld], width: 2, material: Cesium.Color.fromCssColorString("#4fc3f7") },
  });
  viewer.entities.add({
    polyline: {
      positions: [originWorld, satWorld], width: 2,
      material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.GREEN }),
    },
  });

  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, 0),
      point: { pixelSize: 3, color: Cesium.Color.fromCssColorString("#ff6b6b").withAlpha(0.85) },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(
    `rendered real NTN scene from SHARC engine: ${scene.anchor_points.length} anchors, ` +
      `slant range ${(scene.slant_range_m / 1000).toFixed(0)} km, ${scene.ue_positions.length} UE`
  );
}

function renderScene(scene) {
  viewer.entities.removeAll();
  if (scene.error) {
    setStatus("scene error: " + scene.error);
    return;
  }
  // Structural dispatch (by shape, not by an ever-growing name list) — the
  // Python side (core/cesium_bridge.py) produces one of four distinct
  // shapes regardless of which of the 15 SHARC topology/system types was
  // requested (MACROCELL, HOTSPOT, ..., EESS_SS, METSAT_SS, FSS_SS, ...).
  // Any global topology (satellite + earth station, real lat/lon/alt —
  // SINGLE_SPACE_STATION, Macro_countries, EESS_SS, METSAT_SS, FSS_SS, ...)
  // has a `satellite` key; that alone is enough to route it correctly.
  if (scene.buildings !== undefined) {
    renderIndoorScene(scene);
  } else if (scene.anchor_points !== undefined) {
    renderNtnScene(scene);
  } else if (scene.satellite !== undefined) {
    renderSingleSpaceStationScene(scene);
  } else if (scene.devices !== undefined) {
    renderD2DScene(scene);
  } else if (scene.station !== undefined) {
    renderSingleStationScene(scene);
  } else {
    renderHexSectorScene(scene);
  }
}

function requestScene(topologyType) {
  if (!window.pyBridge) return;
  setStatus(`requesting real ${topologyType} scene…`);
  window.pyBridge.get_scene(topologyType, function (json) {
    try {
      renderScene(JSON.parse(json));
    } catch (e) {
      setStatus("FAILED to render scene: " + e);
    }
  });
}

document.getElementById("topoSelect").addEventListener("change", function (event) {
  requestScene(event.target.value);
});

// Cesium defaults to continuous rendering, which is what we want while
// getting the spike visually right. requestRenderMode (see the
// performance section of CESIUMJS_MIGRATION_PLAN.md) is a later
// optimization, deliberately not enabled here yet.
viewer.scene.requestRender();

setStatus("viewer ready, offline (no network requests made)");

// --- QWebChannel bridge: proves Python <-> JS round trip works without any
// server-side push mechanism yet (that comes with the Interaction Layer,
// Fase 5). ---
if (typeof qt !== "undefined" && qt.webChannelTransport) {
  new QWebChannel(qt.webChannelTransport, function (channel) {
    const pyBridge = channel.objects.pyBridge;
    if (!pyBridge) {
      setStatus("viewer ready (no pyBridge object registered)");
      return;
    }
    window.pyBridge = pyBridge;
    pyBridge.pong.connect(function (message) {
      setStatus("pong from Python: " + message);
    });
    setStatus("viewer ready, QWebChannel connected");
    if (!isEmbedded) {
      // Embedded mode: Python calls CesiumSpikeWidget.request_scene(...)
      // once the real scenario/topology is known — no default to guess here.
      requestScene(document.getElementById("topoSelect").value);
    }
  });
} else {
  setStatus("viewer ready (qwebchannel transport not available — opened outside Qt?)");
}
