"""Crop-specific tactical advisor for H+1..H+3.

The advisor consumes crop, stage, environment, and forecast inputs. It does not
fetch weather data and does not change the strategic rotation decision. Rules
use arithmetic/data comparisons; no unsourced rainfall or temperature threshold
is introduced.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from .models import (
    AdvisoryStatus,
    CropRecord,
    EnvironmentContext,
    ForecastBundle,
    ForecastDay,
    TacticalAdvisory,
    WaterDayInput,
)
from .water import et_c, forward_water_balance, kc_for_stage


def _rain_sum(forecast: ForecastBundle) -> float | None:
    values = [d.precipitation_mm for d in forecast.days]
    if not values or any(v is None for v in values):
        return None
    return float(sum(values))


def _forecast_evidence(forecast: ForecastBundle) -> tuple[str, ...]:
    return (
        f"forecast_provider={forecast.provider}",
        f"issue_time={forecast.issue_time}",
        f"retrieval_time={forecast.retrieval_time}",
        f"valid_start={forecast.valid_start}",
        f"valid_end={forecast.valid_end}",
    )


class TacticalCropAdvisor:
    def advise(
        self,
        crop: CropRecord,
        growth_stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        *,
        planting_date: str | None = None,
    ) -> tuple[TacticalAdvisory, ...]:
        stage = growth_stage.strip().lower()

        if forecast.stale:
            return (
                TacticalAdvisory(
                    date=forecast.valid_start,
                    action="FORECAST",
                    status=AdvisoryStatus.ABSTAIN,
                    reason="Forecast is stale; no tactical action can be recommended as current.",
                    evidence=_forecast_evidence(forecast),
                    limitations=("Strategic crop rotation remains separate and is not invalidated by stale forecast.",),
                    crop_id=crop.crop_id,
                    growth_stage=stage,
                    cell_id=environment.cell_id,
                ),
            )
        if not forecast.days:
            return (
                TacticalAdvisory(
                    date=forecast.valid_start,
                    action="FORECAST",
                    status=AdvisoryStatus.ABSTAIN,
                    reason="No forecast days were supplied.",
                    evidence=_forecast_evidence(forecast),
                    limitations=("No weather value was reused or defaulted.",),
                    crop_id=crop.crop_id,
                    growth_stage=stage,
                    cell_id=environment.cell_id,
                ),
            )

        actions = self._actions_for_stage(stage)
        advisories: list[TacticalAdvisory] = []
        for day in forecast.days:
            for action in actions:
                advisory = self._evaluate_action(
                    crop, stage, environment, forecast, day, action,
                    planting_date=planting_date,
                )
                advisories.append(replace(advisory, cell_id=environment.cell_id))
        return tuple(advisories)

    def advise_fallow(
        self,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        *,
        cover_crop_available: bool | None = None,
    ) -> tuple[TacticalAdvisory, ...]:
        """Evaluate fallow/cover actions from supplied BF-EHSI context only.

        The crop module does not calculate BF-EHSI. A threshold for converting
        BF-EHSI into an erosion action is not invented.
        """
        if forecast.stale:
            return (
                TacticalAdvisory(
                    date=forecast.valid_start,
                    action="FORECAST",
                    status=AdvisoryStatus.ABSTAIN,
                    reason="Forecast is stale; fallow advice cannot be treated as current.",
                    evidence=_forecast_evidence(forecast),
                    limitations=("Strategic rotation remains separate and is not invalidated.",),
                    crop_id="fallow",
                    growth_stage="fallow",
                    cell_id=environment.cell_id,
                ),
            )
        if not forecast.days:
            return (
                TacticalAdvisory(
                    date=forecast.valid_start,
                    action="FORECAST",
                    status=AdvisoryStatus.ABSTAIN,
                    reason="No forecast days were supplied.",
                    evidence=_forecast_evidence(forecast),
                    limitations=("No weather value was reused or defaulted.",),
                    crop_id="fallow",
                    growth_stage="fallow",
                    cell_id=environment.cell_id,
                ),
            )

        advisories: list[TacticalAdvisory] = []
        for day in forecast.days:
            if environment.bf_ehsi is None:
                advisories.append(
                    TacticalAdvisory(
                        date=day.date,
                        action="FALLOW",
                        status=AdvisoryStatus.ABSTAIN,
                        reason="BF-EHSI context is unavailable; erosion/cover advice cannot be quantified.",
                        evidence=_forecast_evidence(forecast),
                        limitations=("The crop module does not calculate BF-EHSI.",),
                        crop_id="fallow",
                        growth_stage="fallow",
                    )
                )
                continue
            if day.precipitation_mm is None:
                advisories.append(
                    TacticalAdvisory(
                        date=day.date,
                        action="FALLOW",
                        status=AdvisoryStatus.ABSTAIN,
                        reason="Precipitation forecast is missing.",
                        evidence=_forecast_evidence(forecast),
                        limitations=("No default precipitation was inserted.",),
                        crop_id="fallow",
                        growth_stage="fallow",
                    )
                )
                continue
            if day.precipitation_mm > 0:
                status = AdvisoryStatus.CONDITIONAL
                reason = "BF-EHSI context is supplied and rain is forecast; maintain cover and inspect erosion risk, but no approved BF-EHSI action threshold exists."
            else:
                status = AdvisoryStatus.CONDITIONAL
                reason = "BF-EHSI context is supplied and no rain is forecast; cover/erosion status requires field verification."
            limitations = ("No BF-EHSI-to-action threshold or cover-crop suitability data are defined in the registry.",)
            if cover_crop_available is False:
                limitations += ("Cover crop is reported unavailable; fallow protection cannot be recommended as an action.",)
            advisories.append(
                TacticalAdvisory(
                    date=day.date,
                    action="FALLOW",
                    status=status,
                    reason=reason,
                    evidence=_forecast_evidence(forecast) + (f"bf_ehsi={environment.bf_ehsi}",),
                    limitations=limitations,
                    crop_id="fallow",
                    growth_stage="fallow",
                )
            )
        return tuple(replace(a, cell_id=environment.cell_id) for a in advisories)

    @staticmethod
    def _actions_for_stage(stage: str) -> tuple[str, ...]:
        if stage in ("land_preparation", "planting", "seeding", "seedling"):
            return ("PLANTING", "IRRIGATION", "DRAINAGE")
        if stage in ("vegetative", "tillering", "development"):
            return ("IRRIGATION", "FERTILIZATION", "DRAINAGE")
        if stage in ("reproductive", "flowering", "grain_filling"):
            return ("IRRIGATION", "FERTILIZATION", "DRAINAGE")
        if stage in ("maturity", "harvest"):
            return ("HARVEST", "DRAINAGE")
        return ("IRRIGATION", "DRAINAGE")

    def _evaluate_action(
        self,
        crop: CropRecord,
        stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        day: ForecastDay,
        action: str,
        *,
        planting_date: str | None = None,
    ) -> TacticalAdvisory:
        if action == "PLANTING":
            return self._planting(crop, stage, environment, forecast, day)
        if action == "IRRIGATION":
            return self._irrigation(crop, stage, environment, forecast, day)
        if action == "FERTILIZATION":
            return self._fertilization(crop, stage, environment, forecast, day)
        if action == "DRAINAGE":
            return self._drainage(crop, stage, environment, forecast, day)
        if action == "HARVEST":
            return self._harvest(crop, stage, environment, forecast, day, planting_date=planting_date)
        raise ValueError(f"Unsupported action {action}")

    def _base(
        self,
        *,
        crop: CropRecord,
        stage: str,
        day: ForecastDay,
        action: str,
        status: AdvisoryStatus,
        reason: str,
        forecast: ForecastBundle,
        limitations: tuple[str, ...] = (),
        extra_evidence: tuple[str, ...] = (),
    ) -> TacticalAdvisory:
        return TacticalAdvisory(
            date=day.date,
            action=action,
            status=status,
            reason=reason,
            evidence=_forecast_evidence(forecast) + extra_evidence,
            limitations=limitations,
            crop_id=crop.crop_id,
            growth_stage=stage,
        )

    def _planting(
        self,
        crop: CropRecord,
        stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        day: ForecastDay,
    ) -> TacticalAdvisory:
        if "growing_duration_days" not in crop.parameters or crop.parameter("growing_duration_days").is_missing():
            return self._base(
                crop=crop, stage=stage, day=day, action="PLANTING",
                status=AdvisoryStatus.ABSTAIN,
                reason="Crop duration is unavailable; planting timing cannot be placed on a crop calendar.",
                forecast=forecast,
                limitations=("No duration or phase length was inferred.",),
            )
        if day.precipitation_mm is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="PLANTING",
                status=AdvisoryStatus.ABSTAIN,
                reason="Precipitation forecast is missing for this day.",
                forecast=forecast,
                limitations=("No default precipitation value was inserted.",),
            )
        if day.precipitation_mm > 0:
            return self._base(
                crop=crop, stage=stage, day=day, action="PLANTING",
                status=AdvisoryStatus.CONDITIONAL,
                reason="Rain is forecast; planting may be possible but drainage, trafficability, and seedbed risk are unresolved.",
                forecast=forecast,
                limitations=("No approved planting-after-rain threshold exists in the registry.",),
                extra_evidence=(f"precipitation_mm={day.precipitation_mm}",),
            )
        if environment.soil_moisture_mm is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="PLANTING",
                status=AdvisoryStatus.CONDITIONAL,
                reason="No rain is forecast, but soil moisture is unavailable for a planting decision.",
                forecast=forecast,
                limitations=("No soil-moisture or germination threshold is available.",),
            )
        return self._base(
            crop=crop, stage=stage, day=day, action="PLANTING",
            status=AdvisoryStatus.CONDITIONAL,
            reason="No rain is forecast and soil moisture is present, but no approved germination/trafficability threshold is available.",
            forecast=forecast,
            limitations=("Planting is not promoted to RECOMMENDED without a source-backed threshold.",),
            extra_evidence=(f"soil_moisture_mm={environment.soil_moisture_mm}",),
        )

    def _irrigation(
        self,
        crop: CropRecord,
        stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        day: ForecastDay,
    ) -> TacticalAdvisory:
        storage = environment.soil_moisture_mm
        fc = environment.field_capacity_mm
        wp = environment.wilting_point_mm
        sat = environment.saturation_mm
        if storage is None or fc is None or wp is None or sat is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="Soil storage or soil hydraulic limits are unavailable; irrigation need cannot be calculated.",
                forecast=forecast,
                limitations=("PVRS is not used as a substitute for soil moisture.",),
            )

        kc, kc_reason = kc_for_stage(crop, stage)
        if kc is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.ABSTAIN,
                reason=f"Crop/stage Kc is unavailable ({kc_reason}); irrigation cannot be crop-specific.",
                forecast=forecast,
                limitations=("No generic Kc fallback is inserted.",),
            )

        water_days: list[WaterDayInput] = []
        missing: list[str] = []
        for index, d in enumerate(forecast.days, start=1):
            if d.eto_mm is None:
                missing.append(f"day_{index}.eto_mm")
            if d.effective_rain_mm is None:
                missing.append(f"day_{index}.effective_rain_mm")
            if d.runoff_mm is None:
                missing.append(f"day_{index}.runoff_mm")
            if d.deep_percolation_mm is None:
                missing.append(f"day_{index}.deep_percolation_mm")
            if any(v is None for v in (d.eto_mm, d.effective_rain_mm, d.runoff_mm, d.deep_percolation_mm)):
                continue
            water_days.append(
                WaterDayInput(
                    date=d.date,
                    etc_mm=et_c(kc, float(d.eto_mm)),
                    effective_rain_mm=float(d.effective_rain_mm),
                    irrigation_mm=0.0,
                    runoff_mm=float(d.runoff_mm),
                    deep_percolation_mm=float(d.deep_percolation_mm),
                )
            )
        if missing or len(water_days) != len(forecast.days):
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="Sequential water balance cannot run because forecast ETo/effective rainfall/runoff/percolation is incomplete.",
                forecast=forecast,
                limitations=(
                    "Raw precipitation is not treated as effective rainfall.",
                    "No missing water-balance component was defaulted to zero.",
                ),
                extra_evidence=tuple(f"missing={m}" for m in missing),
            )

        forward = forward_water_balance(
            initial_storage_mm=float(storage),
            field_capacity_mm=float(fc),
            wilting_point_mm=float(wp),
            saturation_mm=float(sat),
            days=water_days,
        )
        if forward.status != "OK":
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="Sequential H+1..H+3 water balance could not be completed.",
                forecast=forecast,
                limitations=tuple(f"missing={m}" for m in forward.missing),
            )

        try:
            day_index = list(forecast.days).index(day)
        except ValueError:
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="Forecast day could not be mapped to a forward-balance step.",
                forecast=forecast,
            )
        day_result = forward.days[day_index]
        projected_storage = day_result.storage_end_mm
        if projected_storage is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="Forward balance did not produce a storage value for this day.",
                forecast=forecast,
            )
        deficit_after = max(0.0, float(fc) - projected_storage)
        evidence = (
            f"storage_initial_mm={round(float(storage), 2)}",
            f"storage_end_mm={round(projected_storage, 2)}",
            f"crop_etc_mm={round(float(day_result.etc_mm), 2)}",
            f"effective_rain_mm={round(float(day.effective_rain_mm), 2)}",
            f"runoff_mm={round(float(day.runoff_mm), 2)}",
            f"deep_percolation_mm={round(float(day.deep_percolation_mm), 2)}",
        )
        if deficit_after <= 0:
            return self._base(
                crop=crop, stage=stage, day=day, action="IRRIGATION",
                status=AdvisoryStatus.DEFER,
                reason="Sequential crop-water balance keeps storage at/above field capacity through this day; defer irrigation.",
                forecast=forecast,
                limitations=("Irrigation efficiency and application losses are not applied.",),
                extra_evidence=evidence,
            )
        return self._base(
            crop=crop, stage=stage, day=day, action="IRRIGATION",
            status=AdvisoryStatus.CONDITIONAL,
            reason="Sequential crop-water balance leaves a root-zone deficit; consider supplemental irrigation and field verification.",
            forecast=forecast,
            limitations=("Irrigation efficiency, application method, and local soil calibration are not applied.",),
            extra_evidence=evidence + (f"refill_deficit_mm={round(deficit_after, 2)}",),
        )

    def _fertilization(
        self,
        crop: CropRecord,
        stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        day: ForecastDay,
    ) -> TacticalAdvisory:
        if "n_requirement_kg_ha" not in crop.parameters or crop.parameter("n_requirement_kg_ha").is_missing():
            return self._base(
                crop=crop, stage=stage, day=day, action="FERTILIZATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="No verified crop N requirement is available; fertilization timing cannot be recommended.",
                forecast=forecast,
                limitations=("No default N dose or application rule was inserted.",),
            )
        if day.precipitation_mm is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="FERTILIZATION",
                status=AdvisoryStatus.ABSTAIN,
                reason="Precipitation forecast is missing.",
                forecast=forecast,
            )
        if day.precipitation_mm > 0:
            return self._base(
                crop=crop, stage=stage, day=day, action="FERTILIZATION",
                status=AdvisoryStatus.CONDITIONAL,
                reason="Rain is forecast; nutrient loss/runoff risk is present but no approved leaching threshold is available.",
                forecast=forecast,
                limitations=("No rainfall threshold for fertilization is defined in the registry.",),
                extra_evidence=(f"precipitation_mm={day.precipitation_mm}",),
            )
        return self._base(
            crop=crop, stage=stage, day=day, action="FERTILIZATION",
            status=AdvisoryStatus.RECOMMENDED,
            reason="No rain is forecast and the crop N requirement is available; stage is appropriate for fertilization.",
            forecast=forecast,
            limitations=("Application method, soil test, and loss risk are not evaluated.",),
        )

    def _drainage(
        self,
        crop: CropRecord,
        stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        day: ForecastDay,
    ) -> TacticalAdvisory:
        storage = environment.soil_moisture_mm
        saturation = environment.saturation_mm
        if storage is None or saturation is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="DRAINAGE",
                status=AdvisoryStatus.ABSTAIN,
                reason="Soil moisture or saturation is unavailable; waterlogging risk cannot be evaluated.",
                forecast=forecast,
                limitations=("Rain forecast alone is not treated as proof of waterlogging.",),
            )
        rain_sum = _rain_sum(forecast)
        if rain_sum is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="DRAINAGE",
                status=AdvisoryStatus.ABSTAIN,
                reason="One or more forecast precipitation values are missing.",
                forecast=forecast,
            )
        if storage >= saturation:
            if rain_sum > 0:
                return self._base(
                    crop=crop, stage=stage, day=day, action="DRAINAGE",
                    status=AdvisoryStatus.CONDITIONAL,
                    reason="Supplied soil storage is at/above saturation and rain is forecast; drainage attention is indicated, but local drainage capacity is not verified.",
                    forecast=forecast,
                    limitations=("No local drainage capacity, outlet condition, or approved trigger threshold is available.",),
                    extra_evidence=(f"storage_mm={storage}", f"saturation_mm={saturation}", f"three_day_rain_mm={rain_sum}"),
                )
            return self._base(
                crop=crop, stage=stage, day=day, action="DRAINAGE",
                status=AdvisoryStatus.CONDITIONAL,
                reason="Storage is at/above saturation but no rain is forecast; field drainage condition still needs verification.",
                forecast=forecast,
                limitations=("Drainage infrastructure condition is not available.",),
            )
        if rain_sum > 0:
            return self._base(
                crop=crop, stage=stage, day=day, action="DRAINAGE",
                status=AdvisoryStatus.CONDITIONAL,
                reason="Rain is forecast and soil is below saturation; monitor drainage, but waterlogging is not established.",
                forecast=forecast,
                limitations=("No drainage-class or infiltration data were supplied.",),
            )
        return self._base(
            crop=crop, stage=stage, day=day, action="DRAINAGE",
            status=AdvisoryStatus.DEFER,
            reason="No rain is forecast and supplied storage is below saturation; drainage action is not indicated by these data.",
            forecast=forecast,
        )

    def _harvest(
        self,
        crop: CropRecord,
        stage: str,
        environment: EnvironmentContext,
        forecast: ForecastBundle,
        day: ForecastDay,
        *,
        planting_date: str | None = None,
    ) -> TacticalAdvisory:
        if planting_date is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.ABSTAIN,
                reason="Planting date is unavailable; crop age/maturity cannot be checked.",
                forecast=forecast,
                limitations=("No maturity date or maturity indicator was assumed.",),
            )
        duration_p = crop.parameters.get("growing_duration_days")
        if duration_p is None or duration_p.is_missing():
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.ABSTAIN,
                reason="Crop duration is unavailable; maturity cannot be checked.",
                forecast=forecast,
            )
        if isinstance(duration_p.value, (list, tuple)):
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.CONDITIONAL,
                reason="Crop duration is a range; no single maturity date is asserted.",
                forecast=forecast,
                limitations=("Maturity indicators (grain moisture, NDVI/NBI, field check) are not supplied.",),
            )
        try:
            planted = date.fromisoformat(planting_date)
            target = planted + timedelta(days=int(float(duration_p.value)))
        except (ValueError, TypeError):
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.ABSTAIN,
                reason="Planting date/duration cannot be converted to a maturity date.",
                forecast=forecast,
            )

        try:
            candidate_day = date.fromisoformat(day.date)
        except ValueError:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.ABSTAIN,
                reason="Forecast date is not ISO-8601.",
                forecast=forecast,
            )
        if candidate_day < target:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.CONDITIONAL,
                reason=f"Forecast date is before the registry-duration maturity date ({target.isoformat()}); do not claim harvest readiness.",
                forecast=forecast,
                limitations=("Registry duration is a guide, not a maturity measurement.",),
                extra_evidence=(f"planting_date={planting_date}", f"duration_days={duration_p.value}"),
            )
        if day.precipitation_mm is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.ABSTAIN,
                reason="Precipitation forecast is missing.",
                forecast=forecast,
            )
        if day.precipitation_mm > 0:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.CONDITIONAL,
                reason="Rain is forecast after the registry-duration maturity date; harvest quality/trafficability risk is present but no approved threshold is available.",
                forecast=forecast,
                limitations=("No harvest-rain threshold or maturity indicator is defined.",),
                extra_evidence=(f"precipitation_mm={day.precipitation_mm}",),
            )
        if environment.soil_moisture_mm is None or environment.saturation_mm is None:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.CONDITIONAL,
                reason="No rain is forecast, but soil/trafficability condition is unavailable.",
                forecast=forecast,
                limitations=("Maturity is based on registry duration only; no field maturity indicator.",),
            )
        if environment.soil_moisture_mm >= environment.saturation_mm:
            return self._base(
                crop=crop, stage=stage, day=day, action="HARVEST",
                status=AdvisoryStatus.CONDITIONAL,
                reason="No rain is forecast but supplied storage is at/above saturation; trafficability is uncertain.",
                forecast=forecast,
                limitations=("Maturity is based on registry duration only; no field maturity indicator.",),
            )
        return self._base(
            crop=crop, stage=stage, day=day, action="HARVEST",
            status=AdvisoryStatus.CONDITIONAL,
            reason="Forecast date is at/after the registry-duration maturity date and no rain is forecast, but no field maturity indicator is supplied.",
            forecast=forecast,
            limitations=("Registry duration is not proof of physiological maturity; verify grain/field indicators.",),
        )
