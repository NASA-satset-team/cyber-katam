# AI Core readiness assessment

Date: 2026-11-14
Scope: can each planned AI Core module start with the files that exist **today**?

Legend:

- **Begin now** — implementation can start with synthetic/provisional inputs.
- **Begin with caveats** — skeleton and pure logic can start; acceptance is blocked.
- **Blocked** — a required input or decision does not exist yet.

> Real NASA data is **not required** for unit tests of deterministic logic. It is
> required before any module may claim field validity or be demonstrated as an
> operational recommendation.

---

## 0. Summary

| Module | Begin? | Real NASA needed before *testing*? | Primary blocker |
|---|---|---|---|
| `contract_validator.py` | Begin with caveats | No (schema tests) | No ratified JSON Schema |
| `synthetic_h3_generator.py` | **Begin now** | No | Must label output synthetic |
| `bare_soil_detector.py` | Begin with caveats | No for unit tests; yes for acceptance | No HLS reflectance time series |
| `pareto_rotation_optimizer.py` | Begin now | No | Agronomic/economic parameters unvalidated |
| `xai_explanation_generator.py` | Begin with caveats | No for templating; yes for content validity | No real indicator values |
| `uncertainty_engine.py` | Begin now | No for math; yes for calibration | Synthetic baseline sigmas |
| `agrophysics_fiscal_integration.py` | Begin with caveats | Yes for end-to-end | Contract unratified; hardcoded indicators |
| `governed_abstention_controller.py` | Begin now | No for logic; yes for acceptance | QC fields absent from dataset |
| `scenario_stress_testing.py` | Begin with caveats | No for harness; yes for valid benchmark | No real pipeline or timings |
| `test_inferencing_suite.py` | **Begin now** | No | Fixtures must be labelled synthetic |

**Recommended start order:** 2 → 1 → 10 (harness) → 6 → 8 → 3 → 4 → 7 → 5 → 9.
Scenario stress testing is last because it needs a real pipeline to measure.

---

## 1. `contract_validator.py`

| Question | Assessment |
|---|---|
| Available inputs | `jsonschema` 4.23.0; contract field reference in `grid_cell_contract_sample.json`; governance rules in `docs/contract_governance.md`; `src/contracts/` package |
| Missing inputs | A ratified JSON Schema file; enum registry; units table; valid/invalid example fixtures |
| Reuse | Governance document and sample field names only. The sample is **not parseable JSON** (UTF-16 console log), so it cannot be loaded directly |
| Begin now? | **Yes, with caveats.** Build a validator API plus a *provisional* schema derived from the sample. Mark it provisional and do not let downstream code treat it as ratified |
| Real NASA required? | No. Tests can run entirely on fixtures |
| Risks | Encoding a wrong provisional schema into tests creates false confidence. Keep schema version explicit and fail closed on unknown fields |

Deliverable direction: `validate_contract(payload) -> ValidationResult` with
structural errors, unit checks, enum checks, and unknown-field policy. Add
`contracts/grid_cell_contract.v1.provisional.schema.json` only as a proposal, not
as the official contract.

---

## 2. `synthetic_h3_generator.py`

| Question | Assessment |
|---|---|
| Available inputs | `h3` 4.1.2; 1,000-cell GeoJSON; `task10_precomputed_geojson.py`; Banyumas bbox |
| Missing inputs | A real paddy mask if the output is meant to represent fields; a seed policy; a documented spatial extent |
| Reuse | `h3.latlng_to_cell`, `h3.grid_disk`, `h3.cell_to_boundary`; Arief's GeoJSON as a shape reference |
| Begin now? | **Yes, immediately** |
| Real NASA required? | No |
| Requirements | Every output must carry `synthetic: true`, a generator version, a seed, and a warning. Never write `land_cover = "Paddy Field"` unless a mask actually proves it. Support `grid_disk` demo mode **and** polygon/mask intersection mode. Preserve deterministic output for tests |
| Tests | Cell count, unique indexes, all res 9, closed rings, deterministic seed, explicit synthetic metadata |

This module is the correct place to replace KI-01/KI-03/KI-04 with an honest,
reproducible fixture generator. Do not reuse Arief's random generator as-is.

---

## 3. `bare_soil_detector.py`

| Question | Assessment |
|---|---|
| Available inputs | Arya's `bf_ehsi_engine.py`: `compute_mbsi()`, `mbsi_to_bare_fraction()`, thresholds; synthetic `MBSI` scalar per cell |
| Missing inputs | HLS L30/S30 surface reflectance (red, NIR, SWIR1, SWIR2) time series; `Fmask` QA; valid-pixel counts; real sensor-specific band mapping |
| Reuse | **Import** `BFEHSIEngine.compute_mbsi` and `mbsi_to_bare_fraction`; do not re-implement |
| Begin now? | **Yes, with caveats.** Build the detector around injected reflectance; test with synthetic spectra; do not claim field detection |
| Real NASA required? | No for unit tests; yes before any bare-field claim |
| Risks | MBSI→bare fraction is a linear assumption needing validation; a single MBSI scalar cannot support temporal bare-soil detection; Sentinel-2 values are not HLS values |

Interface direction: accept a reflectance record + QA, return MBSI, bare fraction,
valid-pixel count, and `data_status`. Fail closed when QA is missing.

---

## 4. `pareto_rotation_optimizer.py`

| Question | Assessment |
|---|---|
| Available inputs | Arya's `solve_pareto_epsilon_constraint()` and `RotationCandidate`; 3 demo candidates; `crop_rotation_matrix.json` with 3 scenarios |
| Missing inputs | Validated water demand, yield, revenue, production cost, SOC change, K_sat requirement, erosion D_i, non-host duration, and BPH burden per scenario |
| Reuse | **Import/wrap** Arya's solver and dataclass. Do not duplicate the dominance or ε-constraint logic |
| Begin now? | **Yes.** The solver is deterministic and already tested by its demo |
| Real NASA required? | No. Agronomic and economic validation is the real blocker, not NASA |
| Risks | Arief's JSON uses a different schema (`water_requirement_mm_per_season`, no revenue/cost/K_sat/D_i). It cannot be fed to Arya's candidate directly. A translation layer must be explicit and must not invent missing economics |
| Tests | Dominance, infeasible candidate filtering, ε-qualification, tie-breaking, empty feasible set |

Deliverable direction: an adapter that either loads a *complete* candidate file or
returns `insufficient_parameters` with the missing field list. No default revenues.

---

## 5. `xai_explanation_generator.py`

| Question | Assessment |
|---|---|
| Available inputs | `xai_decision_block` shape and hardcoded text in Arya's contract builder; contract fields; indicator names |
| Missing inputs | Real computed indicators, evidence timestamps, baseline values, uncertainty, and rule/feature attributions |
| Reuse | The four-part structure: `why_suggested`, `multi_benefits`, `information_gaps`, `local_risks_and_gates` |
| Begin now? | **Yes, with caveats.** Build a deterministic template/rule engine driven by a context object |
| Real NASA required? | No for template tests; yes for meaningful explanation acceptance |
| Risks | The current text contains claims that are not derived from data (e.g. "saves 60% irrigation", "163 kg urea", "9 days before yellowing"). Generating such text from hardcoded numbers would be fabrication. Every sentence must cite a field or be marked as an assumption |
| Tests | No numeric claim without a source field; missing fields produce an explicit information gap, not prose |

---

## 6. `uncertainty_engine.py`

| Question | Assessment |
|---|---|
| Available inputs | Arya's `LipschitzErrorParameters` (`L_g=1.15`, `delta_sensor=0.022`, `delta_support=0.031`, `delta_model=0.015`, `tau=120 h`, tolerance `0.120`); `DecadalClimatologyBaseline` sigmas; PVRS error-bound formula |
| Missing inputs | Real per-cell climatology μ/σ; observation age, cloud fraction, sensor zenith, QA; validated support-error term |
| Reuse | **Import** the parameters and the error-bound logic from `pvrs_engine.py`; do not rewrite the formula |
| Begin now? | **Yes.** The arithmetic is deterministic and testable |
| Real NASA required? | No for math tests; yes for calibration and confidence claims |
| Risks | Current sigmas come from synthetic noise. A confidence percentage derived from them is not meaningful. Clearly separate *propagated numerical uncertainty* from *calibrated real-world uncertainty* |
| Tests | Bounds monotonic in age/cloud/support error; clipping; zero/negative sigma rejection |

---

## 7. `agrophysics_fiscal_integration.py`

| Question | Assessment |
|---|---|
| Available inputs | Arya's `CyberKatamFiscalActuarialEngine`, `build_grid_cell_contract_json()`, N ledger, fiscal clearing, PVRS/BF-EHSI output dataclasses; crop matrix; nitrogen output |
| Missing inputs | Ratified contract schema; real physical indicators; validated fiscal/agronomic constants; a single source of truth for nitrogen coefficients |
| Reuse | **Wrap** Arya's engines. The integration layer should gather outputs and call the contract builder; it must not duplicate ledger or clearing formulas |
| Begin now? | **Yes, with caveats.** Wiring and schema mapping can start against a provisional contract |
| Real NASA required? | Yes for end-to-end acceptance |
| Risks | `build_grid_cell_contract_json()` hardcodes PVRS, BF-EHSI, SMAP, ESI, LST anomaly, BSI, NDVI, rain, slope, and parent H3 (KI-06). Integration must supply real values or refuse to emit. Arief's N model disagrees with Arya's three-tier ledger (KI-10); pick one ratified model |
| Tests | No hardcoded physical value may reach the contract; every field traces to an input object; absent input → abstain/error |

Recommended refactor (in a later PR, with Arya): move contract assembly out of the
fiscal engine into this integration module, so fiscal math and contract shape are
separately testable.

---

## 8. `governed_abstention_controller.py`

| Question | Assessment |
|---|---|
| Available inputs | PVRS `gate_1_pass` / `gate_2_pass` logic and `system_state` values; thresholds (age ≤ 72 h, cloud ≤ 0.65, zenith ≤ 55°, error ≤ 0.120); waterlogging conflict rule |
| Missing inputs | Observation metadata in the dataset (age, cloud, zenith, waterlogging); QA flags; a policy for missing inputs |
| Reuse | **Extract/import** the gate predicates and constants from `pvrs_engine.py`; centralise them rather than duplicating |
| Begin now? | **Yes.** This is deterministic policy logic |
| Real NASA required? | No for logic tests; yes for acceptance |
| Risks | The current H3 GeoJSON has none of the gate inputs. The controller must default to **abstain**, not pass, when metadata is missing. Gate 3/4 referenced in Arya's text are not implemented anywhere |
| Tests | Missing metadata → abstain; each gate failing independently; conflict rule; state/advisory code consistency |

Deliverable direction: one policy object with explicit gate reasons returned to the
XAI layer, so an abstention is explainable.

---

## 9. `scenario_stress_testing.py`

| Question | Assessment |
|---|---|
| Available inputs | 3 rotation scenarios (two inconsistent parameter sets); Arya's water-balance simulator; synthetic benchmark JSON; Pareto solver |
| Missing inputs | A real pipeline to measure; real forcing data; agreed stress ranges; performance SLOs |
| Reuse | Water-balance equations and Pareto solver; **not** the `time.sleep()` benchmark |
| Begin now? | **Yes, with caveats.** Build a scenario runner over synthetic forcing and measure real wall-clock time of real functions |
| Real NASA required? | No for the harness; yes for a meaningful benchmark |
| Risks | The existing benchmark is fake (KI-08). Do not report PASS/FAIL based on sleeps. Separate functional stress tests (parameter extremes) from performance tests (measured runtime) |
| Tests | Scenario matrix expansion, deterministic outputs, runtime measured around real calls, no `sleep` |

---

## 10. `test_inferencing_suite.py`

| Question | Assessment |
|---|---|
| Available inputs | `pytest` 8.3.4; `jsonschema`; `h3`; synthetic GeoJSON/Parquet; Arya's runnable engines |
| Missing inputs | Real-data fixtures for acceptance tests; ratified contract examples; expected-value fixtures from a verified run |
| Reuse | All engine demos can become golden-value tests after pinning seeds/inputs |
| Begin now? | **Yes, immediately** |
| Real NASA required? | No. Unit/integration tests must run offline |
| Risks | Tests that assert on unseeded random data will flake. Tests that treat synthetic values as observations would institutionalise the current problem |

Suggested layers:

1. **Contract tests** — schema validity, required fields, units.
2. **Geometry tests** — H3 res 9, uniqueness, ring closure, deterministic seed.
3. **Physics wrapper tests** — import Arya's engine, assert documented invariants
   (e.g. PVRS ∈ [0,1], bare fraction ∈ [0,1], Pareto filter correctness).
4. **Abstention tests** — missing metadata fails closed.
5. **Integration tests** — one cell end-to-end with synthetic inputs, contract
   validates, synthetic flag present.
6. **Acceptance tests (later)** — real exported NASA sample, marked `@pytest.mark.real_data`
   and skipped by default.

---

## 11. Reuse map — do not duplicate Arya's formulas

| AI Core need | Import from | Do not re-implement |
|---|---|---|
| PVRS score, z-scores, optical lag | `external/aryas_workresult/pvrs_engine.py` | `PVRSEngine.evaluate_cell`, `_safe_z`, `compute_optical_lag_days` |
| SMAP native-support inversion | same | `NativeSupportSpatialInverter` |
| Error bound / tolerance | same | `LipschitzErrorParameters` logic |
| MBSI, bare fraction, crack depth, BF-EHSI, D_i | `external/aryas_workresult/bf_ehsi_engine.py` | `BFEHSIEngine` methods |
| N ledger, subsidy, AUTP, WBC, Pareto | `external/aryas_workresult/fiscal_actuarial.py` | `CyberKatamFiscalActuarialEngine` |
| 90-day water balance | `external/aryas_workresult/build_water_balance_banyumas.py` | `BanyumasWaterBalanceSimulator` |

**Import strategy:** Arya should promote the four modules into an installable
package under `physics-engines/` with `__init__.py` in a dedicated PR. Until then,
AI Core may add `external/aryas_workresult` to `sys.path` **only in test/dev
fixtures**, never as a hidden production import. Do not copy the code.

---

## 12. Data readiness by module

| Input | Exists | Usable for AI Core now? |
|---|---|---|
| 1,000 H3 res-9 cells (geometry) | Yes | Yes, as synthetic geometry |
| H3 attributes (LST/SMAP/GPM/NDVI/MBSI) | Yes, random | Only as mock values, never as observations |
| Paddy mask | No (bbox only) | No |
| Climatology μ/σ | Yes, synthetic | Only for plumbing tests |
| HLS reflectance time series | No | No |
| ECOSTRESS LST + QC | No | No |
| ECOSTRESS ESI | No | No — blocks real PVRS |
| SMAP root-zone series | No | No |
| GPM V07 precipitation series | No | No |
| SRTM slope/TWI | No | Blocks real BF-EHSI |
| Soil hydraulic profile | Assumed constants | Only for scenario tests |
| Contract schema | No | Blocks final validation |
| Economics/agronomy parameters | Partial/assumed | Blocks production Pareto/fiscal output |

## 13. Definition of "module ready"

A module is ready for integration only when:

1. It imports Arya's formulas rather than duplicating them.
2. It fails closed on missing inputs and emits an abstention reason.
3. Its unit tests pass offline in the pinned environment.
4. It labels synthetic data as synthetic.
5. Its output validates against the ratified contract.
6. Any real-data claim is backed by an inspected export recorded in
   `docs/nasa_data_inventory.md`.

Task 0 stops before implementation. The above is the starting plan for the next task.
