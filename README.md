# CYBER-KATAM

**Closed-Loop Dynamic Transition-Window Governance & Fiscal-Actuarial Clearing Engine**

NASA Space Apps Challenge 2026 · Team **Satset Team wkwkwk** · [Team page](https://www.spaceappschallenge.org/2026/find-a-team/1618-12112026-rifaldi-rpl-61-satset-team-wkwkwk/?tab=project)

Case study: monsoon paddy–palawija (rice–upland crop) landscapes of **Banyumas Regency and the Pantura corridor, Java, Indonesia**.

> **Scope of this repository.** This is the upstream *data & indicator layer* of CYBER-KATAM: NASA/ESA satellite ingestion via Google Earth Engine (GEE), daily per-field tables on an Uber H3 hexagonal mesh, explicit uncertainty / observation-age flags, and the per-cell GeoJSON payloads consumed by the team's decision engine and dashboard. The React/Next.js presentation layer (dual-persona web app, WhatsApp cards, B2G fiscal dashboard) is developed in a separate teammate repository.

---

## 1. Problem & doctrine

Open-loop, black-box agronomic AI fails in monsoon tropics in four specific ways:

1. **Optical lag.** NDVI/EVI stay green for 10–14 days after root-zone water stress begins; canopy heating (LST +1.5…+3.0 °C) and evaporative stress precede visible chlorosis.
2. **Bare-field degradation window.** Post-harvest fallow is not passive: desiccation cracking in vertisols + extreme monsoon rain kinetic energy drives sheet erosion and nitrate leaching.
3. **Non-territorial recommendations.** Brown planthopper (*Nilaparvata lugens*, BPH) migrates kilometres; single-field rotation breaks nothing without synchronized non-host planting across an irrigation block.
4. **Non-auditable fertilizer substitution.** Claiming legume N fixation equals subsidy savings without separating fixed / retained / displaced nitrogen fractions is not auditable public finance.

CYBER-KATAM answers with a **closed-loop governed transition** doctrine:

- **Dynamic transition-window governance** — a gate controller that validates whether soil–atmosphere biophysics *permits* a safe commodity transition, instead of forecasting absolute planting dates months ahead.
- **Boundary error confinement** — every satellite estimate is bounded by sensor error, spatial-support discrepancy, and observation age.
- **Strict machine abstention** — when uncertainty exceeds agronomic tolerance, the system refuses to recommend (`ABSTAIN_FIELD_AUDIT_REQUIRED`) and issues a field-verification ticket for the extension officer (PPL).

## 2. Scientific core (design summary)

| Module | Idea | Key parameters |
|---|---|---|
| **PVRS** (Pre-Visual Root-Stress Score) | Sigmoid-bounded composite of physiological stress (ESI, LST, root-zone SM anomalies) minus visual NDVI symptom; detects stress days 1–14 while leaves are still green | weights 0.35 / 0.35 / 0.30, γ = 0.50; dekad climatologies per H3 cell |
| **BF-EHSI** (Bare-Field Hazard Index) | Cumulative risk integral over the fallow window: bare-soil fraction × thermal degradation + slope-connected kinetic rain erosion | MBSI from HLS 30 m; GPM p95 rain (>50 mm/h); LST_crit = 42 °C; α = 0.40, β = 0.60 |
| **BPH cycle break** | ≥60 days of non-host crop (≈2 full pest cycles) synchronized across the irrigation block | H3 resolution-7 macro clusters (design target ≈11,000 ha blocks) |
| **Three-tier nitrogen accounting** | Tier 1 gross biological fixation → Tier 2 soil-matrix retained N (denitrification/leaching losses) → Tier 3 real urea displacement | ΔN_chem ≈ 163 kg urea/ha; audit-safe fiscal clearing |
| **Pareto rotation engine** | ε-constraint multi-objective optimization: N displaced, SOC change, BPH burden; 3 non-dominated scenarios under subsistence, water-balance, legume porosity and erosion constraints | scenarios: existing / water-conservation + pest-break / N-fixing + high-margin |
| **Governed abstention** | Lipschitz bound on decision deviation vs. δ_sensor + δ_support + δ_model + δ_age; 4 sequential verification gates (sensor validity → hydrological ground truth → agronomic feasibility → human authorization) | `ACTIVE_RECOMMENDATION` vs `ABSTAIN_FIELD_AUDIT_REQUIRED` |

Fiscal clearing example (design doc): 11,000 ha × 163 kg/ha × Rp 9,250/kg ≈ **Rp 16.58 billion per rotation season** per block, before extension/transition/verification costs.

## 3. Architecture & where this repo sits

1. **Tier 1 — Ingestion:** NASA Earthdata + GEE connectors (SMAP L4, ECOSTRESS L2/L3, HLS v2, GPM IMERG, NASA POWER, SRTM), indexed on H3 res-9 (≈0.105 km² micro-fields) and aggregated to res-7 for pest/fiscal macro dynamics. **← this repository**
2. **Tier 2 — Inversion & Pareto engine:** native-support spatial inversion (PSF forward operator, total-variation regularization), PVRS / BF-EHSI, ε-constraint solver. *Indicator payloads produced here; full solver in the decision-engine repo.*
3. **Tier 3 — 4-gate verification gatekeeper.** *Gate-1 sensor/age flags produced here.*
4. **Tier 4 — Presentation & actuarial clearinghouse:** dual-persona web app, <150 KB WhatsApp cards, B2G fiscal dashboard. *Separate repository.*

## 4. Study area & spatial grids

All grids are Uber H3 resolution 9. Boundaries: HDX/BPS 2020 village polygons (332 desa, dissolved to 27 kecamatan) and FAO GAUL 2025 regency polygons.

| Grid | Cells | Definition | Role |
|---|---:|---|---|
| `banyumas_h3_precomputed.geojson` | 1,000 | pilot grid, west-central Banyumas | first daily extraction (`out_daily/`) |
| `banyumas_h3_paddy90.geojson` | 4,143 | ESA WorldCover v200 cropland fraction ≥ 0.9 | "Banyumas raya" paddy footprint (`out_daily_paddy/`) |
| `banyumas_h3_paddy_kab.geojson` | **2,088** | cropland fraction ≥ 0.5 **and** centroid inside the real regency polygon; covers 27/27 kecamatan | **final backend grid** (`out_daily_kab/`) |

The paddy90 grid captures the contiguous paddy corridor around Banyumas, extending into neighbouring regencies (Cilacap, Purbalingga, Kebumen, Banjarnegara, Brebes, Pangandaran); it serves as the wider comparison footprint. The regency-clipped grid is the administrative integration grid. Per-kecamatan attribution and maps: `analyze_paddy90_distribution.py`, `out_daily_paddy/paddy90_sebaran_kecamatan.png`.

## 5. Satellite & climate sources

| Variable | Product / GEE ID | Native support | Role |
|---|---|---|---|
| Root-zone & surface soil moisture | `NASA/SMAP/SPL4SMGP/008` | 9 km, 3-hourly → daily mean | cloud-free water state (L-band) |
| Rainfall | `NASA/GPM_L3/IMERG_V07` | 0.1°, half-hourly → daily mm + max mm/h | monsoon kinetic erosion, p95 thresholds |
| Land surface temperature | `MODIS/061/MOD11A1` + `MYD11A1`, LST_Day_1km, QC ≤ 1 | 1 km, daily clear-sky mean | thermal stress, LST anomaly |
| NDVI / MBSI | `NASA/HLS/HLSL30/v002` + `HLSS30/v002`, Fmask | 30 m, per-scene | greenness, bare-soil fraction, optical lag |
| Elevation / slope | `USGS/SRTMGL1_003` | 30 m, static | erosion connectivity |
| Agro-climatology | NASA POWER daily point | ~50 km, **one regional point** | T2m, RH, wind, solar, rain cross-check |
| Cropland fraction | ESA WorldCover v200 (class 40) | 10 m | paddy grid definition & field-shaped ROI |
| LST (optional) | ECOSTRESS `ECO_L2T_LSTE.002` via AppEEARS | 70 m, sparse ISS overpasses | pre-visual stress enrichment (not merged by default) |

## 6. Daily model tables

Period **2021-01-01 → 2026-11-14** (2,144 days), UTC dates, one row per cell per day — joinable to a weather-forecast API on `date`.

| Output | Cells | Rows | Train / val cells (spatial 70/30, seed 42) |
|---|---:|---:|---|
| `out_daily/` | 1,000 | 2,144,000 | 700 / 300 |
| `out_daily_paddy/` | 4,143 | 8,882,592 | 2,900 / 1,243 |
| `out_daily_kab/` (final) | 2,088 | 4,476,672 | 1,462 / 626 |

Schema groups: raw sensor columns (`sm_rootzone`, `sm_surface`, `lst_modis_c`, `rain_mm`, `max_mmhr`, `ndvi`, `mbsi`, `n_obs`), static terrain (`elev_m`, `slope_deg`), POWER climate, slow-variable forward fills (`*_ffill`, limit 15 d), gap-filled series (`ndvi_gapfill`, `lst_gapfill`) with boolean estimation flags (`ndvi_interp`, `lst_interp`), per-sensor `quality_*` flags, and region labels (`kabupaten`, `kecamatan`, `zona`, `cropland_frac`).

Gap policy (final grid, fraction of cell-days): raw LST missing 75.5% → `lst_gapfill` missing 25.0%; raw NDVI missing 89.3% → `ndvi_gapfill` missing 0.5%; soil moisture 0.2%; rain 0%. Gap-fill = linear interpolation between observations (LST ≤ 3 d, NDVI ≤ 30 d) + bounded edge fill; **every estimated value is flagged**. Product-level gaps such as the SMAP outage (2022-08-06 → 2022-09-20) are preserved and flagged rather than silently smoothed.

## 7. Data contract & per-cell indicator payload

`grid_cell_contract.json` (v1.3, extending the v1.0 spec of the design doc) defines the exchange payload per H3 cell: `h3_index`, `physical_indicators`, `operational_flags` (`missing_observation`, `optical_lag_days`, `erosion_alert`, `data_quality_flags`, …), `rotation_scenarios` (3), `xai_decision_block` (4 blocks: why / multi-benefits / information gaps / local risks & gates), `fiscal_metrics`, and `system_state` ∈ {`ACTIVE_RECOMMENDATION`, `ABSTAIN_FIELD_AUDIT_REQUIRED`}.

`make_indicators_v3_geojson.py` emits the integrated payload (`banyumas_h3_indicators_v3.geojson`, 4,143 features) with **last-known-value semantics**: indicators carry the latest observation plus explicit age (`*_asof`, `optical_lag_days`, `lst_lag_days`), never silent nulls. Gate: HLS observation present, ≥1 scene, optical lag ≤ 30 d; missing flag when no HLS ever or no soil-moisture fill. Result at 2026-11-14: **3,254 ACTIVE / 889 ABSTAIN** (paddy90 grid, monsoon season).

## 8. Paddy ROI & GEE assets

| Asset / file | Geometry | Area |
|---|---|---:|
| `projects/booming-voice-509501-c9/assets/banyumas_paddy90_roi` · `banyumas_paddy90_roi.geojson` | union of 4,143 hexes → 552 polygons | 420.7 km² |
| `projects/booming-voice-509501-c9/assets/banyumas_sawah_poligon_roi` · `banyumas_sawah_poligon_roi.geojson` | **field-shaped paddy polygons**: WorldCover cropland vectorized at 10 m inside the footprint, 569 patches ≥ 0.1 ha | 412.8 km² |

The field-shaped ROI follows real field boundaries instead of hexagon edges, delineated from ESA WorldCover cropland at 10 m — the same versioned source that defines the paddy grid; fusion with official protected-paddy cadastre (LSD) is on the roadmap. `gee_roi_code_editor.js` is paste-ready Code Editor JavaScript that displays the ROI and prints a **direct download link (no Google Drive quota needed)** via `getDownloadURL`. `paddy_roi_pipeline.py` runs the whole chain (hex union → local GeoJSON → GEE asset → verify → optional public ACL → optional Drive export); `export_roi_to_drive.py` handles Drive-only exports with switchable project/account.

## 9. Repository layout

```
├── build_daily_model_parquet.py      # Tier-1 daily pipeline (GEE, resumable, per-outdir caches)
├── finalize_daily_kab.py             # region labels + split metadata for the final grid
├── gen_paddy_grid.py / gen_hex_grid.py / extract_paddy_fraction.py
├── analyze_paddy90_distribution.py   # regency attribution of the paddy90 grid
├── make_indicators_v3_geojson.py     # contract v1.3 per-cell payload (last-known + age flags)
├── make_daily_summary_geojson.py     # per-cell daily statistics GeoJSON
├── make_paddy_polygon_roi.py         # field-shaped paddy polygons -> GEE asset + local GeoJSON
├── paddy_roi_pipeline.py             # end-to-end hex-union ROI pipeline
├── export_roi_to_drive.py            # Drive export (project/account switchable)
├── gee_roi_code_editor.js            # paste-in Code Editor: map + no-Drive download link
├── extract_ecostress_earthdata.py    # optional ECOSTRESS via AppEEARS (netrc auth, resumable)
├── extract_*.py                      # per-sensor extractors (SMAP/GPM/HLS/LST/SRTM/POWER)
├── gee_environment_init.py           # GEE auth/ROI helpers, climatology baseline
├── grid_cell_contract.json           # team data contract (v1.3)
├── crop_rotation_matrix.json         # agronomic rotation scenarios
├── banyumas_h3_*.geojson             # grids (pilot / paddy90 / regency-clipped)
├── banyumas_*_roi.geojson            # ROI deliverables (hex union & field polygons)
├── banyumas_h3_indicators_v3.geojson # integrated indicator payload
├── batas_kecamatan_banyumas/         # HDX/BPS 2020 village boundaries (332 desa)
├── batas_kabupaten_gaul.geojson      # FAO GAUL 2025 regency boundaries
├── out_daily/ out_daily_paddy/ out_daily_kab/   # daily parquet tables + sensor caches + meta
├── out_ecostress/                    # optional ECOSTRESS daily parquet (auto-merged if present)
└── legacy/ clean_data_modules/       # archived earlier copies (do not use)
```

## 10. Quickstart

Requirements: Python ≥ 3.10 with `earthengine-api`, `pandas`, `geopandas`, `h3`, `shapely`, `pyproj`, `matplotlib`, `numpy`. A Google Earth Engine account/project; authenticate once (`python -c "import ee; ee.Authenticate()"`). ECOSTRESS additionally needs a NASA Earthdata login stored locally in `~/.netrc` (never committed).

```bash
# 1) daily table for the final regency-clipped grid (resumable; caches per outdir)
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

## 11. Design safeguards & roadmap

CYBER-KATAM treats uncertainty as a first-class product rather than an afterthought:

- **Uncertainty-aware by construction.** Interpolated and forward-filled values carry explicit `*_interp` / `*_ffill` flags, and per-sensor quality columns record observation provenance; the downstream verification gates consume these flags directly.
- **Native-support awareness.** Each extractor respects the instrument's native spatial support (SMAP 9 km, GPM 0.1°, MODIS 1 km, HLS 30 m), and the H3 mesh separates micro-field (res-9) from territorial (res-7) dynamics. *Roadmap:* PSF-based constrained inversion (Tier 2) to resolve within-support variability.
- **Regional climate context, local weather at integration.** NASA POWER supplies a consistent regional agro-climatic baseline; field-level weather enters through the forecast-API join on `date`. *Roadmap:* per-cell climate downscaling.
- **Selective thermal enrichment.** ECOSTRESS contributes high-resolution pre-visual stress evidence where QC passes; the AppEEARS pipeline supports on-demand observation campaigns per grid. *Roadmap:* expanded campaigns for full coverage of the integration grid.
- **Reproducible paddy delineation.** Field boundaries derive from versioned ESA WorldCover cropland at 10 m, consistent with the grid definition, and the regency-clipped grid aligns outputs with administrative boundaries. *Roadmap:* fusion with official protected-paddy cadastre (LSD) once openly available.
- **Governed abstention.** Cells that fail the observation gates are published as `ABSTAIN_FIELD_AUDIT_REQUIRED` together with a field-verification ticket — the system recommends only when it can defend the recommendation.

## 12. Team & links

- Team: [Satset Team wkwkwk — NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/2026/find-a-team/1618-12112026-rifaldi-rpl-61-satset-team-wkwkwk/?tab=project)
- Design specification: *CYBER-KATAM — Closed-Loop Dynamic Transition-Window Governance & Fiscal-Actuarial Clearing Engine* (team idea document, `IDEA_NASAFIELDSHIFTING.pdf`)
- Data portals: [NASA Earthdata](https://urs.earthdata.nasa.gov), [AppEEARS](https://appeears.earthdatacloud.nasa.gov), [GEE Data Catalog](https://developers.google.com/earth-engine/datasets/catalog), [FAO GAUL](https://data.apps.fao.org/catalog/), [HDX Indonesia boundaries](https://data.humdata.org/dataset/indonesia-administrative-level-0-1-2-3-and-4-boundary-polygons)
- Boundary source repo: [JfrAziz/indonesia-district](https://github.com/JfrAziz/indonesia-district) (HDX/BPS 2020 villages)

**Acknowledgements.** NASA (SMAP, GPM IMERG, MODIS, HLS, ECOSTRESS, POWER, SRTM), ESA (WorldCover), FAO (GAUL), BPS/HDX (administrative boundaries), and the Google Earth Engine platform.