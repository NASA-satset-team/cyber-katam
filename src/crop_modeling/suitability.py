"""Crop suitability evaluation from explicit environment inputs.

Only constraints present in the registry are evaluated. A missing constraint
does not become a default threshold; it becomes a missing-data reason.
"""

from __future__ import annotations

from typing import Any

from .models import (
    CropRecord,
    EnvironmentContext,
    EvidenceStatus,
    SuitabilityCheck,
    SuitabilityResult,
    SuitabilityStatus,
)


def _pass_fail(observed: Any, required: Any, op: str) -> bool:
    if op == "between":
        return required[0] <= observed <= required[1]
    if op == "max":
        return observed <= required
    if op == "min":
        return observed >= required
    if op == "in":
        return observed in required
    raise ValueError(f"Unknown operator {op}")


def evaluate_suitability(
    crop: CropRecord,
    environment: EnvironmentContext,
) -> SuitabilityResult:
    checks: list[SuitabilityCheck] = []
    missing: list[str] = []
    reasons: list[str] = []

    def add_check(
        parameter: str,
        observed: Any,
        required: Any,
        unit: str | None,
        op: str,
        *,
        source_id: str | None,
        evidence: str,
        note: str,
    ) -> None:
        if observed is None:
            missing.append(parameter)
            checks.append(
                SuitabilityCheck(
                    parameter=parameter,
                    observed=None,
                    required=required,
                    unit=unit,
                    passed=None,
                    source_id=source_id,
                    evidence_status=evidence,
                    note=f"Missing environment input: {note}",
                )
            )
            return
        if required is None:
            missing.append(parameter)
            checks.append(
                SuitabilityCheck(
                    parameter=parameter,
                    observed=observed,
                    required=None,
                    unit=unit,
                    passed=None,
                    source_id=source_id,
                    evidence_status=evidence,
                    note=f"No approved registry threshold: {note}",
                )
            )
            return
        passed = _pass_fail(observed, required, op)
        checks.append(
            SuitabilityCheck(
                parameter=parameter,
                observed=observed,
                required=required,
                unit=unit,
                passed=passed,
                source_id=source_id,
                evidence_status=evidence,
                note=note,
            )
        )
        if not passed:
            reasons.append(f"{parameter} fails required condition ({observed} vs {required} {unit or ''}).")

    # Soil pH range. Both bounds are required; an optimum point is not a range.
    if "ph_min" in crop.parameters or "ph_max" in crop.parameters:
        ph_p = crop.parameters.get("ph_min")
        ph_q = crop.parameters.get("ph_max")
        if ph_p is None or ph_q is None or ph_p.is_missing() or ph_q.is_missing():
            missing.append("ph_range")
            checks.append(
                SuitabilityCheck(
                    parameter="ph_range",
                    observed=environment.soil_ph,
                    required=None,
                    unit="pH",
                    passed=None,
                    source_id=None,
                    evidence_status="missing",
                    note="Registry has no complete approved pH range; optimum pH alone is not used.",
                )
            )
        else:
            add_check(
                "ph_range",
                environment.soil_ph,
                (float(ph_p.value), float(ph_q.value)),
                "pH",
                "between",
                source_id=ph_p.source_id,
                evidence=ph_p.status.value,
                note="Registry pH range.",
            )

    # Slope maximum.
    slope_p = crop.parameters.get("slope_max_deg")
    if slope_p is not None:
        add_check(
            "slope_max_deg",
            environment.slope_deg,
            None if slope_p.is_missing() else float(slope_p.value),
            "degree",
            "max",
            source_id=slope_p.source_id,
            evidence=slope_p.status.value,
            note="Registry slope limit.",
        )

    # Drainage class membership.
    drain_p = crop.parameters.get("drainage_classes")
    if drain_p is not None:
        add_check(
            "drainage_classes",
            environment.drainage_class,
            None if drain_p.is_missing() else tuple(drain_p.value),
            None,
            "in",
            source_id=drain_p.source_id,
            evidence=drain_p.status.value,
            note="Registry allowed drainage classes.",
        )

    # Salinity threshold.
    salt_p = crop.parameters.get("salinity_max_ds_m")
    if salt_p is not None:
        add_check(
            "salinity_max_ds_m",
            environment.salinity_ds_m,
            None if salt_p.is_missing() else float(salt_p.value),
            "dS/m",
            "max",
            source_id=salt_p.source_id,
            evidence=salt_p.status.value,
            note="Registry salinity threshold.",
        )

    # PVRS/BF-EHSI are context indicators, not suitability thresholds. They are
    # not converted into pass/fail here without an approved crop-specific rule.
    if environment.pvrs is None:
        missing.append("pvrs_context")
    if environment.bf_ehsi is None:
        missing.append("bf_ehsi_context")

    evaluated = [c for c in checks if c.passed is not None]
    failed = [c for c in evaluated if c.passed is False]
    if failed:
        status = SuitabilityStatus.UNSUITABLE
    elif not evaluated:
        status = SuitabilityStatus.INSUFFICIENT_DATA
    elif missing:
        status = SuitabilityStatus.CONDITIONALLY_SUITABLE
    else:
        status = SuitabilityStatus.SUITABLE

    if status is SuitabilityStatus.INSUFFICIENT_DATA:
        reasons.append("No crop suitability constraint could be evaluated from available inputs.")
    elif status is SuitabilityStatus.CONDITIONALLY_SUITABLE:
        reasons.append("Some constraints are missing; result is conditional, not a clean suitability claim.")

    return SuitabilityResult(
        status=status,
        checks=tuple(checks),
        missing=tuple(sorted(set(missing))),
        reasons=tuple(reasons),
    )
