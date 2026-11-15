# CYBER-KATAM Crop Rotation Model Review & Weather-Integration Readiness Audit

**Audit context:** branch `feature/rifaldi-ui`, HEAD `9fc3702`. Audit performed read-only against the actual repository. No source code, formula, coefficient, registry, or data file was modified. No commit, push, merge, or branch switch was performed.

**Important:** the pasted `crop_modeling_pipeline.py` v3.0 is **not present in the actual repository**. No file named `crop_modeling_pipeline.py`, no `data/registry/`, and no `crop_parameter_registry.json` were found. The pasted code is therefore treated as an **uncommitted proposal**, not as an implemented system. A static review of the pasted text is included separately in §2.8.

---

## 1. Repository Implementation Inventory

### 1.1 Repository state

| Item | Result |
|---|---|
| Branch | `feature/rifaldi-ui` |
| HEAD | `9fc3702` |
| Working tree | Only untracked audit documents; no source changes |
| `crop_modeling_pipeline.py` | **Not found** in working tree or Git history |
| `data/registry/` | **Not found** |
| Consensus PDF / 13-page document | **Not found in repository** |
| Existing crop model code | Only scenario matrix, fixed water balance, N/fiscal/Pareto engines |
| Weather/forecast code | **Not found** |
| Backend/API | **Not found**; static frontend only |

### 1.2 Component inventory

| Component | Actual file / function | Status | Evidence |
|---|---|---|---|
| Crop parameter registry | — | **Missing** | No registry file/directory; no crop parameter schema |
| Crop modeling pipeline | — | **Missing** | No `crop_modeling_pipeline.py` or equivalent |
| Crop rotation matrix | `external/ariefs_workresult/crop_rotation_matrix.json`; `task7_agronomy_matrix.py::create_rotation_matrix` lines 11–55 | **Assumption-based; scenario-level** | Three hand-written scenarios; no crop-level parameters; no citations |
| Water balance | `external/aryas_workresult/build_water_balance_banyumas.py` | **Partial; synthetic/fixed** | `BanyumasWaterBalanceSimulator.generate_90day_transition_series` lines 73–187; Kc hardcoded 104–122; root depth 1000 mm line 28; weather from `np.random`/sine 74–100 |
| Nitrogen model (Arya) | `external/aryas_workresult/fiscal_actuarial.py` | **Partial; assumptions** | `ThreeTierNitrogenParams` 16–37; `compute_three_tier_nitrogen_ledger` 85–113 |
| Nitrogen model (Arief) | `external/ariefs_workresult/nitrogen_dynamics.py` | **Partial; assumptions** | `calculate_nitrogen_balance` lines 11–47; not integrated |
| Fiscal/AUTP | `fiscal_actuarial.py` | **Partial; assumptions** | `compute_fiscal_and_autp_clearing` 140–195; constants 39–48 |
| WBC/pest | `fiscal_actuarial.py` | **Partial; uncalibrated coefficients** | `compute_wbc_nymph_survival_rate` 115–138 |
| Pareto optimizer | `fiscal_actuarial.py::solve_pareto_epsilon_constraint` 197–255 | **Implemented core** | Generic multi-objective filter; candidates must be supplied |
| `RotationCandidate` | `fiscal_actuarial.py:51–68` | **Implemented data structure** | Fields only; no generator/evaluator |
| PVRS engine | `external/aryas_workresult/pvrs_engine.py` | **Implemented engine; offline use only** | `PVRSEngine.evaluate_cell` 222–302; `web-app/scripts/compute_pvrs.py` runs offline |
| BF-EHSI engine | `external/aryas_workresult/bf_ehsi_engine.py` | **Implemented engine; not integrated** | `BFEHSIEngine` 64–232; no web/API import; `bf_ehsi` null in data |
| H3/CellContext | `public/demo-grid-levels.json` / GeoJSON only | **Missing as a model interface** | No `CellContext` class or adapter; only static properties |
| Weather forecast | — | **Missing** | No provider, API client, forecast schema, or cache |
| Backend/API | — | **Missing** | `package.json` has only Vite/React; no server |
| Frontend | `web-app/src/main.jsx`, `FieldMap.jsx`, `model.js` | **Static prototype** | Static JSON/GeoJSON fetch; Pareto UI explicitly illustrative |
| Contract | `contracts/grid_cell_contract.schema.json:129–181` | **Partial; rotation fields only** | Seven scenario fields; no crop registry; no optimizer constraints |
| Tests | `tests/`, `web-app/src/model.test.js` | **Partial; no crop-model tests** | 243 Python pass/1 fail; 8 UI tests pass |

### 1.3 Actual test results

| Command | Result | Interpretation |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests -q --tb=no` | **243 passed, 1 failed** | Failure: `tests/test_demo_geometry.py::test_synthetic_multiresolution_parents_are_valid_and_not_observations` (`KeyError: 'synthetic'`); unrelated to crop model |
| `corepack pnpm test` | **8 passed** | Only `web-app/src/model.test.js`; UI-only tests |
| `pnpm test:ui` | Not run in this audit; previous attempt timed out | No backend/weather tests; e2e suite targets old SVG UI |
| Crop model tests | **None** | No tests for registry, Kc/ETc, candidate builder, or weather |

**Passing tests do not validate crop model science.** There is no crop model to test in the repository.

---

## 2. Scientific Formula and Parameter Audit

### 2.1 PVRS

**Actual code:** `external/aryas_workresult/pvrs_engine.py`.

- `PVRSEngine.evaluate_cell()` computes z-scores for ESI, LST, and root-zone moisture; `s_physio`; `s_visual`; sigmoid PVRS; optical lag; Lipschitz error bound; gates; `system_state`.
- Formula is implemented in code, not only comments.
- `web-app/scripts/compute_pvrs.py` runs it **offline** on static indicators, with hardcoded baseline and observation metadata; results are written to `public/demo-grid-levels.json`.
- No crop-specific input or rotation evaluation exists.
- No runtime API.

**Scientific issue:** PVRS is a cell-level root-stress indicator, not a crop growth or rotation model. It can be a context/constraint, but the current system does not feed it into any candidate evaluator.

### 2.2 BF-EHSI

**Actual code:** `external/aryas_workresult/bf_ehsi_engine.py`.

- MBSI formula implemented at lines 74–82.
- `mbsi_to_bare_fraction()` at 84–90.
- BF-EHSI and cumulative `D_i` at 118–232.
- No import in web/API; `physical_indicators.bf_ehsi` is `null` for all 1,000 features.
- The UI BF-EHSI card uses `result.erosion`, a UI simulation, not BF-EHSI.

**Scientific issue:** BF-EHSI cannot be claimed as integrated into rotation evaluation. Its `R_GPM,95th` semantics and `b_it` mapping need reconciliation (see prior audit).

### 2.3 Crop water requirement

**Actual repository water balance:** `build_water_balance_banyumas.py`.

It implements a fixed 90-day balance:

- `ETc = ETo × Kc` at lines 129–132.
- Kc sequences for A/B/C at 104–122.
- Soil profile: root depth 1000 mm, `theta_sat=0.48`, `theta_fc=0.36`, `theta_pwp=0.16`, `K_sat=42 mm/day` at 28–33.
- Runoff is **not** explicitly modeled; bypass/crack flow and percolation are scenario-specific formulas.
- Rainfall/ETo are synthetic (`np.random`/sine); no effective-rainfall separation; no waterlogging state.
- The simulator has no crop-sequence argument; it is fixed to three scenarios.

**Pasted v3.0 water model:** static review only. It does **not** run a daily soil-water balance. It uses:

- `water_demand_mm` for scenario A = `110 × 1.12 × 4.6` (arbitrary 1.12 factor).
- Scenario B = `seasonal_et_measured_mm` for soybean only (323.61 mm).
- Scenario C = `seasonal_et_calculated_mm` for mung bean only (320.72 mm).
- `available_water_mm = 0.75 × seasonal_rain + 165` (arbitrary factors).
- `field_ksat = 42` or `12` (hardcoded; not cell context).

**Critical problem:** seasonal ET is used as irrigation demand. It ignores effective rainfall, soil-water storage, irrigation efficiency, runoff, deep percolation, and the paddy component of the sequence. B and C also ignore paddy and sorghum water demand. This is not a valid crop-sequence water balance.

**Correct relationship:** `ETc = Kc × ETo` is only the atmospheric demand term. Irrigation requirement is a soil-water balance result, not seasonal ET. The implementation must compute daily (or defined-step) `ΔS = P_eff + I + CR − ETc − RO − DP`, with crop-stage Kc and local weather.

### 2.4 Crop suitability

**Actual repository:** no suitability evaluator.

- `ph_optimum_biomass`, `slope_zonation_max_deg`, and `required_ksat_mm_day` appear in the pasted v3.0 registry text, but **no code evaluates them**.
- Actual code has land-cover classes (`src/models/land_cover.py`) but no crop suitability.
- No pH, texture, drainage, soil depth, salinity, water availability, or flooding-risk evaluator.

**Required output:** `SUITABLE`, `CONDITIONALLY_SUITABLE`, `UNSUITABLE`, `INSUFFICIENT_DATA`. The current system can only produce an implicit pass/fail through hardcoded candidate filter values; it cannot evaluate a crop against an H3 cell.

### 2.5 Planting calendar and growth stages

**Actual repository:** no calendar evaluator.

- Water balance has fixed day indices and stage ranges, but no planting date, harvest date, crop overlap, fallow period, or seasonal window.
- `RotationCandidate.non_host_duration_days` is a number; it is not a calendar.
- Pasted v3.0 uses `growing_duration_days` for WBC non-host days and a 110-day factor for paddy water, but does not construct a calendar or check overlap.

**Conclusion:** no candidate can be proven physically feasible within a planning horizon.

### 2.6 Nitrogen

**Arya:** `fiscal_actuarial.py:16–37, 85–113`.
- Three-tier N ledger with fixed soybean parameters (6.25 t/ha biomass, 3.8% N, 76% Ndfa, 42% harvest, 11% denitrification, 7% leaching, 68% mineralization).
- No paddy/mung/sorghum-specific N.

**Arief:** `nitrogen_dynamics.py:11–47`.
- Soybean yield 2.5 t/ha, 1.5 residue ratio, 2.5% N, 75–80% fixation, 40% mineralization.
- Conflicts with Arya’s coefficients; not integrated.

**Pasted v3.0:** static review:
- Uses Ndfa 0.53 and fixed N 67.5 kg/ha as midpoints of tropical ranges; status `proxy`.
- `evaluate_dual_nitrogen_accounting()` uses `crop.get_val("fixed_n_aboveground_kg_ha") or 42.0` and `aftercrop_Direct_n_uptake_kg_ha or 9.5`.
- **For mung bean, these fields are absent, so the code silently uses 42.0 and 9.5.** That is a critical violation of the missing-data policy.
- Policy displacement uses `fixed_n_adj × 0.50`; the 0.50 factor is not sourced in the pasted text.
- `waterlog_penalty = 0.35` after 3 days is arbitrary; the source supports damage, not a 35% factor.
- NUE 0.45 is an assumption; the text only supports typical NUE < 50%.
- No N uptake by paddy/sorghum; no starter-N suppression in the candidate calculation.

**Conclusion:** N accounting is not ready for cross-crop rotation evaluation. The two existing models conflict, and the pasted pipeline introduces unsourced defaults.

### 2.7 WBC/pest

**Actual:** `fiscal_actuarial.py:115–138`.
- `cycles_interrupted = non_host_days / life_cycle_days` (default 28 days).
- `in_field_survival = exp(-3.2 × cycles)`.
- `migration_reinfestation = (1 − adoption_ratio) × 0.42`.
- `effective_survival = min(1, in_field_survival + migration)`.
- No empirical calibration cited in code; 3.2 and 0.42 are assumptions.

**Pasted v3.0:** static review:
- Uses 24.70-day lab cycle (egg 7.20 + five instars 17.50) from Naik et al. 2026; this is a specific source.
- Uses `exp(-2.8 × cycles)`; 2.8 is not derived in the text.
- Uses `recolonization_floor = 0.05 + (1 − adoption_ratio) × 0.35`; 0.35 and the floor structure are assumptions.
- Uses `effective_survival = min(1, max(floor, local_survival + floor × 0.5))`; this is an arbitrary model form.
- Treats `bph_burden_index` as survival; burden semantics are not defined.
- Host status: paddy primary host; soybean/mung/sorghum “putative non-host” is a reasonable status, but not proof of zero local population.
- Migration up to 500 km is used to justify a floor; the source supports migration capacity, not a calibrated local recolonization floor.

**Conclusion:** the pest model is conceptual and uncalibrated; it must not be presented as a validated population model.

### 2.8 Pareto optimizer

**Actual:** `fiscal_actuarial.py:197–255`.

- Implements feasibility filters: income, water, Ksat, erosion.
- Implements non-dominated frontier on N displaced, SOC, BPH.
- Implements epsilon constraints on SOC/BPH and selects maximum N-displaced.
- **Solver core is reusable.**

**Critical limitation:** all candidate fields are externally supplied. The repository has no candidate generator or crop-level evaluator to fill them. In the pasted v3.0:
- SOC (`-0.25`, `0.45`, `0.32`), erosion (`0.68`, `0.19`, `0.22`), and Ksat (`5`, `35`, `30`) are hardcoded.
- Revenue/production cost are partial sequence sums; paddy is allocated 40% in B/C; sorghum is absent; costs are only legume costs.
- `available_water_mm` and field Ksat are scenario assumptions, not H3 context.
- The solver may return a “winner” even when the candidate inputs are scientifically invalid.

### 2.9 Pasted v3.0 static review (not repository implementation)

The pasted code is a substantial proposal, but it is not in the repository and has these scientific/technical issues:

| Issue | Pasted v3.0 implementation | Problem | Severity | Correction / data needed |
|---|---|---|---|---|
| Crop modeling pipeline absent | `crop_modeling_pipeline.py` not found | Cannot be audited/executed against repo; no integration | **Critical** | Commit/import through review; do not claim implemented until present |
| Registry absent | `data/registry/` not found | No actual crop parameter registry; pasted values not persisted | **Critical** | Create registry schema/loader; seed only sourced values |
| Import path | `from fiscal_actuarial import ...` | Actual engine is under `external/aryas_workresult`; no package/`sys.path` guarantee | **High** | Use a stable package/adapter; do not rely on working-directory imports |
| Paddy duration | 110 days (`PURBIATI_2024_INPARI`) | Conflicts with official BRMP description 120 days; time origin/basis must be explicit | **High** | Reconcile observed vs official; store both with source/location |
| Paddy yield | 5.97 t/ha GKG Tegal; 4.82 GKP/4.15 GKG Banyumas | Different locations/bases; cannot be compared or mixed | **High** | Keep product_basis/location; do not average across bases |
| Paddy Kc | 1.05/1.20/1.05 | May be standard system-specific; FAO-56 rice end is 0.90–0.60; no system flag | **High** | Store cultivation system (`flooded`, `AWD`) and source |
| Paddy Ky | `yield_response_ky_reproductive = 1.07` | Pasted note says source reproductive 1.02; 1.07 appears to be transplanting/other phase | **Critical** | Correct phase mapping; use source table exactly |
| Paddy water demand | `110 × 1.12 × 4.6` | Arbitrary 1.12; ignores Kc curve, rainfall, soil water, paddy system | **Critical** | Daily/seasonal balance with Kc stages and local ETo/rain |
| Legume water demand | B/C use soybean/mung seasonal ET only | Ignores paddy, sorghum, effective rainfall, soil storage, irrigation efficiency | **Critical** | Full sequence water balance; do not use ET as irrigation demand |
| Sorghum record | Defined `sorgum_suri3` but not used in `run_evaluation` | Candidate B mentions sorghum but no sorghum yield/water/N/cost; variety data incomplete | **Critical** | Either include full sorghum evaluator or remove from candidate |
| Suitability | pH/slope/Ksat stored but not evaluated | No SUITABLE/CONDITIONAL/UNSUITABLE/INSUFFICIENT_DATA output | **Critical** | Implement suitability rules with approved thresholds |
| Calendar | No planting/harvest/overlap/fallow check | Candidate may not fit the planning horizon | **Critical** | Calendar evaluator and KATAM constraints |
| Root depth | `None` values with scenario 400/600/500 mm | Not used in water balance; defaults hidden in `scenario_assumption_value` | **High** | Use per-crop root depth or abstain; no silent defaults |
| N defaults | `fixed_n ... or 42.0`, `aftercrop ... or 9.5` | Mung bean silently gets soybean-like defaults | **Critical** | Fail closed for missing N parameters |
| N policy factor | `fixed_n_adj × 0.50` | 50% factor not sourced | **High** | Separate conservative credit from policy target; source/decision required |
| WBC decay/floor | 2.8, 0.35, 0.5 arbitrary | No calibration; migration floor not validated | **High** | Empirical calibration or clearly labelled scenario assumption |
| SOC/erosion/Ksat | Hardcoded candidate values | Not model outputs; no H3 context | **Critical** | Compute from SOC model, BF-EHSI, soil context or abstain |
| Revenue/cost | 40% paddy allocation; only legume costs | Incomplete sequence economics; inconsistent with crop_sequence | **Critical** | Full sequence revenue/cost with product basis and all crops |
| Scenario assumption leakage | `get_val()` silently returns scenario value | Provenance not propagated to `RotationCandidate`/output | **High** | Candidate must carry evidence status/assumption flags |
| No forecast | Defaults `seasonal_rain_mm=240`, `eto_daily=4.6` | No weather API; no operational adjustment | **Critical** | Forecast provider + metadata + strategic/operational separation |
| No infeasible reasons | Pareto returns winner only | No rejection reasons/abstention detail | **High** | Return feasible/infeasible/reasons/front |
| No contract output | Returns ad-hoc dict | No `rotation_scenarios`/XAI/fiscal contract | **High** | Contract assembler; validate |

The table above is a **static review of pasted text**, not evidence that the repository currently behaves this way.

---

## 3. Crop Model Readiness Assessment

| Capability | Status | Evidence |
|---|---|---|
| Crop parameter registry | **Missing** | No `data/registry/`; no schema |
| Crop identity/variety registry | **Missing in repo** | Only labels in scenario/UI |
| Growth duration/stage model | **Missing** | No calendar/stage evaluator; fixed water-balance ranges |
| Kc/Kcb by crop and system | **Partial** | FAO generic values exist in audit docs; repo has fixed scenario Kc only |
| Root depth | **Partial/missing** | Single 1000 mm profile; no per-crop use |
| Crop water requirement | **Partial** | `ETc=ETo×Kc` exists in fixed water balance; no general calculator/sequence |
| Effective rainfall/irrigation/soil water | **Partial** | Fixed simulator; no effective rainfall; no sequence input |
| Crop suitability | **Missing** | No pH/texture/drainage/slope/salinity evaluator |
| Planting calendar | **Missing** | No dates/overlap/fallow/KATAM |
| Nitrogen | **Partial** | Two soybean-oriented models; conflict; no crop-specific N |
| Pest/WBC | **Partial** | One survival formula; coefficients uncalibrated |
| Rotation candidate generation | **Missing** | Hardcoded demo candidates only |
| Pareto optimizer | **Implemented core** | Solver exists; inputs not model-derived |
| PVRS integration | **Partial/precomputed** | Offline `compute_pvrs.py`; no runtime candidate input |
| BF-EHSI integration | **Not integrated** | `bf_ehsi` null; no import/API |
| H3 CellContext | **Missing** | Static GeoJSON properties only |
| Weather forecast | **Missing** | No provider/client/schema/cache |
| Backend/API | **Missing** | Static frontend only |
| Frontend | **Static prototype** | UI labels/Pareto illustrative |
| Contracts | **Partial** | Rotation fields only; no crop registry/constraints |
| Tests | **Partial** | No crop model tests; 243/1 Python, 8 UI |

**Readiness verdict:** the actual repository is a **prototype/fragment set**, not a crop rotation recommendation system.

---

## 4. Hardcoded / Proxy / Missing Parameter List

### 4.1 Hardcoded or demo values

| Item | Actual evidence | Problem |
|---|---|---|
| Scenario A/B/C candidates | `fiscal_actuarial.py:334–374` | Water, N, SOC, BPH, revenue, cost, Ksat, erosion are fixed demo values |
| Water balance Kc | `build_water_balance_banyumas.py:104–122` | Scenario-level, not crop-level |
| Root depth | same, line 28 | One shared 1000 mm value |
| Soil hydraulics | same, lines 29–33 | Assumed constants, not H3 soil |
| Weather | same, lines 74–100 | Synthetic random/sine |
| Fiscal constants | `fiscal_actuarial.py:42–48` | Area, subsidy, costs, AUTP probability assumed |
| WBC coefficients | `fiscal_actuarial.py:115–138` | 3.2/0.42 not calibrated |
| UI scores | `web-app/src/model.js:6, 16, 26` | Arbitrary display scores |
| Pasted water demand | v3.0 text | 1.12 factor, seasonal ET, 0.75/165 water supply |
| Pasted SOC/erosion/Ksat | v3.0 text | Hardcoded candidate values |

### 4.2 Proxy values

| Proxy | Actual evidence | Use |
|---|---|---|
| Anjasmoro Kc from SoyTech 815 RR | pasted v3.0 text | Proxy, not Anjasmoro measurement |
| Mung bean Kc from Patil/Sosiawan | pasted v3.0 text | Proxy; Vima-1 not measured |
| Sorghum Kc from Melkassa | pasted v3.0 text | Proxy; Suri 3 not measured |
| WBC lab cycle 24.70 days | pasted v3.0 text | Lab source; field applicability unverified |
| Tropical Ndfa/fixed N/aftercrop N | pasted v3.0 text | Ranges; midpoints are derived/proxy |
| Economies | pasted v3.0 text | Scenario assumptions, not local data |

### 4.3 Missing

- Local Banyumas crop prices and production costs.
- Local Banyumas yield trials for Inpari 32, Anjasmoro, Vima-1, Suri 3.
- Cultivar-specific Kc/Kcb and stage lengths.
- Per-crop root depth and soil suitability.
- pH/texture/drainage/slope/salinity rules with approved thresholds.
- KATAM Banyumas planting calendar.
- Crop-specific N requirement and N fixation for mung bean/sorghum.
- Pest host status beyond paddy WBC; population/migration calibration.
- Weather API/forecast metadata and operational thresholds.
- Contract fields for candidate constraints and provenance.

---

## 5. PVRS/BF-EHSI Integration Assessment

### Actual flow

```text
public/banyumas_h3_indicators_v2.geojson
  -> web-app/scripts/compute_pvrs.py (offline PVRSEngine)
  -> public/demo-grid-levels.json
  -> web-app/src/FieldMap.jsx (fetch static)
  -> UI cards

BF-EHSI engine
  -> no import in web/API
  -> physical_indicators.bf_ehsi = null
  -> UI BF-EHSI card uses result.erosion (UI simulation)
```

- **PVRS** is calculated offline, not at runtime. `compute_pvrs.py` uses hardcoded baseline/observation metadata and writes static PVRS.
- **BF-EHSI** is not integrated. It is not calculated by the web/API and is not a candidate input.
- **No H3 CellContext** exists. The UI receives static properties; no `CellContextAdapter` feeds a crop evaluator.
- **No timestamps/resolution compatibility layer**; static data has no observation timestamp/QA.
- **Historical vs current** is not distinguished in the crop model.

**Conclusion:** PVRS/BF-EHSI appear in the UI as indicators, not as inputs to a crop rotation evaluator.

---

## 6. Rotation Candidate Generation Assessment

**Actual repository:** no candidate generator.

- `RotationCandidate` is a dataclass; `solve_pareto_epsilon_constraint` filters supplied candidates.
- The only candidates are `fiscal_actuarial.py:334–374` demo values.
- No code enumerates crop sequences, checks suitability, builds calendars, or evaluates sequence water/N/pest.
- No output of infeasible candidates/rejection reasons.
- `public/banyumas_h3_indicators_v2.geojson` has `rotation_scenarios: []` for all 1,000 features; `fiscal_metrics` null; `xai_decision_block` null.
- `contracts/grid_cell_contract.schema.json` rotation fields are not populated by a model.

**Pasted v3.0** is also hardcoded A/B/C, not generated:
- A: Padi-Bera
- B: Padi-Anjasmoro-Sorghum (but sorghum not evaluated)
- C: Padi-Vima-1
- No enumeration, feasibility, calendar, or sequence water balance.

**Conclusion:** candidate generation is **not implemented**.

---

## 7. Pareto Optimizer Integration Assessment

**Reusable core:** `solve_pareto_epsilon_constraint()`.

- Correctly filters feasibility and identifies non-dominated candidates given valid inputs.
- It is not a crop model; it cannot validate agronomy.
- Actual inputs are hardcoded demo values.
- Contract gap: `grid_cell_contract.schema.json` rotation fields omit `non_host_duration_days`, `required_ksat_mm_day`, `predicted_erosion_di`, gross revenue/cost, provenance/evidence status.
- No `pareto_front`/infeasible-reason output in a contract/API.
- No candidate provenance or abstention reason.

**Recommendation:** keep solver; build a candidate builder/evaluator that supplies validated fields; extend contract through governance.

---

## 8. Weather API Integration Design

### 8.1 Two horizons

**A. Strategic crop rotation evaluation** (weeks–season):

- Historical/spatial indicators.
- Crop registry, suitability, calendar.
- Seasonal/planning water balance.
- N/pest/economic constraints.
- Pareto optimization.
- Output: rotation alternatives valid for the land.

**B. Operational 3-day adjustment** (hours–days):

- Latest forecast.
- Short-term rainfall/water balance.
- Temporary waterlogging/deficit risk.
- Delay planting/field operations if needed.
- Update confidence/warnings.
- **Do not automatically invalidate a long-term rotation.**

### 8.2 Provider-agnostic forecast contract

No provider is selected in the repository. Design an adapter:

```text
ForecastProvider.fetch(lat, lon, horizon_days=3) -> ForecastBundle
```

`ForecastBundle` must include:

- provider name/version;
- issue time;
- retrieval time;
- valid start/end;
- horizon (days);
- location (lat/lon/H3);
- units per variable;
- variables present: precipitation, temperature (min/max/mean), relative humidity, wind speed, solar radiation, ETo (provided or derived);
- missing-variable indicators;
- quality/uncertainty metadata (ensemble/probability if available);
- raw/cached reference.

**Do not assume all variables exist.** If ETo is not provided, derive only with an approved method and required variables; otherwise mark ETo unavailable.

### 8.3 Freshness and uncertainty

- `forecast_age = retrieval_time − issue_time`; `validity = now vs valid_end`.
- Stale if past valid end or beyond agreed TTL; do not reuse silently.
- Record forecast version in every recommendation.
- If stale/unavailable: preserve strategic result; mark operational status `STALE`, `UNAVAILABLE`, or `REQUIRES_VERIFICATION`.
- Forecast uncertainty: use provider probabilities/ensemble if available; otherwise mark `uncertainty_unknown`; no false precision.

### 8.4 Change policy (avoid flip-flop)

- Store `previous_operational_status`, `previous_forecast_ref`, and change reason.
- Recalculate operational risk on refresh.
- Update status only when an approved threshold/constraint changes; otherwise keep prior status with `NO_MEANINGFUL_CHANGE`.
- Use hysteresis/minimum-duration rules agreed by the team; do not invent thresholds.
- Distinguish `strategic_result` (unchanged) from `operational_adjustment` (may change).

### 8.5 H3 mapping

- Map forecast grid/station to H3 cell; record native resolution and distance.
- Do not claim cell-specific weather when the provider resolution is coarser.
- If multiple cells share one forecast grid, state shared observation/support.
- Store H3 mapping method and uncertainty.

### 8.6 Example metadata

```json
{
  "provider": "provider_name",
  "provider_version": "v1",
  "issue_time": "2026-11-15T00:00:00Z",
  "retrieval_time": "2026-11-15T01:10:00Z",
  "valid_start": "2026-11-15T00:00:00Z",
  "valid_end": "2026-11-18T00:00:00Z",
  "horizon_days": 3,
  "location": {"lat": -7.45, "lon": 109.17, "h3": "..."},
  "units": {"precipitation": "mm", "temperature": "degC", "wind_speed": "m/s", "solar_radiation": "MJ/m2/day"},
  "variables_present": ["precipitation", "temperature", "relative_humidity", "wind_speed"],
  "variables_missing": ["solar_radiation", "ETo"],
  "uncertainty": "unknown",
  "stale": false
}
```

---

## 9. Model Validation and Testing Plan

### 9.1 Unit tests

- Kc/ETc by stage; correct time origin (DAS/DAP/DAT).
- Daily water balance: effective rainfall, irrigation, ETc, runoff, deep percolation, waterlogging.
- Crop duration/stage transitions; planting/harvest/overlap/fallow.
- Suitability: suitable/conditional/unsuitable/insufficient data.
- N balance: fixation, Ndfa, grain export, residue, mineralization, leaching, denitrification, subsequent uptake.
- Pest: host status, cycle, non-host duration, migration/floor; no zero reset.
- Candidate feasibility and rejection reasons.
- Pareto filtering/front/epsilon.
- Forecast parsing/unit normalization/freshness.

### 9.2 Integration tests

- H3 context → suitability.
- Registry → water model.
- Crop model → candidate builder.
- Candidate → Pareto.
- Forecast → operational adjustment.
- Full recommendation response with provenance.

### 9.3 Scenario tests

1. Normal weather, suitable soil.
2. High rainfall forecast + waterlogging risk.
3. Low rainfall forecast + water deficit.
4. Missing soil properties.
5. Missing crop parameters.
6. Proxy-only parameters.
7. Stale/unavailable weather API.
8. Forecast changes significantly between updates.
9. Two H3 cells with different soil/moisture.
10. No feasible candidate → abstention.

**Do not use synthetic fixtures as evidence of real-world accuracy.**

### 9.4 Actual current test status

- Python: **243 passed, 1 failed** (geometry fixture, not crop model).
- UI: **8 passed** (UI-only).
- No crop model/weather/API tests.
- `test:ui` not run; previous attempt timed out; e2e suite is stale.

---

## 10. Prioritized Implementation Roadmap

### Phase 0 — Freeze claims and provenance
- Do not claim v3.0/registry is implemented until committed and reviewed.
- Separate observed/standard/proxy/derived/missing in all outputs.
- No silent defaults.

### Phase 1 — Registry and CellContext foundation
- Implement `crop_parameter_registry.schema.json`, `sources.json`, `units.json`, per-crop JSON, loader.
- Implement `CellContextAdapter` for H3/PVRS/BF-EHSI/soil/weather.
- Seed only sourced values; null otherwise.

### Phase 2 — Suitability and calendar
- Implement `CropSuitabilityEvaluator` with approved pH/texture/drainage/slope/salinity rules.
- Implement `PlantingCalendarEvaluator` with KATAM/window constraints.
- Return `SUITABLE/CONDITIONALLY_SUITABLE/UNSUITABLE/INSUFFICIENT_DATA`.

### Phase 3 — Water and N
- Implement daily/step water balance for a full sequence; reuse/parameterize `BanyumasWaterBalanceSimulator`.
- Correct paddy Kc/system, effective rainfall, irrigation, soil storage, runoff, percolation, waterlogging.
- Resolve N model conflict; no mungbean defaults; use conservative aftercrop N credit vs policy target separately.

### Phase 4 — Candidate generator and Pareto
- Generate candidates from registry; reject with reasons; fill `RotationCandidate` only from model outputs.
- Reuse `solve_pareto_epsilon_constraint`.
- Output feasible/infeasible/front/recommended/abstain.

### Phase 5 — API/UI/contract
- Add backend/API; contract fields for provenance/constraints.
- UI displays actual results, evidence status, missing-data warnings.
- No static “verified” labels.

### Phase 6 — Weather operational layer
- Add provider adapter, forecast bundle, cache/freshness.
- Separate strategic rotation and operational adjustment.
- No automatic invalidation; no flip-flop.

### Phase 7 — Validation
- Unit/integration/scenario tests; field validation; benchmark with real data.
- Do not claim production readiness from synthetic tests.

### Smallest scientifically defensible MVP

For one pilot H3 cell/field and **two crops** (e.g., Padi Inpari 32 + one legume with adequate data):

1. Registry with official/FAO values and explicit nulls.
2. Suitability only if soil data available; otherwise abstain.
3. Calendar with KATAM/approved windows.
4. Daily water balance using local/approved ETo and rainfall.
5. Conservative N credit; no policy displacement unless explicitly scenario mode.
6. Candidate generation and Pareto solver on valid fields.
7. Operational 3-day forecast as a separate warning layer.
8. Contract/API output with provenance and abstention.

Do not start with all four crops if the data are incomplete.

---

## 11. Findings Register

### Critical

| ID | File/function | Current | Problem | Recommendation | New data? |
|---|---|---|---|---|---|
| C-01 | `crop_modeling_pipeline.py` | Not found | User-referenced v3.0 is not in repository; cannot be audited/executed as implementation | Commit through review or treat as proposal only | No |
| C-02 | `data/registry/` | Missing | No actual crop parameter registry | Create schema/loader; seed only sourced values | Yes |
| C-03 | `external/aryas_workresult/build_water_balance_banyumas.py` | Fixed 90-day simulator | Cannot evaluate a full arbitrary crop sequence; synthetic weather; no effective rainfall | Parameterize or build a sequence water-balance adapter; do not duplicate formulas | Yes |
| C-04 | Pasted v3.0 `run_evaluation()` | Seasonal ET used as water demand | Ignores paddy/sorghum, effective rainfall, soil storage, irrigation efficiency | Implement daily/seasonal balance; use ETc only as demand term | Yes |
| C-05 | Pasted v3.0 candidate builder | A/B/C hardcoded | No candidate generation/suitability/calendar | Build generator with rejection reasons | Yes |
| C-06 | `fiscal_actuarial.py:334–374` | Demo candidates | SOC/erosion/Ksat/water/economics hardcoded | Compute from models or abstain | Yes |
| C-07 | Pasted v3.0 N evaluator | `or 42.0`, `or 9.5`, 0.50 policy factor | Silent defaults for mung bean; unsourced policy factor | Fail closed; separate conservative N credit and policy scenario | Yes |
| C-08 | `external/aryas_workresult/fiscal_actuarial.py:115–138` | WBC survival formula | 3.2/0.42 coefficients uncalibrated | Calibrate or label scenario assumption; no population claim | Yes |
| C-09 | No weather/API | No forecast | No operational 3-day adjustment | Build provider-agnostic forecast adapter with metadata/freshness | Yes |
| C-10 | `web-app/src/main.jsx:195–196, 1635–1636` | “No real forecast/API” | UI itself confirms no weather/API | Do not claim weather integration; implement/validate later | No |

### High

| ID | File/function | Current | Problem | Recommendation | New data? |
|---|---|---|---|---|---|
| H-01 | `public/banyumas_h3_indicators_v2.geojson` | `rotation_scenarios: []`, fiscal null, XAI null | No rotation output reaches contract | Populate via evaluator; validate contract | Yes |
| H-02 | `contracts/grid_cell_contract.schema.json:129–181` | Seven scenario fields | Missing non-host, Ksat, erosion, revenue/cost, provenance | Extend via contract governance | Yes |
| H-03 | `web-app/scripts/compute_pvrs.py` | Offline precomputed PVRS | No runtime/H3/crop integration; hardcoded baseline/obs | CellContext adapter; runtime or explicit precomputed status | Yes |
| H-04 | `bf_ehsi_engine.py` / data | Engine exists; `bf_ehsi` null | Not integrated into candidates | Integrate BF-EHSI as constraint/metric or remove claim | Yes |
| H-05 | No `CellContext` | GeoJSON static only | Crop evaluator cannot consume H3 conditions | Add interface; no duplicate engines | Yes |
| H-06 | Pasted v3.0 paddy Ky | 1.07 labelled reproductive | Source note says 1.02 reproductive; phase mapping wrong | Correct mapping; source table | No |
| H-07 | Pasted v3.0 candidate economics | 40% paddy allocation; legume-only costs; no sorghum | Incomplete sequence economics | Full sequence revenue/cost with product basis | Yes |
| H-08 | Pasted v3.0 suitability | pH/slope stored but unused | No suitability output | Implement evaluator with approved thresholds | Yes |
| H-09 | Pasted v3.0 calendar | Duration only | No planting/harvest/overlap/fallow | Calendar evaluator; KATAM | Yes |
| H-10 | Actual tests | 243 pass/1 fail; 8 UI | No crop/weather tests | Add tests from §9; fix geometry regression | No |

### Medium

| ID | File/function | Current | Problem | Recommendation | New data? |
|---|---|---|---|---|---|
| M-01 | `web-app/src/model.js` | Static strategies/Pareto | UI comparison is illustrative | Label explicitly; bind to engine later | No |
| M-02 | `main.jsx:1760` | “Illustrative Pareto” | Not an optimization result | Keep label until solver output wired | No |
| M-03 | `fiscal_actuarial.py:257–327` | Contract builder hardcodes indicators | Not reusable for real data | Move assembly to adapter; inputs required | Yes |
| M-04 | Docs/registry | No Consensus PDF in repo | Citations in pasted code cannot be independently checked | Add source PDF/DOIs/evidence registry | Yes |
| M-05 | Weather design | No provider selected | Variables/units unknown | Provider-agnostic adapter; document capability | Yes |

### Low

| ID | File/function | Current | Problem | Recommendation | New data? |
|---|---|---|---|---|---|
| L-01 | `tests/test_demo_geometry.py:43` | `KeyError: synthetic` | Fixture regression | Update test/data contract | No |
| L-02 | UI text | “NASA DATA RIIL” | Conflicts with static/provenance | Unify labels; show evidence status | No |

---

## 12. Final Verdict

### Is the current implementation only a prototype?

**Yes.** The actual repository has:
- physics/Pareto/N/fiscal engines and a fixed water-balance simulator;
- static UI and precomputed PVRS;
- no crop modeling pipeline v3.0, no crop registry, no suitability/calendar evaluator, no candidate generator, no weather/API.

The pasted v3.0 is an uncommitted proposal, not the repository implementation.

### Which components can be reused?

- `PVRSEngine` and `BFEHSIEngine` as cell-level physics/reference engines, after integration.
- `BanyumasWaterBalanceSimulator` as a reference/parameterizable water-balance component.
- `CyberKatamFiscalActuarialEngine` N/fiscal/AUTP methods (with corrected data).
- `RotationCandidate` and `solve_pareto_epsilon_constraint()` as the optimizer core.
- `src/contracts` validator and UI shell.
- `public` H3/indicator data as static context, with provenance caveats.

### Which formulas must be corrected?

- Pasted v3.0 water demand: seasonal ET used as irrigation demand; paddy/sorghum omitted; arbitrary factors.
- Pasted v3.0 paddy Ky phase mapping (1.07 vs 1.02).
- Pasted v3.0 N defaults (42/9.5) and 50% policy factor.
- WBC decay/floor coefficients and semantics.
- Candidate economics/SOC/erosion/Ksat: must come from models, not constants.
- Paddy Kc/system and root depth; crop-specific Kc/phase.
- Contract/optimizer field mapping.

### What is missing to produce valid crop rotation recommendations?

- Actual crop registry and source/provenance.
- H3 CellContext adapter.
- Suitability, calendar, daily water balance, crop-specific N/pest, local yield/economics.
- Candidate generator with feasible/infeasible reasons.
- Runtime PVRS/BF-EHSI consumption.
- Weather forecast adapter and operational adjustment layer.
- API/contract/UI integration.
- Validation with real data.

### Smallest scientifically defensible MVP

One pilot H3 cell/field, **two crops** with adequate data (e.g., Padi Inpari 32 + one legume), using:

- registry with official/FAO values and explicit nulls;
- suitability only when soil data exist;
- KATAM/approved calendar;
- daily water balance with local ETo/rain;
- conservative N credit;
- candidate generator + existing Pareto solver;
- 3-day forecast as a separate operational warning;
- abstention on missing data.

**Do not claim production readiness. Do not treat generic/proxy values as Banyumas measurements. Do not use synthetic tests as field validation.**

---

## 13. Audit Evidence Limitations

- The 13-page Consensus PDF is not present in the repository; pasted citations/values are not independently verifiable from the repo.
- Some official PDF pages could not be machine-parsed in the audit environment; their values are marked with source limitations in the agronomic audit.
- No real Banyumas crop trial, KATAM export, weather provider, or backend API exists in the repository.
- The pasted v3.0 code was not executed or imported; only statically reviewed. Running it would write `data/registry/crop_parameter_registry.json` and was not done because this is audit-only and the file is not part of the repository.
