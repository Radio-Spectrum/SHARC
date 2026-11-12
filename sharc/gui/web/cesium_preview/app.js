// SHARC Preview — CesiumJS (Fase 2/3+ of CESIUMJS_MIGRATION_PLAN.md).

const statusEl = document.getElementById("status");
const isEmbedded = new URLSearchParams(window.location.search).get("embedded") === "1";

if (isEmbedded) {
  document.getElementById("topoPicker").style.display = "none";
}


// ── Global loading indicator: slim progress bar + label while tiles, relief, buildings, hydro or the scene load.
const Loading = (function () {
  const box = document.createElement("div");
  box.id = "loadBox";
  box.innerHTML = '<div id="loadLabel">Loading...</div><div id="loadTrack"><div id="loadFill"></div></div>';
  document.body.appendChild(box);
  const label = box.querySelector("#loadLabel"), fill = box.querySelector("#loadFill");
  const tasks = new Map();                 // name -> {done, total} ; total 0 = indeterminate
  let hideTimer = null;
  function render() {
    if (!tasks.size) { hideTimer = hideTimer || setTimeout(() => { box.classList.remove("on"); hideTimer = null; }, 350); return; }
    clearTimeout(hideTimer); hideTimer = null;
    box.classList.add("on");
    let done = 0, total = 0, indeterminate = false;
    const names = [];
    tasks.forEach((t, n) => { names.push(n); if (t.total > 0) { done += t.done; total += t.total; } else indeterminate = true; });
    label.textContent = "Loading " + names.join(", ") + "...";
    if (total > 0 && !indeterminate) { fill.classList.remove("ind"); fill.style.width = Math.max(4, 100 * done / total) + "%"; }
    else { fill.classList.add("ind"); fill.style.width = "35%"; }
  }
  return {
    set(name, done, total) { tasks.set(name, { done: done || 0, total: total || 0 }); render(); },
    end(name) { tasks.delete(name); render(); },
    async track(name, promise) { this.set(name, 0, 0); try { return await promise; } finally { this.end(name); } },
  };
})();
window.SharcLoading = Loading;

function setStatus(text) {
  statusEl.textContent = text;
  console.log("[cesium_spike]", text);
}

// Problems of the scene that the preview worked around (e.g. an antenna pattern the engine rejected): shown
// in amber under the status until the next scene, so a fallback is never mistaken for the real result
function showWarnings(list) {
  const el = document.getElementById("hudWarn");
  if (!el) return;
  const items = (list || []).filter(Boolean);
  el.textContent = items.map((w) => "Warning: " + w).join("\n");
  el.hidden = items.length === 0;
}

window.addEventListener("unhandledrejection", function (event) {
  console.error("UNHANDLED REJECTION: " + (event.reason && (event.reason.stack || event.reason.message) || event.reason));
});

window.addEventListener("error", function (event) {
  const stack = event.error && event.error.stack ? ` | ${String(event.error.stack).split("\n").slice(0, 3).join(" > ")}` : "";
  const where = (event.filename ? ` (${event.filename.split("/").pop()}:${event.lineno})` : "") + stack;
  console.error("JS ERROR: " + event.message + where);
  setStatus("JS ERROR: " + event.message + where);
});

setStatus("creating viewer (offline mode)…");

const params = new URLSearchParams(window.location.search);
const ION_TOKEN = params.get("ion") || "";
if (ION_TOKEN) {
  Cesium.Ion.defaultAccessToken = ION_TOKEN;
}

// ── Mapas-base: offline por padrão; satélite online é opcional ──
const BASEMAPS = [
  {
    id: "neii", name: "Natural Earth II", offline: true,
    make: () => Cesium.TileMapServiceImageryProvider.fromUrl(
      Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")),
  },
  {
    id: "dark", name: "Dark political", offline: true,
    make: () => Promise.resolve(new Cesium.SingleTileImageryProvider({
      url: "./assets/world_basemap.jpg", tileWidth: 4096, tileHeight: 2048,
      rectangle: Cesium.Rectangle.MAX_VALUE,
    })),
  },
  {
    id: "esri", name: "Esri World Imagery", offline: false,
    make: () => Promise.resolve(new Cesium.UrlTemplateImageryProvider({
      url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      maximumLevel: 19,
      credit: "Esri, Maxar, Earthstar Geographics",
    })),
  },
];
let currentBasemapId = null;

let viewer;
try {
  viewer = new Cesium.Viewer("cesiumContainer", {
    baseLayer: false,
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    infoBox: true,
    selectionIndicator: true,
    shouldAnimate: false,
    msaaSamples: 4,
    requestRenderMode: false,
  });
} catch (e) {
  setStatus("FAILED to construct Cesium.Viewer: " + e);
  throw e;
}

function setBasemap(id) {
  const def = BASEMAPS.find((b) => b.id === id) || BASEMAPS[0];
  def.make().then((provider) => {
    viewer.imageryLayers.removeAll();
    // A tile that fails (busy network, source timeout) is retried with a pause instead of staying blank.
    const request = provider.requestImage.bind(provider);
    provider.requestImage = async function (x, y, level, req) {
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          return await request(x, y, level, req);   // undefined = Cesium throttling, handled by Cesium
        } catch (e) { /* retry below */ }
        await new Promise((res) => setTimeout(res, 800 * (attempt + 1)));
      }
      throw new Error('tile unavailable');
    };
    const layer = viewer.imageryLayers.addImageryProvider(provider);
    layer.brightness = def.id === "esri" ? 1.0 : 1.08;
    layer.saturation = def.id === "dark" ? 1.0 : 1.12;
    currentBasemapId = def.id;
    viewer.scene.requestRender();
  }).catch((err) => {
    console.warn("[cesium_spike] basemap failed:", def.id, err);
    if (def.id !== "neii") setBasemap("neii");
  });
}
window.SharcBasemaps = {
  list: BASEMAPS.map((b) => ({ id: b.id, name: b.name, offline: b.offline })),
  current: () => currentBasemapId,
  set: setBasemap,
};
setBasemap(params.get("base") || "neii");

if (ION_TOKEN) {
  Cesium.createWorldTerrainAsync().then((t) => { viewer.terrainProvider = t; })
    .catch((err) => console.warn("[cesium_spike] world terrain failed:", err));
}

// ── Aparência realista: sol, atmosfera, névoa, bloom, antialias ──
const scene = viewer.scene;
scene.backgroundColor = Cesium.Color.fromCssColorString("#03050a");
scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1d33");
scene.renderError.addEventListener((sc, err) => console.error('RENDER ERROR: ' + (err && (err.stack || err.message) || err)));
scene.globe.enableLighting = true;
scene.globe.dynamicAtmosphereLighting = true;
scene.globe.dynamicAtmosphereLightingFromSun = true;
scene.globe.showGroundAtmosphere = true;
scene.globe.atmosphereLightIntensity = 14.0;
scene.globe.depthTestAgainstTerrain = false;
scene.globe.maximumScreenSpaceError = 1.5;
scene.skyAtmosphere.show = true;
scene.skyAtmosphere.brightnessShift = 0.05;
scene.fog.enabled = true;
scene.fog.density = 0.00018;
scene.sun.show = true;
scene.moon.show = true;
scene.highDynamicRange = true;
scene.postProcessStages.fxaa.enabled = true;
viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 2);

const bloom = scene.postProcessStages.bloom;
bloom.enabled = true;
bloom.uniforms.contrast = 128;
bloom.uniforms.brightness = -0.5;
bloom.uniforms.glowOnly = false;
bloom.uniforms.delta = 1.0;
bloom.uniforms.sigma = 2.6;
bloom.uniforms.stepSize = 1.0;

// ── Solo de análise: a base offline é de baixa resolução; ao aproximar a
// câmera (escala de célula), esmaece a imagem e deixa só a grade métrica. ──
function updateGroundMode() {
  try {
    const layer = viewer.imageryLayers.length ? viewer.imageryLayers.get(0) : null;
    if (!layer) return;
    const def = BASEMAPS.find((b) => b.id === currentBasemapId);
    const h = viewer.camera.positionCartographic.height;
    const near = 80000, far = 400000;                 // 80 km .. 400 km
    let a = 1.0;
    if (def && def.offline && h < far) {
      a = Cesium.Math.clamp((h - near) / (far - near), 0.0, 1.0) * 0.85 + 0.15;
    }
    layer.alpha = a;
    const cityDs = viewer.dataSources.getByName("cities")[0];
    if (cityDs && window.__citiesWanted !== false) cityDs.show = h > 600000;
    viewer.scene.requestRender();
  } catch (e) { /* sem imagem ainda */ }
}
viewer.camera.percentageChanged = 0.02;
viewer.camera.changed.addEventListener(updateGroundMode);
viewer.camera.moveEnd.addEventListener(updateGroundMode);

// Grade métrica local (referência de escala nas cenas locais).
function addLocalGrid(toWorld, extentM, stepM) {
  const n = Math.ceil(extentM / stepM);
  for (let i = -n; i <= n; i++) {
    const major = i % 5 === 0;
    const col = Cesium.Color.fromCssColorString(major ? "#6b7480" : "#3a4048").withAlpha(major ? 0.55 : 0.35);
    const c = i * stepM;
    viewer.entities.add({ polyline: { positions: [toWorld(c, -extentM, 0.5), toWorld(c, extentM, 0.5)], width: major ? 1.4 : 1, material: col } });
    viewer.entities.add({ polyline: { positions: [toWorld(-extentM, c, 0.5), toWorld(extentM, c, 0.5)], width: major ? 1.4 : 1, material: col } });
  }
}

// Sol sobre a América do Sul (luz do dia, terminador visível ao afastar).
viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2026-03-21T15:30:00Z");
viewer.clock.shouldAnimate = false;

viewer.camera.setView({
  destination: Cesium.Cartesian3.fromDegrees(-47.0, -15.0, 18000000),
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


// ═══════════════════════════════════════════════════════════════════
// 3D models (procedural glTF served by the local server)
// ═══════════════════════════════════════════════════════════════════
function modelOrientation(position, headingDeg, pitchDeg) {
  // Cesium: heading turns clockwise seen from above, 0 = East (the model's forward axis).
  const hpr = new Cesium.HeadingPitchRoll(
    Cesium.Math.toRadians(headingDeg), Cesium.Math.toRadians(pitchDeg), 0);
  return Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
}

// Orientation (Cesium model frame: X forward, Y left, Z up) that points a model's forward axis at `target`.
function orientToward(position, target) {
  const C3 = Cesium.Cartesian3;
  const f = C3.normalize(C3.subtract(target, position, new C3()), new C3());
  let up = C3.normalize(position, new C3());                          // radial up at the model
  up = C3.subtract(up, C3.multiplyByScalar(f, C3.dot(up, f), new C3()), new C3());
  if (C3.magnitude(up) < 1e-6) up = new C3(0, 0, 1);                  // looking straight down: any up works
  up = C3.normalize(up, new C3());
  const left = C3.cross(up, f, new C3());
  return Cesium.Quaternion.fromRotationMatrix(new Cesium.Matrix3(f.x, left.x, up.x, f.y, left.y, up.y, f.z, left.z, up.z));
}

function addModel(name, uri, position, headingDeg, pitchDeg, opts = {}) {
  return viewer.entities.add({
    name,
    position,
    orientation: modelOrientation(position, headingDeg, pitchDeg),
    model: {
      uri,
      scale: opts.scale || 1.0,
      minimumPixelSize: opts.minimumPixelSize || 0,
      maximumScale: opts.maximumScale || 20000,
      shadows: Cesium.ShadowMode.DISABLED,
      distanceDisplayCondition: opts.nearM ? new Cesium.DistanceDisplayCondition(0, opts.nearM) : undefined,
    },
  });
}

function glow(color, power = 0.22) {
  return new Cesium.PolylineGlowMaterialProperty({ glowPower: power, color });
}

function addBeamCone(toWorld, entities, bx, by, bz, azDeg, downtiltDeg, length, color, halfAngleDeg = 12) {
  const beamStart = entities.values.length;
  const { apex, base } = beamConePositions(bx, by, bz, azDeg, downtiltDeg, length, halfAngleDeg);
  const apexWorld = toWorld(apex[0], apex[1], apex[2]);
  const baseWorld = base.map((p) => toWorld(p[0], p[1], p[2]));

  entities.add({
    polygon: {
      hierarchy: baseWorld,
      material: color.withAlpha(0.16),
      outline: false,
      perPositionHeight: true,
    },
  });
  const radialStep = Math.max(1, Math.floor(base.length / 8));
  for (let i = 0; i < base.length; i += radialStep) {
    entities.add({
      polyline: { positions: [apexWorld, baseWorld[i]], width: 2.5, material: glow(color.withAlpha(0.85), 0.3) },
    });
  }
  for (const e of entities.values.slice(beamStart)) if (e.layer === undefined) tag(e, "beams");
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

// ── Colour-scale legends live in a detached Qt window (the 3D view only reports what is on screen)
// ── Show/hide layers: every entity tagged with `layer` can be toggled from the legend (state survives redraws)
const layerState = {};
function tag(ent, layer) { ent.layer = layer; if (layerState[layer] === false) ent.show = false; return ent; }
function setLayer(name, on) {
  layerState[name] = !!on;
  const all = viewer.entities.values.concat(warnSource.entities.values);
  for (const e of all) if (e.layer === name) e.show = !!on;
  if (name === "footprint" && !on && heat.mode.startsWith("sat_")) setHeat("");
  viewer.scene.requestRender();
}
function toggleLayer(name) { setLayer(name, layerState[name] === false); return layerState[name] !== false; }
function layerOn(name) { return layerState[name] !== false; }
window.setLayer = setLayer; window.toggleLayer = toggleLayer; window.layerOn = layerOn;

// Frame the whole scene (satellite + network + earth station), not only the IMT cells.
const frame = { points: [] };
// Home view. Aims at the point on the GROUND under the scene (never at a point in space) from the south, looking down.
// With a satellite in the scene the camera backs off far enough to keep it in frame.
function frameScene() {
  const C3 = Cesium.Cartesian3, rad = Cesium.Math.toRadians;
  const heightOf = (p) => Cesium.Cartographic.fromCartesian(p).height;
  let pts = frame.points.filter(Boolean);
  let ground = pts.filter((p) => heightOf(p) < 2.0e5);
  const far = pts.filter((p) => heightOf(p) >= 2.0e5);
  if (ground.length < 2 || Cesium.BoundingSphere.fromPoints(ground).radius < 150) {   // too little geometry: use every positioned entity
    const t = viewer.clock.currentTime;
    for (const e of viewer.entities.values) {
      const v = e.position && e.position.getValue ? e.position.getValue(t) : null;
      if (v && heightOf(v) < 2.0e5) ground.push(v);
    }
  }
  if (!ground.length) { viewer.zoomTo(viewer.entities); return; }
  const bs = Cesium.BoundingSphere.fromPoints(ground);
  const c = Cesium.Cartographic.fromCartesian(bs.center);
  const target = C3.fromRadians(c.longitude, c.latitude, 0);        // straight down to the surface
  const radius = Math.max(bs.radius, 250);
  if (far.length) {                                                // satellite: orbital view, spherical geometry
    // The tangent-plane offset of HeadingPitchRange breaks down at orbital range, so place the camera by hand: above and
    // south of the network, looking at the middle of the network-to-satellite segment, "up" pointing away from the Earth.
    const fb = Cesium.BoundingSphere.fromPoints(far);
    const dSat = C3.distance(target, fb.center) + fb.radius;
    const rHat = C3.normalize(target, new C3());
    const east = C3.normalize(C3.cross(new C3(0, 0, 1), rHat, new C3()), new C3());
    const south = C3.negate(C3.cross(rHat, east, new C3()), new C3());           // tangent, pointing south
    const th = rad(20), rc = Cesium.Ellipsoid.WGS84.maximumRadius + dSat * 2.0;
    const cp = C3.multiplyByScalar(
      C3.normalize(C3.add(C3.multiplyByScalar(rHat, Math.cos(th), new C3()), C3.multiplyByScalar(south, Math.sin(th), new C3()), new C3()), new C3()),
      rc, new C3());
    const mid = C3.midpoint(target, fb.center, new C3());
    const dir = C3.normalize(C3.subtract(mid, cp, new C3()), new C3());
    const pHat = C3.normalize(cp, new C3());
    const up = C3.normalize(C3.subtract(pHat, C3.multiplyByScalar(dir, C3.dot(pHat, dir), new C3()), new C3()), new C3());
    viewer.camera.flyTo({ destination: cp, orientation: { direction: dir, up }, duration: 1.4 });
    return;
  }
  const range = Math.max(radius * 2.6, 400);
  const pitch = rad(radius > 5.0e4 ? -60 : -45);
  viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(target, 1),
    { duration: 1.2, offset: new Cesium.HeadingPitchRange(0, pitch, range) });
}
window.frameScene = frameScene;

// Elevation [deg] of `satWorld` seen from the ground point (lat, lon).
function elevationDeg(latDeg, lonDeg, satWorld) {
  const ground = Cesium.Cartesian3.fromDegrees(lonDeg, latDeg, 0);
  const inv = Cesium.Matrix4.inverse(Cesium.Transforms.eastNorthUpToFixedFrame(ground), new Cesium.Matrix4());
  const l = Cesium.Matrix4.multiplyByPoint(inv, satWorld, new Cesium.Cartesian3());
  return Cesium.Math.toDegrees(Math.atan2(l.z, Math.hypot(l.x, l.y)));
}

// Tag the entities the scene renderers did not tag themselves, by what they are drawn as (towers and sector wedges: bs,
// small points: UEs, hex outlines / fills / circles: cells), so every legend row can hide its elements.
function autoTag() {
  for (const e of viewer.entities.values) {
    if (e.layer !== undefined) continue;
    if (e.model) { if (e.name === "Base station") tag(e, "bs"); }
    else if (e.point) { const px = e.point.pixelSize && e.point.pixelSize.getValue ? e.point.pixelSize.getValue() : e.point.pixelSize; if (px && px <= 5) tag(e, "ues"); else if (px && px <= 8) tag(e, "bs"); }
    else if (e.ellipse) tag(e, "cells");
    else if (e.polygon) { const pph = e.polygon.perPositionHeight; tag(e, pph && (pph.getValue ? pph.getValue() : pph) ? "bs" : "cells"); }
    else if (e.polyline) { const w = e.polyline.width && e.polyline.width.getValue ? e.polyline.width.getValue() : e.polyline.width; if (w === 3) tag(e, "cells"); }
  }
}

function publishLegend() {
  const items = [];
  if (lobes.on && lobes.info) {
    items.push({ id: "lobe", title: "Antenna gain", unit: "dBi", vmin: lobes.info.floor_dbi, vmax: lobes.info.peak_dbi });
  }
  if (interf.on && interf.data && interf.data.contrib) {
    items.push({ id: "interf", title: "BS contribution to the victim interference", unit: "dBm/MHz",
                 vmin: interf.data.cmin - ((interf.data.cmax - interf.data.cmin) < 0.5 ? 1 : 0),
                 vmax: interf.data.cmax + ((interf.data.cmax - interf.data.cmin) < 0.5 ? 1 : 0) });
  }
  const hs = heat.mode ? heatSource() : null;
  const m = hs ? hs.maps[heat.mode] : null;
  if (m) {
    const [lo, hi] = heatRange(m);
    items.push({ id: "heat", title: m.title, unit: m.unit, vmin: lo, vmax: hi, stops: heatLegendStops(heatPaletteName(heat.mode)) });
  }
  if (window.pyBridge && window.pyBridge.set_legend) window.pyBridge.set_legend(JSON.stringify(items));
}

// ── 3D antenna gain lobes (a GLB built by core/gain_lobe.py from the engine antenna, one instance per sector)
const lobes = { on: false, ents: [], info: null };

function setLobes(on) {
  lobes.on = !!on;
  for (const e of lobes.ents) e.show = lobes.on;
  const btn = document.getElementById("btnLobes");
  if (btn) btn.classList.toggle("on", lobes.on);
  publishLegend();
  if (lobes.on) {
    setStatus(lobes.info
      ? `Antenna gain lobe: peak ${lobes.info.peak_dbi} dBi, ${lobes.info.range_db} dB range (cold = side lobes, hot = main beam)`
      : "No antenna gain lobe for this scene");
  }
  viewer.scene.requestRender();
}

(function wireFootprintButton() {
  const btn = document.getElementById("btnFoot");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const on = heat.mode === "sat_gain";
    if (on) { setHeat(""); btn.classList.remove("on"); return; }
    if (!heat.sat || !heat.sat.maps || !heat.sat.maps.sat_gain) { setStatus("No satellite footprint map for this scene"); return; }
    setLayer("footprint", true);
    setHeat("sat_gain");
    btn.classList.add("on");
    const sm = heat.sat.summary || {};
    const rKm = sm.beamwidth_deg && sm.altitude_km ? sm.altitude_km * Math.tan(Cesium.Math.toRadians(sm.beamwidth_deg / 2)) : null;
    setStatus(rKm ? `Footprint: -3 dB radius about ${rKm.toFixed(0)} km (area ${(Math.PI * rKm * rKm).toExponential(2)} km²), contours at -3/-6/-10/-15/-20 dB`
                  : "Satellite footprint: gain contours at -3/-6/-10/-15/-20 dB");
  });
})();

(function wireLobesButton() {
  const btn = document.getElementById("btnLobes");
  if (btn) btn.addEventListener("click", () => setLobes(!lobes.on));
})();

// ── Ground heat map (PSD / I/N / strongest-BS power, computed by core/heatmap.py from the engine scene)
const heat = { mode: "", ent: null, data: null, sat: null };
function heatSource() { return heat.mode.startsWith("sat_") ? heat.sat : heat.data; }
function heatOrder() {                                    // IMT maps, plus the satellite footprint maps when there is a satellite
  const order = ["", "psd", "inr", "power"];
  if (heat.sat) order.push(...Object.keys(heat.sat.maps));
  return order;
}

// STK-style rainbow: antenna lobes, BS interference contribution and UE link SNR (same stops as the Qt legend)
function jetRGB(t) {
  t = Math.min(1, Math.max(0, t));
  const f = (c) => Math.round(255 * Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - c))));
  return [f(3), f(2), f(1)];
}

// Heat-map palettes. Names match core/heat_style.PALETTES (a test keeps the lists equal); "auto" picks viridis for
// levels and magma for I/N. Perceptually uniform ones first: readable in grayscale and for colour-blind users.
const HEAT_STOPS = {
  viridis: ["#440154", "#472d7b", "#3b528b", "#2c728e", "#21918c", "#28ae80", "#5ec962", "#addc30", "#fde725"],
  magma: ["#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f", "#cd4071", "#f1605d", "#fd9567", "#fcfdbf"],
  inferno: ["#000004", "#1f0c48", "#550f6d", "#88226a", "#a83655", "#e35933", "#f9950a", "#f8c932", "#fcffa4"],
  plasma: ["#0d0887", "#47039f", "#7301a8", "#9c179e", "#bd3786", "#d8576b", "#ed7953", "#fa9e3b", "#fdc926", "#f0f921"],
  cividis: ["#00224e", "#123570", "#3b496c", "#575d6d", "#707173", "#8a8678", "#a69d75", "#c4b56c", "#e4cf5b", "#fee838"],
  turbo: ["#30123b", "#4662d7", "#36aaf9", "#1ae4b6", "#72fe5e", "#c7ef34", "#faba39", "#f66b19", "#ca2a04", "#7a0403"],
  jet: ["#00007f", "#0000ff", "#007fff", "#00ffff", "#7fff7f", "#ffff00", "#ff7f00", "#ff0000", "#7f0000"],
  coolwarm: ["#3b4cc0", "#6788ee", "#9abbff", "#c9d7f0", "#edd1c2", "#f7a889", "#e26952", "#b40426"],
  gray: ["#000000", "#ffffff"],
};
const HEAT_RGB = {};
for (const k of Object.keys(HEAT_STOPS)) {
  HEAT_RGB[k] = HEAT_STOPS[k].map((h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)));
}

// What the user chose in the View panel (pushed by Qt through setHeatStyle): see core/heat_style.HeatStyle
const heatStyle = { palette: "auto", reverse: false, vmin: null, vmax: null, opacity: 0.85, isolines: true, bands: 0,
                    threshold: -6 };                      // threshold: I/N protection contour [dB] or null

function heatPaletteName(mode) {
  return heatStyle.palette !== "auto" && HEAT_RGB[heatStyle.palette] ? heatStyle.palette : (mode === "inr" ? "magma" : "viridis");
}
function heatRange(m) {                                  // manual range when set, else the one of the map
  const lo = heatStyle.vmin, hi = heatStyle.vmax;
  return lo !== null && hi !== null && hi > lo ? [lo, hi] : [m.vmin, m.vmax];
}
function heatRGB(t, name) {                              // t in [0, 1] -> [r, g, b]; honours bands and reverse
  const s = HEAT_RGB[name] || HEAT_RGB.viridis, n = heatStyle.bands;
  t = Math.min(1, Math.max(0, t));
  if (n >= 2) t = Math.min(n - 1, Math.floor(t * n)) / (n - 1);
  if (heatStyle.reverse) t = 1 - t;
  t *= s.length - 1;
  const i = Math.min(s.length - 2, Math.floor(t)), f = t - i;
  return [0, 1, 2].map((c) => s[i][c] + (s[i + 1][c] - s[i][c]) * f);
}
function heatLegendStops(name) {                         // [[position 0..1, "#rrggbb"], ...] as the 3D view draws it
  const hex = (t) => "#" + heatRGB(t, name).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  const n = heatStyle.bands, out = [];
  if (n >= 2) {
    for (let k = 0; k < n; k++) { const c = hex((k + 0.5) / n); out.push([k / n, c], [(k + 1) / n, c]); }
  } else {
    for (let k = 0; k <= 32; k++) out.push([k / 32, hex(k / 32)]);
  }
  return out;
}

// Bilinear sample of a south-to-north n x n grid at fractional (x, y) in [0, n-1]
function heatSample(vals, n, x, y) {
  const x0 = Math.min(n - 2, Math.floor(x)), y0 = Math.min(n - 2, Math.floor(y));
  const fx = x - x0, fy = y - y0, a = y0 * n + x0;
  return vals[a] * (1 - fx) * (1 - fy) + vals[a + 1] * fx * (1 - fy) + vals[a + n] * (1 - fx) * fy + vals[a + n + 1] * fx * fy;
}

// Smooth, contoured, edge-feathered ground map: values are interpolated first and coloured afterwards,
// so the 80-150 cell grid does not show as blocks; iso-lines give a quantitative reading
function renderHeatCanvas(m, n, mode) {
  const S = Math.min(1024, n * 7);
  const cv = document.createElement("canvas");
  cv.width = S; cv.height = S;
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(S, S);
  const [vmin, vmax] = heatRange(m), span = vmax - vmin;
  const name = heatPaletteName(mode), bands = heatStyle.bands, thr = mode === "inr" ? heatStyle.threshold : null;
  const rawStep = span / 8, mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const niceStep = [1, 2, 5, 10].map((k) => k * mag).reduce((a, b) => (Math.abs(b - rawStep) < Math.abs(a - rawStep) ? b : a));
  const step = bands >= 2 ? span / bands : niceStep, origin = bands >= 2 ? vmin : 0;   // lines on the band edges
  const level = new Float32Array(S * S);
  for (let row = 0; row < S; row++) {
    const gy = (1 - row / (S - 1)) * (n - 1);          // image row 0 is north
    for (let col = 0; col < S; col++) level[row * S + col] = heatSample(m.values, n, (col / (S - 1)) * (n - 1), gy);
  }
  const feather = S * 0.06, cell = (x) => Math.floor((x - origin) / step);
  const levels = Array.isArray(m.levels) ? m.levels : null;          // footprint maps: contours at fixed dB below the peak
  const crosses = (L, v, o) => (v >= L) !== (o >= L);
  for (let row = 0; row < S; row++) {
    for (let col = 0; col < S; col++) {
      const i = row * S + col, v = level[i];
      const t = (v - vmin) / span;
      let [r, g, b] = heatRGB(t, name);
      let a = heatStyle.opacity * (0.62 + 0.38 * Math.min(1, Math.max(0, t)));
      const edge = Math.min(row, col, S - 1 - row, S - 1 - col);
      a *= Math.min(1, edge / feather);               // fade out at the border: no hard square on the globe
      if (m.fade_below !== undefined) a *= Math.min(1, Math.max(0, (v - m.fade_below) / (0.15 * span)));   // only the beam
      const right = col < S - 1 ? level[i + 1] : v, down = row < S - 1 ? level[i + S] : v;
      const left = col > 0 ? level[i - 1] : v, up = row > 0 ? level[i - S] : v;
      if (levels) {
        const edgeAt = (L) => crosses(L, v, right) || crosses(L, v, down);
        if (m.bold !== undefined && (edgeAt(m.bold) || crosses(m.bold, v, left) || crosses(m.bold, v, up))) {
          r = 255; g = 255; b = 255; a = 1;           // the -3 dB contour: the edge of the beam
        } else if (heatStyle.isolines && levels.some(edgeAt)) {
          r = r * 0.45 + 255 * 0.55; g = g * 0.45 + 255 * 0.55; b = b * 0.45 + 255 * 0.55; a = Math.max(a, 0.75);
        }
      } else if (heatStyle.isolines && (cell(v) !== cell(right) || cell(v) !== cell(down))) {
        r = r * 0.55 + 255 * 0.45; g = g * 0.55 + 255 * 0.45; b = b * 0.55 + 255 * 0.45; a = Math.min(1, a + 0.2);
      }
      if (thr !== null && ((v >= thr) !== (right >= thr) || (v >= thr) !== (down >= thr))) { r = 0; g = 229; b = 255; a = 1; }
      const o = i * 4;
      img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = Math.round(255 * a);
    }
  }
  ctx.putImageData(img, 0, 0);
  return cv;
}

// Called by Qt (View panel > Heat map) with a JSON from core/heat_style.HeatStyle.to_js(); redraws the visible map
function setHeatStyle(style) {
  const s = typeof style === "string" ? JSON.parse(style) : (style || {});
  const num = (v) => (v === null || v === undefined || v === "" || !isFinite(Number(v)) ? null : Number(v));
  if (typeof s.palette === "string") heatStyle.palette = HEAT_RGB[s.palette] ? s.palette : "auto";
  if ("reverse" in s) heatStyle.reverse = !!s.reverse;
  if ("vmin" in s || "vmax" in s) { heatStyle.vmin = num(s.vmin); heatStyle.vmax = num(s.vmax); }
  if ("opacity" in s) heatStyle.opacity = Math.min(1, Math.max(0.2, num(s.opacity) ?? 0.85));
  if ("isolines" in s) heatStyle.isolines = !!s.isolines;
  if ("bands" in s) { const b = Math.floor(num(s.bands) ?? 0); heatStyle.bands = b < 2 ? 0 : Math.min(16, b); }
  if ("threshold" in s) heatStyle.threshold = num(s.threshold);
  if (heat.mode) setHeat(heat.mode);
}

function setHeat(mode) {
  const fb = document.getElementById("btnFoot"); if (fb) fb.classList.toggle("on", mode === "sat_gain");
  heat.mode = mode || "";
  if (heat.ent) { viewer.entities.remove(heat.ent); heat.ent = null; }
  const btn = document.getElementById("btnHeat");
  const src = heat.mode ? heatSource() : null;
  const m = src ? src.maps[heat.mode] : null;
  if (btn) btn.classList.toggle("on", !!m);
  publishLegend();
  if (!m) { viewer.scene.requestRender(); return; }
  const n = src.n;
  const cv = renderHeatCanvas(m, n, heat.mode);
  heat.ent = viewer.entities.add({
    name: "Heat map: " + m.title,
    rectangle: {
      coordinates: Cesium.Rectangle.fromDegrees(src.west, src.south, src.east, src.north),
      material: new Cesium.ImageMaterialProperty({ image: cv.toDataURL("image/png"), transparent: true }),
    },
  });
  const [lo, hi] = heatRange(m);
  if (m.levels) {
    setStatus(`${m.title}: peak ${hi.toFixed(1)} ${m.unit}; contours -3 (white), -6, -10, -15, -20 dB below the peak`);
    viewer.scene.requestRender();
    return;
  }
  setStatus(`${m.title}: ${lo.toFixed(0)} to ${hi.toFixed(0)} ${m.unit} (free space, nominal full power${src.freq_mhz ? ", " + src.freq_mhz + " MHz" : ""})`);
  viewer.scene.requestRender();
}

(function wireHeatButton() {
  const btn = document.getElementById("btnHeat");
  if (btn) btn.addEventListener("click", () => {
    if (!heat.data && !heat.sat) { setStatus("No heat map for this scene"); return; }
    const order = heatOrder();
    setHeat(order[(order.indexOf(heat.mode) + 1) % order.length]);
  });
})();

// ── Interferer vs victim: role labels, base stations coloured by their contribution to the interference at the
//    victim, and the interference paths drawn from every base station to the victim (core/interference.py)
const interf = { on: false, bsEnts: [], bsWorld: [], victimWorld: null, data: null, lines: [] };
const ROLE_COLOR = { interferer: "#ff7043", victim: "#00e5ff" };

function addRoleLabel(position, name, role, heightPx) {
  if (!role) return;
  const col = Cesium.Color.fromCssColorString(ROLE_COLOR[role] || "#ffffff");
  viewer.entities.add({
    position,
    label: {
      text: `${role === "interferer" ? "INTERFERER" : "VICTIM"}  ·  ${name}`,
      font: "bold 13px 'Segoe UI', Arial, sans-serif", fillColor: col, outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE, showBackground: true,
      backgroundColor: Cesium.Color.fromCssColorString("#14161899"),
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -(heightPx || 22)),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });
}

function setInterf(on) {
  interf.on = !!on;
  for (const l of interf.lines) viewer.entities.remove(l);
  interf.lines = [];
  const d = interf.data;
  const btn = document.getElementById("btnInterf");
  const usable = !!(d && d.contrib && d.contrib.length === interf.bsEnts.length);
  if (btn) btn.classList.toggle("on", interf.on && usable);
  const flat = usable && (d.cmax - d.cmin) < 0.5;      // e.g. the engine's array-gain floor makes every BS equal
  const span = usable ? Math.max(d.cmax - d.cmin, 1) : 1;
  interf.bsEnts.forEach((ent, i) => {
    const colored = interf.on && usable;
    const [r, g, b] = colored ? jetRGB(flat ? 0.5 : (d.contrib[i] - d.cmin) / span) : [0, 0, 0];
    ent.point.color = colored ? Cesium.Color.fromBytes(r, g, b, 255) : C.bs;
    ent.point.pixelSize = colored ? 12 : 8;
    ent.point.distanceDisplayCondition = colored
      ? new Cesium.DistanceDisplayCondition(0, Number.POSITIVE_INFINITY)
      : new Cesium.DistanceDisplayCondition(2200, Number.POSITIVE_INFINITY);
    if (colored && interf.victimWorld) {
      interf.lines.push(viewer.entities.add({
        polyline: { positions: [interf.bsWorld[i], interf.victimWorld], width: 1.6,
                    material: Cesium.Color.fromBytes(r, g, b, 150), arcType: Cesium.ArcType.NONE },
      }));
    }
  });
  publishLegend();
  if (interf.on) {
    setStatus(usable
      ? `Interference: ${d.victim_name || "victim"} receives ${d.psd_dbm_mhz} dBm/MHz (I/N = ${d.inr_db} dB); ` +
        (flat ? `every base station contributes the same (${d.cmax} dBm/MHz each: the antenna sees only the sidelobe floor)`
              : `base stations coloured by contribution (${d.cmin} to ${d.cmax} dBm/MHz)`)
      : "No victim interference to show for this scenario (the system is not the victim, or its antenna is not supported)");
  }
  viewer.scene.requestRender();
}

(function wireInterfButton() {
  const btn = document.getElementById("btnInterf");
  if (btn) btn.addEventListener("click", () => setInterf(!interf.on));
})();

// ── UE links (colour = SNR) with their link budget; click one to open it in the "Link budget" window
const links = { on: false, ents: [], data: null };

function linkColor(snr) {
  const [r, g, b] = jetRGB((snr + 10) / 50);                       // -10 dB blue ... 40 dB red
  return Cesium.Color.fromBytes(r, g, b, 235);
}

function setLinks(on) {
  links.on = !!on;
  for (const e of links.ents) e.show = links.on;
  const btn = document.getElementById("btnLinks");
  if (btn) btn.classList.toggle("on", links.on);
  if (links.on) setStatus(links.data ? "UE links: colour = SNR (-10 dB blue to 40 dB red); click a link for its link budget" : "No links for this scene");
  viewer.scene.requestRender();
}

(function wireLinks() {
  const btn = document.getElementById("btnLinks");
  if (btn) btn.addEventListener("click", () => setLinks(!links.on));
  const h = new Cesium.ScreenSpaceEventHandler(viewer.canvas);
  h.setInputAction((c) => {
    const p = viewer.scene.pick(c.position);
    if (p && p.id && p.id.linkInfo && window.pyBridge && window.pyBridge.set_link) {
      window.pyBridge.set_link(JSON.stringify(p.id.linkInfo));
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
})();

// ── Snapshot animation: the engine redraws the UEs every snapshot; play through a short sequence
const snap = { frames: null, ues: [], bs: [], toWorld: null, ueH: 1.5, idx: 0, timer: null };

function applySnapshot(i) {
  const f = snap.frames && snap.frames[i];
  if (!f) return;
  snap.ues.forEach((ent, n) => { if (n < f.x.length) ent.position = snap.toWorld(f.x[n], f.y[n], snap.ueH); });
  links.ents.forEach((ent) => {
    const k = ent.linkOrig;
    const bs = snap.bs[f.bs[k.ue]];
    if (!bs) return;
    ent.polyline.positions = [snap.toWorld(f.x[k.ue], f.y[k.ue], k.ue_xyz[2]), snap.toWorld(bs.x, bs.y, bs.z)];
    ent.polyline.material = linkColor(f.snr[k.ue]);
  });
  setStatus(`Snapshot ${i + 1}/${snap.frames.length}: UEs redrawn as in the simulation, links follow the strongest base station`);
  viewer.scene.requestRender();
}

function setPlay(on) {
  const btn = document.getElementById("btnPlay");
  if (snap.timer) { clearInterval(snap.timer); snap.timer = null; }
  if (btn) btn.classList.toggle("on", !!on);
  if (!on) {
    snap.idx = 0;
    if (snap.frames) {                                  // back to the scene's own draw
      snap.ues.forEach((ent) => { if (ent.uePos0) ent.position = ent.uePos0; });
      links.ents.forEach((ent) => {
        const k = ent.linkOrig;
        ent.polyline.positions = [snap.toWorld(...k.ue_xyz), snap.toWorld(...k.bs_xyz)];
        ent.polyline.material = linkColor(k.snr_db);
      });
    }
    viewer.scene.requestRender();
    return;
  }
  if (!snap.frames) { setStatus("No snapshots for this scene"); if (btn) btn.classList.remove("on"); return; }
  snap.timer = setInterval(() => { snap.idx = (snap.idx + 1) % snap.frames.length; applySnapshot(snap.idx); }, 900);
  applySnapshot(snap.idx);
}

(function wirePlay() {
  const btn = document.getElementById("btnPlay");
  if (btn) btn.addEventListener("click", () => setPlay(!snap.timer));
})();

function renderHexSectorScene(scene) {
  renderHexSectorScene._sites = new Set();
  lobes.ents = [];
  lobes.info = scene.lobe || null;
  heat.data = scene.heat || null;
  heat.sat = null;
  heat.ent = null;                                  // the old entity went away with the scene
  if (snap.timer) { clearInterval(snap.timer); snap.timer = null; const pb = document.getElementById("btnPlay"); if (pb) pb.classList.remove("on"); }
  links.ents = []; links.data = scene.links || null;
  for (const l of interf.lines) viewer.entities.remove(l);
  interf.lines = []; interf.bsEnts = []; interf.bsWorld = []; interf.victimWorld = null; interf.data = scene.interference || null;
  snap.frames = scene.snapshots || null; snap.ues = []; snap.bs = scene.base_stations; snap.idx = 0;
  if (window.pyBridge && window.pyBridge.set_plots) window.pyBridge.set_plots(JSON.stringify(scene.plots || null));
  const { toWorld } = makeEnuHelpers(scene.reference);
  const bsHeightM = scene.bs_height_m;
  const ueHeightM = scene.ue_height_m;
  const arrowLenM = scene.hex_radius_m * 0.6;

  // Grade métrica de referência
  {
    let ext = 0;
    for (const hc of scene.hex_centers) ext = Math.max(ext, Math.abs(hc.x), Math.abs(hc.y));
    ext += scene.hex_radius_m * 1.6;
    const step = Math.pow(10, Math.floor(Math.log10(ext / 6)));
    addLocalGrid(toWorld, Math.ceil(ext / step) * step, step);
  }

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
      polyline: { positions, width: 3, material: glow(C.hex.brighten(-0.1, new Cesium.Color()).withAlpha(0.9), 0.16) },
    });
    // Subtle hex fill
    viewer.entities.add({
      polygon: {
        hierarchy: positions,
        material: C.hex.withAlpha(0.07),
        outline: false,
      },
    });
  }

  // Base stations
  const sectorRadius = Math.max(scene.hex_radius_m * 0.85, arrowLenM);
  for (const bs of scene.base_stations) {
    const groundPos = toWorld(bs.x, bs.y, 0);
    const worldPos = toWorld(bs.x, bs.y, bsHeightM);

    // One tower model per site (the 3 sectors of a site share the position)
    const siteKey = `${bs.x.toFixed(1)},${bs.y.toFixed(1)}`;
    if (!renderHexSectorScene._sites.has(siteKey)) {
      renderHexSectorScene._sites.add(siteKey);
      const towerPos = toWorld(bs.x, bs.y, 0);
      addModel("Base station", "/models/tower.glb", towerPos, -bs.azimuth_deg, 0,
        { scale: Math.max(1, bsHeightM / 30), nearM: 2500 });
    }
    const bsPoint = viewer.entities.add({
      position: worldPos,
      point: {
        pixelSize: 8, color: C.bs, outlineColor: C.bsOutline, outlineWidth: 1.5,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(2200, Number.POSITIVE_INFINITY),
      },
    });
    interf.bsEnts.push(bsPoint);
    interf.bsWorld.push(worldPos);
    const ringR = Math.max(scene.hex_radius_m * 0.06, 8);
    viewer.entities.add({
      position: groundPos,
      ellipse: {
        semiMajorAxis: ringR, semiMinorAxis: ringR,
        material: C.bs.withAlpha(0.22), outline: true, outlineColor: C.bs.withAlpha(0.8),
      },
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

    if (scene.lobe) {                                   // gain lobe: same heading convention as the tower model
      const lobe = addModel("Antenna gain lobe", scene.lobe.uri, worldPos, -bs.azimuth_deg, 0, { scale: arrowLenM * 0.9 });
      lobe.show = lobes.on;
      lobes.ents.push(lobe);
    }
  }

  // UE scatter
  snap.toWorld = toWorld; snap.ueH = ueHeightM;
  for (const ue of scene.ue_positions) {
    const ent = viewer.entities.add({
      position: toWorld(ue.x, ue.y, ueHeightM),
      point: { pixelSize: 4.5, color: C.ue.withAlpha(0.95), outlineColor: Cesium.Color.WHITE.withAlpha(0.6), outlineWidth: 0.8 },
    });
    ent.uePos0 = ent.position;
    snap.ues.push(ent);
  }
  for (const k of links.data || []) {                 // serving-BS links with their link budget
    const ent = viewer.entities.add({
      polyline: { positions: [toWorld(...k.ue_xyz), toWorld(...k.bs_xyz)], width: 2, material: linkColor(k.snr_db) },
    });
    ent.linkInfo = k; ent.linkOrig = k; ent.show = links.on;
    links.ents.push(ent);
  }

  if (scene.roles) addRoleLabel(toWorld(0, 0, bsHeightM + 40), "IMT network", scene.roles.imt, 30);
  if (heat.mode) setHeat(heat.mode);                 // keep the chosen map across redraws
  viewer.zoomTo(viewer.entities);
  setStatus(
    `${scene.topology_type}: ${scene.base_stations.length} BS, ` +
      `${scene.hex_centers.length} cells, ${scene.ue_positions.length} UE`
  );
}

// Layer state of an IMT network scene (lobes, ground maps, UE links, HUD plots, snapshots). Every IMT renderer starts
// from it so a scene never inherits the previous scene's maps or links. Victim-system renderers must NOT call it:
// in a composite scene they draw after the IMT network and would wipe its layers.
function resetEngineLayers(scene) {
  lobes.ents = []; lobes.info = scene.lobe || null;
  heat.data = scene.heat || null; heat.sat = null; heat.ent = null;
  if (snap.timer) { clearInterval(snap.timer); snap.timer = null; const pb = document.getElementById("btnPlay"); if (pb) pb.classList.remove("on"); }
  links.ents = []; links.data = scene.links || null;
  for (const l of interf.lines) viewer.entities.remove(l);
  interf.lines = []; interf.bsEnts = []; interf.bsWorld = []; interf.victimWorld = null; interf.data = scene.interference || null;
  snap.frames = null; snap.ues = []; snap.bs = scene.base_stations || []; snap.idx = 0;
  if (window.pyBridge && window.pyBridge.set_plots) window.pyBridge.set_plots(JSON.stringify(scene.plots || null));
}

// Serving-BS links (local ENU), coloured by SNR; click one for its link budget
function addEnuLinks(toWorld) {
  for (const k of links.data || []) {
    const ent = viewer.entities.add({
      polyline: { positions: [toWorld(...k.ue_xyz), toWorld(...k.bs_xyz)], width: 2, material: linkColor(k.snr_db) },
    });
    ent.linkInfo = k; ent.linkOrig = k; ent.show = links.on;
    links.ents.push(ent);
  }
}

function renderIndoorScene(scene) {
  const { toWorld, orientation } = makeEnuHelpers(scene.reference);
  resetEngineLayers(scene);

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

  const lobeScale = Math.max(2.5, (scene.buildings[0] ? scene.buildings[0].floor_height : 3) * 1.2);
  for (const bs of scene.base_stations) {
    viewer.entities.add({
      position: toWorld(bs.x, bs.y, bs.z),
      point: { pixelSize: 6, color: C.bs, outlineColor: C.bsOutline, outlineWidth: 1 },
    });
    if (scene.lobe) {                                   // gain lobe of the access point, same pointing for all
      const lobe = addModel("Antenna gain lobe", scene.lobe.uri, toWorld(bs.x, bs.y, bs.z), 0, 0, { scale: lobeScale });
      lobe.show = lobes.on;
      lobes.ents.push(lobe);
    }
  }

  for (const ue of scene.ue_positions) {
    viewer.entities.add({
      position: toWorld(ue.x, ue.y, ue.z),
      point: { pixelSize: 4.5, color: C.ue.withAlpha(0.95), outlineColor: Cesium.Color.WHITE.withAlpha(0.6), outlineWidth: 0.8 },
    });
  }
  addEnuLinks(toWorld);
  if (heat.mode) setHeat(heat.mode);                    // keep the chosen map across redraws

  viewer.zoomTo(viewer.entities);
  setStatus(
    `INDOOR: ${scene.buildings.length} buildings, ${scene.base_stations.length} BS, ` +
      `${scene.ue_positions.length} UE${scene.source === "engine" ? " (engine)" : " (illustration)"}`
  );
}

// Macro_countries network from the engine (core/country_scene.py): everything is placed by latitude/longitude
// because the sites are thousands of km apart; each site gets its own local ENU frame for sector, cone and lobe.
function renderCountryNetwork(scene) {
  const c = scene.country;
  const sites = c.sites || [];
  const R = Math.max(c.cell_radius_m || 1000, 200);
  const detailed = sites.length <= 300;               // towers, cones and lobes only while the entity count stays low
  lobes.ents = []; lobes.info = c.lobe || null;
  heat.data = c.heat || null; heat.ent = null;
  links.ents = []; links.data = c.links || null;
  snap.frames = null; snap.ues = []; snap.idx = 0;
  const near = new Cesium.DistanceDisplayCondition(0, Math.max(60 * R, 150000));
  const dotFar = new Cesium.DistanceDisplayCondition(0, Number.POSITIVE_INFINITY);

  for (const s of sites) {
    const h = Math.max(s.height_m || 20, 5);
    const { toWorld } = makeEnuHelpers({ lat_deg: s.lat_deg, lon_deg: s.lon_deg, alt_m: 0 });
    const top = toWorld(0, 0, h);
    tag(viewer.entities.add({                           // visible from space: a site is a dot until you zoom in
      position: top,
      point: { pixelSize: 7, color: C.countryBs, outlineColor: C.bsOutline, outlineWidth: 1.5, distanceDisplayCondition: dotFar,
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }), "bs");
    tag(viewer.entities.add({                           // the cell, to scale
      position: toWorld(0, 0, 0),
      ellipse: { semiMajorAxis: R, semiMinorAxis: R, material: C.hex.withAlpha(0.10), outline: true,
                 outlineColor: C.hex.withAlpha(0.7), distanceDisplayCondition: near },
    }), "cells");
    tag(viewer.entities.add({                           // sector wedge along the engine azimuth (site frame)
      polygon: { hierarchy: sectorWedgePositions(toWorld, 0, 0, h, s.azimuth_deg, R * 0.9), material: C.sector.withAlpha(0.14),
                 outline: true, outlineColor: C.sector.withAlpha(0.6), perPositionHeight: true, distanceDisplayCondition: near },
    }), "sectors");
    frame.points.push(top);
    if (!detailed) continue;
    addBeamCone(toWorld, viewer.entities, 0, 0, h, s.azimuth_deg, s.downtilt_deg, R * 0.6, C.beam);
    addModel("Base station", "/models/tower.glb", toWorld(0, 0, 0), -s.azimuth_deg, 0,
      { scale: Math.max(1, h / 30), nearM: Math.max(2500, 4 * R) });
    if (c.lobe) {
      const lobe = addModel("Antenna gain lobe", c.lobe.uri, top, -s.azimuth_deg, 0, { scale: R * 0.9, nearM: 40 * R });
      lobe.show = lobes.on;
      lobes.ents.push(lobe);
    }
  }

  for (const u of c.ues || []) {
    tag(viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(u.lon_deg, u.lat_deg, 1.5),
      point: { pixelSize: 4.5, color: C.ue.withAlpha(0.95), outlineColor: Cesium.Color.WHITE.withAlpha(0.6), outlineWidth: 0.8,
               heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, distanceDisplayCondition: dotFar,
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }), "ues");
  }
  for (const k of c.links || []) {                      // engine-assigned serving BS, coloured by nominal SNR
    const ent = viewer.entities.add({
      polyline: { positions: [Cesium.Cartesian3.fromDegrees(k.ue_lla[1], k.ue_lla[0], k.ue_lla[2]),
                              Cesium.Cartesian3.fromDegrees(k.bs_lla[1], k.bs_lla[0], k.bs_lla[2])],
                  width: 2, material: linkColor(k.snr_db), depthFailMaterial: linkColor(k.snr_db),
                  arcType: Cesium.ArcType.GEODESIC, distanceDisplayCondition: near },
    });
    ent.linkInfo = k; ent.linkOrig = k; ent.show = links.on;
    links.ents.push(ent);
  }
  if (window.pyBridge && window.pyBridge.set_plots) window.pyBridge.set_plots(JSON.stringify(null));
  if (heat.mode) setHeat(heat.mode);                    // keep the chosen map across redraws
  const nUe = c.ue_total || (c.ues || []).length;
  scene._countryStatus = `${sites.length} sites, ${nUe} UE, cell radius ${(R / 1000).toFixed(1)} km`;
}

function renderSingleSpaceStationScene(scene) {
  const sat = scene.satellite;
  const es = scene.earth_station;
  const isMacroCountries = scene.topology_type === "Macro_countries";
  const satWorld = Cesium.Cartesian3.fromDegrees(sat.lon_deg, sat.lat_deg, sat.alt_m);
  const esWorld = Cesium.Cartesian3.fromDegrees(es.lon_deg, es.lat_deg, es.alt_m);
  const nadirWorld = Cesium.Cartesian3.fromDegrees(sat.lon_deg, sat.lat_deg, 0);
  const boundary = Array.isArray(scene.footprint_boundary) ? scene.footprint_boundary
                 : (Array.isArray(scene.footprint) ? scene.footprint : []);
  frame.points.push(satWorld, nadirWorld);

  // Gain map (heatmap) — rendered first so it sits under other elements
  renderGainMap(scene);

  // Satellite model with the dish looking at the Earth (nadir)
  // The engine points the satellite (by default at the IMT network); aim the model and its lobe the same way.
  const fpt = scene.footprint && scene.footprint.pointing;
  const aimAt = fpt ? Cesium.Cartesian3.fromDegrees(fpt.target_lon_deg, fpt.target_lat_deg, 0) : null;
  const satModel = tag(addModel("Satellite model", "/models/satellite.glb", satWorld, 0, -90,
    { minimumPixelSize: 72, maximumScale: 400000 }), "sat");
  if (aimAt) satModel.orientation = orientToward(satWorld, aimAt);
  heat.sat = scene.footprint || null;                 // satellite footprint maps join the heat-map button
  interf.victimWorld = satWorld;
  addRoleLabel(satWorld, "satellite", scene.roles && scene.roles.system, 44);
  if (window.pyBridge && window.pyBridge.set_satellite) {
    window.pyBridge.set_satellite(JSON.stringify(scene.footprint ? scene.footprint.summary : null));
  }
  if (scene.show_heat && heat.sat && heat.sat.maps[scene.show_heat]) {   // "Show gain map" in the View panel
    heat.fromCheckbox = true;
    setHeat(scene.show_heat);
  } else if (heat.fromCheckbox) {                     // the checkbox was turned off: take its map away
    heat.fromCheckbox = false;
    setHeat("");
  } else if (heat.mode) {
    setHeat(heat.mode);
  }
  if (scene.lobe) {                                   // 3D gain lobe of the satellite antenna (nadir-pointing)
    const lobe = addModel("Satellite antenna lobe", scene.lobe.uri, satWorld, 0, -90,
      { scale: aimAt ? Cesium.Cartesian3.distance(satWorld, aimAt) : Math.max(sat.alt_m, 20000), maximumScale: 4e7 });
    if (aimAt) lobe.orientation = orientToward(satWorld, aimAt);   // the main beam ends on the aimed ground point
    lobe.show = lobes.on;
    lobes.ents.push(lobe);
    lobes.info = lobes.info || scene.lobe;
  }

  // Satellite: marker, nadir line and sub-satellite point (so the beam always has a visible origin)
  tag(viewer.entities.add({
    polyline: { positions: [satWorld, nadirWorld], width: 1.4, arcType: Cesium.ArcType.NONE,
                material: new Cesium.PolylineDashMaterialProperty({ color: C.satellite.withAlpha(0.8), dashLength: 24 }) },
  }), "nadir");
  tag(viewer.entities.add({
    position: nadirWorld,
    point: { pixelSize: 7, color: C.satellite, outlineColor: Cesium.Color.WHITE, outlineWidth: 1.5,
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: { text: `nadir ${sat.lat_deg.toFixed(2)}°, ${sat.lon_deg.toFixed(2)}°`, font: "11px 'Segoe UI', Arial, sans-serif",
             fillColor: C.satellite, outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
             verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 8),
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
  }), "nadir");
  tag(viewer.entities.add({
    name: "Satellite",
    position: satWorld,
    point: { pixelSize: 14, color: C.satellite, outlineColor: Cesium.Color.WHITE, outlineWidth: 2,
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: {
      text: `SAT  alt ${(sat.alt_m / 1000).toFixed(0)} km\nsub-sat ${sat.lat_deg.toFixed(2)}°, ${sat.lon_deg.toFixed(2)}°`,
      font: "bold 13px 'Segoe UI', Arial, sans-serif",
      fillColor: C.satellite,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -16),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  }), "sat");

  if (!isMacroCountries) {
    frame.points.push(esWorld);
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
        positions: [satWorld, esWorld], width: 1.6,
        material: glow(C.link.withAlpha(0.9), 0.25),
        arcType: Cesium.ArcType.NONE,
      },
    });
  }

  // Footprint (-3 dB boundary): tagged as one layer
  const fpStart = viewer.entities.values.length;
  if (boundary.length > 1) {
    const footprintPositions = Cesium.Cartesian3.fromDegreesArray(
      boundary.flatMap((p) => [p.lon_deg, p.lat_deg])
    );
    // Contorno fino com brilho; preenchimento translúcido
    viewer.entities.add({
      polyline: { positions: footprintPositions, width: 1.8, material: glow(C.footprint.withAlpha(0.95), 0.22), clampToGround: true },
    });
    viewer.entities.add({
      polygon: {
        hierarchy: new Cesium.PolygonHierarchy(footprintPositions),
        material: C.footprint.withAlpha(0.12),
        outline: false,
      },
    });
    // Volume do feixe: leque de triângulos translúcidos (satélite -> contorno) + poucas arestas finas
    const triStep = Math.max(1, Math.floor(footprintPositions.length / 48));
    for (let i = 0; i + triStep < footprintPositions.length; i += triStep) {
      viewer.entities.add({
        polygon: {
          hierarchy: [satWorld, footprintPositions[i], footprintPositions[i + triStep]],
          perPositionHeight: true,
          material: C.footprint.withAlpha(0.045),
          outline: false,
        },
      });
    }
    const beamStep = Math.max(1, Math.floor(footprintPositions.length / 8));
    for (let i = 0; i < footprintPositions.length; i += beamStep) {
      viewer.entities.add({
        polyline: {
          positions: [satWorld, footprintPositions[i]],
          width: 1,
          material: C.footprint.withAlpha(0.35),
          arcType: Cesium.ArcType.NONE,
        },
      });
    }
  }

  for (const e of viewer.entities.values.slice(fpStart)) tag(e, "footprint");

  // Country borders
  const bdStart = viewer.entities.values.length;
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

  for (const e of viewer.entities.values.slice(bdStart)) tag(e, "borders");

  // Macro_countries from the engine: sites with sectors, cells, UEs, links, lobes and ground maps
  if (scene.country) renderCountryNetwork(scene);

  // Country BS (Macro_countries) — larger dots + triangle markers (plain dots when there is no engine data)
  if (scene.country_bs && scene.country_bs.length > 0) {
    for (const bs of (scene.country ? [] : scene.country_bs)) {
      viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(bs.lon_deg, bs.lat_deg, (bs.ground_m || 0) + 25),
        point: { pixelSize: 6, color: C.countryBs, outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
      });
    }
    // Link lines from satellite to BS centroid area
    if (scene.bs_centroid) {
      const centroidWorld = Cesium.Cartesian3.fromDegrees(scene.bs_centroid.lon_deg, scene.bs_centroid.lat_deg, 0);
      tag(viewer.entities.add({
        polyline: {
          positions: [satWorld, centroidWorld], width: 2.5,
          material: new Cesium.PolylineDashMaterialProperty({ color: C.link }),
          arcType: Cesium.ArcType.NONE,
        },
      }), "boresight");
      tag(viewer.entities.add({
        position: centroidWorld,
        point: { pixelSize: 8, color: C.link, outlineColor: Cesium.Color.WHITE, outlineWidth: 1.5 },
        label: {
          text: `boresight target: centroid of ${scene.country_bs.length} BS`,
          font: "bold 11px 'Segoe UI', Arial, sans-serif",
          fillColor: C.link,
          outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(0, -12),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      }), "boresight");
    }
  }

  frameScene();
  let statusMsg =
    `${scene.topology_type}: satellite (${sat.lat_deg.toFixed(1)}°, ${sat.lon_deg.toFixed(1)}°), ` +
    `footprint ${boundary.length} pts`;
  if (scene._countryStatus) statusMsg += `, ${scene._countryStatus}`;
  else if (scene.country_bs) statusMsg += `, ${scene.country_bs.length} BS`;
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

  interf.victimWorld = worldPos;
  addRoleLabel(worldPos, "earth station", scene.roles && scene.roles.system, 40);

  // Dish model, pointed with the station azimuth/elevation
  addModel("Earth station", "/models/earth_station.glb", groundPos,
    -(scene.antenna_azimuth_deg || 0), (scene.antenna_elevation_deg || 0),
    { nearM: 1500 });
  if (scene.lobe) {                                   // 3D gain lobe of the dish, same pointing as the dish model
    const lobe = addModel("Earth station antenna lobe", scene.lobe.uri, worldPos,
      -(scene.antenna_azimuth_deg || 0), (scene.antenna_elevation_deg || 0),
      { scale: Math.max(50, s.z * 3) * 1.3 });
    lobe.show = lobes.on;
    lobes.ents.push(lobe);
    lobes.info = lobes.info || scene.lobe;
  }

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

// MSS_DC: a constellation seen from the ground (core/country_scene.constellation). Beams are the engine's "base
// stations": each footprint is where the beam boresight meets the Earth; colour = serving satellite.
function renderMssDcScene(scene) {
  const c = scene.constellation;
  if (!scene.as_system) resetEngineLayers({});   // a victim constellation draws after the IMT network: keep its layers
  const hue = (k) => Cesium.Color.fromHsl((k * 0.618033988) % 1, 0.65, 0.55);
  const satPos = c.satellites.map((s) => Cesium.Cartesian3.fromDegrees(s.lon_deg, s.lat_deg, s.alt_m));

  c.satellites.forEach((s, k) => {
    addModel("Satellite model", "/models/satellite.glb", satPos[k], 0, -90, { minimumPixelSize: 30, maximumScale: 300000 });
    viewer.entities.add({
      position: satPos[k],
      point: { pixelSize: 6, color: hue(k), outlineColor: Cesium.Color.WHITE, outlineWidth: 1 },
      label: { text: `SAT ${k + 1} · ${s.beams} beams`, font: "11px 'Segoe UI', Arial, sans-serif", fillColor: hue(k),
               outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
               verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -14),
               distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 6.0e6) },
    });
  });
  for (const b of c.beams) {                           // footprint on the ground, to scale
    viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(b.lon_deg, b.lat_deg, 0),
      ellipse: { semiMajorAxis: c.beam_radius_m, semiMinorAxis: c.beam_radius_m, material: hue(b.sat).withAlpha(0.20),
                 outline: true, outlineColor: hue(b.sat).withAlpha(0.75) },
    });
  }
  for (const u of c.ues) {
    viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(u.lon_deg, u.lat_deg, 1.5),
      point: { pixelSize: 3.5, color: C.ue.withAlpha(0.95), outlineColor: Cesium.Color.WHITE.withAlpha(0.5), outlineWidth: 0.6 },
    });
  }
  for (const l of c.links) {                           // UE to the satellite of its beam
    viewer.entities.add({
      name: `UE link: ${l.dist_km} km, elevation ${l.elev_deg}°`,
      polyline: { positions: [Cesium.Cartesian3.fromDegrees(l.ue_lon_deg, l.ue_lat_deg, 1.5), satPos[l.sat]], width: 1.2,
                  material: new Cesium.PolylineDashMaterialProperty({ color: hue(l.sat).withAlpha(0.6) }),
                  arcType: Cesium.ArcType.NONE },
    });
  }
  viewer.zoomTo(viewer.entities);
  const miss = c.beams_missing ? `, ${c.beams_missing} beams miss the Earth` : "";
  setStatus(`${scene.topology_type}: ${c.satellites.length} satellites, ${c.beams.length} beams of ${(c.beam_radius_m / 1000).toFixed(1)} km radius, ` +
            `${c.ue_total ? c.ue_total + " UE (engine)" : "engine geometry"}${miss}`);
}

function renderNtnScene(scene) {
  const { toWorld } = makeEnuHelpers(scene.reference);
  resetEngineLayers(scene);

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
      polyline: { positions, width: 3, material: glow(C.hex.brighten(-0.1, new Cesium.Color()).withAlpha(0.9), 0.16) },
    });
    viewer.entities.add({
      polygon: { hierarchy: positions, material: C.hex.withAlpha(0.07), outline: false },
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
      point: { pixelSize: 4.5, color: C.ue.withAlpha(0.95), outlineColor: Cesium.Color.WHITE.withAlpha(0.6), outlineWidth: 0.8 },
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

function hudFromScene(scene, system) {
  if (!window.SharcHud || scene.error) return;
  const sys = system || (scene.satellite ? scene : null);
  const n = (a) => (Array.isArray(a) ? a.length : 0);
  const stats = [];
  const add = (k, v) => { if (v) stats.push([k, String(v)]); };
  add("Base stations", n(scene.base_stations));
  add("Cells", n(scene.hex_centers));
  add("UEs", n(scene.ue_positions));
  add("Buildings", n(scene.buildings));
  add("Anchors", n(scene.anchor_points));
  add("Devices", n(scene.devices));
  if (scene.constellation) {
    add("Satellites", n(scene.constellation.satellites));
    add("Beams", n(scene.constellation.beams));
    add("UEs", scene.constellation.ue_total);
  }
  if (scene.country) {
    add("Sites", n(scene.country.sites));
    add("UEs", scene.country.ue_total);
  }
  if (scene.satellite) add("Satellite", "1");
  if (scene.station) add("Earth station", "1");
  if (sys && sys.satellite) {                           // the numbers that matter for a satellite victim
    const sm = (sys.footprint && sys.footprint.summary) || {};
    const sat = sys.satellite;
    const satWorld = Cesium.Cartesian3.fromDegrees(sat.lon_deg, sat.lat_deg, sat.alt_m);
    const tgt = (sys.footprint && sys.footprint.pointing)
      ? { lat: sys.footprint.pointing.target_lat_deg, lon: sys.footprint.pointing.target_lon_deg }
      : (sys.bs_centroid ? { lat: sys.bs_centroid.lat_deg, lon: sys.bs_centroid.lon_deg }
      : (scene.reference ? { lat: scene.reference.lat_deg, lon: scene.reference.lon_deg } : null));
    add("Sat altitude", `${(sat.alt_m / 1000).toFixed(0)} km`);
    if (tgt) add("Sat elevation @ network", `${elevationDeg(tgt.lat, tgt.lon, satWorld).toFixed(1)}°`);
    if (sm.freq_mhz) add("Sat frequency", `${sm.freq_mhz} MHz`);
    if (sm.imt_freq_mhz) add("IMT frequency", `${sm.imt_freq_mhz} MHz`);
    if (sm.imt_bw_mhz) add("IMT bandwidth", `${sm.imt_bw_mhz} MHz`);
    if (sm.bs_eirp_dbm != null) add("BS EIRP toward sat (max)", `${sm.bs_eirp_dbm} dBm`);
    if (sm.peak_gain_dbi != null) add("Sat peak gain", `${sm.peak_gain_dbi} dBi`);
    if (sm.beamwidth_deg) {
      add("Sat 3 dB beamwidth", `${sm.beamwidth_deg}°`);
      const rKm = (sat.alt_m / 1000) * Math.tan(Cesium.Math.toRadians(sm.beamwidth_deg / 2));   // nadir approximation
      add("-3 dB radius", `${rKm.toFixed(0)} km`);
      add("-3 dB area", `${(Math.PI * rKm * rKm).toExponential(2)} km²`);
    }
    if (sm.inr_db != null) add("I/N estimate", `${sm.inr_db} dB`);
  }
  if (scene.reference) {
    stats.push(["Reference", scene.reference.lat_deg.toFixed(3) + ", " + scene.reference.lon_deg.toFixed(3)]);
  }
  window.SharcHud.setScene({ title: scene.topology_type || "Scene", stats });
  window.SharcHud.setLegend(legendItems(scene, sys));
}

// Legend rows; those with a `layer` are click-to-hide (see hud.js). Only layers present in the scene are listed.
function legendItems(scene, sys) {
  const country = scene.country || (sys && sys.country);
  const items = [{ color: "#4fc3f7", label: "Base station / sector", layer: "bs" }];
  if (country) items.push({ color: "#7986cb", label: "Cell", layer: "cells" }, { color: "#ffd54f", label: "Sector", layer: "sectors" });
  items.push({ color: "#ef5350", label: "UE", layer: "ues" });
  if (!country) items.push({ color: "#ffd54f", label: "Beam", layer: "beams" }, { color: "#7986cb", label: "Cell", layer: "cells" });
  if (sys && sys.satellite) {
    items.push({ color: "#ff1744", label: `Satellite${sys.roles && sys.roles.system ? " (" + sys.roles.system + ")" : ""}`, layer: "sat" },
               { color: "#ff1744", label: "Nadir line / sub-satellite point", layer: "nadir", dash: true },
               { color: "#e040fb", label: "Footprint (-3 dB)", layer: "footprint" });
    if (sys.bs_centroid) items.push({ color: "#ffa726", label: "Boresight: satellite to BS centroid", layer: "boresight", dash: true });
    if (sys.borders) items.push({ color: "#90a4ae", label: "Country borders", layer: "borders" });
  } else if (sys) {
    items.push({ color: "#00e5ff", label: (sys.topology_type || "system") + " (victim)" });
  }
  if (warnSource.entities.values.length) items.push({ color: "#ff5252", label: "Sites on water", layer: "water" });
  return items;
}


// ═══════════════════════════════════════════════════════════════════
// Adaptive terrain and land cover: tiles are requested as the camera moves
// (served by the local tile server, cached on disk), nothing is downloaded up front.
// ═══════════════════════════════════════════════════════════════════
const tileState = { key: null, layers: [] };

function clearTerrain() {
  for (const l of tileState.layers) viewer.imageryLayers.remove(l, true);
  tileState.layers = [];
  viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
  viewer.scene.verticalExaggeration = 1.0;
  viewer.scene.globe.depthTestAgainstTerrain = false;
  tileState.key = null;
}

const hydro = { source: new Cesium.CustomDataSource("hydro"), on: false, timer: null, last: "" };
viewer.dataSources.add(hydro.source);

async function updateHydro() {
  if (!hydro.on) { hydro.source.entities.removeAll(); hydro.last = ""; return; }
  const h = viewer.camera.positionCartographic.height;
  const rect = h < 2.5e6 ? viewer.camera.computeViewRectangle() : null;
  if (!rect) { hydro.source.entities.removeAll(); hydro.last = ""; return; }
  const d = Cesium.Math.toDegrees;
  const box = [d(rect.west), d(rect.south), d(rect.east), d(rect.north)].map((v) => v.toFixed(3));
  const key = box.join(",");
  if (key === hydro.last) return;
  hydro.last = key;
  try {
    const r = await Loading.track('rivers & lakes', fetch(`/hydro?west=${box[0]}&south=${box[1]}&east=${box[2]}&north=${box[3]}`));
    if (!r.ok) return;
    const gj = await r.json();
    hydro.source.entities.removeAll();
    const blue = Cesium.Color.fromCssColorString("#3aa0ff");
    for (const f of gj.features) {
      const g = f.geometry;
      const lines = g.type === "LineString" ? [g.coordinates] : g.type === "MultiLineString" ? g.coordinates : [];
      for (const c of lines) {
        hydro.source.entities.add({ polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(c.flat()), width: 2.2, clampToGround: true,
          material: new Cesium.PolylineGlowMaterialProperty({ glowPower: 0.15, color: blue.withAlpha(0.95) }) } });
      }
      const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
      for (const p of polys) {
        hydro.source.entities.add({ polygon: {
          hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(p[0].flat())),
          material: blue.withAlpha(0.3), outline: false, classificationType: Cesium.ClassificationType.TERRAIN } });
      }
    }
    viewer.scene.requestRender();
  } catch (e) { /* offline: keep the view clean */ }
}
for (const ev of [viewer.camera.moveEnd, viewer.camera.changed]) {
  ev.addEventListener(() => {
    clearTimeout(hydro.timer);
    hydro.timer = setTimeout(updateHydro, 500);
  });
}


// Buildings (OpenStreetMap), extruded from their footprints when the camera is close.
const FACADES = ["#d9d2c3", "#cfc7b8", "#e6e1d6", "#b9a58e", "#c9b79c", "#a8b2bd", "#d8cdb8", "#bfae9a", "#e0d6c5", "#9fa8b0", "#a8685a", "#8d8f94"];
function facadeColor(f) {
  if (bld.clean) return Cesium.Color.fromCssColorString("#f4f5f6");
  const tall = Math.min(1, f.h / 70);
  const base = Cesium.Color.fromCssColorString(FACADES[Math.abs(f.id | 0) % FACADES.length]);
  return Cesium.Color.lerp(base, Cesium.Color.fromCssColorString("#7f9bbd"), tall * 0.55, new Cesium.Color());
}

const bld = { clean: false, realistic: false, source: new Cesium.CustomDataSource("buildings"), on: false, timer: null, last: "", ids: new Set(), max: 3000, dist: 3500, minH: 0 };
viewer.dataSources.add(bld.source);

// ── Trees: OpenStreetMap trees plus vegetation-based trees, drawn as two batched primitives (crowns, trunks).
const trees = { on: false, max: 2500, crowns: null, trunks: null, key: "", dist: 1200 };
function clearTrees() {
  for (const k of ["crowns", "trunks"]) { if (trees[k]) { viewer.scene.primitives.remove(trees[k]); trees[k] = null; } }
  trees.key = "";
}
function setTrees(list) {
  if (!trees.on || !list || !list.length) { clearTrees(); return; }
  const key = list.length + ":" + list[0].join(",") + ":" + list[list.length - 1].join(",");
  if (key === trees.key) return;
  clearTrees(); trees.key = key;
  const crownGeom = new Cesium.EllipsoidGeometry({ radii: new Cesium.Cartesian3(1, 1, 1), stackPartitions: 6, slicePartitions: 8,
    vertexFormat: Cesium.PerInstanceColorAppearance.VERTEX_FORMAT });
  const trunkGeom = new Cesium.CylinderGeometry({ length: 1, topRadius: 0.5, bottomRadius: 0.7, slices: 6,
    vertexFormat: Cesium.PerInstanceColorAppearance.VERTEX_FORMAT });
  const crowns = [], trunks = [];
  const rnd = (i, s) => { const v = Math.sin(i * 12.9898 + s * 78.233) * 43758.5453; return v - Math.floor(v); };
  const trunkColor = Cesium.ColorGeometryInstanceAttribute.fromColor(Cesium.Color.fromCssColorString("#5b4636"));
  list.forEach((t, i) => {
    const th = Math.max(3, t[2] || 8);
    const g = viewer.scene.globe.getHeight(Cesium.Cartographic.fromDegrees(t[0], t[1])) || 0;
    const crownR = th * (0.36 + 0.1 * rnd(i, 1)), trunkLen = th * 0.45, tr = Math.max(0.25, th * 0.03);
    const crownPos = Cesium.Cartesian3.fromDegrees(t[0], t[1], g + trunkLen + crownR * 0.9);
    const trunkPos = Cesium.Cartesian3.fromDegrees(t[0], t[1], g + trunkLen / 2);
    const m1 = Cesium.Matrix4.multiplyByScale(Cesium.Transforms.eastNorthUpToFixedFrame(crownPos), new Cesium.Cartesian3(crownR, crownR, crownR * 1.2), new Cesium.Matrix4());
    const m2 = Cesium.Matrix4.multiplyByScale(Cesium.Transforms.eastNorthUpToFixedFrame(trunkPos), new Cesium.Cartesian3(tr, tr, trunkLen), new Cesium.Matrix4());
    const green = Cesium.Color.fromHsl(0.25 + 0.06 * rnd(i, 2), 0.45 + 0.2 * rnd(i, 3), 0.22 + 0.14 * rnd(i, 4));
    crowns.push(new Cesium.GeometryInstance({ geometry: crownGeom, modelMatrix: m1, attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(green) } }));
    trunks.push(new Cesium.GeometryInstance({ geometry: trunkGeom, modelMatrix: m2, attributes: { color: trunkColor } }));
  });
  const ap = () => new Cesium.PerInstanceColorAppearance({ translucent: false, closed: true });
  trees.crowns = viewer.scene.primitives.add(new Cesium.Primitive({ geometryInstances: crowns, appearance: ap(), asynchronous: false }));
  trees.trunks = viewer.scene.primitives.add(new Cesium.Primitive({ geometryInstances: trunks, appearance: ap(), asynchronous: false }));
  viewer.scene.requestRender();
}

// ── City-scale 3D from streamed tilesets (optional, free Cesium ion token or a Google Map Tiles key):
//   "osm"   = Cesium OSM Buildings (every OpenStreetMap building of the world, LOD streamed, city scale)
//   "photo" = Google Photorealistic 3D Tiles (photogrammetry of buildings and trees), through ion or a Google key
// While one is active our own extruded buildings/trees are hidden so they do not overlap (and, for "photo", the globe).
// The bottom-bar counter follows the globe's own tiles. A hidden globe (photorealistic mode) is no longer updated, so it
// never reports its final "0 pending": the bar then stayed on "loading N map tiles" forever. Clear it when the globe is
// hidden and follow the photorealistic tileset's own progress instead.
function setLoadText(text) {
  const el = document.getElementById("barLoad");
  if (el) el.textContent = text;
}
function clearGlobeTileIndicator() {
  tileLoadPeak = 0;
  setLoadText("");
  Loading.end("map tiles");
}
function trackTilesetProgress(ts) {
  let peak = 0;
  ts.loadProgress.addEventListener((pending, processing) => {
    const n = pending + processing;
    peak = n === 0 ? 0 : Math.max(peak, n);
    setLoadText(n > 0 ? `loading ${n} 3D tiles...` : "");
    if (n > 0) Loading.set("3D tiles", peak - n, peak); else Loading.end("3D tiles");
  });
}

const photoreal = { tileset: null, key: "", busy: false, mode: "" };
async function setPhotoreal(mode, ionToken, googleKey) {
  mode = mode || "";
  ionToken = (ionToken || "").trim();
  googleKey = (googleKey || "").trim();
  if (mode === "photo" && !ionToken && !googleKey) mode = "";
  if (mode === "osm" && !ionToken) mode = "";
  const key = [mode, ionToken, googleKey].join("|");
  if (key === photoreal.key || photoreal.busy) return;
  photoreal.key = key;
  if (photoreal.tileset) {
    viewer.scene.primitives.remove(photoreal.tileset);
    photoreal.tileset = null;
    viewer.scene.globe.show = true;
    setLoadText("");
    Loading.end("3D tiles");
    photoreal.mode = "";
    bld.last = "";
    setTimeout(updateBuildings, 200);
  }
  if (!mode) { viewer.scene.requestRender(); return; }
  photoreal.busy = true;
  Loading.set(mode === "osm" ? "city buildings" : "photorealistic 3D", 0, 0);
  try {
    if (ionToken) Cesium.Ion.defaultAccessToken = ionToken;
    let ts;
    if (mode === "osm") ts = await Cesium.createOsmBuildingsAsync();
    else if (ionToken) ts = await Cesium.Cesium3DTileset.fromIonAssetId(2275207, { showCreditsOnScreen: true, maximumScreenSpaceError: 6 });
    else ts = await Cesium.Cesium3DTileset.fromUrl("https://tile.googleapis.com/v1/3dtiles/root.json?key=" + encodeURIComponent(googleKey),
      { showCreditsOnScreen: true, maximumScreenSpaceError: 6 });
    viewer.scene.primitives.add(ts);
    photoreal.tileset = ts;
    photoreal.mode = mode;
    if (mode === "photo") {
      viewer.scene.globe.show = false;
      clearGlobeTileIndicator();
      trackTilesetProgress(ts);
    }
    if (bld.ids.size) { bld.source.entities.removeAll(); bld.ids.clear(); }
    clearTrees();
    setStatus(mode === "osm" ? "Cesium OSM Buildings on" : "Photorealistic 3D Tiles on");
  } catch (e) {
    photoreal.key = "";
    setStatus("City 3D unavailable: " + (e && e.message ? e.message : e) + " (check the token / key and your internet connection)");
  } finally {
    photoreal.busy = false;
    Loading.end(mode === "osm" ? "city buildings" : "photorealistic 3D");
    viewer.scene.requestRender();
  }
}

// ── Roads (OpenStreetMap highways) drawn as ground corridors in the "clean city model" look.
const roads = { source: new Cesium.CustomDataSource("roads"), ids: new Set(), on: false };
viewer.dataSources.add(roads.source);
function setRoads(list) {
  if (!roads.on) { if (roads.ids.size) { roads.source.entities.removeAll(); roads.ids.clear(); } return; }
  const color = Cesium.Color.fromCssColorString("#7c828c");
  for (const [w, pts] of list || []) {
    const id = pts[0].join(",") + ">" + pts[pts.length - 1].join(",") + ":" + pts.length;
    if (roads.ids.has(id)) continue;
    roads.ids.add(id);
    roads.source.entities.add({ corridor: { positions: Cesium.Cartesian3.fromDegreesArray(pts.flat()), width: w,
      material: color, cornerType: Cesium.CornerType.ROUNDED, classificationType: Cesium.ClassificationType.TERRAIN } });
  }
  if (roads.ids.size > 6000) { roads.source.entities.removeAll(); roads.ids.clear(); }
  viewer.scene.requestRender();
}

function heightAboveGround() {
  const c = viewer.camera.positionCartographic;
  const g = viewer.scene.globe.getHeight(c);
  return g === undefined ? c.height : Math.max(0, c.height - g);
}

async function updateBuildings() {
  if (photoreal.tileset) return;
  const h = heightAboveGround();
  if (h > trees.dist) clearTrees();
  if (!bld.on || h > bld.dist) { if (bld.ids.size) { bld.source.entities.removeAll(); bld.ids.clear(); } bld.last = ""; return; }
  // Only the ground around the screen centre (a tilted view's full rectangle reaches the horizon).
  const cv = viewer.scene.canvas;
  // Pick the terrain, not the sea-level ellipsoid: at 1100 m elevation (Brasilia) the ellipsoid hit lies km away.
  const centre = new Cesium.Cartesian2(cv.clientWidth / 2, cv.clientHeight / 2);
  const hit = viewer.scene.globe.pick(viewer.camera.getPickRay(centre), viewer.scene)
    || viewer.camera.pickEllipsoid(centre, viewer.scene.globe.ellipsoid);
  if (!hit) return;
  const c = Cesium.Cartographic.fromCartesian(hit);
  const d = Cesium.Math.toDegrees;
  const half = Math.min(0.0045, Math.max(0.002, (h * 0.9) / 111000));
  const box = [d(c.longitude) - half, d(c.latitude) - half, d(c.longitude) + half, d(c.latitude) + half]
    .map((v) => v.toFixed(4));
  try {
    const r = await Loading.track('buildings', fetch(`/buildings?west=${box[0]}&south=${box[1]}&east=${box[2]}&north=${box[3]}&trees=${trees.on && h <= trees.dist ? trees.max : 0}&roads=${roads.on ? 1 : 0}`));
    if (!r.ok) return;
    const gj = await r.json();
    const cx = d(c.longitude), cy = d(c.latitude);
    const near = gj.features.filter((f) => f.h >= bld.minH).map((f) => ({ f, d: Math.hypot(f.ring[0][0] - cx, f.ring[0][1] - cy) }))
      .sort((a, b) => a.d - b.d).slice(0, bld.max).map((o) => o.f);
    if (bld.ids.size + near.length > bld.max * 1.6) { bld.source.entities.removeAll(); bld.ids.clear(); }
    for (const f of near) {
      if (bld.ids.has(f.id)) continue;
      bld.ids.add(f.id);
      const color = facadeColor(f);
      bld.source.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(f.ring.flat())),
          height: 0, extrudedHeight: f.h, shadows: Cesium.ShadowMode.ENABLED,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          extrudedHeightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
          material: color, outline: false,
        },
      });
    }
    viewer.scene.requestRender();
    if (trees.on && h <= trees.dist) setTrees(gj.trees || []);
    setRoads(gj.roads || []);
    if (gj.error) setStatus('buildings unavailable (OpenStreetMap servers busy): ' + gj.error);
    if (gj.pending > 0) { clearTimeout(bld.timer); bld.timer = setTimeout(updateBuildings, 4000); }   // tiles still downloading
  } catch (e) { /* offline */ }
}
for (const ev of [viewer.camera.moveEnd, viewer.camera.changed]) {
  ev.addEventListener(() => {
    clearTimeout(bld.timer);
    bld.timer = setTimeout(updateBuildings, 600);
  });
}

// Warning for base stations on water: red markers in the scene + a note in the scene card.
const warnSource = new Cesium.CustomDataSource("site-warnings");
viewer.dataSources.add(warnSource);

function setSiteWarning(info) {
  warnSource.entities.removeAll();
  const card = document.getElementById("hudScene");
  let box = document.getElementById("hudWarn");
  if (!info) { if (box) box.remove(); return; }
  if (!box) {
    box = document.createElement("div");
    box.id = "hudWarn";
    box.className = "warn";
    card.appendChild(box);
  }
  box.textContent = "";
  const msg = document.createElement("div");
  msg.textContent = "\u26A0 " + info.message;
  box.appendChild(msg);
  const chips = document.createElement("div");
  chips.className = "chips";
  const sites = info.sites || [];
  const flyTo = (s) => viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(s.lon, s.lat, 12000), duration: 1.2 });
  sites.slice(0, 24).forEach((s) => {                   // one chip per site: click to fly there
    const b = document.createElement("button");
    b.textContent = "#" + (s.index + 1);
    b.title = `Fly to site ${s.index + 1} (${s.lat.toFixed(3)}, ${s.lon.toFixed(3)})`;
    b.addEventListener("click", () => flyTo(s));
    chips.appendChild(b);
  });
  if (sites.length > 24) chips.appendChild(document.createTextNode(` +${sites.length - 24} more`));
  if (window.pyBridge && window.pyBridge.resample_sites) {
    const r = document.createElement("button");
    r.className = "act";
    r.textContent = "Resample";
    r.title = "Draw the sites again with the next seed";
    r.addEventListener("click", () => { r.disabled = true; r.textContent = "Resampling..."; window.pyBridge.resample_sites(); });
    chips.appendChild(r);
  }
  box.appendChild(chips);
  const blink = new Cesium.CallbackProperty(() =>                     // pulsing ring so the eye finds the site
    Cesium.Color.fromCssColorString("#ff5252").withAlpha(0.45 + 0.55 * Math.abs(Math.sin(Date.now() / 350))), false);
  for (const s of sites) {
    tag(warnSource.entities.add({
      position: Cesium.Cartesian3.fromDegrees(s.lon, s.lat, 30),
      point: { pixelSize: 16, color: Cesium.Color.TRANSPARENT, outlineColor: blink,
               outlineWidth: 3, disableDepthTestDistance: Number.POSITIVE_INFINITY },
      label: { text: "ON WATER", font: "bold 11px 'Segoe UI', sans-serif", fillColor: Cesium.Color.fromCssColorString("#ff8a80"),
               outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
               verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -14),
               distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 60000),
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }), "water");
  }
  if (window.SharcHud && lastScene) window.SharcHud.setLegend(legendItems(lastScene.imt || lastScene, lastScene.system || null));
  viewer.scene.requestRender();
}

// "Loading terrain tiles" indicator in the bottom bar.
let tileLoadPeak = 0;
(function () {
  const bar = document.getElementById("hudBar");
  if (!bar) return;
  const el = document.createElement("span");
  el.id = "barLoad";
  el.style.color = "#d9a23b";
  bar.insertBefore(el, document.getElementById("barBase"));
  viewer.scene.globe.tileLoadProgressEvent.addEventListener((n) => {
    el.textContent = n > 0 ? `loading ${n} map tiles...` : "";
    tileLoadPeak = n === 0 ? 0 : Math.max(tileLoadPeak, n);
    if (n > 0) Loading.set("map tiles", tileLoadPeak - n, tileLoadPeak); else Loading.end("map tiles");
  });
})();

// ═══════════════════════════════════════════════════════════════════
// Place the simulation scenario on the map: draggable centre marker, click-to-place,
// right-click menu and a "go to coordinates" box.
// ═══════════════════════════════════════════════════════════════════
const place = { source: new Cesium.CustomDataSource("scenario-center"), marker: null, dragging: false, mode: false };
viewer.dataSources.add(place.source);

const PIN_SVG = "data:image/svg+xml;utf8," + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="52" viewBox="0 0 40 52">' +
  '<path d="M20 50 C20 50 4 30 4 19 a16 16 0 1 1 32 0 C36 30 20 50 20 50Z" fill="#4f9dde" stroke="#ffffff" stroke-width="2.5"/>' +
  '<circle cx="20" cy="19" r="6" fill="#ffffff"/></svg>');

function groundPick(pos) {
  const ray = viewer.camera.getPickRay(pos);
  if (!ray) return null;
  return viewer.scene.globe.pick(ray, viewer.scene) || viewer.camera.pickEllipsoid(pos, viewer.scene.globe.ellipsoid) || null;
}

function cartToLatLon(c) {
  const g = Cesium.Cartographic.fromCartesian(c);
  return { lat: Cesium.Math.toDegrees(g.latitude), lon: Cesium.Math.toDegrees(g.longitude) };
}

function showCenterMarker(ref) {
  place.source.entities.removeAll();
  if (!ref) return;
  place.marker = place.source.entities.add({
    id: "scenario-center", name: "Scenario centre",
    position: Cesium.Cartesian3.fromDegrees(ref.lon_deg, ref.lat_deg, (ref.alt_m || 0) + 3),
    billboard: { image: PIN_SVG, width: 28, height: 36, verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                 disableDepthTestDistance: Number.POSITIVE_INFINITY, scaleByDistance: new Cesium.NearFarScalar(2000, 1.2, 2.0e6, 0.6) },
    label: { text: "Scenario centre - drag to move", font: "11px 'Segoe UI', sans-serif",
             fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
             style: Cesium.LabelStyle.FILL_AND_OUTLINE, verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
             pixelOffset: new Cesium.Cartesian2(0, -40), showBackground: false,
             distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 80000),
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
  });
}

function commitCenter(lat, lon) {
  if (window.pyBridge && window.pyBridge.set_scenario_center) window.pyBridge.set_scenario_center(lat, lon);
  setStatus(`scenario centre -> ${lat.toFixed(5)}, ${lon.toFixed(5)}`);
}

function setPlaceMode(on) {
  place.mode = on;
  document.body.classList.toggle("placing", on);
  const b = document.getElementById("btnPlace");
  if (b) b.classList.toggle("on", on);
}

(function wirePlacement() {
  const canvas = viewer.scene.canvas;
  const handler = new Cesium.ScreenSpaceEventHandler(canvas);
  const ctrl = viewer.scene.screenSpaceCameraController;

  handler.setInputAction((e) => {
    const picked = viewer.scene.pick(e.position);
    if (picked && picked.id && picked.id.id === "scenario-center") {
      place.dragging = true;
      ctrl.enableInputs = false;
    }
  }, Cesium.ScreenSpaceEventType.LEFT_DOWN);

  handler.setInputAction((e) => {
    if (!place.dragging || !place.marker) return;
    const c = groundPick(e.endPosition);
    if (c) place.marker.position = c;
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

  handler.setInputAction((e) => {
    if (!place.dragging) return;
    place.dragging = false;
    ctrl.enableInputs = true;
    const c = groundPick(e.position);
    if (c) { const ll = cartToLatLon(c); commitCenter(ll.lat, ll.lon); }
  }, Cesium.ScreenSpaceEventType.LEFT_UP);

  handler.setInputAction((e) => {
    if (!place.mode) return;
    const c = groundPick(e.position);
    setPlaceMode(false);
    if (c) { const ll = cartToLatLon(c); commitCenter(ll.lat, ll.lon); }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  // right-click menu
  let menu = null;
  const closeMenu = () => { if (menu) { menu.remove(); menu = null; } };
  document.addEventListener("click", closeMenu);
  canvas.addEventListener("contextmenu", (ev) => {
    ev.preventDefault();
    closeMenu();
    const rect = canvas.getBoundingClientRect();
    const c = groundPick(new Cesium.Cartesian2(ev.clientX - rect.left, ev.clientY - rect.top));
    const ll = c ? cartToLatLon(c) : null;
    menu = document.createElement("div");
    menu.className = "ctx";
    menu.style.left = Math.min(ev.clientX, window.innerWidth - 210) + "px";
    menu.style.top = Math.min(ev.clientY, window.innerHeight - 160) + "px";
    const add = (text, fn, cls) => {
      const d = document.createElement("div");
      d.textContent = text;
      if (cls) d.className = cls;
      if (fn) d.addEventListener("click", (e2) => { e2.stopPropagation(); closeMenu(); fn(); });
      menu.appendChild(d);
    };
    if (ll) add(`${ll.lat.toFixed(5)}, ${ll.lon.toFixed(5)}`, null, "hd");
    if (ll) add("Place scenario here", () => commitCenter(ll.lat, ll.lon));
    if (ll) add("Copy coordinates", () => {
      const t = `${ll.lat.toFixed(6)}, ${ll.lon.toFixed(6)}`;
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).catch(() => {});
      else { const ta = document.createElement("textarea"); ta.value = t; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
    });
    if (ll) add("Zoom here", () => viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(ll.lon, ll.lat, 3000) }));
    const sep = document.createElement("div"); sep.className = "sep"; menu.appendChild(sep);
    add("Zoom to scenario", () => { if (place.marker) viewer.flyTo(place.source, { duration: 1.2 }); });
    add("Reset view", () => viewer.camera.flyHome(1.0));
    document.body.appendChild(menu);
  });

  // toolbar button + go-to box
  const btn = document.getElementById("btnPlace");
  if (btn) btn.addEventListener("click", () => setPlaceMode(!place.mode));
  const box = document.getElementById("gotoBox");
  const parse = () => {
    const m = (box.value || "").replace(/,/g, " ").match(/(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/);
    return m ? { lat: parseFloat(m[1]), lon: parseFloat(m[2]) } : null;
  };
  const go = () => {
    const p = parse();
    if (!p || Math.abs(p.lat) > 90 || Math.abs(p.lon) > 180) { box.style.borderColor = "#e0605a"; return null; }
    box.style.borderColor = "";
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(p.lon, p.lat, 12000) });
    return p;
  };
  if (box) {
    box.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); e.stopPropagation(); });
    document.getElementById("gotoGo").addEventListener("click", go);
    document.getElementById("gotoPlace").addEventListener("click", () => { const p = go(); if (p) commitCenter(p.lat, p.lon); });
  }
})();

function warmTiles(lat, lon) {
  fetch(`/warm?lat=${lat}&lon=${lon}&z=15`).catch(() => {});
}

// Cinematic look: ambient occlusion, filmic tone mapping and a time-of-day sun (Cesium 1.119 APIs).
function applyRealism(t) {
  try { applyRealismUnsafe(t); } catch (e) { console.error("[realism] " + (e && e.message)); }
}

function applyRealismUnsafe(t) {
  const scene = viewer.scene;
  const on = !!(t && t.effects);
  const ao = scene.postProcessStages.ambientOcclusion;
  // AO samples the depth buffer: it haloes photogrammetry tiles, so skip it there.
  const aoOk = false;  // AO blanked the scene in QtWebEngine; re-enable only after testing on target GPUs
  ao.enabled = aoOk;
  if (aoOk) {
    Object.assign(ao.uniforms, { intensity: 2.5, bias: 0.1, lengthCap: 0.26, stepSize: 1.95, frustumLength: 1000.0 });
  }
  scene.postProcessStages.tonemapper = on ? Cesium.Tonemapper.ACES : Cesium.Tonemapper.REINHARD;
  if (typeof t.sun_hour !== "number" || street.on) { scene.requestRender(); return; }
  const lon = Cesium.Math.toDegrees(viewer.camera.positionCartographic.longitude);
  const utcH = (((t.sun_hour - lon / 15) % 24) + 24) % 24;
  viewer.clock.currentTime = Cesium.JulianDate.fromDate(new Date(Date.UTC(2026, 2, 21) + Math.round(utcH * 3600e3)));
  viewer.clock.shouldAnimate = false;
  const day = Cesium.Math.clamp((Math.cos(((t.sun_hour - 12) / 12) * Math.PI) + 0.15) / 1.15, 0, 1);
  scene.globe.atmosphereLightIntensity = Cesium.Math.lerp(3.0, 14.0, day);
  scene.fog.minimumBrightness = Cesium.Math.lerp(0.02, 0.08, day);
  scene.requestRender();
}

function applyDetail(t) {
  // Quality knobs from the Terrain tab (they also apply when terrain streaming is off).
  if (!t) return;
  viewer.scene.globe.maximumScreenSpaceError = t.sse || 1.5;
  viewer.resolutionScale = t.render_scale || Math.min(window.devicePixelRatio || 1, 2);
  bld.realistic = !!t.realistic;
  bld.clean = !!t.clean;
  viewer.shadows = !!(t.clean || t.realistic);
  if (t.clean || t.realistic) { viewer.shadowMap.softShadows = true; viewer.shadowMap.maximumDistance = 4000; viewer.shadowMap.darkness = 0.55; viewer.shadowMap.size = 2048; }
  if (t.clean || t.realistic) viewer.scene.light = new Cesium.SunLight();
  roads.on = !!t.clean;
  setPhotoreal(t.city_mode || "", t.ion_token || "", t.photoreal_key || "");
  applyRealism(t);
  // Photogrammetry: follow the map-quality setting (lower error = sharper, heavier) and keep more tiles cached.
  if (photoreal.tileset) {
    photoreal.tileset.maximumScreenSpaceError = Math.max(2, (t.sse || 1.5) * 2.5);
    photoreal.tileset.cacheBytes = 1024 * 1024 * 1024;
    photoreal.tileset.maximumCacheOverflowBytes = 512 * 1024 * 1024;
  }
  trees.on = !!t.trees; trees.max = t.trees_max || 2500;
  if (!trees.on) clearTrees();
  bld.max = Math.max(t.buildings_max || 3000, t.clean ? 8000 : 0);
  bld.dist = t.buildings_distance_m || 3500;
  bld.minH = t.buildings_min_height || 0;
  if (t.basemap && window.SharcBasemaps && window.SharcBasemaps.current() !== t.basemap) window.SharcBasemaps.set(t.basemap);
}

function applyTerrain(t) {
  applyDetail(t);
  hydro.on = !!(t && t.hydro);
  bld.on = !!(t && t.buildings);
  updateBuildings();
  hydro.last = "";
  updateHydro();
  if (!t) { if (tileState.key) clearTerrain(); return; }
  const key = [t.clean, t.relief, t.clutter, t.hillshade, t.exaggeration, t.opacity, t.relief_samples, t.max_level,
    t.world_terrain, t.world_terrain ? t.ion_token : ""].join("|");
  if (key === tileState.key) return;
  clearTerrain();
  tileState.key = key;
  const merc = new Cesium.WebMercatorTilingScheme();
  const addLayer = (url, alpha) => {
    const provider = new Cesium.UrlTemplateImageryProvider({
      url, tilingScheme: merc, tileWidth: 256, tileHeight: 256, maximumLevel: t.max_level || 15,
    });
    const layer = viewer.imageryLayers.addImageryProvider(provider);
    layer.alpha = alpha;
    tileState.layers.push(layer);
  };
  if (t.hillshade) addLayer("/tiles/hillshade/{z}/{x}/{y}.png", 0.5);
  if (t.clutter) addLayer(t.clean ? "/tiles/clutter_clean/{z}/{x}/{y}.png" : "/tiles/clutter/{z}/{x}/{y}.png", t.opacity);
  if (t.relief && t.world_terrain && t.ion_token) {
    // Cesium World Terrain (ion): much finer than the 30 m SRTM tiles, no "waves" over cities.
    Cesium.Ion.defaultAccessToken = t.ion_token;
    Cesium.createWorldTerrainAsync({ requestVertexNormals: true }).then((tp) => {
      viewer.terrainProvider = tp;
      viewer.scene.verticalExaggeration = t.exaggeration || 1.0;
      viewer.scene.globe.depthTestAgainstTerrain = true;
      setStatus("Cesium World Terrain on");
      viewer.scene.requestRender();
    }).catch((e) => {
      tileState.key = "";                      // let the next change retry
      setStatus("Cesium World Terrain unavailable: " + (e && e.message ? e.message : e) + " (check the ion token)");
    });
  } else if (t.relief) {
    const W = t.relief_samples || 65;
    viewer.terrainProvider = new Cesium.CustomHeightmapTerrainProvider({
      width: W, height: W, tilingScheme: merc,
      callback: async (x, y, level) => {
        try {
          // A tile that fails once (busy network) must not stay flat at 0 m: retry before giving up.
          let r = null;
          for (let attempt = 0; attempt < 4; attempt++) {
            r = await fetch(`/tiles/terrain/${level}/${x}/${y}.f32?v=6`);
            if (r.ok) break;
            if (r.status === 404 && attempt >= 1) break;               // no data for this tile (e.g. open sea)
            await new Promise((res) => setTimeout(res, 600 * (attempt + 1)));
          }
          if (!r || !r.ok) return new Float32Array(W * W);
          const src = new Float32Array(await r.arrayBuffer());      // 256 x 256, row 0 = north
          if (src.length !== 256 * 256) return new Float32Array(W * W);
          const out = new Float32Array(W * W);
          for (let j = 0; j < W; j++) {
            const sy = Math.min(255, Math.round((j * 255) / (W - 1)));
            for (let i = 0; i < W; i++) out[j * W + i] = src[sy * 256 + Math.min(255, Math.round((i * 255) / (W - 1)))];
          }
          return out;
        } catch (e) { return new Float32Array(W * W); }
      },
    });
    viewer.terrainProvider.errorEvent.addEventListener((e) => console.error('[terrain] ' + (e && e.message)));
    viewer.scene.verticalExaggeration = t.exaggeration || 1.0;
    viewer.scene.globe.depthTestAgainstTerrain = true;
  }
  viewer.scene.requestRender();
}

function showSceneProblem(scene) {
  const card = document.getElementById("hudScene");
  if (card) card.classList.add("problem");
  const title = document.getElementById("hudTitle");
  if (title) title.textContent = "Scenario problem";
  const stats = document.getElementById("hudStats");
  if (stats) {
    stats.textContent = "";
    const msg = document.createElement("div");
    msg.className = "problem-msg";
    msg.textContent = String(scene.error);
    stats.appendChild(msg);
  }
  if (window.SharcHud) window.SharcHud.setLegend([]);
}

function clearSceneProblem() {
  const card = document.getElementById("hudScene");
  if (card) card.classList.remove("problem");
}

function renderPart(scene) {
  if (scene.constellation !== undefined) renderMssDcScene(scene);
  else if (scene.buildings !== undefined) renderIndoorScene(scene);
  else if (scene.anchor_points !== undefined) renderNtnScene(scene);
  else if (scene.satellite !== undefined) renderSingleSpaceStationScene(scene);
  else if (scene.devices !== undefined) renderD2DScene(scene);
  else if (scene.station !== undefined) renderSingleStationScene(scene);
  else renderHexSectorScene(scene);
}

function renderComposite(scene) {
  showCenterMarker(scene.imt && scene.imt.reference);
  if (scene.terrain && scene.imt && scene.imt.reference) warmTiles(scene.imt.reference.lat_deg, scene.imt.reference.lon_deg);
  const realZoom = viewer.zoomTo.bind(viewer);
  viewer.zoomTo = () => Promise.resolve(true);   // só enquadra uma vez, no fim
  if (scene.imt && scene.imt.reference) frame.points.push(Cesium.Cartesian3.fromDegrees(scene.imt.reference.lon_deg, scene.imt.reference.lat_deg, 0));
  renderPart(scene.imt);
  const imtCount = viewer.entities.values.length;
  const imtEntities = viewer.entities.values.slice();
  if (scene.system) renderPart(scene.system);
  autoTag();
  if (lobes.on) setLobes(true);                        // refresh the colour bar after a redraw
  if (interf.on || interf.bsEnts.length) setInterf(interf.on);   // victim position is known only now
  viewer.zoomTo = realZoom;
  // enquadra a rede IMT (a escala de células); o sistema fica a um zoom-out
  viewer.zoomTo(imtEntities.length ? imtEntities : viewer.entities);
  if (window.SharcHud) {
    hudFromScene(scene.imt, scene.system);
  }
  if (scene.system && scene.system.satellite) frameScene();   // satellite + network in one frame, never a beam without origin
  setStatus((scene.topology_type || '') + ': ' + imtCount + ' IMT entities' + (scene.system ? ' + victim system' : ''));
}

// ── Protection contour (Protection Contour page): one curve per BS off-axis angle around the protected station, clamped
//    to the terrain, with violated ray ends and the end of the rays. Lives in its own data source, so it survives the
//    scene redraws (`viewer.entities.removeAll()`). Data: core/contour_scene.payload().
const contour = { ds: null, data: null };

function contourSource() {
  if (!contour.ds) {
    contour.ds = new Cesium.CustomDataSource("Protection contour");
    viewer.dataSources.add(contour.ds);
  }
  return contour.ds;
}

function clearContour() {
  contour.data = null;
  if (contour.ds) contour.ds.entities.removeAll();
  viewer.scene.requestRender();
}

function setContour(payload, fly) {
  const d = typeof payload === "string" ? JSON.parse(payload) : payload;
  const ds = contourSource();
  ds.entities.removeAll();
  contour.data = d;
  if (!d) { viewer.scene.requestRender(); return; }
  d.curves.forEach((c, i) => {
    const color = Cesium.Color.fromCssColorString(c.color);
    const positions = Cesium.Cartesian3.fromDegreesArray(c.points.flat());
    ds.entities.add({ name: c.label, polyline: { positions, width: 3, material: color, clampToGround: true } });
    if (i === 0 && c.points.length > 3) {              // the first curve (usually off-axis 0) as a translucent area
      ds.entities.add({ name: c.label + " (area)",
        polygon: { hierarchy: new Cesium.PolygonHierarchy(positions), material: color.withAlpha(0.16), classificationType: Cesium.ClassificationType.TERRAIN } });
    }
  });
  if (d.ray_ends && d.ray_ends.length > 2) {
    ds.entities.add({ name: "End of the rays",
      polyline: { positions: Cesium.Cartesian3.fromDegreesArray(d.ray_ends.flat()), width: 1.5, clampToGround: true,
                  material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.WHITE.withAlpha(0.55) }) } });
  }
  (d.violated || []).forEach((v) => {
    ds.entities.add({ name: "Criterion still violated at the end of this ray (off-axis " + v.off_axis_deg + ")",
      position: Cesium.Cartesian3.fromDegrees(v.lon, v.lat),
      point: { pixelSize: 9, color: Cesium.Color.fromCssColorString(v.color), outlineColor: Cesium.Color.WHITE, outlineWidth: 2,
               heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY } });
  });
  ds.entities.add({ name: d.station.name,
    position: Cesium.Cartesian3.fromDegrees(d.station.lon, d.station.lat),
    point: { pixelSize: 11, color: Cesium.Color.BLACK, outlineColor: Cesium.Color.WHITE, outlineWidth: 2,
             heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: { text: d.station.name, font: "12px sans-serif", fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK,
             outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, -18),
             heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: Number.POSITIVE_INFINITY } });
  if (fly !== false && d.bounds) {
    const [w, s, e, n] = d.bounds, padX = Math.max((e - w) * 0.35, 0.02), padY = Math.max((n - s) * 0.35, 0.02);
    viewer.camera.flyTo({ destination: Cesium.Rectangle.fromDegrees(w - padX, s - padY, e + padX, n + padY), duration: 1.2 });
  }
  setStatus(`Protection contour: ${d.curves.length} curve(s) around ${d.station.name}` +
            (d.violated && d.violated.length ? `; ${d.violated.length} ray(s) still violate the criterion where they end` : ""));
  viewer.scene.requestRender();
}

let lastScene = null;
function renderScene(scene) {
  lastScene = scene;
  viewer.entities.removeAll();
  frame.points = [];
  showWarnings(scene.warnings);
  applyTerrain(scene.terrain || null);
  if (scene.composite && !scene.error) { clearSceneProblem(); renderComposite(scene); return; }
  if (scene.error) {
    setStatus("scene error: " + scene.error);
    showSceneProblem(scene);
    return;
  }
  clearSceneProblem();
  if (scene.constellation !== undefined) {
    renderMssDcScene(scene);
  } else if (scene.buildings !== undefined) {
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
  autoTag();
  hudFromScene(scene);
}

function requestScene(topologyType) {
  if (!window.pyBridge) return;
  setStatus(`loading ${topologyType}…`);
  Loading.set('scenario', 0, 0);
  window.pyBridge.get_scene(topologyType, function (json) {
    try {
      renderScene(JSON.parse(json));
    } catch (e) {
      setStatus("render failed: " + e);
    } finally {
      Loading.end('scenario');
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
    if (pyBridge.notify_ready) pyBridge.notify_ready();
    if (!isEmbedded) {
      requestScene(document.getElementById("topoSelect").value);
    }
  });
} else {
  setStatus("viewer ready (no QWebChannel — standalone browser?)");
}


// ═══════════════════════════════════════════════════════════════════
// Street view: walk through the scene at eye level (procedural 3D from real data, not photographs).
// W A S D / arrows move, drag looks around, Shift runs, Q/E change eye height, Esc leaves.
// ═══════════════════════════════════════════════════════════════════
const street = { on: false, keys: new Set(), lon: 0, lat: 0, heading: 0, pitch: 0, eye: 1.7, saved: null, fog: null, drag: null, tick: null, busy: false };
const STREET_CTL = ["enableRotate", "enableTranslate", "enableZoom", "enableTilt", "enableLook"];
function enterStreet() {
  if (street.on) return;
  const cv = viewer.scene.canvas;
  const hit = viewer.camera.pickEllipsoid(new Cesium.Cartesian2(cv.clientWidth / 2, cv.clientHeight / 2), viewer.scene.globe.ellipsoid);
  const c = hit ? Cesium.Cartographic.fromCartesian(hit)
    : (place.marker ? Cesium.Cartographic.fromCartesian(place.marker.position.getValue(Cesium.JulianDate.now())) : null);
  if (!c) return;
  const cam = viewer.camera;
  street.saved = { pos: cam.positionWC.clone(), heading: cam.heading, pitch: cam.pitch, roll: cam.roll };
  street.lon = Cesium.Math.toDegrees(c.longitude); street.lat = Cesium.Math.toDegrees(c.latitude);
  street.heading = cam.heading; street.pitch = 0; street.eye = 1.7;
  // Terrain height under the view centre (the globe may not report heights for tiles still loading).
  const terrainHit = viewer.scene.globe.pick(cam.getPickRay(new Cesium.Cartesian2(cv.clientWidth / 2, cv.clientHeight / 2)), viewer.scene);
  street.lastG = terrainHit ? Cesium.Cartographic.fromCartesian(terrainHit).height : 0;
  if (terrainHit) { const tc = Cesium.Cartographic.fromCartesian(terrainHit); street.lon = Cesium.Math.toDegrees(tc.longitude); street.lat = Cesium.Math.toDegrees(tc.latitude); }
  const sc = viewer.scene, ctl = sc.screenSpaceCameraController;
  street.fog = { en: sc.fog.enabled, d: sc.fog.density, sky: sc.skyAtmosphere ? sc.skyAtmosphere.show : false,
                 ground: sc.globe.showGroundAtmosphere, near: cam.frustum.near };
  STREET_CTL.forEach((k) => { ctl[k] = false; });
  sc.fog.enabled = true; sc.fog.density = 0.0007; sc.fog.minimumBrightness = 0.12;
  if (sc.skyAtmosphere) sc.skyAtmosphere.show = true;
  sc.globe.showGroundAtmosphere = true;
  cam.frustum.near = 0.3;
  trees.dist = 1200; bld.dist = Math.max(bld.dist, 2500);
  street.on = true;
  document.getElementById("btnStreet").classList.add("on");
  setStatus("street view: W A S D move, drag to look, Shift run, Esc leave");
  street.tick = streetStep;
  viewer.scene.preRender.addEventListener(street.tick);
  setTimeout(updateBuildings, 300);
}
function leaveStreet() {
  if (!street.on) return;
  street.on = false;
  viewer.scene.preRender.removeEventListener(street.tick);
  const sc = viewer.scene, ctl = sc.screenSpaceCameraController;
  STREET_CTL.forEach((k) => { ctl[k] = true; });
  sc.fog.enabled = street.fog.en; sc.fog.density = street.fog.d;
  if (sc.skyAtmosphere) sc.skyAtmosphere.show = street.fog.sky;
  sc.globe.showGroundAtmosphere = street.fog.ground;
  viewer.camera.frustum.near = street.fog.near;
  viewer.camera.setView({ destination: street.saved.pos,
    orientation: { heading: street.saved.heading, pitch: street.saved.pitch, roll: street.saved.roll } });
  document.getElementById("btnStreet").classList.remove("on");
  setStatus("street view closed");
}
function streetStep() {
  if (!street.on) return;
  const speed = (street.keys.has("shift") ? 12 : 3.5) / 60;                 // metres per frame (~60 fps)
  let f = 0, r = 0;
  if (street.keys.has("w") || street.keys.has("arrowup")) f += 1;
  if (street.keys.has("s") || street.keys.has("arrowdown")) f -= 1;
  if (street.keys.has("d") || street.keys.has("arrowright")) r += 1;
  if (street.keys.has("a") || street.keys.has("arrowleft")) r -= 1;
  if (street.keys.has("q")) street.eye = Math.max(1.0, street.eye - 0.05);
  if (street.keys.has("e")) street.eye = Math.min(60, street.eye + 0.05);
  const mLat = 111320, mLon = 111320 * Math.cos(Cesium.Math.toRadians(street.lat));
  street.lon += ((Math.sin(street.heading) * f + Math.cos(street.heading) * r) * speed) / mLon;
  street.lat += ((Math.cos(street.heading) * f - Math.sin(street.heading) * r) * speed) / mLat;
  const gh = viewer.scene.globe.getHeight(Cesium.Cartographic.fromDegrees(street.lon, street.lat));
  if (gh !== undefined) street.lastG = gh;
  const g = street.lastG;
  viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(street.lon, street.lat, g + street.eye),
    orientation: { heading: street.heading, pitch: street.pitch, roll: 0 } });
  if ((f || r) && !street.busy) { street.busy = true; setTimeout(() => { street.busy = false; updateBuildings(); }, 1200); }
}
(function () {
  const btn = document.getElementById("btnStreet");
  if (btn) btn.addEventListener("click", () => (street.on ? leaveStreet() : enterStreet()));
  window.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if (k === "escape") { leaveStreet(); return; }
    if (street.on) { street.keys.add(k); if (k.startsWith("arrow")) e.preventDefault(); }
  });
  window.addEventListener("keyup", (e) => street.keys.delete(e.key.toLowerCase()));
  const cv = viewer.scene.canvas;
  cv.addEventListener("pointerdown", (e) => { if (street.on) { street.drag = { x: e.clientX, y: e.clientY }; cv.setPointerCapture(e.pointerId); } });
  cv.addEventListener("pointerup", () => { street.drag = null; });
  cv.addEventListener("pointermove", (e) => {
    if (!street.on || !street.drag) return;
    street.heading += (e.clientX - street.drag.x) * 0.004;
    street.pitch = Math.max(-1.2, Math.min(1.2, street.pitch - (e.clientY - street.drag.y) * 0.004));
    street.drag = { x: e.clientX, y: e.clientY };
  });
  window.SharcStreet = { enter: enterStreet, leave: leaveStreet, state: street };
})();


// ═════════════════════════════════════════════════
// Navigation: damped, collision-aware camera; Shift/Ctrl/middle drag tilts; double-click flies to the point under the cursor;
// arrow / Q E / N T keys; compass and help card.
// ═════════════════════════════════════════════════
(function navigation() {
  const cam = viewer.camera, canvas = viewer.canvas, ctl = viewer.scene.screenSpaceCameraController;
  const T = Cesium.CameraEventType, M = Cesium.KeyboardEventModifier;
  ctl.enableCollisionDetection = true;
  ctl.minimumZoomDistance = 25;                       // never dive into the ground
  ctl.maximumZoomDistance = 6.0e7;
  ctl.inertiaSpin = 0.92; ctl.inertiaTranslate = 0.92; ctl.inertiaZoom = 0.82;
  ctl.tiltEventTypes = [T.MIDDLE_DRAG, T.PINCH, { eventType: T.LEFT_DRAG, modifier: M.CTRL }, { eventType: T.RIGHT_DRAG, modifier: M.CTRL },
                        { eventType: T.LEFT_DRAG, modifier: M.SHIFT }];
  ctl.zoomEventTypes = [T.RIGHT_DRAG, T.WHEEL, T.PINCH];

  const deg = Cesium.Math.toDegrees, rad = Cesium.Math.toRadians;
  const centrePoint = () => groundPick(new Cesium.Cartesian2(canvas.clientWidth / 2, canvas.clientHeight / 2));

  // Orbit about the screen centre: new heading / pitch keep the distance to the point looked at.
  function orbit(headingDeg, pitchDeg) {
    const target = centrePoint();
    if (!target) return;
    const range = Cesium.Cartesian3.distance(cam.positionWC, target);
    const h = headingDeg == null ? cam.heading : rad(headingDeg);
    const p = pitchDeg == null ? cam.pitch : rad(pitchDeg);
    cam.flyToBoundingSphere(new Cesium.BoundingSphere(target, 1), { duration: 0.6, offset: new Cesium.HeadingPitchRange(h, p, range) });
  }
  const step = (d) => orbit(deg(cam.heading) + d, null);

  // Double-click: fly closer to the point under the cursor, keep heading, look down at least 30 degrees.
  viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  viewer.screenSpaceEventHandler.setInputAction((m) => {
    if (street.on) return;
    const target = groundPick(m.position);
    if (!target) return;
    const range = Math.max(Cesium.Cartesian3.distance(cam.positionWC, target) * 0.4, 120);
    cam.flyToBoundingSphere(new Cesium.BoundingSphere(target, 1), {
      duration: 1.1, offset: new Cesium.HeadingPitchRange(cam.heading, Math.min(cam.pitch, rad(-30)), range) });
  }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

  // Keyboard (skipped while typing, in street view, or with a modifier).
  window.addEventListener("keydown", (e) => {
    const t = e.target && e.target.tagName ? e.target.tagName.toUpperCase() : "";
    if (t === "INPUT" || t === "TEXTAREA" || t === "SELECT" || e.ctrlKey || e.altKey || e.metaKey || street.on) return;
    const height = Math.max(cam.positionCartographic ? cam.positionCartographic.height : 1000, 50);
    const k = e.key;
    const done = () => { e.preventDefault(); viewer.scene.requestRender(); };
    if (k === "ArrowUp") { cam.moveForward(height * 0.08); done(); }
    else if (k === "ArrowDown") { cam.moveBackward(height * 0.08); done(); }
    else if (k === "ArrowLeft") { cam.moveLeft(height * 0.08); done(); }
    else if (k === "ArrowRight") { cam.moveRight(height * 0.08); done(); }
    else if (k === "+" || k === "=") { cam.zoomIn(height * 0.25); done(); }
    else if (k === "-" || k === "_") { cam.zoomOut(height * 0.25); done(); }
    else if (k === "q" || k === "Q") { step(-10); e.preventDefault(); }
    else if (k === "e" || k === "E") { step(10); e.preventDefault(); }
    else if (k === "n" || k === "N") { orbit(0, null); e.preventDefault(); }
    else if (k === "t" || k === "T") { orbit(null, -90); e.preventDefault(); }
    else if (k === "?") { toggleHelp(); e.preventDefault(); }
  });

  // Compass: needle follows the heading; click = north up, double-click = top-down.
  const compass = document.getElementById("hudCompass");
  if (compass) {
    const dial = compass.querySelector(".dial");
    viewer.scene.postRender.addEventListener(() => { dial.style.transform = `rotate(${-deg(cam.heading).toFixed(1)}deg)`; });
    compass.addEventListener("click", () => orbit(0, null));
    compass.addEventListener("dblclick", () => orbit(0, -90));
  }

  function toggleHelp() {
    const h = document.getElementById("navHelp"), b = document.getElementById("btnNav");
    if (!h) return;
    const on = h.classList.toggle("show");
    if (b) b.classList.toggle("on", on);
  }
  const bn = document.getElementById("btnNav");
  if (bn) bn.addEventListener("click", toggleHelp);
})();
