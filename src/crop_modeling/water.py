"""Crop-level ETc and simple soil-water balance.

This is a crop-specific adapter, not a replacement for the existing scenario
water-balance simulator. It deliberately fails closed when required components
are missing and never treats seasonal ET as irrigation demand.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from .models import (
    CropRecord,
    ForwardWaterResult,
    WaterDayInput,
    WaterResult,
)


def et_c(kc: float, eto_mm: float) -> float:
    """Return crop evapotranspiration (mm/day).

    Both inputs must be non-negative. No missing-value default is applied.
    """
    if kc is None or eto_mm is None:
        raise ValueError("kc and eto_mm are required")
    if kc < 0 or eto_mm < 0:
        raise ValueError("kc and eto_mm must be non-negative")
    return float(kc) * float(eto_mm)


def kc_for_stage(crop: CropRecord, stage: str) -> tuple[float | None, str | None]:
    """Return a Kc for a named stage, or (None, reason).

    Only Kc (not Kcb) is used. A range is not silently converted to a point.
    """
    key = {
        "initial": "kc_initial",
        "vegetative": "kc_initial",
        "development": "kc_development",
        "mid": "kc_mid",
        "reproductive": "kc_mid",
        "late": "kc_end",
        "maturity": "kc_end",
        "harvest": "kc_end",
    }.get(stage)
    if key is None:
        return None, f"No Kc mapping for stage '{stage}'"
    if key not in crop.parameters:
        return None, f"Parameter '{key}' is not in the registry"
    p = crop.parameter(key)
    if p.is_missing():
        return None, f"Parameter '{key}' is missing"
    if isinstance(p.value, (list, tuple)):
        return None, f"Parameter '{key}' is a range; stage Kc must be an explicit scalar"
    try:
        value = float(p.value)
    except (TypeError, ValueError):
        return None, f"Parameter '{key}' is not numeric"
    return value, None


def seasonal_etc(
    crop: CropRecord,
    eto_by_stage_mm_day: Mapping[str, float],
) -> WaterResult:
    """Compute seasonal ETc from stage lengths, Kc, and stage ETo.

    Missing phase lengths/Kc/ETo produce INSUFFICIENT_DATA. No seasonal ET is
    interpreted as irrigation demand here.
    """
    if "phase_lengths_days" not in crop.parameters:
        return WaterResult(
            status="INSUFFICIENT_DATA",
            etc_mm=None,
            irrigation_requirement_mm=None,
            storage_end_mm=None,
            components={},
            missing=("phase_lengths_days",),
            notes=("No phase lengths in registry; cannot integrate seasonal ETc.",),
        )
    phase_p = crop.parameter("phase_lengths_days")
    if phase_p.is_missing() or not isinstance(phase_p.value, (list, tuple)) or len(phase_p.value) != 4:
        return WaterResult(
            status="INSUFFICIENT_DATA",
            etc_mm=None,
            irrigation_requirement_mm=None,
            storage_end_mm=None,
            components={},
            missing=("phase_lengths_days",),
            notes=("Phase lengths must be four non-null stage lengths.",),
        )

    stages = ("initial", "development", "mid", "late")
    total = 0.0
    components: dict[str, float | None] = {}
    missing: list[str] = []
    for stage, days_raw in zip(stages, phase_p.value):
        if days_raw is None:
            missing.append(f"phase_lengths_days.{stage}")
            continue
        eto = eto_by_stage_mm_day.get(stage)
        if eto is None:
            missing.append(f"eto.{stage}")
            continue
        kc, reason = kc_for_stage(crop, stage)
        if kc is None:
            missing.append(f"kc.{stage}:{reason}")
            continue
        etc_stage = et_c(kc, eto) * float(days_raw)
        components[f"etc_{stage}_mm"] = round(etc_stage, 4)
        total += etc_stage

    if missing:
        return WaterResult(
            status="INSUFFICIENT_DATA",
            etc_mm=None,
            irrigation_requirement_mm=None,
            storage_end_mm=None,
            components=components,
            missing=tuple(missing),
            notes=("Seasonal ETc is not complete; no default Kc/ETo was inserted.",),
        )
    return WaterResult(
        status="OK",
        etc_mm=round(total, 4),
        irrigation_requirement_mm=None,
        storage_end_mm=None,
        components=components,
        missing=(),
        notes=("Seasonal ETc only; not an irrigation requirement.",),
    )


def daily_water_balance(
    *,
    storage_mm: float | None,
    field_capacity_mm: float | None,
    wilting_point_mm: float | None,
    saturation_mm: float | None,
    etc_mm: float | None,
    effective_rain_mm: float | None,
    irrigation_mm: float | None,
    runoff_mm: float | None,
    deep_percolation_mm: float | None,
) -> WaterResult:
    """One-step root-zone water balance.

    All components are required. ``runoff_mm`` and ``deep_percolation_mm`` may
    be explicitly 0.0, but None means the balance is not computable.
    """
    required = {
        "storage_mm": storage_mm,
        "field_capacity_mm": field_capacity_mm,
        "wilting_point_mm": wilting_point_mm,
        "saturation_mm": saturation_mm,
        "etc_mm": etc_mm,
        "effective_rain_mm": effective_rain_mm,
        "irrigation_mm": irrigation_mm,
        "runoff_mm": runoff_mm,
        "deep_percolation_mm": deep_percolation_mm,
    }
    missing = tuple(k for k, v in required.items() if v is None)
    if missing:
        return WaterResult(
            status="INSUFFICIENT_DATA",
            etc_mm=etc_mm,
            irrigation_requirement_mm=None,
            storage_end_mm=None,
            components=required,
            missing=missing,
            notes=("No water-balance component was defaulted.",),
        )

    if saturation_mm < field_capacity_mm or field_capacity_mm < wilting_point_mm:
        raise ValueError("Expected wilting_point <= field_capacity <= saturation")

    def clamp(value: float) -> tuple[float, float]:
        excess = 0.0
        deficit = 0.0
        if value > saturation_mm:
            excess = value - saturation_mm
            value = saturation_mm
        elif value < wilting_point_mm:
            deficit = wilting_point_mm - value
            value = wilting_point_mm
        return value, excess + deficit

    after = (
        float(storage_mm)
        + float(effective_rain_mm)
        + float(irrigation_mm)
        - float(etc_mm)
        - float(runoff_mm)
        - float(deep_percolation_mm)
    )
    storage_end, clipping = clamp(after)

    # Irrigation needed to refill to field capacity if no irrigation is applied.
    no_irrigation = (
        float(storage_mm)
        + float(effective_rain_mm)
        - float(etc_mm)
        - float(runoff_mm)
        - float(deep_percolation_mm)
    )
    storage_no_irrigation, _ = clamp(no_irrigation)
    irrigation_requirement = max(0.0, float(field_capacity_mm) - storage_no_irrigation)

    notes: list[str] = []
    if clipping > 0:
        notes.append("Storage clipped at wilting point/saturation; clipping amount reported in components.")
    if irrigation_requirement > 0:
        notes.append("Irrigation requirement is the refill-to-field-capacity estimate, not a schedule.")

    components = {
        **required,
        "storage_end_mm": round(storage_end, 4),
        "clipping_mm": round(clipping, 4),
        "irrigation_requirement_mm": round(irrigation_requirement, 4),
    }
    return WaterResult(
        status="OK",
        etc_mm=round(float(etc_mm), 4),
        irrigation_requirement_mm=round(irrigation_requirement, 4),
        storage_end_mm=round(storage_end, 4),
        components=components,
        missing=(),
        notes=tuple(notes),
    )


def forward_water_balance(
    *,
    initial_storage_mm: float | None,
    field_capacity_mm: float | None,
    wilting_point_mm: float | None,
    saturation_mm: float | None,
    days: tuple[WaterDayInput, ...] | list[WaterDayInput],
) -> ForwardWaterResult:
    """Run H+1..H+n sequentially, carrying storage forward.

    H+1 uses ``initial_storage_mm``. H+2 uses H+1's storage_end, and so on.
    If any day is incomplete, processing stops and no later day is fabricated.
    """
    required = {
        "initial_storage_mm": initial_storage_mm,
        "field_capacity_mm": field_capacity_mm,
        "wilting_point_mm": wilting_point_mm,
        "saturation_mm": saturation_mm,
    }
    missing = tuple(name for name, value in required.items() if value is None)
    if missing:
        return ForwardWaterResult(
            status="INSUFFICIENT_DATA",
            days=(),
            final_storage_mm=None,
            missing=missing,
            notes=("Forward balance requires an explicit initial state and soil limits.",),
        )
    if not days:
        return ForwardWaterResult(
            status="INSUFFICIENT_DATA",
            days=(),
            final_storage_mm=None,
            missing=("days",),
            notes=("No forecast/water-balance days were supplied.",),
        )

    results: list[WaterResult] = []
    storage = float(initial_storage_mm)
    for index, day in enumerate(days, start=1):
        result = daily_water_balance(
            storage_mm=storage,
            field_capacity_mm=field_capacity_mm,
            wilting_point_mm=wilting_point_mm,
            saturation_mm=saturation_mm,
            etc_mm=day.etc_mm,
            effective_rain_mm=day.effective_rain_mm,
            irrigation_mm=day.irrigation_mm,
            runoff_mm=day.runoff_mm,
            deep_percolation_mm=day.deep_percolation_mm,
        )
        results.append(result)
        if result.status != "OK" or result.storage_end_mm is None:
            return ForwardWaterResult(
                status="INSUFFICIENT_DATA",
                days=tuple(results),
                final_storage_mm=None,
                missing=tuple(f"day_{index}.{name}" for name in result.missing),
                notes=(
                    f"Stopped at H+{index} ({day.date}); later days were not projected.",
                    "No missing component was replaced by a default.",
                ),
            )
        storage = float(result.storage_end_mm)

    return ForwardWaterResult(
        status="OK",
        days=tuple(results),
        final_storage_mm=round(storage, 4),
        missing=(),
        notes=(
            "H+1 used initial storage; each subsequent day used the prior day's storage_end_mm.",
            "Precipitation input is effective rainfall supplied by the caller, not raw forecast precipitation.",
        ),
    )
