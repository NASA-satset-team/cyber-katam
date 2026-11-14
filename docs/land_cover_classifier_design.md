# H3 Land-Cover Classification Module — Design and Usage

**Status: PROVISIONAL / SCAFFOLD**
**Task:** Task 3 — Land-Cover Classification (CYBER-KATAM AI Core, Aqila)
**Models:** `src/models/land_cover.py`
**Module:** `src/engines/land_cover_classifier.py`
**Tests:** `tests/test_land_cover_classifier.py`
**Sidecar schema:** `land_cover.sidecar.v0.1`

> This module does **not** classify satellite imagery. It does not detect paddy
> fields from NDVI, BSI, LST, a bounding box, or random values. It accepts
> land-cover information from an external source, validates it, manages
> verification/provenance, and serializes a sidecar keyed by H3 index.

---

## 1. Purpose and responsibility boundary

### In scope

- Validate one H3 cell index.
- Accept an optional land-cover class from an external source.
- Accept optional source-provided coverage fractions.
- Validate verification status and provenance.
- Distinguish real, synthetic, and unknown-source records.
- Default to `UNKNOWN` when no information exists.
- Reject duplicate H3 records and conflicting land-cover classes.
- Serialize a deterministic sidecar JSON keyed by H3 index.
- Optionally enrich a GeoJSON FeatureCollection outside `properties.contract`.

### Out of scope

- Image classification or machine learning.
- Paddy detection from NDVI, BSI, LST, or other indicators.
- Computing coverage from polygons, rasters, or H3 geometry.
- Calling Google Earth Engine or downloading datasets.
- Creating confidence, accuracy, or quality scores.
- Changing the strict grid-cell contract.
- Changing Task 1, Task 2, Arief's pipeline, Arya's engines, or frontend/GIS files.
- Resolving conflicts between sources without an approved policy.

---

## 2. Domain model

### 2.1 LandCoverClass

| Value | Meaning |
|---|---|
| `PADDY_FIELD` | A source explicitly classifies the cell as paddy field |
| `NON_PADDY` | A source explicitly classifies the cell as not paddy |
| `MIXED` | A source explicitly classifies the cell as mixed land cover |
| `UNKNOWN` | No information, or insufficient information |

`UNKNOWN` is never converted to `NON_PADDY` and never auto-promoted to
`PADDY_FIELD`. Coverage does not determine the class in v0.1.

### 2.2 VerificationStatus

| Value | Meaning |
|---|---|
| `FIELD_VERIFIED` | Verified through field observation; requires verification method, date, and reference |
| `REFERENCE_VALIDATED` | Compared against an independent reference dataset; requires reference dataset, method, and date |
| `SOURCE_ASSERTED` | The data producer asserts the class; CYBER-KATAM has not independently verified it |
| `UNVERIFIED` | A class exists but no verification evidence is available |
| `NOT_ASSESSED` | Verification was not performed, or there is no class |

`SOURCE_ASSERTED` is **not** field verification and **not** independent
verification. `FIELD_VERIFIED` does not automatically mean ground truth outside
the documented field evidence.

### 2.3 SourceKind

| Value | Meaning |
|---|---|
| `OFFICIAL_DATASET` | Published/versioned land-cover product; not automatically paddy-specific |
| `DERIVED_CLASSIFICATION` | Automated/model/remote-sensing classification |
| `FIELD_OBSERVATION` | Field survey, GPS, or agronomist observation |
| `SYNTHETIC_MOCK` | Test fixture; not an observation |
| `UNKNOWN_SOURCE` | No source information |

### 2.4 is_synthetic

`is_synthetic` is derived, not an independent input:

```text
SYNTHETIC_MOCK -> True
known non-synthetic source -> False
UNKNOWN_SOURCE -> None
```

A mock record cannot claim `FIELD_VERIFIED`, `REFERENCE_VALIDATED`, or
`SOURCE_ASSERTED`.

**Trust boundary:** `is_synthetic` is only a label derived from the caller's
`source_kind`. It is not an automatic detector for fake data. A caller that
mislabels a mock payload as `OFFICIAL_DATASET` will produce
`is_synthetic=False`; the module cannot prove otherwise. This limitation is
intentional and must be covered by upstream data governance or a future
approved source registry.

### 2.5 Consistency rules

1. `UNKNOWN` requires `verification_status = NOT_ASSESSED`.
2. A non-`UNKNOWN` class requires a known `source_kind` and
   `provenance.source`.
3. `FIELD_VERIFIED` requires `verification_method`, `verification_date`, and
   `verification_reference`.
4. `REFERENCE_VALIDATED` requires `reference_dataset`, `verification_method`,
   and `verification_date`.
5. `SYNTHETIC_MOCK` may only use `NOT_ASSESSED` or `UNVERIFIED`.
6. Coverage cannot change `land_cover_class`.
7. No confidence, accuracy, or quality score is generated.

---

## 3. Input

### 3.1 LandCoverObservation

| Field | Required | Type | Default |
|---|---|---|---|
| `h3_index` | yes | string | — |
| `land_cover_class` | no | `LandCoverClass` / null | `UNKNOWN` |
| `verification_status` | no | `VerificationStatus` / null | `NOT_ASSESSED` for `UNKNOWN`; `UNVERIFIED` otherwise |
| `source_kind` | no | `SourceKind` / null | `UNKNOWN_SOURCE`; required for non-`UNKNOWN` class |
| `coverage` | no | `CoverageFractions` / null | `None` |
| `provenance` | no | `Provenance` / null | `None` |
| `notes` | no | string / null | `None` |

`is_synthetic` is intentionally absent from the input model. Supplying it in a
raw payload is rejected as an unknown field.

### 3.2 Provenance

Optional fields:

- `source`
- `dataset_id`
- `product_version`
- `observation_date` (`YYYY-MM-DD`)
- `processing_date` (`YYYY-MM-DD`)
- `spatial_resolution_m`
- `classification_method`
- `verification_method`
- `verification_date` (`YYYY-MM-DD`)
- `verification_reference`
- `reference_dataset`
- `license`
- `attribution`

Unavailable fields remain `None`/omitted. Dates are not auto-filled.
`coverage.method` is the only home for the coverage method; `Provenance` has no
`coverage_method` field.

**Trust boundary:** `source_kind`, `provenance.source`, and verification evidence
are assertions supplied by the caller. The module validates internal consistency
but does not independently verify the dataset, field survey, or reference
dataset. A caller can mislabel mock data as an official or field-verified record;
that is outside the module's detection capability. See Section 10.2.

### 3.3 Accepted payload forms

`parse_land_cover_payload()` accepts:

- a `LandCoverObservation`;
- a single observation mapping with `h3_index`;
- a mapping keyed by H3 index;
- a list/tuple of observation mappings or observations;
- a JSON string of any of the above.

Sidecar payloads must use `deserialize_land_cover_layer()`.

---

## 4. Output

### 4.1 Primary output: sidecar JSON keyed by H3

```json
{
  "schema_version": "land_cover.sidecar.v0.1",
  "status": "PROVISIONAL",
  "module": "land_cover_classifier",
  "module_version": "0.1.0",
  "records": {
    "898d8d654cbffff": {
      "h3_index": "898d8d654cbffff",
      "land_cover_class": "PADDY_FIELD",
      "verification_status": "SOURCE_ASSERTED",
      "source_kind": "OFFICIAL_DATASET",
      "is_synthetic": false,
      "coverage": {
        "paddy_fraction": 0.6,
        "non_paddy_fraction": 0.3,
        "other_fraction": 0.1,
        "method": "PIXEL_AREA_FRACTION",
        "valid_pixel_count": 60,
        "total_pixel_count": 100
      },
      "provenance": {
        "source": "Example land-cover dataset",
        "dataset_id": "EXAMPLE-LC-001"
      },
      "notes": null
    }
  },
  "warnings": []
}
```

Rules:

- Records are sorted by H3.
- Mapping key equals `record.h3_index`.
- `UNKNOWN` records are kept.
- `is_synthetic` is `true`, `false`, or `null`.
- Missing coverage is `null`, not zero.
- Missing provenance fields are omitted, not invented.
- No `contract`, `confidence`, `accuracy`, or `quality_score` is present.
- Warnings are derived from records and serialized at top level.

### 4.2 Serialization validation

`serialize_land_cover_layer()` revalidates and normalizes every record before
output. It checks H3 validity/resolution, enum types, `is_synthetic`,
coverage, provenance, verification completeness, `notes`, `warnings`,
record-key consistency, and layer metadata. This protects against manually
constructed layers and layers mutated after `process_land_cover_observations()`.
Validation failures are raised as `LandCoverSerializationError` with the
module's normal error codes.

`write_land_cover_sidecar()` performs a serialize → deserialize round-trip
before creating a file. It never writes a payload that fails its own
deserializer. Revalidation uses the default expected H3 resolution 9 and the
maximum permitted coverage tolerance (0.001), so a layer built with any allowed
tolerance can round-trip.

### 4.3 Output path allow-list

The only permitted output directory is:

```text
data/land_cover/
```

Output must be a `.json` file under that directory, for example:

```text
data/land_cover/banyumas_land_cover.json
```

The writer rejects relative/absolute paths outside the allow-list, `..`
traversal, Windows separator variants, case variants that resolve outside,
non-`.json` extensions, and symlink/junction escapes. It never writes to
`.git/`, `src/`, `tests/`, `docs/`, `contracts/`, `data/boundaries/`,
`data/mock/` (no sidecar output is allowed there), `external/`, README files, or
the Task 2 H3 GeoJSON.

### 4.4 Optional GeoJSON enrichment

`enrich_geojson_with_land_cover()` returns a deep copy of a FeatureCollection
with `properties.land_cover_record` added outside `properties.contract`.

- The input GeoJSON is not mutated.
- `properties.contract` is never modified.
- Missing H3 records can become explicit `UNKNOWN` records, or be left absent.
- The Task 2 output file is never overwritten.

---

## 5. Coverage

`CoverageFractions` fields:

- `paddy_fraction`
- `non_paddy_fraction`
- `other_fraction`
- `method`
- `valid_pixel_count`
- `total_pixel_count`

Validation rules:

- Each fraction is `[0.0, 1.0]`.
- Known fractions must sum to no more than `1.0` plus a configurable tolerance.
- `coverage_tolerance` is limited to `[0.0, 0.001]`; larger values are rejected.
- Missing fraction is `None`, not `0.0`.
- `0.0` is a real zero and is preserved.
- Negative, greater-than-one, non-numeric, or boolean fractions are rejected.
- `valid_pixel_count` and `total_pixel_count` must be non-negative integers.
- `valid_pixel_count` must not exceed `total_pixel_count`.
- Coverage without `method` is accepted with warning
  `COVERAGE_METHOD_UNKNOWN`.
- Empty coverage is accepted with warning `COVERAGE_EMPTY`.
- Coverage never changes `land_cover_class`.
- No coverage is computed from geometry or raster data in this task.

Conceptual future methods (not implemented):

| Method | Requirement | Limitation |
|---|---|---|
| Area intersection | H3 polygon + mask geometry + projection/area rule | Needs clipping and edge policy |
| Pixel area fraction | Raster mask + pixel grid + aggregation rule | Scale mismatch and valid-pixel QA |
| Center-point sampling | H3 center + mask lookup | Not a coverage fraction; ignores heterogeneity |

---

## 6. Public API

```python
parse_land_cover_payload(payload) -> list[LandCoverObservation]
validate_land_cover_observation(observation, *, config=None) -> tuple[str, ...]
process_land_cover_observations(observations, *, config=None) -> LandCoverLayer
serialize_land_cover_layer(layer) -> dict[str, Any]
deserialize_land_cover_layer(payload) -> LandCoverLayer
write_land_cover_sidecar(layer, output_path) -> int
read_land_cover_sidecar(input_path) -> LandCoverLayer
enrich_geojson_with_land_cover(
    feature_collection,
    layer,
    *,
    include_missing_as_unknown=True,
) -> dict[str, Any]
```

### 6.1 Example

```python
from src.engines.land_cover_classifier import (
    process_land_cover_observations,
    serialize_land_cover_layer,
    write_land_cover_sidecar,
)
from src.models.land_cover import (
    LandCoverClass,
    LandCoverObservation,
    Provenance,
    SourceKind,
    VerificationStatus,
)

observations = [
    LandCoverObservation(
        h3_index="898d8d654cbffff",
        land_cover_class=LandCoverClass.PADDY_FIELD,
        verification_status=VerificationStatus.SOURCE_ASSERTED,
        source_kind=SourceKind.OFFICIAL_DATASET,
        provenance=Provenance(
            source="Example land-cover dataset",
            dataset_id="EXAMPLE-LC-001",
        ),
    ),
    # A cell with no information is still emitted as UNKNOWN.
    LandCoverObservation(h3_index="898d8d67243ffff"),
]

layer = process_land_cover_observations(observations)
payload = serialize_land_cover_layer(layer)
write_land_cover_sidecar(layer, "data/land_cover/land_cover_sidecar.json")
```

### 6.2 Configuration

```python
LandCoverConfig(
    expected_resolution=9,
    coverage_tolerance=1e-6,  # allowed range: 0.0 .. 0.001
    derive_class_from_coverage=False,  # must remain False in v0.1
    conflict_policy="ERROR",           # only supported policy in v0.1
)
```

`derive_class_from_coverage=True` and any other conflict policy raise
`UnsupportedPolicyError` until the team approves a policy. A
`coverage_tolerance` below `0.0` or above `0.001` raises
`LandCoverInputError`.

---

## 7. Duplicate and conflict handling

Default v0.1 behavior:

- Same H3 + same class → `DUPLICATE_H3_INDEX`.
- Same H3 + different class → `CONFLICTING_LAND_COVER`.
- Duplicate JSON keys → `DUPLICATE_H3_INDEX` for H3 keys, otherwise
  `DUPLICATE_JSON_KEY`.

No priority, recency, source-authority, or manual-review resolution is
implemented. Those require a team decision. Possible future options are
`KEEP_ALL`, `PRIORITY`, and `MANUAL_REVIEW`, but they are not active.

---

## 8. Errors

| Code | Meaning |
|---|---|
| `INVALID_PAYLOAD` | Malformed object, wrong type, unknown field, invalid date/resolution |
| `INVALID_H3_INDEX` | Missing or invalid H3 index |
| `UNSUPPORTED_H3_RESOLUTION` | Valid H3 but unexpected resolution |
| `UNKNOWN_LAND_COVER_CLASS` | Class is not one of the four values |
| `UNKNOWN_VERIFICATION_STATUS` | Verification status is not recognized |
| `UNKNOWN_SOURCE_KIND` | Source kind is not recognized |
| `MISSING_SOURCE` | Non-UNKNOWN class has no known source/provenance source |
| `INVALID_COVERAGE` | Bad fraction, count, method, or coverage sum |
| `INCOMPLETE_VERIFICATION_PROVENANCE` | Required verification evidence is missing |
| `SYNTHETIC_CANNOT_BE_VERIFIED` | Synthetic record claims verification |
| `DUPLICATE_H3_INDEX` | Same H3 appears more than once |
| `CONFLICTING_LAND_COVER` | Same H3 has different classes |
| `DUPLICATE_JSON_KEY` | Duplicate non-H3 JSON key |
| `UNSUPPORTED_SCHEMA_VERSION` | Sidecar version is not v0.1 |
| `INCONSISTENT_VERIFICATION_STATUS` | `UNKNOWN` used with non-`NOT_ASSESSED` |
| `INCONSISTENT_SYNTHETIC_FLAG` | `is_synthetic` disagrees with `source_kind` |
| `UNSUPPORTED_POLICY` | Unapproved coverage/conflict policy requested |
| `UNSAFE_OUTPUT_PATH` | Output is not a `.json` file under `data/land_cover/` |
| `SIDECAR_READ_ERROR` | Sidecar cannot be read |

Errors carry a code, a message, and H3 index/path where available.

---

## 9. Integration

### Task 2 — Synthetic H3 Generator

- Use H3 indexes from Task 2 output or a small fixture.
- Do not modify `data/mock/banyumas_h3_synthetic.geojson`.
- Do not make tests depend on that gitignored file.
- Optional enrichment returns a copy and adds
  `properties.land_cover_record` outside `properties.contract`.

### Arief — Data Pipeline

Arief should provide, when available:

- a verified paddy/land-cover mask;
- per-H3 class and optional coverage;
- coverage method and native resolution;
- observation/processing dates;
- dataset/product identity and license/attribution;
- a clear distinction between cropland and paddy-specific classification.

The module does not call GEE or download data.

### Contract Validator

- The contract has no `land_cover` field.
- `additionalProperties: false` means the contract would reject one.
- The sidecar remains outside the strict contract.
- A future contract integration requires a new schema version and team approval.

### GIS Viewer Rifaldi / Frontend Rafi

- Sidecar can be joined by `h3_index`.
- Optional enrichment provides a per-feature `land_cover_record`.
- Field names, legend, `UNKNOWN` display, and `MIXED` display need confirmation.
- No confidence/accuracy fields are available.

### Other AI Core modules

- Treat `UNKNOWN` as unknown, not `NON_PADDY`.
- Do not drop `UNKNOWN` cells from visualization or collection.
- Do not use synthetic records as verified real data.

---

## 10. Limitations and pending decisions

### Limitations

- No real paddy mask or verified land-cover source exists yet.
- The module cannot detect paddy from imagery.
- Coverage is not computed.
- `MIXED` must be supplied by the source; no threshold is active.
- Conflict resolution is not implemented.
- No confidence, accuracy, or quality score exists.
- No contract integration exists.
- No frontend/GIS format is ratified.
- The sidecar is provisional.

### 10.1 Serialization revalidation

Every record is revalidated and normalized before serialization. Manual layers
and layers mutated after `process_land_cover_observations()` cannot bypass
H3, coverage, provenance, verification, `notes`, `warnings`, enum, or
`is_synthetic` checks. `write_land_cover_sidecar()` also round-trips the payload
through `deserialize_land_cover_layer()` before writing.

### 10.2 Provenance trust boundary

`source_kind`, `provenance.source`, dataset identity, and verification evidence
are caller assertions. The module enforces internal consistency but cannot prove
that a caller's dataset is official, that a field survey occurred, or that a
reference comparison was performed. A caller can mislabel mock data as
`OFFICIAL_DATASET` and `FIELD_VERIFIED`; the module will accept it as a
caller-asserted record. This is a deliberate trust boundary, not a detection
capability. An approved source registry or signed provenance would be required
for stronger assurance.

### 10.3 is_synthetic limitation

`is_synthetic` is derived only from `source_kind`:

- `SYNTHETIC_MOCK` → `True`
- known non-synthetic source → `False`
- `UNKNOWN_SOURCE` → `None`

It is not an automatic fake-data detector. A mislabelled mock payload with
`source_kind=OFFICIAL_DATASET` produces `is_synthetic=False`.

### 10.4 Output path allow-list

Only `data/land_cover/*.json` is writable. The writer rejects paths outside that
directory, non-JSON extensions, `..` traversal, Windows separator/case variants
that resolve outside, and symlink/junction escapes. Path checking is path-based;
hard-link aliases and alternate filesystem identities are not detected.

### 10.5 Warnings

`record.warnings` and `layer.warnings` must be tuples of strings, but serialized
warnings are derived from normalized records. Caller-supplied warning content is
not trusted. Missing coverage method produces `COVERAGE_METHOD_UNKNOWN`; empty
coverage produces `COVERAGE_EMPTY`.

### Pending team decisions

1. Final class names and semantics.
2. Whether the five-level verification enum is accepted.
3. Definitions of acceptable `FIELD_VERIFIED` and `REFERENCE_VALIDATED` evidence.
4. Whether `SOURCE_ASSERTED` is useful or should be removed.
5. Whether `OFFICIAL_DATASET` means a government product or any published product.
6. Whether ESA WorldCover class 40 may be used as a cropland proxy.
7. Coverage shape and whether `[0,1]` fractions are accepted.
8. Approved coverage method and resolution handling.
9. Whether a `MIXED` threshold should ever be introduced.
10. Conflict resolution policy.
11. Sidecar vs GeoJSON enrichment as the consumer contract.
12. GIS/frontend field names and legend behavior.
13. Whether `UNKNOWN` must always be materialized for missing H3 cells.
14. H3 resolution policy beyond the default 9.
15. Whether land cover will ever enter the strict contract.
16. Dataset license/attribution requirements.
17. Whether an approved source registry or signed provenance is required for stronger verification.
18. Whether caller-asserted `SOURCE_ASSERTED`/`FIELD_VERIFIED` is sufficient for operational use.
19. Whether `data/land_cover/` remains the approved sidecar output directory.

---

## 11. Verification

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_land_cover_classifier.py -v
.venv\Scripts\python.exe -m pytest tests/ -v
```

The module's tests cover all four classes, default `UNKNOWN`, invalid H3,
resolution mismatch, duplicate/conflict handling, coverage validation and
warnings, coverage-tolerance bounds, provenance/verification rules,
synthetic/real separation, caller-asserted provenance limits, parsing,
duplicate JSON keys, serialize/deserialize round-trip, serializer rejection of
manual/mutated invalid layers, deterministic ordering, GeoJSON enrichment
without mutation, output-path allow-list, traversal/separator/case checks,
symlink/junction escape, and policy guards.

No Task 1, Task 2, contract, Arief, Arya, frontend, or GIS file is modified by
this module.
