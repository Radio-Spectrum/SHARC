// SHARC Preview — CesiumJS (Fase 2/3+ of CESIUMJS_MIGRATION_PLAN.md).

const statusEl = document.getElementById("status");
const isEmbedded = new URLSearchParams(window.location.search).get("embedded") === "1";

if (isEmbedded) {
  document.getElementById("topoPicker").style.display = "none";
}

function setStatus(text) {
  statusEl.textContent = text;
  console.log("[cesium_spike]", text);
}

window.addEventListener("error", function (event) {
  setStatus("JS ERROR: " + event.message);
});

setStatus("creating viewer (offline mode)…");

const worldBasemap = new Cesium.SingleTileImageryProvider({
  url: "./assets/world_basemap.jpg",
  tileWidth: 4096,
  tileHeight: 2048,
  rectangle: Cesium.Rectangle.MAX_VALUE,
});

let viewer;
try {
  viewer = new Cesium.Viewer("cesiumContainer", {
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

viewer.scene.globe.enableLighting = false;
viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#1a3a5c");
viewer.scene.skyAtmosphere.show = true;
viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#070b14");
viewer.scene.globe.showGroundAtmosphere = true;

viewer.camera.setView({
  destination: Cesium.Cartesian3.fromDegrees(-47.0, -15.0, 25000000),
});

// ═══════════════════════════════════════════════════════════════════
// Reference layers (cities + graticule) — kept in separate DataSources
// so they persist across topology switches (viewer.entities.removeAll
// only clears the default entity collection).
// ═══════════════════════════════════════════════════════════════════

const cityDataSource = new Cesium.CustomDataSource("cities");
viewer.dataSources.add(cityDataSource);

const graticuleDataSource = new Cesium.CustomDataSource("graticule");
viewer.dataSources.add(graticuleDataSource);

const WORLD_CITIES = [
  // Americas
  { name: "New York", lat: 40.71, lon: -74.01 },
  { name: "Los Angeles", lat: 34.05, lon: -118.24 },
  { name: "Chicago", lat: 41.88, lon: -87.63 },
  { name: "Mexico City", lat: 19.43, lon: -99.13 },
  { name: "Toronto", lat: 43.65, lon: -79.38 },
  { name: "São Paulo", lat: -23.55, lon: -46.63 },
  { name: "Rio de Janeiro", lat: -22.91, lon: -43.17 },
  { name: "Brasília", lat: -15.79, lon: -47.88 },
  { name: "Buenos Aires", lat: -34.60, lon: -58.38 },
  { name: "Lima", lat: -12.05, lon: -77.04 },
  { name: "Bogotá", lat: 4.71, lon: -74.07 },
  { name: "Santiago", lat: -33.45, lon: -70.67 },
  // Europe
  { name: "London", lat: 51.51, lon: -0.13 },
  { name: "Paris", lat: 48.86, lon: 2.35 },
  { name: "Berlin", lat: 52.52, lon: 13.41 },
  { name: "Madrid", lat: 40.42, lon: -3.70 },
  { name: "Rome", lat: 41.90, lon: 12.50 },
  { name: "Moscow", lat: 55.76, lon: 37.62 },
  { name: "Istanbul", lat: 41.01, lon: 28.98 },
  { name: "Lisbon", lat: 38.72, lon: -9.14 },
  // Africa
  { name: "Cairo", lat: 30.04, lon: 31.24 },
  { name: "Lagos", lat: 6.52, lon: 3.38 },
  { name: "Johannesburg", lat: -26.20, lon: 28.05 },
  { name: "Nairobi", lat: -1.29, lon: 36.82 },
  { name: "Cape Town", lat: -33.93, lon: 18.42 },
  // Asia
  { name: "Tokyo", lat: 35.68, lon: 139.69 },
  { name: "Beijing", lat: 39.90, lon: 116.40 },
  { name: "Shanghai", lat: 31.23, lon: 121.47 },
  { name: "Mumbai", lat: 19.08, lon: 72.88 },
  { name: "Delhi", lat: 28.61, lon: 77.21 },
  { name: "Seoul", lat: 37.57, lon: 126.98 },
  { name: "Singapore", lat: 1.35, lon: 103.82 },
  { name: "Dubai", lat: 25.20, lon: 55.27 },
  { name: "Bangkok", lat: 13.76, lon: 100.50 },
  { name: "Jakarta", lat: -6.21, lon: 106.85 },
  { name: "Tehran", lat: 35.69, lon: 51.39 },
  // Oceania
  { name: "Sydney", lat: -33.87, lon: 151.21 },
  { name: "Melbourne", lat: -37.81, lon: 144.96 },
  { name: "Auckland", lat: -36.85, lon: 174.76 },
];

(function addCityLabels() {
  const cityColor = Cesium.Color.fromCssColorString("#ffd54f");
  const cityOutline = Cesium.Color.fromCssColorString("#c68400");
  for (const city of WORLD_CITIES) {
    cityDataSource.entities.add({
      position: Cesium.Cartesian3.fromDegrees(city.lon, city.lat, 0),
      label: {
        text: city.name,
        font: "bold 11px 'Segoe UI', Arial, sans-serif",
        fillColor: Cesium.Color.WHITE.withAlpha(0.95),
        outlineColor: Cesium.Color.BLACK.withAlpha(0.8),
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -8),
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 25000000),
        scaleByDistance: new Cesium.NearFarScalar(500000, 1.0, 20000000, 0.45),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      point: {
        pixelSize: 5,
        color: cityColor,
        outlineColor: cityOutline,
        outlineWidth: 1.5,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 25000000),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
  }
})();

(function addGraticule() {
  const gridColor = Cesium.Color.WHITE.withAlpha(0.08);
  const majorGridColor = Cesium.Color.WHITE.withAlpha(0.15);
  // Latitude lines
  for (let lat = -60; lat <= 60; lat += 30) {
    const positions = [];
    for (let lon = -180; lon <= 180; lon += 3) {
      positions.push(Cesium.Cartesian3.fromDegrees(lon, lat, 100));
    }
    graticuleDataSource.entities.add({
      polyline: {
        positions,
        width: lat === 0 ? 1.5 : 1,
        material: lat === 0 ? majorGridColor : gridColor,
      },
    });
  }
  // Longitude lines
  for (let lon = -180; lon < 180; lon += 30) {
    const positions = [];
    for (let lat = -85; lat <= 85; lat += 3) {
      positions.push(Cesium.Cartesian3.fromDegrees(lon, lat, 100));
    }
    graticuleDataSource.entities.add({
      polyline: {
        positions,
        width: lon === 0 ? 1.5 : 1,
        material: lon === 0 ? majorGridColor : gridColor,
      },
    });
  }
})();

// ═══════════════════════════════════════════════════════════════════
// Color palette — cohesive scheme for all topology renderers
// ═══════════════════════════════════════════════════════════════════

const C = {
  bs:          Cesium.Color.fromCssColorString("#4fc3f7"),   // light blue
  bsOutline:   Cesium.Color.WHITE,
  ue:          Cesium.Color.fromCssColorString("#ef5350"),   // warm red
  hex:         Cesium.Color.fromCssColorString("#7986cb"),   // indigo
  sector:      Cesium.Color.fromCssColorString("#4fc3f7"),   // cyan
  beam:        Cesium.Color.fromCssColorString("#ffd54f"),   // amber
  mast:        Cesium.Color.fromCssColorString("#90a4ae"),   // steel
  satellite:   Cesium.Color.fromCssColorString("#ff1744"),   // vivid red
  station:     Cesium.Color.fromCssColorString("#00e5ff"),   // electric cyan
  footprint:   Cesium.Color.fromCssColorString("#e040fb"),   // magenta
  link:        Cesium.Color.fromCssColorString("#ffab00"),   // amber
  building:    Cesium.Color.fromCssColorString("#d4a574"),   // sandstone
  buildingOut: Cesium.Color.fromCssColorString("#8a6d3b"),   // dark wood
  ntnAnchor:   Cesium.Color.fromCssColorString("#b0bec5"),   // blue-grey
  d2dA:        Cesium.Color.fromCssColorString("#66bb6a"),   // green
  d2dB:        Cesium.Color.fromCssColorString("#ab47bc"),   // purple
  borderSel:   Cesium.Color.fromCssColorString("#76ff03"),   // lime
  borderDef:   Cesium.Color.WHITE.withAlpha(0.5),
  countryBs:   Cesium.Color.fromCssColorString("#4fc3f7"),
};

// ═══════════════════════════════════════════════════════════════════
// ENU helpers (local → world coordinate transform)
// ═══════════════════════════════════════════════════════════════════

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

// ═══════════════════════════════════════════════════════════════════
// Geometry helpers (beam cone, sector wedge)
// ═══════════════════════════════════════════════════════════════════

function unit3(v) {
  const n = Math.hypot(v[0], v[1], v[2]);
  return n > 0 ? [v[0] / n, v[1] / n, v[2] / n] : v;
}

function cross3(a, b) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

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

  entities.add({
    polygon: {
      hierarchy: baseWorld,
      material: color.withAlpha(0.2),
      outline: false,
      perPositionHeight: true,
    },
  });
  const radialStep = Math.max(1, Math.floor(base.length / 8));
  for (let i = 0; i < base.length; i += radialStep) {
    entities.add({
      polyline: { positions: [apexWorld, baseWorld[i]], width: 1, material: color.withAlpha(0.55) },
    });
  }
}

// ═══════════════════════════════════════════════════════════════════
// Gain Map (antenna heatmap) — turbo colormap + rectangle entities
// ═══════════════════════════════════════════════════════════════════

const TURBO_STOPS = [
  [0.00, 0.19, 0.07, 0.23],
  [0.07, 0.23, 0.17, 0.45],
  [0.15, 0.25, 0.39, 0.76],
  [0.22, 0.18, 0.53, 0.90],
  [0.30, 0.11, 0.73, 0.80],
  [0.37, 0.20, 0.83, 0.63],
  [0.45, 0.36, 0.91, 0.44],
  [0.52, 0.57, 0.96, 0.33],
  [0.60, 0.78, 0.94, 0.20],
  [0.67, 0.92, 0.85, 0.14],
  [0.75, 0.98, 0.70, 0.12],
  [0.82, 0.99, 0.53, 0.13],
  [0.90, 0.87, 0.30, 0.12],
  [1.00, 0.64, 0.12, 0.11],
];

function turboColor(t) {
  t = Math.max(0, Math.min(1, t));
  let lo = 0;
  for (let i = 0; i < TURBO_STOPS.length - 1; i++) {
    if (t >= TURBO_STOPS[i][0] && t <= TURBO_STOPS[i + 1][0]) { lo = i; break; }
  }
  const hi = Math.min(lo + 1, TURBO_STOPS.length - 1);
  const range = TURBO_STOPS[hi][0] - TURBO_STOPS[lo][0];
  const f = range > 0 ? (t - TURBO_STOPS[lo][0]) / range : 0;
  return new Cesium.Color(
    TURBO_STOPS[lo][1] + f * (TURBO_STOPS[hi][1] - TURBO_STOPS[lo][1]),
    TURBO_STOPS[lo][2] + f * (TURBO_STOPS[hi][2] - TURBO_STOPS[lo][2]),
    TURBO_STOPS[lo][3] + f * (TURBO_STOPS[hi][3] - TURBO_STOPS[lo][3]),
    0.55
  );
}

function renderGainMap(scene) {
  if (!scene.gain_map || !scene.gain_map.cells || scene.gain_map.cells.length === 0) return;
  const step = scene.gain_map.step || 2.0;
  const half = step / 2.0;
  for (const cell of scene.gain_map.cells) {
    viewer.entities.add({
      rectangle: {
        coordinates: Cesium.Rectangle.fromDegrees(
          cell.lon - half, cell.lat - half,
          cell.lon + half, cell.lat + half
        ),
        material: turboColor(cell.v),
        outline: false,
        height: 0,
      },
    });
  }
}

// ═══════════════════════════════════════════════════════════════════
// Topology renderers
// ═══════════════════════════════════════════════════════════════════

function renderHexSectorScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  const bsHeightM = scene.bs_height_m;
  const ueHeightM = scene.ue_height_m;
  const arrowLenM = scene.hex_radius_m * 0.6;

  // Hex cells
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
      polyline: { positions, width: 1.5, material: C.hex.withAlpha(0.5) },
    });
    // Subtle hex fill
    viewer.entities.add({
      polygon: {
        hierarchy: positions,
        material: C.hex.withAlpha(0.04),
        outline: false,
      },
    });
  }

  // Base stations
  const sectorRadius = Math.max(scene.hex_radius_m * 0.85, arrowLenM);
  for (const bs of scene.base_stations) {
    const groundPos = toWorld(bs.x, bs.y, 0);
    const worldPos = toWorld(bs.x, bs.y, bsHeightM);

    // Mast
    viewer.entities.add({
      polyline: { positions: [groundPos, worldPos], width: 2, material: C.mast },
    });
    // Antenna point
    viewer.entities.add({
      position: worldPos,
      point: { pixelSize: 7, color: C.bs, outlineColor: C.bsOutline, outlineWidth: 1 },
    });

    // Sector wedge
    viewer.entities.add({
      polygon: {
        hierarchy: sectorWedgePositions(toWorld, bs.x, bs.y, bsHeightM, bs.azimuth_deg, sectorRadius),
        material: C.sector.withAlpha(0.1),
        outline: true,
        outlineColor: C.sector.withAlpha(0.45),
        perPositionHeight: true,
      },
    });

    // Beam cone
    addBeamCone(
      toWorld, viewer.entities, bs.x, bs.y, bsHeightM,
      bs.azimuth_deg, scene.downtilt_deg, arrowLenM, C.beam
    );
  }

  // UE scatter
  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, ueHeightM),
      point: { pixelSize: 3.5, color: C.ue.withAlpha(0.8) },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(
    `${scene.topology_type}: ${scene.base_stations.length} BS, ` +
      `${scene.hex_centers.length} cells, ${scene.ue_positions.length} UE`
  );
}

function renderIndoorScene(scene) {
  const { toWorld, orientation } = makeEnuHelpers(scene.reference);

  for (const b of scene.buildings) {
    const totalHeight = b.floor_height * b.num_floors;
    const centerWorld = toWorld(b.x0 + b.width / 2, b.y0 + b.depth / 2, totalHeight / 2);
    viewer.entities.add({
      position: centerWorld,
      orientation,
      box: {
        dimensions: new Cesium.Cartesian3(b.width, b.depth, totalHeight),
        material: C.building.withAlpha(0.5),
        outline: true,
        outlineColor: C.buildingOut,
      },
    });
    // Floor lines
    for (let f = 1; f < b.num_floors; f++) {
      const fz = b.floor_height * f;
      const corners = [
        toWorld(b.x0, b.y0, fz), toWorld(b.x0 + b.width, b.y0, fz),
        toWorld(b.x0 + b.width, b.y0 + b.depth, fz), toWorld(b.x0, b.y0 + b.depth, fz),
        toWorld(b.x0, b.y0, fz),
      ];
      viewer.entities.add({
        polyline: { positions: corners, width: 1, material: C.buildingOut.withAlpha(0.3) },
      });
    }
  }

  for (const bs of scene.base_stations) {
    viewer.entities.add({
      position: toWorld(bs.x, bs.y, bs.z),
      point: { pixelSize: 6, color: C.bs, outlineColor: C.bsOutline, outlineWidth: 1 },
    });
  }

  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, ue.z),
      point: { pixelSize: 3.5, color: C.ue.withAlpha(0.8) },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(
    `INDOOR: ${scene.buildings.length} buildings, ${scene.base_stations.length} BS, ` +
      `${scene.ue_positions.length} UE`
  );
}

function renderSingleSpaceStationScene(scene) {
  const sat = scene.satellite;
  const es = scene.earth_station;
  const isMacroCountries = scene.topology_type === "Macro_countries";
  const satWorld = Cesium.Cartesian3.fromDegrees(sat.lon_deg, sat.lat_deg, sat.alt_m);
  const esWorld = Cesium.Cartesian3.fromDegrees(es.lon_deg, es.lat_deg, es.alt_m);

  // Gain map (heatmap) — rendered first so it sits under other elements
  renderGainMap(scene);

  // Satellite
  viewer.entities.add({
    name: "Satellite",
    position: satWorld,
    point: { pixelSize: 14, color: C.satellite, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: {
      text: "SAT",
      font: "bold 13px 'Segoe UI', Arial, sans-serif",
      fillColor: C.satellite,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -16),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  if (!isMacroCountries) {
    // Earth station (only for non-Macro_countries)
    viewer.entities.add({
      name: "Earth Station",
      position: esWorld,
      point: { pixelSize: 10, color: C.station, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
      label: {
        text: "ES",
        font: "bold 11px 'Segoe UI', Arial, sans-serif",
        fillColor: C.station,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -12),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    // Link line SAT → ES (straight 3D line, not geodesic)
    viewer.entities.add({
      polyline: {
        positions: [satWorld, esWorld], width: 2.5,
        material: C.link.withAlpha(0.85),
        arcType: Cesium.ArcType.NONE,
      },
    });
  }

  // Footprint
  if (scene.footprint && scene.footprint.length > 1) {
    const footprintPositions = Cesium.Cartesian3.fromDegreesArray(
      scene.footprint.flatMap((p) => [p.lon_deg, p.lat_deg])
    );
    viewer.entities.add({
      polyline: { positions: footprintPositions, width: 3, material: C.footprint },
    });
    viewer.entities.add({
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(footprintPositions),
        material: C.footprint.withAlpha(0.1),
        outline: false,
      },
    });
    // Beam volume lines — straight in 3D space
    const beamStep = Math.max(1, Math.floor(footprintPositions.length / 16));
    for (let i = 0; i < footprintPositions.length; i += beamStep) {
      viewer.entities.add({
        polyline: {
          positions: [satWorld, footprintPositions[i]],
          width: 1,
          material: C.footprint.withAlpha(0.2),
          arcType: Cesium.ArcType.NONE,
        },
      });
    }
  }

  // Country borders
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
          material: b.selected ? C.borderSel : C.borderDef,
        },
      });
    }
  }

  // Country BS (Macro_countries) — larger dots + triangle markers
  if (scene.country_bs && scene.country_bs.length > 0) {
    for (const bs of scene.country_bs) {
      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(bs.lon_deg, bs.lat_deg, 0),
        point: { pixelSize: 6, color: C.countryBs, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
      });
    }
    // Link lines from satellite to BS centroid area
    if (scene.bs_centroid) {
      const centroidWorld = Cesium.Cartesian3.fromDegrees(scene.bs_centroid.lon_deg, scene.bs_centroid.lat_deg, 0);
      viewer.entities.add({
        polyline: {
          positions: [satWorld, centroidWorld], width: 2.5,
          material: new Cesium.PolylineDashMaterialProperty({ color: C.link }),
          arcType: Cesium.ArcType.NONE,
        },
      });
      viewer.entities.add({
        position: centroidWorld,
        point: { pixelSize: 8, color: C.link, outlineColor: Cesium.Color.WHITE, outlineWidth: 1.5 },
        label: {
          text: `${scene.country_bs.length} BS`,
          font: "bold 11px 'Segoe UI', Arial, sans-serif",
          fillColor: C.link,
          outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(0, -12),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    }
  }

  viewer.zoomTo(viewer.entities);
  let statusMsg =
    `${scene.topology_type}: satellite (${sat.lat_deg.toFixed(1)}°, ${sat.lon_deg.toFixed(1)}°), ` +
    `footprint ${scene.footprint.length} pts`;
  if (scene.country_bs) statusMsg += `, ${scene.country_bs.length} BS`;
  if (scene.borders) statusMsg += `, ${scene.borders.length} borders`;
  if (scene.gain_map) statusMsg += `, gain map ${scene.gain_map.cells.length} cells`;
  setStatus(statusMsg);
}

function renderD2DScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  const z = scene.ue_height_m;
  const devices = scene.devices;

  const colors = [C.d2dA, C.d2dB];
  const worldPositions = devices.map((d) => toWorld(d.x, d.y, z));

  worldPositions.forEach((pos, i) => {
    viewer.entities.add({
      name: `Device ${i + 1}`,
      position: pos,
      point: { pixelSize: 10, color: colors[i % colors.length], outlineColor: Cesium.Color.WHITE, outlineWidth: 1.5 },
      label: {
        text: `D${i + 1}`,
        font: "bold 11px 'Segoe UI', Arial, sans-serif",
        fillColor: colors[i % colors.length],
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -12),
      },
    });
  });

  if (worldPositions.length > 1) {
    viewer.entities.add({
      polyline: {
        positions: worldPositions,
        width: 3,
        material: new Cesium.PolylineDashMaterialProperty({ color: C.link }),
      },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(`MSS_D2D: ${devices.length} devices`);
}

function renderSingleStationScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  const s = scene.station;
  const worldPos = toWorld(s.x, s.y, s.z);
  const groundPos = toWorld(s.x, s.y, 0);

  // Mast / pedestal
  viewer.entities.add({
    polyline: { positions: [groundPos, worldPos], width: 3, material: C.mast },
  });

  // Station point — cyan (C.station), distinct from satellite red
  viewer.entities.add({
    name: "Single Earth Station",
    position: worldPos,
    point: { pixelSize: 14, color: C.station, outlineColor: Cesium.Color.WHITE, outlineWidth: 2.5 },
    label: {
      text: "ES",
      font: "bold 13px 'Segoe UI', Arial, sans-serif",
      fillColor: C.station,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -16),
    },
  });

  // Coverage / reception circle on the ground
  const coverageRadius = Math.max(50, s.z * 3);
  const circleSegments = 36;
  const circlePositions = [];
  for (let i = 0; i <= circleSegments; i++) {
    const ang = (2 * Math.PI * i) / circleSegments;
    circlePositions.push(toWorld(s.x + coverageRadius * Math.cos(ang), s.y + coverageRadius * Math.sin(ang), 0));
  }
  viewer.entities.add({
    polyline: { positions: circlePositions, width: 1.5, material: C.station.withAlpha(0.4) },
  });
  viewer.entities.add({
    polygon: {
      hierarchy: circlePositions,
      material: C.station.withAlpha(0.06),
      outline: false,
    },
  });

  // Antenna pointing direction (elevation cone toward sky)
  const elDeg = scene.antenna_elevation_deg || 25;
  const azDeg = scene.antenna_azimuth_deg || 0;
  const coneLen = coverageRadius * 1.5;
  addBeamCone(toWorld, viewer.entities, s.x, s.y, s.z, azDeg, -elDeg, coneLen,
    Cesium.Color.fromCssColorString("#4dd0e1"), 15);

  viewer.zoomTo(viewer.entities);
  setStatus(
    `SINGLE_EARTH_STATION: at (${s.x.toFixed(0)}, ${s.y.toFixed(0)}) m, el=${elDeg.toFixed(0)}°`
  );
}

function renderNtnScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);

  // Hex cells around anchor points
  for (const ap of scene.anchor_points) {
    const positions = [];
    for (let i = 0; i <= 6; i++) {
      const angle = Cesium.Math.toRadians(30 + i * 60);
      positions.push(
        toWorld(ap.x + scene.hex_radius_m * Math.cos(angle), ap.y + scene.hex_radius_m * Math.sin(angle), 0)
      );
    }
    viewer.entities.add({
      polyline: { positions, width: 1.5, material: C.hex.withAlpha(0.5) },
    });
    viewer.entities.add({
      polygon: { hierarchy: positions, material: C.hex.withAlpha(0.04), outline: false },
    });
    viewer.entities.add({
      position: toWorld(ap.x, ap.y, 0),
      point: { pixelSize: 5, color: C.ntnAnchor, outlineColor: Cesium.Color.BLACK, outlineWidth: 1 },
    });
  }

  // Satellite
  const satLocal = scene.satellite;
  const satWorld = toWorld(satLocal.x, satLocal.y, satLocal.z);
  const groundBelowSat = toWorld(satLocal.x, satLocal.y, 0);
  const originWorld = toWorld(0, 0, 0);

  viewer.entities.add({
    name: `Satellite (el=${scene.elevation_deg.toFixed(0)}°)`,
    position: satWorld,
    point: { pixelSize: 12, color: C.satellite, outlineColor: Cesium.Color.WHITE, outlineWidth: 2 },
    label: {
      text: `SAT  el=${scene.elevation_deg.toFixed(0)}°`,
      font: "bold 11px 'Segoe UI', Arial, sans-serif",
      fillColor: C.satellite,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -14),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  // Vertical projection line
  viewer.entities.add({
    polyline: { positions: [groundBelowSat, satWorld], width: 2, material: C.station.withAlpha(0.7) },
  });
  // Slant range line
  viewer.entities.add({
    polyline: {
      positions: [originWorld, satWorld], width: 2,
      material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.fromCssColorString("#69f0ae") }),
    },
  });

  // UE
  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, 0),
      point: { pixelSize: 3.5, color: C.ue.withAlpha(0.8) },
    });
  }

  viewer.zoomTo(viewer.entities);
  setStatus(
    `NTN: ${scene.anchor_points.length} anchors, ` +
      `slant ${(scene.slant_range_m / 1000).toFixed(0)} km, ${scene.ue_positions.length} UE`
  );
}

// ═══════════════════════════════════════════════════════════════════
// Scene dispatcher + QWebChannel bridge
// ═══════════════════════════════════════════════════════════════════

function renderScene(scene) {
  viewer.entities.removeAll();
  if (scene.error) {
    setStatus("scene error: " + scene.error);
    return;
  }
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
  setStatus(`loading ${topologyType}…`);
  window.pyBridge.get_scene(topologyType, function (json) {
    try {
      renderScene(JSON.parse(json));
    } catch (e) {
      setStatus("render failed: " + e);
    }
  });
}

document.getElementById("topoSelect").addEventListener("change", function (event) {
  requestScene(event.target.value);
});

viewer.scene.requestRender();
setStatus("viewer ready — offline");

if (typeof qt !== "undefined" && qt.webChannelTransport) {
  new QWebChannel(qt.webChannelTransport, function (channel) {
    const pyBridge = channel.objects.pyBridge;
    if (!pyBridge) {
      setStatus("viewer ready (no pyBridge)");
      return;
    }
    window.pyBridge = pyBridge;
    pyBridge.pong.connect(function (message) {
      setStatus("pong: " + message);
    });
    setStatus("connected — waiting for scene");
    if (!isEmbedded) {
      requestScene(document.getElementById("topoSelect").value);
    }
  });
} else {
  setStatus("viewer ready (no QWebChannel — standalone browser?)");
}
