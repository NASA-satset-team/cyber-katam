# Crop Modeling Validation & Forward-Stepping Readiness Audit

**Audit context:** branch `feature/rifaldi-ui`, HEAD `9fc3702`. Audit and validation are read-only with respect to existing engines/frontend. Changes are limited to the new `src/crop_modeling/` module, registry, tests, and documentation.

**Scope:** forward-stepping water balance, crop calendar completeness, tactical advisor, scenario tests, interface readiness, and regression results.

**Important:** unit tests demonstrate software correctness and fail-closed behavior. They do **not** validate agronomic accuracy or local Banyumas field performance.

---

## 1. Audit Report

### 1.1 What existed before this task

- `src/crop_modeling/water.py` had `et_c`, `seasonal_etc`, and **one-step** `daily_water_balance`.
- There was **no forward H+1 → H+2 → H+3 sequential balance**.
- `calendar.py` could build a calendar from registry phase lengths, but only Kedelai Anjasmoro had phase lengths (FAO generic proxy).
- `tactical.py` had planting, irrigation, fertilization, drainage, harvest, and fallow advisories.
- Tactical irrigation used a simple refill deficit, not crop-specific ETc.
- `CalendarResult.status` returned `OK` even when phase lengths were proxy values.
- No scenario test covered H+2 rain, heavy rain after planting, high moisture, deficit, vegetative/generative differentiation, missing forecast values, and strategic-vs-tactical independence.

### 1.2 Changes made in this task

- Added `WaterDayInput`, `ForwardWaterResult`, and `forward_water_balance()`.
- Added sequential H+1 → H+2 → H+3 tests, including missing-day and saturation-cap tests.
- Calendar now returns `PROVISIONAL_PROXY` when phase lengths are not `observed`, and `INSUFFICIENT_DATA` when phase lengths are missing.
- Tactical irrigation now uses crop/stage Kc × forecast ETo when available, with transparent fallback when crop ETc is unavailable.
- Added scenario tests for H+2 rain, heavy rain after planting, high moisture, deficit, vegetative/generative actions, missing forecast values, missing crop N, and strategic/tactical separation.
- Added interface-readiness assertions.

No existing engine, frontend, registry source, or teammate code was modified.

---

## 2. Forward-Stepping Water Balance Validation

### 2.1 Implementation

`src/crop_modeling/water.py::forward_water_balance()`:

```text
H+1: storage_1 = balance(initial_storage, day_1)
H+2: storage_2 = balance(storage_1, day_2)
H+3: storage_3 = balance(storage_2, day_3)
```

Properties:

- Each `WaterResult.storage_end_mm` is passed to the next day.
- `H+1` uses the supplied initial storage.
- If any day has a missing component, processing stops.
- No later day is fabricated.
- Storage is clamped to wilting point/saturation.
- Saturation excess is reported as `clipping_mm`.
- Units are mm/day for ETc/rain/irrigation/runoff/percolation and mm for storage.
- `effective_rain_mm` is explicitly supplied by the caller; raw forecast precipitation is not silently treated as effective rainfall.

### 2.2 Validation tests

| Test | Expected/observed |
|---|---|
| `test_forward_water_balance_uses_previous_day_storage` | Initial 80 mm, ETc 5 mm/day → 75, 70, 65 mm; final 65 mm |
| `test_forward_water_balance_stops_on_missing_day` | H+2 effective rainfall None → status `INSUFFICIENT_DATA`, 2 days returned, final None |
| `test_forward_water_balance_caps_at_saturation` | Initial 115 + rain 10 → storage 120, clipping 5 mm |
| `test_daily_water_balance_and_missing` | One-step complete/missing behavior |

### 2.3 Limitations

- `forward_water_balance` is not connected to a weather API; the integration layer must supply effective rainfall, runoff, percolation, and ETc.
- No runoff/percolation model is implemented; values must be supplied explicitly.
- Crop-specific ETc requires `kc_initial`/`kc_development`/`kc_mid`/`kc_end` and forecast ETo. The current registry lacks `kc_development` and several phase lengths, so production forward runs will often return `INSUFFICIENT_DATA`.
- The tactical advisor uses a simplified 3-day crop-ETc/rain balance; it is not the full forward water balance.

**Status:** forward-stepping **implemented and software-validated**; agronomic production use **blocked by missing inputs**.

---

## 3. Crop Calendar Completeness Report

| Crop | Phase lengths in registry | Source/evidence | Calendar behavior |
|---|---|---|---|
| Padi Inpari 32 | `null` / missing | No cultivar-specific phase split; FAO generic rice phases total 150 days vs official 120 days, therefore not used | `INSUFFICIENT_DATA` |
| Kedelai Anjasmoro | `[15, 15, 40, 15]` (85 days) | FAO-56 Table 11, Soybeans (Tropics), status `proxy`; official Anjasmoro duration 82.5–92.5 days | `PROVISIONAL_PROXY` (not `OK`) |
| Kacang Hijau Vima-1 | `null` / missing | No Vima-1 phase split; FAO green gram 110 days is not applicable to 57-day Vima-1 | `INSUFFICIENT_DATA` |
| Sorgum | `null` / missing | No variety specified; no phase split | `INSUFFICIENT_DATA` |

### 3.1 Calendar status semantics

- `OK`: phase lengths have `observed` status.
- `PROVISIONAL_PROXY`: phase lengths are `proxy`/`standard`/`derived`, not cultivar observations.
- `INSUFFICIENT_DATA`: phase lengths or planting date are missing/invalid.

### 3.2 Validation

`test_calendar_completeness_for_registry_crops` asserts:

- Padi → `INSUFFICIENT_DATA`
- Vima-1 → `INSUFFICIENT_DATA`
- Sorgum → `INSUFFICIENT_DATA`
- Anjasmoro → `PROVISIONAL_PROXY` with a note that phase lengths are not cultivar observations.

**Status:** calendar logic is ready; calendar **data** is complete only for Anjasmoro as a proxy, not as a cultivar measurement.

---

## 4. Tactical Advisor Audit

### 4.1 Actions and stage logic

| Action | Applied stages | Crop/stage logic | Current behavior |
|---|---|---|---|
| PLANTING | land preparation/planting/seeding/seedling | Stage-specific action selection; crop-specific germination threshold missing | `CONDITIONAL`/`ABSTAIN`; no automatic safe/unsafe claim |
| IRRIGATION | all except harvest | Stage Kc × forecast ETo when available; crop-specific ETc; fallback refill deficit with limitation | `DEFER`/`CONDITIONAL`/`ABSTAIN` |
| FERTILIZATION | vegetative/development/reproductive | Crop N requirement required; missing N → `ABSTAIN`; rain → `CONDITIONAL` | No unsourced leaching threshold |
| DRAINAGE | all except harvest | Stage-specific action; soil moisture/saturation; crop drainage class missing | `ABSTAIN`/`CONDITIONAL`/`DEFER`/`RECOMMENDED` only with supplied storage/saturation |
| HARVEST | maturity/harvest | Stage-specific action; rain/trafficability | `CONDITIONAL`/`RECOMMENDED` with limitations |
| FALLOW | fallow | Uses supplied BF-EHSI only | `ABSTAIN` without BF-EHSI; `CONDITIONAL` with context |

### 4.2 Advisory fields

Every advisory has:

- `date`
- `action`
- `status` (`RECOMMENDED`/`CONDITIONAL`/`DEFER`/`ABSTAIN`)
- `reason`
- `evidence`
- `limitations`
- `crop_id`
- `growth_stage`

### 4.3 Crop-specific irrigation update

Tactical irrigation now computes:

```text
projected_storage = storage + three_day_rain - three_day_crop_ETc
```

- `three_day_crop_ETc = Σ(Kc(stage) × ETo_day)` when Kc and forecast ETo are available.
- If the projected storage reaches field capacity → `DEFER`.
- If a deficit remains → `CONDITIONAL`.
- If Kc/ETo is missing → fallback to a refill deficit with a limitation, not a crop-specific claim.

This makes irrigation stage/crop-sensitive where data exist. It is still not a full daily balance; runoff, percolation, and irrigation efficiency are not applied.

### 4.4 Threshold policy

No new agronomic threshold was invented. The advisor uses:

- forecast precipitation missing / present,
- rain sum vs simple refill deficit,
- storage vs field capacity/saturation,
- crop N requirement presence,
- stale forecast status.

It does **not** use unsourced “rain > 25 mm means seed rot” or similar rules.

**Status:** tactical rule engine is software-ready; agronomic thresholds remain missing.

---

## 5. Scenario Testing

Added/retained tests:

| Scenario | Test | Result |
|---|---|---|
| Rain on H+2 | `test_tactical_h2_rain_and_heavy_rain_after_planting` | H+2 planting `CONDITIONAL` |
| No rain for three days | `test_tactical_irrigation_defer_and_conditional` | Irrigation `CONDITIONAL` |
| Heavy rain after planting | same | H+2 planting `CONDITIONAL` |
| High soil moisture | `test_tactical_high_moisture_and_deficit` | Irrigation `DEFER` |
| Water deficit | same | Irrigation `CONDITIONAL` |
| Vegetative stage | `test_tactical_stage_actions_are_specific` | Irrigation/fertilization/drainage present |
| Generative stage | same | Irrigation/fertilization/drainage present |
| Forecast missing | `test_tactical_missing_forecast_values_abstain` | Planting/irrigation `ABSTAIN` |
| Forecast stale | `test_tactical_stale_forecast_abstains` | `FORECAST` `ABSTAIN` |
| Crop parameter missing | calendar test + `test_tactical_registry_crop_missing_n_abstains` | `INSUFFICIENT_DATA` / fertilization `ABSTAIN` |
| Strategic unchanged by forecast | `test_strategic_rotation_is_independent_of_forecast` | Rotation evaluation identical |

### 5.1 Strategic/tactical separation

`evaluate_sequence()` has no forecast input. Forecast changes cannot alter the strategic candidate in this module. Tactical advisories are separate outputs. A future integration layer must preserve this separation.

**Important:** the test only proves API separation, not that a final UI/decision engine will preserve it.

---

## 6. Interface Readiness

### 6.1 Input fields

| Field | Available | Notes |
|---|---|---|
| H3 cell ID | `EnvironmentContext.cell_id` | Present |
| Crop ID | `CropRecord.crop_id` | Present |
| Growth stage | `TacticalCropAdvisor.advise(growth_stage=...)` | Present |
| Planting date | `planting_date` parameter | Present in signature; not currently used by tactical rules |
| Environmental context | `EnvironmentContext` | soil moisture, FC, WP, saturation, pH, slope, drainage, salinity, PVRS, BF-EHSI, observed_at |
| PVRS/BF-EHSI | optional fields | Consumed as context; BF-EHSI used by fallow only |
| Weather forecast H+1..H+3 | `ForecastBundle.days` | Provider, issue/retrieval/valid times, stale flag |
| Timestamp/freshness | `ForecastBundle.issue_time`, `retrieval_time`, `valid_start`, `valid_end`, `stale`; `EnvironmentContext.observed_at` | Present but not all surfaced as explicit output fields |
| Units | `ForecastDay` fields by name; registry units | Present in data model; unit validation for forecast values is not yet enforced |

### 6.2 Output fields

`TacticalAdvisory` includes date/action/status/reason/evidence/limitations/crop/stage. Forecast evidence includes provider/issue/retrieval/valid times.

### 6.3 Gaps

- `TacticalAdvisory` has no explicit `forecast_freshness_status` or `input_observed_at` field; this is embedded in evidence strings. The integration contract should add typed fields.
- `ForecastDay` does not carry per-variable units; units are documented by field name only.
- `planting_date` is accepted but not used to validate stage/date consistency.
- No final JSON serialization/API contract; dataclasses are the module interface.
- H3 ID is not cross-checked against forecast location; the integration layer must enforce it.
- No Weather API or historical ingestion is implemented, by scope.

**Status:** interface is mostly ready for integration, but typed freshness/units and H3-forecast consistency need to be added at the integration/API layer.

---

## 7. Parameters and Thresholds Still Requiring Sources

### 7.1 Crop parameters

- Cultivar-specific Kc/Kcb for Inpari 32, Anjasmoro, Vima-1, and the intended sorghum variety.
- Phase lengths for Inpari 32, Vima-1, and Sorgum; Anjasmoro currently has FAO proxy phase lengths only.
- Per-crop root depth and depletion fraction (currently FAO generic ranges).
- Local water requirement (not seasonal ET used as irrigation demand).
- Local N requirement and N fixation parameters.
- Local yield and product basis (GKP/GKG/dry seed).
- Crop prices and production costs.
- Pest host status and population parameters.

### 7.2 Suitability thresholds

- Approved pH range per crop.
- Soil texture/drainage classes.
- Slope limit per crop.
- Salinity threshold per crop (only generic FAO values for paddy/soybean/sorghum; Vima-1 null).
- Flooding/waterlogging sensitivity per crop.

### 7.3 Tactical thresholds

- Planting-after-rain / seedbed risk thresholds.
- Germination soil-moisture window.
- Fertilization leaching/runoff thresholds.
- Harvest rain/trafficability thresholds.
- Drainage action trigger beyond “storage ≥ saturation.”
- Forecast uncertainty/hysteresis policy.

### 7.4 Operational data

- KATAM Banyumas calendar/recommendations.
- Banyumas local soil and yield trials.
- Weather provider variable availability, units, freshness, and spatial resolution.
- H3-to-forecast mapping method.

---

## 8. Regression Test Results

| Command | Result |
|---|---|
| `pytest tests/test_crop_modeling.py -q` | **23 passed** |
| `pytest tests -q --tb=no` | **266 passed, 1 failed** |
| `pnpm test` | **8 passed** |
| Registry schema validation | **0 errors** |

### Existing failure

`tests/test_demo_geometry.py::test_synthetic_multiresolution_parents_are_valid_and_not_observations` fails with `KeyError: 'synthetic'`.

This is **not a regression from the crop modeling module**. The test expects the older synthetic `public/demo-grid-levels.json` schema; the current data artifact changed. It should be fixed separately by the data/UI owner.

### Test interpretation

- Software correctness: tests pass for module behavior.
- Agronomic validity: **not established**.
- Data availability: **incomplete**; many registry values are `null` and many tactical actions abstain.

---

## 9. Findings

| ID | File/function | Finding | Severity | Recommendation | New data? |
|---|---|---|---|---|---|
| F-01 | `water.py::forward_water_balance` | Forward stepping was absent before this task; now implemented and tested | High (resolved) | Keep sequential tests; integrate effective rainfall/runoff/percolation from upstream | No |
| F-02 | `water.py::daily_water_balance` | Simple balance; no runoff/percolation model; caller must supply them | Medium | Keep explicit inputs; do not default to zero | No |
| F-03 | `calendar.py::build_calendar` | Padi/Vima-1/Sorgum phase lengths missing; Anjasmoro only FAO proxy | High | Keep `INSUFFICIENT_DATA`/`PROVISIONAL_PROXY`; source cultivar phase lengths | Yes |
| F-04 | `tactical.py::_irrigation` | Crop ETc used when available; fallback refill deficit when not | Medium | Surface fallback clearly; require Kc/ETo for production advisory | Yes |
| F-05 | `tactical.py::_fertilization` | Missing N requirement → `ABSTAIN`; no unsourced leaching threshold | Medium (correct behavior) | Source N recommendation and loss thresholds before `DEFER` | Yes |
| F-06 | `tactical.py::_drainage` | Drainage uses soil storage/saturation; drainage infrastructure missing | High | Add drainage class/capacity input; do not infer from rain alone | Yes |
| F-07 | `tactical.py::advise_fallow` | Uses BF-EHSI only; no BF-EHSI action threshold | Medium | Keep `CONDITIONAL`; integration must supply BF-EHSI and threshold policy | Yes |
| F-08 | `models.py::TacticalAdvisory` | Freshness/H3 linkage is evidence-text, not typed output | Medium | Add typed forecast freshness/input timestamp/H3 fields in integration contract | No |
| F-09 | Registry | Missing local prices/costs, N, suitability, phase lengths | High | Do not fill; source with citations | Yes |
| F-10 | Strategic rotation | No forecast input; strategic/tactical separation holds | Medium (correct) | Enforce in integration engine; never pass forecast into strategic evaluator | No |
| F-11 | Existing tests | One pre-existing geometry test failure | Medium | Fix separately with data/test owner | No |

---

## 10. Bottom Line

**What is now validated:**

- Forward H+1 → H+2 → H+3 storage propagation is implemented and tested.
- Missing inputs stop the projection; no H+3 with missing H+2.
- Saturation capping is tested.
- Calendar returns `INSUFFICIENT_DATA` for missing phase lengths and `PROVISIONAL_PROXY` for proxy phase lengths.
- Tactical advisories include status/action/reason/evidence/limitations/date.
- Tactical irrigation uses crop/stage Kc × forecast ETo where available.
- Strategic rotation is independent of forecast input.
- Scenario tests cover rain, no rain, heavy rain, high/low moisture, stages, missing/stale forecast, missing crop parameters, and strategic independence.

**What is not validated:**

- Agronomic accuracy of the registry values.
- Local Banyumas yield/water/N/suitability.
- Full drainage/fertilization/harvest thresholds.
- Weather-provider integration or H3-forecast mapping.
- Production-level strategic recommendations; most candidates will be rejected/abstain until metrics are sourced.

**Readiness:** **software foundation ready for integration tests; agronomic production readiness not yet achieved.**
