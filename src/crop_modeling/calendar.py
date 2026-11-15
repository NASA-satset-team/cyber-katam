"""Crop calendar construction from explicit phase lengths and planting date."""

from __future__ import annotations

from datetime import date, timedelta

from .models import CalendarEvent, CalendarResult, CropRecord, EvidenceStatus


def build_calendar(
    crop: CropRecord,
    planting_date: str | None,
) -> CalendarResult:
    """Build stage windows and planting/harvest events.

    Missing phase lengths or planting date produce INSUFFICIENT_DATA. No
    phase length is inferred from total duration.
    """
    missing: list[str] = []
    notes: list[str] = []

    if planting_date is None:
        missing.append("planting_date")
        notes.append("A planting date is required to place stages on a calendar.")

    phase_p = crop.parameters.get("phase_lengths_days")
    if phase_p is None or phase_p.is_missing():
        missing.append("phase_lengths_days")
        notes.append("No stage lengths; total duration alone is not split into stages.")
        return CalendarResult(
            status="INSUFFICIENT_DATA",
            planting_date=planting_date,
            events=(),
            stage_windows={},
            missing=tuple(missing),
            notes=tuple(notes),
        )

    lengths = phase_p.value
    if not isinstance(lengths, (list, tuple)) or len(lengths) != 4 or any(v is None for v in lengths):
        missing.append("phase_lengths_days")
        notes.append("Phase lengths must be four non-null numeric values.")
        return CalendarResult(
            status="INSUFFICIENT_DATA",
            planting_date=planting_date,
            events=(),
            stage_windows={},
            missing=tuple(missing),
            notes=tuple(notes),
        )

    if missing:
        return CalendarResult(
            status="INSUFFICIENT_DATA",
            planting_date=planting_date,
            events=(),
            stage_windows={},
            missing=tuple(missing),
            notes=tuple(notes),
        )

    try:
        start = date.fromisoformat(planting_date)
    except ValueError:
        return CalendarResult(
            status="INSUFFICIENT_DATA",
            planting_date=planting_date,
            events=(),
            stage_windows={},
            missing=("planting_date",),
            notes=("planting_date is not ISO-8601.",),
        )

    stage_names = ("initial", "development", "mid", "late")
    cursor = start
    windows: dict[str, tuple[str | None, str | None]] = {}
    for name, length in zip(stage_names, lengths):
        stage_start = cursor
        stage_end = stage_start + timedelta(days=int(length) - 1)
        windows[name] = (stage_start.isoformat(), stage_end.isoformat())
        cursor = stage_end + timedelta(days=1)

    harvest = cursor
    events = (
        CalendarEvent(
            date=start.isoformat(),
            action="PLANTING",
            stage="initial",
            status="CONDITIONAL",
            source_id=phase_p.source_id,
            note="Calendar from registry phase lengths; agronomic planting suitability is evaluated separately.",
        ),
        CalendarEvent(
            date=harvest.isoformat(),
            action="HARVEST",
            stage="late",
            status="CONDITIONAL",
            source_id=phase_p.source_id,
            note="Harvest window from summed phase lengths; local harvest decisions require field checks.",
        ),
    )

    status = "OK" if phase_p.status is EvidenceStatus.OBSERVED else "PROVISIONAL_PROXY"
    notes = ["Calendar stage lengths are registry-sourced; their evidence status is not upgraded."]
    if status == "PROVISIONAL_PROXY":
        notes.append(f"Phase lengths have evidence status '{phase_p.status.value}', not a cultivar observation.")
    return CalendarResult(
        status=status,
        planting_date=start.isoformat(),
        events=events,
        stage_windows=windows,
        missing=(),
        notes=tuple(notes),
    )


def stage_for_date(calendar: CalendarResult, target: str) -> str | None:
    """Return the stage containing an ISO date, or None if outside the calendar."""
    try:
        day = date.fromisoformat(target)
    except ValueError:
        return None
    for stage, (start, end) in calendar.stage_windows.items():
        if start is None or end is None:
            continue
        if date.fromisoformat(start) <= day <= date.fromisoformat(end):
            return stage
    return None
