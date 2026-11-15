# Crop Modeling End-to-End Integration Readiness Audit

**Audit scope:** Crop Modeling Module integration readiness.

**Repository:** branch `feature/rifaldi-ui`, HEAD `9fc3702`.

**Status:** audit only. No Historical & Spatial, Weather API, Economic/Actuarial, Integration/Decision Engine, frontend, PVRS, or BF-EHSI code was changed in this task. No commit/push/merge/branch switch was performed.

**Important:** passing unit tests prove software behavior, not agronomic or production readiness.

---

## 1. Executive Summary

The Crop Modeling Module has a clear software interface, but the repository does **not** yet contain the upstream adapters or data needed to produce an end-to-end crop recommendation.

### Ready/usable now

- `CropRegistry` loads and validates the registry, units, sources, and missing/null policy.
- `EnvironmentContext`, `ForecastBundle`, `ForecastDay`, `CandidateMetrics`, `RotationCandidateRecord`, and `TacticalAdvisory` are defined.
- Suitability, calendar, ETc, one-step and forward water balance, candidate generation, Pareto adapter, and tactical advisor execute with explicit inputs.
- Pareto solver integration reuses `solve_pareto_epsilon_constraint()`.
- Missing metrics/data fail closed (`INSUFFICIENT_DATA`, `CONDITIONAL`, `ABSTAIN`); no default economic value is inserted.
- `TacticalAdvisory` now includes `cell_id`, date, action, status, reason, evidence, and limitations.
- 32 crop modeling tests pass.

### Not ready

- No adapter from Banyumas H3 GeoJSON to `EnvironmentContext`.
- BF-EHSI is `null` in the actual H3 data.
- SMAP wetness is not root-zone water storage in mm.
- GPM dekadal rainfall is not daily forecast precipitation or effective rainfall.
- SRTM slope is not drainage capacity.
- No actual Meteomatics H+1–H+3 forecast.
- No local soil hydraulic properties (FC/WP/saturation/Ksat/drainage).
- Crop registry is incomplete: paddy/Vima-1/Sorgum phase lengths, N requirement, suitability ranges, prices/costs, and pest host status are missing.
- No Economic/Actuarial module output is connected.
- No Integration/Decision API exists.
- Current registry candidates are `INSUFFICIENT_DATA`; `pareto_optimize_records()` returns `NO_ELIGIBLE_CANDIDATE`.

**Integration verdict:** **PARTIAL / BLOCKED for end-to-end decision output.** The module is a validated software foundation, not a production-ready integrated crop recommendation system.

---

## 2. Architecture and Current Flow

```text
Crop Parameter Registry (JSON)
        │
        ▼
CropRegistry / CropRecord / ParameterValue
        │
        ├──► evaluate_suitability(CropRecord, EnvironmentContext)
        ├──► build_calendar(CropRecord, planting_date)
        ├──► seasonal_etc(CropRecord, ETo-by-stage)
        ├──► daily_water_balance / forward_water_balance
        └──► generate_candidates(...)
                 │
                 ├──► RotationCandidateRecord
                 └──► pareto_optimize_records()
                          └──► existing solve_pareto_epsilon_constraint()

Historical/Spatial indicators ──(no adapter)──► EnvironmentContext
Meteomatics forecast ──────────(no client)──► ForecastBundle
Economic/Actuarial metrics ────(no adapter)──► CandidateMetrics
Integration/Decision Engine ───(absent)─────► API/contract
Tactical: CropRecord + EnvironmentContext + ForecastBundle → TacticalAdvisory
```

### Actual module files

| File | Role |
|---|---|
| `src/crop_modeling/models.py` | Dataclasses, status enums, input/output structures |
| `src/crop_modeling/registry.py` | Registry loader and unit/source/status validation |
| `src/crop_modeling/water.py` | ETc, seasonal ETc, one-step and forward water balance |
| `src/crop_modeling/suitability.py` | Explicit suitability checks and missing/conditional logic |
| `src/crop_modeling/calendar.py` | Stage windows, planting/harvest events |
| `src/crop_modeling/rotation.py` | Candidate generation, constraint aggregation, Pareto adapter |
| `src/crop_modeling/tactical.py` | H+1–H+3 tactical rules |
| `data/registry/crop_parameter_registry.json` | Crop parameters/provenance |
| `contracts/crop_parameter_registry.schema.json` | Registry schema |
| `tests/test_crop_modeling.py` | Crop modeling tests |

---

## 3. Input/Output Contracts per Module

### 3.1 Crop Registry

**Input:** JSON registry (`data/registry/crop_parameter_registry.json`).

**Output:** `CropRegistry` containing `CropRecord` and `ParameterValue`.

**Validation:**
- source IDs resolve;
- unit IDs resolve;
- `missing` requires `value=null`;
- non-missing requires a value and source;
- duplicate crop/source IDs rejected.

**Status:** **READY for interface use, incomplete for content.**

### 3.2 Suitability

**Function:** `suitability.py::evaluate_suitability(crop, environment)`.

**Input:** `CropRecord`, `EnvironmentContext` (soil pH, slope, drainage, salinity, PVRS/BF-EHSI context).

**Output:** `SuitabilityResult` with `SUITABLE`, `CONDITIONALLY_SUITABLE`, `UNSUITABLE`, or `INSUFFICIENT_DATA`, plus checks/missing/reasons.

**Current constraint:** target crop registry has no pH range, drainage classes, or slope limit; actual H3 cell has no soil pH/drainage/salinity. Therefore actual suitability is `INSUFFICIENT_DATA`.

### 3.3 Calendar

**Function:** `calendar.py::build_calendar(crop, planting_date)`.

**Input:** `CropRecord` with `phase_lengths_days`, ISO planting date.

**Output:** `CalendarResult` with status, stage windows, planting/harvest events, missing.

**Current status:**
- Padi: `INSUFFICIENT_DATA` (no phase lengths)
- Anjasmoro: `PROVISIONAL_PROXY` (FAO proxy phases)
- Vima-1: `INSUFFICIENT_DATA`
- Sorgum: `INSUFFICIENT_DATA`

### 3.4 Water

**Functions:**
- `et_c(kc, eto)`
- `seasonal_etc(crop, eto_by_stage)`
- `daily_water_balance(...)`
- `forward_water_balance(...)`

**Input:** Kc/ETc, ETo, effective rainfall, irrigation, runoff, percolation, storage/FC/WP/saturation.

**Output:** `WaterResult` or `ForwardWaterResult`.

**Important:** raw precipitation is not effective rainfall; seasonal ET is not irrigation demand; no missing component is defaulted.

### 3.5 Candidate Generator

**Function:** `rotation.py::generate_candidates(...)`.

**Output:** `RotationCandidateRecord` with candidate ID, cell ID, sequence, season count, status, metrics, checked/unchecked constraints, rejection reasons, limitations, evidence, data quality, optional Pareto candidate.

**Current actual result:** all tested registry candidates are `INSUFFICIENT_DATA`.

### 3.6 Pareto Adapter

**Function:** `rotation.py::pareto_optimize_records(records)`.

**Input:** `RotationCandidateRecord` objects.

**Output:** `ParetoResult` from Arya’s existing solver.

**Rule:** only `ELIGIBLE` + `pareto_ready` + non-null `pareto_candidate`/`candidate_metrics` enter ranking.

**Current actual result:** `NO_ELIGIBLE_CANDIDATE`.

### 3.7 Tactical Advisor

**Function:** `TacticalCropAdvisor.advise(crop, growth_stage, environment, forecast, planting_date=None)`.

**Output:** tuple of `TacticalAdvisory` with `cell_id`, date, action, status, reason, evidence, limitations, crop/stage.

**Actions:** planting, irrigation, fertilization, drainage, harvest; fallow via `advise_fallow()`.

---

## 4. Integration Contract Matrix

| Source Module | Data / Field | Expected Crop Modeling Contract | Current Interface | Gap | Owner | Priority |
|---|---|---|---|---|---|---|
| Historical & Spatial | H3 cell ID | `EnvironmentContext.cell_id` (`str`) | Available | No adapter from `public/banyumas_h3_indicators_v2.geojson` to context | Historical/Spatial | **Critical** |
| Historical & Spatial | PVRS | `EnvironmentContext.pvrs` (`float`) | Available | Static/precomputed only; no timestamp/freshness typed field | Historical/Spatial + Crop | **High** |
| Historical & Spatial | BF-EHSI | `EnvironmentContext.bf_ehsi` (`float`) | Available | Actual value `null` for all 1,000 cells; engine not integrated | Historical/Spatial | **Critical** |
| Historical & Spatial | SMAP wetness | `EnvironmentContext.soil_moisture_mm` (`float`, mm) | Type exists | Data is `smap_wetness` m³/m³, not root-zone mm; no approved conversion | Historical/Spatial + Crop | **Critical** |
| Historical & Spatial | NDVI / BSI | Crop context / future suitability | No `EnvironmentContext` field | No mapping/adapter; not used by suitability | Historical/Spatial + Crop | **High** |
| Historical & Spatial | GPM rainfall | Forecast/water input (`mm`) | No mapping | `gpm_rain_dekad` is static dekadal, not daily forecast/effective rainfall | Historical/Spatial + Weather | **High** |
| Historical & Spatial | SRTM slope | `EnvironmentContext.slope_deg` (`degree`) | Type exists | Available as `srtm_slope`; no adapter; slope alone is not drainage capacity | Historical/Spatial + Crop | **Medium** |
| Historical & Spatial | Soil properties | FC, WP, saturation, Ksat, pH, texture, drainage | Environment fields partially exist | No local soil dataset/adapter; current simulator uses assumed profile | Historical/Spatial | **Critical** |
| Weather API | Forecast date/time, provider, issue/retrieval/valid | `ForecastBundle` / `ForecastDay` | Interface exists | No Meteomatics client; no actual forecast | Weather/Integration | **Critical** |
| Weather API | ETo | `ForecastDay.eto_mm` (`mm/day`) | Field exists | No provider/derivation; unit enforcement not implemented | Weather + Crop | **Critical** |
| Weather API | Rainfall / effective rainfall | `precipitation_mm`, `effective_rain_mm` (`mm/day`) | Fields exist | Must be separately supplied; no raw-to-effective conversion | Weather + Historical | **Critical** |
| Weather API | Runoff / deep percolation | `ForecastDay.runoff_mm`, `deep_percolation_mm` (`mm/day`) | Fields exist | No supplier/model; must not default to zero | Weather + Historical | **High** |
| Weather API | H3/location mapping | `cell_id` + forecast location | Not implemented | No H3-to-forecast mapping or spatial-resolution metadata | Weather/Integration | **High** |
| Economic/Actuarial | Revenue, cost, profit, prices, input costs | `CandidateMetrics` fields (`IDR/ha`, etc.) | Interface exists | No Economic/Actuarial adapter; all actual metrics missing | Arya/Economic | **Critical** |
| Economic/Actuarial | AUTP/fiscal metrics | Not calculated in Crop Modeling | Not passed to crop module | Should be supplied separately; Crop Modeling must not duplicate | Arya/Economic | **High** |
| Economic/Actuarial | Product basis (GKG/GKP/dry seed) | Crop registry/product basis; metrics basis | Registry has basis; metrics adapter absent | Need basis/period/unit consistency in CandidateMetrics | Arya/Economic + Crop | **High** |
| Integration/Decision | Final API/JSON response | Candidate records + tactical advisories | No API | No Integration/Decision Engine or contract serializer | Integration/Decision | **Critical** |
| Crop Modeling | Candidate statuses | `ELIGIBLE/CONDITIONAL/INSUFFICIENT_DATA/REJECTED` | Implemented | Actual registry yields no eligible candidate | Crop Modeling | **High** |
| Crop Modeling | Tactical statuses | `RECOMMENDED/CONDITIONAL/DEFER/ABSTAIN` | Implemented | Actual local/forecast inputs missing, so most actions ABSTAIN | Crop Modeling + upstream | **High** |
| Frontend | Display of crop advisory | Not in scope | No change | Integration/API must provide contract first | Frontend/Integration | **Medium** |

### Status grouping

- **READY:** internal dataclasses/functions, CandidateMetrics interface, TacticalAdvisory fields.
- **PARTIAL:** H3 cell ID, PVRS, slope, registry, calendar, Pareto adapter.
- **MISSING:** BF-EHSI actual values, soil hydraulic properties, NDVI/BSI mapping, effective rainfall/runoff/percolation, weather provider, economic metrics, final API.
- **BLOCKED:** end-to-end eligible candidate and operational advisory until upstream data/contracts arrive.

---

## 5. Candidate Generator Audit

### 5.1 Actual registry completeness

| Crop | Observed | Standard | Proxy | Derived | Missing | Missing count |
|---|---:|---:|---:|---:|---:|---:|
| Padi Inpari 32 | 3 | 6 | 0 | 0 | 10 | 10 |
| Kedelai Anjasmoro | 2 | 6 | 1 | 0 | 10 | 10 |
| Kacang Hijau Vima-1 | 3 | 5 | 0 | 0 | 11 | 11 |
| Sorgum | 0 | 6 | 0 | 0 | 13 | 13 |

### 5.2 Actual candidate run

For cell `898d8d60803ffff`, crops Padi + Kedelai, 2 seasons:

| Candidate | Status | Checked | Unchecked | Pareto ready |
|---|---|---|---|---|
| `...:padi_inpari_32_hdb+kedelai_anjasmoro` | `INSUFFICIENT_DATA` | crop exists, season count, duration | suitability (both), paddy calendar, water ETc, Pareto metrics | false |
| `...:kedelai_anjasmoro+padi_inpari_32_hdb` | `INSUFFICIENT_DATA` | crop exists, season count, duration | suitability (both), both calendars, water ETc, Pareto metrics | false |

`pareto_optimize_records()` returns `NO_ELIGIBLE_CANDIDATE`.

### 5.3 Why candidates are not ELIGIBLE

- Suitability: no pH range, drainage class, slope threshold, or salinity input for the crops/cell.
- Calendar: paddy/Vima/Sorgum phase lengths missing; Anjasmoro only proxy.
- Water ETc: no `eto_by_crop_stage` supplied; paddy phase lengths missing.
- Pareto metrics: no revenue/cost/SOC/BPH/Ksat/erosion metrics from Economic/Integration.
- BF-EHSI absent.
- Local soil properties absent.

### 5.4 Requirements for statuses

**To become `CONDITIONAL`:**
- crop exists and duration present;
- no known suitability failure;
- missing constraints explicitly listed;
- no fabricated values.

**To become `ELIGIBLE`:**
- every crop suitability check must be evaluated and pass with approved thresholds;
- calendar must be complete (`OK`, not `PROVISIONAL_PROXY`);
- water ETc must be complete from Kc + ETo;
- Pareto metrics complete and valid;
- no unchecked mandatory constraint.

**To become `pareto_ready = true`:**
- `status == ELIGIBLE`;
- complete `CandidateMetrics`;
- `pareto_candidate` built;
- all units/bases consistent.

No status should be forced upward.

---

## 6. Tactical Advisor Audit

### 6.1 Action matrix

| Action | Required inputs | Available now | Missing now | Status behavior |
|---|---|---|---|---|
| Planting | crop duration, forecast precipitation, soil moisture/field condition | crop duration registry; forecast interface | actual forecast, soil condition, approved seedbed threshold | rain → CONDITIONAL; missing duration/soil → ABSTAIN/CONDITIONAL |
| Irrigation | storage, FC/WP/saturation, Kc, ETo, effective rain, runoff, percolation | Kc/interface | actual local soil, actual forecast, effective rain/runoff/percolation | missing → ABSTAIN; storage ≥ FC → DEFER; deficit → CONDITIONAL |
| Fertilization | N requirement, stage, rain forecast | stage; N field in registry | N requirement all null | missing N → ABSTAIN; rain → CONDITIONAL |
| Drainage | soil moisture, saturation, drainage capacity/outlet | soil fields in interface | local soil/drainage data | missing → ABSTAIN; saturation+rain → CONDITIONAL; no unsourced RECOMMENDED |
| Harvest | planting date, crop age/calendar, maturity indicator, forecast | crop duration for some crops | planting date, field maturity indicator, actual forecast | missing maturity → ABSTAIN/CONDITIONAL; no final readiness claim |
| Fallow | BF-EHSI context, forecast | BF-EHSI field in interface | actual BF-EHSI (`null`) | missing BF-EHSI → ABSTAIN; context+rain → CONDITIONAL |

### 6.2 Output fields

All advisories have:
- `action`
- `status`
- `reason`
- `evidence`
- `limitations`
- `date`
- `cell_id`
- `crop_id`
- `growth_stage`

### 6.3 Sequential water balance

`forward_water_balance()` is correctly sequential:
- H+1 initial storage;
- H+2 H+1 storage;
- H+3 H+2 storage;
- missing later-day input stops projection;
- storage clamped to WP/saturation.

Tactical irrigation uses this function only when all required inputs are present. Otherwise it returns `ABSTAIN`; it does not use raw precipitation as effective rainfall.

### 6.4 Actual tactical run

With actual cell and no forecast:

`TacticalCropAdvisor.advise(...)` returns **`FORECAST ABSTAIN`**: “Forecast is stale; no tactical action can be recommended as current.”

This is correct fail-closed behavior, not evidence of operational readiness.

---

## 7. End-to-End Scenario for One H3 Cell

### 7.1 Selected cell

**Cell:** `898d8d60803ffff` from `public/banyumas_h3_indicators_v2.geojson`.

Actual values:

| Field | Value | Unit/semantics | Status |
|---|---|---|---|
| `pvrs` | 0.2428 | dimensionless | Static/precomputed |
| `bf_ehsi` | null | — | Missing |
| `smap_wetness` | 0.3923 | m³/m³ (not root-zone mm) | Static/coarse |
| `ecostress_esi` | null | — | Missing |
| `lst_anomaly` | -0.6586 | °C | Static/MODIS-derived |
| `hls_bsi` | -0.4125 | dimensionless | Static |
| `hls_ndvi` | 0.7715 | dimensionless | Static |
| `gpm_rain_dekad` | 60.485 | mm/dekad | Static, not daily forecast |
| `srtm_slope` | 7.3356 | degree | Static |
| `paddy_fraction` | 0.0748 | fraction | Static/Sentinel-derived |
| `system_state` | `ABSTAIN_FIELD_AUDIT_REQUIRED` | status | Precomputed |

`meta.contract_version` is `grid_cell_contract_v1.2`; no matching v1.2 schema is in repository. The cell has no soil hydraulic properties, no root-zone mm, no drainage class, no pH, no actual weather.

### 7.2 Flow result

1. **H3 context**: available as static GeoJSON; no adapter to `EnvironmentContext`.
2. **Suitability**: with actual available values, paddy/kedelai/Vima/Sorgum → `INSUFFICIENT_DATA` due missing pH/drainage/slope thresholds and BF-EHSI.
3. **Calendar**: paddy/Vima/Sorgum → `INSUFFICIENT_DATA`; Anjasmoro → `PROVISIONAL_PROXY`.
4. **Rotation candidate**: Padi+Kedelai → `INSUFFICIENT_DATA`; no `pareto_candidate`; Pareto → `NO_ELIGIBLE_CANDIDATE`.
5. **Tactical**: no actual Meteomatics forecast → `FORECAST ABSTAIN`.
6. **Integration output**: only incomplete candidate records with explicit missing reasons; no valid recommendation.

### 7.3 What the output can say

```text
cell_id: 898d8d60803ffff
crop_sequence: padi_inpari_32_hdb + kedelai_anjasmoro
status: INSUFFICIENT_DATA
checked: crop_exists, season_count, growing_duration
unchecked:
  suitability:padi_inpari_32_hdb
  suitability:kedelai_anjasmoro
  calendar:padi_inpari_32_hdb
  water_etc
  pareto_metrics
pareto_ready: false
tactical: FORECAST ABSTAIN (no current forecast)
```

This is a **correct abstention**, not a failed generator. Synthetic fixtures may be used to test software, but they are **not** evidence of Banyumas agronomic validity.

---

## 8. Blockers and Data Needed

### Critical blockers

1. No H3-to-`EnvironmentContext` adapter for local PVRS/BF-EHSI/SMAP/NDVI/BSI/GPM/slope.
2. No root-zone soil water in mm or local FC/WP/saturation/Ksat.
3. BF-EHSI is null; no integration.
4. No actual Meteomatics forecast, effective rainfall, runoff, or deep percolation.
5. No Economic/Actuarial `CandidateMetrics`; no revenue/cost/SOC/BPH/Ksat/erosion supply.
6. No Integration/Decision API or contract serializer.
7. Registry lacks phase lengths (Padi/Vima/Sorgum), N requirement, suitability thresholds, prices/costs, pest host status.

### High

- PVRS/BF-EHSI timestamps/freshness not typed in context.
- SMAP/GPM native resolution and aggregation semantics need documentation.
- Anjasmoro phase lengths are proxy only.
- Harvest maturity indicators absent.
- Drainage capacity/outlet condition absent.

### Medium

- Calendar transition/turnaround/fallow duration not modeled.
- Forecast uncertainty/hysteresis policy not implemented.
- No local calibration dataset.

---

## 9. Recommended Implementation Order

1. **Freeze integration contracts**
   - Define `EnvironmentContext` adapter output and typed freshness/units.
   - Define `ForecastBundle` provider output and H3/location mapping.
   - Define `CandidateMetrics` economic input contract.

2. **Historical/Spatial adapter**
   - Map actual H3 fields to context.
   - Convert SMAP wetness to root-zone mm only with an approved method; otherwise leave null.
   - Add BF-EHSI values or explicitly null.
   - Map slope; add soil properties.

3. **Weather adapter**
   - Meteomatics H+1–H+3 parser.
   - ETo and effective rainfall; runoff/percolation only with approved derivation.
   - Provider/issue/retrieval/valid/units/stale metadata.
   - H3/location mapping.

4. **Economic/Actuarial adapter**
   - Supply `CandidateMetrics` only; do not duplicate economic calculations.
   - Enforce product basis/units/period.

5. **Crop registry completion**
   - Phase lengths for Padi/Vima/Sorgum.
   - N requirement/fixation, suitability thresholds, local yield/prices/costs, pest host status.
   - Keep `null` until sourced.

6. **Integration/Decision API**
   - Serialize `RotationCandidateRecord` + tactical advisories.
   - Preserve statuses, reasons, evidence, limitations, missing fields.
   - Do not promote conditional/insufficient candidates.

7. **Validation**
   - Unit tests (already), integration tests with actual adapters, scenario tests, field validation.

---

## 10. Tests Run and Results

| Command | Result |
|---|---|
| `pytest tests/test_crop_modeling.py -q` | **32 passed** |
| Full Python suite | **275 passed, 1 failed** |
| `pnpm test` | **8 passed** |

### Existing failure

`tests/test_demo_geometry.py::test_synthetic_multiresolution_parents_are_valid_and_not_observations` (`KeyError: 'synthetic'`) is a pre-existing data/test mismatch, not a crop modeling regression.

### Test interpretation

- **Software correctness:** validated.
- **Interface compatibility:** partially validated through dataclasses.
- **Agronomic validity:** not established.
- **Local calibration:** not performed.
- **Production readiness:** not established.

---

## 11. Bottom Line

### Ready to integrate

- Crop modeling dataclasses and registry loader.
- Suitability/calendar/water/candidate/tactical functions.
- Candidate status/evidence output.
- Pareto adapter with strict eligibility filtering.
- Tactical output fields including `cell_id`.

### Not ready

- Actual Banyumas environment adapter.
- BF-EHSI values.
- Local soil/water data.
- Meteomatics forecast.
- Economic metrics.
- Integration/Decision API.
- Complete crop registry.

### Most critical blocker

The upstream data contract is not implemented: H3 indicators are static fields, BF-EHSI is null, SMAP wetness is not root-zone storage, GPM is not daily effective rainfall, and no forecast/economic metrics are connected. Without those, Crop Modeling correctly returns `INSUFFICIENT_DATA`/`ABSTAIN`; it must not be forced to produce recommendations.

### Next task

Implement the **Historical/Spatial → EnvironmentContext adapter** first, with explicit units/semantics and null preservation. Then add the Weather and Economic adapters and the Integration API. Do not lower eligibility statuses or fill missing data with assumptions.
