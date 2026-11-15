"""Tests for the crop modeling module.

These tests validate software behavior and fail-closed handling. They are not
agronomic validation of the parameter values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.crop_modeling import (
    AdvisoryStatus,
    CandidateMetrics,
    CandidateStatus,
    CropRecord,
    CropRegistry,
    EnvironmentContext,
    EvidenceStatus,
    ForecastBundle,
    ForecastDay,
    ParameterValue,
    SuitabilityStatus,
    TacticalCropAdvisor,
    WaterDayInput,
    build_calendar,
    daily_water_balance,
    enumerate_sequences,
    et_c,
    evaluate_sequence,
    evaluate_suitability,
    forward_water_balance,
    generate_candidates,
    pareto_optimize,
    pareto_optimize_records,
    seasonal_etc,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "registry" / "crop_parameter_registry.json"


def pv(value, unit, status=EvidenceStatus.OBSERVED, source_id="S05_FAO56_TABLE12", **kwargs):
    return ParameterValue(
        value=value,
        unit=unit,
        status=status,
        source_id=source_id,
        **kwargs,
    )


def _make_crop(crop_id="test_crop"):
    return CropRecord(
        crop_id=crop_id,
        common_name="Test",
        scientific_name="Testus testus",
        variety="Test-1",
        category="test",
        region="Banyumas",
        record_status="test_fixture",
        parameters={
            "growing_duration_days": pv(70.0, "day", required_for=("planting_calendar",)),
            "phase_lengths_days": pv([20, 20, 20, 10], "day", required_for=("planting_calendar",)),
            "kc_initial": pv(0.5, "fraction"),
            "kc_development": pv(0.8, "fraction"),
            "kc_mid": pv(1.1, "fraction"),
            "kc_end": pv(0.6, "fraction"),
            "ph_min": pv(4.5, "pH", required_for=("suitability",)),
            "ph_max": pv(7.0, "pH", required_for=("suitability",)),
            "slope_max_deg": pv(8.0, "degree", required_for=("suitability",)),
            "drainage_classes": pv(("well", "moderate"), "enum", required_for=("suitability",)),
            "salinity_max_ds_m": pv(2.0, "dS_per_m", required_for=("suitability",)),
            "n_requirement_kg_ha": pv(100.0, "kg_per_ha", required_for=("tactical_fertilization",)),
        },
    )


def test_registry_loads_and_preserves_missing_value():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    padi = registry.crop("padi_inpari_32_hdb")
    assert padi.value("growing_duration_days") == 120
    assert padi.value("water_requirement_mm_season") is None
    assert padi.parameter("water_requirement_mm_season").status is EvidenceStatus.MISSING
    assert registry.crop("sorgum").value("growing_duration_days") is None


def test_etc():
    assert et_c(1.05, 4.6) == pytest.approx(4.83)
    with pytest.raises(ValueError):
        et_c(-1, 4.6)


def test_seasonal_etc_complete_and_missing():
    crop = _make_crop()
    result = seasonal_etc(crop, {
        "initial": 4.0,
        "development": 4.0,
        "mid": 5.0,
        "late": 4.0,
    })
    assert result.status == "OK"
    assert result.etc_mm == pytest.approx((0.5 * 4 * 20) + (0.8 * 4 * 20) + (1.1 * 5 * 20) + (0.6 * 4 * 10))

    incomplete = seasonal_etc(crop, {"initial": 4.0})
    assert incomplete.status == "INSUFFICIENT_DATA"
    assert "eto.development" in incomplete.missing


def test_daily_water_balance_and_missing():
    result = daily_water_balance(
        storage_mm=80.0,
        field_capacity_mm=100.0,
        wilting_point_mm=40.0,
        saturation_mm=120.0,
        etc_mm=5.0,
        effective_rain_mm=10.0,
        irrigation_mm=0.0,
        runoff_mm=0.0,
        deep_percolation_mm=0.0,
    )
    assert result.status == "OK"
    assert result.storage_end_mm == pytest.approx(85.0)
    assert result.irrigation_requirement_mm == pytest.approx(15.0)

    missing = daily_water_balance(
        storage_mm=None,
        field_capacity_mm=100.0,
        wilting_point_mm=40.0,
        saturation_mm=120.0,
        etc_mm=5.0,
        effective_rain_mm=10.0,
        irrigation_mm=0.0,
        runoff_mm=0.0,
        deep_percolation_mm=0.0,
    )
    assert missing.status == "INSUFFICIENT_DATA"
    assert "storage_mm" in missing.missing


def _water_day(date: str, *, etc=5.0, rain=0.0, irrigation=0.0, runoff=0.0, percolation=0.0):
    return WaterDayInput(
        date=date,
        etc_mm=etc,
        effective_rain_mm=rain,
        irrigation_mm=irrigation,
        runoff_mm=runoff,
        deep_percolation_mm=percolation,
    )


def test_forward_water_balance_uses_previous_day_storage():
    result = forward_water_balance(
        initial_storage_mm=80.0,
        field_capacity_mm=100.0,
        wilting_point_mm=40.0,
        saturation_mm=120.0,
        days=[
            _water_day("2026-11-15"),
            _water_day("2026-11-16"),
            _water_day("2026-11-17"),
        ],
    )
    assert result.status == "OK"
    assert [d.storage_end_mm for d in result.days] == pytest.approx([75.0, 70.0, 65.0])
    assert result.final_storage_mm == pytest.approx(65.0)


def test_forward_water_balance_stops_on_missing_day():
    result = forward_water_balance(
        initial_storage_mm=80.0,
        field_capacity_mm=100.0,
        wilting_point_mm=40.0,
        saturation_mm=120.0,
        days=[
            _water_day("2026-11-15", rain=10.0),
            WaterDayInput("2026-11-16", 5.0, None, 0.0, 0.0, 0.0),
            _water_day("2026-11-17", rain=10.0),
        ],
    )
    assert result.status == "INSUFFICIENT_DATA"
    assert len(result.days) == 2
    assert result.final_storage_mm is None
    assert any("day_2.effective_rain_mm" in item for item in result.missing)


def test_forward_water_balance_caps_at_saturation():
    result = forward_water_balance(
        initial_storage_mm=115.0,
        field_capacity_mm=100.0,
        wilting_point_mm=40.0,
        saturation_mm=120.0,
        days=[_water_day("2026-11-15", etc=0.0, rain=10.0)],
    )
    assert result.status == "OK"
    assert result.final_storage_mm == pytest.approx(120.0)
    assert result.days[0].components["clipping_mm"] == pytest.approx(5.0)


def test_suitability_pass_fail_and_missing():
    env = EnvironmentContext(
        cell_id="cell",
        soil_ph=6.0,
        slope_deg=5.0,
        drainage_class="well",
        salinity_ds_m=1.0,
        pvrs=0.2,
        bf_ehsi=0.1,
    )
    result = evaluate_suitability(_make_crop(), env)
    assert result.status is SuitabilityStatus.SUITABLE

    bad = evaluate_suitability(_make_crop(), EnvironmentContext(
        cell_id="cell", soil_ph=3.0, slope_deg=5.0, drainage_class="well",
        salinity_ds_m=1.0, pvrs=0.2, bf_ehsi=0.1,
    ))
    assert bad.status is SuitabilityStatus.UNSUITABLE

    missing = evaluate_suitability(_make_crop(), EnvironmentContext(cell_id="cell"))
    assert missing.status is SuitabilityStatus.INSUFFICIENT_DATA


def test_calendar():
    result = build_calendar(_make_crop(), "2026-11-20")
    assert result.status == "OK"
    assert result.stage_windows["initial"] == ("2026-11-20", "2026-12-09")
    assert result.stage_windows["late"] == ("2027-01-19", "2027-01-28")
    assert result.events[0].action == "PLANTING"
    assert result.events[-1].action == "HARVEST"

    no_dates = build_calendar(_make_crop(), None)
    assert no_dates.status == "INSUFFICIENT_DATA"


def test_calendar_completeness_for_registry_crops():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    assert build_calendar(registry.crop("padi_inpari_32_hdb"), "2026-11-20").status == "INSUFFICIENT_DATA"
    assert build_calendar(registry.crop("kacang_hijau_vima_1"), "2026-11-20").status == "INSUFFICIENT_DATA"
    assert build_calendar(registry.crop("sorgum"), "2026-11-20").status == "INSUFFICIENT_DATA"
    kedelai = build_calendar(registry.crop("kedelai_anjasmoro"), "2026-11-20")
    assert kedelai.status == "PROVISIONAL_PROXY"
    assert kedelai.stage_windows
    assert any("not a cultivar observation" in n for n in kedelai.notes)


def test_candidate_generation_and_rejection():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    sequences = enumerate_sequences(["padi_inpari_32_hdb", "kedelai_anjasmoro"], min_length=2, max_length=2)
    assert ("padi_inpari_32_hdb", "kedelai_anjasmoro") in sequences

    metrics = CandidateMetrics(
        non_host_duration_days=100,
        water_demand_mm=300.0,
        n_fertilizer_displaced_kg_ha=50.0,
        soc_change_ton_ha=0.2,
        bph_burden_index=0.1,
        gross_revenue_idr_ha=20_000_000.0,
        production_cost_idr_ha=5_000_000.0,
        required_ksat_mm_day=20.0,
        predicted_erosion_di=0.2,
    )
    evaluation = evaluate_sequence(
        registry,
        ("padi_inpari_32_hdb", "kedelai_anjasmoro"),
        metrics,
    )
    assert evaluation.feasible is True
    assert evaluation.candidate is not None
    assert evaluation.reasons == ()

    missing = evaluate_sequence(
        registry,
        ("padi_inpari_32_hdb", "kedelai_anjasmoro"),
        CandidateMetrics(),
    )
    assert missing.feasible is False
    assert any("Missing candidate metric" in r for r in missing.reasons)

    pareto = pareto_optimize([evaluation])
    assert pareto.status == "OK"
    assert pareto.winner is not None


def _test_registry():
    return CropRegistry(
        sources={},
        units={},
        crops={
            "crop_a": _make_crop("crop_a"),
            "crop_b": _make_crop("crop_b"),
        },
        schema_version="test",
        registry_version="test",
    )


def _complete_metrics():
    return CandidateMetrics(
        non_host_duration_days=100,
        water_demand_mm=300.0,
        n_fertilizer_displaced_kg_ha=50.0,
        soc_change_ton_ha=0.2,
        bph_burden_index=0.1,
        gross_revenue_idr_ha=20_000_000.0,
        production_cost_idr_ha=5_000_000.0,
        required_ksat_mm_day=20.0,
        predicted_erosion_di=0.2,
    )


def _candidate_inputs():
    eto = {crop_id: {"initial": 4.0, "development": 4.0, "mid": 5.0, "late": 4.0}
           for crop_id in ("crop_a", "crop_b")}
    metrics = {("crop_a", "crop_b"): _complete_metrics()}
    return eto, metrics


def test_generate_candidates_eligible_and_pareto_ready():
    registry = _test_registry()
    eto, metrics = _candidate_inputs()
    records = generate_candidates(
        registry,
        "cell-1",
        environment=env(
            soil_ph=6.0, slope_deg=5.0, drainage_class="well", salinity_ds_m=1.0,
            pvrs=0.2, bf_ehsi=0.1,
        ),
        crop_ids=["crop_a", "crop_b"],
        min_seasons=2,
        max_seasons=2,
        max_candidates=10,
        planting_date="2026-11-20",
        eto_by_crop_stage=eto,
        metrics_by_sequence=metrics,
    )
    record = next(r for r in records if r.crop_sequence == ("crop_a", "crop_b"))
    assert record.status is CandidateStatus.ELIGIBLE
    assert record.pareto_ready is True
    assert record.candidate_id == "cell-1:crop_a+crop_b"
    assert record.crop_sequence == ("crop_a", "crop_b")
    assert record.season_count == 2
    assert record.constraints_checked
    assert record.constraints_unchecked == ()
    assert record.rejection_reasons == ()
    assert record.agronomic_metrics["total_duration_days"] == 140.0
    assert record.pareto_candidate is not None
    assert record.evidence  # source IDs from test crop parameters
    assert record.data_quality["parameter_status_counts"]

    pareto = pareto_optimize_records(records)
    assert pareto.status == "OK"
    assert pareto.winner is not None
    assert pareto.winner.scenario_id == record.candidate_id


def test_generate_candidates_without_metrics_is_conditional_not_pareto_ready():
    registry = _test_registry()
    eto, _ = _candidate_inputs()
    records = generate_candidates(
        registry,
        "cell-2",
        environment=env(
            soil_ph=6.0, slope_deg=5.0, drainage_class="well", salinity_ds_m=1.0,
            pvrs=0.2, bf_ehsi=0.1,
        ),
        crop_ids=["crop_a", "crop_b"],
        min_seasons=2,
        max_seasons=2,
        planting_date="2026-11-20",
        eto_by_crop_stage=eto,
        metrics_by_sequence=None,
    )
    record = next(r for r in records if r.crop_sequence == ("crop_a", "crop_b"))
    assert record.status is CandidateStatus.CONDITIONAL
    assert record.pareto_ready is False
    assert record.pareto_candidate is None
    assert "pareto_metrics" in record.constraints_unchecked
    assert pareto_optimize_records(records).status == "NO_ELIGIBLE_CANDIDATE"


def test_generate_candidates_rejects_known_suitability_failure():
    registry = _test_registry()
    eto, metrics = _candidate_inputs()
    records = generate_candidates(
        registry,
        "cell-3",
        environment=env(
            soil_ph=3.0, slope_deg=5.0, drainage_class="well", salinity_ds_m=1.0,
            pvrs=0.2, bf_ehsi=0.1,
        ),
        crop_ids=["crop_a", "crop_b"],
        min_seasons=2,
        max_seasons=2,
        planting_date="2026-11-20",
        eto_by_crop_stage=eto,
        metrics_by_sequence=metrics,
    )
    record = next(r for r in records if r.crop_sequence == ("crop_a", "crop_b"))
    assert record.status is CandidateStatus.REJECTED
    assert any("suitability UNSUITABLE" in reason for reason in record.rejection_reasons)
    assert record.pareto_ready is False


def test_generate_candidates_deterministic_and_bounded():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    first = generate_candidates(registry, "cell-4", max_candidates=8)
    second = generate_candidates(registry, "cell-4", max_candidates=8)
    assert [r.candidate_id for r in first] == [r.candidate_id for r in second]
    assert len(first) <= 8
    for record in first:
        assert 2 <= record.season_count <= 3
        assert all(a != b for a, b in zip(record.crop_sequence, record.crop_sequence[1:]))
        assert record.cell_id == "cell-4"
        assert record.candidate_id.startswith("cell-4:")


def test_actual_registry_does_not_produce_false_eligible_candidates():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    records = generate_candidates(registry, "cell-6", max_candidates=20)
    assert records
    assert all(record.status is not CandidateStatus.ELIGIBLE for record in records)
    assert all(record.pareto_ready is False for record in records)


def test_generate_candidates_configurable_season_length():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    records = generate_candidates(
        registry,
        "cell-5",
        min_seasons=2,
        max_seasons=2,
        max_candidates=20,
    )
    assert records
    assert all(record.season_count == 2 for record in records)


def forecast(stale=False, rain=(0.0, 0.0, 0.0)):
    return ForecastBundle(
        provider="test",
        issue_time="2026-11-15T00:00:00Z",
        retrieval_time="2026-11-15T01:00:00Z",
        valid_start="2026-11-15",
        valid_end="2026-11-18",
        days=tuple(
            ForecastDay(
                date=f"2026-11-{15 + i}",
                precipitation_mm=rain[i],
                eto_mm=4.5,
                effective_rain_mm=rain[i],
                runoff_mm=0.0,
                deep_percolation_mm=0.0,
            )
            for i in range(3)
        ),
        stale=stale,
    )


def env(**kwargs):
    defaults = dict(
        cell_id="cell",
        soil_moisture_mm=80.0,
        field_capacity_mm=100.0,
        wilting_point_mm=40.0,
        saturation_mm=120.0,
    )
    defaults.update(kwargs)
    return EnvironmentContext(**defaults)


def test_tactical_stale_forecast_abstains():
    advisories = TacticalCropAdvisor().advise(
        _make_crop(), "planting", env(), forecast(stale=True)
    )
    assert len(advisories) == 1
    assert advisories[0].status is AdvisoryStatus.ABSTAIN
    assert advisories[0].action == "FORECAST"


def test_tactical_planting_rain_is_conditional():
    advisories = TacticalCropAdvisor().advise(
        _make_crop(), "planting", env(), forecast(rain=(5.0, 0.0, 0.0))
    )
    planting = [a for a in advisories if a.action == "PLANTING" and a.date.endswith("15")]
    assert planting[0].status is AdvisoryStatus.CONDITIONAL


def test_tactical_irrigation_defer_and_conditional():
    defer = TacticalCropAdvisor().advise(
        _make_crop(), "vegetative", env(soil_moisture_mm=80.0), forecast(rain=(15.0, 15.0, 0.0))
    )
    irrigation = [a for a in defer if a.action == "IRRIGATION"]
    assert any(a.status is AdvisoryStatus.DEFER for a in irrigation)

    conditional = TacticalCropAdvisor().advise(
        _make_crop(), "vegetative", env(soil_moisture_mm=80.0), forecast(rain=(0.0, 0.0, 0.0))
    )
    irrigation = [a for a in conditional if a.action == "IRRIGATION"]
    assert any(a.status is AdvisoryStatus.CONDITIONAL for a in irrigation)


def test_tactical_fallow_requires_bf_ehsi():
    advisor = TacticalCropAdvisor()
    absent = advisor.advise_fallow(env(bf_ehsi=None), forecast())
    assert any(a.action == "FALLOW" and a.status is AdvisoryStatus.ABSTAIN for a in absent)

    present = advisor.advise_fallow(env(bf_ehsi=0.4), forecast(rain=(5.0, 0.0, 0.0)))
    assert any(a.action == "FALLOW" and a.status is AdvisoryStatus.CONDITIONAL for a in present)


def test_tactical_missing_soil_and_missing_n_abstain():
    missing_soil = TacticalCropAdvisor().advise(
        _make_crop(), "vegetative", env(soil_moisture_mm=None, field_capacity_mm=None), forecast()
    )
    assert any(a.action == "IRRIGATION" and a.status is AdvisoryStatus.ABSTAIN for a in missing_soil)
    assert any(a.action == "DRAINAGE" and a.status is AdvisoryStatus.ABSTAIN for a in missing_soil)

    no_n_params = {
        k: v for k, v in _make_crop().parameters.items()
        if k != "n_requirement_kg_ha"
    }
    no_n = CropRecord(
        crop_id="no_n",
        common_name="No N",
        scientific_name=None,
        variety=None,
        category=None,
        region=None,
        record_status="test_fixture",
        parameters=no_n_params,
    )
    advisories = TacticalCropAdvisor().advise(no_n, "vegetative", env(), forecast())
    assert any(a.action == "FERTILIZATION" and a.status is AdvisoryStatus.ABSTAIN for a in advisories)


def test_tactical_h2_rain_and_heavy_rain_after_planting():
    h2 = TacticalCropAdvisor().advise(
        _make_crop(), "planting", env(), forecast(rain=(0.0, 10.0, 0.0))
    )
    day2 = [a for a in h2 if a.action == "PLANTING" and a.date == "2026-11-16"]
    assert day2 and day2[0].status is AdvisoryStatus.CONDITIONAL
    assert "Rain" in day2[0].reason

    heavy = TacticalCropAdvisor().advise(
        _make_crop(), "planting", env(), forecast(rain=(0.0, 30.0, 0.0))
    )
    heavy_day2 = [a for a in heavy if a.action == "PLANTING" and a.date == "2026-11-16"]
    assert heavy_day2 and heavy_day2[0].status is AdvisoryStatus.CONDITIONAL


def test_tactical_missing_forecast_values_abstain():
    missing = ForecastBundle(
        provider="test",
        issue_time="2026-11-15T00:00:00Z",
        retrieval_time="2026-11-15T01:00:00Z",
        valid_start="2026-11-15",
        valid_end="2026-11-18",
        days=(
            ForecastDay("2026-11-15", precipitation_mm=None),
            ForecastDay("2026-11-16", precipitation_mm=None),
            ForecastDay("2026-11-17", precipitation_mm=None),
        ),
    )
    advisories = TacticalCropAdvisor().advise(_make_crop(), "planting", env(), missing)
    assert any(a.action == "PLANTING" and a.status is AdvisoryStatus.ABSTAIN for a in advisories)
    assert any(a.action == "IRRIGATION" and a.status is AdvisoryStatus.ABSTAIN for a in advisories)


def test_tactical_raw_precipitation_is_not_effective_rainfall():
    raw_only = ForecastBundle(
        provider="test",
        issue_time="2026-11-15T00:00:00Z",
        retrieval_time="2026-11-15T01:00:00Z",
        valid_start="2026-11-15",
        valid_end="2026-11-18",
        days=tuple(
            ForecastDay(
                date=f"2026-11-{15 + i}",
                precipitation_mm=10.0,
                eto_mm=4.5,
                effective_rain_mm=None,
                runoff_mm=0.0,
                deep_percolation_mm=0.0,
            )
            for i in range(3)
        ),
    )
    advisories = TacticalCropAdvisor().advise(_make_crop(), "vegetative", env(), raw_only)
    irrigation = [a for a in advisories if a.action == "IRRIGATION"]
    assert irrigation and all(a.status is AdvisoryStatus.ABSTAIN for a in irrigation)
    assert all(a.cell_id == "cell" for a in advisories)


def test_tactical_drainage_without_local_threshold_is_conditional():
    advisories = TacticalCropAdvisor().advise(
        _make_crop(), "vegetative", env(soil_moisture_mm=120.0), forecast(rain=(10.0, 0.0, 0.0))
    )
    drainage = [a for a in advisories if a.action == "DRAINAGE"]
    assert any(a.status is AdvisoryStatus.CONDITIONAL for a in drainage)
    assert all(a.status is not AdvisoryStatus.RECOMMENDED for a in drainage)


def test_tactical_harvest_without_maturity_data_abstains():
    advisories = TacticalCropAdvisor().advise(
        _make_crop(), "harvest", env(), forecast()
    )
    harvest = [a for a in advisories if a.action == "HARVEST"]
    assert harvest and all(a.status is AdvisoryStatus.ABSTAIN for a in harvest)


def test_tactical_high_moisture_and_deficit():
    high = TacticalCropAdvisor().advise(
        _make_crop(), "vegetative", env(soil_moisture_mm=110.0), forecast()
    )
    assert any(a.action == "IRRIGATION" and a.status is AdvisoryStatus.DEFER for a in high)

    deficit = TacticalCropAdvisor().advise(
        _make_crop(), "vegetative", env(soil_moisture_mm=30.0), forecast()
    )
    assert any(a.action == "IRRIGATION" and a.status is AdvisoryStatus.CONDITIONAL for a in deficit)


def test_tactical_stage_actions_are_specific():
    advisor = TacticalCropAdvisor()
    vegetative = {a.action for a in advisor.advise(_make_crop(), "vegetative", env(), forecast())}
    generative = {a.action for a in advisor.advise(_make_crop(), "reproductive", env(), forecast())}
    harvest = {a.action for a in advisor.advise(_make_crop(), "harvest", env(), forecast())}
    assert {"IRRIGATION", "FERTILIZATION", "DRAINAGE"} <= vegetative
    assert {"IRRIGATION", "FERTILIZATION", "DRAINAGE"} <= generative
    assert "HARVEST" in harvest


def test_tactical_registry_crop_missing_n_abstains():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    advisories = TacticalCropAdvisor().advise(
        registry.crop("padi_inpari_32_hdb"), "vegetative", env(), forecast()
    )
    assert any(a.action == "FERTILIZATION" and a.status is AdvisoryStatus.ABSTAIN for a in advisories)


def test_interface_readiness_fields():
    f = forecast()
    a = TacticalCropAdvisor().advise(_make_crop(), "planting", env(), f)[0]
    assert f.provider and f.issue_time and f.retrieval_time and f.valid_start and f.valid_end
    assert a.date and a.action and a.status and a.reason
    assert a.evidence and a.limitations is not None
    assert a.cell_id == "cell"
    assert a.crop_id and a.growth_stage


def test_strategic_rotation_is_independent_of_forecast():
    registry = CropRegistry.from_file(REGISTRY_PATH)
    metrics = CandidateMetrics(
        non_host_duration_days=100,
        water_demand_mm=300.0,
        n_fertilizer_displaced_kg_ha=50.0,
        soc_change_ton_ha=0.2,
        bph_burden_index=0.1,
        gross_revenue_idr_ha=20_000_000.0,
        production_cost_idr_ha=5_000_000.0,
        required_ksat_mm_day=20.0,
        predicted_erosion_di=0.2,
    )
    sequence = ("padi_inpari_32_hdb", "kedelai_anjasmoro")
    first = evaluate_sequence(registry, sequence, metrics)
    # Forecast changes are tactical-only; this call has no forecast input.
    second = evaluate_sequence(registry, sequence, metrics)
    assert first.feasible == second.feasible is True
    assert first.reasons == second.reasons
    assert first.candidate.scenario_id == second.candidate.scenario_id
