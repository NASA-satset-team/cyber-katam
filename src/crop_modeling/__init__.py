"""CYBER-KATAM crop modeling module.

Public entry points:
- CropRegistry
- et_c, seasonal_etc, daily_water_balance
- evaluate_suitability
- build_calendar, stage_for_date
- enumerate_sequences, evaluate_sequence, pareto_optimize
- TacticalCropAdvisor
"""

from .calendar import build_calendar, stage_for_date
from .models import (
    AdvisoryStatus,
    CalendarEvent,
    CalendarResult,
    CandidateMetrics,
    CandidateStatus,
    CropRecord,
    EnvironmentContext,
    EvidenceStatus,
    ForecastBundle,
    ForecastDay,
    ForwardWaterResult,
    ParameterValue,
    ParetoResult,
    RotationCandidateRecord,
    RotationEvaluation,
    SourceRecord,
    SuitabilityCheck,
    SuitabilityResult,
    SuitabilityStatus,
    TacticalAdvisory,
    UnitRecord,
    WaterDayInput,
    WaterResult,
)
from .registry import CropRegistry, RegistryValidationError
from .rotation import (
    enumerate_sequences,
    evaluate_sequence,
    generate_candidates,
    pareto_optimize,
    pareto_optimize_records,
)
from .suitability import evaluate_suitability
from .tactical import TacticalCropAdvisor
from .water import (
    daily_water_balance,
    et_c,
    forward_water_balance,
    kc_for_stage,
    seasonal_etc,
)

__all__ = [
    "AdvisoryStatus",
    "CalendarEvent",
    "CalendarResult",
    "CandidateMetrics",
    "CandidateStatus",
    "CropRecord",
    "CropRegistry",
    "EnvironmentContext",
    "EvidenceStatus",
    "ForecastBundle",
    "ForecastDay",
    "ForwardWaterResult",
    "ParameterValue",
    "ParetoResult",
    "RegistryValidationError",
    "RotationCandidateRecord",
    "RotationEvaluation",
    "SourceRecord",
    "SuitabilityCheck",
    "SuitabilityResult",
    "SuitabilityStatus",
    "TacticalAdvisory",
    "TacticalCropAdvisor",
    "UnitRecord",
    "WaterDayInput",
    "WaterResult",
    "build_calendar",
    "daily_water_balance",
    "enumerate_sequences",
    "et_c",
    "evaluate_sequence",
    "evaluate_suitability",
    "forward_water_balance",
    "generate_candidates",
    "kc_for_stage",
    "pareto_optimize",
    "pareto_optimize_records",
    "seasonal_etc",
    "stage_for_date",
]
