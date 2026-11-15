# CYBER-KATAM — Data Processing & Spatial Analysis Layer

**Closed-Loop Dynamic Transition-Window Governance & Fiscal-Actuarial Clearing Engine**

NASA Space Apps Challenge 2026 · Team **Satset Team wkwkwk** · [Team page](https://www.spaceappschallenge.org/2026/find-a-team/1618-12112026-rifaldi-rpl-61-satset-team-wkwkwk/?tab=project) · [Main team repository](https://github.com/NASA-satset-team/cyber-katam)

Pilot area: **Banyumas, Central Java, Indonesia** (monsoon paddy–palawija landscape).

> **Scope of this repository.** CYBER-KATAM is a team-wide, modular decision-support system. This repository implements its **Data Processing & Spatial Analysis layer**: NASA/ESA satellite ingestion via Google Earth Engine, quality control, unit normalization, temporal alignment, H3 spatial indexing, provenance and missing-value preservation, and the standardized daily per-cell inputs and environmental indicator payloads consumed by the modeling modules. The Crop Modeling, Economic/Fiscal/Actuarial Modeling, Meteomatics forecast integration, Integration & Decision Engine, and the web application are developed in the [main team repository](https://github.com/NASA-satset-team/cyber-katam) and are **not** claimed as implemented here.

---

## 1. Project overview

CYBER-KATAM is an integrated, data-driven agricultural decision-support system connecting NASA Earth observation, geospatial analysis, crop modeling, external weather forecasts (Meteomatics Weather API, a NASA Space Apps Challenge partner resource), and economic/fiscal/actuarial assessment. It links environmental monitoring with crop suitability, water-balance calculations, multi-season rotation planning, and short-term advisories, so that agricultural transitions are evaluated against environmental constraints, resource availability, and financial implications.

The system is intended to **support human decision-making, not replace farmers' experience or guarantee agricultural outcomes**.

## 2. System architecture & module status

```
NASA/ESA data + GEE ──► Data Processing & Spatial Analysis ──► Historical & Spatial Modeling ─
ESA WorldCover, H3      (THIS REPOSITORY)                    Crop Modeling (FAO-56, registry)  ├─► Integration &
Meteomatics Weather API ───────────────────────────────────► Economic, Fiscal & Actuarial ────┘   Decision Engine
                                                                                                  (fail-closed)
                                                                                                       │
                                                                                          Web application (React + Leaflet)
```

| Module | Responsibility | Where |
|---|---|---|
| Data Processing & Spatial Analysis | validation, unit normalization, temporal alignment, spatial processing, H3 indexing, provenance & missing-status preservation | **this repository** |
| Historical & Spatial Modeling | soil moisture, vegetation, thermal stress, bare-soil exposure, terrain hazards, PVRS, BF-EHSI | team main repo (inputs & indicator payloads supplied here) |
| Crop Modeling | parameter registry (rice Inpari 32, soybean Anjasmoro, mungbean Vima-1, sorghum), FAO-56 water balance, suitability, calendar, strategic rotation (Pareto), tactical advisory | team main repo |
| Economic, Fiscal & Actuarial | three-tier nitrogen accounting, subsidy scenarios, insurance risk, gross margins | team main repo |
| External Weather Forecast | Meteomatics API → standardized ForecastBundle/ForecastDay | team main repo |
| Integration & Decision Engine | completeness checks, fail-closed advisories, explainability, human verification | team main repo |
| Web application | farmer & policymaker personas, Leaflet maps | team main repo |

## 3. What this repository delivers

The data-processing workflow follows the team specification: acquire → check quality/availability → normalize units and names → align timestamps → process coordinates and boundaries → associate with H3 cells → preserve metadata, provenance, and missing-value status → emit standardized inputs.

Concretely:

- **Daily per-cell tables** (2021-01-01 → 2026-11-14, 2,144 days) on Uber H3 resolution 9, joinable to forecast APIs on `date`.
- **Three spatial grids** (pilot, paddy corridor, regency-clipped integration grid) with administrative labels.
- **Environmental indicator payloads** per cell (`banyumas_h3_indicators_v3.geojson`) conforming to the team data contract: last-known indicators with explicit observation age, quality flags, erosion alerts, and governed `system_state`.
- **Paddy ROI deliverables**: hex-union footprint and field-shaped paddy polygons, published as GEE assets and local GeoJSON.
- **Dekad climatological baselines** and per-sensor caches for reproducible re-extraction.

## 4. Study area & spatial grids

Boundaries: HDX/BPS 2020 village polygons (332 desa, dissolved to 27 kecamatan) and FAO GAUL 2025 regency polygons.

| Grid | Cells | Definition | Role |
|---|---:|---|---|
| `banyumas_h3_precomputed.geojson` | 1,000 | pilot grid, west-central Banyumas | first daily extraction (`out_daily/`) |
| `banyumas_h3_paddy90.geojson` | 4,143 | ESA WorldCover v200 cropland fraction ≥ 0.9 | wider paddy-corridor comparison footprint (`out_daily_paddy/`) |
| `banyumas_h3_paddy_kab.geojson` | **2,088** | cropland fraction ≥ 0.5 and centroid inside the regency polygon; 27/27 kecamatan | **integration grid** (`out_daily_kab/`) |

The paddy90 grid captures the contiguous paddy corridor around Banyumas, extending into neighbouring regencies (Cilacap, Purbalingga, Kebumen, Banjarnegara, Brebes, Pangandaran); the regency-clipped grid aligns outputs with administrative boundaries. Per-kecamatan attribution: `analyze_paddy90_distribution.py`, `out_daily_paddy/paddy90_sebaran_kecamatan.png`.

**H3 does not increase the native resolution of satellite data.** A coarse observation assigned to a finer H3 cell is never presented as a direct field-level measurement; native supports are declared per source (Section 5) and carried in metadata.

## 5. Data sources

| Variable | Product / GEE ID | Native support | Role |
|---|---|---|---|
| Surface & root-zone soil moisture | `NASA/SMAP/SPL4SMGP/008` | 9 km, 3-hourly → daily mean | water-stress context (cloud-free L-band) |
| Land surface temperature | `MODIS/061/MOD11A1` (+ `MYD11A1`), LST_Day_1km, QC ≤ 1 | 1 km, daily clear-sky mean | thermal condition & stress |
| Precipitation | `NASA/GPM_L3/IMERG_V07` | 0.1°, half-hourly → daily mm + max mm/h | water inputs, rainfall hazard, p95 thresholds |
| Reflectance / NDVI / MBSI | `NASA/HLS/HLSL30/v002` + `HLSS30/v002`, Fmask | 30 m, per-scene | vegetation & bare-soil indicators |
| Elevation / slope | `USGS/SRTMGL1_003` | 30 m, static | terrain & erosion connectivity |
| Agro-climatology | NASA POWER daily point | regional (~50 km) point | climate calculations, ETo inputs |
| Cropland fraction | ESA WorldCover v200 (class 40) | 10 m | paddy grid definition & field-shaped ROI |
| LST (optional enrichment) | ECOSTRESS `ECO_L2T_LSTE.002` via AppEEARS | 70 m, sparse ISS overpasses | pre-visual stress evidence where QC passes |

Team-level resources outside this repository: **Meteomatics Weather API** (forecast input), **FAO-56** crop evapotranspiration framework, **Uber H3**, crop parameter registry with evidence status (reference values are distinguished from locally calibrated values), and **Leaflet** for the web application.

## 6. Daily tables, provenance & missing-value status

| Output | Cells | Rows | Train / val cells (spatial 70/30, seed 42) |
|---|---:|---:|---|
| `out_daily/` | 1,000 | 2,144,000 | 700 / 300 |
| `out_daily_paddy/` | 4,143 | 8,882,592 | 2,900 / 1,243 |
| `out_daily_kab/` (integration) | 2,088 | 4,476,672 | 1,462 / 626 |

Schema groups: raw sensor columns (`sm_rootzone`, `sm_surface`, `lst_modis_c`, `rain_mm`, `max_mmhr`, `ndvi`, `mbsi`, `n_obs`), terrain (`elev_m`, `slope_deg`), POWER climate, bounded forward fills (`*_ffill`, limit 15 d), gap-filled series (`ndvi_gapfill`, `lst_gapfill`) with estimation flags (`ndvi_interp`, `lst_interp`), per-sensor `quality_*` flags, and region labels (`kabupaten`, `kecamatan`, `zona`, `cropland_frac`).

Gap policy (integration grid, fraction of cell-days): raw LST missing 75.5% → `lst_gapfill` missing 25.0%; raw NDVI missing 89.3% → `ndvi_gapfill` missing 0.5%; soil moisture 0.2%; rain 0%. Gap-fill = linear interpolation between observations (LST ≤ 3 d, NDVI ≤ 30 d) plus bounded edge fill; every estimated value is flagged. Product-level gaps such as the SMAP outage (2022-08-06 → 2022-09-20) are preserved and flagged rather than silently smoothed. Each output ships a `daily_model_meta.json` documenting units, sources, gap fractions, and grid definition.

## 7. Environmental indicators & team modeling spec

`grid_cell_contract.json` (v1.3) defines the per-cell exchange payload: `h3_index`, `physical_indicators`, `operational_flags` (`missing_observation`, `optical_lag_days`, `erosion_alert`, `data_quality_flags`, …), `rotation_scenarios`, `xai_decision_block` (evidence / expected benefits / information gaps / local risks), `fiscal_metrics`, and `system_state` ∈ {`ACTIVE_RECOMMENDATION`, `ABSTAIN_FIELD_AUDIT_REQUIRED`}.

`make_indicators_v3_geojson.py` emits the integrated payload with **last-known-value semantics**: latest observation plus explicit age (`*_asof`, `optical_lag_days`, `lst_lag_days`), never silent nulls. Gate: HLS observation present, ≥1 scene, optical lag ≤ 30 d; missing flag when no HLS ever or no soil-moisture fill. At 2026-11-14 (paddy90 grid, monsoon season): **3,254 ACTIVE / 889 ABSTAIN**.

These payloads supply the inputs and components of the team's Historical & Spatial Modeling formulations, which remain **project-specific and require baselines, calibration, and validation** before being treated as calibrated predictions:

- **MBSI** = (SWIR1 − SWIR2 − NIR) / (SWIR1 + SWIR2 + NIR); bare-soil fraction `b_it = clip((MBSI + 0.15)/0.45, 0, 1)` — a project implementation assumption to be calibrated against reference observations.
- **PVRS** = 1 / (1 + exp[−(S_physio − γ·S_visual)]) with S_physio from ESI, LST, and root-zone SM anomalies (w = 0.35/0.35/0.30, γ = 0.50) and S_visual from NDVI anomaly; detects pre-visual stress during optical lag. ESI input comes from ECOSTRESS where available.
- **BF-EHSI** = b_it · [α·(LST/LST_crit) + β·tan(θ_SRTM)·(R_GPM,95th/R_norm)] with α = 0.40, β = 0.60, LST_crit = 42 °C, plus the cumulative degradation-risk integral D_i.

This repository computes the environmental components (LST/SM/NDVI anomalies against dekad climatologies, MBSI, slope, rain-p95 exceedance, erosion alerts, observation-age flags); the composite scores and downstream rotation/fiscal logic belong to the team modeling modules.

## 8. Paddy ROI & GEE assets

| Asset / file | Geometry | Area |
|---|---|---:|
| `projects/booming-voice-509501-c9/assets/banyumas_paddy90_roi` · `banyumas_paddy90_roi.geojson` | union of 4,143 hexes → 552 polygons | 420.7 km² |
| `projects/booming-voice-509501-c9/assets/banyumas_sawah_poligon_roi` · `banyumas_sawah_poligon_roi.geojson` | field-shaped paddy polygons: WorldCover cropland vectorized at 10 m inside the footprint, 569 patches ≥ 0.1 ha | 412.8 km² |

The field-shaped ROI follows real field boundaries instead of hexagon edges, delineated from versioned ESA WorldCover cropland — the same source that defines the paddy grid; fusion with official protected-paddy cadastre (LSD) is on the roadmap. `gee_roi_code_editor.js` is paste-ready Code Editor JavaScript displaying the ROI and printing a direct download link via `getDownloadURL` (no Google Drive quota needed). `paddy_roi_pipeline.py` runs the full chain (hex union → local GeoJSON → GEE asset → verify → optional public ACL → optional Drive export); `export_roi_to_drive.py` handles Drive-only exports with switchable project/account.

## 9. Repository layout

```
├── build_daily_model_parquet.py      # daily ingestion pipeline (GEE, resumable, per-outdir caches)
├── finalize_daily_kab.py             # region labels + split metadata for the integration grid
├── gen_paddy_grid.py / gen_hex_grid.py / extract_paddy_fraction.py
├── analyze_paddy90_distribution.py   # per-kecamatan / per-regency attribution
├── make_indicators_v3_geojson.py     # contract v1.3 per-cell payload (last-known + age flags)
├── make_daily_summary_geojson.py     # per-cell daily statistics GeoJSON
├── make_paddy_polygon_roi.py         # field-shaped paddy polygons -> GEE asset + local GeoJSON
├── paddy_roi_pipeline.py             # end-to-end hex-union ROI pipeline
├── export_roi_to_drive.py            # Drive export (project/account switchable)
├── gee_roi_code_editor.js            # paste-in Code Editor: map + no-Drive download link
├── extract_ecostress_earthdata.py    # optional ECOSTRESS via AppEEARS (netrc auth, resumable)
├── extract_*.py                      # per-sensor extractors (SMAP/GPM/HLS/LST/SRTM/POWER)
├── gee_environment_init.py           # GEE auth/ROI helpers, dekad climatology baseline
├── grid_cell_contract.json           # team data contract (v1.3)
├── crop_rotation_matrix.json         # agronomic rotation reference matrix
├── banyumas_h3_*.geojson             # grids (pilot / paddy corridor / integration)
├── banyumas_*_roi.geojson            # ROI deliverables (hex union & field polygons)
├── banyumas_h3_indicators_v3.geojson # integrated environmental indicator payload
├── batas_kecamatan_banyumas/         # HDX/BPS 2020 village boundaries (332 desa)
├── batas_kabupaten_gaul.geojson      # FAO GAUL 2025 regency boundaries
└── out_daily/ out_daily_paddy/ out_daily_kab/   # metadata, per-kecamatan CSVs, figures, summaries
```

In the public repository, `out_*/` ships metadata, per-kecamatan CSVs, figures and the daily-summary GeoJSON only; the full parquet tables and sensor caches stay local and are regenerated with the Quickstart pipeline. Archived earlier copies (`legacy/`, `clean_data_modules/`) are not published.

## 10. Quickstart

Requirements: Python ≥ 3.10 with `earthengine-api`, `pandas`, `geopandas`, `h3`, `shapely`, `pyproj`, `matplotlib`, `numpy`. A Google Earth Engine account/project; authenticate once (`python -c "import ee; ee.Authenticate()"`). ECOSTRESS additionally needs a NASA Earthdata login stored locally in `~/.netrc` (never committed).

```bash
# 1) daily table for the integration grid (resumable; caches per outdir)
python build_daily_model_parquet.py --hex banyumas_h3_paddy_kab.geojson \
       --outdir out_daily_kab --end 2026-11-14

# 2) attach kabupaten/kecamatan/zona labels + split metadata
python finalize_daily_kab.py

# 3) per-cell indicator payload (contract v1.3) and daily-summary GeoJSON
python make_indicators_v3_geojson.py --hex banyumas_h3_paddy90_kecamatan.geojson \
       --outdir out_daily_paddy --out banyumas_h3_indicators_v3.geojson
python make_daily_summary_geojson.py

# 4) field-shaped paddy ROI -> GEE asset + local GeoJSON (no Drive required)
python make_paddy_polygon_roi.py

# 5) full hex-union ROI pipeline (add --public / remove --skip-drive as needed)
python paddy_roi_pipeline.py --skip-drive

# 6) optional ECOSTRESS enrichment (AppEEARS point tasks, 500 points/task, resumable)
python extract_ecostress_earthdata.py --hex banyumas_h3_paddy_kab.geojson
```

Extraction is resumable: parts are keyed by month + slice-end + chunk, sensor caches are per-output-directory, and interrupted runs continue where they stopped. Train/validation splits are spatial (70/30, seed 42) with zero cell overlap.

## 11. Limitations & future development

Consistent with the team specification, several boundaries must be addressed before CYBER-KATAM operates as a fully validated recommendation system:

- Satellite observations have different native resolutions and cannot automatically provide field-level measurements; spatial aggregation and downscaling require documented methods and validation.
- Some crop parameters rely on general scientific references or proxies rather than local field experiments; local calibration is required before strong claims about crop performance in Banyumas.
- Fiscal and actuarial calculations are scenario estimates until verified local prices, production costs, subsidy regulations, insurance rules, and historical claim data are available.
- External weather forecasts are not equivalent to historical satellite observations; the two categories are handled separately and used for their appropriate purposes.
- The Integration & Decision Engine generates recommendations only when required inputs are sufficiently complete and reliable (fail-closed); incomplete inputs yield conditional outputs or abstention with field-verification tickets.

Future development focuses on verified data ingestion, local parameter calibration, field validation, economic/actuarial integration, complete API connectivity, and runtime integration of all modeling modules. Within this layer: PSF-based constrained inversion for within-support variability, per-cell climate downscaling, expanded ECOSTRESS campaigns, and cadastre (LSD) fusion for paddy delineation.

## 12. Team & links

- Team: [Satset Team wkwkwk — NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/2026/find-a-team/1618-12112026-rifaldi-rpl-61-satset-team-wkwkwk/?tab=project)
- Main team repository: [NASA-satset-team/cyber-katam](https://github.com/NASA-satset-team/cyber-katam)
- Data portals: [NASA Earthdata](https://urs.earthdata.nasa.gov), [AppEEARS](https://appeears.earthdatacloud.nasa.gov), [GEE Data Catalog](https://developers.google.com/earth-engine/datasets/catalog), [FAO GAUL](https://data.apps.fao.org/catalog/), [HDX Indonesia boundaries](https://data.humdata.org/dataset/indonesia-administrative-level-0-1-2-3-and-4-boundary-polygons)
- Boundary source repo: [JfrAziz/indonesia-district](https://github.com/JfrAziz/indonesia-district) (HDX/BPS 2020 villages)
- Partner forecast resource: Meteomatics Weather API (NASA Space Apps Challenge partner)

**Acknowledgements.** NASA (SMAP, GPM IMERG, MODIS, HLS, ECOSTRESS, POWER, SRTM), ESA (WorldCover), FAO (GAUL, FAO-56), BPS/HDX (administrative boundaries), Meteomatics, and the Google Earth Engine platform.