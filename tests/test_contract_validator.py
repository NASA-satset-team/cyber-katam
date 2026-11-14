"""Unit tests for the provisional CYBER-KATAM grid-cell contract validator.

All payloads in this module are synthetic mock/test data. They are not NASA
observations, and they do not establish field validity.

Run with:
    python -m pytest tests/test_contract_validator.py -v
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import h3
import pytest
from jsonschema import Draft202012Validator

from src.contracts import (
    DEFAULT_SCHEMA_PATH,
    ContractValidator,
    ErrorCode,
    SchemaConfigurationError,
    load_contract_schema,
    validate_contract,
)

# Synthetic, structurally valid H3 cells. No resolution assumption is made by the
# schema; these values are used only as deterministic mock indexes.
MOCK_H3_INDEX = "898d8d654cbffff"
MOCK_H3_PARENT_RES7 = h3.cell_to_parent(MOCK_H3_INDEX, 7)
MOCK_ALT_H3_PARENT_RES7 = h3.latlng_to_cell(-7.0, 110.0, 7)

# Arya's sample contract contains this string. It matches the provisional hex
# pattern but is NOT a valid H3 cell under h3 4.1.2.
SAMPLE_INVALID_H3_INDEX = "892e42426ffffff"
INVALID_H3_HEX = "000000000000000"


def _single_error(result: Any) -> Any:
    """Assert that a result has exactly one error and return it."""

    assert result.is_valid is False
    assert result.error_count == 1
    assert len(result.errors) == 1
    return result.errors[0]


def _mock_contract() -> dict[str, Any]:
    """Return a synthetic contract that satisfies the provisional schema."""

    return {
        "contract_version": "1.0",
        "h3_index": MOCK_H3_INDEX,
        "h3_parent_res7": MOCK_H3_PARENT_RES7,
        "physical_indicators": {
            "PVRS": 0.8124,
            "BF_EHSI": 0.648,
            "SMAP_wetness": 0.1912,
            "ECOSTRESS_ESI": 0.38,
            "LST_anomaly": 2.1,
            "HLS_BSI": 0.384,
            "HLS_NDVI": 0.74,
            "GPM_rain_7d": 54.0,
            "SRTM_slope": 8.4,
        },
        "operational_flags": {
            "missing_observation": False,
            "optical_lag_days": 9,
            "erosion_alert": True,
        },
        "rotation_scenarios": [
            {
                "id": "SCENARIO_A_EXISTING",
                "crop_sequence": "Padi -> Bera -> Padi (mock)",
                "water_demand_mm": 680.0,
                "n_fertilizer_displaced_kg": 0.0,
                "soc_change_ton": -0.42,
                "bph_risk_score": 0.82,
                "net_margin_idr": 11300000.0,
            },
            {
                "id": "SCENARIO_B_OPTIMAL_LEGUME",
                "crop_sequence": "Padi -> Kedelai -> Sorghum (mock)",
                "water_demand_mm": 270.0,
                "n_fertilizer_displaced_kg": 163.0,
                "soc_change_ton": 1.25,
                "bph_risk_score": 0.04,
                "net_margin_idr": 18600000.0,
            },
            {
                "id": "SCENARIO_C_FAST_MUNGBEAN",
                "crop_sequence": "Padi -> Kacang Hijau -> Cover Crop (mock)",
                "water_demand_mm": 245.0,
                "n_fertilizer_displaced_kg": 128.0,
                "soc_change_ton": 0.88,
                "bph_risk_score": 0.06,
                "net_margin_idr": 16300000.0,
            },
        ],
        "xai_decision_block": {
            "why_suggested": "Mock explanation for a synthetic cell.",
            "multi_benefits": "Mock multi-benefit statement.",
            "information_gaps": "Mock information-gap statement.",
            "local_risks_and_gates": "Mock local risk and gate statement.",
        },
        "fiscal_metrics": {
            "urea_subsidy_saved_idr": 1467698.0,
            "cluster_h3_7_gross_saving_idr": 16144672500.0,
            "cluster_h3_7_net_saving_s_net_idr": 15224672500.0,
            "autp_risk_reduction_pct": 34.0,
        },
        "system_state": "ACTIVE_RECOMMENDATION",
    }


@pytest.fixture()
def valid_contract() -> dict[str, Any]:
    """Synthetic contract fixture (mock data, not an observation)."""

    return _mock_contract()


@pytest.fixture()
def validator() -> ContractValidator:
    """Default structural validator; provisional semantic rules are disabled."""

    return ContractValidator()


@pytest.fixture()
def semantic_validator() -> ContractValidator:
    """Validator with unratified provisional semantic rules explicitly enabled."""

    return ContractValidator(enable_provisional_semantics=True)


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------


def test_valid_contract_passes(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    result = validator.validate(valid_contract)

    assert result.is_valid is True
    assert result.error_count == 0
    assert result.errors == []
    assert result.to_dict() == {"is_valid": True, "errors": [], "error_count": 0}


def test_validator_does_not_mutate_input(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    before = copy.deepcopy(valid_contract)

    validator.validate(valid_contract)

    assert valid_contract == before


def test_optional_fields_can_be_omitted(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    del valid_contract["h3_parent_res7"]
    del valid_contract["fiscal_metrics"]["cluster_h3_7_gross_saving_idr"]
    del valid_contract["fiscal_metrics"]["cluster_h3_7_net_saving_s_net_idr"]

    result = validator.validate(valid_contract)

    assert result.is_valid is True
    assert result.error_count == 0


def test_minimum_boundary_values_are_accepted(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"].update(
        {
            "PVRS": 0.0,
            "BF_EHSI": 0.0,
            "SMAP_wetness": 0.0,
            "ECOSTRESS_ESI": 0.0,
            "LST_anomaly": -12.5,
            "HLS_BSI": -1.0,
            "HLS_NDVI": -1.0,
            "GPM_rain_7d": 0.0,
            "SRTM_slope": 0.0,
        }
    )
    valid_contract["operational_flags"]["optical_lag_days"] = 0
    valid_contract["rotation_scenarios"][0]["water_demand_mm"] = 0.0
    valid_contract["rotation_scenarios"][0]["n_fertilizer_displaced_kg"] = 0.0
    valid_contract["rotation_scenarios"][0]["bph_risk_score"] = 0.0
    valid_contract["fiscal_metrics"]["urea_subsidy_saved_idr"] = 0.0
    valid_contract["fiscal_metrics"]["autp_risk_reduction_pct"] = 0.0

    result = validator.validate(valid_contract)

    assert result.is_valid is True
    assert result.error_count == 0


def test_maximum_boundary_values_are_accepted(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"].update(
        {
            "PVRS": 1.0,
            "BF_EHSI": 2.5,
            "SMAP_wetness": 1.0,
            "ECOSTRESS_ESI": 1.0,
            "HLS_BSI": 1.0,
            "HLS_NDVI": 1.0,
            "SRTM_slope": 90.0,
        }
    )
    valid_contract["operational_flags"]["optical_lag_days"] = 14
    valid_contract["rotation_scenarios"][0]["bph_risk_score"] = 1.0
    valid_contract["fiscal_metrics"]["autp_risk_reduction_pct"] = 100.0

    result = validator.validate(valid_contract)

    assert result.is_valid is True
    assert result.error_count == 0


def test_empty_rotation_scenario_list_is_allowed_provisionally(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["rotation_scenarios"] = []

    result = validator.validate(valid_contract)

    assert result.is_valid is True


def test_json_string_input_is_accepted(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    result = validator.validate(json.dumps(valid_contract))

    assert result.is_valid is True


# ---------------------------------------------------------------------------
# Negative structural cases
# ---------------------------------------------------------------------------


def test_missing_required_top_level_field(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    del valid_contract["h3_index"]

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.REQUIRED_FIELD
    assert error.path == "/h3_index"
    assert error.validator == "required"
    assert error.layer == "schema"
    assert "h3_index" in error.message


def test_missing_required_nested_field(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    del valid_contract["operational_flags"]["optical_lag_days"]

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.REQUIRED_FIELD
    assert error.path == "/operational_flags/optical_lag_days"


def test_numeric_string_is_rejected_without_coercion(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = "0.5"

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/physical_indicators/PVRS"
    assert error.validator == "type"
    assert "number" in error.message
    assert "string" in error.message


def test_boolean_is_rejected_for_numeric_indicator(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = True

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/physical_indicators/PVRS"
    assert "boolean" in error.message


def test_boolean_is_rejected_for_integer_flag(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["operational_flags"]["optical_lag_days"] = True

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/operational_flags/optical_lag_days"


def test_value_below_minimum(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = -0.01

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.BELOW_MINIMUM
    assert error.path == "/physical_indicators/PVRS"
    assert error.validator == "minimum"


def test_value_above_maximum(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = 1.01

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.ABOVE_MAXIMUM
    assert error.path == "/physical_indicators/PVRS"
    assert error.validator == "maximum"


def test_invalid_enum_value(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["system_state"] = "UNKNOWN_STATE"

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.ENUM_MISMATCH
    assert error.path == "/system_state"
    assert error.validator == "enum"


def test_invalid_nested_object_type(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"] = []

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/physical_indicators"
    assert "object" in error.message
    assert "array" in error.message


def test_unexpected_additional_property(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["MBSI"] = 0.3

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.ADDITIONAL_PROPERTY
    assert error.path == "/physical_indicators/MBSI"
    assert error.validator == "additionalProperties"


def test_unexpected_top_level_additional_property(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["unexpected_field"] = 1

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.ADDITIONAL_PROPERTY
    assert error.path == "/unexpected_field"


def test_invalid_rotation_scenario_field_type(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["rotation_scenarios"][0]["water_demand_mm"] = "270"

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/rotation_scenarios/0/water_demand_mm"


def test_xai_block_requires_string(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["xai_decision_block"]["why_suggested"] = 123

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/xai_decision_block/why_suggested"


def test_null_indicator_is_rejected_provisionally(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = None

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.TYPE_MISMATCH
    assert error.path == "/physical_indicators/PVRS"
    assert "null" in error.message


def test_fiscal_metric_above_maximum(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["fiscal_metrics"]["autp_risk_reduction_pct"] = 100.1

    error = _single_error(validator.validate(valid_contract))

    assert error.code == ErrorCode.ABOVE_MAXIMUM
    assert error.path == "/fiscal_metrics/autp_risk_reduction_pct"


# ---------------------------------------------------------------------------
# Semantic cases (provisional rules are opt-in)
# ---------------------------------------------------------------------------


def test_invalid_h3_requires_opt_in_semantics(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["h3_index"] = SAMPLE_INVALID_H3_INDEX

    # Default validation is structural only, so an unratified H3 rule does not
    # silently become a hard failure.
    assert validator.validate(valid_contract).is_valid is True


def test_invalid_h3_detected_when_provisional_semantics_enabled(
    semantic_validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["h3_index"] = SAMPLE_INVALID_H3_INDEX

    error = _single_error(semantic_validator.validate(valid_contract))

    assert error.code == ErrorCode.H3_INVALID_INDEX
    assert error.path == "/h3_index"
    assert error.validator == "h3.is_valid_cell"
    assert error.layer == "semantic"


def test_invalid_h3_parent_detected_when_provisional_semantics_enabled(
    semantic_validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["h3_parent_res7"] = INVALID_H3_HEX

    error = _single_error(semantic_validator.validate(valid_contract))

    assert error.code == ErrorCode.H3_INVALID_PARENT_INDEX
    assert error.path == "/h3_parent_res7"


def test_h3_parent_mismatch_detected_when_provisional_semantics_enabled(
    semantic_validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["h3_parent_res7"] = MOCK_ALT_H3_PARENT_RES7

    error = _single_error(semantic_validator.validate(valid_contract))

    assert error.code == ErrorCode.H3_PARENT_MISMATCH
    assert error.path == "/h3_parent_res7"
    assert error.validator == "h3.cell_to_parent"


def test_duplicate_rotation_scenario_ids_detected_when_enabled(
    semantic_validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["rotation_scenarios"][1]["id"] = valid_contract[
        "rotation_scenarios"
    ][0]["id"]

    error = _single_error(semantic_validator.validate(valid_contract))

    assert error.code == ErrorCode.DUPLICATE_SCENARIO_ID
    assert error.path == "/rotation_scenarios/1/id"
    assert error.layer == "semantic"


def test_duplicate_rotation_scenario_ids_ignored_by_default(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["rotation_scenarios"][1]["id"] = valid_contract[
        "rotation_scenarios"
    ][0]["id"]

    assert validator.validate(valid_contract).is_valid is True


# ---------------------------------------------------------------------------
# Parsing cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", [None, "", "   ", {}, "{}"])
def test_empty_input_is_rejected(payload: Any) -> None:
    result = validate_contract(payload)

    error = _single_error(result)
    assert error.code == ErrorCode.EMPTY_INPUT
    assert error.layer == "parsing"
    assert error.path == ""


def test_malformed_json_is_rejected() -> None:
    result = validate_contract('{"h3_index": ')

    error = _single_error(result)
    assert error.code == ErrorCode.INVALID_JSON
    assert error.layer == "parsing"
    assert "line" in error.message
    assert "column" in error.message


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_literal_is_rejected(literal: str) -> None:
    result = validate_contract(f'{{"physical_indicators": {{"PVRS": {literal}}}}}')

    error = _single_error(result)
    assert error.code == ErrorCode.NON_FINITE_NUMBER
    assert error.layer == "parsing"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_python_value_is_rejected(
    value: float, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = value

    error = _single_error(validate_contract(valid_contract))

    assert error.code == ErrorCode.NON_FINITE_NUMBER
    assert error.path == "/physical_indicators/PVRS"
    assert error.layer == "parsing"


def test_overflowing_json_number_is_rejected() -> None:
    result = validate_contract('{"physical_indicators": {"PVRS": 1e999}}')

    error = _single_error(result)
    assert error.code == ErrorCode.NON_FINITE_NUMBER
    assert error.path == "/physical_indicators/PVRS"


@pytest.mark.parametrize("payload", ["[]", '"text"', "42", "null", "true"])
def test_top_level_non_object_is_rejected(payload: str) -> None:
    result = validate_contract(payload)

    error = _single_error(result)
    assert error.code == ErrorCode.ROOT_NOT_OBJECT
    assert error.layer == "parsing"


def test_unsupported_input_type_is_rejected() -> None:
    result = validate_contract(42)  # type: ignore[arg-type]

    error = _single_error(result)
    assert error.code == ErrorCode.UNSUPPORTED_INPUT_TYPE


# ---------------------------------------------------------------------------
# Determinism, error shape, and schema configuration
# ---------------------------------------------------------------------------


def test_errors_are_deterministic_and_path_sorted(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    del valid_contract["h3_index"]
    valid_contract["physical_indicators"]["PVRS"] = True
    valid_contract["system_state"] = "UNKNOWN_STATE"
    valid_contract["unexpected_field"] = 1

    first = validator.validate(valid_contract)
    second = validator.validate(valid_contract)

    assert first.to_dict() == second.to_dict()
    assert first.error_count == 4
    assert [error.path for error in first.errors] == [
        "/h3_index",
        "/physical_indicators/PVRS",
        "/system_state",
        "/unexpected_field",
    ]


def test_error_has_required_fields(
    validator: ContractValidator, valid_contract: dict[str, Any]
) -> None:
    valid_contract["physical_indicators"]["PVRS"] = -1

    error = _single_error(validator.validate(valid_contract))

    assert set(error.to_dict()) == {
        "code",
        "message",
        "path",
        "validator",
        "layer",
    }
    assert error.code
    assert error.message
    assert error.path
    assert error.validator


def test_schema_declares_draft_2020_12() -> None:
    schema = load_contract_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_schema_loads_independently_of_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    valid_contract: dict[str, Any],
) -> None:
    monkeypatch.chdir(tmp_path)

    validator = ContractValidator()

    assert DEFAULT_SCHEMA_PATH.is_absolute()
    assert validator.schema_path == DEFAULT_SCHEMA_PATH
    assert validator.validate(valid_contract).is_valid is True


def test_missing_schema_file_raises_configuration_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.schema.json"

    with pytest.raises(SchemaConfigurationError) as exc_info:
        ContractValidator(missing)

    assert exc_info.value.code == ErrorCode.SCHEMA_LOAD_ERROR


def test_malformed_schema_json_raises_configuration_error(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.schema.json"
    malformed.write_text("{", encoding="utf-8")

    with pytest.raises(SchemaConfigurationError) as exc_info:
        ContractValidator(malformed)

    assert exc_info.value.code == ErrorCode.SCHEMA_PARSE_ERROR


def test_invalid_schema_raises_configuration_error(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.schema.json"
    invalid.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": 123,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaConfigurationError) as exc_info:
        ContractValidator(invalid)

    assert exc_info.value.code == ErrorCode.SCHEMA_INVALID


def test_schema_without_draft_2020_12_declaration_is_rejected(tmp_path: Path) -> None:
    schema_without_draft = tmp_path / "no-draft.schema.json"
    schema_without_draft.write_text('{"type": "object"}', encoding="utf-8")

    with pytest.raises(SchemaConfigurationError) as exc_info:
        ContractValidator(schema_without_draft)

    assert exc_info.value.code == ErrorCode.SCHEMA_INVALID
