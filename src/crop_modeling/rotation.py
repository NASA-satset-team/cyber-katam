"""Candidate generation, agronomic constraint evaluation, and Pareto adapter.

The generator does not calculate revenue, cost, profit, AUTP, or fiscal metrics.
Those must be supplied by the integration/decision layer. Missing metrics keep a
candidate out of the final Pareto ranking.
"""

from __future__ import annotations

import itertools
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from external.aryas_workresult.fiscal_actuarial import (  # type: ignore
        CyberKatamFiscalActuarialEngine,
        RotationCandidate,
    )
except ImportError:  # pragma: no cover
    from fiscal_actuarial import (  # type: ignore
        CyberKatamFiscalActuarialEngine,
        RotationCandidate,
    )

from .calendar import build_calendar
from .models import (
    CandidateMetrics,
    CandidateStatus,
    CropRecord,
    EnvironmentContext,
    EvidenceStatus,
    ParetoResult,
    RotationCandidateRecord,
    RotationEvaluation,
    SuitabilityStatus,
)
from .registry import CropRegistry
from .suitability import evaluate_suitability
from .water import seasonal_etc

REQUIRED_METRICS = (
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

CORE_CONSTRAINTS = ("growing_duration", "suitability", "calendar")
CONDITIONAL_CONSTRAINTS = ("water_etc", "pareto_metrics")


def enumerate_sequences(
    crop_ids: Iterable[str],
    *,
    min_length: int = 2,
    max_length: int = 3,
) -> tuple[tuple[str, ...], ...]:
    """Enumerate unique, non-repeating crop sequences deterministically."""
    ids = tuple(dict.fromkeys(crop_ids))
    if min_length < 2 or max_length < min_length:
        raise ValueError("Require 2 <= min_length <= max_length")
    sequences: list[tuple[str, ...]] = []
    for length in range(min_length, max_length + 1):
        sequences.extend(itertools.permutations(ids, length))
    return tuple(sequences)


def _candidate_id(cell_id: str, sequence: Sequence[str]) -> str:
    """Stable candidate ID for the same cell and sequence."""
    return f"{cell_id}:{'+'.join(sequence)}"


def _crop_duration(crop: CropRecord) -> tuple[bool, float | None]:
    """Return (present, scalar_duration_if_any). Ranges are present but not summed."""
    p = crop.parameters.get("growing_duration_days")
    if p is None or p.is_missing():
        return False, None
    if isinstance(p.value, (list, tuple)):
        if len(p.value) == 2 and all(isinstance(v, (int, float)) for v in p.value):
            return True, None
        return False, None
    try:
        return True, float(p.value)
    except (TypeError, ValueError):
        return False, None


def _source_evidence(crops: Iterable[CropRecord]) -> tuple[str, ...]:
    source_ids: set[str] = set()
    for crop in crops:
        for parameter in crop.parameters.values():
            if parameter.source_id:
                source_ids.add(parameter.source_id)
    return tuple(sorted(source_ids))


def _quality(crops: Iterable[CropRecord]) -> dict[str, Any]:
    counts = {status.value: 0 for status in EvidenceStatus}
    missing: list[str] = []
    proxy: list[str] = []
    for crop in crops:
        for key, parameter in crop.parameters.items():
            counts[parameter.status.value] = counts.get(parameter.status.value, 0) + 1
            if parameter.status is EvidenceStatus.MISSING:
                missing.append(f"{crop.crop_id}.{key}")
            elif parameter.status is EvidenceStatus.PROXY:
                proxy.append(f"{crop.crop_id}.{key}")
    return {
        "parameter_status_counts": counts,
        "missing_parameters": tuple(missing),
        "proxy_parameters": tuple(proxy),
    }


def evaluate_sequence(
    registry: CropRegistry,
    sequence: Sequence[str],
    metrics: CandidateMetrics | None,
    *,
    candidate_id: str | None = None,
) -> RotationEvaluation:
    """Build an external RotationCandidate only when metrics are complete."""
    reasons: list[str] = []
    sequence = tuple(sequence)

    if len(sequence) < 2:
        reasons.append("A rotation must contain at least two crops/states.")
    for crop_id in sequence:
        if crop_id not in registry.crops:
            reasons.append(f"Unknown crop_id '{crop_id}'.")
            continue
        crop = registry.crop(crop_id)
        if "growing_duration_days" not in crop.parameters:
            reasons.append(f"{crop_id}: growing_duration_days missing from registry.")
        elif crop.parameter("growing_duration_days").is_missing():
            reasons.append(f"{crop_id}: growing_duration_days is null/missing.")

    if metrics is None:
        reasons.append("No CandidateMetrics supplied.")
        return RotationEvaluation(
            crop_sequence=sequence,
            feasible=False,
            reasons=tuple(reasons),
            metrics=None,
            candidate=None,
        )

    missing = metrics.missing_fields()
    reasons.extend(f"Missing candidate metric: {name}" for name in missing)

    for name in (
        "water_demand_mm",
        "n_fertilizer_displaced_kg_ha",
        "required_ksat_mm_day",
        "predicted_erosion_di",
        "gross_revenue_idr_ha",
        "production_cost_idr_ha",
    ):
        value = getattr(metrics, name)
        if value is not None and value < 0:
            reasons.append(f"{name} must be non-negative.")
    if metrics.non_host_duration_days is not None and metrics.non_host_duration_days < 0:
        reasons.append("non_host_duration_days must be non-negative.")
    if metrics.bph_burden_index is not None and not (0.0 <= metrics.bph_burden_index <= 1.0):
        reasons.append("bph_burden_index must be in [0, 1].")

    if reasons:
        return RotationEvaluation(
            crop_sequence=sequence,
            feasible=False,
            reasons=tuple(reasons),
            metrics=metrics,
            candidate=None,
        )

    candidate = RotationCandidate(
        scenario_id=candidate_id or " + ".join(sequence),
        crop_sequence=" -> ".join(sequence),
        non_host_duration_days=int(metrics.non_host_duration_days),
        water_demand_mm=float(metrics.water_demand_mm),
        n_fertilizer_displaced_kg_ha=float(metrics.n_fertilizer_displaced_kg_ha),
        soc_change_ton_ha=float(metrics.soc_change_ton_ha),
        bph_burden_index=float(metrics.bph_burden_index),
        gross_revenue_idr_ha=float(metrics.gross_revenue_idr_ha),
        production_cost_idr_ha=float(metrics.production_cost_idr_ha),
        required_ksat_mm_day=float(metrics.required_ksat_mm_day),
        predicted_erosion_di=float(metrics.predicted_erosion_di),
    )
    return RotationEvaluation(
        crop_sequence=sequence,
        feasible=True,
        reasons=(),
        metrics=metrics,
        candidate=candidate,
    )


def _evaluate_sequence_calendar(
    crops: Sequence[CropRecord],
    planting_date: str | None,
) -> tuple[str | None, list[str], list[str], dict[str, Any]]:
    """Return overall status, checked, unchecked, and per-crop calendar data."""
    checked: list[str] = []
    unchecked: list[str] = []
    per_crop: dict[str, Any] = {}
    if planting_date is None:
        unchecked.append("calendar")
        return None, checked, unchecked, per_crop

    current = planting_date
    for crop in crops:
        result = build_calendar(crop, current)
        per_crop[crop.crop_id] = {
            "status": result.status,
            "planting_date": result.planting_date,
            "stage_windows": result.stage_windows,
            "missing": result.missing,
        }
        if result.status == "OK":
            checked.append(f"calendar:{crop.crop_id}")
            if result.events:
                current = result.events[-1].date or current
        elif result.status == "PROVISIONAL_PROXY":
            unchecked.append(f"calendar:{crop.crop_id}")
            if result.events:
                current = result.events[-1].date or current
        else:
            unchecked.append(f"calendar:{crop.crop_id}")
            break
    return ("OK" if len(checked) == len(crops) else "PARTIAL"), checked, unchecked, per_crop


def generate_candidates(
    registry: CropRegistry,
    cell_id: str,
    *,
    environment: EnvironmentContext | None = None,
    crop_ids: Iterable[str] | None = None,
    min_seasons: int = 2,
    max_seasons: int = 3,
    max_candidates: int = 50,
    planting_date: str | None = None,
    eto_by_crop_stage: Mapping[str, Mapping[str, float]] | None = None,
    metrics_by_sequence: Mapping[tuple[str, ...], CandidateMetrics] | None = None,
) -> tuple[RotationCandidateRecord, ...]:
    """Generate and evaluate deterministic crop rotation candidates.

    Economic/fiscal metrics are not computed here. A candidate is ELIGIBLE only
    when all core checks and the Pareto metrics are available; otherwise it is
    CONDITIONAL or INSUFFICIENT_DATA and is not passed to the final ranking.
    """
    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    if not cell_id:
        raise ValueError("cell_id is required")

    available = tuple(crop_ids) if crop_ids is not None else tuple(registry.crops.keys())
    unknown = [crop_id for crop_id in available if crop_id not in registry.crops]
    if unknown:
        raise KeyError(f"Unknown crop_ids: {unknown}")

    sequences = enumerate_sequences(available, min_length=min_seasons, max_length=max_seasons)
    records: list[RotationCandidateRecord] = []

    for sequence in sequences[:max_candidates]:
        cid = _candidate_id(cell_id, sequence)
        crops = [registry.crop(crop_id) for crop_id in sequence]
        checked: list[str] = ["crop_exists", "season_count"]
        unchecked: list[str] = []
        rejection: list[str] = []
        limitations: list[str] = []
        metrics: dict[str, Any] = {"crops": {}, "season_count": len(sequence)}

        # Growing duration.
        total_duration = 0.0
        duration_complete = True
        duration_scalar = True
        for crop in crops:
            present, duration = _crop_duration(crop)
            metrics["crops"].setdefault(crop.crop_id, {})["growing_duration_days"] = (
                crop.parameters["growing_duration_days"].value
                if "growing_duration_days" in crop.parameters
                else None
            )
            if not present:
                duration_complete = False
                unchecked.append(f"growing_duration:{crop.crop_id}")
                limitations.append(f"{crop.crop_id}: growing_duration_days missing or invalid.")
            elif duration is None:
                duration_scalar = False
                limitations.append(f"{crop.crop_id}: growing duration is a range; total duration not summed.")
            else:
                total_duration += duration
        if duration_complete:
            checked.append("growing_duration")
            metrics["total_duration_days"] = total_duration if duration_scalar else None
        else:
            metrics["total_duration_days"] = None

        # Suitability.
        suitability_core_missing = False
        suitability_conditional = False
        for crop in crops:
            if environment is None:
                suitability_core_missing = True
                unchecked.append(f"suitability:{crop.crop_id}")
                limitations.append(f"{crop.crop_id}: environment context not provided.")
                continue
            suit = evaluate_suitability(crop, environment)
            metrics["crops"][crop.crop_id]["suitability"] = {
                "status": suit.status.value,
                "missing": suit.missing,
                "reasons": suit.reasons,
            }
            if suit.status is SuitabilityStatus.UNSUITABLE:
                rejection.append(f"{crop.crop_id}: suitability UNSUITABLE.")
            elif suit.status is SuitabilityStatus.SUITABLE:
                checked.append(f"suitability:{crop.crop_id}")
            elif suit.status is SuitabilityStatus.CONDITIONALLY_SUITABLE:
                suitability_conditional = True
                unchecked.append(f"suitability:{crop.crop_id}")
                limitations.append(f"{crop.crop_id}: suitability {suit.status.value}.")
            else:
                suitability_core_missing = True
                unchecked.append(f"suitability:{crop.crop_id}")
                limitations.append(f"{crop.crop_id}: suitability {suit.status.value}.")

        # Calendar.
        calendar_status, cal_checked, cal_unchecked, cal_data = _evaluate_sequence_calendar(crops, planting_date)
        checked.extend(cal_checked)
        unchecked.extend(cal_unchecked)
        metrics["calendar"] = cal_data
        metrics["calendar_status"] = calendar_status
        if cal_unchecked:
            limitations.append("Calendar has proxy/missing phase or planting-date data.")

        # Water ETc only when ETo-by-stage is supplied. Seasonal ETc is not irrigation demand.
        water_complete = True
        if eto_by_crop_stage is None:
            water_complete = False
            unchecked.append("water_etc")
            limitations.append("ETo-by-stage not supplied; seasonal ETc not evaluated.")
        else:
            for crop in crops:
                eto_map = eto_by_crop_stage.get(crop.crop_id)
                if eto_map is None:
                    water_complete = False
                    unchecked.append(f"water_etc:{crop.crop_id}")
                    continue
                water = seasonal_etc(crop, eto_map)
                metrics["crops"][crop.crop_id]["seasonal_etc"] = {
                    "status": water.status,
                    "etc_mm": water.etc_mm,
                    "missing": water.missing,
                }
                if water.status == "OK":
                    checked.append(f"water_etc:{crop.crop_id}")
                else:
                    water_complete = False
                    unchecked.append(f"water_etc:{crop.crop_id}")
            if water_complete:
                checked.append("water_etc")

        # Pareto metrics are supplied, never calculated here.
        candidate = None
        metrics_for_pareto = metrics_by_sequence.get(sequence) if metrics_by_sequence else None
        if metrics_for_pareto is None:
            unchecked.append("pareto_metrics")
            limitations.append("CandidateMetrics not supplied; candidate is not Pareto-ready.")
        else:
            eval_result = evaluate_sequence(registry, sequence, metrics_for_pareto, candidate_id=cid)
            if eval_result.feasible:
                candidate = eval_result.candidate
                checked.append("pareto_metrics")
            else:
                # Missing metrics are data gaps, invalid values are real rejections.
                if metrics_for_pareto.missing_fields():
                    unchecked.append("pareto_metrics")
                    limitations.extend(eval_result.reasons)
                else:
                    rejection.extend(eval_result.reasons)

        if rejection:
            status = CandidateStatus.REJECTED
        elif not duration_complete or suitability_core_missing:
            status = CandidateStatus.INSUFFICIENT_DATA
        elif suitability_conditional or any(item.startswith("calendar") for item in unchecked) or not water_complete:
            status = CandidateStatus.CONDITIONAL
        elif "pareto_metrics" in unchecked:
            status = CandidateStatus.CONDITIONAL
        else:
            status = CandidateStatus.ELIGIBLE

        # A candidate without complete Pareto metrics is never final-ranking ready.
        pareto_ready = status is CandidateStatus.ELIGIBLE and candidate is not None

        records.append(
            RotationCandidateRecord(
                candidate_id=cid,
                cell_id=cell_id,
                crop_sequence=sequence,
                season_count=len(sequence),
                status=status,
                agronomic_metrics=metrics,
                constraints_checked=tuple(dict.fromkeys(checked)),
                constraints_unchecked=tuple(dict.fromkeys(unchecked)),
                rejection_reasons=tuple(dict.fromkeys(rejection)),
                limitations=tuple(dict.fromkeys(limitations)),
                evidence=_source_evidence(crops),
                data_quality=_quality(crops),
                candidate_metrics=metrics_for_pareto,
                pareto_candidate=candidate,
                pareto_ready=pareto_ready,
            )
        )

    return tuple(records)


def pareto_optimize(
    evaluations: Iterable[RotationEvaluation],
    *,
    subsistence_income_min_idr: float = 12_000_000.0,
    available_water_supply_mm: float = 550.0,
    field_ksat_mm_day: float = 42.0,
    erosion_tolerance_max: float = 0.45,
    epsilon_1_min_soc_ton: float = 0.10,
    epsilon_2_max_bph_burden: float = 0.25,
) -> ParetoResult:
    """Reuse the existing Pareto solver; do not duplicate it."""
    evaluations = tuple(evaluations)
    feasible = [e.candidate for e in evaluations if e.feasible and e.candidate is not None]
    if not feasible:
        return ParetoResult(
            status="NO_FEASIBLE_CANDIDATE",
            front=(),
            winner=None,
            reasons=tuple(
                reason
                for e in evaluations
                for reason in e.reasons
            ) or ("No feasible candidate was supplied.",),
        )

    engine = CyberKatamFiscalActuarialEngine()
    front, winner = engine.solve_pareto_epsilon_constraint(
        list(feasible),
        subsistence_income_min_idr=subsistence_income_min_idr,
        available_water_supply_mm=available_water_supply_mm,
        field_ksat_mm_day=field_ksat_mm_day,
        erosion_tolerance_max=erosion_tolerance_max,
        epsilon_1_min_soc_ton=epsilon_1_min_soc_ton,
        epsilon_2_max_bph_burden=epsilon_2_max_bph_burden,
    )
    if winner is None:
        return ParetoResult(
            status="NO_EPSILON_QUALIFIED_CANDIDATE",
            front=tuple(front),
            winner=None,
            reasons=("Candidates were feasible but none qualified under epsilon constraints.",),
        )
    return ParetoResult(status="OK", front=tuple(front), winner=winner, reasons=())


def pareto_optimize_records(
    records: Iterable[RotationCandidateRecord],
    **kwargs: Any,
) -> ParetoResult:
    """Rank only ELIGIBLE records with complete Pareto metrics.

    Conditional/incomplete candidates are intentionally excluded from final
    ranking and remain available for evidence/limitations reporting.
    """
    records = tuple(records)
    eligible = [
        record for record in records
        if record.status is CandidateStatus.ELIGIBLE
        and record.pareto_ready
        and record.pareto_candidate is not None
        and record.candidate_metrics is not None
    ]
    if not eligible:
        return ParetoResult(
            status="NO_ELIGIBLE_CANDIDATE",
            front=(),
            winner=None,
            reasons=("No ELIGIBLE candidate with complete Pareto metrics.",),
        )
    evaluations = [
        RotationEvaluation(
            crop_sequence=record.crop_sequence,
            feasible=True,
            reasons=(),
            metrics=record.candidate_metrics,
            candidate=record.pareto_candidate,
        )
        for record in eligible
    ]
    return pareto_optimize(evaluations, **kwargs)
