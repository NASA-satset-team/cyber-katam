# Project file inventory and data-provenance audit

Audit date: 2026-11-14
Scope: repository root, `external/aryas_workresult/`, `external/ariefs_workresult/`
Method: direct file inspection, SHA-256 comparison, JSON/Parquet parsing, H3
recomputation, and scratch-directory execution. No received source file was edited.

> **Bottom line:** there are **no verified NASA observations** in this repository
> yet. The H3 dataset, climatology baseline, benchmark, and several model inputs
> are synthetic or assumed. Arya's engines are real implementations, but their demo
> inputs are synthetic.

---

## 1. Incoming Arief archive

| Item | Value |
|---|---|
| Archive | `Arief_work-20261114T003733Z-1-001.zip` |
| Size | 132,806 bytes |
| SHA-256 | `165679277C9165225E95B6BF1ED8B70D8474680414D0FA4311801FDD3DB17DA0` |
| Preserved at | `external/ariefs_workresult/_source_archive/` (identical hash) |
| Extract destination | `external/ariefs_workresult/` |
| Extraction integrity | 25 extracted files compared; **0 mismatches** |

### 1.1 Duplicate analysis (compare before deleting)

`clean_data_modules/` is **not** a second implementation. It is a byte-identical
copy of six root scripts, created by `task12_smoke_test_deconstruction.py`.

| File | Root SHA-256 prefix | `clean_data_modules/` prefix | Verdict |
|---|---|---|---|
| `nitrogen_dynamics.py` | `C162CACAE1599312` | `C162CACAE1599312` | identical |
| `task7_agronomy_matrix.py` | `0A10F34C69FF1660` | `0A10F34C69FF1660` | identical |
| `task9_climatology_baseline.py` | `39B98B24077D89C0` | `39B98B24077D89C0` | identical |
| `task10_precomputed_geojson.py` | `BB44555A126A435A` | `BB44555A126A435A` | identical |
| `task11_benchmark.py` | `DB5505AF1DAABC98` | `DB5505AF1DAABC98` | identical |
| `task12_smoke_test_deconstruction.py` | `A4AA04C728553860` | `A4AA04C728553860` | identical |

Both copies are retained. The root copy is treated as canonical. No file was
deleted.

---

## 2. Arief — source scripts

Legend for "Ready": **No** = do not integrate as production; **Partial** = logic
is reusable but needs correction; **Yes** = safe to reuse as delivered.

| File | Purpose | Data source | Actual vs synthetic | Dependencies | Ready | Known issues |
|---|---|---|---|---|---|---|
| `gee_environment_init.py` | Initialize GEE, get Banyumas ROI, build paddy mask, export ROI GeoJSON | GEE; FAO GAUL 2015 vs 2025 inconsistent; ESA WorldCover v200 | Real GEE calls, but exported "ROI" is a hand-written bbox | `earthengine-api` | Partial | Writes a bbox and names it paddy ROI; `get_banyumas_paddy_mask()` is defined but never used for export; hardcoded GEE project ID; credential handling is implicit |
| `harmonize_h3_spatial.py` | Build a multi-band GEE data cube (LST, SMAP, GPM, NDVI, MBSI) | MODIS MOD11A1, SMAP SPL4SMGP/008, GPM IMERG V07, Sentinel-2 SR | Real collection queries; no exported artifact | `earthengine-api` | Partial | Labels output "HLS" but uses Sentinel-2; no QA/cloud masking beyond scene-level cloud %; no H3 resampling despite the name; no export |
| `task7_extract_h3.py` | Sample the cube, convert lat/lon to H3 res 9, download CSV | Same as above via GEE | Real extraction code; **no CSV in archive**, so success unverified | `ee`, `pandas`, `h3` | Partial | Samples at 2,000 m then assigns H3 res 9; `drop_duplicates(h3_index)` discards points arbitrarily; no paddy mask or QA; `GPM_P95` computed over half-hourly rates without unit handling |
| `extract_smap_downscaling.py` | Fetch SMAP L4 root-zone soil moisture | `NASA/SMAP/SPL4SMGP/008` | Real collection query; no exported data | `earthengine-api` | Partial | File name says "downscaling" but no downscaling is implemented; scene count only; no date/QA filtering beyond bounds |
| `extract_ecostress_banyumas.py` | Fetch ECOSTRESS L2T LSTE and convert kelvin to Celsius; MODIS fallback | `NASA/ECOSTRESS/L2T_LSTE/V2`; MODIS MOD11A1 | Real query; no export | `earthengine-api` | Partial | Averages all scenes (destroys irregular overpass timing); no QC/cloud mask; no observation timestamps; fallback silently mixes products |
| `extract_gpm_precipitation.py` | Fetch IMERG and compute P95 | `NASA/GPM_L3/IMERG_V06` first, V07 fallback, CHIRPS fallback | Real query; **incorrect product/band selection** | `earthengine-api` | No | Target is IMERG V07 with band `precipitation` (mm/hr); script uses V06 and `precipitationCal`, and silently falls back to CHIRPS. P95 of half-hourly rates is not P95 daily rainfall. No export |
| `extract_hls_vegetation_bsi.py` | Compute NDVI and MBSI | **`COPERNICUS/S2_SR_HARMONIZED`** | Real query, but **not the NASA HLS product** | `earthengine-api` | No | Uses Sentinel-2 band names B8/B4/B11/B12, not HLS L30 B5/B6/B7 or S30 B8A/B11/B12; no QA/Fmask; no BRDF/illumination normalization; no export |
| `task7_agronomy_matrix.py` | Write three rotation scenarios to JSON | Hand-written constants | Assumed, not measured | stdlib `json` | Partial | Water demand, yields, thresholds, and drought vulnerability have no cited source; scenarios overlap with Arya's names but not his parameter set |
| `nitrogen_dynamics.py` | Soybean residue N fixation and next-season availability | Assumed coefficients | Assumed, not measured | stdlib `json` | Partial | 1.5 residue ratio, 2.5% N, 75–80% fixation, 40% mineralization are unsourced; conflicts with Arya's three-tier ledger (3.8% N, 76% Ndfa, 68% mineralization, harvest/denitrification/leaching terms) |
| `task9_climatology_baseline.py` | Build dekadal μ/σ baseline | **Synthetic sine wave + Gaussian noise** | **Synthetic** | `pandas`, `numpy`, `pyarrow` | No | No real historical query; no seed, so every run differs; fails on Windows cp1252 console because it prints `μ`/`σ`; 36 rows only (12 months × 3 dekads) |
| `task10_precomputed_geojson.py` | Generate 1,000 H3 res-9 cells + "satellite" attributes | **`h3.grid_disk` + `random.uniform`** | **Synthetic** | `h3` | No (as data); Partial (as geometry demo) | Not clipped to paddy mask; hardcoded land cover; random values; no seed; cells are a disc around one point, not the regency; output differs every run |
| `task11_benchmark.py` | "Stress test" pipeline timing | **`time.sleep()`** | **Simulated** | stdlib | No | Not a pipeline benchmark; measured values are artificial delays; always passes the 300 s target |
| `task12_smoke_test_deconstruction.py` | Null check + copy scripts into `clean_data_modules/` | Local files | Real file operations | stdlib | Partial | Only checks for `None`; prints "SELURUH PIPELINE ... SIAP" even when 0 scripts are copied (observed); copies itself last and reports a skip; no schema/units/geometry checks |

---

## 3. Arief — data artifacts

| File | Size (bytes) | SHA-256 prefix | Purpose | Data source | Actual vs synthetic | Ready | Known issues |
|---|---:|---|---|---|---|---|---|
| `banyumas_h3_precomputed.geojson` | 536,965 | `44DCC8CDA26FDA7F` | 1,000-cell H3 GeoJSON for MVP/UI | Generated by `task10` | **Synthetic** | No (data); Partial (UI fixture) | See forensic findings §5.1 |
| `banyumas_paddy_roi.geojson` | 771 | `7D564A96DC91FCB8` | Supposed paddy ROI | Hand-written bbox in `gee_environment_init.py` | Boundary only, **not a paddy mask** | No | Rectangle 108.92–109.38 E, −7.60 to −7.25 S; no land-cover class |
| `climatology_baseline_banyumas.parquet` | 7,224 | `FCE7BBA7740A6A5D` | Dekadal μ/σ for LST, precipitation, soil moisture | Generated by `task9` | **Synthetic** | No | 36 rows; sine + noise; no seed; not from NASA data |
| `crop_rotation_matrix.json` | 1,805 | `0CA060884ACBC400` | Three rotation scenarios | Hand-written | **Assumed** | Partial | No citations; lacks economic, K_sat, erosion, non-host-duration fields needed by Arya's Pareto solver |
| `nitrogen_balance_output.json` | 444 | `CC5EBD1E96603404` | Soybean N balance | `nitrogen_dynamics.py` | **Model output from assumptions** | Partial | 2.5 t/ha yield, 3.75 t/ha residue, 93.75 kg N, 75 kg fixed, 30 kg available — all assumption-driven |
| `data_pipeline_benchmark.json` | 447 | `680A5CA0F4E764FD` | Fake benchmark report | `task11` | **Simulated** | No | Steps 0.6086 + 2.6537 + 3.8881 + 0.528 = 7.6784 s of `sleep`, reported as PASS |

---

## 4. Arya — received work

Source archive was received 2026-11-11; files were already placed in
`external/aryas_workresult/` before Task 0 and are preserved unchanged.

| File | Purpose | Data source | Actual vs synthetic | Dependencies | Ready | Known issues |
|---|---|---|---|---|---|---|
| `pvrs_engine.py` | PVRS score, native-support SMAP inversion, optical-lag estimate, Lipschitz error bound, gates 1–2 | Intended: ECOSTRESS ESI/LST, SMAP L4, HLS NDVI | **Real formulas; synthetic demo inputs** | `numpy` | Yes (as physics reference) | Baseline must be real per cell; demo baseline and observation are hand-set; gate inputs (age, cloud, zenith) are absent from Arief's GeoJSON |
| `bf_ehsi_engine.py` | MBSI, bare fraction, crack depth, hydrological connectivity, BF-EHSI, cumulative risk D_i | Intended: HLS reflectance, ECOSTRESS LST, GPM extremes, SMAP surface moisture | **Real formulas; synthetic demo series** | `numpy` | Yes (as physics reference) | Constants (K_rusle, TWI_max, thresholds) need local calibration; MBSI→bare fraction mapping is an assumption; demo reflectance/LST/rain are synthetic |
| `build_water_balance_banyumas.py` | 90-day root-zone water balance for three rotations + Excel export | **`np.random` simulation** with FAO-56 Kc values | **Simulated** | `numpy`, `openpyxl` | Partial (Excel/format logic) | Columns labelled "GPM IMERG" and "NASA POWER" contain simulated values; irrigation saving came out 100% in verification, which is not physically credible; Kc values and initial moisture need validation |
| `fiscal_actuarial.py` | Three-tier N ledger, APBN subsidy saving, AUTP actuarial clearing, WBC model, Pareto ε-constraint solver, contract builder | Intended: agronomic and fiscal parameters | **Real implementation; assumed parameters** | stdlib only | Yes (solver/ledger), Partial (contract builder) | `build_grid_cell_contract_json()` hardcodes PVRS 0.8124, BF-EHSI 0.6480, SMAP 0.1912, ESI 0.38, LST anomaly 2.10, BSI 0.384, NDVI 0.74, rain 54.0, slope 8.4, and `h3_parent_res7`; subsidy/insurance constants need validation |
| `grid_cell_contract_sample.json` | Contract field reference | Console output of `fiscal_actuarial.py` | Real sample values, but payload values are hardcoded | none | No (not machine-readable) | UTF-16 console log: begins `=== LAPORAN AUDIT ... ===` and contains two JSON blocks. `json.load()` fails. Not a schema. No official v1.0 schema exists |
| `water_balance_banyumas.xlsx` | Excel output | Simulator | **Simulated** | Excel viewer / `openpyxl` | Partial (format reference) | Two sheets, 90 rows; formulas reference the synthetic daily sheet |

---

## 5. Forensic findings (measured, not assumed)

### 5.1 `banyumas_h3_precomputed.geojson`

| Check | Measured value |
|---|---|
| Feature count | 1,000 |
| Unique `h3_index` values | **1,000** |
| H3 resolution | **9** (all cells; index length 15, prefix `89`) |
| Geometry | 1,000 `Polygon`, rings closed |
| Generation | `h3.grid_disk(center, k_rings=18)` around `(-7.45, 109.17)`, truncated to 1,000 |
| Ring distance from centre | 0 through 18 (contiguous disc) |
| Bounding box | 109.11175–109.22587 E, −7.50322 to −7.39568 S |
| Total cell area | ~102.03 km² |
| Paddy mask clipping | **None** |
| `land_cover` | **Hardcoded `"Paddy Field"` in every feature** |
| MODIS_LST | `random.uniform(26.5, 31.0)` → observed 26.5–31.0 |
| SMAP_ROOTZONE | `random.uniform(0.30, 0.55)` → observed 0.3002–0.5498 |
| GPM_P95 | `random.uniform(5.0, 45.0)` → observed 5.02–44.98 |
| NDVI | `random.uniform(0.40, 0.85)` → observed 0.4005–0.8495 |
| MBSI | `random.uniform(-0.15, 0.10)` → observed −0.1499–0.0998 |

**Conclusion:** this is a synthetic hexagonal UI/demo fixture, not a paddy-field
dataset and not a satellite observation. The exact random ranges in the source
match the observed extrema, confirming `random.uniform` generation.

Missing fields needed by AI Core: ESI, observation timestamp/age, cloud fraction,
sensor zenith, QA flags, slope, TWI, surface soil moisture, HLS reflectance bands,
native pixel IDs.

### 5.2 `climatology_baseline_banyumas.parquet`

- Shape: 36 rows × 8 columns.
- Columns: `month`, `dekad`, `LST_mu`, `LST_sigma`, `Precipitation_mu`,
  `Precipitation_sigma`, `Soil_mu`, `Soil_sigma`.
- No nulls; all 12 months × 3 dekads.
- Values are consistent with
  `28 + 2·sin(...) + N(0,1.5)`, `max(0, 10 − 10·sin(...) + N(0,5))`, and
  `0.3 − 0.1·sin(...) + N(0,0.05)`.
- **It is not a climatology of NASA observations** and must not be used as a
  baseline for PVRS until replaced.

### 5.3 `banyumas_paddy_roi.geojson`

- One polygon: `[108.92,−7.60] → [109.38,−7.60] → [109.38,−7.25] → [108.92,−7.25]`.
- It is exactly the fallback bbox in the GEE scripts.
- No WorldCover class-40 mask, no administrative boundary, no clipping.

### 5.4 `data_pipeline_benchmark.json`

- Sum of the four reported step times equals the total (7.6784 s).
- Every step is a `time.sleep(random.uniform(...))` call.
- The script has no data loading, no H3 indexing, no GEE call, and no write cost
  measurement. It is a demo timer, not a benchmark.

### 5.5 Windows reproducibility

`task9_climatology_baseline.py` raises `UnicodeEncodeError` on a cp1252 console
when printing `μ`/`σ` before writing the parquet. On a UTF-8 terminal it proceeds.
Either way, the output is non-deterministic because `numpy.random` is unseeded.

---

## 6. Existing repository files (pre-Task 0)

| File | Purpose | Status / action |
|---|---|---|
| `README.md` | Project overview | Rewritten in Task 0; previous content preserved in spirit (structure, roles, setup) |
| `CONTRIBUTING.md` | Branch/PR rules | Expanded with contract, data-integrity, and secret rules |
| `.gitignore` | Git exclusions | Expanded (secrets, raw data, caches, node) |
| `requirements.txt` | Dependencies | Replaced with tested Python 3.12 pins; optional split out |
| `docs/contract_governance.md` | Contract approval rules | Preserved unchanged |
| `audit_report.md` | Prior Phase 1 audit (Indonesian) | **Moved** to `docs/audit_report_phase1.md`; content unchanged |
| `test_h3.py` | Exploratory H3 check | **Moved** to `tests/manual/test_h3_smoke.py`; content unchanged; not a pytest test |
| `src/__init__.py` + `src/{contracts,engines,models,utils}/__init__.py` | Package skeleton | Preserved |
| `tests/__init__.py` | Test package marker | Preserved |
| `external/aryas_workresult/*` | Arya's work | Preserved unchanged; README added |
| `data/boundaries/banyumas_paddy_roi.geojson` | Copy for stable access | Added in Task 0; original untouched |
| `docs/contracts/` | Empty directory | Preserved (empty); not removed |

No source file from Arya or Arief was deleted or modified.

---

## 7. Known-issue register

| ID | Severity | Issue | Where |
|---|---|---|---|
| KI-01 | High | H3 grid is a `grid_disk` disc around one point, not a paddy-field coverage | `task10_precomputed_geojson.py` |
| KI-02 | High | H3 cells are not clipped to a verified paddy mask | `task10`, `gee_environment_init.py` |
| KI-03 | High | `land_cover` is hardcoded `"Paddy Field"` | `task10` |
| KI-04 | High | MODIS LST, SMAP, GPM, NDVI, MBSI values are random synthetic | `task10` |
| KI-05 | High | Contract sample is a UTF-16 console log, not valid JSON; no ratified schema | `grid_cell_contract_sample.json`, `contracts/` |
| KI-06 | High | Contract builder hardcodes physical indicator values and parent H3 | `fiscal_actuarial.py` |
| KI-07 | High | Climatology baseline is synthetic sine + noise | `task9_climatology_baseline.py` |
| KI-08 | High | Benchmark uses `time.sleep()`; not a pipeline measurement | `task11_benchmark.py` |
| KI-09 | High | HLS extraction uses Sentinel-2 SR Harmonized, not NASA HLS; water balance labels simulated values as GPM/POWER | `extract_hls_vegetation_bsi.py`, `build_water_balance_banyumas.py` |
| KI-10 | High | Crop-rotation and nitrogen parameters need agronomic validation; Arief's and Arya's N models disagree | `crop_rotation_matrix.json`, `nitrogen_dynamics.py`, `fiscal_actuarial.py` |
| KI-11 | Medium | Smoke test reports pipeline "SIAP" even when 0 scripts are copied; no schema/units checks | `task12_smoke_test_deconstruction.py` |
| KI-12 | Medium | GPM script uses IMERG V06 / `precipitationCal`, silent CHIRPS fallback; P95 on half-hourly rates | `extract_gpm_precipitation.py` |
| KI-13 | Medium | ECOSTRESS scene mean ignores irregular overpasses and QC/cloud flags | `extract_ecostress_banyumas.py` |
| KI-14 | Medium | No random seeds in synthetic generators; outputs differ each run | `task9`, `task10`, `task11` |
| KI-15 | Medium | GEE project ID is hardcoded; scripts assume ambient credentials | all GEE scripts |
| KI-16 | Low | `μ`/`σ` print crashes on cp1252 Windows console | `task9` |
| KI-17 | Low | ROI file is a bbox but named as a paddy ROI | `banyumas_paddy_roi.geojson` |
| KI-18 | Low | MBSI (engine) vs HLS_BSI (contract) naming mismatch | Arya contract/engine |
| KI-19 | Low | Empty `docs/contracts/` directory is redundant with `/contracts` | `docs/` |

---

## 8. Actual vs synthetic summary

| Category | Count | Files |
|---|---|---|
| Verified real NASA observations | **0** | — |
| Real NASA acquisition code, output unverified | 7 scripts | `extract_*`, `task7_extract_h3`, `harmonize_h3_spatial`, `gee_environment_init` |
| Synthetic data artifacts | 3 | H3 GeoJSON, climatology Parquet, benchmark JSON |
| Boundary only (not a mask) | 1 | paddy ROI GeoJSON |
| Assumption-based model artifacts | 2 | crop rotation JSON, nitrogen JSON |
| Real physics/fiscal implementations | 4 | Arya engines |
| Simulated model output | 1 | water balance XLSX |

## 9. Integration readiness

| Ready to reuse as-is | Ready with corrections | Not ready |
|---|---|---|
| Arya's PVRS/BF-EHSI/fiscal solver logic (import, do not copy) | Arief's GEE query structure; Arief's GeoJSON as UI fixture; Arya's Excel formatting | H3 data as paddy observations; climatology baseline; benchmark; contract sample as schema; HLS/GPM scripts as NASA pipelines; water-balance values as measured |

Integration sequencing and module-level blockers are in
`docs/ai_core_readiness.md`.
