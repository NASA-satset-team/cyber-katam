# Crop Parameter Registry — Repository Audit & Design

**Status:** audit and design only. No source code, formula, coefficient, engine, or registry implementation was changed.

**Repository context:** branch `feature/rifaldi-ui`, HEAD `9fc3702`. Audit performed read-only against the local working tree. No commit, push, merge, or branch switch was performed.

---

## 1. Executive Summary

A centralized crop parameter registry **does not exist** in the repository.

The repository contains crop-related values, but they are scattered across:

- `external/aryas_workresult/fiscal_actuarial.py`
- `external/aryas_workresult/build_water_balance_banyumas.py`
- `external/aryas_workresult/water_balance_banyumas.xlsx`
- `external/ariefs_workresult/crop_rotation_matrix.json`
- `external/ariefs_workresult/task7_agronomy_matrix.py`
- `external/ariefs_workresult/nitrogen_dynamics.py`
- `external/ariefs_workresult/nitrogen_balance_output.json`
- `web-app/src/model.js`
- `contracts/grid_cell_contract.schema.json`

Most values are **assumption-based, hardcoded demo values, or synthetic**. No crop parameter in the repository has a complete, traceable external citation sufficient for production use. No scientific names, crop categories, per-crop growing durations, planting calendars, suitability limits, crop price data, or crop-level yield models were found.

The closest existing components are:

- `RotationCandidate` and `solve_pareto_epsilon_constraint()` in `fiscal_actuarial.py` — a generic optimizer core, not a crop rotation evaluator.
- A fixed three-scenario water balance in `build_water_balance_banyumas.py`.
- A three-scenario hand-written parameter matrix in `crop_rotation_matrix.json`.
- A soybean nitrogen balance in `nitrogen_dynamics.py`.
- Static UI strategies and an illustrative Pareto chart in `web-app/src/model.js` and `main.jsx`.

**Readiness verdict:**

- **Ready to start:** schema, loader, unit registry, source registry, validation tests, and an empty crop registry with explicit missing statuses.
- **Not ready for production content:** no verified agronomic values, no agreed crop list/sources, no N-model choice, no calendar/suitability/yield models, and no ratified contract extension for the optimizer fields.
- **Not ready for integration:** crop suitability, water requirement, planting calendar, candidate generator, and rotation evaluator do not exist.

No parameter should be promoted to “verified” merely because it appears in an engine, an Excel workbook, or documentation.

---

## 2. Existing Crop Parameter Inventory

### 2.1 Method and files inspected

Files and directories inspected:

- `external/aryas_workresult/`
- `external/ariefs_workresult/`
- `src/`
- `contracts/`
- `docs/`
- `web-app/src/`
- `tests/`
- `data/`
- `public/`

Search terms included crop names, `Kc`, crop coefficient, water requirement, root depth, growing duration, planting/harvest, nitrogen, fixation, Ndfa, yield, price, cost, pest, WBC, BPH, suitability, pH, drainage, and Pareto.

No crop parameter CSV was found. The only `.xlsx` crop/water file is `external/aryas_workresult/water_balance_banyumas.xlsx`. The `data/` tree contains boundaries, mock H3 data, and synthetic fixtures, not a crop parameter registry.

### 2.2 Crop identity and calendar

| Parameter | Crop | Value | Unit | Source | Status | Usage |
|---|---|---|---|---|---|---|
| Scenario/crop labels | Padi, Bera, Kedelai Anjasmoro, Sorghum, Kacang Hijau Vima-1, Cover Crop | Labels only | n/a | `external/aryas_workresult/fiscal_actuarial.py:334–374`; `external/aryas_workresult/build_water_balance_banyumas.py:42–55` | Scenario labels, not verified crop records | Demo and UI names |
| Scenario/crop labels | Padi, Bera, Kedelai Anjasmoro, Kacang Hijau | Labels only | n/a | `web-app/src/model.js:4–31`; `web-app/src/i18n.js` | UI labels | UI only |
| Scenario/crop labels | Padi, Bera, Kedelai, Sorghum, Bawang Merah, Legum | Labels only | n/a | `external/ariefs_workresult/crop_rotation_matrix.json`; `external/ariefs_workresult/task7_agronomy_matrix.py:20–52` | Hand-written assumptions | Not used by engine |
| Scientific name | All crops | Not found | n/a | No repository source | **Missing** | None |
| Crop category | All crops | Not found | n/a | No repository source | **Missing** | None |
| Stable crop identifier | All crops | Not found | n/a | No repository source | **Missing** | None |
| Growing duration per crop | All crops | Not found | day | No repository source | **Missing** | None |
| Non-host duration | Scenario A / B / C | 15 / 68 / 60 | day | `fiscal_actuarial.py:338, 351, 364` | Hardcoded demo | Defined in `RotationCandidate`; not used by `solve_pareto_epsilon_constraint()`; `compute_fiscal_and_autp_clearing()` defaults to 65 |
| WBC life cycle | WBC/pest model | 28.0 | day | `fiscal_actuarial.py:115–138` (default `life_cycle_days=28.0`) | Assumption-based | Used when `compute_wbc_nymph_survival_rate()` is called |
| Planting window start/end | All crops | Not found | date | No repository source | **Missing** | None |
| Harvest window/date | All crops | Not found | date | No repository source | **Missing** | None |
| Fixed water-balance phase ranges | Scenario A / B / C | Day ranges 1–40, 40–65, etc.; day 1–90 | day | `build_water_balance_banyumas.py:86–122` | Hardcoded scenario logic | Used only by fixed water balance |

### 2.3 Water and soil parameters

| Parameter | Crop | Value | Unit | Source | Status | Usage |
|---|---|---|---|---|---|---|
| Kc initial / mid / late — A | Padi → Bera → Padi | 0.28 / 1.05 / 1.20 | fraction | `build_water_balance_banyumas.py:104` | Hardcoded; no citation | Used by fixed scenario A |
| Kc initial / development / mid / late — B | Padi → Kedelai Anjasmoro → Sorghum | 0.40 / 0.75 / 1.10 / 0.50 | fraction | `build_water_balance_banyumas.py:107–113` | Hardcoded; no citation | Used by fixed scenario B |
| Kc initial / development / late / cover | Padi → Kacang Hijau (60 hari) → cover crop | 0.35 / 0.95 / 0.35 / 0.30 | fraction | `build_water_balance_banyumas.py:116–122` | Hardcoded; no citation | Used by fixed scenario C |
| Seasonal water requirement | Padi–Bera / Padi–Kedelai–Sorghum / Padi–Bawang–Legum | 800 / 1200 / 1050 | mm/season | `crop_rotation_matrix.json`; `task7_agronomy_matrix.py:25, 36, 47` | Assumption-based; no citation | **Defined but not used** by any engine |
| Root depth | All scenarios | 1000 | mm | `build_water_balance_banyumas.py:28` | Assumption-based; single profile | Used by fixed water balance for all crops |
| Saturated water content, `theta_sat` | All scenarios | 0.48 | m³/m³ | `build_water_balance_banyumas.py:29` | Assumption-based | Used by fixed water balance |
| Field capacity, `theta_fc` | All scenarios | 0.36 | m³/m³ | `build_water_balance_banyumas.py:30` | Assumption-based | Used by fixed water balance |
| Permanent wilting point, `theta_pwp` | All scenarios | 0.16 | m³/m³ | `build_water_balance_banyumas.py:31` | Assumption-based | Used by fixed water balance |
| Saturated hydraulic conductivity, `K_sat` | All scenarios | 42 | mm/day | `build_water_balance_banyumas.py:32` | Assumption-based | Used by fixed water balance |
| Required K_sat for legume | Legume scenarios | 35 | mm/day | `build_water_balance_banyumas.py:33` | Assumption-based | Used in fixed water balance profile |
| Initial root-zone moisture | All scenarios | 295 | mm | `build_water_balance_banyumas.py:77–79` | Assumption/synthetic start state | Used by fixed water balance |
| ETo forcing | All scenarios | Sine function around 4.1–5.8 | mm/day | `build_water_balance_banyumas.py:88–100` | Synthetic | Used by fixed water balance |
| Rainfall forcing | All scenarios | `np.random.choice` values | mm/day | `build_water_balance_banyumas.py:89–99` | Synthetic | Used by fixed water balance |
| Crop ETc | All scenarios | `ETo × Kc` | mm/day | `build_water_balance_banyumas.py:129–132` | Implemented formula; inputs synthetic/hardcoded | Used by fixed water balance |
| Water demand in candidate | A / B / C | 680 / 270 / 245 | mm | `fiscal_actuarial.py:342, 354, 367` | Hardcoded demo values | Used by demo Pareto solver |
| Required K_sat in candidate | A / B / C | 10 / 35 / 30 | mm/day | `fiscal_actuarial.py:345, 358, 371` | Hardcoded demo values | Used by demo Pareto solver |
| pH range | All crops | Not found | pH | No repository source | **Missing** | None |
| Soil texture / drainage / salinity suitability | All crops | Not found | text / class | No repository source | **Missing** | None |
| Slope suitability limit | All crops | Not found | degree | No repository source | **Missing** | None |
| Effective rainfall / irrigation efficiency | All crops | Not found as crop parameters | mm | No repository source | **Missing/unverified** | Fixed water balance uses its own rules |
| Root depth per crop | Each crop | Not found | mm | No repository source; only one shared 1000 mm profile | **Missing** | None |

### 2.4 Nitrogen parameters

| Parameter | Crop | Value | Unit | Source | Status | Usage |
|---|---|---|---|---|---|---|
| Dry biomass | Soybean (Arya ledger) | 6.25 | t/ha | `fiscal_actuarial.py:23` | Assumption-based; no citation | Used by `compute_three_tier_nitrogen_ledger()` |
| Tissue N fraction | Soybean | 0.038 | fraction | `fiscal_actuarial.py:24` | Assumption-based; no citation | Used by N ledger |
| Ndfa fraction | Soybean | 0.76 | fraction | `fiscal_actuarial.py:25` | Assumption-based; no citation | Used by N ledger |
| Harvest N export fraction | Soybean | 0.42 | fraction | `fiscal_actuarial.py:28` | Assumption-based | Used by N ledger |
| Denitrification fraction | Soybean | 0.11 | fraction | `fiscal_actuarial.py:29` | Assumption-based | Used by N ledger |
| Leaching fraction | Soybean | 0.07 | fraction | `fiscal_actuarial.py:30` | Assumption-based | Used by N ledger |
| Mineralization fraction | Soybean | 0.68 | fraction | `fiscal_actuarial.py:31` | Assumption-based | Used by N ledger |
| Urea N content | Urea | 0.46 | fraction | `fiscal_actuarial.py:34` | Standard constant, but no source in repository | Used by N ledger |
| NUE urea paddy | Paddy | 0.7998 | fraction | `fiscal_actuarial.py:35` | Assumption-based; no citation | Used by N ledger |
| Permentan maximum urea displacement | Paddy/rotation | 163 | kg/ha | `fiscal_actuarial.py:36` | Assumption-based; docstring refers to Permentan but no bibliographic citation | Used by N ledger |
| Soybean yield | Soybean | 2.5 | t/ha | `nitrogen_dynamics.py:11, 54` | Assumption-based | Arief N model only |
| Residue ratio | Soybean | 1.5 | t residue per t grain | `nitrogen_dynamics.py:16–17` | Assumption-based | Arief N model |
| N content of residue | Soybean | 0.025 | fraction | `nitrogen_dynamics.py:20–22` | Assumption-based | Arief N model |
| N fixation fraction | Soybean | 0.75 default; 0.80 in demo | fraction | `nitrogen_dynamics.py:11, 26, 54` | Assumption-based | Arief N model |
| Mineralization rate | Soybean residue | 0.40 | fraction | `nitrogen_dynamics.py:31` | Assumption-based | Arief N model |
| Arief N output: residue | Soybean | 3.75 | t/ha | `nitrogen_balance_output.json` | Model output from assumptions | **Not used** by engine |
| Arief N output: total N | Soybean | 93.75 | kg/ha | `nitrogen_balance_output.json` | Model output from assumptions | **Not used** |
| Arief N output: fixed N | Soybean | 75.0 | kg/ha | `nitrogen_balance_output.json` | Model output from assumptions | **Not used** |
| Arief N output: available next season | Soybean | 30.0 | kg/ha | `nitrogen_balance_output.json` | Model output from assumptions | **Not used** |
| Fertilizer N displaced in candidate | A / B / C | 0 / 163 / 128 | kg/ha | `fiscal_actuarial.py:339, 352, 365` | Hardcoded demo | Used by demo Pareto solver |
| N fixation per crop/variety | All crops | Not found | kg/ha | No repository source | **Missing** | None |
| Soil initial N / N response / N losses per crop | All crops | Not found | kg/ha or fraction | No repository source | **Missing** | None |

**Important conflict:** Arya’s N ledger uses 3.8% tissue N, 76% Ndfa, 68% mineralization, plus harvest/denitrification/leaching terms. Arief’s model uses 2.5% N, 1.5 residue ratio, 75–80% fixation, and 40% mineralization. These are different models and parameters. `docs/project_file_inventory.md:194` records this as KI-10 (High).

### 2.5 Yield, financial, and pest parameters

| Parameter | Crop/scenario | Value | Unit | Source | Status | Usage |
|---|---|---|---|---|---|---|
| Expected yield | Padi–Bera / Padi–Kedelai–Sorghum / Padi–Bawang–Legum | 6.5 / 9.0 / 8.5 | t/ha | `crop_rotation_matrix.json`; `task7_agronomy_matrix.py:27, 38, 49` | Assumption-based; no citation | **Defined but not used** |
| Gross revenue | A / B / C | 26.5M / 31.4M / 27.8M | IDR/ha | `fiscal_actuarial.py:343, 356, 369` | Hardcoded demo | Used by demo Pareto solver |
| Production cost | A / B / C | 15.2M / 12.8M / 11.5M | IDR/ha | `fiscal_actuarial.py:344, 357, 370` | Hardcoded demo | Used by demo Pareto solver |
| Net margin | A / B / C | Revenue − cost | IDR/ha | `fiscal_actuarial.py:66–68` | Implemented formula; demo inputs | Used by demo Pareto solver |
| H3-7 effective area | Cluster | 11,000 | ha | `fiscal_actuarial.py:42` | Assumption-based; no source | Used by fiscal clearing |
| Urea subsidy per kg | Urea | 9,250 | IDR/kg | `fiscal_actuarial.py:43` | Assumption-based; no source | Used by fiscal clearing |
| PPL extension cost | Cluster | 185,000,000 | IDR/cluster | `fiscal_actuarial.py:44` | Assumption-based | Used by fiscal clearing |
| Transition seed/inoculant cost | Cluster | 640,000,000 | IDR/cluster | `fiscal_actuarial.py:45` | Assumption-based | Used by fiscal clearing |
| Verification/audit cost | Cluster | 95,000,000 | IDR/cluster | `fiscal_actuarial.py:46` | Assumption-based | Used by fiscal clearing |
| AUTP sum insured | Per ha | 6,000,000 | IDR/ha | `fiscal_actuarial.py:47` | Assumption-based | Used by fiscal/AUTP clearing |
| Baseline AUTP claim probability | Cluster | 0.145 | fraction | `fiscal_actuarial.py:48` | Assumption-based | Used by fiscal/AUTP clearing |
| Crop price | All crops | Not found | IDR/kg | No repository source | **Missing** | None |
| Crop-level production cost | All crops | Not found; only aggregate candidate cost | IDR/ha | No repository source | **Missing** | None |
| BPH burden index | A / B / C | 0.82 / 0.04 / 0.06 | dimensionless, 0–1 | `fiscal_actuarial.py:342, 355, 368` | Hardcoded demo | Used by demo Pareto solver |
| WBC population suppression | Pest model | Formula using non-host days and adoption | % | `fiscal_actuarial.py:115–138` | Assumption-based formula | Used when fiscal/AUTP method is called |
| Crop host status for WBC | All crops | Not found | enum | No repository source | **Missing** | None |
| Pest susceptibility / host range | All crops | Not found | enum/fraction | No repository source | **Missing** | None |
| SOC change | A / B / C | −0.42 / 1.25 / 0.88 | t/ha | `fiscal_actuarial.py:341, 354, 367` | Hardcoded demo | Used by demo Pareto solver; no SOC model |
| Predicted erosion D_i | A / B / C | 0.81 / 0.19 / 0.22 | dimensionless (as used) | `fiscal_actuarial.py:346, 359, 372` | Hardcoded demo | Used by demo Pareto solver; BF-EHSI could provide a value, but no adapter |
| UI water/soil/pest scores | A / B / C | 35/30/28; 82/88/80; 90/67/73 | arbitrary UI score | `web-app/src/model.js:6, 16, 26` | Synthetic/UI-only | UI display only; not an engine |

### 2.6 Context data that is not a crop parameter

| Item | Value/status | Source | Note |
|---|---|---|---|
| Land-cover classes | `PADDY_FIELD`, `NON_PADDY`, `MIXED`, `UNKNOWN` | `src/models/land_cover.py:35–40` | Land-cover classes, not crop parameters |
| Paddy fraction / paddy gate | Fractions and booleans | `scripts/integrate_sentinel_roi.py:72–105`; `public/demo-grid-levels.json` | Site context; not crop registry |
| Rotation scenarios in web data | `rotation_scenarios: []` for all 1,000 features | `public/banyumas_h3_indicators_v2.geojson` | No rotation output exists |
| Fiscal/XAI in web data | `fiscal_metrics` null; `xai_decision_block` null | same | No computed rotation/fiscal/XAI output |
| Contract sample | Invalid JSON; UTF-16 console log | `external/aryas_workresult/grid_cell_contract_sample.json` | Not a schema or valid fixture |
| Water workbook | Two sheets, 90 daily rows, three fixed scenarios | `external/aryas_workresult/water_balance_banyumas.xlsx` | Output of synthetic simulator |
| Crop matrix | Three hand-written scenarios | `external/ariefs_workresult/crop_rotation_matrix.json` | No citations; no economics/Ksat/erosion/non-host fields |
| Synthetic H3 data | Random attributes; `land_cover` hardcoded | `external/ariefs_workresult/banyumas_h3_precomputed.geojson`; `docs/project_file_inventory.md:99–121` | Not crop observations |

---

## 3. Parameter Provenance and Verification Status

### 3.1 Status vocabulary used in this report

| Status | Meaning |
|---|---|
| **Verified** | Value has a traceable external reference and has been checked by the team. **No such crop parameter was found.** |
| **Assumption-based** | Value exists in code/JSON/Excel, but the repository does not provide a citation or validation. |
| **Synthetic** | Value is generated by a simulator/random function, or is a demo start state. |
| **Hardcoded/demo** | Value is fixed in a demo candidate/UI and is not derived from data. |
| **Unknown** | Value/meaning exists only as a label or cannot be identified. |
| **Missing** | No value or parameter exists. |
| **Requires source** | Parameter is needed, but the repository has no value; an external agronomic source must be selected. |
| **Conflicting** | Two repository sources define the same concept with incompatible values/models. |

### 3.2 Provenance findings

1. **No verified crop parameter was found.**
   - The values in `fiscal_actuarial.py` and `build_water_balance_banyumas.py` are not accompanied by a bibliographic citation, source dataset, page, or retrieval date.
   - `ThreeTierNitrogenParams` mentions “Permentan No. 40/2007” and “uji isotop 15N BRIN” in its docstring, but the repository does not include the cited document, exact table, or reference details. The values must remain **unverified/requires source**.
   - Kc values are labeled “FAO-56” in a comment, but there is no citation, crop-stage definition, or source table. They remain **assumption-based**.
   - Arief’s crop matrix values (water, yield, soil moisture threshold, drought vulnerability) are hand-written with no cited source; `docs/project_file_inventory.md:59` records this.
   - Arief’s N model values are assumption-based; `docs/project_file_inventory.md:60` records the unsourced 1.5 residue ratio, 2.5% N, 75–80% fixation, and 40% mineralization.
   - Fiscal constants (area, subsidy, costs, AUTP probability) have no source in the repository.
   - WBC life cycle/suppression parameters have no source in the repository.

2. **Water balance is synthetic, not an agronomic data source.**
   - `build_water_balance_banyumas.py:74` uses `np.random.seed(20261114)`.
   - Rainfall is `np.random.choice`; ETo is a sine function; Kc and initial moisture are hardcoded.
   - `docs/project_file_inventory.md:90` states that columns labeled “GPM IMERG” and “NASA POWER” contain simulated values, and that the reported 100% irrigation saving is not physically credible.
   - `water_balance_banyumas.xlsx` is an output of that simulator, not a crop parameter source.

3. **Crop matrix is not an engine input.**
   - `crop_rotation_matrix.json` is generated by `task7_agronomy_matrix.py` from hand-written constants.
   - It uses `water_requirement_mm_per_season`, while Arya’s `RotationCandidate` uses `water_demand_mm`.
   - It lacks revenue, production cost, required K_sat, predicted erosion D_i, and non-host duration, which are needed by `solve_pareto_epsilon_constraint()` and the fiscal/WBC model.
   - `docs/ai_core_readiness.md:98` explicitly says it cannot be fed directly to Arya’s candidate.

4. **Two nitrogen models conflict.**
   - Arya: `fiscal_actuarial.py:23–36` uses 6.25 t/ha biomass, 3.8% N, 76% Ndfa, 42% harvest export, 11% denitrification, 7% leaching, 68% mineralization, 46% urea N, 79.98% NUE, 163 kg/ha cap.
   - Arief: `nitrogen_dynamics.py:11–47` uses 2.5 t/ha soybean yield, 1.5 residue ratio, 2.5% N, 75–80% fixation, 40% mineralization.
   - `docs/project_file_inventory.md:194` (KI-10) marks this as High and requires agronomic validation.

5. **No scientific names, categories, or stable crop IDs exist.**
   - Search found no `scientific_name`, `Oryza`, `Glycine`, `Vigna`, `Sorghum`, or `Allium` records.
   - Crop names are scenario labels, not registry entities.
   - No crop category (cereal, legume, vegetable, cover crop) is defined in code.

6. **No planting calendar or suitability data exists.**
   - No planting-window, harvest-window, growing-duration, pH, texture, drainage, salinity, or slope-suitability parameter was found.
   - Water balance uses fixed day ranges, not crop calendars.

7. **No yield model or price data exists.**
   - `expected_yield_ton_per_ha` exists only as a hand-written constant in Arief’s matrix; it is not used by an engine.
   - No crop price, crop-level production cost, or yield-response model exists.
   - Arya’s candidate revenue/cost values are hardcoded demo values.

8. **The contract does not carry a crop parameter registry.**
   - `contracts/grid_cell_contract.schema.json:129–181` defines seven rotation-scenario fields, not crop parameters.
   - `contracts/grid_cell_contract_v1.1.schema.json:39` defines `rotation_scenarios` only as an array.
   - `grid_cell_contract_sample.json` is not valid JSON; it cannot be used as a schema or data source.
   - `docs/contract_governance.md:12–29, 43–45` requires all-team agreement for field names, types, units, and nested structures.

9. **Parameters defined but not used:**
   - `crop_rotation_matrix.json`: water requirement, expected yield, soil moisture threshold, drought vulnerability. No module imports this file.
   - `nitrogen_balance_output.json`: output only; no module imports it.
   - `RotationCandidate.non_host_duration_days`: defined in the dataclass, but `solve_pareto_epsilon_constraint()` does not use it; `compute_fiscal_and_autp_clearing()` defaults to 65; `build_grid_cell_contract_json()` does not pass candidate-specific non-host days.
   - UI scores `waterScore`, `soilScore`, `pestScore`: used only for UI display; not engine inputs.
   - `water_balance_banyumas.xlsx`: output artifact; not consumed by any engine.

10. **Parameters used in calculations:**
    - Arya N constants: used by `compute_three_tier_nitrogen_ledger()`.
    - Fiscal constants: used by `compute_fiscal_and_autp_clearing()`.
    - WBC parameters: used by `compute_wbc_nymph_survival_rate()`.
    - Kc/soil/initial moisture: used by the fixed `BanyumasWaterBalanceSimulator`.
    - Demo `RotationCandidate` values: used by the `__main__` Pareto demo, not by production data.
    - UI scores: used only by React UI.

---

## 4. Missing Parameter List

The following is the minimum set needed before a crop rotation evaluator can be implemented without inventing values. Units are proposed; values are intentionally absent.

### 4.1 Crop suitability evaluation

| Missing parameter | Why needed | Consumer | Expected unit | Available in repo? | Source required? |
|---|---|---|---|---|---|
| Crop identity and scientific name | Stable identity and source lookup | Registry, suitability, UI | string | No; only scenario labels | Yes |
| Crop category | Grouping and rule selection | Registry, suitability | enum | No | Yes |
| Soil texture suitability | Match crop to soil | Suitability evaluator | text/class | No | Yes |
| pH minimum/maximum | Match crop to soil chemistry | Suitability evaluator | pH | No | Yes |
| Drainage class tolerance | Waterlogging/root health | Suitability evaluator | enum | No | Yes |
| Slope maximum | Erosion/mechanization constraint | Suitability evaluator | degree | No | Yes |
| Salinity tolerance | Soil suitability | Suitability evaluator | dS/m or class | No | Yes |
| Temperature range | Crop suitability | Suitability evaluator | °C | No | Yes |
| Water availability requirement | Suitability/water constraint | Suitability/water evaluator | mm/season | No; Arief’s 800/1200/1050 are assumption-based | Yes |

### 4.2 Crop water requirement calculation

| Missing parameter | Why needed | Consumer | Expected unit | Available in repo? | Source required? |
|---|---|---|---|---|---|
| Growing duration per crop/variety | Stage lengths and calendar | Calendar/water evaluator | day | No | Yes |
| Kc by stage per crop/variety | ETc = ETo × Kc | Water requirement calculator | fraction | Only fixed demo Kc in `build_water_balance_banyumas.py` | Yes |
| Root depth per crop | Soil water reservoir | Water requirement calculator | mm | Only shared 1000 mm profile | Yes |
| Depletion fraction / allowable depletion | Irrigation scheduling | Water requirement calculator | fraction | No | Yes |
| Seasonal water requirement | Candidate `water_demand_mm` | Candidate builder/water evaluator | mm/season | Arief matrix is assumption-based and not used | Yes |
| Effective rainfall method | Net water demand | Water requirement calculator | mm | No | Yes |
| Irrigation efficiency | Net irrigation requirement | Water requirement calculator | fraction | No | Yes |
| Soil water holding parameters per soil | Water balance | Water evaluator | m³/m³ or mm | Only one assumed profile | Yes |

### 4.3 Growing-period and planting-calendar evaluation

| Missing parameter | Why needed | Consumer | Expected unit | Available in repo? | Source required? |
|---|---|---|---|---|---|
| Planting window start/end | Feasible planting date | Calendar evaluator | date | No | Yes |
| Harvest window | Rotation turnaround | Calendar evaluator | date | No | Yes |
| Crop duration and stage boundaries | Calendar and water stages | Calendar evaluator | day | No | Yes |
| Fallow duration | Scenario A and pest break | Calendar evaluator | day | Only demo `non_host_duration_days`; not crop-specific | Yes |
| Turnaround/land preparation period | Double-cropping feasibility | Calendar evaluator | day | No | Yes |
| Photoperiod/temperature constraints | Crop suitability/calendar | Calendar evaluator | hour/°C | No | Yes |

### 4.4 Nitrogen-related evaluation

| Missing parameter | Why needed | Consumer | Expected unit | Available in repo? | Source required? |
|---|---|---|---|---|---|
| Ndfa fraction per crop/variety | Biological N fixation | N evaluator | fraction | Only fixed soybean values | Yes |
| Dry biomass / residue ratio | N input from residues | N evaluator | t/ha | Arief assumptions only | Yes |
| Tissue N fraction | N in residue | N evaluator | fraction | Arya 0.038; Arief 0.025; conflicting | Yes; choose model |
| Harvest N export | N removed | N evaluator | fraction | Arya 0.42 | Yes |
| Denitrification/leaching/mineralization | N losses/availability | N evaluator | fraction | Arya values; no citation | Yes |
| Soil initial N / indigenous N | N balance baseline | N evaluator | kg/ha | No | Yes |
| N response/yield relationship | Yield effect | Yield/N evaluator | kg yield per kg N or response curve | No | Yes |
| Inoculant/soil biological assumptions | Fixation feasibility | N evaluator | text/fraction | No | Yes |

### 4.5 Pest-cycle interruption evaluation

| Missing parameter | Why needed | Consumer | Expected unit | Available in repo? | Source required? |
|---|---|---|---|---|---|
| Crop host status for WBC | Non-host rotation | Pest evaluator | enum | No | Yes |
| Pest life cycle / survival parameters | Population model | Pest evaluator | day / fraction | Only WBC 28-day assumption | Yes |
| Non-host duration per crop | Break length | Pest evaluator | day | Only demo values | Yes |
| Adoption ratio / landscape synchrony | Migration/reinfestation | Pest evaluator | fraction | Only fiscal method input; no data | Yes |
| Pest pressure / BPH burden | Candidate constraint | Pest evaluator | 0–1 index | Demo values only | Yes |
| Natural enemy / refuge parameters | Realistic suppression | Pest evaluator | various | No | Yes |

### 4.6 Yield and financial evaluation

| Missing parameter | Why needed | Consumer | Expected unit | Available in repo? | Source required? |
|---|---|---|---|---|---|
| Yield per crop/variety/management | Revenue and candidate net margin | Yield/financial evaluator | t/ha | Arief matrix constants only; no citation | Yes |
| Yield response to water/N | Scenario evaluation | Yield evaluator | response function | No | Yes |
| Farm-gate price | Revenue | Financial evaluator | IDR/kg | No | Yes |
| Production cost per crop | Net margin | Financial evaluator | IDR/ha | Only aggregate demo candidates | Yes |
| Subsidy/adoption parameters | Fiscal evaluation | Fiscal evaluator | IDR/kg; fraction | Arya constants only | Yes |
| AUTP parameters | Insurance evaluation | Fiscal/AUTP evaluator | IDR/ha; probability | Arya constants only | Yes |
| Cluster area / adoption | Scaling fiscal result | Fiscal evaluator | ha; fraction | Arya 11,000 ha assumption | Yes |
| SOC change | `RotationCandidate.soc_change_ton_ha` | Soil/rotation evaluator | t/ha | Demo values only; no model | Yes |

### 4.7 Scenario-specific gaps

| Scenario | Existing support | Missing for a real evaluation |
|---|---|---|
| **A — Existing crop rotation** | Fixed water-balance scenario A; demo `RotationCandidate` A; UI static A | Actual baseline calendar/area/yield/water/fertilizer/cost; verified fallow duration; SOC/erosion/pest baseline; data for existing practice |
| **B — Water conservation & pest-cycle interruption** | Fixed water-balance scenarios B/C; WBC survival formula; UI static B/C | General crop water requirement; Kc/root depth per crop; planting calendar; K_sat/drainage constraints; pest host/population model; yield/economics; real weather/soil data |
| **C — Nitrogen fixation & financial potential** | Arya N ledger; Arief N model/output; fiscal/AUTP; Pareto solver; UI static C | Single agreed N model; crop-specific N fixation/mineralization; soil N; yield response; crop prices/costs; adoption/cluster data; integration to `RotationCandidate` and contract |

---

## 5. Proposed Registry Schema

### 5.1 Format recommendation

Use a **combination**:

1. **JSON Schema (Draft 2020-12)** for the external file format and validation.
2. **JSON data files** per crop, versioned in Git.
3. **Python frozen dataclasses** for internal use, following the style already used in `src/models/land_cover.py` (`@dataclass(frozen=True, slots=True)`).
4. **`jsonschema`** for validation; it is already available in the project environment (`docs/ai_core_readiness.md:42`).

Do **not** use a database or a new ML model for the first version. A Git-versioned JSON registry is auditable and reviewable.

### 5.2 Proposed file layout (not created in this task)

```text
contracts/
  crop_parameter_registry.schema.json       # proposed schema
data/
  registry/
    index.json                              # crop ids, versions, record status
    units.json                              # unit vocabulary
    sources.json                            # source/citation registry
    crops/
      padi.json
      kedelai.json
      kacang_hijau.json
      sorghum.json
      bawang_merah.json
      legum.json
src/
  registry/
    models.py                               # dataclasses, no formulas
    loader.py                               # JSON + schema validation
```

These paths are a proposal only. No files were created except this audit report.

### 5.3 Core record structure

```text
CropRegistry
  ├── schema_version
  ├── registry_version
  ├── units[]            (UnitRecord)
  ├── sources[]          (SourceRecord)
  └── crops[]            (CropRecord)

CropRecord
  ├── crop_id
  ├── common_name
  ├── scientific_name
  ├── category
  ├── variety
  ├── synonyms[]
  ├── region
  ├── parameters
  │   ├── water
  │   ├── root
  │   ├── nitrogen
  │   ├── calendar
  │   ├── suitability
  │   ├── pest
  │   └── yield_finance
  ├── record_status
  ├── verified_parameter_count
  ├── sources[]
  └── notes

ParameterValue
  ├── value
  ├── unit
  ├── status
  ├── source_id
  ├── source_locator
  ├── required_for[]
  ├── used_by[]
  ├── usage_status
  ├── confidence
  └── notes

SourceRecord
  ├── source_id
  ├── type
  ├── citation
  ├── url
  ├── dataset
  ├── version
  ├── accessed
  ├── license
  └── quality

UnitRecord
  ├── unit_id
  ├── symbol
  ├── dimension
  └── description
```

### 5.4 Field definitions

#### Crop identity

| Field | Type | Required | Notes |
|---|---|---|---|
| `crop_id` | string | yes | Stable slug; must be unique; no display-name-only IDs |
| `common_name` | string | yes | Name used in project |
| `scientific_name` | string/null | yes | Null until sourced; do not invent |
| `category` | enum/null | yes | Null until sourced; do not infer from name |
| `variety` | string/null | no | e.g., named variety only if sourced |
| `synonyms` | array[string] | no | Local names |
| `region` | string/null | yes | e.g., Banyumas only if source/scope confirms |
| `record_status` | enum | yes | `complete`, `incomplete`, `conflicting`, `deprecated` |

#### Parameter value

| Field | Type | Required | Notes |
|---|---|---|---|
| `value` | number/string/array/null | yes | `null` when missing; never use zero as a default |
| `unit` | string | yes | Must reference `UnitRecord`; dates use `ISO-8601 date` |
| `status` | enum | yes | See status vocabulary below |
| `source_id` | string/null | yes | Required non-null for verified values |
| `source_locator` | string/null | no | Page/table/row/URL fragment |
| `required_for` | array[string] | yes | Capabilities that need this parameter |
| `used_by` | array[string] | yes | Existing modules that consume it; empty if none |
| `usage_status` | enum | yes | `used_in_calculation`, `defined_not_used`, `demo_only`, `ui_only`, `not_used` |
| `confidence` | enum | no | `high`, `medium`, `low`, `none`; qualitative only |
| `notes` | string | no | Explain assumptions/conflicts |

#### Status vocabulary

- `verified` — traceable external source and team review; **none found in current repository**.
- `assumption_based` — present in code/JSON but no citation.
- `synthetic` — generated by a simulator/random process.
- `hardcoded_demo` — fixed demo candidate/UI value.
- `unverified` — value exists but provenance is unclear.
- `missing` — no value exists.
- `requires_source` — parameter is required, but no value/source exists.
- `conflicting` — multiple sources use incompatible values/models.
- `deprecated` — retained for history but not used.

#### Source record

| Field | Type | Required | Notes |
|---|---|---|---|
| `source_id` | string | yes | Stable ID |
| `type` | enum | yes | `peer_reviewed`, `official_dataset`, `extension_guideline`, `project_assumption`, `synthetic`, `unknown` |
| `citation` | string/null | yes | Full citation or exact document reference; null only for assumptions/synthetic |
| `url` | string/null | no | DOI/URL if available |
| `dataset` | string/null | no | Dataset/product name |
| `version` | string/null | no | Dataset/document version |
| `accessed` | string/null | no | ISO date |
| `license` | string/null | no | License/attribution |
| `quality` | enum | yes | `high`, `medium`, `low`, `unknown` |

#### Unit record

| Field | Type | Required | Notes |
|---|---|---|---|
| `unit_id` | string | yes | Stable ID, e.g. `mm`, `mm_per_day`, `kg_per_ha` |
| `symbol` | string | yes | Display symbol |
| `dimension` | string | yes | length, mass, time, fraction, temperature, currency, etc. |
| `description` | string | yes | Human-readable definition |

### 5.5 Validation rules

1. Unknown top-level or parameter fields are rejected (`additionalProperties: false`) until a schema version adds them.
2. A parameter with `value: null` must have `status` `missing` or `requires_source`; it cannot be `verified`.
3. A parameter with `status: verified` must have a non-null `source_id` and a source record with a citation/reference.
4. A parameter with `status: assumption_based`, `synthetic`, or `hardcoded_demo` must not be used as production input without an explicit override/decision.
5. `unit` is required for every non-identity parameter; no implicit units.
6. `crop_id` values must be unique; `source_id` references must resolve; `unit` references must resolve.
7. Duplicate/conflicting records for the same crop and parameter are rejected or flagged `conflicting`.
8. A missing required parameter must cause `insufficient_parameters` in downstream evaluators; no default Kc, yield, price, N, or water value may be inserted.
9. `record_status: complete` requires all parameters required for the declared capabilities to have non-null, sourced values.
10. Schema/registry/source versions are explicit; changes require review under `docs/contract_governance.md` where they affect `grid_cell_contract.json`.

---

## 6. Example Registry Record

**Important:** no crop parameter in the repository qualifies as verified. Therefore this is a **schema example with placeholders**, not a production record. No value below is invented; all values are `null` with explicit missing/requires-source status.

```json
{
  "schema_version": "0.1.0-proposed",
  "registry_version": "0.1.0-proposed",
  "crop_id": "padi",
  "common_name": "Padi",
  "scientific_name": null,
  "category": null,
  "variety": null,
  "synonyms": [],
  "region": "Banyumas",
  "identity_status": "observed_in_repository_labels",
  "identity_source": [
    "web-app/src/model.js:4-31",
    "external/ariefs_workresult/crop_rotation_matrix.json"
  ],
  "parameters": {
    "growing_duration_days": {
      "value": null,
      "unit": "day",
      "status": "missing",
      "source_id": null,
      "source_locator": null,
      "required_for": ["planting_calendar", "crop_water_requirement"],
      "used_by": [],
      "usage_status": "not_used",
      "confidence": "none",
      "notes": "No verified crop duration found in repository."
    },
    "kc_initial": {
      "value": null,
      "unit": "fraction",
      "status": "requires_source",
      "source_id": null,
      "source_locator": null,
      "required_for": ["crop_water_requirement"],
      "used_by": ["external/aryas_workresult/build_water_balance_banyumas.py"],
      "usage_status": "demo_only",
      "confidence": "none",
      "notes": "A fixed demo Kc exists for scenario A, but it is hardcoded and not crop-record verification."
    },
    "root_depth_mm": {
      "value": null,
      "unit": "mm",
      "status": "requires_source",
      "source_id": null,
      "source_locator": null,
      "required_for": ["crop_water_requirement", "suitability"],
      "used_by": ["external/aryas_workresult/build_water_balance_banyumas.py"],
      "usage_status": "demo_only",
      "confidence": "none",
      "notes": "The water balance uses one shared 1000 mm profile; this is not a per-crop root depth."
    },
    "water_requirement_mm_season": {
      "value": null,
      "unit": "mm/season",
      "status": "requires_source",
      "source_id": null,
      "source_locator": null,
      "required_for": ["crop_water_requirement", "rotation_candidate"],
      "used_by": [],
      "usage_status": "defined_not_used",
      "confidence": "none",
      "notes": "A hand-written 800 mm value exists in crop_rotation_matrix.json but has no citation and is not consumed by an engine."
    },
    "n_fixation_kg_ha": {
      "value": null,
      "unit": "kg/ha",
      "status": "missing",
      "source_id": null,
      "source_locator": null,
      "required_for": ["nitrogen_evaluation", "fiscal_evaluation"],
      "used_by": [],
      "usage_status": "not_used",
      "confidence": "none",
      "notes": "Arya and Arief provide conflicting soybean-specific N models; no agreed crop-level fixation value exists."
    },
    "expected_yield_t_ha": {
      "value": null,
      "unit": "t/ha",
      "status": "requires_source",
      "source_id": null,
      "source_locator": null,
      "required_for": ["yield_evaluation", "financial_evaluation"],
      "used_by": [],
      "usage_status": "defined_not_used",
      "confidence": "none",
      "notes": "A hand-written 6.5 t/ha value exists for a scenario, not for a verified padi record."
    },
    "planting_window_start": {
      "value": null,
      "unit": "ISO-8601 date",
      "status": "missing",
      "source_id": null,
      "source_locator": null,
      "required_for": ["planting_calendar"],
      "used_by": [],
      "usage_status": "not_used",
      "confidence": "none",
      "notes": "No planting calendar found."
    },
    "planting_window_end": {
      "value": null,
      "unit": "ISO-8601 date",
      "status": "missing",
      "source_id": null,
      "source_locator": null,
      "required_for": ["planting_calendar"],
      "used_by": [],
      "usage_status": "not_used",
      "confidence": "none",
      "notes": "No planting calendar found."
    },
    "ph_min": {
      "value": null,
      "unit": "pH",
      "status": "missing",
      "source_id": null,
      "source_locator": null,
      "required_for": ["suitability"],
      "used_by": [],
      "usage_status": "not_used",
      "confidence": "none",
      "notes": "No soil pH suitability parameter found."
    },
    "host_status_wbc": {
      "value": null,
      "unit": "enum",
      "status": "missing",
      "source_id": null,
      "source_locator": null,
      "required_for": ["pest_cycle_evaluation"],
      "used_by": [],
      "usage_status": "not_used",
      "confidence": "none",
      "notes": "No crop host-status matrix found; WBC formula is pest-specific, not crop-specific."
    }
  },
  "record_status": "incomplete",
  "verified_parameter_count": 0,
  "sources": [],
  "notes": "Schema example only. No verified agronomic values exist in the repository. Do not use this record for calculations."
}
```

The omitted parameter sections (`water`, `root`, `nitrogen`, `calendar`, `suitability`, `pest`, `yield_finance`) should follow the same `ParameterValue` object. Missing values remain `null`; no synthetic or hardcoded value should be copied into a verified record.

---

## 7. Integration Architecture

### 7.1 Target flow

```text
NASA / Arief data + H3 cell context
        │
        ▼
CellContextAdapter
  - H3, land cover, soil, climate
  - PVRS output
  - BF-EHSI output
  - fixed/parameterized water-balance context
  - data status/QA
        │
        ▼
CropParameterRegistry
  - crop/variety records
  - water/Kc/root/calendar/suitability/N/pest/yield/finance
  - source/status/units per parameter
        │
        ▼
CropSuitabilityEvaluator
PlantingCalendarEvaluator
CropWaterRequirementCalculator
        │
        ▼
RotationCandidateBuilder (rule-based, no ML)
  - enumerate sequences/calendars
  - validate suitability/windows
  - fill RotationCandidate or return insufficient_parameters
        │
        ▼
RotationEvaluator
  ├── PVRSEngine           → cell stress context/constraint
  ├── BFEHSIEngine         → fallow/erosion context/constraint
  ├── Water balance        → water demand/irrigation
  ├── N ledger/fiscal      → N displaced, subsidy, AUTP
  └── candidate metrics
        │
        ▼
ParetoAdapter
  └── CyberKatamFiscalActuarialEngine.solve_pareto_epsilon_constraint()
        │
        ▼
ContractAssembler + API + UI
  - rotation_scenarios
  - Pareto front/selected
  - XAI, data status, abstention
```

### 7.2 Reuse map — do not duplicate existing engines

| Need | Reuse | Do not duplicate |
|---|---|---|
| PVRS | `external/aryas_workresult/pvrs_engine.py::PVRSEngine` | Z-score/sigmoid/optical-lag formulas |
| BF-EHSI/MBSI/bare fraction | `external/aryas_workresult/bf_ehsi_engine.py::BFEHSIEngine` | MBSI/BF-EHSI/D_i formulas |
| Fixed water balance | `external/aryas_workresult/build_water_balance_banyumas.py::BanyumasWaterBalanceSimulator` | New water-balance engine |
| N ledger/WBC/fiscal/AUTP | `external/aryas_workresult/fiscal_actuarial.py::CyberKatamFiscalActuarialEngine` | Ledger/clearing formulas |
| Pareto optimizer | `fiscal_actuarial.py::solve_pareto_epsilon_constraint` | Dominance/epsilon logic |
| Candidate dataclass | `fiscal_actuarial.py::RotationCandidate` | A parallel candidate schema |
| Contract validation | `src/contracts` and `contracts/grid_cell_contract.schema.json` | Ad-hoc validation |

### 7.3 Mapping registry outputs to `RotationCandidate`

| `RotationCandidate` field | Should come from | Current status |
|---|---|---|
| `scenario_id` | Candidate builder | Missing |
| `crop_sequence` | Candidate builder | Missing (only demo/hand-written) |
| `non_host_duration_days` | Calendar/pest evaluator | Partial (demo values; not used by solver) |
| `water_demand_mm` | Water requirement calculator / water balance | Missing general calculator; demo values only |
| `n_fertilizer_displaced_kg_ha` | N ledger | Partial; two conflicting models; demo values |
| `soc_change_ton_ha` | SOC model | Missing; demo values only |
| `bph_burden_index` | Pest evaluator | Partial; demo values only |
| `gross_revenue_idr_ha` | Yield × price | Missing; demo revenue only |
| `production_cost_idr_ha` | Crop cost model | Missing; demo aggregate cost only |
| `required_ksat_mm_day` | Soil/water suitability | Partial; demo values; one shared soil profile |
| `predicted_erosion_di` | BF-EHSI | Engine exists; no adapter to candidate |

### 7.4 Contract gap

`contracts/grid_cell_contract.schema.json:129–181` supports only:

- `id`
- `crop_sequence`
- `water_demand_mm`
- `n_fertilizer_displaced_kg`
- `soc_change_ton`
- `bph_risk_score`
- `net_margin_idr`

It does **not** carry:

- `non_host_duration_days`
- `required_ksat_mm_day`
- `predicted_erosion_di`
- `gross_revenue_idr_ha`
- `production_cost_idr_ha`
- parameter provenance/status
- crop/version identifiers

`contracts/grid_cell_contract_v1.1.schema.json:39` defines `rotation_scenarios` only as an untyped array. `grid_cell_contract_sample.json` is invalid and cannot be used to fill the gap. Any extension must follow `docs/contract_governance.md` and be agreed by all teams.

### 7.5 Interface additions required

- `CropRegistryLoader.load(crop_id) -> CropRecord`
- `CropParameterResolver.get(crop_id, parameter_id) -> ParameterValue`
- `CropSuitabilityEvaluator.evaluate(crop, cell_context) -> SuitabilityResult`
- `PlantingCalendarEvaluator.evaluate(crop, season) -> CalendarResult`
- `CropWaterRequirementCalculator.evaluate(crop, cell_context, calendar) -> WaterRequirementResult`
- `RotationCandidateBuilder.build(sequence, calendar, cell_context) -> CandidateBuildResult` (`RotationCandidate` or `insufficient_parameters`)
- `RotationEvaluator.evaluate(candidate) -> RotationEvaluation`
- `ParetoAdapter.optimize(evaluations) -> ParetoResult`

No implementation was created in this task.

---

## 8. Recommended Next Implementation Steps

1. **Approve the scope and status vocabulary.**
   - Decide which crops/varieties are in scope: Padi, Kedelai Anjasmoro, Kacang Hijau Vima-1, Sorghum, Bawang Merah, Legum/Cover Crop, or a smaller set.
   - Confirm that “Bera” is a fallow state, not a crop record.
   - Approve the `verified` / `assumption_based` / `synthetic` / `missing` / `requires_source` / `conflicting` vocabulary.

2. **Create the schema and loader only.**
   - Add a proposed schema, empty registry, source registry, unit registry, and loader tests.
   - Do not add crop values yet.
   - Enforce `value: null` + `status` for missing parameters; no defaults.

3. **Build the source and unit registries.**
   - Every parameter will reference a `source_id` and `unit_id`.
   - No source may be invented; `project_assumption` and `synthetic` are valid source types but cannot be labeled `verified`.

4. **Reconcile existing values.**
   - Record Arya’s constants in `fiscal_actuarial.py` as `assumption_based`/`unverified`.
   - Record Arief’s crop matrix and N output as `assumption_based`; note they are not used.
   - Record water-balance Kc/soil values as `hardcoded`/`synthetic`; note they are fixed-scenario only.
   - Mark the Arya-vs-Arief N conflict as `conflicting`; do not choose silently.

5. **Obtain agronomic sources for the minimum crop set.**
   - Source each parameter from an approved official/extension/peer-reviewed reference.
   - Populate only parameters that have a citation; leave the rest `null`/`requires_source`.

6. **Implement evaluators incrementally.**
   - Suitability → calendar → water requirement → candidate builder.
   - Reuse `BanyumasWaterBalanceSimulator` by parameterization, not by writing a second water-balance engine.
   - Reuse `PVRSEngine` and `BFEHSIEngine` as cell-level context/constraints; do not treat them as crop-growth models.

7. **Connect to `RotationCandidate` and the Pareto solver.**
   - Fill `RotationCandidate` only when all required fields are sourced.
   - Use `solve_pareto_epsilon_constraint()` unchanged.
   - Return `insufficient_parameters` with a field list when data is incomplete.

8. **Resolve the contract gap before UI/API integration.**
   - Propose fields for non-host duration, required K_sat, erosion D_i, revenue, cost, source/status, and crop/version.
   - Follow `docs/contract_governance.md`; do not change `grid_cell_contract.json` unilaterally.

9. **Add tests.**
   - Registry schema validation, unit/source resolution, missing-value handling, duplicate IDs.
   - Candidate builder: missing parameters fail closed.
   - Pareto wrapper: dominance, infeasible filtering, epsilon qualification, empty feasible set.
   - No synthetic value may pass as verified.

10. **Only then integrate API/UI.**
    - Current UI is static; do not expose registry values as operational recommendations.
    - Show data status/provenance and abstention in the UI.

---

## 9. Open Questions Requiring Agronomic or Team Decisions

1. Which crops and varieties are officially in scope?
2. Is “Bera” a fallow state, a cover-crop system, or both?
3. Which source hierarchy is approved: official extension materials, peer-reviewed papers, field trials, or a combination?
4. Which Kc stage system and growing-duration source should be used?
5. Which water-balance method is authoritative: FAO-56, a local trial, or the existing simulator after parameterization?
6. Which nitrogen model is authoritative: Arya’s three-tier ledger or Arief’s soybean residue model?
7. Should the registry be variety-specific or species-level first?
8. Which crop price, production cost, and yield sources are acceptable for Banyumas?
9. Which pest model and host-status matrix should be used beyond WBC?
10. Which soil suitability thresholds are approved, and for which soil map?
11. Which contract version/fields should carry optimizer constraints?
12. How should conflicting values be resolved and recorded?
13. Who owns registry approval and updates?
14. Should `rotation_scenarios` remain `minItems: 0`, or must a recommendation contain at least one scenario?
15. Should the registry live under `data/registry/`, `contracts/`, or `src/registry/`?

---

## 10. Bottom Line

**What already exists:**

- PVRS and BF-EHSI physics engines.
- A fixed three-scenario water-balance simulator and Excel output.
- Arya’s N ledger, WBC survival formula, fiscal/AUTP clearing, and generic Pareto solver.
- `RotationCandidate` dataclass.
- A hand-written three-scenario crop matrix and soybean N output from Arief.
- Static UI strategies and an illustrative Pareto chart.

**What is missing:**

- A centralized crop parameter registry.
- Scientific names, crop categories, stable crop IDs.
- Growing duration/calendar, per-crop Kc/root depth, suitability limits.
- General crop water requirement calculation.
- Agreed crop-specific N fixation and soil N data.
- Yield model, crop prices, crop-level costs.
- Pest host/population model.
- Crop-level SOC model.
- Candidate generator, crop evaluators, and engine-to-web adapters.
- Verified external citations for existing constants.
- Contract fields for optimizer constraints and registry provenance.
- Tests for the registry and rotation evaluator.

**What needs verification from the team:**

- Crop/variety list and scenario definitions.
- All agronomic constants and their sources.
- Arya vs Arief N model.
- Kc/water-balance assumptions.
- Yield, price, cost, subsidy, and AUTP assumptions.
- WBC/pest assumptions.
- Contract schema extension.
- Registry ownership and approval workflow.

**Is the repository ready for registry implementation?**

- **Schema/loader skeleton:** yes, can start now.
- **Production registry content:** no; there are no verified crop parameter values.
- **Crop rotation integration:** no; suitability, calendar, water requirement, candidate generation, and evaluators do not exist yet.

The correct next step is to implement the registry structure and validation with **explicit missing/requires-source values**, then source and approve agronomic data before any calculation uses it. No default or synthetic value should be silently promoted to a verified crop parameter.
