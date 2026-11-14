# Contract Schema Validator — Design and Governance Record

**Status: PROVISIONAL — NOT RATIFIED**
**Task:** Task 1 — Contract Schema Validator (CYBER-KATAM AI Core, Aqila)
**Schema:** `contracts/grid_cell_contract.schema.json`
**Package:** `src/contracts/`
**Tests:** `tests/test_contract_validator.py`

> This validator checks structure and explicitly labelled provisional consistency
> rules. A passing result does **not** prove that a NASA-derived observation is
> physically correct, calibrated, or suitable for an operational recommendation.

---

## 1. Scope and non-goals

### In scope

- Strict parsing of a Python mapping or JSON string.
- Structural validation with JSON Schema Draft 2020-12.
- Deterministic, field-addressable error reporting.
- A small set of opt-in semantic checks whose rules are definitional rather than
  business thresholds.
- Unit tests built entirely from synthetic mock data.

### Out of scope

- Changing Arya's physics engines or formulas.
- Recomputing PVRS, BF-EHSI, fiscal, or water-balance values.
- Imputing missing satellite observations.
- Converting units or numeric strings.
- Clipping out-of-range values.
- Claiming field validity or NASA data quality.
- Ratifying any unresolved contract decision.

---

## 2. Sources audited

| Source | What was used |
|---|---|
| `contracts/README.md` | Schema location, versioning rules, known open issues |
| `docs/contract_governance.md` | Change approval, required/optional, enum and nested-structure governance |
| `docs/ai_core_readiness.md` | Validator direction, fail-closed warning, no real-data requirement for unit tests |
| `external/aryas_workresult/grid_cell_contract_sample.json` | Field reference only (UTF-16 console log, not a JSON document) |
| `external/aryas_workresult/pvrs_engine.py` | PVRS [0,1], ESI [0,1], NDVI [-1,1], optical lag 0..14, system-state strings |
| `external/aryas_workresult/bf_ehsi_engine.py` | BF-EHSI [0,2.5], MBSI [-1,1], slope handling |
| `external/aryas_workresult/fiscal_actuarial.py` | Contract field assembly, fiscal fields, scenario fields |
| `external/aryas_workresult/build_water_balance_banyumas.py` | Scenario water demand and crop-sequence context |

### Audit findings that affect the schema

1. `grid_cell_contract_sample.json` is a UTF-16 console-log dump containing a
   fiscal report, a Pareto line, and a JSON payload. It is not parseable as a JSON
   document and is not used as a test fixture.
2. The sample's `h3_index` value, `892e42426ffffff`, matches the 15-hex-character
   pattern but is **not a valid H3 cell** under `h3 4.1.2` (`h3.is_valid_cell`
   returns `False`). The sample therefore cannot be treated as a golden contract.
   The validator exposes H3 validity only as an opt-in provisional semantic rule.
   When the JSON payload is extracted from the console-log wrapper, it passes the
   structural schema; only the provisional H3 rule rejects it.
3. The sample and `build_grid_cell_contract_json()` contain hardcoded physical
   values (KI-06). Structural validation cannot detect hardcoded-but-in-range
   values; that remains an integration concern.
4. `HLS_BSI` (contract) and `MBSI` (engine) are different names. The schema uses
   `HLS_BSI` and explicitly rejects `MBSI` as an additional property until the
   naming decision is ratified.
5. The repository contains two abstention spellings:
   `ABSTAIN_AUDIT_REQUIRED` and `ABSTAIN_FIELD_AUDIT_REQUIRED`. Both are accepted
   provisionally in the `system_state` enum; neither is declared final.

---

## 3. Validation architecture

The validator is layered so that a failure in one layer is not misreported as a
failure in another.

```text
payload (mapping | JSON string)
        |
        v
Layer 1: strict JSON parsing
  - reject None / empty string / empty object
  - catch JSONDecodeError
  - reject NaN, Infinity, -Infinity (including 1e999 overflow)
  - require top-level object
  - reject non-string object keys and circular references
  - do not coerce, clip, default, or impute
        |
        v
Layer 2: JSON Schema Draft 2020-12
  - schema loaded with pathlib from contracts/
  - Draft202012Validator.check_schema() before use
  - no format checker (no contract-defined formats)
  - required, type, nested structure, arrays, enum, min/max, strings,
    additional properties
        |
        v
Layer 3: opt-in semantic checks
  - disabled by default
  - H3 validity (h3.is_valid_cell)
  - H3 parent consistency (h3.cell_to_parent at resolution 7)
  - unique rotation scenario ids
  - no business threshold is applied
        |
        v
ValidationResult(is_valid, errors[], error_count)
```

Semantic checks run only when structural validation succeeds. This avoids
cascading `KeyError`/`TypeError` failures and keeps error output focused.

### Schema path independence

`DEFAULT_SCHEMA_PATH` is derived from `Path(__file__).resolve().parents[2]`, so it
works from the repository root, from `tests/`, or from any other working
directory. Callers may pass an explicit `schema_path`; the default never depends
on `os.getcwd()`.

### No shared mutable validator state

- `ContractValidator` loads and validates the schema once per instance.
- It stores an immutable schema path and a `Draft202012Validator`.
- There is no module-level schema cache or mutable global registry.
- For batch use, instantiate one validator and reuse it; `validate_contract()` is a
  convenience wrapper that creates a validator per call.

---

## 4. JSON Schema methodology

- `$schema` is `https://json-schema.org/draft/2020-12/schema`.
- The schema is a separate JSON file, not Python literals.
- `Draft202012Validator.check_schema(schema)` runs before the schema is used.
- The loader also rejects a schema that does not declare the Draft 2020-12 URI.
- No `format` keyword is used. The contract does not define formats such as
  `date-time` or `email`, and a format checker must not be used as a substitute
  for type or domain checks.
- `additionalProperties: false` is used at every object level as a **provisional
  fail-closed policy**. Known optional fields are explicitly listed.
- `number` rejects booleans. JSON Schema's integer semantics accept a JSON number
  with a zero fractional part (for example `9.0`); this is a JSON Schema rule, not
  a coercion performed by the validator.
- Ranges are asserted only when an existing engine or governance document states
  them. Unresolved ranges are left unbounded rather than invented.
- The schema does not enforce an H3 resolution.

### Additional-properties policy

The fail-closed policy was chosen because `docs/ai_core_readiness.md` warns that
unknown fields must not be silently ignored. It is provisional: a ratified
contract may choose permissive additional properties, a versioned extension
namespace, or a strict allow-list. Until then, unknown fields produce
`ADDITIONAL_PROPERTY` with the exact JSON Pointer.

---

## 5. Field specification

Legend for **Status**:

- **Sample-backed** — present in Arya's sample / `build_grid_cell_contract_json()`.
- **Engine-backed** — range or type taken from an existing engine definition.
- **Provisional** — a choice made to make validation runnable; requires ratification.

### A. Grid identity

| Field | Type | Constraint | Required | Status |
|---|---|---|---|---|
| `contract_version` | string | `const "1.0"` | yes | Sample-backed; ratification pending |
| `h3_index` | string | `^[0-9a-f]{15}$` | yes | Sample-backed; resolution not enforced |
| `h3_parent_res7` | string | `^[0-9a-f]{15}$` | no | Provisional optional |

H3 **validity** is not a structural rule. Enable
`ContractValidator(enable_provisional_semantics=True)` to run `h3.is_valid_cell`.
Parent consistency is checked only when `h3_parent_res7` is present and the child
index is valid.

### B. Physical indicators

| Field | Type | Minimum | Maximum | Basis |
|---|---|---|---|---|
| `PVRS` | number | 0 | 1 | Sigmoid score in `pvrs_engine.py` |
| `BF_EHSI` | number | 0 | 2.5 | Engine clips instantaneous BF-EHSI to [0, 2.5] |
| `SMAP_wetness` | number | 0 | 1 | Physical volumetric domain (m3/m3); narrower engine inversion bounds not ratified |
| `ECOSTRESS_ESI` | number | 0 | 1 | Engine documents ET/PET ratio [0, 1] |
| `LST_anomaly` | number | — | — | Celsius anomaly; may be negative; no ratified bound |
| `HLS_BSI` | number | -1 | 1 | MBSI definition in `bf_ehsi_engine.py`; naming unresolved |
| `HLS_NDVI` | number | -1 | 1 | Engine documents NDVI [-1, 1] |
| `GPM_rain_7d` | number | 0 | — | Seven-day accumulation in mm; no upper bound asserted |
| `SRTM_slope` | number | 0 | 90 | Slope in degrees |

All nine indicators are required and non-null in the provisional schema. This is a
**fail-closed choice**, not a ratified nullable policy. `missing_observation` is a
separate operational flag and is never treated as zero or as an imputed value.

### C. Operational flags

| Field | Type | Constraint | Required | Basis |
|---|---|---|---|---|
| `missing_observation` | boolean | — | yes | Sample-backed |
| `optical_lag_days` | integer | 0..14 | yes | `compute_optical_lag_days()` returns 0 or [1, 14] |
| `erosion_alert` | boolean | — | yes | Sample-backed; no ratified mapping to a BF-EHSI/D_i threshold |

### D. Rotation scenarios

`rotation_scenarios` is an array with `minItems: 0`. The required number of
scenarios is unresolved, so no count above zero is enforced.

| Scenario field | Type | Constraint | Required |
|---|---|---|---|
| `id` | string | min length 1 | yes |
| `crop_sequence` | string | min length 1 | yes |
| `water_demand_mm` | number | >= 0 | yes |
| `n_fertilizer_displaced_kg` | number | >= 0 | yes |
| `soc_change_ton` | number | unbounded (negative allowed) | yes |
| `bph_risk_score` | number | 0..1 | yes |
| `net_margin_idr` | number | unbounded (negative allowed) | yes |

The Permentan 163 kg/ha cap appears in `fiscal_actuarial.py`, but it is not
enforced as a scenario maximum because the contract has not ratified that mapping.

### E. XAI decision block

| Field | Type | Constraint | Required |
|---|---|---|---|
| `why_suggested` | string | min length 1 | yes |
| `multi_benefits` | string | min length 1 | yes |
| `information_gaps` | string | min length 1 | yes |
| `local_risks_and_gates` | string | min length 1 | yes |

Text content is not fact-checked. The validator cannot detect fabricated claims;
that is the responsibility of the XAI generator and its provenance rules.

### F. Fiscal metrics

| Field | Type | Constraint | Required | Basis |
|---|---|---|---|---|
| `urea_subsidy_saved_idr` | number | >= 0 | yes | Task contract |
| `autp_risk_reduction_pct` | number | 0..100 | yes | Percentage domain |
| `cluster_h3_7_gross_saving_idr` | number | >= 0 | no | Present in Arya's sample; not in the task-level required set |
| `cluster_h3_7_net_saving_s_net_idr` | number | unbounded | no | Present in Arya's sample; may be negative |

### G. System state

`system_state` is a string enum containing, provisionally:

- `ACTIVE_RECOMMENDATION`
- `ABSTAIN_AUDIT_REQUIRED`
- `ABSTAIN_FIELD_AUDIT_REQUIRED`

The last two are both accepted because the final abstention name is unresolved.
No semantic rule links `system_state` to operational flags yet.

---

## 6. Business / semantic validation methodology

No business rule has been ratified. Therefore:

- The default validator executes **zero** semantic rules.
- `enable_provisional_semantics=True` enables only definitional consistency
  checks:
  1. `h3_index` is a valid H3 cell (`h3.is_valid_cell`).
  2. `h3_parent_res7`, when present, is valid and equals
     `h3.cell_to_parent(h3_index, 7)`.
  3. Rotation scenario `id` values are unique.

These are not claimed to be ratified business policy. They are opt-in because the
contract governance process has not approved them.

Rules deliberately **not** implemented:

- No implication from `missing_observation` to null/zero indicator values.
- No `erosion_alert` ↔ BF-EHSI/D_i threshold equivalence.
- No `system_state` ↔ scenario-count or advisory-code implication.
- No cross-indicator threshold, ratio, or ranking rule.
- No fiscal arithmetic or Pareto feasibility re-check.
- No nullable-indicator policy.
- No resolution constraint on H3.

Each of these would require an explicit contract decision first.

---

## 7. Error handling

### Result contract

```python
ValidationResult(
    is_valid: bool,
    errors: list[ValidationError],
    error_count: int,
)
```

Each `ValidationError` has:

- `code` — stable error code
- `message` — human-readable, no full payload dump
- `path` — RFC 6901 JSON Pointer, for example
  `/physical_indicators/HLS_NDVI`
- `validator` — producing keyword, parser, or semantic rule
- `layer` — `parsing`, `schema`, `semantic`, or `configuration`

Errors are sorted deterministically by JSON Pointer path first, then layer, code,
validator, and message. Array indexes sort numerically.

### Layer separation

| Layer | Produced as | Examples |
|---|---|---|
| Parsing | `ValidationResult` | `EMPTY_INPUT`, `INVALID_JSON`, `NON_FINITE_NUMBER`, `ROOT_NOT_OBJECT` |
| Schema | `ValidationResult` | `REQUIRED_FIELD`, `TYPE_MISMATCH`, `BELOW_MINIMUM`, `ADDITIONAL_PROPERTY` |
| Semantic | `ValidationResult` | `H3_INVALID_INDEX`, `H3_PARENT_MISMATCH`, `DUPLICATE_SCENARIO_ID` |
| Configuration | **raised** `SchemaConfigurationError` | missing schema, malformed schema, invalid schema, wrong `$schema` |

A broken schema is a programming/configuration failure, not bad payload data, so
it is raised rather than converted into `is_valid=False`.

`parse_contract_payload()` exposes `ContractParsingError` with `.errors` for
callers that need the parsing layer directly.

### Privacy / leakage

Messages use field paths and schema expectations. They do not include the whole
payload. Scalar values are generally omitted; schema enum values, limits, and
patterns are included because they are public contract metadata.

---

## 8. Testing methodology

Tests use only synthetic mock data and the pinned offline environment
(Python 3.12, `jsonschema==4.23.0`, `h3==4.1.2`, `pytest==8.3.4`).

Coverage groups:

- **Positive:** valid contract, omitted optional fields, min/max boundaries,
  empty scenario list, JSON-string input.
- **Structural negative:** missing required fields, numeric strings, booleans in
  numeric fields, below/above range, invalid enum, invalid nested object, extra
  properties, invalid scenario/XAI/fiscal fields, null indicator.
- **Semantic:** invalid H3, invalid parent, parent mismatch, duplicate scenario
  ids, and proof that these rules are off by default.
- **Parsing:** empty input, malformed JSON, NaN/Infinity literals, non-finite
  Python values, `1e999` overflow, non-object roots, unsupported input type.
- **Determinism/configuration:** repeated results are identical, paths are
  sorted, error shape is stable, schema loads from another working directory,
  missing/malformed/invalid schema files raise configuration errors.

Commands:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_contract_validator.py -v
.venv\Scripts\python.exe -m pytest tests/ -v
```

The test fixture file is explicitly labelled mock/test data. No NASA observations
are required, and no test asserts field truth.

---

## 9. Unresolved decisions requiring Arya / contract-owner confirmation

| # | Decision | Current provisional behavior | Risk if wrong |
|---|---|---|---|
| 1 | `MBSI` or `HLS_BSI` | Only `HLS_BSI` is accepted; `MBSI` is an additional property | MBSI-producing integrations are rejected |
| 2 | Final abstention status | Both `ABSTAIN_AUDIT_REQUIRED` and `ABSTAIN_FIELD_AUDIT_REQUIRED` accepted | Consumers may implement only one string |
| 3 | Is Arya's sample official v1.0? | Treated as field reference only, not golden data | A hardcoded/invalid sample could become a false acceptance target |
| 4 | Required vs optional fields | Top-level, indicator, flag, scenario, XAI, and two fiscal fields required; `h3_parent_res7` and cluster fiscal fields optional | Missing operational data may be rejected or accepted incorrectly |
| 5 | Nullable policy for missing observations | All indicators required and non-null | Missing-observation contracts are rejected |
| 6 | Valid range per indicator | Only engine/document-backed ranges encoded; `LST_anomaly`, `GPM_rain_7d` upper bound, etc. left open | Too loose or too strict domain checks |
| 7 | Required number of rotation scenarios | `minItems: 0` | A recommendation with zero scenarios validates structurally |
| 8 | Additional properties policy | `additionalProperties: false` everywhere | Future fields are rejected until the schema is versioned |
| 9 | Is H3 validity a hard requirement? | Opt-in semantic rule, off by default | Invalid H3 indexes pass default validation |
| 10 | Is `h3_parent_res7` required? | Optional | Parent-less contracts pass |
| 11 | Is `LST_anomaly` bounded? | Unbounded | Extreme anomalies pass |
| 12 | Is `SMAP_wetness` bounded by [0,1] or engine inversion bounds? | [0,1] | Engine-specific invalid values may pass |
| 13 | Is BF-EHSI max 2.5 a contract rule or an engine implementation detail? | Encoded as 2.5 | Future engine changes may desynchronize |
| 14 | Does `erosion_alert` equal a BF-EHSI/D_i threshold? | No semantic mapping | Inconsistent alert/index combinations pass |
| 15 | Must scenario ids be unique? | Opt-in semantic rule, off by default | Duplicate ids pass default validation |
| 16 | Are cluster fiscal fields required? | Optional | Consumers must handle absence |
| 17 | Units and rounding conventions | Types/ranges only; no unit conversion or rounding check | Unit mistakes inside a valid range pass |
| 18 | Meaning of `contract_version` | `const "1.0"` | Version evolution requires a new schema file |

---

## 10. Known limitations

- **Structural validity is not physical truth.** An in-range value can still be
  fabricated, stale, mis-united, or scientifically wrong.
- **Hardcoded values are invisible.** The validator cannot detect that an
  in-range value came from a literal in `build_grid_cell_contract_json()`.
- **No nullable indicators.** The provisional schema rejects `null`; the real
  missing-observation policy is unresolved.
- **No imputation or clipping.** Out-of-range values fail; they are not repaired.
- **No numeric coercion.** `"0.5"` is a string, not a number.
- **Python mappings should contain JSON-native values.** The scanner rejects
  non-finite Python floats, but non-native numeric types (for example some NumPy
  or Decimal values) are not normalised or guaranteed to behave identically to a
  JSON number. Serialise the contract to JSON before validation in production.
- **H3 resolution is not checked.** Only optional cell validity is available.
- **H3 parent check assumes resolution 7**, because the field is named
  `h3_parent_res7`; the field itself is optional.
- **Duplicate JSON object keys are not detected.** Python `json.loads` keeps the
  last value. A future strict parser could add duplicate-key rejection.
- **JSON Schema integer semantics** accept `9.0` as an integer.
- **Additional-properties policy is provisional** and may reject valid future
  contract extensions.
- **No format checks** are applied because the contract defines no formats.
- **Text fields are not fact-checked.** XAI prose can still contain unsupported
  claims.
- **No cross-engine threshold consistency** is enforced (PVRS z-scores versus
  BF-EHSI's 42 °C reference, for example).
- **The schema is provisional.** It must not be presented to downstream teams as
  the ratified v1.0 contract.
- **No NASA data validation.** Passing tests only prove deterministic behavior on
  synthetic fixtures.

---

## 11. Integration example

```python
from src.contracts import ContractValidator

# Instantiate once per process/pipeline stage.
validator = ContractValidator(enable_provisional_semantics=False)

result = validator.validate(payload)
if not result.is_valid:
    for error in result.errors:
        print(error.code, error.path, error.message)
```

For a future ratified semantic rule set, change the constructor default or pass
an explicit policy object in a later task. Do not silently convert the
provisional rules into production hard failures before ratification.

---

## 12. Definition-of-done mapping

| DoD item | Evidence |
|---|---|
| JSON Schema exists and is checkable | `contracts/grid_cell_contract.schema.json`; `load_contract_schema()` |
| Independent of working directory | `DEFAULT_SCHEMA_PATH` from `__file__`; test with `monkeypatch.chdir` |
| Strict JSON parsing | Layer 1 parser and parsing tests |
| Structural validation | `Draft202012Validator` and structural tests |
| Semantic validation only for agreed rules | Default disabled; three opt-in definitional rules documented |
| Errors have code/path/message | `ValidationError`; determinism/shape tests |
| Unit tests pass | Run commands in Section 8 |
| Arya/Arief files untouched | No edits to `external/` |
| Design documentation | This file |
| Unresolved decisions recorded | Section 9 |
| No observation-truth claim | Section 10 and header warning |

---

*End of provisional design record.*
