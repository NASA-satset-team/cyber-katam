# Rotation Candidate Generator — Audit & Completion Report

**Task:** complete the Rotation Candidate Generator in the CYBER-KATAM Crop Modeling Module.

**Context:** branch `feature/rifaldi-ui`, HEAD `9fc3702`. No frontend, Weather API, historical ingestion, PVRS/BF-EHSI recalculation, or final integration engine was added. No commit/push/merge/branch switch was performed.

**Validation:** software correctness only. The current registry is incomplete, so most production candidates correctly return `INSUFFICIENT_DATA`/`CONDITIONAL`.

---

## 1. Audit First

### 1.1 Existing functions before this task

| Function/file | State | Audit result |
|---|---|---|
| `rotation.py::enumerate_sequences` | Implemented | Deterministic permutations from supplied crop IDs; no hardcoded A/B/C |
| `rotation.py::evaluate_sequence` | Implemented | Builds external `RotationCandidate` only when `CandidateMetrics` are complete; otherwise returns reasons |
| `rotation.py::pareto_optimize` | Implemented | Wraps Arya’s `solve_pareto_epsilon_constraint`; does not duplicate optimizer |
| `models.py::CandidateMetrics` | Implemented | Explicit economic/agronomic metric fields; no calculation/default |
| `models.py::RotationEvaluation` | Implemented | Feasible flag, reasons, metrics, external candidate |
| `registry.py::CropRegistry` | Implemented | Validates units/sources/status; null preserved |
| `calendar.py::build_calendar` | Implemented | Requires phase lengths + planting date; returns `INSUFFICIENT_DATA` when missing |
| `suitability.py::evaluate_suitability` | Implemented | Explicit constraints; missing thresholds not invented |
| `water.py::seasonal_etc` | Implemented | Requires phases/Kc/ETo; does not treat seasonal ET as irrigation demand |
| `water.py::daily_water_balance` | Implemented | One-step balance; explicit components only |
| Tests | Partial | No generator-level tests before this task |

### 1.2 Missing before this task

- No `generate_candidates()` orchestration.
- No candidate-level fields:
  - `candidate_id`
  - `cell_id`
  - `status`
  - `constraints_checked`
  - `constraints_unchecked`
  - `rejection_reasons`
  - `limitations`
  - `evidence`
  - `data_quality`
- No explicit statuses: `REJECTED`, `CONDITIONAL`, `INSUFFICIENT_DATA`, `ELIGIBLE`.
- No per-candidate suitability/calendar/water evidence aggregation.
- No direct `pareto_optimize_records` that excludes non-eligible candidates.
- No test proving actual registry does not produce false `ELIGIBLE` candidates.

### 1.3 Constraints actually supported by data

| Constraint | Supported? | Evidence/notes |
|---|---|---|
| Crop exists in registry | Yes | `CropRegistry.crops` |
| Growing duration present | Yes | Registry `growing_duration_days`; ranges accepted but not summed |
| Crop suitability | Conditional | Only if `EnvironmentContext` and registry thresholds exist; current target crops lack pH/slope/drainage ranges |
| Calendar | Partial | Only if planting date + phase lengths; only Anjasmoro has proxy phase lengths |
| Seasonal ETc | Partial | Only if phase lengths + Kc + ETo by stage; current registry lacks `kc_development`/phase lengths for most crops |
| Nitrogen | Not in generator | No N model; N metrics must be supplied by integration |
| Pest | Not in generator | No host/population model; not inferred |
| Water balance | Not in generator | One-step/forward functions exist but require supplied effective rain/runoff/percolation |
| Economics/fiscal | Not in generator | Revenue/cost/AUTP/Pareto metrics must be supplied; no dummy values |
| Forecast | Not in generator | Strategic generation has no forecast input; correct separation |

### 1.4 Constraints not yet evaluable

- Local crop suitability thresholds.
- Local phase lengths for Inpari 32, Vima-1, Sorgum.
- Local water requirement and full seasonal water balance.
- Crop-specific N requirement/fixation.
- Pest host/population.
- Economic/fiscal metrics.
- KATAM Banyumas planting windows.
- H3 cell-specific soil/weather inputs.

---

## 2. Candidate Generation Implementation

### 2.1 New API

`src/crop_modeling/rotation.py::generate_candidates()`:

```text
generate_candidates(
  registry,
  cell_id,
  environment=None,
  crop_ids=None,
  min_seasons=2,
  max_seasons=3,
  max_candidates=50,
  planting_date=None,
  eto_by_crop_stage=None,
  metrics_by_sequence=None,
) -> tuple[RotationCandidateRecord, ...]
```

Properties:

- Crop list comes from `registry.crops` unless `crop_ids` is supplied.
- Sequence lengths configurable via `min_seasons`/`max_seasons`.
- Deterministic `itertools.permutations` order.
- No direct crop repetition in a sequence (permutations of unique IDs).
- `max_candidates` limits output deterministically.
- Candidate ID: `"{cell_id}:{crop1}+{crop2}+..."`; stable for same cell/sequence.
- `season_count` exactly sequence length.
- No economic/fiscal metric is calculated.

### 2.2 Candidate output fields

`RotationCandidateRecord` includes:

- `candidate_id`
- `cell_id`
- `crop_sequence`
- `season_count`
- `status` (`ELIGIBLE`/`CONDITIONAL`/`INSUFFICIENT_DATA`/`REJECTED`)
- `agronomic_metrics`
- `constraints_checked`
- `constraints_unchecked`
- `rejection_reasons`
- `limitations`
- `evidence`
- `data_quality`
- `candidate_metrics`
- `pareto_candidate`
- `pareto_ready`

### 2.3 Status semantics

| Status | Meaning |
|---|---|
| `REJECTED` | Known constraint violated: suitability `UNSUITABLE` or invalid supplied metrics |
| `INSUFFICIENT_DATA` | Core data missing (duration/suitability) and no known violation |
| `CONDITIONAL` | Core checks pass/no known failure, but calendar is proxy/missing, water ETc missing, or Pareto metrics missing |
| `ELIGIBLE` | Core checks + water ETc + complete Pareto metrics all available and pass |

**Important:** `ELIGIBLE` requires complete Pareto metrics. A candidate without metrics is `CONDITIONAL`, `pareto_ready=False`, and is not passed to final ranking.

### 2.4 Agronomic metrics

`agronomic_metrics` stores:

- per-crop `growing_duration_days`
- per-crop suitability status/missing/reasons
- per-crop calendar status/stage windows/missing
- per-crop seasonal ETc status/value/missing
- total duration where scalar
- season count
- calendar status

No metric is filled with a default.

### 2.5 Data quality/evidence

- `data_quality.parameter_status_counts` counts `observed/standard/proxy/derived/missing`.
- `data_quality.missing_parameters` lists missing parameters.
- `data_quality.proxy_parameters` lists proxy parameters.
- `evidence` lists source IDs used by the sequence’s crop parameters.

---

## 3. Constraint Evaluation Details

### 3.1 Suitability

- Uses `evaluate_suitability()` from the existing module.
- `UNSUITABLE` → `REJECTED` with reason.
- `SUITABLE` → checked.
- `CONDITIONALLY_SUITABLE` → unchecked, `CONDITIONAL`.
- `INSUFFICIENT_DATA` → unchecked, `INSUFFICIENT_DATA`.
- PVRS/BF-EHSI remain context, not suitability thresholds.

### 3.2 Calendar

- Uses `build_calendar()` per crop when `planting_date` is supplied.
- `OK` → checked.
- `PROVISIONAL_PROXY` → unchecked/limitation (not `ELIGIBLE`).
- `INSUFFICIENT_DATA` → unchecked.
- Calendar sequence starts each next crop from the prior harvest date; turnaround time is not modeled (limitation).
- No KATAM window is inferred.

### 3.3 Water ETc

- `seasonal_etc()` is called only when `eto_by_crop_stage` is supplied.
- Missing phase/Kc/ETo → unchecked; no ETc default.
- Seasonal ETc is not treated as irrigation demand.
- Full daily sequence balance is not run in the generator; use `forward_water_balance()` when upstream supplies effective rain/runoff/percolation.

### 3.4 Pareto metrics

- `metrics_by_sequence` is supplied by integration.
- No revenue, cost, profit, AUTP, or fiscal calculation here.
- Missing metrics → `CONDITIONAL`, no `pareto_candidate`.
- Complete valid metrics → candidate built by existing `evaluate_sequence()`.
- Invalid supplied metrics → `REJECTED`.

---

## 4. Pareto Integration

`src/crop_modeling/rotation.py::pareto_optimize_records()`:

- Accepts `RotationCandidateRecord` objects.
- Uses only records with:
  - `status == ELIGIBLE`
  - `pareto_ready == True`
  - non-null `pareto_candidate`
  - non-null `candidate_metrics`
- Converts eligible records to `RotationEvaluation` and calls the existing `pareto_optimize()`.
- `pareto_optimize()` calls Arya’s `solve_pareto_epsilon_constraint()`.
- No second optimizer is implemented.
- If no eligible records → `ParetoResult.status = NO_ELIGIBLE_CANDIDATE`.
- Candidate ID is preserved as `RotationCandidate.scenario_id` via `evaluate_sequence(candidate_id=...)`.

---

## 5. Tests Added

`tests/test_crop_modeling.py` adds:

- `test_generate_candidates_eligible_and_pareto_ready`
- `test_generate_candidates_without_metrics_is_conditional_not_pareto_ready`
- `test_generate_candidates_rejects_known_suitability_failure`
- `test_generate_candidates_deterministic_and_bounded`
- `test_generate_candidates_configurable_season_length`
- `test_actual_registry_does_not_produce_false_eligible_candidates`

Coverage:

- Eligible candidate with complete test-registry inputs.
- No false eligible from incomplete actual registry.
- Missing Pareto metrics → conditional and not Pareto-ready.
- Suitability failure → rejected.
- Deterministic candidate IDs.
- Configurable 2-season sequences.
- No direct duplicate crop in a sequence.
- Candidate ID consistency into Pareto winner.

### Actual test results

| Command | Result |
|---|---|
| `pytest tests/test_crop_modeling.py -q` | **29 passed** |
| Full Python suite | **272 passed, 1 failed** |
| `pnpm test` | **8 passed** |

Existing failure remains `tests/test_demo_geometry.py::test_synthetic_multiresolution_parents_are_valid_and_not_observations` (`KeyError: 'synthetic'`), unrelated to crop modeling.

### Actual registry behavior

`generate_candidates()` on the current registry with 4 crops, 2–3 seasons, max 36 produces **36 candidates, all `INSUFFICIENT_DATA`, all `pareto_ready=False`**.

Why:

- Padi: no phase lengths, no pH/slope/drainage thresholds, no local water/N/price.
- Anjasmoro: phase lengths are proxy, suitability thresholds missing.
- Vima-1: no phase lengths/suitability thresholds.
- Sorgum: no variety/duration/phase lengths.

This is the intended fail-closed behavior, not a generator failure.

---

## 6. Limitations

- Generator does not calculate water balance, N, pest, economics, or fiscal values.
- Generator does not fetch weather or use forecast; strategic generation is independent.
- `ELIGIBLE` requires complete Pareto metrics; current registry cannot produce eligible candidates without integration-supplied metrics.
- Calendar transition uses harvest date without a turn-around/fallow duration; this is a limitation, not a validated agronomic rule.
- Crop phase lengths are missing for 3 of 4 crops.
- `max_candidates` truncates deterministically; no ranking of omitted candidates.
- No H3 spatial validation beyond `cell_id` string.
- Unit tests are software tests, not agronomic validation.

---

## 7. Remaining Data Needs

1. Source phase lengths for Inpari 32, Vima-1, and Sorgum.
2. Source cultivar-specific Kc/Kcb and ETo/water requirements.
3. Source pH/texture/drainage/slope/salinity thresholds.
4. Source N requirement/fixation and pest host/population data.
5. Source local Banyumas yield, prices, production costs, and adoption.
6. Source KATAM Banyumas planting windows.
7. Integration-supplied `CandidateMetrics` from historical/decision modules.
8. Integration-supplied `EnvironmentContext` and `eto_by_crop_stage`.
9. H3 cell validation and weather forecast mapping (separate modules).

---

## 8. Verdict

**Implemented and software-validated:**

- Deterministic, configurable candidate generation.
- Registry-driven crop availability.
- Candidate-level statuses and evidence.
- Suitability/calendar/water constraint aggregation.
- Existing Pareto solver adapter with strict eligibility filtering.
- Stable candidate IDs.

**Not yet production-ready:**

- Most crop parameter values are missing/proxy.
- No eligible candidates on the current registry.
- No economic/fiscal/N/pest calculations in crop modeling.
- No KATAM/local Banyumas data.

**Correct next step:** wire integration-supplied `EnvironmentContext`, `eto_by_crop_stage`, and `CandidateMetrics`; source missing crop parameters; then run eligibility and Pareto tests with real data. Do not lower statuses to `ELIGIBLE` by filling defaults.
