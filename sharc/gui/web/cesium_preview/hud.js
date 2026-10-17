/**
 * SHARC Scene HUD & Controls for CesiumJS preview.
 * Plain classic browser JS (no modules, no imports, no network calls).
 */
(function () {
  "use strict";

  function getViewer() {
    if (typeof viewer !== "undefined" && viewer) return viewer;
    if (typeof window !== "undefined" && window.viewer) return window.viewer;
    return null;
  }

  function getCesium() {
    if (typeof Cesium !== "undefined" && Cesium) return Cesium;
    if (typeof window !== "undefined" && window.Cesium) return window.Cesium;
    return null;
  }

  // ── 1. Global API for scene metadata and legend ──
  window.SharcHud = {
    setScene: function (info) {
      try {
        var hudTitle = document.getElementById("hudTitle");
        var hudStats = document.getElementById("hudStats");
        if (hudTitle) {
          hudTitle.textContent = (info && info.title != null) ? String(info.title) : "—";
        }
        if (hudStats) {
          hudStats.textContent = "";
          if (info && Array.isArray(info.stats)) {
            for (var i = 0; i < info.stats.length; i++) {
              var pair = info.stats[i];
              if (!pair) continue;
              var span = document.createElement("span");
              span.textContent = pair[0] != null ? String(pair[0]) : "";
              var b = document.createElement("b");
              b.textContent = pair[1] != null ? String(pair[1]) : "";
              hudStats.appendChild(span);
              hudStats.appendChild(b);
            }
          }
        }
      } catch (err) {
        console.warn("[hud.js] setScene error:", err);
      }
    },

    setLegend: function (items) {
      try {
        var hudLegend = document.getElementById("hudLegend");
        if (!hudLegend) return;
        hudLegend.textContent = "";
        if (Array.isArray(items) && items.length > 0) {
          for (var i = 0; i < items.length; i++) {
            var item = items[i];
            if (!item) continue;
            var row = document.createElement("div");
            row.className = "row";
            var sw = document.createElement("span");
            sw.className = "sw";
            if (item.color) {
              sw.style.backgroundColor = item.color;
            }
            row.appendChild(sw);
            row.appendChild(document.createTextNode(item.label != null ? String(item.label) : ""));
            hudLegend.appendChild(row);
          }
          hudLegend.classList.add("show");
        } else {
          hudLegend.classList.remove("show");
        }
      } catch (err) {
        console.warn("[hud.js] setLegend error:", err);
      }
    }
  };

  function initHud() {
    try {
      var v = getViewer();
      var C = getCesium();

      var barCursor = document.getElementById("barCursor");
      var barAlt = document.getElementById("barAlt");
      var barScale = document.getElementById("barScale");
      var barBase = document.getElementById("barBase");

      var btnHome = document.getElementById("btnHome");
      var btnMode = document.getElementById("btnMode");
      var btnBase = document.getElementById("btnBase");
      var btnGrid = document.getElementById("btnGrid");
      var btnLight = document.getElementById("btnLight");
      var btnShot = document.getElementById("btnShot");

      var canvas = (v && v.scene) ? v.scene.canvas : null;

      // ── 2. Mouse position on ellipsoid ──
      var mousePos = null;
      var mousePending = false;
      var scratchC2 = (C && C.Cartesian2) ? new C.Cartesian2() : null;

      function updateCursor() {
        mousePending = false;
        try {
          if (!barCursor) return;
          var curViewer = getViewer();
          var curCesium = getCesium();
          if (!mousePos || !curViewer || !curViewer.scene || !curViewer.scene.globe || !curViewer.camera || !curCesium) {
            barCursor.textContent = "lat -  lon -";
            return;
          }
          var c = curViewer.scene.canvas;
          if (!c) {
            barCursor.textContent = "lat -  lon -";
            return;
          }
          var rect = c.getBoundingClientRect();
          if (!scratchC2) scratchC2 = new curCesium.Cartesian2();
          scratchC2.x = mousePos.x - rect.left;
          scratchC2.y = mousePos.y - rect.top;

          var cartesian = curViewer.camera.pickEllipsoid(scratchC2, curViewer.scene.globe.ellipsoid);
          if (cartesian) {
            var carto = curCesium.Cartographic.fromCartesian(cartesian);
            if (carto) {
              var lat = curCesium.Math.toDegrees(carto.latitude);
              var lon = curCesium.Math.toDegrees(carto.longitude);
              barCursor.textContent = "lat " + lat.toFixed(4) + "°  lon " + lon.toFixed(4) + "°";
              return;
            }
          }
          barCursor.textContent = "lat -  lon -";
        } catch (e) {
          if (barCursor) barCursor.textContent = "lat -  lon -";
        }
      }

      if (canvas) {
        canvas.addEventListener("mousemove", function (e) {
          mousePos = { x: e.clientX, y: e.clientY };
          if (!mousePending) {
            mousePending = true;
            requestAnimationFrame(updateCursor);
          }
        });

        canvas.addEventListener("mouseleave", function () {
          mousePos = null;
          if (barCursor) barCursor.textContent = "lat -  lon -";
        });
      }

      // ── 3. Altitude and Scale updates ──
      function updateCameraInfo() {
        try {
          var curViewer = getViewer();
          var curCesium = getCesium();
          if (!curViewer || !curViewer.camera) return;

          var carto = curViewer.camera.positionCartographic;
          var height = carto ? carto.height : 0;

          // Altitude: below 10 km -> m; below 10000 km -> 1 decimal km; else -> km
          if (barAlt) {
            if (height < 10000) {
              barAlt.textContent = "alt " + Math.round(height) + " m";
            } else if (height < 10000000) {
              barAlt.textContent = "alt " + (height / 1000).toFixed(1) + " km";
            } else {
              barAlt.textContent = "alt " + Math.round(height / 1000) + " km";
            }
          }

          // Scale: approximate ground resolution at screen centre
          if (barScale) {
            var c = curViewer.scene ? curViewer.scene.canvas : null;
            var frustum = curViewer.camera.frustum;
            var isPerspective = curCesium && curCesium.PerspectiveFrustum && (frustum instanceof curCesium.PerspectiveFrustum);
            if (!isPerspective && frustum && typeof frustum.fovy === "number") {
              isPerspective = true;
            }

            if (isPerspective && c && c.clientHeight > 0) {
              var fov = frustum.fovy;
              var mpp = (2 * Math.max(0, height) * Math.tan(fov / 2)) / c.clientHeight;
              if (mpp < 1000) {
                barScale.textContent = "1 px = " + mpp.toFixed(1) + " m";
              } else {
                barScale.textContent = "1 px = " + (mpp / 1000).toFixed(1) + " km";
              }
            }
          }
        } catch (e) {
          // defensive: never throw
        }
      }

      if (v && v.camera) {
        v.camera.percentageChanged = 0.01;
        if (v.camera.changed) {
          v.camera.changed.addEventListener(updateCameraInfo);
        }
        if (v.camera.moveEnd) {
          v.camera.moveEnd.addEventListener(updateCameraInfo);
        }
      }

      // ── 4. Basemap UI helper ──
      function updateBaseLabel(baseDef) {
        if (!barBase) return;
        if (!baseDef) {
          barBase.textContent = "base: —";
          return;
        }
        barBase.textContent = "base: " + baseDef.name + " (" + (baseDef.offline ? "offline" : "online") + ")";
      }

      function getCurrentBase() {
        if (!window.SharcBasemaps || !Array.isArray(window.SharcBasemaps.list) || window.SharcBasemaps.list.length === 0) {
          return null;
        }
        var list = window.SharcBasemaps.list;
        var curId = (typeof window.SharcBasemaps.current === "function") ? window.SharcBasemaps.current() : null;
        for (var i = 0; i < list.length; i++) {
          if (list[i].id === curId) return list[i];
        }
        return list[0];
      }

      function syncBasemap() {
        try {
          if (!window.SharcBasemaps || !Array.isArray(window.SharcBasemaps.list) || window.SharcBasemaps.list.length === 0) {
            if (btnBase) btnBase.disabled = true;
            updateBaseLabel(null);
            return;
          }
          if (btnBase) btnBase.disabled = false;
          updateBaseLabel(getCurrentBase());
        } catch (e) {
          if (btnBase) btnBase.disabled = true;
        }
      }

      // ── 4. Buttons ──
      if (btnHome) {
        btnHome.addEventListener("click", function () {
          try {
            var curViewer = getViewer();
            if (!curViewer) return;
            if (curViewer.entities && curViewer.entities.values && curViewer.entities.values.length > 0) {
              curViewer.zoomTo(curViewer.entities);
            } else if (curViewer.camera && typeof curViewer.camera.flyHome === "function") {
              curViewer.camera.flyHome(1.0);
            }
            if (curViewer.scene) curViewer.scene.requestRender();
          } catch (e) {
            console.warn("[hud.js] btnHome error:", e);
          }
        });
      }

      function updateModeText() {
        try {
          if (!btnMode) return;
          var curViewer = getViewer();
          var curCesium = getCesium();
          var is2D = (curViewer && curViewer.scene && curCesium && curViewer.scene.mode === curCesium.SceneMode.SCENE2D);
          btnMode.textContent = is2D ? "2D" : "3D";
        } catch (e) {}
      }

      if (btnMode) {
        btnMode.addEventListener("click", function () {
          try {
            var curViewer = getViewer();
            var curCesium = getCesium();
            if (!curViewer || !curViewer.scene || !curCesium) return;
            var is2D = (curViewer.scene.mode === curCesium.SceneMode.SCENE2D);
            if (is2D) {
              curViewer.scene.morphTo3D(0.6);
              btnMode.textContent = "3D";
            } else {
              curViewer.scene.morphTo2D(0.6);
              btnMode.textContent = "2D";
            }
            curViewer.scene.requestRender();
          } catch (e) {
            console.warn("[hud.js] btnMode error:", e);
          }
        });

        if (v && v.scene && v.scene.morphComplete) {
          v.scene.morphComplete.addEventListener(updateModeText);
        }
      }

      if (btnBase) {
        btnBase.addEventListener("click", function () {
          try {
            if (!window.SharcBasemaps || !Array.isArray(window.SharcBasemaps.list) || window.SharcBasemaps.list.length === 0) {
              btnBase.disabled = true;
              return;
            }
            var list = window.SharcBasemaps.list;
            var curId = (typeof window.SharcBasemaps.current === "function") ? window.SharcBasemaps.current() : null;
            var curIdx = 0;
            for (var i = 0; i < list.length; i++) {
              if (list[i].id === curId) { curIdx = i; break; }
            }
            var next = list[(curIdx + 1) % list.length];
            if (typeof window.SharcBasemaps.set === "function") {
              window.SharcBasemaps.set(next.id);
            }
            updateBaseLabel(next);
            var curViewer = getViewer();
            if (curViewer && curViewer.scene) curViewer.scene.requestRender();
          } catch (e) {
            console.warn("[hud.js] btnBase error:", e);
          }
        });
      }

      function getDataSource(name) {
        var curViewer = getViewer();
        if (!curViewer || !curViewer.dataSources) return null;
        var list = curViewer.dataSources.getByName(name);
        return (list && list.length > 0) ? list[0] : null;
      }

      if (btnGrid) {
        btnGrid.addEventListener("click", function () {
          try {
            var grat = getDataSource("graticule");
            var cities = getDataSource("cities");
            var isCurrentlyOn = btnGrid.classList.contains("on");
            var nextShow = !isCurrentlyOn;
            if (grat) grat.show = nextShow;
            if (cities) cities.show = nextShow;
            btnGrid.classList.toggle("on", nextShow);
            var curViewer = getViewer();
            if (curViewer && curViewer.scene) curViewer.scene.requestRender();
          } catch (e) {
            console.warn("[hud.js] btnGrid error:", e);
          }
        });
      }

      if (btnLight) {
        btnLight.addEventListener("click", function () {
          try {
            var curViewer = getViewer();
            if (curViewer && curViewer.scene && curViewer.scene.globe) {
              curViewer.scene.globe.enableLighting = !curViewer.scene.globe.enableLighting;
              btnLight.classList.toggle("on", curViewer.scene.globe.enableLighting);
              curViewer.scene.requestRender();
            }
          } catch (e) {
            console.warn("[hud.js] btnLight error:", e);
          }
        });
      }

      if (btnShot) {
        btnShot.addEventListener("click", function () {
          try {
            var curViewer = getViewer();
            if (!curViewer || !curViewer.scene) return;
            if (typeof curViewer.render === "function") {
              curViewer.render();
            }
            var c = curViewer.scene.canvas;
            if (c && typeof c.toBlob === "function") {
              c.toBlob(function (blob) {
                try {
                  if (!blob) return;
                  var url = URL.createObjectURL(blob);
                  var a = document.createElement("a");
                  a.href = url;
                  var d = new Date();
                  var pad = function (n) { return (n < 10 ? "0" : "") + n; };
                  a.download = "sharc_scene_" + d.getFullYear() +
                    pad(d.getMonth() + 1) +
                    pad(d.getDate()) + "_" +
                    pad(d.getHours()) +
                    pad(d.getMinutes()) +
                    pad(d.getSeconds()) + ".png";
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  setTimeout(function () {
                    URL.revokeObjectURL(url);
                  }, 1000);
                } catch (err) {
                  console.warn("[hud.js] toBlob error:", err);
                }
              }, "image/png");
            }
          } catch (e) {
            console.warn("[hud.js] btnShot error:", e);
          }
        });
      }

      // ── 5. Keyboard shortcuts ──
      window.addEventListener("keydown", function (e) {
        try {
          var target = e.target;
          if (target) {
            var tag = target.tagName ? target.tagName.toUpperCase() : "";
            if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || target.isContentEditable) {
              return;
            }
          }
          if (e.ctrlKey || e.altKey || e.metaKey) {
            return;
          }
          var key = e.key ? e.key.toUpperCase() : "";
          if (key === "H") {
            if (btnHome) { e.preventDefault(); btnHome.click(); }
          } else if (key === "G") {
            if (btnGrid) { e.preventDefault(); btnGrid.click(); }
          } else if (key === "L") {
            if (btnLight) { e.preventDefault(); btnLight.click(); }
          } else if (key === "M") {
            if (btnMode) { e.preventDefault(); btnMode.click(); }
          } else if (key === "B") {
            if (btnBase) { e.preventDefault(); btnBase.click(); }
          }
        } catch (err) {
          console.warn("[hud.js] keydown error:", err);
        }
      });

      // ── 6. Initial updates ──
      if (barCursor) {
        barCursor.textContent = "lat -  lon -";
      }

      updateModeText();
      updateCameraInfo();
      syncBasemap();

      setTimeout(function () {
        try {
          syncBasemap();
        } catch (e) {}
      }, 600);

      var gratInit = getDataSource("graticule");
      var citiesInit = getDataSource("cities");
      var isGridInit = (gratInit && gratInit.show) || (citiesInit && citiesInit.show);
      if (btnGrid) {
        btnGrid.classList.toggle("on", Boolean(isGridInit));
      }

      if (btnLight && v && v.scene && v.scene.globe) {
        btnLight.classList.toggle("on", Boolean(v.scene.globe.enableLighting));
      }

      if (v && v.scene) {
        v.scene.requestRender();
      }
    } catch (err) {
      console.warn("[hud.js] Init error:", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initHud);
  } else {
    initHud();
  }
})();
