"""Shared data structures for the CYBER-KATAM crop modeling module.

This package is intentionally independent from the historical/weather ingestion
and final integration engine. It consumes explicit inputs and never fills a
missing value with a default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class EvidenceStatus(str, Enum):
    OBSERVED = "observed"
    STANDARD = "standard"
    PROXY = "proxy"
    DERIVED = "derived"
    MISSING = "missing"


class SuitabilityStatus(str, Enum):
    SUITABLE = "SUITABLE"
    CONDITIONALLY_SUITABLE = "CONDITIONALLY_SUITABLE"
    UNSUITABLE = "UNSUITABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class AdvisoryStatus(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    CONDITIONAL = "CONDITIONAL"
    DEFER = "DEFER"
    ABSTAIN = "ABSTAIN"


class CandidateStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    CONDITIONAL = "CONDITIONAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    type: str
    citation: str
    url: str | None
    location: str | None
    scope_note: str


@dataclass(frozen=True)
class UnitRecord:
    unit_id: str
    symbol: str
    dimension: str
    description: str


@dataclass(frozen=True)
class ParameterValue:
    """A parameter with explicit units and provenance.

    ``value is None`` is allowed only for ``MISSING``. Consumers must not
    substitute a default; they should abstain or return insufficient data.
    """

    value: Any
    unit: str
    status: EvidenceStatus
    source_id: str | None
    location: str | None = None
    product_basis: str | None = None
    time_origin: str | None = None
    required_for: tuple[str, ...] = ()
    notes: str = ""

    def is_missing(self) -> bool:
        return self.status is EvidenceStatus.MISSING or self.value is None


@dataclass(frozen=True)
class CropRecord:
    crop_id: str
    common_name: str
    scientific_name: str | None
    variety: str | None
    category: str | None
    region: str | None
    record_status: str
    parameters: Mapping[str, ParameterValue]
    identity_source_ids: tuple[str, ...] = ()

    def parameter(self, key: str) -> ParameterValue:
        if key not in self.parameters:
            raise KeyError(f"Unknown parameter '{key}' for crop '{self.crop_id}'")
        return self.parameters[key]

    def value(self, key: str) -> Any:
        """Return a verified/sourced value, or None for missing."""
        return self.parameter(key).value

    def has_value(self, key: str) -> bool:
        return not self.parameter(key).is_missing()


@dataclass(frozen=True)
class EnvironmentContext:
    """Inputs supplied by historical/spatial/integration modules."""

    cell_id: str
    soil_moisture_mm: float | None = None
    field_capacity_mm: float | None = None
    wilting_point_mm: float | None = None
    saturation_mm: float | None = None
    soil_ph: float | None = None
    slope_deg: float | None = None
    drainage_class: str | None = None
    salinity_ds_m: float | None = None
    pvrs: float | None = None
    bf_ehsi: float | None = None
    observed_at: str | None = None
    data_status: str = "UNKNOWN"


@dataclass(frozen=True)
class ForecastDay:
    date: str
    precipitation_mm: float | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    relative_humidity_pct: float | None = None
    wind_speed_mps: float | None = None
    solar_radiation_mj_m2_day: float | None = None
    eto_mm: float | None = None
    effective_rain_mm: float | None = None
    runoff_mm: float | None = None
    deep_percolation_mm: float | None = None
    missing_variables: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForecastBundle:
    provider: str
    issue_time: str
    retrieval_time: str
    valid_start: str
    valid_end: str
    days: tuple[ForecastDay, ...]
    stale: bool = False
    missing_variables: tuple[str, ...] = ()


@dataclass(frozen=True)
class WaterResult:
    status: str
    etc_mm: float | None
    irrigation_requirement_mm: float | None
    storage_end_mm: float | None
    components: Mapping[str, float | None]
    missing: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WaterDayInput:
    date: str
    etc_mm: float | None
    effective_rain_mm: float | None
    irrigation_mm: float | None
    runoff_mm: float | None
    deep_percolation_mm: float | None


@dataclass(frozen=True)
class ForwardWaterResult:
    status: str
    days: tuple[WaterResult, ...]
    final_storage_mm: float | None
    missing: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SuitabilityCheck:
    parameter: str
    observed: Any
    required: Any
    unit: str | None
    passed: bool | None
    source_id: str | None
    evidence_status: str
    note: str


@dataclass(frozen=True)
class SuitabilityResult:
    status: SuitabilityStatus
    checks: tuple[SuitabilityCheck, ...]
    missing: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CalendarEvent:
    date: str | None
    action: str
    stage: str
    status: str
    source_id: str | None
    note: str


@dataclass(frozen=True)
class CalendarResult:
    status: str
    planting_date: str | None
    events: tuple[CalendarEvent, ...]
    stage_windows: Mapping[str, tuple[str | None, str | None]]
    missing: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TacticalAdvisory:
    date: str
    action: str
    status: AdvisoryStatus
    reason: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    crop_id: str
    growth_stage: str
    cell_id: str = ""


@dataclass
class CandidateMetrics:
    non_host_duration_days: int | None = None
    water_demand_mm: float | None = None
    n_fertilizer_displaced_kg_ha: float | None = None
    soc_change_ton_ha: float | None = None
    bph_burden_index: float | None = None
    gross_revenue_idr_ha: float | None = None
    production_cost_idr_ha: float | None = None
    required_ksat_mm_day: float | None = None
    predicted_erosion_di: float | None = None

    def missing_fields(self) -> tuple[str, ...]:
        fields = (
            "non_host_duration_days",
            "water_demand_mm",
            "n_fertilizer_displaced_kg_ha",
            "soc_change_ton_ha",
            "bph_burden_index",
            "gross_revenue_idr_ha",
            "production_cost_idr_ha",
            "required_ksat_mm_day",
            "predicted_erosion_di",
        )
        return tuple(name for name in fields if getattr(self, name) is None)


@dataclass(frozen=True)
class RotationEvaluation:
    crop_sequence: tuple[str, ...]
    feasible: bool
    reasons: tuple[str, ...]
    metrics: CandidateMetrics | None
    candidate: Any | None


@dataclass(frozen=True)
class ParetoResult:
    status: str
    front: tuple[Any, ...]
    winner: Any | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RotationCandidateRecord:
    candidate_id: str
    cell_id: str
    crop_sequence: tuple[str, ...]
    season_count: int
    status: CandidateStatus
    agronomic_metrics: Mapping[str, Any]
    constraints_checked: tuple[str, ...]
    constraints_unchecked: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence: tuple[str, ...]
    data_quality: Mapping[str, Any]
    candidate_metrics: CandidateMetrics | None = None
    pareto_candidate: Any | None = None
    pareto_ready: bool = False
