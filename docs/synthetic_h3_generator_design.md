# Synthetic H3 Generator — Design and Provenance

**Status: SYNTHETIC TEST FIXTURE — NOT NASA DATA**
**Task:** Task 2 — Synthetic H3 Generator (CYBER-KATAM AI Core, Aqila)
**Module:** `src/engines/synthetic_h3_generator.py`
**Tests:** `tests/test_synthetic_h3_generator.py`
**Output:** `data/mock/banyumas_h3_synthetic.geojson` (gitignored, generated)
**Contract:** `contracts/grid_cell_contract.schema.json` (PROVISIONAL)

> The generator creates deterministic test geometry and placeholder attributes.
> It does not query NASA, does not implement a physics engine, does not produce
> an agronomic recommendation, and does not prove any field observation.

---

## 1. Purpose and scope

### In scope

- Read the actual Banyumas ROI GeoJSON.
- Generate valid H3 resolution-9 cells with `h3.geo_to_cells`.
- Select exactly 1,000 cells deterministically and spatially across the ROI.
- Produce valid GeoJSON Polygons in longitude/latitude order.
- Attach clearly labelled synthetic contract fixtures that pass Task 1's
  provisional validator.
- Record explicit provenance and a per-variable manifest.
- Provide a small CLI and a reusable Python API.

### Out of scope

- NASA data extraction or Earth Engine calls.
- A verified paddy-field mask or land-cover classification.
- PVRS/BF-EHSI/fiscal calculations.
- Imputation of missing observations.
- Agronomic, rotation, XAI, or fiscal recommendations.
- Replacing the received `banyumas_h3_precomputed.geojson`.
- Modifying Arya's or Arief's source files.

---

## 2. Input ROI and its limitations

Input:

`data/boundaries/banyumas_paddy_roi.geojson`

Measured properties:

| Property | Value |
|---|---|
| GeoJSON type | `FeatureCollection` with exactly one `Feature` |
| Geometry | `Polygon` |
| Ring | one closed 5-position ring |
| Longitude range | 108.92 to 109.38 E |
| Latitude range | -7.60 to -7.25 S |
| Coordinate order | `[longitude, latitude]` |
| Candidate H3 res-9 cells | **19,332** |
| H3 res-7 parent groups | **438** |
| Is this a paddy mask? | **No** — it is a rectangular bounding box |
| Is this an administrative boundary? | **No** |
| Verified land cover? | **No** |

The file was written as a fallback bbox in Arief's GEE scripts. It must not be
used to claim that a cell is paddy field. The generated fixture therefore uses
`land_cover: "unverified"`.

The generator does not clip H3 cell polygons to the ROI boundary. It follows
H3 v4 `geo_to_cells` center-containment semantics: a cell is a candidate when its
centre falls inside the ROI. Cell boundaries may cross the bbox edge.

---

## 3. H3 generation method

- Library: `h3==4.1.2`.
- API: `h3.geo_to_cells(roi_geometry, 9)`.
- Resolution: **9**.
- Every returned index is checked with `h3.is_valid_cell`.
- Every returned index is checked with `h3.get_resolution(...) == 9`.
- Candidate indexes are de-duplicated and sorted.
- Geometry uses `h3.cell_to_boundary(cell)`, which returns `(latitude, longitude)`.
  Each position is converted to GeoJSON `[longitude, latitude]`.
- Each ring is closed by appending the first position when necessary.
- Geometry generation is independent of the synthetic-attribute seed.

If the ROI produces fewer than the requested number of cells, generation stops
with `InsufficientCellsError`. The generator never expands the ROI, generates
outside it, duplicates cells, or silently substitutes another region.

---

## 4. Exact 1,000-cell selection strategy

Method name:

`deterministic_stratified_round_robin_by_h3_res7_parent`

Algorithm:

1. Sort all candidate cells by H3 index.
2. Group cells by `h3.cell_to_parent(cell, 7)`.
3. Sort parent groups by H3 index and cells within each group by H3 index.
4. Take one cell from each parent group per round, in sorted group order.
5. Stop at exactly 1,000 cells.
6. Sort the final selected list by H3 index for deterministic output order.

For the current ROI:

- 438 res-7 parent groups exist.
- Round 1: 438 cells.
- Round 2: 438 cells (876 total).
- Round 3: 124 cells to reach 1,000.
- Therefore **all 438 res-7 parents are represented**, and 124 of them contribute
  a third cell.

This avoids selecting a small contiguous corner that merely sorts first. The
selection is independent of the random seed.

---

## 5. Synthetic variable definitions

The authoritative machine-readable manifest is embedded in each output under
`FeatureCollection.synthetic_variable_manifest`. The table below summarises it.

Legend:

- **source-like** — resembles a satellite-derived variable, but is synthetic.
- **derived placeholder** — in real operation this would come from Arya's engine;
  here it is only a schema-compatible test value.
- **constant placeholder** — a fixed test value, not a model output.
- **test-only** — must not be used for analysis or recommendations.

| Field | Meaning | Unit | Classification | Generation | Evidence / limitation |
|---|---|---|---|---|---|
| `h3_index` | H3 res-9 cell identity | none | geometry identity | `geo_to_cells` + deterministic selection | Valid H3 cell; not a paddy parcel |
| `h3_parent_res7` | H3 res-7 parent | none | geometry derived | `cell_to_parent` | Consistency only |
| `contract_version` | Contract version | none | constant | `"1.0"` | Schema is provisional |
| `physical_indicators.PVRS` | Pre-Visual Root-Stress Score placeholder | dimensionless [0,1] | derived placeholder | uniform over schema bounds | **NOT computed by Arya's engine** |
| `physical_indicators.BF_EHSI` | Bare-Field Erosion/Heat Shock placeholder | dimensionless [0,2.5] | derived placeholder | uniform over schema bounds | **NOT computed by Arya's engine** |
| `physical_indicators.SMAP_wetness` | Root-zone soil moisture placeholder | m3/m3 [0,1] | source-like | uniform over schema bounds | Not a SMAP observation; no aggregation claim |
| `physical_indicators.ECOSTRESS_ESI` | Evaporative Stress Index placeholder | dimensionless [0,1] | source-like | uniform over schema bounds | Not ECOSTRESS; ESI source not selected |
| `physical_indicators.LST_anomaly` | LST anomaly placeholder | °C | derived placeholder | constant `0.0` | No schema bound; not a modeled anomaly |
| `physical_indicators.HLS_BSI` | Bare-soil index placeholder | dimensionless [-1,1] | source-like | uniform over schema bounds | Not HLS; `HLS_BSI` vs `MBSI` unresolved |
| `physical_indicators.HLS_NDVI` | NDVI placeholder | dimensionless [-1,1] | source-like | uniform over schema bounds | Not HLS; no QA/cloud mask |
| `physical_indicators.GPM_rain_7d` | Seven-day rainfall placeholder | mm | source-like | uniform over arbitrary test cap [0,100] | Not GPM; 100 mm cap is not a threshold or distribution |
| `physical_indicators.SRTM_slope` | Slope placeholder | degrees [0,90] | source-like | uniform over schema bounds | Not SRTM; schema-constrained test values |
| `operational_flags.missing_observation` | Missing-observation flag | boolean | constant placeholder | `false` | Schema requires non-null indicators; nullable policy unresolved |
| `operational_flags.optical_lag_days` | Optical-lag placeholder | days [0,14] | derived placeholder | uniform integer | **NOT computed by PVRS** |
| `operational_flags.erosion_alert` | Erosion-alert placeholder | boolean | derived placeholder | uniform boolean | Not derived from BF-EHSI or D_i |
| `rotation_scenarios` | Rotation scenario list | n/a | test-only empty | `[]` | Scenario generation is out of Task 2 scope |
| `xai_decision_block.*` | Four XAI text fields | text | constant placeholder | Explicit "SYNTHETIC TEST FIXTURE" sentences | Not factual explanations |
| `fiscal_metrics.urea_subsidy_saved_idr` | Subsidy-saving placeholder | IDR/ha | derived placeholder | constant `0.0` | **NOT computed by Arya's fiscal engine** |
| `fiscal_metrics.autp_risk_reduction_pct` | AUTP risk-reduction placeholder | % | derived placeholder | constant `0.0` | **NOT computed by Arya's fiscal engine** |
| `system_state` | System state for UI testing | enum string | test-only pattern | deterministic cycle over all three enum values | Not a recommendation policy; both abstention spellings are test samples |

All values are schema-constrained or explicit test constants. No empirical
distribution, seasonal pattern, correlation, crop type, observation date, cloud
fraction, or missing-data frequency is invented.

---

## 6. Seed and reproducibility

- RNG: `numpy.random.default_rng(seed)`.
- Default seed: `20261114`.
- Seed is configurable through `GenerationConfig` and `--seed`.
- Same seed + same code + same ROI + same pinned environment → identical
  attributes and identical GeoJSON output.
- Different seed → different synthetic attributes, but **identical H3 indexes and
  identical geometry**.
- No global random state.
- No time-dependent or OS-dependent metadata.
- Attribute-generation call order is part of generator version `1.0.0`. Changing
  the order requires a version bump and new expected fixtures.

---

## 7. GeoJSON output structure

Top-level object:

```json
{
  "type": "FeatureCollection",
  "name": "CYBER_KATAM_SYNTHETIC_H3_1000",
  "is_synthetic": true,
  "data_source": "synthetic",
  "warnings": ["..."],
  "generator": {
    "name": "synthetic_h3_generator",
    "version": "1.0.0",
    "random_seed": 20261114,
    "h3_resolution": 9,
    "target_count": 1000,
    "candidate_count": 19332,
    "selected_count": 1000,
    "roi_source": "data/boundaries/banyumas_paddy_roi.geojson",
    "selection_method": "deterministic_stratified_round_robin_by_h3_res7_parent",
    "selection_details": {},
    "contract_schema": "contracts/grid_cell_contract.schema.json",
    "contract_schema_status": "PROVISIONAL",
    "contract_payloads_validated": true,
    "contracts_validated": 1000
  },
  "synthetic_variable_manifest": {},
  "features": []
}
```

Each feature:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[longitude, latitude], "..."]]
  },
  "properties": {
    "h3_index": "898d88b4903ffff",
    "is_synthetic": true,
    "data_source": "synthetic",
    "generator_name": "synthetic_h3_generator",
    "generator_version": "1.0.0",
    "random_seed": 20261114,
    "h3_resolution": 9,
    "roi_source": "data/boundaries/banyumas_paddy_roi.geojson",
    "selection_method": "deterministic_stratified_round_robin_by_h3_res7_parent",
    "selection_ordinal": 0,
    "land_cover": "unverified",
    "contract_schema": "contracts/grid_cell_contract.schema.json",
    "contract_schema_status": "PROVISIONAL",
    "contract": {}
  }
}
```

Design rules:

- GeoJSON coordinates are longitude/latitude (WGS84, RFC 7946 default).
- Polygon rings are closed.
- The strict contract payload is nested under `properties.contract`.
- Provenance fields are outside `properties.contract` because the contract schema
  rejects additional properties.
- `land_cover` is `"unverified"`; it is never `"Paddy Field"`.
- There is no `crs` member; RFC 7946 uses WGS84.
- Foreign members such as `generator`, `warnings`, and
  `synthetic_variable_manifest` are allowed by GeoJSON and are not part of the
  contract payload.

---

## 8. Contract compatibility

- The schema is loaded from `contracts/grid_cell_contract.schema.json`.
- Every generated contract is validated with Task 1's `ContractValidator`,
  including the opt-in provisional H3/parent semantic rules.
- The default CLI fails if any contract is invalid.
- Contract top-level keys are exactly the schema's properties.
- Required nested blocks are present.
- `rotation_scenarios` is `[]`, which is valid under the provisional
  `minItems: 0`.
- `h3_parent_res7` is present and correct.
- `missing_observation` is `false` because all indicators are populated.
- The generator does not add provenance to the contract object.
- The schema is **provisional** and is not modified by this task.

Known contract incompatibility recorded, not worked around:

> The provisional schema requires nine non-null physical indicators. Real
> satellite missingness cannot be represented without a ratified nullable policy.
> The generator therefore keeps all indicators populated and sets
> `missing_observation` to `false`. This is a fixture limitation, not a
> missing-data policy.

---

## 9. What is synthetic versus derived

| Category | Examples | Status in this fixture |
|---|---|---|
| Geometry | H3 indexes, polygons | Mathematically generated from the actual ROI bbox |
| Source-like values | SMAP, ECOSTRESS ESI, HLS NDVI/BSI, GPM, SRTM | Synthetic placeholders; not observations |
| Derived indicators | PVRS, BF-EHSI | Synthetic placeholders; **not** engine output |
| Operational flags | optical lag, erosion alert | Synthetic placeholders; **not** engine output |
| XAI text | four explanation fields | Constant test strings; not factual |
| Fiscal metrics | subsidy saving, AUTP reduction | Zero placeholders; **not** engine output |
| System state | recommendation/abstention enum | Test cycle; not a policy decision |

No formula from `external/aryas_workresult/` is copied or reimplemented.

---

## 10. How to run

Default 1,000-cell generation:

```powershell
.venv\Scripts\python.exe -m src.engines.synthetic_h3_generator
```

Custom seed and output:

```powershell
.venv\Scripts\python.exe -m src.engines.synthetic_h3_generator `
  --seed 42 `
  --output data/mock/banyumas_h3_synthetic.geojson
```

CLI options:

| Option | Default | Notes |
|---|---|---|
| `--roi` | `data/boundaries/banyumas_paddy_roi.geojson` | Actual ROI path |
| `--output` | `data/mock/banyumas_h3_synthetic.geojson` | Generated output |
| `--seed` | `20261114` | Synthetic-attribute seed |
| `--resolution` | `9` | Only 9 is accepted for contract fixtures |
| `--target-count` | `1000` | Exact selected cell count |

Python API:

```python
from src.engines.synthetic_h3_generator import (
    GenerationConfig,
    generate_and_write,
    generate_feature_collection,
)

config = GenerationConfig(seed=42, target_count=1000)
result = generate_feature_collection(config)   # in memory
# or
result = generate_and_write(config)            # writes GeoJSON
```

Measured default output:

- Path: `data/mock/banyumas_h3_synthetic.geojson`
- Features: 1,000
- File size: approximately **2.86 MB**
- Formatting: UTF-8 JSON, two-space indentation
- Git status: gitignored generated artifact, not committed

---

## 11. Known limitations

- The ROI is a bounding box, not a paddy mask.
- H3 cells are selected by centre containment; polygons are not clipped to the
  ROI boundary.
- No real NASA observation, QA flag, cloud mask, timestamp, or native pixel
  resolution is represented.
- No SMAP/GPM native-pixel sharing or downscaling is modeled.
- PVRS, BF-EHSI, optical lag, erosion alert, fiscal metrics, and XAI text are not
  engine outputs.
- The schema cannot represent realistic missing observations.
- `LST_anomaly` is a constant placeholder because no bound exists.
- `GPM_rain_7d` uses an arbitrary 100 mm test cap because the schema has no
  maximum.
- Uniform values are schema-constrained test values, not empirical
  distributions.
- Rotation scenarios are empty.
- The system-state cycle is for UI testing only and does not select a final
  abstention spelling.
- No frontend or GIS consumer schema has been agreed yet.
- The contract itself is provisional and not ratified.

---

## 12. Replacement and recalibration plan

When real data and engines become available:

1. Replace source-like values with documented, QA-filtered NASA exports.
2. Record native resolution, aggregation/downscaling, timestamps, and valid-pixel
   counts.
3. Replace PVRS/BF-EHSI placeholders by importing Arya's engines through an
   agreed adapter; do not copy formulas.
4. Replace fiscal placeholders with Arya's fiscal engine outputs.
5. Replace XAI placeholders with evidence-backed explanations.
6. Ratify the nullable/missing-observation policy before allowing null indicators.
7. Ratify `MBSI` vs `HLS_BSI` and the final abstention spelling.
8. Add a verified paddy/land-cover mask if `land_cover` is to be populated.
9. Keep the geometry/provenance structure stable, or version the output schema.
10. Update `GENERATOR_VERSION` and regenerate expected fixtures whenever the
    attribute-generation order changes.

The geometry and provenance design can remain; the placeholder values must be
replaced, not treated as a baseline for real analysis.

---

## 13. Definition-of-done mapping

| Requirement | Evidence |
|---|---|
| Generator module exists | `src/engines/synthetic_h3_generator.py` |
| Uses actual ROI | `load_roi_geometry(DEFAULT_ROI_PATH)` |
| Exactly 1,000 unique res-9 cells | CLI output and tests |
| Valid GeoJSON polygons | Closed rings, lon/lat order, Polygon type |
| Reproducible attributes | `default_rng(seed)`; same-seed tests |
| Definitions grounded or marked unresolved | Embedded manifest and this document |
| Contract compatibility | 1,000 contracts validated by Task 1 validator |
| Explicit synthetic provenance | Top-level and per-feature metadata |
| No unverified paddy claim | `land_cover: "unverified"` |
| Unit tests pass | `tests/test_synthetic_h3_generator.py` |
| Documentation | This file and `data/mock/README.md` |
| Arya/Arief untouched | `external/` unchanged |
| No unrelated task implemented | Scope limited to synthetic H3 generation |

---

*End of synthetic H3 generator design record.*
