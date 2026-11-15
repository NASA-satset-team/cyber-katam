# CYBER-KATAM Crop Modeling Module

**Scope:** crop-specific strategic evaluation and H+1..H+3 tactical advisory. This module does not ingest historical NASA data, fetch weather, recalculate PVRS/BF-EHSI, or implement the final integration/decision engine.

**Audit basis:** `docs/crop_rotation_model_review_weather_readiness_audit.md`, `docs/agronomic_data_foundation_audit.md`, and `docs/crop_parameter_registry_audit.md`.

---

## 1. Package layout

```text
src/crop_modeling/
  __init__.py
  models.py       # dataclasses, status enums, I/O structures
  registry.py     # registry loader + provenance/unit validation
  water.py        # ETc, seasonal ETc, one-step water balance
  suitability.py  # explicit suitability checks
  calendar.py     # stage windows / planting-harvest calendar
  rotation.py     # candidate evaluation + existing Pareto adapter
  tactical.py     # crop-specific H+1..H+3 tactical rule engine

data/registry/
  crop_parameter_registry.json

contracts/
  crop_parameter_registry.schema.json

tests/
  test_crop_modeling.py
```

The existing files in `external/aryas_workresult/`, `external/ariefs_workresult/`, `web-app/`, and existing contracts were not modified.

---

## 2. Registry policy

Each parameter has:

- `value`
- `unit`
- `status`: `observed`, `standard`, `proxy`, `derived`, or `missing`
- `source_id`
- `location`
- `product_basis` (where relevant)
- `time_origin` (where relevant)
- `notes`

Rules enforced by `CropRegistry`:

1. `status=missing` requires `value=null`.
2. A non-missing status requires a non-null value and a known `source_id`.
3. Every unit must resolve in the registry unit list.
4. No consumer fills a missing value with a default.
5. Generic FAO values remain `standard`; they are not relabeled as cultivar observations.
6. Official national variety descriptions remain `observed` national values, not Banyumas field validation.

The current registry deliberately has many `null` entries. It is not a complete production registry.

---

## 3. Water model

### 3.1 ETc

`src/crop_modeling/water.py::et_c` implements:

```text
ETc = Kc × ETo
```

Kc is taken from explicit registry parameters. Kc and Kcb are not mixed. A Kc range is not silently converted to a point value.

### 3.2 Seasonal ETc

`seasonal_etc()` requires:

- four phase lengths (`phase_lengths_days`),
- a Kc for each phase (`kc_initial`, `kc_development`, `kc_mid`, `kc_end`),
- ETo for each phase.

Missing values produce `INSUFFICIENT_DATA`. Seasonal ETc is **not** irrigation demand.

### 3.3 One-step water balance

`daily_water_balance()` requires:

- root-zone storage,
- field capacity,
- wilting point,
- saturation,
- ETc,
- effective rainfall,
- irrigation,
- runoff,
- deep percolation.

All components must be explicit. `None` produces `INSUFFICIENT_DATA`. The function returns storage end, clipping, and a simple refill-to-field-capacity irrigation estimate. It is not a full irrigation scheduling model.

### 3.4 Limitations

- The existing fixed `BanyumasWaterBalanceSimulator` remains the reference scenario simulator; this module is a crop-level adapter, not a replacement.
- Effective rainfall, runoff, and deep percolation must be supplied by the integration/historical layer.
- No local ETo/rain/soil data is fabricated here.

---

## 4. Suitability model

`evaluate_suitability()` evaluates only parameters present in the registry:

- pH range (`ph_min`, `ph_max`) — an optimum point is not used as a range.
- slope maximum (`slope_max_deg`).
- drainage class membership (`drainage_classes`).
- salinity threshold (`salinity_max_ds_m`).

Outputs:

- `SUITABLE`: all evaluated constraints pass and no required constraint is missing.
- `CONDITIONALLY_SUITABLE`: no known failure, but some constraints/context are missing.
- `UNSUITABLE`: a known constraint fails.
- `INSUFFICIENT_DATA`: no constraint can be evaluated.

`PVRS` and `BF-EHSI` are context indicators. They are not converted into pass/fail crop suitability thresholds without an approved crop-specific rule.

The current registry has no pH range, slope limit, or drainage classes for the target crops, so most production results will be `INSUFFICIENT_DATA` or `CONDITIONALLY_SUITABLE` until those data are sourced.

---

## 5. Calendar

`build_calendar()` requires:

- a planting date,
- four registry phase lengths.

It returns stage windows plus `PLANTING` and `HARVEST` events. It does not invent activity dates for irrigation, fertilization, or drainage. Those are handled tactically when the current stage and forecast are known.

Only Kedelai Anjasmoro currently has proxy phase lengths (FAO generic soybean) in the registry; the official Anjasmoro duration is 82.5–92.5 days. The phase split is not cultivar-specific.

---

## 6. Strategic rotation and Pareto

`enumerate_sequences()` generates permutations from the supplied crop ID list; there are no hardcoded A/B/C scenario names.

`evaluate_sequence()` only accepts a candidate when all required metrics are explicit:

- non-host duration,
- water demand,
- N displaced,
- SOC change,
- BPH burden,
- gross revenue,
- production cost,
- required Ksat,
- predicted erosion.

Missing metrics produce rejection reasons. No value is imputed.

`pareto_optimize()` wraps the existing `solve_pareto_epsilon_constraint()` from `external/aryas_workresult/fiscal_actuarial.py`. It does not implement a second optimizer.

The current repository has no runtime source for most metrics, so strategic output will usually abstain/reject until the integration layer supplies them.

---

## 7. Tactical advisor

`TacticalCropAdvisor.advise()` consumes:

- `CropRecord`,
- current growth stage,
- `EnvironmentContext`,
- `ForecastBundle` (H+1..H+3).

It produces `TacticalAdvisory` records with:

- date,
- action,
- `RECOMMENDED` / `CONDITIONAL` / `DEFER` / `ABSTAIN`,
- reason,
- evidence,
- limitations,
- crop/stage.

Supported actions:

- `PLANTING`
- `IRRIGATION`
- `FERTILIZATION`
- `DRAINAGE`
- `HARVEST`
- `FORECAST` (stale/unavailable abstention)
- `FALLOW` (via `advise_fallow`, using only supplied BF-EHSI context)

### Threshold policy

No unsourced rainfall or temperature threshold is used. The advisor uses arithmetic/data conditions:

- rain expected (`precipitation_mm > 0`) → conditional, not automatic defer;
- rain sum vs simple soil refill deficit → defer/conditional;
- storage vs field capacity/saturation → irrigation/drainage conditions;
- missing N requirement → fertilization abstains;
- missing soil moisture/saturation → drainage/irrigation abstains;
- stale forecast → tactical actions abstain.

This intentionally produces many `CONDITIONAL`/`ABSTAIN` results. That is preferable to fabricated certainty.

### Strategic/tactical separation

The tactical advisor never changes the strategic rotation. It only returns H+1..H+3 operational advisories. A forecast refresh changes tactical status/evidence, not the seasonal crop sequence.

---

## 8. Input/output examples

### Input

```json
{
  "cell_id": "example_h3_cell",
  "current_crop": "kedelai_anjasmoro",
  "growth_stage": "planting",
  "environment": {
    "soil_moisture_mm": null,
    "field_capacity_mm": null,
    "wilting_point_mm": null,
    "saturation_mm": null,
    "soil_ph": null,
    "slope_deg": null,
    "drainage_class": null,
    "salinity_ds_m": null,
    "pvrs": null,
    "bf_ehsi": null,
    "observed_at": null,
    "data_status": "MISSING"
  },
  "weather_forecast": {
    "provider": "provider_name",
    "issue_time": "2026-11-15T00:00:00Z",
    "retrieval_time": "2026-11-15T01:00:00Z",
    "valid_start": "2026-11-15",
    "valid_end": "2026-11-18",
    "stale": false,
    "days": [
      {"date": "2026-11-15", "precipitation_mm": null},
      {"date": "2026-11-16", "precipitation_mm": null},
      {"date": "2026-11-17", "precipitation_mm": null}
    ]
  }
}
```

### Output shape

```json
{
  "crop_model": {
    "crop_id": "kedelai_anjasmoro",
    "growth_stage": "planting",
    "water_requirement": null,
    "suitability_status": "INSUFFICIENT_DATA"
  },
  "tactical_advisory": [
    {
      "date": "2026-11-15",
      "action": "PLANTING",
      "status": "ABSTAIN",
      "reason": "Precipitation forecast is missing for this day.",
      "evidence": ["forecast_provider=provider_name"],
      "limitations": ["No default precipitation value was inserted."]
    }
  ]
}
```

The exact serialization is not the final application contract; it is the crop-module interface. The integration team should map it into the final API contract.

---

## 9. Tested behavior

`tests/test_crop_modeling.py` covers:

- registry loading and null preservation;
- ETc and seasonal ETc;
- complete/incomplete water balance;
- suitability pass/fail/missing;
- calendar construction;
- candidate generation, rejection reasons, and Pareto adapter;
- stale forecast abstention;
- planting with rain conditional;
- irrigation defer/conditional;
- missing soil and missing N abstention.

These tests verify software behavior and fail-closed logic. They do **not** validate agronomic accuracy.

---

## 10. Data still required

- Banyumas local crop prices and production costs.
- Local yield trials for Inpari 32, Anjasmoro, Vima-1, and the intended sorghum variety.
- Cultivar-specific Kc/Kcb and phase lengths.
- Per-crop root depth and soil suitability thresholds.
- pH/texture/drainage/slope/salinity suitability rules.
- KATAM Banyumas planting calendar.
- Crop-specific N requirement and N fixation.
- Pest host/population parameters.
- Weather provider metadata and operational thresholds.
- Contract fields for candidate constraints and provenance.

Until these are sourced and approved, the module must continue to return `null`, `CONDITIONAL`, or `ABSTAIN` rather than inventing values.
