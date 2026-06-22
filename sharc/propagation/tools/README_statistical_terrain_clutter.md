# Statistical terrain & clutter models for ITU-R P.1812 (SHARC)

Reproducible description of the statistical terrain and distance-dependent
clutter models used by `PropagationP1812` (`terrain_profile: statistical`,
`clutter_mode: terrain`, `clutter_statistical: true`). Parameters were estimated
for **Campinas-SP** from real elevation (SRTM) and land cover (ESA WorldCover).

In a Monte-Carlo simulation the BS/UE positions are generic, so a path-specific
terrain is not meaningful. Instead a **synthetic terrain profile** is generated
per snapshot, and the **clutter height** is drawn from a distance-dependent
distribution. Real data is used only **offline** (estimation); the simulation
runtime uses the fitted parameters (no SRTM/WorldCover dependency).

## 1. Statistical terrain model (5D/1059 approach)

Per snapshot, a profile is synthesized from two fitted distributions:

- peak/valley **height deviation** relative to the local mean line — Student's t
  (location 0): `sigma`, `nu`;
- **distance between consecutive extrema** — lognormal: `dist_mu`, `dist_sigma`.

The piecewise-linear profile is smoothed over ~`smoothing_km` (≈ the terrain
correlation length) to emulate the roundness of real hills (calibrated so the
P.1812 loss matches the real Campinas profiles within ±4 dB of the median).

**Campinas-SP fit (20 radials × 50 km):**

| Quantity | Distribution | Parameters |
|---|---|---|
| Height deviation | Student-t (mu=0) | sigma = 36.27 m, nu = 2.93 |
| Distance between extrema | Lognormal | mu = -0.652, sigma = 0.720 (mean 0.68 km) |
| Smoothing length | — | 1.6 km |

Implementation: `sharc/propagation/terrain_statistical.py::StatisticalTerrainModel`.

## 2. Distance-dependent clutter model

The representative clutter height `R` (m) at a terminal a distance `d` (km) from
the IMT cluster centre is a **deterministic trend × multiplicative lognormal**:

```
f(d)     = C + (A - C) * exp(-d / d0)          # exponential-with-floor trend
mu_ln(d) = ln f(d) - sigma^2/2                  # target = "mean"
R(d)     = exp( Normal( mu_ln(d), sigma ) )     # metres

=>  mean[R(d)]   = f(d)
    median[R(d)] = f(d) * exp(-sigma^2/2)
```

With `target = "median"`, `mu_ln(d) = ln f(d)` (median becomes `f(d)`).

**Campinas-SP fit (trend fitted to the MEAN, R^2 = 0.98):**

| Parameter | Symbol | Value |
|---|---|---|
| Central mean height | A | 22.68 m |
| Rural floor mean height | C | 7.90 m |
| Decay scale | d0 | 5.97 km |
| Lognormal log-std | sigma | 1.238 |
| Trend target | target | mean |

Model values: mean 21.96 / 16.84 / 8.00 m and median 10.20 / 7.83 / 3.72 m at
300 m / 3 km / 30 km respectively.

Implementation: `sharc/propagation/terrain_statistical.py::StatisticalClutterModel`.
In P.1812 each terminal draws its clutter height at its own distance from the
cluster centre, applied via the representative-clutter height-gain correction
(Section 4.7).

> **Limitation:** in the urban core the real distribution is left-skewed
> (median > mean), which a unimodal lognormal cannot reproduce. The model
> matches the **mean**; full-shape fidelity would need a per-class mixture model.

## 3. How clutter was estimated from real land use

- **Source:** ESA WorldCover v200 (2021), 10 m, tile `S24W048` (public COG, no auth).
- **Geometry:** 20 radials of 50 km from `(-22.9048878490284, -47.06032221390534)`,
  azimuths 0..342 deg (18 deg step), sampled every 100 m.
- **Class -> height:** each point's WorldCover class is mapped to a representative
  clutter height (`land_use_clutter.WORLDCOVER_CLUTTER_HEIGHTS`):

| Code | Class | Height (m) |
|---|---|---|
| 10 | Tree cover | 15 |
| 20 | Shrubland | 3 |
| 30 | Grassland | 1 |
| 40 | Cropland | 2 |
| 50 | Built-up | 20 |
| 60 | Bare/sparse | 0.5 |
| 70 | Snow/ice | 0 |
| 80 | Water | 0 |
| 90 | Wetland | 2 |
| 95 | Mangroves | 8 |
| 100 | Moss/lichen | 0.5 |

- **Fit:** per 5-km-bin arithmetic mean -> non-linear least squares of
  `f(d) = C + (A - C) exp(-d/d0)`; `sigma` = std of `ln(h) - ln(f(d))`.

The land cover correctly shows Built-up (78 %) at the centre decaying to
tree/grass/cropland in the rural ring, giving the urban -> rural clutter decay.

## 4. Reproduction

Requires `rasterio` (offline estimation only): `pip install "numpy<2" "rasterio<1.4"`.

```bash
# Terrain parameters (downloads SRTM tiles for Campinas on first run)
python -m sharc.propagation.tools.estimate_terrain_params_campinas

# Clutter parameters from real land use (downloads the WorldCover tile, ~80 MB)
python -m sharc.propagation.tools.estimate_clutter_landuse_campinas

# Clutter PDFs at 300 m / 3 km / 30 km
python -m sharc.propagation.tools.plot_clutter_pdfs

# Validate statistical terrain vs real Campinas profiles
python -m sharc.propagation.tools.validate_statistical_terrain
```

Outputs go to `$CLAUDE_SCRATCH` if set, otherwise `tools/_campinas_out/`.

## 5. Usage in a campaign

```yaml
single_earth_station:
  channel_model: P1812
  param_p1812:
    terrain_profile: statistical
    clutter_mode: terrain
    clutter_statistical: true
    # defaults below are the Campinas fit; override as needed
    stat_clutter_trend_A: 22.68
    stat_clutter_trend_C: 7.90
    stat_clutter_trend_d0_km: 5.97
    stat_clutter_sigma: 1.238
    stat_clutter_target: mean
```
